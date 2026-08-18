from __future__ import annotations

import copy
import importlib
import sys
from pathlib import Path
from typing import Any, Dict


class AuthoritativeBodyServices:
    """Adapter over the existing Gates 1-10 body.

    The adapter returns verdict/evidence only. It never writes creative state.
    """

    def __init__(self, explainer_motion_root: str | Path):
        self.root = Path(explainer_motion_root)
        runtime = self.root / "public-hardening-v1" / "runtime"
        if not runtime.exists():
            raise FileNotFoundError(runtime)
        if str(runtime) not in sys.path:
            sys.path.insert(0, str(runtime))
        self.public_hardening = importlib.import_module("public_hardening")
        self.public_capability = importlib.import_module("public_capability")

    def semantic_validate(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        result = self.public_hardening.validate_semantic_candidate(
            copy.deepcopy(candidate), min_confidence=.78, allow_assumptions=False
        )
        return {
            "verdict": "ACCEPT" if result.get("ok") else "VETO",
            "evidence": {
                "validator": "GATES1-10.public_hardening.validate_semantic_candidate",
                "blocked": bool(result.get("blocked")),
                "failure": copy.deepcopy(result.get("failure")),
                "version": result.get("version"),
            },
            "validated_graph": result.get("graph"),
        }

    def capability_validate(self, graph: Dict[str, Any]) -> Dict[str, Any]:
        result = self.public_capability.resolve(copy.deepcopy(graph))
        return {
            "verdict": "FAIL_CLOSED" if result.get("blocked") else "ACCEPT",
            "evidence": {
                "validator": "GATES1-10.public_capability.resolve",
                "blocked": bool(result.get("blocked")),
                "failure": copy.deepcopy(result.get("failure")),
                "coverage": copy.deepcopy(result.get("coverage")),
            },
            "capability": result,
        }
