from __future__ import annotations

import copy
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve()
SERVICE = HERE.parents[1]
ROOT = HERE.parents[3]
sys.path.insert(0, str(SERVICE))
sys.path.insert(0, str(ROOT / "vendor" / "nexmind-god-mode-p8" / "src"))

from orchestrator import run_finalize_p8, _judge_ensemble_hash
from nexmind_god_mode.final_critic_ensemble import PRIOR_SLOTS
from nexmind_god_mode.final_producer_contracts import HUMAN_REVIEW_DIMENSIONS, CRAFT_DIMENSIONS, TASTE_DIMENSIONS
from nexmind_god_mode.showrunner_p8 import NexMindSupremeShowrunnerP8
from nexmind_god_mode.multimodal_evidence import build_multimodal_evidence
import hashlib, json

CRAFT=CRAFT_DIMENSIONS
TASTE=TASTE_DIMENSIONS


def sd(v=9.7): return {"score":v,"confidence":"HIGH","rationale":"specific evidence"}

def machine(v=9.7, verdict="ACCEPT"):
    return {
        "verdict":verdict,
        "hard_gates":[{"dimension":"EVIDENCE_TRUTH","status":"PASS","code":"OK","evidence":["bound"]}],
        "craft_scores":{k:sd(v) for k in CRAFT},
        "taste_judgments":{k:sd(v) for k in TASTE},
        "divergence":{"novelty":8.2,"conceptual_risk":5.2,"template_similarity":2.1,"rationale":"not templated"},
        "uncertainty":{"confidence":"HIGH","reasons":[],"human_review_required":False,"multimodal_evidence_complete":True},
        "strengths":["commercially coherent"],
        "issues":[] if verdict=="ACCEPT" else ["weak"],
        "revision_plan":[] if verdict=="ACCEPT" else ["repair weak area"],
        "commercial_recommendation":"RENDER_FOR_INTERNAL_REVIEW" if verdict=="ACCEPT" else "DO_NOT_RENDER",
    }

def human(v=9.7, reviewer="H"):
    return {"reviewer_id":reviewer,"reviewer_provenance":"independent blind panel","blind":True,"independent":True,"scores":{k:v for k in HUMAN_REVIEW_DIMENSIONS},"hard_rejects":[],"notes":"blind"}

def semantic(slot):
    if slot=='film_thesis': return {'central_argument':'One clear causal argument','final_payoff':'The audience sees the whole consequence','audience_before':'unclear','audience_after':'understands'}
    if slot=='visual_concept': return {'visual_thesis':'one dominant physical argument','hero_kind':'literal hero object','transformation':'state changes causally','beat_treatments':[1,2]}
    if slot=='art_direction': return {'art_thesis':'authored visual world','hero_treatment':'dominant','settled_state':'resolved','risk_notes':[]}
    if slot=='cinematography': return {'cinema_thesis':'camera follows attention','shots':[{'motivation':'reveal'},{'motivation':'payoff'}]}
    if slot=='editorial_rhythm': return {'rhythm_thesis':'escalating pace','beats':[{'duration':2},{'duration':5}]}
    if slot=='motion_performance': return {'motion_thesis':'motivated action only','actions':[{'status':'EXECUTABLE','contact_requirement':'TARGET_CONTACT'}]}
    if slot=='sound_direction': return {'sound_thesis':'silence and action cues','resource_gaps':[],'events':[{'kind':'SILENCE'},{'kind':'FOLEY'}]}
    if slot=='storyboard': return {'rehearsal_states':['opening','settled','payoff']}
    if slot=='storyboard_temporal': return {'timing':'resolved'}
    return {'resolved':True}

def checkpoint():
    sr=NexMindSupremeShowrunnerP8('P-AUTO',{'topic':'x','family':'EXPLAINER'})
    for slot in PRIOR_SLOTS:
        sr.state['decisions'][slot]={'decision_slot':slot,'department':'fixture','proposal_id':slot,'payload':semantic(slot),'revision':sr.state['revision'],'status':'COMMITTED_BY_SHOWRUNNER','producer_review_id':'fixture-review'}
    return {"schema":"NexMindSupremeShowrunnerCheckpointV1","state":copy.deepcopy(sr.state),"state_hash":sr.state_hash()}

def board():
    return {'schema':'NexMindCanonicalSoundStoryboardV4','beats':[{'beat_id':'B1','sound_plan_status':'DIRECTED_SOUND'},{'beat_id':'B2','sound_plan_status':'DIRECTED_SOUND','final_payoff':'resolved'}],'unresolved_departments':['final_producer']}

def artifacts():
    return [
        {"artifact_id":"v","kind":"VIDEO","sha256":"a"*64,"media_sha256":"a"*64,"source":"object://v","object_key":"review/v.mp4"},
        {"artifact_id":"a","kind":"AUDIO_MIX","sha256":"b"*64,"media_sha256":"b"*64,"source":"object://a","object_key":"review/a.wav"},
    ]

def media_set_sha():
    return build_multimodal_evidence(artifacts(),audio_expected=True)["media_set_sha256"]

def perceptual_media():
    # The production finalizer creates these data URLs from the exact reviewed MP4.
    # Unit tests exercise the orchestration contract; byte extraction is separately
    # certified by the production-media identity gate.
    return {
        "videoArtifactId":"v",
        "videoMediaSha256":"a"*64,
        "temporalFrames":[{"timestampSeconds":0.0,"sha256":"c"*64,"dataUrl":"data:image/jpeg;base64,/9j/2Q=="}],
        "audio":{"sha256":"d"*64,"mimeType":"audio/wav","sampleRate":48000,"channels":2,"dataUrl":"data:audio/wav;base64,UklGRg=="},
        "referenceVisuals":[],
    }

def judge_ensemble_hash():
    return _judge_ensemble_hash(Provider(machine()))

P8_BUILD="p8-fixture-build-v3"

def calibration_records():
    out=[]; ensemble=judge_ensemble_hash()
    # Exact family/build/judge set with reviewer diversity and rank variation.
    for i in range(48):
        v=9.5+(i%10)*0.05
        out.append({"productionId":f"prod-{i}","family":"EXPLAINER","evidenceHash":f"e-{i}","p8BuildHash":P8_BUILD,"judgeEnsembleHash":ensemble,"machineReview":machine(v),"humanReview":human(v,f"R-{i%12}"),"synthetic":False})
    return {"schema":"StudioTasteCalibrationSnapshotV3","records":out}

class Provider:
    def __init__(self,payload):
        self.payload=payload; self._media_set=""
    def complete(self,task,request):
        self._media_set=str((request.get("multimodal_evidence") or {}).get("media_set_sha256") or self._media_set)
        if task=="final_producer": return copy.deepcopy(self.payload)
        if task=="perceptual_auditor": return {"verdict":"PASS","issues":[],"rationale":"independent fixture veto passed"}
        raise AssertionError(task)
    def audit_dicts(self):
        # Deliberately use one provider/model identity across upstream creative work
        # and both final-review roles. Independence is role/process based, not
        # manufactured by forcing multiple paid models.
        shared={"status":"PASS","provider":"fixture","resolved_model":"one-capable-model-v1"}
        return [
            {**shared,"task":"story","role":"StoryDirector"},
            {**shared,"task":"visual","role":"VisualConceptDirector"},
            {**shared,"task":"art","role":"ArtDirector"},
            {**shared,"task":"final_producer","role":"IndependentFinalExecutiveProducer"},
            {**shared,"task":"perceptual_auditor","role":"IndependentPerceptualAuditor"},
        ]
    def perceptual_delivery_dicts(self):
        return [
            {"task":"final_producer","media_set_sha256":self._media_set,"image_count":1,"audio_count":1},
            {"task":"perceptual_auditor","media_set_sha256":self._media_set,"image_count":1,"audio_count":1},
        ]

class AutonomousFinalizeIntegration(unittest.TestCase):
    def request(self, **extra):
        x={"schema":"StudioNexMindP8FinalizeRequestV1","operation":"FINALIZE_WITH_MULTIMODAL_EVIDENCE","productionId":"P-AUTO","workflowRunId":"W","family":"EXPLAINER","p8BuildHash":P8_BUILD,"checkpoint":checkpoint(),"finalBoard":board(),"multimodalArtifacts":artifacts(),"mediaSetSha256":media_set_sha(),"perceptualMedia":perceptual_media(),"audioExpected":True,"autonomyPolicy":{"repairRound":0}}
        x.update(extra); return x

    def test_calibrated_multimodal_can_lock_without_per_job_human(self):
        r=run_finalize_p8(self.request(studioTasteCalibration=calibration_records()),provider=Provider(machine()))
        self.assertEqual(r["status"],"CREATIVE_LOCKED")
        self.assertEqual(r["creativeLockMode"],"AUTONOMOUS_CALIBRATED")
        self.assertEqual(r["autonomousQualityEvidence"]["status"],"PASS")

    def test_before_calibration_human_bridge_stays_required_and_can_unlock(self):
        nohuman=run_finalize_p8(self.request(studioTasteCalibration={"schema":"StudioTasteCalibrationSnapshotV1","records":[]}),provider=Provider(machine()))
        self.assertEqual(nohuman["status"],"HUMAN_REVIEW_REQUIRED")
        self.assertEqual(nohuman["code"],"P8_STUDIO_TASTE_CALIBRATION_NOT_YET_PROVEN")
        withhuman=run_finalize_p8(self.request(studioTasteCalibration={"schema":"StudioTasteCalibrationSnapshotV1","records":[]},humanReview=human()),provider=Provider(machine()))
        self.assertEqual(withhuman["status"],"CREATIVE_LOCKED")
        self.assertEqual(withhuman["creativeLockMode"],"HUMAN_CALIBRATION_BRIDGE")

    def test_weak_finished_work_routes_repair_even_with_good_calibration(self):
        bad=machine();bad["craft_scores"]["art_craft"]=sd(7.8)
        r=run_finalize_p8(self.request(studioTasteCalibration=calibration_records()),provider=Provider(bad))
        self.assertEqual(r["status"],"REVISE")
        self.assertEqual(r["code"],"P8_AUTONOMOUS_CREATIVE_REPAIR_REQUIRED")
        self.assertEqual(r["repairRequest"]["round"],1)
        self.assertFalse(r["repairRequest"]["exhausted"])

    def test_persistent_quality_failure_escalates_strategy_without_customer_failure(self):
        bad=machine();bad["taste_judgments"]["commercial_believability"]=sd(7.7)
        req=self.request(studioTasteCalibration=calibration_records(),autonomyPolicy={"repairRound":2})
        r=run_finalize_p8(req,provider=Provider(bad))
        self.assertEqual(r["status"],"REVISE")
        self.assertEqual(r["code"],"P8_AUTONOMOUS_CREATIVE_REPAIR_REQUIRED")
        self.assertEqual(r["repairRequest"]["round"],3)
        self.assertEqual(r["repairRequest"]["escalation_scope"],"WHOLE_FILM_CREATIVE_STRATEGY")
        self.assertFalse(r["repairRequest"]["exhausted"])
        self.assertFalse(r["repairRequest"]["quality_floor_may_weaken"])
        self.assertFalse(r["repairRequest"]["silent_generic_fallback_allowed"])


    def test_one_model_one_provider_all_roles_does_not_trigger_identity_block(self):
        provider=Provider(machine())
        ensemble=_judge_ensemble_hash(provider)
        self.assertIsInstance(ensemble,str)
        self.assertEqual(len(ensemble),64)
        r=run_finalize_p8(self.request(studioTasteCalibration=calibration_records()),provider=provider)
        self.assertNotEqual(r.get("code"),"P8_JUDGE_INDEPENDENCE_RECOVERY_REQUIRED")
        self.assertNotEqual(r.get("code"),"P8_JUDGE_MODEL_INDEPENDENCE_VIOLATION")
        self.assertNotEqual(r.get("code"),"P8_AUTHOR_REVIEWER_MODEL_INDEPENDENCE_VIOLATION")
        self.assertEqual(r["status"],"CREATIVE_LOCKED")

if __name__=="__main__": unittest.main(verbosity=2)
