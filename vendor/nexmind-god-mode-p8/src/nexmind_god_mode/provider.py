from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Protocol, Tuple


class ProviderError(RuntimeError):
    pass


class CreativeModelProvider(Protocol):
    def complete(self, task: str, request: Dict[str, Any]) -> Dict[str, Any]: ...


def canonical_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class CallRecord:
    task: str
    production_id: str
    iteration: int
    request_hash: str


class RecordedModelProvider:
    """Deterministic provider used for executable integration/regression tests.

    Recorded responses represent model outputs captured for a request. Production
    code is topic-agnostic; all topic-specific material lives in fixture data.
    This is intentionally NOT described as live-provider inference.
    """

    def __init__(self, responses: Dict[str, Any]):
        self.responses = copy.deepcopy(responses)
        self.calls: List[CallRecord] = []
        self.counts: Dict[Tuple[str, str], int] = {}

    def complete(self, task: str, request: Dict[str, Any]) -> Dict[str, Any]:
        production_id = str(request.get("production_id") or "")
        if not production_id:
            raise ProviderError("request.production_id is required")
        key = (production_id, task)
        iteration = self.counts.get(key, 0)
        self.counts[key] = iteration + 1
        fixture_key = f"{production_id}::{task}::{iteration}"
        if fixture_key not in self.responses:
            raise ProviderError(f"no recorded response for {fixture_key}")
        self.calls.append(CallRecord(task, production_id, iteration, canonical_hash(request)))
        return copy.deepcopy(self.responses[fixture_key])
