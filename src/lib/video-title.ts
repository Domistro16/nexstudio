import { callNexMindDetailed, parseProviderJson } from "@/lib/nexmind";
import { checkText } from "@/lib/content-guard";
import { normalizeNarration } from "@/lib/narration-text";
import { scriptProvider, scriptProviderKey } from "@/lib/studio-script-provider";

const MAX_WORDS = 8;
const MAX_CHARS = 60;
const BREAK_WORD = /^(is|are|was|were|can|could|will|would|has|have|had|does|do|helps?|makes?|means?|lets?|gives?|uses?|turns?)$/i;

export function cleanTitle(raw: unknown): string {
  const text = normalizeNarration(String(raw ?? "").split(/\r?\n/)[0] ?? "")
    .replace(/^["'“‘]+|["'”’]+$/g, "")
    .replace(/[.!?…:;,]+$/, "")
    .replace(/\s+/g, " ")
    .trim();
  const words = text.split(" ").filter(Boolean).slice(0, MAX_WORDS);
  while (words.length > 1 && words.join(" ").length > MAX_CHARS) words.pop();
  return words.join(" ").slice(0, MAX_CHARS).trim();
}

export function fallbackTitle(script: string): string {
  const first = normalizeNarration(script).split(/(?<=[.!?])\s+|\n+/).map((s) => s.trim()).find((s) => /\p{L}/u.test(s)) ?? "";
  const words = first.replace(/[^\p{L}\p{N}'’\-, ]/gu, " ").split(/\s+/).filter(Boolean);
  const verb = words.findIndex((w, i) => i > 0 && BREAK_WORD.test(w));
  const comma = words.findIndex((w) => w.endsWith(","));
  const cuts = [verb, comma >= 0 ? comma + 1 : -1, 6].filter((n) => n >= 2);
  return cleanTitle(words.slice(0, Math.min(...cuts)).join(" "));
}

async function writtenTitle(script: string): Promise<string> {
  if (!scriptProviderKey()) return "";
  const provider = scriptProvider();
  const result = await callNexMindDetailed([
    {
      role: "system",
      content: [
        "You are NexMind, NexStudio's editor. Give a narrated video a short, specific title that is drawn as the heading of the video.",
        "Return JSON only: {title: string}. 2 to 6 words, title case, no quotation marks, no emoji, no trailing punctuation.",
        "Name the subject of the narration; never use generic words like Video, Whiteboard, Explainer or Untitled.",
      ].join("\n"),
    },
    { role: "user", content: `Narration:\n${script.slice(0, 3000)}` },
  ], {
    ...provider,
    maxTokens: 400,
    timeoutMs: Math.min(provider.timeoutMs, 20_000),
    jsonSchema: {
      name: "video_title",
      schema: { type: "object", additionalProperties: false, required: ["title"], properties: { title: { type: "string", maxLength: 80 } } },
    },
  });
  return cleanTitle((parseProviderJson(result.content) as { title?: string }).title);
}

export async function chooseVideoTitle(script: string, provided?: unknown): Promise<string> {
  const given = cleanTitle(provided);
  if (given && checkText(given).ok) return given;
  const heading = /^\s*#\s+(.+)$/m.exec(script)?.[1];
  if (heading && cleanTitle(heading)) return cleanTitle(heading);
  if (!script.trim()) return "";
  const written = await writtenTitle(script).catch(() => "");
  if (written && checkText(written).ok) return written;
  return fallbackTitle(script);
}
