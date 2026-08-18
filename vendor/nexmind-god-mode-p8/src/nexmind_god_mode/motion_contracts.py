from __future__ import annotations
from copy import deepcopy
from typing import Any,Dict,List,Set
from .contracts import ContractViolation, reject_geometry_code_authority, require_exact_keys, assert_semantic_candidate_diversity

VERBS={'HOLD','LOOK','WALK','RUN','SPRINT','SIT','STAND','REACH','POINT','PRESENT','PRESS','TAP','PICKUP','PLACE','CARRY_LIGHT','CARRY_HEAVY','HANDOFF_DIRECT','HANDOFF_PLACE_AND_TAKE','TYPE','PHONE_HOLD','DANCE','REVEAL','HIGHLIGHT','DE_EMPHASIZE','TRACE_FLOW','TRANSFORM','OBJECT_MOVE','TYPE_REVEAL','SETTLE','DRAW','ANNOTATE','ERASE','REFRAME_CONTENT','SCROLL','STATE_CHANGE','SIDESTEP','LATERAL_REPOSITION'}
PERFORMERS={'STICKMAN_V2','HUMANOID','ROBOT','SCENE_GRAPH','WHITEBOARD','PRODUCT_UI','SPECIALIST'}
OVERLAP={'SERIAL_REQUIRED','MAY_OVERLAP','OVERLAP_PREFERRED','HOLD'}
FALLBACK={'FAIL_CLOSED','ALLOW_SEMANTIC_EQUIVALENT'}
CONTACT={'NONE','TARGET_CONTACT','GRIP_CONTACT','SEAT_CONTACT','SHARED_SUPPORT_CONTACT'}
BAD_DECORATIVE={'idle bobbing','decorative orbit','meaningless pulse','generic spin','whole-scene dissolve','move for energy','keep it moving'}


def validate_action(a:Dict[str,Any], beat_ids:Set[str])->Dict[str,Any]:
    reject_geometry_code_authority(a)
    require_exact_keys(a,{'action_id','beat_id','actor','semantic_action','requested_verb','performer_class','target','prop','semantic_goal','causal_role','dependencies','overlap_policy','anticipation','contact_requirement','ownership_before','ownership_after','settle','reduced_motion','fallback_policy','available_requirements','motivation'},label='motion_action')
    if a['beat_id'] not in beat_ids: raise ContractViolation('motion action unknown beat')
    if not isinstance(a['semantic_action'],str) or not a['semantic_action'].strip(): raise ContractViolation('open semantic action required')
    if a['requested_verb'] not in VERBS: raise ContractViolation('invalid execution-binding motion primitive')
    if a['performer_class'] not in PERFORMERS: raise ContractViolation('invalid performer class')
    if a['overlap_policy'] not in OVERLAP or a['fallback_policy'] not in FALLBACK or a['contact_requirement'] not in CONTACT: raise ContractViolation('invalid motion policy vocabulary')
    if not isinstance(a['dependencies'],list) or not isinstance(a['available_requirements'],list): raise ContractViolation('motion dependencies/requirements must be lists')
    if a['action_id'] in a['dependencies']: raise ContractViolation('motion action cannot depend on itself')
    if not str(a['semantic_goal']).strip() or not str(a['causal_role']).strip() or not str(a['motivation']).strip(): raise ContractViolation('semantic goal/causal role/motivation required')
    if str(a['motivation']).strip().lower() in BAD_DECORATIVE: raise ContractViolation('decorative/unmotivated motion rejected')
    if a['requested_verb']=='HOLD' and a['overlap_policy']!='HOLD': raise ContractViolation('HOLD must use HOLD overlap policy')
    return deepcopy(a)


def validate_motion_candidate(c:Dict[str,Any], beat_ids:Set[str])->Dict[str,Any]:
    reject_geometry_code_authority(c)
    require_exact_keys(c,{'candidate_id','motion_thesis','restraint_strategy','actions','beat_motion_summary','global_rules','risk_notes'},label='motion_candidate')
    if not str(c['motion_thesis']).strip() or not str(c['restraint_strategy']).strip(): raise ContractViolation('motion thesis/restraint required')
    acts=c['actions'];
    if not isinstance(acts,list) or not acts: raise ContractViolation('motion candidate requires actions')
    ids=set(); out=[]
    for a in acts:
        v=validate_action(a,beat_ids)
        if v['action_id'] in ids: raise ContractViolation('duplicate action id')
        ids.add(v['action_id']); out.append(v)
    for a in out:
        missing=set(a['dependencies'])-ids
        if missing: raise ContractViolation(f"unknown motion dependencies: {sorted(missing)}")
        if a['contact_requirement']!='NONE' and a['overlap_policy']=='OVERLAP_PREFERRED' and a['dependencies']:
            raise ContractViolation('contact-dependent physical action cannot force overlap across dependency')
    if not isinstance(c['beat_motion_summary'],list) or {x.get('beat_id') for x in c['beat_motion_summary']}!=beat_ids: raise ContractViolation('motion summary must cover every beat exactly')
    return deepcopy(c)


def fingerprint(c:Dict[str,Any]):
    return tuple((a['beat_id'],a['requested_verb'],a['performer_class'],a['overlap_policy'],a['semantic_goal']) for a in c['actions'])


def validate_motion_output(payload:Dict[str,Any], beat_ids:Set[str], *, repair_mode:bool=False)->List[Dict[str,Any]]:
    reject_geometry_code_authority(payload); require_exact_keys(payload,{'candidates'},{'director_notes'},label='motion_output')
    cs=payload['candidates']
    if not isinstance(cs,list): raise ContractViolation('motion candidates must be an array')
    if repair_mode:
        if len(cs)!=1: raise ContractViolation('motion surgical repair must return exactly one candidate')
    elif len(cs)<2: raise ContractViolation('motion requires genuine candidate competition')
    out=[]; ids=set(); fps=set()
    for c in cs:
        v=validate_motion_candidate(c,beat_ids)
        if v['candidate_id'] in ids: raise ContractViolation('duplicate motion candidate id')
        ids.add(v['candidate_id']); fps.add(fingerprint(v)); out.append(v)
    if not repair_mode:
        if len(fps)<2: raise ContractViolation('motion candidates not materially different')
        assert_semantic_candidate_diversity(out,label="motion_contracts candidates")
    return out
