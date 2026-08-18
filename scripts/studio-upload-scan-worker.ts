import type { Prisma } from "../src/generated/prisma/client";
import { getPrisma } from "../src/lib/db";
import { deleteObject, readObject, writeObject } from "../src/lib/object-storage";
import { clamAvScan, finalSourceObjectKey, inspectUpload } from "../src/lib/upload-security";
import { extractAndPersistSourceIntelligence } from "../src/studio-v1/source-intelligence/extract";

async function scanOne(){
  const prisma=getPrisma();if(!prisma)throw new Error("DATABASE_REQUIRED");
  const job=await prisma.uploadScanJob.findFirst({where:{status:"QUEUED"},orderBy:{createdAt:"asc"},include:{source:true}});if(!job)return false;
  const claim=await prisma.uploadScanJob.updateMany({where:{id:job.id,status:"QUEUED"},data:{status:"RUNNING",attempts:{increment:1},claimedAt:new Date()}});if(claim.count!==1)return true;
  try{
    if(!job.source.quarantineObjectKey)throw new Error("QUARANTINE_OBJECT_MISSING");
    const bytes=await readObject(job.source.quarantineObjectKey);const structural=inspectUpload(bytes,job.source.mimeType);const scan=await clamAvScan(bytes);
    if(!scan.available)throw new Error("CLAMAV_NOT_CONFIGURED");
    if(!scan.clean){await prisma.$transaction([prisma.uploadScanJob.update({where:{id:job.id},data:{status:"BLOCKED",verdict:"MALWARE",detail:scan.detail,completedAt:new Date()}}),prisma.source.update({where:{id:job.sourceId},data:{status:"BLOCKED",securityStatus:"BLOCKED"}})]);return true;}
    // Understand clean bytes before publishing them as READY. Failure leaves the\n    // quarantine object intact so the durable scan job can retry safely.\n    const extracted=await extractAndPersistSourceIntelligence({userId:job.source.ownerUserId,sourceId:job.source.id,name:job.source.name||"upload",mimeType:structural.detectedMime,bytes});
    const finalKey=finalSourceObjectKey(job.source.ownerUserId,job.source.id,job.source.name||"upload");
    await writeObject(finalKey,bytes,{contentType:structural.detectedMime});await deleteObject(job.source.quarantineObjectKey);
    await prisma.$transaction([
      prisma.uploadScanJob.update({where:{id:job.id},data:{status:"CLEAN",verdict:"CLEAN",detail:scan.detail,completedAt:new Date()}}),
      prisma.source.update({where:{id:job.sourceId},data:{objectKey:finalKey,quarantineObjectKey:null,status:"READY",securityStatus:"CLEAN",detectedMimeType:structural.detectedMime,contentHash:structural.contentHash,extracted:extracted as unknown as Prisma.InputJsonValue}}),
    ]);return true;
  }catch(error){
    const reason=error instanceof Error?error.message:"SCAN_FAILED";const attempts=job.attempts+1;
    await prisma.uploadScanJob.update({where:{id:job.id},data:{status:attempts>=3?"FAILED":"QUEUED",detail:reason,completedAt:attempts>=3?new Date():null}});
    if(attempts>=3)await prisma.source.update({where:{id:job.sourceId},data:{status:"FAILED",securityStatus:reason.startsWith("SOURCE_INTELLIGENCE_")?"SOURCE_INTELLIGENCE_FAILED":"SCAN_FAILED"}});
    return true;
  }
}
(async()=>{while(await scanOne()){}process.exit(0);})().catch(error=>{console.error(error);process.exit(1);});
