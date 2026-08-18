#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ENGINE_PATHS={
 'WHITEBOARD':ROOT/'engines/whiteboard/Whiteboard_Execution_Body_V2',
 'EXPLAINER':ROOT/'engines/explainer/NexStudio_Explainer_Execution_Body_V2',
 'EDITORIAL_MOTION':ROOT/'engines/editorial',
 'STICKMAN':ROOT/'engines/stickman/NEXSTICK_MASTER_V2_UNIFIED_PERFORMANCE_V5_1_CLEAN_2026-08-13',
 'SOUND':ROOT/'engines/sound/NexStudio_Sound_Library_V2_Production',
}
AUTHORITIES={
 'WHITEBOARD':'WHITEBOARD_EXECUTION_BODY_V2_P8_UNIFIED',
 'EXPLAINER':'EXPLAINER_EXECUTION_BODY_V2_P8_UNIFIED',
 'EDITORIAL_MOTION':'EDITORIAL_EXECUTION_BODY_V2_P8_UNIFIED',
 'STICKMAN':'NEXSTICK_MASTER_V2_PERFORMANCE_V5_1',
}

def sha(path:Path)->str:
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()

def request_for(family:str,out:Path)->dict:
 if family=='STICKMAN':
  action={'action_id':'A1','performer_class':'STICKMAN_V2','actor':'male presenter broad','requested_verb':'HOLD','execution':{'resolved_verb':'HOLD'},'contact_requirement':'NONE','available_requirements':[]}
  thesis='A presenter holds a calm opening pose.'; hero='presenter'
 else:
  action={'action_id':'A1','performer_class':'SCENE_GRAPH','actor':'scene','requested_verb':'TYPE_REVEAL','execution':{'resolved_verb':'TYPE_REVEAL'},'contact_requirement':'NONE','available_requirements':[]}
  thesis='MAKE THE IDEA CLEAR.'; hero='central idea'
 board={'schema':'NexMindCanonicalSoundStoryboardV4','beats':[{
  'beat_id':'B1','scene_thesis':thesis,'hero_identity':hero,'supporting_assets':[],
  'continuity_in':'opening','continuity_out':'settled',
  'motion_plan_status':'DIRECTED_MOTION_PERFORMANCE','sound_plan_status':'DIRECTED_SOUND',
  'motion_actions':[action],
  'sound_events':[{'event_id':'S1','kind':'SILENCE','semantic_tag':'','intensity':'NONE'}],
  'editorial':{'duration':{'value':2,'rate':1}},
  'camera':{'semantic_target':hero,'camera_atom':{'motivation':'establish the directed subject'}}
 }]}
 return {'schema':'StudioFamilyEngineRequestV1','operation':'BUILD_INTERNAL_REVIEW_EVIDENCE','family':family,'authorityId':AUTHORITIES[family],'productionId':'standalone-smoke-'+family.lower(),'creativeStateArtifactId':'smoke-state','creativeStateArtifactHash':'a'*64,'durationSeconds':2,'aspectRatio':'16:9','outputDirectory':str(out/family.lower()),'brandExecution':{'schema':'StudioBrandExecutionV1','sourceAuthority':'MEMORY_INPUT','memoryInputSnapshotId':'smoke-memory','memoryInputSnapshotHash':'b'*64,'brandExecutionHash':'c'*64,'tokens':{}},'finalBoard':board}

def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument('--install',action='store_true');ap.add_argument('--output',default=str(ROOT/'reports/STANDALONE_FAMILY_ENGINE_SMOKE.json'));args=ap.parse_args()
 if args.install:subprocess.run([sys.executable,str(ROOT/'scripts/install-engines.py')],cwd=ROOT,check=True)
 missing=[str(p) for p in ENGINE_PATHS.values() if not p.exists()]
 if missing:raise SystemExit('Engine sources are not installed. Run: python scripts/run-family-engine-smoke.py --install')
 env={**os.environ,
  'STUDIO_WHITEBOARD_ENGINE_ROOT':str(ENGINE_PATHS['WHITEBOARD']),
  'STUDIO_EXPLAINER_ENGINE_ROOT':str(ENGINE_PATHS['EXPLAINER']),
  'STUDIO_EDITORIAL_ENGINE_ROOT':str(ENGINE_PATHS['EDITORIAL_MOTION']),
  'STUDIO_STICKMAN_ENGINE_ROOT':str(ENGINE_PATHS['STICKMAN']),
  'STUDIO_SOUND_LIBRARY_ROOT':str(ENGINE_PATHS['SOUND']),
  'STUDIO_CHROMIUM_PATH':os.environ.get('STUDIO_CHROMIUM_PATH','/usr/bin/chromium')}
 worker=ROOT/'services/studio-family-engines/worker.py'; results={};passed=True
 with tempfile.TemporaryDirectory(prefix='studio-standalone-smoke-') as td:
  out=Path(td)
  for family in AUTHORITIES:
   if family=='EXPLAINER':
    eroot=ENGINE_PATHS['EXPLAINER']; runner=eroot/'scripts/studio-p8-explainer-runner.ts'; qa=eroot/'EXECUTION_BODY_QA.json'
    qobj=json.loads(qa.read_text()) if qa.exists() else {}
    rtxt=runner.read_text() if runner.exists() else ''
    ok=runner.exists() and qobj.get('status')=='PASS' and isinstance(qobj.get('passed'), int) and qobj.get('passed')==qobj.get('total') and qobj.get('total',0)>=40 and 'StudioFamilyExecutionFidelityV1' in rtxt and 'commercialScore:null' in rtxt and 'runNexMindExplainerDirectors' not in rtxt
    passed=passed and ok
    results[family]={'ok':ok,'status':'SOURCE_AND_SPINE_READY__LIVE_EXECUTION_ENV_REQUIRED' if ok else 'FAIL','authorityId':AUTHORITIES[family],'technicalQa':'EXECUTION_BODY_V2_QA' if qobj.get('status')=='PASS' else 'FAIL','finalVideoAudioSampleRate':None,'artifacts':[],'truthBoundary':'No fake P8 board is used for Explainer smoke. Live P8 + installed Node dependencies are required for encoded evidence.'}
    continue
   req=request_for(family,out)
   cp=subprocess.run([sys.executable,str(worker)],input=json.dumps(req),text=True,capture_output=True,cwd=worker.parent,env=env,check=True)
   result=json.loads(cp.stdout)
   artifacts=[]
   for item in result.get('artifacts') or []:
    p=Path(item['path']); actual=sha(p) if p.exists() else None
    artifacts.append({'kind':item.get('kind'),'bytes':p.stat().st_size if p.exists() else None,'sha256':item.get('sha256'),'hashMatches':actual==item.get('sha256')})
   video=next((Path(x['path']) for x in result.get('artifacts') or [] if x.get('kind')=='VIDEO'),None)
   audio_rate=None
   if video and video.exists():
    probe=json.loads(subprocess.run(['ffprobe','-v','error','-select_streams','a:0','-show_entries','stream=sample_rate','-of','json',str(video)],capture_output=True,text=True,check=True).stdout)
    streams=probe.get('streams') or [];audio_rate=(streams[0].get('sample_rate') if streams else None)
   ok=result.get('status')=='EVIDENCE_READY' and (result.get('technicalQa') or {}).get('status')=='PASS' and all(x['hashMatches'] for x in artifacts) and audio_rate=='48000'
   passed=passed and ok
   results[family]={'ok':ok,'status':result.get('status'),'authorityId':result.get('authorityId'),'technicalQa':(result.get('technicalQa') or {}).get('status'),'finalVideoAudioSampleRate':audio_rate,'artifacts':artifacts}
 report={'schema':'StudioStandaloneFamilyEngineSmokeV1','pass':passed,'sourceRoot':'.','families':results}
 Path(args.output).parent.mkdir(parents=True,exist_ok=True);Path(args.output).write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2));return 0 if passed else 1
if __name__=='__main__':raise SystemExit(main())
