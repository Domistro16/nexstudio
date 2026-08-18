from __future__ import annotations
import json, os
from typing import Any


def _routes(name: str) -> list[dict[str, Any]]:
    raw=os.getenv(name,'').strip()
    if not raw:return []
    try: obj=json.loads(raw)
    except Exception:return []
    if isinstance(obj,dict): obj=obj.get('routes') or []
    if not isinstance(obj,list):return []
    out=[]
    for item in obj:
        if not isinstance(item,dict):continue
        rid=str(item.get('id') or '').strip(); command=item.get('command')
        if not rid or not isinstance(command,list) or not command or not all(isinstance(x,str) and x for x in command):continue
        if item.get('commercialUseAllowed') is not True:continue
        env_name=str(item.get('credentialEnv') or '').strip()
        available=not env_name or bool(os.getenv(env_name,''))
        out.append({**item,'id':rid,'available':available,'priority':int(item.get('priority') or 0)})
    return sorted(out,key=lambda x:(-x['priority'],x['id']))

class TTSAdapter:
    """Provider/model-neutral speech body port; Sound remains creative authority."""
    def capability(self):
        routes=_routes('NEXSTUDIO_TTS_ROUTES_JSON')
        return {
            'provider':'RUNTIME_DECLARED',
            'generation_available':any(x['available'] for x in routes),
            'routes':[{'id':x['id'],'available':x['available'],'priority':x['priority']} for x in routes],
            'rights_policy':'COMMERCIAL_USE_MUST_BE_EXPLICIT_PER_ROUTE',
            'role':'body_specialist',
        }
    def request(self,text,performance_intent):
        if not text.strip(): raise ValueError('TTS text required')
        return {'kind':'TTS_REQUEST','text':text,'performance_intent':performance_intent,'provider_capability':self.capability()}

class MusicAdapter:
    def capability(self):
        routes=_routes('NEXSTUDIO_MUSIC_ROUTES_JSON')
        return {
            'provider':'RUNTIME_DECLARED',
            'generation_available':any(x['available'] for x in routes),
            'routes':[{'id':x['id'],'available':x['available'],'priority':x['priority']} for x in routes],
            'rights_policy':'COMMERCIAL_USE_MUST_BE_EXPLICIT_PER_ROUTE',
            'role':'body_specialist',
        }
