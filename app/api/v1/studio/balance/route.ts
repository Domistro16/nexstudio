import { requireSession } from "@/lib/route-auth";
import { json } from "@/lib/http";
import { standaloneStudioBalance } from "@/studio-v1/billing";
export const runtime = "nodejs";
export async function GET(request: Request) {
  const auth = await requireSession(request); if (auth.response) return auth.response;
  return json(await standaloneStudioBalance(auth.session!.userId), auth.id);
}
