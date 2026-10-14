import { z } from "zod";
import { callNexMindDetailed, parseProviderJson } from "@/lib/nexmind";
import { consumeRateLimit, requestIpHash } from "@/lib/rate-limit";
import { requireTrustedOrigin } from "@/lib/route-auth";
import { json, problem, requestId, zodProblem } from "@/lib/http";
import { scriptProvider, scriptProviderKey } from "@/lib/studio-script-provider";
import { checkScriptLines, checkText } from "@/lib/content-guard";
import { writeLocalScript } from "@/lib/studio-script-local";
import { normalizeNarration } from "@/lib/narration-text";

export const runtime = "nodejs";

const inputSchema = z.object({
  brief: z.string().trim().min(8).max(4000),
  family: z.string().trim().min(1).max(40),
  videoType: z.string().trim().min(1).max(80),
  duration: z.number().int().min(5).max(600),
  beats: z.array(z.object({ purposeTitle: z.string().max(120), description: z.string().max(400) })).max(12).optional(),
}).strict();

const outputSchema = {
  type: "object", additionalProperties: false, required: ["lines"],
  properties: {
    lines: { type: "array", minItems: 2, maxItems: 24, items: { type: "string", minLength: 3, maxLength: 220 } },
    title: { type: "string", maxLength: 80 },
  },
} as const;

const POLICY = [
  "NexStudio content policy. The narration script must comply with all of it:",
  "- No vulgar or profane language of any kind.",
  "- No attacks on government officials, politicians, or public figures. No claims that they are corrupt, criminal, evil, or should be harmed, arrested, or removed.",
  "- No promotion, instruction, or glorification of crime, weapons, drugs, hacking, fraud, or evasion.",
  "- No hate or dehumanization of any group (race, religion, nationality, gender, orientation).",
  "- No sexual content, and absolutely none involving minors.",
  "- No self-harm instructions or encouragement.",
  "- No extremist praise or recruitment.",
  "- No medical, legal, or financial claims presented as guarantees; keep advice general.",
  "- No copyrighted text (lyrics, poems, book passages); write original narration.",
  "If the brief asks for content that breaks this policy, do not write a script. The caller treats that as a refusal.",
].join("\n");

async function writeScript(brief: string, family: string, videoType: string, duration: number, beats: { purposeTitle: string; description: string }[] | undefined, extraInstruction?: string) {
  const provider = scriptProvider();
  const beatHint = beats?.length
    ? `\nDirection beats to cover (one line per beat, same order):\n${beats.map((b, i) => `${i + 1}. ${b.purposeTitle}: ${b.description}`).join("\n")}`
    : "";
  const words = Math.max(12, Math.round(duration * 2.4));
  const result = await callNexMindDetailed([
    {
      role: "system",
      content: [
        "You are NexMind, NexStudio's narration scriptwriter. Turn a customer brief into a spoken-narration script for a short video.",
        `This video: family=${family}, type=${videoType}, target ${duration}s (about ${words} words total).`,
        "Return JSON only: {lines: string[], title: string}. One narration line per board beat; each line is a single complete spoken sentence (max ~30 words), in a warm, clear voiceover register.",
        "Lines are read verbatim by text-to-speech and shown one board at a time. No headings, no scene directions, no markdown, no quotation marks, no speaker labels.",
        "Title is a short work title for the dashboard (max 8 words).",
        POLICY,
        extraInstruction ?? "",
      ].filter(Boolean).join("\n"),
    },
    { role: "user", content: `Customer brief: ${brief}${beatHint}` },
  ], {
    ...provider,
    maxTokens: 900,
    jsonSchema: { name: "studio_script", schema: outputSchema as unknown as Record<string, unknown> },
  });
  return parseProviderJson(result.content) as { lines?: string[]; title?: string; refused?: boolean; reason?: string };
}

export async function POST(request: Request) {
  const id = requestId(request);
  const origin = requireTrustedOrigin(request, id); if (origin) return origin;
  const parsed = inputSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return zodProblem(id, parsed.error);
  const { brief, family, videoType, duration, beats } = parsed.data;

  const limit = await consumeRateLimit(requestIpHash(request), "studio_script_ip", 20, 60 * 60_000);
  if (!limit.allowed) return problem(id, 429, "SCRIPT_RATE_LIMITED", "Script generation temporarily unavailable", `Try again in ${limit.retryAfterSeconds} seconds.`);

  // Guard the input itself — an unsafe brief is refused before the provider runs.
  const briefCheck = checkText(brief);
  if (!briefCheck.ok) {
    return problem(id, 422, "BRIEF_NOT_ALLOWED", "This brief can't be produced", `Remove this content and try again: ${briefCheck.flagged[0] ?? "flagged content"}.`);
  }

  // No provider key in this environment → deterministic local writer.
  // The local path still passes the same output guard before anything is shown.
  if (!scriptProviderKey()) {
    const local = writeLocalScript(brief, duration, beats);
    const guard = checkScriptLines(local.lines);
    if (!guard.ok) {
      return problem(id, 422, "SCRIPT_NOT_ALLOWED", "NexMind couldn't write a safe script for this brief", "Rephrase the brief and try again.");
    }
    if (!local.lines.length) return problem(id, 503, "SCRIPT_EMPTY", "Script generation returned nothing", "Try again.");
    return json({ status: "ready", source: "local", script: local.lines.join("\n"), lines: local.lines, title: local.title }, id);
  }

  try {
    let out = await writeScript(brief, family, videoType, duration, beats);
    let lines = (out.lines ?? []).map((l) => normalizeNarration(l)).filter(Boolean);
    let guard = checkScriptLines(lines);
    if (!guard.ok) {
      // One retry with the flagged content removed; if it still fails, refuse.
      out = await writeScript(brief, family, videoType, duration, beats,
        `Your previous draft contained disallowed content (${guard.categories.join(", ")}): "${guard.flagged[0]}". Rewrite it cleanly.`);
      lines = (out.lines ?? []).map((l) => normalizeNarration(l)).filter(Boolean);
      guard = checkScriptLines(lines);
      if (!guard.ok) {
        return problem(id, 422, "SCRIPT_NOT_ALLOWED", "NexMind couldn't write a safe script for this brief", "Rephrase the brief and try again.");
      }
    }
    if (lines.length < 2) return problem(id, 503, "SCRIPT_EMPTY", "Script generation returned nothing", "Try again.");
    return json({ status: "ready", source: "nexmind", script: lines.join("\n"), lines, title: (out.title ?? "").trim() || null }, id);
  } catch {
    return problem(id, 503, "SCRIPT_UNAVAILABLE", "Script generation unavailable", "Choose Script mode to paste your own narration, or try again later.");
  }
}
