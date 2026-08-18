#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SERVICE=ROOT/'services/studio-nexmind-p8';sys.path.insert(0,str(SERVICE))
spec=importlib.util.spec_from_file_location('studio_p8_orchestrator',SERVICE/'orchestrator.py');mod=importlib.util.module_from_spec(spec);assert spec and spec.loader;spec.loader.exec_module(mod)
checks=[]
def ck(name,ok,detail=''):checks.append({'name':name,'ok':bool(ok),'detail':detail})
request={'productionId':'qa-source-contradiction','prompt':'Explain the supplied launch facts without reconciling disagreements.','family':'EXPLAINER','videoType':'general','sourceIntelligence':{'extractedSourceCount':2,'visualReferences':[],'warnings':[],'provenanceLaw':'SOURCE_PROVENANCE_REQUIRED'}}
evidence=[{'claim_id':'SRC-A','claim':'The launch date is 12 September.','source':'source-a :: page 2 :: sha256 a','status':'USER_SOURCE_EXTRACTED'},{'claim_id':'SRC-B','claim':'The launch date is 19 September.','source':'source-b :: slide 4 :: sha256 b','status':'USER_SOURCE_EXTRACTED'}]
class Good:
 def complete(self,role,payload):
  assert role=='source_understanding'
  return {'status':'READY','summary':'The supplied sources disagree on launch date.','claims':[],'contradictions':[{'topic':'launch date','source_claim_ids':['SRC-A','SRC-B'],'values':['12 September','19 September']}],'unresolved_questions':['Which launch date is authoritative?'],'creative_relevance':['Do not state a single launch date as settled.'],'visual_evidence_needs':[],'source_integrity':{'used_only_provided_evidence':True,'contradictions_preserved':True,'invented_facts':False}}
a,out=mod._source_understanding(request,evidence,Good());ck('Contradiction survives source analysis',bool(a and a.get('contradictions')) and len(out)==2);ck('Contradiction does not invent resolved evidence',all(x['claim_id'] in {'SRC-A','SRC-B'} for x in out))
class BadUnknown:
 def complete(self,role,payload):
  return {'claims':[{'claim':'Launch date is 15 September.','source_claim_ids':['SRC-C']}],'contradictions':[],'source_integrity':{'used_only_provided_evidence':True,'contradictions_preserved':True,'invented_facts':False}}
try:mod._source_understanding(request,evidence,BadUnknown());ck('Unknown provenance ID is rejected',False,'no error')
except mod.ProviderError as e:ck('Unknown provenance ID is rejected','UNKNOWN_PROVENANCE_ID' in str(e),str(e))
class BadIntegrity:
 def complete(self,role,payload):return {'claims':[],'contradictions':[],'source_integrity':{'used_only_provided_evidence':False,'contradictions_preserved':False,'invented_facts':True}}
try:mod._source_understanding(request,evidence,BadIntegrity());ck('Invented/reconciled source analysis is rejected',False,'no error')
except mod.ProviderError as e:ck('Invented/reconciled source analysis is rejected',('NEGATIVE_INTEGRITY_ADMISSION' in str(e) or 'INTEGRITY_VIOLATION' in str(e)),str(e))
class Down:
 def complete(self,role,payload):raise mod.ProviderError('qa provider unavailable')
a,out=mod._source_understanding(request,evidence,Down());ck('Unavailable specialist preserves raw evidence',a.get('status')=='UNAVAILABLE' and a.get('raw_evidence_preserved') is True and out==evidence)
result={'schema':'StudioSourceIntelligenceContradictionQAV1','pass':all(x['ok'] for x in checks),'passed':sum(x['ok'] for x in checks),'total':len(checks),'checks':checks,'commercialScoreEvidence':False,'truthBoundary':'Provenance/contradiction integrity and resilience only; this does not prove live source reasoning quality.'}
outp=ROOT/'reports/source-intelligence/SOURCE_INTELLIGENCE_CONTRADICTION_QA.json';outp.parent.mkdir(parents=True,exist_ok=True);outp.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));raise SystemExit(0 if result['pass'] else 1)
