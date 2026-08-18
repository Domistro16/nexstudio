from __future__ import annotations
from copy import deepcopy
from typing import Any, Dict, List, Set
from .contracts import ContractViolation, reject_geometry_code_authority, require_exact_keys, assert_semantic_candidate_diversity

SHOT_IDIOMS={
    "HERO_ESTABLISH","STATIC_TABLEAU","REVEAL_SUPPORT","COMPONENT_INSPECT",
    "COMPONENT_DIVE_IN","TRACK_TRANSFORMATION","COMPARE_SPLIT","CAUSE_EFFECT_FOLLOW",
    "HANDOFF_CONTACT","CONSEQUENCE_PULLBACK","SYNTHESIS_PULLBACK"
}
SHOT_SCALES={"EXTREME_WIDE","WIDE","MEDIUM_WIDE","MEDIUM","MEDIUM_CLOSE","CLOSE","MACRO"}
ANGLES={"EYE_LEVEL","HIGH","LOW","TOP_DOWN","THREE_QUARTER","PROFILE","FRONTAL"}
CAMERA_ATOMS={"HOLD","REFRAME","PUSH_IN","PULL_BACK","PAN","TILT","TRACK","ARC","FOLLOW"}
DEPTH={"FLAT","LAYERED","SHALLOW_FOCUS","DEEP_FOCUS","MACRO_DEPTH"}
TRANSITION_REL={"HOLD_CONTINUITY","MATCH_POSITION","MATCH_ACTION","CUT_ON_REVEAL","CARRY_MOTION","HARD_CUT","DISSOLVE_MOTIVATED"}

BAD_MOTIVATIONS={"because new beat","new beat","for energy","make it dynamic","keep it interesting","cinematic"}


def validate_camera_atom(a:Dict[str,Any], beat_id:str)->Dict[str,Any]:
    reject_geometry_code_authority(a)
    require_exact_keys(a,{"atom","target","motivation","intensity","start_semantic_state","end_semantic_state"},label=f"camera_atom:{beat_id}")
    if a["atom"] not in CAMERA_ATOMS: raise ContractViolation(f"invalid camera atom {a['atom']}")
    if not str(a["target"]).strip(): raise ContractViolation("camera target required")
    if a["intensity"] not in {"NONE","SUBTLE","MODERATE","STRONG"}: raise ContractViolation("invalid camera intensity")
    mot=str(a["motivation"]).strip().lower()
    if a["atom"]!="HOLD" and (not mot or mot in BAD_MOTIVATIONS):
        raise ContractViolation("camera movement requires semantic motivation")
    if a["atom"]=="HOLD" and a["intensity"]!="NONE": raise ContractViolation("HOLD must have NONE intensity")
    return deepcopy(a)


def validate_cinema_candidate(c:Dict[str,Any], beat_ids:Set[str], art_hero:str)->Dict[str,Any]:
    reject_geometry_code_authority(c)
    require_exact_keys(c,{"candidate_id","cinema_thesis","attention_strategy","shots","global_rules","risk_notes"},label="cinema_candidate")
    if not str(c["cinema_thesis"]).strip() or not str(c["attention_strategy"]).strip(): raise ContractViolation("cinema thesis/attention strategy required")
    if not isinstance(c["global_rules"],list) or not isinstance(c["risk_notes"],list): raise ContractViolation("cinema arrays required")
    shots=c["shots"]
    if not isinstance(shots,list) or not shots: raise ContractViolation("cinema requires authored shots")
    if len(shots)!=len(beat_ids): raise ContractViolation("cinematography execution body requires exactly one shot binding per story beat")
    seen=set(); move_count=0; hold_count=0
    for s in shots:
        require_exact_keys(s,{"beat_id","idiom","shot_scale","angle","subject_target","reveal_framing","depth_strategy","camera_atom","transition_relation","attention_anchor","continuity_reason"},label="cinema_shot")
        bid=s["beat_id"]
        if bid not in beat_ids: raise ContractViolation("cinema beat coverage mismatch")
        if bid in seen: raise ContractViolation("cinematography execution body supports exactly one shot binding per story beat")
        seen.add(bid)
        for field in ("idiom","shot_scale","angle","depth_strategy","transition_relation"):
            if not isinstance(s.get(field),str) or not s[field].strip(): raise ContractViolation(f"cinema {field} must be descriptive")
        if not str(s["subject_target"]).strip() or not str(s["attention_anchor"]).strip(): raise ContractViolation("cinema target/attention anchor required")
        atom=validate_camera_atom(s["camera_atom"],bid)
        if atom["atom"]=="HOLD": hold_count+=1
        else: move_count+=1
        if not str(s["continuity_reason"]).strip(): raise ContractViolation("continuity_reason required")
    if seen!=beat_ids: raise ContractViolation("cinema missing beats")
    # Camera movement is allowed, but a film that moves on every beat must explicitly justify why.
    if len(shots)>=3 and move_count==len(shots) and "continuous_camera_is_story" not in c["global_rules"]:
        raise ContractViolation("camera moves on every beat without explicit continuous-camera story rule")
    return deepcopy(c)


def _strategy_fingerprint(c:Dict[str,Any]):
    return tuple((s["idiom"],s["shot_scale"],s["angle"],s["camera_atom"]["atom"],s["transition_relation"]) for s in c["shots"])


def validate_cinema_output(payload:Dict[str,Any], beat_ids:Set[str], art_hero:str, *, repair_mode:bool=False)->List[Dict[str,Any]]:
    reject_geometry_code_authority(payload)
    require_exact_keys(payload,{"candidates"},{"director_notes"},label="cinema_output")
    cs=payload["candidates"]
    if not isinstance(cs,list): raise ContractViolation("cinema candidates must be an array")
    if repair_mode:
        if len(cs)!=1: raise ContractViolation("cinematography surgical repair must return exactly one candidate")
    elif len(cs)<2: raise ContractViolation("cinema requires genuine candidate competition")
    out=[]; ids=set(); fps=set()
    for c in cs:
        v=validate_cinema_candidate(c,beat_ids,art_hero)
        if v["candidate_id"] in ids: raise ContractViolation("duplicate cinema candidate id")
        ids.add(v["candidate_id"]); fps.add(_strategy_fingerprint(v)); out.append(v)
    if not repair_mode:
        if len(fps)<2: raise ContractViolation("cinema candidates are not materially different")
        assert_semantic_candidate_diversity(out,label="cinema_contracts candidates")
    return out
