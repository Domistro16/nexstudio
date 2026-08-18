from __future__ import annotations
from copy import deepcopy
from typing import Any,Dict
class PerformanceStoryboardCompiler:
    def compile(self,temporal_board:Dict[str,Any],motion:Dict[str,Any])->Dict[str,Any]:
        out=deepcopy(temporal_board); out['schema']='NexMindCanonicalPerformanceStoryboardV3'; by={}
        for a in motion['actions']: by.setdefault(a['beat_id'],[]).append(deepcopy(a))
        for b in out['beats']:
            b['motion_plan_status']='DIRECTED_MOTION_PERFORMANCE'; b['motion_actions']=by.get(b['beat_id'],[])
            b['sound_plan_status']='UNRESOLVED_SOUND_DIRECTOR'
        out['motion_candidate_id']=motion['candidate_id']; out['motion_executable']=motion['executable']; out['unresolved_departments']=['sound_direction','final_producer']; return out
    def gate(self,board):
        bad=[b['beat_id'] for b in board['beats'] if b.get('motion_plan_status')!='DIRECTED_MOTION_PERFORMANCE']
        return {'status':'PASS' if not bad and board.get('motion_executable') else 'BLOCKED','missing_motion_beats':bad,'sound_unresolved':True}
