from __future__ import annotations
import base64, hashlib, json, os, shlex, subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List
from PIL import Image

REGISTRY_ENV="NEXSTUDIO_ART_EXECUTION_REGISTRY_JSON"
CAPABILITY="authored_scene_illustration"
FIDELITY_CAPABILITY="authored_scene_pixel_fidelity_review"

class ArtExecutionUnavailable(RuntimeError): pass
class ArtExecutionInvalid(RuntimeError): pass

def _stable(value:Any)->str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

def _registry()->Dict[str,Any]:
    raw=os.environ.get(REGISTRY_ENV,"").strip()
    if not raw: return {}
    try: obj=json.loads(raw)
    except Exception as e: raise ArtExecutionInvalid(f"{REGISTRY_ENV}_INVALID:{e}") from e
    if not isinstance(obj,dict): raise ArtExecutionInvalid(f"{REGISTRY_ENV}_INVALID_ROOT")
    return obj

def _single_capability_available(name:str)->bool:
    caps=(_registry().get("capabilities") or {}) if _registry() else {}
    rec=caps.get(name) if isinstance(caps,dict) else None
    return isinstance(rec,dict) and rec.get("transport")=="command" and bool(rec.get("command"))

def capability_available(name:str=CAPABILITY)->bool:
    # Authored-art execution is not considered production-capable unless exact
    # generated pixels can also be independently checked against the locked P8
    # Art/Brand/composition contract.
    if name==CAPABILITY:
        return _single_capability_available(CAPABILITY) and _single_capability_available(FIDELITY_CAPABILITY)
    return _single_capability_available(name)

def _capability_record(name:str=CAPABILITY)->Dict[str,Any]:
    reg=_registry(); caps=reg.get("capabilities") or {}
    rec=caps.get(name) if isinstance(caps,dict) else None
    if not isinstance(rec,dict): raise ArtExecutionUnavailable(f"ART_CAPABILITY_NOT_CONFIGURED:{name}")
    if rec.get("transport")!="command": raise ArtExecutionUnavailable(f"ART_CAPABILITY_TRANSPORT_UNSUPPORTED:{name}")
    cmd=rec.get("command")
    if not cmd: raise ArtExecutionUnavailable(f"ART_CAPABILITY_COMMAND_MISSING:{name}")
    return rec

def _required_semantics(scene:Dict[str,Any])->List[str]:
    out=[]
    for value in [scene.get("heroRole"),*(scene.get("supportingRoles") or [])]:
        text=str(value or "").strip()
        if text and text.lower() not in {x.lower() for x in out}: out.append(text)
    return out

def build_request(scene:Dict[str,Any],family:str,style_profile:str,ratio:str)->Dict[str,Any]:
    # Everything creative here was already committed by P8. The execution provider
    # is an illustrator/body: it may realize these decisions, never replace them.
    locked={
        "scene_id":scene.get("sceneId"),"beat_id":scene.get("beatId"),"family":family,"style_profile":style_profile,"ratio":ratio,
        "hero":scene.get("heroRole"),"supports":list(scene.get("supportingRoles") or []),
        "source_text":scene.get("sourceText"),"visual_direction":scene.get("visualDirection") or {},"art_direction":scene.get("artDirection") or {},
        "art_execution_directives":scene.get("artExecutionDirectives") or {},"semantic_needs":scene.get("semanticNeeds") or {},
    }
    return {
        "schema":"NexStudioAuthoredSceneExecutionRequestV1",
        "locked_semantics":locked,
        "locked_semantics_hash":_stable(locked),
        "requirements":{
            "semantic_fidelity":"EXACT_REQUIRED_SEMANTICS_NO_REPLACEMENT",
            "creative_choice_introduced":False,
            "output_schema":"NexStudioAuthoredScenePlateV1",
            "required_semantics":_required_semantics(scene),
            "stage_count":{"min":4,"max":12},
            "stage_format":"PNG_BASE64",
            "forbidden":["new story beat","new metaphor","generic icon substitution","template card/grid replacement","external URL dependency","model/provider identity in output"],
        },
    }

def _decode_png(data:str,path:Path,ratio:str)->None:
    try: raw=base64.b64decode(data,validate=True)
    except Exception as e: raise ArtExecutionInvalid(f"ART_STAGE_BASE64_INVALID:{e}") from e
    path.write_bytes(raw)
    try:
        with Image.open(path) as im:
            if im.format!="PNG": raise ArtExecutionInvalid("ART_STAGE_NOT_PNG")
            w,h=im.size
            if w<640 or h<360: raise ArtExecutionInvalid("ART_STAGE_RESOLUTION_TOO_LOW")
            expected={"16:9":16/9,"1:1":1.0,"9:16":9/16}.get(ratio)
            if expected and abs((w/h)-expected)>.04: raise ArtExecutionInvalid("ART_STAGE_RATIO_MISMATCH")
    except ArtExecutionInvalid: raise
    except Exception as e: raise ArtExecutionInvalid(f"ART_STAGE_IMAGE_INVALID:{e}") from e

def validate_and_materialize(payload:Dict[str,Any],request:Dict[str,Any],out_dir:Path)->Dict[str,Any]:
    if not isinstance(payload,dict) or payload.get("schema")!="NexStudioAuthoredScenePlateV1": raise ArtExecutionInvalid("ART_OUTPUT_SCHEMA_INVALID")
    if payload.get("creative_choice_introduced") is not False: raise ArtExecutionInvalid("ART_EXECUTOR_CLAIMED_CREATIVE_AUTHORITY")
    if payload.get("locked_semantics_hash")!=request["locked_semantics_hash"]: raise ArtExecutionInvalid("ART_LOCKED_SEMANTICS_HASH_MISMATCH")
    bindings=payload.get("semantic_bindings")
    if not isinstance(bindings,list): raise ArtExecutionInvalid("ART_SEMANTIC_BINDINGS_MISSING")
    bound=[]
    for b in bindings:
        if not isinstance(b,dict): raise ArtExecutionInvalid("ART_BINDING_INVALID")
        ref=str(b.get("semantic_ref") or "").strip()
        if ref: bound.append(ref.lower())
    missing=[x for x in request["requirements"]["required_semantics"] if x.lower() not in bound]
    if missing: raise ArtExecutionInvalid("ART_REQUIRED_SEMANTICS_MISSING:"+",".join(missing))
    extra=[str(b.get("semantic_ref")) for b in bindings if str(b.get("semantic_ref") or "").strip().lower() not in {x.lower() for x in request["requirements"]["required_semantics"]} and str(b.get("role") or "").upper()!="CONTEXT"]
    if extra: raise ArtExecutionInvalid("ART_UNAUTHORED_SEMANTICS_PRESENT:"+",".join(extra))
    stages=payload.get("stages")
    if not isinstance(stages,list) or not (4<=len(stages)<=12): raise ArtExecutionInvalid("ART_STAGE_COUNT_INVALID")
    out_dir.mkdir(parents=True,exist_ok=True); files=[]
    ratio=str(request["locked_semantics"].get("ratio") or "16:9")
    for i,stage in enumerate(stages):
        if not isinstance(stage,dict) or not isinstance(stage.get("png_base64"),str): raise ArtExecutionInvalid("ART_STAGE_PAYLOAD_INVALID")
        p=out_dir/f"stage-{i:02d}.png"; _decode_png(stage["png_base64"],p,ratio); files.append(str(p))
    manifest={
        "schema":"NexStudioAuthoredScenePlateMaterializedV1","scene_id":request["locked_semantics"].get("scene_id"),
        "locked_semantics_hash":request["locked_semantics_hash"],"semantic_bindings":bindings,"stage_files":files,
        "creative_choice_introduced":False,"provider_trace":{"capability":CAPABILITY,"provider_identity_persisted":False},
    }
    mp=out_dir/"plate-manifest.json";mp.write_text(json.dumps(manifest,indent=2)+"\n");manifest["manifest_path"]=str(mp)
    return manifest


def _sha256_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def _review_pixel_fidelity(request:Dict[str,Any],manifest:Dict[str,Any])->Dict[str,Any]:
    rec=_capability_record(FIDELITY_CAPABILITY)
    stage_evidence=[]
    for raw in manifest.get("stage_files") or []:
        p=Path(raw); data=p.read_bytes()
        stage_evidence.append({"sha256":hashlib.sha256(data).hexdigest(),"mime_type":"image/png","png_base64":base64.b64encode(data).decode()})
    review_request={
        "schema":"NexStudioAuthoredScenePixelFidelityReviewRequestV1",
        "locked_semantics_hash":request["locked_semantics_hash"],
        "locked_semantics":request["locked_semantics"],
        "stage_evidence":stage_evidence,
        "law":"EXECUTION_FIDELITY_ONLY__NO_TASTE_SCORE__NO_ALTERNATIVE_ART_DIRECTION",
        "checks":["art_bible_conformance","brand_fidelity","composition_fidelity","semantic_fidelity","required_entity_visibility","no_unauthorized_visual_substitution"],
    }
    command=rec.get("command"); argv=list(command) if isinstance(command,list) else shlex.split(str(command))
    timeout=max(10,min(600,int(rec.get("timeout_seconds") or 180)))
    proc=subprocess.run(argv,input=json.dumps(review_request),text=True,capture_output=True,timeout=timeout,env={**os.environ,"NEXSTUDIO_ART_CAPABILITY":FIDELITY_CAPABILITY})
    if proc.returncode!=0: raise ArtExecutionUnavailable(f"ART_FIDELITY_COMMAND_FAILED:{proc.returncode}:{proc.stderr[-600:]}")
    try: payload=json.loads(proc.stdout)
    except Exception as e: raise ArtExecutionInvalid(f"ART_FIDELITY_JSON_INVALID:{e}") from e
    if not isinstance(payload,dict) or payload.get("schema")!="NexStudioAuthoredScenePixelFidelityReviewV1": raise ArtExecutionInvalid("ART_FIDELITY_SCHEMA_INVALID")
    if payload.get("locked_semantics_hash")!=request["locked_semantics_hash"]: raise ArtExecutionInvalid("ART_FIDELITY_LOCK_HASH_MISMATCH")
    expected=[x["sha256"] for x in stage_evidence]; reviewed=[str(x) for x in payload.get("reviewed_stage_sha256") or []]
    if reviewed!=expected: raise ArtExecutionInvalid("ART_FIDELITY_STAGE_HASH_MISMATCH")
    verdict=str(payload.get("verdict") or "").upper()
    if verdict not in {"PASS","VETO"}: raise ArtExecutionInvalid("ART_FIDELITY_VERDICT_INVALID")
    if payload.get("commercial_score") not in {None}: raise ArtExecutionInvalid("ART_FIDELITY_COMMERCIAL_SCORE_FORBIDDEN")
    if verdict!="PASS": raise ArtExecutionInvalid("ART_PIXEL_FIDELITY_VETO:"+";".join(map(str,payload.get("veto_reasons") or []))[:700])
    return {"schema":"NexStudioAuthoredScenePixelFidelityProofV1","verdict":"PASS","locked_semantics_hash":request["locked_semantics_hash"],"reviewed_stage_sha256":expected,"review_capability":FIDELITY_CAPABILITY,"commercialJudgmentAuthority":False}

def execute_scene(scene:Dict[str,Any],family:str,style_profile:str,ratio:str,out_dir:Path)->Dict[str,Any]:
    rec=_capability_record(CAPABILITY); req=build_request(scene,family,style_profile,ratio)
    command=rec.get("command"); argv=list(command) if isinstance(command,list) else shlex.split(str(command))
    timeout=max(10,min(600,int(rec.get("timeout_seconds") or 180)))
    env=os.environ.copy();env["NEXSTUDIO_ART_CAPABILITY"]=CAPABILITY
    proc=subprocess.run(argv,input=json.dumps(req),text=True,capture_output=True,timeout=timeout,env=env)
    if proc.returncode!=0: raise ArtExecutionUnavailable(f"ART_EXECUTION_COMMAND_FAILED:{proc.returncode}:{proc.stderr[-600:]}")
    try: payload=json.loads(proc.stdout)
    except Exception as e: raise ArtExecutionInvalid(f"ART_EXECUTION_JSON_INVALID:{e}") from e
    manifest=validate_and_materialize(payload,req,out_dir)
    manifest["pixel_fidelity_proof"]=_review_pixel_fidelity(req,manifest)
    Path(manifest["manifest_path"]).write_text(json.dumps({k:v for k,v in manifest.items() if k!="manifest_path"},indent=2)+"\n")
    return manifest
