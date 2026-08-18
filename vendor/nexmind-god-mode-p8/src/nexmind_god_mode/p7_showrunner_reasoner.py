from __future__ import annotations
from copy import deepcopy
from .showrunner_reasoner import validate_showrunner_selection
class SoundShowrunnerDecisionIntelligence:
    def __init__(self,provider): self.provider=provider
    def select(self,production_id,story,reviewed):
        eligible=[x for x in reviewed if x['review']['verdict']=='ACCEPT' and x['candidate'].get('executable_resource_plan')]
        if not eligible: raise ValueError('no Producer-accepted executable sound candidate')
        req={'production_id':production_id,'film_thesis':deepcopy(story['film_thesis']),'candidates':[{'candidate':deepcopy(x['candidate']),'review':deepcopy(x['review'])} for x in eligible],'instruction':{'role':'NexMind Supreme Showrunner — Sound Selection','goal':'Choose the strongest sonic argument for narrative clarity, restraint, emotional arc, synchronization and rights-safe execution. Give brief-specific decision_basis, at least two concrete evidence statements, the strongest alternative and why it loses, plus remaining risk.'}}
        return validate_showrunner_selection(self.provider.complete('showrunner_select_sound',req),{x['candidate']['candidate_id'] for x in eligible},{x['candidate']['candidate_id'] for x in reviewed})
