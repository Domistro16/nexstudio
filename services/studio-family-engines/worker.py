#!/usr/bin/env python3
from __future__ import annotations
import json,sys,traceback,uuid
from contracts import AdapterBlocked,AdapterReplan
from execution_plan import compile_execution_plan, compatibility_board
from whiteboard_adapter import build_internal_evidence
from explainer_adapter import build_internal_evidence as build_explainer_evidence
from editorial_adapter import build_internal_evidence as build_editorial_evidence

def _meta(plan):
    if not isinstance(plan,dict): return {}
    return {
        "executionPlanSchema":plan.get("schema"),
        "executionPlanHash":plan.get("executionPlanHash"),
        "executionPlanAuthority":plan.get("authority"),
    }

def main():
    plan=None
    try:
        incoming=json.load(sys.stdin)
        if incoming.get("schema")!="StudioFamilyEngineRequestV1": raise AdapterBlocked("ENGINE_REQUEST_SCHEMA_INVALID")
        operation=incoming.get("operation")
        if operation != "BUILD_INTERNAL_REVIEW_EVIDENCE": raise AdapterBlocked("ENGINE_OPERATION_UNSUPPORTED",str(operation))
        raw_board=incoming.get("finalBoard") or {}
        plan=compile_execution_plan(incoming,raw_board)
        # Renderer ports never receive the caller's raw board object. The only
        # board-shaped input they see is mechanically reconstructed from the
        # canonical execution representation above.
        request=dict(incoming)
        request.pop("finalBoard",None)
        request["executionPlan"]=plan
        request["finalBoard"]=compatibility_board(plan)
        family=request.get("family")
        if family=="WHITEBOARD": out=build_internal_evidence(request)
        elif family=="EXPLAINER": out=build_explainer_evidence(request)
        elif family=="STICKMAN":
            from stickman_adapter import build_internal_evidence as build_stickman_evidence
            out=build_stickman_evidence(request)
        elif family=="EDITORIAL_MOTION": out=build_editorial_evidence(request)
        else: raise AdapterBlocked("FAMILY_ENGINE_ADAPTER_NOT_IMPLEMENTED",str(family))
        out={**out,**_meta(plan)}
        json.dump(out,sys.stdout,separators=(",",":"));sys.stdout.write("\n")
    except AdapterReplan as e:
        json.dump({"schema":"StudioFamilyEngineResultV1","status":"REPLAN_REQUIRED","code":e.code,"detail":e.detail,"repairRequest":e.repair_request,**_meta(plan)},sys.stdout,separators=(",",":"));sys.stdout.write("\n")
    except AdapterBlocked as e:
        json.dump({"schema":"StudioFamilyEngineResultV1","status":"TECHNICAL_RETRY_REQUIRED","code":e.code,"detail":e.detail,**_meta(plan)},sys.stdout,separators=(",",":"));sys.stdout.write("\n")
    except Exception as exc:
        correlation_id="family-"+uuid.uuid4().hex
        traceback.print_exc(file=sys.stderr)
        print(f"FAMILY_ENGINE_CORRELATION_ID:{correlation_id}",file=sys.stderr)
        json.dump({"schema":"StudioFamilyEngineResultV1","status":"TECHNICAL_RETRY_REQUIRED","code":"ENGINE_ADAPTER_INTERNAL_ERROR","detail":"The internal family-engine adapter failed safely.","diagnosticCorrelationId":correlation_id,"internalErrorClass":type(exc).__name__,**_meta(plan)},sys.stdout,separators=(",",":"));sys.stdout.write("\n")
if __name__=="__main__":main()
