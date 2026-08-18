import { spawn } from "node:child_process";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { createHash } from "node:crypto";
import { writeObject } from "@/lib/object-storage";

export type SourceIntelligenceSegment = {
  segmentId: string;
  locator: string;
  kind: string;
  index?: number | null;
  text: string;
  sha256: string;
};

export type SourceIntelligenceRecord = {
  schema: "StudioSourceIntelligenceV1";
  status: "EXTRACTED" | "MEDIA_OR_BINARY";
  name: string;
  mimeType: string;
  documentKind: string;
  contentHash?: string;
  segmentCount?: number;
  totalExtractedChars?: number;
  segments: SourceIntelligenceSegment[];
  pageCount?: number | null;
  visualOnlyPages?: number[];
  visualEvidencePages?: number[];
  visualPreviews: Array<{ page?: number | null; locator: string; role: string; visuallyComplex?: boolean; objectKey: string; mimeType: "image/png" | "image/jpeg" | "image/webp"; sha256: string; bytes: number }>;
  visualCoverage?: "FULL" | "PARTIAL" | "NONE";
  warnings?: string[];
  provenanceLaw?: string;
};

type PythonRecord = Omit<SourceIntelligenceRecord, "visualPreviews"> & { visualPreviews?: Array<{ page?: number | null; locator?: string; role?: string; visuallyComplex?: boolean; path: string; mimeType: string; sha256: string }> };

function safePart(value:string){return value.normalize("NFKC").replace(/[^a-zA-Z0-9._-]+/g,"-").replace(/^-+|-+$/g,"").slice(0,100)||"source";}
function previewKey(userId:string,sourceId:string,index:number,mimeType:string,sha256:string){const ext=mimeType==="image/jpeg"?"jpg":mimeType==="image/webp"?"webp":"png";return `sources/${safePart(userId)}/${safePart(sourceId)}/intelligence/visual-${String(index).padStart(4,"0")}-${sha256.slice(0,16)}.${ext}`;}

async function runPython(input:Record<string,unknown>):Promise<PythonRecord>{
  const python=process.env.STUDIO_NEXMIND_P8_PYTHON_BIN?.trim()||"python3";
  const script=path.join(process.cwd(),"services","studio-source-intelligence","source_intelligence.py");
  return new Promise((resolve,reject)=>{
    const child=spawn(python,[script],{cwd:process.cwd(),env:process.env,stdio:["pipe","pipe","pipe"]});
    const stdout:Buffer[]=[];const stderr:Buffer[]=[];
    child.stdout.on("data",chunk=>stdout.push(Buffer.from(chunk)));child.stderr.on("data",chunk=>stderr.push(Buffer.from(chunk)));child.on("error",reject);
    child.on("close",code=>{
      const out=Buffer.concat(stdout).toString("utf8").trim();const err=Buffer.concat(stderr).toString("utf8").trim();
      let parsed:Record<string,unknown>={};try{parsed=JSON.parse(out);}catch{}
      if(code!==0||parsed.status==="BLOCKED")return reject(new Error(`SOURCE_INTELLIGENCE_FAILED:${String(parsed.code||code)}:${String(parsed.detail||err).slice(0,1000)}`));
      if(parsed.schema!=="StudioSourceIntelligenceV1")return reject(new Error("SOURCE_INTELLIGENCE_INVALID_RESPONSE"));
      resolve(parsed as unknown as PythonRecord);
    });
    child.stdin.end(JSON.stringify(input));
  });
}

export async function extractAndPersistSourceIntelligence(input:{
  userId:string;sourceId:string;name:string;mimeType:string;bytes:Uint8Array;
}):Promise<SourceIntelligenceRecord>{
  const dir=path.join(os.tmpdir(),`studio-source-intelligence-${input.sourceId}-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  await mkdir(dir,{recursive:true});const sourcePath=path.join(dir,"source.bin");await writeFile(sourcePath,input.bytes);
  try{
    const parsed=await runPython({path:sourcePath,outputDirectory:dir,mimeType:input.mimeType,name:input.name,sourceId:input.sourceId});
    if(parsed.contentHash&&parsed.contentHash!==createHash("sha256").update(input.bytes).digest("hex"))throw new Error("SOURCE_INTELLIGENCE_CONTENT_HASH_MISMATCH");
    const visualPreviews:SourceIntelligenceRecord["visualPreviews"]=[];
    for(const [index,preview] of (parsed.visualPreviews||[]).entries()){
      const page=preview.page==null?null:Number(preview.page);if(page!==null&&(!Number.isInteger(page)||page<1))continue;
      const mimeType=(preview.mimeType==="image/jpeg"||preview.mimeType==="image/webp")?preview.mimeType:"image/png";
      const bytes=await readFile(preview.path);const actual=createHash("sha256").update(bytes).digest("hex");
      if(actual!==preview.sha256)throw new Error(`SOURCE_INTELLIGENCE_PREVIEW_HASH_MISMATCH:${page??index+1}`);
      const objectKey=previewKey(input.userId,input.sourceId,index+1,mimeType,actual);await writeObject(objectKey,bytes,{contentType:mimeType});
      visualPreviews.push({page,locator:String(preview.locator|| (page?`page ${page}`:`visual ${index+1}`)),role:String(preview.role||"EMBEDDED_IMAGE"),visuallyComplex:Boolean(preview.visuallyComplex),objectKey,mimeType,sha256:actual,bytes:bytes.byteLength});
    }
    return {...parsed,visualPreviews} as SourceIntelligenceRecord;
  } finally {await rm(dir,{recursive:true,force:true}).catch(()=>undefined);}
}
