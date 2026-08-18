import type { Prisma } from "@/generated/prisma/client";
import { getPrisma } from "./db";
import { canonicalHash } from "@/studio-v1/architecture/hash";

type ArtifactInput={
  productionId:string;
  versionId?:string;
  schemaVersion?:string;
  projectVersion?:number;
  artifactType:string;
  status:"candidate"|"approved"|"rejected"|"superseded";
  content:unknown;
  inputs:{artifactId:string;sha256:string}[];
  createdBy:{type:"user"|"agent"|"service"|"operator";role:string;runId:string;promptVersion?:string;model?:string;userId?:string};
};

export async function saveStudioArtifactTx(tx:Prisma.TransactionClient,input:ArtifactInput){
  if(input.status==="approved"&&input.createdBy.type==="agent")throw new Error("Agents cannot approve their own artifacts.");
  const projectVersion=input.projectVersion??1;
  const contentHash=canonicalHash(input.content);
  const where={productionId_projectVersion_artifactType_contentHash:{productionId:input.productionId,projectVersion,artifactType:input.artifactType,contentHash}} as const;
  const existing=await tx.studioArtifact.findUnique({where});
  if(existing){
    if(existing.status!==input.status)throw new Error(`STUDIO_ARTIFACT_STATUS_CONFLICT:${input.artifactType}:${existing.status}->${input.status}`);
    return existing;
  }
  return tx.studioArtifact.create({data:{
    productionId:input.productionId,
    versionId:input.versionId,
    schemaVersion:input.schemaVersion??"1.0.0",
    projectVersion,
    artifactType:input.artifactType,
    status:input.status,
    content:input.content as Prisma.InputJsonValue,
    contentHash,
    inputs:input.inputs as Prisma.InputJsonValue,
    createdBy:input.createdBy as Prisma.InputJsonValue,
  }});
}

export async function saveStudioArtifact(input:ArtifactInput){
  const prisma=getPrisma();
  if(!prisma)throw new Error("Persistent database required.");
  for(let attempt=0;attempt<5;attempt+=1){
    try{return await prisma.$transaction((tx)=>saveStudioArtifactTx(tx,input),{isolationLevel:"Serializable"});}
    catch(error){
      const code=(error as {code?:string}).code;
      if(!["P2002","P2034"].includes(String(code))||attempt===4)throw error;
    }
  }
  throw new Error("STUDIO_ARTIFACT_SAVE_RETRY_EXHAUSTED");
}
