from __future__ import annotations
from copy import deepcopy
from typing import Any,Dict,List
from .provider import CreativeModelProvider
from .art_contracts import validate_art_output

class ArtDirector:
    def __init__(self,provider:CreativeModelProvider): self.provider=provider
    def propose(self,production_id:str,brief:Dict[str,Any],story:Dict[str,Any],visual:Dict[str,Any],doctrine:Dict[str,Any],capability_graph:Dict[str,Any])->List[Dict[str,Any]]:
        brief_copy=deepcopy(brief); reference_visual_evidence=brief_copy.pop("_direct_reference_visuals",[]); reference_visual_omissions=brief_copy.pop("_direct_reference_visual_omissions",[])
        revision_context=brief_copy.get("autonomous_revision_context") if isinstance(brief_copy.get("autonomous_revision_context"),dict) else {}
        broader_replan=revision_context.get("department")=="ART_DIRECTION" and revision_context.get("repair_mode")=="MATERIAL_STRATEGY_REPLAN"
        repair_anchor=revision_context.get("previous_output") if revision_context.get("department")=="ART_DIRECTION" else None
        surgical_repair=isinstance(repair_anchor,dict) and bool(repair_anchor) and not broader_replan
        duration=int(brief_copy.get("duration_s") or 0)
        candidate_budget=1 if surgical_repair else 2 + (1 if duration>=45 or len(story.get("beats") or [])>=6 or len(reference_visual_evidence)>=3 else 0)
        candidate_budget=max(1,min(4,candidate_budget))
        goal=(
            "Surgically repair the supplied Art Direction repair_anchor into exactly one stronger candidate. Preserve every anchor decision not implicated by the binding repair context and cover every story beat exactly once."
            if surgical_repair else
            (f"Materially replan Art Direction against the accepted Story and Visual Concept. Generate exactly {candidate_budget} genuinely different premium Art systems; do not cosmetically polish the exhausted Art route." if broader_replan else f"Generate exactly {candidate_budget} genuinely competing brief-specific premium Art Direction systems whose settled frames already look commercially authored before motion.")
        )
        req={"production_id":production_id,"brief":brief_copy,"reference_visual_evidence":reference_visual_evidence,"reference_visual_omissions":reference_visual_omissions,"film_thesis":deepcopy(story["film_thesis"]),"beats":deepcopy(story["beats"]),"visual_concept":deepcopy(visual),"creative_doctrine":deepcopy(doctrine),"capability_graph":deepcopy(capability_graph),"repair_anchor":deepcopy(repair_anchor) if surgical_repair else None,"candidate_budget":candidate_budget,"instruction":{"goal":goal,"must":["dominant recognizable hero when required","if recognizable_required is true, the effective art budget is HIGH","explicit hierarchy and negative space","author every support and environmental detail that the concept genuinely requires; do not impose a house count quota","settled state communicates without motion",
                    "art_thesis must define one coherent illustration/world language rather than an asset collage",
                    "composition must create deliberate foreground/midground/background depth or an equally intentional flat-design hierarchy; isolated small props are not an environment",
                    "author scene-specific props and environmental evidence that make the world feel lived-in when the concept needs a world",
                    "when characters are present, prioritize readable silhouette, face/gaze, hands/contact, pose and emotional action over mascot-like decoration",
                    "typography, palette/material/line/shape language and density must support the same art system rather than decorate it",
                    "author a complete art_bible covering shape language, line/edge language, palette relationships, material/texture language, lighting/value structure, depth language, environment language, prop language, character language, typography relationship and continuity rules",
                    "composition must explicitly state foreground, midground and background strategies plus scale contrast and overlap intent; do not leave spatial authorship to a generic layout solver",
                    "also commit execution_directives as bounded semantic art decisions: spatial_mode FLAT_CANVAS/GROUNDED_SCENE/PRODUCT_STAGE/INFORMATION_SPACE; depth_mode FLAT/LAYERED/DEEP; hero_scale DOMINANT_CLOSE/LARGE/MEDIUM; environment_density MINIMAL/CONTEXTUAL/LIVED_IN; overlap_mode NONE/HERO_SUPPORT/PURPOSEFUL_FOREGROUND; typography_mode EMBEDDED/SUPPORT/HERO. These are creative decisions owned here; downstream bodies may bind them mechanically but may not reinterpret prose into a different composition",
                    "every beat must specify environment state, prop specificity, character performance state (or deliberate absence), typography role and depth read in addition to the settled frame",
                    "if a requested premium character/environment/object realization is not available in the capability graph, choose a different premium art realization that preserves the concept; never downgrade to generic icons/cards",
                    "form request is semantic, not coordinates","when autonomous_revision_context is present, repair every listed contract or Producer issue without weakening the concept","no renderer code"]}}
        payload=deepcopy(self.provider.complete("art",req))
        # visual_candidate_id is orchestration-owned lineage, not a creative field.
        # Bind every Art candidate to the actually committed Visual candidate after
        # provider inference, then let the runtime contract validate that binding.
        candidates=payload.get("candidates") if isinstance(payload,dict) else None
        if isinstance(candidates,list):
            for candidate in candidates:
                if isinstance(candidate,dict):
                    candidate["visual_candidate_id"]=visual["candidate_id"]
                    # recognizable_required is the semantic quality requirement.
                    # The corresponding HIGH art budget is a deterministic quality
                    # floor, not a discretionary creative choice. Never terminate a
                    # production because a provider underspecified this dependent
                    # resource field; enforce the floor before contract validation.
                    hero=candidate.get("hero")
                    if isinstance(hero,dict) and hero.get("recognizable_required") is True:
                        hero["art_budget"]="HIGH"
                    # support_budget is an execution-capacity declaration, not a creative quota.
                    # It must never truncate roles the Art Director actually authored.
                    comp=candidate.get("composition")
                    beat_art=candidate.get("beat_art")
                    if isinstance(comp,dict) and isinstance(beat_art,list):
                        authored_support_floor=max([len(b.get("supporting_roles") or []) for b in beat_art if isinstance(b,dict)] or [0])
                        try: declared=max(0,int(comp.get("support_budget",0)))
                        except Exception: declared=0
                        comp["support_budget"]=max(declared,authored_support_floor)
        return validate_art_output(payload,{x["beat_id"] for x in story["beats"]},visual["candidate_id"],repair_mode=surgical_repair)
