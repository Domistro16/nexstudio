from __future__ import annotations
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import os
from .motion_director import MotionPerformanceDirector
from .p6_producer import MotionExecutiveProducer
from .p6_showrunner_reasoner import MotionShowrunnerDecisionIntelligence
from .storyboard_compiler_v3 import PerformanceStoryboardCompiler
from .showrunner_p6 import NexMindSupremeShowrunnerP6
from .contracts import ContractViolation

def _parallel(items,fn):
    items=list(items)
    try:configured=int(os.getenv('NEXMIND_REVIEW_PARALLELISM','3') or 3)
    except Exception:configured=3
    workers=max(1,min(len(items),6,max(1,configured)))
    if len(items)<=1 or workers<=1:return [fn(x) for x in items]
    with ThreadPoolExecutor(max_workers=workers,thread_name_prefix='nexmind-motion-review') as pool:
        fs=[pool.submit(fn,x) for x in items];return [f.result() for f in fs]

def _surgical(sr,reviewed):
    ctx=sr.state.get('brief',{}).get('autonomous_revision_context') or {}
    return ctx.get('department')=='MOTION_PERFORMANCE' and ctx.get('repair_mode')!='MATERIAL_STRATEGY_REPLAN' and len(reviewed)==1

class CreativeCouncilP6:
    def __init__(self,sr:NexMindSupremeShowrunnerP6,motion:MotionPerformanceDirector,producer:MotionExecutiveProducer,reasoner:MotionShowrunnerDecisionIntelligence,storyboard:PerformanceStoryboardCompiler):self.sr=sr;self.motion=motion;self.producer=producer;self.reasoner=reasoner;self.storyboard=storyboard
    def develop(self,story,visual,art,cinema,editorial,temporal_board):
        cs=self.motion.propose(self.sr.state['production_id'],self.sr.state['brief'],story,visual,art,cinema,editorial,temporal_board,self.sr.state.get('creative_doctrine',{}));prepared=[];refs=[]
        for c in cs:
            pp={'representation':'MOTION_PERFORMANCE_PLAN','visual_thesis':c['motion_thesis'],'hero_kind':c['actions'][0]['performer_class'],'transformation':' | '.join(a['requested_verb'] for a in c['actions']),'camera_idea':'motion follows committed cinematography','motion_performance':deepcopy(c)}
            proposal_id=c['candidate_id'];proposal_id=(f"r{self.sr.state['revision']}:{proposal_id}" if proposal_id in self.sr.state.get('proposals',{}).get('MotionPerformanceDirector',{}) else proposal_id);ref=self.sr.submit_proposal('MotionPerformanceDirector',proposal_id,pp);refs.append(ref);prepared.append((c,ref))
        def review_one(item):
            c,ref=item;return c,ref,self.producer.review(self.sr.state['production_id'],self.sr.state['brief'],story,c)
        reviewed=[]
        for c,ref,r in _parallel(prepared,review_one):
            tok=self.sr.register_p6_review(ref,r);reviewed.append({'candidate':c,'review':r,'ref':ref,'review_id':tok})
        surgical=_surgical(self.sr,reviewed);div={'meaningfully_diverse':True,'surgical_repair':True} if surgical else self.sr.candidate_diversity('MotionPerformanceDirector',[x.proposal_id for x in refs])
        return {'reviewed':reviewed,'diversity':div}
    def select(self,story,developed):
        eligible=[x for x in developed['reviewed'] if x['review']['verdict']=='ACCEPT' and x['candidate'].get('executable')]
        if not eligible:raise RuntimeError('motion selection requires Producer-accepted executable work')
        surgical=_surgical(self.sr,developed['reviewed'])
        if len(eligible)==1:
            item=eligible[0];sel={'selected_candidate_id':item['candidate']['candidate_id'],'why':'Only Producer-accepted executable Motion candidate; no redundant selector call required.','tradeoffs':[],'rejected_alternatives':[],'notes':'Deterministic accepted executable commit.'}
        else:
            sel=self.reasoner.select(self.sr.state['production_id'],story,developed['reviewed']);item=next((x for x in eligible if x['candidate']['candidate_id']==sel['selected_candidate_id']),None)
            if item is None: raise ContractViolation('selected Motion candidate is missing, non-executable, or not Producer-accepted')
        self.sr.commit_p6_reviewed(item['ref'],item['review_id'],require_diversity_from=None if surgical else [x['ref'].proposal_id for x in developed['reviewed']]);return {**item,'selection':sel}
    def compile_performance_storyboard(self,temporal_board,motion_item):
        board=self.storyboard.compile(temporal_board,motion_item['candidate']);gate=self.storyboard.gate(board);return {'board':board,'gate':gate}
