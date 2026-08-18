import unittest

from nexmind_god_mode.final_producer_contracts import HUMAN_REVIEW_DIMENSIONS, TASTE_DIMENSIONS
from nexmind_god_mode.human_calibration import HumanCalibrationRegistry
from nexmind_god_mode.p0_kernel import AuthorityViolation
from nexmind_god_mode.showrunner_p8 import NexMindSupremeShowrunnerP8
from nexmind_god_mode.studio_quality import studio_autonomous_quality_gate, build_repair_request
from nexmind_god_mode.story_director import StoryDirector
from nexmind_god_mode.executive_producer import ExecutiveProducer
from nexmind_god_mode.showrunner_reasoner import ShowrunnerDecisionIntelligence
from nexmind_god_mode.council import CreativeCouncil


def scored(score=9.4, confidence="HIGH"):
    return {"score": score, "confidence": confidence, "rationale": "test evidence"}


def machine_review(score=9.7, verdict="ACCEPT", human_required=False):
    return {
        "verdict": verdict,
        "hard_gates": [{"dimension": d, "status": "PASS", "code": "PASS", "evidence": ["test"]} for d in (
            "EVIDENCE_TRUTH","DEPARTMENT_COMPLETENESS","STORY_COHERENCE","STRUCTURAL_VISUAL_INTENT","STRUCTURAL_ART_DIRECTION","STRUCTURAL_CINEMATOGRAPHY_DIRECTION","STRUCTURAL_EDITORIAL_DIRECTION","STRUCTURAL_MOTION_EXECUTABILITY","STRUCTURAL_SOUND_RIGHTS_AND_FUNCTION","FINAL_PAYOFF","TECHNICAL_BODY_VETOES"
        )],
        "craft_scores": {k: scored(score) for k in ("story_clarity","visual_communication","art_craft","visual_hierarchy","cinematography","editorial_rhythm","motion_intentionality","sound_design","final_payoff","commercial_finish")},
        "taste_judgments": {k: scored(score) for k in TASTE_DIMENSIONS},
        "divergence": {"novelty": 8.2, "conceptual_risk": 5.0, "template_similarity": 2.0, "rationale": "distinct"},
        "uncertainty": {"confidence": "HIGH", "reasons": [], "human_review_required": human_required, "multimodal_evidence_complete": True},
        "strengths": ["strong"], "issues": [] if verdict == "ACCEPT" else ["needs work"], "revision_plan": [] if verdict == "ACCEPT" else ["repair"],
        "commercial_recommendation": "RENDER_FOR_INTERNAL_REVIEW" if verdict == "ACCEPT" else "DO_NOT_RENDER",
    }


def human_review(score, reviewer_id="blind-reviewer"):
    return {
        "reviewer_id": reviewer_id,
        "reviewer_provenance": "independent-panel",
        "blind": True,
        "independent": True,
        "scores": {d: score for d in HUMAN_REVIEW_DIMENSIONS},
        "hard_rejects": [],
        "notes": "blind review",
    }


class StoryCompetitionProvider:
    def __init__(self):
        self.story_lenses=[]
    def complete(self, task, request):
        if task == "story":
            self.story_lenses.append(request.get("instruction",{}).get("strategy_lens"))
            idx=len(self.story_lenses); lens=f"brief-specific-route-{idx}"
            return {
                "film_thesis": {
                    "central_argument": f"Argument strategy {idx} changes the viewer through {lens}",
                    "film_kind": "commercial explainer",
                    "hero_kind": f"persistent causal hero {idx}",
                    "camera_idea": f"follow causal hero strategy {idx}",
                    "audience_before": "uncertain",
                    "audience_after": f"understands route {idx}",
                    "emotional_trajectory": ["curious", "convinced"],
                    "visual_trajectory": [f"state-{idx}-a", f"state-{idx}-b"],
                    "opening_contract": f"Open question {idx}",
                    "final_payoff": f"Resolve consequence {idx} with clarity",
                    "anti_goals": ["generic list"],
                },
                "beats": [
                    {"beat_id":"B1","purpose":"setup","question":"why","audience_before":"uncertain","audience_after":f"curious {idx}","hero_state":f"hero setup {idx}","reveal":f"evidence route {idx}","required_claim_ids":[]},
                    {"beat_id":"B2","purpose":"payoff","question":"so what","audience_before":f"curious {idx}","audience_after":f"understands route {idx}","hero_state":f"hero payoff {idx}","reveal":f"payoff route {idx}","required_claim_ids":[]},
                ],
            }
        if task == "producer":
            return {"verdict":"ACCEPT","issues":[],"strengths":["clear"],"revision_brief":"","commercial_confidence":"HIGH"}
        if task == "showrunner_select":
            candidates=request["candidates"]
            selected=candidates[1]["candidate"]["candidate_id"]
            rejected=[{"candidate_id":x["candidate"]["candidate_id"],"reason":"tradeoff"} for i,x in enumerate(candidates) if i!=1]
            return {"selected_candidate_id":selected,"why":"Best audience-state progression for this brief.","tradeoffs":["less literal"],"rejected_alternatives":rejected}
        raise AssertionError(task)


class AutonomousAuthorityTests(unittest.TestCase):
    def calibrated_registry(self, family="EXPLAINER"):
        build="b"*64; judges="j"*64
        reg = HumanCalibrationRegistry(target_family=family,p8_build_hash=build,judge_ensemble_hash=judges)
        for i in range(48):
            score = 9.55 + i * 0.007
            reg.add(f"prod-{i//2}", machine_review(score), human_review(score, f"reviewer-{i%6}"), family=family, evidence_hash=f"e-{i}",p8_build_hash=build,judge_ensemble_hash=judges)
        return reg


    def test_story_simple_brief_competes_two_distinct_narrative_strategies_before_commit(self):
        provider=StoryCompetitionProvider()
        sr=NexMindSupremeShowrunnerP8("p-story",{"goal":"explain a new product"})
        council=CreativeCouncil(sr,StoryDirector(provider),None,ExecutiveProducer(provider),ShowrunnerDecisionIntelligence(provider))
        result=council.develop_story_competition([])
        self.assertEqual(len(provider.story_lenses),2)
        self.assertEqual(provider.story_lenses[0],'INVENT_A_BRIEF_SPECIFIC_NARRATIVE_STRATEGY')
        self.assertTrue(all(x not in {'DIRECT_CAUSAL_REVEAL','EMBODIED_TRANSFORMATION','CONTRAST_AND_PAYOFF'} for x in provider.story_lenses))
        self.assertTrue(any('prior' in str(x).lower() or 'different' in str(x).lower() for x in provider.story_lenses[1:]))
        self.assertEqual(result["diversity"]["candidate_count"],2)
        self.assertGreaterEqual(result["diversity"]["distinct_strategy_count"],2)
        self.assertTrue(result["diversity"]["meaningfully_diverse"])
        self.assertEqual(sr.state["decisions"]["film_thesis"]["department"],"StoryDirector")

    def test_autonomy_requires_strong_studio_calibration(self):
        weak = HumanCalibrationRegistry().status()
        q = studio_autonomous_quality_gate(machine_review(), calibration=weak, multimodal_evidence={"status":"COMPLETE","perceptually_reviewed":True})
        self.assertEqual(q["status"], "HUMAN_CALIBRATION_REQUIRED")
        strong = self.calibrated_registry().status()
        self.assertEqual(strong["status"], "CALIBRATED")
        q2 = studio_autonomous_quality_gate(machine_review(), calibration=strong, multimodal_evidence={"status":"COMPLETE","perceptually_reviewed":True})
        self.assertEqual(q2["status"], "PASS")

    def test_one_weak_dimension_cannot_be_laundered_by_average(self):
        strong = self.calibrated_registry().status()
        review = machine_review()
        review["craft_scores"]["art_craft"] = scored(8.4)
        q = studio_autonomous_quality_gate(review, calibration=strong, multimodal_evidence={"status":"COMPLETE","perceptually_reviewed":True})
        self.assertEqual(q["status"], "REPAIR")
        self.assertIn("art_craft", q["craft_below_9"])

    def test_machine_uncertainty_routes_exceptional_human_even_when_calibrated(self):
        strong = self.calibrated_registry().status()
        review = machine_review(verdict="ESCALATE_HUMAN", human_required=True)
        review["issues"] = ["ambiguous taste call"]
        review["revision_plan"] = ["independent judgment"]
        review["commercial_recommendation"] = "HUMAN_REVIEW_REQUIRED"
        q = studio_autonomous_quality_gate(review, calibration=strong, multimodal_evidence={"status":"COMPLETE","perceptually_reviewed":True})
        self.assertEqual(q["status"], "REPAIR")  # issue-bearing uncertainty is never silently accepted

    def test_pure_calibrated_uncertainty_routes_exceptional_human_judgment(self):
        strong = self.calibrated_registry().status()
        review = machine_review(verdict="ESCALATE_HUMAN", human_required=True)
        review["issues"] = ["two equally viable contextual interpretations"]
        review["revision_plan"] = []
        review["commercial_recommendation"] = "HUMAN_REVIEW_REQUIRED"
        q = studio_autonomous_quality_gate(review, calibration=strong, multimodal_evidence={"status":"COMPLETE","perceptually_reviewed":True})
        self.assertEqual(q["status"], "HUMAN_JUDGMENT_REQUIRED")

    def test_synthetic_reviews_never_unlock_autonomy(self):
        reg = HumanCalibrationRegistry(target_family="EXPLAINER",p8_build_hash="b"*64,judge_ensemble_hash="j"*64)
        for i in range(60):
            reg.add(f"synthetic-{i}", machine_review(9.4), human_review(9.4), synthetic=True, family="EXPLAINER", evidence_hash=f"s-{i}",p8_build_hash="b"*64,judge_ensemble_hash="j"*64)
        status = reg.status()
        self.assertEqual(status["status"], "INSUFFICIENT_HUMAN_CALIBRATION")
        self.assertEqual(status["human_reviews"], 0)

    def test_calibration_is_scoped_to_exact_family_build_and_judges(self):
        build="b"*64; judges="j"*64
        reg=HumanCalibrationRegistry(target_family="EXPLAINER",p8_build_hash=build,judge_ensemble_hash=judges)
        for i in range(40):
            score=9.2+(i%10)*0.06
            reg.add(f"other-{i}",machine_review(score),human_review(score,f"r-{i%6}"),family="WHITEBOARD",evidence_hash=f"e-{i}",p8_build_hash=build,judge_ensemble_hash=judges)
        status=reg.status()
        self.assertEqual(status["status"],"INSUFFICIENT_HUMAN_CALIBRATION")
        self.assertIn("FEWER_THAN_12_EXACT_BUILD_JUDGE_FAMILY_REVIEWS",status["reasons"])

    def test_machine_false_accept_blocks_calibration(self):
        reg = self.calibrated_registry()
        bad_human = human_review(7.5)
        reg.add("bad-human-prod", machine_review(9.6), bad_human, family="EXPLAINER", evidence_hash="bad",p8_build_hash="b"*64,judge_ensemble_hash="j"*64)
        status = reg.status()
        self.assertEqual(status["status"], "CALIBRATION_WEAK")
        self.assertGreater(status["machine_false_accepts"], 0)
        self.assertIn("MACHINE_FALSE_ACCEPT_PRESENT", status["reasons"])

    def test_repair_scope_escalates_without_terminal_creative_exhaustion(self):
        q={"reasons":["CRAFT_DIMENSION_BELOW_9"],"hard_gate_failures":[]}
        review={"issues":["art weak"],"revision_plan":["rebuild art"],"department_revisions":[{"owner_department":"ART_DIRECTION","issue_code":"ART_WEAK","required_change":"rebuild art","preserve":[],"priority":"HIGH"}]}
        r1=build_repair_request(review,q,round_number=1)
        r2=build_repair_request(review,q,round_number=2)
        r3=build_repair_request(review,q,round_number=3)
        r4=build_repair_request(review,q,round_number=4)
        self.assertEqual([r1["escalation_scope"],r2["escalation_scope"],r3["escalation_scope"],r4["escalation_scope"]],["RESPONSIBLE_DEPARTMENT","UPSTREAM_VISUAL_STRATEGY","WHOLE_FILM_CREATIVE_STRATEGY","BEST_VIABLE_PREMIUM_STRATEGY"])
        self.assertTrue(all(r["exhausted"] is False for r in (r1,r2,r3,r4)))
        self.assertTrue(all(r["quality_floor_may_weaken"] is False for r in (r1,r2,r3,r4)))
        self.assertTrue(all(r["silent_generic_fallback_allowed"] is False for r in (r1,r2,r3,r4)))

    def test_director_slot_boundary_is_enforced(self):
        sr=NexMindSupremeShowrunnerP8("p",{"goal":"x"})
        ref=sr.submit_proposal("VisualConceptDirector","v",{"representation":"x","visual_thesis":"x","hero_kind":"x","transformation":"x","camera_idea":"x"})
        with self.assertRaises(AuthorityViolation):
            sr.commit_decision("film_thesis",ref)

    def test_only_promoted_memory_enters_live_state(self):
        sr=NexMindSupremeShowrunnerP8("p",{"goal":"x"})
        sr.set_creative_memory_refs([
            {"memory_id":"m1","status":"OBSERVED","provenance":"x"},
            {"memory_id":"m2","status":"PROMOTED","provenance":"human-calibrated"},
            {"memory_id":"m3","status":"PROMOTED"},
        ])
        self.assertEqual([x["memory_id"] for x in sr.state["creative_memory_refs"]],["m2"])


if __name__ == "__main__": unittest.main()
