#!/usr/bin/env python3
from __future__ import annotations
import json, re, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def read(rel): return (ROOT/rel).read_text(encoding='utf-8')
checks=[]
def ck(name,ok,detail=''): checks.append({'name':name,'ok':bool(ok),'detail':detail})

p8=read('vendor/nexmind-god-mode-p8/src/nexmind_god_mode/showrunner_p8.py')
story=read('vendor/nexmind-god-mode-p8/src/nexmind_god_mode/story_director.py')
council=read('vendor/nexmind-god-mode-p8/src/nexmind_god_mode/council.py')
quality=read('vendor/nexmind-god-mode-p8/src/nexmind_god_mode/studio_quality.py')
final_producer=read('vendor/nexmind-god-mode-p8/src/nexmind_god_mode/final_executive_producer.py')
provider=read('vendor/nexmind-god-mode-p8/src/nexmind_god_mode/live_provider.py')
cal=read('vendor/nexmind-god-mode-p8/src/nexmind_god_mode/human_calibration.py')
auto=read('src/studio-v1/nexmind-p8/autonomy.ts')
workflow=read('src/studio-v1/nexmind-p8/workflow.ts')
state=read('src/studio-v1/nexmind-p8/creative-state.ts')
authority=read('src/studio-v1/production-engines/authority.ts')
prod=read('src/studio-v1/production-engines/workflow.ts')
survival=read('src/studio-v1/architecture/workflow-durability.ts')
worker=read('scripts/studio-worker.ts')
model_route=read('src/lib/nexmind-routing.ts')
mem_contracts=read('src/studio-v1/memory/contracts.ts')
mem_input=read('src/studio-v1/memory/production-input.ts')

ck('P8 has explicit governed decision-slot authority', all(x in p8 for x in ['film_thesis','visual_concept','art_direction','cinematography','editorial_rhythm','motion_performance','sound_direction']))
ck('Final Producer cannot be committed as an ordinary department', "if slot=='final_producer':raise AuthorityViolation" in p8)
ck('Story strategies are brief-specific rather than three house lenses', 'INVENT_A_BRIEF_SPECIFIC_NARRATIVE_STRATEGY' in story and 'INVENT_A_MATERIALLY_DIFFERENT_STRATEGY_NOT_EQUIVALENT_TO_PRIOR' in story and all(x not in story for x in ['DIRECT_CAUSAL_ARGUMENT','TENSION_REFRAME_PAYOFF','EVIDENCE_FIRST_DISCOVERY']))
ck('Story candidate diversity is mandatory before commit', 'develop_story_competition' in council and 'story candidate set is not meaningfully diverse' in council)
ck('Paid Studio path uses Story competition', 'p2.develop_story_competition(evidence)' in read('services/studio-nexmind-p8/orchestrator.py') and 'p2.develop_story(evidence)' not in read('services/studio-nexmind-p8/orchestrator.py'))
ck('Commercial craft/taste means are locked at 9.5', 'craftMeanFloor: 9.5' in auto and 'tasteMeanFloor: 9.5' in auto)
ck('Every creative dimension has a 9.0 floor and critical dimensions 9.5', 'dimensionFloor: 9.0' in auto and 'criticalDimensionFloor: 9.5' in auto)
ck('Quality evaluator uses 9.5 means and 9.0 per-dimension floor', all(x in quality for x in ['CRAFT_DIMENSION_BELOW_9','TASTE_DIMENSION_BELOW_9','CRAFT_MEAN_BELOW_9_5','TASTE_MEAN_BELOW_9_5']))
ck('Boring/generic/derivative work is an explicit Final Producer rejection class', all(x in final_producer.lower() for x in ['boring','generic','derivative','emotionally','aesthetically']))
ck('Creative defects cannot be laundered by human calibration', 'Creative defects outrank calibration' in quality and 'P8_AUTONOMOUS_CREATIVE_REPAIR_REQUIRED' in read('services/studio-nexmind-p8/orchestrator.py'))
ck('Creative recovery preserves quality floor', 'quality_floor_may_weaken: false' in workflow and 'silent_generic_fallback_allowed: false' in workflow)
ck('Creative BLOCKED/REVISE states keep production running', 'const creativeRecovery = result.status === "REVISE" || result.status === "BLOCKED"' in workflow and 'creativeRecovery ? "RUNNING"' in workflow)
ck('Family execution inability routes back to P8 replan', 'routeFamilyEngineCreativeReplan' in prod and 'REPLAN_REQUIRED' in prod and 'quality_floor_may_weaken:false' in prod.replace(' ',''))
ck('Worker exhaustion enters technical recovery, not production failure', 'TECHNICAL_RETRY' in worker and 'PRODUCTION_FAILED' not in worker)
ck('Expired activity exhaustion requeues durable workflow', 'recoveryCount' in survival and 'RUNNING' in survival and 'FAILED' not in re.sub(r'//.*','',survival))
ck('Provider failure stays technical retry', '"TECHNICAL_RETRY"' in workflow and 'PROVIDER_UNAVAILABLE' in workflow)
ck('No named model fallback in P8 provider', 'NEXMIND_MODEL_REGISTRY_JSON' in provider and not re.search(r'(?i)\b(?:gpt-5(?:\.\d+)?|claude(?:-[a-z0-9.]+)?|gemini(?:-[a-z0-9.]+)?|deepseek(?:-[a-z0-9.]+)?|luna|sol)\b', provider))
ck('Plan preview is capability-routed with no named fallback', 'creative_reasoning' in model_route and not re.search(r'(?i)\b(?:gpt-5(?:\.\d+)?|claude(?:-[a-z0-9.]+)?|gemini(?:-[a-z0-9.]+)?|deepseek(?:-[a-z0-9.]+)?|luna|sol)\b', model_route))
ck('Autonomy calibration is exact family/build/judge bound with a real-review floor', 'AUTONOMY_MIN_REAL_REVIEWS=36' in cal.replace(' ','') and 'TARGET_FAMILY_NOT_BOUND' in cal and 'P8_BUILD_HASH_NOT_BOUND' in cal and 'JUDGE_ENSEMBLE_HASH_NOT_BOUND' in cal)
ck('Autonomy calibration does not mix unrelated families', 'target_family' in cal and "r.get('family')==self.target_family" in cal and 'AUTONOMY_MIN_PER_FAMILY' not in cal)
ck('Machine false accepts block calibration', 'MACHINE_FALSE_ACCEPT_PRESENT' in cal and 'machineFalseAcceptCeiling: 0' in auto)
ck('Synthetic reviews cannot count', "real=[r for r in self.records if not r['synthetic']]" in cal)
ck('Studio creative state validates P8 ownership', 'StudioNexMindP8CreativeStateV2' in state and 'NEXMIND_CREATIVE_STATE_AUTHORITY_MISMATCH' in state and 'assertStudioNexMindCreativeState(content)' in workflow)
ck('Autonomous Creative Lock mode exists', 'AUTONOMOUS_CALIBRATED' in read('services/studio-nexmind-p8/orchestrator.py') and 'AUTONOMOUS_CALIBRATED' in workflow)
ck('Explainer is a neutral execution-only body beneath P8', 'EXPLAINER_EXECUTION_BODY_V2_P8_UNIFIED' in authority and 'execution-only' in authority.lower())
ck('All public family release gates remain fail-closed until evidence passes', authority.count('eligibleForPublicProduction: false')==4)
ck('References are analyzed before P8 creative execution', workflow.index('analyzeStandaloneReferenceLanguage(draft.sources)') < workflow.index('executeStudioNexMindP8(request'))
ck('Reference media bytes are materialized for execution', 'materializeReferenceMedia' in prod and 'referenceMedia' in prod and 'readObject' in prod)
ck('Five-scope persistent Creative Memory is canonical', all(x in mem_contracts for x in ['ACCOUNT','BRAND','CAST','SERIES','PRODUCTION']) and 'StudioProductionMemoryPacketV1' in mem_contracts)
ck('Paid P8 freezes MEMORY_INPUT before creative execution', workflow.index('captureProductionMemoryInputSnapshot') < workflow.index('executeStudioNexMindP8(request') and 'memoryInputSnapshotHash' in state)
ck('Final lineage binds MEMORY_INPUT and emits FILM_MEMORY', 'PRODUCTION_MEMORY_INPUT_LINEAGE_MISMATCH' in prod and 'captureFilmMemorySnapshotTx' in prod and 'StudioFilmMemoryV1' in mem_input)
ck('Creative workflow does not import billing authority', 'billing' not in workflow.lower() and 'billing' not in p8.lower())

# Live regression commands that are source-level, not commercial-taste proof.
for name,cmd in [
 ('Autonomous finalization unit tests',[sys.executable,'-m','unittest','services/studio-nexmind-p8/tests/test_autonomous_finalize.py']),
 ('Negative-space authority QA',[sys.executable,'scripts/nexmind-negative-space-qa.py']),
 ('Production-survival QA',[sys.executable,'scripts/production-survival-qa.py']),
]:
    cp=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    ck(name,cp.returncode==0,(cp.stdout+cp.stderr)[-1200:])

out={'schema':'StudioNexMindAutonomousAuthorityQA V2','pass':all(c['ok'] for c in checks),'passed':sum(c['ok'] for c in checks),'total':len(checks),'checks':checks,'truthBoundary':'Authority/recovery/model-routing implementation QA only; does not award 9.5 creative taste without blind rendered evidence.'}
path=ROOT/'reports/NEXMIND_AUTONOMOUS_AUTHORITY_QA.json';path.write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2));raise SystemExit(0 if out['pass'] else 1)
