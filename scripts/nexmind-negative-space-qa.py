#!/usr/bin/env python3
from __future__ import annotations
import json,re,sys,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCAN=[ROOT/'src',ROOT/'services',ROOT/'config']
EXT={'.ts','.tsx','.js','.mjs','.cjs','.py','.json'}
# Architecture-owned active source must not contain literal model identities.
MODEL_PATTERNS=[
    re.compile(r'(?i)gpt[-_. ]?5(?:\.6)?[-_. ]?(?:luna|sol)'),
    re.compile(r'(?i)\b(?:openai-)?gpt-5\.6-(?:luna|sol)\b'),
    re.compile(r'(?i)\bdeepseek(?:[-_/][a-z0-9.:-]+)?\b'),
]
REJECTED_AUTHORITY_PATTERNS=[
    re.compile(r'\bDirectorV3\b'),
    re.compile(r'canonical\.explainer_plan'),
    re.compile(r'\bP14\.1\b'),
]
# Files which intentionally describe backward-compatibility/source evidence are
# not architecture-owned routing. Vendored/engine snapshots are excluded.
EXCLUDE_PARTS={'vendor','engine_sources','reports','docs','fixtures','__pycache__','node_modules'}
violations=[]
for base in SCAN:
    if not base.exists(): continue
    for path in base.rglob('*'):
        if not path.is_file() or path.suffix.lower() not in EXT: continue
        rel=path.relative_to(ROOT)
        if any(part in EXCLUDE_PARTS for part in rel.parts): continue
        try: data=path.read_text(encoding='utf-8',errors='ignore')
        except Exception: continue
        for pat in MODEL_PATTERNS:
            for m in pat.finditer(data):
                violations.append({'kind':'hardcoded_model_identity','path':str(rel),'match':m.group(0)[:120]})
        # Rejected authorities may occur in negative assertions. Only flag executable imports/calls/config authority declarations.
        for pat in REJECTED_AUTHORITY_PATTERNS:
            for m in pat.finditer(data):
                line=data.count('\n',0,m.start())+1
                snippet=data.splitlines()[line-1] if data.splitlines() else ''
                lower=snippet.lower()
                if any(token in lower for token in ('forbid','reject','must not','no ','not ','legacy','deleted','assert','ban','remove','stale')): continue
                if rel.name.endswith(('_qa.py','qa.py')) or 'test' in rel.parts: continue
                violations.append({'kind':'reachable_rejected_authority_reference','path':str(rel),'line':line,'match':m.group(0),'snippet':snippet.strip()[:220]})

routing=(ROOT/'src/lib/nexmind-routing.ts').read_text(encoding='utf-8')

def zip_names(path:Path):
    if not path.exists():
        violations.append({'kind':'missing_authoritative_engine_archive','path':str(path.relative_to(ROOT))})
        return []
    try:
        with zipfile.ZipFile(path) as zf:
            return [n.lower() for n in zf.namelist()]
    except Exception as exc:
        violations.append({'kind':'invalid_authoritative_engine_archive','path':str(path.relative_to(ROOT)),'detail':type(exc).__name__})
        return []

wb_names=zip_names(ROOT/'engine_sources/WHITEBOARD_ENGINE_SOURCE.zip')
ed_names=zip_names(ROOT/'engine_sources/EDITORIAL_MOTION_ENGINE_SOURCE.zip')
wb_forbidden=[n for n in wb_names if any(x in n for x in ('narrative-director','director-v3','p14.1','canonical.explainer_plan'))]
ed_forbidden=[n for n in ed_names if any(x in n for x in ('level1_shared_intelligence','level2_world_editorial','level3_film_state','level4_art_composition','public-hardening','director-v3','p14.1'))]
if wb_forbidden:
    violations.append({'kind':'whiteboard_archive_contains_retired_creative_stack','path':'engine_sources/WHITEBOARD_ENGINE_SOURCE.zip','matches':wb_forbidden[:20]})
if ed_forbidden:
    violations.append({'kind':'editorial_archive_contains_retired_creative_stack','path':'engine_sources/EDITORIAL_MOTION_ENGINE_SOURCE.zip','matches':ed_forbidden[:20]})

editorial_adapter=(ROOT/'services/studio-family-engines/editorial_adapter.py').read_text(encoding='utf-8')
checks={
 'plan_preview_capability_routed':'creative_reasoning' in routing,
 'plan_preview_no_named_default':'gpt-5.6-luna' not in routing.lower() and 'gpt-5.6-sol' not in routing.lower(),
 'model_registry_supported':'NEXMIND_MODEL_REGISTRY_JSON' in routing,
 'no_default_provider_identity':'provider:"openai"' not in routing.replace(' ',''),
 'missing_config_fails_as_capability_config':'NEXMIND_NO_COMPATIBLE_MODEL_CONFIG' in routing,
 'whiteboard_archive_execution_only':not wb_forbidden,
 'editorial_archive_execution_only':not ed_forbidden,
 'editorial_adapter_imports_execution_only_renderer':'editorial_renderer_execution' in editorial_adapter and 'level5_renderer_execution' not in editorial_adapter,
 'active_scan_clean':not violations,
}
result={'schema':'NexMindNegativeSpaceQAV2','status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'violations':violations}
out=ROOT/'reports/NEXMIND_NEGATIVE_SPACE_QA.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
sys.exit(0 if result['status']=='PASS' else 1)
