from __future__ import annotations
from copy import deepcopy
class SoundStoryboardCompiler:
    def compile(self,performance_board,sound):
        out=deepcopy(performance_board);out['schema']='NexMindCanonicalSoundStoryboardV4';by={}
        for e in sound['events']:by.setdefault(e['beat_id'],[]).append(deepcopy(e))
        summaries={x['beat_id']:x for x in sound['beat_sound_summary']}
        for b in out['beats']:
            b['sound_plan_status']='DIRECTED_SOUND';b['sound_events']=by.get(b['beat_id'],[]);b['sound_summary']=deepcopy(summaries.get(b['beat_id'],{}))
        out['sound_candidate_id']=sound['candidate_id'];out['sound_direction']={k:deepcopy(sound[k]) for k in ('sound_thesis','narration_strategy','music_strategy','motifs','mix_intent','silence_strategy','risk_notes') if k in sound};out['unresolved_departments']=['final_producer'];return out
    def gate(self,board):
        bad=[b['beat_id'] for b in board['beats'] if b.get('sound_plan_status')!='DIRECTED_SOUND'];return {'status':'PASS' if not bad else 'BLOCKED','missing_sound_beats':bad,'final_producer_unresolved':True}
