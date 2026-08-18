import { spawn } from "node:child_process";
import { mkdir, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { readObject } from "@/lib/object-storage";

type Source = { id?: unknown; kind?: unknown; label?: unknown; reference?: unknown; mimeType?: unknown };
export type StudioReferenceLanguageEvidence = {
  schema: "StudioReferenceLanguageEvidenceV1";
  profile: Record<string, unknown>;
  styleHint: string;
  sourceName: string;
};
function record(value: unknown): Record<string, unknown> { return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {}; }
async function runAnalyzer(input: Record<string, unknown>): Promise<StudioReferenceLanguageEvidence> {
  const python=process.env.STUDIO_NEXMIND_P8_PYTHON_BIN?.trim()||"python3";
  const script=path.join(process.cwd(),"services","studio-nexmind-p8","reference_language.py");
  return new Promise((resolve,reject)=>{
    const child=spawn(python,[script],{cwd:process.cwd(),env:process.env,stdio:["pipe","pipe","pipe"]}); const out:Buffer[]=[];const err:Buffer[]=[];
    child.stdout.on("data",x=>out.push(Buffer.from(x)));child.stderr.on("data",x=>err.push(Buffer.from(x)));child.on("error",reject);
    child.on("close",code=>{const stdout=Buffer.concat(out).toString("utf8").trim();const stderr=Buffer.concat(err).toString("utf8").trim();if(code!==0)return reject(new Error(`REFERENCE_LANGUAGE_ANALYZER_EXIT_${code}:${stdout.slice(0,500)}:${stderr.slice(0,300)}`));try{const parsed=JSON.parse(stdout) as StudioReferenceLanguageEvidence;if(parsed.schema!=="StudioReferenceLanguageEvidenceV1"||!parsed.profile)throw new Error("invalid analyzer response");resolve(parsed);}catch(error){reject(new Error(`REFERENCE_LANGUAGE_ANALYZER_INVALID:${error instanceof Error?error.message:String(error)}`));}}); child.stdin.end(JSON.stringify(input));
  });
}
export async function analyzeStandaloneReferenceLanguage(rawSources: unknown): Promise<StudioReferenceLanguageEvidence | null> {
  const sources=Array.isArray(rawSources)?rawSources.map(record):[];
  const source=sources.find((item)=>{const kind=String(item.kind||"");const mime=String(item.mimeType||"");return (kind==="UPLOAD"||kind==="LIBRARY")&&(mime.startsWith("video/")||mime.startsWith("image/"))&&typeof item.reference==="string";});
  if(!source)return null;
  const reference=String(source.reference);const mimeType=String(source.mimeType);const name=String(source.label||path.basename(reference));const bytes=await readObject(reference);const dir=path.join(os.tmpdir(),`studio-reference-language-${Date.now()}-${Math.random().toString(16).slice(2)}`);await mkdir(dir,{recursive:true});
  const ext=mimeType.startsWith("video/")?(mimeType.includes("quicktime")?"mov":"mp4"):(mimeType.includes("png")?"png":"jpg");const target=path.join(dir,`reference.${ext}`);
  try{await writeFile(target,bytes);return await runAnalyzer({path:target,mimeType,assetId:String(source.id||"reference-1"),name});}finally{await rm(dir,{recursive:true,force:true}).catch(()=>undefined);}
}
