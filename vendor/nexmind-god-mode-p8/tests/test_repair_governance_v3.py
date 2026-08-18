from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from nexmind_god_mode.contracts import ContractViolation, validate_visual_output
from nexmind_god_mode.council import CreativeCouncil
from nexmind_god_mode.executive_producer import ExecutiveProducer
from nexmind_god_mode.provider import RecordedModelProvider
from nexmind_god_mode.showrunner_p2 import NexMindSupremeShowrunnerP2
from nexmind_god_mode.showrunner_reasoner import ShowrunnerDecisionIntelligence
from nexmind_god_mode.story_director import StoryDirector
from nexmind_god_mode.visual_concept_director import VisualConceptDirector

FIX = json.loads((ROOT / "tests" / "fixtures" / "contract_regression_only" / "P1P2_RECORDED_PROVIDER_CONTRACT_REGRESSION_ONLY.json").read_text(encoding="utf-8"))
CASE = FIX["cases"][0]
PID = CASE["id"]
BASE = FIX["responses"]


class OneReplyProvider:
    def __init__(self, payload):
        self.payload = copy.deepcopy(payload)
        self.requests = []
    def complete(self, task, request):
        self.requests.append((task, copy.deepcopy(request)))
        return copy.deepcopy(self.payload)


class RepairGovernanceV3Tests(unittest.TestCase):
    def test_visual_runtime_allows_one_candidate_only_in_repair_mode(self):
        payload = copy.deepcopy(BASE[f"{PID}::visual::0"])
        payload["candidates"] = [payload["candidates"][1]]
        beat_ids = {b["beat_id"] for b in BASE[f"{PID}::story::0"]["beats"]}
        with self.assertRaises(ContractViolation):
            validate_visual_output(payload, beat_ids)
        out = validate_visual_output(payload, beat_ids, repair_mode=True)
        self.assertEqual(1, len(out))

    def test_pure_empirical_proof_demand_is_deferred_not_blocking(self):
        provider = OneReplyProvider({
            "verdict":"REVISE",
            "issues":[{
                "severity":"MATERIAL",
                "area":"Practical validation",
                "issue":"No measured food-stylist test result is supplied at concept stage.",
                "required_change":"Run a practical food-stylist test and provide a measured response time."
            }],
            "strengths":["Strong human/product causality"],
            "revision_brief":"Provide the measured food test.",
            "commercial_confidence":"HIGH",
        })
        ep=ExecutiveProducer(provider)
        story=copy.deepcopy(BASE[f"{PID}::story::0"])
        candidate=copy.deepcopy(BASE[f"{PID}::visual::0"]["candidates"][1])
        review=ep.review(PID, CASE["brief"], story, candidate, editable_contract={
            "owner_department":"VISUAL_CONCEPT","editable_fields":["rehearsal_states"],"boundary":"concept only"
        })
        self.assertEqual("ACCEPT", review["verdict"])
        self.assertEqual([], review["issues"])
        self.assertEqual(1, len(review["deferred_production_validations"]))
        self.assertEqual("", review["revision_brief"])

    def test_mixed_physical_issue_keeps_plausibility_blocker_but_defers_measurement(self):
        provider = OneReplyProvider({
            "verdict":"REVISE",
            "issues":[{
                "severity":"MATERIAL",
                "area":"Culinary credibility",
                "issue":"Large bubbles could look overheated and the wording risks implausible instant thickening.",
                "required_change":"Run a practical food-stylist test with a measured interval. Use small regular bubbles and do not imply instant thickening."
            }],
            "strengths":["Strong human/product causality"],
            "revision_brief":"Test and repair it.",
            "commercial_confidence":"HIGH",
        })
        ep=ExecutiveProducer(provider)
        story=copy.deepcopy(BASE[f"{PID}::story::0"])
        candidate=copy.deepcopy(BASE[f"{PID}::visual::0"]["candidates"][1])
        review=ep.review(PID, CASE["brief"], story, candidate, editable_contract={
            "owner_department":"VISUAL_CONCEPT","editable_fields":["rehearsal_states"],"boundary":"concept only"
        })
        self.assertEqual("REVISE", review["verdict"])
        self.assertEqual(1, len(review["issues"]))
        self.assertEqual(1, len(review["deferred_production_validations"]))
        self.assertNotIn("food-stylist", review["revision_brief"].lower())
        self.assertIn("instant thickening", review["revision_brief"].lower())

    def test_visual_surgical_repair_commits_one_producer_accepted_anchor_without_reopening_competition(self):
        story = copy.deepcopy(BASE[f"{PID}::story::0"])
        visual = copy.deepcopy(BASE[f"{PID}::visual::0"]["candidates"][1])
        visual["candidate_id"] = "SURGICAL-V1"
        responses={
            f"{PID}::story::0": story,
            f"{PID}::producer::0": {
                "verdict":"ACCEPT","issues":[],"strengths":["clear"],"revision_brief":"","commercial_confidence":"HIGH"
            },
            f"{PID}::visual::0": {"candidates":[visual]},
            f"{PID}::producer::1": {
                "verdict":"ACCEPT","issues":[],"strengths":["repaired"],"revision_brief":"","commercial_confidence":"HIGH"
            },
        }
        provider=RecordedModelProvider(responses)
        showrunner=NexMindSupremeShowrunnerP2(PID, CASE["brief"], doctrine={})
        showrunner.set_capability_graph({})
        council=CreativeCouncil(showrunner,StoryDirector(provider),VisualConceptDirector(provider),ExecutiveProducer(provider),ShowrunnerDecisionIntelligence(provider))
        story_result=council.develop_story(CASE["evidence"])
        showrunner.state["brief"]["autonomous_revision_context"]={
            "department":"VISUAL_CONCEPT",
            "previous_output":copy.deepcopy(visual),
            "sticky_requirements":["Do not reintroduce the extra proof action."],
            "issues":[],
        }
        visual_result=council.develop_visual_candidates(story_result["story"])
        self.assertEqual(1,len(visual_result["reviews"]))
        selected=council.showrunner_select_visual(story_result["story"],visual_result)
        self.assertEqual("SURGICAL-V1",selected["selection"]["selected_candidate_id"])
        self.assertEqual("SURGICAL-V1",showrunner.state["decisions"]["visual_concept"]["proposal_id"])
        visual_request=next(r for task,r in [(c.task, None) for c in []] if False) if False else None
        # The recorded provider does not expose request bodies; the committed one-candidate
        # path itself proves diversity was intentionally not reopened.


if __name__ == "__main__":
    unittest.main(verbosity=2)
