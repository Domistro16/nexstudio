from __future__ import annotations
import hashlib,json
from copy import deepcopy
from typing import Any,Dict

def _h(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
class RejectionFeedbackLedger:
    """Structured feedback for future P9 optimization. Never mutates live production policy."""
    def __init__(self):self.records=[]
    def record_machine(self,production_id:str,revision:int,review:Dict[str,Any]):
        rec={'source':'FINAL_EXECUTIVE_PRODUCER','production_id':production_id,'revision':revision,'verdict':review['verdict'],'issues':deepcopy(review['issues']),'revision_plan':deepcopy(review['revision_plan']),'hard_failures':[g['dimension'] for g in review['hard_gates'] if g['status']=='FAIL'],'taste_low':[k for k,v in review['taste_judgments'].items() if float(v['score'])<8.0]}
        rec['feedback_id']=_h(rec);self.records.append(rec);return deepcopy(rec)
    def record_human(self,production_id:str,revision:int,human_review:Dict[str,Any],gate:Dict[str,Any]):
        rec={'source':'BLIND_HUMAN_REVIEW','production_id':production_id,'revision':revision,'reviewer_id':human_review['reviewer_id'],'gate':deepcopy(gate),'hard_rejects':deepcopy(human_review['hard_rejects']),'notes':human_review['notes']};rec['feedback_id']=_h(rec);self.records.append(rec);return deepcopy(rec)
    def export(self):return deepcopy(self.records)
