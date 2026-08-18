from __future__ import annotations
import copy,hashlib,json
from .showrunner_p7 import NexMindSupremeShowrunnerP7
from .p0_kernel import NexMindSupremeShowrunner,AuthorityViolation,CandidateError,CreativeLockError
from .showrunner_p2 import ProducerGateError
from .final_producer_contracts import human_review_gate

def h(o):return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

class NexMindSupremeShowrunnerP8(NexMindSupremeShowrunnerP7):
    DECISION_SLOT_AUTHORITY={
        'film_thesis':{'StoryDirector'},'visual_concept':{'VisualConceptDirector'},
        'art_direction':{'ArtDirector'},'storyboard':{'StoryboardCompiler'},
        'cinematography':{'CinematographyDirector'},'editorial_rhythm':{'EditorialRhythmDirector'},
        'storyboard_temporal':{'StoryboardCompilerV2'},'motion_performance':{'MotionPerformanceDirector'},
        'sound_direction':{'SoundDirector'},
    }
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw);self.state['p8_schema']='NexMindSupremeShowrunnerP8StateV1';self.state['final_producer_reviews']=[];self.state['human_creative_reviews']=[];self.state['p8_gate']={'status':'OPEN'}
        fm=self.state.setdefault('film_memory',{})
        for key,default in {
            'persistent_entities':[],'established_relationships':[],'used_visual_motifs':[],
            'density_history':[],'palette_material_progression':[],'intensity_curve':[],
            'current_scene_state':None,
        }.items(): fm.setdefault(key,copy.deepcopy(default))
    def set_creative_memory_refs(self,records):
        self._assert_unlocked();accepted=[]
        for raw in records or []:
            if not isinstance(raw,dict) or raw.get('status')!='PROMOTED':continue
            if not str(raw.get('memory_id') or '').strip() or not str(raw.get('provenance') or '').strip():continue
            accepted.append(copy.deepcopy(raw))
        self.state['creative_memory_refs']=accepted
        self._event('CREATIVE_MEMORY_BOUND',{'count':len(self.state['creative_memory_refs']),'hash':h(self.state['creative_memory_refs'])})
    def _assert_slot_authority(self,slot,proposal):
        allowed=self.DECISION_SLOT_AUTHORITY.get(slot)
        if allowed is not None and proposal.department not in allowed:
            self._event('DIRECTOR_AUTHORITY_BOUNDARY_BLOCKED',{'decision_slot':slot,'department':proposal.department,'allowed':sorted(allowed)})
            raise AuthorityViolation(f'{proposal.department} cannot own {slot}; allowed={sorted(allowed)}')
    def commit_reviewed_decision(self,slot,proposal,review_id,*,require_diversity_from=None):
        self._assert_slot_authority(slot,proposal)
        return super().commit_reviewed_decision(slot,proposal,review_id,require_diversity_from=require_diversity_from)
    def commit_p3_reviewed(self,slot,proposal,review_id,*,require_diversity_from=None):
        self._assert_slot_authority(slot,proposal)
        return super().commit_p3_reviewed(slot,proposal,review_id,require_diversity_from=require_diversity_from)
    def commit_p45_reviewed(self,slot,proposal,review_id,*,require_diversity_from=None):
        self._assert_slot_authority(slot,proposal)
        return super().commit_p45_reviewed(slot,proposal,review_id,require_diversity_from=require_diversity_from)
    def commit_p6_reviewed(self,proposal,review_id,*,require_diversity_from=None):
        self._assert_slot_authority('motion_performance',proposal)
        return super().commit_p6_reviewed(proposal,review_id,require_diversity_from=require_diversity_from)
    def commit_p7_reviewed(self,proposal,review_id,*,require_diversity_from=None):
        self._assert_slot_authority('sound_direction',proposal)
        return super().commit_p7_reviewed(proposal,review_id,require_diversity_from=require_diversity_from)
    def commit_decision(self,slot,proposal,*,require_diversity_from=None):
        if slot=='final_producer':raise AuthorityViolation('final_producer is independent-review governed in P8')
        self._assert_slot_authority(slot,proposal)
        return super().commit_decision(slot,proposal,require_diversity_from=require_diversity_from)
    def register_final_producer_review(self,review,final_board):
        # Bind the review to the complete committed creative state and final board.
        snapshot={k:v for k,v in self.state['decisions'].items() if k!='final_producer'}
        rid=h({'production_id':self.state['production_id'],'revision':self.state['revision'],'decisions_hash':h(snapshot),'board_hash':h(final_board),'review':review})
        self.state['final_producer_reviews'].append({'review_id':rid,'revision':self.state['revision'],'decisions_hash':h(snapshot),'board_hash':h(final_board),'review':copy.deepcopy(review)})
        return rid
    def commit_final_producer(self,review_id,final_board):
        ms=[x for x in self.state['final_producer_reviews'] if x['review_id']==review_id]
        if len(ms)!=1:raise ProducerGateError('final producer token not found')
        rr=ms[0];snapshot={k:v for k,v in self.state['decisions'].items() if k!='final_producer'}
        if rr['revision']!=self.state['revision'] or rr['decisions_hash']!=h(snapshot) or rr['board_hash']!=h(final_board):raise ProducerGateError('final producer review stale or production tampered')
        if rr['review'].get('verdict') not in {'ACCEPT','ESCALATE_HUMAN'}:raise ProducerGateError('final producer did not accept machine creative state')
        self.state['decisions']['final_producer']={'decision_slot':'final_producer','department':'IndependentFinalExecutiveProducer','proposal_id':review_id,'payload':copy.deepcopy(rr['review']),'revision':self.state['revision'],'status':'COMMITTED_FINAL_PRODUCER_REVIEW'}
        return copy.deepcopy(self.state['decisions']['final_producer'])
    def register_human_creative_review(self,review):
        gate=human_review_gate(review);rec={'review':copy.deepcopy(review),'gate':gate,'revision':self.state['revision']};self.state['human_creative_reviews'].append(rec);return copy.deepcopy(gate)
    def p8_ready_gate(self):
        self.p7_ready_gate()
        if 'final_producer' not in self.state['decisions']:raise ProducerGateError({'missing_p8':['final_producer']})
        fp=self.state['decisions']['final_producer']['payload']
        human=[x for x in self.state['human_creative_reviews'] if x['revision']==self.state['revision'] and x['gate']['status']=='PASS']
        cal_block=fp.get('uncertainty',{}).get('human_review_required',True) and not human
        self.state['p8_gate']={'status':'BLOCKED_HUMAN_REVIEW' if cal_block else 'PASS','revision':self.state['revision'],'human_review_pass_count':len(human)}
        return copy.deepcopy(self.state['p8_gate'])
    def creative_lock(self):
        missing=[x for x in self.FINAL_CREATIVE_DEPARTMENTS if x not in self.state['decisions']]
        if missing:raise ProducerGateError({'status':'FINAL_CREATIVE_LOCK_BLOCKED_INCOMPLETE_BRAIN','missing_decisions':missing})
        gate=self.p8_ready_gate()
        if gate['status']!='PASS':raise CreativeLockError({'status':'FINAL_CREATIVE_LOCK_BLOCKED_HUMAN_REVIEW','gate':gate})
        return NexMindSupremeShowrunner.creative_lock(self)
