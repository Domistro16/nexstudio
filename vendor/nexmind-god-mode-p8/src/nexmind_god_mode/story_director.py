from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable
import json

from .contracts import ContractViolation, validate_evidence_ledger, validate_story_output
from .provider import CreativeModelProvider


class StoryDirector:
    def __init__(self, provider: CreativeModelProvider):
        self.provider = provider

    def propose(self, production_id: str, brief: Dict[str, Any], evidence: Iterable[Dict[str, Any]], doctrine: Dict[str, Any], *, strategy_lens: str | None = None, competition_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        ledger = validate_evidence_ledger(evidence)
        evidence_ids = {x["claim_id"] for x in ledger}
        revision_context = brief.get("autonomous_revision_context") if isinstance(brief.get("autonomous_revision_context"), dict) else {}
        revision_department = revision_context.get("department") or revision_context.get("owner_department")
        broader_replan = revision_department == "STORY" and revision_context.get("repair_mode") == "MATERIAL_STRATEGY_REPLAN"
        previous_output = revision_context.get("previous_output") if revision_department == "STORY" else None
        repair_anchor = previous_output.get("story") if isinstance(previous_output, dict) and isinstance(previous_output.get("story"), dict) else previous_output
        surgical_repair = isinstance(repair_anchor, dict) and bool(repair_anchor) and not broader_replan
        negative_signatures = deepcopy(revision_context.get("exhausted_strategy_signatures") or []) if broader_replan else []
        request = {
            "production_id": production_id,
            "brief": deepcopy(brief),
            "evidence_ledger": ledger,
            "creative_doctrine": deepcopy(doctrine),
            "repair_anchor": deepcopy(repair_anchor) if surgical_repair else None,
            "candidate_competition_context": deepcopy(competition_context or {}),
            "exhausted_strategy_signatures": negative_signatures,
            "instruction": {
                "goal": (
                    "Surgically repair the supplied Story repair_anchor into one stronger narrative strategy. Preserve every accepted strength and unaffected decision, and resolve the binding Producer issues without reopening candidate competition."
                    if surgical_repair else
                    ("Materially replan Story after lineage exhaustion. Invent one genuinely different governing causal strategy from the customer brief and authoritative evidence. Prior rejected Story inventions are negative-only anti-repetition context, not requirements to preserve." if broader_replan else "Create one complete film thesis and audience-state beat structure before visual execution.")
                ),
                "strategy_lens": strategy_lens or ("SURGICAL_REPAIR_OF_STRONGEST_REJECTED_STORY" if surgical_repair else "INVENT_A_BRIEF_SPECIFIC_NARRATIVE_STRATEGY"),
                "competition_law": "ONE_CANDIDATE_EQUALS_ONE_FILM. The outer CreativeCouncil owns strategy competition. Never compare, rank, list, summarize, or select alternative routes inside this candidate.",
                "restart_law": (
                    "This is a clean Story restart. You may discard every prop, character action, beat device, camera device, payoff object, or visual motif invented by the rejected lineage unless it is independently required by the customer brief, brand context, customer revision, or evidence ledger. Do not mention exhausted_strategy_signatures in the output; use them only to avoid recreating the same governing causal pattern."
                    if broader_replan else "NONE"
                ),
                "must": [
                    "commit to exactly one governing narrative strategy in this candidate; never write an options/route comparison or explain why this candidate was selected over alternatives",
                    "change audience belief or understanding across beats",
                    "use only supplied evidence ids for factual claims",
                    "separate film argument from literal sentence-by-sentence visualization",
                    "declare the on-screen hero/causal agent in film_thesis.hero_kind",
                    "commit a story-level governing visual/camera principle in film_thesis.camera_idea without prescribing shot-level cinematography",
                    "for every beat, express hero_state as the observable state/progression of that hero, never as audience understanding",
                    "when autonomous_revision_context requests changes to hero_kind, camera_idea, or hero_state, edit those authored fields directly",
                    "author narration_mode/narration_text/narration_purpose for every beat; choose SILENT when narration would weaken the film, and never use narration to compensate for weak visual storytelling",
                    "when narration_mode is VOICEOVER, write concise spoken copy that advances the argument rather than reading on-screen labels",
                    "produce no coordinates, renderer code, or creative-lock authority",
                ],
            },
        }
        payload = self.provider.complete("story", request)
        story = validate_story_output(payload, evidence_ids)
        self._enforce_single_strategy_candidate(story)
        return story

    @staticmethod
    def _enforce_single_strategy_candidate(story: Dict[str, Any]) -> None:
        """Reject nested strategy competitions inside one Story candidate.

        The CreativeCouncil already owns candidate competition. A Story candidate must
        therefore be one film, not an essay that compares several routes and selects one.
        This is treated as an output-contract miss so it can be regenerated without
        consuming a creative-quality attempt.
        """
        thesis = story.get("film_thesis") or {}
        corpus = " ".join(str(thesis.get(k) or "") for k in (
            "central_argument", "film_kind", "opening_contract", "final_payoff"
        )).lower()
        competition_terms = (" route", "routes", " option", "options", " alternative", "alternatives", " candidate", "candidates", "strategies")
        selection_terms = ("compare", "compared", "comparison", "select", "selected", "choose", "chosen", "strongest", "ranked", "three materially different")
        explicit_markers = ("candidate a", "candidate b", "candidate c", "route 1", "route 2", "route 3", "option 1", "option 2", "option 3")
        if any(x in corpus for x in explicit_markers) or (any(x in corpus for x in competition_terms) and any(x in corpus for x in selection_terms)):
            raise ContractViolation("story candidate contains nested strategy competition; one Story candidate must commit to exactly one film and must not compare/select alternative routes")

    @staticmethod
    def _candidate_target(brief: Dict[str, Any], evidence: list[Dict[str, Any]]) -> int:
        """Choose a bounded operational competition depth from task complexity.

        This is a resource budget, not creative doctrine: the brief never receives a
        fixed house count such as "always three ideas".  The semantic diversity
        validator remains authoritative and can reject near-duplicate candidates.
        """
        target = 2
        # Operational competition depth is driven by actual complexity. Topic/goal
        # presence is intentionally ignored because _brief() always populates them;
        # counting them made every simple brief look complex and forced a third Story call.
        duration = int(brief.get("duration_s") or 0)
        if duration >= 45:
            target += 1
        if len(evidence) >= 8:
            target += 1
        if len(evidence) >= 30:
            target += 1
        complexity_brief={k:v for k,v in brief.items() if k not in {
            "autonomous_revision_context","autonomous_repair_context","creative_memory_context","source_intelligence"
        }}
        if len(json.dumps(complexity_brief, ensure_ascii=False, sort_keys=True)) >= 1800:
            target += 1
        return max(2, min(5, target))

    def propose_candidates(self, production_id: str, brief: Dict[str, Any], evidence: Iterable[Dict[str, Any]], doctrine: Dict[str, Any]) -> list[Dict[str, Any]]:
        evidence = list(evidence)
        candidates=[]
        revision_context = brief.get("autonomous_revision_context") if isinstance(brief.get("autonomous_revision_context"), dict) else {}
        revision_department = revision_context.get("department") or revision_context.get("owner_department")
        previous_output = revision_context.get("previous_output") if revision_department == "STORY" else None
        broader_replan = revision_department == "STORY" and revision_context.get("repair_mode") == "MATERIAL_STRATEGY_REPLAN"
        surgical_repair = isinstance(previous_output, dict) and bool(previous_output) and not broader_replan
        target = 1 if surgical_repair else self._candidate_target(brief,evidence)
        for index in range(target):
            prior=[{
                "central_argument":c.get("film_thesis",{}).get("central_argument"),
                "hero_kind":c.get("film_thesis",{}).get("hero_kind"),
                "opening_contract":c.get("film_thesis",{}).get("opening_contract"),
                "final_payoff":c.get("film_thesis",{}).get("final_payoff"),
            } for c in candidates]
            lens=("SURGICAL_REPAIR_OF_STRONGEST_REJECTED_STORY" if surgical_repair else ("INVENT_A_BRIEF_SPECIFIC_NARRATIVE_STRATEGY" if not prior else "INVENT_A_MATERIALLY_DIFFERENT_STRATEGY_NOT_EQUIVALENT_TO_PRIOR"))
            competition_context={
                "candidate_index": index + 1,
                "candidate_count": target,
                "prior_candidate_signatures": prior,
                "law": "Prior signatures are negative-only anti-repetition constraints. Do not discuss, compare, rank, or select them in the candidate output.",
            }
            candidates.append(self.propose(production_id, brief, evidence, doctrine, strategy_lens=lens, competition_context=competition_context))
        return candidates
