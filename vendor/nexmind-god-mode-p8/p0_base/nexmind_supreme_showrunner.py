from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

SCHEMA_VERSION = "NexMindSupremeShowrunnerP0StateV1"
KERNEL_VERSION = "0.1.0-p0-authority-kernel"


class AuthorityViolation(RuntimeError):
    pass


class StateIntegrityError(RuntimeError):
    pass


class CreativeLockError(RuntimeError):
    pass


class CandidateError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(obj: Any) -> str:
    return hashlib.sha256(_canonical(obj).encode("utf-8")).hexdigest()


def _strategy_fingerprint(payload: Dict[str, Any]) -> str:
    """Fingerprints the *creative strategy*, not layout coordinates.

    P0 intentionally uses explicit semantic fields. A future model-based diversity
    critic can replace/augment this, but departments cannot satisfy diversity by
    moving the same boxes around.
    """
    strategy = {
        "representation": payload.get("representation"),
        "visual_thesis": payload.get("visual_thesis"),
        "hero_kind": payload.get("hero_kind"),
        "transformation": payload.get("transformation"),
        "camera_idea": payload.get("camera_idea"),
    }
    return _hash(strategy)


@dataclass(frozen=True)
class ProposalRef:
    department: str
    proposal_id: str


class NexMindSupremeShowrunner:
    """P0 authority kernel.

    This does NOT pretend to be the full creative intelligence. It establishes
    the authority, state, checkpoint, validator and replan laws that the future
    Story/Visual/Art/Cinema/Editorial/Motion/Sound intelligences must obey.
    """

    REQUIRED_LOCK_DECISIONS = (
        "film_thesis",
        "visual_concept",
        "art_direction",
        "storyboard",
    )
    CREATIVE_MUTATION_KEYS = {
        "film_thesis",
        "visual_concept",
        "visual_thesis",
        "hero",
        "hero_kind",
        "representation",
        "art_direction",
        "camera_idea",
        "scene_thesis",
        "storyboard",
        "film_score",
    }
    VALID_BODY_VERDICTS = {"ACCEPT", "VETO", "FAIL_CLOSED", "BOUNDED_REPAIR"}

    def __init__(self, production_id: str, brief: Dict[str, Any], *, doctrine: Optional[Dict[str, Any]] = None):
        if not production_id:
            raise ValueError("production_id is required")
        if not isinstance(brief, dict) or not brief:
            raise ValueError("brief must be a non-empty object")
        self.__authority_nonce = hashlib.sha256(f"{production_id}|{_utc_now()}".encode()).hexdigest()
        self.state: Dict[str, Any] = {
            "schema": SCHEMA_VERSION,
            "kernel_version": KERNEL_VERSION,
            "production_id": production_id,
            "brief": copy.deepcopy(brief),
            "revision": 0,
            "creative_locked": False,
            "evidence_ledger": [],
            "creative_memory_refs": [],
            "film_memory": {
                "shown": [],
                "learned_by_audience": [],
                "open_promises": [],
                "used_metaphors": [],
                "camera_grammar_used": [],
            },
            "capability_graph": {},
            "creative_doctrine": copy.deepcopy(doctrine or {}),
            "task_ledger": [],
            "progress_ledger": [],
            "quality_ledger": [],
            "proposals": {},
            "decisions": {},
            "body_validations": [],
            "legacy_events": [],
            "history": [],
        }
        self._event("PRODUCTION_STARTED", {"brief_hash": _hash(brief)})

    def _event(self, kind: str, payload: Dict[str, Any]) -> None:
        event = {
            "seq": len(self.state["history"]) + 1,
            "at": _utc_now(),
            "kind": kind,
            "revision": self.state["revision"],
            "payload": copy.deepcopy(payload),
        }
        event["event_hash"] = _hash({k: v for k, v in event.items() if k != "event_hash"})
        self.state["history"].append(event)

    def set_evidence(self, records: Iterable[Dict[str, Any]]) -> None:
        self._assert_unlocked()
        self.state["evidence_ledger"] = [copy.deepcopy(x) for x in records]
        self._event("EVIDENCE_LEDGER_UPDATED", {"count": len(self.state["evidence_ledger"])})

    def set_capability_graph(self, graph: Dict[str, Any]) -> None:
        self._assert_unlocked()
        self.state["capability_graph"] = copy.deepcopy(graph)
        self._event("CAPABILITY_GRAPH_UPDATED", {"hash": _hash(graph)})

    def submit_proposal(self, department: str, proposal_id: str, payload: Dict[str, Any]) -> ProposalRef:
        self._assert_unlocked()
        if not department or not proposal_id:
            raise CandidateError("department and proposal_id are required")
        if department.lower().startswith("legacy") or department == "DirectorV3":
            raise AuthorityViolation("Legacy Director is quarantined and cannot submit production-authority proposals")
        bucket = self.state["proposals"].setdefault(department, {})
        if proposal_id in bucket:
            raise CandidateError(f"duplicate proposal_id: {proposal_id}")
        record = {
            "proposal_id": proposal_id,
            "department": department,
            "payload": copy.deepcopy(payload),
            "strategy_fingerprint": _strategy_fingerprint(payload),
            "status": "PROPOSED",
            "revision": self.state["revision"],
        }
        bucket[proposal_id] = record
        self._event("DEPARTMENT_PROPOSAL_SUBMITTED", {
            "department": department,
            "proposal_id": proposal_id,
            "strategy_fingerprint": record["strategy_fingerprint"],
        })
        return ProposalRef(department, proposal_id)

    def candidate_diversity(self, department: str, proposal_ids: Iterable[str]) -> Dict[str, Any]:
        ids = list(proposal_ids)
        bucket = self.state["proposals"].get(department, {})
        found = [bucket[x] for x in ids if x in bucket]
        if len(found) != len(ids):
            missing = [x for x in ids if x not in bucket]
            raise CandidateError(f"missing proposals: {missing}")
        fingerprints = {x["strategy_fingerprint"] for x in found}
        return {
            "candidate_count": len(found),
            "distinct_strategy_count": len(fingerprints),
            "meaningfully_diverse": len(fingerprints) >= 2,
        }

    def subordinate_commit_attempt(self, department: str, proposal_id: str, decision_slot: str) -> None:
        # Explicit attack surface used by tests/adapters.
        self._event("AUTHORITY_ATTACK_BLOCKED", {
            "source": department,
            "proposal_id": proposal_id,
            "decision_slot": decision_slot,
        })
        raise AuthorityViolation("Departments propose; only NexMind Supreme Showrunner may commit")

    def legacy_commit_attempt(self, source: str, payload: Dict[str, Any]) -> None:
        self.state["legacy_events"].append({"source": source, "payload_hash": _hash(payload), "at": _utc_now()})
        self._event("LEGACY_AUTHORITY_ATTACK_BLOCKED", {"source": source, "payload_hash": _hash(payload)})
        raise AuthorityViolation("Legacy creative authority is quarantined")

    def commit_decision(
        self,
        decision_slot: str,
        proposal: ProposalRef,
        *,
        require_diversity_from: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        self._assert_unlocked()
        bucket = self.state["proposals"].get(proposal.department, {})
        rec = bucket.get(proposal.proposal_id)
        if not rec:
            raise CandidateError("proposal does not exist")
        if rec["revision"] != self.state["revision"]:
            raise CandidateError("proposal belongs to a stale revision")
        if require_diversity_from is not None:
            report = self.candidate_diversity(proposal.department, require_diversity_from)
            if not report["meaningfully_diverse"]:
                raise CandidateError("candidate set is not meaningfully diverse")
        committed = {
            "decision_slot": decision_slot,
            "department": proposal.department,
            "proposal_id": proposal.proposal_id,
            "payload": copy.deepcopy(rec["payload"]),
            "revision": self.state["revision"],
            "status": "COMMITTED_BY_SHOWRUNNER",
        }
        self.state["decisions"][decision_slot] = committed
        rec["status"] = "SELECTED_BY_SHOWRUNNER"
        self._event("SHOWRUNNER_DECISION_COMMITTED", {
            "decision_slot": decision_slot,
            "department": proposal.department,
            "proposal_id": proposal.proposal_id,
        })
        return copy.deepcopy(committed)

    def record_body_validation(
        self,
        service: str,
        verdict: str,
        evidence: Dict[str, Any],
        *,
        target_decision: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._assert_unlocked()
        verdict = verdict.upper()
        if verdict not in self.VALID_BODY_VERDICTS:
            raise ValueError(f"invalid body verdict: {verdict}")
        leaked = sorted(self.CREATIVE_MUTATION_KEYS.intersection(evidence.keys()))
        if leaked:
            self._event("BODY_CREATIVE_AUTHORITY_ATTACK_BLOCKED", {"service": service, "leaked_keys": leaked})
            raise AuthorityViolation(f"body service attempted creative mutation: {leaked}")
        record = {
            "service": service,
            "verdict": verdict,
            "target_decision": target_decision,
            "evidence": copy.deepcopy(evidence),
            "revision": self.state["revision"],
        }
        self.state["body_validations"].append(record)
        self._event("BODY_VALIDATION_RECORDED", {"service": service, "verdict": verdict, "target": target_decision})
        if verdict in {"VETO", "FAIL_CLOSED"}:
            self.state["quality_ledger"].append({
                "type": "BODY_VETO",
                "service": service,
                "target_decision": target_decision,
                "evidence": copy.deepcopy(evidence),
                "revision": self.state["revision"],
                "status": "OPEN",
            })
        return copy.deepcopy(record)

    def replan(self, reason: str, *, invalidate_slots: Optional[Iterable[str]] = None) -> None:
        self._assert_unlocked()
        old_revision = self.state["revision"]
        self.state["revision"] += 1
        slots = list(invalidate_slots or self.state["decisions"].keys())
        invalidated = []
        for slot in slots:
            if slot in self.state["decisions"]:
                old = self.state["decisions"].pop(slot)
                invalidated.append({"slot": slot, "proposal_id": old["proposal_id"]})
        for item in self.state["quality_ledger"]:
            if item.get("status") == "OPEN":
                item["status"] = "SUPERSEDED_BY_REPLAN"
        self._event("SHOWRUNNER_REPLAN", {
            "reason": reason,
            "from_revision": old_revision,
            "to_revision": self.state["revision"],
            "invalidated": invalidated,
        })

    def creative_lock(self) -> Dict[str, Any]:
        self._assert_unlocked()
        missing = [x for x in self.REQUIRED_LOCK_DECISIONS if x not in self.state["decisions"]]
        open_vetoes = [x for x in self.state["quality_ledger"] if x.get("status") == "OPEN"]
        if missing or open_vetoes:
            raise CreativeLockError({
                "missing_decisions": missing,
                "open_veto_count": len(open_vetoes),
            })
        self.state["creative_locked"] = True
        self._event("CREATIVE_LOCK_COMMITTED", {"decisions": list(self.state["decisions"])})
        return {"locked": True, "revision": self.state["revision"], "state_hash": self.state_hash()}

    def _assert_unlocked(self) -> None:
        if self.state.get("creative_locked"):
            raise CreativeLockError("creative state is locked")

    def state_hash(self) -> str:
        return _hash(self.state)

    def checkpoint(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        envelope = {
            "schema": "NexMindSupremeShowrunnerCheckpointV1",
            "state": self.state,
            "state_hash": self.state_hash(),
        }
        p.write_text(json.dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8")
        return p

    @classmethod
    def resume(cls, path: str | Path) -> "NexMindSupremeShowrunner":
        p = Path(path)
        envelope = json.loads(p.read_text(encoding="utf-8"))
        state = envelope.get("state")
        if not isinstance(state, dict) or envelope.get("state_hash") != _hash(state):
            raise StateIntegrityError("checkpoint hash mismatch")
        if state.get("schema") != SCHEMA_VERSION:
            raise StateIntegrityError("unsupported state schema")
        obj = cls.__new__(cls)
        obj.__authority_nonce = hashlib.sha256(f"resume|{state['production_id']}|{_utc_now()}".encode()).hexdigest()
        obj.state = state
        obj._event("PRODUCTION_RESUMED", {"checkpoint_hash": envelope["state_hash"]})
        return obj
