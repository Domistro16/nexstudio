from __future__ import annotations
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import os
from .contracts import ContractViolation

def _parallel(items,fn):
    items=list(items)
    try:configured=int(os.getenv('NEXMIND_REVIEW_PARALLELISM','3') or 3)
    except Exception:configured=3
    workers=max(1,min(len(items),6,max(1,configured)))
    if len(items)<=1 or workers<=1:return [fn(x) for x in items]
    with ThreadPoolExecutor(max_workers=workers,thread_name_prefix='nexmind-sound-review') as pool:
        fs=[pool.submit(fn,x) for x in items];return [f.result() for f in fs]

def _surgical(sr,reviewed):
    ctx=sr.state.get('brief',{}).get('autonomous_revision_context') or {}
    return ctx.get('department')=='SOUND_DIRECTION' and ctx.get('repair_mode')!='MATERIAL_STRATEGY_REPLAN' and len(reviewed)==1

class CreativeCouncilP7:
    def __init__(self,sr,sound,producer,reasoner,storyboard):self.sr=sr;self.sound=sound;self.producer=producer;self.reasoner=reasoner;self.storyboard=storyboard
    def develop(self,story,editorial,motion,performance_board):
        cs=self.sound.propose(self.sr.state['production_id'],self.sr.state['brief'],story,editorial,motion,performance_board,self.sr.state.get('creative_doctrine',{}));prepared=[];refs=[]
        for c in cs:
            pp={'representation':'SOUND_DIRECTION_PLAN','visual_thesis':c['sound_thesis'],'hero_kind':c['music_strategy']['mode'],'transformation':' | '.join(e['kind']+':'+e['semantic_tag'] for e in c['events']),'camera_idea':'sound follows committed editorial and motion','sound_direction':deepcopy(c)}
            proposal_id=c['candidate_id'];proposal_id=(f"r{self.sr.state['revision']}:{proposal_id}" if proposal_id in self.sr.state.get('proposals',{}).get('SoundDirector',{}) else proposal_id);ref=self.sr.submit_proposal('SoundDirector',proposal_id,pp);refs.append(ref);prepared.append((c,ref))
        def review_one(item):
            c,ref=item;return c,ref,self.producer.review(self.sr.state['production_id'],self.sr.state['brief'],story,c)
        reviewed=[]
        for c,ref,r in _parallel(prepared,review_one):
            tok=self.sr.register_p7_review(ref,r);reviewed.append({'candidate':c,'review':r,'ref':ref,'review_id':tok})
        surgical=_surgical(self.sr,reviewed);div={'meaningfully_diverse':True,'surgical_repair':True} if surgical else self.sr.candidate_diversity('SoundDirector',[x.proposal_id for x in refs])
        return {'reviewed':reviewed,'diversity':div}
    def select(self,story,developed):
        eligible=[x for x in developed['reviewed'] if x['review']['verdict']=='ACCEPT' and x['candidate'].get('executable_resource_plan')]
        if not eligible:raise RuntimeError('sound selection requires Producer-accepted executable work')
        surgical=_surgical(self.sr,developed['reviewed'])
        if len(eligible)==1:
            item=eligible[0];sel={'selected_candidate_id':item['candidate']['candidate_id'],'why':'Only Producer-accepted executable Sound candidate; no redundant selector call required.','tradeoffs':[],'rejected_alternatives':[],'notes':'Deterministic accepted executable commit.'}
        else:
            sel=self.reasoner.select(self.sr.state['production_id'],story,developed['reviewed']);item=next((x for x in eligible if x['candidate']['candidate_id']==sel['selected_candidate_id']),None)
            if item is None: raise ContractViolation('selected Sound candidate is missing, non-executable, or not Producer-accepted')
        self.sr.commit_p7_reviewed(item['ref'],item['review_id'],require_diversity_from=None if surgical else [x['ref'].proposal_id for x in developed['reviewed']]);return {**item,'selection':sel}
    def compile_sound_storyboard(self,performance_board,sound_item):
        board=self.storyboard.compile(performance_board,sound_item['candidate']);return {'board':board,'gate':self.storyboard.gate(board)}
