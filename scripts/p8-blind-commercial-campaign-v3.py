#!/usr/bin/env python3
from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];VENDOR=ROOT/'vendor/nexmind-god-mode-p8/src';sys.path.insert(0,str(VENDOR))
from nexmind_god_mode.live_provider import RoleRouter
from nexmind_god_mode.provider import ProviderError
PACK=ROOT/'evaluations/nexmind-p8-commercial-brain-v2/BLIND_COMMERCIAL_BRIEFS_V2.json'
OUT=ROOT/'reports/P8_BLIND_COMMERCIAL_CAMPAIGN_V3.json'
data=json.loads(PACK.read_text());briefs=data.get('briefs') or []
checks=[]
def ck(name,ok,detail=''):checks.append({'name':name,'ok':bool(ok),'detail':detail})
ck('30 sealed unfamiliar briefs present',len(briefs)==30,str(len(briefs)))
ck('Pack stores no recorded answers',data.get('recorded_answers_present') is False)
ck('Pack stores no expected candidate',data.get('expected_candidate_present') is False)
ck('Pack stores no preferred strategy',data.get('preferred_strategy_present') is False)
ck('Pack stores no candidate position labels',data.get('candidate_labels_present') is False)
ck('Brief domains are diverse',len({str(x.get('domain')) for x in briefs})>=25,str(len({str(x.get('domain')) for x in briefs})))
router=RoleRouter();required=['visual','art','producer','showrunner_select','final_producer'];routes={};missing=[]
for task in required:
 try:
  candidates=router.resolve_candidates(task);routes[task]=[{'role':x.role,'provider':x.provider,'modelConfigured':bool(x.model),'capability':router.ROLE_CAPABILITIES[task][0]} for x in candidates]
  if not candidates:missing.append(task)
 except ProviderError as e:missing.append(task);routes[task]={'status':'UNAVAILABLE','reason':str(e)}
ck('Campaign requires capability-routed live models, never named benchmark fixtures',all('RecordedModelProvider' not in json.dumps(v) for v in routes.values()))
status='READY_FOR_LIVE_EXECUTION' if not missing else 'BLOCKED_PRE_INFERENCE_NO_COMPATIBLE_MODEL'
result={'schema':'NexMindP8BlindCommercialCampaignV3','status':status,'pass':all(x['ok'] for x in checks),'passed':sum(x['ok'] for x in checks),'total':len(checks),'checks':checks,'briefCount':len(briefs),'inScopeFamilies':['EXPLAINER','WHITEBOARD','EDITORIAL_MOTION'],'characterFamilyIncluded':False,'requiredLiveTasks':required,'routeStatus':routes,'missingLiveTasks':missing,'filmsCompleted':0,'commercialScoreEmitted':False,'commercialScoreEvidence':False,'truthBoundary':'This harness certifies blindness, anti-curation and live capability prerequisites only. No Visual Concept, Art or Final Judgment score may rise until the sealed briefs run through real live inference, encoded film+audio and blind review.'}
OUT.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));raise SystemExit(0 if result['pass'] else 1)
