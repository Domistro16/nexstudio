from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

PRIOR_SLOTS=(
    'film_thesis','visual_concept','art_direction','storyboard','cinematography',
    'editorial_rhythm','storyboard_temporal','motion_performance','sound_direction'
)

class FinalCriticEnsemble:
    """Deterministic hard-gate evidence. Taste stays with the independent model/human critics."""

    def evaluate(self, state: Dict[str, Any], final_board: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        decisions=state.get('decisions',{})
        gates=[]
        missing=[x for x in PRIOR_SLOTS if x not in decisions]
        gates.append(self._gate('DEPARTMENT_COMPLETENESS', not missing, 'ALL_CREATIVE_DEPARTMENTS_COMMITTED' if not missing else 'MISSING_DEPARTMENTS', missing or list(PRIOR_SLOTS)))

        evidence=state.get('evidence_ledger',[]) or []
        bad=[x.get('claim_id','?') for x in evidence if x.get('status') in {'UNRESOLVED','DISPUTED'}]
        gates.append(self._gate('EVIDENCE_TRUTH', not bad, 'EVIDENCE_LEDGER_CLEAN' if not bad else 'UNRESOLVED_OR_DISPUTED_EVIDENCE', bad or [f'{len(evidence)} evidence records']))

        thesis=self._payload(decisions.get('film_thesis'))
        coherent=bool(thesis) and self._contains_nonempty(thesis, ('central_argument','final_payoff'))
        gates.append(self._gate('STORY_COHERENCE', coherent, 'FILM_THESIS_PRESENT' if coherent else 'FILM_THESIS_INCOMPLETE', ['central_argument','final_payoff']))

        visual=self._payload(decisions.get('visual_concept'))
        visual_ok=bool(visual) and self._semantic_length(visual) >= 4
        gates.append(self._gate('STRUCTURAL_VISUAL_INTENT', visual_ok, 'VISUAL_ARGUMENT_PRESENT' if visual_ok else 'VISUAL_ARGUMENT_WEAK_OR_MISSING', [f'semantic_fields={self._semantic_length(visual)}']))

        art=self._payload(decisions.get('art_direction'))
        art_ok=bool(art) and not self._contains_status(art, {'UNRESOLVED','UNSUPPORTED','FAIL_CLOSED'})
        gates.append(self._gate('STRUCTURAL_ART_DIRECTION', art_ok, 'ART_DIRECTION_RESOLVED' if art_ok else 'ART_DIRECTION_GAP', []))

        cinema=self._payload(decisions.get('cinematography'))
        cinema_ok=bool(cinema) and not self._contains_status(cinema, {'UNRESOLVED','UNSUPPORTED','FAIL_CLOSED'})
        gates.append(self._gate('STRUCTURAL_CINEMATOGRAPHY_DIRECTION', cinema_ok, 'CINEMATOGRAPHY_RESOLVED' if cinema_ok else 'CINEMATOGRAPHY_GAP', []))

        editorial=self._payload(decisions.get('editorial_rhythm'))
        editorial_ok=bool(editorial) and not self._contains_status(editorial, {'UNRESOLVED','UNSUPPORTED','FAIL_CLOSED'})
        gates.append(self._gate('STRUCTURAL_EDITORIAL_DIRECTION', editorial_ok, 'EDITORIAL_RESOLVED' if editorial_ok else 'EDITORIAL_GAP', []))

        motion=self._payload(decisions.get('motion_performance'))
        motion_ok=bool(motion) and not self._contains_status(motion, {'UNRESOLVED','UNSUPPORTED','FAIL_CLOSED','CAPABILITY_GAP'})
        gates.append(self._gate('STRUCTURAL_MOTION_EXECUTABILITY', motion_ok, 'MOTION_EXECUTABLE' if motion_ok else 'MOTION_CAPABILITY_GAP', []))

        sound=self._payload(decisions.get('sound_direction'))
        sound_ok=bool(sound) and not self._contains_status(sound, {'UNRESOLVED','UNSUPPORTED','RIGHTS_UNSAFE','RESOURCE_GAP'})
        gates.append(self._gate('STRUCTURAL_SOUND_RIGHTS_AND_FUNCTION', sound_ok, 'SOUND_RESOLVED_RIGHTS_SAFE' if sound_ok else 'SOUND_RESOURCE_OR_RIGHTS_GAP', []))

        board=final_board or {}
        payoff_ok=self._final_payoff_present(board, thesis)
        gates.append(self._gate('FINAL_PAYOFF', payoff_ok, 'FINAL_PAYOFF_PRESENT' if payoff_ok else 'FINAL_PAYOFF_MISSING', []))

        open_veto=[x for x in state.get('quality_ledger',[]) if x.get('status')=='OPEN']
        body_bad=[x for x in state.get('body_validations',[]) if x.get('revision')==state.get('revision') and x.get('verdict') in {'VETO','FAIL_CLOSED'}]
        gates.append(self._gate('TECHNICAL_BODY_VETOES', not open_veto and not body_bad, 'NO_OPEN_BODY_VETO' if not open_veto and not body_bad else 'OPEN_BODY_VETO', [x.get('service','?') for x in body_bad]+[x.get('service','?') for x in open_veto]))
        return gates

    @staticmethod
    def _gate(dimension:str, ok:bool, code:str, evidence:list)->Dict[str,Any]:
        return {'dimension':dimension,'status':'PASS' if ok else 'FAIL','code':code,'evidence':deepcopy(evidence)}

    @staticmethod
    def _payload(decision: Dict[str, Any] | None)->Dict[str,Any]:
        if not decision: return {}
        p=decision.get('payload',decision)
        if not isinstance(p,dict): return {}
        # Department wrappers are intentionally semantic. Prefer nested specialist payload where present.
        for k in ('sound_direction','motion_performance','editorial_rhythm','cinematography','art_direction','visual_concept','film_thesis'):
            if isinstance(p.get(k),dict): return p[k]
        return p

    @staticmethod
    def _contains_nonempty(obj:Dict[str,Any], keys:tuple[str,...])->bool:
        text=str(obj).lower()
        return all((k in obj and bool(str(obj[k]).strip())) or k.lower() in text for k in keys)

    @staticmethod
    def _semantic_length(obj:Dict[str,Any])->int:
        if not isinstance(obj,dict): return 0
        return sum(1 for v in obj.values() if (isinstance(v,str) and len(v.strip())>=5) or isinstance(v,(list,dict)))

    @classmethod
    def _contains_status(cls,obj:Any,bad:set[str])->bool:
        if isinstance(obj,dict):
            for k,v in obj.items():
                if str(k).lower() in {'status','code','capability_status','resource_status'} and str(v).upper() in bad:return True
                if cls._contains_status(v,bad):return True
        elif isinstance(obj,list): return any(cls._contains_status(x,bad) for x in obj)
        return False

    @staticmethod
    def _final_payoff_present(board:Dict[str,Any], thesis:Dict[str,Any])->bool:
        if thesis and str(thesis.get('final_payoff','')).strip():
            if not board:return True
            beats=board.get('beats',[]) or []
            return bool(beats and (beats[-1].get('sound_plan_status')=='DIRECTED_SOUND' or beats[-1].get('settled_state') or beats[-1].get('final_payoff')))
        return False
