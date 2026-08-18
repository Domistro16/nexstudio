from __future__ import annotations

import copy, json, os, sys, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))

from nexmind_god_mode import (
    IllustrationFormResolver, StoryboardCompiler, StoryboardGateError,
    validate_art_output, NexMindSupremeShowrunnerP3, CreativeCouncilP3,
    ArtDirector, P3ExecutiveProducer, ArtShowrunnerDecisionIntelligence,
)
from nexmind_god_mode.contracts import ContractViolation
from nexmind_god_mode.p0_kernel import AuthorityViolation, CreativeLockError
from nexmind_god_mode.showrunner_p2 import ProducerGateError
from nexmind_god_mode.provider import ProviderError

INDEX=ROOT/'donors'/'NEXSTUDIO_ILLUSTRATION_CAPABILITY_INDEX_V1.json'


def story():
    return {
        "film_thesis":{
            "central_argument":"A computer is useful because one persistent device transforms input into output through coordinated internal parts.",
            "film_kind":"causal explainer",
            "audience_before":"A laptop feels like one opaque box.",
            "audience_after":"The audience can trace input through processor and memory to output.",
            "emotional_trajectory":["familiar","curious","oriented"],
            "visual_trajectory":["whole laptop","cutaway internals","whole system payoff"],
            "opening_contract":"Start with one familiar laptop.",
            "final_payoff":"Return to the same laptop now understood as a coordinated system.",
            "anti_goals":["no card grid","no connector soup"],
        },
        "beats":[
            {"beat_id":"B1","purpose":"setup","question":"Where does the work happen?","audience_before":"Sees laptop shell","audience_after":"Expects hidden internals","reveal":"Open the same laptop into a cutaway","required_claim_ids":["C1"]},
            {"beat_id":"B2","purpose":"mechanism","question":"How does input become output?","audience_before":"Knows internals exist","audience_after":"Can trace processor/memory/output relationship","reveal":"Follow one data task through internals to screen","required_claim_ids":["C1"]},
            {"beat_id":"B3","purpose":"synthesis","question":"What is the whole machine doing?","audience_before":"Knows component steps","audience_after":"Sees one coordinated system","reveal":"Return to whole laptop with the internal relationship retained mentally","required_claim_ids":["C1"]},
        ]
    }


def visual():
    return {
        "candidate_id":"V-COMPUTER-1",
        "representation":"AUTHORED_ILLUSTRATION",
        "visual_thesis":"One persistent laptop opens, performs the task internally, then returns whole.",
        "hero_kind":"recognizable laptop hero",
        "transformation":"opaque familiar object becomes an intelligible working system",
        "camera_idea":"Hold the laptop as anchor; one motivated push into internals; return to whole.",
        "rationale":"Preserves identity and avoids replacing the hero with a diagram.",
        "beat_treatments":[
            {"beat_id":"B1","hero_state":"closed laptop","visual_action":"open a semantic cutaway without replacing the laptop","audience_takeaway":"the work is inside this same object"},
            {"beat_id":"B2","hero_state":"laptop cutaway","visual_action":"trace one task through processor and memory into output","audience_takeaway":"components cooperate causally"},
            {"beat_id":"B3","hero_state":"whole laptop with understood internals","visual_action":"settle back to the recognizable whole","audience_takeaway":"the laptop is one coordinated system"},
        ]
    }


def art_candidate(cid, archetype, settled_suffix=""):
    modes={
        "cutaway":("monumental cutaway reveal","one dominant laptop shell opens as a sectional monument","reserve a quiet vertical annotation trench","heavy exterior mass against a luminous internal core","processor chamber and routed data path","labels engraved into the cutaway edge"),
        "cutaway-monument":("monumental cutaway reveal","one dominant laptop shell opens as a sectional monument","reserve a quiet vertical annotation trench","heavy exterior mass against a luminous internal core","processor chamber and routed data path","labels engraved into the cutaway edge"),
        "macro":("macro-detail continuity","the laptop remains whole while one magnified internal window carries the explanation","reserve negative space around the magnified inspection window","small precise macro field counterweights the whole-device silhouette","magnified processor detail linked back to whole device","micro labels live only inside the inspection window"),
        "hero-and-macro-inset":("macro-detail continuity","the laptop remains whole while one magnified internal window carries the explanation","reserve negative space around the magnified inspection window","small precise macro field counterweights the whole-device silhouette","magnified processor detail linked back to whole device","micro labels live only inside the inspection window"),
        "depth":("layered depth journey","foreground keyboard, midground processor and background display create one traversable spatial system","preserve a diagonal breathing corridor through the depth layers","near keyboard plane drives toward a distant output plane","layered components connected by spatial depth rather than boxes","labels sit on depth planes and recede with the world"),
        "split-depth-object":("layered depth journey","foreground keyboard, midground processor and background display create one traversable spatial system","preserve a diagonal breathing corridor through the depth layers","near keyboard plane drives toward a distant output plane","layered components connected by spatial depth rather than boxes","labels sit on depth planes and recede with the world"),
    }
    thesis,scene,negative,asym,form,typography=modes.get(archetype,(f"brief-specific {archetype}",f"distinct {archetype} visual system",f"negative space specific to {archetype}",f"asymmetry specific to {archetype}",f"form realization for {archetype}",f"typography integrated with {archetype}"))
    return {
        "candidate_id":cid,
        "visual_candidate_id":"V-COMPUTER-1",
        "art_thesis":f"{thesis}: keep the laptop unmistakable while revealing its causal interior.",
        "hero":{"semantic_ref":"computer.hero","art_budget":"HIGH","prominence":"DOMINANT","recognizable_required":True},
        "composition":{"archetype":archetype,"hierarchy_order":["computer.hero",form,"live type"],"negative_space_intent":negative,"density":"BALANCED","asymmetry_intent":asym,"support_budget":3,"decoration_budget":0},
        "form_request":{"concept":form,"representation":"AUTHORED_ILLUSTRATION","semantic_parts":["computer.hero",form,"computer.output"],"required_operations":[f"realize.{archetype}","trace_data","return_to_whole"],"style":f"brief-authored-{archetype}"},
        "beat_art":[
            {"beat_id":"B1","settled_visual_state":scene+"; the opening state exposes the hidden cause without replacing the recognizable device"+settled_suffix,"focal_owner":"computer.hero","supporting_roles":[f"{archetype} reveal"],"meaning_without_motion":True},
            {"beat_id":"B2","settled_visual_state":scene+"; the mechanism state makes one processor-to-output causal path legible in this specific art system"+settled_suffix,"focal_owner":"computer.hero","supporting_roles":[form,"screen output"],"meaning_without_motion":True},
            {"beat_id":"B3","settled_visual_state":scene+"; the payoff restores the whole laptop while preserving the learned internal relationship"+settled_suffix,"focal_owner":"computer.hero","supporting_roles":["resolved output"],"meaning_without_motion":True},
        ],
        "typography_intent":typography+"; typography never becomes a floating dashboard.",
        "risk_notes":[],
    }


class DynamicProvider:
    """Deterministic department simulator for control-layer tests only; not live inference."""
    def __init__(self): self.calls=[]
    def complete(self,task,request):
        self.calls.append((task,copy.deepcopy(request)))
        if task=="art":
            return {"candidates":[art_candidate("A1","cutaway-monument"),art_candidate("A2","hero-and-macro-inset"," variant-b"),art_candidate("A3","split-depth-object"," variant-c")]}
        if task in {"art_review","storyboard_review"}:
            if task=="art_review" and request.get("form_resolution",{}).get("status")=="UNSUPPORTED_FORM_REQUIRED":
                return {"verdict":"REVISE","issues":[{"code":"FORM_GAP","detail":"needs coherent hero"}],"strengths":[],"revision_brief":"Resolve the hero form or choose another valid representation.","commercial_confidence":"LOW"}
            return {"verdict":"ACCEPT","issues":[],"strengths":["strong settled-state hierarchy","clear hero"],"revision_brief":"","commercial_confidence":"HIGH"}
        if task=="showrunner_select_art":
            cs=request["candidates"]
            accepted=[x for x in cs if x["producer_review"]["verdict"]=="ACCEPT"]
            chosen=accepted[1] if len(accepted)>1 else accepted[0]
            return {"selected_candidate_id":chosen["candidate"]["candidate_id"],"why":"This option preserves the hero while giving the mechanism a distinct readable key state.","tradeoffs":["Slightly denser than the most minimal option"],"rejected_alternatives":[{"candidate_id":x["candidate"]["candidate_id"],"reason":"Weaker balance of hero identity and mechanism legibility"} for x in cs if x["candidate"]["candidate_id"]!=chosen["candidate"]["candidate_id"]]}
        raise ProviderError(task)


def seed_p2(sr:NexMindSupremeShowrunnerP3):
    s=story(); v=visual()
    sp=sr.submit_proposal("StoryDirector","story-r0",{"representation":"NARRATIVE_ARGUMENT","visual_thesis":s["film_thesis"]["central_argument"],"hero_kind":"audience-belief-change","transformation":"opaque -> understood","camera_idea":"none","story":s})
    review={"verdict":"ACCEPT","issues":[],"strengths":["clear thesis"],"revision_brief":"","commercial_confidence":"HIGH"}
    st=sr.register_producer_review("film_thesis",sp,review); sr.commit_reviewed_decision("film_thesis",sp,st)
    vp=sr.submit_proposal("VisualConceptDirector",v["candidate_id"],v)
    vt=sr.register_producer_review("visual_concept",vp,review); sr.commit_reviewed_decision("visual_concept",vp,vt)
    return s,v


class P3Tests(unittest.TestCase):
    def setUp(self): self.resolver=IllustrationFormResolver.from_file(INDEX)

    def test_existing_computer_form_resolves_from_phase3_bank(self):
        req=art_candidate("A","cutaway")["form_request"]
        r=self.resolver.resolve(req,{})
        self.assertEqual(r["status"],"RESOLVED_EXISTING")
        self.assertEqual(r["record"]["illustrationId"],"nexstudio.computer.laptop.v1")
        self.assertTrue(r["no_silent_degrade"])

    def test_unknown_recognizable_form_fails_closed_not_diagram(self):
        req={"concept":"deep sea hydrothermal vent shrimp anatomy","representation":"AUTHORED_ILLUSTRATION","semantic_parts":["shrimp.body","gill.chamber","vent.plume"],"required_operations":["open","highlight","trace_flow"],"style":"explainer"}
        r=self.resolver.resolve(req,{})
        self.assertEqual(r["status"],"UNSUPPORTED_FORM_REQUIRED")
        self.assertEqual(r["forbidden_fallback"],"DIAGRAM")

    def test_unknown_form_can_request_production_scoped_generation(self):
        req={"concept":"deep sea hydrothermal vent shrimp anatomy","representation":"AUTHORED_ILLUSTRATION","semantic_parts":["shrimp.body"],"required_operations":["highlight"],"style":"explainer"}
        r=self.resolver.resolve(req,{"production_scoped_asset_generation":True})
        self.assertEqual(r["status"],"GENERATION_REQUIRED")

    def test_nonillustration_route_does_not_fake_form(self):
        req={"concept":"quarterly revenue","representation":"TYPOGRAPHY_DATA","semantic_parts":["revenue"],"required_operations":[],"style":"explainer"}
        self.assertEqual(self.resolver.resolve(req,{})["status"],"NOT_APPLICABLE")


    def test_art_director_binds_visual_lineage_after_provider_inference(self):
        class WrongForeignKeyProvider:
            def complete(self,task,request):
                self.assert_task = task
                cs=[art_candidate("A1","cutaway"),art_candidate("A2","macro"),art_candidate("A3","depth")]
                for c in cs: c["visual_candidate_id"]="WRONG-INTERNAL-ID"
                return {"candidates":cs}
        out=ArtDirector(WrongForeignKeyProvider()).propose("P",{"topic":"computer"},story(),visual(),{}, {})
        self.assertEqual({x["visual_candidate_id"] for x in out},{visual()["candidate_id"]})

    def test_art_live_schema_does_not_delegate_visual_foreign_key_to_model(self):
        from nexmind_god_mode.provider_schemas import ART_SCHEMA
        item=ART_SCHEMA["properties"]["candidates"]["items"]
        self.assertNotIn("visual_candidate_id",item["required"])
        self.assertNotIn("visual_candidate_id",item["properties"])

    def test_recognizable_hero_gets_deterministic_high_art_budget_floor(self):
        class UnderBudgetProvider:
            def complete(self,task,request):
                cs=[art_candidate("A1","cutaway"),art_candidate("A2","macro"),art_candidate("A3","depth")]
                for c in cs:
                    c["hero"]["recognizable_required"]=True
                    c["hero"]["art_budget"]="LOW"
                return {"candidates":cs}
        out=ArtDirector(UnderBudgetProvider()).propose("P",{"topic":"computer"},story(),visual(),{}, {})
        self.assertEqual({x["hero"]["art_budget"] for x in out},{"HIGH"})

    def test_art_director_raises_support_budget_to_authored_role_count(self):
        class UnderDeclaredSupportProvider:
            def complete(self,task,request):
                cs=[art_candidate("A1","cutaway"),art_candidate("A2","macro"),art_candidate("A3","depth")]
                for c in cs:
                    c["composition"]["support_budget"]=1
                return {"candidates":cs}
        out=ArtDirector(UnderDeclaredSupportProvider()).propose("P",{"topic":"computer"},story(),visual(),{}, {})
        self.assertEqual({x["composition"]["support_budget"] for x in out},{2})

    def test_art_director_does_not_mask_support_over_hard_maximum(self):
        class OverloadedSupportProvider:
            def complete(self,task,request):
                cs=[art_candidate("A1","cutaway"),art_candidate("A2","macro"),art_candidate("A3","depth")]
                for c in cs:
                    c["composition"]["support_budget"]=4
                    c["beat_art"][0]["supporting_roles"]=["r1","r2","r3","r4","r5"]
                return {"candidates":cs}
        out=ArtDirector(OverloadedSupportProvider()).propose("P",{"topic":"computer"},story(),visual(),{}, {})
        self.assertEqual({x["composition"]["support_budget"] for x in out},{5})
        self.assertTrue(all(len(x["beat_art"][0]["supporting_roles"])==5 for x in out))

    def test_art_contract_requires_three_material_candidates(self):
        out={"candidates":[art_candidate("A1","cutaway"),art_candidate("A2","macro"),art_candidate("A3","depth") ]}
        self.assertEqual(len(validate_art_output(out,{"B1","B2","B3"},"V-COMPUTER-1")),3)

    def test_art_rejects_coordinate_leak(self):
        c=art_candidate("A1","cutaway"); c["composition"]["x"]=10
        with self.assertRaises(ContractViolation): validate_art_output({"candidates":[c,art_candidate("A2","macro"),art_candidate("A3","depth")]},{"B1","B2","B3"},"V-COMPUTER-1")

    def test_art_support_provisioning_is_not_a_house_creative_ceiling(self):
        c=art_candidate("A1","cutaway"); c["composition"]["support_budget"]=5
        out=validate_art_output({"candidates":[c,art_candidate("A2","macro"),art_candidate("A3","depth")]},{"B1","B2","B3"},"V-COMPUTER-1")
        self.assertEqual(out[0]["composition"]["support_budget"],5)

    def test_art_rejects_settled_state_that_needs_motion_to_make_sense(self):
        c=art_candidate("A1","cutaway"); c["beat_art"][1]["meaning_without_motion"]=False
        with self.assertRaisesRegex(ContractViolation,"settled key state"):
            validate_art_output({"candidates":[c,art_candidate("A2","macro"),art_candidate("A3","depth")]},{"B1","B2","B3"},"V-COMPUTER-1")

    def test_storyboard_compiles_required_rehearsal_states(self):
        a=art_candidate("A1","cutaway"); fr=self.resolver.resolve(a["form_request"],{})
        board=StoryboardCompiler().compile(story(),visual(),a,fr)
        self.assertEqual(len(board["beats"]),3)
        for b in board["beats"]:
            for k in ["opening_state","hero_key_state","critical_action_states","settled_state","scene_thesis","audience_state_change","hero_identity","continuity_in","continuity_out","motion_intent"]:
                self.assertIn(k,b)

    def test_storyboard_gate_passes_strong_settled_states(self):
        a=art_candidate("A1","cutaway"); fr=self.resolver.resolve(a["form_request"],{})
        board=StoryboardCompiler().compile(story(),visual(),a,fr)
        self.assertEqual(StoryboardCompiler().gate(board)["status"],"PASS")

    def test_storyboard_gate_blocks_form_gap(self):
        a=art_candidate("A1","cutaway")
        fr={"status":"UNSUPPORTED_FORM_REQUIRED","concept":"unknown"}
        board=StoryboardCompiler().compile(story(),visual(),a,fr)
        with self.assertRaises(StoryboardGateError): StoryboardCompiler().gate(board)

    def test_storyboard_gate_blocks_generic_card_grid(self):
        a=art_candidate("A1","cutaway"); a["beat_art"][0]["settled_visual_state"]="A grid of cards explains the system"
        fr=self.resolver.resolve(a["form_request"],{})
        board=StoryboardCompiler().compile(story(),visual(),a,fr)
        with self.assertRaises(StoryboardGateError): StoryboardCompiler().gate(board)

    def test_p3_direct_art_commit_is_blocked(self):
        sr=NexMindSupremeShowrunnerP3("P",{"topic":"computer"}); seed_p2(sr)
        ref=sr.submit_proposal("ArtDirector","A",{"representation":"AUTHORED_ILLUSTRATION","visual_thesis":"x","hero_kind":"computer","transformation":"closed to open","camera_idea":"hold"})
        with self.assertRaises(AuthorityViolation): sr.commit_decision("art_direction",ref)

    def test_p3_review_token_binds_payload(self):
        sr=NexMindSupremeShowrunnerP3("P",{"topic":"computer"}); seed_p2(sr)
        ref=sr.submit_proposal("ArtDirector","A",{"representation":"AUTHORED_ILLUSTRATION","visual_thesis":"x","hero_kind":"computer","transformation":"closed to open","camera_idea":"hold"})
        review={"verdict":"ACCEPT","issues":[],"strengths":[],"revision_brief":"","commercial_confidence":"HIGH"}
        token=sr.register_p3_review("art_direction",ref,review)
        sr.state["proposals"]["ArtDirector"]["A"]["payload"]["visual_thesis"]="tampered"
        with self.assertRaisesRegex(ProducerGateError,"tampered"): sr.commit_p3_reviewed("art_direction",ref,token)

    def test_p3_rejected_art_cannot_commit(self):
        sr=NexMindSupremeShowrunnerP3("P",{"topic":"computer"}); seed_p2(sr)
        ref=sr.submit_proposal("ArtDirector","A",{"representation":"AUTHORED_ILLUSTRATION","visual_thesis":"x","hero_kind":"computer","transformation":"closed to open","camera_idea":"hold"})
        review={"verdict":"REVISE","issues":[],"strengths":[],"revision_brief":"fix","commercial_confidence":"LOW"}
        token=sr.register_p3_review("art_direction",ref,review)
        with self.assertRaisesRegex(ProducerGateError,"not Producer accepted"): sr.commit_p3_reviewed("art_direction",ref,token)

    def test_full_p3_council_art_and_storyboard_reaches_p3_gate(self):
        provider=DynamicProvider(); sr=NexMindSupremeShowrunnerP3("P",{"topic":"How a computer processes input"}); s,v=seed_p2(sr)
        council=CreativeCouncilP3(sr,ArtDirector(provider),self.resolver,P3ExecutiveProducer(provider),ArtShowrunnerDecisionIntelligence(provider),StoryboardCompiler())
        art_result=council.develop_art(s,v)
        self.assertTrue(art_result["diversity"]["meaningfully_diverse"])
        selected=council.select_art(s,v,art_result)
        self.assertIn(selected["candidate"]["candidate_id"],{"A1","A2","A3"})
        board=council.compile_and_review_storyboard(s,v,selected)
        self.assertEqual(board["review"]["verdict"],"ACCEPT")
        self.assertEqual(sr.p3_ready_gate()["status"],"PASS")

    def test_p3_cannot_falsely_claim_final_creative_lock(self):
        provider=DynamicProvider(); sr=NexMindSupremeShowrunnerP3("P",{"topic":"How a computer processes input"}); s,v=seed_p2(sr)
        council=CreativeCouncilP3(sr,ArtDirector(provider),self.resolver,P3ExecutiveProducer(provider),ArtShowrunnerDecisionIntelligence(provider),StoryboardCompiler())
        ar=council.develop_art(s,v); selected=council.select_art(s,v,ar); council.compile_and_review_storyboard(s,v,selected); sr.p3_ready_gate()
        with self.assertRaisesRegex(ProducerGateError,"FINAL_CREATIVE_LOCK_BLOCKED_INCOMPLETE_BRAIN") as cm: sr.creative_lock()
        missing=cm.exception.args[0]["missing_decisions"]
        for slot in ["cinematography","editorial_rhythm","motion_performance","sound_direction","final_producer"]: self.assertIn(slot,missing)

    def test_production_source_contains_no_p3_test_topics(self):
        terms=["hydrothermal vent shrimp","computer processes input"]
        prod='\n'.join(p.read_text(encoding="utf-8", errors='ignore').lower() for p in (ROOT/'src').rglob('*.py'))
        for t in terms: self.assertNotIn(t,prod)

if __name__=='__main__': unittest.main(verbosity=2)
