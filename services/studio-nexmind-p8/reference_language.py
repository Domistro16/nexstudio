#!/usr/bin/env python3
from __future__ import annotations
import json,math,re,subprocess,sys,tempfile
from pathlib import Path
from PIL import Image


def _probe(path:Path)->float:
    p=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(path)],capture_output=True,text=True,check=True)
    d=float(json.loads(p.stdout).get('format',{}).get('duration') or 0)
    if not math.isfinite(d) or d<=0: raise RuntimeError('REFERENCE_LANGUAGE_ANALYSIS_FAILED:invalid_duration')
    return d

def _metrics(path:Path):
    im=Image.open(path).convert('L')
    if im.width>320:
        h=max(1,round(im.height*(320/im.width))); im=im.resize((320,h))
    pix=list(im.getdata()); n=max(1,len(pix)); non=sum(1 for v in pix if v<242); total=sum(pix); sq=sum(v*v for v in pix); mean=total/n
    edge=0; w,h=im.size
    for y in range(h):
        row=y*w
        for x in range(w):
            i=row+x; v=pix[i]
            if x>0 and abs(v-pix[i-1])>26: edge+=1
            if y>0 and abs(v-pix[i-w])>26: edge+=1
    var=max(0,sq/n-mean*mean)
    return {'raw':pix,'occ':non/n,'edge':edge/max(1,n*2),'std':math.sqrt(var),'width':w,'height':h}

def _delta(a,b):
    n=min(len(a),len(b));
    return 0 if n==0 else sum(abs(a[i]-b[i]) for i in range(n))/(n*255)

def _style_hint(name:str):
    s=(name or '').lower()
    if re.search(r'hand[ _-]?draw|whiteboard|marker|sketch|line[ _-]?draw',s): return 'hand-drawn-whiteboard'
    if re.search(r'cartoon|illustrat|movement|motion',s): return 'authored-illustrated-motion'
    return 'unspecified-reference-language'

def analyze(req):
    path=Path(req['path']); mime=str(req.get('mimeType') or ''); asset=str(req.get('assetId') or 'reference'); name=str(req.get('name') or path.name)
    if mime.startswith('video/'):
        duration=_probe(path); samples=max(4,min(8,math.ceil(duration*1.5)))
        with tempfile.TemporaryDirectory(prefix='studio-ref-') as td:
            out=Path(td)/'frame-%02d.jpg'; fps=samples/duration
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(path),'-vf',f'fps={fps},scale=640:-2','-frames:v',str(samples),'-q:v','3',str(out)],check=True)
            fs=sorted(Path(td).glob('frame-*.jpg'))
            if len(fs)<2: raise RuntimeError('REFERENCE_LANGUAGE_ANALYSIS_FAILED:too_few_frames')
            ms=[_metrics(x) for x in fs]
    elif mime.startswith('image/'):
        duration=None; ms=[_metrics(path)]; fs=[path]
    else: raise RuntimeError('REFERENCE_LANGUAGE_ANALYSIS_FAILED:unsupported_mime')
    mean=lambda k:sum(x[k] for x in ms)/len(ms)
    occ,edges,std=mean('occ'),mean('edge'),mean('std'); deltas=[_delta(ms[i-1]['raw'],ms[i]['raw']) for i in range(1,len(ms))]; mdelta=sum(deltas)/max(1,len(deltas))
    bias=max(0,min(1,occ*1.35+edges*4.2+mdelta*.8)); density='rich' if occ>=.24 or edges>=.055 else ('balanced' if occ>=.13 else 'sparse'); white=occ<.44
    hint=_style_hint(name)
    profile={'version':'reference-language.v2','authority':'INDEXING_AID_ONLY','creativeStyleAuthority':'DIRECT_HASH_BOUND_VISUAL_EVIDENCE','sourceIds':[asset],'sourceKinds':[mime],'frameCount':len(ms),'meanNonWhiteOccupancy':round(occ,4),'meanEdgeDensity':round(edges,4),'meanLumaStd':round(std,2),'meanFrameDelta':round(mdelta,4),'whiteField':white,'authoredSceneBias':round(bias,3),'densityTarget':density,'textDominanceMax':.18 if density=='rich' else .25,'minimumForegroundOccupancy':round(max(.12,occ*.72),3),'maximumDeadWhiteRatio':round(min(.7,max(.28,1-occ*.82)),3),'notes':['These deterministic statistics are indexing/coverage telemetry only and must not substitute for multimodal inspection of the hash-bound reference pixels.','Reference media constrains visual language only; shots, story content and compositions must remain original.']}
    if duration is not None: profile['durationSec']=duration
    return {'schema':'StudioReferenceLanguageEvidenceV1','profile':profile,'styleHint':hint,'sourceName':name}

try:
    req=json.load(sys.stdin); json.dump(analyze(req),sys.stdout,separators=(',',':'));sys.stdout.write('\n')
except Exception as e:
    json.dump({'schema':'StudioReferenceLanguageEvidenceV1','status':'BLOCKED','code':'REFERENCE_LANGUAGE_ANALYSIS_FAILED','detail':str(e)},sys.stdout,separators=(',',':'));sys.stdout.write('\n');sys.exit(2)
