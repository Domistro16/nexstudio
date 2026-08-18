from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from .contracts import ContractViolation, reject_geometry_code_authority, require_exact_keys, validate_premium_selection_reasoning
from .provider import CreativeModelProvider


def validate_showrunner_selection(payload: Dict[str, Any], accepted_ids: set[str], all_ids: set[str]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractViolation("showrunner selection must be object")
    reject_geometry_code_authority(payload)
    require_exact_keys(payload, {"selected_candidate_id", "why", "tradeoffs", "rejected_alternatives"}, {"notes","decision_basis","brief_specific_evidence","strongest_alternative_id","why_strongest_alternative_loses","selection_risk"}, label="showrunner selection")
    cid = payload["selected_candidate_id"]
    if cid not in all_ids:
        raise ContractViolation(f"showrunner selected unknown candidate: {cid}")
    if cid not in accepted_ids:
        raise ContractViolation(f"showrunner selected candidate without Executive Producer acceptance: {cid}")
    if not isinstance(payload["why"], str) or not payload["why"].strip():
        raise ContractViolation("showrunner selection requires why")
    if not isinstance(payload["tradeoffs"], list) or not isinstance(payload["rejected_alternatives"], list):
        raise ContractViolation("showrunner selection tradeoffs/rejected_alternatives must be lists")
    rejected_ids={x.get("candidate_id") for x in payload["rejected_alternatives"] if isinstance(x,dict)}
    unknown=rejected_ids-all_ids
    if unknown:
        raise ContractViolation(f"showrunner rejection list contains unknown candidates: {sorted(unknown)}")
    validate_premium_selection_reasoning(payload,all_ids)
    return deepcopy(payload)


class ShowrunnerDecisionIntelligence:
    """Boss-level selection reasoning. It cannot select Producer-rejected work."""
    def __init__(self, provider: CreativeModelProvider):
        self.provider=provider


    def select_story(self, production_id: str, brief: Dict[str, Any], reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
        accepted=[x for x in reviews if x["review"]["verdict"]=="ACCEPT"]
        if not accepted:
            raise ContractViolation("no Producer-accepted story candidate is available for Showrunner selection")
        request={
            "production_id":production_id,
            "brief":deepcopy(brief),
            "candidates":[{
                "candidate":deepcopy(x["candidate"]),
                "producer_review":deepcopy(x["review"]),
            } for x in reviews],
            "instruction":{
                "role":"NexMind Supreme Showrunner",
                "choose_for":["brief specificity","strongest film thesis","audience-state change","causal structure","opening/payoff","engagement and memorability","emotional trajectory","originality","authorship specificity","reference independence","evidence discipline","commercial clarity"],
                "rule":"Choose among Producer-accepted narrative strategies by their actual creative merit. Candidate order and identifier carry no preference signal. Reject merely competent, derivative, emotionally flat, generic or transplantable story strategies even when structurally correct. Populate decision_basis with brief-specific fit, creative distinctiveness, audience effect, commercial finish and capability fit; cite at least two concrete brief-specific facts/states; name the strongest alternative and explain precisely why it loses; state the remaining risk."
            }
        }
        payload=self.provider.complete("showrunner_select",request)
        return validate_showrunner_selection(payload,{x["candidate"]["candidate_id"] for x in accepted},{x["candidate"]["candidate_id"] for x in reviews})

    def select_visual(self, production_id: str, brief: Dict[str, Any], story: Dict[str, Any], reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
        accepted=[x for x in reviews if x["review"]["verdict"]=="ACCEPT"]
        if not accepted:
            raise ContractViolation("no Producer-accepted visual candidate is available for Showrunner selection")
        request={
            "production_id":production_id,
            "brief":deepcopy(brief),
            "film_thesis":deepcopy(story["film_thesis"]),
            "candidates":[{
                "candidate":deepcopy(x["candidate"]),
                "producer_review":deepcopy(x["review"]),
            } for x in reviews],
            "instruction":{
                "role":"NexMind Supreme Showrunner",
                "choose_for":["film thesis","audience-state change","brief specificity","originality","engagement and memorability","emotional force","visual authorship","strongest hero","causal transformation","aesthetic potential","brand fit","non-repetition","commercial clarity","capability feasibility"],
                "rule":"Choose among Producer-accepted candidates by comparing the actual creative strategies, not position or a fixed preference for literal/metaphor/character. State what makes the winner specifically right for this brief and why the strongest alternative loses. A generic, derivative, emotionally flat or merely competent winner is forbidden even when technically feasible. Populate decision_basis with brief-specific fit, creative distinctiveness, audience effect, commercial finish and capability fit; cite at least two concrete brief-specific facts/states; name the strongest alternative and explain precisely why it loses; state the remaining risk. Do not output renderer instructions or coordinates."
            }
        }
        payload=self.provider.complete("showrunner_select",request)
        return validate_showrunner_selection(payload,{x["candidate"]["candidate_id"] for x in accepted},{x["candidate"]["candidate_id"] for x in reviews})
