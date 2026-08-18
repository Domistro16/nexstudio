#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,json,sys,tempfile,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FAMILY=ROOT/'services'/'studio-family-engines'
sys.path.insert(0,str(FAMILY))
from execution_plan import compile_execution_plan, compatibility_board, SCHEMA, COMPILER_ROLE

spec=importlib.util.spec_from_file_location('smoke',ROOT/'scripts'/'run-family-engine-smoke.py')
smoke=importlib.util.module_from_spec(spec);spec.loader.exec_module(smoke)
checks=[]
def check(name,cond,detail=''):
    checks.append({'name':name,'pass':bool(cond),'detail':detail})

hashes={}
for family in smoke.AUTHORITIES:
    req=smoke.request_for(family,Path('/tmp/shared-execution-plan-qa'))
    original=req['finalBoard']
    plan=compile_execution_plan(req,original)
    compat=compatibility_board(plan)
    hashes[family]=plan['executionPlanHash']
    check(f'{family}:schema',plan.get('schema')==SCHEMA)
    check(f'{family}:sole-creative-authority',(plan.get('authority') or {}).get('creativeAuthority')=='NEXMIND_P8')
    check(f'{family}:deterministic-normalizer',(plan.get('authority') or {}).get('compilerRole')==COMPILER_ROLE and (plan.get('authority') or {}).get('creativeChoiceIntroduced') is False)
    check(f'{family}:roundtrip',compat==original)
    check(f'{family}:stable-hash',compile_execution_plan(req,original).get('executionPlanHash')==plan.get('executionPlanHash'))

worker=(FAMILY/'worker.py').read_text()
check('worker-removes-raw-board-before-adapter','request.pop("finalBoard",None)' in worker)
check('worker-compiles-once','compile_execution_plan(incoming,raw_board)' in worker)
check('worker-adapters-see-compatibility-only','request["finalBoard"]=compatibility_board(plan)' in worker)
check('worker-emits-execution-lineage','executionPlanHash' in worker and 'executionPlanSchema' in worker)

bridge=(ROOT/'src/studio-v1/production-engines/bridge.ts').read_text()
workflow=(ROOT/'src/studio-v1/production-engines/workflow.ts').read_text()
check('ts-bridge-carries-execution-plan','executionPlanHash?: string' in bridge and 'StudioCanonicalExecutionPlanV1' in bridge)
check('final-lineage-binds-execution-plan','executionPlanHash:result.executionPlanHash??null' in workflow)
check('source-hash-binds-execution-plan','executionPlan:lineageMaterial.execution.executionPlanHash' in workflow and 'sourceHash:canonicalHash' in workflow)

report={'schema':'StudioSharedExecutionPlanQAV1','pass':all(x['pass'] for x in checks),'passed':sum(x['pass'] for x in checks),'total':len(checks),'families':list(smoke.AUTHORITIES),'hashes':hashes,'checks':checks}
out=ROOT/'reports'/'architecture'/'SHARED_EXECUTION_PLAN_QA.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2));raise SystemExit(0 if report['pass'] else 1)
