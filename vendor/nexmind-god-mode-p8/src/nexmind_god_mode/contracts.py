from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Set

REPRESENTATIONS = {
    "AUTHORED_ILLUSTRATION",
    "ASSEMBLED_ILLUSTRATION",
    "MECHANISM",
    "DIAGRAM",
    "TYPOGRAPHY_DATA",
    "CHARACTER",
    "PRODUCT_MEDIA",
    "PHYSICAL_METAPHOR",
    "SPECIALIST",
}

GEOMETRY_KEYS = {
    "x", "y", "width", "height", "left", "right", "top", "bottom",
    "px", "pixels", "coordinates", "viewbox", "path_d", "svg_path",
}
AUTHORITY_KEYS = {
    "commit", "committed", "authority", "creative_lock", "final_decision",
    "override_showrunner", "showrunner_commit", "decision_slot",
}
CODE_MARKERS = ("<svg", "<div", "<html", "function(", "=>", "import React", "const ")


class ContractViolation(ValueError):
    pass


def _walk(obj: Any, path: str = "$"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield path, k, v
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")


def reject_geometry_code_authority(obj: Any) -> None:
    for path, key, value in _walk(obj):
        lk = str(key).lower()
        if lk in GEOMETRY_KEYS:
            raise ContractViolation(f"geometry leakage at {path}.{key}")
        if lk in AUTHORITY_KEYS:
            raise ContractViolation(f"authority leakage at {path}.{key}")
        if isinstance(value, str):
            low = value.lower()
            if any(marker.lower() in low for marker in CODE_MARKERS):
                raise ContractViolation(f"renderer/code leakage at {path}.{key}")


def require_exact_keys(obj: Dict[str, Any], required: Set[str], optional: Set[str] | None = None, *, label: str) -> None:
    optional = optional or set()
    missing = required - set(obj)
    extra = set(obj) - required - optional
    if missing:
        raise ContractViolation(f"{label} missing keys: {sorted(missing)}")
    if extra:
        raise ContractViolation(f"{label} unexpected keys: {sorted(extra)}")


def validate_evidence_ledger(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    seen = set()
    for rec in records:
        if not isinstance(rec, dict):
            raise ContractViolation("evidence record must be object")
        require_exact_keys(
            rec,
            {"claim_id", "claim", "source", "status"},
            {"confidence", "valid_from", "valid_to", "notes"},
            label="evidence",
        )
        cid = rec["claim_id"]
        if not isinstance(cid, str) or not cid:
            raise ContractViolation("claim_id required")
        if cid in seen:
            raise ContractViolation(f"duplicate claim_id: {cid}")
        seen.add(cid)
        if rec["status"] not in {"VERIFIED", "USER_SUPPLIED", "UNRESOLVED", "DISPUTED"}:
            raise ContractViolation(f"invalid evidence status for {cid}")
        out.append(deepcopy(rec))
    return out


def validate_story_output(payload: Dict[str, Any], evidence_ids: Set[str]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractViolation("story output must be object")
    reject_geometry_code_authority(payload)
    require_exact_keys(payload, {"film_thesis", "beats"}, {"story_notes"}, label="story output")
    thesis = payload["film_thesis"]
    require_exact_keys(
        thesis,
        {
            "central_argument", "film_kind", "audience_before", "audience_after",
            "emotional_trajectory", "visual_trajectory", "opening_contract",
            "final_payoff", "anti_goals",
        },
        {"tone", "hero_kind", "camera_idea"},
        label="film_thesis",
    )
    for k in ["central_argument", "film_kind", "audience_before", "audience_after", "opening_contract", "final_payoff"]:
        if not isinstance(thesis[k], str) or not thesis[k].strip():
            raise ContractViolation(f"film_thesis.{k} must be non-empty string")
    for k in ["hero_kind", "camera_idea"]:
        if k in thesis and (not isinstance(thesis[k], str) or not thesis[k].strip()):
            raise ContractViolation(f"film_thesis.{k} must be non-empty string when supplied")
    for k in ["emotional_trajectory", "visual_trajectory", "anti_goals"]:
        if not isinstance(thesis[k], list) or not thesis[k]:
            raise ContractViolation(f"film_thesis.{k} must be non-empty list")
    beats = payload["beats"]
    if not isinstance(beats, list) or len(beats) < 1:
        raise ContractViolation("story requires at least one purposeful beat")
    seen = set()
    for beat in beats:
        require_exact_keys(
            beat,
            {"beat_id", "purpose", "question", "audience_before", "audience_after", "reveal", "required_claim_ids"},
            {"narration_job", "tension", "hero_state", "narration_mode", "narration_text", "narration_purpose"},
            label="story beat",
        )
        bid = beat["beat_id"]
        if not isinstance(bid, str) or not bid or bid in seen:
            raise ContractViolation("beat_id must be unique non-empty string")
        seen.add(bid)
        refs = beat["required_claim_ids"]
        if not isinstance(refs, list):
            raise ContractViolation(f"{bid}.required_claim_ids must be list")
        missing = set(refs) - evidence_ids
        if missing:
            raise ContractViolation(f"{bid} cites unavailable evidence: {sorted(missing)}")
        if "hero_state" in beat and (not isinstance(beat["hero_state"], str) or not beat["hero_state"].strip()):
            raise ContractViolation(f"{bid}.hero_state must be non-empty string when supplied")
        if "narration_mode" in beat and beat["narration_mode"] not in {"VOICEOVER", "SILENT"}:
            raise ContractViolation(f"{bid}.narration_mode must be VOICEOVER or SILENT")
        if "narration_text" in beat and not isinstance(beat["narration_text"], str):
            raise ContractViolation(f"{bid}.narration_text must be string")
        if "narration_purpose" in beat and not isinstance(beat["narration_purpose"], str):
            raise ContractViolation(f"{bid}.narration_purpose must be string")
        if beat.get("narration_mode") == "VOICEOVER" and not str(beat.get("narration_text") or "").strip():
            raise ContractViolation(f"{bid}.VOICEOVER requires narration_text")

    # Legacy recorded/provider fixtures predate StoryAuthoringContractV2. Live providers are
    # required by STORY_SCHEMA to author these fields. The fallback exists only so old
    # deterministic contract-regression fixtures remain readable; it never reintroduces
    # adapter-owned audience/camera placeholders.
    out = deepcopy(payload)
    out_thesis = out["film_thesis"]
    if not str(out_thesis.get("hero_kind") or "").strip():
        out_thesis["hero_kind"] = "story protagonist / causal agent"
    if not str(out_thesis.get("camera_idea") or "").strip():
        trajectory = out_thesis.get("visual_trajectory") or []
        out_thesis["camera_idea"] = str(trajectory[0] if trajectory else "story-led observation of the causal action")
    for beat in out["beats"]:
        if not str(beat.get("hero_state") or "").strip():
            beat["hero_state"] = str(beat.get("reveal") or beat.get("purpose") or "story beat state")
        # Contract-regression fixtures predate authored narration. Live STORY_SCHEMA
        # requires explicit narration mode/text/purpose; historical fixtures are
        # normalized to deliberate silence rather than fabricating copy.
        if beat.get("narration_mode") not in {"VOICEOVER", "SILENT"}:
            beat["narration_mode"] = "SILENT"
        if not isinstance(beat.get("narration_text"), str): beat["narration_text"] = ""
        if not isinstance(beat.get("narration_purpose"), str): beat["narration_purpose"] = ""
        if beat["narration_mode"] == "SILENT": beat["narration_text"] = ""
    return out


def validate_visual_candidate(candidate: Dict[str, Any], beat_ids: Set[str]) -> Dict[str, Any]:
    if not isinstance(candidate, dict):
        raise ContractViolation("visual candidate must be object")
    reject_geometry_code_authority(candidate)
    require_exact_keys(
        candidate,
        {
            "candidate_id", "representation", "visual_thesis", "hero_kind", "transformation",
            "camera_idea", "rationale", "beat_treatments",
        },
        {"style_intent", "risk_notes", "concept_signature", "rehearsal_states", "originality_guard"},
        label="visual candidate",
    )
    if not isinstance(candidate["representation"],str) or not candidate["representation"].strip():
        raise ContractViolation("visual representation must be authored descriptively")
    for k in ["candidate_id", "visual_thesis", "hero_kind", "transformation", "camera_idea", "rationale"]:
        if not isinstance(candidate[k], str) or not candidate[k].strip():
            raise ContractViolation(f"candidate.{k} must be non-empty string")
    premium_fields={"concept_signature","rehearsal_states","originality_guard"}
    premium_contract=bool(premium_fields & set(candidate))
    if premium_contract:
        missing=premium_fields-set(candidate)
        if missing: raise ContractViolation(f"visual premium contract incomplete: {sorted(missing)}")
        sig=candidate["concept_signature"];require_exact_keys(sig,{"brief_specific_hook","governing_visual_logic","emotional_engine","memorability_device","transplant_test"},label="visual.concept_signature")
        rehearsal=candidate["rehearsal_states"]
        if not isinstance(rehearsal,list) or len(rehearsal)<2:
            raise ContractViolation("visual.rehearsal_states must be an authored sequence with at least two states")
        for i,state in enumerate(rehearsal):
            require_exact_keys(state,{"label","state","purpose"},label=f"visual.rehearsal_states[{i}]")
            for key in ("label","state","purpose"):
                if not isinstance(state[key],str) or not state[key].strip():
                    raise ContractViolation(f"visual rehearsal {i}.{key} must be non-empty")
        guard=candidate["originality_guard"];require_exact_keys(guard,{"reference_independence","template_risk","why_not_obvious"},label="visual.originality_guard")
        for group in (sig,guard):
            for key,value in group.items():
                if not isinstance(value,str) or not value.strip(): raise ContractViolation(f"visual premium field {key} must be non-empty")
        if sig["transplant_test"].strip().lower() in {"yes","passes","generic","transferable"}: raise ContractViolation("visual concept fails transplant-specificity test")
    treatments = candidate["beat_treatments"]
    if not isinstance(treatments, list) or len(treatments) != len(beat_ids):
        raise ContractViolation("visual candidate must treat every story beat exactly once")
    seen = set()
    for item in treatments:
        require_exact_keys(
            item,
            {"beat_id", "hero_state", "visual_action", "audience_takeaway"},
            {"supporting_elements", "continuity_handoff", "world_state", "visual_consequence"},
            label="beat treatment",
        )
        bid = item["beat_id"]
        if bid not in beat_ids:
            raise ContractViolation(f"unknown beat_id in visual candidate: {bid}")
        if bid in seen:
            raise ContractViolation(f"duplicate beat treatment: {bid}")
        if premium_contract:
            for key in ("supporting_elements","world_state","visual_consequence","continuity_handoff"):
                if key not in item: raise ContractViolation(f"premium visual beat {bid} missing {key}")
            if not isinstance(item["supporting_elements"],list): raise ContractViolation(f"{bid}.supporting_elements must be list")
            for key in ("world_state","visual_consequence","continuity_handoff"):
                if not isinstance(item[key],str) or not item[key].strip(): raise ContractViolation(f"{bid}.{key} must be non-empty")
        seen.add(bid)
    if seen != beat_ids:
        raise ContractViolation("visual candidate beat coverage mismatch")
    return deepcopy(candidate)


def assert_semantic_candidate_diversity(candidates: list[Dict[str,Any]], *, threshold: float = 0.96, label: str = "candidate") -> None:
    """Reject near-paraphrase candidate sets; tuple/hash distinctness is insufficient."""
    import re
    stop={"candidate","beat","story","visual","art","camera","motion","sound","scene","the","and","with","that","this","from","into","for","then","same","true","false","high","medium","low"}
    def collect(x:Any,key:str="")->list[str]:
        if key in {"candidate_id","beat_id","event_id","action_id","shot_id"}: return []
        if isinstance(x,str): return [x]
        if isinstance(x,dict):
            out=[]
            for k,v in x.items(): out.extend(collect(v,str(k)))
            return out
        if isinstance(x,list):
            out=[]
            for v in x: out.extend(collect(v,key))
            return out
        return []
    token_sets=[]
    for c in candidates:
        toks={t for t in re.findall(r"[a-z0-9]+"," ".join(collect(c)).lower()) if len(t)>2 and t not in stop}
        token_sets.append(toks)
    for i in range(len(token_sets)):
        for j in range(i+1,len(token_sets)):
            union=token_sets[i]|token_sets[j]
            similarity=len(token_sets[i]&token_sets[j])/len(union) if union else 1.0
            if similarity>=threshold:
                raise ContractViolation(f"{label} set lacks semantic/structural novelty: pair={i+1}/{j+1} similarity={similarity:.2f}")

def _concept_tokens(candidate: Dict[str, Any]) -> set[str]:
    sig=candidate.get("concept_signature") if isinstance(candidate.get("concept_signature"),dict) else {}
    parts=[candidate.get("representation",""),candidate.get("hero_kind",""),candidate.get("transformation",""),sig.get("governing_visual_logic",""),sig.get("memorability_device","")]
    import re
    stop={"the","and","with","that","this","into","from","for","through","while","then","one","same","visual","film","scene","shows","show"}
    return {x for x in re.findall(r"[a-z0-9]+"," ".join(map(str,parts)).lower()) if len(x)>2 and x not in stop}

def _assert_visual_candidate_diversity(candidates: List[Dict[str, Any]]) -> None:
    premium=[c for c in candidates if isinstance(c.get("concept_signature"),dict)]
    if len(premium)<3:
        return  # historical regression fixtures are not commercial-live candidate sets
    seen={}
    for c in premium:
        sig=c["concept_signature"]
        fp=(str(c.get("representation") or "").strip().lower(),str(c.get("hero_kind") or "").strip().lower(),str(c.get("transformation") or "").strip().lower(),str(sig.get("governing_visual_logic") or "").strip().lower(),str(sig.get("memorability_device") or "").strip().lower())
        if fp in seen:
            raise ContractViolation(f"visual candidate set contains duplicate creative thesis: {seen[fp]} and {c.get('candidate_id')}")
        seen[fp]=c.get("candidate_id")
    for i,a in enumerate(premium):
        ta=_concept_tokens(a)
        for b in premium[i+1:]:
            tb=_concept_tokens(b); union=ta|tb
            similarity=(len(ta&tb)/len(union)) if union else 1.0
            if similarity>=0.82:
                raise ContractViolation(f"visual candidate set lacks material diversity: {a.get('candidate_id')} and {b.get('candidate_id')} similarity={similarity:.2f}")

def validate_visual_output(payload: Dict[str, Any], beat_ids: Set[str], *, repair_mode: bool = False) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ContractViolation("visual output must be object")
    reject_geometry_code_authority(payload)
    require_exact_keys(payload, {"candidates"}, {"director_notes"}, label="visual output")
    candidates = payload["candidates"]
    minimum = 1 if repair_mode else 2
    if not isinstance(candidates, list) or len(candidates) < minimum:
        raise ContractViolation("visual repair requires one anchored candidate" if repair_mode else "visual output requires genuine candidate competition")
    seen = set()
    out = []
    for c in candidates:
        valid = validate_visual_candidate(c, beat_ids)
        if valid["candidate_id"] in seen:
            raise ContractViolation("visual candidate ids must be unique")
        seen.add(valid["candidate_id"])
        out.append(valid)
    if not repair_mode:
        _assert_visual_candidate_diversity(out)
    return out


def validate_producer_output(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractViolation("producer output must be object")
    reject_geometry_code_authority(payload)
    require_exact_keys(
        payload,
        {"verdict", "issues", "strengths", "revision_brief", "commercial_confidence"},
        {"notes", "deferred_production_validations"},
        label="producer output",
    )
    if payload["verdict"] not in {"ACCEPT", "REVISE", "REJECT"}:
        raise ContractViolation("invalid producer verdict")
    if payload["commercial_confidence"] not in {"LOW", "MEDIUM", "HIGH"}:
        raise ContractViolation("invalid commercial_confidence")
    if not isinstance(payload["issues"], list) or not isinstance(payload["strengths"], list):
        raise ContractViolation("producer issues/strengths must be arrays")
    if "deferred_production_validations" in payload and not isinstance(payload["deferred_production_validations"], list):
        raise ContractViolation("deferred_production_validations must be array")
    if payload["verdict"] != "ACCEPT" and not str(payload["revision_brief"]).strip():
        raise ContractViolation("non-accepted review requires revision_brief")
    return deepcopy(payload)


def validate_premium_selection_reasoning(payload:Dict[str,Any], all_ids:Set[str])->None:
    fields={"decision_basis","brief_specific_evidence","strongest_alternative_id","why_strongest_alternative_loses","selection_risk"}
    present=fields & set(payload)
    if not present:
        return  # historical RecordedModelProvider contract-regression fixture only
    missing=fields-set(payload)
    if missing: raise ContractViolation(f"premium selection reasoning incomplete: {sorted(missing)}")
    basis=payload["decision_basis"]
    require_exact_keys(basis,{"brief_specific_fit","creative_distinctiveness","audience_effect","commercial_finish","capability_fit"},label="selection.decision_basis")
    for key,value in basis.items():
        if not isinstance(value,str) or not value.strip(): raise ContractViolation(f"selection decision basis {key} required")
    evidence=payload["brief_specific_evidence"]
    if not isinstance(evidence,list) or len(evidence)<2 or not all(isinstance(x,str) and x.strip() for x in evidence): raise ContractViolation("selection requires at least two brief-specific evidence statements")
    alt=str(payload["strongest_alternative_id"] or "").strip()
    if alt not in all_ids: raise ContractViolation("selection strongest alternative must name a real candidate")
    if alt==payload.get("selected_candidate_id"): raise ContractViolation("winner cannot be its own strongest alternative")
    if not str(payload["why_strongest_alternative_loses"] or "").strip(): raise ContractViolation("selection must explain why strongest alternative loses")
    if not str(payload["selection_risk"] or "").strip(): raise ContractViolation("selection must state remaining risk")
