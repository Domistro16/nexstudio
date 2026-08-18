from __future__ import annotations
from copy import deepcopy
from typing import Any,Dict
from .provider import CreativeModelProvider
from .contracts import validate_producer_output
from .review_governance import calibrate_review, release_decision_law

class P45ExecutiveProducer:
    def __init__(self,provider:CreativeModelProvider): self.provider=provider
    def review_cinema(self,production_id:str,brief:Dict[str,Any],story:Dict[str,Any],visual:Dict[str,Any],art:Dict[str,Any],cinema:Dict[str,Any])->Dict[str,Any]:
        mechanical=[]
        for s in cinema["shots"]:
            atom=s["camera_atom"]
            if atom["atom"]!="HOLD" and not atom["motivation"].strip(): mechanical.append({"code":"UNMOTIVATED_CAMERA","beat_id":s["beat_id"]})
        req={"production_id":production_id,"brief":deepcopy(brief),"film_thesis":deepcopy(story["film_thesis"]),"visual_concept":deepcopy(visual),"art_direction":deepcopy(art),"cinema_candidate":deepcopy(cinema),"mechanical_preflight":mechanical,"instruction":{"role":"Independent Executive Producer — Cinematography Review","release_decision_law":release_decision_law("CINEMATOGRAPHY"),"questions":["Does each shot direct attention to meaning?","Is HOLD used when movement adds nothing?","Are scale/angle/depth choices motivated?","Does the camera preserve continuity of attention?","Is there gratuitous camera activity?"]}}
        r=validate_producer_output(self.provider.complete("cinematography_review",req))
        if mechanical and r["verdict"]=="ACCEPT":
            r=deepcopy(r); r["verdict"]="REVISE"
            mechanical_blockers=[]
            for issue in mechanical:
                item=deepcopy(issue); item["blocking"]=True; mechanical_blockers.append(item)
            r["issues"]=[*mechanical_blockers,*r["issues"]]; r["revision_brief"]="Remove or motivate gratuitous camera movement."; r["commercial_confidence"]="LOW"
        return validate_producer_output(calibrate_review(r,stage="CINEMATOGRAPHY"))
    def review_editorial(self,production_id:str,brief:Dict[str,Any],story:Dict[str,Any],cinema:Dict[str,Any],editorial:Dict[str,Any],timeline:Dict[str,Any])->Dict[str,Any]:
        req={"production_id":production_id,"brief":deepcopy(brief),"film_thesis":deepcopy(story["film_thesis"]),"cinematography":deepcopy(cinema),"editorial_candidate":deepcopy(editorial),"timeline":deepcopy(timeline),"instruction":{"role":"Independent Executive Producer — Editorial Review","release_decision_law":release_decision_law("EDITORIAL_RHYTHM"),"questions":["Does pacing reflect narrative function rather than equal subdivision?","Are kinetic peaks scarce enough to feel meaningful?","Are holds actual stillness?","Does escalation breathe and compress deliberately?","Does the final payoff get enough settled time?"]}}
        r=validate_producer_output(self.provider.complete("editorial_review",req))
        return validate_producer_output(calibrate_review(r,stage="EDITORIAL_RHYTHM"))
    def review_temporal_storyboard(self,production_id:str,brief:Dict[str,Any],story:Dict[str,Any],board:Dict[str,Any],gate_report:Dict[str,Any])->Dict[str,Any]:
        req={"production_id":production_id,"brief":deepcopy(brief),"film_thesis":deepcopy(story["film_thesis"]),"temporal_storyboard":deepcopy(board),"mechanical_gate":deepcopy(gate_report),"instruction":{"role":"Independent Executive Producer — Canonical Temporal Storyboard Review","release_decision_law":release_decision_law("TEMPORAL_STORYBOARD"),"questions":["Can the whole film be judged coherently before animation?","Does every camera move have a reason?","Does pacing escalate rather than serialize?","Are strong settled frames given enough hold?","Are Motion and Sound still correctly marked unresolved until their directors act?"]}}
        r=validate_producer_output(self.provider.complete("temporal_storyboard_review",req))
        return validate_producer_output(calibrate_review(r,stage="TEMPORAL_STORYBOARD"))
