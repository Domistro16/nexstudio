from __future__ import annotations

import hashlib, json, os, random, secrets, time, urllib.error, urllib.request
from copy import deepcopy

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

from .provider import CreativeModelProvider, ProviderError, canonical_hash
from .provider_schemas import SCHEMAS

AMBIGUOUS_MODELS={"auto","latest","default"}
ALLOWED_REASONING={"none","low","medium","high","xhigh","max"}
TRANSIENT={408,409,429,500,502,503,504}

def _model_basename(model:str)->str:
    """Return provider-neutral model identity for namespaced transport aliases.

    Examples:
      vendor-model-a -> vendor-model-a
      provider/vendor-model-a -> vendor-model-a
      router/provider/vendor-model-a -> vendor-model-a
    """
    return str(model or "").strip().lower().rsplit("/",1)[-1]

def _configured_model_aliases(requested_model:str)->set[str]:
    """Operator-declared exact aliases for providers whose returned ID is not namespaced canonically.

    NEXMIND_MODEL_EQUIVALENCE_JSON example:
      {"vendor-model-a":["gateway/deployment-a-prod"]}

    This is deliberately exact-match only: it enables provider portability without
    accepting ambiguous wildcards or silent model-family downgrades.
    """
    raw=os.getenv("NEXMIND_MODEL_EQUIVALENCE_JSON","").strip()
    if not raw:
        return set()
    try:
        obj=json.loads(raw)
    except json.JSONDecodeError as e:
        raise ProviderError(f"invalid NEXMIND_MODEL_EQUIVALENCE_JSON: {e}")
    if not isinstance(obj,dict):
        raise ProviderError("NEXMIND_MODEL_EQUIVALENCE_JSON must be a JSON object")
    keys={str(requested_model),_model_basename(requested_model)}
    out=set()
    for key in keys:
        vals=obj.get(key,[])
        if isinstance(vals,str): vals=[vals]
        if vals is None: continue
        if not isinstance(vals,list) or any(not isinstance(x,str) for x in vals):
            raise ProviderError(f"model equivalence aliases for {key} must be a string or list of strings")
        out.update(x.strip().lower() for x in vals if x.strip())
    return out

def models_equivalent(requested_model:str,resolved_model:str)->bool:
    """Accept transport/provider aliases while preserving exact model-family intent.

    Provider qualification is transport syntax, not a model change. A genuinely
    different family remains forbidden unless the operator explicitly declares an
    exact alias in NEXMIND_MODEL_EQUIVALENCE_JSON.
    """
    requested=str(requested_model or "").strip().lower()
    resolved=str(resolved_model or "").strip().lower()
    if requested==resolved:
        return True
    if requested and resolved and _model_basename(requested)==_model_basename(resolved):
        return True
    return resolved in _configured_model_aliases(requested)

@dataclass(frozen=True)
class RoleRoute:
    role: str
    provider: str
    model: str
    reasoning: str
    base_url: str
    api_key_env: str
    api_mode: str  # responses | chat_completions | chat_completions_prompt_json
    capabilities: tuple[str,...] = ()
    input_modalities: tuple[str,...] = ()
    audio_input_mode: str = ""

@dataclass
class ProviderCallAudit:
    task: str
    role: str
    requested_provider: str
    resolved_provider: str
    requested_model: str
    resolved_model: str
    reasoning: str
    request_hash: str
    response_hash: str
    provider_request_id: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    duration_ms: int
    retries: int
    status: str
    error: str = ""
    schema_repairs: int = 0

class RoleRouter:
    """Capability-based runtime model routing.

    NexMind roles are architectural capabilities, not provider/model identities.
    A deployment must explicitly configure a compatible runtime route through a
    role override, a capability registry, or a legacy transport alias. There is
    deliberately no baked model/provider fallback.
    """
    ROLE_NAMES={
        "source_understanding":"SourceIntelligenceAnalyst",
        "source_visual_understanding":"SourceVisualIntelligenceAnalyst",
        "story":"StoryDirector","visual":"VisualConceptDirector",
        "producer":"ExecutiveProducer","showrunner_select":"NexMindSupremeShowrunner",
        "art":"ArtDirector","art_review":"ExecutiveProducerArt","showrunner_select_art":"NexMindSupremeShowrunnerArt",
        "storyboard_review":"ExecutiveProducerStoryboard",
        "cinematography":"CinematographyDirector","cinematography_review":"ExecutiveProducerCinematography","showrunner_select_cinematography":"NexMindSupremeShowrunnerCinematography",
        "editorial_rhythm":"EditorialRhythmDirector","editorial_review":"ExecutiveProducerEditorial","showrunner_select_editorial":"NexMindSupremeShowrunnerEditorial","temporal_storyboard_review":"ExecutiveProducerTemporalStoryboard",
        "motion_performance":"MotionPerformanceDirector","motion_review":"ExecutiveProducerMotion","showrunner_select_motion":"NexMindSupremeShowrunnerMotion",
        "sound_direction":"SoundDirector","sound_review":"ExecutiveProducerSound","showrunner_select_sound":"NexMindSupremeShowrunnerSound",
        "final_producer":"IndependentFinalExecutiveProducer",
        "perceptual_auditor":"IndependentPerceptualAuditor",
    }
    ENV_PREFIX={
        "source_understanding":"NEXMIND_SOURCE_INTELLIGENCE",
        "source_visual_understanding":"NEXMIND_SOURCE_VISUAL_INTELLIGENCE",
        "story":"NEXMIND_STORY_DIRECTOR", "visual":"NEXMIND_VISUAL_CONCEPT_DIRECTOR",
        "producer":"NEXMIND_EXECUTIVE_PRODUCER", "showrunner_select":"NEXMIND_SUPREME_SHOWRUNNER",
        "art":"NEXMIND_ART_DIRECTOR", "art_review":"NEXMIND_EXECUTIVE_PRODUCER", "showrunner_select_art":"NEXMIND_SUPREME_SHOWRUNNER",
        "storyboard_review":"NEXMIND_EXECUTIVE_PRODUCER",
        "cinematography":"NEXMIND_CINEMATOGRAPHY_DIRECTOR", "cinematography_review":"NEXMIND_EXECUTIVE_PRODUCER", "showrunner_select_cinematography":"NEXMIND_SUPREME_SHOWRUNNER",
        "editorial_rhythm":"NEXMIND_EDITORIAL_RHYTHM_DIRECTOR", "editorial_review":"NEXMIND_EXECUTIVE_PRODUCER", "showrunner_select_editorial":"NEXMIND_SUPREME_SHOWRUNNER",
        "temporal_storyboard_review":"NEXMIND_EXECUTIVE_PRODUCER",
        "motion_performance":"NEXMIND_MOTION_PERFORMANCE_DIRECTOR", "motion_review":"NEXMIND_EXECUTIVE_PRODUCER", "showrunner_select_motion":"NEXMIND_SUPREME_SHOWRUNNER",
        "sound_direction":"NEXMIND_SOUND_DIRECTOR", "sound_review":"NEXMIND_EXECUTIVE_PRODUCER", "showrunner_select_sound":"NEXMIND_SUPREME_SHOWRUNNER",
        "final_producer":"NEXMIND_FINAL_EXECUTIVE_PRODUCER",
        "perceptual_auditor":"NEXMIND_PERCEPTUAL_AUDITOR",
    }
    CREATIVE_TASKS={"source_understanding","story","visual","art","cinematography","editorial_rhythm","motion_performance","sound_direction"}
    ROLE_CAPABILITIES={
        "source_understanding":("source_reasoning","high"),
        "source_visual_understanding":("multimodal_source_understanding","high"),
        "story":("creative_reasoning","high"),
        "visual":("creative_reasoning","high"),
        "art":("creative_reasoning","high"),
        "cinematography":("creative_reasoning","high"),
        "editorial_rhythm":("creative_reasoning","high"),
        "motion_performance":("creative_reasoning","high"),
        "sound_direction":("creative_reasoning","high"),
        "producer":("commercial_creative_review","high"),
        "showrunner_select":("commercial_creative_selection","high"),
        "art_review":("commercial_creative_review","high"),
        "showrunner_select_art":("commercial_creative_selection","high"),
        "storyboard_review":("commercial_creative_review","high"),
        "cinematography_review":("commercial_creative_review","high"),
        "showrunner_select_cinematography":("commercial_creative_selection","high"),
        "editorial_review":("commercial_creative_review","high"),
        "showrunner_select_editorial":("commercial_creative_selection","high"),
        "temporal_storyboard_review":("commercial_creative_review","high"),
        "motion_review":("commercial_creative_review","high"),
        "showrunner_select_motion":("commercial_creative_selection","high"),
        "sound_review":("commercial_creative_review","high"),
        "showrunner_select_sound":("commercial_creative_selection","high"),
        "final_producer":("multimodal_commercial_taste","high"),
        "perceptual_auditor":("multimodal_perceptual_audit","high"),
    }

    CAPABILITY_COMPATIBILITY={
        "source_reasoning": ("source_reasoning", "creative_reasoning"),
        "multimodal_source_understanding": ("multimodal_source_understanding", "multimodal_commercial_taste", "multimodal_perceptual_audit"),
        "multimodal_perceptual_audit": ("multimodal_perceptual_audit", "multimodal_commercial_taste"),
    }

    @staticmethod
    def _registry()->list[dict]:
        raw=os.getenv("NEXMIND_MODEL_REGISTRY_JSON","").strip()
        if not raw:
            return []
        try:
            obj=json.loads(raw)
        except json.JSONDecodeError as e:
            raise ProviderError(f"invalid NEXMIND_MODEL_REGISTRY_JSON: {e}")
        routes=obj.get("routes") if isinstance(obj,dict) else obj
        if not isinstance(routes,list):
            raise ProviderError("NEXMIND_MODEL_REGISTRY_JSON must be a list or {routes:[...]}")
        out=[]
        for i,item in enumerate(routes):
            if not isinstance(item,dict):
                raise ProviderError(f"model registry route {i} must be object")
            if item.get("enabled",True) is False:
                continue
            model=str(item.get("model") or "").strip()
            provider=str(item.get("provider") or item.get("id") or "").strip().lower()
            caps=item.get("capabilities") or []
            if not model or not provider or not isinstance(caps,list):
                raise ProviderError(f"model registry route {i} requires provider, model and capabilities[]")
            out.append(dict(item, provider=provider, model=model, capabilities=[str(x) for x in caps]))
        return out

    @staticmethod
    def _validate_model(task:str,model:str)->str:
        model=str(model or "").strip()
        if not model:
            raise ProviderError(f"LIVE_PROVIDER_BLOCKED_NO_COMPATIBLE_MODEL_CONFIG:{task}")
        key=model.lower()
        if key in AMBIGUOUS_MODELS or key.startswith("latest"):
            raise ProviderError(f"ambiguous model alias forbidden for {task}: {model}")
        return model

    @staticmethod
    def _route_from_config(role:str, provider:str, model:str, reasoning:str, base_url:str, key_env:str, mode:str, *, capabilities=(), input_modalities=(), audio_input_mode="")->RoleRoute:
        reasoning=str(reasoning or "high").strip().lower()
        if reasoning not in ALLOWED_REASONING:
            raise ProviderError(f"invalid reasoning: {reasoning}")
        mode=str(mode or "chat_completions_prompt_json").strip().lower()
        if mode not in {"responses","chat_completions","chat_completions_prompt_json"}:
            raise ProviderError(f"unsupported model route api_mode: {mode}")
        if not str(provider or "").strip():
            raise ProviderError(f"runtime provider label required for {role}")
        if not str(key_env or "").strip():
            raise ProviderError(f"runtime api_key_env required for {role}")
        caps=tuple(sorted({str(x).strip() for x in capabilities if str(x).strip()}))
        modalities=tuple(sorted({str(x).strip().lower() for x in input_modalities if str(x).strip()}))
        audio_mode=str(audio_input_mode or "").strip().lower()
        if audio_mode and audio_mode not in {"chat_input_audio","responses_input_audio"}:
            raise ProviderError(f"unsupported audio_input_mode: {audio_mode}")
        return RoleRoute(role,str(provider).strip().lower(),model,reasoning,str(base_url or "").rstrip("/"),str(key_env).strip(),mode,caps,modalities,audio_mode)

    @staticmethod
    def _assert_route_modalities(task:str,route:RoleRoute)->None:
        mods=set(route.input_modalities)
        if task=="source_visual_understanding" and "images" not in mods:
            raise ProviderError(f"LIVE_PROVIDER_ROUTE_MODALITY_MISMATCH:{task}:missing=images")
        if task in {"final_producer","perceptual_auditor"}:
            missing=[m for m in ("images","audio") if m not in mods]
            if missing: raise ProviderError(f"LIVE_PROVIDER_ROUTE_MODALITY_MISMATCH:{task}:missing={','.join(missing)}")
            if not route.audio_input_mode: raise ProviderError(f"LIVE_PROVIDER_ROUTE_MODALITY_MISMATCH:{task}:missing=native_audio_payload_mode")

    def resolve_candidates(self,task:str)->list[RoleRoute]:
        if task not in self.ROLE_NAMES:
            raise ProviderError(f"unsupported live-provider task: {task}")
        role=self.ROLE_NAMES[task]
        prefix=self.ENV_PREFIX[task]
        capability,default_reasoning=self.ROLE_CAPABILITIES[task]
        prompt_json=os.getenv("NEXMIND_PROMPT_JSON_COMPAT","").strip().lower() in {"1","true","yes","on"}

        # 1) Exact role override is intentionally binding. An operator who pins a
        # role owns that decision; registry failover applies when no role pin exists.
        role_model=os.getenv(prefix+"_MODEL","").strip()
        if role_model:
            model=self._validate_model(task,role_model)
            provider=(os.getenv(prefix+"_PROVIDER","").strip() or os.getenv("NEXMIND_PROVIDER","").strip() or "runtime").lower()
            base=(os.getenv(prefix+"_BASE_URL","").strip() or os.getenv("NEXMIND_BASE_URL","").strip())
            key_env=(os.getenv(prefix+"_API_KEY_ENV","").strip() or os.getenv("NEXMIND_API_KEY_ENV","").strip() or "NEXMIND_API_KEY")
            mode=(os.getenv(prefix+"_API_MODE","").strip() or os.getenv("NEXMIND_API_MODE","").strip() or ("chat_completions_prompt_json" if prompt_json else "chat_completions"))
            reasoning=os.getenv(prefix+"_REASONING",default_reasoning)
            caps=[x.strip() for x in os.getenv(prefix+"_CAPABILITIES",capability).split(",") if x.strip()]
            modalities=[x.strip() for x in os.getenv(prefix+"_INPUT_MODALITIES","").split(",") if x.strip()]
            audio_mode=os.getenv(prefix+"_AUDIO_INPUT_MODE","").strip()
            route=self._route_from_config(role,provider,model,reasoning,base,key_env,mode,capabilities=caps,input_modalities=modalities,audio_input_mode=audio_mode)
            self._assert_route_modalities(task,route)
            return [route]

        # 2) Capability registry. Every compatible route is retained, ordered by
        # operator priority. LiveCreativeModelProvider may fail over only across
        # this declared list; no undeclared model/provider can appear.
        candidates=[]
        compatible=set(self.CAPABILITY_COMPATIBILITY.get(capability,(capability,)))
        for index,item in enumerate(self._registry()):
            caps=set(item.get("capabilities") or [])
            if caps.intersection(compatible) or "*" in caps:
                candidates.append((-int(item.get("priority",0) or 0),index,item))
        if candidates:
            routes=[]; seen=set()
            for _,_,item in sorted(candidates,key=lambda x:(x[0],x[1])):
                model=self._validate_model(task,item["model"])
                base=str(item.get("base_url") or os.getenv(str(item.get("base_url_env") or ""),"") or "").strip()
                key_env=str(item.get("api_key_env") or "NEXMIND_API_KEY").strip()
                mode=str(item.get("api_mode") or ("chat_completions_prompt_json" if prompt_json else "chat_completions"))
                reasoning=str(item.get("reasoning") or os.getenv(prefix+"_REASONING",default_reasoning))
                route=self._route_from_config(role,item["provider"],model,reasoning,base,key_env,mode,capabilities=item.get("capabilities") or [],input_modalities=item.get("input_modalities") or [],audio_input_mode=item.get("audio_input_mode") or "")
                self._assert_route_modalities(task,route)
                key=(route.provider,route.model,route.base_url,route.api_key_env,route.api_mode)
                if key not in seen: routes.append(route); seen.add(key)
            if routes: return routes

        # 3) Provider-neutral operator compatibility lane. Provider-named aliases
        # are deliberately forbidden so a fresh deployment cannot recreate a hidden
        # provider-named hidden architecture.
        creative=task in self.CREATIVE_TASKS
        lane="NEXMIND_CREATIVE" if creative else "NEXMIND_REVIEW"
        model=os.getenv(lane+"_MODEL","").strip()
        if model:
            model=self._validate_model(task,model)
            provider=os.getenv(lane+"_PROVIDER","runtime").strip() or "runtime"
            base=os.getenv(lane+"_BASE_URL","").strip()
            key_env=os.getenv(lane+"_API_KEY_ENV","NEXMIND_API_KEY").strip() or "NEXMIND_API_KEY"
            mode=os.getenv(lane+"_API_MODE","").strip() or ("chat_completions_prompt_json" if prompt_json else "chat_completions")
            caps=[x.strip() for x in os.getenv(lane+"_CAPABILITIES",capability).split(",") if x.strip()]
            modalities=[x.strip() for x in os.getenv(lane+"_INPUT_MODALITIES","").split(",") if x.strip()]
            audio_mode=os.getenv(lane+"_AUDIO_INPUT_MODE","").strip()
            reasoning=os.getenv(prefix+"_REASONING",default_reasoning)
            route=self._route_from_config(role,provider,model,reasoning,base,key_env,mode,capabilities=caps,input_modalities=modalities,audio_input_mode=audio_mode)
            self._assert_route_modalities(task,route)
            return [route]

        raise ProviderError(f"LIVE_PROVIDER_BLOCKED_NO_COMPATIBLE_MODEL_CONFIG:{capability}:{task}")

    def resolve(self,task:str)->RoleRoute:
        return self.resolve_candidates(task)[0]

class LiveCreativeModelProvider(CreativeModelProvider):
    def __init__(self, router:Optional[RoleRouter]=None, timeout_s:Optional[float]=None, max_retries:Optional[int]=None):
        self.router=router or RoleRouter()
        if timeout_s is None:
            try: timeout_s=float(os.getenv("NEXMIND_PROVIDER_TIMEOUT_SECONDS","90") or 90)
            except Exception: timeout_s=90.0
        if max_retries is None:
            try: max_retries=int(os.getenv("NEXMIND_PROVIDER_MAX_RETRIES","1") or 1)
            except Exception: max_retries=1
        self.timeout_s=max(10.0,min(300.0,float(timeout_s)))
        self.max_retries=max(0,min(4,int(max_retries)))
        self.audits=[]; self.candidate_order_audits=[]; self.perceptual_deliveries=[]

    @staticmethod
    def _replace_exact_strings(value:Any, mapping:Dict[str,str])->Any:
        if isinstance(value,str):
            return mapping.get(value,value)
        if isinstance(value,list):
            return [LiveCreativeModelProvider._replace_exact_strings(x,mapping) for x in value]
        if isinstance(value,dict):
            return {k:LiveCreativeModelProvider._replace_exact_strings(v,mapping) for k,v in value.items()}
        return value

    @staticmethod
    def _candidate_id(item:Any)->str:
        if not isinstance(item,dict): return ''
        c=item.get('candidate') if isinstance(item.get('candidate'),dict) else item
        return str(c.get('candidate_id') or '') if isinstance(c,dict) else ''

    def _blind_showrunner_candidates(self, task:str, request:Dict[str,Any])->tuple[Dict[str,Any],Dict[str,str],Dict[str,str]]:
        """Randomize and relabel candidate presentation for live Showrunner selection.

        The model never sees positional V1/V2/V3-style identifiers. Mapping is kept
        only inside the provider and is reversed after structured output returns.
        """
        candidates=request.get('candidates')
        if not isinstance(candidates,list) or len(candidates)<2:
            return request,{},{}
        original_ids=[self._candidate_id(x) for x in candidates]
        if any(not x for x in original_ids) or len(set(original_ids))!=len(original_ids):
            raise ProviderError(f'{task}: live candidate blinding requires unique candidate_id values')
        # SystemRandom gives each live selection an independent permutation.
        rng=secrets.SystemRandom()
        shuffled=list(candidates); rng.shuffle(shuffled)
        forward={oid:'OPT-'+secrets.token_hex(6).upper() for oid in original_ids}
        reverse={v:k for k,v in forward.items()}
        blinded=[self._replace_exact_strings(x,forward) for x in shuffled]
        req=dict(request); req['candidates']=blinded
        req['candidate_presentation_policy']={
            'blind_order':True,
            'opaque_identifiers':True,
            'position_has_no_semantic_meaning':True,
            'instruction':'Judge each option only on its creative merits. Candidate order and identifier carry no preference signal.'
        }
        presented=[self._candidate_id(x) for x in blinded]
        self.candidate_order_audits.append({
            'task':task,
            'production_id':str(request.get('production_id') or ''),
            'original_id_set_sha256':canonical_hash(sorted(original_ids)),
            'presented_opaque_ids':presented,
            'mapping_sha256':canonical_hash(forward),
            'candidate_count':len(original_ids),
            'policy':'RANDOMIZED_OPAQUE_LIVE_SELECTION_V2'
        })
        return req,forward,reverse

    def _unblind_showrunner_result(self, payload:Dict[str,Any], reverse:Dict[str,str])->Dict[str,Any]:
        if not reverse: return payload
        out=self._replace_exact_strings(payload,reverse)
        sid=str(out.get('selected_candidate_id') or '')
        if sid not in reverse.values():
            raise ProviderError('showrunner returned candidate identifier outside the blinded live set')
        return out

    def _system(self, task:str, route:RoleRoute)->str:
        if task=="source_visual_understanding":
            return (
                "You are SourceVisualIntelligenceAnalyst, a factual multimodal/provenance service beneath NexMind Supreme Showrunner. "
                "Inspect only the supplied source images and their metadata. You are NOT a creative Director. "
                "Every observation must repeat the exact source_id, locator, and sha256 supplied for that image. Never invent facts that are not visible. "
                "Charts, screenshots and diagrams may be described factually, but ambiguity must remain unresolved rather than guessed. "
                "Return only the requested structured object."
            )
        if task=="perceptual_auditor":
            return (
                "You are the IndependentPerceptualAuditor. You are a second machine veto, not a creative Director and not a scoring model. "
                "Inspect the exact supplied reviewed film frames, native audio, and bound reference visuals. Do not see or infer the Final Producer's verdict or scores. "
                "VETO if the finished work is generic/template-like, materially derivative of references, aesthetically incoherent, emotionally ineffective, weakly authored, payoff-deficient, Brand-infaithful, audio-visually incoherent, or uses an unauthored/generic environment when the film requires a specific world. "
                "Return only the structured PASS/VETO contract. Do not propose replacement creative direction."
            )
        if task=="source_understanding":
            return (
                "You are SourceIntelligenceAnalyst, a factual/provenance service beneath NexMind Supreme Showrunner. "
                "You are NOT a creative Director and may not choose the film, visual concept, art direction, camera, edit, motion, or sound. "
                "Use only the supplied evidence records and their exact claim IDs. Never invent evidence IDs or facts. "
                "Every synthesized claim must cite one or more supplied source_claim_ids. Preserve material contradictions rather than guessing which source is correct. "
                "If a visual-only page or chart must be inspected before a factual conclusion is safe, put it in visual_evidence_needs instead of inferring unseen pixels. "
                "Return only the requested structured object and keep creative_relevance descriptive: what facts matter to the eventual film, not how to direct it."
            )
        return (
            f"You are {route.role}, a department inside NexMind Supreme Showrunner. "
            "Return only the requested structured object. Never claim final authority unless you are the Supreme Showrunner selection role. "
            "Never output pixel coordinates, SVG/HTML/CSS/JS/TS, renderer code, or invent evidence IDs. "
            "When the request or brief contains autonomous_revision_context, treat it as a binding repair contract: preserve stated strengths and unaffected upstream decisions, resolve every material issue, and do not merely paraphrase or cosmetically polish rejected work. "
            "Optimize for commercially strong film thinking: one clear thesis, strong hero, causal transformation, non-generic visual ideas, and audience-state change."
        )

    @staticmethod
    def _schema_name(task:str)->str: return "nexmind_"+task.replace("-","_")

    @staticmethod
    def _endpoint(base_url:str, api_mode:str)->str:
        base=str(base_url or "").rstrip("/")
        suffix="/responses" if api_mode=="responses" else "/chat/completions"
        if base.endswith(suffix):
            return base
        if api_mode!="responses" and base.endswith("/responses"):
            raise ProviderError("chat-completions mode cannot use a /responses endpoint")
        if api_mode=="responses" and base.endswith("/chat/completions"):
            raise ProviderError("responses mode cannot use a /chat/completions endpoint")
        return base+suffix

    @staticmethod
    def _schema_for_request(task:str, request:Dict[str,Any])->Dict[str,Any]:
        schema=deepcopy(SCHEMAS[task])
        candidate_tasks={"visual","art","cinematography","editorial_rhythm","motion_performance","sound_direction"}
        if task in candidate_tasks:
            props=schema.get("properties") if isinstance(schema,dict) else None
            candidates=props.get("candidates") if isinstance(props,dict) else None
            if isinstance(candidates,dict):
                repair_anchor=request.get("repair_anchor")
                if isinstance(repair_anchor,dict) and repair_anchor:
                    candidates["minItems"]=1
                    candidates["maxItems"]=1
                else:
                    try: budget=int(request.get("candidate_budget") or 0)
                    except Exception: budget=0
                    if budget>0:
                        candidates["minItems"]=budget
                        candidates["maxItems"]=budget
        if task.startswith("showrunner_select"):
            accepted=[]
            for item in request.get("candidates") or []:
                if not isinstance(item,dict):
                    continue
                candidate=item.get("candidate") if isinstance(item.get("candidate"),dict) else item
                cid=str(candidate.get("candidate_id") or "") if isinstance(candidate,dict) else ""
                review=item.get("review") if isinstance(item.get("review"),dict) else item.get("producer_review") if isinstance(item.get("producer_review"),dict) else None
                if cid and (review is None or str(review.get("verdict") or "").upper()=="ACCEPT"):
                    accepted.append(cid)
            selected=schema.get("properties",{}).get("selected_candidate_id") if isinstance(schema,dict) else None
            if accepted and isinstance(selected,dict):
                selected["enum"]=sorted(set(accepted))
        return schema

    def _prompt_json_system(self, task:str, route:RoleRoute, request:Optional[Dict[str,Any]]=None)->str:
        schema=json.dumps(self._schema_for_request(task,request or {}),ensure_ascii=False,separators=(",",":"))
        return (
            self._system(task,route)
            + " OUTPUT CONTRACT: Return exactly one JSON object and nothing else. "
            + "Do not use markdown fences, prose before/after the JSON, comments, NaN, Infinity, or trailing commas. "
            + "The object MUST validate exactly against this JSON Schema (including required fields, enums, types, and additionalProperties rules): "
            + schema
        )

    def _prompt_json_payload(self, task:str, request:Dict[str,Any], route:RoleRoute)->Dict[str,Any]:
        # Lowest-common-denominator OpenAI-compatible chat payload. Prompt-JSON may
        # still carry standard multimodal chat content when the configured route
        # explicitly declares multimodal source-understanding capability.
        safe,images,audios=self._multimodal_request(task,request)
        user_content:Any=json.dumps(safe,ensure_ascii=False)
        if images or audios:
            user_content=[{"type":"text","text":json.dumps(safe,ensure_ascii=False)}]+[{"type":"image_url","image_url":{"url":url}} for url in images]+[self._audio_content(a,route) for a in audios]
        return {
            "model":route.model,
            "messages":[
                {"role":"system","content":self._prompt_json_system(task,route,request)},
                {"role":"user","content":user_content},
            ],
        }

    def _prompt_json_schema_repair_payload(self, task:str, request:Dict[str,Any], invalid_output:Dict[str,Any], validation_error:str, route:RoleRoute)->Dict[str,Any]:
        """Build one bounded schema-repair request without weakening the creative contract.

        The same route receives the original task context, the invalid object, and
        the exact local validation failure. It must preserve valid creative content
        and return the complete object against the same strict schema.
        """
        safe,images,audios=self._multimodal_request(task,request)
        repair_context={
            "schema_repair":{
                "task":task,
                "validation_error":validation_error,
                "instruction":(
                    "Repair the existing JSON object only enough to satisfy the exact output schema. "
                    "Preserve every already-valid creative value. Add or correct only missing/invalid fields. "
                    "Do not delete required creative substance, do not replace the concept with a new generic concept, "
                    "and return the full corrected object, not a patch."
                ),
            },
            "original_request":safe,
            "invalid_output":invalid_output,
        }
        user_content:Any=json.dumps(repair_context,ensure_ascii=False)
        if images or audios:
            user_content=[{"type":"text","text":json.dumps(repair_context,ensure_ascii=False)}]+[{"type":"image_url","image_url":{"url":url}} for url in images]+[self._audio_content(a,route) for a in audios]
        return {
            "model":route.model,
            "messages":[
                {"role":"system","content":self._prompt_json_system(task,route,request)+" SCHEMA REPAIR MODE: preserve valid content and return the complete corrected object only."},
                {"role":"user","content":user_content},
            ],
        }

    def _prompt_json_syntax_repair_payload(self, task:str, request:Dict[str,Any], invalid_text:str, parse_error:str, route:RoleRoute)->Dict[str,Any]:
        """Build one bounded repair request for malformed provider JSON text.

        This does not weaken the schema. The same route receives the original task
        context, the raw malformed output, the exact JSON parse error and the same
        strict schema, then must return one complete schema-valid object.
        """
        safe,images,audios=self._multimodal_request(task,request)
        repair_context={
            "json_syntax_repair":{
                "task":task,
                "parse_error":parse_error,
                "instruction":(
                    "Repair the malformed JSON syntax only as necessary and return the complete object. "
                    "Preserve every recoverable creative value from the malformed output. Do not replace the concept, "
                    "summarize it, or return a patch. The corrected object must also satisfy the exact strict output schema."
                ),
            },
            "original_request":safe,
            "malformed_output":invalid_text,
        }
        user_content:Any=json.dumps(repair_context,ensure_ascii=False)
        if images or audios:
            user_content=[{"type":"text","text":json.dumps(repair_context,ensure_ascii=False)}]+[{"type":"image_url","image_url":{"url":url}} for url in images]+[self._audio_content(a,route) for a in audios]
        return {
            "model":route.model,
            "messages":[
                {"role":"system","content":self._prompt_json_system(task,route,request)+" JSON SYNTAX REPAIR MODE: return one complete corrected JSON object only; it must satisfy the same strict schema."},
                {"role":"user","content":user_content},
            ],
        }

    def _repair_prompt_json_syntax(self, task:str, request:Dict[str,Any], invalid_text:str, parse_error:str, route:RoleRoute, *, endpoint:str, key:str)->tuple[Dict[str,Any],Dict[str,Any],str]:
        payload=self._prompt_json_syntax_repair_payload(task,request,invalid_text,parse_error,route)
        repair_hash=canonical_hash({"endpoint":endpoint,"payload":payload,"kind":"json_syntax_repair"})
        body=json.dumps(payload).encode("utf-8")
        req=urllib.request.Request(endpoint,data=body,headers={"Authorization":"Bearer "+key,"Content-Type":"application/json","Idempotency-Key":repair_hash},method="POST")
        try:
            with urllib.request.urlopen(req,timeout=self.timeout_s) as resp:
                data=json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail=e.read().decode("utf-8",errors="replace")[:500]
            raise ProviderError(f"PROMPT_JSON_SYNTAX_REPAIR_FAILED task={task} HTTP {e.code}: {detail}") from e
        except (urllib.error.URLError,TimeoutError) as e:
            raise ProviderError(f"PROMPT_JSON_SYNTAX_REPAIR_FAILED task={task} transport: {e}") from e
        resolved=str(data.get("model") or route.model)
        if not models_equivalent(route.model,resolved):
            raise ProviderError(f"MODEL_FAMILY_MISMATCH requested={route.model} resolved={resolved} requested_identity={_model_basename(route.model)} resolved_identity={_model_basename(resolved)}")
        try:
            parsed=json.loads(self._extract_chat(data))
        except (json.JSONDecodeError,ProviderError) as e:
            raise ProviderError(f"PROMPT_JSON_SYNTAX_REPAIR_FAILED task={task}: repaired response is not valid JSON object: {e}") from e
        if not isinstance(parsed,dict):
            raise ProviderError(f"PROMPT_JSON_SYNTAX_REPAIR_FAILED task={task}: repaired output must be a JSON object")
        parsed=self._strip_schema_only_extras(parsed,self._schema_for_request(task,request))
        try:
            self._validate_local_schema(task,parsed,request)
        except ProviderError as e:
            raise ProviderError(f"PROMPT_JSON_SYNTAX_REPAIR_FAILED task={task}: repaired output failed strict schema: {e}") from e
        return parsed,data,repair_hash

    def _repair_prompt_json_schema(self, task:str, request:Dict[str,Any], invalid_output:Dict[str,Any], validation_error:str, route:RoleRoute, *, endpoint:str, key:str)->tuple[Dict[str,Any],Dict[str,Any],str]:
        payload=self._prompt_json_schema_repair_payload(task,request,invalid_output,validation_error,route)
        repair_hash=canonical_hash({"endpoint":endpoint,"payload":payload,"kind":"schema_repair"})
        body=json.dumps(payload).encode("utf-8")
        req=urllib.request.Request(endpoint,data=body,headers={"Authorization":"Bearer "+key,"Content-Type":"application/json","Idempotency-Key":repair_hash},method="POST")
        try:
            with urllib.request.urlopen(req,timeout=self.timeout_s) as resp:
                data=json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail=e.read().decode("utf-8",errors="replace")[:500]
            raise ProviderError(f"PROMPT_JSON_SCHEMA_REPAIR_FAILED task={task} HTTP {e.code}: {detail}") from e
        except (urllib.error.URLError,TimeoutError) as e:
            raise ProviderError(f"PROMPT_JSON_SCHEMA_REPAIR_FAILED task={task} transport: {e}") from e
        resolved=str(data.get("model") or route.model)
        if not models_equivalent(route.model,resolved):
            raise ProviderError(f"MODEL_FAMILY_MISMATCH requested={route.model} resolved={resolved} requested_identity={_model_basename(route.model)} resolved_identity={_model_basename(resolved)}")
        try:
            parsed=json.loads(self._extract_chat(data))
        except (json.JSONDecodeError,ProviderError) as e:
            raise ProviderError(f"PROMPT_JSON_SCHEMA_REPAIR_FAILED task={task}: repair response is not valid JSON object: {e}") from e
        if not isinstance(parsed,dict):
            raise ProviderError(f"PROMPT_JSON_SCHEMA_REPAIR_FAILED task={task}: repair output must be a JSON object")
        parsed=self._strip_schema_only_extras(parsed,self._schema_for_request(task,request))
        try:
            self._validate_local_schema(task,parsed,request)
        except ProviderError as e:
            raise ProviderError(f"PROMPT_JSON_SCHEMA_REPAIR_FAILED task={task}: {e}") from e
        return parsed,data,repair_hash

    @staticmethod
    def _extract_chat(data:Dict[str,Any])->str:
        try:
            content=data["choices"][0]["message"]["content"]
        except (KeyError,IndexError,TypeError) as e:
            raise ProviderError("chat-completions response missing choices[0].message.content") from e
        if isinstance(content,str):
            return content
        if isinstance(content,list):
            chunks=[]
            for item in content:
                if isinstance(item,str): chunks.append(item)
                elif isinstance(item,dict) and isinstance(item.get("text"),str): chunks.append(item["text"])
            if chunks: return "".join(chunks)
        raise ProviderError("chat-completions response content is not text")

    @staticmethod
    def _validate_schema_node(value:Any, schema:Dict[str,Any], path:str="<root>")->None:
        """Dependency-free validator for the exact JSON-Schema subset used by P8.

        P8 provider schemas intentionally use a narrow, auditable subset of Draft 2020-12:
        type, required, properties, additionalProperties=false, items, minItems,
        maxItems, minLength, enum, minimum, and maximum. Keeping this validator local prevents
        prompt-JSON transport from acquiring an undeclared third-party runtime dependency.
        """
        expected=schema.get("type")
        if expected:
            ok={
                "object": lambda x:isinstance(x,dict),
                "array": lambda x:isinstance(x,list),
                "string": lambda x:isinstance(x,str),
                "boolean": lambda x:isinstance(x,bool),
                "integer": lambda x:isinstance(x,int) and not isinstance(x,bool),
                "number": lambda x:(isinstance(x,(int,float)) and not isinstance(x,bool)),
            }.get(expected)
            if ok is None:
                raise ProviderError(f"PROMPT_JSON_SCHEMA_INTERNAL_UNSUPPORTED task-schema type={expected}")
            if not ok(value):
                raise ProviderError(f"PROMPT_JSON_SCHEMA_VALIDATION_FAILED path={path}: expected {expected}")

        if "enum" in schema and value not in schema["enum"]:
            raise ProviderError(f"PROMPT_JSON_SCHEMA_VALIDATION_FAILED path={path}: value not in enum")

        if isinstance(value,str) and "minLength" in schema and len(value) < int(schema["minLength"]):
            raise ProviderError(f"PROMPT_JSON_SCHEMA_VALIDATION_FAILED path={path}: shorter than minLength {schema['minLength']}")

        if isinstance(value,(int,float)) and not isinstance(value,bool):
            if "minimum" in schema and value < schema["minimum"]:
                raise ProviderError(f"PROMPT_JSON_SCHEMA_VALIDATION_FAILED path={path}: below minimum {schema['minimum']}")
            if "maximum" in schema and value > schema["maximum"]:
                raise ProviderError(f"PROMPT_JSON_SCHEMA_VALIDATION_FAILED path={path}: above maximum {schema['maximum']}")

        if isinstance(value,list):
            if "minItems" in schema and len(value) < schema["minItems"]:
                raise ProviderError(f"PROMPT_JSON_SCHEMA_VALIDATION_FAILED path={path}: fewer than minItems {schema['minItems']}")
            if "maxItems" in schema and len(value) > schema["maxItems"]:
                raise ProviderError(f"PROMPT_JSON_SCHEMA_VALIDATION_FAILED path={path}: more than maxItems {schema['maxItems']}")
            item_schema=schema.get("items")
            if isinstance(item_schema,dict):
                for i,item in enumerate(value):
                    LiveCreativeModelProvider._validate_schema_node(item,item_schema,f"{path}[{i}]")

        if isinstance(value,dict):
            props=schema.get("properties") or {}
            required=schema.get("required") or []
            for key in required:
                if key not in value:
                    raise ProviderError(f"PROMPT_JSON_SCHEMA_VALIDATION_FAILED path={path}.{key}: required property missing")
            if schema.get("additionalProperties") is False:
                extras=[k for k in value if k not in props]
                if extras:
                    raise ProviderError(f"PROMPT_JSON_SCHEMA_VALIDATION_FAILED path={path}.{extras[0]}: additional property forbidden")
            for key,subschema in props.items():
                if key in value and isinstance(subschema,dict):
                    LiveCreativeModelProvider._validate_schema_node(value[key],subschema,f"{path}.{key}")

    @staticmethod
    def _strip_schema_only_extras(value:Any, schema:Dict[str,Any])->Any:
        """Normalize only unknown object keys for prompt-JSON transport.

        Missing required fields, types, enums and semantic contracts remain strict.
        This exists solely because some compatible providers add harmless keys even
        when instructed not to; it must never synthesize or coerce creative data.
        """
        if isinstance(value,dict):
            props=schema.get("properties") if isinstance(schema.get("properties"),dict) else {}
            allowed=set(props) if schema.get("additionalProperties") is False else None
            out={}
            for key,item in value.items():
                if allowed is not None and key not in allowed:
                    continue
                subschema=props.get(key) if isinstance(props,dict) else None
                out[key]=LiveCreativeModelProvider._strip_schema_only_extras(item,subschema) if isinstance(subschema,dict) else item
            return out
        if isinstance(value,list):
            item_schema=schema.get("items") if isinstance(schema.get("items"),dict) else {}
            return [LiveCreativeModelProvider._strip_schema_only_extras(x,item_schema) for x in value]
        return value

    @classmethod
    def _validate_local_schema(cls, task:str, parsed:Dict[str,Any], request:Optional[Dict[str,Any]]=None)->None:
        schema=cls._schema_for_request(task,request or {}) if task in SCHEMAS else None
        if not isinstance(schema,dict):
            raise ProviderError(f"PROMPT_JSON_SCHEMA_INTERNAL_MISSING task={task}")
        try:
            LiveCreativeModelProvider._validate_schema_node(parsed,schema)
        except ProviderError as e:
            msg=str(e)
            if msg.startswith("PROMPT_JSON_SCHEMA_VALIDATION_FAILED"):
                raise ProviderError(f"PROMPT_JSON_SCHEMA_VALIDATION_FAILED task={task} {msg.split(' ',1)[1] if ' ' in msg else ''}".rstrip()) from e
            raise

    @staticmethod
    def _multimodal_request(task:str, request:Dict[str,Any])->tuple[Dict[str,Any],list[str],list[dict]]:
        safe=deepcopy(request) if False else dict(request)
        images=[]; audios=[]
        if task in {"source_visual_understanding","visual","art"}:
            key="source_visual_evidence" if task=="source_visual_understanding" else "reference_visual_evidence"
            raw=safe.pop(key,[]) or []; metadata=[]
            for item in raw:
                if not isinstance(item,dict): continue
                url=str(item.get("dataUrl") or item.get("data_url") or "")
                if not url.startswith("data:image/"): continue
                images.append(url); metadata.append({k:item.get(k) for k in ["sourceId","sourceLabel","page","locator","role","sha256","mimeType"]})
            safe["visual_evidence_metadata" if task=="source_visual_understanding" else "reference_visual_evidence_metadata"]=metadata
        elif task in {"final_producer","perceptual_auditor"}:
            mm=dict(safe.get("multimodal_evidence") or {})
            percept=dict(mm.pop("perceptual_media",{}) or {})
            frame_meta=[]
            for item in percept.get("temporalFrames",[]) or percept.get("temporal_frames",[]) or []:
                if not isinstance(item,dict): continue
                url=str(item.get("dataUrl") or item.get("data_url") or "")
                if url.startswith("data:image/"):
                    images.append(url); frame_meta.append({"timestamp_seconds":item.get("timestampSeconds",item.get("timestamp_seconds")),"sha256":item.get("sha256")})
            audio=percept.get("audio")
            if isinstance(audio,dict):
                url=str(audio.get("dataUrl") or audio.get("data_url") or "")
                if url.startswith("data:audio/"):
                    audios.append({"data_url":url,"sha256":audio.get("sha256"),"mime_type":audio.get("mimeType",audio.get("mime_type")),"sample_rate":audio.get("sampleRate",audio.get("sample_rate")),"channels":audio.get("channels")})
            refs=percept.get("referenceVisuals") or percept.get("reference_visuals") or []
            ref_meta=[]
            for item in refs:
                if not isinstance(item,dict): continue
                url=str(item.get("dataUrl") or item.get("data_url") or "")
                if url.startswith("data:image/"):
                    images.append(url); ref_meta.append({k:item.get(k) for k in ["sha256","sourceId","source_id","locator"]})
            mm["perceptual_delivery_metadata"]={"video_artifact_id":percept.get("videoArtifactId",percept.get("video_artifact_id")),"video_media_sha256":percept.get("videoMediaSha256",percept.get("video_media_sha256")),"temporal_frames":frame_meta,"reference_visuals":ref_meta,"audio":[{k:v for k,v in a.items() if k!="data_url"} for a in audios]}
            safe["multimodal_evidence"]=mm
        return safe,images,audios

    @staticmethod
    def _audio_content(audio:dict,route:RoleRoute)->dict:
        url=str(audio.get("data_url") or "")
        if "," not in url: raise ProviderError("FINAL_PRODUCER_AUDIO_DATA_URL_INVALID")
        header,data=url.split(",",1);fmt="mp3" if "mpeg" in header else "wav" if "wav" in header else "mp3"
        if route.audio_input_mode not in {"chat_input_audio","responses_input_audio"}: raise ProviderError("FINAL_PRODUCER_NATIVE_AUDIO_MODE_UNSUPPORTED")
        return {"type":"input_audio","input_audio":{"data":data,"format":fmt}}

    def _responses_payload(self, task:str, request:Dict[str,Any], route:RoleRoute)->Dict[str,Any]:
        safe,images,audios=self._multimodal_request(task,request); content=[{"type":"input_text","text":json.dumps(safe,ensure_ascii=False)}]
        content.extend({"type":"input_image","image_url":url} for url in images)
        content.extend(self._audio_content(a,route) for a in audios)
        return {
            "model":route.model,
            "reasoning":{"effort":route.reasoning,"context":"current_turn"},
            "instructions":self._system(task,route),
            "input":[{"role":"user","content":content}],
            "text":{"format":{"type":"json_schema","name":self._schema_name(task),"schema":self._schema_for_request(task,request),"strict":True}},
            "store":False,
        }

    def _chat_payload(self, task:str, request:Dict[str,Any], route:RoleRoute)->Dict[str,Any]:
        safe,images,audios=self._multimodal_request(task,request)
        user_content:Any=json.dumps(safe,ensure_ascii=False)
        if images or audios:
            user_content=[{"type":"text","text":json.dumps(safe,ensure_ascii=False)}]+[{"type":"image_url","image_url":{"url":url}} for url in images]+[self._audio_content(a,route) for a in audios]
        return {
            "model":route.model,
            "messages":[{"role":"system","content":self._system(task,route)},{"role":"user","content":user_content}],
            "response_format":{"type":"json_schema","json_schema":{"name":self._schema_name(task),"schema":self._schema_for_request(task,request),"strict":True}},
            "reasoning_effort":route.reasoning,
        }

    @staticmethod
    def _extract_responses(data:Dict[str,Any])->str:
        if isinstance(data.get("output_text"),str): return data["output_text"]
        chunks=[]
        for item in data.get("output",[]) or []:
            for c in item.get("content",[]) or []:
                if c.get("type") in {"output_text","text"} and isinstance(c.get("text"),str): chunks.append(c["text"])
        if not chunks: raise ProviderError("Responses API returned no output_text")
        return "".join(chunks)

    @staticmethod
    def _usage(data:Dict[str,Any])->tuple[int,int,int,int]:
        u=data.get("usage") or {}
        inp=int(u.get("input_tokens",u.get("prompt_tokens",0)) or 0)
        out=int(u.get("output_tokens",u.get("completion_tokens",0)) or 0)
        inp_det=u.get("input_tokens_details") or u.get("prompt_tokens_details") or {}
        out_det=u.get("output_tokens_details") or u.get("completion_tokens_details") or {}
        return inp,int(inp_det.get("cached_tokens",0) or 0),out,int(out_det.get("reasoning_tokens",0) or 0)

    def _complete_on_route(self, task:str, request:Dict[str,Any], route:RoleRoute)->Dict[str,Any]:
        if task in {"visual","art"} and (request.get("reference_visual_evidence") or []):
            if "images" not in set(route.input_modalities):
                raise ProviderError(f"LIVE_PROVIDER_ROUTE_MODALITY_MISMATCH:{task}:missing=images_for_bound_references")
        key=os.getenv(route.api_key_env,"")
        if not key: raise ProviderError(f"LIVE_PROVIDER_BLOCKED_MISSING_CREDENTIAL:{route.api_key_env}")
        if not route.base_url: raise ProviderError(f"LIVE_PROVIDER_BLOCKED_MISSING_BASE_URL:{route.provider}")
        if route.api_mode=="responses": payload=self._responses_payload(task,request,route)
        elif route.api_mode=="chat_completions_prompt_json": payload=self._prompt_json_payload(task,request,route)
        else: payload=self._chat_payload(task,request,route)
        endpoint=self._endpoint(route.base_url,route.api_mode)
        req_hash=canonical_hash({"endpoint":endpoint,"payload":payload})
        started=time.monotonic(); retries=0; last=""
        for attempt in range(self.max_retries+1):
            try:
                body=json.dumps(payload).encode("utf-8")
                req=urllib.request.Request(endpoint,data=body,headers={"Authorization":"Bearer "+key,"Content-Type":"application/json","Idempotency-Key":req_hash},method="POST")
                with urllib.request.urlopen(req,timeout=self.timeout_s) as resp:
                    data=json.loads(resp.read().decode("utf-8")); headers=dict(resp.headers)
                resolved=str(data.get("model") or route.model)
                if not models_equivalent(route.model,resolved):
                    raise ProviderError(f"MODEL_FAMILY_MISMATCH requested={route.model} resolved={resolved} requested_identity={_model_basename(route.model)} resolved_identity={_model_basename(resolved)}")
                rid=str(data.get("id") or headers.get("x-request-id") or headers.get("X-Request-Id") or "")
                text=self._extract_responses(data) if route.api_mode=="responses" else self._extract_chat(data)
                inp,cached,out,reas=self._usage(data); schema_repairs=0
                try:
                    parsed=json.loads(text)
                except json.JSONDecodeError as syntax_error:
                    if route.api_mode!="chat_completions_prompt_json":
                        raise
                    parsed,repair_data,repair_hash=self._repair_prompt_json_syntax(task,request,text,str(syntax_error),route,endpoint=endpoint,key=key)
                    rinp,rcached,rout,rreas=self._usage(repair_data)
                    inp+=rinp; cached+=rcached; out+=rout; reas+=rreas
                    req_hash=canonical_hash({"initial":req_hash,"json_syntax_repair":repair_hash})
                    schema_repairs=1
                if not isinstance(parsed,dict): raise ProviderError(f"structured provider output for {task} must be a JSON object")
                if route.api_mode=="chat_completions_prompt_json":
                    parsed=self._strip_schema_only_extras(parsed,self._schema_for_request(task,request))
                    try:
                        self._validate_local_schema(task,parsed,request)
                    except ProviderError as schema_error:
                        if schema_repairs:
                            raise ProviderError(f"PROMPT_JSON_SYNTAX_REPAIR_FAILED task={task}: repaired output failed strict schema: {schema_error}") from schema_error
                        if not str(schema_error).startswith("PROMPT_JSON_SCHEMA_VALIDATION_FAILED"):
                            raise
                        parsed,repair_data,repair_hash=self._repair_prompt_json_schema(task,request,parsed,str(schema_error),route,endpoint=endpoint,key=key)
                        rinp,rcached,rout,rreas=self._usage(repair_data)
                        inp+=rinp; cached+=rcached; out+=rout; reas+=rreas
                        req_hash=canonical_hash({"initial":req_hash,"schema_repair":repair_hash})
                        schema_repairs=1
                audit=ProviderCallAudit(task,route.role,route.provider,route.provider,route.model,resolved,route.reasoning,req_hash,canonical_hash(parsed),rid,inp,cached,out,reas,int((time.monotonic()-started)*1000),retries,"PASS",schema_repairs=schema_repairs)
                self.audits.append(audit)
                if task in {"final_producer","perceptual_auditor"}:
                    _,_imgs,_aud=self._multimodal_request(task,request)
                    if not _imgs or not _aud: raise ProviderError(f"{task.upper()}_PERCEPTUAL_INPUTS_NOT_DELIVERED")
                    self.perceptual_deliveries.append({"task":task,"model":resolved,"provider":route.provider,"image_count":len(_imgs),"audio_count":len(_aud),"input_modalities":list(route.input_modalities),"audio_input_mode":route.audio_input_mode,"media_set_sha256":str((request.get("multimodal_evidence") or {}).get("media_set_sha256") or "")})
                return parsed
            except urllib.error.HTTPError as e:
                last=f"HTTP {e.code}: "+e.read().decode("utf-8",errors="replace")[:500]
                if e.code not in TRANSIENT or attempt>=self.max_retries: break
            except (urllib.error.URLError,TimeoutError) as e:
                last=f"transport: {e}"
                if attempt>=self.max_retries: break
            except (KeyError,IndexError,json.JSONDecodeError,ProviderError) as e:
                last=str(e); break
            retries += 1; time.sleep(min(1.5,0.15*(2**attempt))+random.random()*0.03)
        self.audits.append(ProviderCallAudit(task,route.role,route.provider,route.provider,route.model,route.model,route.reasoning,req_hash,"","",0,0,0,0,int((time.monotonic()-started)*1000),retries,"FAIL",last))
        raise ProviderError(last or "live provider call failed")

    def complete(self, task:str, request:Dict[str,Any])->Dict[str,Any]:
        reverse={}
        if task.startswith('showrunner_select') and isinstance(request.get('candidates'),list):
            request,_,reverse=self._blind_showrunner_candidates(task,request)
        routes=self.router.resolve_candidates(task)
        failures=[]
        for route in routes:
            try:
                parsed=self._complete_on_route(task,request,route)
                return self._unblind_showrunner_result(parsed,reverse)
            except ProviderError as error:
                failures.append(f"{route.provider}/{route.model}:{str(error)[:300]}")
        if len(routes)==1 and failures:
            # Preserve precise single-route operational diagnostics used by the
            # durable product recovery state machine.
            raise ProviderError(failures[0].split(':',1)[1])
        raise ProviderError(f"LIVE_PROVIDER_BLOCKED_ALL_COMPATIBLE_ROUTES_FAILED:{task}:"+" | ".join(failures)[:1800])

    def audit_dicts(self): return [asdict(x) for x in self.audits]
    def perceptual_delivery_dicts(self): return list(self.perceptual_deliveries)
    def candidate_order_audit_dicts(self): return list(self.candidate_order_audits)
