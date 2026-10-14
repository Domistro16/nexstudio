#!/usr/bin/env python3
"""Presenter video job: saved Cast character + script (or voice upload) -> MP4 per format.

python3 presenter-job.py JOB_DIR
JOB_DIR/request.json: {config, script, voice, voiceFile?, aspects, background, accent?,
                       promo?: {mode, name, image?, label?}}
Writes progress.json while running and status.json with the outputs at the end.
Voice -> phonemes (MFA) -> gesture plan -> Blender motion timeline -> browser point
cache -> headless Chrome frames -> kinetic captions, background and promo -> MP4.
"""
import fcntl, functools, hashlib, http.server, json, os, re, shutil, subprocess, sys, threading, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/studio-family-engines'))
from parallel_aspects import render_aspects
S = ROOT / 'scripts'
WEB = S / 'presenter-browser'
BLENDER = os.environ.get('BLENDER_BIN') or shutil.which('blender') or '/opt/blender-5.2.1-linux-x64/blender'
SOURCE = Path(os.environ.get('CAST_SOURCE_DIR', ROOT / 'engine_sources/makehuman-lineart/presenters_v1'))
SCENES = Path(os.environ.get('PRESENTER_SCENE_CACHE', ROOT / 'engine_sources/makehuman-lineart/out/presenter-scenes'))
KINETIC = os.environ.get('WHITEBOARD_KINETIC_RUNTIME_DIR') or next(
    (str(d) for d in (Path.home() / 'wb-kinetic-runtime', Path.home() / 'work/wb-kinetic-runtime')
     if (d / 'kinetic_icons.py').exists()),
    str(ROOT / 'engine_sources/whiteboard-v3-runtime'))
VOICES = {
    'emma': 'en-US-EmmaMultilingualNeural', 'ava': 'en-US-AvaMultilingualNeural',
    'andrew': 'en-US-AndrewMultilingualNeural', 'brian': 'en-US-BrianMultilingualNeural',
    'sonia': 'en-GB-SoniaNeural', 'natasha': 'en-AU-NatashaNeural',
}
ENVIRONMENTS = ROOT / 'public/cast/environments'
FOLDER = {'16:9': 'landscape', '1:1': 'square', '9:16': 'portrait'}
SCENES_ENGINE = Path(os.environ.get('WHITEBOARD_SCENES_RUNTIME_DIR',
                                    ROOT / 'engine_sources/whiteboard-board-scenes'))
LESSON_BG = 'lesson_board'
KIDS_BG = 'kids_book'
EDITORIAL_ENGINE = Path(os.environ.get('EDITORIAL_MOTION_RUNTIME_DIR',
                                       ROOT / 'engine_sources/editorial-motion-v2'))
WHISPER_PY = Path(os.environ.get('NEXSTUDIO_WHISPER_PYTHON',
                                 str(Path.home() / 'tools/whisper/bin/python3')))
PROFILE = dict(CAST_QUALITY_PILOT='1', CAST_FINISH_UPGRADE='1', CAST_GARMENT_STRUCTURE_PILOT='1',
               CAST_SKIN_APPEARANCE='1', CAST_HAIR_GROOM='1', CAST_FACIAL_REFINEMENT='1', CAST_CLOTH_APPEARANCE='1')
STEPS = ['voice', 'lipsync', 'gestures', 'character', 'motion', 'frames', 'compose']

_MFA = Path.home() / 'tools/mamba/envs/mfa/bin/mfa'
if _MFA.exists():
    os.environ.setdefault('MFA_BIN', str(_MFA))
_WHISPER = Path.home() / 'tools/whisper/bin/python3'
if _WHISPER.exists():
    os.environ.setdefault('WHISPER_PYTHON', str(_WHISPER))
J = Path(sys.argv[1]).resolve()
REQ = json.loads((J / 'request.json').read_text())
LOG = (J / 'job.log').open('a')


def progress(phase, pct=None, **extra):
    i = STEPS.index(phase)
    base = i / len(STEPS)
    span = 1 / len(STEPS)
    p = base + span * (pct if pct is not None else 0)
    (J / 'progress.json').write_text(json.dumps({'phase': phase, 'step': i + 1, 'steps': len(STEPS),
                                                 'percent': round(p * 100), **extra}))


def run(cmd, env=None, cwd=None):
    LOG.write(f'$ {" ".join(map(str, cmd))}\n'); LOG.flush()
    subprocess.run([str(c) for c in cmd], env=env, cwd=cwd or ROOT, stdout=LOG, stderr=subprocess.STDOUT, check=True)


def cast_env():
    env = dict(os.environ, **REQ['config']['env'], **PROFILE)
    env.update(CAST_SOURCE_DIR=str(SOURCE), BLENDER_BIN=BLENDER, CAST_RENDER_ENTRY=str(S / 'cast-render-assembled.py'),
               MH_ROOT=os.environ.get('MH_ROOT', str(SOURCE.parent / 'assets')), PYTHONUNBUFFERED='1', OPENBLAS_NUM_THREADS='1')
    return env


def voice():
    progress('voice')
    wav = J / 'voice.wav'
    script = (REQ.get('script') or '').strip()
    if REQ.get('voiceFile'):
        run(['ffmpeg', '-loglevel', 'error', '-y', '-i', J / REQ['voiceFile'], '-ac', '1', '-ar', '24000', wav])
    else:
        sys.path.insert(0, str(ROOT / 'engine_sources/whiteboard-v3-runtime'))
        import vo_synth
        vo_synth.synth_edge(script, wav, voice=VOICES[REQ.get('voice') or 'andrew'], speed=float(REQ.get('speed') or 1.0))
    if script:
        (J / 'script.txt').write_text(script + '\n')
    return wav


def lipsync(wav):
    progress('lipsync')
    out = J / 'phones.json'
    run([sys.executable, S / 'cast-phoneme-align.py', wav, J / 'script.txt' if (J / 'script.txt').exists() else '-', out])
    if not (J / 'script.txt').exists():
        words = json.loads(out.read_text())['words']
        (J / 'script.txt').write_text(' '.join(w[2] for w in words) + '\n')
    return out


def punctuated(words, script):
    """Aligner words lose punctuation; carry the script's sentence ends back onto them."""
    norm = lambda w: re.sub(r"[^\w']+", '', w.lower())
    toks = [t for t in script.split() if norm(t)]
    out, j = [], 0
    for s0, e0, w in words:
        k = next((k for k in range(j, min(j + 4, len(toks))) if norm(toks[k]) == norm(w)), None)
        if k is not None:
            j = k + 1
            w = w + (re.search(r'[.!?]+$', toks[k]).group(0) if re.search(r'[.!?]+$', toks[k]) else '')
        out.append([s0, e0, w])
    return out


def gestures(wav, phones):
    progress('gestures')
    out = J / 'timeline.json'
    seed = int(hashlib.sha256(J.name.encode()).hexdigest()[:6], 16)
    words = punctuated(json.loads(Path(phones).read_text())['words'], (J / 'script.txt').read_text())
    (J / 'words.json').write_text(json.dumps(words))
    run([sys.executable, S / 'cast-gesture-plan.py', J / 'words.json', out, '--audio', wav, '--phonemes', phones,
         '--presenter', REQ['config']['env']['CAST_CHARACTER'], '--seed', seed, '--profile', 'presenter'])
    return out


def character():
    progress('character')
    key = hashlib.sha256(json.dumps(REQ['config'], sort_keys=True).encode()).hexdigest()
    d = SCENES / key
    d.mkdir(parents=True, exist_ok=True)
    # The scene cache is shared across jobs using the same cast config, so the
    # exists()-check alone lets concurrent jobs write assembled.tmp.blend at
    # once and each other's rename steals the file (FileNotFoundError) or
    # caches a half-written scene. Serialize the build under a lock.
    lock = (d / 'build.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        scene = d / 'assembled.blend'
        if not scene.exists():
            (d / 'request.json').write_text(json.dumps({'config': REQ['config']}))
            tmp = d / 'assembled.tmp.blend'
            run(['bash', S / 'cast-preview-render.sh', d / 'request.json', d / 'render.png', '--scene-output', tmp], env=cast_env())
            tmp.rename(scene)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
    return scene


def motion(scene, timeline):
    progress('motion', 0.0)
    env = cast_env()
    animated = J / 'animated.blend'
    run([BLENDER, '-b', scene, '--python-exit-code', '1', '--python', S / 'cast-gesture-timeline.py', '--', timeline, animated], env=env)
    total = round(json.loads((J / 'phones.json').read_text())['words'][-1][1] * 24) + 12
    progress('motion', 0.1)
    run([BLENDER, '-b', animated, '--python-exit-code', '1', '--python', WEB / 'ref_frame.py', '--', J / 'ref.png', 1], env=env)
    progress('motion', 0.2)
    run([BLENDER, '-b', animated, '--python-exit-code', '1', '--python', WEB / 'cache.py', '--', J / 'cache', 1, 1, total, J / 'ref.png'], env=env)
    run([sys.executable, WEB / 'filter_lines.py', J / 'cache', J / 'ref.png'])
    return total


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def frames(total):
    progress('frames', 0.0)
    web = J / 'web'
    web.mkdir(exist_ok=True)
    for name, target in [('index.html', WEB / 'index.html'), ('render.mjs', WEB / 'render.mjs'),
                         ('three', ROOT / 'node_modules/three'), ('cache', J / 'cache')]:
        link = web / name
        if not link.exists():
            link.symlink_to(target)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(web)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    out = J / 'frames'
    out.mkdir(exist_ok=True)
    done = threading.Event()

    def watch():
        while not done.wait(5):
            progress('frames', min(0.99, len(list(out.glob('*.png'))) / total), frames=total)
    threading.Thread(target=watch, daemon=True).start()
    try:
        url = f'http://127.0.0.1:{srv.server_address[1]}/index.html?d=./cache/'
        run(['node', WEB / 'capture.mjs', url, 1, total, out, os.environ.get('PRESENTER_CAPTURE_WORKERS', '4')])
    finally:
        done.set()
        srv.shutdown()
    return out


def lesson_title():
    """'\# Lesson name' heading convention first, else the opening words."""
    lines = [l.strip() for l in (J / 'script.txt').read_text().splitlines() if l.strip()]
    if lines and lines[0].startswith('#'):
        return lines[0].lstrip('#').strip() or 'Lesson'
    words = (lines[0].split() if lines else [])[:6]
    return ' '.join(words) or 'Lesson'


def lesson_boards(wav, aspects):
    """Board-scenes render behind the teacher, driven by this job's own voice.wav
    and MFA word timings so board and character stay in sync. The job runner
    plans, gates and renders every aspect; GATE_REFUSED fails the job rather
    than ship a broken lesson."""
    out = J / 'board'
    words = json.loads((J / 'words.json').read_text())
    timings = out / 'vo_words.json'
    out.mkdir(exist_ok=True)
    timings.write_text(json.dumps(
        [{'word': w[2], 'start': w[0], 'end': w[1]} for w in words]))
    run([sys.executable, SCENES_ENGINE / 'tools/nexstudio_job.py',
         '--script', J / 'script.txt', '--voice-file', wav, '--type', 'board-scenes',
         '--title', lesson_title(), '--aspects', ','.join(aspects),
         '--word-timings', timings,
         '--out', out, '--job-id', J.name],
        env={**os.environ, 'WHITEBOARD_SCENES_RUNTIME_DIR': str(SCENES_ENGINE)})
    return json.loads((out / 'manifest.json').read_text())['outputs']


def kids_books(wav, aspects):
    """Kids math/storybook lesson: paperbook pages (ten-frames, addition joins,
    number lines — edu.py) drawn behind the teacher. Same voice.wav drives both
    passes; --no-poster keeps the film aligned to it (the poster holds + delays)."""
    out = J / 'book'
    asp = ','.join(a.replace(':', 'x') for a in aspects)
    node_bin = Path.home() / '.nvm/versions/node/v24.19.0/bin'
    run([str(WHISPER_PY) if WHISPER_PY.exists() else sys.executable,
         EDITORIAL_ENGINE / 'tools/make_reel.py',
         '--script-file', J / 'script.txt', '--voice-file', wav,
         '--book', 'paperbook', '--aspects', asp, '--no-poster',
         '--out', out],
        env={**os.environ, 'PATH': str(node_bin) + os.pathsep + os.environ['PATH']})
    man = json.loads((out / 'manifest.json').read_text())['outputs']
    return {a: man[a.replace(':', 'x')] for a in aspects if a.replace(':', 'x') in man}


def compose(frames_dir, boards=None):
    aspects = REQ.get('aspects') or ['16:9']
    promo = REQ.get('promo') or {}
    progress('compose', 0, aspectsActive=aspects)

    def render(a):
        key = a.replace(':', 'x')
        out = J / 'files' / f'{key}.mp4'
        out.parent.mkdir(exist_ok=True)
        cmd = [sys.executable, S / 'presenter-compose.py', '--frames', frames_dir, '--audio', J / 'voice.wav',
               '--words', J / 'phones.json', '--script', J / 'script.txt', '--aspect', a,
               '--out', out, '--kinetic-dir', KINETIC]
        if boards and a in boards:
            cmd += ['--background-video', boards[a], '--lesson']
        else:
            bg = ENVIRONMENTS / FOLDER[a] / f"{REQ.get('background') or 'neutral_studio'}.jpg"
            cmd += ['--background', bg]
        if REQ.get('accent'):
            cmd += ['--accent', REQ['accent']]
        # cinematic effects are opt-out; infographic cards are opt-in
        if REQ.get('cinematic') is False:
            cmd += ['--captions', 'pill']
        if REQ.get('infographic'):
            cmd += ['--infographic']
        if promo.get('mode') in ('lower-third', 'squeeze'):
            cmd += ['--promo', promo['mode'], '--promo-name', promo['name']]
            if promo.get('image'):
                cmd += ['--promo-image', J / promo['image']]
            if promo.get('label'):
                cmd += ['--promo-label', promo['label']]
        run(cmd)
        plan_file = out.with_suffix('.director.json')
        if plan_file.exists():
            plan_file.rename(J / f'director-plan-{key}.json')  # the executed shot grammar, per aspect
        return f'/api/v1/presenters/{J.name}/files/{out.name}'

    outputs = render_aspects(aspects, render,
                            lambda aspect, count, total: progress('compose', count / total))
    return {aspect.replace(':', 'x'): output for aspect, output in outputs.items()}


def main():
    started = time.monotonic()
    try:
        wav = voice()
        phones = lipsync(wav)
        timeline = gestures(wav, phones)
        boards = None
        if REQ.get('background') == LESSON_BG:
            boards = lesson_boards(wav, REQ.get('aspects') or ['16:9'])
        elif REQ.get('background') == KIDS_BG:
            boards = kids_books(wav, REQ.get('aspects') or ['16:9'])
        scene = character()
        total = motion(scene, timeline)
        fdir = frames(total)
        outputs = compose(fdir, boards)
        shutil.rmtree(J / 'frames', ignore_errors=True)
        shutil.rmtree(J / 'cache', ignore_errors=True)
        for f in ('animated.blend', 'animated.blend1'):
            (J / f).unlink(missing_ok=True)
        status = {'status': 'done', 'outputs': outputs, 'seconds': round(time.monotonic() - started)}
    except Exception as e:
        LOG.write(f'FAILED {e!r}\n')
        status = {'status': 'failed', 'error': 'The presenter video could not be made. Try again, or shorten the script.',
                  'detail': type(e).__name__, 'seconds': round(time.monotonic() - started)}
    status['finishedAt'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    (J / 'status.json').write_text(json.dumps(status))
    print('PRESENTER_JOB', json.dumps(status), flush=True)


if __name__ == '__main__':
    main()
