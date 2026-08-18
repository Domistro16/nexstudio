#!/usr/bin/env python3
from __future__ import annotations
import json,os,py_compile,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ENGINE=ROOT/'engines/explainer/NexStudio_Explainer_Execution_Body_V2'
checks=[]
def add(name,ok,detail=''): checks.append({'name':name,'pass':bool(ok),'detail':detail})
def text(p): return Path(p).read_text(errors='replace')
ad=text(ROOT/'services/studio-family-engines/explainer_adapter.py')
runner=text(ENGINE/'scripts/studio-p8-explainer-runner.ts')
prod=text(ENGINE/'src/studio/explainer-motion-v1/nexart/production-art.ts')
runtime=text(ENGINE/'runtime-assets/explainer-motion-v1/library/components/visual-constructions.js')
types=text(ENGINE/'src/studio/explainer-motion-v1/types.ts')
add('Explainer adapter discovers authored-art by capability rather than provider name','authored_art_available()' in ad and 'NEXSTUDIO_ART_EXECUTION_REGISTRY_JSON' not in ad)
add('Missing authored-art capability escalates to P8 replan, never generic fallback','EXPLAINER_AUTHORED_ART_CAPABILITY_REQUIRED' in ad and 'creative_replan_request(' in ad and 'generic cards, icons, canned rooms or diagram shorthand' in ad)
add('Every active P8 Explainer beat requires production-scoped authored art',"for beat in require_review_board(board)" in ad and "EXPLAINER_AUTHORED_ART_CAPABILITY_REQUIRED" in ad and "form.get('status')=='GENERATION_REQUIRED'" not in ad)
add('Runner carries a semantic-locked production-scoped art binding','authoredScenePlates' in runner and 'lockedSemanticsHash' in runner and 'creativeChoiceIntroduced:false' in runner)
add('Execution body rejects plate semantics that do not cover exact construction hero/supports','PRODUCTION_SCOPED_ART_SEMANTICS_MISSING' in prod)
add('Production-scoped plate bypasses weaker stock/procedural substrate rather than duplicating it',"return renderExecutionLayer(authoredSceneLayer,plan)" in runtime)
add('Family body is execution-fidelity only; commercial critic authority removed','StudioFamilyExecutionFidelityV1' in runner and 'commercialScore:null' in runner and 'reviewExplainerCompositionFrames' not in runner and 'EXPLAINER_STRICT_VISUAL_CRITIC_FAILED' not in runner)
add('Production-scoped art carries provenance into production-art plan','productionScopedAuthoredPlate' in types and 'lockedSemanticsHash:plate.lockedSemanticsHash' in prod)
add('No retired P14 creative authority label remains in the active runner','P14_2' not in runner and 'P14.2' not in runner)
# Syntax: Python + modified TS via global TypeScript transpile
try: py_compile.compile(str(ROOT/'services/studio-family-engines/explainer_adapter.py'),doraise=True); pyok=True
except Exception as e: pyok=False; add('Explainer adapter Python syntax',False,str(e))
if pyok:add('Explainer adapter Python syntax',True)
files=[ENGINE/'scripts/studio-p8-explainer-runner.ts',ENGINE/'src/studio/explainer-motion-v1/types.ts',ENGINE/'src/studio/explainer-motion-v1/nexart/production-art.ts',ENGINE/'src/studio/explainer-motion-v1/nexart/environment-constructor.ts']
js="const ts=require('/opt/nvm/versions/node/v22.16.0/lib/node_modules/typescript/lib/typescript.js'),fs=require('fs');let bad=[];for(const p of process.argv.slice(1)){const r=ts.transpileModule(fs.readFileSync(p,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext},reportDiagnostics:true,fileName:p});for(const d of r.diagnostics||[])if(d.category===ts.DiagnosticCategory.Error)bad.push(p+':'+ts.flattenDiagnosticMessageText(d.messageText,' '));}if(bad.length){console.error(bad.join('\\n'));process.exit(1)}"
r=subprocess.run(['node','-e',js,*map(str,files)],capture_output=True,text=True)
add('Modified Explainer TypeScript parses',r.returncode==0,r.stderr[-1000:])
report={'schema':'NexStudioExplainerAuthoredArtExecutionQA V1','evidenceClass':'MECHANICAL_CONTRACT_ONLY_NOT_CREATIVE_QUALITY','passed':sum(c['pass'] for c in checks),'total':len(checks),'checks':checks}
(ROOT/'reports/EXPLAINER_AUTHORED_ART_EXECUTION_QA.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2));sys.exit(0 if report['passed']==report['total'] else 1)
