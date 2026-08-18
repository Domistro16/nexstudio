from __future__ import annotations
from copy import deepcopy
from typing import Any,Dict
from .provider import CreativeModelProvider
from .contracts import validate_producer_output
from .review_governance import calibrate_review, release_decision_law

class MotionExecutiveProducer:
    def __init__(self,provider:CreativeModelProvider): self.provider=provider
    def review(self,production_id:str,brief:Dict[str,Any],story:Dict[str,Any],motion:Dict[str,Any])->Dict[str,Any]:
        mechanical=[]
        if motion.get('capability_gaps'): mechanical.append({'code':'UNSUPPORTED_PERFORMER_ACTION','gaps':deepcopy(motion['capability_gaps'])})
        for a in motion['actions']:
            if a['execution']['status']=='REWRITE' and not a['execution'].get('preserves_semantic_goal'): mechanical.append({'code':'UNSAFE_CHOREOGRAPHY_REWRITE','action_id':a['action_id']})
            if a['contact_requirement']!='NONE' and a['ownership_before']!=a['ownership_after'] and a['requested_verb'] not in {'PICKUP','PLACE','HANDOFF_DIRECT','HANDOFF_PLACE_AND_TAKE'}:
                mechanical.append({'code':'UNEXPLAINED_OWNERSHIP_CHANGE','action_id':a['action_id']})
        req={'production_id':production_id,'brief':deepcopy(brief),'film_thesis':deepcopy(story['film_thesis']),'motion_candidate':deepcopy(motion),'mechanical_preflight':mechanical,'instruction':{'role':'Independent Executive Producer — Motion/Performance','release_decision_law':release_decision_law('MOTION_PERFORMANCE'),'questions':['Is every movement motivated by state, causality, hierarchy or attention?','Are contact and ownership believable?','Do physical dependencies serialize while safe explanatory actions overlap?','Does every action settle or carry intentionally?','Is the film over-animated or mechanically busy?','Were unsupported performer actions rejected rather than approximated?']}}
        r=validate_producer_output(self.provider.complete('motion_review',req))
        if mechanical and r['verdict']=='ACCEPT':
            r=deepcopy(r); r['verdict']='REVISE'
            mechanical_blockers=[]
            for issue in mechanical:
                item=deepcopy(issue); item['blocking']=True; mechanical_blockers.append(item)
            r['issues']=[*mechanical_blockers,*r['issues']]; r['revision_brief']='Resolve performer capability/ownership failures without approximating them.'; r['commercial_confidence']='LOW'
        return validate_producer_output(calibrate_review(r,stage='MOTION_PERFORMANCE'))
