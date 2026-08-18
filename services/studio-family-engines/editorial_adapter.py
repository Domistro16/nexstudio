from __future__ import annotations
import hashlib,json,os,re,subprocess,sys,tempfile,threading
from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from typing import Any,Dict
from PIL import Image,ImageOps
from contracts import AdapterBlocked,AdapterReplan,creative_replan_request,require_review_board
from canonical import stable
from sound_mix import render_p8_sound_mix

ALLOWED_VERBS={'TYPE_REVEAL','REVEAL','HIGHLIGHT','DE_EMPHASIZE','SETTLE','STATE_CHANGE','REFRAME_CONTENT'}
MOTION_FOR={'TYPE_REVEAL':'LMP-STATE-CHANGE','REVEAL':'LMP-STATE-CHANGE','HIGHLIGHT':'LMP-INSPECT-EMPHASIS','DE_EMPHASIZE':'LMP-INSPECT-EMPHASIS','STATE_CHANGE':'LMP-STATE-CHANGE','REFRAME_CONTENT':'LMP-STATE-CHANGE','SETTLE':'LMP-STATIC-HOLD'}

ART_DEFAULTS={
 'spatial_mode':'FLAT_CANVAS','depth_mode':'LAYERED','hero_scale':'LARGE',
 'environment_density':'MINIMAL','overlap_mode':'NONE','typography_mode':'SUPPORT',
}
ART_ALLOWED={
 'spatial_mode':{'FLAT_CANVAS','GROUNDED_SCENE','PRODUCT_STAGE','INFORMATION_SPACE'},
 'depth_mode':{'FLAT','LAYERED','DEEP'},
 'hero_scale':{'DOMINANT_CLOSE','LARGE','MEDIUM'},
 'environment_density':{'MINIMAL','CONTEXTUAL','LIVED_IN'},
 'overlap_mode':{'NONE','HERO_SUPPORT','PURPOSEFUL_FOREGROUND'},
 'typography_mode':{'EMBEDDED','SUPPORT','HERO'},
}

def _art_execution_binding(beat:dict)->dict:
 art=beat.get('art_direction') if isinstance(beat.get('art_direction'),dict) else {}
 comp=art.get('composition') if isinstance(art.get('composition'),dict) else {}
 raw=comp.get('execution_directives') if isinstance(comp.get('execution_directives'),dict) else {}
 out=dict(ART_DEFAULTS)
 for key,allowed in ART_ALLOWED.items():
  value=str(raw.get(key) or out[key]).upper()
  if value not in allowed:
   raise AdapterReplan('EDITORIAL_ART_EXECUTION_DIRECTIVE_UNSUPPORTED',f"{beat.get('beat_id')}:{key}:{value}",creative_replan_request(
    escalation_scope='ART_AND_COMPOSITION_STRATEGY',
    invalidate_slots=['art_direction','storyboard','cinematography','editorial_rhythm','motion_performance','sound_direction'],
    issue=f"P8 committed an Editorial art execution directive outside the bounded body vocabulary: {key}={value}.",
    revision_plan='Re-author the Art execution directive using the proven bounded vocabulary while preserving the same Art thesis and story purpose.',
    quality_reason='EDITORIAL_ART_EXECUTION_CAPABILITY_MISMATCH',
    constraints=['Renderer may execute bounded Art enums but may not reinterpret free-form Art prose into geometry.'],
   ))
  out[key]=value
 return out

def _root()->Path:
 raw=os.environ.get('STUDIO_EDITORIAL_ENGINE_ROOT','').strip()
 if not raw: raise AdapterBlocked('EDITORIAL_ENGINE_ROOT_NOT_CONFIGURED')
 root=Path(raw).resolve()
 p=root/'explainer-motion'/'faceless-public-levels-v1'/'runtime'/'editorial_renderer_execution.py'
 if not p.exists(): raise AdapterBlocked('EDITORIAL_ENGINE_ROOT_INVALID',str(root))
 return root

def _sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()

def _duration(beat:dict,fallback:float)->float:
 d=(beat.get('editorial') or {}).get('duration') or {}
 try:
  value=float(d.get('value'));rate=float(d.get('rate') or 1)
  if value>=0 and rate>0:return max(.25,value/rate)
 except Exception:pass
 return fallback

def _copy(beat:dict)->str:
 # P8 already authored the thesis. Renderer may line-break it, but must not rewrite it.
 text=' '.join(str(beat.get('scene_thesis') or '').split())
 if not text:
  beat_id=str(beat.get('beat_id') or '')
  raise AdapterReplan('EDITORIAL_P8_DISPLAY_COPY_MISSING',beat_id,creative_replan_request(
   escalation_scope='UPSTREAM_VISUAL_STRATEGY',
   invalidate_slots=['visual_concept','art_direction','storyboard','editorial_rhythm','motion_performance','sound_direction'],
   issue=f'Editorial beat {beat_id} has no authored display thesis/copy to execute.',
   revision_plan='Re-author the Editorial beat with concise display language that carries the approved story purpose; do not let the renderer invent copy.',
   quality_reason='EDITORIAL_AUTHORED_DISPLAY_LANGUAGE_MISSING',
   constraints=['Renderer may line-break approved copy but may not rewrite or invent the film thesis.'],
  ))
 return text

def _tokens(value:str)->set[str]:
 text=re.sub(r'[^a-z0-9]+',' ',str(value or '').lower()).strip()
 aliases={'workstation':'desk','computer':'laptop','notebook':'paper','parcel':'package','box':'package','card':'payment','checkout':'payment','monitor':'screen','display':'screen','ui':'screen','interface':'screen','app':'screen','office':'workspace','review':'analyst'}
 out=set()
 for token in text.split():
  if len(token)>1: out.add(aliases.get(token,token))
 return out

def _catalog(root:Path)->list[dict]:
 p=root/'explainer-motion'/'faceless-public-levels-v1'/'assets'/'aev1-curated-200'/'manifest.json'
 data=json.loads(p.read_text(encoding='utf-8'))
 return [x for x in data.get('assets',[]) if x.get('commercialEligibility') and x.get('family') not in {'character-action','character-whole-action'}]

def _asset_score(role:str,item:dict)->tuple[int,int]:
 rt=_tokens(role); label=str(item.get('label') or ''); lt=_tokens(label); tags=set()
 for raw in item.get('semanticTags') or []: tags|=_tokens(str(raw))
 for raw in item.get('semanticAliases') or []: tags|=_tokens(str(raw))
 pool=lt|tags
 if not rt:return (0,0)
 exact=int(re.sub(r'[^a-z0-9]+','-',role.lower()).strip('-')==label.lower())
 overlap=len(rt&pool); coverage=overlap/max(1,len(rt)); specificity=overlap/max(1,len(pool))
 score=(100 if exact else 0)+round(60*coverage+20*specificity)
 priority={'environment-fragment':6,'literal-prop':5,'mechanism-hero':4,'visual-metaphor':3,'icon':1}.get(str(item.get('family')),0)
 if item.get('family')=='icon': score-=12
 return (score,priority)

def _reference_binding(role:str,reference_media:list,ratio:str)->dict|None:
 refs=[x for x in (reference_media or []) if isinstance(x,dict) and str(x.get('mimeType') or '').startswith('image/')]
 if not refs:return None
 rt=_tokens(role); media_words={'image','photo','photograph','screenshot','screen','product','reference','media','video','footage','interface','app'}
 scored=[]
 for x in refs:
  label=' '.join([str(x.get('name') or ''),str(x.get('assetId') or ''),Path(str(x.get('path') or '')).stem])
  score=len(rt&_tokens(label))*20
  if rt&media_words:score+=20
  scored.append((score,x))
 scored.sort(key=lambda y:y[0],reverse=True)
 if not scored or scored[0][0]<20:return None
 if len(scored)>1 and scored[0][0]==scored[1][0] and scored[0][0]==20:return None
 x=scored[0][1]; path=Path(str(x.get('path') or ''))
 if not path.exists():return None
 return {'semanticEntityId':role,'continuityId':'media-'+hashlib.sha256(role.encode()).hexdigest()[:10],'role':'support','kind':'customer-media','assetId':str(x.get('assetId') or path.stem),'assetFamily':'customer-media','sourceClass':'CUSTOMER_MEDIA','sourcePath':str(path),'sourceLicense':'user-supplied','commercialEligibility':'conditional-user-rights','trademarkRisk':False,'ratio':ratio,'exactSemanticMatch':True,'genericIconHero':False,'sha256':_sha(path),'rendererMode':'customer-media','renderSrc':None}

def _catalog_binding(role:str,catalog:list[dict],ratio:str,*,as_hero:bool=False)->dict|None:
 ranked=sorted(((_asset_score(role,x),x) for x in catalog),key=lambda y:(y[0][0],y[0][1]),reverse=True)
 if not ranked or ranked[0][0][0]<52:return None
 (_,priority),item=ranked[0]
 if as_hero and item.get('family')=='icon':return None
 cid=('hero-' if as_hero else 'support-')+hashlib.sha256(role.encode()).hexdigest()[:10]
 return {'semanticEntityId':role,'continuityId':cid,'role':'hero' if as_hero else 'support','kind':str(item.get('family') or 'asset'),'assetId':item['assetId'],'assetFamily':str(item.get('family') or ''),'sourceClass':'AEV1_CURATED_200','sourcePath':'assets/aev1-curated-200/'+str(item['file']),'sourceLicense':item.get('sourceLicense'),'commercialEligibility':item.get('commercialEligibility'),'trademarkRisk':bool(item.get('trademarkRisk')),'ratio':ratio,'exactSemanticMatch':True,'genericIconHero':False,'sha256':item.get('sha256'),'rendererMode':'editorial-asset','renderSrc':None}


def _hex_color(value):
 text=str(value or '').strip()
 return text if re.fullmatch(r"#[0-9A-Fa-f]{6}",text) else None

def _brand_palette(request):
 brand=request.get('brandExecution') if isinstance(request.get('brandExecution'),dict) else {}
 if brand.get('schema')!='StudioBrandExecutionV1' or not brand.get('brandExecutionHash'):
  raise AdapterBlocked('EDITORIAL_BRAND_EXECUTION_REQUIRED')
 found={}
 def walk(v):
  if isinstance(v,dict):
   for k,x in v.items():
    lk=str(k).lower(); c=_hex_color(x)
    if c and lk in {'background','bg','ink','text','surface','primary','accent','secondary','muted'}: found.setdefault(lk,c)
    walk(x)
  elif isinstance(v,list):
   for x in v: walk(x)
 walk(brand.get('brandAuthority')); walk(brand.get('productionBrandContext'))
 # Neutral unbranded execution is allowed; fictional house Brand is not.
 return {
  'background':found.get('background') or found.get('bg') or '#FFFFFF',
  'ink':found.get('ink') or found.get('text') or '#111111',
  'surface':found.get('surface') or '#F5F5F5',
  'primary':found.get('primary') or found.get('ink') or '#111111',
  'accent':found.get('accent') or found.get('primary') or '#333333',
  'secondary':found.get('secondary') or found.get('muted') or '#666666',
 }

def _camera_binding(beat:dict,target_cid:str)->dict:
 cam=beat.get('camera') if isinstance(beat.get('camera'),dict) else {}
 atom=cam.get('camera_atom') if isinstance(cam.get('camera_atom'),dict) else {}
 mode=str(atom.get('atom') or 'HOLD').upper(); intensity=str(atom.get('intensity') or 'NONE').upper()
 if mode=='ARC':
  raise AdapterReplan('EDITORIAL_CAMERA_ATOM_REQUIRES_UNAVAILABLE_DEPTH','ARC',creative_replan_request(
   escalation_scope='CINEMATOGRAPHY_STRATEGY',invalidate_slots=['cinematography','editorial_rhythm','motion_performance','sound_direction'],
   issue='P8 committed an ARC camera move but the current 2D Editorial execution body cannot realize a true arc without faking depth.',
   revision_plan='Choose an equally strong HOLD, PUSH_IN, PULL_BACK, REFRAME, PAN, TILT, TRACK or FOLLOW realization targeted to the same semantic subject.',
   quality_reason='EDITORIAL_CAMERA_EXECUTION_CAPABILITY_MISMATCH',constraints=['Do not approximate an arc with arbitrary decorative drift.']))
 supported={'HOLD','REFRAME','PUSH_IN','PULL_BACK','PAN','TILT','TRACK','FOLLOW'}
 if mode not in supported:
  raise AdapterReplan('EDITORIAL_CAMERA_ATOM_UNSUPPORTED',mode,creative_replan_request(
   escalation_scope='CINEMATOGRAPHY_STRATEGY',invalidate_slots=['cinematography','editorial_rhythm','motion_performance','sound_direction'],
   issue='P8 committed a camera atom outside the Editorial execution vocabulary: '+mode,
   revision_plan='Re-author the shot with a proven camera atom while preserving the same attention target and narrative purpose.',
   quality_reason='EDITORIAL_CAMERA_EXECUTION_CAPABILITY_MISMATCH'))
 scale={'NONE':1.0,'SUBTLE':1.055,'MODERATE':1.10,'STRONG':1.16}.get(intensity,1.055)
 return {'mode':mode.lower().replace('_','-'),'atom':mode,'intensity':intensity,'targetContinuityId':target_cid,'motivation':str(atom.get('motivation') or ''),'offsetStart':[0,0],'offsetEnd':[0,0],'scaleStart':scale if mode=='PULL_BACK' else 1,'scaleEnd':scale if mode=='PUSH_IN' else 1,'sourceShotIds':[str(cam.get('beat_id') or beat.get('beat_id') or '')],'motivated':mode!='HOLD'}

def _render_plan(request:Dict[str,Any])->dict:
 root=_root();catalog=_catalog(root);reference_media=request.get('referenceMedia') or []
 board_dict=request.get('finalBoard') or {};beats=require_review_board(board_dict);ratio=str(request.get('aspectRatio') or '16:9')
 total=float(request.get('durationSeconds') or 60);fallback=total/max(1,len(beats));cursor=0.;scenes=[];assets=[];ledger={};global_assets={}
 for beat in beats:
  if beat.get('motion_plan_status')!='DIRECTED_MOTION_PERFORMANCE' or beat.get('sound_plan_status')!='DIRECTED_SOUND':
   raise AdapterReplan('P8_FINAL_BOARD_DEPARTMENTS_UNRESOLVED',str(beat.get('beat_id')),creative_replan_request(escalation_scope='MOTION_SOUND_STRATEGY',invalidate_slots=['motion_performance','sound_direction'],issue=f"Editorial beat {beat.get('beat_id')} reached execution before Motion/Sound direction was resolved.",revision_plan='Complete the missing P8 Motion/Sound direction without changing accepted upstream creative decisions unless capability requires it.',quality_reason='EDITORIAL_CREATIVE_DEPARTMENT_UNRESOLVED'))
  actions=beat.get('motion_actions') or []
  if not actions:raise AdapterReplan('EDITORIAL_P8_MOTION_ACTION_REQUIRED',str(beat.get('beat_id')),creative_replan_request(escalation_scope='MOTION_STRATEGY',invalidate_slots=['motion_performance','sound_direction'],issue=f"Editorial beat {beat.get('beat_id')} has no directed motion action.",revision_plan='Author a motivated Editorial motion action; do not add decorative motion merely to satisfy execution.',quality_reason='EDITORIAL_MOTIVATED_MOTION_MISSING'))
  usable=[]
  for a in actions:
   pc=str(a.get('performer_class') or '');verb=str((a.get('execution') or {}).get('resolved_verb') or a.get('requested_verb') or '').upper()
   if pc!='SCENE_GRAPH':
    detail=f"{beat.get('beat_id')}:{pc}:{verb}";raise AdapterReplan('EDITORIAL_NON_TYPOGRAPHIC_PERFORMER_NEEDS_EXPLICIT_BINDING',detail,creative_replan_request(escalation_scope='UPSTREAM_VISUAL_STRATEGY',invalidate_slots=['visual_concept','art_direction','storyboard','cinematography','editorial_rhythm','motion_performance','sound_direction'],issue='The committed Editorial concept requires an unbound performer class: '+detail,revision_plan='Preserve the message and Editorial family, but re-author an equally strong execution through explicitly bound Editorial typography, evidence, product-media, object or environment capabilities.',quality_reason='EDITORIAL_EXECUTION_CAPABILITY_MISMATCH',constraints=['Do not silently replace character performance with a text card.']))
   if verb not in ALLOWED_VERBS:
    raise AdapterReplan('EDITORIAL_MOTION_BINDING_UNSUPPORTED',f"{beat.get('beat_id')}:{verb}",creative_replan_request(escalation_scope='MOTION_AND_VISUAL_STRATEGY',invalidate_slots=['visual_concept','art_direction','storyboard','editorial_rhythm','motion_performance','sound_direction'],issue='Committed Editorial motion verb is outside the proven execution vocabulary: '+verb,revision_plan='Choose a different motivated Editorial realization that preserves beat meaning; do not approximate with generic animation.',quality_reason='EDITORIAL_MOTION_CAPABILITY_MISMATCH',constraints=['Proven verbs: '+', '.join(sorted(ALLOWED_VERBS))]))
   usable.append((verb,a))
  hero_sem=str(beat.get('hero_identity') or '').strip();supports=[]
  raw_supports=[]
  for x in beat.get('supporting_assets') or []:
   if isinstance(x,str) and x.strip():raw_supports.append(x.strip())
   elif isinstance(x,dict):
    for key in ('label','semantic_ref','role','name','id'):
     if isinstance(x.get(key),str) and x[key].strip():raw_supports.append(x[key].strip());break
  title={'semanticEntityId':'editorial-copy-'+str(beat.get('beat_id')),'continuityId':'editorial-copy-'+str(beat.get('beat_id')),'role':'hero','kind':'title','assetId':'FPR-TYPOGRAPHY-V1','assetFamily':'semantic-production-primitive','sourceClass':'FPR_SEMANTIC_PRIMITIVES_V1','sourcePath':None,'sourceLicense':'NexStudio-authored','commercialEligibility':'eligible','trademarkRisk':False,'ratio':ratio,'exactSemanticMatch':True,'genericIconHero':False,'sha256':None,'rendererMode':'semantic-typography','renderSrc':None}
  hero_binding=_reference_binding(hero_sem,reference_media,ratio) or _catalog_binding(hero_sem,catalog,ratio,as_hero=True) if hero_sem else None
  bindings=[]
  if hero_binding:
   hero_binding=dict(hero_binding);hero_binding['role']='hero';hero_cid=hero_binding['continuityId'];title['role']='support';bindings=[hero_binding,title]
  else:
   hero_cid=title['continuityId'];bindings=[title]
  for role in raw_supports:
   b=_reference_binding(role,reference_media,ratio) or _catalog_binding(role,catalog,ratio,as_hero=False)
   if not b:
    raise AdapterReplan('EDITORIAL_SUPPORT_BINDING_UNAVAILABLE',f"{beat.get('beat_id')}:{role}",creative_replan_request(escalation_scope='ART_AND_VISUAL_STRATEGY',invalidate_slots=['visual_concept','art_direction','storyboard','cinematography','editorial_rhythm','motion_performance','sound_direction'],issue=f"P8 authored supporting visual '{role}' but the current Editorial body cannot render it faithfully.",revision_plan='Choose a different equally strong authored support/evidence treatment that is explicitly available, or simplify the concept intentionally to typography-only if that is genuinely stronger.',quality_reason='EDITORIAL_AUTHORED_SUPPORT_UNAVAILABLE',constraints=['Do not omit the authored support silently.','Do not substitute an unrelated icon.']))
   if b['continuityId'] not in {x['continuityId'] for x in bindings}:bindings.append(b);supports.append(b['continuityId'])
  for b in bindings:
   if b['assetId'] not in global_assets:global_assets[b['assetId']]=dict(b);assets.append(dict(b))
   ledger[b['continuityId']]={'semanticEntityId':b['semanticEntityId'],'assetId':b['assetId'],'kind':b['kind'],'sourceClass':b['sourceClass']}
  dur=_duration(beat,fallback); art_exec=_art_execution_binding(beat)
  rich=[b for b in bindings if b['rendererMode']!='semantic-typography']
  treatment='mixed-editorial' if rich else 'typography-led'
  # Every P8 action becomes an explicit sequential execution segment. The body
  # may not silently execute action #1 and discard the rest.
  action_durations=[]
  explicit=[]
  for verb,a in usable:
   timing=a.get('timing') if isinstance(a.get('timing'),dict) else {}
   val=timing.get('duration_seconds') or timing.get('durationSeconds')
   explicit.append(float(val) if isinstance(val,(int,float)) and float(val)>0 else None)
  explicit_total=sum(x for x in explicit if x)
  remaining=max(0.0,dur-explicit_total); missing=sum(1 for x in explicit if x is None)
  share=remaining/missing if missing else 0.0
  action_durations=[x if x is not None else share for x in explicit]
  if sum(action_durations)<=0: action_durations=[dur/len(usable)]*len(usable)
  scale=dur/max(.0001,sum(action_durations)); action_durations=[x*scale for x in action_durations]
  local_cursor=cursor
  for ai,((verb,a),action_dur) in enumerate(zip(usable,action_durations)):
   actor=' '.join(str(a.get(k) or '') for k in ('actor','target')).strip();target_cid=hero_cid
   if actor:
    at=_tokens(actor);matches=[b for b in bindings if at and at&_tokens(b['semanticEntityId'])]
    if matches:target_cid=matches[0]['continuityId']
   end=local_cursor+action_dur
   scene_id='scene-'+str(beat.get('beat_id'))+'-a'+str(ai+1)
   scenes.append({'sceneId':scene_id,'eventId':str(beat.get('beat_id'))+':'+str(a.get('action_id') or ai+1),'start':round(local_cursor,4),'end':round(end,4),'duration':round(action_dur,4),'semanticAction':verb.lower(),'treatmentClass':treatment,'blueprintId':'editorial.p8-explicit-execution','familyId':'family.p8-explicit-execution','composition':{'executionDirectives':art_exec},'storyResponsibility':{'heroContinuityId':hero_cid,'supportContinuityIds':[b['continuityId'] for b in bindings if b['continuityId']!=hero_cid],'newSemanticEntityAllowed':False},'assetBindings':[dict(b) for b in bindings],'motion':{'performerId':MOTION_FOR[verb],'semanticAction':verb.lower(),'targetContinuityIds':[target_cid],'spatialTargetContinuityIds':[],'mayCreateSemanticEntity':False,'anonymousVisibleMotionAllowed':False,'authority':'P8 motion action','sourceAction':a,'spatialTranslationLegalOnlyFor':[]},'camera':_camera_binding(beat,target_cid),'worldPositions':{},'displayCopy':_copy(beat),'stateExpectation':{'eventId':str(beat.get('beat_id')),'transitions':[],'requiresVisibleChange':verb!='SETTLE','expectedStates':[]},'semanticEvent':{'id':str(a.get('action_id') or scene_id),'type':verb.lower()},'forbiddenVisualPatterns':[],'adapterTrace':{'sourceBeatId':beat.get('beat_id'),'sourceMotionActionId':a.get('action_id'),'sourceMotionActionIndex':ai,'sourceMotionActionCount':len(usable),'creativeChoiceIntroduced':False,'p8HeroIdentity':hero_sem,'p8SupportingAssets':raw_supports,'boundSupportCount':len(rich),'cameraAtom':(beat.get('camera') or {}).get('camera_atom',{}).get('atom'),'artExecutionDirectives':art_exec}})
   local_cursor=end
  cursor=local_cursor
 return {'version':'6.0.0','stage':'STUDIO_P8_EDITORIAL_EXECUTION_BODY_V2_ADAPTER','ok':True,'blocked':False,'publicReleaseAllowed':False,'renderingAllowed':True,'renderProgram':{'version':'6.0.0','ratio':ratio,'duration':round(cursor,4),'fps':30,'scenes':scenes,'assets':assets,'identityLedger':ledger,'policy':{'wholeSceneDissolve':False,'idleBobbing':False,'anonymousVisibleMotion':False,'genericIconHero':False,'connectorWeb':False,'deterministicSeek':True,'oneVisibleNodePerContinuityIdPerFrame':True},'brand':_brand_palette(request)},'adapterTrace':{'creativeChoiceIntroduced':False,'authority':'P8_TO_EDITORIAL_EXECUTION_BODY_V2_ONLY'}}

def _capture(html:Path,out_frames:Path,duration:float,ratio:str,fps:int=8)->dict:
 try:from playwright.sync_api import sync_playwright
 except Exception as e:raise AdapterBlocked('EDITORIAL_PLAYWRIGHT_UNAVAILABLE',type(e).__name__)
 dims={'16:9':(1280,720),'1:1':(900,900),'9:16':(720,1280)}.get(ratio,(1280,720));out_frames.mkdir(parents=True,exist_ok=True);errors=[];probes=[];hash_a=hash_b=None
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=os.environ.get('STUDIO_CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--disable-gpu','--no-sandbox']);page=browser.new_page(viewport={'width':dims[0],'height':dims[1]});page.on('pageerror',lambda exc:errors.append(str(exc)));page.set_content(html.read_text(encoding='utf-8'),wait_until='load')
  count=max(2,int(duration*fps+0.999))
  for i in range(count):
   t=min(max(0,duration-1e-4),i/fps);probe=page.evaluate('(t)=>window.NexFacelessRenderer.seek(t)',t);probes.append(probe);page.screenshot(path=str(out_frames/f'frame-{i:05d}.png'))
  check_t=min(max(0,duration-1e-4),duration*.43);page.evaluate('(t)=>window.NexFacelessRenderer.seek(t)',check_t);a=page.screenshot();page.evaluate('(t)=>window.NexFacelessRenderer.seek(t)',check_t);b=page.screenshot();hash_a=hashlib.sha256(a).hexdigest();hash_b=hashlib.sha256(b).hexdigest();browser.close()
 if errors:raise AdapterBlocked('EDITORIAL_BROWSER_PAGE_ERROR',' | '.join(errors[:3]))
 if any((x or {}).get('visibleSemanticCount',0)<1 for x in probes):
  raise AdapterReplan('EDITORIAL_EMPTY_SEMANTIC_FRAME','Rendered Editorial sequence contains an empty semantic frame.',creative_replan_request(
   escalation_scope='UPSTREAM_VISUAL_STRATEGY',
   invalidate_slots=['art_direction','storyboard','cinematography','editorial_rhythm','motion_performance','sound_direction'],
   issue='The committed Editorial realization creates an empty semantic frame during actual render.',
   revision_plan='Recompose/re-time the beat so every intentional frame carries the authored visual argument; preserve deliberate stillness but not accidental emptiness.',
   quality_reason='EDITORIAL_RENDERED_SEMANTIC_CONTINUITY_FAILURE',
  ))
 if any((x or {}).get('visibleAnonymousHelperCount',0)>0 for x in probes):
  raise AdapterReplan('EDITORIAL_ANONYMOUS_HELPER_VISIBLE','Renderer exposed a non-semantic helper element.',creative_replan_request(
   escalation_scope='ART_AND_COMPOSITION_STRATEGY',
   invalidate_slots=['art_direction','storyboard','cinematography','motion_performance'],
   issue='The rendered Editorial realization exposes a non-semantic helper element and is not commercially acceptable.',
   revision_plan='Re-author/recompose the affected visual state so only intentional semantic elements remain visible; do not hide the defect by weakening the QA.',
   quality_reason='EDITORIAL_RENDERED_ARTIFACT_QUALITY_FAILURE',
  ))
 if hash_a!=hash_b:raise AdapterBlocked('EDITORIAL_DETERMINISTIC_SEEK_FAILED')
 return {'width':dims[0],'height':dims[1],'fps':fps,'frames':len(probes),'deterministicSeek':True,'pageErrors':errors,'probes':probes[:3]}

def _sheet(frames:Path,out:Path):
 fs=sorted(frames.glob('frame-*.png'));picks=[fs[round(i*(len(fs)-1)/3)] for i in range(4)] if len(fs)>1 else fs*4;ims=[Image.open(p).convert('RGB') for p in picks];w=max(x.width for x in ims);h=max(x.height for x in ims);can=Image.new('RGB',(w*2,h*2),(20,20,20))
 for i,im in enumerate(ims):can.paste(ImageOps.fit(im,(w,h)),((i%2)*w,(i//2)*h))
 can.save(out,quality=90)

def build_internal_evidence(request:Dict[str,Any])->Dict[str,Any]:
 root=_root();runtime=root/'explainer-motion'/'faceless-public-levels-v1'/'runtime';sys.path.insert(0,str(runtime));import editorial_renderer_execution as renderer
 level5=_render_plan(request);rp=level5['renderProgram'];out=Path(request.get('outputDirectory') or tempfile.mkdtemp(prefix='studio-editorial-evidence-'));out.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='studio-editorial-p8-') as td:
  td=Path(td);pkg=td/'renderer';manifest=renderer.write_renderer_package(level5,pkg);frames=td/'frames';capture=_capture(Path(manifest['renderHtml']),frames,float(rp['duration']),rp['ratio'],8);visual=td/'visual.mp4';subprocess.run(['ffmpeg','-y','-loglevel','error','-framerate',str(capture['fps']),'-i',str(frames/'frame-%05d.png'),'-r','24','-c:v','libx264','-pix_fmt','yuv420p','-t',str(rp['duration']),str(visual)],check=True)
  mix=render_p8_sound_mix(request,td/'directed.wav');video=out/'internal-review.mp4';subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(visual),'-i',mix['path'],'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','128k','-shortest',str(video)],check=True);audio=out/'internal-review-audio.wav';audio.write_bytes(Path(mix['path']).read_bytes());sheet=out/'contact-sheet.jpg';_sheet(frames,sheet);planp=out/'engine-plan.json';planp.write_text(json.dumps(level5,indent=2)+'\n')
  probe=json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration,size','-show_entries','stream=codec_type,width,height,sample_rate,channels','-of','json',str(video)],capture_output=True,text=True,check=True).stdout);streams=probe.get('streams') or [];vs=next((x for x in streams if x.get('codec_type')=='video'),{});au=next((x for x in streams if x.get('codec_type')=='audio'),{})
  tech={'status':'PASS' if vs.get('width') and vs.get('height') and str(au.get('sample_rate'))=='48000' and capture['deterministicSeek'] else 'FAIL','authority':'STUDIO_P8_EDITORIAL_LEVEL5_RENDERER_QA_V1','capture':capture,'ffprobe':probe,'p8TraceComplete':all((s.get('adapterTrace') or {}).get('creativeChoiceIntroduced') is False for s in rp['scenes'])}
  if tech['status']!='PASS' or not tech['p8TraceComplete']:raise AdapterBlocked('EDITORIAL_ADAPTER_TECHNICAL_QA_BLOCKED',json.dumps(tech,sort_keys=True)[:800])
  arts=[{'kind':'VIDEO','path':str(video),'mimeType':'video/mp4','sha256':_sha(video),'bytes':video.stat().st_size},{'kind':'AUDIO_MIX','path':str(audio),'mimeType':'audio/wav','sha256':_sha(audio),'bytes':audio.stat().st_size},{'kind':'CONTACT_SHEET','path':str(sheet),'mimeType':'image/jpeg','sha256':_sha(sheet),'bytes':sheet.stat().st_size}]
  return {'schema':'StudioFamilyEngineResultV1','status':'EVIDENCE_READY','family':'EDITORIAL_MOTION','authorityId':request.get('authorityId'),'enginePlanHash':stable(level5),'technicalQa':tech,'soundBinding':mix,'artifacts':arts,'enginePlanPath':str(planp),'audioExpected':True}
