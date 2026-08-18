from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

CRITICAL_CRAFT = ("story_clarity", "visual_communication", "final_payoff", "commercial_finish")
CRITICAL_TASTE = ("originality", "contextual_appropriateness", "commercial_believability", "engagement_memorability", "authorship_specificity", "reference_independence", "aesthetic_coherence", "emotional_resonance")


def _scores(group: Dict[str, Any]) -> Dict[str, float]:
    return {str(k): float((v or {}).get("score", 0.0)) for k, v in (group or {}).items() if isinstance(v, dict)}


def _mean(values):
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def studio_autonomous_quality_gate(review: Dict[str, Any], *, calibration: Dict[str, Any], multimodal_evidence: Dict[str, Any]) -> Dict[str, Any]:
    """Studio-specific elite final gate.

    This deliberately does not emit one blended quality score. Structural truth,
    craft, taste, divergence, uncertainty, calibration and multimodal evidence
    remain independent blockers. A strong average can never launder one weak gate.
    """
    review = deepcopy(review)
    hard_fail = [g.get("dimension") for g in review.get("hard_gates", []) if g.get("status") != "PASS"]
    craft = _scores(review.get("craft_scores", {}))
    taste = _scores(review.get("taste_judgments", {}))
    craft_low = {k: v for k, v in craft.items() if v < 9.0}
    taste_low = {k: v for k, v in taste.items() if v < 9.0}
    critical_craft_low = {k: craft.get(k, 0.0) for k in CRITICAL_CRAFT if craft.get(k, 0.0) < 9.5}
    critical_taste_low = {k: taste.get(k, 0.0) for k in CRITICAL_TASTE if taste.get(k, 0.0) < 9.5}
    low_confidence = [
        f"craft:{k}" for k, v in review.get("craft_scores", {}).items()
        if isinstance(v, dict) and v.get("confidence") == "LOW"
    ] + [
        f"taste:{k}" for k, v in review.get("taste_judgments", {}).items()
        if isinstance(v, dict) and v.get("confidence") == "LOW"
    ]
    divergence = review.get("divergence", {}) or {}
    novelty = float(divergence.get("novelty", 0.0))
    template_similarity = float(divergence.get("template_similarity", 10.0))
    mm_complete = (multimodal_evidence or {}).get("status") == "COMPLETE" and bool((multimodal_evidence or {}).get("perceptually_reviewed"))
    calibrated = (calibration or {}).get("status") == "CALIBRATED"
    uncertainty = review.get("uncertainty", {}) or {}
    reasons = []
    if not mm_complete: reasons.append("MULTIMODAL_EVIDENCE_INCOMPLETE")
    if not calibrated: reasons.append("STUDIO_TASTE_CALIBRATION_NOT_PROVEN")
    if hard_fail: reasons.append("HARD_GATES_NOT_ALL_PASS")
    if review.get("verdict") != "ACCEPT": reasons.append(f"FINAL_PRODUCER_{review.get('verdict', 'UNKNOWN')}")
    if craft and _mean(craft.values()) < 9.5: reasons.append("CRAFT_MEAN_BELOW_9_5")
    if taste and _mean(taste.values()) < 9.5: reasons.append("TASTE_MEAN_BELOW_9_5")
    if craft_low: reasons.append("CRAFT_DIMENSION_BELOW_9")
    if taste_low: reasons.append("TASTE_DIMENSION_BELOW_9")
    if critical_craft_low: reasons.append("CRITICAL_CRAFT_BELOW_9_5")
    if critical_taste_low: reasons.append("CRITICAL_TASTE_BELOW_9_5")
    if novelty < 7.5: reasons.append("NOVELTY_BELOW_STUDIO_FLOOR")
    if template_similarity > 2.5: reasons.append("TEMPLATE_SIMILARITY_TOO_HIGH")
    if low_confidence: reasons.append("LOW_CONFIDENCE_DIMENSIONS")
    if uncertainty.get("confidence") == "LOW": reasons.append("FINAL_UNCERTAINTY_LOW_CONFIDENCE")
    if bool(uncertainty.get("human_review_required", False)): reasons.append("FINAL_PRODUCER_REQUESTED_HUMAN_REVIEW")
    if review.get("revision_plan") and (calibrated or review.get("verdict") in {"REVISE", "REJECT"}): reasons.append("FINAL_PRODUCER_REVISION_PLAN_PRESENT")

    # Creative defects outrank calibration. Human review may bridge missing
    # calibration, but it may never launder a machine-detected quality failure.
    # Pure, well-scored uncertainty is different: after Studio taste is calibrated
    # it becomes the exceptional human-judgment path instead of a routine repair.
    non_creative_markers={
        "STUDIO_TASTE_CALIBRATION_NOT_PROVEN",
        "FINAL_PRODUCER_ESCALATE_HUMAN",
        "FINAL_PRODUCER_REQUESTED_HUMAN_REVIEW",
    }
    creative_reasons=[r for r in reasons if r not in non_creative_markers]
    if not mm_complete:
        disposition = "FAIL_CLOSED"
    elif hard_fail or review.get("verdict") in {"REVISE", "REJECT"} or creative_reasons:
        disposition = "REPAIR"
    elif not calibrated:
        disposition = "HUMAN_CALIBRATION_REQUIRED"
    elif review.get("verdict") == "ESCALATE_HUMAN" or bool(uncertainty.get("human_review_required", False)):
        disposition = "HUMAN_JUDGMENT_REQUIRED"
    else:
        disposition = "PASS"
    return {
        "schema": "StudioAutonomousQualityEvidenceV1",
        "status": disposition,
        "hard_gate_failures": hard_fail,
        "craft_mean": round(_mean(craft.values()), 4) if craft else None,
        "craft_below_9": craft_low,
        "critical_craft_below_9_5": critical_craft_low,
        "taste_mean": round(_mean(taste.values()), 4) if taste else None,
        "taste_below_9": taste_low,
        "critical_taste_below_9_5": critical_taste_low,
        "novelty": novelty,
        "template_similarity": template_similarity,
        "low_confidence_dimensions": low_confidence,
        "multimodal_complete": mm_complete,
        "calibration_status": (calibration or {}).get("status"),
        "reasons": reasons,
    }


def build_repair_request(review: Dict[str, Any], quality: Dict[str, Any], *, round_number: int, max_rounds: int = 0) -> Dict[str, Any]:
    """Build a quality-preserving hierarchical replan request.

    ``round_number`` is an audit sequence, not a permission to weaken quality and
    not a terminal retry budget. Local department attempts remain bounded inside
    P8. When the same scope cannot repair the film, ownership escalates upward.
    The production remains recoverable; a creative dead-end is not a customer
    failure state.
    """
    issues = [str(x) for x in review.get("issues", [])]
    plan = [str(x) for x in review.get("revision_plan", [])]
    hard = quality.get("hard_gate_failures", [])
    text = " ".join([*issues, *plan, *[str(x) for x in hard]]).lower()
    slots = []
    department_to_slot={"STORY":"film_thesis","VISUAL_CONCEPT":"visual_concept","ART_DIRECTION":"art_direction","CINEMATOGRAPHY":"cinematography","EDITORIAL_RHYTHM":"editorial_rhythm","MOTION_PERFORMANCE":"motion_performance","SOUND_DIRECTION":"sound_direction"}
    # Causal repair ownership is authored by the independent final judge. Never
    # infer a department from score names, issue keywords, or a static defect map.
    # If the judge cannot provide a valid causal owner, widen the repair safely to
    # the complete creative strategy instead of risking a confidently wrong local fix.
    for item in review.get("department_revisions",[]) or []:
        if not isinstance(item,dict): continue
        slot=department_to_slot.get(str(item.get("owner_department") or ""))
        if slot and slot not in slots: slots.append(slot)
    causal_owner_resolved=bool(slots)
    if not slots:
        slots = ["film_thesis", "visual_concept", "art_direction", "cinematography", "editorial_rhythm", "motion_performance", "sound_direction"]

    # Escalation is by creative scope, not by raising a retry allowance. Once the
    # local problem persists, the next run is authorized to change an earlier
    # decision and eventually the whole production strategy while preserving the
    # user brief, evidence truth, brand laws and the 9.5 quality floor.
    if round_number <= 1:
        scope = "RESPONSIBLE_DEPARTMENT" if causal_owner_resolved else "WHOLE_FILM_CAUSAL_DIAGNOSIS_MISSING"
    elif round_number == 2:
        scope = "UPSTREAM_VISUAL_STRATEGY"
        if "visual_concept" not in slots: slots.insert(0, "visual_concept")
    elif round_number == 3:
        scope = "WHOLE_FILM_CREATIVE_STRATEGY"
        slots = ["film_thesis", "visual_concept", "art_direction", "cinematography", "editorial_rhythm", "motion_performance", "sound_direction"]
    else:
        scope = "BEST_VIABLE_PREMIUM_STRATEGY"
        slots = ["film_thesis", "visual_concept", "art_direction", "cinematography", "editorial_rhythm", "motion_performance", "sound_direction"]

    return {
        "schema": "StudioAutonomousCreativeRepairRequestV2",
        "round": round_number,
        "escalation_scope": scope,
        "exhausted": False,
        "invalidate_slots": slots,
        "issues": issues,
        "revision_plan": plan,
        "quality_reasons": deepcopy(quality.get("reasons", [])),
        "production_disposition": "CONTINUE_REPLANNING",
        "quality_floor_may_weaken": False,
        "silent_generic_fallback_allowed": False,
        "law": "LOCAL_IDEA_MAY_FAIL__PAID_PRODUCTION_REPLANS__NEVER_LOWER_QUALITY_GATE",
    }
