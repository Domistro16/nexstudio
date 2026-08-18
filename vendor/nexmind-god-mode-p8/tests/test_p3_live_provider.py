from __future__ import annotations
import json,os,sys,threading,unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from nexmind_god_mode.live_provider import LiveCreativeModelProvider,RoleRouter


def art_payload():
    ba=[
      {"beat_id":"B1","settled_visual_state":"Hero dominates with semantic cutaway","focal_owner":"hero","supporting_roles":["support"],"meaning_without_motion":True},
      {"beat_id":"B2","settled_visual_state":"Hero settles with causal relationship legible","focal_owner":"hero","supporting_roles":["support"],"meaning_without_motion":True},
    ]
    def c(i,a): return {"candidate_id":f"A{i}","visual_candidate_id":"V1","art_thesis":f"Art thesis {i}","hero":{"semantic_ref":"hero","art_budget":"HIGH","prominence":"DOMINANT","recognizable_required":True},"composition":{"archetype":a,"hierarchy_order":["hero","support"],"negative_space_intent":"intentional","density":"BALANCED","asymmetry_intent":"controlled","support_budget":2,"decoration_budget":0},"form_request":{"concept":"laptop computer","representation":"AUTHORED_ILLUSTRATION","semantic_parts":["computer.hero"],"required_operations":["open.cutaway"],"style":"explainer"},"beat_art":ba,"typography_intent":"sparse","risk_notes":[]}
    return {"candidates":[c(1,"cutaway"),c(2,"macro"),c(3,"depth")]}

def review(): return {"verdict":"ACCEPT","issues":[],"strengths":["strong"],"revision_brief":"","commercial_confidence":"HIGH"}
def selection(): return {"selected_candidate_id":"A2","why":"strongest settled key state","tradeoffs":["denser"],"rejected_alternatives":[{"candidate_id":"A1","reason":"weaker"},{"candidate_id":"A3","reason":"weaker"}]}

class H(BaseHTTPRequestHandler):
    calls=[]
    def log_message(self,*a): pass
    def do_POST(self):
        n=int(self.headers.get('Content-Length','0')); p=json.loads(self.rfile.read(n)); H.calls.append((self.path,p))
        if self.path.endswith('/responses'):
            out=art_payload(); data={"id":"resp-art","model":p['model'],"output_text":json.dumps(out),"usage":{"input_tokens":10,"output_tokens":10}}
        else:
            name=p['response_format']['json_schema']['name']
            out=selection() if name.endswith('showrunner_select_art') else review()
            data={"id":"chat-p3","model":p['model'],"choices":[{"message":{"content":json.dumps(out)}}],"usage":{"prompt_tokens":10,"completion_tokens":10}}
        b=json.dumps(data).encode(); self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)

@contextmanager
def srv():
    H.calls=[]; s=ThreadingHTTPServer(('127.0.0.1',0),H); t=threading.Thread(target=s.serve_forever,daemon=True); t.start()
    try: yield f"http://127.0.0.1:{s.server_address[1]}/v1"
    finally: s.shutdown();t.join(timeout=2);s.server_close()

class P3LiveProviderTests(unittest.TestCase):
    def env(self,b): return patch.dict(os.environ,{"NEXMIND_API_KEY":"x","NEXMIND_CREATIVE_MODEL":"test-creative-model","NEXMIND_CREATIVE_BASE_URL":b,"NEXMIND_CREATIVE_API_MODE":"responses","NEXMIND_API_KEY":"y","NEXMIND_REVIEW_MODEL":"test-review-model","NEXMIND_REVIEW_BASE_URL":b,"NEXMIND_REVIEW_API_MODE":"chat_completions"},clear=False)
    def test_p3_routes_exact_models(self):
        with patch.dict(os.environ,{'NEXMIND_CREATIVE_MODEL':'test-creative-model','NEXMIND_REVIEW_MODEL':'test-review-model'},clear=True):
            r=RoleRouter(); self.assertEqual(r.resolve('art').model,'test-creative-model')
            for task in ['art_review','showrunner_select_art','storyboard_review']: self.assertEqual(r.resolve(task).model,'test-review-model')
    def test_art_responses_strict_schema(self):
        with srv() as b,self.env(b):
            p=LiveCreativeModelProvider(); out=p.complete('art',{'production_id':'P'}); self.assertEqual(len(out['candidates']),3)
            call=H.calls[-1][1]; self.assertTrue(call['text']['format']['strict']); self.assertEqual(call['model'],'test-creative-model')
    def test_art_review_sol(self):
        with srv() as b,self.env(b):
            p=LiveCreativeModelProvider(); self.assertEqual(p.complete('art_review',{'production_id':'P'})['verdict'],'ACCEPT'); self.assertEqual(H.calls[-1][1]['model'],'test-review-model')
    def test_storyboard_review_sol(self):
        with srv() as b,self.env(b):
            p=LiveCreativeModelProvider(); self.assertEqual(p.complete('storyboard_review',{'production_id':'P'})['verdict'],'ACCEPT'); self.assertEqual(H.calls[-1][1]['model'],'test-review-model')
    def test_art_showrunner_selection_sol(self):
        with srv() as b,self.env(b):
            p=LiveCreativeModelProvider(); self.assertEqual(p.complete('showrunner_select_art',{'production_id':'P'})['selected_candidate_id'],'A2'); self.assertEqual(H.calls[-1][1]['model'],'test-review-model')

if __name__=='__main__': unittest.main(verbosity=2)
