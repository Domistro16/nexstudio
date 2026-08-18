from __future__ import annotations
from copy import deepcopy
from typing import Any, Dict, List, Set
from .contracts import ContractViolation, reject_geometry_code_authority, require_exact_keys, assert_semantic_candidate_diversity

DENSITY={"SPARSE","BALANCED","RICH"}
SPATIAL_MODE={"FLAT_CANVAS","GROUNDED_SCENE","PRODUCT_STAGE","INFORMATION_SPACE"}
DEPTH_MODE={"FLAT","LAYERED","DEEP"}
HERO_SCALE={"DOMINANT_CLOSE","LARGE","MEDIUM"}
ENVIRONMENT_DENSITY={"MINIMAL","CONTEXTUAL","LIVED_IN"}
OVERLAP_MODE={"NONE","HERO_SUPPORT","PURPOSEFUL_FOREGROUND"}
TYPOGRAPHY_MODE={"EMBEDDED","SUPPORT","HERO"}
PROMINENCE={"DOMINANT","PRIMARY","SECONDARY"}
ART_BUDGET={"HIGH","MEDIUM","LOW"}


def validate_form_request(obj:Dict[str,Any])->Dict[str,Any]:
    reject_geometry_code_authority(obj)
    require_exact_keys(obj,{"concept","representation","semantic_parts","required_operations","style"},{"notes"},label="form_request")
    if not isinstance(obj["representation"],str) or not obj["representation"].strip(): raise ContractViolation("form representation required")
    if not isinstance(obj["semantic_parts"],list) or not isinstance(obj["required_operations"],list): raise ContractViolation("form_request arrays required")
    return deepcopy(obj)


def validate_art_candidate(c:Dict[str,Any], beat_ids:Set[str], visual_candidate_id:str)->Dict[str,Any]:
    reject_geometry_code_authority(c)
    require_exact_keys(c,{"candidate_id","visual_candidate_id","art_thesis","hero","composition","form_request","beat_art","typography_intent","risk_notes"},{"art_bible"},label="art_candidate")
    if c["visual_candidate_id"]!=visual_candidate_id: raise ContractViolation("art candidate targets wrong visual candidate")
    if not str(c["art_thesis"]).strip(): raise ContractViolation("art_thesis required")
    premium_contract="art_bible" in c
    if premium_contract:
        bible=c["art_bible"]
        require_exact_keys(bible,{"shape_language","line_edge_language","palette_relationship","material_texture_language","lighting_value_structure","depth_language","environment_language","prop_language","character_language","typography_relationship","continuity_rules"},label="art.art_bible")
        for key,value in bible.items():
            if key=="continuity_rules":
                if not isinstance(value,list) or len(value)<2 or not all(isinstance(x,str) and x.strip() for x in value): raise ContractViolation("art bible requires at least two continuity rules")
            elif not isinstance(value,str) or not value.strip(): raise ContractViolation(f"art bible {key} required")
    h=c["hero"]; require_exact_keys(h,{"semantic_ref","art_budget","prominence","recognizable_required"},label="art.hero")
    if h["art_budget"] not in ART_BUDGET or h["prominence"] not in PROMINENCE: raise ContractViolation("invalid hero art fields")
    if h["recognizable_required"] and h["art_budget"]!="HIGH": raise ContractViolation("recognizable hero requires HIGH art budget")
    comp=c["composition"]; require_exact_keys(comp,{"archetype","hierarchy_order","negative_space_intent","density","asymmetry_intent","support_budget","decoration_budget"},{"foreground_strategy","midground_strategy","background_strategy","scale_contrast_intent","overlap_intent","execution_directives"},label="art.composition")
    if comp["density"] not in DENSITY: raise ContractViolation("invalid density")
    if int(comp["support_budget"]) < 0: raise ContractViolation("support budget must be nonnegative")
    if int(comp["decoration_budget"]) < 0: raise ContractViolation("decoration budget must be nonnegative")
    if not isinstance(comp["hierarchy_order"],list) or not comp["hierarchy_order"]: raise ContractViolation("hierarchy_order required")
    if premium_contract:
        for key in ("foreground_strategy","midground_strategy","background_strategy","scale_contrast_intent","overlap_intent"):
            if not isinstance(comp.get(key),str) or not comp[key].strip(): raise ContractViolation(f"premium composition missing {key}")
        directives=comp.get("execution_directives")
        if not isinstance(directives,dict): raise ContractViolation("premium composition missing execution_directives")
        require_exact_keys(directives,{"spatial_mode","depth_mode","hero_scale","environment_density","overlap_mode","typography_mode"},label="art.composition.execution_directives")
        if directives["spatial_mode"] not in SPATIAL_MODE: raise ContractViolation("invalid spatial_mode")
        if directives["depth_mode"] not in DEPTH_MODE: raise ContractViolation("invalid depth_mode")
        if directives["hero_scale"] not in HERO_SCALE: raise ContractViolation("invalid hero_scale")
        if directives["environment_density"] not in ENVIRONMENT_DENSITY: raise ContractViolation("invalid environment_density")
        if directives["overlap_mode"] not in OVERLAP_MODE: raise ContractViolation("invalid overlap_mode")
        if directives["typography_mode"] not in TYPOGRAPHY_MODE: raise ContractViolation("invalid typography_mode")
    validate_form_request(c["form_request"])
    if not isinstance(c["risk_notes"],list): raise ContractViolation("risk_notes must be array")
    ba=c["beat_art"]
    if not isinstance(ba,list) or len(ba)!=len(beat_ids): raise ContractViolation("beat_art must cover every beat")
    seen=set()
    authored_support_floor=max([len(b.get("supporting_roles") or []) for b in ba if isinstance(b,dict)] or [0])
    # support_budget is execution provisioning, never a creative ceiling. Expand it to the
    # Art Director's authored composition rather than truncating/rejecting support roles.
    comp["support_budget"]=max(int(comp["support_budget"]),authored_support_floor)
    for b in ba:
        require_exact_keys(b,{"beat_id","settled_visual_state","focal_owner","supporting_roles","meaning_without_motion"},{"environment_state","prop_specificity","character_performance_state","typography_role","depth_read"},label="beat_art")
        if b["beat_id"] not in beat_ids or b["beat_id"] in seen: raise ContractViolation("beat_art id mismatch")
        seen.add(b["beat_id"])
        if not str(b["settled_visual_state"]).strip(): raise ContractViolation("settled visual state required")
        if not isinstance(b["supporting_roles"],list): raise ContractViolation("beat supporting_roles must be array")
        if premium_contract:
            for key in ("environment_state","prop_specificity","character_performance_state","typography_role","depth_read"):
                if not isinstance(b.get(key),str) or not b[key].strip(): raise ContractViolation(f"premium beat art {b['beat_id']} missing {key}")
        if b["meaning_without_motion"] is not True: raise ContractViolation("settled key state must communicate without motion")
    return deepcopy(c)


def validate_art_output(payload:Dict[str,Any], beat_ids:Set[str], visual_candidate_id:str, *, repair_mode:bool=False)->List[Dict[str,Any]]:
    reject_geometry_code_authority(payload)
    require_exact_keys(payload,{"candidates"},{"director_notes"},label="art_output")
    cs=payload["candidates"]
    if not isinstance(cs,list): raise ContractViolation("art output candidates must be array")
    if repair_mode:
        if len(cs)!=1: raise ContractViolation("art surgical repair must return exactly one candidate")
    elif len(cs)<2:
        raise ContractViolation("art output requires genuine candidate competition")
    ids=set(); out=[]
    for c in cs:
        x=validate_art_candidate(c,beat_ids,visual_candidate_id)
        if x["candidate_id"] in ids: raise ContractViolation("duplicate art candidate")
        ids.add(x["candidate_id"]); out.append(x)
    if not repair_mode:
        assert_semantic_candidate_diversity(out,label="art candidates")
    return out
