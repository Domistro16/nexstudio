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
from nexmind_god_mode.storyboard_compiler import StoryboardCompiler
from nexmind_god_mode.storyboard_compiler_v2 import TemporalStoryboardCompiler
from nexmind_god_mode.storyboard_compiler_v3 import PerformanceStoryboardCompiler
from nexmind_god_mode.storyboard_compiler_v4 import SoundStoryboardCompiler
from nexmind_god_mode.visual_concept_director import VisualConceptDirector
from nexmind_god_mode.p0_kernel import CreativeLockError
from nexmind_god_mode.contracts import ContractViolation
from nexmind_god_mode.showrunner_p2 import ProducerGateError

from capability_adapter import build_capability_graph, load_current_capability_packet

Progress = Optional[Callable[[str, Dict[str, Any]], None]]


DEFAULT_CREATIVE_HARD_CEILING = 6
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
    _schedule_repair(
        sr,
        department,
        f"{department} Director output contract requires autonomous repair",
        _contract_repair_context(error, department),
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
        "ledger": [],
    })
    state["attempt_limits_by_department"] = deepcopy(limits)
    state.pop("max_attempts_per_department",None)
    state.setdefault("attempts", {})
    state.setdefault("lifetime_attempts", {})
    state.setdefault("lineage_resets", [])
    state.setdefault("ledger", [])
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


def _reviews_context(reviewed: list[Dict[str, Any]]) -> Dict[str, Any]:
    issues = []
    strengths = []
    briefs = []
    verdicts = []
    rejected = []
    for item in reviewed:
        review = item.get("review") or {}
        verdicts.append(str(review.get("verdict") or ""))
        issues.extend(deepcopy(review.get("issues") or []))
        strengths.extend(str(x) for x in (review.get("strengths") or []) if str(x).strip())
        rb = str(review.get("revision_brief") or "").strip()
        if rb and rb not in briefs:
            briefs.append(rb)
        rejected.append({
            "verdict": review.get("verdict"),
            "candidate": _candidate_summary(item.get("candidate")),
        })
    # Keep ordering but remove duplicate strength strings.
    seen = set()
    strengths = [x for x in strengths if not (x in seen or seen.add(x))]
    return {
        "issues": issues,
        "strengths_to_preserve": strengths,
        "revision_briefs": briefs,
        "producer_verdicts": verdicts,
        "rejected_candidates": rejected,
    }


def _schedule_repair(sr: NexMindSupremeShowrunnerP8, department: str, reason: str, context: Dict[str, Any]) -> Dict[str, Any]:
    repair = sr.state["autonomous_creative_repair"]
    attempts = int(repair["attempts"].get(department, 0))
    maximum = _department_attempt_limit(sr,department)
    if attempts >= maximum:
        raise CreativeRepairBudgetExhausted(department, attempts, maximum, reason=reason, context=context)
    invalidated = list(DEPARTMENT_INVALIDATION[department])
    preserved = sorted(k for k in sr.state.get("decisions", {}) if k not in invalidated)
    from_revision = int(sr.state.get("revision", 0))
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
        "requirements": [
            "Resolve every material Producer issue; do not merely paraphrase the rejected work.",
            "Preserve the listed strengths and every upstream decision slot not invalidated by this repair.",
            "Do not lower the quality gate or substitute a generic/simpler treatment just to obtain ACCEPT.",
            "Produce a materially improved creative answer that can be independently re-reviewed.",
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
    text = json.dumps({"issues": review.get("issues") or [], "revision_brief": review.get("revision_brief") or ""}, ensure_ascii=False).lower()
    hints = [
        ("STORY", ("story", "thesis", "audience", "beat", "narrative", "payoff", "protagonist", "human priority")),
        ("VISUAL_CONCEPT", ("visual concept", "visual strategy", "hero", "transformation", "generic", "representation")),
        ("ART_DIRECTION", ("art", "composition", "hierarchy", "illustration", "key state", "settled state", "form")),
        ("CINEMATOGRAPHY", ("camera", "cinema", "shot", "framing", "lens", "coverage")),
        ("EDITORIAL_RHYTHM", ("editorial", "rhythm", "timing", "pacing", "duration", "continuity")),
        ("MOTION_PERFORMANCE", ("motion", "performance", "contact", "physical", "gesture", "capability")),
        ("SOUND_DIRECTION", ("sound", "music", "audio", "foley", "mix", "narration")),
    ]
    allowed = allowed or set(DEPARTMENT_ORDER)
    for department, words in hints:
        if department in allowed and any(word in text for word in words):
            return department
    return default if default in allowed else next(iter(allowed))


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


def run_full_p8(request: Dict[str, Any], *, provider=None, progress: Progress = None) -> Dict[str, Any]:
    production_id = str(request.get("productionId") or "")
    if not production_id:
        raise ValueError("productionId is required")
    duration = max(1, min(60, int(request.get("durationSeconds") or 60)))
    brief = _brief(request)
    evidence = _evidence(request)
    packet = load_current_capability_packet()
    capability_graph = build_capability_graph(request, packet)
    provider = provider or LiveCreativeModelProvider()
    _emit(progress, "CAPABILITY_GRAPH_VALIDATED", {"familyExecutionAuthority": capability_graph["current_authorities"].get("family_execution_body", {}), "capabilityGraphSchema": capability_graph.get("schema"), "creativeRepairPolicy": "ADAPTIVE_BOUNDED_ESCALATION"})
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
    try:
        while True:
            # STORY — adaptive brief-specific materially different narrative strategies + independent Producer review + Showrunner selection.
            if "film_thesis" not in sr.state["decisions"]:
                while "film_thesis" not in sr.state["decisions"]:
                    attempt = _reserve_attempt(sr, "STORY")
                    _emit(progress, "STORY", {"attempt": attempt, "maximum": _department_attempt_limit(sr,"STORY"), "repair": attempt > 1})
                    try:
                        story_result = p2.develop_story_competition(evidence)
                    except ContractViolation as error:
                        _schedule_director_contract_repair(sr, "STORY", error)
                        continue
                    story = story_result.get("story")
                    if "film_thesis" in sr.state["decisions"] and story:
                        _clear_repair_context(sr, "STORY")
                        break
                    _schedule_repair(sr, "STORY", "No Producer-accepted Story candidate", _reviews_context(story_result.get("reviews") or []))
            else:
                story = _committed_payload(sr, "film_thesis")

            # VISUAL CONCEPT — regenerate a materially new candidate set if none is Producer-accepted.
            if "visual_concept" not in sr.state["decisions"]:
                while "visual_concept" not in sr.state["decisions"]:
                    attempt = _reserve_attempt(sr, "VISUAL_CONCEPT")
                    _emit(progress, "VISUAL_CONCEPT", {"attempt": attempt, "maximum": _department_attempt_limit(sr,"VISUAL_CONCEPT"), "repair": attempt > 1})
                    try:
                        visual_result = p2.develop_visual_candidates(story)
                    except ContractViolation as error:
                        _schedule_director_contract_repair(sr, "VISUAL_CONCEPT", error)
                        continue
                    accepted = [x for x in visual_result["reviews"] if x["review"]["verdict"] == "ACCEPT"]
                    if accepted:
                        selected_visual = p2.showrunner_select_visual(story, visual_result)
                        visual = selected_visual["committed"]["payload"]
                        _clear_repair_context(sr, "VISUAL_CONCEPT")
                        break
                    _schedule_repair(sr, "VISUAL_CONCEPT", "No Producer-accepted Visual Concept candidate", _reviews_context(visual_result["reviews"]))
            else:
                visual = _committed_payload(sr, "visual_concept")

            # ART DIRECTION.
            if "art_direction" not in sr.state["decisions"]:
                while "art_direction" not in sr.state["decisions"]:
                    attempt = _reserve_attempt(sr, "ART_DIRECTION")
                    _emit(progress, "ART_DIRECTION", {"attempt": attempt, "maximum": _department_attempt_limit(sr,"ART_DIRECTION"), "repair": attempt > 1})
                    try:
                        art_result = p3.develop_art(story, visual)
                    except ContractViolation as error:
                        _schedule_director_contract_repair(sr, "ART_DIRECTION", error)
                        continue
                    accepted = [x for x in art_result["reviewed"] if x["review"]["verdict"] == "ACCEPT"]
                    if accepted:
                        selected_art = p3.select_art(story, visual, art_result)
                        art = selected_art["candidate"]
                        art_form = selected_art["form_resolution"]
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
                _emit(progress, "STORYBOARD", {"revision": sr.state["revision"]})
                key_board_result = p3.compile_and_review_storyboard(story, visual, selected_art)
                key_board = key_board_result["board"]
                if "storyboard" not in sr.state["decisions"]:
                    owner = _review_owner(key_board_result["review"], "ART_DIRECTION", {"STORY", "VISUAL_CONCEPT", "ART_DIRECTION"})
                    _schedule_repair(sr, owner, "Key-state storyboard review requested upstream repair", _review_context(key_board_result["review"], previous={"storyboard_hash": canonical_hash(key_board)}))
                    continue
            else:
                sb_payload = _decision_payload(sr, "storyboard")
                key_board = deepcopy(sb_payload.get("storyboard") or sb_payload)

            # CINEMATOGRAPHY.
            if "cinematography" not in sr.state["decisions"]:
                while "cinematography" not in sr.state["decisions"]:
                    attempt = _reserve_attempt(sr, "CINEMATOGRAPHY")
                    _emit(progress, "CINEMATOGRAPHY", {"attempt": attempt, "maximum": _department_attempt_limit(sr,"CINEMATOGRAPHY"), "repair": attempt > 1})
                    try:
                        cinema_result = p45.develop_cinema(story, visual, art, key_board)
                    except ContractViolation as error:
                        _schedule_director_contract_repair(sr, "CINEMATOGRAPHY", error)
                        continue
                    accepted = [x for x in cinema_result["reviewed"] if x["review"]["verdict"] == "ACCEPT"]
                    if accepted:
                        cinema_item = p45.select_cinema(story, cinema_result)
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
                    attempt = _reserve_attempt(sr, "EDITORIAL_RHYTHM")
                    _emit(progress, "EDITORIAL_RHYTHM", {"attempt": attempt, "maximum": _department_attempt_limit(sr,"EDITORIAL_RHYTHM"), "repair": attempt > 1})
                    try:
                        editorial_result = p45.develop_editorial(story, visual, art, cinema, target_duration_frames=duration * 30, project_rate=30)
                    except ContractViolation as error:
                        _schedule_director_contract_repair(sr, "EDITORIAL_RHYTHM", error)
                        continue
                    accepted = [x for x in editorial_result["reviewed"] if x["review"]["verdict"] == "ACCEPT"]
                    if accepted:
                        editorial_item = p45.select_editorial(story, editorial_result)
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
                temporal = p45.compile_temporal_storyboard(story, key_board, cinema_item, editorial_item)
                temporal_board = temporal["board"]
                if "storyboard_temporal" not in sr.state["decisions"]:
                    owner = _review_owner(temporal["review"], "EDITORIAL_RHYTHM", {"CINEMATOGRAPHY", "EDITORIAL_RHYTHM"})
                    _schedule_repair(sr, owner, "Temporal storyboard review requested upstream repair", _review_context(temporal["review"], previous={"storyboard_temporal_hash": canonical_hash(temporal_board)}))
                    continue
            else:
                temporal_payload = _decision_payload(sr, "storyboard_temporal")
                temporal_board = deepcopy(temporal_payload.get("storyboard_temporal") or temporal_payload)

            # MOTION / PERFORMANCE — capability gaps are first offered a bounded safe rewrite.
            if "motion_performance" not in sr.state["decisions"]:
                while "motion_performance" not in sr.state["decisions"]:
                    attempt = _reserve_attempt(sr, "MOTION_PERFORMANCE")
                    _emit(progress, "MOTION_PERFORMANCE", {"attempt": attempt, "maximum": _department_attempt_limit(sr,"MOTION_PERFORMANCE"), "repair": attempt > 1})
                    try:
                        motion_result = p6.develop(story, visual, art, cinema, editorial, temporal_board)
                    except ContractViolation as error:
                        _schedule_director_contract_repair(sr, "MOTION_PERFORMANCE", error)
                        continue
                    eligible = [x for x in motion_result["reviewed"] if x["review"]["verdict"] == "ACCEPT" and x["candidate"].get("executable", False)]
                    if eligible:
                        motion_item = p6.select(story, motion_result)
                        motion = motion_item["candidate"]
                        _clear_repair_context(sr, "MOTION_PERFORMANCE")
                        break
                    _schedule_repair(sr, "MOTION_PERFORMANCE", "No Producer-accepted executable Motion/Performance candidate", _reviews_context(motion_result["reviewed"]))
            else:
                motion = _committed_payload(sr, "motion_performance")
                motion_item = {"candidate": motion}
            performance = p6.compile_performance_storyboard(temporal_board, motion_item)

            # SOUND.
            if "sound_direction" not in sr.state["decisions"]:
                while "sound_direction" not in sr.state["decisions"]:
                    attempt = _reserve_attempt(sr, "SOUND_DIRECTION")
                    _emit(progress, "SOUND_DIRECTION", {"attempt": attempt, "maximum": _department_attempt_limit(sr,"SOUND_DIRECTION"), "repair": attempt > 1})
                    try:
                        sound_result = p7.develop(story, editorial, motion, performance["board"])
                    except ContractViolation as error:
                        _schedule_director_contract_repair(sr, "SOUND_DIRECTION", error)
                        continue
                    accepted = [x for x in sound_result["reviewed"] if x["review"]["verdict"] == "ACCEPT"]
                    if accepted:
                        sound_item = p7.select(story, sound_result)
                        sound = sound_item["candidate"]
                        _clear_repair_context(sr, "SOUND_DIRECTION")
                        break
                    _schedule_repair(sr, "SOUND_DIRECTION", "No Producer-accepted Sound Direction candidate", _reviews_context(sound_result["reviewed"]))
            else:
                sound = _committed_payload(sr, "sound_direction")
                sound_item = {"candidate": sound}
            final_board = p7.compile_sound_storyboard(performance["board"], sound_item)["board"]

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
                },
            )
    except CreativeRepairBudgetExhausted as error:
        # Local bounded repair exhausted. Escalate the creative scope; do not
        # convert a valid paid production into a terminal product failure.
        escalation_owner={
            "STORY":"STORY", "VISUAL_CONCEPT":"STORY", "ART_DIRECTION":"VISUAL_CONCEPT",
            "CINEMATOGRAPHY":"VISUAL_CONCEPT", "EDITORIAL_RHYTHM":"STORY",
            "MOTION_PERFORMANCE":"VISUAL_CONCEPT", "SOUND_DIRECTION":"EDITORIAL_RHYTHM",
        }.get(error.department,"VISUAL_CONCEPT")
        prior=request.get("autonomousRepairContext") or {}
        repair_request={
            "schema":"StudioAutonomousCreativeRepairRequestV2",
            "round":int(prior.get("round") or 0)+1 if isinstance(prior,dict) else 1,
            "escalation_scope":"BROADER_CREATIVE_STRATEGY",
            "owner_department":escalation_owner,
            "source_department":error.department,
            "invalidate_slots":deepcopy(DEPARTMENT_INVALIDATION.get(escalation_owner,["visual_concept","art_direction","cinematography","editorial_rhythm","motion_performance","sound_direction"])),
            "issues":deepcopy(error.context.get("issues") or []) if isinstance(error.context,dict) else [],
            "revision_plan":deepcopy(error.context.get("revision_briefs") or []) if isinstance(error.context,dict) else [],
            "quality_reasons":["LOCAL_CREATIVE_LINEAGE_EXHAUSTED",str(error.reason or "")],
            "production_disposition":"CONTINUE_REPLANNING",
            "quality_floor_may_weaken":False,
            "silent_generic_fallback_allowed":False,
            "law":"LOCAL_IDEA_MAY_FAIL__PAID_PRODUCTION_REPLANS__NEVER_LOWER_QUALITY_GATE",
        }
        _emit(progress,"BROADER_STRATEGY_REPLAN",{"department":error.department,"ownerDepartment":escalation_owner,"attempts":error.attempts})
        return _result(sr,provider,"REVISE","P8_BROADER_STRATEGY_REPLAN_REQUIRED",story=story,final_board=final_board,extra={
            "department":error.department,"attempts":error.attempts,"maxAttempts":error.maximum,
            "repairRequest":repair_request,"autonomousRepair":deepcopy(sr.state.get("autonomous_creative_repair")),
            "qualityOverrideAllowed":False,"customerVisibleFailure":False,
        })


def _resolved_task_audit(provider, task: str) -> Dict[str, Any] | None:
    audits=provider.audit_dicts() if hasattr(provider,"audit_dicts") else []
    for item in reversed(audits):
        if isinstance(item,dict) and item.get("task")==task and item.get("status")=="PASS": return item
    return None

def _judge_ensemble_hash(provider) -> str | None:
    fp=_resolved_task_audit(provider,"final_producer"); pa=_resolved_task_audit(provider,"perceptual_auditor")
    if not fp or not pa: return None
    identities=[f"{fp.get('provider')}:{fp.get('resolved_model') or fp.get('model')}",f"{pa.get('provider')}:{pa.get('resolved_model') or pa.get('model')}"]
    if identities[0]==identities[1]: raise ProviderError("P8_JUDGE_MODEL_INDEPENDENCE_VIOLATION")
    upstream=[]
    for item in provider.audit_dicts() if hasattr(provider,"audit_dicts") else []:
        if not isinstance(item,dict) or item.get("status")!="PASS" or item.get("task") in {"final_producer","perceptual_auditor"}: continue
        upstream.append(f"{item.get('provider')}:{item.get('resolved_model') or item.get('model')}")
    if identities[0] in upstream or identities[1] in upstream: raise ProviderError("P8_AUTHOR_REVIEWER_MODEL_INDEPENDENCE_VIOLATION")
    return hashlib.sha256(json.dumps(sorted(identities),separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

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
    try: ensemble_hash=_judge_ensemble_hash(provider)
    except ProviderError as error:
        return _result(sr,provider,"REVISE","P8_JUDGE_INDEPENDENCE_RECOVERY_REQUIRED",story=story,final_board=final_board,extra={"detail":str(error),"finalReview":final_review,"perceptualAudit":perceptual_audit,"multimodalEvidence":mm})
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
