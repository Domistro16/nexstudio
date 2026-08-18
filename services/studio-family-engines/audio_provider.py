from __future__ import annotations
import json, os, subprocess, tempfile
from pathlib import Path
from typing import Any, Dict, List

from contracts import AdapterBlocked

class AudioRouteUnavailable(RuntimeError): pass


def declared_routes(env_name: str) -> List[Dict[str, Any]]:
    raw=os.environ.get(env_name,'').strip()
    if not raw:return []
    try: parsed=json.loads(raw)
    except Exception as exc: raise AdapterBlocked('AUDIO_ROUTE_REGISTRY_INVALID',f'{env_name}:{type(exc).__name__}')
    if isinstance(parsed,dict): parsed=parsed.get('routes') or []
    if not isinstance(parsed,list): raise AdapterBlocked('AUDIO_ROUTE_REGISTRY_INVALID',f'{env_name}:routes')
    routes=[]
    for item in parsed:
        if not isinstance(item,dict):continue
        rid=str(item.get('id') or '').strip();cmd=item.get('command')
        if not rid or not isinstance(cmd,list) or not cmd or not all(isinstance(x,str) and x.strip() for x in cmd):continue
        if item.get('commercialUseAllowed') is not True:continue
        credential=str(item.get('credentialEnv') or '').strip()
        if credential and not os.environ.get(credential,'').strip():continue
        routes.append({**item,'id':rid,'priority':int(item.get('priority') or 0),'command':list(cmd)})
    return sorted(routes,key=lambda x:(-x['priority'],x['id']))


def _probe_duration(path:Path)->float:
    cp=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(path)],capture_output=True,text=True)
    if cp.returncode!=0:raise AudioRouteUnavailable('generated audio could not be probed')
    try:return float(cp.stdout.strip())
    except Exception:raise AudioRouteUnavailable('generated audio duration invalid')


def generate_audio(kind:str,payload:Dict[str,Any],out:Path)->Dict[str,Any]:
    env_name='NEXSTUDIO_TTS_ROUTES_JSON' if kind=='TTS' else 'NEXSTUDIO_MUSIC_ROUTES_JSON'
    routes=declared_routes(env_name)
    if not routes:raise AudioRouteUnavailable(f'NO_DECLARED_{kind}_ROUTE')
    failures=[]
    out.parent.mkdir(parents=True,exist_ok=True)
    for route in routes:
        with tempfile.TemporaryDirectory(prefix=f'nexstudio-{kind.lower()}-') as td:
            raw=Path(td)/'generated-audio'
            env={**os.environ,'NEXSTUDIO_AUDIO_OUTPUT_PATH':str(raw),'NEXSTUDIO_AUDIO_ROUTE_ID':route['id'],'NEXSTUDIO_AUDIO_KIND':kind}
            request={
                'schema':'NexStudioAudioProviderRequestV1',
                'kind':kind,
                'routeId':route['id'],
                'payload':payload,
                'outputPath':str(raw),
                'requirements':{'commercialUseAllowed':True,'noTrainingRightsAssumption':True,'audioOnly':True},
            }
            try:
                cp=subprocess.run(route['command'],input=json.dumps(request),text=True,capture_output=True,env=env,timeout=int(route.get('timeoutSeconds') or 120))
                if cp.returncode!=0:
                    failures.append(f"{route['id']}:exit-{cp.returncode}");continue
                meta={}
                if cp.stdout.strip():
                    try:meta=json.loads(cp.stdout.strip().splitlines()[-1])
                    except Exception:meta={}
                generated=Path(str(meta.get('audioPath') or raw))
                if not generated.exists() or generated.stat().st_size<=44:
                    failures.append(f"{route['id']}:no-audio");continue
                # Normalize the plug-in result into Studio's deterministic mix format.
                norm=out
                conv=subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(generated),'-ar','48000','-ac','2','-c:a','pcm_s24le',str(norm)],capture_output=True,text=True)
                if conv.returncode!=0 or not norm.exists():
                    failures.append(f"{route['id']}:normalize-failed");continue
                return {
                    'path':str(norm),'routeId':route['id'],'durationSeconds':_probe_duration(norm),
                    'rightsEvidence':meta.get('rightsEvidence') or {'commercialUseAllowed':True,'declaredByOperatorRoute':True},
                    'providerEvidence':meta.get('providerEvidence') or {},
                }
            except subprocess.TimeoutExpired:
                failures.append(f"{route['id']}:timeout")
            except Exception as exc:
                failures.append(f"{route['id']}:{type(exc).__name__}")
    raise AudioRouteUnavailable(';'.join(failures) or f'NO_WORKING_{kind}_ROUTE')
