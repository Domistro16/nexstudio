from __future__ import annotations
import copy, importlib.util, json, pathlib, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
FLOW_PATH=ROOT/'scripts'/'nexmind-final-release-flow-qa.py'
spec=importlib.util.spec_from_file_location('nexmind_final_flow_support',FLOW_PATH)
ff=importlib.util.module_from_spec(spec); spec.loader.exec_module(ff)
sys.path.insert(0,str(ROOT/'vendor'/'nexmind-god-mode-p8'/'src'))
from nexmind_god_mode.review_governance import calibrate_review, release_decision_law
from nexmind_god_mode.provider_schemas import PRODUCER_SCHEMA

checks=[]
def add(name,ok,detail=''):
    checks.append({'name':name,'status':'PASS' if ok else 'FAIL','detail':str(detail)})

# 1. Safety-biased stopping semantics.
def rev(issue,confidence='MEDIUM',verdict='REVISE'):
    return {'verdict':verdict,'issues':[issue],'strengths':['strong authored work'],'revision_brief':'Improve it.','commercial_confidence':confidence}

add('Advisory REVISE becomes ACCEPT only when explicitly non-blocking',
    calibrate_review(rev({'blocking':False,'severity':'MODERATE','finding':'Could be more elegant.'}),stage='STORY')['verdict']=='ACCEPT')
add('Explicit blocking REVISE remains REVISE',
    calibrate_review(rev({'blocking':True,'severity':'MAJOR','finding':'Causal chain is broken.'}),stage='STORY')['verdict']=='REVISE')
add('Missing blocking metadata preserves old strict REVISE behavior',
    calibrate_review(rev({'severity':'MODERATE','finding':'Legacy review.'}),stage='STORY')['verdict']=='REVISE')
add('LOW confidence cannot advance even when issue is marked advisory',
    calibrate_review(rev({'blocking':False,'severity':'MODERATE','finding':'Could be better.'},'LOW'),stage='STORY')['verdict']=='REVISE')
add('REJECT is never softened',
    calibrate_review(rev({'blocking':False,'severity':'MODERATE','finding':'Optional note.'},'MEDIUM','REJECT'),stage='STORY')['verdict']=='REJECT')
accept_with_blocker={'verdict':'ACCEPT','issues':[{'blocking':True,'severity':'MAJOR','required_change':'Repair the real defect.'}],'strengths':[],'revision_brief':'','commercial_confidence':'HIGH'}
forced=calibrate_review(accept_with_blocker,stage='ART_DIRECTION')
add('Explicit blocker can never hide inside ACCEPT',forced['verdict']=='REVISE' and forced['commercial_confidence']!='HIGH',forced)

# 2. Live Producer contract must force the model to classify every criticism.
issue_schema=((PRODUCER_SCHEMA.get('properties') or {}).get('issues') or {}).get('items') or {}
add('Live Producer schema requires blocking classification on every issue','blocking' in (issue_schema.get('required') or []),issue_schema)
law=' '.join(release_decision_law('STORY')).lower()
add('Release law explicitly rejects perfection optimization','not a perfection optimizer' in law and 'perfection is not a release criterion' in law,law)
add('Release law explicitly preserves high creative quality','do not accept generic' in law and 'commercially strong' in law,law)

# 3. All V9 quality/review topology remains intact on a clean run.
p=ff.FlowProvider(); r=ff.orch.run_full_p8(copy.deepcopy(ff.REQ),provider=p)
tasks=[t for t,_ in p.calls]
expected=['story','story','producer','producer','showrunner_select','visual','producer','producer','producer','showrunner_select','art','art_review','art_review','storyboard_review','cinematography','cinematography_review','cinematography_review','showrunner_select_cinematography','editorial_rhythm','editorial_review','editorial_review','showrunner_select_editorial','temporal_storyboard_review','motion_performance','motion_review','motion_review','sound_direction','sound_review','sound_review','showrunner_select_sound']
add('Clean B01 still reaches DEPARTMENTS_COMPLETE',r.get('status')=='DEPARTMENTS_COMPLETE',(r.get('status'),r.get('code')))
add('No quality-review calls were removed',tasks==expected,tasks)
add('Clean B01 still performs the full 30-call V9 review topology',len(tasks)==30,len(tasks))

# 4. Advisory criticism at every Producer/review boundary must not create a repair loop.
REVIEW_TASKS={'producer','art_review','storyboard_review','cinematography_review','editorial_review','temporal_storyboard_review','motion_review','sound_review'}
class AdvisoryEverywhere(ff.FlowProvider):
    def complete(self,task,request):
        if task in REVIEW_TASKS:
            with self._lock:self.calls.append((task,copy.deepcopy(request)))
            return {
                'verdict':'REVISE',
                'issues':[{
                    'blocking':False,
                    'severity':'MODERATE',
                    'area':'Optional refinement',
                    'finding':'The current work is commercially strong and coherent; an alternate micro-choice might be even more elegant.',
                    'required_change':'Optional polish only.',
                }],
                'strengths':['Brief-faithful, distinctive, coherent, executable and commercially strong.'],
                'revision_brief':'Optional polish only.',
                'commercial_confidence':'MEDIUM',
            }
        return super().complete(task,request)

p=AdvisoryEverywhere(); events=[]
r=ff.orch.run_full_p8(copy.deepcopy(ff.REQ),provider=p,progress=lambda ph,payload:events.append(ph))
tasks_adv=[t for t,_ in p.calls]; repair=r.get('autonomousRepair') or {}
add('Advisory criticism at every stage does not trigger regeneration',r.get('status')=='DEPARTMENTS_COMPLETE',(r.get('status'),r.get('code')))
add('Advisory-only run preserves all 30 quality calls',tasks_adv==expected,tasks_adv)
add('Advisory-only run has no repair ledger',not (repair.get('ledger') or []),repair.get('ledger'))
add('Advisory-only run has no broader strategy replan','BROADER_STRATEGY_REPLAN' not in events,events)
add('Advisory-only run uses one attempt per department',all(v==1 for v in (repair.get('attempts') or {}).values()),repair.get('attempts'))

# 5. A true blocker must still cause bounded repair.
class StoryboardBlockOnce(ff.FlowProvider):
    def __init__(self): super().__init__(); self.n=0
    def complete(self,task,request):
        if task=='storyboard_review':
            with self._lock:
                self.calls.append((task,copy.deepcopy(request))); self.n+=1; n=self.n
            if n==1:
                return {
                    'verdict':'REVISE',
                    'issues':[{
                        'blocking':True,
                        'code':'WEAK_SETTLED_STATE','owner_department':'ART_DIRECTION','severity':'MAJOR',
                        'area':'Commercial legibility','finding':'The hero is not readable in the settled key state, so the brief cannot land.',
                        'required_change':'Repair Art hierarchy so the hero and causal state read without motion.',
                    }],
                    'strengths':['Story and Visual strategy remain strong.'],
                    'revision_brief':'Repair the blocking Art hierarchy defect only.',
                    'commercial_confidence':'LOW',
                }
            return {'verdict':'ACCEPT','issues':[],'strengths':['Hero now reads clearly.'],'revision_brief':'','commercial_confidence':'HIGH'}
        return super().complete(task,request)

p=StoryboardBlockOnce(); events=[]
r=ff.orch.run_full_p8(copy.deepcopy(ff.REQ),provider=p,progress=lambda ph,payload:events.append(ph)); repair=r.get('autonomousRepair') or {}
add('True blocking storyboard defect still forces repair',r.get('status')=='DEPARTMENTS_COMPLETE' and (repair.get('attempts') or {}).get('ART_DIRECTION')==2,(r.get('status'),repair.get('attempts')))
add('Blocking repair remains bounded and does not become perfection loop',(repair.get('attempts') or {}).get('ART_DIRECTION')==2 and events.count('ART_DIRECTION')==2,events)


# 6. Every creative department still repairs a real blocking defect exactly once.
STAGE_SPECS={
    'STORY':('producer',2),
    'VISUAL_CONCEPT':('producer',3),
    'ART_DIRECTION':('art_review',2),
    'CINEMATOGRAPHY':('cinematography_review',2),
    'EDITORIAL_RHYTHM':('editorial_review',2),
    'MOTION_PERFORMANCE':('motion_review',2),
    'SOUND_DIRECTION':('sound_review',2),
}
class BlockDepartmentFirstAttempt(ff.FlowProvider):
    def __init__(self,department):
        super().__init__(); self.department=department; self.review_count=0
    def _matches(self,task,request):
        review_task,initial_count=STAGE_SPECS[self.department]
        if task!=review_task: return False
        if task=='producer':
            return str((request.get('instruction') or {}).get('review_scope') or '')==self.department
        return True
    def complete(self,task,request):
        # FlowProvider's first synthetic Motion candidate is deliberately capability-incompatible.
        # For this test we are isolating Producer stopping behavior, so the anchored repair
        # returns its known-executable fallback rather than testing capability recovery again.
        if self.department=='MOTION_PERFORMANCE' and task=='motion_performance' and request.get('repair_anchor') is not None:
            with self._lock:self.calls.append((task,copy.deepcopy(request)))
            return {'candidates':[ff.motion_candidate('M2',2)]}
        if self._matches(task,request):
            review_task,initial_count=STAGE_SPECS[self.department]
            with self._lock:
                self.calls.append((task,copy.deepcopy(request))); self.review_count+=1; n=self.review_count
            if n<=initial_count:
                return {
                    'verdict':'REVISE',
                    'issues':[{'blocking':True,'severity':'MAJOR','area':'Release floor','finding':f'{self.department} contains a material defect that makes the current artifact unfit to advance.','required_change':f'Repair the material {self.department} defect.'}],
                    'strengths':['Preserve the strong brief-specific work.'],
                    'revision_brief':f'Repair the material {self.department} defect only.',
                    'commercial_confidence':'LOW',
                }
            return {'verdict':'ACCEPT','issues':[],'strengths':['Material defect resolved.'],'revision_brief':'','commercial_confidence':'HIGH'}
        return super().complete(task,request)

for department in STAGE_SPECS:
    p=BlockDepartmentFirstAttempt(department); events=[]
    r=ff.orch.run_full_p8(copy.deepcopy(ff.REQ),provider=p,progress=lambda ph,payload:events.append(ph)); repair=r.get('autonomousRepair') or {}
    attempts=repair.get('attempts') or {}
    add(f'True blocker in {department} causes exactly one local repair and then completes',
        r.get('status')=='DEPARTMENTS_COMPLETE' and attempts.get(department)==2 and 'BROADER_STRATEGY_REPLAN' not in events,
        {'status':r.get('status'),'attempts':attempts,'events':events})

failed=[x for x in checks if x['status']!='PASS']
out={'schema':'NexMindReleaseStoppingGovernanceQAV1','status':'PASS' if not failed else 'FAIL','passed':len(checks)-len(failed),'total':len(checks),'failed':failed,'checks':checks,'law':'FULL_QUALITY_REVIEW_DEPTH_PRESERVED__ONLY_EXPLICIT_MATERIAL_BLOCKERS_TRIGGER_REGENERATION__ADVISORY_IMPROVEMENTS_ADVANCE'}
print(json.dumps(out,indent=2))
raise SystemExit(0 if not failed else 1)
