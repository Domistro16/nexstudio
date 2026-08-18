from __future__ import annotations
from copy import deepcopy
from typing import Any,Dict,List
from .contracts import ContractViolation, reject_geometry_code_authority, require_exact_keys, validate_premium_selection_reasoning
from .provider import CreativeModelProvider

def validate_selection(payload:Dict[str,Any],accepted:set[str],all_ids:set[str],label:str)->Dict[str,Any]:
    reject_geometry_code_authority(payload)
    require_exact_keys(payload,{"selected_candidate_id","why","tradeoffs","rejected_alternatives"},{"notes","decision_basis","brief_specific_evidence","strongest_alternative_id","why_strongest_alternative_loses","selection_risk"},label=label)
    cid=payload["selected_candidate_id"]
    if cid not in all_ids: raise ContractViolation(f"{label}: unknown candidate")
    if cid not in accepted: raise ContractViolation(f"{label}: candidate lacks Producer acceptance")
    if not str(payload["why"]).strip() or not isinstance(payload["tradeoffs"],list): raise ContractViolation(f"{label}: rationale required")
    validate_premium_selection_reasoning(payload,all_ids)
    return deepcopy(payload)

class P45ShowrunnerDecisionIntelligence:
    def __init__(self,provider:CreativeModelProvider): self.provider=provider
    def select_cinema(self,production_id:str,story:Dict[str,Any],reviewed:List[Dict[str,Any]])->Dict[str,Any]:
        accepted=[x for x in reviewed if x["review"]["verdict"]=="ACCEPT"]
        if not accepted: raise ContractViolation("no Producer-accepted cinematography")
        req={"production_id":production_id,"film_thesis":deepcopy(story["film_thesis"]),"candidates":[{"candidate":deepcopy(x["candidate"]),"review":deepcopy(x["review"])} for x in reviewed],"instruction":{"role":"NexMind Supreme Showrunner — Cinematography Selection","choose_for":["Film Thesis","attention continuity","meaningful shot scale","motivated camera","restraint","payoff"],"rule":"Choose only Producer-accepted work. Use brief-specific decision_basis, cite at least two concrete brief-specific facts/states, identify the strongest alternative and why it loses, and state the remaining risk; do not reuse a generic rationale."}}
        out=self.provider.complete("showrunner_select_cinematography",req)
        return validate_selection(out,{x["candidate"]["candidate_id"] for x in accepted},{x["candidate"]["candidate_id"] for x in reviewed},"cinema selection")
    def select_editorial(self,production_id:str,story:Dict[str,Any],reviewed:List[Dict[str,Any]])->Dict[str,Any]:
        accepted=[x for x in reviewed if x["review"]["verdict"]=="ACCEPT"]
        if not accepted: raise ContractViolation("no Producer-accepted editorial plan")
        req={"production_id":production_id,"film_thesis":deepcopy(story["film_thesis"]),"candidates":[{"candidate":deepcopy(x["candidate"]),"timeline":deepcopy(x.get("timeline")),"review":deepcopy(x["review"])} for x in reviewed],"instruction":{"role":"NexMind Supreme Showrunner — Editorial Selection","choose_for":["Film Thesis","rhythm shape","peak discipline","stillness","escalation","final payoff"],"rule":"Choose only Producer-accepted work. Use brief-specific decision_basis, cite at least two concrete brief-specific facts/states, identify the strongest alternative and why it loses, and state the remaining risk; do not reuse a generic rationale."}}
        out=self.provider.complete("showrunner_select_editorial",req)
        return validate_selection(out,{x["candidate"]["candidate_id"] for x in accepted},{x["candidate"]["candidate_id"] for x in reviewed},"editorial selection")
