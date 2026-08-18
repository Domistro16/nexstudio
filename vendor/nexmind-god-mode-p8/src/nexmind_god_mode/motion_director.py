from __future__ import annotations
from copy import deepcopy
from typing import Any,Dict,List
from .provider import CreativeModelProvider
from .motion_contracts import validate_motion_output
from .performer_capabilities import PerformerCapabilityRegistry, UNSUPPORTED, REWRITE

class MotionPerformanceDirector:
    def __init__(self,provider:CreativeModelProvider,capabilities:PerformerCapabilityRegistry): self.provider=provider; self.capabilities=capabilities
    def propose(self,production_id:str,brief:Dict[str,Any],story:Dict[str,Any],visual:Dict[str,Any],art:Dict[str,Any],cinema:Dict[str,Any],editorial:Dict[str,Any],temporal_storyboard:Dict[str,Any],doctrine:Dict[str,Any])->List[Dict[str,Any]]:
        brief_copy=deepcopy(brief)
        revision_context=brief_copy.get('autonomous_revision_context') if isinstance(brief_copy.get('autonomous_revision_context'),dict) else {}
        broader_replan=revision_context.get('department')=='MOTION_PERFORMANCE' and revision_context.get('repair_mode')=='MATERIAL_STRATEGY_REPLAN'
        repair_anchor=revision_context.get('previous_output') if revision_context.get('department')=='MOTION_PERFORMANCE' else None
        surgical_repair=isinstance(repair_anchor,dict) and bool(repair_anchor) and not broader_replan
        duration=int(brief_copy.get('duration_s') or 0)
        candidate_budget=1 if surgical_repair else 2 + (1 if duration>=45 or len(story.get('beats') or [])>=6 else 0)
        candidate_budget=max(1,min(4,candidate_budget))
        req={
            'production_id':production_id,'brief':brief_copy,'film_thesis':deepcopy(story['film_thesis']),'visual_concept':deepcopy(visual),'art_direction':deepcopy(art),'cinematography':deepcopy(cinema),'editorial_rhythm':deepcopy(editorial),'temporal_storyboard':deepcopy(temporal_storyboard),'creative_doctrine':deepcopy(doctrine),
            'performer_capabilities':self.capabilities.model_view(),'repair_anchor':deepcopy(repair_anchor) if surgical_repair else None,'candidate_budget':candidate_budget,
            'instruction':{
                'role':'NexMind Motion / Performance Director',
                'goal':(
                    'Surgically repair the supplied Motion repair_anchor into exactly one stronger executable performance plan. Preserve unaffected choreography and resolve every binding repair issue without reopening competition.'
                    if surgical_repair else
                    (f'Materially replan Motion/Performance with exactly {candidate_budget} genuinely different executable strategies; do not cosmetically polish the exhausted route.' if broader_replan else f'Generate exactly {candidate_budget} genuinely competing semantic performance strategies, then bind each intent to an explicit supported execution primitive.')
                ),
                'laws':['authored/captured performer motion first','physical contact and ownership are hard constraints','safe independent explanatory actions may overlap','dependencies serialize','no idle bobbing or decorative orbit','motion cannot create semantic entities','choose performer_class/requested_verb/available_requirements from performer_capabilities so the plan is executable on first pass','unsupported action must fail closed or use a semantically equivalent choreography explicitly allowed by policy','when repair_anchor is supplied, return exactly one repaired candidate and preserve sticky_requirements','no coordinates, joints, IK or renderer code']
            }
        }
        candidates=validate_motion_output(self.provider.complete('motion_performance',req),{b['beat_id'] for b in story['beats']},repair_mode=surgical_repair)
        return [self._resolve(c) for c in candidates]
    def _resolve(self,c):
        out=deepcopy(c); gaps=[]; rewrites=[]
        for a in out['actions']:
            dec=self.capabilities.resolve(a['performer_class'],a['requested_verb'],set(a['available_requirements']),semantic_goal=a['semantic_goal'],fallback_policy=a['fallback_policy'])
            a['execution']=dec
            if dec['status']==REWRITE:
                rewrites.append({'action_id':a['action_id'],'from':a['requested_verb'],'to':dec['resolved_verb'],'code':dec['code']})
            elif dec['status']==UNSUPPORTED:
                gaps.append({'action_id':a['action_id'],'code':dec['code'],'requested_verb':a['requested_verb'],'performer_class':a['performer_class']})
        out['capability_gaps']=gaps; out['choreography_rewrites']=rewrites; out['executable']=not gaps
        return out
