import { getPrisma } from "@/lib/db";

export async function loadStudioProductionAuditTrail(userId:string,productionId:string){
  const prisma=getPrisma();
  if(!prisma)throw new Error("Persistent database required.");
  const production=await prisma.production.findFirst({
    where:{id:productionId,ownerUserId:userId},
    include:{
      studioProductionInputs:{orderBy:{ordinal:"asc"}},
      studioLineageSnapshots:{orderBy:[{projectVersion:"asc"},{createdAt:"asc"}]},
      studioStateTransitions:{orderBy:{sequence:"asc"}},
      versions:{orderBy:{versionNumber:"asc"}},
      studioProductionEntitlements:{orderBy:{createdAt:"asc"}},
      studioPurchaseQuotes:{orderBy:{createdAt:"asc"}},
      studioLedgerEntries:{orderBy:{createdAt:"asc"}},
      studioWorkflowRuns:{
        orderBy:{projectVersion:"asc"},
        include:{events:{orderBy:{sequence:"asc"}},activities:{orderBy:{createdAt:"asc"}}},
      },
    },
  });
  if(!production)throw new Error("PRODUCTION_NOT_FOUND");
  return production;
}
