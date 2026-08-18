#!/usr/bin/env python3
from __future__ import annotations
import base64, io, json, os, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/studio-family-engines'))
from authored_art import build_request, validate_and_materialize, execute_scene, capability_available, ArtExecutionInvalid

checks=[]
def ck(name,cond,detail=''):
    checks.append({'name':name,'pass':bool(cond),'detail':detail})

def png64(i):
    im=Image.new('RGBA',(1280,720),(250,248,242,255));d=ImageDraw.Draw(im);d.rectangle((150,150,450+i*15,420),outline=(20,20,20,255),width=5);d.ellipse((650,160,930,500),outline=(20,20,20,255),width=5)
    b=io.BytesIO();im.save(b,format='PNG');return base64.b64encode(b.getvalue()).decode()

scene={'sceneId':'qa.B1','beatId':'B1','heroRole':'delivery package','supportingRoles':['courier','doorway'],'sourceText':'delivery proof','visualDirection':{'representation':'AUTHORED_ILLUSTRATION'},'artDirection':{'art_thesis':'locked'},'artExecutionDirectives':{'spatial_mode':'GROUNDED_SCENE'},'semanticNeeds':{}}
req=build_request(scene,'WHITEBOARD','style.whiteboard-editorial','16:9')
payload={'schema':'NexStudioAuthoredScenePlateV1','creative_choice_introduced':False,'locked_semantics_hash':req['locked_semantics_hash'],'semantic_bindings':[{'semantic_ref':'delivery package','element_id':'hero','role':'HERO'},{'semantic_ref':'courier','element_id':'actor','role':'SUPPORT'},{'semantic_ref':'doorway','element_id':'door','role':'SUPPORT'}],'stages':[{'png_base64':png64(i)} for i in range(4)]}
with tempfile.TemporaryDirectory() as td:
    m=validate_and_materialize(payload,req,Path(td)/'ok')
    ck('valid authored plate materializes four staged PNGs',len(m['stage_files'])==4 and all(Path(x).exists() for x in m['stage_files']))
    bad=json.loads(json.dumps(payload));bad['semantic_bindings']=bad['semantic_bindings'][:-1]
    try: validate_and_materialize(bad,req,Path(td)/'bad'); missing_rejected=False
    except ArtExecutionInvalid: missing_rejected=True
    ck('missing P8 support semantic is rejected',missing_rejected)
    bad2=json.loads(json.dumps(payload));bad2['semantic_bindings'].append({'semantic_ref':'invented robot','element_id':'x','role':'SUPPORT'})
    try: validate_and_materialize(bad2,req,Path(td)/'bad2'); extra_rejected=False
    except ArtExecutionInvalid: extra_rejected=True
    ck('unauthored semantic invention is rejected',extra_rejected)
    # Mechanical command transport fixture. It proves the provider-agnostic contract only, not art quality.
    fixture=Path(td)/'fixture.py'
    fixture.write_text('''import sys,json,base64,io\nfrom PIL import Image,ImageDraw\nr=json.load(sys.stdin); stages=[]\nfor i in range(4):\n im=Image.new("RGBA",(1280,720),(250,248,242,255)); d=ImageDraw.Draw(im); d.rectangle((140,140,480+i*10,430),outline=(10,10,10,255),width=4); b=io.BytesIO(); im.save(b,format="PNG"); stages.append({"png_base64":base64.b64encode(b.getvalue()).decode()})\nrefs=r["requirements"]["required_semantics"]\nout={"schema":"NexStudioAuthoredScenePlateV1","creative_choice_introduced":False,"locked_semantics_hash":r["locked_semantics_hash"],"semantic_bindings":[{"semantic_ref":x,"element_id":"s"+str(i),"role":"HERO" if i==0 else "SUPPORT"} for i,x in enumerate(refs)],"stages":stages}\njson.dump(out,sys.stdout)\n''')
    fidelity=Path(td)/'fidelity.py'
    fidelity.write_text('''import sys,json\nr=json.load(sys.stdin); print(json.dumps({"schema":"NexStudioAuthoredScenePixelFidelityReviewV1","locked_semantics_hash":r["locked_semantics_hash"],"reviewed_stage_sha256":[x["sha256"] for x in r["stage_evidence"]],"verdict":"PASS","veto_reasons":[],"commercial_score":None}))\n''')
    old=os.environ.get('NEXSTUDIO_ART_EXECUTION_REGISTRY_JSON')
    os.environ['NEXSTUDIO_ART_EXECUTION_REGISTRY_JSON']=json.dumps({'schema':'NexStudioArtExecutionRegistryV1','capabilities':{'authored_scene_illustration':{'transport':'command','command':[sys.executable,str(fixture)],'timeout_seconds':30},'authored_scene_pixel_fidelity_review':{'transport':'command','command':[sys.executable,str(fidelity)],'timeout_seconds':30}}})
    try:
        ck('authored scene capability is discovered by capability name',capability_available())
        m2=execute_scene(scene,'WHITEBOARD','style.whiteboard-editorial','16:9',Path(td)/'cmd')
        ck('command transport executes without any provider/model identity',len(m2['stage_files'])==4 and m2['provider_trace']['provider_identity_persisted'] is False and m2['pixel_fidelity_proof']['verdict']=='PASS')
    finally:
        if old is None: os.environ.pop('NEXSTUDIO_ART_EXECUTION_REGISTRY_JSON',None)
        else: os.environ['NEXSTUDIO_ART_EXECUTION_REGISTRY_JSON']=old

ck('request explicitly forbids creative authority in executor',req['requirements']['creative_choice_introduced'] is False)
ck('request locks exact semantic hash',len(req['locked_semantics_hash'])==64)
ck('request forbids model/provider identity in output','model/provider identity in output' in req['requirements']['forbidden'])
report={'schema':'NexStudioAuthoredArtExecutionQAV1','evidenceClass':'MECHANICAL_CONTRACT_ONLY_NOT_CREATIVE_QUALITY','passed':sum(x['pass'] for x in checks),'total':len(checks),'checks':checks}
print(json.dumps(report,indent=2));sys.exit(0 if report['passed']==report['total'] else 1)
