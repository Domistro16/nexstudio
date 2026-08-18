from __future__ import annotations
from copy import deepcopy
from fractions import Fraction
from typing import Any,Dict,List,Set
from .contracts import ContractViolation, reject_geometry_code_authority, require_exact_keys, assert_semantic_candidate_diversity

ENERGY={"STILL","LOW","MEDIUM","HIGH","PEAK"}
TRANSITIONS={"CUT","MATCH_CUT","CARRY","DISSOLVE_MOTIVATED","HOLD_THROUGH"}


def rt(value:int,rate:int)->Dict[str,int]: return {"value":int(value),"rate":int(rate)}

def validate_rational_time(x:Dict[str,Any],label:str)->Dict[str,int]:
    require_exact_keys(x,{"value","rate"},label=label)
    if type(x["value"]) is not int or type(x["rate"]) is not int or x["value"]<0 or x["rate"]<=0: raise ContractViolation(f"invalid RationalTime {label}")
    return {"value":x["value"],"rate":x["rate"]}



def _as_int(value:Any, default:int=0)->int:
    if type(value) is int:
        return value
    try:
        return int(value)
    except Exception:
        return int(default)


def _allocate_durations(raw:List[int], minimums:List[int], target_sum:int)->List[int]:
    """Deterministically preserve relative pacing while hitting an exact frame sum."""
    if len(raw)!=len(minimums) or not raw:
        return raw
    floor=sum(minimums)
    if target_sum<floor:
        # This indicates an impossible execution contract rather than arithmetic drift.
        return raw
    weights=[max(1,int(x)) for x in raw]
    free=target_sum-floor
    total_weight=sum(weights) or len(weights)
    exact=[free*w/total_weight for w in weights]
    extras=[int(x) for x in exact]
    remainder=free-sum(extras)
    order=sorted(range(len(raw)), key=lambda i:(-(exact[i]-extras[i]), i))
    for i in order[:remainder]:
        extras[i]+=1
    return [minimums[i]+extras[i] for i in range(len(raw))]


def normalize_editorial_output(payload:Dict[str,Any], ordered_beat_ids:List[str], *, target_duration_frames:int, project_rate:int)->Dict[str,Any]:
    """Canonicalize deterministic timing metadata without changing Editorial's creative choices.

    Editorial owns pacing intent: roles, energy, relative duration emphasis, overlap intent,
    transition type, stillness and rationale. The runtime owns exact frame arithmetic:
    project rate, target total, event ordering, contiguous starts and in-beat marker bounds.
    Missing/duplicate beats or semantic vocabulary errors remain hard contract failures.
    """
    out=deepcopy(payload)
    candidates=out.get('candidates')
    if not isinstance(candidates,list):
        return out
    ordered=[str(x) for x in ordered_beat_ids]
    minimum=max(6,int(project_rate)//4)
    for c in candidates:
        if not isinstance(c,dict):
            continue
        c['project_rate']=int(project_rate)
        c['target_duration_frames']=int(target_duration_frames)
        beats=c.get('beats')
        if not isinstance(beats,list) or len(beats)!=len(ordered):
            continue
        by_id={}
        duplicate=False
        for b in beats:
            if not isinstance(b,dict):
                duplicate=True; break
            bid=str(b.get('beat_id') or '')
            if not bid or bid in by_id:
                duplicate=True; break
            by_id[bid]=b
        if duplicate or set(by_id)!=set(ordered):
            continue
        beats=[by_id[x] for x in ordered]
        c['beats']=beats

        # Canonicalize overlap intent first. Last-beat overlap has no executable meaning.
        overlaps=[]
        for i,b in enumerate(beats):
            ov=max(0,_as_int(b.get('overlap_to_next_frames'),0)) if i<len(beats)-1 else 0
            overlaps.append(ov)

        raw_durations=[]
        minimums=[]
        for i,b in enumerate(beats):
            d=b.get('duration') if isinstance(b.get('duration'),dict) else {}
            raw=max(1,_as_int(d.get('value'),minimum))
            raw_durations.append(raw)
            # duration must remain longer than its overlap and leave room for action/settle.
            minimums.append(max(minimum, overlaps[i]+2, 3))

        desired_sum=int(target_duration_frames)+sum(overlaps[:-1])
        effective=sum(raw_durations)-sum(overlaps[:-1])
        if effective==int(target_duration_frames) and all(raw_durations[i]>=minimums[i] for i in range(len(beats))):
            durations=list(raw_durations)
        else:
            durations=_allocate_durations(raw_durations,minimums,desired_sum)

        expected_start=0
        for i,b in enumerate(beats):
            old_dur=max(1,raw_durations[i])
            dur=max(minimums[i],int(durations[i]))
            ov=min(overlaps[i],max(0,dur-2)) if i<len(beats)-1 else 0
            b['overlap_to_next_frames']=ov
            b['start']={'value':expected_start,'rate':int(project_rate)}
            b['duration']={'value':dur,'rate':int(project_rate)}

            action=b.get('action_frame'); settle=b.get('settle_frame')
            if type(action) is int and type(settle) is int and 0<=action<settle:
                # Preserve their relative authored positions even when the original markers
                # extended beyond the beat due to arithmetic drift.
                denom=max(old_dur,settle+1,action+2,2)
                a=int(round((action/denom)*dur))
                s=int(round((settle/denom)*dur))
                a=max(0,min(a,dur-2))
                s=max(a+1,min(s,dur-1))
                b['action_frame']=a
                b['settle_frame']=s

            # Stillness cannot exceed the executable settled tail. Keep the model's
            # intent but clamp impossible bookkeeping.
            if type(b.get('stillness_frames')) is int and type(b.get('settle_frame')) is int:
                tail=max(0,dur-b['settle_frame'])
                b['stillness_frames']=max(0,min(b['stillness_frames'],tail))
            expected_start=expected_start+dur-(ov if i<len(beats)-1 else 0)

        # Round-off in weighted allocation should already be exact; correct only a final
        # one-frame arithmetic residue, never a semantic field.
        residue=int(target_duration_frames)-expected_start
        if residue and beats:
            last=beats[-1]
            dur=int(last['duration']['value'])+residue
            if dur>=minimum and type(last.get('settle_frame')) is int and last['settle_frame']<dur:
                last['duration']={'value':dur,'rate':int(project_rate)}

        if beats and type(c.get('final_payoff_hold_frames')) is int and type(beats[-1].get('settle_frame')) is int:
            tail=max(0,int(beats[-1]['duration']['value'])-beats[-1]['settle_frame'])
            c['final_payoff_hold_frames']=max(0,min(c['final_payoff_hold_frames'],tail))
    return out

def validate_editorial_candidate(c:Dict[str,Any], beat_ids:Set[str])->Dict[str,Any]:
    reject_geometry_code_authority(c)
    require_exact_keys(c,{"candidate_id","editorial_thesis","project_rate","target_duration_frames","rhythm_profile","peak_budget","beats","final_payoff_hold_frames","risk_notes"},label="editorial_candidate")
    rate=c["project_rate"]; total=c["target_duration_frames"]
    if type(rate) is not int or rate not in {24,25,30,48,50,60}: raise ContractViolation("unsupported editorial rate")
    if type(total) is not int or total<rate*3: raise ContractViolation("target duration too short/invalid")
    if type(c["peak_budget"]) is not int or c["peak_budget"]<1: raise ContractViolation("peak budget required")
    if type(c["final_payoff_hold_frames"]) is not int or c["final_payoff_hold_frames"]<0: raise ContractViolation("invalid final payoff hold")
    beats=c["beats"]
    if not isinstance(beats,list) or len(beats)!=len(beat_ids): raise ContractViolation("editorial execution body requires exactly one event per story beat")
    seen=set(); event_ids=set(); peaks=0; expected_start=0; durations=[]
    for i,b in enumerate(beats):
        require_exact_keys(b,{"beat_id","role","start","duration","action_frame","settle_frame","energy","stillness_frames","overlap_to_next_frames","transition","duration_rationale"},{"event_id"},label="editorial_event")
        bid=b["beat_id"]
        if bid not in beat_ids: raise ContractViolation("editorial event references unknown story beat")
        if bid in seen: raise ContractViolation("editorial execution body supports exactly one event per story beat")
        seen.add(bid)
        event_id=str(b.get("event_id") or f"{bid}.edit.{i+1}")
        if not event_id.strip() or event_id in event_ids: raise ContractViolation("editorial event_id must be unique")
        event_ids.add(event_id)
        if not isinstance(b["role"],str) or not b["role"].strip() or b["energy"] not in ENERGY or b["transition"] not in TRANSITIONS: raise ContractViolation("invalid editorial execution vocabulary")
        start=validate_rational_time(b["start"],f"{bid}.start"); dur=validate_rational_time(b["duration"],f"{bid}.duration")
        if start["rate"]!=rate or dur["rate"]!=rate: raise ContractViolation("mixed editorial rate")
        if start["value"]!=expected_start: raise ContractViolation("editorial timeline has gap/overlap accounting error")
        if dur["value"]<max(6,rate//4): raise ContractViolation("beat duration below minimum")
        if type(b["action_frame"]) is not int or type(b["settle_frame"]) is not int: raise ContractViolation("action/settle frames must be integers")
        if not (0<=b["action_frame"]<b["settle_frame"]<dur["value"]): raise ContractViolation("action/settle outside beat")
        if type(b["stillness_frames"]) is not int or b["stillness_frames"]<0: raise ContractViolation("invalid stillness")
        if type(b["overlap_to_next_frames"]) is not int or b["overlap_to_next_frames"]<0 or b["overlap_to_next_frames"]>=dur["value"]: raise ContractViolation("invalid overlap")
        if not str(b["duration_rationale"]).strip(): raise ContractViolation("duration rationale required")
        if b["energy"]=="PEAK": peaks+=1
        durations.append(dur["value"])
        expected_start=start["value"]+dur["value"]-(b["overlap_to_next_frames"] if i<len(beats)-1 else 0)
    if seen!=beat_ids: raise ContractViolation("editorial missing beats")
    if expected_start!=total: raise ContractViolation(f"editorial total mismatch: schedule={expected_start} target={total}")
    if peaks>c["peak_budget"]: raise ContractViolation("kinetic peak budget exceeded")
    if c["final_payoff_hold_frames"]>beats[-1]["duration"]["value"]-beats[-1]["settle_frame"]: raise ContractViolation("final payoff hold exceeds settled tail")
    # Equal subdivision is legal only when explicitly chosen as the rhythm profile.
    if len(set(durations))==1 and c["rhythm_profile"]!="EVENLY_METERED_BY_INTENT":
        raise ContractViolation("equal beat subdivision requires explicit editorial intent")
    return deepcopy(c)


def _rhythm_fingerprint(c:Dict[str,Any]):
    return tuple((b["duration"]["value"],b["energy"],b["stillness_frames"],b["overlap_to_next_frames"],b["role"]) for b in c["beats"])


def validate_editorial_output(payload:Dict[str,Any],beat_ids:Set[str],*,repair_mode:bool=False)->List[Dict[str,Any]]:
    reject_geometry_code_authority(payload)
    require_exact_keys(payload,{"candidates"},{"director_notes"},label="editorial_output")
    cs=payload["candidates"]
    if not isinstance(cs,list): raise ContractViolation("editorial candidates must be an array")
    if repair_mode:
        if len(cs)!=1: raise ContractViolation("editorial surgical repair must return exactly one candidate")
    elif len(cs)<2: raise ContractViolation("editorial requires genuine candidate competition")
    out=[]; ids=set(); fps=set()
    for c in cs:
        v=validate_editorial_candidate(c,beat_ids)
        if v["candidate_id"] in ids: raise ContractViolation("duplicate editorial candidate id")
        ids.add(v["candidate_id"]); fps.add(_rhythm_fingerprint(v)); out.append(v)
    if not repair_mode:
        if len(fps)<2: raise ContractViolation("editorial candidates are not materially different")
        assert_semantic_candidate_diversity(out,label="editorial_contracts candidates")
    return out


def pacing_signature(c:Dict[str,Any])->str:
    return "|".join(f"{b['role']}:{b['duration']['value']}:{b['energy']}:{b['stillness_frames']}:{b['overlap_to_next_frames']}" for b in c["beats"])
