from __future__ import annotations
from copy import deepcopy
from .provider import CreativeModelProvider
from .sound_contracts import validate_sound_output
from .sound_resources import SoundResourceRegistry
class SoundDirector:
    def __init__(self,provider:CreativeModelProvider,resources:SoundResourceRegistry,music_generation_available:bool=False): self.provider=provider; self.resources=resources; self.music_generation_available=music_generation_available
    def propose(self,production_id,brief,story,editorial,motion,performance_storyboard,doctrine):
        brief_copy=deepcopy(brief)
        revision_context=brief_copy.get('autonomous_revision_context') if isinstance(brief_copy.get('autonomous_revision_context'),dict) else {}
        broader_replan=revision_context.get('department')=='SOUND_DIRECTION' and revision_context.get('repair_mode')=='MATERIAL_STRATEGY_REPLAN'
        repair_anchor=revision_context.get('previous_output') if revision_context.get('department')=='SOUND_DIRECTION' else None
        surgical_repair=isinstance(repair_anchor,dict) and bool(repair_anchor) and not broader_replan
        duration=int(brief_copy.get('duration_s') or 0)
        candidate_budget=1 if surgical_repair else 2 + (1 if duration>=45 or len(story.get('beats') or [])>=6 else 0)
        candidate_budget=max(1,min(4,candidate_budget))
        req={
            'production_id':production_id,'brief':brief_copy,'film_thesis':deepcopy(story['film_thesis']),'editorial_rhythm':deepcopy(editorial),'motion_performance':deepcopy(motion),'performance_storyboard':deepcopy(performance_storyboard),'creative_doctrine':deepcopy(doctrine),
            'sound_resources':self.resources.model_view(),'music_generation_available':bool(self.music_generation_available),'repair_anchor':deepcopy(repair_anchor) if surgical_repair else None,'candidate_budget':candidate_budget,
            'instruction':{
                'role':'NexMind Sound Director',
                'goal':(
                    'Surgically repair the supplied Sound repair_anchor into exactly one stronger rights-safe executable sonic plan. Preserve unaffected sonic decisions and resolve every binding issue without reopening competition.'
                    if surgical_repair else
                    (f'Materially replan Sound Direction with exactly {candidate_budget} genuinely different rights-safe sonic strategies; do not cosmetically polish the exhausted route.' if broader_replan else f'Generate exactly {candidate_budget} genuinely competing sonic arguments: narration performance, silence, motifs, foley, transitions, music energy and mix/ducking. Silence is first-class.')
                ),
                'laws':['sound must follow narrative function and physical/visual state','narration remains intelligible','for SFX/FOLEY/TRANSITION use only authorized_semantic_tags listed in sound_resources unless the event is optional and may be omitted','if music_generation_available is false, do not choose GENERATIVE music','generative music requires a rights-safe provider','do not use a generic full-length music bed','when repair_anchor is supplied, return exactly one repaired candidate and preserve sticky_requirements','do not output audio samples, DSP code or file fabrication']
            }
        }
        cs=validate_sound_output(self.provider.complete('sound_direction',req),{b['beat_id'] for b in story['beats']},repair_mode=surgical_repair);return [self._resolve(c) for c in cs]
    def _resolve(self,c):
        out=deepcopy(c); gaps=[]; assets=[]
        for e in out['events']:
            if e['kind'] in {'SFX','FOLEY','TRANSITION'}:
                r=self.resources.resolve(e['semantic_tag'],optional=e['optional']); e['resource']=r
                if r['status']=='AUTHORIZED_ASSET': assets.append(r['asset_id'])
                elif r['status']=='UNSUPPORTED_SOUND_TAG': gaps.append({'event_id':e['event_id'],'code':r['code'],'semantic_tag':e['semantic_tag']})
            else: e['resource']={'status':'DIRECTIVE_ONLY'}
        if out['music_strategy']['mode']=='GENERATIVE' and not self.music_generation_available: gaps.append({'code':'RIGHTS_SAFE_MUSIC_PROVIDER_UNAVAILABLE'})
        out['resource_gaps']=gaps; out['authorized_assets']=sorted(set(assets)); out['executable_resource_plan']=not gaps
        return out
