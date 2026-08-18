from __future__ import annotations

import copy
import unittest

from nexmind_god_mode.council import CreativeCouncil
from nexmind_god_mode.executive_producer import ExecutiveProducer
from nexmind_god_mode.provider_schemas import STORY_SCHEMA
from nexmind_god_mode.showrunner_p2 import NexMindSupremeShowrunnerP2
from nexmind_god_mode.story_director import StoryDirector


class CaptureProvider:
    def __init__(self, story):
        self.story = copy.deepcopy(story)
        self.calls = []

    def complete(self, task, request):
        self.calls.append((task, copy.deepcopy(request)))
        if task == "story":
            return copy.deepcopy(self.story)
        if task == "producer":
            return {
                "verdict": "ACCEPT",
                "issues": [],
                "strengths": ["contract aligned"],
                "revision_brief": "",
                "commercial_confidence": "HIGH",
            }
        raise AssertionError(task)


class DummyVisual:
    pass


class DummySelector:
    pass


class StoryReviewContractV2Tests(unittest.TestCase):
    def setUp(self):
        self.story = {
            "film_thesis": {
                "central_argument": "The cook notices an early change and corrects it deliberately.",
                "film_kind": "30-second product film",
                "audience_before": "Heat control feels generic.",
                "audience_after": "Precise control feels like an extension of judgment.",
                "hero_kind": "cook",
                "camera_idea": "intimate food-level observation following the cook's attention",
                "emotional_trajectory": ["tension", "agency", "confidence"],
                "visual_trajectory": ["sauce texture", "eyes and hand", "recovery"],
                "opening_contract": "A sauce begins to separate.",
                "final_payoff": "The cook finishes confidently.",
                "anti_goals": ["no feature list"],
            },
            "beats": [
                {
                    "beat_id": "B1",
                    "purpose": "notice",
                    "question": "Will the cook catch it?",
                    "audience_before": "ordinary cooking",
                    "audience_after": "a decision is imminent",
                    "hero_state": "cook detects emerging graininess",
                    "reveal": "macro sauce begins to separate",
                    "required_claim_ids": [],
                },
                {
                    "beat_id": "B2",
                    "purpose": "correct",
                    "question": "Can a small correction work?",
                    "audience_before": "uncertain",
                    "audience_after": "control is legible",
                    "hero_state": "cook makes a small decrement and watches the response",
                    "reveal": "bubbling softens and whisking steadies the sauce",
                    "required_claim_ids": [],
                },
            ],
        }

    def _run(self):
        provider = CaptureProvider(self.story)
        sr = NexMindSupremeShowrunnerP2("P", {"topic": "x"})
        council = CreativeCouncil(sr, StoryDirector(provider), DummyVisual(), ExecutiveProducer(provider), DummySelector())
        result = council.develop_story([])
        producer_request = next(req for task, req in provider.calls if task == "producer")
        return result, producer_request

    def test_live_story_schema_requires_reviewer_owned_fields(self):
        thesis_required = STORY_SCHEMA["properties"]["film_thesis"]["required"]
        beat_required = STORY_SCHEMA["properties"]["beats"]["items"]["required"]
        self.assertIn("hero_kind", thesis_required)
        self.assertIn("camera_idea", thesis_required)
        self.assertIn("hero_state", beat_required)

    def test_story_candidate_metadata_is_authored_not_adapter_placeholder(self):
        _, req = self._run()
        candidate = req["candidate"]
        self.assertEqual(candidate["hero_kind"], "cook")
        self.assertEqual(candidate["camera_idea"], "intimate food-level observation following the cook's attention")
        self.assertEqual(candidate["beat_treatments"][0]["hero_state"], "cook detects emerging graininess")
        self.assertNotEqual(candidate["hero_kind"], "audience understanding")
        self.assertNotIn("no camera committed", candidate["camera_idea"].lower())

    def test_producer_receives_explicit_editable_contract(self):
        _, req = self._run()
        contract = req["editable_contract"]
        self.assertEqual(contract["owner_department"], "STORY")
        self.assertIn("film_thesis.hero_kind", contract["editable_fields"])
        self.assertIn("film_thesis.camera_idea", contract["editable_fields"])
        self.assertIn("beats[].hero_state", contract["editable_fields"])

    def test_story_proposal_and_review_candidate_agree(self):
        result, req = self._run()
        proposal = result["proposal"]
        stored = result["story"]["film_thesis"]
        candidate = req["candidate"]
        self.assertEqual(stored["hero_kind"], candidate["hero_kind"])
        self.assertEqual(stored["camera_idea"], candidate["camera_idea"])
        self.assertEqual(proposal.proposal_id, candidate["candidate_id"])


if __name__ == "__main__":
    unittest.main()
