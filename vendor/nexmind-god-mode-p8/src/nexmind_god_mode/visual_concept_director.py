from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from .contracts import validate_visual_output
from .provider import CreativeModelProvider


class VisualConceptDirector:
    def __init__(self, provider: CreativeModelProvider):
        self.provider = provider

    def propose(self, production_id: str, brief: Dict[str, Any], story: Dict[str, Any], doctrine: Dict[str, Any], capability_graph: Dict[str, Any]) -> List[Dict[str, Any]]:
        beat_ids = {x["beat_id"] for x in story["beats"]}
        brief_copy=deepcopy(brief)
        reference_visual_evidence=brief_copy.pop("_direct_reference_visuals",[])
        reference_visual_omissions=brief_copy.pop("_direct_reference_visual_omissions",[])
        revision_context = brief_copy.get("autonomous_revision_context") if isinstance(brief_copy.get("autonomous_revision_context"), dict) else {}
        broader_replan = revision_context.get("department") == "VISUAL_CONCEPT" and revision_context.get("repair_mode") == "MATERIAL_STRATEGY_REPLAN"
        repair_anchor = revision_context.get("previous_output") if revision_context.get("department") == "VISUAL_CONCEPT" else None
        repair_mode = isinstance(repair_anchor, dict) and bool(repair_anchor) and not broader_replan
        duration=int(brief_copy.get("duration_s") or 0)
        candidate_budget=1 if repair_mode else 3 + (1 if duration>=45 or len(story.get("beats") or [])>=6 or len(reference_visual_evidence)>=3 else 0)
        candidate_budget=max(1,min(5,candidate_budget))
        request = {
            "production_id": production_id,
            "brief": brief_copy,
            "reference_visual_evidence": reference_visual_evidence,
            "reference_visual_omissions": reference_visual_omissions,
            "film_thesis": deepcopy(story["film_thesis"]),
            "beats": deepcopy(story["beats"]),
            "creative_doctrine": deepcopy(doctrine),
            "capability_graph": deepcopy(capability_graph),
            "repair_anchor": deepcopy(repair_anchor) if repair_mode else None,
            "candidate_budget": candidate_budget,
            "instruction": {
                "goal": (
                    "Surgically repair the supplied repair_anchor into exactly one stronger senior-commercial visual concept. Preserve every anchor decision not implicated by the binding repair context; do not reopen resolved choices or generate alternative concepts."
                    if repair_mode else
                    (f"The prior downstream lineage exhausted Art/production repair. Materially replan the Visual Concept against the accepted Story with exactly {candidate_budget} genuinely different strategies rather than cosmetically polishing the exhausted visual route." if broader_replan else f"Generate exactly {candidate_budget} genuinely different senior-commercial visual concepts. Each must be a different way of thinking, not a different layout for the same idea.")
                ),
                "must": [
                    "choose a dominant hero and transformation",
                    "cover every story beat",
                    "prefer authored/assembled form when recognizable hero quality matters",
                    "avoid generic cards, connector soup, tiny central icons, and default dashboards",
                    "make every concept brief-specific: its visual thesis, hero, transformation and beat actions should be difficult to transplant unchanged to an unrelated client brief",
                    "rehearse the concept through a brief-specific sequence of authored visual states; choose the number and labels from the actual visual argument rather than a house four-stage template",
                    "prefer an authored world, physical consequence, character event, product-native treatment, typography/data argument or hybrid only when that strategy is genuinely best for this brief",
                    "do not default to the safest literal middle option; compare emotional force, memorability, authorship and commercial distinctiveness",
                    "author concept_signature explicitly: brief-specific hook, governing visual logic, emotional engine, memorability device, and a transplant test explaining why the concept cannot be moved unchanged to an unrelated brief",
                    "author rehearsal_states as an open sequence of labeled visual states before selection; the sequence must prove the concept across its actual argument, not satisfy a fixed house progression",
                    "author originality_guard explicitly: reference independence, template/repetition risk, and why the chosen idea is not the obvious first-answer treatment",
                    "for every beat author the world state, supporting elements, visible consequence of the action and continuity handoff; a noun list is not enough",
                    "if the highest-ambition realization exceeds current premium body capability, invent a different equally strong executable concept rather than silently degrading it",
                    "when repair_anchor is supplied, return exactly one candidate derived from that anchor; keep its governing concept/relationship/staging decisions unless a listed issue explicitly requires changing them",
                    "when repair_anchor is supplied, every sticky_requirement in autonomous_revision_context is binding and must not regress",
                    "production-only empirical validation requirements may be acknowledged as downstream production checks, but do not invent measured test results",
                    "produce no coordinates or renderer code",
                ],
            },
        }
        payload = self.provider.complete("visual", request)
        return validate_visual_output(payload, beat_ids, repair_mode=repair_mode)
