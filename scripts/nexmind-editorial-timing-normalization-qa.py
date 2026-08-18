from __future__ import annotations
import copy, json, pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vendor'/'nexmind-god-mode-p8'/'src'))
from nexmind_god_mode.editorial_contracts import normalize_editorial_output, validate_editorial_output, ContractViolation

RATE=30; TOTAL=900; IDS=['B1','B2','B3']

def base():
    return {'candidates':[{
        'candidate_id':'E1','editorial_thesis':'Pressure yields to human calm through asymmetric pacing.',
        'project_rate':24,'target_duration_frames':777,'rhythm_profile':'ASYMMETRIC_HUMAN_RELEASE','peak_budget':2,
        'beats':[
            {'beat_id':'B1','role':'PRESSURE','start':{'value':17,'rate':24},'duration':{'value':220,'rate':24},'action_frame':240,'settle_frame':280,'energy':'HIGH','stillness_frames':40,'overlap_to_next_frames':20,'transition':'CARRY','duration_rationale':'Give pressure enough space to register before the adjustment.'},
            {'beat_id':'B2','role':'RELEASE','start':{'value':141,'rate':24},'duration':{'value':420,'rate':24},'action_frame':430,'settle_frame':490,'energy':'PEAK','stillness_frames':55,'overlap_to_next_frames':15,'transition':'MATCH_CUT','duration_rationale':'Make the control consequence the longest and most legible passage.'},
            {'beat_id':'B3','role':'PAYOFF','start':{'value':301,'rate':24},'duration':{'value':260,'rate':24},'action_frame':270,'settle_frame':310,'energy':'LOW','stillness_frames':90,'overlap_to_next_frames':99,'transition':'HOLD_THROUGH','duration_rationale':'Protect the human payoff with a settled tail.'},
        ],
        'final_payoff_hold_frames':999,'risk_notes':[]
    }]}

checks=[]
def add(name,ok,detail=''):checks.append({'name':name,'status':'PASS' if ok else 'FAIL','detail':str(detail)})

def rejects(payload):
    try:
        n=normalize_editorial_output(payload,IDS,target_duration_frames=TOTAL,project_rate=RATE)
        validate_editorial_output(n,set(IDS),repair_mode=True)
        return False
    except ContractViolation:
        return True

def run():
    raw=base(); n=normalize_editorial_output(raw,IDS,target_duration_frames=TOTAL,project_rate=RATE); c=n['candidates'][0]; beats=c['beats']
    validated=validate_editorial_output(n,set(IDS),repair_mode=True)[0]
    add('Canonical project rate is runtime-owned',c['project_rate']==RATE and all(b['start']['rate']==RATE and b['duration']['rate']==RATE for b in beats),c)
    add('Canonical target duration is runtime-owned',c['target_duration_frames']==TOTAL,c['target_duration_frames'])
    expected=0; contiguous=True
    for i,b in enumerate(beats):
        contiguous &= b['start']['value']==expected
        expected += b['duration']['value']-(b['overlap_to_next_frames'] if i<len(beats)-1 else 0)
    add('Starts are derived from duration/overlap accounting',contiguous and expected==TOTAL,[(b['start']['value'],b['duration']['value'],b['overlap_to_next_frames']) for b in beats])
    add('Out-of-beat markers are mapped inside each beat without reversing intent',all(0<=b['action_frame']<b['settle_frame']<b['duration']['value'] for b in beats),[(b['action_frame'],b['settle_frame'],b['duration']['value']) for b in beats])
    add('Last-beat overlap is deterministically removed',beats[-1]['overlap_to_next_frames']==0,beats[-1]['overlap_to_next_frames'])
    add('Final payoff hold is clamped to executable settled tail',0<=c['final_payoff_hold_frames']<=beats[-1]['duration']['value']-beats[-1]['settle_frame'],c['final_payoff_hold_frames'])
    add('Relative duration emphasis is preserved',beats[1]['duration']['value']>beats[2]['duration']['value']>beats[0]['duration']['value'],[b['duration']['value'] for b in beats])
    shuffled=base();shuffled['candidates'][0]['beats']=[shuffled['candidates'][0]['beats'][2],shuffled['candidates'][0]['beats'][0],shuffled['candidates'][0]['beats'][1]]
    sn=normalize_editorial_output(shuffled,IDS,target_duration_frames=TOTAL,project_rate=RATE)
    add('Beat order is canonicalized from accepted Story order',[b['beat_id'] for b in sn['candidates'][0]['beats']]==IDS,[b['beat_id'] for b in sn['candidates'][0]['beats']])
    missing=base();missing['candidates'][0]['beats']=missing['candidates'][0]['beats'][:2]
    add('Missing beat remains a hard contract failure',rejects(missing))
    dup=base();dup['candidates'][0]['beats'][2]['beat_id']='B2'
    add('Duplicate beat remains a hard contract failure',rejects(dup))
    badtx=base();badtx['candidates'][0]['beats'][1]['transition']='MAGIC_WIPE'
    add('Illegal transition vocabulary remains a hard contract failure',rejects(badtx))
    blank=base();blank['candidates'][0]['beats'][1]['duration_rationale']=''
    add('Empty duration rationale remains a hard contract failure',rejects(blank))
    reversed_markers=base();reversed_markers['candidates'][0]['beats'][1]['action_frame']=400;reversed_markers['candidates'][0]['beats'][1]['settle_frame']=200
    add('Reversed action-settle creative intent remains a hard contract failure',rejects(reversed_markers))
    failed=[x for x in checks if x['status']!='PASS']
    out={'schema':'NexMindEditorialTimingNormalizationQAV1','status':'PASS' if not failed else 'FAIL','passed':len(checks)-len(failed),'total':len(checks),'failed':failed,'checks':checks}
    print(json.dumps(out,indent=2));return 0 if not failed else 1

if __name__=='__main__': raise SystemExit(run())
