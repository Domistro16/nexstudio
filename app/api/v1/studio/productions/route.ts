import { requireSession } from "@/lib/route-auth";
import { json } from "@/lib/http";
import { getPrisma } from "@/lib/db";
export const runtime = "nodejs";
export async function GET(request: Request) {
  const auth = await requireSession(request); if (auth.response) return auth.response;
  const prisma = getPrisma()!;
  const drafts = await prisma.draft.findMany({ where: { ownerUserId: auth.session!.userId, family: { not: null }, prompt: { not: null } }, orderBy: { updatedAt: "desc" }, take: 100 });
  const ids = drafts.map((draft) => draft.id);
  const productions = ids.length ? await prisma.production.findMany({ where: { id: { in: ids }, ownerUserId: auth.session!.userId }, include: { currentVersion: true, seriesEpisode: true } }) : [];
  const byId = new Map(productions.map((production) => [production.id, production]));
  return json({ productions: drafts.map((draft) => {
    const production = byId.get(draft.id); const version = production?.currentVersion;
    return {
      id: draft.id, ownerId: draft.ownerUserId, anonymousSessionId: null, family: draft.family, videoType: draft.videoType ?? "", prompt: draft.prompt ?? "", sources: Array.isArray(draft.sources) ? draft.sources : [], duration: draft.duration, aspectRatio: draft.aspectRatio, voicePreference: draft.voicePreference, brandContext: draft.brandContext, createdAt: draft.createdAt.toISOString(), updatedAt: draft.updatedAt.toISOString(), state: production?.studioState ?? draft.studioState, title: draft.title,
      coverUrl: version?.thumbnailObjectKey ? `/api/v1/productions/${draft.id}/poster` : null,
      previewUrl: version?.previewObjectKey ? `/api/v1/productions/${draft.id}/preview` : null,
      latestOutputUrl: version?.outputObjectKey ? `/api/v1/productions/${draft.id}/output` : null,
      brandId: production?.brandId ?? null, seriesId: production?.seriesId ?? null, episodeOrdinal: production?.seriesEpisode?.episodeOrdinal ?? null,
    };
  }), fetchedAt: new Date().toISOString() }, auth.id);
}
