from __future__ import annotations
import copy,hashlib,json
from .showrunner_p6 import NexMindSupremeShowrunnerP6
from .p0_kernel import NexMindSupremeShowrunner,AuthorityViolation
from .showrunner_p2 import ProducerGateError
from .p0_kernel import CandidateError
P7_SLOTS={'sound_direction'}
def h(o):return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
class NexMindSupremeShowrunnerP7(NexMindSupremeShowrunnerP6):
    FINAL_CREATIVE_DEPARTMENTS=('film_thesis','visual_concept','art_direction','storyboard','cinematography','editorial_rhythm','storyboard_temporal','motion_performance','sound_direction','final_producer')
    def __init__(self,*a,**kw):super().__init__(*a,**kw);self.state['p7_schema']='NexMindSupremeShowrunnerP7StateV1';self.state['p7_reviews']=[];self.state['p7_gate']={'status':'OPEN'}
    def commit_decision(self,slot,proposal,*,require_diversity_from=None):
        if slot in P7_SLOTS: raise AuthorityViolation('sound_direction is Producer-governed in P7')
        return super().commit_decision(slot,proposal,require_diversity_from=require_diversity_from)
    def register_p7_review(self,proposal,review):
        rec=self.state['proposals'].get(proposal.department,{}).get(proposal.proposal_id)
        if not rec or rec['revision']!=self.state['revision']:raise CandidateError('review target stale/missing')
        rid=h({'production_id':self.state['production_id'],'revision':self.state['revision'],'slot':'sound_direction','department':proposal.department,'proposal_id':proposal.proposal_id,'payload_hash':h(rec['payload']),'review':review});self.state['p7_reviews'].append({'review_id':rid,'proposal_id':proposal.proposal_id,'department':proposal.department,'payload_hash':h(rec['payload']),'review':copy.deepcopy(review),'revision':self.state['revision']});return rid
    def commit_p7_reviewed(self,proposal,review_id,*,require_diversity_from=None):
        ms=[x for x in self.state['p7_reviews'] if x['review_id']==review_id]
        if len(ms)!=1:raise ProducerGateError('P7 review token not found')
        rr=ms[0];rec=self.state['proposals'].get(proposal.department,{}).get(proposal.proposal_id)
        if rr['proposal_id']!=proposal.proposal_id or rr['department']!=proposal.department:raise ProducerGateError('P7 review token mismatch')
        if rr['revision']!=self.state['revision'] or not rec or rr['payload_hash']!=h(rec['payload']):raise ProducerGateError('P7 review stale/tampered')
        if rr['review'].get('verdict')!='ACCEPT':raise ProducerGateError('sound work not Producer accepted')
        if 'motion_performance' not in self.state['decisions']:raise ProducerGateError('sound requires committed motion/performance')
        out=NexMindSupremeShowrunner.commit_decision(self,'sound_direction',proposal,require_diversity_from=require_diversity_from);self.state['decisions']['sound_direction']['producer_review_id']=review_id;return out
    def p7_ready_gate(self):
        self.p6_ready_gate()
        if 'sound_direction' not in self.state['decisions']:raise ProducerGateError({'missing_p7':['sound_direction']})
        self.state['p7_gate']={'status':'PASS','revision':self.state['revision']};return copy.deepcopy(self.state['p7_gate'])
    def creative_lock(self):
        missing=[x for x in self.FINAL_CREATIVE_DEPARTMENTS if x not in self.state['decisions']]
        if missing:raise ProducerGateError({'status':'FINAL_CREATIVE_LOCK_BLOCKED_INCOMPLETE_BRAIN','missing_decisions':missing})
        return NexMindSupremeShowrunner.creative_lock(self)
