from __future__ import annotations
from copy import deepcopy
from typing import Any,Dict,List
from .contracts import ContractViolation, reject_geometry_code_authority, require_exact_keys, validate_premium_selection_reasoning
from .provider import CreativeModelProvider

def validate_art_selection(payload:Dict[str,Any],accepted:set[str],all_ids:set[str])->Dict[str,Any]:
    reject_geometry_code_authority(payload)
    require_exact_keys(payload,{"selected_candidate_id","why","tradeoffs","rejected_alternatives"},{"notes","decision_basis","brief_specific_evidence","strongest_alternative_id","why_strongest_alternative_loses","selection_risk"},label="art showrunner selection")
    cid=payload["selected_candidate_id"]
    if cid not in all_ids: raise ContractViolation("art selection unknown candidate")
    if cid not in accepted: raise ContractViolation("art selection lacks Producer acceptance")
    if not str(payload["why"]).strip() or not isinstance(payload["tradeoffs"],list) or not isinstance(payload["rejected_alternatives"],list): raise ContractViolation("invalid art selection rationale")
    unknown={x.get("candidate_id") for x in payload["rejected_alternatives"] if isinstance(x,dict)}-all_ids
    if unknown: raise ContractViolation(f"art rejection list has unknown candidates: {sorted(unknown)}")
    validate_premium_selection_reasoning(payload,all_ids)
    return deepcopy(payload)

class ArtShowrunnerDecisionIntelligence:
    def __init__(self,provider:CreativeModelProvider): self.provider=provider
    def select(self,production_id:str,brief:Dict[str,Any],story:Dict[str,Any],visual:Dict[str,Any],reviewed:List[Dict[str,Any]])->Dict[str,Any]:
        accepted=[x for x in reviewed if x["review"]["verdict"]=="ACCEPT"]
        if not accepted: raise ContractViolation("no Producer-accepted Art candidate")
        req={"production_id":production_id,"brief":deepcopy(brief),"film_thesis":deepcopy(story["film_thesis"]),"visual_concept":deepcopy(visual),"candidates":[{"candidate":deepcopy(x["candidate"]),"form_resolution":deepcopy(x["form_resolution"]),"producer_review":deepcopy(x["review"])} for x in reviewed],"instruction":{"role":"NexMind Supreme Showrunner — Art Selection","choose_for":["Film Thesis","brief-specific authorship","strongest settled key state","hero dominance","complete art-bible coherence","foreground/midground/background authorship","scale and overlap control","environment/world coherence","lived-in environmental evidence","character expressiveness when present","prop specificity","typography integration","material/shape/line consistency","form quality","composition distinctiveness","aesthetic coherence","continuity potential","commercial clarity"],"rule":"Choose only Producer-accepted Art Direction. Reject merely tidy, stock-looking, sparse, asset-collage or presentation-like art even when structurally correct. Prefer the candidate whose settled frames could plausibly pass premium commercial review before motion. Populate decision_basis across brief-specific fit, creative distinctiveness, audience effect, commercial finish and capability fit; cite at least two concrete brief-specific pieces of evidence; name the strongest alternative and explain precisely why it loses; state the remaining risk. No coordinates or renderer instructions."}}
        out=self.provider.complete("showrunner_select_art",req)
        return validate_art_selection(out,{x["candidate"]["candidate_id"] for x in accepted},{x["candidate"]["candidate_id"] for x in reviewed})
