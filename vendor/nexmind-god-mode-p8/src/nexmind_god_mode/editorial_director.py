from __future__ import annotations
from copy import deepcopy
from typing import Any,Dict,List
from .provider import CreativeModelProvider
from .editorial_contracts import validate_editorial_output, normalize_editorial_output

class EditorialRhythmDirector:
    def __init__(self,provider:CreativeModelProvider): self.provider=provider
    def propose(self,production_id:str,brief:Dict[str,Any],story:Dict[str,Any],visual:Dict[str,Any],art:Dict[str,Any],cinema:Dict[str,Any],*,target_duration_frames:int,project_rate:int)->List[Dict[str,Any]]:
        brief_copy=deepcopy(brief)
        revision_context=brief_copy.get("autonomous_revision_context") if isinstance(brief_copy.get("autonomous_revision_context"),dict) else {}
        broader_replan=revision_context.get("department")=="EDITORIAL_RHYTHM" and revision_context.get("repair_mode")=="MATERIAL_STRATEGY_REPLAN"
        repair_anchor=revision_context.get("previous_output") if revision_context.get("department")=="EDITORIAL_RHYTHM" else None
        surgical_repair=isinstance(repair_anchor,dict) and bool(repair_anchor) and not broader_replan
        duration_seconds=max(1,int(round(target_duration_frames/max(1,project_rate))))
        candidate_budget=1 if surgical_repair else 2 + (1 if duration_seconds>=45 or len(story.get("beats") or [])>=6 else 0)
        candidate_budget=max(1,min(4,candidate_budget))
        req={
            "production_id":production_id,"brief":brief_copy,"film_thesis":deepcopy(story["film_thesis"]),"beats":deepcopy(story["beats"]),
            "visual_concept":deepcopy(visual),"art_direction":deepcopy(art),"cinematography":deepcopy(cinema),
            "target_duration_frames":target_duration_frames,"project_rate":project_rate,"repair_anchor":deepcopy(repair_anchor) if surgical_repair else None,"candidate_budget":candidate_budget,
            "instruction":{
                "role":"NexMind Editorial / Rhythm Director",
                "goal":(
                    "Surgically repair the supplied Editorial repair_anchor into exactly one stronger rhythm plan. Preserve unaffected timing logic and resolve every binding issue without reopening competition."
                    if surgical_repair else
                    (f"Materially replan Editorial/Rhythm with exactly {candidate_budget} genuinely different pacing strategies; do not cosmetically polish the exhausted route." if broader_replan else f"Generate exactly {candidate_budget} genuinely competing brief-specific editorial pacing strategies. Editorial purpose language is open; executable time/transition mechanics remain bounded. Duration is a narrative decision, not equal subdivision.")
                ),
                "own":["beat duration","kinetic peaks","stillness","breath","overlap","escalation","compression","transition timing","final payoff hold"],
                "laws":[
                    "use rational frame time only","holds are real stillness","all motion settles before next peak unless carry is explicitly motivated","do not output float seconds","do not output renderer code",
                    "author pacing intent, not arithmetic perfection: the runtime deterministically canonicalizes project rate, exact target-frame accounting, beat start frames and in-beat action/settle bounds after your creative plan is returned",
                    "the current temporal execution body supports exactly one executable editorial event per story beat; express sub-beat rhythm inside action_frame, settle_frame, stillness, overlap and duration rationale rather than adding another event for that beat",
                    "when repair_anchor is supplied, return exactly one repaired candidate and preserve sticky_requirements",
                ]
            }
        }
        raw=self.provider.complete("editorial_rhythm",req)
        ordered_beat_ids=[x["beat_id"] for x in story["beats"]]
        normalized=normalize_editorial_output(raw,ordered_beat_ids,target_duration_frames=target_duration_frames,project_rate=project_rate)
        return validate_editorial_output(normalized,set(ordered_beat_ids),repair_mode=surgical_repair)
