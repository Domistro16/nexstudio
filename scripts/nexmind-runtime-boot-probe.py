#!/usr/bin/env python3
"""Real boot/conformance probe for configured NexMind model routes.

Makes tiny live inference calls. Visual/Art are probed with an image. Final
Producer/Auditor are probed with image + native audio. Output is a build-bound
attestation consumed by Studio's pre-payment readiness gate. It never marks a
missing credential/model/binary as PASS.
"""
from __future__ import annotations
import base64, io, json, os, struct, subprocess, time, urllib.request, urllib.error, wave
from datetime import datetime, timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vendor/nexmind-god-mode-p8/src'))
from nexmind_god_mode.live_provider import RoleRouter

PNG='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAAbUlEQVR42u3XMQ0AIAxFQeQgAmGoQwkikICBMnWBcAljB256+WWNFr7aZ/huuy8AAAAAACnAKx893QMAAAAA5ABKDAAAAGAPKDEAAACAPaDEAAAAAPaAEgMAAADYA0oMAAAAYA8oMQAAAMA3gA2g9DGWVZTODQAAAABJRU5ErkJggg=='
def wav_url():
    bio=io.BytesIO()
    with wave.open(bio,'wb') as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(48000);w.writeframes(b'\x00\x00\x00\x00'*4800)
    return 'data:audio/wav;base64,'+base64.b64encode(bio.getvalue()).decode()
AUDIO=wav_url()
TASKS=['story','visual','art','final_producer','perceptual_auditor']
def role_name(task,router): return router.ROLE_NAMES[task]
def endpoint(base,mode):
    base=base.rstrip('/'); suffix='/responses' if mode=='responses' else '/chat/completions'
    return base if base.endswith(suffix) else base+suffix
def audio_part(route):
    raw=AUDIO.split(',',1)[1]
    return {'type':'input_audio','input_audio':{'data':raw,'format':'wav'}}
def payload(route,task):
    prompt='Runtime conformance probe only. Inspect supplied modalities and reply with exactly NEXMIND_BOOT_PROBE_OK.'
    wants_image=task in {'visual','art','final_producer','perceptual_auditor'}
    wants_audio=task in {'final_producer','perceptual_auditor'}
    if route.api_mode=='responses':
        content=[{'type':'input_text','text':prompt}]
        if wants_image: content.append({'type':'input_image','image_url':PNG})
        if wants_audio: content.append(audio_part(route))
        return {'model':route.model,'input':[{'role':'user','content':content}],'store':False}
    content=[{'type':'text','text':prompt}]
    if wants_image: content.append({'type':'image_url','image_url':{'url':PNG}})
    if wants_audio: content.append(audio_part(route))
    return {'model':route.model,'messages':[{'role':'user','content':content}]}
def extract(data,mode):
    if mode=='responses':
        if isinstance(data.get('output_text'),str): return data['output_text']
        return json.dumps(data)
    try:return str(data['choices'][0]['message']['content'])
    except Exception:return json.dumps(data)
def live_probe(route,task):
    key=os.getenv(route.api_key_env,'')
    if not key:return False,'missing credential '+route.api_key_env
    if not route.base_url:return False,'missing base_url'
    if task in {'visual','art','final_producer','perceptual_auditor'} and 'images' not in route.input_modalities:return False,'missing images modality'
    if task in {'final_producer','perceptual_auditor'} and ('audio' not in route.input_modalities or not route.audio_input_mode):return False,'missing native audio modality/mode'
    req=urllib.request.Request(endpoint(route.base_url,route.api_mode),data=json.dumps(payload(route,task)).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=30) as r:data=json.loads(r.read().decode())
        text=extract(data,route.api_mode)
        return ('NEXMIND_BOOT_PROBE_OK' in text),text[:200]
    except urllib.error.HTTPError as e:
        body=e.read().decode('utf-8',errors='replace')[:700]
        return False,f'HTTP {e.code}: {body}'
    except Exception as e:return False,str(e)[:300]
def main():
    router=RoleRouter(); rows=[]; all_ok=True
    for task in TASKS:
        try: routes=router.resolve_candidates(task)
        except Exception as e:
            rows.append({'task':task,'role':router.ROLE_NAMES.get(task,task),'model':'','probeStatus':'FAIL','detail':str(e)});all_ok=False;continue
        if not routes:
            rows.append({'task':task,'role':role_name(task,router),'model':'','probeStatus':'FAIL','detail':'no compatible route'});all_ok=False;continue
        route=routes[0];ok,detail=live_probe(route,task);all_ok &= ok
        rows.append({'task':task,'role':route.role,'provider':route.provider,'model':route.model,'probeStatus':'PASS' if ok else 'FAIL','detail':detail,'inputModalities':list(route.input_modalities),'audioInputMode':route.audio_input_mode,'apiMode':route.api_mode})
    for binary in ('ffmpeg','ffprobe'):
        ok=subprocess.run([binary,'-version'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0 if shutil_which(binary) else False
        all_ok &= ok; rows.append({'task':'binary','role':binary,'model':'','probeStatus':'PASS' if ok else 'FAIL','detail':'binary -version'})
    out={'schema':'StudioNexMindRuntimeBootAttestationV1','status':'PASS' if all_ok else 'BLOCKED','p8BuildHash':os.getenv('NEXMIND_P8_BUILD_HASH',''),'checkedAt':datetime.now(timezone.utc).isoformat(),'routes':rows}
    print(json.dumps(out,separators=(',',':')))
    return 0 if all_ok else 2
def shutil_which(name):
    import shutil; return shutil.which(name)
if __name__=='__main__': raise SystemExit(main())
