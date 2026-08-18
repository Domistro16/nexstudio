from __future__ import annotations
from copy import deepcopy
from typing import Any, Dict, List
from .contracts import validate_producer_output
from .provider import CreativeModelProvider
from .executive_producer import ExecutiveProducer
from .review_governance import calibrate_review, release_decision_law

class P3ExecutiveProducer:
    def __init__(self, provider:CreativeModelProvider): self.provider=provider

    def review_art(self, production_id:str, brief:Dict[str,Any], story:Dict[str,Any], visual:Dict[str,Any], art:Dict[str,Any], form_resolution:Dict[str,Any])->Dict[str,Any]:
        issues=[]
        if art["hero"]["prominence"] not in {"DOMINANT","PRIMARY"}: issues.append({"code":"WEAK_HERO_PROMINENCE","detail":art["hero"]["prominence"]})
        if form_resolution.get("status")=="UNSUPPORTED_FORM_REQUIRED": issues.append({"code":"FORM_GAP","detail":form_resolution.get("concept","")})
        request={"production_id":production_id,"brief":deepcopy(brief),"film_thesis":deepcopy(story["film_thesis"]),"visual_concept":deepcopy(visual),"art_candidate":deepcopy(art),"form_resolution":deepcopy(form_resolution),"mechanical_preflight":deepcopy(issues),"instruction":{"role":"Independent Executive Producer — Art Review","questions":["Is the settled frame already strong without motion?","Is the hero unmistakably dominant?","Does the art bible define a specific coherent world rather than generic styling?","Do foreground/midground/background, scale contrast and overlap create intentional composition rather than a slide/card layout?","Are environments lived-in enough for the concept and are props scene-specific rather than generic symbols?","If characters exist, do silhouette, face/gaze, hands/contact and emotional action read at the intended shot scale?","Does typography belong to the art system instead of sitting on top of it?","Is the form resolution commercially plausible?","Are support and decorative elements compositionally disciplined by hierarchy, not by a fixed house count?","Would these frames still feel authored if motion were removed entirely?","Reject implausible or unsafe Art choices, but do not require fabricated real-world test results at Art stage; carry empirical food/camera/product validation downstream."],"release_decision_law":release_decision_law("ART_DIRECTION")}}
        review=validate_producer_output(self.provider.complete("art_review",request))
        # Art may require real food/camera/product tests, but absence of those physical
        # results cannot be fabricated or used as a concept-stage rejection. Keep any
        # intrinsic plausibility/composition defect blocking and defer only the empirical
        # proof requirement downstream, exactly as Story/Visual governance does.
        blocking=[]; deferred=[]
        for issue in review.get("issues") or []:
            b,d=ExecutiveProducer._split_external_validation_requirement(issue)
            if b is not None: blocking.append(b)
            if d is not None: deferred.append(d)
        if deferred:
            review=deepcopy(review); review["issues"]=blocking; review["deferred_production_validations"]=deferred
            if not blocking:
                review["verdict"]="ACCEPT"; review["revision_brief"]=""
            else:
                changes=[]
                for item in blocking:
                    change=ExecutiveProducer._required_change(item)
                    if change and change not in changes: changes.append(change)
                review["revision_brief"]="Resolve only the remaining Art-stage issues: " + " ".join(changes)
        if issues:
            review=deepcopy(review); review["verdict"]="REVISE" if review["verdict"]=="ACCEPT" else review["verdict"]
            mechanical=[]
            for issue in issues:
                item=deepcopy(issue); item["blocking"]=True; mechanical.append(item)
            review["issues"]=[*mechanical,*review["issues"]]
            if not review["revision_brief"].strip(): review["revision_brief"]="Repair hero prominence/form coverage before Art Direction can be committed."
            review["commercial_confidence"]="LOW"
        return validate_producer_output(calibrate_review(review,stage="ART_DIRECTION"))

    def review_storyboard(self, production_id:str, brief:Dict[str,Any], story:Dict[str,Any], visual:Dict[str,Any], art:Dict[str,Any], board:Dict[str,Any], gate_report:Dict[str,Any])->Dict[str,Any]:
        request={
            "production_id":production_id,
            "brief":deepcopy(brief),
            "film_thesis":deepcopy(story["film_thesis"]),
            "visual_concept":deepcopy(visual),
            "art_direction":deepcopy(art),
            "storyboard":deepcopy(board),
            "mechanical_gate":deepcopy(gate_report),
            "instruction":{
                "role":"Independent Executive Producer — Storyboard Review",
                "questions":[
                    "Does the film read as still key states?",
                    "Does each beat have one clear hero/action/payoff?",
                    "Does the storyboard realization visibly express the already-accepted Film Thesis?",
                    "Would motion be enhancing strong frames rather than rescuing weak frames?",
                    "Is continuity coherent across settled states?",
                ],
                "release_decision_law":release_decision_law("STORYBOARD"),
                "causal_owner_law":[
                    "Story has already passed its dedicated Producer gate. Do not reopen STORY merely because a storyboard fails to express the thesis, hero, payoff, escalation or transformation; those are normally VISUAL_CONCEPT or ART_DIRECTION realization defects.",
                    "Every blocking issue should include owner_department and code when possible.",
                    "Assign STORY only when the Story artifact itself is internally contradictory or directly violates the customer brief independent of Visual Concept and Art Direction. STORY escalation requires one of: STORY_INTERNAL_CONTRADICTION, STORY_CAUSAL_CHAIN_BROKEN, STORY_BRIEF_CONTRADICTION.",
                    "If the accepted Story is sound but the key states do not communicate it, assign VISUAL_CONCEPT. If the visual strategy is sound but settled frames/composition/form fail, assign ART_DIRECTION.",
                ],
            },
        }
        review=validate_producer_output(self.provider.complete("storyboard_review",request))
        return validate_producer_output(calibrate_review(review,stage="STORYBOARD"))
