from __future__ import annotations
from copy import deepcopy
from typing import Any,Dict
from concurrent.futures import ThreadPoolExecutor
import os
from .cinematography_director import CinematographyDirector
from .editorial_director import EditorialRhythmDirector
from .editorial_timeline import EditorialTimelineCompiler
from .p45_producer import P45ExecutiveProducer
from .p45_showrunner_reasoner import P45ShowrunnerDecisionIntelligence
from .storyboard_compiler_v2 import TemporalStoryboardCompiler
from .showrunner_p45 import NexMindSupremeShowrunnerP45
from .contracts import ContractViolation


def _parallel(items,fn,prefix):
    items=list(items)
    try: configured=int(os.getenv('NEXMIND_REVIEW_PARALLELISM','3') or 3)
    except Exception: configured=3
    workers=max(1,min(len(items),6,max(1,configured)))
    if len(items)<=1 or workers<=1:return [fn(x) for x in items]
    with ThreadPoolExecutor(max_workers=workers,thread_name_prefix=prefix) as pool:
        futures=[pool.submit(fn,x) for x in items]
        return [f.result() for f in futures]


def _surgical(sr,department,reviewed):
    ctx=sr.state.get('brief',{}).get('autonomous_revision_context') or {}
    return ctx.get('department')==department and ctx.get('repair_mode')!='MATERIAL_STRATEGY_REPLAN' and len(reviewed)==1

class CreativeCouncilP45:
    def __init__(self,sr:NexMindSupremeShowrunnerP45,cinema:CinematographyDirector,editorial:EditorialRhythmDirector,producer:P45ExecutiveProducer,reasoner:P45ShowrunnerDecisionIntelligence,timeline:EditorialTimelineCompiler,storyboard:TemporalStoryboardCompiler):
        self.sr=sr; self.cinema=cinema; self.editorial=editorial; self.producer=producer; self.reasoner=reasoner; self.timeline=timeline; self.storyboard=storyboard
    def develop_cinema(self,story,visual,art,key_board):
        cs=self.cinema.propose(self.sr.state['production_id'],self.sr.state['brief'],story,visual,art,key_board,self.sr.state.get('creative_doctrine',{}))
        prepared=[];refs=[]
        for c in cs:
            proposal_payload={'representation':'CINEMATOGRAPHY_PLAN','visual_thesis':c['cinema_thesis'],'hero_kind':c['shots'][0]['subject_target'],'transformation':' -> '.join(x['idiom'] for x in c['shots']),'camera_idea':' | '.join(x['camera_atom']['atom']+':'+x['subject_target'] for x in c['shots']),'cinematography':deepcopy(c)}
            proposal_id=c['candidate_id']
            if proposal_id in self.sr.state.get('proposals',{}).get('CinematographyDirector',{}):proposal_id=f"r{self.sr.state['revision']}:{proposal_id}"
            ref=self.sr.submit_proposal('CinematographyDirector',proposal_id,proposal_payload);refs.append(ref);prepared.append((c,ref))
        def review_one(item):
            c,ref=item
            return c,ref,self.producer.review_cinema(self.sr.state['production_id'],self.sr.state['brief'],story,visual,art,c)
        reviewed=[]
        for c,ref,r in _parallel(prepared,review_one,'nexmind-cinema-review'):
            token=self.sr.register_p45_review('cinematography',ref,r);reviewed.append({'candidate':c,'review':r,'ref':ref,'review_id':token})
        surgical=_surgical(self.sr,'CINEMATOGRAPHY',reviewed)
        div={'meaningfully_diverse':True,'surgical_repair':True} if surgical else self.sr.candidate_diversity('CinematographyDirector',[x.proposal_id for x in refs])
        return {'reviewed':reviewed,'diversity':div}
    def select_cinema(self,story,developed):
        accepted=[x for x in developed['reviewed'] if x['review']['verdict']=='ACCEPT']
        if not accepted: raise RuntimeError('cinematography selection requires Producer-accepted work')
        surgical=_surgical(self.sr,'CINEMATOGRAPHY',developed['reviewed'])
        if len(accepted)==1:
            item=accepted[0];sel={'selected_candidate_id':item['candidate']['candidate_id'],'why':'Only Producer-accepted Cinematography candidate; no redundant selector call required.','tradeoffs':[],'rejected_alternatives':[],'notes':'Deterministic accepted commit.'}
        else:
            sel=self.reasoner.select_cinema(self.sr.state['production_id'],story,developed['reviewed']);item=next((x for x in accepted if x['candidate']['candidate_id']==sel['selected_candidate_id']),None)
            if item is None: raise ContractViolation('selected Cinematography candidate is missing or not Producer-accepted')
        self.sr.commit_p45_reviewed('cinematography',item['ref'],item['review_id'],require_diversity_from=None if surgical else [x['ref'].proposal_id for x in developed['reviewed']])
        self.sr.state['film_memory']['camera_grammar_used'].append({'revision':self.sr.state['revision'],'candidate_id':item['candidate']['candidate_id'],'idioms':[s['idiom'] for s in item['candidate']['shots']]})
        return {**item,'selection':sel}
    def develop_editorial(self,story,visual,art,cinema,*,target_duration_frames,project_rate):
        cs=self.editorial.propose(self.sr.state['production_id'],self.sr.state['brief'],story,visual,art,cinema,target_duration_frames=target_duration_frames,project_rate=project_rate)
        prepared=[];refs=[]
        for c in cs:
            timeline=self.timeline.compile(c)
            proposal_payload={'representation':'EDITORIAL_TIMELINE','visual_thesis':c['editorial_thesis'],'hero_kind':c['rhythm_profile'],'transformation':' | '.join(f"{x['role']}:{x['duration']['value']}:{x['energy']}" for x in c['beats']),'camera_idea':cinema['candidate_id'],'editorial_rhythm':deepcopy(c),'editorial_timeline':deepcopy(timeline)}
            proposal_id=c['candidate_id']
            if proposal_id in self.sr.state.get('proposals',{}).get('EditorialRhythmDirector',{}):proposal_id=f"r{self.sr.state['revision']}:{proposal_id}"
            ref=self.sr.submit_proposal('EditorialRhythmDirector',proposal_id,proposal_payload);refs.append(ref);prepared.append((c,timeline,ref))
        def review_one(item):
            c,timeline,ref=item
            return c,timeline,ref,self.producer.review_editorial(self.sr.state['production_id'],self.sr.state['brief'],story,cinema,c,timeline)
        reviewed=[]
        for c,timeline,ref,r in _parallel(prepared,review_one,'nexmind-editorial-review'):
            token=self.sr.register_p45_review('editorial_rhythm',ref,r);reviewed.append({'candidate':c,'timeline':timeline,'review':r,'ref':ref,'review_id':token})
        surgical=_surgical(self.sr,'EDITORIAL_RHYTHM',reviewed)
        div={'meaningfully_diverse':True,'surgical_repair':True} if surgical else self.sr.candidate_diversity('EditorialRhythmDirector',[x.proposal_id for x in refs])
        return {'reviewed':reviewed,'diversity':div}
    def select_editorial(self,story,developed):
        accepted=[x for x in developed['reviewed'] if x['review']['verdict']=='ACCEPT']
        if not accepted: raise RuntimeError('editorial selection requires Producer-accepted work')
        surgical=_surgical(self.sr,'EDITORIAL_RHYTHM',developed['reviewed'])
        if len(accepted)==1:
            item=accepted[0];sel={'selected_candidate_id':item['candidate']['candidate_id'],'why':'Only Producer-accepted Editorial candidate; no redundant selector call required.','tradeoffs':[],'rejected_alternatives':[],'notes':'Deterministic accepted commit.'}
        else:
            sel=self.reasoner.select_editorial(self.sr.state['production_id'],story,developed['reviewed']);item=next((x for x in accepted if x['candidate']['candidate_id']==sel['selected_candidate_id']),None)
            if item is None: raise ContractViolation('selected Editorial candidate is missing or not Producer-accepted')
        self.sr.commit_p45_reviewed('editorial_rhythm',item['ref'],item['review_id'],require_diversity_from=None if surgical else [x['ref'].proposal_id for x in developed['reviewed']])
        return {**item,'selection':sel}
    def compile_temporal_storyboard(self,story,key_board,cinema_item,editorial_item):
        board=self.storyboard.compile(key_board,cinema_item['candidate'],editorial_item['candidate'],editorial_item['timeline'])
        gate=self.storyboard.gate(board)
        proposal_payload={'representation':'CANONICAL_TEMPORAL_STORYBOARD','visual_thesis':story['film_thesis']['central_argument'],'hero_kind':board['beats'][0]['hero_identity'] if board['beats'] else 'none','transformation':'temporal key-state progression with directed camera and editorial rhythm','camera_idea':cinema_item['candidate']['cinema_thesis'],'storyboard_temporal':deepcopy(board)}
        ref=self.sr.submit_proposal('StoryboardCompilerV2','storyboard-temporal-r'+str(self.sr.state['revision']),proposal_payload)
        review=self.producer.review_temporal_storyboard(self.sr.state['production_id'],self.sr.state['brief'],story,board,gate)
        token=self.sr.register_p45_review('storyboard_temporal',ref,review)
        if review['verdict']=='ACCEPT':self.sr.commit_p45_reviewed('storyboard_temporal',ref,token)
        return {'board':board,'gate':gate,'review':review,'ref':ref,'review_id':token}
