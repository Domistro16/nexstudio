from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List

ALLOWED_FAMILIES={"EXPLAINER","WHITEBOARD","STICKMAN","EDITORIAL_MOTION"}

class AdapterBlocked(RuntimeError):
    def __init__(self, code:str, detail:str=""):
        super().__init__(detail or code); self.code=code; self.detail=detail or code

class AdapterReplan(RuntimeError):
    def __init__(self, code:str, detail:str="", repair_request:Dict[str,Any]|None=None):
        super().__init__(detail or code); self.code=code; self.detail=detail or code; self.repair_request=repair_request or {}

def require_review_board(board:Dict[str,Any])->List[Dict[str,Any]]:
    if not isinstance(board,dict) or board.get("schema")!="NexMindCanonicalSoundStoryboardV4":
        raise AdapterBlocked("P8_FINAL_BOARD_SCHEMA_UNSUPPORTED","Expected NexMindCanonicalSoundStoryboardV4.")
    beats=board.get("beats")
    if not isinstance(beats,list) or not beats:
        raise AdapterBlocked("P8_FINAL_BOARD_EMPTY","The P8 final board has no beats.")
    for beat in beats:
        if not isinstance(beat,dict) or not beat.get("beat_id"):
            raise AdapterBlocked("P8_FINAL_BOARD_BEAT_INVALID","Every P8 beat needs a stable beat_id.")
        if beat.get("motion_plan_status")!="DIRECTED_MOTION_PERFORMANCE" or beat.get("sound_plan_status")!="DIRECTED_SOUND":
            raise AdapterBlocked("P8_FINAL_BOARD_DEPARTMENTS_UNRESOLVED",f"Beat {beat.get('beat_id')} is not fully motion/sound directed.")
    return beats

def rational_seconds(value:Any, fallback:float)->float:
    if isinstance(value,dict):
        v=value.get("value"); r=value.get("rate")
        if isinstance(v,(int,float)) and isinstance(r,(int,float)) and r>0: return max(.25,float(v)/float(r))
    return max(.25,float(fallback))


def creative_replan_request(
    *,
    escalation_scope:str,
    invalidate_slots:List[str],
    issue:str,
    revision_plan:str,
    quality_reason:str,
    constraints:List[str]|None=None,
)->Dict[str,Any]:
    """Build the family-body -> NexMind recovery contract.

    Family bodies may reject a realization, never the paid production.  This
    request preserves the brief/Film Thesis, raises the problem to the creative
    owner able to change strategy, and explicitly forbids quality-floor
    weakening or generic substitution.
    """
    return {
        "escalation_scope": escalation_scope,
        "invalidate_slots": list(invalidate_slots),
        "issues": [issue],
        "revision_plan": [revision_plan],
        "quality_reasons": [quality_reason],
        "execution_constraints": list(constraints or []),
        "preserve": ["film_thesis","factual_intent","user_requested_family","brand_and_source_truth"],
        "production_disposition": "CONTINUE_REPLANNING",
        "quality_floor_may_weaken": False,
        "silent_generic_fallback_allowed": False,
    }
