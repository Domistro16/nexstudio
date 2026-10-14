#!/usr/bin/env python3
"""NexStudio board-scenes job runner.

One production request -> VO (Microsoft edge-tts) -> storyboard plan ->
composition gate -> one board_sections render per aspect -> manifest.json
the /api/v1/whiteboards route collects.

    python3 tools/nexstudio_job.py --script script.txt --type board-scenes \
        --theme light --voice emma --title 'My Film' \
        --aspects '16:9,1x1,9:16' --out out/job --job-id wb-abc12345

Script format: '# Title' line, optional '## Scene name' lines, then one
narration beat per paragraph. The gate refuses (nonzero exit, no files)
when a scene's composition audit reports a real break.
"""
from __future__ import annotations

import argparse
import json
import os
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
    "board-scenes": "pipeline_v3_narration_timed.py",
}

WHISPER_PYTHON = (os.environ.get("NEXSTUDIO_WHISPER_PYTHON")
                  or os.environ.get("WHISPER_PYTHON")
                  or str(Path.home() / "tools/whisper/bin/python3"))


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

    text = re.sub(r"\[[^\]]*\]", " ", script_text or "")
    text = re.sub(r"(?m)^\s*#{1,6}\s+.*$", " ", text).strip()
    if not text:
        raise RuntimeError("VOICE_REQUIRED: script produced no narration text")
    speed = min(max(getattr(args, "speed", None) or 1.0, 0.6), 2.0)
    sh([sys.executable, "-c",
        "import sys; sys.path.insert(0, %r); import vo_synth; "
        "vo_synth.synth_edge(%r, %r, voice=%r, speed=%r)"
        % (str(ROOT), text, str(vo_wav), VOICES[args.voice], speed)])
    words = work / "vo_words.json"
    if words.exists():
        print('[voice] Using Microsoft word timings; local alignment skipped', flush=True)
        return vo_wav, words
    try:
        # The timing helper applies an explicit override, or uses available CPUs.
        timing_env = dict(os.environ)
        sh([WHISPER_PYTHON, "-c",
            "import sys; sys.path.insert(0, %r); import vo_synth; "
            "vo_synth.word_timings(%r, %r, 'small', %r)"
            % (str(ROOT), str(vo_wav), str(words), text)], env=timing_env)
        return vo_wav, words
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise RuntimeError('NARRATION_ALIGNMENT_FAILED: could not prepare narration timing') from error


def build_plan(args, script_text: str, work: Path, aspects: list[str]) -> Path:
    import plan_author
    if args.type == "board-scenes":
        plan = plan_author.build_storyboard(script_text, title=args.title)
    else:
        plan = plan_author.build_plan(script_text, vtype="kinetic", title=args.title)
    plan_path = work / "plan.json"
    plan_path.write_text(json.dumps(plan, indent=1))
    if args.type == "board-scenes":
        import sb_qa
        fails: list[str] = []
        for aspect in aspects:
            issues, _ = sb_qa.visual(plan, aspect)
            fails += [f"{aspect}:{i.get('check')}:{i.get('beat','')}:{i.get('detail','')}"
                      for i in issues if i.get("severity") == "fail"]
        if fails:
            raise RuntimeError("GATE_REFUSED " + "; ".join(fails[:12]))
    return plan_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--script", help="narration script text file (one beat per paragraph)")
    ap.add_argument("--voice-file", help="uploaded narration audio; replaces TTS")
    ap.add_argument("--voice", default="emma", choices=sorted(VOICES))
    ap.add_argument("--type", default="board-scenes", choices=sorted(PIPELINES))
    ap.add_argument("--theme", default="light", choices=("light", "dark"))
    ap.add_argument("--accent", default=None)
    ap.add_argument("--title", default="")
    ap.add_argument("--aspects", default="16:9,1x1,9:16")
    ap.add_argument("--duration", type=float, default=None)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--icons", default=None)
    ap.add_argument("--word-timings", help="precomputed word timings JSON; skips whisper pass")
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

    aspect_list = [a.strip() for a in args.aspects.split(",") if a.strip()]
    # Refuse an invalid visual plan before spending time on narration.
    progress(phase="direction")
    plan_path = build_plan(args, script_text or "", work, aspect_list)
    progress(phase="voice")
    vo_wav, words_json = build_voice(args, script_text, work)
    if args.word_timings:
        words_json = Path(args.word_timings)

    pipeline = ROOT / PIPELINES[args.type]
    active = list(aspect_list)
    progress(phase="render", aspectsActive=active, aspectsDone=0, aspectsTotal=len(aspect_list))

    def render(aspect):
        ratio_dir = out / aspect.replace(":", "x")
        pipeline_ratio = aspect.replace("x", ":") if args.type == "kinetic" else aspect
        cmd = [sys.executable, str(pipeline), str(plan_path),
               "--out-dir", str(ratio_dir), "--ratio", pipeline_ratio,
               "--theme", args.theme, "--voiceover", str(vo_wav)]
        if args.type == "board-scenes":
            cmd += ["--variant", "board_sections"]
        if words_json:
            cmd += ["--word-timings", str(words_json)]
        if args.accent:
            cmd += ["--accent", args.accent]
        if args.icons:
            cmd += ["--icons", args.icons]
        sh(cmd, cwd=ROOT,
           env={**os.environ,
                "NEXSTUDIO_SCENE_LLM": "off",
                "WHITEBOARD_V3_SYSTEM_PACKAGE": os.environ.get(
                    "WHITEBOARD_V3_SYSTEM_PACKAGE", "")})
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
