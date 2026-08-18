from __future__ import annotations
from copy import deepcopy
from typing import Any,Dict
from .editorial_contracts import validate_editorial_candidate

class EditorialTimelineCompiler:
    """OTIO-compatible editorial representation without importing third-party objects into NexMind state."""
    def compile(self,editorial:Dict[str,Any])->Dict[str,Any]:
        beat_ids={x["beat_id"] for x in editorial["beats"]}
        e=validate_editorial_candidate(editorial,beat_ids)
        rate=e["project_rate"]
        clips=[]; transitions=[]; markers=[]
        for i,b in enumerate(e["beats"]):
            event_id=str(b.get("event_id") or f"{b['beat_id']}.edit.{i+1}")
            clips.append({
                "type":"Clip","name":event_id,
                "source_range":{"start_time":{"value":b["start"]["value"],"rate":rate},"duration":{"value":b["duration"]["value"],"rate":rate}},
                "metadata":{"nexstudio:id":f"clip.{event_id}","nexstudio:scene_ref":b["beat_id"],"nexstudio:event_ref":event_id,"nexstudio:role":b["role"],"nexstudio:energy":b["energy"]}
            })
            markers.extend([
                {"name":"ACTION","marked_range":{"start_time":{"value":b["start"]["value"]+b["action_frame"],"rate":rate},"duration":{"value":0,"rate":rate}},"metadata":{"nexstudio:scene_ref":b["beat_id"]}},
                {"name":"SETTLE","marked_range":{"start_time":{"value":b["start"]["value"]+b["settle_frame"],"rate":rate},"duration":{"value":0,"rate":rate}},"metadata":{"nexstudio:scene_ref":b["beat_id"]}},
            ])
            if i<len(e["beats"])-1 and b["overlap_to_next_frames"]:
                transitions.append({"type":"Transition","transition_type":b["transition"],"in_offset":{"value":b["overlap_to_next_frames"],"rate":rate},"out_offset":{"value":0,"rate":rate},"metadata":{"nexstudio:transition_ref":f"tx.{b['beat_id']}.{e['beats'][i+1]['beat_id']}"}})
        return {
            "schema":"NexStudioEditorialTimelineOTIOCompatibleV1",
            "time_model":"RationalTime/TimeRange","rate":rate,
            "duration":{"value":e["target_duration_frames"],"rate":rate},
            "tracks":[{"type":"Track","kind":"Video","name":"NexStudio Master Editorial","children":clips}],
            "transitions":transitions,"markers":markers,
            "round_trip_invariants":["no float seconds","stable nexstudio ids","no layout coordinates","semantic graph remains sidecar"]
        }
