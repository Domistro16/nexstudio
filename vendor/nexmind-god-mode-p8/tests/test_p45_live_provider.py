from __future__ import annotations
import json,os,sys,threading,unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src')); sys.path.insert(0,str(ROOT/'tests'))
from nexmind_god_mode.live_provider import LiveCreativeModelProvider,RoleRouter
from test_p45_cinema_editorial import cinema_candidate,editorial_candidate

def review(): return {"verdict":"ACCEPT","issues":[],"strengths":["strong"],"revision_brief":"","commercial_confidence":"HIGH"}
def select(prefix): return {"selected_candidate_id":prefix+"1","why":"best semantic strategy","tradeoffs":["bounded tradeoff"],"rejected_alternatives":[{"candidate_id":prefix+"2","reason":"weaker"},{"candidate_id":prefix+"3","reason":"weaker"}]}

class H(BaseHTTPRequestHandler):
    calls=[]
    def log_message(self,*a): pass
    def do_POST(self):
        n=int(self.headers.get('Content-Length','0')); p=json.loads(self.rfile.read(n)); H.calls.append((self.path,p))
        if self.path.endswith('/responses'):
            name=p['text']['format']['name']
            if name.endswith('cinematography'): out={"candidates":[cinema_candidate('C1',1),cinema_candidate('C2',2),cinema_candidate('C3',3)]}
            elif name.endswith('editorial_rhythm'): out={"candidates":[editorial_candidate('E1',1),editorial_candidate('E2',2),editorial_candidate('E3',3)]}
            else: out={}
            data={"id":"resp-p45","model":p['model'],"output_text":json.dumps(out),"usage":{"input_tokens":10,"output_tokens":20}}
        else:
            name=p['response_format']['json_schema']['name']
            if name.endswith('showrunner_select_cinematography'): out=select('C')
            elif name.endswith('showrunner_select_editorial'): out=select('E')
            else: out=review()
            data={"id":"chat-p45","model":p['model'],"choices":[{"message":{"content":json.dumps(out)}}],"usage":{"prompt_tokens":10,"completion_tokens":20}}
        b=json.dumps(data).encode(); self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)

@contextmanager
def srv():
    H.calls=[]; s=ThreadingHTTPServer(('127.0.0.1',0),H); t=threading.Thread(target=s.serve_forever,daemon=True); t.start()
    try: yield f"http://127.0.0.1:{s.server_address[1]}/v1"
    finally: s.shutdown();t.join(timeout=2);s.server_close()

class P45LiveProviderTests(unittest.TestCase):
    def env(self,b): return patch.dict(os.environ,{"NEXMIND_API_KEY":"x","NEXMIND_CREATIVE_MODEL":"test-creative-model","NEXMIND_CREATIVE_BASE_URL":b,"NEXMIND_CREATIVE_API_MODE":"responses","NEXMIND_API_KEY":"y","NEXMIND_REVIEW_MODEL":"test-review-model","NEXMIND_REVIEW_BASE_URL":b,"NEXMIND_REVIEW_API_MODE":"chat_completions"},clear=False)
    def test_p45_routes_exact_models(self):
        with patch.dict(os.environ,{'NEXMIND_CREATIVE_MODEL':'test-creative-model','NEXMIND_REVIEW_MODEL':'test-review-model'},clear=True):
            r=RoleRouter()
            for task in ['cinematography','editorial_rhythm']: self.assertEqual(r.resolve(task).model,'test-creative-model')
            for task in ['cinematography_review','showrunner_select_cinematography','editorial_review','showrunner_select_editorial','temporal_storyboard_review']: self.assertEqual(r.resolve(task).model,'test-review-model')
    def test_cinematography_live_transport_uses_strict_nested_schema(self):
        with srv() as b,self.env(b):
            p=LiveCreativeModelProvider(); out=p.complete('cinematography',{'production_id':'P'}); self.assertEqual(len(out['candidates']),3)
            schema=H.calls[-1][1]['text']['format']['schema']; shot=schema['properties']['candidates']['items']['properties']['shots']['items']; self.assertFalse(shot['additionalProperties']); self.assertIn('camera_atom',shot['properties'])
    def test_editorial_live_transport_uses_rational_integer_schema(self):
        with srv() as b,self.env(b):
            p=LiveCreativeModelProvider(); out=p.complete('editorial_rhythm',{'production_id':'P'}); self.assertEqual(len(out['candidates']),3)
            schema=H.calls[-1][1]['text']['format']['schema']; beat=schema['properties']['candidates']['items']['properties']['beats']['items']; self.assertEqual(beat['properties']['duration']['properties']['value']['type'],'integer')
    def test_p45_reviews_and_showrunner_use_sol(self):
        with srv() as b,self.env(b):
            p=LiveCreativeModelProvider()
            for task in ['cinematography_review','editorial_review','temporal_storyboard_review']:
                self.assertEqual(p.complete(task,{'production_id':'P'})['verdict'],'ACCEPT'); self.assertEqual(H.calls[-1][1]['model'],'test-review-model')
            self.assertEqual(p.complete('showrunner_select_cinematography',{'production_id':'P'})['selected_candidate_id'],'C1')
            self.assertEqual(p.complete('showrunner_select_editorial',{'production_id':'P'})['selected_candidate_id'],'E1')

if __name__=='__main__': unittest.main(verbosity=2)
