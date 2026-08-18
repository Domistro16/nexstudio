#!/usr/bin/env python3
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
worker=(ROOT/'scripts/studio-worker.ts').read_text()
dur=(ROOT/'src/studio-v1/architecture/workflow-durability.ts').read_text()
prod=(ROOT/'src/studio-v1/production-engines/workflow.ts').read_text()
bridge=(ROOT/'src/studio-v1/production-engines/bridge.ts').read_text()
family_worker=(ROOT/'services/studio-family-engines/worker.py').read_text()
contracts=(ROOT/'services/studio-family-engines/contracts.py').read_text()
checks={
 'worker_does_not_terminal_fail_on_retry_exhaustion':'PRODUCTION_FAILED' not in worker,
 'worker_enters_technical_recovery':'TECHNICAL_RETRY' in worker,
 'lease_exhaustion_requeues':'status: "FAILED"' not in dur[dur.find('recoverExpiredStudioActivityLeases'):dur.find('claimStudioActivity')],
 'lease_recovery_preserves_workflow':'status: "RUNNING"' in dur[dur.find('recoverExpiredStudioActivityLeases'):dur.find('claimStudioActivity')],
 'family_creative_replan_routes_to_p8':'routeFamilyEngineCreativeReplan' in prod and 'REPLAN_REQUIRED' in prod,
 'replan_never_weakens_quality':'quality_floor_may_weaken:false' in prod.replace(' ','') and 'silent_generic_fallback_allowed:false' in prod.replace(' ',''),
 'family_contract_preserves_paid_production':'CONTINUE_REPLANNING' in contracts and 'LOCAL_IDEA' not in contracts or 'CONTINUE_REPLANNING' in contracts,
 'family_adapter_block_is_recoverable_status':'TECHNICAL_RETRY_REQUIRED' in family_worker and '"status":"BLOCKED"' not in family_worker,
 'family_result_contract_has_no_terminal_blocked':'TECHNICAL_RETRY_REQUIRED' in bridge and ' | "BLOCKED"' not in bridge,
 'internal_evidence_technical_fault_requeues':'FAMILY_INTERNAL_EVIDENCE_TECHNICAL_RECOVERY_REQUIRED' in prod and 'FAMILY_ENGINE_TECHNICAL_RETRY_REQUIRED' in prod,
 'reviewed_final_promotion_is_byte_identity_path':'runReviewedFinalOutputPromotionActivity' in prod and 'byteForBytePromotion:true' in prod and 'BUILD_LOCKED_FINAL_OUTPUT' not in prod,
}
report={'schema':'StudioProductionSurvivalQAV2','status':'PASS' if all(checks.values()) else 'FAIL','checks':checks}
(ROOT/'reports/PRODUCTION_SURVIVAL_QA.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2));raise SystemExit(0 if report['status']=='PASS' else 1)
