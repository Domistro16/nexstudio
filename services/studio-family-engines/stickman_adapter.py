from __future__ import annotations
import json,os,subprocess,tempfile,hashlib
from pathlib import Path
from typing import Any,Dict
from PIL import Image,ImageOps
import cairosvg
from contracts import AdapterBlocked,AdapterReplan,creative_replan_request,require_review_board
from canonical import stable
from sound_mix import render_p8_sound_mix

def _root()->Path:
 raw=os.environ.get('STUDIO_STICKMAN_ENGINE_ROOT','').strip()
 if not raw:raise AdapterBlocked('STICKMAN_ENGINE_ROOT_NOT_CONFIGURED')
 root=Path(raw).resolve()
 if not (root/'cast/runtime/nexstick-cast-v2.js').exists():raise AdapterBlocked('STICKMAN_ENGINE_ROOT_INVALID',str(root))
 return root
def _sha(p:Path):return hashlib.sha256(p.read_bytes()).hexdigest()
def build_internal_evidence(request:Dict[str,Any])->Dict[str,Any]:
 require_review_board(request.get('finalBoard') or {});root=_root();out=Path(request.get('outputDirectory') or tempfile.mkdtemp(prefix='studio-stickman-evidence-'));out.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='studio-stickman-p8-') as td:
  td=Path(td);svgs=td/'svgs';svgs.mkdir();req=td/'request.json';req.write_text(json.dumps(request));runner=Path(__file__).with_name('stickman_render.cjs')
  env={**os.environ,'STUDIO_STICKMAN_ENGINE_ROOT':str(root)};r=subprocess.run(['node',str(runner),str(req),str(svgs)],capture_output=True,text=True,env=env,check=True);meta=json.loads(r.stdout.strip());
  if not meta.get('ok'):
   code=str(meta.get('code') or 'STICKMAN_RENDER_BLOCKED');detail=str(meta.get('detail') or '')
   creative_codes={
    'STICKMAN_CAST_SELECTION_REQUIRED','STICKMAN_BEAT_REQUIRES_STICKMAN_ACTION','STICKMAN_MOTION_BINDING_UNSUPPORTED',
    'STICKMAN_CONTACT_ACTION_NEEDS_EXPLICIT_ENGINE_TARGET','STICKMAN_ACTOR_REQUIRED','STICKMAN_SEQUENCE_BLOCKED',
    'STICKMAN_SEQUENCE_QA_BLOCKED','STICKMAN_RENDER_STATE_BLOCKED','P8_FINAL_BOARD_DEPARTMENTS_UNRESOLVED'
   }
   if code in creative_codes:
    scope='PERFORMANCE_STRATEGY' if code.startswith('STICKMAN_') else 'UPSTREAM_VISUAL_STRATEGY'
    raise AdapterReplan(code,detail,creative_replan_request(
     escalation_scope=scope,
     invalidate_slots=['storyboard','cinematography','editorial_rhythm','motion_performance','sound_direction'],
     issue=f'The committed Stickman performance cannot be executed at the current proven quality/capability floor ({code}): {detail}',
     revision_plan='Preserve the beat purpose and requested Stickman family. Re-stage the action, interaction, blocking or cast/performance choice into an equally clear and engaging realization supported by the proven Stickman performance body.',
     quality_reason='STICKMAN_PERFORMANCE_CAPABILITY_OR_QA_REPLAN_REQUIRED',
     constraints=['Do not silently approximate unsupported contact/action with decorative motion.','Do not switch out of Stickman merely to make the engine pass.','Keep the requested meaning and audience-state change intact.'],
    ))
   raise AdapterBlocked(code,detail)
  pngs=td/'pngs';pngs.mkdir(); files=sorted(svgs.glob('frame-*.svg'))
  for f in files:cairosvg.svg2png(bytestring=f.read_bytes(),write_to=str(pngs/(f.stem+'.png')),output_width=meta['width'],output_height=meta['height'])
  visual=td/'visual.mp4';subprocess.run(['ffmpeg','-y','-loglevel','error','-framerate',str(meta['fps']),'-i',str(pngs/'frame-%05d.png'),'-r','24','-c:v','libx264','-pix_fmt','yuv420p','-t',str(meta['duration']),str(visual)],check=True)
  mix=render_p8_sound_mix(request,td/'directed.wav');video=out/'internal-review.mp4';subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(visual),'-i',mix['path'],'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','128k','-shortest',str(video)],check=True);audio=out/'internal-review-audio.wav';audio.write_bytes(Path(mix['path']).read_bytes())
  picks=[pngs/f'frame-{round(i*(len(files)-1)/3):05d}.png' for i in range(4)] if len(files)>1 else [pngs/(files[0].stem+'.png')]*4;ims=[Image.open(p).convert('RGB') for p in picks];w=max(x.width for x in ims);h=max(x.height for x in ims);sheet=Image.new('RGB',(w*2,h*2),(20,20,20));
  for i,im in enumerate(ims):sheet.paste(ImageOps.fit(im,(w,h)),((i%2)*w,(i//2)*h))
  sheetp=out/'contact-sheet.jpg';sheet.save(sheetp,quality=90);probe=json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration,size','-show_entries','stream=codec_type,width,height,sample_rate,channels','-of','json',str(video)],capture_output=True,text=True,check=True).stdout)
  planp=out/'engine-plan.json';planp.write_text(json.dumps({'schema':'StudioStickmanP8ExecutionPlanV1','render':meta,'creativeStateArtifactHash':request.get('creativeStateArtifactHash'),'finalBoardHash':stable(request.get('finalBoard')),'creativeChoiceIntroduced':False},indent=2)+'\n')
  arts=[{'kind':'VIDEO','path':str(video),'mimeType':'video/mp4','sha256':_sha(video),'bytes':video.stat().st_size},{'kind':'AUDIO_MIX','path':str(audio),'mimeType':'audio/wav','sha256':_sha(audio),'bytes':audio.stat().st_size},{'kind':'CONTACT_SHEET','path':str(sheetp),'mimeType':'image/jpeg','sha256':_sha(sheetp),'bytes':sheetp.stat().st_size}]
  return {'schema':'StudioFamilyEngineResultV1','status':'EVIDENCE_READY','family':'STICKMAN','authorityId':request.get('authorityId'),'enginePlanHash':_sha(planp),'technicalQa':{'status':'PASS','authority':'NEXSTICK_V5_1_SEQUENCE_QA_PLUS_MEDIA_PROBE','ffprobe':probe,'render':meta},'soundBinding':mix,'artifacts':arts,'enginePlanPath':str(planp),'audioExpected':True}
