from __future__ import annotations
from copy import deepcopy
from typing import Any, Dict

SUPPORTED='SUPPORTED'; UNSUPPORTED='UNSUPPORTED'; REWRITE='REWRITE'

class CapabilityError(ValueError): pass

class PerformerCapabilityRegistry:
    """NexMind-facing capability view. It never exposes joint writes or geometry."""
    def __init__(self, overrides:Dict[str,Any]|None=None):
        self.performers={
            'STICKMAN_V2':{
                'supported':{'LOOK','WALK','RUN','SPRINT','SIT','STAND','REACH','POINT','PRESENT','PRESS','TAP','PICKUP','PLACE','HOLD','CARRY_LIGHT','TYPE','PHONE_HOLD','DANCE','HANDOFF_PLACE_AND_TAKE'},
                'blocked':{
                    'CARRY_HEAVY':'HEAVY_CARRY_DONOR_REQUIRED',
                    'SIDESTEP':'NO_AUTHORED_SIDESTEP_DONOR',
                    'LATERAL_REPOSITION':'COMPOSITE_NOT_YET_ADMITTED',
                    'HANDOFF_DIRECT':'QUARANTINED_VISUAL_COLLAPSE',
                },
                'requirements':{
                    'SIT':{'seat_anchor'}, 'STAND':{'seat_anchor'},
                    'PICKUP':{'grip_frame','support_state'}, 'PLACE':{'support_surface'},
                    'PRESS':{'button_target'}, 'TAP':{'contact_target'},
                    'CARRY_LIGHT':{'grip_frame'}, 'HANDOFF_PLACE_AND_TAKE':{'support_surface','grip_frame'},
                },
                'evidence':{'engine':'NexStickmanEngineV2','contact_correction_max_m':0.035,'ownership':'contact/load gated','direct_handoff':'quarantined','heavy_carry':'blocked'}
            },
            'SCENE_GRAPH':{
                'supported':{'HOLD','REVEAL','HIGHLIGHT','DE_EMPHASIZE','TRACE_FLOW','TRANSFORM','OBJECT_MOVE','TYPE_REVEAL','SETTLE'},
                'blocked':{},'requirements':{},'evidence':{'authority':'deterministic scene-graph body'}
            },
            'WHITEBOARD':{
                'supported':{'HOLD','DRAW','ANNOTATE','ERASE','REVEAL','HIGHLIGHT','TRACE_FLOW','TRANSFORM','SETTLE'},
                'blocked':{},'requirements':{},'evidence':{'authority':'NexWhiteboard body service'}
            },
            'PRODUCT_UI':{
                'supported':{'HOLD','REFRAME_CONTENT','SCROLL','HIGHLIGHT','STATE_CHANGE','SETTLE'},
                'blocked':{},'requirements':{},'evidence':{'authority':'product media body service'}
            },
            # Generic robot is deliberately conservative until an exact performer capability packet is supplied.
            'ROBOT':{
                'supported':{'HOLD','LOOK'},
                'blocked':{'PICKUP':'ROBOT_GRASP_CAPABILITY_NOT_PROVEN','PRESS':'ROBOT_CONTACT_CAPABILITY_NOT_PROVEN','HANDOFF_DIRECT':'ROBOT_HANDOFF_CAPABILITY_NOT_PROVEN','CARRY_LIGHT':'ROBOT_CARRY_CAPABILITY_NOT_PROVEN'},
                'requirements':{},'evidence':{'authority':'capability-packet required for articulated interaction'}
            },
            'HUMANOID':{
                'supported':{'HOLD','LOOK'},
                'blocked':{},'requirements':{},'evidence':{'authority':'exact performer packet required beyond passive presence'}
            }
        }
        if overrides:
            for k,v in overrides.items(): self.performers[k]=deepcopy(v)

    def model_view(self)->Dict[str,Any]:
        """JSON-safe execution capability view for creative planning."""
        out={}
        for performer,packet in self.performers.items():
            out[performer]={
                'supported':sorted(packet.get('supported',set())),
                'blocked':deepcopy(packet.get('blocked',{})),
                'requirements':{verb:sorted(reqs) for verb,reqs in (packet.get('requirements',{}) or {}).items()},
            }
        return {'schema':'NexMindPerformerCapabilityModelViewV1','performers':out}

    def resolve(self, performer:str, verb:str, available_requirements:set[str], *, semantic_goal:str='', fallback_policy:str='FAIL_CLOSED')->Dict[str,Any]:
        if performer not in self.performers:
            return {'status':UNSUPPORTED,'code':'UNKNOWN_PERFORMER_CLASS','performer':performer,'requested_verb':verb}
        p=self.performers[performer]
        if verb in p.get('blocked',{}):
            code=p['blocked'][verb]
            if performer=='STICKMAN_V2' and verb=='HANDOFF_DIRECT' and fallback_policy=='ALLOW_SEMANTIC_EQUIVALENT' and 'support_surface' in available_requirements and 'grip_frame' in available_requirements and semantic_goal in {'TRANSFER_OWNERSHIP','TRANSFER_OBJECT','REVIEW_HANDOFF'}:
                return {'status':REWRITE,'code':'DIRECT_HANDOFF_REWRITTEN_TO_SAFE_PLACE_AND_TAKE','performer':performer,'requested_verb':verb,'resolved_verb':'HANDOFF_PLACE_AND_TAKE','preserves_semantic_goal':True,'evidence':deepcopy(p['evidence'])}
            return {'status':UNSUPPORTED,'code':code,'performer':performer,'requested_verb':verb,'preserves_semantic_goal':False}
        if verb not in p.get('supported',set()):
            return {'status':UNSUPPORTED,'code':'PERFORMER_CAPABILITY_NOT_ADMITTED','performer':performer,'requested_verb':verb,'preserves_semantic_goal':False}
        needed=set(p.get('requirements',{}).get(verb,set())); missing=sorted(needed-set(available_requirements))
        if missing:
            return {'status':UNSUPPORTED,'code':'MISSING_PERFORMER_REQUIREMENTS','performer':performer,'requested_verb':verb,'missing_requirements':missing,'preserves_semantic_goal':False}
        return {'status':SUPPORTED,'code':'CAPABILITY_ADMITTED','performer':performer,'requested_verb':verb,'resolved_verb':verb,'preserves_semantic_goal':True,'evidence':deepcopy(p.get('evidence',{}))}
