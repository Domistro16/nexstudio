import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { engineDir, engineJobsDir } from "../src/lib/engine-paths";
import { explainerStyles } from "../src/lib/explainer-catalog";
import { renderEnv } from "../src/lib/render-queue";
import { friendlyEngineError, gateFailureMessage } from "../src/lib/engine-jobs";

const original = process.env.EXPLAINER_ENGINE_DIR;
const fixture = mkdtempSync(path.join(tmpdir(), "explainer-dispatch-"));
try {
  for (const value of [undefined, "", "  "]) {
    if (value === undefined) delete process.env.EXPLAINER_ENGINE_DIR;
    else process.env.EXPLAINER_ENGINE_DIR = value;
    assert.equal(engineDir("explainer"), path.join(process.cwd(), "engine_sources", "explainer-locks"));
    assert.equal(engineJobsDir("explainer"), path.join(engineDir("explainer"), "out", "explainer-jobs"));
    assert.deepEqual(explainerStyles().map((s) => s.id), ["photo_story", "sketch", "emoji", "journey", "collage", "dataviz", "newscast"]);
  }
  process.env.EXPLAINER_ENGINE_DIR = `  ${fixture}  `;
  assert.equal(engineDir("explainer"), fixture);
  writeFileSync(path.join(fixture, "styles.json"), JSON.stringify({ styles: [
    { id: "tiles", name: "Legacy Tiles" },
    { id: "sketch", name: "Sketch", variants: [{ id: "paper", name: "Paper" }] },
    { id: "uncertified", name: "Uncertified" },
  ] }));
  const styles = explainerStyles();
  assert.deepEqual(styles.map((s) => s.id), ["sketch"]);
  assert.deepEqual(styles[0].variants.map((v) => v.id), ["sketch.paper"]);
  assert.throws(() => explainerStyles(path.join(fixture, "missing")));
  const env = renderEnv();
  assert.equal(env.PATH?.split(path.delimiter)[0], path.dirname(process.execPath));
  writeFileSync(path.join(fixture, "status.json"), JSON.stringify({ status: "failed", error: "engine exited 1 with no outputs" }));
  writeFileSync(path.join(fixture, "job.log"), "--- P8 dispatch 00:00 ---\nedge_tts WSServerHandshakeError: 403");
  assert.match(friendlyEngineError(fixture) ?? "", /selected voice/);
  writeFileSync(path.join(fixture, "job.log"), "--- P8 dispatch 00:00 ---\nedge_tts WSServerHandshakeError: 403\n--- P8 dispatch 00:01 ---\nunrelated failure");
  assert.equal(friendlyEngineError(fixture), "engine exited 1 with no outputs");
  writeFileSync(path.join(fixture, "status.json"), JSON.stringify({ status: "failed", error: "Specific quality gate error" }));
  assert.equal(friendlyEngineError(fixture), "Specific quality gate error");
  writeFileSync(path.join(fixture, "status.json"), JSON.stringify({ status: "failed", failureCode: "ILLUSTRATION_COLLIDES_TEXT", error: "16x9:b09:ILLUSTRATION_COLLIDES_TEXT:e1_highlight2:3" }));
  assert.match(friendlyEngineError(fixture) ?? "", /laid out cleanly/);
  assert.equal(gateFailureMessage("1x1:b02:NEW_GATE_CODE:e1"), "The render didn't pass its quality gate — NEW_GATE_CODE.");
  assert.match(gateFailureMessage("9x16:b01:LEGIBLE_HOLD_143MS_UNDER_161MS"), /long enough to read/);
  console.log("Explainer dispatch and empty-path regression checks passed.");
} finally {
  if (original === undefined) delete process.env.EXPLAINER_ENGINE_DIR;
  else process.env.EXPLAINER_ENGINE_DIR = original;
  assert.equal(path.dirname(fixture), path.resolve(tmpdir()));
  rmSync(fixture, { recursive: true, force: true });
}
