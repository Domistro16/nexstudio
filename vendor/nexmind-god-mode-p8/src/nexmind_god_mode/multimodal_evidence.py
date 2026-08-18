from __future__ import annotations
import hashlib, json
from copy import deepcopy
from typing import Any, Dict, Iterable

ALLOWED={'CONTACT_SHEET','KEYFRAME','VIDEO','AUDIO_MIX','WAVEFORM','TRANSCRIPT'}

def _media_set_hash(arts):
    items=[{'artifact_id':a['artifact_id'],'kind':a['kind'],'media_sha256':a.get('media_sha256') or a['sha256'],'object_key':a.get('object_key','')} for a in arts]
    items=sorted(items,key=lambda x:x['artifact_id'])
    return hashlib.sha256(json.dumps(items,separators=(',',':'),sort_keys=False).encode()).hexdigest()

def build_multimodal_evidence(artifacts:Iterable[Dict[str,Any]],*,audio_expected:bool=True)->Dict[str,Any]:
    arts=[];issues=[]
    for a in artifacts:
        if not isinstance(a,dict): issues.append('MALFORMED_ARTIFACT_RECORD');continue
        required={'artifact_id','kind','sha256','source'}
        if not required.issubset(a): issues.append('MALFORMED_ARTIFACT_RECORD');continue
        if a['kind'] not in ALLOWED:issues.append('UNSUPPORTED_ARTIFACT_KIND:'+str(a['kind']));continue
        if len(str(a['sha256']))!=64:issues.append('MISSING_OR_INVALID_SHA256:'+str(a['artifact_id']));continue
        item=deepcopy(a)
        media_sha=str(item.get('media_sha256') or item['sha256'])
        if item['kind']!='TRANSCRIPT' and len(media_sha)!=64:issues.append('MISSING_MEDIA_BYTE_SHA256:'+str(a['artifact_id']));continue
        item['media_sha256']=media_sha
        arts.append(item)
    visual=any(a['kind'] in {'CONTACT_SHEET','KEYFRAME','VIDEO'} for a in arts)
    audio=any(a['kind'] in {'AUDIO_MIX','WAVEFORM','VIDEO'} for a in arts)
    if not visual:issues.append('NO_VISUAL_RENDER_EVIDENCE')
    if audio_expected and not audio:issues.append('NO_AUDIO_RENDER_EVIDENCE')
    return {'status':'COMPLETE' if not issues else 'MISSING','artifacts':arts,'issues':issues,'visual_present':visual,'audio_present':audio,'perceptually_reviewed':False,'media_set_sha256':_media_set_hash(arts) if arts else None}
