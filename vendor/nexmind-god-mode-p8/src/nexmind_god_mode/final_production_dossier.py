from __future__ import annotations
from copy import deepcopy
class FinalProductionDossierCompiler:
    def compile(self,sound_board,final_review):
        out=deepcopy(sound_board);out['schema']='NexMindFinalProductionDossierV5';out['final_producer_review']=deepcopy(final_review);out['unresolved_departments']=[]
        out['creative_lock_eligibility']='HUMAN_REVIEW_REQUIRED' if final_review['uncertainty']['human_review_required'] else ('ELIGIBLE' if final_review['verdict']=='ACCEPT' else 'BLOCKED')
        return out
