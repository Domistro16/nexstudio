#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'vendor/nexmind-god-mode-p8/src'))
from nexmind_god_mode.live_provider import RoleRouter
from nexmind_god_mode.provider import ProviderError
CONTROLS=ROOT/'evaluations/nexmind-p8-commercial-brain-v2/CREATIVE_NEGATIVE_CONTROLS_V3.json'
OUT=ROOT/'reports/P8_FINAL_JUDGMENT_NEGATIVE_MEDIA_GATE.json'
ap=argparse.ArgumentParser();ap.add_argument('--manifest');a=ap.parse_args();defs=json.loads(CONTROLS.read_text());controls=defs.get('controls') or defs.get('negative_controls') or []
required_ids=[str(x.get('id')) for x in controls];checks=[]
def ck(name,ok,detail=''):checks.append({'name':name,'ok':bool(ok),'detail':detail})
ck('Locked negative-control definitions exist',len(required_ids)>=8,str(len(required_ids)))
manifest={}
if a.manifest and Path(a.manifest).exists(): manifest=json.loads(Path(a.manifest).read_text())
items={str(x.get('id')):x for x in (manifest.get('controls') or []) if isinstance(x,dict)}
media_missing=[];media_valid=[]
for cid in required_ids:
 item=items.get(cid);video=Path(str((item or {}).get('video') or ''));audio=Path(str((item or {}).get('audio') or ''))
 if not item or not video.is_file() or not audio.is_file():media_missing.append(cid);continue
 try:
  v=json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_type,width,height,r_frame_rate,sample_rate,channels','-of','json',str(video)],capture_output=True,text=True,check=True).stdout)
  au=json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_type,sample_rate,channels','-of','json',str(audio)],capture_output=True,text=True,check=True).stdout)
  has_v=any(x.get('codec_type')=='video' and x.get('width') for x in v.get('streams') or []);has_a=any(x.get('codec_type')=='audio' for x in au.get('streams') or [])
  if has_v and has_a:media_valid.append(cid)
  else:media_missing.append(cid)
 except Exception:media_missing.append(cid)
try: routes=RoleRouter().resolve_candidates('final_producer');live_final=bool(routes);route_detail=[{'provider':x.provider,'modelConfigured':bool(x.model)} for x in routes]
except ProviderError as e:live_final=False;route_detail={'status':'UNAVAILABLE','reason':str(e)}
ck('Recorded/structural fixture cannot substitute for encoded negative-control media',True)
status='READY_FOR_LIVE_FINAL_JUDGMENT' if not media_missing and live_final else ('BLOCKED_NO_ENCODED_NEGATIVE_CONTROL_MEDIA' if media_missing else 'BLOCKED_NO_LIVE_MULTIMODAL_FINAL_JUDGE')
result={'schema':'NexMindP8FinalJudgmentNegativeMediaGateV1','status':status,'pass':all(x['ok'] for x in checks),'passed':sum(x['ok'] for x in checks),'total':len(checks),'checks':checks,'requiredControlIds':required_ids,'encodedMediaReady':media_valid,'missingEncodedMedia':media_missing,'finalProducerRoute':route_detail,'commercialScoreEmitted':False,'commercialScoreEvidence':False,'truthBoundary':'Final taste certification requires real encoded video + audio for every negative-control class and a capability-routed live multimodal Final Producer. Policy fixtures alone cannot raise the Final Judgment score.'}
OUT.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));raise SystemExit(0 if result['pass'] else 1)
