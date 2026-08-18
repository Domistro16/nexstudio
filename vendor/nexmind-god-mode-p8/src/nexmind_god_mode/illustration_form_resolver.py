from __future__ import annotations
import json,re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable
from .art_contracts import validate_form_request

ILLUSTRATION_REPS={"AUTHORED_ILLUSTRATION","ASSEMBLED_ILLUSTRATION"}

def toks(s:str): return {x for x in re.findall(r"[a-z0-9]+",s.lower()) if len(x)>2}

class IllustrationFormResolver:
    """Generic resolver over semantic capability records. Never silently downgrades illustration intent to diagram."""
    def __init__(self,index:Dict[str,Any]):
        self.index=deepcopy(index); self.records=list(index.get("records",[]))
    @classmethod
    def from_file(cls,path:str|Path): return cls(json.loads(Path(path).read_text(encoding="utf-8")))
    def resolve(self,request:Dict[str,Any], capability_graph:Dict[str,Any]|None=None)->Dict[str,Any]:
        q=validate_form_request(request); cap=capability_graph or {}
        if q["representation"] not in ILLUSTRATION_REPS:
            return {"status":"NOT_APPLICABLE","representation":q["representation"],"reason":"selected representation is not canonical-illustration based"}
        qt=toks(q["concept"]+" "+" ".join(q["semantic_parts"]))
        scored=[]
        for r in self.records:
            if r.get("representation") not in ILLUSTRATION_REPS: continue
            rt=toks(str(r.get("concept",""))+" "+" ".join(r.get("semanticParts",[])))
            inter=len(qt&rt); union=max(1,len(qt|rt)); score=inter/union
            required=set(q.get("required_operations",[])); available=set(r.get("capabilities",[]))
            op_hits=sum(1 for need in required if any(need in a or a in need for a in available))
            score += 0.04*op_hits
            if score>0: scored.append((score,r))
        scored.sort(key=lambda x:(x[0],x[1].get("illustrationId","")),reverse=True)
        if scored and scored[0][0] >= 0.28:
            r=deepcopy(scored[0][1])
            return {"status":"RESOLVED_EXISTING","score":round(scored[0][0],4),"record":r,"no_silent_degrade":True}
        if cap.get("production_scoped_asset_generation"):
            return {"status":"GENERATION_REQUIRED","concept":q["concept"],"representation":q["representation"],"semantic_parts":q["semantic_parts"],"required_operations":q["required_operations"],"no_silent_degrade":True}
        return {"status":"UNSUPPORTED_FORM_REQUIRED","concept":q["concept"],"representation":q["representation"],"no_silent_degrade":True,"forbidden_fallback":"DIAGRAM"}
