import { spawn } from "node:child_process";
import path from "node:path";
import { nexMindP8Phases, nexMindP8ResultSchema, type NexMindP8Result, type NexMindProgress, type StudioNexMindP8BridgeRequest } from "./contract";

export type StudioNexMindP8BridgeMode = "disabled" | "process" | "http";

type ProgressHandler = (event: NexMindProgress) => void | Promise<void>;

function bridgeMode(): StudioNexMindP8BridgeMode {
  const value = (process.env.STUDIO_NEXMIND_P8_BRIDGE_MODE || "disabled").trim().toLowerCase();
  if (value === "process" || value === "http" || value === "disabled") return value;
  throw new Error(`Invalid STUDIO_NEXMIND_P8_BRIDGE_MODE: ${value}`);
}

function timeoutMs() {
  const parsed = Number(process.env.STUDIO_NEXMIND_P8_TIMEOUT_MS || 15 * 60_000);
  return Number.isFinite(parsed) ? Math.max(10_000, Math.min(parsed, 30 * 60_000)) : 15 * 60_000;
}

function disabledResult(code = "STUDIO_NEXMIND_P8_BRIDGE_DISABLED"): NexMindP8Result {
  return { schema: "StudioNexMindP8ResultV1", status: "PROVIDER_UNAVAILABLE", code, detail: "The paid NexMind bridge is not configured on this server." };
}

async function processBridge(request: StudioNexMindP8BridgeRequest, onProgress?: ProgressHandler): Promise<NexMindP8Result> {
  const python = process.env.STUDIO_NEXMIND_P8_PYTHON_BIN?.trim() || "python3";
  const worker = path.join(process.cwd(), "services", "studio-nexmind-p8", "worker.py");
  const child = spawn(python, [worker], { cwd: process.cwd(), env: process.env, windowsHide: true, stdio: ["pipe", "pipe", "pipe"] });
  let stdout = "";
  let stderrBuffer = "";
  let stderrTail = "";
  const progressTasks: Promise<void>[] = [];
  const limit = 12 * 1024 * 1024;
  const timer = setTimeout(() => child.kill("SIGKILL"), timeoutMs());
  timer.unref?.();

  child.stdout.setEncoding("utf8");
  child.stderr.setEncoding("utf8");
  child.stdout.on("data", (chunk: string) => {
    stdout += chunk;
    if (stdout.length > limit) child.kill("SIGKILL");
  });
  child.stderr.on("data", (chunk: string) => {
    stderrBuffer += chunk;
    stderrTail = (stderrTail + chunk).slice(-8_000);
    const lines = stderrBuffer.split(/\r?\n/);
    stderrBuffer = lines.pop() || "";
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const value = JSON.parse(line) as { type?: string; phase?: string; payload?: Record<string, unknown> };
        if (value.type === "progress" && value.phase && (nexMindP8Phases as readonly string[]).includes(value.phase) && onProgress) {
          progressTasks.push(Promise.resolve(onProgress({ phase: value.phase as NexMindProgress["phase"], payload: value.payload || {} })).then(() => undefined));
        }
      } catch {
        // Stderr is server-side diagnostic output only; never pass it to the browser.
      }
    }
  });
  child.stdin.end(JSON.stringify(request));

  const exit = await new Promise<{ code: number | null; signal: NodeJS.Signals | null }>((resolve, reject) => {
    child.once("error", reject);
    child.once("exit", (code, signal) => resolve({ code, signal }));
  }).finally(() => clearTimeout(timer));
  await Promise.allSettled(progressTasks);
  if (exit.code !== 0) return disabledResult(`STUDIO_NEXMIND_P8_PROCESS_EXIT_${exit.code ?? exit.signal ?? "UNKNOWN"}`);
  try {
    return nexMindP8ResultSchema.parse(JSON.parse(stdout));
  } catch {
    return { schema: "StudioNexMindP8ResultV1", status: "BLOCKED", code: "STUDIO_NEXMIND_P8_INVALID_PROCESS_RESPONSE", detail: stderrTail ? "The internal NexMind worker returned an invalid response." : "The internal NexMind worker returned no valid response." };
  }
}

async function httpBridge(request: StudioNexMindP8BridgeRequest): Promise<NexMindP8Result> {
  const base = process.env.STUDIO_NEXMIND_P8_HTTP_URL?.trim().replace(/\/$/, "");
  const token = process.env.STUDIO_NEXMIND_P8_HTTP_TOKEN?.trim();
  if (!base || !token) return disabledResult("STUDIO_NEXMIND_P8_HTTP_NOT_CONFIGURED");
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs());
  timer.unref?.();
  try {
    const response = await fetch(`${base}/v1/studio/nexmind-p8`, {
      method: "POST",
      headers: { "content-type": "application/json", authorization: `Bearer ${token}` },
      body: JSON.stringify(request),
      signal: controller.signal,
      cache: "no-store",
    });
    if (!response.ok) return disabledResult(`STUDIO_NEXMIND_P8_HTTP_${response.status}`);
    return nexMindP8ResultSchema.parse(await response.json());
  } catch {
    return disabledResult("STUDIO_NEXMIND_P8_HTTP_UNAVAILABLE");
  } finally {
    clearTimeout(timer);
  }
}

export async function executeStudioNexMindP8(request: StudioNexMindP8BridgeRequest, onProgress?: ProgressHandler): Promise<NexMindP8Result> {
  const mode = bridgeMode();
  if (mode === "disabled") return disabledResult();
  if (mode === "process") return processBridge(request, onProgress);
  return httpBridge(request);
}
