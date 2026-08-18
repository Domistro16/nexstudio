from __future__ import annotations
import copy,hashlib,json
from typing import Any,Dict,Iterable,Optional
from .showrunner_p45 import NexMindSupremeShowrunnerP45
from .p0_kernel import NexMindSupremeShowrunner, ProposalRef, AuthorityViolation, CandidateError
from .showrunner_p2 import ProducerGateError
P6_SLOTS={'motion_performance'}
def h(o): return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
class NexMindSupremeShowrunnerP6(NexMindSupremeShowrunnerP45):
    FINAL_CREATIVE_DEPARTMENTS=('film_thesis','visual_concept','art_direction','storyboard','cinematography','editorial_rhythm','storyboard_temporal','motion_performance','sound_direction','final_producer')
    def __init__(self,*a,**kw): super().__init__(*a,**kw); self.state['p6_schema']='NexMindSupremeShowrunnerP6StateV1'; self.state['p6_reviews']=[]; self.state['p6_gate']={'status':'OPEN'}
    def commit_decision(self,slot,proposal,*,require_diversity_from=None):
        if slot in P6_SLOTS: raise AuthorityViolation(f'{slot} is Producer-governed in P6')
        return super().commit_decision(slot,proposal,require_diversity_from=require_diversity_from)
    def register_p6_review(self,proposal:ProposalRef,review:Dict[str,Any])->str:
        rec=self.state['proposals'].get(proposal.department,{}).get(proposal.proposal_id)
        if not rec or rec['revision']!=self.state['revision']: raise CandidateError('review target stale/missing')
        rid=h({'production_id':self.state['production_id'],'revision':self.state['revision'],'slot':'motion_performance','department':proposal.department,'proposal_id':proposal.proposal_id,'payload_hash':h(rec['payload']),'review':review})
        self.state['p6_reviews'].append({'review_id':rid,'slot':'motion_performance','department':proposal.department,'proposal_id':proposal.proposal_id,'payload_hash':h(rec['payload']),'review':copy.deepcopy(review),'revision':self.state['revision']}); return rid
    def commit_p6_reviewed(self,proposal:ProposalRef,review_id:str,*,require_diversity_from:Optional[Iterable[str]]=None):
        ms=[x for x in self.state['p6_reviews'] if x['review_id']==review_id]
        if len(ms)!=1: raise ProducerGateError('P6 review token not found')
        rr=ms[0]; rec=self.state['proposals'].get(proposal.department,{}).get(proposal.proposal_id)
        if rr['proposal_id']!=proposal.proposal_id or rr['department']!=proposal.department: raise ProducerGateError('P6 review token mismatch')
        if rr['revision']!=self.state['revision'] or not rec or rr['payload_hash']!=h(rec['payload']): raise ProducerGateError('P6 review stale/tampered')
        if rr['review'].get('verdict')!='ACCEPT': raise ProducerGateError('motion work not Producer accepted')
        if 'storyboard_temporal' not in self.state['decisions']: raise ProducerGateError('motion requires canonical temporal storyboard')
        out=NexMindSupremeShowrunner.commit_decision(self,'motion_performance',proposal,require_diversity_from=require_diversity_from); self.state['decisions']['motion_performance']['producer_review_id']=review_id; return out
    def p6_ready_gate(self):
        self.p45_ready_gate()
        if 'motion_performance' not in self.state['decisions']: raise ProducerGateError({'missing_p6':['motion_performance']})
        self.state['p6_gate']={'status':'PASS','revision':self.state['revision']}; return copy.deepcopy(self.state['p6_gate'])
    def creative_lock(self):
        missing=[x for x in self.FINAL_CREATIVE_DEPARTMENTS if x not in self.state['decisions']]
        if missing: raise ProducerGateError({'status':'FINAL_CREATIVE_LOCK_BLOCKED_INCOMPLETE_BRAIN','missing_decisions':missing})
        return NexMindSupremeShowrunner.creative_lock(self)
