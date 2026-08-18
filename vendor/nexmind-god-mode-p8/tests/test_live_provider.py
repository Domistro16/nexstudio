from __future__ import annotations

import json, os, threading, unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(ROOT/'src'))

from nexmind_god_mode.live_provider import LiveCreativeModelProvider, RoleRouter, models_equivalent
from nexmind_god_mode.provider import ProviderError


def story_payload():
    return {
        "film_thesis":{
            "central_argument":"The visible outcome is produced by a hidden sequence of transformations.",
            "film_kind":"causal explainer",
            "audience_before":"The process feels like a black box.",
            "audience_after":"The audience can mentally trace the causal stages.",
            "emotional_trajectory":["curious","oriented","satisfied"],
            "visual_trajectory":["whole","inside","consequence"],
            "opening_contract":"Begin with the familiar outcome and expose the hidden cause.",
            "final_payoff":"Return to the outcome with the mechanism now legible.",
            "anti_goals":["no sentence-by-sentence transcription","no generic card grid"]
        },
        "beats":[
            {"beat_id":"B1","purpose":"setup","question":"What is actually happening?","audience_before":"Sees only outcome","audience_after":"Sees there is an internal process","reveal":"Open the black box","required_claim_ids":["C1"]},
            {"beat_id":"B2","purpose":"payoff","question":"What changed?","audience_before":"Knows stages exist","audience_after":"Understands causal chain","reveal":"Trace the transformation","required_claim_ids":["C1"]}
        ]
    }

def visual_payload():
    beats=[
        {"beat_id":"B1","hero_state":"intact object","visual_action":"open the object to expose its working interior","audience_takeaway":"the result has an internal cause"},
        {"beat_id":"B2","hero_state":"working interior","visual_action":"follow one transformed element through the mechanism","audience_takeaway":"the causal chain is now legible"},
    ]
    return {"candidates":[
        {"candidate_id":"V1","representation":"AUTHORED_ILLUSTRATION","visual_thesis":"One hero object becomes transparent enough to reveal the process inside.","hero_kind":"recognizable hero object","transformation":"closed exterior becomes legible layered interior","camera_idea":"hold the hero, then make one motivated move inward","rationale":"Preserves object identity while revealing causal structure.","beat_treatments":beats},
        {"candidate_id":"V2","representation":"PHYSICAL_METAPHOR","visual_thesis":"One input physically changes state as it crosses a sequence of meaningful thresholds.","hero_kind":"single transforming material","transformation":"one persistent material visibly changes form at each causal threshold","camera_idea":"track the persistent material rather than the whole system","rationale":"Makes cause and consequence physical rather than diagrammatic.","beat_treatments":beats},
        {"candidate_id":"V3","representation":"CHARACTER","visual_thesis":"A guide handles one persistent object through the process so scale and agency remain clear.","hero_kind":"performer plus persistent object","transformation":"object changes through meaningful handled actions","camera_idea":"frame hands and object, then widen for the final consequence","rationale":"Uses embodied action only where it clarifies the process.","beat_treatments":beats},
    ]}

def producer_payload():
    return {"verdict":"ACCEPT","issues":[],"strengths":["clear hero","causal transformation"],"revision_brief":"","commercial_confidence":"HIGH"}

def selection_payload():
    return {"selected_candidate_id":"V2","why":"The physical transformation makes causality easiest to understand without turning the film into a diagram.","tradeoffs":["Requires a capable transformation performer"],"rejected_alternatives":[{"candidate_id":"V1","reason":"Less tactile"},{"candidate_id":"V3","reason":"Adds a character without needing one"}]}

class FakeHandler(BaseHTTPRequestHandler):
    calls=[]
    status_queue=[]
    model_override=None
    def log_message(self,*args): pass
    def do_POST(self):
        n=int(self.headers.get('Content-Length','0')); raw=self.rfile.read(n); payload=json.loads(raw or b'{}')
        self.__class__.calls.append({"path":self.path,"headers":dict(self.headers),"payload":payload})
        if self.__class__.status_queue:
            code=self.__class__.status_queue.pop(0)
            if code!=200:
                self.send_response(code); self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(b'{"error":"transient"}'); return
        if self.path.endswith('/responses'):
            # infer task from schema name
            name=payload.get('text',{}).get('format',{}).get('name','')
            out=story_payload() if name.endswith('story') else visual_payload()
            data={"id":"resp_test_1","model":self.__class__.model_override or payload['model'],"output_text":json.dumps(out),"usage":{"input_tokens":120,"input_tokens_details":{"cached_tokens":10},"output_tokens":55,"output_tokens_details":{"reasoning_tokens":8}}}
        elif self.path.endswith('/chat/completions'):
            name=payload.get('response_format',{}).get('json_schema',{}).get('name','')
            out=producer_payload() if name.endswith('producer') else selection_payload()
            data={"id":"chatcmpl_test_1","model":self.__class__.model_override or payload['model'],"choices":[{"message":{"role":"assistant","content":json.dumps(out)}}],"usage":{"prompt_tokens":100,"prompt_tokens_details":{"cached_tokens":4},"completion_tokens":40,"completion_tokens_details":{"reasoning_tokens":12}}}
        else:
            self.send_response(404); self.end_headers(); return
        body=json.dumps(data).encode(); self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('x-request-id','req_hdr_1'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)

@contextmanager
def fake_server():
    FakeHandler.calls=[]; FakeHandler.status_queue=[]; FakeHandler.model_override=None
    srv=ThreadingHTTPServer(('127.0.0.1',0),FakeHandler); t=threading.Thread(target=srv.serve_forever,daemon=True); t.start()
    try: yield f"http://127.0.0.1:{srv.server_address[1]}/v1"
    finally: srv.shutdown(); t.join(timeout=2); srv.server_close()

class LiveProviderTests(unittest.TestCase):
    def common_env(self,base):
        return patch.dict(os.environ,{"NEXMIND_API_KEY":"test-openai","NEXMIND_CREATIVE_BASE_URL":base,"NEXMIND_CREATIVE_MODEL":"test-creative-model","NEXMIND_CREATIVE_API_MODE":"responses","NEXMIND_API_KEY":"test-agent","NEXMIND_REVIEW_BASE_URL":base,"NEXMIND_REVIEW_MODEL":"test-review-model","NEXMIND_REVIEW_API_MODE":"chat_completions"},clear=False)

    def test_no_architecture_owned_model_defaults(self):
        with patch.dict(os.environ,{},clear=True):
            for task in ('source_understanding','source_visual_understanding','story','visual','producer','showrunner_select','final_producer'):
                with self.assertRaisesRegex(ProviderError,'NO_COMPATIBLE_MODEL_CONFIG'):
                    RoleRouter().resolve(task)

    def test_ambiguous_alias_is_rejected(self):
        with patch.dict(os.environ,{"NEXMIND_STORY_DIRECTOR_MODEL":"auto"},clear=True):
            with self.assertRaisesRegex(ProviderError,'ambiguous model alias'): RoleRouter().resolve('story')

    def test_custom_provider_label_is_runtime_configuration_not_architecture(self):
        env={"NEXMIND_STORY_DIRECTOR_PROVIDER":"custom-compatible","NEXMIND_STORY_DIRECTOR_MODEL":"test-custom-model","NEXMIND_STORY_DIRECTOR_BASE_URL":"https://gateway.invalid/v1","NEXMIND_STORY_DIRECTOR_API_KEY_ENV":"CUSTOM_KEY"}
        with patch.dict(os.environ,env,clear=True):
            route=RoleRouter().resolve('story')
            self.assertEqual((route.provider,route.model,route.api_key_env),("custom-compatible","test-custom-model","CUSTOM_KEY"))

    def test_missing_openai_key_is_explicit_blocker(self):
        with patch.dict(os.environ,{"NEXMIND_CREATIVE_MODEL":"test-creative-model","NEXMIND_CREATIVE_BASE_URL":"https://api.invalid/v1"},clear=True):
            with self.assertRaisesRegex(ProviderError,'LIVE_PROVIDER_BLOCKED_MISSING_CREDENTIAL:NEXMIND_API_KEY'):
                LiveCreativeModelProvider().complete('story',{'production_id':'X'})

    def test_missing_review_lane_base_is_explicit_blocker(self):
        with patch.dict(os.environ,{"NEXMIND_API_KEY":"x","NEXMIND_REVIEW_MODEL":"test-review-model"},clear=True):
            with self.assertRaisesRegex(ProviderError,'LIVE_PROVIDER_BLOCKED_MISSING_BASE_URL:runtime'):
                LiveCreativeModelProvider().complete('producer',{'production_id':'X'})

    def test_responses_api_uses_strict_schema_reasoning_and_exact_model(self):
        with fake_server() as base, self.common_env(base):
            p=LiveCreativeModelProvider(); out=p.complete('story',{'production_id':'P','brief':{'topic':'blind'}})
            self.assertIn('film_thesis',out); call=FakeHandler.calls[-1]
            self.assertTrue(call['path'].endswith('/responses')); self.assertEqual(call['payload']['model'],'test-creative-model')
            self.assertEqual(call['payload']['reasoning']['effort'],'high'); self.assertTrue(call['payload']['text']['format']['strict'])
            self.assertEqual(call['headers'].get('Idempotency-Key'),p.audits[-1].request_hash)
            self.assertEqual(p.audits[-1].resolved_model,'test-creative-model'); self.assertEqual(p.audits[-1].cached_input_tokens,10)

    def test_source_visual_payload_keeps_images_out_of_text_json(self):
        registry={"routes":[{"provider":"vision","model":"vision-model","capabilities":["multimodal_source_understanding"],"input_modalities":["images"],"priority":1,"base_url":"https://vision.invalid/v1","api_key_env":"VISION_KEY","api_mode":"responses"}]}
        with patch.dict(os.environ,{"NEXMIND_MODEL_REGISTRY_JSON":json.dumps(registry)},clear=True):
            p=LiveCreativeModelProvider(); route=RoleRouter().resolve('source_visual_understanding')
            payload=p._responses_payload('source_visual_understanding',{
                'production_id':'P',
                'source_visual_evidence':[{'sourceId':'S1','locator':'page 2','sha256':'abc','mimeType':'image/png','dataUrl':'data:image/png;base64,AAAA'}]
            },route)
            content=payload['input'][0]['content']
            self.assertEqual(content[1]['type'],'input_image')
            self.assertEqual(content[1]['image_url'],'data:image/png;base64,AAAA')
            self.assertNotIn('base64,AAAA',content[0]['text'])
            self.assertIn('page 2',content[0]['text'])

    def test_visual_schema_path_parses(self):
        with fake_server() as base, self.common_env(base):
            out=LiveCreativeModelProvider().complete('visual',{'production_id':'P'})
            self.assertEqual(len(out['candidates']),3)

    def test_agentrouter_chat_schema_exact_sol(self):
        with fake_server() as base, self.common_env(base):
            p=LiveCreativeModelProvider(); out=p.complete('producer',{'production_id':'P'})
            self.assertEqual(out['verdict'],'ACCEPT'); call=FakeHandler.calls[-1]
            self.assertTrue(call['path'].endswith('/chat/completions')); self.assertEqual(call['payload']['model'],'test-review-model')
            self.assertEqual(call['payload']['reasoning_effort'],'high'); self.assertTrue(call['payload']['response_format']['json_schema']['strict'])
            self.assertEqual(p.audits[-1].reasoning_tokens,12)

    def test_showrunner_uses_sol_and_parses(self):
        with fake_server() as base, self.common_env(base):
            out=LiveCreativeModelProvider().complete('showrunner_select',{'production_id':'P'})
            self.assertEqual(out['selected_candidate_id'],'V2'); self.assertEqual(FakeHandler.calls[-1]['payload']['model'],'test-review-model')

    def test_provider_qualified_model_alias_is_accepted(self):
        with fake_server() as base, self.common_env(base):
            FakeHandler.model_override='openai/test-review-model'
            p=LiveCreativeModelProvider(); out=p.complete('producer',{'production_id':'P'})
            self.assertEqual(out['verdict'],'ACCEPT')
            self.assertEqual(p.audits[-1].requested_model,'test-review-model')
            self.assertEqual(p.audits[-1].resolved_model,'openai/test-review-model')

    def test_explicit_provider_alias_is_accepted(self):
        with fake_server() as base, self.common_env(base), patch.dict(os.environ,{
            'NEXMIND_MODEL_EQUIVALENCE_JSON':json.dumps({'test-review-model':['vendor/deployment-sol-prod']})
        },clear=False):
            FakeHandler.model_override='vendor/deployment-sol-prod'
            out=LiveCreativeModelProvider().complete('producer',{'production_id':'P'})
            self.assertEqual(out['verdict'],'ACCEPT')

    def test_model_family_mismatch_is_rejected(self):
        with fake_server() as base, self.common_env(base):
            FakeHandler.model_override='openai/ambiguous-family-terra'
            with self.assertRaisesRegex(ProviderError,'MODEL_FAMILY_MISMATCH'):
                LiveCreativeModelProvider().complete('story',{'production_id':'P'})

    def test_capability_registry_fails_over_only_to_declared_compatible_route(self):
        with fake_server() as base:
            registry={"routes":[
                {"provider":"dead","model":"creative-primary","capabilities":["creative_reasoning"],"priority":9,"base_url":"https://dead.invalid/v1","api_key_env":"DEAD_KEY","api_mode":"responses"},
                {"provider":"healthy","model":"creative-secondary","capabilities":["creative_reasoning"],"priority":5,"base_url":base,"api_key_env":"HEALTHY_KEY","api_mode":"responses"},
            ]}
            with patch.dict(os.environ,{"NEXMIND_MODEL_REGISTRY_JSON":json.dumps(registry),"HEALTHY_KEY":"ok"},clear=True):
                p=LiveCreativeModelProvider(); out=p.complete('story',{'production_id':'P'})
                self.assertIn('film_thesis',out)
                self.assertEqual(FakeHandler.calls[-1]['payload']['model'],'creative-secondary')
                self.assertEqual(p.audits[-1].requested_model,'creative-secondary')

    def test_429_retries_idempotently(self):
        with fake_server() as base, self.common_env(base):
            FakeHandler.status_queue=[429,200]
            p=LiveCreativeModelProvider(max_retries=2); out=p.complete('story',{'production_id':'P'})
            self.assertIn('film_thesis',out); self.assertEqual(p.audits[-1].retries,1)
            self.assertEqual(len(FakeHandler.calls),2)
            self.assertEqual(FakeHandler.calls[0]['headers']['Idempotency-Key'],FakeHandler.calls[1]['headers']['Idempotency-Key'])

    def test_nontransient_401_does_not_retry_or_fallback(self):
        with fake_server() as base, self.common_env(base):
            FakeHandler.status_queue=[401]
            p=LiveCreativeModelProvider(max_retries=2)
            with self.assertRaises(ProviderError): p.complete('story',{'production_id':'P'})
            self.assertEqual(len(FakeHandler.calls),1); self.assertEqual(p.audits[-1].retries,0)

if __name__=='__main__': unittest.main(verbosity=2)
