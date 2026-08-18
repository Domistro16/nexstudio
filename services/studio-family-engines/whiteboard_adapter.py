from __future__ import annotations
import importlib.util,json,os,sys,tempfile,hashlib,subprocess,shutil
from pathlib import Path
from typing import Any,Dict
from PIL import Image,ImageOps,ImageDraw
from contracts import AdapterBlocked,AdapterReplan,creative_replan_request
from canonical import whiteboard_plan,stable
from authored_art import capability_available as authored_art_available, execute_scene as execute_authored_scene, ArtExecutionUnavailable, ArtExecutionInvalid

def _engine_root()->Path:
    raw=os.environ.get("STUDIO_WHITEBOARD_ENGINE_ROOT","").strip()
    if not raw: raise AdapterBlocked("WHITEBOARD_ENGINE_ROOT_NOT_CONFIGURED","STUDIO_WHITEBOARD_ENGINE_ROOT is required.")
    root=Path(raw).resolve()
    candidates=[root, *[p for p in root.glob("*") if p.is_dir()]]
    for c in candidates:
        if (c/"explainer-motion"/"whiteboard-v1"/"runtime"/"whiteboard_compiler.py").exists(): return c
    raise AdapterBlocked("WHITEBOARD_ENGINE_ROOT_INVALID",str(root))

def _load_runtime(root:Path):
    # Renderer-only family engine. Creative planning belongs exclusively to NexMind P8.
    dirs=[
      root/"explainer-motion"/"benchmarks-stress-v1"/"runtime",
      root/"explainer-motion"/"semantic-performance-v1"/"runtime",
      root/"explainer-motion"/"whiteboard-v1"/"runtime",
      root/"explainer-motion"/"whiteboard-v1"/"qa",
    ]
    for d in reversed(dirs):
        if str(d) not in sys.path: sys.path.insert(0,str(d))
    import semantic_performance as perf
    import whiteboard_compiler as wb
    import whiteboard_qa as wbqa
    import sound_choreographer as wb_sound
    import benchmark_renderer as br
    return perf,wb,wbqa,wb_sound,br

def _render_p8_plan(root:Path,plan:dict,ratio:str,out_dir:Path,perf,wb,wb_sound,br)->dict:
    """Render an already-committed P8 plan. No story/visual candidate generation exists here."""
    frames=out_dir/"frames"; shutil.rmtree(frames,ignore_errors=True); frames.mkdir(parents=True,exist_ok=True)
    scenes=plan.get("sceneSpecs") or []
    if not scenes:
        raise AdapterReplan("WHITEBOARD_P8_PLAN_HAS_NO_SCENES","Committed Whiteboard plan contains no executable scenes.",creative_replan_request(
            escalation_scope="UPSTREAM_VISUAL_STRATEGY",
            invalidate_slots=["visual_concept","art_direction","storyboard","cinematography","editorial_rhythm","motion_performance","sound_direction"],
            issue="The committed Whiteboard realization contains no executable scene sequence.",
            revision_plan="Preserve the approved Film Thesis and re-author a complete Whiteboard scene progression with drawable, causally legible beats.",
            quality_reason="WHITEBOARD_EXECUTABLE_SCENE_STRUCTURE_MISSING",
            constraints=["Remain Whiteboard; do not replace the requested family with another family.","Use only currently proven Whiteboard drawing/performance capabilities or change the visual realization."],
        ))
    durations=[float(s.get("timingOverrideSeconds") or 0) for s in scenes]
    if any(x<=0 for x in durations):
        raise AdapterReplan("WHITEBOARD_P8_TIMING_INVALID","Committed Whiteboard plan contains non-positive scene timing.",creative_replan_request(
            escalation_scope="EDITORIAL_AND_STORYBOARD_STRATEGY",
            invalidate_slots=["storyboard","editorial_rhythm","motion_performance","sound_direction"],
            issue="The committed Whiteboard timing cannot form a valid production sequence.",
            revision_plan="Re-author scene durations and pacing while preserving the approved story/visual concept and maintaining meaningful drawing holds and transitions.",
            quality_reason="WHITEBOARD_TEMPORAL_REALIZATION_INVALID",
            constraints=["Do not compress scenes below readable drawing/explanation time simply to fit duration."],
        ))
    duration=sum(durations)
    bounds=[];acc=0.0
    for d in durations: bounds.append((acc,acc+d));acc+=d
    keyframe_fps=max(6,min(12,int(perf.plan_semantic_frame_rate(plan,12))))
    total=max(2,int(round(duration*keyframe_fps))); transition_frames=0
    for fi in range(total):
        t=min(max(0.0,duration-1e-6),fi/keyframe_fps)
        si=max(0,min(len(bounds)-1,next((i for i,(a,b) in enumerate(bounds) if a<=t<b),len(bounds)-1)))
        scene=scenes[si];a,b=bounds[si];local=t-a
        tr=((scene.get("whiteboardRuntime") or {}).get("transitionIn")) or {}
        tr_d=float(tr.get("duration") or 0)
        if si>0 and tr.get("enabled") and local<tr_d:
            im=br.render_transition_frame(scenes[si-1],scene,plan,ratio,local/max(.001,tr_d),False); transition_frames+=1
        else:
            im=br.render_scene(scene,plan,ratio,scene_time=local,hide_text=False)
        im.save(frames/f"frame-{fi:05d}.jpg",quality=90)
    audio_path=out_dir/"whiteboard-foley-48k.wav"
    audio=wb_sound.render(plan,duration,audio_path)
    if not audio_path.exists(): raise AdapterBlocked("WHITEBOARD_DIRECTED_AUDIO_MISSING")
    video=out_dir/"internal-review.mp4"
    subprocess.run([
      "ffmpeg","-y","-loglevel","error","-framerate",str(keyframe_fps),"-i",str(frames/"frame-%05d.jpg"),
      "-i",str(audio_path),"-map","0:v","-map","1:a","-vf","fps=24,format=yuv420p","-r","24","-t",str(duration),
      "-c:v","libx264","-preset","veryfast","-crf","24","-c:a","aac","-b:a","128k","-ar","48000","-movflags","+faststart",str(video)
    ],check=True)
    probe=json.loads(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration,size","-show_entries","stream=codec_type,width,height,r_frame_rate,sample_rate,channels","-of","json",str(video)],capture_output=True,text=True,check=True).stdout)
    streams=probe.get("streams") or [];v=next((x for x in streams if x.get("codec_type")=="video"),{});a=next((x for x in streams if x.get("codec_type")=="audio"),{})
    if not v.get("width") or not v.get("height") or str(a.get("sample_rate"))!="48000": raise AdapterBlocked("WHITEBOARD_ENCODE_QA_FAILED",json.dumps(probe)[:600])
    return {"path":str(video),"frames":frames,"audio":str(audio_path),"ffprobe":probe,"frameCount":total,"semanticFrameRate":keyframe_fps,"outputFps":24,"transitionFrameCount":transition_frames,"directedAudio":audio}

def _sha_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def _contact_sheet(frames:Path,out:Path):
    files=sorted(frames.glob('frame-*.jpg'))
    if not files: raise AdapterBlocked("WHITEBOARD_RENDER_NO_FRAMES")
    picks=[files[round(i*(len(files)-1)/3)] for i in range(4)] if len(files)>1 else files*4
    ims=[Image.open(p).convert('RGB') for p in picks]
    tw=max(im.width for im in ims); th=max(im.height for im in ims)
    canvas=Image.new('RGB',(tw*2,th*2),(20,20,20))
    for i,im in enumerate(ims): canvas.paste(ImageOps.fit(im,(tw,th)),((i%2)*tw,(i//2)*th))
    canvas.save(out,quality=90)

def build_internal_evidence(request:Dict[str,Any])->Dict[str,Any]:
    root=_engine_root(); perf,wb,wbqa,wb_sound,br=_load_runtime(root)
    plan=whiteboard_plan(request)
    out_root=Path(request.get("outputDirectory") or tempfile.mkdtemp(prefix="studio-whiteboard-evidence-out-"));out_root.mkdir(parents=True,exist_ok=True)
    # P8's Illustration Form Resolver may request production-scoped authored art.
    # The body only executes the already-locked Visual/Art state; it cannot replace
    # the hero, supports, metaphor, beat purpose or composition directives.
    form=plan.get("formResolution") or {}
    if form.get("status")=="GENERATION_REQUIRED":
        if not authored_art_available():
            raise AdapterReplan("WHITEBOARD_AUTHORED_ART_CAPABILITY_REQUIRED","P8 committed an authored illustration form but no production-scoped authored-art execution capability is configured.",creative_replan_request(
                escalation_scope="ART_AND_VISUAL_STRATEGY",
                invalidate_slots=["art_direction","storyboard","cinematography","editorial_rhythm","motion_performance","sound_direction"],
                issue="The selected authored Whiteboard illustration requires a production-scoped illustration executor that is not currently available.",
                revision_plan="Preserve the Film Thesis and visual concept if possible; choose another premium executable art realization, or route through an available authored-art capability. Do not downgrade to generic diagram primitives.",
                quality_reason="WHITEBOARD_AUTHORED_ART_EXECUTOR_UNAVAILABLE",
                constraints=["No generic icon/card fallback.","Do not weaken the 9.5 creative quality floor."]
            ))
        for scene in plan.get("sceneSpecs") or []:
            try:
                plate=execute_authored_scene(scene,"WHITEBOARD",'brand:'+str((plan.get('brandExecution') or {}).get('brandExecutionHash') or ''),request.get("aspectRatio") or "16:9",out_root/"authored-art"/str(scene.get("beatId") or scene.get("sceneId")))
            except (ArtExecutionUnavailable,ArtExecutionInvalid) as e:
                raise AdapterReplan("WHITEBOARD_AUTHORED_ART_EXECUTION_REPLAN_REQUIRED",str(e),creative_replan_request(
                    escalation_scope="ART_AND_VISUAL_STRATEGY",
                    invalidate_slots=["art_direction","storyboard","cinematography","editorial_rhythm","motion_performance","sound_direction"],
                    issue="The authored-art execution body could not faithfully realize the committed Whiteboard scene: "+str(e),
                    revision_plan="Repair the Art realization or select a different premium executable treatment while preserving the Film Thesis and factual/brand intent.",
                    quality_reason="WHITEBOARD_AUTHORED_ART_SEMANTIC_OR_EXECUTION_FAILURE",
                    constraints=["Do not drop required hero/support semantics.","No diagrammatic downgrade unless P8 explicitly chooses diagram as the strongest concept."]
                )) from e
            scene["authoredScenePlate"]=plate
    # P8 is creative authority. These calls only compile the committed semantics into executable Whiteboard state.
    plan=perf.compile_plan_runtime(plan)
    plan=wb.compile_whiteboard_plan(plan,{"ratio":request.get("aspectRatio") or "16:9"})
    plan["whiteboardRuntimeDigest"]=wb.runtime_digest(plan)
    qa=wbqa.evaluate(plan,root/"explainer-motion"/"whiteboard-v1"/"assets"/"audio"/"production")
    if qa.get("status")!="PASS":
        detail=json.dumps(qa,sort_keys=True)[:1400]
        raise AdapterReplan("WHITEBOARD_ENGINE_QA_REPLAN_REQUIRED",detail,creative_replan_request(
            escalation_scope="UPSTREAM_VISUAL_STRATEGY",
            invalidate_slots=["visual_concept","art_direction","storyboard","cinematography","editorial_rhythm","motion_performance","sound_direction"],
            issue="The committed Whiteboard realization fails the execution body's semantic/drawing QA: "+detail,
            revision_plan="Re-author the Whiteboard realization around the exact QA evidence. Preserve the thesis and explanatory intent; choose a different drawable scene construction rather than weakening the Whiteboard QA gate.",
            quality_reason="WHITEBOARD_EXECUTION_BODY_QUALITY_OR_CAPABILITY_BELOW_FLOOR",
            constraints=["Do not substitute generic diagram shorthand unless the Visual Concept explicitly establishes diagrammatic abstraction as the strongest treatment.","Do not weaken Whiteboard continuity, drawing-order, semantic or audio gates."],
        ))
    rendered=_render_p8_plan(root,plan,request.get("aspectRatio") or "16:9",out_root,perf,wb,wb_sound,br)
    video=Path(rendered["path"]);audio=Path(rendered["audio"]);sheet=out_root/"contact-sheet.jpg";_contact_sheet(rendered["frames"],sheet)
    copied=[]
    for kind,src,mime in [("VIDEO",video,"video/mp4"),("AUDIO_MIX",audio,"audio/wav"),("CONTACT_SHEET",sheet,"image/jpeg")]:
        if not src.exists(): raise AdapterBlocked("WHITEBOARD_RENDER_ARTIFACT_MISSING",str(src))
        copied.append({"kind":kind,"path":str(src),"mimeType":mime,"sha256":_sha_file(src),"bytes":src.stat().st_size})
    plan_path=out_root/"engine-plan.json"; plan_path.write_text(json.dumps(plan,indent=2)+"\n")
    technical={"status":"PASS","authority":"P8_WHITEBOARD_RENDERER_ONLY_V2","whiteboardQA":qa,"ffprobe":rendered["ffprobe"],"p8TraceComplete":all((s.get("adapterTrace") or {}).get("creativeChoiceIntroduced") is False for s in plan.get("sceneSpecs") or [])}
    if not technical["p8TraceComplete"]: raise AdapterBlocked("WHITEBOARD_P8_TRACE_INCOMPLETE")
    return {"schema":"StudioFamilyEngineResultV1","status":"EVIDENCE_READY","family":"WHITEBOARD","authorityId":request.get("authorityId"),"enginePlanHash":stable(plan),"runtimeDigest":plan.get("whiteboardRuntimeDigest"),"technicalQa":technical,"artifacts":copied,"enginePlanPath":str(plan_path),"audioExpected":True}
