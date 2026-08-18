from __future__ import annotations
import argparse
import json
import os
import pathlib
import sys
import time
from copy import deepcopy

ROOT=pathlib.Path(__file__).resolve().parents[1]


def _load_local_env(path: pathlib.Path) -> None:
    """Load simple KEY=VALUE entries for direct CLI runs without overriding process env."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line=raw_line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line=line[7:].lstrip()
        key, separator, value=line.partition('=')
        key=key.strip()
        if not separator or not key or any(ch.isspace() for ch in key):
            continue
        value=value.strip()
        if len(value)>=2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value=value[1:-1]
        os.environ.setdefault(key, value)


_load_local_env(ROOT/'.env')
sys.path.insert(0,str(ROOT/'services'/'studio-nexmind-p8'))
from orchestrator import run_full_p8, classify_exception
from nexmind_god_mode.live_provider import LiveCreativeModelProvider


def _provider_recovery_limit() -> int:
    try:
        return max(0,min(4,int(os.getenv('NEXMIND_PREFLIGHT_PROVIDER_RECOVERY_ROUNDS','2') or 2)))
    except Exception:
        return 2


def run_with_provider_recovery(req, provider, progress=None, *, max_provider_recoveries=None):
    """Run one brief and absorb bounded transient provider failures inside the same command.

    Recovery resumes from the exact pre-call checkpoint returned by run_full_p8. A
    transient provider failure therefore does not consume a creative attempt, create
    duplicate proposal IDs, or require the operator/customer to restart the brief.
    Configuration/capability blocks are intentionally not retried as transport faults.
    """
    current_req=deepcopy(req)
    continuation_state=None
    maximum=_provider_recovery_limit() if max_provider_recoveries is None else max(0,min(4,int(max_provider_recoveries)))
    recoveries=0
    while True:
        try:
            result=run_full_p8(current_req,provider=provider,progress=progress,_continuation_state=continuation_state)
        except Exception as error:
            result=classify_exception(error)
        recoverable=(
            result.get('status')=='PROVIDER_UNAVAILABLE'
            and result.get('code')=='LIVE_PROVIDER_CALL_FAILED'
            and result.get('resumeSafe') is True
            and isinstance((result.get('checkpoint') or {}).get('state'),dict)
        )
        if not recoverable or recoveries>=maximum:
            return result,recoveries
        recoveries+=1
        continuation_state=deepcopy(result['checkpoint']['state'])
        overrides=result.get('continuationRequestOverrides') if isinstance(result.get('continuationRequestOverrides'),dict) else {}
        for key,value in overrides.items():
            current_req[key]=deepcopy(value)
        if progress:
            progress('PROVIDER_RECOVERY_AUTO_CONTINUE',{
                'round':recoveries,'maximum':maximum,'resumeStage':result.get('resumeStage'),
                'law':'TRANSIENT_PROVIDER_FAILURE_DOES_NOT_CONSUME_CREATIVE_ATTEMPT',
            })


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description='Run the provider-backed NexMind autonomy blind preflight.')
    parser.add_argument('--limit', type=int, default=None, help='Run only the first N sealed briefs (default: all).')
    args=parser.parse_args(argv)

    brief_file=ROOT/'evaluations'/'nexmind-p8-commercial-brain-v2'/'BLIND_COMMERCIAL_BRIEFS_V2.json'
    data=json.loads(brief_file.read_text(encoding='utf-8'))
    all_briefs=data['briefs']
    if args.limit is not None and args.limit < 1:
        parser.error('--limit must be at least 1')
    briefs=all_briefs[:args.limit] if args.limit is not None else all_briefs
    families=['EXPLAINER','WHITEBOARD','STICKMAN','EDITORIAL_MOTION']
    rows=[]
    for i,b in enumerate(briefs):
        phases=[]
        events=[]
        started=time.monotonic()
        def record_progress(phase, payload, *, brief_id=b['id'], position=i+1):
            phases.append(phase)
            events.append({'phase':phase,'payload':payload if isinstance(payload,dict) else {'value':payload}})
            print(f"[{position}/{len(briefs)}] {brief_id} phase={phase}", flush=True)
        req={
            'schema':'StudioNexMindP8RequestV1','productionId':f"blind-{b['id']}",'workflowRunId':f"w-{b['id']}",'projectVersion':1,
            'family':families[i%4],'videoType':'blind-commercial-eval','prompt':b['brief'],'planPreview':None,'sourceSummaries':[],
            'evidence':[{'claim_id':'USER-BRIEF-1','claim':b['brief'],'source':'sealed-blind-brief','status':'USER_SUPPLIED'}],
            'durationSeconds':b['duration_seconds'],'aspectRatio':'16:9','voicePreference':None,'brandContext':None,'creativeMemory':[],
            'policy':{'fullNexMindRequired':True,'planPreviewIsNotCreativeLock':True},
        }
        provider=LiveCreativeModelProvider()
        result,provider_recoveries=run_with_provider_recovery(req,provider,record_progress)
        elapsed_seconds=round(time.monotonic()-started,3)
        detail=str(result.get('detail') or '')[:1200]
        repair_request=result.get('repairRequest') if isinstance(result.get('repairRequest'),dict) else None
        autonomous_repair=result.get('autonomousRepair') if isinstance(result.get('autonomousRepair'),dict) else None
        provider_audits=result.get('providerAudits') if isinstance(result.get('providerAudits'),list) else []
        provider_performance=result.get('providerPerformance') if isinstance(result.get('providerPerformance'),dict) else {}
        diagnostic={
            'department':result.get('department'),
            'attempts':result.get('attempts'),
            'maxAttempts':result.get('maxAttempts'),
            'repairRequest':repair_request,
            'providerAuditsTail':provider_audits[-12:],
            'providerPerformance':provider_performance,
            'providerRecoveryRounds':provider_recoveries,
            'elapsedSeconds':elapsed_seconds,
        }
        if autonomous_repair:
            diagnostic['autonomousRepair']={
                'attempt_limits_by_department':autonomous_repair.get('attempt_limits_by_department'),
                'attempts':autonomous_repair.get('attempts'),
                'lifetime_attempts':autonomous_repair.get('lifetime_attempts'),
                'ledgerTail':(autonomous_repair.get('ledger') or [])[-8:] if isinstance(autonomous_repair.get('ledger'),list) else [],
            }
        rows.append({'id':b['id'],'family':families[i%4],'domain':b['domain'],'status':result.get('status'),'code':result.get('code'),'detail':detail,'elapsedSeconds':elapsed_seconds,'phases':phases,'events':events,'diagnostic':diagnostic})
        suffix=f" detail={detail}" if detail else ''
        print(f"[{i+1}/{len(briefs)}] {b['id']} status={result.get('status')} code={result.get('code')} elapsed={elapsed_seconds}s{suffix}", flush=True)

    provider_configured=bool(os.getenv('NEXMIND_MODEL_REGISTRY_JSON') or os.getenv('NEXMIND_CREATIVE_MODEL') or os.getenv('NEXMIND_REVIEW_MODEL'))
    credential_present=bool(os.getenv('NEXMIND_API_KEY'))
    out={
        'schema':'NexMindAutonomousCreativeAuthorityBlindPreflightV1',
        'brief_count':len(rows),
        'pack_brief_count':len(all_briefs),
        'brief_limit':args.limit,
        'sealed_brief_metadata':{'creative_benchmark_eligible':data.get('creative_benchmark_eligible'),'recorded_answers_present':data.get('recorded_answers_present'),'expected_candidate_present':data.get('expected_candidate_present'),'preferred_strategy_present':data.get('preferred_strategy_present')},
        'provider_neutral_registry_configured':provider_configured,
        'provider_neutral_default_credential_present':credential_present,
        'families_covered':sorted(set(r['family'] for r in rows)),
        'story_phase_entered':sum('STORY' in r['phases'] for r in rows),
        'provider_unavailable':sum(r['status']=='PROVIDER_UNAVAILABLE' for r in rows),
        'films_completed':sum(r['status']=='CREATIVE_LOCKED' for r in rows),
        'departments_complete':sum(r['status']=='DEPARTMENTS_COMPLETE' for r in rows),
        'commercial_score_emitted':False,
        'truth_boundary':('This is a live-path preflight only. Configured live routes are exercised, but this does not measure commercial creative quality.' if (provider_configured and credential_present) else 'This is a live-path preflight only. With no configured live creative-model credentials, it cannot measure commercial creative quality.'),
        'rows':rows,
    }
    path=ROOT/'reports'/'NEXMIND_AUTONOMY_BLIND_PREFLIGHT_2026-08-14.json'
    path.write_text(json.dumps(out,indent=2), encoding='utf-8')
    print(json.dumps({k:out[k] for k in ('brief_count','families_covered','story_phase_entered','provider_unavailable','departments_complete','films_completed','commercial_score_emitted')},indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
