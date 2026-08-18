from __future__ import annotations

import json
import sys
from typing import Any, Dict

from orchestrator import classify_exception, run_finalize_p8, run_full_p8


def progress(phase: str, payload: Dict[str, Any]) -> None:
    sys.stderr.write(json.dumps({"type": "progress", "phase": phase, "payload": payload}, separators=(",", ":")) + "\n")
    sys.stderr.flush()


def main() -> int:
    try:
        request = json.load(sys.stdin)
        if not isinstance(request, dict):
            raise ValueError("request must be a JSON object")
        if request.get("operation") == "FINALIZE_WITH_MULTIMODAL_EVIDENCE":
            result = run_finalize_p8(request, progress=progress)
        else:
            result = run_full_p8(request, progress=progress)
    except Exception as error:  # the bridge converts this structured boundary; no traceback leaks to browser
        result = classify_exception(error)
    sys.stdout.write(json.dumps(result, separators=(",", ":"), ensure_ascii=False))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
