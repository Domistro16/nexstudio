from __future__ import annotations
import copy,hashlib,json
from typing import Any,Dict,Iterable,Optional
from .showrunner_p3 import NexMindSupremeShowrunnerP3
from .p0_kernel import NexMindSupremeShowrunner, ProposalRef, AuthorityViolation, CandidateError
from .showrunner_p2 import ProducerGateError

P45_SLOTS={"cinematography","editorial_rhythm","storyboard_temporal"}
def h(o): return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

class NexMindSupremeShowrunnerP45(NexMindSupremeShowrunnerP3):
    FINAL_CREATIVE_DEPARTMENTS=("film_thesis","visual_concept","art_direction","storyboard","cinematography","editorial_rhythm","storyboard_temporal","motion_performance","sound_direction","final_producer")
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw); self.state["p45_schema"]="NexMindSupremeShowrunnerP45StateV1"; self.state["p45_reviews"]=[]; self.state["p45_gate"]={"status":"OPEN"}
    def commit_decision(self,slot,proposal,*,require_diversity_from=None):
        if slot in P45_SLOTS: raise AuthorityViolation(f"{slot} is Producer-governed in P4/P5")
        return super().commit_decision(slot,proposal,require_diversity_from=require_diversity_from)
    def register_p45_review(self,slot:str,proposal:ProposalRef,review:Dict[str,Any])->str:
        if slot not in P45_SLOTS: raise ProducerGateError("unsupported P45 slot")
        rec=self.state["proposals"].get(proposal.department,{}).get(proposal.proposal_id)
        if not rec or rec["revision"]!=self.state["revision"]: raise CandidateError("review target stale/missing")
        rid=h({"production_id":self.state["production_id"],"revision":self.state["revision"],"slot":slot,"department":proposal.department,"proposal_id":proposal.proposal_id,"payload_hash":h(rec["payload"]),"review":review})
        self.state["p45_reviews"].append({"review_id":rid,"slot":slot,"department":proposal.department,"proposal_id":proposal.proposal_id,"payload_hash":h(rec["payload"]),"review":copy.deepcopy(review),"revision":self.state["revision"]})
        return rid
    def commit_p45_reviewed(self,slot:str,proposal:ProposalRef,review_id:str,*,require_diversity_from:Optional[Iterable[str]]=None):
        ms=[x for x in self.state["p45_reviews"] if x["review_id"]==review_id]
        if len(ms)!=1: raise ProducerGateError("P45 review token not found")
        rr=ms[0]; rec=self.state["proposals"].get(proposal.department,{}).get(proposal.proposal_id)
        if rr["slot"]!=slot or rr["proposal_id"]!=proposal.proposal_id or rr["department"]!=proposal.department: raise ProducerGateError("P45 review token mismatch")
        if rr["revision"]!=self.state["revision"] or not rec or rr["payload_hash"]!=h(rec["payload"]): raise ProducerGateError("P45 review stale/tampered")
        if rr["review"].get("verdict")!="ACCEPT": raise ProducerGateError("P45 work not Producer accepted")
        if slot=="storyboard_temporal" and not all(x in self.state["decisions"] for x in ("cinematography","editorial_rhythm","storyboard")):
            raise ProducerGateError("canonical temporal storyboard requires key-state storyboard + cinema + editorial")
        out=NexMindSupremeShowrunner.commit_decision(self,slot,proposal,require_diversity_from=require_diversity_from)
        self.state["decisions"][slot]["producer_review_id"]=review_id
        return out
    def p45_ready_gate(self):
        self.p3_ready_gate(); missing=[x for x in P45_SLOTS if x not in self.state["decisions"]]
        if missing: raise ProducerGateError({"missing_p45":missing})
        self.state["p45_gate"]={"status":"PASS","revision":self.state["revision"]}; return copy.deepcopy(self.state["p45_gate"])
    def creative_lock(self):
        missing=[x for x in self.FINAL_CREATIVE_DEPARTMENTS if x not in self.state["decisions"]]
        if missing: raise ProducerGateError({"status":"FINAL_CREATIVE_LOCK_BLOCKED_INCOMPLETE_BRAIN","missing_decisions":missing})
        return NexMindSupremeShowrunner.creative_lock(self)
