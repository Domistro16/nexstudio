from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
def _default_stickman_registry() -> Path:
    configured = os.getenv("STUDIO_STICKMAN_ENGINE_ROOT", "").strip()
    roots = [Path(configured)] if configured else []
    roots += [ROOT / "engines" / "stickman"]
    for base in roots:
        base = base if base.is_absolute() else (ROOT / base).resolve()
        candidates = [base, *[x for x in base.glob("*") if x.is_dir()]] if base.exists() else []
        for candidate in candidates:
            registry = candidate / "NEXSTICK_MASTER_V2_CAPABILITY_REGISTRY.json"
            if registry.exists():
                return registry
    return ROOT / "engines" / "stickman" / "NEXSTICK_MASTER_V2_UNIFIED_PERFORMANCE_V5_1_CLEAN_2026-08-13" / "NEXSTICK_MASTER_V2_CAPABILITY_REGISTRY.json"

DEFAULT_STICKMAN_REGISTRY = _default_stickman_registry()


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _requirements() -> Dict[str, set[str]]:
    # These are standalone-adapter requirements, not merely engine-donor claims.
    # P8 must only author motions that the current deterministic evidence adapter
    # can execute without inventing props, targets, world anchors or contact.
    return {
        "REACH": {"high_reach_target"},
        "PRESENT": {"presentation_prop"},
        "TYPE": {"typing_surface"},
        "PHONE_HOLD": {"phone_prop"},
    }


def build_stickman_v5_1_override(registry: Dict[str, Any]) -> Dict[str, Any]:
    """Map the current V5.1 performance master into P8's frozen performer vocabulary.

    `STICKMAN_V2` is retained only as a P8 schema compatibility alias. The evidence
    packet is explicitly rebound to the current V5.1 authority. Capabilities that
    are not explicitly proven by the V5.1 registry stay fail-closed.
    """
    caps = registry.get("productionCapabilities") or {}
    interaction = set(caps.get("interaction") or [])
    acting = set(caps.get("acting") or [])
    locomotion = set(caps.get("locomotion") or [])

    supported = {
        "HOLD",
        "WALK",
        "RUN",
        "REACH",
        "PRESENT",
        "TYPE",
        "PHONE_HOLD",
    }
    # This packet describes the CURRENT STANDALONE ADAPTER, not every donor in
    # the V5.1 engine. A verb stays blocked until its engine binding, world/contact
    # requirements and strict sequence QA are all connected end-to-end.
    blocked = {
        "LOOK": "STANDALONE_ADAPTER_LOOK_TARGET_BINDING_NOT_PROVEN",
        "SPRINT": "CURRENT_V5_1_SPRINT_DONOR_NOT_CERTIFIED",
        "SIT": "STANDALONE_ADAPTER_SEAT_WORLD_BINDING_PENDING",
        "STAND": "STANDALONE_ADAPTER_SEAT_WORLD_BINDING_PENDING",
        "POINT": "CURRENT_V5_1_POINT_VERB_NOT_CERTIFIED",
        "PRESS": "STANDALONE_ADAPTER_BUTTON_TARGET_BINDING_PENDING",
        "TAP": "CURRENT_V5_1_TAP_VERB_NOT_CERTIFIED",
        "PICKUP": "STANDALONE_ADAPTER_GRIP_WORLD_BINDING_PENDING",
        "PLACE": "STANDALONE_ADAPTER_SUPPORT_WORLD_BINDING_PENDING",
        "CARRY_LIGHT": "STANDALONE_ADAPTER_CARRY_WORLD_BINDING_PENDING",
        "CARRY_HEAVY": "FAIL_CLOSED_NO_ADMITTED_HEAVY_DONOR",
        "DANCE": "STANDALONE_ADAPTER_DANCE_STRICT_JERK_QA_NOT_PROVEN",
        "HANDOFF_DIRECT": "STANDALONE_ADAPTER_PAIRED_HANDOFF_BINDING_PENDING",
        "HANDOFF_PLACE_AND_TAKE": "STANDALONE_ADAPTER_PAIRED_HANDOFF_BINDING_PENDING",
        "SIDESTEP": "CURRENT_V5_1_SIDESTEP_DONOR_NOT_CERTIFIED",
        "LATERAL_REPOSITION": "CURRENT_V5_1_LATERAL_REPOSITION_NOT_CERTIFIED",
    }

    evidence = {
        "authority": registry.get("name"),
        "masterVersion": registry.get("masterVersion"),
        "engine": registry.get("performanceEngine"),
        "status": registry.get("status"),
        "compatibilityAlias": "P8_STICKMAN_V2_SCHEMA_ALIAS_TO_CURRENT_V5_1",
        "sourceRegistrySha256": canonical_hash(registry),
        "contactCorrectionMaxM": (registry.get("architecture") or {}).get("finalContactResidualCapM"),
        "ownership": "contact/load gated; no ownership teleport",
        "directHandoff": "V5.1 engine evidence exists, but standalone paired-handoff adapter binding remains fail-closed until connected",
        "standaloneAdapterSupportedVerbs": sorted(supported),
        "heavyCarry": caps.get("heavyCarry"),
        "families": list((registry.get("cast") or {}).get("families") or []),
        "certification": deepcopy((registry.get("certification") or {}).get("releaseSummary") or {}),
        "sourceSignals": {
            "locomotion": sorted(locomotion),
            "acting": sorted(acting),
            "interaction": sorted(interaction),
        },
    }
    return {
        "supported": supported,
        "blocked": blocked,
        "requirements": _requirements(),
        "evidence": evidence,
    }


def load_current_capability_packet(path: str | Path = DEFAULT_STICKMAN_REGISTRY) -> Dict[str, Any]:
    p = Path(path)
    registry = json.loads(p.read_text(encoding="utf-8"))
    return {
        "schema": "StudioNexMindCapabilityPacketV1",
        "authorities": {
            "stickman": {
                "registry": registry,
                "sha256": canonical_hash(registry),
            }
        },
        "performerOverrides": {
            "STICKMAN_V2": build_stickman_v5_1_override(registry),
        },
    }



def _art_generation_available() -> bool:
    raw = os.environ.get("NEXSTUDIO_ART_EXECUTION_REGISTRY_JSON", "").strip()
    if not raw:
        return False
    try:
        registry = json.loads(raw)
    except Exception:
        return False
    caps = registry.get("capabilities") if isinstance(registry, dict) else None
    gen = caps.get("authored_scene_illustration") if isinstance(caps, dict) else None
    review = caps.get("authored_scene_pixel_fidelity_review") if isinstance(caps, dict) else None
    return all(isinstance(rec, dict) and rec.get("transport") == "command" and bool(rec.get("command")) for rec in (gen,review))


def _fallback_family_execution_authority(family: str) -> Dict[str, Any]:
    """Bind direct/preflight P8 calls to the checked-in family execution authority.

    The production workflow normally supplies the runtime authority explicitly.
    Direct Python preflights do not pass through that TypeScript workflow, so without
    this fallback they previously reported familyExecutionAuthority={} and deprived
    the creative brain of the execution-body identity it is meant to target. The
    explicit request authority always wins; this fallback never grants public-ship
    eligibility or invents capabilities absent from the checked-in registry.
    """
    registry_path=ROOT / "src" / "studio-v1" / "public" / "certification" / "four-family-capability-registry.json"
    try:
        registry=json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    rec=((registry.get("families") or {}).get(str(family or "").lower()) or {}) if isinstance(registry,dict) else {}
    authority=rec.get("authority") if isinstance(rec,dict) else None
    if not isinstance(authority,dict) or not str(authority.get("authorityId") or "").strip():
        return {}
    return {
        "authorityId":str(authority.get("authorityId") or ""),
        "sourceLabel":str(authority.get("sourceLabel") or ""),
        "sourceArchiveSha256":str(authority.get("sha256") or ""),
        "technicalStatus":str(authority.get("technical") or ""),
        "executionBody":str(authority.get("execution") or ""),
        "sourceRegistry":"src/studio-v1/public/certification/four-family-capability-registry.json",
        "sourceRegistrySha256":canonical_hash(registry),
        "authorityMode":"DIRECT_PREFLIGHT_FALLBACK__EXPLICIT_WORKFLOW_AUTHORITY_OVERRIDES",
    }

def build_capability_graph(request: Dict[str, Any], packet: Dict[str, Any]) -> Dict[str, Any]:
    family = str(request.get("family") or "").upper()
    base = deepcopy(request.get("capabilityGraph") or {})
    supplied_authority=deepcopy(base.get("familyExecutionAuthority") or {})
    authorities={"family_execution_body": supplied_authority if supplied_authority else _fallback_family_execution_authority(family)}
    if family == "STICKMAN":
        authorities["stickman"]={
            "name": packet["authorities"]["stickman"]["registry"].get("name"),
            "masterVersion": packet["authorities"]["stickman"]["registry"].get("masterVersion"),
            "performanceEngine": packet["authorities"]["stickman"]["registry"].get("performanceEngine"),
            "registrySha256": packet["authorities"]["stickman"]["sha256"],
        }
    base.update({
        "schema": "StudioNexMindCapabilityGraphV2",
        "production_family": family,
        "video_type": request.get("videoType"),
        "duration_seconds": request.get("durationSeconds"),
        "aspect_ratio": request.get("aspectRatio"),
        "current_authorities": authorities,
        "public_family_constraints": list(((base.get("familyExecutionCapabilities") or {}).get("performerClasses") or [])),
        "family_execution_capabilities": deepcopy(base.get("familyExecutionCapabilities") or {}),
        # This bridge must not invent an asset-generation body merely to make an
        # Art Director proposal pass. A later current NexArt capability packet may
        # explicitly enable this.
        "production_scoped_asset_generation": bool(base.get("production_scoped_asset_generation", False) or _art_generation_available()),
    })
    return base
