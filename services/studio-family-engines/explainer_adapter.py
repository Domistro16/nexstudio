from __future__ import annotations
import base64,hashlib,json,os,subprocess
from pathlib import Path
from typing import Any,Dict
from PIL import Image,ImageOps
from contracts import AdapterBlocked,AdapterReplan,creative_replan_request,require_review_board
from sound_mix import render_p8_sound_mix
from authored_art import capability_available as authored_art_available, execute_scene as execute_authored_scene, ArtExecutionUnavailable, ArtExecutionInvalid

def _root()->Path:
 raw=os.environ.get('STUDIO_EXPLAINER_ENGINE_ROOT','').strip()
 if not raw: raise AdapterBlocked('EXPLAINER_ENGINE_ROOT_NOT_CONFIGURED')
 root=Path(raw).resolve(); candidates=[root,*[p for p in root.glob('*') if p.is_dir()]]
 for c in candidates:
  if (c/'scripts'/'studio-p8-explainer-runner.ts').exists() and (c/'src'/'studio'/'explainer-motion-v1'/'nexart'/'production-art.ts').exists(): return c
 raise AdapterBlocked('EXPLAINER_EXECUTION_BODY_ROOT_INVALID',str(root))

def _sha(p:Path): return hashlib.sha256(p.read_bytes()).hexdigest()
def _sheet(frames:Path,out:Path):
 fs=sorted([*frames.glob('*.jpg'),*frames.glob('*.png')]);
 if not fs: raise AdapterBlocked('EXPLAINER_RENDER_NO_FRAMES')
 picks=[fs[round(i*(len(fs)-1)/3)] for i in range(4)] if len(fs)>1 else fs*4
 ims=[Image.open(p).convert('RGB') for p in picks];w=max(x.width for x in ims);h=max(x.height for x in ims);can=Image.new('RGB',(w*2,h*2),(20,20,20))
 for i,im in enumerate(ims): can.paste(ImageOps.fit(im,(w,h)),((i%2)*w,(i//2)*h))
 can.save(out,quality=90)

def _tsx(root:Path)->Path:
 raw=os.environ.get('STUDIO_EXPLAINER_TSX_BIN','').strip()
 candidates=[Path(raw)] if raw else []
 candidates += [Path.cwd()/'node_modules'/'.bin'/'tsx',root/'node_modules'/'.bin'/'tsx']
 for p in candidates:
  if str(p) and p.exists(): return p.resolve()
 raise AdapterBlocked('EXPLAINER_EXECUTION_BODY_DEPENDENCIES_NOT_INSTALLED','tsx not found. Install Standalone Studio production dependencies before rendering.')

def _semantic_strings(value:Any)->list[str]:
 out=[]
 if not isinstance(value,list): return out
 for item in value:
  if isinstance(item,str) and item.strip(): out.append(item.strip())
  elif isinstance(item,dict):
   for key in ("label","semantic_ref","role","name","id"):
    text=item.get(key)
    if isinstance(text,str) and text.strip(): out.append(text.strip()); break
 return out

def _authored_scene_request(beat:Dict[str,Any],production_id:str)->Dict[str,Any]:
 art=beat.get("art_direction") if isinstance(beat.get("art_direction"),dict) else {}
 comp=art.get("composition") if isinstance(art.get("composition"),dict) else {}
 directives=comp.get("execution_directives") if isinstance(comp.get("execution_directives"),dict) else {}
 if not str(beat.get("hero_identity") or "").strip(): raise AdapterBlocked("EXPLAINER_HERO_IDENTITY_REQUIRED",str(beat.get("beat_id")))
 supports=_semantic_strings(beat.get("supporting_assets"))
 return {
  "sceneId":f"{production_id}.{beat.get('beat_id')}","beatId":beat.get("beat_id"),"heroRole":str(beat.get("hero_identity") or "").strip(),
  "supportingRoles":supports,"sourceText":str(beat.get("scene_thesis") or ""),"visualDirection":beat.get("visual_direction") if isinstance(beat.get("visual_direction"),dict) else {},
  "artDirection":art,"artExecutionDirectives":directives,
  "semanticNeeds":{"objectNeeds":[{"concept":x} for x in supports],"environmentNeed":str(art.get("environment_state") or ""),"propSpecificityNeed":str(art.get("prop_specificity") or ""),"characterPerformanceNeed":str(art.get("character_performance_state") or "")},
 }

def _authored_plate_payload(plate:Dict[str,Any],beat_id:str)->Dict[str,Any]:
 stages=[]
 for path in plate.get("stage_files") or []:
  raw=Path(path).read_bytes(); stages.append({"pngDataUrl":"data:image/png;base64,"+base64.b64encode(raw).decode("ascii"),"sha256":hashlib.sha256(raw).hexdigest()})
 if not stages: raise ArtExecutionInvalid("ART_STAGE_FILES_EMPTY")
 return {"schema":"NexStudioAuthoredScenePlateBindingV1","beatId":beat_id,"lockedSemanticsHash":plate["locked_semantics_hash"],"semanticBindings":plate.get("semantic_bindings") or [],"stages":stages,"creativeChoiceIntroduced":False}

def build_internal_evidence(request:Dict[str,Any])->Dict[str,Any]:
 board=request.get('finalBoard') or {}; require_review_board(board)
 checkpoint=request.get('creativeCheckpoint') or {}
 if not isinstance(checkpoint,dict) or checkpoint.get('schema')!='NexMindSupremeShowrunnerCheckpointV1': raise AdapterBlocked('P8_CREATIVE_CHECKPOINT_REQUIRED')
 decisions=((checkpoint.get('state') or {}).get('decisions') or {}) if isinstance(checkpoint.get('state'),dict) else {}
 required={'film_thesis','visual_concept','art_direction','storyboard','cinematography','editorial_rhythm','motion_performance','sound_direction'}
 missing=sorted(required-set(decisions))
 if missing: raise AdapterBlocked('P8_CREATIVE_DEPARTMENTS_INCOMPLETE',','.join(missing))
 root=_root(); out_root=Path(request.get('outputDirectory') or '.').resolve();out_root.mkdir(parents=True,exist_ok=True)
 authored_plates=[]
 # The P8 Explainer path is authored-art-only. The legacy scene-family/object/world
 # catalogues are not creative fallbacks; if exact P8 pixels cannot be produced,
 # execution must replan rather than silently substitute a house template.
 if not authored_art_available():
  raise AdapterReplan('EXPLAINER_AUTHORED_ART_CAPABILITY_REQUIRED','Explainer execution requires the production-scoped authored-art body for every P8 beat.',creative_replan_request(
   escalation_scope='ART_AND_VISUAL_STRATEGY',invalidate_slots=['art_direction','storyboard','cinematography','editorial_rhythm','motion_performance','sound_direction'],
   issue='The exact Explainer art realization cannot be executed because the authored-art capability is unavailable.',
   revision_plan='Preserve the Film Thesis and visual concept if possible; route through an available premium authored-art body or re-author the visual strategy. Do not downgrade to generic cards, icons, canned rooms or diagram shorthand.',
   quality_reason='EXPLAINER_AUTHORED_ART_EXECUTOR_UNAVAILABLE',constraints=['No silent generic fallback.','No renderer-authored creative substitution.']))
 for beat in require_review_board(board):
  scene=_authored_scene_request(beat,str(request.get('productionId')))
  # Preserve exact P8 execution commitments in the locked authored-art request.
  scene['p8MotionActions']=beat.get('motion_actions') if isinstance(beat.get('motion_actions'),list) else []
  scene['p8Camera']=beat.get('camera') if isinstance(beat.get('camera'),dict) else {}
  scene['brandExecution']=request.get('brandExecution')
  try:
   brand=request.get('brandExecution') if isinstance(request.get('brandExecution'),dict) else {};
   if brand.get('schema')!='StudioBrandExecutionV1' or not brand.get('brandExecutionHash'): raise AdapterBlocked('EXPLAINER_BRAND_EXECUTION_REQUIRED')
   plate=execute_authored_scene(scene,'EXPLAINER','brand:'+str(brand['brandExecutionHash']),request.get('aspectRatio') or '16:9',out_root/'authored-art'/str(beat.get('beat_id')))
  except (ArtExecutionUnavailable,ArtExecutionInvalid) as e:
   raise AdapterReplan('EXPLAINER_AUTHORED_ART_EXECUTION_REPLAN_REQUIRED',str(e),creative_replan_request(
    escalation_scope='ART_AND_VISUAL_STRATEGY',invalidate_slots=['art_direction','storyboard','cinematography','editorial_rhythm','motion_performance','sound_direction'],
    issue='The authored-art execution body could not faithfully realize the committed Explainer scene: '+str(e),
    revision_plan='Repair the Art realization or select a different premium executable treatment while preserving Film Thesis, facts and Brand intent.',
    quality_reason='EXPLAINER_AUTHORED_ART_SEMANTIC_OR_EXECUTION_FAILURE',constraints=['Do not drop required hero/support semantics.','No generic renderer fallback.'])) from e
  authored_plates.append(_authored_plate_payload(plate,str(beat.get('beat_id'))))
 runner_request={'schema':'StudioP8ExplainerExecutionRequestV1','operation':request.get('operation'),'productionId':request.get('productionId'),'durationSeconds':request.get('durationSeconds'),'aspectRatio':request.get('aspectRatio') or '16:9','outputDirectory':str(out_root),'finalBoard':board,'creativeCheckpoint':checkpoint,'creativeDossier':request.get('creativeDossier'),'referenceMedia':request.get('referenceMedia') or [],'authoredScenePlates':authored_plates,'executionPlan':request.get('executionPlan'),'brandExecution':request.get('brandExecution')}
 child_env=os.environ.copy(); child_env.setdefault('NEXMIND_PROVIDER','custom')
 proc=subprocess.run([str(_tsx(root)),str(root/'scripts'/'studio-p8-explainer-runner.ts')],cwd=root,env=child_env,input=json.dumps(runner_request),text=True,capture_output=True)
 if proc.returncode!=0:
  detail=(proc.stderr or proc.stdout or 'Explainer execution body failed')[-1800:]
  creative_markers=('PRODUCTION_ART_BLOCKED','PREMIUM_EXECUTION_REPLAN_REQUIRED','SCENE_COMPOSER_BLOCKED','PRESENTATION_PRIMITIVE_IN_AUTHORED_SCENE','AUTHORED_SCENE_DENSITY_UNDERSPECIFIED')
  if any(marker in detail for marker in creative_markers):
   raise AdapterReplan('EXPLAINER_PREMIUM_EXECUTION_REPLAN_REQUIRED',detail,{
    'escalation_scope':'UPSTREAM_VISUAL_STRATEGY',
    'invalidate_slots':['visual_concept','art_direction','storyboard','cinematography','editorial_rhythm','motion_performance','sound_direction'],
    'issues':['The committed realization cannot currently be executed at the Studio premium quality floor.',detail[-900:]],
    'revision_plan':['Preserve the approved film thesis and factual intent. Re-author the visual strategy into a materially strong alternative that the currently proven premium body can execute; do not replace it with generic cards, icons or diagram shorthand unless abstraction is itself the best creative concept.'],
    'quality_reasons':['PREMIUM_EXECUTION_CAPABILITY_OR_RENDERED_QUALITY_BELOW_FLOOR'],
    'production_disposition':'CONTINUE_REPLANNING',
    'quality_floor_may_weaken':False,
    'silent_generic_fallback_allowed':False,
   })
  raise AdapterBlocked('EXPLAINER_EXECUTION_BODY_BLOCKED',detail)
 try: runner=json.loads(proc.stdout)
 except Exception as e: raise AdapterBlocked('EXPLAINER_EXECUTION_BODY_RESULT_INVALID',str(e))
 if runner.get('status')!='RENDERED': raise AdapterBlocked('EXPLAINER_EXECUTION_BODY_RENDER_INCOMPLETE',json.dumps(runner)[:800])
 silent=Path(runner['videoPath']);frames=Path(runner['framesDir']);planp=Path(runner['enginePlanPath'])
 mix=render_p8_sound_mix(request,out_root/'p8-directed-audio.wav');final=out_root/'internal-review.mp4'
 subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(silent),'-i',mix['path'],'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','128k','-shortest',str(final)],check=True)
 audio=out_root/'internal-review-audio.wav';audio.write_bytes(Path(mix['path']).read_bytes());sheet=out_root/'contact-sheet.jpg';_sheet(frames,sheet)
 probe=json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration,size','-show_entries','stream=codec_type,width,height,sample_rate,channels,r_frame_rate','-of','json',str(final)],capture_output=True,text=True,check=True).stdout)
 streams=probe.get('streams') or [];vs=next((x for x in streams if x.get('codec_type')=='video'),{});au=next((x for x in streams if x.get('codec_type')=='audio'),{})
 technical={'status':'PASS' if vs.get('width') and vs.get('height') and str(au.get('sample_rate'))=='48000' else 'FAIL','authority':'STUDIO_P8_EXPLAINER_EXECUTION_BODY_QA_V2','topLevelCreativeAuthority':'NEXMIND_P8','executionBody':'NEXSTUDIO_EXPLAINER_EXECUTION_BODY_V2','directorV3Present':False,'rejectedFamilyCreativeAuthoritiesPresent':False,'referenceLanguage':runner.get('referenceLanguage'),'runnerMetrics':runner.get('metrics'),'executionFidelity':runner.get('executionFidelity'),'ffprobe':probe}
 if technical['status']!='PASS': raise AdapterBlocked('EXPLAINER_EXECUTION_BODY_TECHNICAL_QA_BLOCKED',json.dumps(technical)[:800])
 arts=[{'kind':'VIDEO','path':str(final),'mimeType':'video/mp4','sha256':_sha(final),'bytes':final.stat().st_size},{'kind':'AUDIO_MIX','path':str(audio),'mimeType':'audio/wav','sha256':_sha(audio),'bytes':audio.stat().st_size},{'kind':'CONTACT_SHEET','path':str(sheet),'mimeType':'image/jpeg','sha256':_sha(sheet),'bytes':sheet.stat().st_size}]
 return {'schema':'StudioFamilyEngineResultV1','status':'EVIDENCE_READY','family':'EXPLAINER','authorityId':request.get('authorityId'),'enginePlanHash':_sha(planp),'technicalQa':technical,'soundBinding':mix,'artifacts':arts,'enginePlanPath':str(planp),'audioExpected':True}
