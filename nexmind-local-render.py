#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys
from pathlib import Path
from datetime import datetime

AUTHORITIES = {
    'WHITEBOARD': 'WHITEBOARD_EXECUTION_BODY_V2_P8_UNIFIED',
    'EDITORIAL_MOTION': 'EDITORIAL_EXECUTION_BODY_V2_P8_UNIFIED',
    'STICKMAN': 'NEXSTICK_MASTER_V2_PERFORMANCE_V5_1',
}

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def main() -> int:
    ap = argparse.ArgumentParser(description='Persistently render a local NexStudio family smoke MP4.')
    ap.add_argument('family', choices=sorted(AUTHORITIES))
    ap.add_argument('--root', default='.', help='Extracted NexStudio source root')
    ap.add_argument('--output', default='', help='Output directory (default: local-renders/<family>-timestamp)')
    ap.add_argument('--chromium', default='', help='Chromium executable path')
    args = ap.parse_args()

    root = Path(args.root).resolve()
    worker = root / 'services' / 'studio-family-engines' / 'worker.py'
    if not worker.exists():
        raise SystemExit(f'worker.py not found under {root}')

    engine_paths = {
        'WHITEBOARD': root / 'engines/whiteboard/Whiteboard_Execution_Body_V2',
        'EDITORIAL_MOTION': root / 'engines/editorial',
        'STICKMAN': root / 'engines/stickman/NEXSTICK_MASTER_V2_UNIFIED_PERFORMANCE_V5_1_CLEAN_2026-08-13',
        'SOUND': root / 'engines/sound/NexStudio_Sound_Library_V2_Production',
    }
    missing = [str(p) for p in engine_paths.values() if not p.exists()]
    if missing:
        raise SystemExit('Engines are not installed. First run: python3 scripts/install-engines.py\nMissing:\n' + '\n'.join(missing))

    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    out = Path(args.output).resolve() if args.output else root / 'local-renders' / f'{args.family.lower()}-{stamp}'
    out.mkdir(parents=True, exist_ok=True)

    if args.family == 'STICKMAN':
        action = {
            'action_id': 'A1', 'performer_class': 'STICKMAN_V2', 'actor': 'male presenter broad',
            'requested_verb': 'HOLD', 'execution': {'resolved_verb': 'HOLD'},
            'contact_requirement': 'NONE', 'available_requirements': []
        }
        thesis, hero = 'A presenter holds a calm opening pose.', 'presenter'
    else:
        action = {
            'action_id': 'A1', 'performer_class': 'SCENE_GRAPH', 'actor': 'scene',
            'requested_verb': 'TYPE_REVEAL', 'execution': {'resolved_verb': 'TYPE_REVEAL'},
            'contact_requirement': 'NONE', 'available_requirements': []
        }
        thesis, hero = 'MAKE THE IDEA CLEAR.', 'central idea'

    board = {
        'schema': 'NexMindCanonicalSoundStoryboardV4',
        'beats': [{
            'beat_id': 'B1', 'scene_thesis': thesis, 'hero_identity': hero, 'supporting_assets': [],
            'continuity_in': 'opening', 'continuity_out': 'settled',
            'motion_plan_status': 'DIRECTED_MOTION_PERFORMANCE', 'sound_plan_status': 'DIRECTED_SOUND',
            'motion_actions': [action],
            'sound_events': [{'event_id': 'S1', 'kind': 'SILENCE', 'semantic_tag': '', 'intensity': 'NONE'}],
            'editorial': {'duration': {'value': 2, 'rate': 1}},
            'camera': {'semantic_target': hero, 'camera_atom': {'motivation': 'establish the directed subject'}}
        }]
    }
    request = {
        'schema': 'StudioFamilyEngineRequestV1',
        'operation': 'BUILD_INTERNAL_REVIEW_EVIDENCE',
        'family': args.family,
        'authorityId': AUTHORITIES[args.family],
        'productionId': 'local-render-' + args.family.lower(),
        'creativeStateArtifactId': 'local-smoke-state',
        'creativeStateArtifactHash': 'a' * 64,
        'durationSeconds': 2,
        'aspectRatio': '16:9',
        'outputDirectory': str(out),
        'brandExecution': {
            'schema': 'StudioBrandExecutionV1', 'sourceAuthority': 'MEMORY_INPUT',
            'memoryInputSnapshotId': 'local-smoke-memory', 'memoryInputSnapshotHash': 'b' * 64,
            'brandExecutionHash': 'c' * 64, 'tokens': {}
        },
        'finalBoard': board,
    }
    (out / 'request.json').write_text(json.dumps(request, indent=2) + '\n')

    chromium = args.chromium or shutil.which('chromium') or shutil.which('chromium-browser') or ''
    env = {**os.environ,
           'STUDIO_WHITEBOARD_ENGINE_ROOT': str(engine_paths['WHITEBOARD']),
           'STUDIO_EDITORIAL_ENGINE_ROOT': str(engine_paths['EDITORIAL_MOTION']),
           'STUDIO_STICKMAN_ENGINE_ROOT': str(engine_paths['STICKMAN']),
           'STUDIO_SOUND_LIBRARY_ROOT': str(engine_paths['SOUND'])}
    if chromium:
        env['STUDIO_CHROMIUM_PATH'] = chromium

    cp = subprocess.run([sys.executable, str(worker)], input=json.dumps(request), text=True,
                        capture_output=True, cwd=worker.parent, env=env)
    if cp.stderr:
        (out / 'worker.stderr.txt').write_text(cp.stderr)
    if cp.returncode != 0:
        print(cp.stderr, file=sys.stderr)
        return cp.returncode
    result = json.loads(cp.stdout)
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')

    print(json.dumps({'status': result.get('status'), 'code': result.get('code'),
                      'technicalQa': (result.get('technicalQa') or {}).get('status')}, indent=2))
    videos = []
    for item in result.get('artifacts') or []:
        p = Path(item.get('path', ''))
        if p.exists():
            actual = sha256(p)
            print(f"{item.get('kind')}: {p} | sha256={actual} | hashMatches={actual == item.get('sha256')}")
            if item.get('kind') == 'VIDEO': videos.append(p)
    if videos:
        print('\nWATCH THIS MP4:')
        print(videos[0])
        return 0
    print('\nNo VIDEO artifact was produced. Inspect result.json and worker.stderr.txt in:')
    print(out)
    return 1

if __name__ == '__main__':
    raise SystemExit(main())
