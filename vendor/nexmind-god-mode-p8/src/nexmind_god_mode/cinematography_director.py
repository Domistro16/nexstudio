from __future__ import annotations
from copy import deepcopy
from typing import Any,Dict,List
from .provider import CreativeModelProvider
from .cinema_contracts import validate_cinema_output

class CinematographyDirector:
    def __init__(self,provider:CreativeModelProvider): self.provider=provider
    def propose(self,production_id:str,brief:Dict[str,Any],story:Dict[str,Any],visual:Dict[str,Any],art:Dict[str,Any],storyboard_key_states:Dict[str,Any],doctrine:Dict[str,Any])->List[Dict[str,Any]]:
        brief_copy=deepcopy(brief)
        revision_context=brief_copy.get("autonomous_revision_context") if isinstance(brief_copy.get("autonomous_revision_context"),dict) else {}
        broader_replan=revision_context.get("department")=="CINEMATOGRAPHY" and revision_context.get("repair_mode")=="MATERIAL_STRATEGY_REPLAN"
        repair_anchor=revision_context.get("previous_output") if revision_context.get("department")=="CINEMATOGRAPHY" else None
        surgical_repair=isinstance(repair_anchor,dict) and bool(repair_anchor) and not broader_replan
        duration=int(brief_copy.get("duration_s") or 0)
        candidate_budget=1 if surgical_repair else 2 + (1 if duration>=45 or len(story.get("beats") or [])>=6 else 0)
        candidate_budget=max(1,min(4,candidate_budget))
        req={
            "production_id":production_id,"brief":brief_copy,"film_thesis":deepcopy(story["film_thesis"]),
            "visual_concept":deepcopy(visual),"art_direction":deepcopy(art),"storyboard_key_states":deepcopy(storyboard_key_states),
            "creative_doctrine":deepcopy(doctrine),"repair_anchor":deepcopy(repair_anchor) if surgical_repair else None,"candidate_budget":candidate_budget,
            "instruction":{
                "role":"NexMind Cinematography Director",
                "goal":(
                    "Surgically repair the supplied Cinematography repair_anchor into exactly one stronger shot strategy. Preserve unaffected framing/attention decisions and resolve every binding repair issue without reopening competition."
                    if surgical_repair else
                    (f"Materially replan Cinematography against the accepted upstream work with exactly {candidate_budget} genuinely different shot strategies; do not cosmetically polish the exhausted camera route." if broader_replan else f"Generate exactly {candidate_budget} genuinely competing brief-specific shot strategies. Descriptive shot language is open; camera execution atoms are capability-bounded.")
                ),
                "laws":[
                    "HOLD is first-class","a new beat does not automatically justify camera movement","every movement needs a semantic motivation and target","preserve attention continuity","do not output coordinates or renderer code",
                    "the current temporal execution body supports exactly one executable camera binding per story beat; express any richer sub-beat camera idea inside reveal_framing/continuity_reason rather than adding a second shot for the same beat",
                    "when repair_anchor is supplied, return exactly one repaired candidate and preserve sticky_requirements",
                ]
            }
        }
        return validate_cinema_output(self.provider.complete("cinematography",req),{x["beat_id"] for x in story["beats"]},art["hero"]["semantic_ref"],repair_mode=surgical_repair)
