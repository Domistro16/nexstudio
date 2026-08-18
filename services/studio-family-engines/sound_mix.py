from __future__ import annotations
import json,os,re,subprocess,hashlib
from pathlib import Path
from typing import Any,Dict,List
from contracts import AdapterBlocked,AdapterReplan,creative_replan_request,rational_seconds,require_review_board
from audio_provider import AudioRouteUnavailable,generate_audio

REGISTRY_REL='manifests/NEXSTUDIO_SOUND_V2_REGISTRY.json'

def _root()->Path:
 raw=os.environ.get('STUDIO_SOUND_LIBRARY_ROOT','').strip()
 if not raw: raise AdapterBlocked('STUDIO_SOUND_LIBRARY_ROOT_NOT_CONFIGURED','STUDIO_SOUND_LIBRARY_ROOT is required for directed sound evidence.')
 root=Path(raw).resolve()
 if not root.exists(): raise AdapterBlocked('STUDIO_SOUND_LIBRARY_ROOT_INVALID',str(root))
 return root

def _registry(root:Path)->Dict[str,List[Dict[str,Any]]]:
 p=root/REGISTRY_REL
 if not p.exists(): raise AdapterBlocked('STUDIO_SOUND_V2_REGISTRY_MISSING',str(p))
 try: data=json.loads(p.read_text())
 except Exception as e: raise AdapterBlocked('STUDIO_SOUND_V2_REGISTRY_INVALID',type(e).__name__)
 assets=data.get('assets') if isinstance(data,dict) else None
 if not isinstance(assets,list): raise AdapterBlocked('STUDIO_SOUND_V2_REGISTRY_INVALID','assets')
 by={}
 for a in assets:
  if not isinstance(a,dict) or a.get('status')!='ADMITTED' or a.get('selectable') is False: continue
  tag=str(a.get('semanticTag') or '').strip()
  path=root/str(a.get('path') or '')
  if tag and path.exists(): by.setdefault(tag,[]).append({**a,'resolvedPath':str(path)})
 if not by: raise AdapterBlocked('STUDIO_SOUND_V2_REGISTRY_EMPTY','No admitted selectable assets.')
 return by

def _choose_asset(by:Dict[str,List[Dict[str,Any]]],tag:str,event_id:str)->Dict[str,Any]|None:
 options=by.get(tag) or []
 if not options:return None
 # deterministic variation within the exact semantic tag; never substitutes another tag.
 idx=int(hashlib.sha256(f'{tag}:{event_id}'.encode()).hexdigest()[:8],16)%len(options)
 return options[idx]

def _sync_time(beat:Dict[str,Any],cursor:float,dur:float,target:str)->float|None:
 t=str(target or '').strip(); low=t.lower()
 if low in {'beat.start','start','onset'}: return cursor
 if low in {'beat.end','end','settle'}: return max(cursor,cursor+dur-.04)
 m=re.fullmatch(r'(?:beat\+)?([0-9]+(?:\.[0-9]+)?)s',low)
 if m:return min(cursor+dur,max(cursor,cursor+float(m.group(1))))
 actions=[a for a in beat.get('motion_actions') or [] if isinstance(a,dict)]
 for i,a in enumerate(actions):
  if t and t in {str(a.get('action_id') or ''),str(a.get('semantic_goal') or ''),str(a.get('causal_role') or '')}:
   return cursor+dur*((i+1)/(len(actions)+1))
 if low in {'narration','voice','spoken_line'}: return cursor+.04
 return None

def _gain(intensity:str)->float:
 return {'NONE':0.0,'SOFT':0.30,'MEDIUM':0.44,'STRONG':0.58,'PEAK':0.68}.get(str(intensity or 'SOFT').upper(),.30)

def render_p8_sound_mix(request:Dict[str,Any],out:Path)->Dict[str,Any]:
 board=request.get('finalBoard') or {}; beats=require_review_board(board); root=_root(); assets=_registry(root)
 requested_total=float(request.get('durationSeconds') or 60);default=requested_total/max(1,len(beats));cursor=0.0;events=[];narration=[];music=[]
 sound_direction=board.get('sound_direction') if isinstance(board.get('sound_direction'),dict) else {}
 narration_strategy=str(sound_direction.get('narration_strategy') or 'Follow the Story-authored narration purpose and preserve intelligibility.')
 mix_intent=sound_direction.get('mix_intent') if isinstance(sound_direction.get('mix_intent'),dict) else {}
 voice_preference=str(request.get('voicePreference') or 'Studio decides')
 duck_profile=str(mix_intent.get('ducking_profile') or 'MODERATE').upper(); duck_gain={'NONE':1.0,'LIGHT':.72,'MODERATE':.55,'STRONG':.38}.get(duck_profile,.55)
 for beat in beats:
  editorial=beat.get('editorial') if isinstance(beat.get('editorial'),dict) else {}; dur=rational_seconds(editorial.get('duration'),default)
  narration_mode=str(beat.get('narration_mode') or 'SILENT').upper(); narration_text=str(beat.get('narration_text') or '').strip()
  if narration_mode=='VOICEOVER':
   if not narration_text: raise AdapterReplan('STORY_NARRATION_TEXT_MISSING',f"Beat {beat.get('beat_id')} requires narration but has no authored text.",creative_replan_request(escalation_scope='STORY_AND_SOUND_STRATEGY',invalidate_slots=['storyboard','cinematography','editorial_rhythm','motion_performance','sound_direction'],issue='VOICEOVER beat has no Story-authored narration.',revision_plan='Repair Story narration or intentionally redesign as silent.',quality_reason='NARRATION_AUTHORING_INCOMPLETE'))
   tts_path=out.parent/f"narration-{str(beat.get('beat_id') or 'beat')}.wav"
   try: generated=generate_audio('TTS',{'productionId':request.get('productionId'),'beatId':beat.get('beat_id'),'text':narration_text,'voicePreference':voice_preference,'performanceIntent':narration_strategy,'narrationPurpose':str(beat.get('narration_purpose') or ''),'targetDurationSeconds':dur},tts_path)
   except AudioRouteUnavailable as exc: raise AdapterReplan('NARRATION_ROUTE_UNAVAILABLE',str(exc),creative_replan_request(escalation_scope='STORY_AND_SOUND_STRATEGY',invalidate_slots=['storyboard','cinematography','editorial_rhythm','motion_performance','sound_direction'],issue='Committed narration has no working commercial TTS route.',revision_plan='Re-author intentionally without narration or restore the declared TTS route.',quality_reason='NARRATION_EXECUTION_CAPABILITY_UNAVAILABLE'))
   if float(generated['durationSeconds'])>max(.25,dur-.08): raise AdapterReplan('NARRATION_EXCEEDS_BEAT_DURATION',f"{beat.get('beat_id')}:{generated['durationSeconds']:.3f}>{dur:.3f}",creative_replan_request(escalation_scope='STORY_AND_EDITORIAL_STRATEGY',invalidate_slots=['storyboard','cinematography','editorial_rhythm','motion_performance','sound_direction'],issue='Narration does not fit committed editorial duration.',revision_plan='Rewrite narration or revise editorial duration; do not time-stretch speech unnaturally.',quality_reason='NARRATION_EDITORIAL_FIT_FAILURE'))
   narration.append({'eventId':f"NARRATION-{beat.get('beat_id')}",'beatId':beat.get('beat_id'),'kind':'NARRATION','source':generated['path'],'at':round(cursor+.04,4),'gain':1.0,'routeId':generated['routeId'],'rightsEvidence':generated['rightsEvidence'],'durationSeconds':generated['durationSeconds']})
  for ev in beat.get('sound_events') or []:
   if not isinstance(ev,dict): continue
   kind=str(ev.get('kind') or '').upper(); tag=str(ev.get('semantic_tag') or '').strip(); event_id=str(ev.get('event_id') or '')
   if kind in {'SILENCE','NARRATION_ACCENT'}: continue
   at=_sync_time(beat,cursor,dur,str(ev.get('sync_target') or ''))
   if at is None:
    if ev.get('optional'): continue
    raise AdapterReplan('DIRECTED_SOUND_SYNC_TARGET_UNRESOLVED',str(ev.get('sync_target') or ''),creative_replan_request(escalation_scope='SOUND_STRATEGY',invalidate_slots=['sound_direction'],issue=f"Sound event {event_id} has no executable P8 sync target.",revision_plan='Bind it to a real motion action/beat boundary or remove it deliberately.',quality_reason='SOUND_SYNC_CAPABILITY_MISMATCH'))
   if kind=='MUSIC_CUE':
    music_path=out.parent/f"music-{event_id or len(music)+1}.wav"
    try: generated=generate_audio('MUSIC',{'productionId':request.get('productionId'),'beatId':beat.get('beat_id'),'semanticTag':tag,'narrativeReason':ev.get('narrative_reason'),'intensity':ev.get('intensity'),'targetDurationSeconds':dur,'rightsPolicy':'COMMERCIAL_USE_EVIDENCE_REQUIRED'},music_path)
    except AudioRouteUnavailable as exc:
     if ev.get('optional'): continue
     raise AdapterReplan('MUSIC_ROUTE_OR_LICENSED_ASSET_REQUIRED',str(exc),creative_replan_request(escalation_scope='SOUND_STRATEGY',invalidate_slots=['sound_direction'],issue='Committed music cue has no rights-declared working route.',revision_plan='Restore a commercial-rights music route or re-author Sound without music.',quality_reason='MUSIC_RIGHTS_OR_EXECUTION_CAPABILITY_UNAVAILABLE'))
    music.append({'eventId':event_id,'beatId':beat.get('beat_id'),'kind':'MUSIC','source':generated['path'],'at':round(at,4),'gain':_gain(ev.get('intensity'))*duck_gain,'routeId':generated['routeId'],'rightsEvidence':generated['rightsEvidence']}); continue
   asset=_choose_asset(assets,tag,event_id)
   if not asset:
    if ev.get('optional'): continue
    raise AdapterReplan('DIRECTED_SOUND_TAG_UNMAPPED',tag,creative_replan_request(escalation_scope='SOUND_STRATEGY',invalidate_slots=['sound_direction'],issue=f'No admitted Sound V2 asset exists for exact semantic tag {tag}.',revision_plan='Choose an authorized exact semantic event or a rights-safe route; never substitute an unrelated sound.',quality_reason='SOUND_RESOURCE_CAPABILITY_MISMATCH'))
   event_duck=str(ev.get('ducking') or 'NONE').upper(); event_gain=_gain(ev.get('intensity'))*({'NONE':1.0,'LIGHT':.85,'MODERATE':.68,'STRONG':.50}.get(event_duck,1.0))
   events.append({'eventId':event_id,'beatId':beat.get('beat_id'),'semanticTag':tag,'kind':kind,'source':asset['resolvedPath'],'assetId':asset.get('assetId'),'assetSha256':asset.get('productionSha256'),'rights':asset.get('license'),'at':round(at,4),'gain':event_gain,'syncTarget':ev.get('sync_target')})
  cursor+=dur
 duration=max(.25,cursor); all_events=[*narration,*music,*events]; out.parent.mkdir(parents=True,exist_ok=True)
 if not all_events:
  subprocess.run(['ffmpeg','-y','-loglevel','error','-f','lavfi','-i',f'anullsrc=r=48000:cl=stereo:d={duration}','-c:a','pcm_s24le',str(out)],check=True)
  return {'path':str(out),'durationSeconds':duration,'events':[],'narration':[],'music':[],'silenceOnly':True,'authority':'P8_DIRECTED_SOUND_V2_REGISTRY','mixIntent':mix_intent}
 cmd=['ffmpeg','-y','-loglevel','error','-f','lavfi','-i',f'anullsrc=r=48000:cl=stereo:d={duration}']
 for e in all_events: cmd+=['-i',e['source']]
 chains=[]; labels=[]
 for i,e in enumerate(all_events,1):
  ms=max(0,int(e['at']*1000)); lab=f'a{i}'; chains.append(f'[{i}:a]aresample=48000,volume={e["gain"]},adelay={ms}|{ms}[{lab}]'); labels.append(f'[{lab}]')
 chains.append('[0:a]anull[base]'); chains.append(f'[base]{"".join(labels)}amix=inputs={len(labels)+1}:duration=longest:normalize=0,atrim=0:{duration},alimiter=limit=0.86[out]')
 cmd+=['-filter_complex',';'.join(chains),'-map','[out]','-ar','48000','-ac','2','-c:a','pcm_s24le',str(out)]; subprocess.run(cmd,check=True)
 return {'path':str(out),'durationSeconds':duration,'events':[{k:v for k,v in e.items() if k!='source'} for e in events],'narration':[{k:v for k,v in e.items() if k!='source'} for e in narration],'music':[{k:v for k,v in e.items() if k!='source'} for e in music],'silenceOnly':False,'authority':'P8_DIRECTED_SOUND_V2_REGISTRY','registryAssetCount':sum(len(x) for x in assets.values()),'mixIntent':mix_intent,'ttsPolicy':'RUNTIME_DECLARED_ONLY','musicPolicy':'RIGHTS_DECLARED_ROUTE_ONLY'}
