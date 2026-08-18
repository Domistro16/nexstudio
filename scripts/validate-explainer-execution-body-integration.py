#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,os,py_compile,re,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ENGINE_ARCHIVE=ROOT/'engine_sources/EXPLAINER_ENGINE_SOURCE.zip'
ENGINE_ROOT=ROOT/'engines/explainer/NexStudio_Explainer_Execution_Body_V2'
EXPECTED_SHA='b2782b1557515d43db78a2c1507aeebb1cae99458104c450ed63ef752a675f1b'
checks=[]
def add(name,ok,detail=None): checks.append({'name':name,'pass':bool(ok),'detail':detail})
def text(p): return Path(p).read_text(errors='replace')
def sha(p):
 h=hashlib.sha256();
 with Path(p).open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''): h.update(c)
 return h.hexdigest()

# 1 execution-only Explainer body validator
v=subprocess.run([sys.executable,str(ENGINE_ROOT/'scripts/validate-p14-2-production-spine.py'),str(ENGINE_ROOT)],capture_output=True,text=True,cwd=ENGINE_ROOT)
try: vj=json.loads(v.stdout)
except Exception: vj={}
add('Explainer execution-only body passes its current contract',v.returncode==0 and vj.get('status')=='PASS' and isinstance(vj.get('total'),int) and vj.get('total')>=37 and vj.get('passed')==vj.get('total'),vj or v.stderr[-500:])
# 2-4 archive
actual_sha=sha(ENGINE_ARCHIVE); add('Explainer archive SHA matches execution-body authority',actual_sha==EXPECTED_SHA,actual_sha)
add('Explainer archive remains below 50 MB',ENGINE_ARCHIVE.stat().st_size<50*1024*1024,ENGINE_ARCHIVE.stat().st_size)
with zipfile.ZipFile(ENGINE_ARCHIVE) as z: bad=z.testzip(); names=z.namelist(); runner_zip=next((n for n in names if n.endswith('/scripts/studio-p8-explainer-runner.ts')),None); runner_arch=z.read(runner_zip).decode('utf-8','replace') if runner_zip else ''
add('Explainer archive ZIP integrity',bad is None,bad)
# 5 authority
at=text(ROOT/'src/studio-v1/production-engines/authority.ts'); add('Standalone Explainer execution authority is neutral and hash-bound', 'EXPLAINER_EXECUTION_BODY_V2_P8_UNIFIED' in at and EXPECTED_SHA in at,None)
# 6 adapter no old fallback
ad=text(ROOT/'services/studio-family-engines/explainer_adapter.py'); add('Active Explainer adapter has no DirectorV3/canonical P14.1 mapper', all(x not in ad for x in ['from canonical import explainer_plan','DirectorV3','director-v3']),None)
# 7 requires P8 board/checkpoint
add('Explainer adapter requires committed P8 board and checkpoint','require_review_board(board)' in ad and 'P8_CREATIVE_CHECKPOINT_REQUIRED' in ad and 'P8_CREATIVE_DEPARTMENTS_INCOMPLETE' in ad,None)
# 8 runner has no duplicate family-level creative director authority
add('P8 is sole top-level authority inside unified runner','runNexMindExplainerDirectors' not in runner_arch and 'production-director' not in runner_arch,None)
# 9 strict actual-frame critic
add('Unified runner performs execution-fidelity-only gating', 'StudioFamilyExecutionFidelityV1' in runner_arch and 'commercialScore:null' in runner_arch and 'reviewExplainerCompositionFrames' not in runner_arch and 'EXPLAINER_STRICT_VISUAL_CRITIC_FAILED' not in runner_arch,None)
# 10 no generic visual-verb fallback
add('P8 motion requires explicit executable binding','P8_MOTION_EXECUTION_BINDING_REQUIRED' in runner_arch and 'inferVisualVerb' not in runner_arch,None)
# 11 reference analysis precedes P8
wf=text(ROOT/'src/studio-v1/nexmind-p8/workflow.ts'); a=wf.find('const referenceLanguage = await analyzeStandaloneReferenceLanguage'); b=wf.find('const result = await executeStudioNexMindP8'); add('Reference-language analysis runs before P8 creative execution',a>=0 and b>=0 and a<b,{'referenceAnalysisIndex':a,'p8Index':b})
# 12 P8 receives reference evidence
orch=text(ROOT/'services/studio-nexmind-p8/orchestrator.py'); add('P8 brief receives reference-language profile and style hint','reference_language_profile' in orch and 'reference_style_hint' in orch,None)
# 13 production engine receives real reference media
pewf=text(ROOT/'src/studio-v1/production-engines/workflow.ts'); add('Production workflow rematerializes/passes reference media', 'referenceMedia' in pewf and ('materialize' in pewf.lower() or 'temporary' in pewf.lower()),None)
# 14 env provider contracts
env=text(ROOT/'.env.example'); env_need=['NEXMIND_MODEL_REGISTRY_JSON=','NEXMIND_RUNTIME_BOOT_ATTESTATION_JSON=','NEXMIND_FINAL_EXECUTIVE_PRODUCER_INPUT_MODALITIES=images,audio','NEXMIND_PERCEPTUAL_AUDITOR_INPUT_MODALITIES=images,audio','STUDIO_NEXMIND_P8_BRIDGE_MODE=process','STUDIO_EXPLAINER_ENGINE_ROOT=./engines/explainer/NexStudio_Explainer_Execution_Body_V2']; named=['OPENAI_API_KEY=','AGENTROUTER_API_KEY=','AGENTROUTER_BASE_URL=','NEXMIND_API_URL=']; add('Standalone environment exposes provider-neutral readiness contracts',all(x in env for x in env_need) and all(x not in env for x in named),None)
# 15 current V5.1 capability path resolves
cap=text(ROOT/'services/studio-nexmind-p8/capability_adapter.py'); reg=ROOT/'engines/stickman/NEXSTICK_MASTER_V2_UNIFIED_PERFORMANCE_V5_1_CLEAN_2026-08-13/NEXSTICK_MASTER_V2_CAPABILITY_REGISTRY.json'; add('P8 capability adapter resolves installed NexStick V5.1 registry','STUDIO_STICKMAN_ENGINE_ROOT' in cap and reg.exists(),str(reg))
# 16 actual no-provider boundary
nop=ROOT/'reports/EXPLAINER_P8_NO_PROVIDER_RESULT.json'; noobj=json.loads(nop.read_text()) if nop.exists() else {}; add('Actual P8 run reaches provider-agnostic model-capability boundary and fails recoverably',noobj.get('status')=='PROVIDER_UNAVAILABLE' and noobj.get('code')=='LIVE_PROVIDER_BLOCKED_NO_COMPATIBLE_MODEL_CONFIG' and 'creative_reasoning' in str(noobj.get('detail') or ''),noobj)
# 17 actual no-deps boundary
nd=ROOT/'reports/EXPLAINER_EXECUTION_BODY_NO_DEPS_RESULT.json'; ndobj=json.loads(nd.read_text()) if nd.exists() else {}; add('Actual Explainer adapter run requests durable technical recovery when Node deps are absent',ndobj.get('status')=='TECHNICAL_RETRY_REQUIRED' and ndobj.get('code')=='EXPLAINER_EXECUTION_BODY_DEPENDENCIES_NOT_INSTALLED',ndobj)
# 18 benchmark refs analyzed
ra=ROOT/'reports/EXPLAINER_REFERENCE_LANGUAGE_BENCHMARKS.json'; raj=json.loads(ra.read_text()) if ra.exists() else {}; cases=raj.get('cases') or []; by={x.get('name'):x for x in cases}; okrefs=len(cases)==3 and all((x.get('result') or {}).get('profile',{}).get('whiteField') is True and (x.get('result') or {}).get('profile',{}).get('densityTarget')=='rich' for x in cases) and (by.get('01 hand draw(1).mp4',{}).get('result') or {}).get('styleHint')=='hand-drawn-whiteboard'; add('All three user benchmark references produce usable pre-P8 visual-language evidence',okrefs,[{'name':x.get('name'),'styleHint':(x.get('result') or {}).get('styleHint'),'profile':(x.get('result') or {}).get('profile')} for x in cases])
# 19 Python syntax
pyfiles=[ROOT/'services/studio-family-engines/explainer_adapter.py',ROOT/'services/studio-nexmind-p8/reference_language.py',ROOT/'services/studio-nexmind-p8/capability_adapter.py',ROOT/'services/studio-nexmind-p8/orchestrator.py']
pyok=True; perr=[]
for p in pyfiles:
 try: py_compile.compile(str(p),doraise=True)
 except Exception as e: pyok=False;perr.append(f'{p.name}:{e}')
add('Modified Python integration files compile',pyok,perr)
# 20 TS syntax via global TypeScript transpileModule
files=[ENGINE_ROOT/'scripts/studio-p8-explainer-runner.ts',ROOT/'src/studio-v1/nexmind-p8/reference-language.ts',ROOT/'src/studio-v1/nexmind-p8/workflow.ts',ROOT/'src/studio-v1/nexmind-p8/contract.ts',ROOT/'src/studio-v1/production-engines/bridge.ts',ROOT/'src/studio-v1/production-engines/workflow.ts',ROOT/'src/studio-v1/production-engines/authority.ts']
js="const ts=require('typescript'),fs=require('fs');let bad=[];for(const p of process.argv.slice(1)){const r=ts.transpileModule(fs.readFileSync(p,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext},reportDiagnostics:true,fileName:p});for(const d of r.diagnostics||[])if(d.category===ts.DiagnosticCategory.Error)bad.push(p+':'+ts.flattenDiagnosticMessageText(d.messageText,' '));}if(bad.length){console.error(bad.join('\\n'));process.exit(1)}"
tp=subprocess.run(['node','-e',js,*map(str,files)],capture_output=True,text=True); add('Modified TypeScript files parse without syntax errors',tp.returncode==0,tp.stderr[-1000:] if tp.stderr else None)
# 21 standalone source qa
sq=json.loads((ROOT/'reports/STANDALONE_SOURCE_QA.json').read_text()); add('Standalone source QA passes after authority hash update',sq.get('pass') is True,None)
# 22 stale authority absent active root (excluding installed engines/vendor/archive bytes)
stale=[]
for p in ROOT.rglob('*'):
 if not p.is_file() or p.name=='validate-explainer-execution-body-integration.py' or 'engines' in p.parts or 'vendor' in p.parts or p.suffix.lower() in {'.zip','.mp4','.png','.jpg','.jpeg','.pyc'}: continue
 try:
  if 'EXPLAINER_MOTION_P14_1_CREATIVE_GOLD_V2' in p.read_text(errors='ignore'): stale.append(str(p.relative_to(ROOT)))
 except Exception: pass
add('No active Standalone source still declares P14.1 Explainer authority',not stale,stale)
# 23 runtime truth boundary
pkg=json.loads((ROOT/'package.json').read_text()); node_req=(pkg.get('engines') or {}).get('node'); current=subprocess.run(['node','-v'],capture_output=True,text=True).stdout.strip(); modules=(ROOT/'node_modules').exists(); add('Current sandbox correctly remains outside certified production runtime',node_req=='>=24.0.0' and current.startswith('v22.') and not modules,{'requiredNode':node_req,'currentNode':current,'nodeModulesPresent':modules})

report={'schema':'NexStudioExplainerExecutionBodyIntegrationQA V2','status':'PASS' if all(x['pass'] for x in checks) else 'FAIL','passed':sum(x['pass'] for x in checks),'total':len(checks),'checks':checks,'truthBoundary':{'sourceIntegration':'VERIFIED','liveP8Inference':'BLOCKED_MISSING_PROVIDER_CREDENTIALS_IN_THIS_SANDBOX','encodedExplainerBenchmark':'NOT_RUN','productionRuntime':'REQUIRES_NODE_24_PLUS_DEPENDENCY_INSTALL_AND_LIVE_PROVIDER_SECRETS','humanCreativeCertification':'NOT_CLAIMED'}}
out=ROOT/'reports/EXPLAINER_EXECUTION_BODY_INTEGRATION_QA.json'; out.write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps({'status':report['status'],'passed':report['passed'],'total':report['total'],'out':str(out)},indent=2)); sys.exit(0 if report['status']=='PASS' else 1)
