#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SERVICE=ROOT/'services'/'studio-nexmind-p8'
P8=ROOT/'vendor'/'nexmind-god-mode-p8'/'src'
sys.path.insert(0,str(SERVICE));sys.path.insert(0,str(P8))
import orchestrator as o

checks=[]
def check(name, ok, detail=''):
    checks.append({'name':name,'pass':bool(ok),'detail':str(detail or '')})

# B01-class repair context must preserve an actual candidate anchor and dedupe repeated critique.
reviewed=[
    {'candidate':{'candidate_id':'A','visual_thesis':'x','hero_kind':'father','transformation':'a to b'},'review':{
        'verdict':'REVISE','commercial_confidence':'HIGH','issues':[{'severity':'MATERIAL','area':'Pacing','issue':'An extra spoon test repeats the action.','required_change':'Remove the extra spoon test.'}], 'strengths':['human hero'],'revision_brief':'Remove the extra spoon test.'}},
    {'candidate':{'candidate_id':'B','visual_thesis':'y','hero_kind':'glaze','transformation':'c to d'},'review':{
        'verdict':'REVISE','commercial_confidence':'LOW','issues':[{'severity':'MATERIAL','area':'Pacing','issue':'The extra spoon test repeats the action.','required_change':'Remove the extra spoon test.'}], 'strengths':['human hero'],'revision_brief':'Remove the extra spoon test.'}},
]
ctx=o._reviews_context(reviewed)
check('repair context carries concrete previous_output anchor', isinstance(ctx.get('previous_output'),dict) and bool(ctx['previous_output'].get('candidate_id')), ctx.get('previous_output',{}).get('candidate_id'))
check('duplicate Producer critique is canonicalized', len(ctx.get('issues') or [])==1, len(ctx.get('issues') or []))

# External broader context must enter the same binding revision-context channel used by Directors.
b=o._brief({'prompt':'x','family':'EXPLAINER','autonomousRepairContext':{'round':1,'repair_mode':'MATERIAL_STRATEGY_REPLAN'}})
check('broader replan context reaches autonomous_revision_context', (b.get('autonomous_revision_context') or {}).get('repair_mode')=='MATERIAL_STRATEGY_REPLAN')

# B01 Visual exhaustion maps to Story, so it must continue automatically within a bounded global round budget.
req={'productionId':'p','broaderStrategyMaxRounds':3}
rr={'round':1,'owner_department':'STORY','source_department':'VISUAL_CONCEPT'}
nxt=o._next_broader_strategy_request(req,rr,'STORY')
check('Story-owned broader strategy replan auto-continues', isinstance(nxt,dict) and (nxt.get('request') or {}).get('autonomousRepairContext',{}).get('strategy_replan_required') is True)
rr4={'round':4,'owner_department':'STORY','source_department':'VISUAL_CONCEPT'}
check('broader strategy auto-replan remains globally bounded', o._next_broader_strategy_request(req,rr4,'STORY') is None)
check('downstream exhaustion is not silently converted into Story rewrite', o._next_broader_strategy_request(req,rr,'VISUAL_CONCEPT') is None)

# Ensure local attempt budgets were not loosened to manufacture a pass.
limits=o._adaptive_attempt_limits({'durationSeconds':30})
check('Visual local quality budget remains 3 attempts', limits.get('VISUAL_CONCEPT')==3, limits)
check('Story local quality budget remains 2 attempts', limits.get('STORY')==2, limits)

# Source-level executable laws.
visual=(P8/'nexmind_god_mode'/'visual_concept_director.py').read_text(encoding='utf-8')
ep=(P8/'nexmind_god_mode'/'executive_producer.py').read_text(encoding='utf-8')
council=(P8/'nexmind_god_mode'/'council.py').read_text(encoding='utf-8')
check('Visual repair uses explicit repair_anchor', 'repair_anchor' in visual and 'exactly one candidate derived from that anchor' in visual)
check('Producer separates deferred production validation', 'deferred_production_validations' in ep and '_split_external_validation_requirement' in ep)
check('surgical Visual commit does not require renewed diversity', 'require_diversity=False' in council and 'surgical visual repair' in council)

# V4: downstream causal-owner continuation and Art governance.
art_contracts=(P8/'nexmind_god_mode'/'art_contracts.py').read_text(encoding='utf-8')
art_director=(P8/'nexmind_god_mode'/'art_director.py').read_text(encoding='utf-8')
p3=(P8/'nexmind_god_mode'/'p3_producer.py').read_text(encoding='utf-8')
check('Art surgical repair permits one anchored candidate', 'repair_mode:bool=False' in art_contracts and 'art surgical repair must return exactly one candidate' in art_contracts)
check('Art repair uses explicit repair_anchor', 'repair_anchor' in art_director and 'exactly one stronger candidate' in art_director)
check('Art Producer contains no fixed support count rejection', 'SUPPORT_OVERLOAD' not in p3 and 'DECORATION_OVERLOAD' not in p3)
check('Art Producer defers production-only empirical proof', 'deferred_production_validations' in p3 and '_split_external_validation_requirement' in p3)

# Budget exhaustion is evidence only about the exhausted department. It must not
# climb upstream merely because another department still has local attempts.
from nexmind_god_mode.showrunner_p8 import NexMindSupremeShowrunnerP8
sr=NexMindSupremeShowrunnerP8('qa-owner',{'topic':'x'})
o._ensure_repair_state(sr,{'STORY':2,'VISUAL_CONCEPT':3,'ART_DIRECTION':3,'CINEMATOGRAPHY':2,'EDITORIAL_RHYTHM':2,'MOTION_PERFORMANCE':3,'SOUND_DIRECTION':2})
sr.state['autonomous_creative_repair']['attempts'].update({'STORY':2,'VISUAL_CONCEPT':2,'ART_DIRECTION':3})
owner,chain=o._resolve_available_escalation_owner(sr,'ART_DIRECTION')
check('Art budget exhaustion opens a new Art lineage rather than climbing upstream', owner=='ART_DIRECTION' and chain==['ART_DIRECTION'], chain)
sr.state['autonomous_creative_repair']['attempts']['VISUAL_CONCEPT']=3
owner2,chain2=o._resolve_available_escalation_owner(sr,'VISUAL_CONCEPT')
check('Visual budget exhaustion never cascades to Story by budget alone', owner2=='VISUAL_CONCEPT' and chain2==['VISUAL_CONCEPT'], chain2)
check('structural contract repair has separate bounded budget', 'DEFAULT_DIRECTOR_CONTRACT_REPAIR_LIMIT' in (SERVICE/'orchestrator.py').read_text(encoding='utf-8') and 'contract_repairs' in (SERVICE/'orchestrator.py').read_text(encoding='utf-8'))

# V5 performance governance: preserve quality while eliminating redundant/churning calls.
from nexmind_god_mode.story_director import StoryDirector
from nexmind_god_mode.live_provider import LiveCreativeModelProvider

simple_brief=o._brief({'prompt':'A portable induction cooktop brand wants a 30-second film that makes precise heat control feel surprisingly human and useful, without turning into a feature list.','family':'EXPLAINER','durationSeconds':30})
check('simple 30s Story competition uses two genuine strategies, not forced three', StoryDirector._candidate_target(simple_brief,[{'claim_id':'C1','claim':'x','source':'u','status':'USER_SUPPLIED'}])==2)
complex_brief=dict(simple_brief); complex_brief['duration_s']=60
check('longer Story competition can expand adaptively', StoryDirector._candidate_target(complex_brief,[{'claim_id':'C1','claim':'x','source':'u','status':'USER_SUPPLIED'}])>=3)
art_repair_schema=LiveCreativeModelProvider._schema_for_request('art',{'repair_anchor':{'candidate_id':'A'},'candidate_budget':1})
art_candidates=art_repair_schema['properties']['candidates']
check('Art surgical repair provider schema is exactly one candidate', art_candidates.get('minItems')==1 and art_candidates.get('maxItems')==1, art_candidates)
visual_repair_schema=LiveCreativeModelProvider._schema_for_request('visual',{'repair_anchor':{'candidate_id':'V'},'candidate_budget':1})
visual_candidates=visual_repair_schema['properties']['candidates']
check('Visual surgical repair provider schema is exactly one candidate', visual_candidates.get('minItems')==1 and visual_candidates.get('maxItems')==1, visual_candidates)
art_initial_schema=LiveCreativeModelProvider._schema_for_request('art',{'candidate_budget':2})['properties']['candidates']
check('simple Art competition has explicit bounded operational budget', art_initial_schema.get('minItems')==2 and art_initial_schema.get('maxItems')==2, art_initial_schema)
visual_initial_schema=LiveCreativeModelProvider._schema_for_request('visual',{'candidate_budget':3})['properties']['candidates']
check('simple Visual competition has explicit bounded operational budget', visual_initial_schema.get('minItems')==3 and visual_initial_schema.get('maxItems')==3, visual_initial_schema)
provider_source=(P8/'nexmind_god_mode'/'live_provider.py').read_text(encoding='utf-8')
check('provider retry default is bounded to one retry and remains operator-configurable', 'NEXMIND_PROVIDER_MAX_RETRIES' in provider_source and '\"1\"' in provider_source)
check('candidate Producer reviews use bounded parallel review execution', 'NEXMIND_REVIEW_PARALLELISM' in council and 'ThreadPoolExecutor' in council and 'NEXMIND_REVIEW_PARALLELISM' in (P8/'nexmind_god_mode'/'council_p3.py').read_text(encoding='utf-8'))
orch_source=(SERVICE/'orchestrator.py').read_text(encoding='utf-8')
check('provider performance telemetry is retained in P8 results', 'providerPerformance' in orch_source and '_provider_performance' in orch_source)
check('Story full-strategy restart is explicitly marked as STORY authority', 'rr["department"]="STORY"' in orch_source)
preflight_source=(ROOT/'scripts'/'run-nexmind-autonomy-blind-preflight.py').read_text(encoding='utf-8')
check('blind preflight preserves elapsed time, full events and provider performance diagnostics', all(token in preflight_source for token in ('elapsedSeconds','events.append','providerPerformance')))

out={'schema':'NexMindRepairGovernanceQAV1','status':'PASS' if all(x['pass'] for x in checks) else 'FAIL','passed':sum(x['pass'] for x in checks),'total':len(checks),'checks':checks,'law':'REPAIR_ANCHOR_STICKY_DECISIONS__ART_NO_HOUSE_COUNT_QUOTA__STRUCTURAL_REPAIR_SEPARATE__CAUSAL_OWNER_REPLAN_AUTO_CONTINUES_BOUNDED__PERFORMANCE_WITHOUT_QUALITY_DOWNGRADE'}
print(json.dumps(out,indent=2,ensure_ascii=False))
raise SystemExit(0 if out['status']=='PASS' else 1)
