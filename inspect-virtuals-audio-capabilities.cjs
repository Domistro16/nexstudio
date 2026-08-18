const fs = require("fs");
const path = require("path");

const API_KEY = process.env.NEXMIND_API_KEY;
const BASE = (process.env.NEXMIND_CREATIVE_BASE_URL || "https://compute.virtuals.io/v1").replace(/\/$/, "");

if (!API_KEY) {
  console.error("Missing NEXMIND_API_KEY. Run with: node --env-file=.env .\\inspect-virtuals-audio-capabilities.cjs");
  process.exit(1);
}

function summarize(model) {
  const spec = model.model_spec || model.modelSpec || {};
  const caps = spec.capabilities || model.capabilities || {};
  return {
    id: model.id,
    type: model.type,
    name: spec.name || model.name || "",
    capabilities: caps,
    traits: spec.traits || model.traits || [],
    description: spec.description || model.description || "",
  };
}

function hasAudioSignal(model) {
  const text = JSON.stringify(model).toLowerCase();
  const needles = [
    "input_audio",
    "audio_input",
    "audioinput",
    "supportsaudio",
    "supports_audio",
    "supports audio",
    "audio input",
    '"audio"',
    "multimodal",
  ];
  return needles.some(n => text.includes(n));
}

async function main() {
  const url = BASE + "/models";
  console.log("Querying:", url);

  const r = await fetch(url, {
    headers: {
      Authorization: "Bearer " + API_KEY,
      Accept: "application/json",
    },
  });

  const raw = await r.text();
  console.log("HTTP", r.status);

  if (!r.ok) {
    console.error(raw);
    process.exit(1);
  }

  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    console.error("Models response was not JSON:");
    console.error(raw.slice(0, 4000));
    process.exit(1);
  }

  const outPath = path.join(process.cwd(), "virtuals-models-full.json");
  fs.writeFileSync(outPath, JSON.stringify(body, null, 2), "utf8");
  console.log("Saved full model catalog:", outPath);

  const models = Array.isArray(body.data)
    ? body.data
    : Array.isArray(body.models)
      ? body.models
      : [];

  console.log("Model count:", models.length);

  const audioSignals = models.filter(hasAudioSignal);
  console.log("\n=== MODELS WITH AUDIO/MULTIMODAL SIGNALS IN METADATA ===");
  if (!audioSignals.length) {
    console.log("None found in model metadata.");
  } else {
    for (const m of audioSignals) {
      console.dir(summarize(m), { depth: 10, colors: true });
    }
  }

  const targetIds = new Set([
    "openai-gpt-56-luna",
    "openai-gpt-56-sol",
    "openai-gpt-56-sol-pro",
    "openai-gpt-56-terra",
  ]);

  console.log("\n=== CURRENT NEXMIND TARGET MODELS ===");
  const targets = models.filter(m => targetIds.has(m.id));
  if (!targets.length) {
    console.log("No exact target IDs found in /models response.");
  } else {
    for (const m of targets) {
      console.dir(summarize(m), { depth: 10, colors: true });
    }
  }

  console.log("\n=== TEXT MODELS ADVERTISING VISION ===");
  const vision = models.filter(m => {
    const caps = m.model_spec?.capabilities || m.modelSpec?.capabilities || m.capabilities || {};
    return caps.supportsVision === true || caps.supports_vision === true;
  });
  console.log(vision.map(m => m.id).join("\n") || "No explicit supportsVision flag found.");

  console.log("\nIf no audio-input flag appears, send me the relevant output or virtuals-models-full.json.");
  console.log("We can then probe candidate chat models directly with a tiny WAV without weakening NexMind's audio gate.");
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
