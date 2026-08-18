#!/usr/bin/env python3
from __future__ import annotations
import base64, json, os, subprocess, sys, tempfile, zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT=Path(__file__).resolve().parents[1]
SIDE=ROOT/'services/studio-source-intelligence/source_intelligence.py'
MIME_DOCX='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
MIME_PPTX='application/vnd.openxmlformats-officedocument.presentationml.presentation'
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zjr4AAAAASUVORK5CYII=')
checks=[]
def check(name,ok,detail=''):
    checks.append({'name':name,'ok':bool(ok),'detail':detail})
    if not ok: raise AssertionError(name+(' — '+detail if detail else ''))

def run(path:Path,mime:str,out:Path):
    p=subprocess.run([sys.executable,str(SIDE)],input=json.dumps({'path':str(path),'outputDirectory':str(out),'mimeType':mime,'name':path.name,'sourceId':'qa-source'}),text=True,capture_output=True,cwd=ROOT)
    try: data=json.loads(p.stdout)
    except Exception as e: raise AssertionError(f'invalid sidecar JSON: {p.stdout[:500]} {p.stderr[:500]}') from e
    check(f'{path.suffix} sidecar exits cleanly',p.returncode==0,str(data.get('detail') or p.stderr[:300]))
    return data

def write_docx(path:Path):
    document='''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><w:body><w:p><w:r><w:t>Portable induction cooktops heat compatible cookware with precise electronic control.</w:t></w:r><w:r><a:blip r:embed="rId1"/></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Power</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>1800 W</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>'''
    rels='''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.png"/></Relationships>'''
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('word/document.xml',document);z.writestr('word/_rels/document.xml.rels',rels);z.writestr('word/media/image1.png',PNG);z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')

def write_pptx(path:Path):
    slide='''<?xml version="1.0" encoding="UTF-8"?><p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>Precise heat, fast response.</a:t></a:r></a:p></p:txBody></p:sp><p:pic><p:blipFill><a:blip r:embed="rId1"/></p:blipFill></p:pic></p:spTree></p:cSld></p:sld>'''
    rels='''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart" Target="../charts/chart1.xml"/></Relationships>'''
    chart='''<?xml version="1.0" encoding="UTF-8"?><c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"><c:chart><c:plotArea><c:barChart><c:ser><c:val><c:numRef><c:f>Sheet1!$B$2:$B$3</c:f><c:numCache><c:pt idx="0"><c:v>35</c:v></c:pt><c:pt idx="1"><c:v>90</c:v></c:pt></c:numCache></c:numRef></c:val></c:ser></c:barChart></c:plotArea></c:chart></c:chartSpace>'''
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('ppt/slides/slide1.xml',slide);z.writestr('ppt/slides/_rels/slide1.xml.rels',rels);z.writestr('ppt/media/image1.png',PNG);z.writestr('ppt/charts/chart1.xml',chart);z.writestr('ppt/presentation.xml','<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>');z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')

def write_pdf(path:Path):
    import fitz
    doc=fitz.open();p=doc.new_page();p.insert_text((72,72),'Induction transfers energy through a magnetic field to compatible cookware.')
    for i in range(3): p.draw_rect(fitz.Rect(72+i*30,110,92+i*30,130))
    p2=doc.new_page()
    for i in range(3): p2.draw_rect(fitz.Rect(72+i*40,100,102+i*40,140))
    doc.save(path);doc.close()

def run_packet_behavior(extracted:dict):
    js='''const fs=require('fs'),ts=require('typescript'),vm=require('vm');const f='src/studio-v1/source-intelligence/p8-packet.ts';const out=ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;const m={exports:{}};vm.runInNewContext('(function(require,module,exports){'+out+'\\n})(require,m,m.exports)',{require,m,console,Set,Map,Number,String,Array,Object,Math});const input=JSON.parse(process.argv[1]);process.stdout.write(JSON.stringify(m.exports.buildP8SourcePacket(input)));'''
    persisted=dict(extracted);persisted['visualPreviews']=[{**{k:v for k,v in x.items() if k!='path'},'objectKey':f'sources/qa/{i}.png','bytes':len(PNG)} for i,x in enumerate(extracted.get('visualPreviews') or [],1)]
    input={'rawSources':[{'id':'11111111-1111-1111-1111-111111111111','kind':'FILE','label':'brief.docx'}],'productionInputs':[{'ordinal':0,'sourceId':'11111111-1111-1111-1111-111111111111','kind':'FILE','source':{'id':'11111111-1111-1111-1111-111111111111','name':'brief.docx','mimeType':MIME_DOCX,'detectedMimeType':MIME_DOCX,'extracted':persisted}}],'prompt':'Explain precise heat control for a portable induction cooktop'}
    p=subprocess.run(['node','-e',js,json.dumps(input)],cwd=ROOT,text=True,capture_output=True)
    check('P8 source-packet executable test runs',p.returncode==0,p.stderr[:300])
    data=json.loads(p.stdout)
    check('P8 packet carries extracted evidence',bool(data['evidence']) and data['evidence'][0]['status']=='USER_SOURCE_EXTRACTED')
    check('P8 packet carries hashed provenance','sha256' in data['evidence'][0]['source'])
    check('P8 packet carries visual references',bool(data['visualReferences']))
    return data

with tempfile.TemporaryDirectory(prefix='studio-source-qa-') as td:
    t=Path(td);docx=t/'sample.docx';pptx=t/'sample.pptx';pdf=t/'sample.pdf';txt=t/'sample.txt';write_docx(docx);write_pptx(pptx);write_pdf(pdf);txt.write_text('A brief can be ordinary text.\nIt still retains provenance.','utf-8')
    d=run(docx,MIME_DOCX,t/'docx-out');check('DOCX extracts paragraph and table',any(x['kind']=='paragraph' for x in d['segments']) and any(x['kind']=='table' for x in d['segments']));check('DOCX table text is not duplicated as body paragraphs',sum('1800 W' in x['text'] for x in d['segments'])==1);check('DOCX embedded image becomes visual evidence',len(d['visualPreviews'])==1)
    p=run(pptx,MIME_PPTX,t/'pptx-out');check('PPTX extracts slide text',any(x['kind']=='slide' for x in p['segments']));check('PPTX extracts chart data',any(x['kind']=='chart_data' and '90' in x['text'] for x in p['segments']));check('PPTX embedded image becomes visual evidence',len(p['visualPreviews'])==1)
    q=run(pdf,'application/pdf',t/'pdf-out');check('PDF extracts text with page locator',any(x['locator']=='page 1' for x in q['segments']));check('PDF renders provenance-bound page evidence',len(q['visualPreviews'])==2 and q['visualCoverage']=='FULL');check('PDF marks visual-only page',2 in q['visualOnlyPages']);check('PDF marks visually complex page evidence',2 in q.get('visualEvidencePages',[]))
    z=run(txt,'text/plain',t/'txt-out');check('Text source extracts safely',z['status']=='EXTRACTED' and bool(z['segments']))
    run_packet_behavior(d)

# Architectural source checks.
workflow=(ROOT/'src/studio-v1/nexmind-p8/workflow.ts').read_text(); provider=(ROOT/'vendor/nexmind-god-mode-p8/src/nexmind_god_mode/live_provider.py').read_text(); orchestrator=(ROOT/'services/studio-nexmind-p8/orchestrator.py').read_text(); upload=(ROOT/'src/lib/upload-security.ts').read_text()
check('P8 reads persisted StudioProductionInput Source.extracted','studioProductionInput.findMany' in workflow and 'buildP8SourcePacket' in workflow)
check('Filename-only sourcePacket authority removed','function sourcePacket(raw' not in workflow)
check('Text source understanding precedes Story','_source_understanding(request, evidence, provider)' in orchestrator and orchestrator.index('_source_understanding(request, evidence, provider)') < orchestrator.index('p2 = CreativeCouncil'))
check('Visual source understanding is capability-optional','source_visual_understanding' in provider and 'multimodal_source_understanding' in provider and 'UNAVAILABLE' in orchestrator)
check('Text source synthesis is capability-optional without dropping extracted evidence','provider.complete("source_understanding"' in orchestrator and 'raw_evidence_preserved' in orchestrator and 'Dedicated source synthesis was unavailable' in orchestrator)
check('DOCX/PPTX are secure accepted MIME types',MIME_DOCX in upload and MIME_PPTX in upload and 'UPLOAD_OOXML_ACTIVE_OR_EMBEDDED_CONTENT_BLOCKED' in upload)

result={'schema':'StudioSourceIntelligenceQA V1','pass':all(x['ok'] for x in checks),'passed':sum(x['ok'] for x in checks),'total':len(checks),'checks':checks}
out=ROOT/'reports/source-intelligence';out.mkdir(parents=True,exist_ok=True);(out/'SOURCE_INTELLIGENCE_QA.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2));sys.exit(0 if result['pass'] else 1)
