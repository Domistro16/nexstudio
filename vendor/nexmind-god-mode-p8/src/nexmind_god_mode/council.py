from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Tuple
from concurrent.futures import ThreadPoolExecutor
import os

from .executive_producer import ExecutiveProducer
from .contracts import ContractViolation
from .showrunner_p2 import NexMindSupremeShowrunnerP2, ProducerGateError
from .story_director import StoryDirector
from .showrunner_reasoner import ShowrunnerDecisionIntelligence
from .visual_concept_director import VisualConceptDirector


def _review_parallelism(count: int) -> int:
    try:
        value=int(os.getenv("NEXMIND_REVIEW_PARALLELISM","3") or 3)
    except Exception:
        value=3
    return max(1,min(count,max(1,min(6,value))))

def _parallel_map(items, fn):
    items=list(items)
    if len(items)<=1 or _review_parallelism(len(items))<=1:
        return [fn(x) for x in items]
    with ThreadPoolExecutor(max_workers=_review_parallelism(len(items)), thread_name_prefix="nexmind-review") as pool:
        futures=[pool.submit(fn,x) for x in items]
        return [f.result() for f in futures]


class CreativeCouncil:
    """Non-linear P2 council. Departments propose; Showrunner commits reviewed work."""

    def __init__(self, showrunner: NexMindSupremeShowrunnerP2, story: StoryDirector, visual: VisualConceptDirector, producer: ExecutiveProducer, selector: ShowrunnerDecisionIntelligence):
        self.showrunner = showrunner
        self.story_director = story
        self.visual_director = visual
        self.producer = producer
        self.selector = selector

    def develop_story(self, evidence: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        evidence = list(evidence)
        self.showrunner.set_evidence(evidence)
        story = self.story_director.propose(
            self.showrunner.state["production_id"],
            self.showrunner.state["brief"],
            evidence,
            self.showrunner.state["creative_doctrine"],
        )
        ref = self.showrunner.submit_proposal("StoryDirector", f"story-r{self.showrunner.state['revision']}", {
            "representation": "NARRATIVE_ARGUMENT",
            "visual_thesis": story["film_thesis"]["central_argument"],
            "hero_kind": story["film_thesis"]["hero_kind"],
            "transformation": f"{story['film_thesis']['audience_before']} -> {story['film_thesis']['audience_after']}",
            "camera_idea": story["film_thesis"]["camera_idea"],
            "story": deepcopy(story),
        })
        # Producer reviews Story as a narrative candidate using a thin visual-shaped adapter.
        story_candidate = {
            "candidate_id": ref.proposal_id,
            "representation": "NARRATIVE_ARGUMENT",
            "visual_thesis": story["film_thesis"]["central_argument"],
            "hero_kind": story["film_thesis"]["hero_kind"],
            "transformation": f"belief changes from {story['film_thesis']['audience_before']} to {story['film_thesis']['audience_after']}",
            "camera_idea": story["film_thesis"]["camera_idea"],
            "rationale": story["film_thesis"]["final_payoff"],
            "beat_treatments": [
                {"beat_id": b["beat_id"], "hero_state": b["hero_state"], "visual_action": b["reveal"], "audience_takeaway": b["audience_after"]}
                for b in story["beats"]
            ],
        }
        review = self.producer.review(
            self.showrunner.state["production_id"],
            self.showrunner.state["brief"],
            story,
            story_candidate,
            editable_contract={
                "owner_department": "STORY",
                "editable_fields": [
                    "film_thesis.hero_kind", "film_thesis.camera_idea",
                    "film_thesis.central_argument", "film_thesis.visual_trajectory",
                    "film_thesis.opening_contract", "film_thesis.final_payoff",
                    "beats[].hero_state", "beats[].purpose", "beats[].question",
                    "beats[].reveal", "beats[].audience_before", "beats[].audience_after",
                ],
                "boundary": "Story owns narrative hero, beat-level hero progression, and a governing visual principle; Visual/Cinematography own later representation and shot execution.",
            },
        )
        token = self.showrunner.register_producer_review("film_thesis", ref, review)
        if review["verdict"] == "ACCEPT":
            self.showrunner.commit_reviewed_decision("film_thesis", ref, token)
        return {"story": story, "proposal": ref, "review": review, "review_id": token}

    def develop_story_competition(self, evidence: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        evidence = list(evidence)
        self.showrunner.set_evidence(evidence)
        stories = self.story_director.propose_candidates(
            self.showrunner.state["production_id"],
            self.showrunner.state["brief"],
            evidence,
            self.showrunner.state["creative_doctrine"],
        )
        prepared=[];refs=[]
        for idx, story in enumerate(stories, start=1):
            candidate_id=f"story-r{self.showrunner.state['revision']}-c{idx}"
            candidate={
                "candidate_id":candidate_id,
                "representation":"NARRATIVE_ARGUMENT",
                "visual_thesis":story["film_thesis"]["central_argument"],
                "hero_kind":story["film_thesis"]["hero_kind"],
                "transformation":f"{story['film_thesis']['audience_before']} -> {story['film_thesis']['audience_after']}",
                "camera_idea":story["film_thesis"]["camera_idea"],
                "rationale":story["film_thesis"]["final_payoff"],
                "beat_treatments":[{
                    "beat_id":b["beat_id"],"hero_state":b["hero_state"],"visual_action":b["reveal"],"audience_takeaway":b["audience_after"]
                } for b in story["beats"]],
                "story":deepcopy(story),
            }
            ref=self.showrunner.submit_proposal("StoryDirector", candidate_id, candidate);refs.append(ref)
            prepared.append((story,candidate,ref))
        editable_contract={
            "owner_department":"STORY",
            "editable_fields":["film_thesis.hero_kind","film_thesis.camera_idea","film_thesis.central_argument","film_thesis.visual_trajectory","film_thesis.opening_contract","film_thesis.final_payoff","beats[].hero_state","beats[].purpose","beats[].question","beats[].reveal","beats[].audience_before","beats[].audience_after"],
            "boundary":"Story owns narrative hero, beat-level hero progression, and governing visual principle; later departments own representation and shot execution.",
        }
        def review_one(item):
            story,candidate,ref=item
            review=self.producer.review(self.showrunner.state["production_id"],self.showrunner.state["brief"],story,candidate,editable_contract=editable_contract)
            return story,candidate,ref,review
        reviewed=_parallel_map(prepared,review_one)
        reviews=[]
        for story,candidate,ref,review in reviewed:
            token=self.showrunner.register_producer_review("film_thesis",ref,review)
            reviews.append({"candidate":candidate,"proposal":ref,"review":review,"review_id":token})
        revision_context=self.showrunner.state["brief"].get("autonomous_revision_context") or {}
        surgical_repair=revision_context.get("department")=="STORY" and revision_context.get("repair_mode")!="MATERIAL_STRATEGY_REPLAN" and len(reviews)==1
        diversity={"meaningfully_diverse":True,"surgical_repair":True} if surgical_repair else self.showrunner.candidate_diversity("StoryDirector",[r.proposal_id for r in refs])
        if not surgical_repair and not diversity["meaningfully_diverse"]:
            # Governance invariant: story candidate set is not meaningfully diverse -> never commit.
            # Diversity is a creative-set quality failure, not a kernel/governance crash.
            # Return the reviewed set uncommitted so the orchestrator can schedule a
            # materially new competition without anchoring to one near-duplicate idea.
            return {"story":None,"reviews":reviews,"diversity":diversity,"selection":None,"governance_issue":"CANDIDATE_SET_NOT_MEANINGFULLY_DIVERSE"}
        accepted=[x for x in reviews if x["review"]["verdict"]=="ACCEPT"]
        if not accepted:
            return {"story":None,"reviews":reviews,"diversity":diversity,"selection":None}
        if len(accepted)==1:
            chosen=accepted[0]
            selection={"selected_candidate_id":chosen["candidate"]["candidate_id"],"why":"Only Producer-accepted Story candidate; no redundant selector call required.","tradeoffs":[],"rejected_alternatives":[],"notes":"Deterministic single-accepted commit."}
        else:
            selection=self.selector.select_story(self.showrunner.state["production_id"],self.showrunner.state["brief"],reviews)
            chosen=next((x for x in accepted if x["candidate"]["candidate_id"]==selection["selected_candidate_id"]),None)
            if not chosen: raise ContractViolation("selected Story candidate is missing or not Producer-accepted")
        self.showrunner.commit_reviewed_decision("film_thesis",chosen["proposal"],chosen["review_id"],require_diversity_from=None if surgical_repair else [r.proposal_id for r in refs])
        return {"story":chosen["candidate"]["story"],"reviews":reviews,"diversity":diversity,"selection":selection}

    def develop_visual_candidates(self, story: Dict[str, Any]) -> Dict[str, Any]:
        candidates = self.visual_director.propose(
            self.showrunner.state["production_id"],
            self.showrunner.state["brief"],
            story,
            self.showrunner.state["creative_doctrine"],
            self.showrunner.state["capability_graph"],
        )
        refs = []
        prepared=[]
        for c in candidates:
            proposal_id = c["candidate_id"]
            if proposal_id in self.showrunner.state.get("proposals", {}).get("VisualConceptDirector", {}):
                proposal_id = f"r{self.showrunner.state['revision']}:{proposal_id}"
            ref = self.showrunner.submit_proposal("VisualConceptDirector", proposal_id, c)
            refs.append(ref); prepared.append((c,ref))
        editable_contract={
            "owner_department": "VISUAL_CONCEPT",
            "editable_fields": ["representation", "visual_thesis", "hero_kind", "transformation", "camera_idea", "rationale", "concept_signature", "rehearsal_states", "originality_guard", "beat_treatments[]"],
            "boundary": "Visual Concept owns authored visual strategy and rehearsal states. It may specify plausible production behavior and required downstream validation, but it cannot supply fabricated real-world measurements, physical test results, final shot execution, renderer output, or production evidence."
        }
        revision_context=deepcopy(self.showrunner.state["brief"].get("autonomous_revision_context") or {})
        def review_visual(item):
            c,ref=item
            review=self.producer.review(self.showrunner.state["production_id"],self.showrunner.state["brief"],story,c,revision_context=revision_context,editable_contract=editable_contract)
            return c,ref,review
        reviews=[]
        for c,ref,review in _parallel_map(prepared,review_visual):
            token = self.showrunner.register_producer_review("visual_concept", ref, review)
            reviews.append({"candidate": c, "proposal": ref, "review": review, "review_id": token})
        surgical_repair = revision_context.get("department") == "VISUAL_CONCEPT" and revision_context.get("repair_mode") != "MATERIAL_STRATEGY_REPLAN" and len(reviews) == 1
        diversity = {"meaningfully_diverse":True,"surgical_repair":True} if surgical_repair else self.showrunner.candidate_diversity("VisualConceptDirector", [r.proposal_id for r in refs])
        return {"candidates": candidates, "reviews": reviews, "diversity": diversity}


    def showrunner_select_visual(self, story: Dict[str, Any], visual_result: Dict[str, Any]) -> Dict[str, Any]:
        accepted = [x for x in visual_result["reviews"] if x["review"]["verdict"] == "ACCEPT"]
        revision_context = self.showrunner.state["brief"].get("autonomous_revision_context") or {}
        surgical_repair = revision_context.get("department") == "VISUAL_CONCEPT" and len(visual_result["reviews"]) == 1
        if surgical_repair:
            if len(accepted) != 1:
                raise ProducerGateError("surgical visual repair requires exactly one Producer-accepted repaired candidate")
            chosen = accepted[0]
            selection = {
                "selected_candidate_id": chosen["candidate"]["candidate_id"],
                "why": "Producer-accepted surgical repair of the previously selected repair anchor.",
                "tradeoffs": [],
                "rejected_alternatives": [],
                "notes": "Candidate competition is intentionally not reopened during bounded surgical repair.",
            }
            committed = self.choose_visual(visual_result, selection["selected_candidate_id"], require_diversity=False)
            return {"selection": selection, "committed": committed, "selected_review": deepcopy(chosen["review"])}
        if len(accepted)==1:
            chosen=accepted[0]
            selection={"selected_candidate_id":chosen["candidate"]["candidate_id"],"why":"Only Producer-accepted Visual candidate; no redundant selector call required.","tradeoffs":[],"rejected_alternatives":[],"notes":"Deterministic single-accepted commit."}
        else:
            selection = self.selector.select_visual(
                self.showrunner.state["production_id"],
                self.showrunner.state["brief"],
                story,
                visual_result["reviews"],
            )
            chosen = next((x for x in accepted if x["candidate"]["candidate_id"] == selection["selected_candidate_id"]), None)
            if chosen is None:
                raise ContractViolation("selected Visual candidate is missing or not Producer-accepted")
        committed = self.choose_visual(visual_result, selection["selected_candidate_id"])
        return {"selection": selection, "committed": committed, "selected_review": deepcopy(chosen["review"])}

    def choose_visual(self, visual_result: Dict[str, Any], candidate_id: str, *, require_diversity: bool = True) -> Dict[str, Any]:
        chosen = next((x for x in visual_result["reviews"] if x["candidate"]["candidate_id"] == candidate_id), None)
        if not chosen:
            raise ProducerGateError(f"candidate not found: {candidate_id}")
        all_ids = [x["proposal"].proposal_id for x in visual_result["reviews"]]
        committed = self.showrunner.commit_reviewed_decision(
            "visual_concept",
            chosen["proposal"],
            chosen["review_id"],
            require_diversity_from=all_ids if require_diversity else None,
        )
        return committed
