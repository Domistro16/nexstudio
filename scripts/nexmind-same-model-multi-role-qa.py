#!/usr/bin/env python3
from __future__ import annotations
import json, os, sys
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vendor/nexmind-god-mode-p8/src'))
sys.path.insert(0,str(ROOT/'services/studio-nexmind-p8'))
from nexmind_god_mode.live_provider import RoleRouter
from orchestrator import _judge_ensemble_hash

checks=[]
def ck(name,ok,detail=''):
    checks.append({'name':name,'pass':bool(ok),'detail':str(detail)})

registry={'routes':[{
    'provider':'one-gateway','model':'one-capable-model-v1','capabilities':['*'],
    'input_modalities':['images','audio'],'audio_input_mode':'chat_input_audio',
    'priority':100,'base_url':'https://one.invalid/v1','api_key_env':'ONE_API_KEY'
}]}
with patch.dict(os.environ,{'NEXMIND_MODEL_REGISTRY_JSON':json.dumps(registry),'ONE_API_KEY':'secret'},clear=True):
    routes=[RoleRouter().resolve(task) for task in RoleRouter.ROLE_NAMES]
ck('one model resolves every NexMind role',bool(routes) and {r.model for r in routes}=={'one-capable-model-v1'})
ck('one provider resolves every NexMind role',{r.provider for r in routes}=={'one-gateway'})
ck('one API key env resolves every NexMind role',{r.api_key_env for r in routes}=={'ONE_API_KEY'})

class P:
    def audit_dicts(self):
        shared={'status':'PASS','provider':'one-gateway','resolved_model':'one-capable-model-v1'}
        return [
            {**shared,'task':'story','role':'StoryDirector'},
            {**shared,'task':'visual','role':'VisualConceptDirector'},
            {**shared,'task':'art','role':'ArtDirector'},
            {**shared,'task':'final_producer','role':'IndependentFinalExecutiveProducer'},
            {**shared,'task':'perceptual_auditor','role':'IndependentPerceptualAuditor'},
        ]
h=_judge_ensemble_hash(P())
ck('same-model final roles produce process-bound ensemble hash',isinstance(h,str) and len(h)==64,h or 'missing')

orch=(ROOT/'services/studio-nexmind-p8/orchestrator.py').read_text(encoding='utf-8')
ready=(ROOT/'src/studio-v1/runtime-readiness.ts').read_text(encoding='utf-8')
env=(ROOT/'.env.example').read_text(encoding='utf-8')
readme=(ROOT/'CANONICAL_SOURCE_README.md').read_text(encoding='utf-8')
forbidden=[
    'P8_JUDGE_MODEL_INDEPENDENCE_VIOLATION',
    'P8_AUTHOR_REVIEWER_MODEL_INDEPENDENCE_VIOLATION',
    'judge-model-independence',
    'creator-final-judge-independence',
    'creator-auditor-independence',
]
active=orch+'\n'+ready+'\n'+env+'\n'+readme
ck('no active model-identity blocker remains',not any(x in active for x in forbidden),[x for x in forbidden if x in active])
ck('runtime readiness requires role/process independence','final-review-role-process-independence' in ready)
ck('operator docs explicitly allow same model','may use the same sufficiently capable model identity' in readme and 'may resolve to the SAME capable model' in env)

out={'schema':'NexMindSameModelMultiRoleQAV1','status':'PASS' if all(c['pass'] for c in checks) else 'FAIL','passed':sum(c['pass'] for c in checks),'total':len(checks),'checks':checks,'law':'ONE_CAPABLE_MODEL_AND_ONE_API_KEY_MAY_SERVE_ALL_ROLES__INDEPENDENCE_IS_PROCESS_NOT_MODEL_IDENTITY'}
print(json.dumps(out,indent=2))
out_path=ROOT/'reports/SAME_MODEL_REPAIR/SAME_MODEL_MULTI_ROLE_QA.json'; out_path.parent.mkdir(parents=True,exist_ok=True); out_path.write_text(json.dumps(out,indent=2),encoding='utf-8')
raise SystemExit(0 if out['status']=='PASS' else 1)
