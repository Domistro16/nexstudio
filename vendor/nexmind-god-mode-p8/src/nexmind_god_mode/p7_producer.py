from __future__ import annotations
from copy import deepcopy
from .provider import CreativeModelProvider
from .contracts import validate_producer_output
from .review_governance import calibrate_review, release_decision_law
class SoundExecutiveProducer:
    def __init__(self,provider): self.provider=provider
    def review(self,production_id,brief,story,sound):
        mech=[]
        if sound.get('resource_gaps'): mech.append({'code':'SOUND_RESOURCE_GAP','gaps':deepcopy(sound['resource_gaps'])})
        if sound['music_strategy']['full_length_bed'] and sound['music_strategy']['mode']!='NONE': mech.append({'code':'FULL_LENGTH_MUSIC_REQUIRES_EXCEPTION_REVIEW'})
        req={'production_id':production_id,'brief':deepcopy(brief),'film_thesis':deepcopy(story['film_thesis']),'sound_candidate':deepcopy(sound),'mechanical_preflight':mech,'instruction':{'role':'Independent Executive Producer — Sound','release_decision_law':release_decision_law('SOUND_DIRECTION'),'questions':['Does sound clarify narrative state rather than decorate?','Is silence used deliberately?','Is narration protected by ducking?','Are foley/SFX synchronized to meaningful actions?','Is music shaped by the emotional arc rather than laid under the whole film?','Are all resources rights-safe and mapped?']}}
        r=validate_producer_output(self.provider.complete('sound_review',req))
        if mech and r['verdict']=='ACCEPT':
            r=deepcopy(r);r['verdict']='REVISE'
            mechanical=[]
            for issue in mech:
                item=deepcopy(issue); item['blocking']=True; mechanical.append(item)
            r['issues']=[*mechanical,*r['issues']];r['revision_brief']='Resolve sound-resource/full-bed issues before acceptance.';r['commercial_confidence']='LOW'
        return validate_producer_output(calibrate_review(r,stage='SOUND_DIRECTION'))
