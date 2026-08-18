from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Dict, List

from .contracts import validate_producer_output
from .provider import CreativeModelProvider
from .review_governance import calibrate_review, release_decision_law


class ExecutiveProducer:
    """Independent critic. Mechanical preflight is a floor, never a taste score."""

    GENERIC_PHRASES = (
        "grid of cards", "card grid", "dashboard of tiles", "connector network",
        "node network", "icon row", "row of icons", "generic pipeline",
        "series of boxes", "boxes connected", "tiny icon",
    )
    GENERIC_HEROES = {"icon", "card", "box", "node", "generic symbol", "dashboard"}

    PRODUCTION_VALIDATION_MARKERS = (
        "food-stylist", "food stylist", "practical test", "practically test",
        "practical validation", "rehearse practically", "measured test",
        "measured response", "measured interval", "test result", "tested interval",
        "demonstrated preparation", "defined recipe", "fill depth",
        "physical test", "real-world test", "real world test", "production test",
        "empirical validation", "measured timing", "measured transition",
    )

    @staticmethod
    def _issue_text(issue: Dict[str, Any]) -> str:
        if not isinstance(issue, dict):
            return str(issue or "")
        return " ".join(str(issue.get(k) or "") for k in (
            "area", "category", "issue", "finding", "impact", "required_change", "repair", "detail"
        )).strip()

    @classmethod
    def _requires_external_production_validation(cls, issue: Dict[str, Any]) -> bool:
        text = cls._issue_text(issue).lower()
        return any(marker in text for marker in cls.PRODUCTION_VALIDATION_MARKERS)

    @staticmethod
    def _required_change(issue: Dict[str, Any]) -> str:
        if not isinstance(issue, dict):
            return str(issue or "").strip()
        for key in ("required_change", "repair", "detail", "issue", "finding"):
            value = str(issue.get(key) or "").strip()
            if value:
                return value
        return "Resolve the remaining concept-stage Producer issue."

    @classmethod
    def _split_external_validation_requirement(cls, issue: Dict[str, Any]) -> tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
        """Split mixed concept defects from impossible concept-stage proof demands."""
        if not isinstance(issue, dict):
            return deepcopy(issue), None
        change_key = "required_change" if "required_change" in issue else ("repair" if "repair" in issue else None)
        change = str(issue.get(change_key) or "") if change_key else ""
        sentences=[x.strip() for x in re.split(r"(?<=[.!?])\s+", change) if x.strip()]
        external=[x for x in sentences if any(m in x.lower() for m in cls.PRODUCTION_VALIDATION_MARKERS)]
        internal=[x for x in sentences if x not in external]
        finding=" ".join(str(issue.get(k) or "") for k in ("issue","finding","detail")).lower()
        intrinsic_markers=(
            "unsafe","scorch","overheat","instant","immediate","implausib","contradict","mismatch",
            "repetition","extra ","generic","weak","unclear","ambigu","thicken","violent","large bubble",
            "product appear","product may appear","continuity","pacing","action count","forced",
        )
        intrinsic=any(m in finding for m in intrinsic_markers)
        if external and not internal and not intrinsic:
            deferred=deepcopy(issue)
            deferred["deferred_reason"]="Requires empirical/physical production evidence unavailable at concept stage."
            return None,deferred
        if external:
            blocking=deepcopy(issue)
            if change_key:
                blocking[change_key]=" ".join(internal).strip() or (
                    "Express a physically plausible observable behavior without fabricating measured production evidence."
                )
            deferred=deepcopy(issue)
            deferred["deferred_reason"]="Empirical portion of this mixed issue must be validated downstream in production."
            if change_key:
                deferred[change_key]=" ".join(external).strip()
            return blocking,deferred
        return deepcopy(issue),None

    def _apply_department_boundary(self, review: Dict[str, Any], *, editable_contract: Dict[str, Any] | None) -> Dict[str, Any]:
        """Keep empirical production proof downstream without lowering concept quality.

        Implausible physics, unsafe staging, genericity, weak causality and continuity remain
        blocking. Only the demand to *prove* them with unavailable real-world measurements is
        deferred. Mixed issues are split so the concept defect remains active while the physical
        test requirement travels downstream.
        """
        out = deepcopy(review)
        if not editable_contract or str(editable_contract.get("owner_department") or "") not in {"STORY", "VISUAL_CONCEPT"}:
            return out
        blocking=[];deferred=[]
        for issue in out.get("issues") or []:
            b,d=self._split_external_validation_requirement(issue)
            if b is not None: blocking.append(b)
            if d is not None: deferred.append(d)
        if not deferred:
            return out
        out["issues"] = blocking
        out["deferred_production_validations"] = deferred
        note = str(out.get("notes") or "").strip()
        suffix = f"Deferred {len(deferred)} empirical/production-only validation requirement(s) downstream; no measured result may be fabricated at concept stage."
        out["notes"] = (note + " " + suffix).strip()
        if not blocking:
            out["verdict"] = "ACCEPT"
            out["revision_brief"] = ""
        else:
            changes=[]
            for issue in blocking:
                change=self._required_change(issue)
                if change and change not in changes: changes.append(change)
            out["revision_brief"] = "Resolve only the remaining concept-stage issues: " + " ".join(changes)
        return out


    @staticmethod
    def _review_questions(owner_department: str) -> List[str]:
        if owner_department == "STORY":
            return [
                "Does this candidate commit to one clear governing narrative proposition rather than comparing or selecting multiple strategy routes inside the candidate?",
                "Is the governing Story specific to this exact customer brief, with precise heat control materially causing the human usefulness rather than merely appearing beside it?",
                "Does the Story establish a believable human or experiential tension and a causal audience-state transformation without leaning on sentimental decoration?",
                "Does each beat change the situation or the audience's understanding, with an economical progression appropriate to the requested duration?",
                "Are the hero, opening contract, beat progression, and final payoff coherent enough to hand downstream to Visual Concept without prescribing shot-level execution?",
                "Is the Story distinctive enough that removing the brief-specific product behavior would collapse the idea, rather than leaving a transferable generic commercial?",
                "Is this a filmable narrative argument rather than a feature list, mechanism catalogue, or strategy-selection essay?",
                "Does the final payoff feel earned by the preceding causal chain?",
                "Would a strong studio advance this Story to Visual Concept?",
                "Do not demand concept_signature, rehearsal_states, memorability_device, originality_guard, art direction, shot design, edit design, motion design, or sound design from Story; those belong to later departments.",
                "If revision is required, every requested change must be within editable_contract and must repair Story-owned fields only.",
                "At Story stage, reject physically implausible claims but do NOT require fabricated measurements, recipes, lab/food-stylist results, measured response times, or production evidence. State empirical checks as downstream production validation requirements.",
            ]
        return [
            "Is there one strong visual argument?",
            "Does the concept signature make this unmistakably specific to this brief rather than transferable to another client?",
            "Does the authored rehearsal-state sequence form a compelling, brief-specific visual argument before Art Direction?",
            "Is the memorability device genuinely distinctive rather than an obvious first-answer metaphor or template?",
            "Does the originality guard demonstrate reference independence instead of imitation?",
            "Does every beat create a visible consequence and preserve a meaningful world/continuity handoff?",
            "Does it change what the audience understands or feels?",
            "Is the hero commercially strong and legible?",
            "Is this a film rather than a mechanism catalogue?",
            "Does the visual strategy escalate and pay off?",
            "Would a strong studio send this concept to a client?",
            "If revision is required, is every requested change within editable_contract? Never demand an adapter-generated or downstream-owned field from this Director.",
            "At Story/Visual Concept stage, reject physically implausible claims but do NOT require fabricated real-world measurements, recipes, lab/food-stylist test results, measured response times, or production evidence. State such empirical checks as downstream production validation requirements instead of using their absence as a reason to reject an otherwise strong concept.",
            "A concept may specify the observable behavior production must validate; it must not pretend that validation has already happened.",
        ]

    @staticmethod
    def _compact_revision_context(context: Dict[str, Any] | None) -> Dict[str, Any]:
        if not isinstance(context,dict):
            return {}
        return {k:deepcopy(context.get(k)) for k in (
            "department","owner_department","source_department","repair_mode","strategy_replan_required",
            "issues","sticky_requirements","requirements","exhausted_strategy_signatures",
        ) if context.get(k) not in (None, [], {}, "")}

    def __init__(self, provider: CreativeModelProvider):
        self.provider = provider

    def mechanical_preflight(self, candidate: Dict[str, Any], story: Dict[str, Any]) -> List[Dict[str, str]]:
        issues: List[Dict[str, str]] = []
        corpus = " ".join(
            [candidate.get("visual_thesis", ""), candidate.get("rationale", ""), candidate.get("camera_idea", "")]
            + [str(x.get("visual_action", "")) for x in candidate.get("beat_treatments", [])]
        ).lower()
        for phrase in self.GENERIC_PHRASES:
            if phrase in corpus:
                issues.append({"code": "GENERIC_VISUAL_GRAMMAR", "detail": phrase})
        if candidate.get("hero_kind", "").strip().lower() in self.GENERIC_HEROES:
            issues.append({"code": "WEAK_HERO", "detail": candidate.get("hero_kind", "")})
        if len(candidate.get("transformation", "").strip()) < 5 or candidate.get("transformation", "").strip().lower() in {"reveal", "appear", "fade in"}:
            issues.append({"code": "WEAK_TRANSFORMATION", "detail": candidate.get("transformation", "")})
        treatments = candidate.get("beat_treatments", [])
        actions = [str(x.get("visual_action", "")).strip().lower() for x in treatments]
        if len(actions) >= 3 and len(set(actions)) == 1:
            issues.append({"code": "SERIAL_REPETITION", "detail": actions[0]})
        if story.get("film_thesis", {}).get("final_payoff") and treatments:
            last = treatments[-1]
            if len(str(last.get("audience_takeaway", "")).strip()) < 8:
                issues.append({"code": "WEAK_PAYOFF_STATE", "detail": "final audience takeaway too weak"})
        return issues

    def review(self, production_id: str, brief: Dict[str, Any], story: Dict[str, Any], candidate: Dict[str, Any], *, revision_context: Dict[str, Any] | None = None, editable_contract: Dict[str, Any] | None = None) -> Dict[str, Any]:
        owner_department = str((editable_contract or {}).get("owner_department") or "VISUAL_CONCEPT")
        mechanical = self.mechanical_preflight(candidate, story)
        review_brief=deepcopy(brief)
        embedded_revision=review_brief.pop("autonomous_revision_context",None)
        review_brief.pop("autonomous_repair_context",None)
        compact_revision=self._compact_revision_context(revision_context if isinstance(revision_context,dict) else embedded_revision)
        request = {
            "production_id": production_id,
            "brief": review_brief,
            "film_thesis": deepcopy(story["film_thesis"]),
            "beats": deepcopy(story["beats"]),
            "candidate": deepcopy(candidate),
            "mechanical_preflight": deepcopy(mechanical),
            "revision_context": compact_revision,
            "editable_contract": deepcopy(editable_contract or {}),
            "instruction": {
                "role": "Independent Executive Producer",
                "review_scope": owner_department,
                "questions": self._review_questions(owner_department),
                "release_decision_law": release_decision_law(owner_department),
            },
        }
        model_review = validate_producer_output(self.provider.complete("producer", request))
        model_review = self._apply_department_boundary(model_review, editable_contract=editable_contract)
        if mechanical:
            combined = deepcopy(model_review)
            combined["verdict"] = "REVISE" if model_review["verdict"] == "ACCEPT" else model_review["verdict"]
            mechanical_blockers=[]
            for issue in mechanical:
                item=deepcopy(issue); item["blocking"]=True; mechanical_blockers.append(item)
            combined["issues"] = [*mechanical_blockers, *combined["issues"]]
            if not str(combined["revision_brief"]).strip():
                combined["revision_brief"] = "Remove the generic visual grammar and rebuild around one dominant hero and causal transformation."
            combined["commercial_confidence"] = "LOW" if len(mechanical) >= 2 else "MEDIUM"
            model_review=combined
        model_review=calibrate_review(model_review,stage=owner_department)
        return validate_producer_output(model_review)
