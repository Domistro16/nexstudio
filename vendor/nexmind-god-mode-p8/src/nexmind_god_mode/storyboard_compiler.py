from __future__ import annotations
from copy import deepcopy
from typing import Any, Dict, List

GENERIC_BAD=("grid of cards","card grid","connector network","series of boxes","tiny icon","dashboard of tiles")

class StoryboardGateError(RuntimeError): pass

class StoryboardCompiler:
    """Compiles directed decisions into a rehearsal artifact; does not invent story."""
    def compile(self, story:Dict[str,Any], visual:Dict[str,Any], art:Dict[str,Any], form_resolution:Dict[str,Any], *, vo_spans:Dict[str,Any]|None=None)->Dict[str,Any]:
        vt={x["beat_id"]:x for x in visual["beat_treatments"]}; at={x["beat_id"]:x for x in art["beat_art"]}; spans=vo_spans or {}
        beats=[]; previous="NONE"
        for sb in story["beats"]:
            bid=sb["beat_id"]; v=vt[bid]; a=at[bid]
            settled=a["settled_visual_state"]
            beats.append({
                "beat_id":bid,
                "scene_thesis":sb["purpose"]+": "+sb["reveal"],
                "audience_state_change":{"before":sb["audience_before"],"after":sb["audience_after"]},
                "hero_identity":art["hero"]["semantic_ref"],
                "opening_state":previous if previous!="NONE" else "Establish "+v["hero_state"],
                "hero_key_state":v["hero_state"],
                "critical_action_states":[v["visual_action"]],
                "settled_state":settled,
                "settled_meaning_without_motion":a["meaning_without_motion"],
                "supporting_assets":deepcopy(a["supporting_roles"]),
                "visual_direction":{
                    "representation":visual.get("representation"),
                    "visual_thesis":visual.get("visual_thesis"),
                    "concept_signature":deepcopy(visual.get("concept_signature",{})),
                    "rehearsal_states":deepcopy(visual.get("rehearsal_states",{})),
                    "originality_guard":deepcopy(visual.get("originality_guard",{})),
                    "beat_treatment":deepcopy(v),
                },
                "art_direction":{
                    "art_thesis":art.get("art_thesis"),
                    "art_bible":deepcopy(art.get("art_bible",{})),
                    "composition":deepcopy(art.get("composition",{})),
                    "settled_visual_state":a.get("settled_visual_state"),
                    "focal_owner":a.get("focal_owner"),
                    "environment_state":a.get("environment_state",""),
                    "prop_specificity":a.get("prop_specificity",""),
                    "character_performance_state":a.get("character_performance_state",""),
                    "typography_role":a.get("typography_role",""),
                    "depth_read":a.get("depth_read",""),
                },
                "vo_span":deepcopy(spans.get(bid,{})),
                "narration_mode":str(sb.get("narration_mode") or "SILENT"),
                "narration_text":str(sb.get("narration_text") or ""),
                "narration_purpose":str(sb.get("narration_purpose") or ""),
                "shot_camera_intent":visual["camera_idea"],
                "continuity_in":previous,
                "continuity_out":settled,
                "motion_intent":v["visual_action"],
                "sound_intent":"UNRESOLVED_SOUND_DIRECTOR",
                "capability_risks":deepcopy(art["risk_notes"]),
            }); previous=settled
        return {"schema":"NexMindCanonicalStoryboardV1","form_resolution":deepcopy(form_resolution),"beats":beats}

    def gate(self, board:Dict[str,Any])->Dict[str,Any]:
        issues=[]
        fr=board.get("form_resolution",{})
        if fr.get("status") in {"UNSUPPORTED_FORM_REQUIRED"}: issues.append({"code":"FORM_GAP","detail":fr.get("concept","")})
        for b in board.get("beats",[]):
            corpus=" ".join(str(b.get(k,"")) for k in ["scene_thesis","hero_key_state","settled_state"]).lower()
            if any(x in corpus for x in GENERIC_BAD): issues.append({"code":"GENERIC_STORYBOARD","beat_id":b["beat_id"]})
            if b.get("settled_meaning_without_motion") is not True: issues.append({"code":"WEAK_SETTLED_STATE","beat_id":b["beat_id"]})
            if not b.get("hero_identity"): issues.append({"code":"MISSING_HERO","beat_id":b["beat_id"]})
            if not b.get("critical_action_states"): issues.append({"code":"NO_CRITICAL_ACTION","beat_id":b["beat_id"]})
        if issues: raise StoryboardGateError(issues)
        return {"status":"PASS","beat_count":len(board.get("beats",[])),"settled_key_states_pass":True,"motion_rescue_forbidden":True}
