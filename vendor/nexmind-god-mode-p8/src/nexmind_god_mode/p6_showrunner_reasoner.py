from __future__ import annotations
from copy import deepcopy
from typing import Any,Dict,List
from .provider import CreativeModelProvider
from .showrunner_reasoner import validate_showrunner_selection
class MotionShowrunnerDecisionIntelligence:
    def __init__(self,provider:CreativeModelProvider): self.provider=provider
    def select(self,production_id:str,story:Dict[str,Any],reviewed:List[Dict[str,Any]])->Dict[str,Any]:
        eligible=[x for x in reviewed if x['review']['verdict']=='ACCEPT' and x['candidate'].get('executable')]
        if not eligible: raise ValueError('no Producer-accepted executable motion candidate')
        req={'production_id':production_id,'film_thesis':deepcopy(story['film_thesis']),'candidates':[{'candidate':deepcopy(x['candidate']),'review':deepcopy(x['review'])} for x in eligible],'instruction':{'role':'NexMind Supreme Showrunner — Motion Selection','goal':'Select the strongest executable motion strategy for causality, restraint, physical credibility and rhythm. Do not choose unsupported work. Give brief-specific decision_basis, at least two concrete evidence statements, the strongest alternative and why it loses, plus remaining risk.'}}
        sel=validate_showrunner_selection(self.provider.complete('showrunner_select_motion',req),{x['candidate']['candidate_id'] for x in eligible},{x['candidate']['candidate_id'] for x in reviewed})
        return sel
