from __future__ import annotations
import json
from copy import deepcopy
from pathlib import Path
from typing import Any,Dict

class SoundResourceRegistry:
    def __init__(self,records):
        self.records=deepcopy(records); self.by_tag={}
        for r in self.records:
            if not r.get('provenance',{}).get('userAuthorized'): continue
            for tag in r.get('tags',[]): self.by_tag.setdefault(tag,[]).append(r)
    @classmethod
    def from_file(cls,path): return cls(json.loads(Path(path).read_text(encoding="utf-8")))
    def resolve(self,tag:str,*,optional:bool=False)->Dict[str,Any]:
        xs=self.by_tag.get(tag,[])
        if xs:
            r=xs[0]; return {'status':'AUTHORIZED_ASSET','asset_id':r['id'],'semantic_tag':tag,'production_file':r.get('productionFile'),'sha256':r.get('sha256'),'provenance':deepcopy(r.get('provenance',{}))}
        if optional: return {'status':'OMITTED_UNMAPPED_OPTIONAL','semantic_tag':tag}
        return {'status':'UNSUPPORTED_SOUND_TAG','semantic_tag':tag,'code':'NO_AUTHORIZED_SEMANTIC_MAPPING'}
    def stats(self): return {'records':len(self.records),'authorized_records':sum(bool(x.get('provenance',{}).get('userAuthorized')) for x in self.records),'mapped_tags':len(self.by_tag)}
    def model_view(self):
        return {
            'schema':'NexMindSoundResourceModelViewV1',
            'authorized_semantic_tags':sorted(self.by_tag),
            'stats':self.stats(),
        }
