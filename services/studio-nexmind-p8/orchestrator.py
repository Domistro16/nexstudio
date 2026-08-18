from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, Optional

ROOT = Path(__file__).resolve().parents[2]
P8_ROOT = ROOT / "vendor" / "nexmind-god-mode-p8"
sys.path.insert(0, str(P8_ROOT / "src"))

from nexmind_god_mode.art_director import ArtDirector
from nexmind_god_mode.art_showrunner_reasoner import ArtShowrunnerDecisionIntelligence
from nexmind_god_mode.cinematography_director import CinematographyDirector
from nexmind_god_mode.council import CreativeCouncil
from nexmind_god_mode.council_p3 import CreativeCouncilP3
from nexmind_god_mode.council_p45 import CreativeCouncilP45
from nexmind_god_mode.council_p6 import CreativeCouncilP6
from nexmind_god_mode.council_p7 import CreativeCouncilP7
from nexmind_god_mode.council_p8 import CreativeCouncilP8
from nexmind_god_mode.editorial_director import EditorialRhythmDirector
from nexmind_god_mode.editorial_timeline import EditorialTimelineCompiler
from nexmind_god_mode.executive_producer import ExecutiveProducer
from nexmind_god_mode.final_executive_producer import FinalExecutiveProducer
from nexmind_god_mode.final_producer_contracts import validate_human_review
from nexmind_god_mode.multimodal_evidence import build_multimodal_evidence
from nexmind_god_mode.final_production_dossier import FinalProductionDossierCompiler
from nexmind_god_mode.human_calibration import HumanCalibrationRegistry
from nexmind_god_mode.studio_quality import studio_autonomous_quality_gate, build_repair_request
from nexmind_god_mode.illustration_form_resolver import IllustrationFormResolver
from nexmind_god_mode.live_provider import LiveCreativeModelProvider
from nexmind_god_mode.motion_director import MotionPerformanceDirector
from nexmind_god_mode.p3_producer import P3ExecutiveProducer
from nexmind_god_mode.p45_producer import P45ExecutiveProducer
from nexmind_god_mode.p45_showrunner_reasoner import P45ShowrunnerDecisionIntelligence
from nexmind_god_mode.p6_producer import MotionExecutiveProducer
from nexmind_god_mode.p6_showrunner_reasoner import MotionShowrunnerDecisionIntelligence
from nexmind_god_mode.p7_producer import SoundExecutiveProducer
from nexmind_god_mode.p7_showrunner_reasoner import SoundShowrunnerDecisionIntelligence
from nexmind_god_mode.performer_capabilities import PerformerCapabilityRegistry
from nexmind_god_mode.provider import ProviderError
from nexmind_god_mode.showrunner_p8 import NexMindSupremeShowrunnerP8
from nexmind_god_mode.showrunner_reasoner import ShowrunnerDecisionIntelligence
from nexmind_god_mode.sound_director import SoundDirector
from nexmind_god_mode.sound_resources import SoundResourceRegistry
from nexmind_god_mode.story_director import StoryDirector
from nexmind_god_mode.storyboard_compiler import StoryboardCompiler, StoryboardGateError
from nexmind_god_mode.storyboard_compiler_v2 import TemporalStoryboardCompiler, TemporalStoryboardGateError
from nexmind_god_mode.storyboard_compiler_v3 import PerformanceStoryboardCompiler
from nexmind_god_mode.storyboard_compiler_v4 import SoundStoryboardCompiler
from nexmind_god_mode.visual_concept_director import VisualConceptDirector
from nexmind_god_mode.p0_kernel import CreativeLockError
from nexmind_god_mode.contracts import ContractViolation
from nexmind_god_mode.showrunner_p2 import ProducerGateError

from capability_adapter import build_capability_graph, load_current_capability_packet

Progress = Optional[Callable[[str, Dict[str, Any]], None]]


DEFAULT_CREATIVE_HARD_CEILING = 6
DEFAULT_BROADER_STRATEGY_REPLAN_ROUNDS = 3
DEFAULT_DIRECTOR_CONTRACT_REPAIR_LIMIT = 2
DEFAULT_NONSTORY_BROADER_LINEAGE_LIMIT = 1
DEPARTMENT_ORDER = [
    "STORY", "VISUAL_CONCEPT", "ART_DIRECTION", "CINEMATOGRAPHY",
    "EDITORIAL_RHYTHM", "MOTION_PERFORMANCE", "SOUND_DIRECTION",
]
# Execution dependencies, not a creative ideology. Departments may re-enter through
# causal repair; this graph exists so an upstream decision invalidates only outputs
# that actually depend on it.
DEPARTMENT_DEPENDENCIES = {
    "STORY": set(),
    "VISUAL_CONCEPT": {"STORY"},
    "ART_DIRECTION": {"VISUAL_CONCEPT"},
    "CINEMATOGRAPHY": {"ART_DIRECTION"},
    "EDITORIAL_RHYTHM": {"STORY"},
    "MOTION_PERFORMANCE": {"CINEMATOGRAPHY", "EDITORIAL_RHYTHM"},
    "SOUND_DIRECTION": {"MOTION_PERFORMANCE", "EDITORIAL_RHYTHM"},
}

DEPARTMENT_ESCALATION_OWNER = {
    "STORY": "STORY",
    "VISUAL_CONCEPT": "STORY",
    "ART_DIRECTION": "VISUAL_CONCEPT",
    "CINEMATOGRAPHY": "VISUAL_CONCEPT",
    "EDITORIAL_RHYTHM": "STORY",
    "MOTION_PERFORMANCE": "VISUAL_CONCEPT",
    "SOUND_DIRECTION": "EDITORIAL_RHYTHM",
}
DEPARTMENT_DECISION_SLOT = {
    "STORY": "film_thesis",
    "VISUAL_CONCEPT": "visual_concept",
    "ART_DIRECTION": "art_direction",
    "CINEMATOGRAPHY": "cinematography",
    "EDITORIAL_RHYTHM": "editorial_rhythm",
    "MOTION_PERFORMANCE": "motion_performance",
    "SOUND_DIRECTION": "sound_direction",
}
DEPARTMENT_INVALIDATION = {
    "STORY": ["film_thesis", "visual_concept", "art_direction", "storyboard", "cinematography", "editorial_rhythm", "storyboard_temporal", "motion_performance", "sound_direction", "final_producer"],
    "VISUAL_CONCEPT": ["visual_concept", "art_direction", "storyboard", "cinematography", "storyboard_temporal", "motion_performance", "sound_direction", "final_producer"],
    "ART_DIRECTION": ["art_direction", "storyboard", "cinematography", "storyboard_temporal", "motion_performance", "sound_direction", "final_producer"],
    "CINEMATOGRAPHY": ["cinematography", "storyboard_temporal", "motion_performance", "sound_direction", "final_producer"],
    "EDITORIAL_RHYTHM": ["editorial_rhythm", "storyboard_temporal", "motion_performance", "sound_direction", "final_producer"],
    "MOTION_PERFORMANCE": ["motion_performance", "sound_direction", "final_producer"],
    "SOUND_DIRECTION": ["sound_direction", "final_producer"],
}




HARD_DIRECTOR_CONTRACT_MARKERS = (
    "geometry leakage",
    "authority leakage",
    "renderer/code leakage",
)

def _is_repairable_director_contract_violation(error: Exception) -> bool:
    """Return True only for model-authored structural/craft contract misses.

    Authority, geometry and renderer/code leakage are hard safety/authority failures
    and must still fail closed. Other Director output contract misses are repairable
    within the owning department's bounded creative budget.
    """
    if not isinstance(error, ContractViolation):
        return False
    text = str(error).strip().lower()
    return not any(marker in text for marker in HARD_DIRECTOR_CONTRACT_MARKERS)

def _contract_repair_context(error: ContractViolation, department: str) -> Dict[str, Any]:
    detail = str(error).strip() or type(error).__name__
    return {
        "issues": [{
            "severity": "MAJOR",
            "area": "Director output contract",
            "issue": detail,
            "required_change": f"Repair the {department} output so it satisfies this exact contract requirement while preserving the creative intent and all accepted upstream decisions.",
        }],
        "strengths_to_preserve": [],
        "revision_briefs": [
            f"The previous {department} output was structurally invalid: {detail}. Return a materially equivalent or stronger creative answer that satisfies the contract exactly. Do not weaken the concept merely to pass validation."
        ],
        "producer_verdicts": ["CONTRACT_REPAIR_REQUIRED"],
        "rejected_candidates": [],
        "previous_output": None,
    }

def _schedule_director_contract_repair(sr: NexMindSupremeShowrunnerP8, department: str, error: ContractViolation) -> None:
    if not _is_repairable_director_contract_violation(error):
        raise error
    repair=sr.state.get("autonomous_creative_repair") or {}
    contract_repairs=repair.setdefault("contract_repairs",{})
    used=int(contract_repairs.get(department,0))
    if used >= DEFAULT_DIRECTOR_CONTRACT_REPAIR_LIMIT:
        # Repeated model-authored contract misses are not a provider outage. Consume
        # this creative attempt and force a materially new department strategy; if
        # the local quality budget is already exhausted, normal causal escalation
        # takes over. Reset the structural counter so the new lineage has its own
        # bounded correction allowance.
        contract_repairs[department]=0
        context=_contract_repair_context(error,department)
        prior=sr.state.get("brief",{}).get("autonomous_revision_context")
        if isinstance(prior,dict) and prior.get("department")==department:
            if prior.get("previous_output") is not None:
                context["previous_output"]=deepcopy(prior.get("previous_output"))
            context["strengths_to_preserve"]=deepcopy(prior.get("strengths_to_preserve") or [])
            context["deferred_production_validations"]=deepcopy(prior.get("deferred_production_validations") or [])
        _schedule_repair(sr,department,f"Repeated {department} output-contract failures require a materially new local strategy",context)
        return
    contract_repairs[department]=used+1
    # A structurally malformed Director object has not yet earned a creative-quality
    # attempt. Refund the just-reserved local creative attempt, but retain lifetime
    # telemetry and a separately bounded contract-repair count.
    attempts=repair.setdefault("attempts",{})
    attempts[department]=max(0,int(attempts.get(department,0))-1)
    context=_contract_repair_context(error,department)
    prior=sr.state.get("brief",{}).get("autonomous_revision_context")
    if isinstance(prior,dict) and prior.get("department")==department:
        if prior.get("previous_output") is not None:
            context["previous_output"]=deepcopy(prior.get("previous_output"))
        context["strengths_to_preserve"]=deepcopy(prior.get("strengths_to_preserve") or [])
        context["deferred_production_validations"]=deepcopy(prior.get("deferred_production_validations") or [])
    _schedule_repair(
        sr,
        department,
        f"{department} Director output contract requires autonomous repair",
        context,
    )


class CreativeRepairBudgetExhausted(RuntimeError):
    def __init__(self, department: str, attempts: int, maximum: int, *, reason: str = "", context: Optional[Dict[str, Any]] = None):
        super().__init__(f"{department}: creative repair budget exhausted after {attempts}/{maximum} attempts")
        self.department = department
        self.attempts = attempts
        self.maximum = maximum
        self.reason = str(reason or "")
        self.context = deepcopy(context or {})


def _adaptive_attempt_limits(request: Dict[str, Any]) -> Dict[str, int]:
    """Bound repair effort by production complexity/failure surface, not one global quota."""
    try:
        ceiling=int(request.get("creativeRepairHardCeiling", DEFAULT_CREATIVE_HARD_CEILING))
    except Exception:
        ceiling=DEFAULT_CREATIVE_HARD_CEILING
    ceiling=max(2,min(DEFAULT_CREATIVE_HARD_CEILING,ceiling))
    duration=float(request.get("durationSeconds") or 0)
    source_count=len(request.get("sourceEvidence") or []) + len(request.get("sourceDocuments") or [])
    reference_count=len(request.get("references") or [])
    complexity=(1 if duration>=45 else 0)+(1 if source_count>=6 else 0)+(1 if reference_count>=3 else 0)
    base={"STORY":2,"VISUAL_CONCEPT":3,"ART_DIRECTION":3,"CINEMATOGRAPHY":2,"EDITORIAL_RHYTHM":2,"MOTION_PERFORMANCE":3,"SOUND_DIRECTION":2}
    return {d:min(ceiling,n+(complexity if d in {"STORY","VISUAL_CONCEPT","ART_DIRECTION"} else min(1,complexity))) for d,n in base.items()}

def _ensure_repair_state(sr: NexMindSupremeShowrunnerP8, limits: Dict[str,int]) -> Dict[str, Any]:
    state = sr.state.setdefault("autonomous_creative_repair", {
        "schema": "NexMindAutonomousCreativeRepairV2",
        "policy": "ADAPTIVE_BOUNDED_CAUSAL_REPAIR__NO_QUALITY_OVERRIDE",
        "attempt_limits_by_department": deepcopy(limits),
        "attempts": {},
        "lifetime_attempts": {},
        "lineage_resets": [],
        "broader_strategy_replans": [],
        "contract_repairs": {},
        "ledger": [],
    })
    state["attempt_limits_by_department"] = deepcopy(limits)
    state.pop("max_attempts_per_department",None)
    state.setdefault("attempts", {})
    state.setdefault("lifetime_attempts", {})
    state.setdefault("lineage_resets", [])
    state.setdefault("broader_strategy_replans", [])
    state.setdefault("contract_repairs", {})
    state.setdefault("ledger", [])
    revision_ctx=sr.state.get("brief",{}).get("autonomous_revision_context")
    if isinstance(revision_ctx,dict):
        cumulative=revision_ctx.get("cumulative_lifetime_attempts")
        if isinstance(cumulative,dict) and not state.get("lifetime_attempts"):
            state["lifetime_attempts"]={str(k):int(v) for k,v in cumulative.items()}
        if revision_ctx.get("round") is not None:
            state["global_broader_round"]=max(int(state.get("global_broader_round") or 0),int(revision_ctx.get("round") or 0))
    return state

def _department_attempt_limit(sr:NexMindSupremeShowrunnerP8,department:str)->int:
    limits=sr.state.get("autonomous_creative_repair",{}).get("attempt_limits_by_department") or {}
    return int(limits.get(department,2))

def _reserve_attempt(sr: NexMindSupremeShowrunnerP8, department: str) -> int:
    repair = sr.state["autonomous_creative_repair"]
    attempts = repair["attempts"]
    lifetime = repair.setdefault("lifetime_attempts", {})
    used = int(attempts.get(department, 0))
    maximum = _department_attempt_limit(sr,department)
    if used >= maximum:
        raise CreativeRepairBudgetExhausted(department, used, maximum)
    attempt = used + 1
    attempts[department] = attempt
    lifetime[department] = int(lifetime.get(department, 0)) + 1
    if hasattr(sr, "_event"):
        sr._event("AUTONOMOUS_CREATIVE_ATTEMPT", {
            "department": department, "attempt": attempt, "maximum": maximum,
            "lifetime_attempt": lifetime[department],
        })
    return attempt


def _reset_downstream_attempt_budgets(sr: NexMindSupremeShowrunnerP8, owner: str, reason: str) -> Dict[str, int]:
    """Reset only departments whose accepted upstream authority will change.

    The owning department keeps its bounded attempt count. Departments strictly
    downstream receive a fresh per-lineage budget because their previous attempts
    were generated against now-superseded upstream decisions. This prevents an
    upstream replan from starving downstream Directors while keeping every lineage
    independently bounded.
    """
    repair = sr.state["autonomous_creative_repair"]
    attempts = repair.setdefault("attempts", {})
    if owner not in DEPARTMENT_ORDER:
        return {}
    start = DEPARTMENT_ORDER.index(owner) + 1
    reset: Dict[str, int] = {}
    for department in DEPARTMENT_ORDER[start:]:
        prior = int(attempts.get(department, 0))
        if prior > 0:
            reset[department] = prior
            attempts[department] = 0
    if reset:
        item = {
            "owner_department": owner,
            "reason": reason,
            "reset_attempts": deepcopy(reset),
            "revision": int(sr.state.get("revision", 0)),
        }
        repair.setdefault("lineage_resets", []).append(item)
        if hasattr(sr, "_event"):
            sr._event("AUTONOMOUS_DOWNSTREAM_BUDGET_RESET", deepcopy(item))
    return reset


def _clear_repair_context(sr: NexMindSupremeShowrunnerP8, department: Optional[str] = None) -> None:
    current = sr.state.get("brief", {}).get("autonomous_revision_context")
    if department:
        sr.state.get("autonomous_creative_repair",{}).get("contract_repairs",{}).pop(department,None)
    if not isinstance(current, dict):
        return
    if department and current.get("department") != department:
        return
    sr.state["brief"].pop("autonomous_revision_context", None)


def _candidate_summary(candidate: Any) -> Dict[str, Any]:
    if not isinstance(candidate, dict):
        return {"hash": canonical_hash(candidate)}
    keys = (
        "candidate_id", "representation", "visual_thesis", "hero_kind", "transformation",
        "art_thesis", "cinema_thesis", "editorial_thesis", "rhythm_profile",
        "motion_thesis", "sound_thesis", "risk_notes", "capability_gaps",
    )
    out = {k: deepcopy(candidate[k]) for k in keys if k in candidate}
    if isinstance(candidate.get("hero"), dict):
        out["hero"] = {k: deepcopy(candidate["hero"].get(k)) for k in ("semantic_ref", "prominence", "recognizable_required") if k in candidate["hero"]}
    if isinstance(candidate.get("music_strategy"), dict):
        out["music_strategy"] = {k: deepcopy(candidate["music_strategy"].get(k)) for k in ("mode", "narrative_role") if k in candidate["music_strategy"]}
    story_obj=candidate.get("story") if isinstance(candidate.get("story"),dict) else None
    if story_obj and isinstance(story_obj.get("film_thesis"),dict):
        ft=story_obj["film_thesis"]
        out["story_signature"]={k:deepcopy(ft.get(k)) for k in ("central_argument","hero_kind","audience_before","audience_after","opening_contract","final_payoff") if ft.get(k) is not None}
    out["hash"] = canonical_hash(candidate)
    return out


def _review_context(review: Dict[str, Any], *, previous: Any = None) -> Dict[str, Any]:
    return {
        "issues": deepcopy(review.get("issues") or []),
        "strengths_to_preserve": deepcopy(review.get("strengths") or []),
        "revision_briefs": [str(review.get("revision_brief") or "").strip()] if str(review.get("revision_brief") or "").strip() else [],
        "producer_verdicts": [str(review.get("verdict") or "")],
        "previous_output": deepcopy(previous) if previous is not None else None,
    }


def _issue_text(issue: Any) -> str:
    if not isinstance(issue, dict):
        return str(issue or "").strip()
    return " ".join(str(issue.get(k) or "") for k in (
        "area", "category", "issue", "finding", "impact", "required_change", "repair", "detail", "code"
    )).strip()


def _issue_tokens(issue: Any) -> set[str]:
    stop={"the","and","with","that","this","from","into","for","then","must","should","candidate","concept","visual","film","current","make","keep","every","after","before","rather","than"}
    return {t for t in re.findall(r"[a-z0-9]+", _issue_text(issue).lower()) if len(t)>3 and t not in stop}


def _issues_equivalent(a: Any, b: Any) -> bool:
    ta,tb=_issue_tokens(a),_issue_tokens(b)
    if not ta or not tb:
        return _issue_text(a).strip().lower()==_issue_text(b).strip().lower()
    overlap=len(ta & tb)/max(1,min(len(ta),len(tb)))
    aa=str(a.get("area") or a.get("category") or "").strip().lower() if isinstance(a,dict) else ""
    bb=str(b.get("area") or b.get("category") or "").strip().lower() if isinstance(b,dict) else ""
    area_match=bool(aa and bb and (aa==bb or aa in bb or bb in aa))
    return overlap>=0.72 or (area_match and overlap>=0.52)


def _dedupe_issues(issues: list[Any]) -> list[Any]:
    out=[]
    rank={"CRITICAL":5,"MAJOR":4,"MATERIAL":3,"MODERATE":2,"MINOR":1}
    for issue in issues:
        match=next((i for i,x in enumerate(out) if _issues_equivalent(x,issue)),None)
        if match is None:
            out.append(deepcopy(issue)); continue
        if isinstance(out[match],dict) and isinstance(issue,dict):
            old=rank.get(str(out[match].get("severity") or "").upper(),0)
            new=rank.get(str(issue.get("severity") or "").upper(),0)
            if new>old:
                out[match]=deepcopy(issue)
    return out


def _review_issue_weight(review: Dict[str,Any]) -> int:
    weights={"CRITICAL":9,"MAJOR":6,"MATERIAL":4,"MODERATE":2,"MINOR":1}
    total=0
    for issue in review.get("issues") or []:
        sev=str(issue.get("severity") or "MATERIAL").upper() if isinstance(issue,dict) else "MATERIAL"
        total+=weights.get(sev,4)
    verdict=str(review.get("verdict") or "REVISE").upper()
    total += {"ACCEPT":0,"REVISE":3,"REJECT":9}.get(verdict,5)
    return total


def _repair_anchor_item(reviewed: list[Dict[str,Any]]) -> Dict[str,Any] | None:
    if not reviewed:
        return None
    confidence={"HIGH":0,"MEDIUM":1,"LOW":2}
    ranked=sorted(
        reviewed,
        key=lambda item:(
            _review_issue_weight(item.get("review") or {}),
            confidence.get(str((item.get("review") or {}).get("commercial_confidence") or "LOW").upper(),3),
            canonical_hash(item.get("candidate")),
        ),
    )
    return ranked[0]


def _repair_anchor(reviewed: list[Dict[str,Any]]) -> Dict[str,Any] | None:
    item=_repair_anchor_item(reviewed)
    candidate=item.get("candidate") if isinstance(item,dict) else None
    return deepcopy(candidate) if isinstance(candidate,dict) else None


def _required_change_text(issue: Any) -> str:
    if isinstance(issue,dict):
        for key in ("required_change","repair","detail","issue","finding"):
            value=str(issue.get(key) or "").strip()
            if value: return value
    return str(issue or "").strip()


def _record_deferred_validations(sr:NexMindSupremeShowrunnerP8, review:Dict[str,Any], *, department:str, candidate:Any) -> None:
    items=review.get("deferred_production_validations") or []
    if not items: return
    target=sr.state.setdefault("production_validation_requirements",[])
    seen={canonical_hash(x) for x in target}
    for issue in items:
        rec={
            "schema":"NexMindDeferredProductionValidationV1",
            "source_department":department,
            "candidate_hash":canonical_hash(candidate),
            "requirement":deepcopy(issue),
            "status":"REQUIRED_DOWNSTREAM_BEFORE_FINAL_ACCEPTANCE",
        }
        digest=canonical_hash(rec)
        if digest not in seen:
            target.append(rec);seen.add(digest)
    sr.state["brief"]["production_validation_requirements"]=deepcopy(target)


def _reviews_context(reviewed: list[Dict[str, Any]]) -> Dict[str, Any]:
    """Build surgical repair context around exactly one rejected candidate.

    Reviews from other candidates remain diagnostic/anti-repetition telemetry; they
    must not become binding edits on the selected repair anchor. Merging all reviews
    made one Story candidate inherit contradictory requirements from unrelated films.
    """
    anchor_item=_repair_anchor_item(reviewed)
    anchor_review=(anchor_item or {}).get("review") or {}
    anchor_candidate=(anchor_item or {}).get("candidate")
    issues=_dedupe_issues(deepcopy(anchor_review.get("issues") or []))
    strengths=[];seen=set()
    for x in anchor_review.get("strengths") or []:
        text=str(x).strip()
        if text and text not in seen:
            strengths.append(text);seen.add(text)
    rb=str(anchor_review.get("revision_brief") or "").strip()
    deferred=_dedupe_issues(deepcopy(anchor_review.get("deferred_production_validations") or []))
    rejected=[]
    for item in reviewed:
        review=item.get("review") or {}
        rejected.append({
            "verdict":review.get("verdict"),
            "candidate":_candidate_summary(item.get("candidate")),
            "binding_to_repair_anchor": item is anchor_item,
            "issue_count":len(review.get("issues") or []),
        })
    return {
        "issues":issues,
        "strengths_to_preserve":strengths,
        "revision_briefs":[rb] if rb else [],
        "producer_verdicts":[str((item.get("review") or {}).get("verdict") or "") for item in reviewed],
        "rejected_candidates":rejected,
        "previous_output":deepcopy(anchor_candidate) if isinstance(anchor_candidate,dict) else None,
        "deferred_production_validations":deferred,
        "repair_context_scope":"STRONGEST_REJECTED_CANDIDATE_ONLY",
    }



def _diversity_repair_context(reviewed: list[Dict[str, Any]], department: str) -> Dict[str, Any]:
    """Build a repair request for a weak candidate *set*, not one weak candidate.

    Candidate-set diversity failure must reopen competition. Anchoring to the
    strongest member would collapse the next attempt into surgical repair and
    preserve the very failure (near-duplicate strategy space) we are trying to fix.
    """
    context=_reviews_context(reviewed)
    issue={
        "code":"CANDIDATE_SET_NOT_MEANINGFULLY_DIVERSE",
        "severity":"MAJOR",
        "area":"Creative strategy competition",
        "issue":f"{department} candidate competition did not contain materially different strategies.",
        "required_change":"Reopen candidate competition and generate materially different governing strategies, not paraphrases or layout variants of the same idea.",
    }
    context["issues"]=_dedupe_issues([issue,*list(context.get("issues") or [])])
    context["revision_briefs"]=[
        "Reopen genuine candidate competition. Change the governing creative strategy between candidates; do not anchor this repair to a single prior candidate."
    ]
    context["previous_output"]=None
    context["repair_anchor_forbidden_reason"]="CANDIDATE_SET_DIVERSITY_FAILURE"
    return context

def _schedule_repair(sr: NexMindSupremeShowrunnerP8, department: str, reason: str, context: Dict[str, Any]) -> Dict[str, Any]:
    repair = sr.state["autonomous_creative_repair"]
    attempts = int(repair["attempts"].get(department, 0))
    maximum = _department_attempt_limit(sr,department)
    if attempts >= maximum:
        raise CreativeRepairBudgetExhausted(department, attempts, maximum, reason=reason, context=context)
    invalidated = list(DEPARTMENT_INVALIDATION[department])
    preserved = sorted(k for k in sr.state.get("decisions", {}) if k not in invalidated)
    from_revision = int(sr.state.get("revision", 0))
    prior_context = sr.state.get("brief", {}).get("autonomous_revision_context")
    sticky=[]
    if department!="STORY" and isinstance(prior_context,dict) and prior_context.get("department")==department:
        sticky.extend(str(x) for x in (prior_context.get("sticky_requirements") or []) if str(x).strip())
    # Story repairs bind only the current anchor's active blockers. Historical Producer
    # notes are re-evaluated by the next independent review instead of becoming an
    # ever-growing permanent creative cage.
    for issue in context.get("issues") or []:
        change=_required_change_text(issue)
        if change and change not in sticky: sticky.append(change)
    downstream_budget_resets = _reset_downstream_attempt_budgets(sr, department, reason)
    sr.replan(reason, invalidate_slots=invalidated)
    revision_context = {
        "schema": "NexMindAutonomousRevisionContextV1",
        "department": department,
        "from_revision": from_revision,
        "to_revision": int(sr.state.get("revision", 0)),
        "attempt_completed": attempts,
        "next_attempt": attempts + 1,
        "max_attempts": _department_attempt_limit(sr,department),
        "reason": reason,
        "preserve_decision_slots": preserved,
        "issues": deepcopy(context.get("issues") or []),
        "strengths_to_preserve": deepcopy(context.get("strengths_to_preserve") or []),
        "revision_briefs": deepcopy(context.get("revision_briefs") or []),
        "rejected_candidates": deepcopy(context.get("rejected_candidates") or []),
        "previous_output": deepcopy(context.get("previous_output")),
        "repair_anchor_hash": canonical_hash(context.get("previous_output")) if context.get("previous_output") is not None else None,
        "sticky_requirements": sticky,
        "deferred_production_validations": deepcopy(context.get("deferred_production_validations") or []),
        "requirements": [
            "Resolve every material Producer issue; do not merely paraphrase the rejected work.",
            "Preserve the listed strengths and every upstream decision slot not invalidated by this repair.",
            "Do not lower the quality gate or substitute a generic/simpler treatment just to obtain ACCEPT.",
            "Produce a materially improved creative answer that can be independently re-reviewed.",
            "When previous_output is present, repair that exact anchor rather than reopening candidate competition; preserve all anchor decisions not implicated by the listed issues.",
            "Treat sticky_requirements as binding non-regression constraints for this repair lineage.",
            "Do not fabricate empirical or physical test results; carry production-only validation requirements downstream instead of inventing evidence.",
        ],
    }
    sr.state["brief"]["autonomous_revision_context"] = deepcopy(revision_context)
    ledger_entry = {
        "department": department,
        "reason": reason,
        "from_revision": from_revision,
        "to_revision": sr.state["revision"],
        "attempt_completed": attempts,
        "next_attempt": attempts + 1,
        "invalidated_slots": invalidated,
        "preserved_slots": preserved,
        "downstream_budget_resets": deepcopy(downstream_budget_resets),
        "context_hash": canonical_hash(revision_context),
        "context": deepcopy(revision_context),
    }
    repair["ledger"].append(ledger_entry)
    if hasattr(sr, "_event"):
        sr._event("AUTONOMOUS_CREATIVE_REPAIR_SCHEDULED", {
            "department": department, "next_attempt": attempts + 1, "maximum": _department_attempt_limit(sr,department),
            "reason": reason, "invalidated_slots": invalidated, "context_hash": ledger_entry["context_hash"],
        })
    return revision_context


def _review_owner(review: Dict[str, Any], default: str, allowed: Optional[set[str]] = None) -> str:
    """Resolve causal owner from explicit review semantics, then bounded heuristics.

    An issue may deliberately name owner_department. That field is authoritative only
    when its value is an allowed creative department; arbitrary JSON keys remain ignored.
    """
    allowed=allowed or set(DEPARTMENT_ORDER)
    code_owner={
        "FORM_GAP":"ART_DIRECTION",
        "GENERIC_STORYBOARD":"VISUAL_CONCEPT",
        "WEAK_SETTLED_STATE":"ART_DIRECTION",
        "MISSING_HERO":"VISUAL_CONCEPT",
        "NO_CRITICAL_ACTION":"VISUAL_CONCEPT",
        "MISSING_TEMPORAL_DIRECTION":"EDITORIAL_RHYTHM",
        "MULTI_SHOT_EXECUTION_BINDING_REQUIRED":"CINEMATOGRAPHY",
        "UNMOTIVATED_CAMERA":"CINEMATOGRAPHY",
        "MULTI_EDIT_EXECUTION_BINDING_REQUIRED":"EDITORIAL_RHYTHM",
        "MOTION_RESCUE_DEPENDENCY":"ART_DIRECTION",
        "MOTION_PRETENDED_COMPLETE":"MOTION_PERFORMANCE",
        "SOUND_PRETENDED_COMPLETE":"SOUND_DIRECTION",
    }
    for issue in review.get("issues") or []:
        if isinstance(issue,dict):
            explicit=str(issue.get("owner_department") or "").upper()
            if explicit in allowed:
                return explicit
            code=str(issue.get("code") or "").upper()
        else:
            code=""
        owner=code_owner.get(code)
        if owner in allowed:
            return owner
    # Only values authored as issue semantics are searched. Keys such as beat_id no
    # longer inject the word 'beat' and accidentally escalate ordinary board issues.
    parts=[_issue_text(x) for x in (review.get("issues") or [])]
    parts.append(str(review.get("revision_brief") or ""))
    text=" ".join(parts).lower()
    hints=[
        ("STORY",("story","thesis","audience state","narrative","payoff","protagonist","human priority","causal argument")),
        ("VISUAL_CONCEPT",("visual concept","visual strategy","hero","transformation","generic","representation","visual metaphor")),
        ("ART_DIRECTION",("art direction","composition","hierarchy","illustration","key state","settled state","form","environment")),
        ("CINEMATOGRAPHY",("camera","cinema","shot","framing","lens","coverage")),
        ("EDITORIAL_RHYTHM",("editorial","rhythm","timing","pacing","duration","continuity","cut")),
        ("MOTION_PERFORMANCE",("motion","performance","contact","physical","gesture","capability","choreography")),
        ("SOUND_DIRECTION",("sound","music","audio","foley","mix","narration","sonic")),
    ]
    scored=[]
    for department,words in hints:
        if department not in allowed: continue
        score=sum(text.count(word) for word in words)
        if score: scored.append((score,-DEPARTMENT_ORDER.index(department),department))
    if scored:
        return max(scored)[2]
    if default in allowed: return default
    return next((d for d in DEPARTMENT_ORDER if d in allowed),sorted(allowed)[0])


_STORYBOARD_EXPLICIT_STORY_CODES={
    "STORY_INTERNAL_CONTRADICTION",
    "STORY_CAUSAL_CHAIN_BROKEN",
    "STORY_BRIEF_CONTRADICTION",
}

def _key_storyboard_review_owner(review: Dict[str,Any]) -> str:
    """Route key-state storyboard criticism without casually reopening accepted Story.

    Story has already passed its own Producer gate before this stage. A storyboard
    reviewer may reopen Story only by explicitly diagnosing an internal Story contract
    failure with one of the narrow codes above. Ordinary complaints that a board does
    not express the thesis, payoff, hero, escalation or transformation belong to the
    Visual Concept / Art realization layer.
    """
    for issue in review.get("issues") or []:
        if not isinstance(issue,dict):
            continue
        code=str(issue.get("code") or "").upper()
        owner=str(issue.get("owner_department") or "").upper()
        if owner=="STORY" and code in _STORYBOARD_EXPLICIT_STORY_CODES:
            return "STORY"
    # Accepted Story is sticky at this boundary. Route the realization defect to the
    # nearest editable upstream visual owner instead of inferring Story from words such
    # as "thesis" or "payoff" that are native to storyboard review language.
    return _review_owner(review,"ART_DIRECTION",{"VISUAL_CONCEPT","ART_DIRECTION"})


def _final_review_context(review: Dict[str, Any], final_board: Dict[str, Any]) -> Dict[str, Any]:
    structured = [deepcopy(x) for x in (review.get("department_revisions") or []) if isinstance(x, dict)]
    preserve = list(review.get("strengths") or [])
    for item in structured:
        preserve.extend(str(x) for x in (item.get("preserve") or []) if str(x).strip())
    briefs = [str(x) for x in (review.get("revision_plan") or []) if str(x).strip()]
    briefs.extend(str(x.get("required_change")) for x in structured if str(x.get("required_change") or "").strip())
    return {
        "issues": deepcopy(review.get("issues") or []),
        "strengths_to_preserve": preserve,
        "revision_briefs": briefs,
        "producer_verdicts": [str(review.get("verdict") or "")],
        "rejected_candidates": [{"final_department_revision": x} for x in structured],
        "previous_output": {"final_board_hash": canonical_hash(final_board)},
    }


def _decision_payload(sr: NexMindSupremeShowrunnerP8, slot: str) -> Dict[str, Any]:
    item = sr.state.get("decisions", {}).get(slot)
    if not item:
        raise ProducerGateError({"missing_decision": slot})
    return deepcopy(item.get("payload") or {})


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _emit(progress: Progress, phase: str, payload: Optional[Dict[str, Any]] = None) -> None:
    if progress:
        progress(phase, payload or {})


def _selection_contract_retry(call, *, attempts:int=2):
    """Retry only Showrunner selection reasoning; never regenerate Directors for a malformed selector object."""
    last=None
    for _ in range(max(1,attempts)):
        try:
            return call()
        except ContractViolation as error:
            last=error
    raise last


def _owner_has_local_attempt(sr:NexMindSupremeShowrunnerP8, department:str) -> bool:
    repair=sr.state.get("autonomous_creative_repair") or {}
    used=int((repair.get("attempts") or {}).get(department,0))
    return used < _department_attempt_limit(sr,department)


def _resolve_available_escalation_owner(sr:NexMindSupremeShowrunnerP8, source_department:str) -> tuple[str,list[str]]:
    """Budget exhaustion never proves an upstream creative department is wrong.

    The department attached to CreativeRepairBudgetExhausted is already the causal
    owner chosen by the relevant Producer/review boundary. Exhausting that owner's
    local repair budget therefore opens a NEW LINEAGE OF THE SAME DEPARTMENT. It must
    not climb upstream merely because another department still has attempts left.

    If an upstream department truly owns the defect, the review boundary must have
    explicitly scheduled repair for that upstream department before budget exhaustion.
    In particular, accepted STORY is never reopened just because VISUAL_CONCEPT, Art,
    Cinema, Editorial, Motion or Sound reached their local attempt ceiling.
    """
    owner=source_department if source_department in DEPARTMENT_ORDER else "VISUAL_CONCEPT"
    return owner,[owner]


def _nonstory_broader_lineage_limit(request: Dict[str,Any]) -> int:
    try:
        value=int(request.get("nonStoryBroaderLineageLimit") or DEFAULT_NONSTORY_BROADER_LINEAGE_LIMIT)
    except Exception:
        value=DEFAULT_NONSTORY_BROADER_LINEAGE_LIMIT
    return max(1,min(2,value))


def _nonstory_broader_lineage_count(sr:NexMindSupremeShowrunnerP8, department:str) -> int:
    repair=sr.state.get("autonomous_creative_repair") or {}
    return sum(1 for item in (repair.get("broader_strategy_replans") or [])
               if isinstance(item,dict) and item.get("owner_department")==department
               and item.get("mode")=="SAME_DEPARTMENT_NEW_LINEAGE")


def _reset_owner_for_new_lineage(sr:NexMindSupremeShowrunnerP8, department:str, reason:str) -> int:
    repair=sr.state.setdefault("autonomous_creative_repair",{})
    attempts=repair.setdefault("attempts",{})
    prior=int(attempts.get(department,0))
    attempts[department]=0
    item={
        "owner_department":department,
        "reason":reason,
        "reset_owner_attempts":prior,
        "revision":int(sr.state.get("revision",0)),
        "law":"LOCAL_BUDGET_EXHAUSTION_OPENS_SAME_DEPARTMENT_LINEAGE__NEVER_PROVES_UPSTREAM_CAUSALITY",
    }
    repair.setdefault("lineage_resets",[]).append(item)
    if hasattr(sr,"_event"):
        sr._event("AUTONOMOUS_OWNER_LINEAGE_BUDGET_RESET",deepcopy(item))
    return prior


def _apply_in_place_broader_replan(sr:NexMindSupremeShowrunnerP8, *, owner:str, source_error:CreativeRepairBudgetExhausted, repair_request:Dict[str,Any]) -> Dict[str,Any]:
    if owner=="STORY":
        raise ValueError("Story broader replans use the full-strategy restart path")
    slot=DEPARTMENT_DECISION_SLOT.get(owner)
    previous=None
    if slot and slot in sr.state.get("decisions",{}):
        previous=_committed_payload(sr,slot)
    invalidated=list(DEPARTMENT_INVALIDATION[owner])
    preserved=sorted(k for k in sr.state.get("decisions",{}) if k not in invalidated)
    from_revision=int(sr.state.get("revision",0))
    reason=f"New {owner} lineage after its local repair budget exhausted"
    exhausted_signature=_candidate_summary(previous) if previous is not None else None
    owner_reset=_reset_owner_for_new_lineage(sr,owner,reason)
    downstream_resets=_reset_downstream_attempt_budgets(sr,owner,reason)
    sr.replan(reason,invalidate_slots=invalidated)
    # A broader lineage is genuine re-competition, not another surgical repair. Prior
    # candidate details are negative-only anti-repetition evidence and must not become
    # sticky requirements or a positive repair anchor.
    ctx={
        "schema":"NexMindAutonomousRevisionContextV1",
        "department":owner,
        "source_department":source_error.department,
        "repair_mode":"MATERIAL_STRATEGY_REPLAN",
        "strategy_replan_required":True,
        "from_revision":from_revision,
        "to_revision":int(sr.state.get("revision",0)),
        "attempt_completed":owner_reset,
        "next_attempt":1,
        "max_attempts":_department_attempt_limit(sr,owner),
        "reason":reason,
        "preserve_decision_slots":preserved,
        "issues":deepcopy(repair_request.get("issues") or []),
        "strengths_to_preserve":[],
        "revision_briefs":[
            f"Open a materially different {owner} lineage against the already accepted upstream decisions. Do not cosmetically repair or restage the exhausted local strategy.",
        ],
        "previous_output":None,
        "repair_anchor_hash":None,
        "exhausted_local_strategy_signature":deepcopy(exhausted_signature),
        "sticky_requirements":[],
        "deferred_production_validations":[],
        "requirements":[
            "Treat the exhausted local strategy only as negative anti-repetition evidence; do not preserve its invented devices unless independently required upstream.",
            "Preserve every accepted upstream decision outside the owner's invalidation scope.",
            "Generate genuine candidate competition for the new lineage; this is not surgical repair.",
            "Do not weaken the quality gate or use a generic fallback.",
            "Do not fabricate empirical or physical test results; carry those validation requirements downstream.",
        ],
        "law":"BUDGET_EXHAUSTION_RESETS_SAME_DEPARTMENT_LINEAGE__UPSTREAM_REOPEN_REQUIRES_EXPLICIT_CAUSAL_DIAGNOSIS",
    }
    sr.state["brief"]["autonomous_revision_context"]=deepcopy(ctx)
    rec={
        "owner_department":owner,"source_department":source_error.department,"reason":reason,
        "mode":"SAME_DEPARTMENT_NEW_LINEAGE",
        "from_revision":from_revision,"to_revision":int(sr.state.get("revision",0)),
        "invalidated_slots":invalidated,"preserved_slots":preserved,
        "owner_budget_reset":owner_reset,
        "downstream_budget_resets":deepcopy(downstream_resets),"context_hash":canonical_hash(ctx),
    }
    sr.state.get("autonomous_creative_repair",{}).setdefault("broader_strategy_replans",[]).append(rec)
    if hasattr(sr,"_event"):
        sr._event("AUTONOMOUS_BROADER_OWNER_REPLAN",deepcopy(rec))
    return ctx


def _story_strategy_signature(value: Any) -> Dict[str, Any] | None:
    if not isinstance(value,dict):
        return None
    if isinstance(value.get("film_thesis"),dict):
        ft=value["film_thesis"]
    elif isinstance(value.get("story_signature"),dict):
        ft=value["story_signature"]
    else:
        ft=value
    out={k:deepcopy(ft.get(k)) for k in ("central_argument","hero_kind","audience_before","audience_after","opening_contract","final_payoff") if str(ft.get(k) or "").strip()}
    if not out:
        for source,target in (("visual_thesis","central_argument"),("transformation","transformation"),("hero_kind","hero_kind")):
            if str(value.get(source) or "").strip(): out[target]=deepcopy(value.get(source))
    if not out:
        return None
    out["signature_hash"]=canonical_hash(out)
    return out


def _collect_exhausted_story_signatures(repair_request: Dict[str,Any]) -> list[Dict[str,Any]]:
    values=[]
    current=_story_strategy_signature(repair_request.get("current_story_signature"))
    if current: values.append(current)
    for item in repair_request.get("rejected_candidates") or []:
        candidate=item.get("candidate") if isinstance(item,dict) else None
        sig=_story_strategy_signature(candidate)
        if sig: values.append(sig)
    out=[];seen=set()
    for sig in values:
        digest=str(sig.get("signature_hash") or canonical_hash(sig))
        if digest in seen: continue
        seen.add(digest);out.append(sig)
    return out[:6]


def _next_broader_strategy_request(request: Dict[str,Any], repair_request: Dict[str,Any], escalation_owner: str) -> Dict[str,Any] | None:
    """Return a bounded automatic full-strategy restart request when Story owns the replan.

    Story-owned exhaustion invalidates the whole causal lineage, so restarting run_full_p8 is
    safe and materially broader. Downstream-owned exhaustion remains in-place/recoverable and
    is not silently promoted to a full Story rewrite by this helper.
    """
    try:
        max_broader=max(1,min(6,int(request.get("broaderStrategyMaxRounds") or DEFAULT_BROADER_STRATEGY_REPLAN_ROUNDS)))
    except Exception:
        max_broader=DEFAULT_BROADER_STRATEGY_REPLAN_ROUNDS
    broader_round=int(repair_request.get("round") or 1)
    if escalation_owner!="STORY" or broader_round>max_broader:
        return None
    signatures=_collect_exhausted_story_signatures(repair_request)
    rr={
        "schema":"StudioAutonomousCreativeRepairRequestV3",
        "round":broader_round,
        "maximum":max_broader,
        "escalation_scope":"BROADER_CREATIVE_STRATEGY",
        "owner_department":"STORY",
        "source_department":str(repair_request.get("source_department") or repair_request.get("owner_department") or "STORY"),
        "department":"STORY",
        "strategy_replan_required":True,
        "repair_mode":"MATERIAL_STRATEGY_REPLAN",
        "quality_reasons":deepcopy(repair_request.get("quality_reasons") or ["LOCAL_CREATIVE_LINEAGE_EXHAUSTED"]),
        "invalidate_slots":deepcopy(DEPARTMENT_INVALIDATION["STORY"]),
        "issues":[{
            "code":"STORY_LINEAGE_EXHAUSTED",
            "severity":"MAJOR",
            "area":"Governing Story strategy",
            "finding":"The prior Story lineage exhausted bounded repair or could not support a viable downstream concept. Its invented dramatic devices are not authoritative constraints.",
            "required_change":"Invent a fundamentally different governing causal Story from the original customer brief, brand/revision constraints, and evidence. Do not cosmetically rename or rearrange the exhausted causal pattern.",
        }],
        "revision_plan":[
            "Create a clean Story restart from source authority. Each outer Story candidate must be one complete film, not an internal comparison of routes. Rejected-lineage signatures are negative-only anti-repetition context; do not preserve their props, characters, beat devices, camera devices, or payoff objects unless independently required by the customer/evidence/brand/revision authority."
        ],
        "strengths_to_preserve":[],
        "sticky_requirements":[],
        "previous_output":None,
        "repair_anchor_hash":None,
        "exhausted_strategy_signatures":signatures,
        "cumulative_lifetime_attempts":deepcopy(repair_request.get("cumulative_lifetime_attempts") or {}),
        "instruction":(
            "Clean Story restart. The previous creative lineage is exhausted. Build one materially different governing Story per outer candidate from the original customer brief and authoritative evidence. "
            "Do not preserve rejected-lineage props, scene business, beat devices, camera devices, or payoff objects merely because earlier Producer notes mentioned them. "
            "Use exhausted_strategy_signatures only to avoid repetition; never discuss or compare them inside a candidate. Production-only empirical validation remains downstream and must not be fabricated."
        ),
        "authoritative_preservation_law":"PRESERVE_CUSTOMER_BRIEF_BRAND_REVISION_EVIDENCE_ONLY__REJECTED_STORY_INVENTIONS_ARE_NOT_STICKY",
    }
    # Explicit source-level authority invariant retained for release certification.
    rr["department"]="STORY"
    next_request=deepcopy(request)
    next_request["autonomousRepairContext"]=rr
    return {"request":next_request,"round":broader_round,"maximum":max_broader,"repairRequest":rr}


def _committed_payload(sr: NexMindSupremeShowrunnerP8, slot: str) -> Dict[str, Any]:
    item = sr.state.get("decisions", {}).get(slot)
    if not item:
        raise ProducerGateError({"missing_decision": slot})
    payload = item.get("payload") or {}
    # P0 proposals wrap department data in semantic authority fields. Directors
    # downstream expect their own domain object rather than the wrapper.
    nested_key = {
        "film_thesis": "story",
        "visual_concept": None,
        "art_direction": "art_direction",
        "cinematography": "cinematography",
        "editorial_rhythm": "editorial_rhythm",
        "motion_performance": "motion_performance",
        "sound_direction": "sound_direction",
    }.get(slot)
    if nested_key and isinstance(payload.get(nested_key), dict):
        return deepcopy(payload[nested_key])
    return deepcopy(payload)


def _creative_memory_context(request: Dict[str, Any]) -> Dict[str, Any]:
    """Relevance/scope retrieval over every promoted memory; finite context is a byte budget, never first-N."""
    records=[deepcopy(x) for x in (request.get("creativeMemory") or []) if isinstance(x,dict) and x.get("status")=="PROMOTED"]
    brief_text=" ".join(str(request.get(k) or "") for k in ("prompt","brief","videoType","family")).lower()
    tokens={x for x in re.findall(r"[a-z0-9]{3,}",brief_text)}
    scope_weight={"PRODUCTION":50,"SERIES":40,"BRAND":30,"CAST":25,"ACCOUNT":10}
    ranked=[]
    for rec in records:
        lesson=str(rec.get("lesson") or "")
        rt={x for x in re.findall(r"[a-z0-9]{3,}",lesson.lower())}
        overlap=len(tokens & rt)
        score=scope_weight.get(str(rec.get("scope") or "").upper(),0)+overlap*4
        ranked.append((score,str(rec.get("memory_id") or ""),rec))
    ranked.sort(key=lambda x:(-x[0],x[1]))
    budget=max(4000,int(request.get("creativeMemoryCharacterBudget") or 18000))
    used=0;selected=[];omitted=[]
    for score,mid,rec in ranked:
        payload=json.dumps(rec,sort_keys=True,separators=(",",":"),ensure_ascii=False)
        if used+len(payload)>budget:
            omitted.append({"memory_id":mid,"reason":"CONTEXT_CHARACTER_BUDGET","relevance_score":score})
            continue
        selected.append(rec);used+=len(payload)
    return {
        "schema":"NexMindCreativeMemoryContextV1",
        "authority":"ADVISORY_CONTINUITY_AND_ANTI_REPETITION_ONLY",
        "law":"CURRENT_CUSTOMER_BRIEF_SOURCE_TRUTH_BRAND_AND_REVISION_ALWAYS_OVERRIDE_MEMORY",
        "selected":selected,"omitted":omitted,"indexed_count":len(records),"selected_count":len(selected),"character_budget":budget,
    }

def _brief(request: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "topic": request.get("prompt") or request.get("brief") or "Untitled production",
        "goal": request.get("prompt") or request.get("brief") or "Develop the requested production",
        "duration_s": int(request.get("durationSeconds") or 60),
        "style": str(request.get("family") or "").lower().replace("_", " "),
        "family": request.get("family"),
        "video_type": request.get("videoType"),
        "aspect_ratio": request.get("aspectRatio"),
        "voice_preference": request.get("voicePreference"),
        "brand_context": deepcopy(request.get("brandContext")),
        "approved_plan_preview": deepcopy(request.get("planPreview")),
        "plan_preview_authority": "NON_AUTHORITATIVE_COMMERCIAL_PREVIEW",
        "revision_context": deepcopy(request.get("revisionContext")),
        "customer_revision_instruction": str((request.get("revisionContext") or {}).get("instruction") or ""),
        "customer_revision_timestamp_seconds": (request.get("revisionContext") or {}).get("timestampSeconds"),
        "prior_locked_board": deepcopy((request.get("revisionContext") or {}).get("priorFinalBoard")),
        "revision_preservation_law": (request.get("revisionContext") or {}).get("preservationLaw"),
        "reference_language_profile": deepcopy(request.get("referenceLanguageProfile")),
        "reference_style_hint": None,
        "_reference_style_hint_telemetry": request.get("referenceStyleHint"),
        "_direct_reference_visuals": deepcopy(request.get("sourceVisualEvidence") or []),
        "_direct_reference_visual_omissions": deepcopy(request.get("sourceVisualEvidenceOmissions") or []),
        "reference_law": "Hash-bound reference pixels are the creative visual-language authority; deterministic reference statistics and filename hints are indexing telemetry only; story/shot content must remain original." if (request.get("referenceLanguageProfile") or request.get("sourceVisualEvidence")) else "NONE",
        "autonomous_repair_context": deepcopy(request.get("autonomousRepairContext")),
        "autonomous_revision_context": deepcopy(request.get("autonomousRepairContext")) if isinstance(request.get("autonomousRepairContext"),dict) else None,
        "creative_memory_context": _creative_memory_context(request),
    }


def _evidence(request: Dict[str, Any]) -> list[Dict[str, Any]]:
    records = request.get("evidence") or request.get("sourceSummaries") or []
    out = []
    revision = request.get("revisionContext") or {}
    if isinstance(revision, dict) and str(revision.get("instruction") or "").strip():
        out.append({
            "claim_id": "CUSTOMER-REVISION-1",
            "claim": str(revision.get("instruction")),
            "source": "customer-revision-request",
            "status": "USER_SUPPLIED",
        })
    for idx, record in enumerate(records):
        if isinstance(record, dict):
            claim = record.get("claim") or record.get("summary") or record.get("text")
            if claim:
                out.append({
                    "claim_id": str(record.get("claim_id") or record.get("id") or f"SOURCE-{idx+1}"),
                    "claim": str(claim),
                    "source": str(record.get("source") or record.get("label") or "studio-source"),
                    "status": str(record.get("status") or "USER_SUPPLIED"),
                })
    if not out:
        # This is not invented factual evidence. It is an explicit brief record
        # so Story has a traceable user-intent source while factual claims remain
        # unverified and must be treated accordingly by downstream policy.
        out.append({
            "claim_id": "USER-BRIEF-1",
            "claim": str(request.get("prompt") or request.get("brief") or ""),
            "source": "user-approved-brief",
            "status": "USER_SUPPLIED",
        })
    return out


def _source_understanding(request: Dict[str, Any], evidence: list[Dict[str, Any]], provider) -> tuple[Dict[str, Any] | None, list[Dict[str, Any]]]:
    packet = request.get("sourceIntelligence") or {}
    if not isinstance(packet, dict) or int(packet.get("extractedSourceCount") or 0) <= 0:
        return None, evidence
    supplied_ids = {str(item.get("claim_id") or "") for item in evidence if isinstance(item, dict) and str(item.get("claim_id") or "")}
    if not supplied_ids:
        return None, evidence
    visual_pages = []
    for item in packet.get("visualReferences") or []:
        if not isinstance(item, dict):
            continue
        page = int(item.get("page") or 0)
        if page < 1:
            continue
        visual_pages.append({
            "source_id": str(item.get("sourceId") or ""),
            "source_label": str(item.get("sourceLabel") or ""),
            "page": page,
            "sha256": str(item.get("sha256") or ""),
        })
    try:
        analysis = provider.complete("source_understanding", {
            "production_id": str(request.get("productionId") or ""),
            "brief": {
                "prompt": str(request.get("prompt") or request.get("brief") or ""),
                "family": request.get("family"),
                "video_type": request.get("videoType"),
            },
            "evidence": deepcopy(evidence),
            "source_warnings": list(packet.get("warnings") or []),
            "available_visual_pages": visual_pages,
            "provenance_law": str(packet.get("provenanceLaw") or "SOURCE_PROVENANCE_REQUIRED"),
        })
    except ProviderError as error:
        # Specialist source synthesis is valuable but not allowed to become a
        # single point of failure. The raw extracted, hashed evidence already
        # exists and remains available to Story/Showrunner. Preserve it exactly,
        # expose the missing specialist analysis, and continue; do not invent a
        # summary or silently drop the user's documents.
        return {
            "status":"UNAVAILABLE",
            "reason":str(error)[:800],
            "summary":"Dedicated source synthesis was unavailable; downstream reasoning must use the provenance-bound extracted evidence directly.",
            "claims":[],"contradictions":[],"unresolved_questions":[],"creative_relevance":[],
            "visual_evidence_needs":visual_pages,
            "source_integrity":{"used_only_provided_evidence":True,"contradictions_preserved":True,"invented_facts":False},
            "raw_evidence_preserved":True,
        }, evidence
    integrity = analysis.get("source_integrity") if isinstance(analysis, dict) else {}
    if isinstance(integrity, dict) and (integrity.get("invented_facts") is True or integrity.get("used_only_provided_evidence") is False or integrity.get("contradictions_preserved") is False):
        raise ProviderError("SOURCE_INTELLIGENCE_NEGATIVE_INTEGRITY_ADMISSION")
    # Positive self-certification is telemetry only. Derived claims must independently
    # satisfy provenance, confidence and deterministic lexical entailment before Story
    # can treat them as evidence.
    evidence_by_id={str(item.get("claim_id") or ""):item for item in evidence if isinstance(item,dict)}
    def _tokens(text: str) -> set[str]:
        return {x for x in re.findall(r"[a-z0-9]{4,}",str(text).lower()) if x not in {"that","with","from","this","have","will","into","than","then","they","their","about"}}
    def _entailed(claim: str, refs: list[str]) -> bool:
        ct=_tokens(claim)
        source_text=" ".join(str(evidence_by_id.get(r,{}).get("claim") or "") for r in refs)
        st=_tokens(source_text)
        if not ct: return False
        return len(ct & st)/max(1,len(ct)) >= 0.55
    derived = []
    for index, item in enumerate(analysis.get("claims") or []):
        if not isinstance(item, dict):
            continue
        refs = [str(x) for x in item.get("source_claim_ids") or []]
        if not refs or any(ref not in supplied_ids for ref in refs):
            raise ProviderError("SOURCE_INTELLIGENCE_UNKNOWN_PROVENANCE_ID")
        claim = str(item.get("claim") or "").strip()
        if not claim:
            continue
        confidence=str(item.get("confidence") or "").upper()
        verified=confidence=="HIGH" and _entailed(claim,refs)
        derived.append({
            "claim_id": f"SOURCE-SYNTH-{index + 1:03d}",
            "claim": claim,
            "source": "source-intelligence-analysis:" + ",".join(refs),
            "status": "SOURCE_INTELLIGENCE_VERIFIED" if verified else "DERIVED_PENDING_VERIFY",
            "source_claim_ids":refs,"confidence":confidence or "UNDECLARED","independent_entailment":verified,
        })
    disputed_ids=set()
    for contradiction in analysis.get("contradictions") or []:
        if not isinstance(contradiction, dict): continue
        refs=[str(x) for x in contradiction.get("source_claim_ids") or []]
        if any(ref not in supplied_ids for ref in refs): raise ProviderError("SOURCE_INTELLIGENCE_UNKNOWN_CONTRADICTION_PROVENANCE_ID")
        disputed_ids.update(refs)
    if disputed_ids:
        for item in evidence:
            if isinstance(item,dict) and str(item.get("claim_id") or "") in disputed_ids:
                item["status"]="DISPUTED_UNRESOLVED"; item["source_contradiction_detected"]=True
    verified=[item for item in derived if item.get("status")=="SOURCE_INTELLIGENCE_VERIFIED"]
    analysis["derived_claims_pending_verify"]=[item for item in derived if item.get("status")=="DERIVED_PENDING_VERIFY"]
    analysis["positive_integrity_declaration_is_telemetry_only"]=True
    return analysis, evidence + verified


def _source_visual_understanding(request: Dict[str, Any], evidence: list[Dict[str, Any]], provider) -> tuple[Dict[str, Any] | None, list[Dict[str, Any]]]:
    visuals = request.get("sourceVisualEvidence") or []
    if not isinstance(visuals, list) or not visuals:
        return None, evidence
    allowed = {}
    normalized=[]
    for item in visuals:
        if not isinstance(item,dict): continue
        source_id=str(item.get("sourceId") or ""); locator=str(item.get("locator") or ""); digest=str(item.get("sha256") or "")
        if not source_id or not locator or not digest: continue
        key=(source_id,locator,digest); allowed[key]=item; normalized.append(item)
    if not normalized:
        return None,evidence
    try:
        analysis=provider.complete("source_visual_understanding",{
            "production_id":str(request.get("productionId") or ""),
            "brief":{"prompt":str(request.get("prompt") or request.get("brief") or ""),"family":request.get("family"),"video_type":request.get("videoType")},
            "source_visual_evidence":deepcopy(normalized),
            "law":"FACTUAL_SOURCE_INSPECTION_ONLY__NO_CREATIVE_DIRECTION__NO_UNSEEN_INFERENCE",
        })
    except ProviderError as error:
        return {
            "status":"UNAVAILABLE",
            "reason":str(error)[:800],
            "unresolved_visuals":[{"source_id":str(x.get("sourceId") or ""),"locator":str(x.get("locator") or ""),"reason":"No compatible multimodal source-analysis route completed this inspection."} for x in normalized],
        }, evidence
    integrity=analysis.get("source_integrity") if isinstance(analysis,dict) else {}
    if isinstance(integrity,dict) and (integrity.get("invented_facts") is True or integrity.get("used_only_provided_visuals") is False):
        raise ProviderError("SOURCE_VISUAL_INTELLIGENCE_NEGATIVE_INTEGRITY_ADMISSION")
    derived=[]; counter=0
    for observation in analysis.get("observations") or []:
        if not isinstance(observation,dict): continue
        key=(str(observation.get("source_id") or ""),str(observation.get("locator") or ""),str(observation.get("sha256") or ""))
        if key not in allowed: raise ProviderError("SOURCE_VISUAL_INTELLIGENCE_UNKNOWN_PROVENANCE")
        confidence=str(observation.get("confidence") or "").upper()
        for claim in observation.get("factual_claims") or []:
            text=str(claim or "").strip()
            if not text: continue
            counter+=1; source_id,locator,digest=key
            derived.append({"claim_id":f"SOURCE-VIS-{counter:03d}","claim":text,"source":f"source-visual:{source_id}:{locator}:sha256:{digest}","status":"SOURCE_VISUAL_VERIFIED" if confidence=="HIGH" else "DERIVED_PENDING_VERIFY","confidence":confidence or "UNDECLARED"})
    analysis["derived_claims_pending_verify"]=[x for x in derived if x.get("status")=="DERIVED_PENDING_VERIFY"]
    return analysis,evidence+[x for x in derived if x.get("status")=="SOURCE_VISUAL_VERIFIED"]


def _calibration_registry(request: Dict[str, Any]) -> HumanCalibrationRegistry:
    registry=HumanCalibrationRegistry(target_family=str(request.get("family") or "") or None,p8_build_hash=str(request.get("p8BuildHash") or "") or None,judge_ensemble_hash=str(request.get("judgeEnsembleHash") or "") or None)
    snapshot=request.get("studioTasteCalibration") or {}
    records=snapshot.get("records") if isinstance(snapshot,dict) else []
    if not isinstance(records,list): records=[]
    for item in records:
        if not isinstance(item,dict): continue
        machine=item.get("machineReview"); human=item.get("humanReview")
        if not isinstance(machine,dict) or not isinstance(human,dict): continue
        registry.add(
            str(item.get("productionId") or "unknown"), machine, human,
            synthetic=bool(item.get("synthetic",False)),
            family=str(item.get("family") or "") or None,
            evidence_hash=str(item.get("evidenceHash") or "") or None,
            p8_build_hash=str(item.get("p8BuildHash") or "") or None,
            judge_ensemble_hash=str(item.get("judgeEnsembleHash") or "") or None,
        )
    return registry


def run_full_p8(request: Dict[str, Any], *, provider=None, progress: Progress = None, _continuation_state: Optional[Dict[str,Any]] = None) -> Dict[str, Any]:
    production_id = str(request.get("productionId") or "")
    if not production_id:
        raise ValueError("productionId is required")
    duration = max(1, min(60, int(request.get("durationSeconds") or 60)))
    continuation_state=deepcopy(_continuation_state) if isinstance(_continuation_state,dict) else None
    brief = deepcopy(continuation_state.get("brief") or {}) if continuation_state else _brief(request)
    evidence = deepcopy(continuation_state.get("evidence_ledger") or []) if continuation_state else _evidence(request)
    packet = load_current_capability_packet()
    capability_graph = build_capability_graph(request, packet)
    provider = provider or LiveCreativeModelProvider()
    _emit(progress, "CAPABILITY_GRAPH_VALIDATED", {"familyExecutionAuthority": capability_graph["current_authorities"].get("family_execution_body", {}), "capabilityGraphSchema": capability_graph.get("schema"), "creativeRepairPolicy": "ADAPTIVE_BOUNDED_ESCALATION"})
    if continuation_state:
        source_analysis=None; source_visual_analysis=None
    else:
        source_analysis, evidence = _source_understanding(request, evidence, provider)
        source_visual_analysis, evidence = _source_visual_understanding(request, evidence, provider)
    # A source analyst may request a specific page/slide inspection. Story cannot
    # proceed until every such requirement has a matching inspected hash-bound visual.
    required_visuals=[]
    if isinstance(source_analysis,dict): required_visuals=list(source_analysis.get("visual_evidence_needs") or [])
    if required_visuals:
        inspected=set()
        if isinstance(source_visual_analysis,dict):
            for obs in source_visual_analysis.get("observations") or []:
                if isinstance(obs,dict): inspected.add((str(obs.get("source_id") or ""),str(obs.get("locator") or "")))
        missing=[]
        for need in required_visuals:
            if isinstance(need,dict):
                sid=str(need.get("source_id") or need.get("sourceId") or ""); loc=str(need.get("locator") or (f"page {need.get('page')}" if need.get("page") else ""))
            else: sid=""; loc=str(need or "")
            if loc and not any((not sid or sid==isid) and (loc==iloc or loc in iloc or iloc in loc) for isid,iloc in inspected): missing.append({"source_id":sid,"locator":loc})
        if missing: raise ProviderError("SOURCE_REQUIRED_VISUAL_EVIDENCE_UNINSPECTED:"+json.dumps(missing,separators=(",",":"))[:1200])
    if source_analysis is not None or source_visual_analysis is not None:
        combined_source_analysis=deepcopy(source_analysis or {"summary":"No extracted textual source analysis was required.","claims":[],"contradictions":[],"unresolved_questions":[],"creative_relevance":[],"visual_evidence_needs":[],"source_integrity":{"used_only_provided_evidence":True,"contradictions_preserved":True,"invented_facts":False}})
        combined_source_analysis["visual_analysis"]=deepcopy(source_visual_analysis)
        brief["source_intelligence"] = combined_source_analysis
        _emit(progress, "SOURCE_INTELLIGENCE", {
            "claims": len(combined_source_analysis.get("claims") or []),
            "contradictions": len(combined_source_analysis.get("contradictions") or []),
            "unresolvedQuestions": len(combined_source_analysis.get("unresolved_questions") or []),
            "visualEvidenceNeeds": len(combined_source_analysis.get("visual_evidence_needs") or []),
            "visualAnalysisStatus": "COMPLETE" if isinstance(source_visual_analysis,dict) and source_visual_analysis.get("status")!="UNAVAILABLE" else ("UNAVAILABLE" if source_visual_analysis else "NOT_REQUIRED"),
            "provenancePreserved": True,
        })

    sr = NexMindSupremeShowrunnerP8(production_id, brief, doctrine={
        "product": "Standalone Studio V1",
        "family": request.get("family"),
        "videoType": request.get("videoType"),
        "publicInterfaceLaw": "customer directs; Studio produces",
        "planPreviewAuthority": "NON_AUTHORITATIVE",
        "revisionLaw": "Preserve unaffected previously locked decisions; alter only what the customer revision requires." if request.get("revisionContext") else "NONE",
        "autonomousRepairLaw": "Producer REVISE/REJECT triggers adaptive bounded department-owned repair; local exhaustion escalates causal creative scope and the production remains alive; quality gates never weaken; generic downgrade is forbidden.",
    })
    if continuation_state:
        # Internal recursion only: preserve exact accepted decisions, repair ledger and
        # lineage budgets while re-entering the pipeline at the newly invalidated owner.
        sr.state=deepcopy(continuation_state)
        sr.state["capability_graph"]=deepcopy(capability_graph)
    else:
        sr.set_creative_memory_refs(request.get("creativeMemory") or [])
        sr.set_capability_graph(capability_graph)
    attempt_limits = _adaptive_attempt_limits(request)
    _ensure_repair_state(sr, attempt_limits)

    p2 = CreativeCouncil(sr, StoryDirector(provider), VisualConceptDirector(provider), ExecutiveProducer(provider), ShowrunnerDecisionIntelligence(provider))
    illustration = IllustrationFormResolver.from_file(P8_ROOT / "donors" / "NEXSTUDIO_ILLUSTRATION_CAPABILITY_INDEX_V1.json")
    p3 = CreativeCouncilP3(sr, ArtDirector(provider), illustration, P3ExecutiveProducer(provider), ArtShowrunnerDecisionIntelligence(provider), StoryboardCompiler())
    p45 = CreativeCouncilP45(sr, CinematographyDirector(provider), EditorialRhythmDirector(provider), P45ExecutiveProducer(provider), P45ShowrunnerDecisionIntelligence(provider), EditorialTimelineCompiler(), TemporalStoryboardCompiler())
    performers = PerformerCapabilityRegistry(packet["performerOverrides"])
    p6 = CreativeCouncilP6(sr, MotionPerformanceDirector(provider, performers), MotionExecutiveProducer(provider), MotionShowrunnerDecisionIntelligence(provider), PerformanceStoryboardCompiler())
    resources = SoundResourceRegistry.from_file(P8_ROOT / "donors" / "authorized_sound_index.json")
    p7 = CreativeCouncilP7(sr, SoundDirector(provider, resources, False), SoundExecutiveProducer(provider), SoundShowrunnerDecisionIntelligence(provider), SoundStoryboardCompiler())
    calibration = _calibration_registry(request)
    p8 = CreativeCouncilP8(sr, FinalExecutiveProducer(provider), calibration)

    story = None
    final_board = None
    provider_recovery_state=deepcopy(sr.state)
    provider_recovery_stage="PIPELINE_START"
    try:
        while True:
            # STORY — adaptive brief-specific materially different narrative strategies + independent Producer review + Showrunner selection.
            if "film_thesis" not in sr.state["decisions"]:
                while "film_thesis" not in sr.state["decisions"]:
                    provider_recovery_state=deepcopy(sr.state); provider_recovery_stage="STORY"
                    attempt = _reserve_attempt(sr, "STORY")
                    _emit(progress, "STORY", {"attempt": attempt, "maximum": _department_attempt_limit(sr,"STORY"), "repair": attempt > 1})
                    try:
                        story_result = p2.develop_story_competition(evidence)
                    except ContractViolation as error:
                        _schedule_director_contract_repair(sr, "STORY", error)
                        continue
                    story = story_result.get("story")
                    if not (story_result.get("diversity") or {}).get("meaningfully_diverse", True):
                        _schedule_repair(sr,"STORY","Story candidate set lacked material diversity",_diversity_repair_context(story_result.get("reviews") or [],"STORY"))
                        continue
                    if "film_thesis" in sr.state["decisions"] and story:
                        _clear_repair_context(sr, "STORY")
                        break
                    _schedule_repair(sr, "STORY", "No Producer-accepted Story candidate", _reviews_context(story_result.get("reviews") or []))
            else:
                story = _committed_payload(sr, "film_thesis")

            # VISUAL CONCEPT — regenerate a materially new candidate set if none is Producer-accepted.
            if "visual_concept" not in sr.state["decisions"]:
                while "visual_concept" not in sr.state["decisions"]:
                    provider_recovery_state=deepcopy(sr.state); provider_recovery_stage="VISUAL_CONCEPT"
                    attempt = _reserve_attempt(sr, "VISUAL_CONCEPT")
                    _emit(progress, "VISUAL_CONCEPT", {"attempt": attempt, "maximum": _department_attempt_limit(sr,"VISUAL_CONCEPT"), "repair": attempt > 1})
                    try:
                        visual_result = p2.develop_visual_candidates(story)
                    except ContractViolation as error:
                        _schedule_director_contract_repair(sr, "VISUAL_CONCEPT", error)
                        continue
                    if not (visual_result.get("diversity") or {}).get("meaningfully_diverse", True):
                        _schedule_repair(sr,"VISUAL_CONCEPT","Visual candidate set lacked material diversity",_diversity_repair_context(visual_result.get("reviews") or [],"VISUAL_CONCEPT"))
                        continue
                    accepted = [x for x in visual_result["reviews"] if x["review"]["verdict"] == "ACCEPT"]
                    if accepted:
                        try:
                            selected_visual = _selection_contract_retry(lambda: p2.showrunner_select_visual(story, visual_result))
                        except ContractViolation as error:
                            _schedule_director_contract_repair(sr,"VISUAL_CONCEPT",error)
                            continue
                        visual = selected_visual["committed"]["payload"]
                        _record_deferred_validations(sr, selected_visual.get("selected_review") or {}, department="VISUAL_CONCEPT", candidate=visual)
                        _clear_repair_context(sr, "VISUAL_CONCEPT")
                        break
                    _schedule_repair(sr, "VISUAL_CONCEPT", "No Producer-accepted Visual Concept candidate", _reviews_context(visual_result["reviews"]))
            else:
                visual = _committed_payload(sr, "visual_concept")

            # ART DIRECTION.
            if "art_direction" not in sr.state["decisions"]:
                while "art_direction" not in sr.state["decisions"]:
                    provider_recovery_state=deepcopy(sr.state); provider_recovery_stage="ART_DIRECTION"
                    attempt = _reserve_attempt(sr, "ART_DIRECTION")
                    _emit(progress, "ART_DIRECTION", {"attempt": attempt, "maximum": _department_attempt_limit(sr,"ART_DIRECTION"), "repair": attempt > 1})
                    try:
                        art_result = p3.develop_art(story, visual)
                    except ContractViolation as error:
                        _schedule_director_contract_repair(sr, "ART_DIRECTION", error)
                        continue
                    if not (art_result.get("diversity") or {}).get("meaningfully_diverse", True):
                        _schedule_repair(sr,"ART_DIRECTION","Art candidate set lacked material diversity",_diversity_repair_context(art_result.get("reviewed") or [],"ART_DIRECTION"))
                        continue
                    accepted = [x for x in art_result["reviewed"] if x["review"]["verdict"] == "ACCEPT"]
                    if accepted:
                        try:
                            selected_art = _selection_contract_retry(lambda: p3.select_art(story, visual, art_result))
                        except ContractViolation as error:
                            _schedule_director_contract_repair(sr,"ART_DIRECTION",error)
                            continue
                        art = selected_art["candidate"]
                        art_form = selected_art["form_resolution"]
                        selected_review=next((x.get("review") for x in art_result.get("reviewed",[]) if x.get("candidate",{}).get("candidate_id")==art.get("candidate_id")),{})
                        _record_deferred_validations(sr, selected_review or {}, department="ART_DIRECTION", candidate=art)
                        _clear_repair_context(sr, "ART_DIRECTION")
                        break
                    _schedule_repair(sr, "ART_DIRECTION", "No Producer-accepted Art Direction candidate", _reviews_context(art_result["reviewed"]))
            else:
                art_payload = _decision_payload(sr, "art_direction")
                art = deepcopy(art_payload.get("art_direction") or art_payload)
                art_form = deepcopy(art_payload.get("form_resolution") or {})
                selected_art = {"candidate": art, "form_resolution": art_form}

            # KEY-STATE STORYBOARD — a failed static read routes back to the implicated upstream creative owner.
            if "storyboard" not in sr.state["decisions"]:
                provider_recovery_state=deepcopy(sr.state); provider_recovery_stage="STORYBOARD"
                _emit(progress, "STORYBOARD", {"revision": sr.state["revision"]})
                try:
                    key_board_result = p3.compile_and_review_storyboard(story, visual, selected_art)
                except StoryboardGateError as gate_error:
                    issues=deepcopy(gate_error.args[0] if gate_error.args and isinstance(gate_error.args[0],list) else [{"code":"STORYBOARD_GATE_FAILED","detail":str(gate_error)}])
                    gate_review={"verdict":"REVISE","issues":issues,"strengths":[],"revision_brief":"Repair the upstream owner responsible for the deterministic key-state storyboard gate failure."}
                    owner=_key_storyboard_review_owner(gate_review)
                    owner_anchor = story if owner=="STORY" else visual if owner=="VISUAL_CONCEPT" else art
                    _schedule_repair(sr,owner,"Key-state storyboard deterministic gate requested upstream repair",_review_context(gate_review,previous=owner_anchor))
                    continue
                key_board = key_board_result["board"]
                if "storyboard" not in sr.state["decisions"]:
                    owner = _key_storyboard_review_owner(key_board_result["review"])
                    owner_anchor = story if owner=="STORY" else visual if owner=="VISUAL_CONCEPT" else art
                    _schedule_repair(sr, owner, "Key-state storyboard review requested upstream repair", _review_context(key_board_result["review"], previous=owner_anchor))
                    continue
            else:
                sb_payload = _decision_payload(sr, "storyboard")
                key_board = deepcopy(sb_payload.get("storyboard") or sb_payload)

            # CINEMATOGRAPHY.
            if "cinematography" not in sr.state["decisions"]:
                while "cinematography" not in sr.state["decisions"]:
                    provider_recovery_state=deepcopy(sr.state); provider_recovery_stage="CINEMATOGRAPHY"
                    attempt = _reserve_attempt(sr, "CINEMATOGRAPHY")
                    _emit(progress, "CINEMATOGRAPHY", {"attempt": attempt, "maximum": _department_attempt_limit(sr,"CINEMATOGRAPHY"), "repair": attempt > 1})
                    try:
                        cinema_result = p45.develop_cinema(story, visual, art, key_board)
                    except ContractViolation as error:
                        _schedule_director_contract_repair(sr, "CINEMATOGRAPHY", error)
                        continue
                    if not (cinema_result.get("diversity") or {}).get("meaningfully_diverse", True):
                        _schedule_repair(sr,"CINEMATOGRAPHY","Cinematography candidate set lacked material diversity",_diversity_repair_context(cinema_result.get("reviewed") or [],"CINEMATOGRAPHY"))
                        continue
                    accepted = [x for x in cinema_result["reviewed"] if x["review"]["verdict"] == "ACCEPT"]
                    if accepted:
                        try:
                            cinema_item = _selection_contract_retry(lambda: p45.select_cinema(story, cinema_result))
                        except ContractViolation as error:
                            _schedule_director_contract_repair(sr,"CINEMATOGRAPHY",error)
                            continue
                        cinema = cinema_item["candidate"]
                        _clear_repair_context(sr, "CINEMATOGRAPHY")
                        break
                    _schedule_repair(sr, "CINEMATOGRAPHY", "No Producer-accepted Cinematography candidate", _reviews_context(cinema_result["reviewed"]))
            else:
                cinema = _committed_payload(sr, "cinematography")
                cinema_item = {"candidate": cinema}

            # EDITORIAL / RHYTHM.
            if "editorial_rhythm" not in sr.state["decisions"]:
                while "editorial_rhythm" not in sr.state["decisions"]:
                    provider_recovery_state=deepcopy(sr.state); provider_recovery_stage="EDITORIAL_RHYTHM"
                    attempt = _reserve_attempt(sr, "EDITORIAL_RHYTHM")
                    _emit(progress, "EDITORIAL_RHYTHM", {"attempt": attempt, "maximum": _department_attempt_limit(sr,"EDITORIAL_RHYTHM"), "repair": attempt > 1})
                    try:
                        editorial_result = p45.develop_editorial(story, visual, art, cinema, target_duration_frames=duration * 30, project_rate=30)
                    except ContractViolation as error:
                        _schedule_director_contract_repair(sr, "EDITORIAL_RHYTHM", error)
                        continue
                    if not (editorial_result.get("diversity") or {}).get("meaningfully_diverse", True):
                        _schedule_repair(sr,"EDITORIAL_RHYTHM","Editorial candidate set lacked material diversity",_diversity_repair_context(editorial_result.get("reviewed") or [],"EDITORIAL_RHYTHM"))
                        continue
                    accepted = [x for x in editorial_result["reviewed"] if x["review"]["verdict"] == "ACCEPT"]
                    if accepted:
                        try:
                            editorial_item = _selection_contract_retry(lambda: p45.select_editorial(story, editorial_result))
                        except ContractViolation as error:
                            _schedule_director_contract_repair(sr,"EDITORIAL_RHYTHM",error)
                            continue
                        editorial = editorial_item["candidate"]
                        editorial_timeline = editorial_item["timeline"]
                        _clear_repair_context(sr, "EDITORIAL_RHYTHM")
                        break
                    _schedule_repair(sr, "EDITORIAL_RHYTHM", "No Producer-accepted Editorial/Rhythm candidate", _reviews_context(editorial_result["reviewed"]))
            else:
                ed_payload = _decision_payload(sr, "editorial_rhythm")
                editorial = deepcopy(ed_payload.get("editorial_rhythm") or ed_payload)
                editorial_timeline = deepcopy(ed_payload.get("editorial_timeline") or EditorialTimelineCompiler().compile(editorial))
                editorial_item = {"candidate": editorial, "timeline": editorial_timeline}

            # TEMPORAL STORYBOARD — failed coherence routes to Cinema or Editorial rather than terminating.
            if "storyboard_temporal" not in sr.state["decisions"]:
                provider_recovery_state=deepcopy(sr.state); provider_recovery_stage="STORYBOARD_TEMPORAL"
                try:
                    temporal = p45.compile_temporal_storyboard(story, key_board, cinema_item, editorial_item)
                except TemporalStoryboardGateError as gate_error:
                    issues=deepcopy(gate_error.args[0] if gate_error.args and isinstance(gate_error.args[0],list) else [{"code":"TEMPORAL_STORYBOARD_GATE_FAILED","detail":str(gate_error)}])
                    gate_review={"verdict":"REVISE","issues":issues,"strengths":[],"revision_brief":"Repair the Cinema or Editorial owner responsible for the deterministic temporal execution gate failure."}
                    owner=_review_owner(gate_review,"EDITORIAL_RHYTHM",{"CINEMATOGRAPHY","EDITORIAL_RHYTHM"})
                    owner_anchor = cinema if owner=="CINEMATOGRAPHY" else editorial
                    _schedule_repair(sr,owner,"Temporal storyboard deterministic gate requested upstream repair",_review_context(gate_review,previous=owner_anchor))
                    continue
                temporal_board = temporal["board"]
                if "storyboard_temporal" not in sr.state["decisions"]:
                    owner = _review_owner(temporal["review"], "EDITORIAL_RHYTHM", {"CINEMATOGRAPHY", "EDITORIAL_RHYTHM"})
                    owner_anchor = cinema if owner=="CINEMATOGRAPHY" else editorial
                    _schedule_repair(sr, owner, "Temporal storyboard review requested upstream repair", _review_context(temporal["review"], previous=owner_anchor))
                    continue
            else:
                temporal_payload = _decision_payload(sr, "storyboard_temporal")
                temporal_board = deepcopy(temporal_payload.get("storyboard_temporal") or temporal_payload)

            # MOTION / PERFORMANCE — capability gaps are first offered a bounded safe rewrite.
            if "motion_performance" not in sr.state["decisions"]:
                while "motion_performance" not in sr.state["decisions"]:
                    provider_recovery_state=deepcopy(sr.state); provider_recovery_stage="MOTION_PERFORMANCE"
                    attempt = _reserve_attempt(sr, "MOTION_PERFORMANCE")
                    _emit(progress, "MOTION_PERFORMANCE", {"attempt": attempt, "maximum": _department_attempt_limit(sr,"MOTION_PERFORMANCE"), "repair": attempt > 1})
                    try:
                        motion_result = p6.develop(story, visual, art, cinema, editorial, temporal_board)
                    except ContractViolation as error:
                        _schedule_director_contract_repair(sr, "MOTION_PERFORMANCE", error)
                        continue
                    if not (motion_result.get("diversity") or {}).get("meaningfully_diverse", True):
                        _schedule_repair(sr,"MOTION_PERFORMANCE","Motion candidate set lacked material diversity",_diversity_repair_context(motion_result.get("reviewed") or [],"MOTION_PERFORMANCE"))
                        continue
                    eligible = [x for x in motion_result["reviewed"] if x["review"]["verdict"] == "ACCEPT" and x["candidate"].get("executable", False)]
                    if eligible:
                        try:
                            motion_item = _selection_contract_retry(lambda: p6.select(story, motion_result))
                        except ContractViolation as error:
                            _schedule_director_contract_repair(sr,"MOTION_PERFORMANCE",error)
                            continue
                        motion = motion_item["candidate"]
                        _clear_repair_context(sr, "MOTION_PERFORMANCE")
                        break
                    _schedule_repair(sr, "MOTION_PERFORMANCE", "No Producer-accepted executable Motion/Performance candidate", _reviews_context(motion_result["reviewed"]))
            else:
                motion = _committed_payload(sr, "motion_performance")
                motion_item = {"candidate": motion}
            performance = p6.compile_performance_storyboard(temporal_board, motion_item)
            if performance.get("gate",{}).get("status")!="PASS":
                gate_review={"verdict":"REVISE","issues":[{"code":"PERFORMANCE_STORYBOARD_GATE_BLOCKED","detail":json.dumps(performance.get("gate") or {},sort_keys=True)}],"strengths":[],"revision_brief":"Repair Motion/Performance so the compiled performance storyboard is executable."}
                _schedule_repair(sr,"MOTION_PERFORMANCE","Performance storyboard deterministic gate blocked",_review_context(gate_review,previous=motion))
                continue

            # SOUND.
            if "sound_direction" not in sr.state["decisions"]:
                while "sound_direction" not in sr.state["decisions"]:
                    provider_recovery_state=deepcopy(sr.state); provider_recovery_stage="SOUND_DIRECTION"
                    attempt = _reserve_attempt(sr, "SOUND_DIRECTION")
                    _emit(progress, "SOUND_DIRECTION", {"attempt": attempt, "maximum": _department_attempt_limit(sr,"SOUND_DIRECTION"), "repair": attempt > 1})
                    try:
                        sound_result = p7.develop(story, editorial, motion, performance["board"])
                    except ContractViolation as error:
                        _schedule_director_contract_repair(sr, "SOUND_DIRECTION", error)
                        continue
                    if not (sound_result.get("diversity") or {}).get("meaningfully_diverse", True):
                        _schedule_repair(sr,"SOUND_DIRECTION","Sound candidate set lacked material diversity",_diversity_repair_context(sound_result.get("reviewed") or [],"SOUND_DIRECTION"))
                        continue
                    accepted = [x for x in sound_result["reviewed"] if x["review"]["verdict"] == "ACCEPT" and x["candidate"].get("executable_resource_plan", False)]
                    if accepted:
                        try:
                            sound_item = _selection_contract_retry(lambda: p7.select(story, sound_result))
                        except ContractViolation as error:
                            _schedule_director_contract_repair(sr,"SOUND_DIRECTION",error)
                            continue
                        sound = sound_item["candidate"]
                        _clear_repair_context(sr, "SOUND_DIRECTION")
                        break
                    _schedule_repair(sr, "SOUND_DIRECTION", "No Producer-accepted Sound Direction candidate", _reviews_context(sound_result["reviewed"]))
            else:
                sound = _committed_payload(sr, "sound_direction")
                sound_item = {"candidate": sound}
            sound_compiled = p7.compile_sound_storyboard(performance["board"], sound_item)
            if sound_compiled.get("gate",{}).get("status")!="PASS":
                gate_review={"verdict":"REVISE","issues":[{"code":"SOUND_STORYBOARD_GATE_BLOCKED","detail":json.dumps(sound_compiled.get("gate") or {},sort_keys=True)}],"strengths":[],"revision_brief":"Repair Sound Direction so the compiled sound storyboard is complete."}
                _schedule_repair(sr,"SOUND_DIRECTION","Sound storyboard deterministic gate blocked",_review_context(gate_review,previous=sound))
                continue
            final_board = sound_compiled["board"]

            # RENDER BOUNDARY — Final Producer is forbidden before encoded media exists.
            # The first P8 pass ends with a complete creative state. Family execution then
            # renders the exact review film; only run_finalize_p8 may perform perceptual
            # Final Producer review and Creative Lock on hash-bound media bytes.
            _emit(progress, "DEPARTMENTS_COMPLETE", {"revision": sr.state["revision"], "renderReady": True})
            return _result(
                sr, provider, "DEPARTMENTS_COMPLETE", "P8_DEPARTMENTS_COMPLETE_RENDER_READY",
                story=story, final_board=final_board,
                extra={
                    "renderReady": True,
                    "finalProducerInvoked": False,
                    "creativeLockCommitted": False,
                    "autonomousRepair": deepcopy(sr.state.get("autonomous_creative_repair")),
                    "productionValidationRequirements": deepcopy(sr.state.get("production_validation_requirements") or []),
                },
            )
    except CreativeRepairBudgetExhausted as error:
        # Local bounded repair exhausted. First climb only as far upstream as needed.
        # If a downstream causal owner still has local budget, replan that owner in
        # the SAME Showrunner state and preserve accepted upstream decisions. Only
        # Story-owned exhaustion starts a new globally bounded strategy round.
        escalation_owner, escalation_chain=_resolve_available_escalation_owner(sr,error.department)
        repair_state=sr.state.get("autonomous_creative_repair") or {}
        prior=request.get("autonomousRepairContext") or {}
        prior_round=max(int(prior.get("round") or 0) if isinstance(prior,dict) else 0, int(repair_state.get("global_broader_round") or 0))
        broader_round=prior_round+1 if escalation_owner=="STORY" else _nonstory_broader_lineage_count(sr,escalation_owner)+1
        repair_request={
            "schema":"StudioAutonomousCreativeRepairRequestV2",
            "round":broader_round,
            "escalation_scope":"BROADER_CREATIVE_STRATEGY",
            "owner_department":escalation_owner,
            "source_department":error.department,
            "escalation_chain":escalation_chain,
            "invalidate_slots":deepcopy(DEPARTMENT_INVALIDATION.get(escalation_owner,["visual_concept","art_direction","cinematography","editorial_rhythm","motion_performance","sound_direction"])),
            "issues":deepcopy(error.context.get("issues") or []) if isinstance(error.context,dict) else [],
            "revision_plan":deepcopy(error.context.get("revision_briefs") or []) if isinstance(error.context,dict) else [],
            "rejected_candidates":deepcopy(error.context.get("rejected_candidates") or []) if isinstance(error.context,dict) else [],
            "quality_reasons":["LOCAL_CREATIVE_LINEAGE_EXHAUSTED",str(error.reason or "")],
            "cumulative_lifetime_attempts":deepcopy(repair_state.get("lifetime_attempts") or {}),
            "current_story_signature":_story_strategy_signature(story),
            "production_disposition":"CONTINUE_REPLANNING",
            "quality_floor_may_weaken":False,
            "silent_generic_fallback_allowed":False,
            "law":"LOCAL_IDEA_MAY_FAIL__PAID_PRODUCTION_REPLANS__NEVER_LOWER_QUALITY_GATE",
        }
        _emit(progress,"BROADER_STRATEGY_REPLAN",{"department":error.department,"ownerDepartment":escalation_owner,"attempts":error.attempts,"escalationChain":escalation_chain})
        if escalation_owner!="STORY":
            lineage_limit=_nonstory_broader_lineage_limit(request)
            lineage_used=_nonstory_broader_lineage_count(sr,escalation_owner)
            if lineage_used < lineage_limit:
                ctx=_apply_in_place_broader_replan(sr,owner=escalation_owner,source_error=error,repair_request=repair_request)
                _emit(progress,"BROADER_STRATEGY_REPLAN_AUTO_CONTINUE",{
                    "round":lineage_used+1,"maximum":lineage_limit,"ownerDepartment":escalation_owner,
                    "mode":"SAME_DEPARTMENT_NEW_LINEAGE","preservedDecisions":ctx.get("preserve_decision_slots") or [],
                    "upstreamStoryPreserved":True,
                })
                return run_full_p8(request,provider=provider,progress=progress,_continuation_state=deepcopy(sr.state))
            # Crucial invariant: exhausting a non-Story department's broader lineage is
            # NOT evidence that Story is wrong. Stop with exact department diagnostics
            # rather than silently rewriting an already accepted upstream Story.
            return _result(sr,provider,"REVISE","P8_NONSTORY_BROADER_LINEAGE_EXHAUSTED",story=story,final_board=final_board,extra={
                "department":error.department,"ownerDepartment":escalation_owner,
                "attempts":error.attempts,"maxAttempts":error.maximum,
                "broaderLineagesUsed":lineage_used,"broaderLineageLimit":lineage_limit,
                "repairRequest":repair_request,"autonomousRepair":deepcopy(sr.state.get("autonomous_creative_repair")),
                "upstreamStoryPreserved":True,"upstreamEscalationBlockedWithoutCertifiedDiagnosis":True,
                "qualityOverrideAllowed":False,"customerVisibleFailure":False,
            })
        auto_replan=_next_broader_strategy_request(request,repair_request,"STORY") if escalation_owner=="STORY" else None
        if auto_replan is not None:
            repair_state["global_broader_round"]=repair_request["round"]
            _emit(progress,"BROADER_STRATEGY_REPLAN_AUTO_CONTINUE",{"round":auto_replan["round"],"maximum":auto_replan["maximum"],"ownerDepartment":"STORY","mode":"FULL_STRATEGY_RESTART"})
            return run_full_p8(auto_replan["request"],provider=provider,progress=progress)
        return _result(sr,provider,"REVISE","P8_BROADER_STRATEGY_REPLAN_REQUIRED",story=story,final_board=final_board,extra={
            "department":error.department,"attempts":error.attempts,"maxAttempts":error.maximum,
            "repairRequest":repair_request,"autonomousRepair":deepcopy(sr.state.get("autonomous_creative_repair")),
            "qualityOverrideAllowed":False,"customerVisibleFailure":False,
        })
    except ProviderError as error:
        text=str(error)
        code=text.split(":",1)[0] if text.startswith("LIVE_PROVIDER_BLOCKED_") else "LIVE_PROVIDER_CALL_FAILED"
        # Provider transport/schema failure is not a creative attempt. Restore the
        # exact state from before the incomplete provider-backed stage so a caller
        # can safely resume without duplicate proposal IDs, stale reviews or burned
        # department budget.
        if isinstance(provider_recovery_state,dict):
            sr.state=deepcopy(provider_recovery_state)
        continuation_overrides={}
        if isinstance(request.get("autonomousRepairContext"),dict):
            continuation_overrides["autonomousRepairContext"]=deepcopy(request.get("autonomousRepairContext"))
        if request.get("broaderStrategyMaxRounds") is not None:
            continuation_overrides["broaderStrategyMaxRounds"]=request.get("broaderStrategyMaxRounds")
        return _result(sr,provider,"PROVIDER_UNAVAILABLE",code,story=story,final_board=final_board,extra={
            "detail":text,
            "autonomousRepair":deepcopy(sr.state.get("autonomous_creative_repair")),
            "productionDisposition":"RETRY_PROVIDER_AND_CONTINUE",
            "resumeSafe":True,
            "resumeStage":provider_recovery_stage,
            "continuationRequestOverrides":continuation_overrides,
        })


def _resolved_task_audit(provider, task: str) -> Dict[str, Any] | None:
    audits=provider.audit_dicts() if hasattr(provider,"audit_dicts") else []
    for item in reversed(audits):
        if isinstance(item,dict) and item.get("task")==task and item.get("status")=="PASS": return item
    return None

def _judge_ensemble_hash(provider) -> str | None:
    """Bind calibration to the two-role review process, not to different model identities.

    Final Producer and Perceptual Auditor independence is procedural: separate task
    invocations, separate role contracts, blind auditor input, and exact-media delivery.
    A single sufficiently capable provider/model may serve both roles (and upstream
    creative roles) without becoming a runtime or release blocker.
    """
    fp=_resolved_task_audit(provider,"final_producer"); pa=_resolved_task_audit(provider,"perceptual_auditor")
    if not fp or not pa: return None
    members=[]
    for task,item in (("final_producer",fp),("perceptual_auditor",pa)):
        members.append({
            "task":task,
            "role":str(item.get("role") or task),
            "provider":str(item.get("provider") or item.get("resolved_provider") or item.get("requested_provider") or ""),
            "model":str(item.get("resolved_model") or item.get("model") or item.get("requested_model") or ""),
            "process":"SEPARATE_BLIND_EXACT_MEDIA_REVIEW_V1",
        })
    return hashlib.sha256(json.dumps(sorted(members,key=lambda x:x["task"]),separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

def run_finalize_p8(request: Dict[str, Any], *, provider=None, progress: Progress = None) -> Dict[str, Any]:
    """Re-run independent final authority on real hash-bound render evidence.

    A creative rejection becomes a broader quality-preserving replan request.
    Missing/corrupt evidence becomes recovery work. Neither is a customer-level
    creative failure state.
    """
    checkpoint=request.get("checkpoint"); final_board=request.get("finalBoard"); production_id=str(request.get("productionId") or "")
    if not production_id or not isinstance(checkpoint,dict) or not isinstance(final_board,dict):
        raise ValueError("productionId, checkpoint and finalBoard are required")
    if checkpoint.get("schema") != "NexMindSupremeShowrunnerCheckpointV1": raise ValueError("unsupported checkpoint schema")
    with tempfile.NamedTemporaryFile("w",encoding="utf-8",suffix=".json",delete=False) as handle:
        json.dump(checkpoint,handle,ensure_ascii=False); checkpoint_path=handle.name
    try: sr=NexMindSupremeShowrunnerP8.resume(checkpoint_path)
    finally: Path(checkpoint_path).unlink(missing_ok=True)
    if sr.state.get("production_id") != production_id: raise ValueError("checkpoint production mismatch")
    if sr.state.get("creative_locked"):
        return _result(sr,provider or LiveCreativeModelProvider(),"CREATIVE_LOCKED","CREATIVE_LOCK_ALREADY_COMMITTED",final_board=final_board)

    artifacts=request.get("multimodalArtifacts") or []
    mm=build_multimodal_evidence(artifacts,audio_expected=bool(request.get("audioExpected",True)))
    supplied_media_set=str(request.get("mediaSetSha256") or "")
    perceptual=deepcopy(request.get("perceptualMedia") or {})
    if mm.get("status") != "COMPLETE" or not supplied_media_set or supplied_media_set!=str(mm.get("media_set_sha256") or ""):
        mm["issues"]=[*list(mm.get("issues") or []),"MEDIA_SET_IDENTITY_MISMATCH"]
        return _result(sr,provider or LiveCreativeModelProvider(),"REVISE","P8_MULTIMODAL_EVIDENCE_RECOVERY_REQUIRED",final_board=final_board,extra={"multimodalEvidence":mm,"productionDisposition":"RECOVER_EVIDENCE_AND_CONTINUE"})
    video_hashes={str(a.get("media_sha256") or "") for a in mm.get("artifacts",[]) if isinstance(a,dict) and a.get("kind")=="VIDEO"}
    if str(perceptual.get("videoMediaSha256") or "") not in video_hashes or not (perceptual.get("temporalFrames") or []) or (bool(request.get("audioExpected",True)) and not isinstance(perceptual.get("audio"),dict)):
        mm["issues"]=[*list(mm.get("issues") or []),"PERCEPTUAL_MEDIA_NOT_BOUND_TO_REVIEWED_VIDEO"]
        return _result(sr,provider or LiveCreativeModelProvider(),"REVISE","P8_MULTIMODAL_EVIDENCE_RECOVERY_REQUIRED",final_board=final_board,extra={"multimodalEvidence":mm,"productionDisposition":"RECOVER_EVIDENCE_AND_CONTINUE"})
    mm["media_set_sha256"]=supplied_media_set
    mm["perceptual_media"]=perceptual

    provider=provider or LiveCreativeModelProvider(); story=_committed_payload(sr,"film_thesis")
    review_state=deepcopy(sr.state); review_state.setdefault("decisions",{}).pop("final_producer",None)
    _emit(progress,"FINAL_PRODUCER",{"multimodalEvidence":"COMPLETE"})
    # Before the judge ensemble is actually resolved, calibration must remain fail-closed.
    preliminary_calibration=_calibration_registry(request).status()
    final_review=FinalExecutiveProducer(provider).review(production_id,sr.state["brief"],story,review_state,final_board,multimodal_evidence=mm,calibration=preliminary_calibration)
    auditor_request={"production_id":production_id,"brief":deepcopy(sr.state["brief"]),"final_board":deepcopy(final_board),"multimodal_evidence":deepcopy(mm),"law":"INDEPENDENT_NON_NUMERIC_VETO__DO_NOT_RECEIVE_FINAL_PRODUCER_VERDICT_OR_SCORES"}
    perceptual_audit=provider.complete("perceptual_auditor",auditor_request)
    deliveries=provider.perceptual_delivery_dicts() if hasattr(provider,"perceptual_delivery_dicts") else []
    fp_matching=[d for d in deliveries if d.get("task")=="final_producer" and d.get("media_set_sha256")==supplied_media_set and int(d.get("image_count") or 0)>0 and int(d.get("audio_count") or 0)>0]
    pa_matching=[d for d in deliveries if d.get("task")=="perceptual_auditor" and d.get("media_set_sha256")==supplied_media_set and int(d.get("image_count") or 0)>0 and int(d.get("audio_count") or 0)>0]
    if not fp_matching or not pa_matching:
        mm["perceptually_reviewed"]=False; mm["issues"]=[*list(mm.get("issues") or []),"TWO_JUDGE_NATIVE_MEDIA_DELIVERY_UNPROVEN"]
        return _result(sr,provider,"REVISE","P8_MULTIMODAL_EVIDENCE_RECOVERY_REQUIRED",story=story,final_board=final_board,extra={"finalReview":final_review,"perceptualAudit":perceptual_audit,"multimodalEvidence":mm,"productionDisposition":"RECOVER_EVIDENCE_AND_CONTINUE"})
    ensemble_hash=_judge_ensemble_hash(provider)
    if not ensemble_hash:
        return _result(sr,provider,"REVISE","P8_JUDGE_PROCESS_EVIDENCE_RECOVERY_REQUIRED",story=story,final_board=final_board,extra={"detail":"Both role-scoped review audits are required","finalReview":final_review,"perceptualAudit":perceptual_audit,"multimodalEvidence":mm})
    if perceptual_audit.get("verdict")!="PASS":
        return _result(sr,provider,"REVISE","P8_INDEPENDENT_PERCEPTUAL_AUDITOR_VETO",story=story,final_board=final_board,extra={"finalReview":final_review,"perceptualAudit":perceptual_audit,"judgeEnsembleHash":ensemble_hash,"multimodalEvidence":mm})
    calibration_request=deepcopy(request); calibration_request["judgeEnsembleHash"]=ensemble_hash
    calibration_status=_calibration_registry(calibration_request).status()
    mm["perceptually_reviewed"]=True; mm["perceptual_delivery"]={"finalProducer":deepcopy(fp_matching[-1]),"perceptualAuditor":deepcopy(pa_matching[-1])}; mm.pop("perceptual_media",None)
    quality=studio_autonomous_quality_gate(final_review,calibration=calibration_status,multimodal_evidence=mm)
    repair_policy=request.get("autonomyPolicy") or {}; current_round=int(repair_policy.get("repairRound") or 0)

    if quality["status"] in {"REPAIR","FAIL_CLOSED"}:
        repair=build_repair_request(final_review,quality,round_number=current_round+1)
        _emit(progress,"AUTONOMOUS_REPAIR",{"round":repair["round"],"scope":repair["escalation_scope"]})
        code="P8_AUTONOMOUS_CREATIVE_REPAIR_REQUIRED" if quality["status"]=="REPAIR" else "P8_EVIDENCE_OR_SAFETY_RECOVERY_REQUIRED"
        return _result(sr,provider,"REVISE",code,story=story,final_board=final_board,extra={"finalReview":final_review,"autonomousQualityEvidence":quality,"repairRequest":repair,"studioTasteCalibration":calibration_status,"perceptualAudit":perceptual_audit,"judgeEnsembleHash":ensemble_hash,"multimodalEvidence":mm})

    try:
        token=sr.register_final_producer_review(final_review,final_board); sr.commit_final_producer(token,final_board)
    except ProducerGateError as error:
        repair=build_repair_request(final_review,quality,round_number=current_round+1)
        return _result(sr,provider,"REVISE","FINAL_PRODUCER_COMMIT_REPLAN_REQUIRED",story=story,final_board=final_board,extra={"detail":str(error),"finalReview":final_review,"repairRequest":repair,"autonomousQualityEvidence":quality,"studioTasteCalibration":calibration_status,"perceptualAudit":perceptual_audit,"judgeEnsembleHash":ensemble_hash,"multimodalEvidence":mm})

    human=request.get("humanReview"); human_gate=None; lock_mode=None
    if quality["status"]=="PASS":
        lock_mode="AUTONOMOUS_CALIBRATED"
    else:
        if not isinstance(human,dict):
            _emit(progress,"HUMAN_REVIEW_REQUIRED",{"calibration":calibration_status})
            code="P8_STUDIO_TASTE_CALIBRATION_NOT_YET_PROVEN" if quality["status"]=="HUMAN_CALIBRATION_REQUIRED" else "P8_EXCEPTIONAL_HUMAN_JUDGMENT_REQUIRED"
            return _result(sr,provider,"HUMAN_REVIEW_REQUIRED",code,story=story,final_board=final_board,extra={"finalReview":final_review,"autonomousQualityEvidence":quality,"studioTasteCalibration":calibration_status,"perceptualAudit":perceptual_audit,"judgeEnsembleHash":ensemble_hash,"multimodalEvidence":mm})
        human=validate_human_review(human); human_gate=sr.register_human_creative_review(human)
        if human_gate.get("status")!="PASS":
            repair=build_repair_request(final_review,quality,round_number=current_round+1)
            return _result(sr,provider,"REVISE","P8_HUMAN_REVIEW_GATE_REPLAN_REQUIRED",story=story,final_board=final_board,extra={"finalReview":final_review,"repairRequest":repair,"humanReviewGate":human_gate,"studioTasteCalibration":calibration_status,"perceptualAudit":perceptual_audit,"judgeEnsembleHash":ensemble_hash,"multimodalEvidence":mm})
        lock_mode="HUMAN_CALIBRATION_BRIDGE"
    try: lock=sr.creative_lock()
    except CreativeLockError as error:
        return _result(sr,provider,"REVISE","P8_CREATIVE_LOCK_RECOVERY_REQUIRED",story=story,final_board=final_board,extra={"detail":str(error),"finalReview":final_review,"autonomousQualityEvidence":quality,"humanReviewGate":human_gate,"studioTasteCalibration":calibration_status,"perceptualAudit":perceptual_audit,"judgeEnsembleHash":ensemble_hash,"multimodalEvidence":mm})
    _emit(progress,"CREATIVE_LOCKED",{"stateHash":lock.get("state_hash"),"lockMode":lock_mode})
    dossier=FinalProductionDossierCompiler().compile(final_board,final_review)
    code="CREATIVE_LOCK_COMMITTED_AUTONOMOUS_CALIBRATED" if lock_mode=="AUTONOMOUS_CALIBRATED" else "CREATIVE_LOCK_COMMITTED_WITH_MULTIMODAL_AND_HUMAN_EVIDENCE"
    return _result(sr,provider,"CREATIVE_LOCKED",code,story=story,final_board=final_board,dossier=dossier,extra={"creativeLock":lock,"creativeLockMode":lock_mode,"finalReview":final_review,"autonomousQualityEvidence":quality,"humanReviewGate":human_gate,"studioTasteCalibration":calibration_status,"perceptualAudit":perceptual_audit,"judgeEnsembleHash":ensemble_hash,"multimodalEvidence":mm})


def _provider_performance(provider) -> Dict[str, Any]:
    audits=provider.audit_dicts() if hasattr(provider,"audit_dicts") else []
    by_task={}
    total_latency=0; retries=0; failures=0; schema_repairs=0
    for item in audits:
        if not isinstance(item,dict): continue
        task=str(item.get("task") or "UNKNOWN")
        latency=int(item.get("duration_ms") or item.get("latency_ms") or 0); retry=int(item.get("retries") or 0); repairs=int(item.get("schema_repairs") or 0)
        failed=str(item.get("status") or "")!="PASS"
        total_latency+=latency; retries+=retry; schema_repairs+=repairs; failures+=1 if failed else 0
        rec=by_task.setdefault(task,{"calls":0,"latency_ms":0,"retries":0,"failures":0,"schema_repairs":0})
        rec["calls"]+=1; rec["latency_ms"]+=latency; rec["retries"]+=retry; rec["schema_repairs"]+=repairs; rec["failures"]+=1 if failed else 0
    return {
        "provider_call_count":len(audits),
        "provider_total_latency_ms":total_latency,
        "provider_retry_count":retries,
        "provider_failed_call_count":failures,
        "provider_schema_repair_count":schema_repairs,
        "by_task":by_task,
    }


def _result(sr, provider, status: str, code: str, *, story=None, final_board=None, dossier=None, extra=None) -> Dict[str, Any]:
    state_hash = sr.state_hash()
    result = {
        "schema": "StudioNexMindP8ResultV1",
        "status": status,
        "code": code,
        "productionId": sr.state["production_id"],
        "revision": sr.state["revision"],
        "stateHash": state_hash,
        "decisionSlots": sorted(sr.state.get("decisions", {}).keys()),
        "capabilityGraphHash": canonical_hash(sr.state.get("capability_graph", {})),
        "story": deepcopy(story),
        "finalBoard": deepcopy(final_board),
        "dossier": deepcopy(dossier),
        "checkpoint": {"schema": "NexMindSupremeShowrunnerCheckpointV1", "state": deepcopy(sr.state), "state_hash": state_hash},
        "providerAudits": provider.audit_dicts() if hasattr(provider, "audit_dicts") else [],
        "providerPerformance": _provider_performance(provider),
    }
    if extra:
        result.update(deepcopy(extra))
    return result


def classify_exception(error: Exception) -> Dict[str, Any]:
    text = str(error)
    if isinstance(error, ProviderError) and text.startswith("LIVE_PROVIDER_BLOCKED_"):
        # Preserve the precise recoverable configuration/capability boundary.
        # This is intentionally provider/model agnostic: callers can distinguish
        # missing runtime capability configuration from an actual provider call
        # failure without depending on any provider/model identity.
        return {"schema": "StudioNexMindP8ResultV1", "status": "PROVIDER_UNAVAILABLE", "code": text.split(":", 1)[0], "detail": text}
    if isinstance(error, ProviderError):
        return {"schema": "StudioNexMindP8ResultV1", "status": "PROVIDER_UNAVAILABLE", "code": "LIVE_PROVIDER_CALL_FAILED", "detail": text}
    if isinstance(error, ProducerGateError):
        return {"schema": "StudioNexMindP8ResultV1", "status": "REVISE", "code": "P8_PRODUCER_GATE_BLOCKED", "detail": text}
    return {"schema": "StudioNexMindP8ResultV1", "status": "BLOCKED", "code": type(error).__name__, "detail": text}
