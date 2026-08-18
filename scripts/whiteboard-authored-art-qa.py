#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SVC=ROOT/'services/studio-family-engines';sys.path.insert(0,str(SVC))
spec=importlib.util.spec_from_file_location('wb_adapter',SVC/'whiteboard_adapter.py');m=importlib.util.module_from_spec(spec);assert spec and spec.loader;spec.loader.exec_module(m)
checks=[]
def ck(name,ok,detail=''):checks.append({'name':name,'ok':bool(ok),'detail':detail})
base_plan={'styleProfile':'style.whiteboard-editorial','formResolution':{'status':'GENERATION_REQUIRED'},'sceneSpecs':[{'sceneId':'s1','beatId':'b1','heroRole':'dispatch package','supportingRoles':['desk','doorway'],'timingOverrideSeconds':2.0}]}
m._engine_root=lambda:Path('.')
m._load_runtime=lambda root:(None,None,None,None,None)
m.whiteboard_plan=lambda req:json.loads(json.dumps(base_plan))
m.authored_art_available=lambda:False
try:m.build_internal_evidence({'authorityId':'qa','aspectRatio':'16:9','outputDirectory':tempfile.mkdtemp()});ck('Missing authored-art capability causes replan',False,'no replan')
except m.AdapterReplan as e:
 ck('Missing authored-art capability causes replan',e.code=='WHITEBOARD_AUTHORED_ART_CAPABILITY_REQUIRED',e.code)
 ck('Missing capability replan forbids generic downgrade','No generic icon/card fallback.' in str(e.repair_request),str(e.repair_request)[:500])
m.authored_art_available=lambda:True
def bad(*a,**k):raise m.ArtExecutionInvalid('qa semantic mismatch')
m.execute_authored_scene=bad
try:m.build_internal_evidence({'authorityId':'qa','aspectRatio':'16:9','outputDirectory':tempfile.mkdtemp()});ck('Invalid authored-art output causes replan',False,'no replan')
except m.AdapterReplan as e:
 ck('Invalid authored-art output causes replan',e.code=='WHITEBOARD_AUTHORED_ART_EXECUTION_REPLAN_REQUIRED',e.code)
 ck('Invalid plate preserves required semantics in repair policy','Do not drop required hero/support semantics.' in str(e.repair_request),str(e.repair_request)[:500])
src=(SVC/'whiteboard_adapter.py').read_text();ck('Whiteboard generation is driven only by committed P8 form resolution','form.get("status")=="GENERATION_REQUIRED"' in src and 'execute_authored_scene(scene,"WHITEBOARD"' in src);ck('Whiteboard adapter never names a model/provider','gpt-' not in src.lower() and 'gemini' not in src.lower() and 'claude' not in src.lower() and 'deepseek' not in src.lower())
result={'schema':'NexStudioWhiteboardAuthoredArtExecutionQAV1','pass':all(x['ok'] for x in checks),'passed':sum(x['ok'] for x in checks),'total':len(checks),'checks':checks,'commercialScoreEvidence':False,'truthBoundary':'Recovery and semantic-lock proof only. No authored-art provider is configured here, so live premium Whiteboard illustration quality remains unclaimed.'}
out=ROOT/'reports/WHITEBOARD_AUTHORED_ART_QA.json';out.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));raise SystemExit(0 if result['pass'] else 1)
