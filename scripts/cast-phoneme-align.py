#!/usr/bin/env python3
"""Phoneme timings for lip sync from a voiceover and its script (local, CPU).

Usage: python3 cast-phoneme-align.py voice.wav script.txt|- out.json
faster-whisper (MIT) finds word times; the audio is cut at pauses into short
chunks, the script's words are matched to each chunk, and the Montreal Forced
Aligner (MIT; english_us_arpa) aligns every chunk. Anchoring stops long or
music-led recordings from sliding. With "-" the Whisper transcript is used.
Writes {"phones": [[s, e, "ARPAbet"]], "words": [[s, e, word]], "qa": {...}}.
MFA_BIN: mfa executable (its env bin holds openfst/kaldi). WHISPER_PYTHON:
interpreter with faster_whisper (default: this one). WHISPER_MODEL: small.en.
"""
import difflib,json,os,re,shutil,subprocess,sys,tempfile
from pathlib import Path
voice,script,out=Path(sys.argv[1]),sys.argv[2],Path(sys.argv[3])
mfa=os.environ.get('MFA_BIN') or shutil.which('mfa')
if not mfa:sys.exit('MFA_RUNTIME_MISSING')
env=dict(os.environ,PATH=str(Path(mfa).parent)+os.pathsep+os.environ.get('PATH',''))
norm=lambda w:re.sub(r"[^a-z']",'',w.lower())
WHISPER='''import json,sys
from faster_whisper import WhisperModel
m=WhisperModel(sys.argv[2],device='cpu',compute_type='int8')
seg,_=m.transcribe(sys.argv[1],beam_size=5,vad_filter=True,word_timestamps=True)
print(json.dumps([[w.start,w.end,w.word.strip()] for s in seg for w in s.words]))'''
heard=json.loads(subprocess.run([os.environ.get('WHISPER_PYTHON',sys.executable),'-c',WHISPER,str(voice),os.environ.get('WHISPER_MODEL','small.en')],
                                capture_output=True,text=True,check=True).stdout)
heard=[w for w in heard if norm(w[2])]
# chunks: split at pauses >= 0.3 s, at most ~15 s each
chunks=[[heard[0]]] if heard else []
for w in heard[1:]:
    c=chunks[-1]
    if w[0]-c[-1][1]>=.3 and (w[0]-c[0][0]>=4 or w[0]-c[-1][1]>=1.0) or w[1]-c[0][0]>15:chunks.append([w])
    else:c.append(w)
owner=[i for i,c in enumerate(chunks) for _ in c]
if script=='-':texts=[' '.join(w[2] for w in c) for c in chunks]
else:
    words=Path(script).read_text().split();texts=[[] for _ in chunks]
    sm=difflib.SequenceMatcher(a=[norm(w[2]) for w in heard],b=[norm(w) for w in words],autojunk=False)
    last=0
    for tag,a0,a1,b0,b1 in sm.get_opcodes():
        for k in range(b0,b1):
            if tag in('equal','replace') and a1>a0:last=owner[min(a1-1,a0+round((k-b0)*(a1-a0)/max(1,b1-b0)))]
            texts[last].append(words[k])
    texts=[' '.join(t) for t in texts]
pad=.15
with tempfile.TemporaryDirectory() as tmp:
    # MFA keys its sqlite corpus DB on the source dir NAME under ~/Documents/MFA/
    # — a fixed 'in' makes concurrent presenter jobs fight over one database.
    src=Path(tmp)/f'vo{os.getpid()}';dst=Path(tmp)/'out';src.mkdir();starts=[]
    # The corpus name is not the only shared state: MFA also writes a joblib
    # cache, command history and global config under its root, and lazy model
    # extraction races as well. Point MFA_ROOT_DIR at a private dir with the
    # pre-extracted/pretrained model trees linked in so concurrent aligns are
    # fully isolated while still finding the models.
    mfa_root=Path(tmp)/'mfa_root';mfa_root.mkdir()
    shared_root=Path(os.environ.get('MFA_ROOT_DIR',Path.home()/'Documents/MFA'))
    for sub in ('pretrained_models','extracted_models'):
        shared_sub=shared_root/sub
        if shared_sub.exists():
            (mfa_root/sub).symlink_to(shared_sub,target_is_directory=True)
    for i,(c,txt) in enumerate(zip(chunks,texts)):
        a=max(0.0,c[0][0]-pad);b=c[-1][1]+pad;starts.append(a)
        subprocess.run(['ffmpeg','-loglevel','error','-y','-ss',f'{a:.3f}','-to',f'{b:.3f}','-i',str(voice),'-ac','1','-ar','16000',str(src/f'c{i:04}.wav')],check=True)
        (src/f'c{i:04}.lab').write_text(txt or 'um')
    subprocess.run([mfa,'align','--clean','-j','4','--single_speaker','--output_format','json',str(src),
                    os.environ.get('MFA_DICTIONARY','english_us_arpa'),os.environ.get('MFA_ACOUSTIC','english_us_arpa'),str(dst)]
                   # out-of-dictionary words (brand names) are spelled by the G2P model
                   +['--g2p_model_path',os.environ.get('MFA_G2P','english_us_arpa')],
                   check=True,env={**env,'MFA_ROOT_DIR':str(mfa_root)},stdout=subprocess.DEVNULL)
    phones=[];aligned=[];failed=0
    for i,a in enumerate(starts):
        f=dst/f'c{i:04}.json'
        if not f.exists():failed+=1;continue
        t=json.loads(f.read_text())['tiers']
        phones+=[[round(s+a,3),round(e+a,3),p] for s,e,p in t['phones']['entries']]
        aligned+=[[round(s+a,3),round(e+a,3),w] for s,e,w in t['words']['entries']]
# QA: aligned word starts against Whisper's independent word starts
sm=difflib.SequenceMatcher(a=[norm(w[2]) for w in heard],b=[norm(w[2]) for w in aligned],autojunk=False)
off=sorted(abs(aligned[j][0]-heard[i][0]) for blk in sm.get_matching_blocks() for i,j in zip(range(blk.a,blk.a+blk.size),range(blk.b,blk.b+blk.size)))
qa={'chunks':len(chunks),'failedChunks':failed,'phones':len(phones),'words':len(aligned),'checkedWords':len(off),
    'medianWordOffsetSec':round(off[len(off)//2],3) if off else None,'p95WordOffsetSec':round(off[int(len(off)*.95)],3) if off else None,
    'wordsOver250ms':sum(o>.25 for o in off)}
out.write_text(json.dumps({'phones':phones,'words':aligned,'qa':qa})+'\n')
print('PHONEME_ALIGN',json.dumps(qa))
