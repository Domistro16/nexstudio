from __future__ import annotations

import json, os, threading, unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'tests'))

from nexmind_god_mode.live_provider import LiveCreativeModelProvider, RoleRouter
from nexmind_god_mode.provider import ProviderError
from test_live_provider import story_payload, producer_payload


class PromptJsonHandler(BaseHTTPRequestHandler):
    calls=[]
    invalid_schema=False
    model_override=None
    def log_message(self,*args): pass
    def do_POST(self):
        n=int(self.headers.get('Content-Length','0'))
        payload=json.loads(self.rfile.read(n) or b'{}')
        self.__class__.calls.append({'path':self.path,'headers':dict(self.headers),'payload':payload})
        # Simulate a lowest-common-denominator OpenAI-compatible gateway:
        # chat completions only; no response_format or reasoning_effort support.
        if not self.path.endswith('/chat/completions'):
            self.send_response(404); self.end_headers(); return
        if 'response_format' in payload or 'reasoning_effort' in payload or 'reasoning' in payload or 'text' in payload:
            body=b'{"error":"unsupported strict-schema field"}'
            self.send_response(400); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body); return
        model=str(payload.get('model') or '')
        system_text=str((payload.get('messages') or [{}])[0].get('content') or '')
        if 'ExecutiveProducer' in system_text:
            out=producer_payload()
        else:
            out=story_payload()
            out['film_thesis']['hero_kind']='persistent causal hero'
            out['film_thesis']['camera_idea']='follow the hero through the causal transformation'
            for i,beat in enumerate(out['beats'],1):
                beat['hero_state']=f'hero state {i}'
                beat['narration_mode']='VOICEOVER'
                beat['narration_text']=f'Concise spoken beat {i}.'
                beat['narration_purpose']=f'Advance beat {i} without reading labels.'
        if self.__class__.invalid_schema:
            out=dict(out); out['verdict']=123 if 'verdict' in out else out
        data={
            'id':'virtuals_compat_test',
            'model':self.__class__.model_override or model,
            'choices':[{'message':{'role':'assistant','content':json.dumps(out)}}],
            'usage':{'prompt_tokens':100,'completion_tokens':40}
        }
        raw=json.dumps(data).encode('utf-8')
        self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)

@contextmanager
def prompt_json_server(full_endpoint=False):
    PromptJsonHandler.calls=[]; PromptJsonHandler.invalid_schema=False; PromptJsonHandler.model_override=None
    srv=ThreadingHTTPServer(('127.0.0.1',0),PromptJsonHandler)
    t=threading.Thread(target=srv.serve_forever,daemon=True); t.start()
    base=f'http://127.0.0.1:{srv.server_address[1]}/v1'
    try:
        yield base+'/chat/completions' if full_endpoint else base
    finally:
        srv.shutdown(); t.join(timeout=2); srv.server_close()

class PromptJsonCompatTests(unittest.TestCase):
    def setUp(self):
        self._env=patch.dict(os.environ,{"NEXMIND_CREATIVE_MODEL":"test-creative-model","NEXMIND_REVIEW_MODEL":"test-review-model"},clear=False)
        self._env.start()
    def tearDown(self):
        self._env.stop()

    def env(self,endpoint):
        # This is a hermetic transport-compatibility fixture. It must never inherit
        # operator-selected live model IDs from the shell, otherwise the mocked
        # gateway's canonical alias response can be mistaken for a real family
        # mismatch. Operator model precedence is covered separately by
        # test_operator_model_routing.py / validate-p8-operator-model-routing.py.
        return patch.dict(os.environ,{
            'NEXMIND_PROMPT_JSON_COMPAT':'1',
            'NEXMIND_API_KEY':'virtuals-key',
            'NEXMIND_CREATIVE_BASE_URL':endpoint,
            'NEXMIND_CREATIVE_MODEL':'test-creative-model',
            'NEXMIND_API_KEY':'virtuals-key',
            'NEXMIND_REVIEW_BASE_URL':endpoint,
            'NEXMIND_REVIEW_MODEL':'test-review-model',
        },clear=True)

    def test_compat_switch_moves_both_logical_providers_to_prompt_json_chat(self):
        with prompt_json_server() as endpoint, self.env(endpoint):
            r=RoleRouter()
            self.assertEqual(r.resolve('story').api_mode,'chat_completions_prompt_json')
            self.assertEqual(r.resolve('producer').api_mode,'chat_completions_prompt_json')

    def test_creative_lane_works_on_chat_only_gateway(self):
        with prompt_json_server() as endpoint, self.env(endpoint):
            out=LiveCreativeModelProvider().complete('story',{'production_id':'P'})
            self.assertIn('film_thesis',out)
            call=PromptJsonHandler.calls[-1]
            self.assertTrue(call['path'].endswith('/chat/completions'))
            self.assertNotIn('response_format',call['payload'])
            self.assertNotIn('reasoning_effort',call['payload'])
            self.assertIn('JSON Schema',call['payload']['messages'][0]['content'])

    def test_review_lane_works_on_same_chat_only_gateway(self):
        with prompt_json_server() as endpoint, self.env(endpoint):
            out=LiveCreativeModelProvider().complete('producer',{'production_id':'P'})
            self.assertEqual(out['verdict'],'ACCEPT')
            call=PromptJsonHandler.calls[-1]
            self.assertTrue(call['path'].endswith('/chat/completions'))
            self.assertNotIn('response_format',call['payload'])

    def test_full_chat_completions_endpoint_is_not_double_appended(self):
        with prompt_json_server(full_endpoint=True) as endpoint, self.env(endpoint):
            LiveCreativeModelProvider().complete('story',{'production_id':'P'})
            self.assertEqual(PromptJsonHandler.calls[-1]['path'],'/v1/chat/completions')

    def test_prompt_json_is_locally_schema_validated(self):
        with prompt_json_server() as endpoint, self.env(endpoint):
            PromptJsonHandler.invalid_schema=True
            with self.assertRaisesRegex(ProviderError,'PROMPT_JSON_SCHEMA_VALIDATION_FAILED'):
                LiveCreativeModelProvider().complete('producer',{'production_id':'P'})

    def test_model_alias_guard_still_applies(self):
        with prompt_json_server() as endpoint, self.env(endpoint):
            PromptJsonHandler.model_override='virtuals/test-review-model'
            out=LiveCreativeModelProvider().complete('producer',{'production_id':'P'})
            self.assertEqual(out['verdict'],'ACCEPT')

    def test_per_lane_mode_can_be_enabled_without_global_switch(self):
        with prompt_json_server() as endpoint, patch.dict(os.environ,{
            'NEXMIND_API_KEY':'virtuals-key','NEXMIND_CREATIVE_BASE_URL':endpoint,'NEXMIND_CREATIVE_MODEL':'test-creative-model',
            'NEXMIND_API_KEY':'virtuals-key','NEXMIND_REVIEW_BASE_URL':endpoint,'NEXMIND_REVIEW_MODEL':'test-review-model',
            'NEXMIND_CREATIVE_API_MODE':'chat_completions_prompt_json',
            'NEXMIND_REVIEW_API_MODE':'chat_completions_prompt_json',
        },clear=True):
            self.assertEqual(RoleRouter().resolve('story').api_mode,'chat_completions_prompt_json')
            self.assertEqual(RoleRouter().resolve('producer').api_mode,'chat_completions_prompt_json')

    def test_bad_mode_is_rejected(self):
        with patch.dict(os.environ,{'NEXMIND_CREATIVE_MODEL':'test-creative-model','NEXMIND_CREATIVE_API_MODE':'mystery'},clear=True):
            with self.assertRaisesRegex(ProviderError,'unsupported model route api_mode'):
                RoleRouter().resolve('story')

    def test_prompt_json_runtime_has_no_external_jsonschema_dependency(self):
        source=(ROOT/'src'/'nexmind_god_mode'/'live_provider.py').read_text(encoding='utf-8')
        self.assertNotIn('from jsonschema',source)
        self.assertNotIn('import jsonschema',source)

    def test_dependency_free_validator_catches_nested_type_mismatch(self):
        bad=story_payload()
        bad['film_thesis']['hero_kind']=123
        with self.assertRaisesRegex(ProviderError,'PROMPT_JSON_SCHEMA_VALIDATION_FAILED'):
            LiveCreativeModelProvider._validate_local_schema('story',bad)

if __name__=='__main__': unittest.main(verbosity=2)
