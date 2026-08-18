from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Dict, Iterable, Optional

from .p0_kernel import NexMindSupremeShowrunner, ProposalRef, AuthorityViolation, CandidateError


GOVERNED_SLOTS = {"film_thesis", "visual_concept"}


def _h(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ProducerGateError(RuntimeError):
    pass


class NexMindSupremeShowrunnerP2(NexMindSupremeShowrunner):
    """Adds Story/Visual Producer gate without weakening P0 authority laws."""

    def __init__(self, production_id: str, brief: Dict[str, Any], *, doctrine: Optional[Dict[str, Any]] = None):
        super().__init__(production_id, brief, doctrine=doctrine)
        self.state["p2_schema"] = "NexMindSupremeShowrunnerP2StateV1"
        self.state["producer_reviews"] = []
        self.state["p2_intelligence_gate"] = {"status": "OPEN"}

    def commit_decision(self, decision_slot: str, proposal: ProposalRef, *, require_diversity_from: Optional[Iterable[str]] = None) -> Dict[str, Any]:
        if decision_slot in GOVERNED_SLOTS:
            raise AuthorityViolation(f"{decision_slot} is Producer-governed in P2; use commit_reviewed_decision")
        return super().commit_decision(decision_slot, proposal, require_diversity_from=require_diversity_from)

    def register_producer_review(self, decision_slot: str, proposal: ProposalRef, review: Dict[str, Any]) -> str:
        self._assert_unlocked()
        if decision_slot not in GOVERNED_SLOTS:
            raise ProducerGateError(f"unsupported P2 producer slot: {decision_slot}")
        bucket = self.state["proposals"].get(proposal.department, {})
        rec = bucket.get(proposal.proposal_id)
        if not rec or rec["revision"] != self.state["revision"]:
            raise CandidateError("producer review target does not exist in current revision")
        review_id = _h({
            "production_id": self.state["production_id"],
            "revision": self.state["revision"],
            "slot": decision_slot,
            "department": proposal.department,
            "proposal_id": proposal.proposal_id,
            "payload_hash": _h(rec["payload"]),
            "review": review,
        })
        self.state["producer_reviews"].append({
            "review_id": review_id,
            "decision_slot": decision_slot,
            "department": proposal.department,
            "proposal_id": proposal.proposal_id,
            "payload_hash": _h(rec["payload"]),
            "review": copy.deepcopy(review),
            "revision": self.state["revision"],
        })
        if review.get("verdict") != "ACCEPT":
            self.state["quality_ledger"].append({
                "type": "EXECUTIVE_PRODUCER_REJECTION",
                "target_decision": decision_slot,
                "proposal_id": proposal.proposal_id,
                "review_id": review_id,
                "evidence": copy.deepcopy(review),
                "revision": self.state["revision"],
                "status": "OPEN",
            })
        self._event("EXECUTIVE_PRODUCER_REVIEW", {
            "decision_slot": decision_slot,
            "proposal_id": proposal.proposal_id,
            "review_id": review_id,
            "verdict": review.get("verdict"),
        })
        return review_id

    def commit_reviewed_decision(
        self,
        decision_slot: str,
        proposal: ProposalRef,
        review_id: str,
        *,
        require_diversity_from: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        self._assert_unlocked()
        matches = [x for x in self.state["producer_reviews"] if x["review_id"] == review_id]
        if len(matches) != 1:
            raise ProducerGateError("producer review token not found")
        review_rec = matches[0]
        if review_rec["decision_slot"] != decision_slot or review_rec["proposal_id"] != proposal.proposal_id or review_rec["department"] != proposal.department:
            raise ProducerGateError("producer review token does not match candidate")
        if review_rec["revision"] != self.state["revision"]:
            raise ProducerGateError("producer review belongs to stale revision")
        bucket = self.state["proposals"].get(proposal.department, {})
        rec = bucket.get(proposal.proposal_id)
        if not rec or review_rec["payload_hash"] != _h(rec["payload"]):
            raise ProducerGateError("candidate payload changed after producer review")
        if review_rec["review"].get("verdict") != "ACCEPT":
            raise ProducerGateError("Executive Producer did not accept candidate")
        # Close only rejection records for this exact slot/candidate that predate acceptance.
        for item in self.state["quality_ledger"]:
            if item.get("status") == "OPEN" and item.get("type") == "EXECUTIVE_PRODUCER_REJECTION" and item.get("target_decision") == decision_slot:
                item["status"] = "SUPERSEDED_BY_ACCEPTED_REVISION"
        committed = NexMindSupremeShowrunner.commit_decision(
            self,
            decision_slot,
            proposal,
            require_diversity_from=require_diversity_from,
        )
        committed["producer_review_id"] = review_id
        self.state["decisions"][decision_slot]["producer_review_id"] = review_id
        return committed

    def p2_gate(self) -> Dict[str, Any]:
        required = ["film_thesis", "visual_concept"]
        missing = [slot for slot in required if slot not in self.state["decisions"]]
        open_producer = [x for x in self.state["quality_ledger"] if x.get("status") == "OPEN" and x.get("type") == "EXECUTIVE_PRODUCER_REJECTION"]
        if missing or open_producer:
            raise ProducerGateError({"missing": missing, "open_producer_rejections": len(open_producer)})
        for slot in required:
            if not self.state["decisions"][slot].get("producer_review_id"):
                raise ProducerGateError(f"{slot} lacks producer acceptance token")
        self.state["p2_intelligence_gate"] = {
            "status": "PASS",
            "revision": self.state["revision"],
            "film_thesis_proposal": self.state["decisions"]["film_thesis"]["proposal_id"],
            "visual_concept_proposal": self.state["decisions"]["visual_concept"]["proposal_id"],
        }
        self._event("P2_INTELLIGENCE_GATE_PASS", copy.deepcopy(self.state["p2_intelligence_gate"]))
        return copy.deepcopy(self.state["p2_intelligence_gate"])
