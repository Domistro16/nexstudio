#!/usr/bin/env python3
"""NexStudio whiteboard job runner.

One production request -> VO (Microsoft edge-tts) -> plan -> one render per
aspect -> manifest.json the /api/v1/whiteboards route collects.

    python3 tools/nexstudio_job.py --script script.txt --type kinetic \
        --theme light --accent '#2f6fb3' --voice emma \
        --aspects '16:9,1x1,9:16' --out out/job --job-id wb-abc12345
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parents[1] / 'services/studio-family-engines'))
from parallel_aspects import render_aspects

VOICES = {
    "emma": "en-US-EmmaMultilingualNeural",
    "ava": "en-US-AvaMultilingualNeural",
    "andrew": "en-US-AndrewMultilingualNeural",
    "brian": "en-US-BrianMultilingualNeural",
    "sonia": "en-GB-SoniaNeural",
    "natasha": "en-AU-NatashaNeural",
}

PIPELINES = {
    "kinetic": "pipeline_kinetic_timed.py",
    "board": "pipeline_diagram_timed.py",
}


def sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if proc.returncode != 0:
        raise RuntimeError(f"STAGE_FAILED {Path(cmd[1]).name}: {proc.stderr[-1500:]}")
    return proc


def build_voice(args, script_text: str | None, work: Path) -> tuple[Path, Path | None]:
    vo_wav = work / "vo.wav"
    if args.voice_file:
        src = Path(args.voice_file)
        if src.suffix.lower() == ".wav":
            shutil.copy(src, vo_wav)
        else:
            sh(["ffmpeg", "-y", "-i", str(src), "-ar", "24000", "-ac", "1", str(vo_wav)])
        return vo_wav, None

    import vo_synth
    # authoring hints like [stage: hatch] steer the plan, not the narration
    text = re.sub(r"\[[^\]]*\]", " ", script_text or "").strip()
    if not text:
        raise RuntimeError("VOICE_REQUIRED: script produced no narration text")
    # Narration speed is the user's choice only; duration never retimes the voice.
    speed = min(max(getattr(args, 'speed', None) or 1.0, 0.6), 2.0)
    vo_synth.synth_edge(text, vo_wav, voice=VOICES[args.voice], speed=speed)
    words = work / "vo_words.json"
    if words.exists():
        print('[voice] Using Microsoft word timings; local alignment skipped', flush=True)
        return vo_wav, words
    try:
        vo_synth.word_timings(vo_wav, words)
        return vo_wav, words
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise RuntimeError('NARRATION_ALIGNMENT_FAILED: could not prepare narration timing') from error


def build_plan(args, script_text: str, work: Path) -> Path:
    import plan_author
    plan = plan_author.build_plan(
        script_text,
        vtype="diagram" if args.type == "board" else "kinetic",
        title=args.title,
    )
    plan_path = work / "plan.json"
    plan_path.write_text(json.dumps(plan, indent=1))
    return plan_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--script", help="narration script text file (one beat per line)")
    ap.add_argument("--voice-file", help="uploaded narration audio; replaces TTS")
    ap.add_argument("--voice", default="emma", choices=sorted(VOICES))
    ap.add_argument("--type", required=True, choices=sorted(PIPELINES))
    ap.add_argument("--theme", default="light", choices=("light", "dark"))
    ap.add_argument("--accent", default=None, help="highlight hex color (kinetic)")
    ap.add_argument("--title", default="")
    ap.add_argument("--aspects", default="16:9,1x1,9:16")
    ap.add_argument("--duration", type=float, default=None, help="target seconds preference")
    ap.add_argument("--speed", type=float, default=1.0, help="user narration speed multiplier")
    ap.add_argument("--icons", choices=["auto", "off"], default=None, help="kinetic word icons (runtimes that support them)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--job-id", required=True)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="wbjob-", dir=out))
    progress_file = out.parent / "progress.json"

    def progress(**payload):
        try:
            progress_file.write_text(json.dumps(payload))
        except OSError:
            pass

    script_text = Path(args.script).read_text() if args.script else None
    if not script_text and not args.voice_file:
        raise RuntimeError("SCRIPT_REQUIRED: send --script or --voice-file")

    progress(phase="voice")
    vo_wav, words_json = build_voice(args, script_text, work)
    progress(phase="direction")
    plan_path = build_plan(args, script_text or "", work)

    pipeline = ROOT / PIPELINES[args.type]
    aspect_list = [a.strip() for a in args.aspects.split(",") if a.strip()]
    active = list(aspect_list)
    progress(phase="render", aspectsActive=active, aspectsDone=0, aspectsTotal=len(aspect_list))

    def render(aspect):
        ratio_dir = out / aspect.replace(":", "x")
        cmd = [sys.executable, str(pipeline), str(plan_path),
               "--out-dir", str(ratio_dir), "--ratio", aspect,
               "--theme", args.theme, "--voiceover", str(vo_wav)]
        if words_json:
            cmd += ["--word-timings", str(words_json)]
        if args.accent:
            cmd += ["--accent", args.accent]
        if args.icons:
            cmd += ["--icons", args.icons]
        sh(cmd, cwd=ROOT)
        mp4s = sorted(ratio_dir.glob("*.mp4"))
        if not mp4s:
            raise RuntimeError(f"RENDER_OUTPUT_MISSING: {aspect}")
        return str(mp4s[0])

    def completed(aspect, count, total):
        active.remove(aspect)
        progress(phase="render", aspectsActive=list(active), aspectsDone=count, aspectsTotal=total)

    outputs = render_aspects(aspect_list, render, completed)

    progress(phase="packaging", aspectsDone=len(outputs), aspectsTotal=len(aspect_list))
    (out / "manifest.json").write_text(json.dumps(
        {"jobId": args.job_id, "outputs": outputs}, indent=1))
    print(json.dumps({"ok": True, "outputs": outputs}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"WHITEBOARD_JOB_FAILED: {e}", file=sys.stderr)
        raise SystemExit(1)
