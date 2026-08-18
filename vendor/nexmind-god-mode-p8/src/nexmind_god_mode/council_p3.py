from __future__ import annotations
from copy import deepcopy
from typing import Any,Dict
from concurrent.futures import ThreadPoolExecutor
import os
from .p0_kernel import ProposalRef
from .contracts import ContractViolation
from .showrunner_p3 import NexMindSupremeShowrunnerP3
from .art_director import ArtDirector
from .illustration_form_resolver import IllustrationFormResolver
from .p3_producer import P3ExecutiveProducer
from .art_showrunner_reasoner import ArtShowrunnerDecisionIntelligence
from .storyboard_compiler import StoryboardCompiler


def _review_parallelism(count:int)->int:
    try: value=int(os.getenv("NEXMIND_REVIEW_PARALLELISM","3") or 3)
    except Exception: value=3
    return max(1,min(count,max(1,min(6,value))))

def _parallel_map(items,fn):
    items=list(items); workers=_review_parallelism(len(items))
    if len(items)<=1 or workers<=1: return [fn(x) for x in items]
    with ThreadPoolExecutor(max_workers=workers,thread_name_prefix="nexmind-art-review") as pool:
        futures=[pool.submit(fn,x) for x in items]
        return [f.result() for f in futures]

class CreativeCouncilP3:
    def __init__(self,showrunner:NexMindSupremeShowrunnerP3,art:ArtDirector,resolver:IllustrationFormResolver,producer:P3ExecutiveProducer,selector:ArtShowrunnerDecisionIntelligence,storyboard:StoryboardCompiler):
        self.showrunner=showrunner; self.art=art; self.resolver=resolver; self.producer=producer; self.selector=selector; self.storyboard=storyboard

    def develop_art(self,story:Dict[str,Any],visual:Dict[str,Any])->Dict[str,Any]:
        candidates=self.art.propose(self.showrunner.state["production_id"],self.showrunner.state["brief"],story,visual,self.showrunner.state["creative_doctrine"],self.showrunner.state["capability_graph"])
        prepared=[]
        for c in candidates:
            form=self.resolver.resolve(c["form_request"],self.showrunner.state["capability_graph"])
            beat_states=c["beat_art"]
            proposal_payload={
                "representation":c["form_request"]["representation"],
                "visual_thesis":c["art_thesis"],
                "hero_kind":c["hero"]["semantic_ref"],
                "transformation":f"{beat_states[0]['settled_visual_state']} -> {beat_states[-1]['settled_visual_state']}",
                "camera_idea":visual["camera_idea"],
                "art_direction":deepcopy(c),
                "form_resolution":deepcopy(form),
            }
            proposal_id=c["candidate_id"]
            if proposal_id in self.showrunner.state.get("proposals",{}).get("ArtDirector",{}): proposal_id=f"r{self.showrunner.state['revision']}:{proposal_id}"
            ref=self.showrunner.submit_proposal("ArtDirector",proposal_id,proposal_payload)
            prepared.append((c,form,ref))
        def review_one(item):
            c,form,ref=item
            review=self.producer.review_art(self.showrunner.state["production_id"],self.showrunner.state["brief"],story,visual,c,form)
            return c,form,ref,review
        reviewed=[]
        for c,form,ref,review in _parallel_map(prepared,review_one):
            token=self.showrunner.register_p3_review("art_direction",ref,review)
            reviewed.append({"candidate":c,"form_resolution":form,"proposal":ref,"review":review,"review_id":token})
        revision_context=self.showrunner.state.get("brief",{}).get("autonomous_revision_context") or {}
        surgical_repair=revision_context.get("department")=="ART_DIRECTION" and revision_context.get("repair_mode")!="MATERIAL_STRATEGY_REPLAN" and len(reviewed)==1
        diversity={"meaningfully_diverse":True,"surgical_repair":True} if surgical_repair else self.showrunner.candidate_diversity("ArtDirector",[x["proposal"].proposal_id for x in reviewed])
        return {"reviewed":reviewed,"diversity":diversity}

    def select_art(self,story:Dict[str,Any],visual:Dict[str,Any],art_result:Dict[str,Any])->Dict[str,Any]:
        accepted=[x for x in art_result["reviewed"] if x["review"]["verdict"]=="ACCEPT"]
        revision_context=self.showrunner.state.get("brief",{}).get("autonomous_revision_context") or {}
        surgical_repair=revision_context.get("department")=="ART_DIRECTION" and revision_context.get("repair_mode")!="MATERIAL_STRATEGY_REPLAN" and len(art_result["reviewed"])==1
        if surgical_repair:
            if len(accepted)!=1: raise RuntimeError("surgical Art repair requires exactly one Producer-accepted candidate")
            item=accepted[0]
            selection={"selected_candidate_id":item["candidate"]["candidate_id"],"why":"Producer-accepted surgical repair of the selected Art anchor.","tradeoffs":[],"rejected_alternatives":[],"notes":"Candidate competition is intentionally not reopened during bounded Art repair."}
            committed=self.showrunner.commit_p3_reviewed("art_direction",item["proposal"],item["review_id"])
            return {"selection":selection,"committed":committed,"candidate":item["candidate"],"form_resolution":item["form_resolution"]}
        if len(accepted)==1:
            item=accepted[0]
            selection={"selected_candidate_id":item["candidate"]["candidate_id"],"why":"Only Producer-accepted Art candidate; no redundant selector call required.","tradeoffs":[],"rejected_alternatives":[],"notes":"Deterministic single-accepted commit."}
        else:
            selection=self.selector.select(self.showrunner.state["production_id"],self.showrunner.state["brief"],story,visual,art_result["reviewed"])
            item=next((x for x in accepted if x["candidate"]["candidate_id"]==selection["selected_candidate_id"]),None)
            if item is None: raise ContractViolation("selected Art candidate is missing or not Producer-accepted")
        committed=self.showrunner.commit_p3_reviewed("art_direction",item["proposal"],item["review_id"],require_diversity_from=[x["proposal"].proposal_id for x in art_result["reviewed"]])
        return {"selection":selection,"committed":committed,"candidate":item["candidate"],"form_resolution":item["form_resolution"]}

    def compile_and_review_storyboard(self,story:Dict[str,Any],visual:Dict[str,Any],selected_art:Dict[str,Any],*,vo_spans:Dict[str,Any]|None=None)->Dict[str,Any]:
        board=self.storyboard.compile(story,visual,selected_art["candidate"],selected_art["form_resolution"],vo_spans=vo_spans)
        gate=self.storyboard.gate(board)
        ref=self.showrunner.submit_proposal("StoryboardCompiler",f"storyboard-r{self.showrunner.state['revision']}",{"representation":"STORYBOARD_REHEARSAL","visual_thesis":story["film_thesis"]["central_argument"],"hero_kind":selected_art["candidate"]["hero"]["semantic_ref"],"transformation":"compiled key-state progression across directed beats","camera_idea":visual["camera_idea"],"storyboard":deepcopy(board)})
        review=self.producer.review_storyboard(self.showrunner.state["production_id"],self.showrunner.state["brief"],story,visual,selected_art["candidate"],board,gate)
        token=self.showrunner.register_p3_review("storyboard",ref,review)
        if review["verdict"]=="ACCEPT": self.showrunner.commit_p3_reviewed("storyboard",ref,token)
        return {"board":board,"gate":gate,"proposal":ref,"review":review,"review_id":token}
