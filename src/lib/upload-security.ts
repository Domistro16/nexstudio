import net from "node:net";
import { createHash, randomUUID } from "node:crypto";
import { env } from "./env";

export const ACCEPTED_UPLOAD_MIME = new Set([
  "application/pdf","application/vnd.openxmlformats-officedocument.wordprocessingml.document","application/vnd.openxmlformats-officedocument.presentationml.presentation","image/png","image/jpeg","image/webp","video/mp4","video/webm","audio/mpeg","audio/wav","audio/x-wav","text/plain","text/csv","application/json"
]);

export function sha256Bytes(bytes:Uint8Array){return createHash("sha256").update(bytes).digest("hex");}
export function safeUploadName(name:string){const base=name.normalize("NFKC").replace(/[\\/\0\r\n\t]+/g,"-").replace(/[^a-zA-Z0-9._ -]+/g,"-").replace(/\.{2,}/g,".").trim();return (base||"upload").slice(0,180);}
export function quarantineObjectKey(userId:string,name:string){return `quarantine/${userId}/${new Date().toISOString().slice(0,10)}/${randomUUID()}-${safeUploadName(name)}`;}
export function finalSourceObjectKey(userId:string,sourceId:string,name:string){return `sources/${userId}/${sourceId}/${safeUploadName(name)}`;}

export function detectMime(bytes:Uint8Array,declared?:string|null){
  const b=Buffer.from(bytes);
  if(b.length>=8&&b.subarray(0,8).equals(Buffer.from([0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a])))return"image/png";
  if(b.length>=3&&b[0]===0xff&&b[1]===0xd8&&b[2]===0xff)return"image/jpeg";
  if(b.length>=12&&b.toString("ascii",0,4)==="RIFF"&&b.toString("ascii",8,12)==="WEBP")return"image/webp";
  if(b.length>=5&&b.toString("ascii",0,5)==="%PDF-")return"application/pdf";
  if(b.length>=4&&b[0]===0x50&&b[1]===0x4b&&(b[2]===0x03||b[2]===0x05||b[2]===0x07)&&(b[3]===0x04||b[3]===0x06||b[3]===0x08)){
    // OOXML member names are stored in the ZIP directory and can be identified
    // without decompressing attacker-controlled content merely to detect type.
    if(b.indexOf(Buffer.from("word/document.xml"))>=0)return"application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    if(b.indexOf(Buffer.from("ppt/slides/slide1.xml"))>=0||b.indexOf(Buffer.from("ppt/presentation.xml"))>=0)return"application/vnd.openxmlformats-officedocument.presentationml.presentation";
  }
  if(b.length>=12&&b.toString("ascii",4,8)==="ftyp")return"video/mp4";
  if(b.length>=4&&b[0]===0x1a&&b[1]===0x45&&b[2]===0xdf&&b[3]===0xa3)return"video/webm";
  if(b.length>=3&&b.toString("ascii",0,3)==="ID3")return"audio/mpeg";
  if(b.length>=12&&b.toString("ascii",0,4)==="RIFF"&&b.toString("ascii",8,12)==="WAVE")return"audio/wav";
  if(b.length>=2&&b[0]===0xff&&(b[1]&0xe0)===0xe0)return"audio/mpeg";
  if(b.includes(0))return"application/octet-stream";
  const asText=b.subarray(0,Math.min(b.length,65536)).toString("utf8");
  if(declared==="application/json"){try{JSON.parse(b.toString("utf8"));return"application/json";}catch{return"text/plain";}}
  if(declared==="text/csv")return"text/csv";
  if(!asText.includes("\ufffd"))return"text/plain";
  return"application/octet-stream";
}

export function inspectUpload(bytes:Uint8Array,declaredMime:string|null|undefined){
  if(bytes.byteLength<1)throw new Error("UPLOAD_EMPTY");if(bytes.byteLength>env.uploadMaxBytes)throw new Error("UPLOAD_TOO_LARGE");
  const detected=detectMime(bytes,declaredMime);if(!ACCEPTED_UPLOAD_MIME.has(detected))throw new Error("UPLOAD_TYPE_NOT_ALLOWED");
  if(declaredMime&&declaredMime!=="application/octet-stream"&&!new Set([declaredMime,declaredMime==="audio/x-wav"?"audio/wav":""]).has(detected))throw new Error("UPLOAD_MIME_MISMATCH");
  if(detected==="application/pdf"){
    const text=Buffer.from(bytes).toString("latin1");
    if(/\/(JavaScript|JS|OpenAction|Launch|EmbeddedFile|RichMedia|XFA)\b/i.test(text))throw new Error("UPLOAD_PDF_ACTIVE_CONTENT_BLOCKED");
    if((text.match(/\/ObjStm\b/g)||[]).length>10000)throw new Error("UPLOAD_PDF_COMPLEXITY_BLOCKED");
  }
  if(detected.startsWith("application/vnd.openxmlformats-officedocument.")){
    const text=Buffer.from(bytes).toString("latin1");
    if(/vbaProject\.bin|\/embeddings\/|oleObject|externalLink/i.test(text))throw new Error("UPLOAD_OOXML_ACTIVE_OR_EMBEDDED_CONTENT_BLOCKED");
  }
  return{detectedMime:detected,contentHash:sha256Bytes(bytes)};
}

export async function clamAvScan(bytes:Uint8Array){
  if(!env.clamavHost)return{available:false as const,clean:false as const,detail:"CLAMAV_NOT_CONFIGURED"};
  return new Promise<{available:true;clean:boolean;detail:string}>((resolve,reject)=>{
    const socket=net.createConnection({host:env.clamavHost,port:env.clamavPort});const chunks:Buffer[]=[];const timeout=setTimeout(()=>{socket.destroy();reject(new Error("CLAMAV_TIMEOUT"));},30000);
    socket.on("connect",()=>{socket.write(Buffer.from("zINSTREAM\0"));const data=Buffer.from(bytes);for(let offset=0;offset<data.length;offset+=64*1024){const chunk=data.subarray(offset,Math.min(data.length,offset+64*1024));const size=Buffer.alloc(4);size.writeUInt32BE(chunk.length);socket.write(size);socket.write(chunk);}socket.write(Buffer.alloc(4));});
    socket.on("data",c=>chunks.push(Buffer.from(c)));socket.on("error",e=>{clearTimeout(timeout);reject(e);});socket.on("close",()=>{clearTimeout(timeout);const detail=Buffer.concat(chunks).toString("utf8").replace(/\0/g,"").trim();resolve({available:true,clean:/\bOK$/i.test(detail),detail:detail.slice(0,500)||"CLAMAV_EMPTY_RESPONSE"});});
  });
}
