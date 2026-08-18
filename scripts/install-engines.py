from pathlib import Path
import shutil, zipfile
ROOT=Path(__file__).resolve().parents[1]
SOURCES=ROOT/'engine_sources'; ENGINES=ROOT/'engines'
items={
 'whiteboard':'WHITEBOARD_ENGINE_SOURCE.zip',
 'explainer':'EXPLAINER_ENGINE_SOURCE.zip',
 'editorial':'EDITORIAL_MOTION_ENGINE_SOURCE.zip',
 'stickman':'STICKMAN_V5_1_ENGINE_SOURCE.zip',
 'sound':'SOUND_LIBRARY_V2_SOURCE.zip',
}
ENGINES.mkdir(exist_ok=True)
for name,archive in items.items():
 target=ENGINES/name
 if target.exists(): shutil.rmtree(target)
 target.mkdir(parents=True)
 with zipfile.ZipFile(SOURCES/archive) as z: z.extractall(target)
 print(f'{name}: {target}')

# Explainer archive is an execution-only authored-art body beneath full NexMind P8.
# It is self-contained and must not be supplemented with the P14.1 DirectorV3/semantic-family path.
# Runtime TypeScript executes via the Standalone root node_modules/tsx while cwd is
# the extracted Explainer execution-body root, so its own tsconfig aliases remain authoritative.

# NexStick V5.1 runtime is authored as CommonJS. The standalone Next app is ESM,
# so establish a local package boundary after extraction without altering vendor files.
stick_root=ENGINES/'stickman'/'NEXSTICK_MASTER_V2_UNIFIED_PERFORMANCE_V5_1_CLEAN_2026-08-13'
if stick_root.exists():
    (stick_root/'package.json').write_text('{\n  \"type\": \"commonjs\"\n}\n')

print('\nEngine source installed, shared Paper Motion dependencies assembled, and runtime package boundaries applied. Use the paths in .env.example.')
