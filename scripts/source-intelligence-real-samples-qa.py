#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, json, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SIDE=ROOT/'services/studio-source-intelligence/source_intelligence.py'
P8_TS=ROOT/'src/studio-v1/source-intelligence/p8-packet.ts'
MIMES={'.pdf':'application/pdf','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','.pptx':'application/vnd.openxmlformats-officedocument.presentationml.presentation'}

def sha(p:Path): return hashlib.sha256(p.read_bytes()).hexdigest()
def run_extract(p:Path,mime:str,out:Path):
    out.mkdir(parents=True,exist_ok=True)
    r=subprocess.run([sys.executable,str(SIDE)],input=json.dumps({'path':str(p),'mimeType':mime,'name':p.name,'outputDirectory':str(out)}),text=True,capture_output=True,cwd=ROOT)
    if r.returncode!=0: raise RuntimeError(r.stderr or r.stdout)
    return json.loads(r.stdout)
def packet(raw,prod,prompt):
    js="""const fs=require('fs'),ts=require('/opt/nvm/versions/node/v22.16.0/lib/node_modules/typescript/lib/typescript.js'),vm=require('vm');const f=process.argv[1];const out=ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;const m={exports:{}};vm.runInNewContext('(function(require,module,exports){'+out+'\\n})(require,m,m.exports)',{require,m,console,Set,Map,Number,String,Array,Object,Math});process.stdout.write(JSON.stringify(m.exports.buildP8SourcePacket(JSON.parse(fs.readFileSync(0,'utf8')))));"""
    r=subprocess.run(['node','-e',js,str(P8_TS)],input=json.dumps({'rawSources':raw,'productionInputs':prod,'prompt':prompt}),cwd=ROOT,text=True,capture_output=True)
    if r.returncode: raise RuntimeError(r.stderr)
    return json.loads(r.stdout)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pdf',required=True);ap.add_argument('--docx',required=True);ap.add_argument('--pptx',required=True);ap.add_argument('--out',default=str(ROOT/'reports/source-intelligence/REAL_SOURCE_INTELLIGENCE_QA.json'));a=ap.parse_args()
    files=[('real-pdf',Path(a.pdf)),('real-docx',Path(a.docx)),('real-pptx',Path(a.pptx))]
    checks=[];extracted={};raw=[];prod=[]
    def ck(name,ok,detail=''): checks.append({'name':name,'ok':bool(ok),'detail':detail})
    with tempfile.TemporaryDirectory(prefix='nexstudio-real-source-qa-') as td:
        td=Path(td)
        for ordinal,(sid,p) in enumerate(files):
            mime=MIMES[p.suffix.lower()]; d=run_extract(p,mime,td/sid);extracted[sid]=d
            ck(f'{sid}: extraction succeeds',d.get('status')=='EXTRACTED',str(d.get('status')))
            ck(f'{sid}: content hash binds original bytes',d.get('contentHash')==sha(p),f"expected={sha(p)} got={d.get('contentHash')}")
            ck(f'{sid}: provenance segments exist',bool(d.get('segments')) and all(x.get('locator') and x.get('sha256') for x in d.get('segments') or []),f"segments={len(d.get('segments') or [])}")
            # Replace transient paths with durable object keys exactly like Studio persistence does.
            persisted=json.loads(json.dumps(d));
            for i,v in enumerate(persisted.get('visualPreviews') or [],1):
                v.pop('path',None);v['objectKey']=f'sources/real-proof/{sid}/visual-{i:04d}.png'
            raw.append({'id':sid,'kind':'FILE','label':p.name})
            prod.append({'ordinal':ordinal,'sourceId':sid,'kind':'FILE','source':{'id':sid,'name':p.name,'mimeType':mime,'detectedMimeType':mime,'extracted':persisted}})
        pdf=extracted['real-pdf'];doc=extracted['real-docx'];ppt=extracted['real-pptx']
        ck('PDF has full page-render visual coverage',pdf.get('visualCoverage')=='FULL' and len(pdf.get('visualPreviews') or [])==int(pdf.get('pageCount') or 0),f"coverage={pdf.get('visualCoverage')} pages={pdf.get('pageCount')} visuals={len(pdf.get('visualPreviews') or [])}")
        ck('DOCX preserves embedded visual evidence',len(doc.get('visualPreviews') or [])>=1,f"visuals={len(doc.get('visualPreviews') or [])}")
        unsupported=[x for x in ppt.get('warnings') or [] if 'UNSUPPORTED_EMBEDDED_VISUAL' in str(x)]
        ck('PPTX captures embedded SVG/raster artwork',len(ppt.get('visualPreviews') or [])>=1 and not unsupported,f"visuals={len(ppt.get('visualPreviews') or [])} unsupported={len(unsupported)}")
        ck('PPTX full-slide composition is rendered when local renderer succeeds',ppt.get('visualCoverage')=='FULL' and int(ppt.get('composedPageCount') or 0)==int(ppt.get('pageCount') or 0),f"coverage={ppt.get('visualCoverage')} composed={ppt.get('composedPageCount')} pages={ppt.get('pageCount')}")
        p8=packet(raw,prod,'Create an explainer from these sources while preserving source provenance and evidence.');
        ck('P8 packet contains all real sources',p8.get('extractedSourceCount')==3,f"count={p8.get('extractedSourceCount')}")
        sources={x.get('claim_id','').split(':',1)[0] for x in p8.get('evidence') or []};ck('P8 evidence spans PDF/DOCX/PPTX',{'real-pdf','real-docx','real-pptx'}<=sources,str(sorted(sources)))
        ck('P8 packet retains visual references',len(p8.get('visualReferences') or [])>=3,f"visuals={len(p8.get('visualReferences') or [])}")
        ck('P8 packet retains source-local hashes',all('sha256' in str(x.get('source','')) for x in p8.get('evidence') or []))
        ck('PPTX full visual coverage produces no false partial warning',not any(x=='real-pptx:SOURCE_VISUAL_COVERAGE_PARTIAL' for x in p8.get('warnings') or []),str(p8.get('warnings')))
    metrics={sid:{'name':p.name,'sha256':sha(p),'segments':len(extracted[sid].get('segments') or []),'chars':extracted[sid].get('totalExtractedChars'),'pages':extracted[sid].get('pageCount'),'visuals':len(extracted[sid].get('visualPreviews') or []),'visualCoverage':extracted[sid].get('visualCoverage'),'warnings':extracted[sid].get('warnings') or []} for sid,p in files}
    result={'schema':'StudioRealSourceIntelligenceQAV1','pass':all(x['ok'] for x in checks),'passed':sum(x['ok'] for x in checks),'total':len(checks),'checks':checks,'samples':metrics,'p8Packet':{'extractedSourceCount':p8.get('extractedSourceCount'),'evidenceCount':len(p8.get('evidence') or []),'visualReferenceCount':len(p8.get('visualReferences') or []),'contextChars':p8.get('contextChars'),'warnings':p8.get('warnings') or []},'commercialScoreEvidence':False,'truthBoundary':'Real document extraction and P8 evidence-packet proof. PDF pages and PPTX composed slides are rendered completely when the local render stack succeeds. Dedicated live source-reasoning/multimodal judgment is not claimed when no compatible model is configured.'}
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));return 0 if result['pass'] else 1
if __name__=='__main__':raise SystemExit(main())
