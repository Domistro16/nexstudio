from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from contracts import AdapterBlocked, require_review_board
from canonical import stable

SCHEMA = "StudioCanonicalExecutionPlanV1"
COMPILER_ROLE = "DETERMINISTIC_EXECUTION_NORMALIZER"
CREATIVE_AUTHORITY = "NEXMIND_P8"

_SEMANTIC_KEYS = (
    "scene_thesis",
    "audience_state_change",
    "hero_identity",
    "opening_state",
    "hero_key_state",
    "critical_action_states",
    "settled_state",
    "settled_meaning_without_motion",
    "supporting_assets",
    "vo_span",
    "narration_mode",
    "narration_text",
    "narration_purpose",
    "shot_camera_intent",
    "continuity_in",
    "continuity_out",
    "motion_intent",
    "sound_intent",
    "capability_risks",
)
_RESERVED_BEAT_KEYS = set(_SEMANTIC_KEYS) | {
    "beat_id",
    "camera",
    "editorial",
    "motion_plan_status",
    "semantic_motion_request",
    "motion_actions",
    "sound_plan_status",
    "sound_events",
    "sound_summary",
}


def _clean_dict(value: Any) -> Dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _clean_list(value: Any) -> List[Any]:
    return deepcopy(value) if isinstance(value, list) else []


def compile_execution_plan(request: Dict[str, Any], board: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize the committed P8 board into the one family-engine input contract.

    This compiler is intentionally non-creative. It may copy, group and hash P8
    decisions, but it may not select a metaphor, visual strategy, performer,
    camera move, timing, sound event or substitute capability. Family-specific
    adapters receive only a compatibility projection compiled from this plan.
    """
    beats = require_review_board(board)
    family = str(request.get("family") or "").upper()
    if not family:
        raise AdapterBlocked("EXECUTION_PLAN_FAMILY_REQUIRED")

    out_beats: List[Dict[str, Any]] = []
    for beat in beats:
        semantic = {key: deepcopy(beat.get(key)) for key in _SEMANTIC_KEYS if key in beat}
        extensions = {
            key: deepcopy(value)
            for key, value in beat.items()
            if key not in _RESERVED_BEAT_KEYS
        }
        out_beats.append({
            "beatId": str(beat["beat_id"]),
            "semantic": semantic,
            "camera": _clean_dict(beat.get("camera")),
            "editorial": _clean_dict(beat.get("editorial")),
            "performance": {
                "status": str(beat.get("motion_plan_status") or ""),
                "semanticRequest": deepcopy(beat.get("semantic_motion_request")),
                "actions": _clean_list(beat.get("motion_actions")),
            },
            "sound": {
                "status": str(beat.get("sound_plan_status") or ""),
                "events": _clean_list(beat.get("sound_events")),
                "summary": _clean_dict(beat.get("sound_summary")),
            },
            "extensions": extensions,
            "presentFields": sorted(beat.keys()),
            "sourceBeatHash": stable(beat),
        })

    board_metadata = {
        key: deepcopy(value)
        for key, value in board.items()
        if key not in {"schema", "beats"}
    }
    plan: Dict[str, Any] = {
        "schema": SCHEMA,
        "productionId": str(request.get("productionId") or ""),
        "family": family,
        "durationSeconds": request.get("durationSeconds"),
        "aspectRatio": request.get("aspectRatio") or "16:9",
        "authority": {
            "creativeAuthority": CREATIVE_AUTHORITY,
            "compilerRole": COMPILER_ROLE,
            "creativeChoiceIntroduced": False,
            "sourceFinalBoardSchema": board.get("schema"),
            "sourceFinalBoardHash": stable(board),
            "creativeStateArtifactId": request.get("creativeStateArtifactId"),
            "creativeStateArtifactHash": request.get("creativeStateArtifactHash"),
        },
        "boardMetadata": board_metadata,
        "brandExecution": deepcopy(request.get("brandExecution") or {}),
        "beats": out_beats,
    }
    plan["executionPlanHash"] = stable({k: v for k, v in plan.items() if k != "executionPlanHash"})
    return plan


def validate_execution_plan(plan: Dict[str, Any]) -> None:
    if not isinstance(plan, dict) or plan.get("schema") != SCHEMA:
        raise AdapterBlocked("EXECUTION_PLAN_SCHEMA_INVALID")
    auth = plan.get("authority") if isinstance(plan.get("authority"), dict) else {}
    if auth.get("creativeAuthority") != CREATIVE_AUTHORITY:
        raise AdapterBlocked("EXECUTION_PLAN_CREATIVE_AUTHORITY_INVALID")
    if auth.get("compilerRole") != COMPILER_ROLE or auth.get("creativeChoiceIntroduced") is not False:
        raise AdapterBlocked("EXECUTION_PLAN_COMPILER_AUTHORITY_INVALID")
    brand=plan.get("brandExecution") if isinstance(plan.get("brandExecution"),dict) else {}
    if brand.get("schema")!="StudioBrandExecutionV1" or not brand.get("memoryInputSnapshotId") or not brand.get("memoryInputSnapshotHash") or not brand.get("brandExecutionHash"):
        raise AdapterBlocked("EXECUTION_PLAN_BRAND_AUTHORITY_MISSING")
    beats = plan.get("beats")
    if not isinstance(beats, list) or not beats:
        raise AdapterBlocked("EXECUTION_PLAN_EMPTY")
    for beat in beats:
        if not isinstance(beat, dict) or not beat.get("beatId"):
            raise AdapterBlocked("EXECUTION_PLAN_BEAT_INVALID")
        perf = beat.get("performance") if isinstance(beat.get("performance"), dict) else {}
        sound = beat.get("sound") if isinstance(beat.get("sound"), dict) else {}
        if perf.get("status") != "DIRECTED_MOTION_PERFORMANCE" or sound.get("status") != "DIRECTED_SOUND":
            raise AdapterBlocked("EXECUTION_PLAN_DEPARTMENTS_UNRESOLVED", str(beat.get("beatId")))
    expected = stable({k: v for k, v in plan.items() if k != "executionPlanHash"})
    if plan.get("executionPlanHash") != expected:
        raise AdapterBlocked("EXECUTION_PLAN_HASH_INVALID")


def compatibility_board(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Create a transitional P8-board-shaped view from the canonical plan.

    This exists only so certified legacy renderer ports can migrate incrementally.
    It contains no creative decisions that are not already committed in the plan.
    """
    validate_execution_plan(plan)
    out: Dict[str, Any] = {
        "schema": "NexMindCanonicalSoundStoryboardV4",
        **deepcopy(plan.get("boardMetadata") or {}),
        "beats": [],
    }
    for beat in plan["beats"]:
        semantic = deepcopy(beat.get("semantic") or {})
        perf = beat.get("performance") or {}
        sound = beat.get("sound") or {}
        present=set(beat.get("presentFields") or [])
        rebuilt = {"beat_id": beat["beatId"], **semantic, **deepcopy(beat.get("extensions") or {})}
        candidates={
            "camera": deepcopy(beat.get("camera") or {}),
            "editorial": deepcopy(beat.get("editorial") or {}),
            "motion_plan_status": perf.get("status"),
            "semantic_motion_request": deepcopy(perf.get("semanticRequest")),
            "motion_actions": deepcopy(perf.get("actions") or []),
            "sound_plan_status": sound.get("status"),
            "sound_events": deepcopy(sound.get("events") or []),
            "sound_summary": deepcopy(sound.get("summary") or {}),
        }
        for key,value in candidates.items():
            if key in present: rebuilt[key]=value
        if stable(rebuilt) != beat.get("sourceBeatHash"):
            raise AdapterBlocked("EXECUTION_PLAN_COMPATIBILITY_ROUNDTRIP_FAILED", str(beat.get("beatId")))
        out["beats"].append(rebuilt)
    if stable(out) != (plan.get("authority") or {}).get("sourceFinalBoardHash"):
        raise AdapterBlocked("EXECUTION_PLAN_FINAL_BOARD_ROUNDTRIP_FAILED")
    return out
