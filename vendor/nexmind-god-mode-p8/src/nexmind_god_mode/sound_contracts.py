from __future__ import annotations
from copy import deepcopy
from typing import Any,Dict,List,Set
from .contracts import ContractViolation,reject_geometry_code_authority,require_exact_keys,assert_semantic_candidate_diversity
KINDS={'SFX','FOLEY','TRANSITION','NARRATION_ACCENT','MUSIC_CUE','SILENCE'}
INTENSITY={'NONE','SOFT','MEDIUM','STRONG','PEAK'}
MUSIC_MODES={'NONE','MOTIF_ONLY','EXISTING_LICENSED','GENERATIVE'}
DUCK={'NONE','LIGHT','MODERATE','STRONG'}
BAD_REASONS={'add energy','keep it interesting','generic energy','fill silence','make it cinematic','background music'}

def validate_sound_event(e:Dict[str,Any],beat_ids:Set[str])->Dict[str,Any]:
    reject_geometry_code_authority(e); require_exact_keys(e,{'event_id','beat_id','kind','semantic_tag','intensity','optional','ducking','narrative_reason','sync_target','silence_before','silence_after'},label='sound_event')
    if e['beat_id'] not in beat_ids: raise ContractViolation('sound event unknown beat')
    if e['kind'] not in KINDS or e['intensity'] not in INTENSITY or e['ducking'] not in DUCK: raise ContractViolation('invalid sound vocabulary')
    if not str(e['narrative_reason']).strip() or str(e['narrative_reason']).strip().lower() in BAD_REASONS: raise ContractViolation('sound event requires narrative reason')
    if e['kind']=='SILENCE' and e['semantic_tag']!='silence': raise ContractViolation('silence event tag must be silence')
    if not isinstance(e['optional'],bool) or not isinstance(e['silence_before'],bool) or not isinstance(e['silence_after'],bool): raise ContractViolation('sound booleans invalid')
    return deepcopy(e)

def validate_sound_candidate(c:Dict[str,Any],beat_ids:Set[str])->Dict[str,Any]:
    reject_geometry_code_authority(c); require_exact_keys(c,{'candidate_id','sound_thesis','narration_strategy','music_strategy','motifs','events','beat_sound_summary','mix_intent','silence_strategy','risk_notes'},label='sound_candidate')
    if not str(c['sound_thesis']).strip() or not str(c['narration_strategy']).strip() or not str(c['silence_strategy']).strip(): raise ContractViolation('sound thesis/narration/silence required')
    m=c['music_strategy']; require_exact_keys(m,{'mode','full_length_bed','narrative_role','energy_arc','rights_policy'},label='music_strategy')
    if m['mode'] not in MUSIC_MODES: raise ContractViolation('invalid music mode')
    if not isinstance(m['full_length_bed'],bool): raise ContractViolation('music full_length_bed must be bool')
    if m['full_length_bed'] and str(m['narrative_role']).strip().lower() in BAD_REASONS|{'continuous underscore'}: raise ContractViolation('generic full-length music bed rejected')
    if m['mode']=='GENERATIVE' and m['rights_policy']!='RIGHTS_SAFE_PROVIDER_REQUIRED': raise ContractViolation('generative music requires rights-safe provider policy')
    mix=c['mix_intent']; require_exact_keys(mix,{'narration_priority','ducking_profile','impact_headroom','mastering_intent'},label='mix_intent')
    if mix['ducking_profile'] not in DUCK: raise ContractViolation('invalid ducking profile')
    ev=c['events'];
    if not isinstance(ev,list): raise ContractViolation('sound events must be list')
    seen=set(); out=[]
    for e in ev:
        v=validate_sound_event(e,beat_ids)
        if v['event_id'] in seen: raise ContractViolation('duplicate sound event id')
        seen.add(v['event_id']); out.append(v)
    if not isinstance(c['beat_sound_summary'],list) or {x.get('beat_id') for x in c['beat_sound_summary']}!=beat_ids: raise ContractViolation('sound summary must cover every beat')
    return deepcopy(c)

def fingerprint(c): return (c['music_strategy']['mode'],c['music_strategy']['full_length_bed'],tuple((e['beat_id'],e['kind'],e['semantic_tag'],e['intensity']) for e in c['events']))
def validate_sound_output(payload:Dict[str,Any],beat_ids:Set[str],*,repair_mode:bool=False)->List[Dict[str,Any]]:
    reject_geometry_code_authority(payload); require_exact_keys(payload,{'candidates'},{'director_notes'},label='sound_output'); cs=payload['candidates']
    if not isinstance(cs,list): raise ContractViolation('sound candidates must be an array')
    if repair_mode:
        if len(cs)!=1: raise ContractViolation('sound surgical repair must return exactly one candidate')
    elif len(cs)<2: raise ContractViolation('sound requires genuine candidate competition')
    out=[];ids=set();fps=set()
    for c in cs:
        v=validate_sound_candidate(c,beat_ids)
        if v['candidate_id'] in ids: raise ContractViolation('duplicate sound candidate id')
        ids.add(v['candidate_id']);fps.add(fingerprint(v));out.append(v)
    if not repair_mode:
        if len(fps)<2: raise ContractViolation('sound candidates not materially different')
        assert_semantic_candidate_diversity(out,label="sound_contracts candidates")
    return out
