from __future__ import annotations
import copy
import importlib.util
import json
import pathlib
import sys
import threading

ROOT=pathlib.Path(__file__).resolve().parents[1]
VENDOR=ROOT/'vendor'/'nexmind-god-mode-p8'
sys.path.insert(0,str(VENDOR/'src'))
sys.path.insert(0,str(VENDOR/'tests'))
sys.path.insert(0,str(ROOT/'services'/'studio-nexmind-p8'))

import orchestrator as orch
import capability_adapter
from nexmind_god_mode.provider import ProviderError
from nexmind_god_mode.live_provider import LiveCreativeModelProvider
from nexmind_god_mode.contracts import ContractViolation
from nexmind_god_mode.cinema_contracts import validate_cinema_output, validate_cinema_candidate
from nexmind_god_mode.editorial_contracts import validate_editorial_output, validate_editorial_candidate
from nexmind_god_mode.motion_contracts import validate_motion_output
from nexmind_god_mode.sound_contracts import validate_sound_output
from nexmind_god_mode.performer_capabilities import PerformerCapabilityRegistry
from nexmind_god_mode.sound_resources import SoundResourceRegistry
from test_p3_art_storyboard import art_candidate
from test_p45_cinema_editorial import cinema_candidate
from test_p6_motion_performance import candidate as motion_candidate
from test_p7_sound import cand as sound_candidate

PREFLIGHT_PATH=ROOT/'scripts'/'run-nexmind-autonomy-blind-preflight.py'
spec=importlib.util.spec_from_file_location('nexmind_blind_preflight',PREFLIGHT_PATH)
preflight=importlib.util.module_from_spec(spec); spec.loader.exec_module(preflight)
SOUND_INDEX=VENDOR/'donors'/'authorized_sound_index.json'


def story_variant(v:int):
    if v==1:
        arg='Precise heat feels human when the cooktop visibly responds to one small cooking decision at a time.'
        hero='portable induction cooktop and the cook using it'
        cam='Stay close to the cooktop and food; tighten only when a tiny heat change creates a visible cooking consequence.'
        payoff='End on the same pan now calm and exactly where the cook wants it, making control feel intuitive rather than technical.'
        traj=['restless pan state','small human adjustment','visible controlled response']
        reveals=['A pan threatens to run too hot while the cook watches, making the need for control immediate.','One deliberate heat adjustment changes the food response without a feature-list cutaway.','The pan settles into the intended cooking state and the cook continues confidently.']
    else:
        arg='The product disappears into the cooking rhythm when exact heat control answers human instinct immediately.'
        hero='the cook hand, pan, and portable induction surface as one causal system'
        cam='Observe one continuous cooking moment, moving attention from hand to pan consequence and back to the person.'
        payoff='Resolve with the cook no longer thinking about settings—only the food—because the surface obeyed the intended change.'
        traj=['human instinct','surface response','effortless cooking rhythm']
        reveals=['The cook senses the pan needs less aggression before anything is ruined.','A subtle adjustment produces a readable change in the pan behavior while the same cooking moment continues.','The cook returns attention to the meal as the heat stays controlled without technical spectacle.']
    beats=[]
    purposes=['setup','cause-and-effect','payoff']
    before=['control feels abstract','heat adjustment could feel like a number','precise control still feels technical']
    after=['control is a human cooking need','a small input has a useful visible consequence','precision feels natural and useful']
    for i in range(3):
        beats.append({
            'beat_id':f'B{i+1}','purpose':purposes[i],
            'question':['Why does precision matter?','What does the adjustment actually change?','What does good control feel like?'][i],
            'audience_before':before[i],'audience_after':after[i],'reveal':reveals[i],
            'required_claim_ids':['USER-BRIEF-1'],
            'hero_state':['cooktop under a pan approaching an unwanted cooking state','same cooktop receives one intentional heat adjustment','same cooktop holds the pan in a calm desired state'][i],
            'narration_mode':'SILENT','narration_text':'','narration_purpose':'let the physical cooking consequence carry the argument',
        })
    return {'film_thesis':{
        'central_argument':arg,'film_kind':'human product explainer',
        'audience_before':'precise heat control sounds like a specification',
        'audience_after':'precise heat control feels like a useful human cooking advantage',
        'emotional_trajectory':['recognition','relief','confidence'],'visual_trajectory':traj,
        'opening_contract':'Begin inside one recognizable cooking problem, not with a product feature card.',
        'final_payoff':payoff,'anti_goals':['no feature list','no dashboard tiles','no generic spec montage'],
        'tone':'warm precise useful','hero_kind':hero,'camera_idea':cam,
    },'beats':beats,'story_notes':['Keep the product inside one causal human cooking moment.']}


def visual_variant(cid:str,v:int):
    if v==1:
        hero='recognizable portable induction cooktop with one pan and cook hand'; trans='an unruly pan response settles into visibly controlled cooking after one human adjustment'; cam='hold the cooktop as anchor, tighten briefly on the pan response, return to the person'; thesis='One continuous pan becomes a readable heat-response portrait: agitation, adjustment, calm.'
        actions=['establish one slightly unruly pan on the same cooktop','show one small adjustment and an immediate but plausible change in cooking behavior','settle on the controlled pan as the cook resumes naturally']
    elif v==2:
        hero='cook hand, induction surface, and pan as one tactile causal chain'; trans='a human gesture travels into a quieter, more exact pan state without exposing a feature list'; cam='observe hand to surface to pan as one continuous attention handoff'; thesis='Treat precision as a tactile conversation between hand, surface, and food rather than as a numerical feature.'
        actions=['begin with the cook reading the food rather than the controls','carry attention through one deliberate heat change into the pan','finish with the hand leaving the control because the food now behaves correctly']
    else:
        hero='portable cooktop as a calm stage for one demanding pan moment'; trans='visual tension compresses from noisy heat behavior into a clean stable cooking state'; cam='use a stable tableau with one motivated close inspection, then restore the whole cooking station'; thesis='Make exact control visible as the removal of cooking noise: the same world becomes calmer, not more technical.'
        actions=['frame a busy pan state against a calm minimal cooktop stage','let only the cooking behavior change after a precise adjustment','resolve in a quiet whole-station tableau with the desired state sustained']
    return {'candidate_id':cid,'representation':'AUTHORED_ILLUSTRATION','visual_thesis':thesis,'hero_kind':hero,'transformation':trans,'camera_idea':cam,
        'rationale':'The concept makes heat control legible through a human cooking consequence instead of listing features.',
        'beat_treatments':[{'beat_id':f'B{i+1}','hero_state':['pan approaching unwanted heat behavior','same pan during one intentional adjustment','same pan in desired controlled state'][i],'visual_action':actions[i],'audience_takeaway':['precision matters in a real cooking moment','small control changes create useful physical consequences','good control feels effortless and human'][i]} for i in range(3)]}


def editorial30(cid:str,v:int=1):
    rate=30;total=900
    specs=([('B1','SETUP',0,250,50,180,'LOW',70,25,'CUT'),('B2','CONTROL',225,400,80,300,'PEAK',75,25,'MATCH_CUT'),('B3','PAYOFF',600,300,50,190,'MEDIUM',110,0,'HOLD_THROUGH')]
           if v==1 else [('B1','READ',0,300,55,220,'MEDIUM',80,0,'CUT'),('B2','RESPOND',300,330,70,235,'MEDIUM',95,0,'CUT'),('B3','RESOLVE',630,270,45,170,'MEDIUM',100,0,'HOLD_THROUGH')])
    beats=[]
    for bid,role,start,dur,action,settle,energy,still,overlap,tx in specs:
        beats.append({'beat_id':bid,'role':role,'start':{'value':start,'rate':rate},'duration':{'value':dur,'rate':rate},'action_frame':action,'settle_frame':settle,'energy':energy,'stillness_frames':still,'overlap_to_next_frames':overlap,'transition':tx,'duration_rationale':f'{role} receives {dur} frames because its narrative job differs from adjacent beats.'})
    return {'candidate_id':cid,'editorial_thesis':f'Pacing strategy {v} prioritizes the human control moment and a readable payoff.','project_rate':rate,'target_duration_frames':total,'rhythm_profile':'TENSION_ADJUST_SETTLE' if v==1 else 'OBSERVE_RESPOND_RESOLVE','peak_budget':2,'beats':beats,'final_payoff_hold_frames':90,'risk_notes':[]}


class FlowProvider:
    def __init__(self,fail_once_task=None):
        self.calls=[];self.fail_once_task=fail_once_task;self.failed=False;self._lock=threading.Lock()
    def audit_dicts(self): return []
    def _maybe_fail(self,task):
        with self._lock:
            if self.fail_once_task==task and not self.failed:
                self.failed=True
                raise ProviderError('transport: injected transient timeout')
    def complete(self,task,request):
        # Mirror the real provider boundary: every model request must be plain JSON.
        # Internal authority objects (e.g. ProposalRef) must never leak into provider payloads.
        json.dumps(request, sort_keys=True, ensure_ascii=False)
        with self._lock: self.calls.append((task,copy.deepcopy(request)))
        self._maybe_fail(task)
        if task=='story':
            with self._lock: idx=sum(1 for t,_ in self.calls if t=='story')
            return story_variant(1 if idx%2 else 2)
        if task=='visual':
            cs=[visual_variant('V-COMPUTER-1',1),visual_variant('V-HAND-2',2),visual_variant('V-CALM-3',3)]
            return {'candidates':cs[:max(1,int(request.get('candidate_budget') or len(cs)))]}
        if task=='producer': return {'verdict':'ACCEPT','issues':[],'strengths':['brief-specific causal human product argument'],'revision_brief':'','commercial_confidence':'HIGH'}
        if task=='showrunner_select': return self._select(request)
        if task=='art':
            cs=[art_candidate('A1','cutaway-monument'),art_candidate('A2','hero-and-macro-inset',' alternate')]
            for c in cs:c['visual_candidate_id']='V-COMPUTER-1'
            return {'candidates':cs[:max(1,int(request.get('candidate_budget') or len(cs)))]}
        if task in {'art_review','storyboard_review','cinematography_review','editorial_review','temporal_storyboard_review','motion_review','sound_review'}:
            return {'verdict':'ACCEPT','issues':[],'strengths':['clear executable hierarchy'],'revision_brief':'','commercial_confidence':'HIGH'}
        if task.startswith('showrunner_select'): return self._select(request)
        if task=='cinematography':
            cs=[cinema_candidate('C1',1),cinema_candidate('C2',2)]
            return {'candidates':cs[:max(1,int(request.get('candidate_budget') or len(cs)))]}
        if task=='editorial_rhythm':
            cs=[editorial30('E1',1),editorial30('E2',2)]
            return {'candidates':cs[:max(1,int(request.get('candidate_budget') or len(cs)))]}
        if task=='motion_performance':
            cs=[motion_candidate('M1',1),motion_candidate('M2',2)]
            return {'candidates':cs[:max(1,int(request.get('candidate_budget') or len(cs)))]}
        if task=='sound_direction':
            cs=[sound_candidate('S1',1),sound_candidate('S2',2)]
            return {'candidates':cs[:max(1,int(request.get('candidate_budget') or len(cs)))]}
        raise RuntimeError('unhandled synthetic task '+task)
    @staticmethod
    def _select(request):
        rows=request.get('candidates') or [];ids=[]
        for row in rows:
            if not isinstance(row,dict): continue
            c=row.get('candidate') if isinstance(row.get('candidate'),dict) else None
            rv=row.get('review') or row.get('producer_review') or {}
            if c and rv.get('verdict')=='ACCEPT': ids.append(c['candidate_id'])
        if not ids:
            ids=[(row.get('candidate') or {}).get('candidate_id') for row in rows if isinstance(row,dict) and (row.get('candidate') or {}).get('candidate_id')]
        ch=ids[0]
        return {'selected_candidate_id':ch,'why':'Best executable causal option for this synthetic control-flow proof.','tradeoffs':['Another accepted option emphasizes a different valid strategy.'],'rejected_alternatives':[{'candidate_id':x,'reason':'Valid but less direct for this proof.'} for x in ids if x!=ch]}


class StoryboardThesisRejectOnceProvider(FlowProvider):
    def __init__(self):super().__init__();self.storyboard_reviews=0
    def complete(self,task,request):
        if task=='storyboard_review':
            with self._lock:
                self.calls.append((task,copy.deepcopy(request)));self.storyboard_reviews+=1;n=self.storyboard_reviews
            self._maybe_fail(task)
            if n==1:
                return {
                    'verdict':'REVISE',
                    'issues':[{'severity':'MAJOR','area':'Film thesis and payoff','finding':'The still key states do not make the accepted Film Thesis and payoff visually legible.','required_change':'Strengthen the visual hero progression so the accepted thesis reads before motion.'}],
                    'strengths':['Story causality is coherent; the realization needs a clearer visual read.'],
                    'revision_brief':'Repair the visual realization of the accepted thesis and payoff. Story itself is not contradicted.',
                    'commercial_confidence':'MEDIUM',
                }
            return {'verdict':'ACCEPT','issues':[],'strengths':['clear executable hierarchy'],'revision_brief':'','commercial_confidence':'HIGH'}
        return super().complete(task,request)


class StoryAttempt2ThenStoryboardRejectProvider(FlowProvider):
    """Reproduce the live trace: Story uses 2/2, then downstream Storyboard rejects."""
    def __init__(self):
        super().__init__();self.story_producer_reviews=0;self.storyboard_reviews=0
    def complete(self,task,request):
        if task=='producer' and (request.get('instruction') or {}).get('review_scope')=='STORY':
            with self._lock:
                self.calls.append((task,copy.deepcopy(request)));self.story_producer_reviews+=1;n=self.story_producer_reviews
            self._maybe_fail(task)
            if n<=2:
                return {'verdict':'REVISE','issues':[{'severity':'MODERATE','area':'Story clarity','finding':'The first Story competition needs a tighter causal throughline.','required_change':'Repair the selected Story anchor into one clearer causal progression.'}],'strengths':['brief-specific human premise'],'revision_brief':'Tighten the causal progression without reopening competition.','commercial_confidence':'MEDIUM'}
            return {'verdict':'ACCEPT','issues':[],'strengths':['clear causal Story'],'revision_brief':'','commercial_confidence':'HIGH'}
        if task=='storyboard_review':
            with self._lock:
                self.calls.append((task,copy.deepcopy(request)));self.storyboard_reviews+=1;n=self.storyboard_reviews
            self._maybe_fail(task)
            if n==1:
                return {'verdict':'REVISE','issues':[{'severity':'MAJOR','area':'Film thesis and payoff','finding':'The storyboard key states do not make the accepted thesis and payoff visually legible enough.','required_change':'Repair the visual hero progression and settled-state hierarchy; the accepted Story itself is coherent.'}],'strengths':['accepted Story causality remains coherent'],'revision_brief':'Strengthen the visual realization of the accepted Story without reopening Story.','commercial_confidence':'MEDIUM'}
            return {'verdict':'ACCEPT','issues':[],'strengths':['clear executable hierarchy'],'revision_brief':'','commercial_confidence':'HIGH'}
        return super().complete(task,request)


class VisualExhaustAfterStoryboardProvider(StoryAttempt2ThenStoryboardRejectProvider):
    """Exact user trace: accepted Story 2/2, Storyboard sends repair to Visual, Visual 3/3 exhausts.

    The corrected law must open a fresh VISUAL_CONCEPT lineage against the same Story,
    never climb to Story merely because Visual used its local attempts.
    """
    def __init__(self):
        super().__init__();self.visual_surgical_reviews=0
    def complete(self,task,request):
        if task=='storyboard_review':
            with self._lock:
                self.calls.append((task,copy.deepcopy(request)));self.storyboard_reviews+=1;n=self.storyboard_reviews
            self._maybe_fail(task)
            if n==1:
                return {
                    'verdict':'REVISE',
                    'issues':[{'code':'GENERIC_STORYBOARD','owner_department':'VISUAL_CONCEPT','severity':'MAJOR','area':'Visual realization','finding':'The accepted Story is coherent but the key-state visual strategy is generic and does not communicate it strongly enough.','required_change':'Replan Visual Concept against the accepted Story; do not reopen Story.'}],
                    'strengths':['accepted Story causality remains coherent'],
                    'revision_brief':'Repair Visual Concept only; Story is accepted and not contradicted.',
                    'commercial_confidence':'MEDIUM',
                }
            return {'verdict':'ACCEPT','issues':[],'strengths':['clear executable hierarchy'],'revision_brief':'','commercial_confidence':'HIGH'}
        if task=='producer' and (request.get('instruction') or {}).get('review_scope')=='VISUAL_CONCEPT':
            rev=request.get('revision_context') or {}
            if rev.get('department')=='VISUAL_CONCEPT' and rev.get('repair_mode')!='MATERIAL_STRATEGY_REPLAN':
                with self._lock:
                    self.calls.append((task,copy.deepcopy(request)));self.visual_surgical_reviews+=1;n=self.visual_surgical_reviews
                self._maybe_fail(task)
                if n<=2:
                    return {
                        'verdict':'REVISE',
                        'issues':[{'severity':'MAJOR','area':'Visual realization','finding':'The repaired visual strategy still does not make the accepted Story legible enough.','required_change':'Change the visual strategy materially while preserving the accepted Story.'}],
                        'strengths':['accepted Story remains coherent'],
                        'revision_brief':'Repair Visual Concept only; do not reopen Story.',
                        'commercial_confidence':'MEDIUM',
                    }
        return super().complete(task,request)


class EditorialTimingDriftProvider(FlowProvider):
    """Return creatively valid Editorial plans with deliberately broken frame arithmetic.

    Runtime normalization must repair start accounting and out-of-beat action/settle
    markers deterministically in the same Director call.
    """
    def complete(self,task,request):
        if task=='editorial_rhythm':
            with self._lock:
                self.calls.append((task,copy.deepcopy(request)))
            self._maybe_fail(task)
            cs=[editorial30('E-DRIFT-1',1),editorial30('E-DRIFT-2',2)]
            for idx,c in enumerate(cs):
                c['project_rate']=24
                c['target_duration_frames']=777
                for j,b in enumerate(c['beats']):
                    b['start']={'value':17+(j*113),'rate':24}
                    b['duration']['rate']=24
                    # Preserve action-before-settle intent but put both outside the beat.
                    raw=max(1,int(b['duration']['value']))
                    b['action_frame']=raw+20+idx
                    b['settle_frame']=raw+60+idx
                c['final_payoff_hold_frames']=999
            return {'candidates':cs[:max(1,int(request.get('candidate_budget') or len(cs)))]}
        return super().complete(task,request)


class StoryDiversityProvider(FlowProvider):
    def __init__(self): super().__init__();self.story_invocations=0
    def complete(self,task,request):
        if task=='story':
            with self._lock:
                self.calls.append((task,copy.deepcopy(request)));self.story_invocations+=1;n=self.story_invocations
            self._maybe_fail(task)
            if n<=2:return story_variant(1)  # deliberately duplicate initial competition
            return story_variant(1 if n%2 else 2)
        return super().complete(task,request)


class VisualDiversityProvider(FlowProvider):
    def __init__(self):super().__init__();self.visual_invocations=0
    def complete(self,task,request):
        if task=='visual':
            with self._lock:
                self.calls.append((task,copy.deepcopy(request)));self.visual_invocations+=1;n=self.visual_invocations
            self._maybe_fail(task)
            if n==1:
                a=visual_variant('V-COMPUTER-1',1);b=copy.deepcopy(a);c=copy.deepcopy(a);b['candidate_id']='V-DUP-2';c['candidate_id']='V-DUP-3'
                return {'candidates':[a,b,c]}
            return {'candidates':[visual_variant('V-COMPUTER-1',1),visual_variant('V-HAND-2',2),visual_variant('V-CALM-3',3)]}
        return super().complete(task,request)


class MalformedArtOnceProvider(FlowProvider):
    def __init__(self):super().__init__();self.art_invocations=0
    def complete(self,task,request):
        if task=='art':
            with self._lock:
                self.calls.append((task,copy.deepcopy(request)));self.art_invocations+=1;n=self.art_invocations
            self._maybe_fail(task)
            if n==1:
                cs=[art_candidate('A1','cutaway-monument'),art_candidate('A2','hero-and-macro-inset',' alternate')]
                for c in cs:c['visual_candidate_id']='V-COMPUTER-1'
                cs[0]['beat_art']=cs[0]['beat_art'][:-1]
                return {'candidates':cs}
            cs=[art_candidate('A1','cutaway-monument'),art_candidate('A2','hero-and-macro-inset',' alternate')]
            for c in cs:c['visual_candidate_id']='V-COMPUTER-1'
            return {'candidates':cs}
        return super().complete(task,request)


class InvalidSelectorOnceProvider(FlowProvider):
    def __init__(self):super().__init__();self.invalid_sent=False
    def complete(self,task,request):
        if task=='showrunner_select_cinematography' and not self.invalid_sent:
            with self._lock:self.calls.append((task,copy.deepcopy(request)));self.invalid_sent=True
            return {'selected_candidate_id':'NOT-A-CANDIDATE','why':'Injected malformed selector result.','tradeoffs':['fault injection'],'rejected_alternatives':[]}
        return super().complete(task,request)


REQ={'productionId':'FINAL-FLOW-B01','family':'EXPLAINER','durationSeconds':30,'brief':'A portable induction cooktop brand wants a 30-second film that makes precise heat control feel surprisingly human and useful, without turning into a feature list.'}

checks=[]
def add(name,ok,detail=''):
    checks.append({'name':name,'status':'PASS' if ok else 'FAIL','detail':str(detail or '')})


def run():
    # 1. Direct-preflight family authority must be bound, not {}.
    packet=capability_adapter.load_current_capability_packet();graph=capability_adapter.build_capability_graph(REQ,packet);auth=graph['current_authorities']['family_execution_body']
    add('Explainer direct preflight binds frozen family execution authority',auth.get('authorityId')=='EXPLAINER_EXECUTION_BODY_V2_P8_UNIFIED',auth)

    # 2. Live schemas agree with surgical repair for every multi-candidate Director.
    lp=LiveCreativeModelProvider()
    for task in ['visual','art','cinematography','editorial_rhythm','motion_performance','sound_direction']:
        schema=lp._schema_for_request(task,{'repair_anchor':{'candidate_id':'ANCHOR'},'candidate_budget':1})
        arr=schema['properties']['candidates']
        add(f'{task} live schema surgical repair is exactly one candidate',arr.get('minItems')==1 and arr.get('maxItems')==1,arr)
    for task,budget in [('visual',3),('art',2),('cinematography',2),('editorial_rhythm',2),('motion_performance',2),('sound_direction',2)]:
        schema=lp._schema_for_request(task,{'candidate_budget':budget})
        arr=schema['properties']['candidates']
        add(f'{task} initial live schema matches runtime candidate budget',arr.get('minItems')==budget and arr.get('maxItems')==budget,arr)

    # 3. Selector output is schema-bound to Producer-accepted candidates.
    ss=lp._schema_for_request('showrunner_select_sound',{'candidates':[{'candidate':{'candidate_id':'S1'},'review':{'verdict':'ACCEPT'}},{'candidate':{'candidate_id':'S2'},'review':{'verdict':'REVISE'}}]})
    add('Showrunner selector schema forbids rejected/missing candidate IDs',ss['properties']['selected_candidate_id'].get('enum')==['S1'],ss['properties']['selected_candidate_id'])
    try:
        lp._validate_schema_node('',{'type':'string','minLength':1}); minlen=False
    except ProviderError:
        minlen=True
    add('Prompt-JSON local schema validator enforces minLength',minlen)

    # 4. Execution contracts match the one-binding-per-beat temporal body.
    c=cinema_candidate('C1',1)
    try: validate_cinema_output({'candidates':[c]}, {'B1','B2','B3'},'computer.hero',repair_mode=True); one_cinema=True
    except Exception as e: one_cinema=False
    add('Cinematography surgical contract accepts one anchored candidate',one_cinema)
    try:
        bad=copy.deepcopy(c);bad['shots'].append(copy.deepcopy(bad['shots'][0]));validate_cinema_candidate(bad,{'B1','B2','B3'},'computer.hero');dup=False
    except ContractViolation:dup=True
    add('Cinematography rejects multiple executable shot bindings for one beat',dup)
    e=editorial30('E1',1)
    try:validate_editorial_output({'candidates':[e]}, {'B1','B2','B3'},repair_mode=True);one_edit=True
    except Exception:one_edit=False
    add('Editorial surgical contract accepts one anchored candidate',one_edit)
    try:
        bad=copy.deepcopy(e);bad['beats'].append(copy.deepcopy(bad['beats'][0]));validate_editorial_candidate(bad,{'B1','B2','B3'});dup=False
    except ContractViolation:dup=True
    add('Editorial rejects multiple executable edit bindings for one beat',dup)
    try:validate_motion_output({'candidates':[motion_candidate('M1',1)]},{'B1','B2','B3'},repair_mode=True);one_motion=True
    except Exception:one_motion=False
    add('Motion surgical contract accepts one anchored candidate',one_motion)
    try:validate_sound_output({'candidates':[sound_candidate('S1',1)]},{'B1','B2','B3'},repair_mode=True);one_sound=True
    except Exception:one_sound=False
    add('Sound surgical contract accepts one anchored candidate',one_sound)

    # 5. Directors see only executable performer/sound vocabularies.
    perf=PerformerCapabilityRegistry().model_view();snd=SoundResourceRegistry.from_file(SOUND_INDEX).model_view()
    add('Motion Director model view exposes admitted performer primitives','WALK' in perf['performers']['STICKMAN_V2']['supported'])
    add('Sound Director model view exposes authorized semantic tags','object.place' in snd['authorized_semantic_tags'])

    # 6. Causal owner routing cannot be hijacked by beat_id metadata.
    add('beat_id camera issue routes to Cinematography, not Story',orch._review_owner({'issues':[{'code':'UNMOTIVATED_CAMERA','beat_id':'B2'}]},'STORY')=='CINEMATOGRAPHY')
    add('Generic storyboard routes to Visual Concept',orch._review_owner({'issues':[{'code':'GENERIC_STORYBOARD','beat_id':'B2'}]},'ART_DIRECTION')=='VISUAL_CONCEPT')
    add('Semantic camera text with beat_id routes to Cinematography',orch._review_owner({'issues':[{'issue':'Camera framing loses the hero','beat_id':'B3'}]},'STORY')=='CINEMATOGRAPHY')

    # 7. Provider performance uses the field actually emitted by LiveCreativeModelProvider.
    class AuditProvider:
        def audit_dicts(self):return [{'task':'story','duration_ms':250,'retries':1,'schema_repairs':0,'status':'PASS'},{'task':'visual','duration_ms':500,'retries':0,'schema_repairs':1,'status':'FAIL'}]
    pp=orch._provider_performance(AuditProvider())
    add('Provider performance accumulates real duration_ms',pp['provider_total_latency_ms']==750 and pp['provider_retry_count']==1 and pp['provider_failed_call_count']==1 and pp['provider_schema_repair_count']==1,pp)

    # 8. Entire B01 control-flow path completes through every department.
    events=[];p=FlowProvider();result=orch.run_full_p8(copy.deepcopy(REQ),provider=p,progress=lambda ph,payload:events.append(ph))
    required=['STORY','VISUAL_CONCEPT','ART_DIRECTION','STORYBOARD','CINEMATOGRAPHY','EDITORIAL_RHYTHM','MOTION_PERFORMANCE','SOUND_DIRECTION','DEPARTMENTS_COMPLETE']
    add('Synthetic B01 traverses all departments to render-ready',result.get('status')=='DEPARTMENTS_COMPLETE' and result.get('code')=='P8_DEPARTMENTS_COMPLETE_RENDER_READY' and all(x in events for x in required),{'status':result.get('status'),'code':result.get('code'),'events':events})
    add('Clean synthetic B01 uses one creative attempt per department',all(v==1 for v in (result.get('autonomousRepair') or {}).get('attempts',{}).values()),(result.get('autonomousRepair') or {}).get('attempts'))
    add('Clean B01 provider-call count stays bounded',len(p.calls)<=30,len(p.calls))
    cinema_selector_requests=[r for t,r in p.calls if t=='showrunner_select_cinematography']
    editorial_selector_requests=[r for t,r in p.calls if t=='showrunner_select_editorial']
    cinema_rows=(cinema_selector_requests[-1].get('candidates') or []) if cinema_selector_requests else []
    editorial_rows=(editorial_selector_requests[-1].get('candidates') or []) if editorial_selector_requests else []
    add('Cinema selector provider payload excludes internal ProposalRef/review tokens',
        bool(cinema_rows) and all(isinstance(x,dict) and 'ref' not in x and 'review_id' not in x for x in cinema_rows),
        cinema_rows)
    add('Editorial selector provider payload excludes internal ProposalRef/review tokens',
        bool(editorial_rows) and all(isinstance(x,dict) and 'ref' not in x and 'review_id' not in x and 'timeline' in x for x in editorial_rows),
        editorial_rows)

    # 8a. Live-discovered Editorial arithmetic defects must be canonicalized locally,
    # not trigger repeated model regeneration.
    ev=[];p=EditorialTimingDriftProvider();res=orch.run_full_p8(copy.deepcopy(REQ),provider=p,progress=lambda ph,payload:ev.append((ph,copy.deepcopy(payload))))
    editorial_calls=sum(1 for t,_ in p.calls if t=='editorial_rhythm')
    repair=(res.get('autonomousRepair') or {});ledger=repair.get('ledger',[]);attempts=repair.get('attempts',{});lifetime=repair.get('lifetime_attempts',{})
    ed_contract_repairs=[x for x in ledger if x.get('department')=='EDITORIAL_RHYTHM' and 'contract' in str(x.get('reason','')).lower()]
    add('Editorial frame arithmetic is normalized without a second Director call',
        res.get('status')=='DEPARTMENTS_COMPLETE' and editorial_calls==1 and attempts.get('EDITORIAL_RHYTHM')==1 and lifetime.get('EDITORIAL_RHYTHM')==1 and not ed_contract_repairs,
        {'status':res.get('status'),'editorialCalls':editorial_calls,'attempts':attempts,'lifetime':lifetime,'editorialContractRepairs':ed_contract_repairs,'events':[x[0] for x in ev]})

    # 8b. A normal key-state storyboard rejection must repair Visual/Art in-place, not restart Story.
    ev=[];p=StoryboardThesisRejectOnceProvider();res=orch.run_full_p8(copy.deepcopy(REQ),provider=p,progress=lambda ph,payload:ev.append((ph,copy.deepcopy(payload))))
    phases=[x[0] for x in ev];attempts=(res.get('autonomousRepair') or {}).get('attempts',{});ledger=(res.get('autonomousRepair') or {}).get('ledger',[])
    storyboard_repairs=[x for x in ledger if 'storyboard' in str(x.get('reason','')).lower()]
    add('Storyboard thesis/payoff rejection repairs realization without full Story restart',res.get('status')=='DEPARTMENTS_COMPLETE' and 'BROADER_STRATEGY_REPLAN_AUTO_CONTINUE' not in phases and attempts.get('STORY')==1 and attempts.get('VISUAL_CONCEPT')==2 and any(x.get('department')=='VISUAL_CONCEPT' for x in storyboard_repairs),{'status':res.get('status'),'phases':phases,'attempts':attempts,'storyboardRepairs':storyboard_repairs})
    visual_repair_requests=[r for t,r in p.calls if t=='visual' and isinstance(r.get('repair_anchor'),dict)]
    add('Storyboard-driven Visual repair is anchored to accepted Visual candidate',bool(visual_repair_requests) and 'visual_thesis' in visual_repair_requests[-1]['repair_anchor'] and 'storyboard_hash' not in visual_repair_requests[-1]['repair_anchor'],visual_repair_requests[-1].get('repair_anchor') if visual_repair_requests else {})

    # 8c. Exact live-shape reproduction: Story uses 2/2, then Storyboard rejects once.
    ev=[];p=StoryAttempt2ThenStoryboardRejectProvider();res=orch.run_full_p8(copy.deepcopy(REQ),provider=p,progress=lambda ph,payload:ev.append((ph,copy.deepcopy(payload))))
    phases=[x[0] for x in ev];attempts=(res.get('autonomousRepair') or {}).get('attempts',{});lifetime=(res.get('autonomousRepair') or {}).get('lifetime_attempts',{})
    realization_repaired=(attempts.get('VISUAL_CONCEPT',0)>1 or attempts.get('ART_DIRECTION',0)>1)
    add('Story 2/2 accepted then Storyboard rejection does not trigger full Story restart',res.get('status')=='DEPARTMENTS_COMPLETE' and attempts.get('STORY')==2 and lifetime.get('STORY')==2 and realization_repaired and 'BROADER_STRATEGY_REPLAN' not in phases and 'BROADER_STRATEGY_REPLAN_AUTO_CONTINUE' not in phases,{'status':res.get('status'),'phases':phases,'attempts':attempts,'lifetime':lifetime})

    # 8d. Exact V8 failure reproduction: Visual reaches 3/3 after Storyboard. Budget
    # exhaustion must create a fresh Visual lineage; it must never climb to Story.
    ev=[];p=VisualExhaustAfterStoryboardProvider();res=orch.run_full_p8(copy.deepcopy(REQ),provider=p,progress=lambda ph,payload:ev.append((ph,copy.deepcopy(payload))))
    phases=[x[0] for x in ev];payloads=[x[1] for x in ev]
    repair=(res.get('autonomousRepair') or {});attempts=repair.get('attempts',{});lifetime=repair.get('lifetime_attempts',{})
    broader=[payload for ph,payload in ev if ph=='BROADER_STRATEGY_REPLAN']
    auto=[payload for ph,payload in ev if ph=='BROADER_STRATEGY_REPLAN_AUTO_CONTINUE']
    add('Visual 3/3 exhaustion opens same-Visual broader lineage and preserves accepted Story',
        res.get('status')=='DEPARTMENTS_COMPLETE' and lifetime.get('STORY')==2 and all(x.get('ownerDepartment')=='VISUAL_CONCEPT' for x in broader) and any(x.get('mode')=='SAME_DEPARTMENT_NEW_LINEAGE' and x.get('upstreamStoryPreserved') is True for x in auto) and not any(x.get('ownerDepartment')=='STORY' for x in broader+auto),
        {'status':res.get('status'),'phases':phases,'attempts':attempts,'lifetime':lifetime,'broader':broader,'auto':auto})
    visual_broader_calls=[r for t,r in p.calls if t=='visual' and ((r.get('brief') or {}).get('autonomous_revision_context') or {}).get('repair_mode')=='MATERIAL_STRATEGY_REPLAN']
    add('Fresh Visual lineage is genuine competition, not another anchored surgical repair',
        bool(visual_broader_calls) and visual_broader_calls[-1].get('repair_anchor') is None and int(visual_broader_calls[-1].get('candidate_budget') or 0)>=2,
        visual_broader_calls[-1] if visual_broader_calls else {})

    # 9. Same-command transient-provider recovery at early, parallel-review, selector,
    # temporal-board and late stages. No creative attempt is burned by transport failure.
    for task in ['story','producer','showrunner_select_cinematography','temporal_storyboard_review','sound_direction']:
        ev=[];provider=FlowProvider(task);res,recoveries=preflight.run_with_provider_recovery(copy.deepcopy(REQ),provider,lambda ph,payload:ev.append(ph),max_provider_recoveries=2)
        attempts=(res.get('autonomousRepair') or {}).get('attempts',{})
        add(f'Same-command provider recovery survives injected {task} timeout',res.get('status')=='DEPARTMENTS_COMPLETE' and recoveries==1 and 'PROVIDER_RECOVERY_AUTO_CONTINUE' in ev and all(v==1 for v in attempts.values()),{'status':res.get('status'),'recoveries':recoveries,'attempts':attempts,'eventsTail':ev[-6:]})

    # 10. Candidate-set diversity failures re-open competition rather than escaping as ProducerGateError.
    p=StoryDiversityProvider();res=orch.run_full_p8(copy.deepcopy(REQ),provider=p)
    attempts=(res.get('autonomousRepair') or {}).get('attempts',{})
    ledger=(res.get('autonomousRepair') or {}).get('ledger',[])
    add('Story non-diversity autonomously regenerates competition',res.get('status')=='DEPARTMENTS_COMPLETE' and attempts.get('STORY')==2 and any('diversity' in str(x.get('reason','')).lower() for x in ledger),{'status':res.get('status'),'attempts':attempts,'ledger':ledger[:2]})
    p=VisualDiversityProvider();res=orch.run_full_p8(copy.deepcopy(REQ),provider=p)
    attempts=(res.get('autonomousRepair') or {}).get('attempts',{})
    add('Visual non-diversity autonomously regenerates competition',res.get('status')=='DEPARTMENTS_COMPLETE' and attempts.get('VISUAL_CONCEPT')==2,{'status':res.get('status'),'attempts':attempts})

    # 11. Structural Director malformation is repaired without consuming the quality attempt.
    p=MalformedArtOnceProvider();res=orch.run_full_p8(copy.deepcopy(REQ),provider=p)
    attempts=(res.get('autonomousRepair') or {}).get('attempts',{});lifetime=(res.get('autonomousRepair') or {}).get('lifetime_attempts',{})
    add('Repairable Art structural miss does not burn creative-quality attempt',res.get('status')=='DEPARTMENTS_COMPLETE' and attempts.get('ART_DIRECTION')==1 and lifetime.get('ART_DIRECTION')==2,{'status':res.get('status'),'attempts':attempts,'lifetime':lifetime})

    # 12. Malformed selector gets one reasoning retry; Directors are not regenerated.
    p=InvalidSelectorOnceProvider();res=orch.run_full_p8(copy.deepcopy(REQ),provider=p)
    selector_calls=sum(1 for t,_ in p.calls if t=='showrunner_select_cinematography');cinema_calls=sum(1 for t,_ in p.calls if t=='cinematography')
    add('Malformed Showrunner selector retries selector only',res.get('status')=='DEPARTMENTS_COMPLETE' and selector_calls==2 and cinema_calls==1,{'status':res.get('status'),'selectorCalls':selector_calls,'cinemaDirectorCalls':cinema_calls})

    failed=[x for x in checks if x['status']!='PASS']
    out={'schema':'NexMindFinalReleaseFlowQAV1','status':'PASS' if not failed else 'FAIL','passed':len(checks)-len(failed),'total':len(checks),'failed':failed,'checks':checks}
    print(json.dumps(out,indent=2))
    return 0 if not failed else 1

if __name__=='__main__':raise SystemExit(run())
