const fs = require("fs");
const path = require("path");

const API_KEY = process.env.NEXMIND_API_KEY;
const BASE = (process.env.NEXMIND_CREATIVE_BASE_URL || "https://compute.virtuals.io/v1").replace(/\/$/, "");

if (!API_KEY) {
  console.error("Missing NEXMIND_API_KEY. Run with:");
  console.error("  node --env-file=.env .\\probe-virtuals-gemini-audio.cjs");
  process.exit(1);
}

// 100 ms mono PCM16 silence at 16 kHz, encoded as WAV.
function makeWavBase64() {
  const sampleRate = 16000;
  const sampleCount = 1600;
  const dataSize = sampleCount * 2;
  const buf = Buffer.alloc(44 + dataSize);
  let o = 0;
  buf.write("RIFF", o); o += 4;
  buf.writeUInt32LE(36 + dataSize, o); o += 4;
  buf.write("WAVE", o); o += 4;
  buf.write("fmt ", o); o += 4;
  buf.writeUInt32LE(16, o); o += 4;
  buf.writeUInt16LE(1, o); o += 2;       // PCM
  buf.writeUInt16LE(1, o); o += 2;       // mono
  buf.writeUInt32LE(sampleRate, o); o += 4;
  buf.writeUInt32LE(sampleRate * 2, o); o += 4;
  buf.writeUInt16LE(2, o); o += 2;
  buf.writeUInt16LE(16, o); o += 2;
  buf.write("data", o); o += 4;
  buf.writeUInt32LE(dataSize, o); o += 4;
  // data is already zero-filled silence.
  return buf.toString("base64");
}

const AUDIO = makeWavBase64();
const IMAGE = "https://www.gstatic.com/webp/gallery/1.jpg";

const MODELS = [
  "google-gemini-3-1-pro-preview",
  "google-gemini-3-5-flash",
  "google-gemini-3-7-flash",
];

async function request(model, label, content) {
  const url = BASE + "/chat/completions";
  const started = Date.now();

  let response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: "Bearer " + API_KEY,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model,
        max_tokens: 16,
        messages: [{ role: "user", content }],
      }),
    });
  } catch (err) {
    return {
      model,
      test: label,
      status: 0,
      pass: false,
      elapsedMs: Date.now() - started,
      body: String(err),
    };
  }

  const text = await response.text();
  return {
    model,
    test: label,
    status: response.status,
    pass: response.ok,
    elapsedMs: Date.now() - started,
    body: text.slice(0, 2500),
  };
}

async function main() {
  const results = [];

  for (const model of MODELS) {
    console.log("\n" + "=".repeat(88));
    console.log(model);

    const audioOnly = await request(model, "AUDIO_ONLY", [
      { type: "text", text: "Listen to this short audio and reply exactly AUDIO_OK." },
      {
        type: "input_audio",
        input_audio: {
          data: AUDIO,
          format: "wav",
        },
      },
    ]);
    results.push(audioOnly);
    console.log("\nAUDIO_ONLY HTTP", audioOnly.status, audioOnly.pass ? "PASS" : "FAIL");
    console.log(audioOnly.body);

    const imageAudio = await request(model, "IMAGE_PLUS_AUDIO", [
      { type: "text", text: "Inspect the image and audio. Reply exactly BOTH_OK if both inputs were received." },
      {
        type: "image_url",
        image_url: { url: IMAGE },
      },
      {
        type: "input_audio",
        input_audio: {
          data: AUDIO,
          format: "wav",
        },
      },
    ]);
    results.push(imageAudio);
    console.log("\nIMAGE_PLUS_AUDIO HTTP", imageAudio.status, imageAudio.pass ? "PASS" : "FAIL");
    console.log(imageAudio.body);
  }

  const report = {
    checkedAt: new Date().toISOString(),
    baseUrl: BASE,
    results,
    audioCapable: [...new Set(results.filter(r => r.test === "AUDIO_ONLY" && r.pass).map(r => r.model))],
    imageAudioCapable: [...new Set(results.filter(r => r.test === "IMAGE_PLUS_AUDIO" && r.pass).map(r => r.model))],
  };

  const out = path.join(process.cwd(), "virtuals-gemini-audio-probe.json");
  fs.writeFileSync(out, JSON.stringify(report, null, 2), "utf8");

  console.log("\n" + "=".repeat(88));
  console.log("SUMMARY");
  console.log("Audio-capable:", report.audioCapable.length ? report.audioCapable.join(", ") : "NONE");
  console.log("Image+audio-capable:", report.imageAudioCapable.length ? report.imageAudioCapable.join(", ") : "NONE");
  console.log("Saved:", out);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
