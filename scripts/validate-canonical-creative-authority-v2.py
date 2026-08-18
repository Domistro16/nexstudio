#!/usr/bin/env python3
from pathlib import Path
import json, re, sys, zipfile, hashlib, subprocess
ROOT=Path(__file__).resolve().parents[1]
checks=[]
def add(name,ok,detail=None): checks.append({'name':name,'pass':bool(ok),'detail':detail})
# No physical legacy director implementation paths.
legacy=[str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.name.lower()=='director-v3' or p.name=='NexStudio_P11_Director_V3_Runtime.py']
add('No physical DirectorV3 implementation remains in canonical source',not legacy,legacy)
# Active Explainer adapter must be execution-only and contain no retired creative mapper.
ad=(ROOT/'services/studio-family-engines/explainer_adapter.py').read_text(errors='replace')
add('Explainer adapter has no retired creative Director/mapper','DirectorV3' not in ad and 'director-v3' not in ad and 'canonical.explainer_plan' not in ad,None)
# Recorded fixture is quarantined and policy-tagged.
q=ROOT/'vendor/nexmind-god-mode-p8/tests/fixtures/contract_regression_only/P1P2_RECORDED_PROVIDER_CONTRACT_REGRESSION_ONLY.json'
qo=json.loads(q.read_text()) if q.exists() else {}
pol=qo.get('_evaluation_policy') or {}
add('Curated nine-topic fixture is regression-only',q.exists() and pol.get('creative_benchmark_eligible') is False and pol.get('human_calibration_eligible') is False,pol)
add('Old general fixtures location is absent',not (ROOT/'vendor/nexmind-god-mode-p8/fixtures/recorded_provider_cases.json').exists(),None)
# Live candidate blinding is present and audited.
lp=(ROOT/'vendor/nexmind-god-mode-p8/src/nexmind_god_mode/live_provider.py').read_text(errors='replace')
need=['_blind_showrunner_candidates','secrets.SystemRandom','OPT-','candidate_presentation_policy','_unblind_showrunner_result','candidate_order_audits']
add('Live Showrunner candidate order is randomized and opaque',all(x in lp for x in need),None)
# Benchmark policy blocks recorded providers.
bp=(ROOT/'vendor/nexmind-god-mode-p8/src/nexmind_god_mode/benchmark_policy.py').read_text(errors='replace')
add('Commercial benchmark policy rejects RecordedModelProvider','RECORDED_MODEL_PROVIDER_FORBIDDEN_FOR_COMMERCIAL_CREATIVE_BENCHMARK' in bp,None)
# New brief pack has no expected creative answer fields.
pack=ROOT/'evaluations/nexmind-p8-commercial-brain-v2/BLIND_COMMERCIAL_BRIEFS_V2.json'; po=json.loads(pack.read_text())
brief_raw=json.dumps(po.get('briefs',[]),sort_keys=True).lower()
banned=['selected_candidate','preferred_strategy','visual_thesis','film_thesis','candidate_id']
add('Replacement benchmark has 30 client-like briefs',po.get('brief_count')==30 and len(po.get('briefs',[]))==30,po.get('brief_count'))
add('Replacement brief pack stores no expected creative answers',not any(x in brief_raw for x in banned),[x for x in banned if x in brief_raw])
# Canonical authority doc exists.
ca=(ROOT/'docs/studio-v1/CANONICAL_CREATIVE_AUTHORITY.md').read_text(errors='replace')
add('Canonical authority explicitly deletes DirectorV3','Deleted / forbidden' in ca and 'DirectorV3' in ca and 'NexMind P8' in ca,None)
# Python tests for policy.
env=dict(__import__('os').environ); env['PYTHONPATH']=str(ROOT/'vendor/nexmind-god-mode-p8/src')
r=subprocess.run([sys.executable,'-m','unittest','vendor/nexmind-god-mode-p8/tests/test_p8_blind_benchmark_policy.py'],cwd=ROOT,env=env,capture_output=True,text=True)
add('Blind benchmark policy tests pass',r.returncode==0,r.stdout+r.stderr)
report={'schema':'StudioCanonicalCreativeAuthorityQA V2','status':'PASS' if all(x['pass'] for x in checks) else 'FAIL','passed':sum(x['pass'] for x in checks),'total':len(checks),'checks':checks}
out=ROOT/'reports/CANONICAL_CREATIVE_AUTHORITY_QA_V2.json'; out.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':report['status'],'passed':report['passed'],'total':report['total'],'out':str(out)},indent=2))
sys.exit(0 if report['status']=='PASS' else 1)
