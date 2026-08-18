import { requireSession } from "@/lib/route-auth";
import { json } from "@/lib/http";
import { standaloneBillingHistory } from "@/studio-v1/billing";
export const runtime = "nodejs";
export async function GET(request: Request) {
  const auth = await requireSession(request); if (auth.response) return auth.response;
  return json({ entries: await standaloneBillingHistory(auth.session!.userId), nextCursor: null }, auth.id);
}
