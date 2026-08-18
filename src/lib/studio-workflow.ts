import { getPrisma } from "./db";
import { appendStudioWorkflowEventTx, assertStudioActivityLeaseTx } from "@/studio-v1/architecture/workflow-durability";

export async function completeStudioActivity(activityId: string, workerId: string, output: Record<string, unknown>) {
  const prisma = getPrisma();
  if (!prisma) throw new Error("Persistent database required.");
  return prisma.$transaction(async (tx) => {
    const activity = await tx.studioWorkflowActivity.findUnique({ where: { id: activityId }, include: { workflowRun: true } });
    if (!activity) throw new Error("STUDIO_ACTIVITY_NOT_FOUND");
    if (activity.status === "COMPLETED") return true;
    await assertStudioActivityLeaseTx(tx, activityId, workerId);
    await tx.studioWorkflowActivity.update({
      where: { id: activityId },
      data: {
        status: "COMPLETED",
        output: output as never,
        completedAt: new Date(),
        heartbeatAt: new Date(),
        claimedBy: null,
        leaseExpiresAt: null,
      },
    });
    await appendStudioWorkflowEventTx(tx, activity.workflowRunId, "ACTIVITY_COMPLETED", {
      activityId,
      activityType: activity.activityType,
      output,
    });
    return true;
  });
}
