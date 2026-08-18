#!/usr/bin/env python3
from __future__ import annotations

import base64, io, json, os, urllib.request, urllib.error, wave

PNG_DATA = (
    "data:image/png;base64,"
    + base64.b64encode(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII="
        )
    ).decode()
)

REMOTE_IMAGE = "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/Fronalpstock_big.jpg/320px-Fronalpstock_big.jpg"

def wav_b64() -> str:
    bio = io.BytesIO()
    with wave.open(bio, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 1600)
    return base64.b64encode(bio.getvalue()).decode()

AUDIO_B64 = wav_b64()

def endpoint(base: str) -> str:
    b = (base or "").rstrip("/")
    if b.endswith("/chat/completions"):
        return b
    return b + "/chat/completions"

def call(label: str, *, model: str, base: str, key: str, content):
    print("\n" + "=" * 80)
    print(label)
    print("model:", model)
    print("endpoint:", endpoint(base))

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
    }

    req = urllib.request.Request(
        endpoint(base),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            raw = r.read().decode("utf-8", errors="replace")
            print("HTTP:", r.status)
            print("BODY:")
            print(raw[:4000])
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        print("HTTP:", e.code)
        print("BODY:")
        print(raw[:4000])
    except Exception as e:
        print("ERROR:", repr(e))

def env(name: str, fallback: str = "") -> str:
    return os.getenv(name, fallback).strip()

def main():
    key = env("NEXMIND_API_KEY")
    creative_model = env("NEXMIND_CREATIVE_MODEL")
    creative_base = env("NEXMIND_CREATIVE_BASE_URL")
    final_model = env("NEXMIND_FINAL_EXECUTIVE_PRODUCER_MODEL")
    final_base = env("NEXMIND_FINAL_EXECUTIVE_PRODUCER_BASE_URL")
    auditor_model = env("NEXMIND_PERCEPTUAL_AUDITOR_MODEL")
    auditor_base = env("NEXMIND_PERCEPTUAL_AUDITOR_BASE_URL")

    missing = [
        n for n, v in [
            ("NEXMIND_API_KEY", key),
            ("NEXMIND_CREATIVE_MODEL", creative_model),
            ("NEXMIND_CREATIVE_BASE_URL", creative_base),
            ("NEXMIND_FINAL_EXECUTIVE_PRODUCER_MODEL", final_model),
            ("NEXMIND_FINAL_EXECUTIVE_PRODUCER_BASE_URL", final_base),
            ("NEXMIND_PERCEPTUAL_AUDITOR_MODEL", auditor_model),
            ("NEXMIND_PERCEPTUAL_AUDITOR_BASE_URL", auditor_base),
        ]
        if not v
    ]
    if missing:
        raise SystemExit("Missing env vars: " + ", ".join(missing))

    # Creative/Luna: isolate text vs image forms.
    call(
        "CREATIVE TEXT ONLY",
        model=creative_model,
        base=creative_base,
        key=key,
        content="Reply exactly OK",
    )
    call(
        "CREATIVE IMAGE — DATA URI",
        model=creative_model,
        base=creative_base,
        key=key,
        content=[
            {"type": "text", "text": "Describe the image briefly."},
            {"type": "image_url", "image_url": {"url": PNG_DATA}},
        ],
    )
    call(
        "CREATIVE IMAGE — REMOTE HTTPS URL",
        model=creative_model,
        base=creative_base,
        key=key,
        content=[
            {"type": "text", "text": "Describe the image briefly."},
            {"type": "image_url", "image_url": {"url": REMOTE_IMAGE}},
        ],
    )

    # Final Producer/Sol: isolate image vs audio.
    call(
        "FINAL PRODUCER — IMAGE ONLY",
        model=final_model,
        base=final_base,
        key=key,
        content=[
            {"type": "text", "text": "Describe the image briefly."},
            {"type": "image_url", "image_url": {"url": PNG_DATA}},
        ],
    )
    call(
        "FINAL PRODUCER — AUDIO ONLY",
        model=final_model,
        base=final_base,
        key=key,
        content=[
            {"type": "text", "text": "What do you hear?"},
            {
                "type": "input_audio",
                "input_audio": {"data": AUDIO_B64, "format": "wav"},
            },
        ],
    )
    call(
        "FINAL PRODUCER — IMAGE + AUDIO",
        model=final_model,
        base=final_base,
        key=key,
        content=[
            {"type": "text", "text": "Inspect both modalities."},
            {"type": "image_url", "image_url": {"url": PNG_DATA}},
            {
                "type": "input_audio",
                "input_audio": {"data": AUDIO_B64, "format": "wav"},
            },
        ],
    )

    # Auditor: at least verify whether the configured model ID itself exists.
    call(
        "AUDITOR TEXT ONLY",
        model=auditor_model,
        base=auditor_base,
        key=key,
        content="Reply exactly OK",
    )
    call(
        "AUDITOR IMAGE ONLY",
        model=auditor_model,
        base=auditor_base,
        key=key,
        content=[
            {"type": "text", "text": "Describe the image briefly."},
            {"type": "image_url", "image_url": {"url": PNG_DATA}},
        ],
    )

if __name__ == "__main__":
    main()
