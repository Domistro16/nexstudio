from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from nexmind_god_mode.contracts import (
    ContractViolation,
    validate_producer_output,
    validate_story_output,
    validate_visual_output,
)
from nexmind_god_mode.council import CreativeCouncil
from nexmind_god_mode.executive_producer import ExecutiveProducer
from nexmind_god_mode.provider import RecordedModelProvider
from nexmind_god_mode.showrunner_p2 import NexMindSupremeShowrunnerP2, ProducerGateError
from nexmind_god_mode.showrunner_reasoner import ShowrunnerDecisionIntelligence
from nexmind_god_mode.p0_kernel import AuthorityViolation, CandidateError, CreativeLockError, ProposalRef
from nexmind_god_mode.story_director import StoryDirector
from nexmind_god_mode.visual_concept_director import VisualConceptDirector

FIX = json.loads((ROOT / "tests" / "fixtures" / "contract_regression_only" / "P1P2_RECORDED_PROVIDER_CONTRACT_REGRESSION_ONLY.json").read_text(encoding="utf-8"))
RESPONSES = FIX["responses"]
CASES = FIX["cases"]

DOCTRINE = {
    "hero_first": True,
    "story_before_diagram": True,
    "anti_patterns": ["card_grid", "connector_soup", "tiny_central_hero", "decorative_motion"],
}
CAPS = {
    "authored_illustration": True,
    "assembled_illustration": True,
    "mechanism": True,
    "character": True,
    "camera": {"hold": True, "track": True, "macro_dive": True},
}


def make_stack(case, responses=None):
    provider = RecordedModelProvider(responses or RESPONSES)
    showrunner = NexMindSupremeShowrunnerP2(case["id"], case["brief"], doctrine=DOCTRINE)
    showrunner.set_capability_graph(CAPS)
    council = CreativeCouncil(
        showrunner,
        StoryDirector(provider),
        VisualConceptDirector(provider),
        ExecutiveProducer(provider),
        ShowrunnerDecisionIntelligence(provider),
    )
    return provider, showrunner, council


def run_case(case):
    provider, s, council = make_stack(case)
    story_result = council.develop_story(case["evidence"])
    visual_result = council.develop_visual_candidates(story_result["story"])
    selection = council.showrunner_select_visual(story_result["story"], visual_result)
    gate = s.p2_gate()
    return provider, s, story_result, visual_result, gate


class P1P2IntelligenceTests(unittest.TestCase):
    def test_all_unrelated_briefs_reach_p2_gate(self):
        for case in CASES:
            with self.subTest(case=case["id"]):
                provider, s, sr, vr, gate = run_case(case)
                self.assertEqual("PASS", gate["status"])
                self.assertIn("film_thesis", s.state["decisions"])
                self.assertIn("visual_concept", s.state["decisions"])
                self.assertFalse(s.state["creative_locked"])

    def test_p2_does_not_falsely_claim_final_creative_lock(self):
        _, s, _, _, gate = run_case(CASES[0])
        self.assertEqual("PASS", gate["status"])
        with self.assertRaises(CreativeLockError):
            s.creative_lock()  # Art Direction + storyboard are intentionally not implemented yet.

    def test_story_changes_audience_state_and_uses_evidence(self):
        for case in CASES:
            _, _, sr, _, _ = run_case(case)
            thesis = sr["story"]["film_thesis"]
            self.assertNotEqual(thesis["audience_before"], thesis["audience_after"])
            evidence_ids = {x["claim_id"] for x in case["evidence"]}
            for beat in sr["story"]["beats"]:
                self.assertTrue(set(beat["required_claim_ids"]).issubset(evidence_ids))

    def test_visual_sets_are_meaningfully_diverse(self):
        for case in CASES:
            _, _, _, vr, _ = run_case(case)
            self.assertTrue(vr["diversity"]["meaningfully_diverse"])
            self.assertGreaterEqual(vr["diversity"]["distinct_strategy_count"], 3)

    def test_generic_first_candidate_is_rejected_every_time(self):
        for case in CASES:
            _, _, _, vr, _ = run_case(case)
            first = vr["reviews"][0]
            self.assertNotEqual("ACCEPT", first["review"]["verdict"])
            codes = {i.get("code") for i in first["review"]["issues"] if isinstance(i, dict)}
            self.assertTrue("GENERIC_VISUAL_GRAMMAR" in codes or "WEAK_HERO" in codes or "WEAK_TRANSFORMATION" in codes)

    def test_showrunner_selection_is_not_the_first_legal_idea(self):
        for case in CASES:
            _, s, _, vr, _ = run_case(case)
            chosen = s.state["decisions"]["visual_concept"]["proposal_id"]
            self.assertNotEqual(vr["reviews"][0]["candidate"]["candidate_id"], chosen)
            self.assertEqual("ACCEPT", next(x for x in vr["reviews"] if x["candidate"]["candidate_id"]==chosen)["review"]["verdict"])

    def test_direct_commit_to_governed_slot_is_blocked(self):
        case = CASES[0]
        _, s, council = make_stack(case)
        sr = council.develop_story(case["evidence"])
        # Story is already committed through reviewed path. Try a fresh raw proposal.
        ref = s.submit_proposal("VisualConceptDirector", "raw", {
            "representation":"DIAGRAM","visual_thesis":"raw","hero_kind":"thing","transformation":"changes materially","camera_idea":"hold"
        })
        with self.assertRaises(AuthorityViolation):
            s.commit_decision("visual_concept", ref)

    def test_rejected_candidate_cannot_commit_even_with_real_review_token(self):
        case = CASES[0]
        _, s, council = make_stack(case)
        sr = council.develop_story(case["evidence"])
        vr = council.develop_visual_candidates(sr["story"])
        rejected = vr["reviews"][0]
        with self.assertRaises(ProducerGateError):
            s.commit_reviewed_decision("visual_concept", rejected["proposal"], rejected["review_id"], require_diversity_from=[x["candidate"]["candidate_id"] for x in vr["reviews"]])

    def test_review_token_cannot_be_reused_for_another_candidate(self):
        case = CASES[0]
        _, s, council = make_stack(case)
        sr = council.develop_story(case["evidence"])
        vr = council.develop_visual_candidates(sr["story"])
        accepted_a = vr["reviews"][1]
        accepted_b = vr["reviews"][2]
        with self.assertRaises(ProducerGateError):
            s.commit_reviewed_decision("visual_concept", accepted_b["proposal"], accepted_a["review_id"], require_diversity_from=[x["candidate"]["candidate_id"] for x in vr["reviews"]])

    def test_candidate_tamper_after_review_is_detected(self):
        case = CASES[0]
        _, s, council = make_stack(case)
        sr = council.develop_story(case["evidence"])
        vr = council.develop_visual_candidates(sr["story"])
        accepted = vr["reviews"][1]
        s.state["proposals"]["VisualConceptDirector"][accepted["proposal"].proposal_id]["payload"]["visual_thesis"] = "tampered"
        with self.assertRaises(ProducerGateError):
            s.commit_reviewed_decision("visual_concept", accepted["proposal"], accepted["review_id"], require_diversity_from=[x["candidate"]["candidate_id"] for x in vr["reviews"]])

    def test_stale_producer_review_cannot_commit_after_replan(self):
        case = CASES[0]
        _, s, council = make_stack(case)
        sr = council.develop_story(case["evidence"])
        vr = council.develop_visual_candidates(sr["story"])
        accepted = vr["reviews"][1]
        s.replan("new evidence changes visual strategy", invalidate_slots=[])
        with self.assertRaises((ProducerGateError, CandidateError)):
            s.commit_reviewed_decision("visual_concept", accepted["proposal"], accepted["review_id"])

    def test_story_hallucinated_evidence_is_rejected(self):
        case = CASES[0]
        bad = copy.deepcopy(RESPONSES)
        bad[f"{case['id']}::story::0"]["beats"][0]["required_claim_ids"] = ["DOES-NOT-EXIST"]
        _, _, council = make_stack(case, bad)
        with self.assertRaises(ContractViolation):
            council.develop_story(case["evidence"])

    def test_story_geometry_leak_is_rejected(self):
        case = CASES[0]
        bad = copy.deepcopy(RESPONSES)
        bad[f"{case['id']}::story::0"]["film_thesis"]["x"] = 100
        _, _, council = make_stack(case, bad)
        with self.assertRaises(ContractViolation):
            council.develop_story(case["evidence"])

    def test_visual_geometry_leak_is_rejected(self):
        case = CASES[0]
        bad = copy.deepcopy(RESPONSES)
        bad[f"{case['id']}::visual::0"]["candidates"][1]["beat_treatments"][0]["width"] = 900
        _, _, council = make_stack(case, bad)
        sr = council.develop_story(case["evidence"])
        with self.assertRaises(ContractViolation):
            council.develop_visual_candidates(sr["story"])

    def test_model_authority_injection_is_rejected(self):
        case = CASES[0]
        bad = copy.deepcopy(RESPONSES)
        bad[f"{case['id']}::visual::0"]["candidates"][1]["commit"] = True
        _, _, council = make_stack(case, bad)
        sr = council.develop_story(case["evidence"])
        with self.assertRaises(ContractViolation):
            council.develop_visual_candidates(sr["story"])

    def test_renderer_code_leak_is_rejected(self):
        case = CASES[0]
        bad = copy.deepcopy(RESPONSES)
        bad[f"{case['id']}::visual::0"]["candidates"][1]["rationale"] = "<svg><path d='x'/></svg>"
        _, _, council = make_stack(case, bad)
        sr = council.develop_story(case["evidence"])
        with self.assertRaises(ContractViolation):
            council.develop_visual_candidates(sr["story"])

    def test_producer_authority_injection_is_rejected(self):
        payload = {
            "verdict":"ACCEPT","issues":[],"strengths":["x"],"revision_brief":"","commercial_confidence":"HIGH","creative_lock":True
        }
        with self.assertRaises(ContractViolation):
            validate_producer_output(payload)

    def test_production_source_contains_no_fixture_topics_or_ids(self):
        source_text = "\n".join(p.read_text(encoding="utf-8") for p in (SRC / "nexmind_god_mode").glob("*.py"))
        for case in CASES:
            self.assertNotIn(case["id"], source_text)
            topic = case["brief"]["topic"]
            self.assertNotIn(topic, source_text)

    def test_recorded_provider_is_explicitly_not_live_inference(self):
        text = (SRC / "nexmind_god_mode" / "provider.py").read_text(encoding="utf-8")
        self.assertIn("NOT described as live-provider inference", text)

    def test_p0_kernel_is_byte_identical_to_frozen_base_copy(self):
        a = (SRC / "nexmind_god_mode" / "p0_kernel.py").read_bytes()
        b = (ROOT / "p0_base" / "nexmind_supreme_showrunner.py").read_bytes()
        self.assertEqual(hashlib.sha256(a).hexdigest(), hashlib.sha256(b).hexdigest())

    def test_checkpoint_resume_preserves_p2_state(self):
        _, s, _, _, _ = run_case(CASES[0])
        with tempfile.TemporaryDirectory() as td:
            p = s.checkpoint(Path(td)/"cp.json")
            resumed = NexMindSupremeShowrunnerP2.resume(p)
            self.assertEqual("PASS", resumed.state["p2_intelligence_gate"]["status"])
            self.assertEqual(s.state["decisions"]["visual_concept"]["proposal_id"], resumed.state["decisions"]["visual_concept"]["proposal_id"])

    def test_provider_call_order_is_auditable(self):
        provider, _, _, _, _ = run_case(CASES[0])
        tasks = [c.task for c in provider.calls]
        self.assertEqual(["story", "producer", "visual", "producer", "producer", "producer", "showrunner_select"], tasks)
        self.assertTrue(all(len(c.request_hash) == 64 for c in provider.calls))

    def test_no_cross_case_exact_film_thesis_reuse(self):
        theses=[]
        for case in CASES:
            _, _, sr, _, _ = run_case(case)
            theses.append(sr["story"]["film_thesis"]["central_argument"])
        self.assertEqual(len(theses), len(set(theses)))

    def test_all_visuals_rejected_forces_real_replan_and_new_candidates(self):
        case = CASES[0]
        custom = copy.deepcopy(RESPONSES)
        pid = case["id"]
        # Make first-round candidates mechanically generic and Producer-rejected.
        first = custom[f"{pid}::visual::0"]
        for i, c in enumerate(first["candidates"], 1):
            c["candidate_id"] = f"R1-V{i}"
            c["hero_kind"] = "box"
            c["visual_thesis"] = "A grid of cards and boxes connected left to right."
            c["transformation"] = "reveal"
            for bt in c["beat_treatments"]:
                bt["visual_action"] = "Reveal another box in the same generic layout"
        for n in (1,2,3):
            custom[f"{pid}::producer::{n}"] = {
                "verdict":"REVISE","issues":[{"code":"CONCEPT_FAMILY_REJECTED","detail":"No candidate establishes a compelling hero or transformation."}],
                "strengths":[],"revision_brief":"Abandon the diagram family and originate a new hero-led visual strategy.","commercial_confidence":"LOW"
            }
        # Second visual generation is genuinely new and gets new IDs/reviews.
        revised = copy.deepcopy(RESPONSES[f"{pid}::visual::0"])
        for i, c in enumerate(revised["candidates"], 1):
            c["candidate_id"] = f"R2-V{i}"
        custom[f"{pid}::visual::1"] = revised
        custom[f"{pid}::producer::4"] = {"verdict":"REVISE","issues":[{"code":"GENERIC_ALT","detail":"Still too diagrammatic."}],"strengths":[],"revision_brief":"Use the stronger hero-led option.","commercial_confidence":"LOW"}
        custom[f"{pid}::producer::5"] = {"verdict":"ACCEPT","issues":[],"strengths":["Persistent hero","Causal transformation","Clear payoff"],"revision_brief":"","commercial_confidence":"HIGH"}
        custom[f"{pid}::producer::6"] = {"verdict":"ACCEPT","issues":[],"strengths":["Distinct alternative"],"revision_brief":"","commercial_confidence":"MEDIUM"}
        custom[f"{pid}::showrunner_select::0"] = {
            "selected_candidate_id":"R2-V2",
            "why":"The revised second option is the first concept with a persistent hero, causal transformation and clear payoff.",
            "tradeoffs":["Higher art burden."],
            "rejected_alternatives":[{"candidate_id":"R2-V1","reason":"Still too generic."},{"candidate_id":"R2-V3","reason":"More metaphorical than necessary."}]
        }

        provider, s, council = make_stack(case, custom)
        sr = council.develop_story(case["evidence"])
        round1 = council.develop_visual_candidates(sr["story"])
        self.assertTrue(all(x["review"]["verdict"] != "ACCEPT" for x in round1["reviews"]))
        with self.assertRaises(ProducerGateError):
            council.choose_visual(round1, "R1-V2")
        old_revision = s.state["revision"]
        s.replan("Executive Producer rejected the entire visual concept family", invalidate_slots=["visual_concept"])
        self.assertEqual(old_revision + 1, s.state["revision"])
        round2 = council.develop_visual_candidates(sr["story"])
        self.assertEqual({"R2-V1","R2-V2","R2-V3"}, {x["candidate"]["candidate_id"] for x in round2["reviews"]})
        chosen = council.showrunner_select_visual(sr["story"], round2)
        self.assertEqual("R2-V2", chosen["selection"]["selected_candidate_id"])
        self.assertEqual("PASS", s.p2_gate()["status"])
        self.assertEqual("R2-V2", s.state["decisions"]["visual_concept"]["proposal_id"])
        self.assertTrue(any(e["kind"] == "SHOWRUNNER_REPLAN" for e in s.state["history"]))

    def test_no_cross_case_exact_selected_visual_strategy_reuse(self):
        strategies=[]
        for case in CASES:
            _, s, _, _, _ = run_case(case)
            p=s.state["decisions"]["visual_concept"]["payload"]
            strategies.append((p["representation"],p["visual_thesis"],p["hero_kind"],p["transformation"],p["camera_idea"]))
        self.assertEqual(len(strategies), len(set(strategies)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
