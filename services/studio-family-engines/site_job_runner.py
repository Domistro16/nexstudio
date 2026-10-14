#!/usr/bin/env python3
"""P8 site dispatch runner: the single entry point every site render goes through.

python3 site_job_runner.py JOB_DIR

JOB_DIR/engine_request.json (written by the API route):
  {"family": "whiteboard"|"explainer"|"presenter", "subtype": "<id>",
   "jobId": "...", "params": {...adapter-specific...}}

Behaviour: the subtype must be registered in site-dispatch.json (fail-closed),
then the matching adapter builds the engine invocation, runs it synchronously,
collects the manifest artifacts into JOB_DIR/files/, and writes:
  status.json  — the job contract the status routes already read
  result.json  — StudioFamilyEngineResultV1-shaped P8 evidence envelope
"""
from __future__ import annotations

import hashlib, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
REGISTRY = HERE / "site-dispatch.json"
AUTHORITY_ID = "P8_SITE_DISPATCH_V1"


def _write_status(j: Path, **fields):
    (j / "status.json").write_text(json.dumps(fields, indent=1) + "\n")


def _result(j: Path, status: str, **fields):
    doc = {"schema": "StudioFamilyEngineResultV1", "status": status,
           "authorityId": AUTHORITY_ID, **fields}
    # P8 cast scope: when the job was dispatched with a registered character,
    # the envelope carries the cast authority identity + spec hash so memory
    # and certification can bind the render to that performer.
    try:
        params = (json.loads((j / "engine_request.json").read_text())
                  .get("params") or {})
        cast = params.get("cast")
        if cast:
            doc["castAuthority"] = cast
        director = params.get("director")
        if director:
            doc["director"] = director
    except Exception:
        pass
    (j / "result.json").write_text(json.dumps(doc, indent=1) + "\n")
    return doc


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _env(extra: dict | None = None) -> dict:
    env = os.environ.copy()
    node_bin = str(Path.home() / ".nvm/versions/node/v24.19.0/bin")
    if Path(node_bin).is_dir():
        env["PATH"] = node_bin + os.pathsep + env.get("PATH", "")
    env.setdefault("WHITEBOARD_V3_SYSTEM_PACKAGE",
                   str(ROOT / "engines/whiteboard-v3-system/NEXMIND_WHITEBOARD_V3_SYSTEM_PACKAGE"))
    env.setdefault("NLTK_DATA", str(ROOT / "llm" / "nltk"))
    local_model = ROOT / 'llm' / 'whisper-small'
    if (local_model / 'model.bin').exists():
        env.setdefault('WHISPER_MODEL_PATH', str(local_model))
    whisper = Path.home() / "tools/whisper/bin/python3"
    if whisper.exists():
        env.setdefault("WHISPER_PYTHON", str(whisper))
    env.update(extra or {})
    return env


def _engine_root(env_key: str | None, fallback: str) -> Path:
    raw = os.environ.get(env_key, "").strip() if env_key else ""
    return Path(raw).resolve() if raw else (ROOT / fallback).resolve()


def _manifest_outputs(j: Path, url_prefix: str) -> dict:
    """manifest.json -> copy each output into files/, return aspect->url map."""
    manifest_path = j / "out" / "manifest.json"
    outputs: dict[str, str] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        files_dir = j / "files"
        files_dir.mkdir(exist_ok=True)
        for aspect, src in (manifest.get("outputs") or {}).items():
            dest = files_dir / f"{aspect.replace(':', 'x')}.mp4"
            try:
                shutil.copyfile(src, dest)
            except OSError:
                continue
            outputs[aspect.replace(":", "x")] = f"{url_prefix}/{dest.name}"
    return outputs


def _artifacts(files_dir: Path) -> list:
    if not files_dir.exists():
        return []
    out = []
    for p in sorted(files_dir.iterdir()):
        if p.is_file():
            out.append({"kind": "VIDEO" if p.suffix == ".mp4" else "ARTIFACT",
                        "path": str(p), "mimeType": "video/mp4" if p.suffix == ".mp4" else "application/octet-stream",
                        "sha256": _sha(p), "bytes": p.stat().st_size})
    return out


def _first_gate_failure(j: Path) -> str | None:
    out_dir = j / "out"
    if not out_dir.exists():
        return None
    for entry in out_dir.iterdir():
        report = entry / "gate_report.json"
        if report.exists():
            try:
                failures = (json.loads(report.read_text()).get("failures") or [])
            except Exception:
                continue
            if failures:
                return failures[0]
    return None


def _gate_code(gate: str) -> str:
    return next((part for part in gate.split(":") if re.fullmatch(r"[A-Z][A-Z0-9_]+", part)),
                "ENGINE_QA_GATE_FAILED")


def _engine_failure(j: Path, code: int) -> tuple[str, str]:
    try:
        log = (j / "job.log").read_text(errors="replace").rsplit("--- P8 dispatch", 1)[-1]
        if "WHITEBOARD_V3_EXECUTION_BODY_MISSING" in log:
            return ("ENGINE_RUNTIME_MISSING", "The whiteboard renderer isn't installed on this server. Your narration is saved; retry after the renderer is restored.")
        if "WHITEBOARD_LANGUAGE_DATA_MISSING" in log:
            return ("WHITEBOARD_LANGUAGE_DATA_MISSING", "The whiteboard planner's language data isn't installed on this server. Your narration is saved; retry after it is restored.")
        if "mkl_malloc: failed to allocate memory" in log or "The paging file is too small" in log:
            return ("RENDER_MEMORY_UNAVAILABLE", "The render server ran out of memory. Try again after freeing some memory.")
        if "NARRATION_PROVIDER_UNAVAILABLE" in log or (
            "edge_tts" in log and "WSServerHandshakeError: 403" in log
        ):
            return ("NARRATION_PROVIDER_UNAVAILABLE",
                    "The narration service couldn't generate your selected voice. Try again shortly or choose another voice.")
        if "NARRATION_ALIGNMENT_FAILED" in log:
            return ("NARRATION_ALIGNMENT_FAILED",
                    "The narration audio couldn't be prepared for rendering. Try again shortly.")
        if "GATE_REFUSED" in log and "overlap/off-frame" in log:
            return ("BOARD_SCENE_LAYOUT_REFUSED",
                    "Some scene drawings overlap or extend outside the selected video sizes. Your narration and settings are saved; review the direction and retry.")
        if "GATE_REFUSED" in log and any(reason in log for reason in (
                "semantic-loose", "semantic-art", "generic-art")):
            return ("BOARD_SCENE_ART_REFUSED",
                    "The whiteboard planner couldn't find suitable artwork for a scene. Your narration and settings are saved; review the direction and retry.")
    except OSError:
        pass
    return "ENGINE_EXIT_NONZERO", f"engine exited {code} with no outputs"


def _run(j: Path, argv: list[str], cwd: Path, env_extra: dict | None = None) -> int:
    log = (j / "job.log").open("a")
    log.write(f"\n--- P8 dispatch {time.strftime('%H:%M:%S')} ---\n{' '.join(argv)}\n")
    log.flush()
    proc = subprocess.run(argv, cwd=str(cwd), env=_env(env_extra),
                          stdout=log, stderr=subprocess.STDOUT)
    log.flush()
    log.close()
    return proc.returncode


def _whiteboard(j: Path, spec: dict, params: dict, subtype: dict) -> tuple[list[str], Path, dict]:
    engine = _engine_root(subtype.get("engineEnv"), subtype["engineFallback"])
    argv = [str(engine / "tools" / "nexstudio_job.py"),
            "--type", subtype["pipeline"],
            "--theme", params.get("theme", "light"),
            "--voice", params.get("voice", "emma"),
            "--title", spec["jobId"].upper(),
            "--aspects", ",".join(a.replace("x", ":") for a in params.get("aspects", ["16x9"])),
            "--out", str(j / "out"), "--job-id", spec["jobId"]]
    if params.get("duration"):
        argv += ["--duration", str(params["duration"])]
    if params.get("speed"):
        argv += ["--speed", str(params["speed"])]
    if params.get("scriptPath"):
        argv += ["--script", params["scriptPath"]]
    if params.get("voiceFile"):
        argv += ["--voice-file", params["voiceFile"]]
    if params.get("wordTimings"):
        argv += ["--word-timings", params["wordTimings"]]
    if params.get("accent"):
        argv += ["--accent", params["accent"]]
    if subtype.get("icons"):
        argv += ["--icons", subtype["icons"]]
    return argv, engine, {}


def _explainer(j: Path, spec: dict, params: dict, family: dict) -> tuple[list[str], Path, dict]:
    engine = _engine_root(family.get("engineEnv"), family["engineFallback"])
    argv = [str(engine / "tools" / "make_reel.py"),
            "--style", spec["subtype"],
            "--aspects", ",".join(params.get("aspects", ["16x9"])),
            "--out", str(j / "out"), "--film-id", spec["jobId"]]
    if params.get("duration"):
        argv += ["--duration", str(params["duration"])]
    if params.get("speed"):
        argv += ["--speed", str(params["speed"])]
    if params.get("voiceFile"):
        argv += ["--voice-file", params["voiceFile"]]
    else:
        argv += ["--script", params.get("script", ""), "--voice", params.get("voice", "andrew")]
    if params.get("media"):
        argv += ["--media", *params["media"]]
    if params.get("subject"):
        argv += ["--subject", str(params["subject"])]
    return argv, engine, {}


def _presenter(j: Path, spec: dict) -> tuple[list[str], Path, dict]:
    return [str(ROOT / "scripts" / "presenter-job.py"), str(j)], ROOT, {}


def main() -> int:
    j = Path(sys.argv[1]).resolve()
    spec = json.loads((j / "engine_request.json").read_text())
    family_id, subtype_id = spec.get("family"), spec.get("subtype")
    params = spec.get("params") or {}

    registry = json.loads(REGISTRY.read_text())
    family = (registry.get("families") or {}).get(family_id)
    subtype = (family or {}).get("subtypes", {}).get(subtype_id.split(".")[0])
    if not family or not subtype or subtype.get("status") != "CERTIFIED_FOR_DISPATCH":
        _write_status(j, status="failed", finishedAt=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                      failureCode="SUBTYPE_NOT_CERTIFIED",
                      error=f"{family_id}/{subtype_id} is not a certified dispatch subtype.")
        _result(j, "TECHNICAL_RETRY_REQUIRED", family=family_id, subtype=subtype_id,
                code="SUBTYPE_NOT_CERTIFIED", detail=f"{family_id}/{subtype_id} not in site-dispatch.json")
        return 2

    if family_id == "whiteboard":
        argv, cwd, env_extra = _whiteboard(j, spec, params, subtype)
        url_prefix = f"/api/v1/whiteboards/{spec['jobId']}/files"
    elif family_id == "explainer":
        argv, cwd, env_extra = _explainer(j, spec, params, family)
        url_prefix = f"/api/v1/explainers/{spec['jobId']}/files"
    elif family_id == "presenter":
        argv, cwd, env_extra = _presenter(j, spec)
        url_prefix = f"/api/v1/presenters/{spec['jobId']}/files"
    else:
        _write_status(j, status="failed", failureCode="FAMILY_UNKNOWN")
        _result(j, "TECHNICAL_RETRY_REQUIRED", family=family_id, subtype=subtype_id,
                code="FAMILY_UNKNOWN")
        return 2

    code = _run(j, [sys.executable, *argv], cwd, env_extra)

    if family_id == "presenter":
        # presenter-job.py owns status.json; the runner only records the P8 envelope.
        # If the job died before writing a terminal status, close it here so the
        # job never reads "running" forever.
        status = json.loads((j / "status.json").read_text()) if (j / "status.json").exists() else {}
        if status.get("status") not in ("done", "failed"):
            _write_status(j, status="failed", exitCode=code,
                          failureCode="PRESENTER_JOB_FAILED",
                          error="presenter pipeline exited without a terminal status",
                          finishedAt=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
            status = json.loads((j / "status.json").read_text())
        done = status.get("status") == "done" and code == 0
        _result(j, "FINAL_OUTPUT_READY" if done else "TECHNICAL_RETRY_REQUIRED",
                family=family_id, subtype=subtype_id,
                code=None if done else "PRESENTER_JOB_FAILED",
                artifacts=_artifacts(j / "files"),
                technicalQa={"exitCode": code, "statusJson": status})
        return 0 if done else 1

    outputs = _manifest_outputs(j, url_prefix)
    if code == 0 and outputs:
        _write_status(j, status="done", exitCode=0, outputs=outputs,
                      finishedAt=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        _result(j, "FINAL_OUTPUT_READY", family=family_id, subtype=subtype_id,
                artifacts=_artifacts(j / "files"),
                technicalQa={"exitCode": 0, "outputs": outputs})
        return 0

    gate = _first_gate_failure(j)
    failure_code, failure_message = _engine_failure(j, code)
    _write_status(j, status="failed", exitCode=code,
                  failureCode=(_gate_code(gate) if gate else failure_code),
                  error=gate or failure_message,
                  finishedAt=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    _result(j, "TECHNICAL_RETRY_REQUIRED", family=family_id, subtype=subtype_id,
            code=failure_code if not gate else "ENGINE_QA_GATE_FAILED",
            detail=gate or failure_message, artifacts=[])
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # never leave a job dir without a terminal status
        j = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
        if j and j.exists():
            _write_status(j, status="failed", failureCode="DISPATCH_INTERNAL_ERROR", error=str(exc))
            _result(j, "TECHNICAL_RETRY_REQUIRED", code="DISPATCH_INTERNAL_ERROR", detail=str(exc))
        raise
