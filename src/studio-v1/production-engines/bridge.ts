import { spawn } from "node:child_process";
import path from "node:path";

export type StudioFamilyEngineOperation = "BUILD_INTERNAL_REVIEW_EVIDENCE";
export type StudioFamilyEngineRequest = {
  schema: "StudioFamilyEngineRequestV1";
  operation: StudioFamilyEngineOperation;
  family: "EXPLAINER" | "WHITEBOARD" | "STICKMAN" | "EDITORIAL_MOTION";
  authorityId: string;
  productionId: string;
  creativeStateArtifactId: string;
  creativeStateArtifactHash: string;
  durationSeconds: number;
  aspectRatio: string | null;
  voicePreference?: string | null;
  outputDirectory: string;
  finalBoard: Record<string, unknown>;
  creativeCheckpoint: Record<string, unknown>;
  creativeDossier?: Record<string, unknown> | null;
  referenceMedia?: Array<{ assetId: string; path: string; mimeType: string; name?: string }>;
  brandExecution?: { schema:"StudioBrandExecutionV1"; memoryInputSnapshotId:string; memoryInputSnapshotHash:string; brandAuthority:Record<string,unknown>; productionBrandContext:Record<string,unknown>|null; brandExecutionHash:string };
};
export type StudioFamilyEngineResult = {
  schema: "StudioFamilyEngineResultV1";
  status: "EVIDENCE_READY" | "FINAL_OUTPUT_READY" | "REPLAN_REQUIRED" | "TECHNICAL_RETRY_REQUIRED";
  family?: StudioFamilyEngineRequest["family"];
  authorityId?: string;
  code?: string;
  detail?: string;
  repairRequest?: Record<string, unknown>;
  executionPlanSchema?: "StudioCanonicalExecutionPlanV1";
  executionPlanHash?: string;
  executionPlanAuthority?: Record<string, unknown>;
  enginePlanHash?: string;
  technicalQa?: Record<string, unknown>;
  soundBinding?: Record<string, unknown>;
  artifacts?: Array<{ kind: "VIDEO" | "AUDIO_MIX" | "CONTACT_SHEET"; path: string; mimeType: string; sha256: string; bytes: number }>;
  enginePlanPath?: string;
  audioExpected?: boolean;
};

export async function executeStudioFamilyEngine(request: StudioFamilyEngineRequest): Promise<StudioFamilyEngineResult> {
  const python = process.env.STUDIO_FAMILY_ENGINE_PYTHON?.trim() || "python3";
  const worker = process.env.STUDIO_FAMILY_ENGINE_WORKER?.trim() || path.join(process.cwd(), "services", "studio-family-engines", "worker.py");
  return new Promise((resolve, reject) => {
    const child = spawn(python, [worker], {
      cwd: process.cwd(),
      env: process.env,
      stdio: ["pipe", "pipe", "pipe"],
    });
    const out: Buffer[] = []; const err: Buffer[] = [];
    child.stdout.on("data", (chunk) => out.push(Buffer.from(chunk)));
    child.stderr.on("data", (chunk) => err.push(Buffer.from(chunk)));
    child.on("error", reject);
    child.on("close", (code) => {
      const stdout = Buffer.concat(out).toString("utf8").trim();
      const stderr = Buffer.concat(err).toString("utf8").trim();
      if (code !== 0) return reject(new Error(`FAMILY_ENGINE_WORKER_EXIT_${code}:${stderr.slice(0, 500)}`));
      try {
        const result = JSON.parse(stdout) as StudioFamilyEngineResult;
        if (result.schema !== "StudioFamilyEngineResultV1") throw new Error("FAMILY_ENGINE_RESULT_SCHEMA_INVALID");
        resolve(result);
      } catch (error) {
        reject(new Error(`FAMILY_ENGINE_RESULT_INVALID:${error instanceof Error ? error.message : String(error)}:${stdout.slice(0, 500)}:${stderr.slice(0, 300)}`));
      }
    });
    child.stdin.end(JSON.stringify(request));
  });
}
