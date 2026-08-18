from __future__ import annotations
import hashlib,json,re
from copy import deepcopy
from typing import Any,Dict,List
from contracts import AdapterBlocked,require_review_board,rational_seconds

# Mechanical vocabulary binding only. It never changes P8's story, beat order,
# hero, timing, camera motivation, ownership, or performer choice.
WB_VERB={
 "HOLD":"settle","LOOK":"inspect","WALK":"deliver","RUN":"deliver","SIT":"settle","STAND":"reveal",
 "REACH":"receive","PRESENT":"reveal","PRESS":"activate-unlock","PICKUP":"receive","PLACE":"deliver",
 "CARRY_LIGHT":"carry-transfer","HANDOFF_DIRECT":"carry-transfer","HANDOFF_PLACE_AND_TAKE":"carry-transfer",
 "TYPE":"reveal","PHONE_HOLD":"reveal","DANCE":"reveal","REVEAL":"reveal","HIGHLIGHT":"point-focus",
 "DE_EMPHASIZE":"settle","TRACE_FLOW":"route","TRANSFORM":"transform","OBJECT_MOVE":"route",
 "TYPE_REVEAL":"reveal","SETTLE":"settle","DRAW":"reveal","ANNOTATE":"inspect","ERASE":"retry-repair",
 "REFRAME_CONTENT":"transform","SCROLL":"route","STATE_CHANGE":"transform",
}

def stable(value:Any)->str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

def _strings(value:Any)->List[str]:
    if not isinstance(value,list): return []
    out=[]
    for x in value:
        if isinstance(x,str) and x.strip(): out.append(x.strip())
        elif isinstance(x,dict):
            for k in ("label","semantic_ref","role","name","id"):
                if isinstance(x.get(k),str) and x[k].strip(): out.append(x[k].strip()); break
    return out

def _actions(beat:Dict[str,Any])->List[Dict[str,Any]]:
    raw=beat.get("motion_actions") or []
    return [x for x in raw if isinstance(x,dict)]

def _brand_execution(request:Dict[str,Any])->Dict[str,Any]:
    brand=request.get("brandExecution") if isinstance(request.get("brandExecution"),dict) else {}
    if brand.get("schema")!="StudioBrandExecutionV1" or not brand.get("brandExecutionHash"):
        raise AdapterBlocked("WHITEBOARD_BRAND_EXECUTION_REQUIRED","Exact immutable Brand execution authority is required.")
    return deepcopy(brand)

def _resolved_action(action:Dict[str,Any],beat_id:str)->Dict[str,Any]:
    execution=action.get("execution") if isinstance(action.get("execution"),dict) else {}
    resolved=str(execution.get("resolved_verb") or "").strip().upper()
    if not resolved:
        raise AdapterBlocked("WHITEBOARD_EXPLICIT_MOTION_BINDING_REQUIRED",f"Beat {beat_id} action {action.get('action_id') or ''} lacks an explicit executable binding.")
    return {
        "actionId":str(action.get("action_id") or ""),
        "semanticIntent":deepcopy(action.get("semantic_intent") or action.get("requested_verb") or ""),
        "performerClass":str(action.get("performer_class") or ""),
        "execution":deepcopy(execution),
        "resolvedVerb":resolved,
        "actor":deepcopy(action.get("actor")),
        "target":deepcopy(action.get("target")),
        "timing":deepcopy(action.get("timing")),
        "source":deepcopy(action),
    }

def whiteboard_plan(request:Dict[str,Any])->Dict[str,Any]:
    board=request.get("finalBoard") or {}; beats=require_review_board(board)
    ratio=str(request.get("aspectRatio") or "16:9")
    if ratio not in {"16:9","1:1","9:16"}: raise AdapterBlocked("WHITEBOARD_RATIO_UNSUPPORTED",ratio)
    brand=_brand_execution(request)
    requested_duration=float(request.get("durationSeconds") or 60)
    default_duration=requested_duration/max(1,len(beats))
    scenes=[]
    for b in beats:
        beat_id=str(b["beat_id"])
        editorial=b.get("editorial") if isinstance(b.get("editorial"),dict) else {}
        dur=rational_seconds(editorial.get("duration"),default_duration)
        hero=str(b.get("hero_identity") or "").strip()
        if not hero:
            raise AdapterBlocked("WHITEBOARD_HERO_IDENTITY_REQUIRED",f"Beat {beat_id} has no P8-authored hero identity.")
        supports=_strings(b.get("supporting_assets"))
        actions=[_resolved_action(a,beat_id) for a in _actions(b)]
        if not actions:
            raise AdapterBlocked("WHITEBOARD_P8_MOTION_ACTION_REQUIRED",f"Beat {beat_id} has no P8-authored executable motion action.")
        camera=b.get("camera") if isinstance(b.get("camera"),dict) else {}
        camera_atom=camera.get("camera_atom") if isinstance(camera.get("camera_atom"),dict) else {}
        if not camera_atom:
            raise AdapterBlocked("WHITEBOARD_EXPLICIT_CAMERA_BINDING_REQUIRED",f"Beat {beat_id} has no P8-authored camera atom.")
        continuity_in=str(b.get("continuity_in") or "")
        continuity_out=str(b.get("continuity_out") or "")
        visual_direction=b.get("visual_direction") if isinstance(b.get("visual_direction"),dict) else {}
        art_direction=b.get("art_direction") if isinstance(b.get("art_direction"),dict) else {}
        art_composition=art_direction.get("composition") if isinstance(art_direction.get("composition"),dict) else {}
        art_directives=art_composition.get("execution_directives") if isinstance(art_composition.get("execution_directives"),dict) else {}
        relationships=[]
        for rel in (b.get("semantic_relationships") or art_direction.get("semantic_relationships") or visual_direction.get("semantic_relationships") or []):
            if isinstance(rel,dict): relationships.append(deepcopy(rel))
        scene={
          "executionMode":"WHITEBOARD_SEMANTIC_GRAPH","sceneId":f"{request['productionId']}.{beat_id}","beatId":beat_id,
          "sourceText":str(b.get("scene_thesis") or ""),"screenCopy":{},"narrativePurpose":str(b.get("scene_thesis") or ""),
          "compositionBlueprint":"p8.semantic-graph","mechanismId":"P8_EXPLICIT_EXECUTION","heroRole":hero,
          "supportingRoles":supports,"supportingObjectBudget":len(supports),
          "persistentObject":{"uid":re.sub(r'[^a-zA-Z0-9_.-]+','-',hero)[:80] or beat_id,"semanticEntityId":hero,"label":hero},
          "semanticRelationships":relationships,
          "transitionContinuity":{"type":"meaning-continuity","motivation":f"P8 continuity: {continuity_in} -> {continuity_out}","continuityPreserved":True},
          "cameraAtom":deepcopy(camera_atom),"cameraIntent":deepcopy(camera_atom),"cameraPurpose":str(camera_atom.get("motivation") or b.get("shot_camera_intent") or ""),
          "cameraTarget":deepcopy(camera.get("semantic_target")),"typographyRole":str(art_direction.get("typography_role") or ""),
          "visualDirection":deepcopy(visual_direction),"artDirection":deepcopy(art_direction),"artExecutionDirectives":deepcopy(art_directives),
          "p8MotionActions":actions,"actionSequence":[a["resolvedVerb"] for a in actions],"narrativeRequiredActions":[a["resolvedVerb"] for a in actions],
          "timingOverrideSeconds":round(dur,4),
          "shots":[{"shotId":f"{beat_id}.shot","start":0.0,"end":round(dur,4),"cameraAtom":deepcopy(camera_atom),"semanticTarget":deepcopy(camera.get("semantic_target")),"requiredVisibleConcepts":[hero,*supports],"actions":deepcopy(actions)}],
          "semanticNeeds":{"objectNeeds":[{"concept":x} for x in supports],"actorNeeds":[],"environmentNeed":str(art_direction.get("environment_state") or ""),"propSpecificityNeed":str(art_direction.get("prop_specificity") or ""),"characterPerformanceNeed":str(art_direction.get("character_performance_state") or "")},
          "brandExecution":deepcopy(brand),
          "adapterTrace":{"authority":"NexMind P8 canonical final board","creativeChoiceIntroduced":False,"sourceBeatHash":stable(b),"boundP8ActionIds":[a["actionId"] for a in actions],"cameraAtomHash":stable(camera_atom)},
        }
        scenes.append(scene)
    total=sum(float(s["timingOverrideSeconds"]) for s in scenes)
    return {
      "directorVersion":"P8_SEMANTIC_EXECUTION_V2","briefId":request["productionId"],"inputDigest":str(request.get("creativeStateArtifactHash") or stable(board)),
      "executionMode":"WHITEBOARD_SEMANTIC_GRAPH","formResolution":deepcopy(board.get("form_resolution") or {}),
      "beats":[{"beatId":s["beatId"],"source":"NEXMIND_P8"} for s in scenes],"sceneSpecs":scenes,
      "decisionTraceComplete":True,"selfServiceReadyClaim":False,"durationSeconds":round(total,4),"outputRatios":[ratio],
      "brandExecution":deepcopy(brand),"narrativePlan":{"narrativeStateGraph":{"transformations":[]}},
      "adapterAuthority":{"schema":"StudioP8FamilyAdapterTraceV1","creativeStateArtifactId":request.get("creativeStateArtifactId"),"creativeStateArtifactHash":request.get("creativeStateArtifactHash"),"finalBoardHash":stable(board),"creativeChoiceIntroduced":False},
    }

