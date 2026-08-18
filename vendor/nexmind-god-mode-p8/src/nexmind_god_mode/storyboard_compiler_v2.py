from __future__ import annotations
from copy import deepcopy
from typing import Any,Dict
from .cinema_contracts import validate_cinema_candidate
from .editorial_contracts import validate_editorial_candidate

class TemporalStoryboardGateError(RuntimeError): pass

class TemporalStoryboardCompiler:
    def compile(self,key_board:Dict[str,Any],cinema:Dict[str,Any],editorial:Dict[str,Any],timeline:Dict[str,Any])->Dict[str,Any]:
        beat_ids={x["beat_id"] for x in key_board["beats"]}
        validate_cinema_candidate(cinema,beat_ids,key_board["beats"][0]["hero_identity"] if key_board["beats"] else "")
        validate_editorial_candidate(editorial,beat_ids)
        shots={bid:[] for bid in beat_ids}; edits={bid:[] for bid in beat_ids}
        for item in cinema["shots"]: shots[item["beat_id"]].append(item)
        for item in editorial["beats"]: edits[item["beat_id"]].append(item)
        beats=[]
        for kb in key_board["beats"]:
            bid=kb["beat_id"]; shot_events=shots[bid]; edit_events=edits[bid]
            beats.append({
                **deepcopy(kb),
                "camera_shots":deepcopy(shot_events),
                "editorial_events":deepcopy(edit_events),
                "camera":deepcopy(shot_events[0]) if len(shot_events)==1 else {},
                "editorial":deepcopy(edit_events[0]) if len(edit_events)==1 else {},
                "motion_plan_status":"UNRESOLVED_MOTION_DIRECTOR",
                "sound_plan_status":"UNRESOLVED_SOUND_DIRECTOR",
                "semantic_motion_request":kb["motion_intent"],
            })
        return {"schema":"NexMindCanonicalTemporalStoryboardV2","beats":beats,"editorial_timeline":deepcopy(timeline),"cinema_candidate_id":cinema["candidate_id"],"editorial_candidate_id":editorial["candidate_id"]}
    def gate(self,board:Dict[str,Any])->Dict[str,Any]:
        issues=[]; last_end=None
        if board.get("schema")!="NexMindCanonicalTemporalStoryboardV2": issues.append({"code":"WRONG_SCHEMA"})
        for b in board.get("beats",[]):
            shots=b.get("camera_shots") if isinstance(b.get("camera_shots"),list) else []
            edits=b.get("editorial_events") if isinstance(b.get("editorial_events"),list) else []
            if not shots or not edits:
                issues.append({"code":"MISSING_TEMPORAL_DIRECTION","beat_id":b.get("beat_id")}); continue
            # The current execution bodies bind one camera/edit event per canonical beat.
            # Preserve richer authorship but fail/replan explicitly instead of collapsing it.
            if len(shots)!=1:
                issues.append({"code":"MULTI_SHOT_EXECUTION_BINDING_REQUIRED","beat_id":b.get("beat_id"),"shot_count":len(shots)})
            if len(edits)!=1:
                issues.append({"code":"MULTI_EDIT_EXECUTION_BINDING_REQUIRED","beat_id":b.get("beat_id"),"edit_count":len(edits)})
            cam=shots[0]; edit=edits[0]
            atom=cam.get("camera_atom",{})
            if atom.get("atom")!="HOLD" and not str(atom.get("motivation","")).strip(): issues.append({"code":"UNMOTIVATED_CAMERA","beat_id":b["beat_id"]})
            if b.get("settled_meaning_without_motion") is not True: issues.append({"code":"MOTION_RESCUE_DEPENDENCY","beat_id":b["beat_id"]})
            if b.get("motion_plan_status")!="UNRESOLVED_MOTION_DIRECTOR": issues.append({"code":"MOTION_PRETENDED_COMPLETE","beat_id":b["beat_id"]})
            if b.get("sound_plan_status")!="UNRESOLVED_SOUND_DIRECTOR": issues.append({"code":"SOUND_PRETENDED_COMPLETE","beat_id":b["beat_id"]})
        if issues: raise TemporalStoryboardGateError(issues)
        return {"status":"PASS","beat_count":len(board.get("beats",[])),"camera_semantic":True,"editorial_rational":True,"motion_unresolved":True,"sound_unresolved":True}
