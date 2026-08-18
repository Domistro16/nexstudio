from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Set

from .contracts import ContractViolation, reject_geometry_code_authority, require_exact_keys

HARD_GATE_DIMENSIONS = {
    "EVIDENCE_TRUTH",
    "DEPARTMENT_COMPLETENESS",
    "STORY_COHERENCE",
    "STRUCTURAL_VISUAL_INTENT",
    "STRUCTURAL_ART_DIRECTION",
    "STRUCTURAL_CINEMATOGRAPHY_DIRECTION",
    "STRUCTURAL_EDITORIAL_DIRECTION",
    "STRUCTURAL_MOTION_EXECUTABILITY",
    "STRUCTURAL_SOUND_RIGHTS_AND_FUNCTION",
    "FINAL_PAYOFF",
    "TECHNICAL_BODY_VETOES",
}

CRAFT_DIMENSIONS = (
    "story_clarity",
    "visual_communication",
    "art_craft",
    "visual_hierarchy",
    "cinematography",
    "editorial_rhythm",
    "motion_intentionality",
    "sound_design",
    "final_payoff",
    "commercial_finish",
)

TASTE_DIMENSIONS = (
    "beauty_composition",
    "illustration_quality",
    "charm_appeal",
    "emotional_appropriateness",
    "originality",
    "contextual_appropriateness",
    "commercial_believability",
    "engagement_memorability",
    "authorship_specificity",
    "reference_independence",
    "aesthetic_coherence",
    "emotional_resonance",
)

HUMAN_REVIEW_DIMENSIONS = (
    "story_clarity",
    "visual_communication",
    "illustration_art_quality",
    "character_subject_storytelling",
    "visual_hierarchy",
    "originality_appropriateness",
    "continuity_transformation",
    "motion_intentionality",
    "cinematography",
    "editorial_rhythm",
    "sound_design",
    "beauty_composition_taste",
    "charm_appeal",
    "emotional_appropriateness",
    "final_payoff",
    "commercial_believability",
    "engagement_memorability",
    "authorship_specificity",
    "reference_independence",
    "aesthetic_coherence",
    "emotional_resonance",
)

CRITICAL_HUMAN_DIMENSIONS = {
    "story_clarity",
    "visual_communication",
    "illustration_art_quality",
    "continuity_transformation",
    "final_payoff",
    "commercial_believability",
    "engagement_memorability",
    "authorship_specificity",
    "reference_independence",
    "aesthetic_coherence",
    "emotional_resonance",
}


def _validate_scored_dimension(name: str, value: Dict[str, Any]) -> None:
    require_exact_keys(value, {"score", "confidence", "rationale"}, label=f"score.{name}")
    if not isinstance(value["score"], (int, float)) or isinstance(value["score"], bool) or not 0 <= float(value["score"]) <= 10:
        raise ContractViolation(f"{name}.score must be 0..10")
    if value["confidence"] not in {"LOW", "MEDIUM", "HIGH"}:
        raise ContractViolation(f"{name}.confidence invalid")
    if not str(value["rationale"]).strip():
        raise ContractViolation(f"{name}.rationale required")


def validate_final_producer_output(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractViolation("final producer output must be object")
    reject_geometry_code_authority(payload)
    require_exact_keys(
        payload,
        {
            "verdict",
            "hard_gates",
            "craft_scores",
            "taste_judgments",
            "divergence",
            "uncertainty",
            "strengths",
            "issues",
            "revision_plan",
            "commercial_recommendation",
        },
        {"department_revisions"},
        label="final producer output",
    )
    if payload["verdict"] not in {"ACCEPT", "REVISE", "REJECT", "ESCALATE_HUMAN"}:
        raise ContractViolation("invalid final producer verdict")
    if payload["commercial_recommendation"] not in {
        "DO_NOT_RENDER",
        "RENDER_FOR_INTERNAL_REVIEW",
        "MACHINE_ACCEPT_HUMAN_REVIEW_REQUIRED",
        "HUMAN_REVIEW_REQUIRED",
    }:
        raise ContractViolation("invalid commercial_recommendation")
    if not isinstance(payload["hard_gates"], list) or not payload["hard_gates"]:
        raise ContractViolation("hard_gates required")
    seen: Set[str] = set()
    for gate in payload["hard_gates"]:
        require_exact_keys(gate, {"dimension", "status", "code", "evidence"}, label="hard_gate")
        if gate["dimension"] not in HARD_GATE_DIMENSIONS:
            raise ContractViolation(f"unknown hard gate dimension: {gate['dimension']}")
        if gate["dimension"] in seen:
            raise ContractViolation(f"duplicate hard gate dimension: {gate['dimension']}")
        seen.add(gate["dimension"])
        if gate["status"] not in {"PASS", "FAIL", "UNKNOWN"}:
            raise ContractViolation("invalid hard gate status")
        if not isinstance(gate["evidence"], list):
            raise ContractViolation("hard gate evidence must be array")
    require_exact_keys(payload["craft_scores"], set(CRAFT_DIMENSIONS), label="craft_scores")
    for name in CRAFT_DIMENSIONS:
        _validate_scored_dimension(name, payload["craft_scores"][name])
    require_exact_keys(payload["taste_judgments"], set(TASTE_DIMENSIONS), label="taste_judgments")
    for name in TASTE_DIMENSIONS:
        _validate_scored_dimension(name, payload["taste_judgments"][name])
    div = payload["divergence"]
    require_exact_keys(div, {"novelty", "conceptual_risk", "template_similarity", "rationale"}, label="divergence")
    for k in ("novelty", "conceptual_risk", "template_similarity"):
        if not isinstance(div[k], (int, float)) or isinstance(div[k], bool) or not 0 <= float(div[k]) <= 10:
            raise ContractViolation(f"divergence.{k} must be 0..10")
    unc = payload["uncertainty"]
    require_exact_keys(unc, {"confidence", "reasons", "human_review_required", "multimodal_evidence_complete"}, label="uncertainty")
    if unc["confidence"] not in {"LOW", "MEDIUM", "HIGH"}:
        raise ContractViolation("uncertainty.confidence invalid")
    if not isinstance(unc["reasons"], list) or not isinstance(unc["human_review_required"], bool) or not isinstance(unc["multimodal_evidence_complete"], bool):
        raise ContractViolation("uncertainty fields invalid")
    if not isinstance(payload["strengths"], list) or not isinstance(payload["issues"], list) or not isinstance(payload["revision_plan"], list):
        raise ContractViolation("strengths/issues/revision_plan must be arrays")
    department_revisions = payload.get("department_revisions", [])
    if not isinstance(department_revisions, list):
        raise ContractViolation("department_revisions must be array")
    allowed_departments = {"STORY","VISUAL_CONCEPT","ART_DIRECTION","CINEMATOGRAPHY","EDITORIAL_RHYTHM","MOTION_PERFORMANCE","SOUND_DIRECTION"}
    for item in department_revisions:
        require_exact_keys(item, {"owner_department","issue_code","required_change","preserve","priority"}, label="department_revision")
        if item["owner_department"] not in allowed_departments:
            raise ContractViolation("department_revision owner invalid")
        if item["priority"] not in {"HIGH","MEDIUM","LOW"}:
            raise ContractViolation("department_revision priority invalid")
        if not str(item["issue_code"]).strip() or not str(item["required_change"]).strip() or not isinstance(item["preserve"], list):
            raise ContractViolation("department_revision content invalid")
    # A final critic may not hide failure behind a blended average.
    if any(k in payload for k in ("overall_score", "quality_score", "final_score", "weighted_score")):
        raise ContractViolation("single aggregate quality score is forbidden")
    if any(g["status"] == "FAIL" for g in payload["hard_gates"]) and payload["verdict"] == "ACCEPT":
        raise ContractViolation("hard-gate failure cannot be ACCEPT")
    if payload["verdict"] != "ACCEPT" and not payload["issues"]:
        raise ContractViolation("non-accepted final review requires issues")
    if payload["verdict"] == "ACCEPT":
        if payload["issues"]:
            raise ContractViolation("ACCEPT final review cannot contain blocking issues")
        if payload["revision_plan"]:
            raise ContractViolation("ACCEPT final review cannot contain a revision plan")
        if department_revisions:
            raise ContractViolation("ACCEPT final review cannot contain department revisions")
        if payload["commercial_recommendation"] == "DO_NOT_RENDER":
            raise ContractViolation("ACCEPT final review cannot recommend DO_NOT_RENDER")
    return deepcopy(payload)


def validate_human_review(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractViolation("human review must be object")
    require_exact_keys(
        payload,
        {"reviewer_id", "reviewer_provenance", "blind", "independent", "scores", "hard_rejects", "notes"},
        label="human review",
    )
    if not str(payload["reviewer_id"]).strip() or not str(payload["reviewer_provenance"]).strip():
        raise ContractViolation("human reviewer provenance required")
    if payload["blind"] is not True or payload["independent"] is not True:
        raise ContractViolation("human review must be blind and independent")
    require_exact_keys(payload["scores"], set(HUMAN_REVIEW_DIMENSIONS), label="human review scores")
    for name, score in payload["scores"].items():
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= float(score) <= 10:
            raise ContractViolation(f"human score {name} must be 0..10")
    if not isinstance(payload["hard_rejects"], list):
        raise ContractViolation("hard_rejects must be array")
    return deepcopy(payload)


def human_review_gate(payload: Dict[str, Any]) -> Dict[str, Any]:
    p = validate_human_review(payload)
    scores = {k: float(v) for k, v in p["scores"].items()}
    mean = sum(scores.values()) / len(scores)
    low = {k: v for k, v in scores.items() if v < 9.0}
    critical_low = {k: scores[k] for k in CRITICAL_HUMAN_DIMENSIONS if scores[k] < 9.5}
    passed = mean >= 9.5 and not low and not critical_low and not p["hard_rejects"]
    return {
        "status": "PASS" if passed else "FAIL",
        "mean": round(mean, 4),
        "below_9": low,
        "critical_below_9_5": critical_low,
        "hard_rejects": deepcopy(p["hard_rejects"]),
    }
