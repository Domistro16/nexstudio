#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,subprocess,textwrap
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ENV=ROOT/'engines/explainer/NexStudio_Explainer_Execution_Body_V2/src/studio/explainer-motion-v1/nexart/environment-constructor.ts'
OBJ=ROOT/'engines/explainer/NexStudio_Explainer_Execution_Body_V2/src/studio/explainer-motion-v1/nexart/constructed-object.ts'
ASSET=ROOT/'engines/explainer/NexStudio_Explainer_Execution_Body_V2/src/studio/explainer-motion-v1/nexart/asset-body.ts'
checks=[]
def ck(n,o,d=''):checks.append({'name':n,'ok':bool(o),'detail':d})
env=ENV.read_text();obj=OBJ.read_text();asset=ASSET.read_text()
ck('No finite world-kind catalogue remains','WorldKind' not in env and 'worldKind(' not in env)
ck('No prose-to-inline-world constructor remains','semanticWorldSvg' not in env and 'semantic-environment:' not in env)
ck('No finite prose-to-object catalogue remains','type ObjectKind' not in obj and 'kindFor(' not in obj)
ck('Constructed-object compatibility symbol fails closed','return undefined' in obj)
ck('Asset body does not call canned constructed object','constructedObjectBinding(' not in asset)
ck('Environment requires explicit authored world','PRODUCTION_SCOPED_AUTHORED_ENVIRONMENT_REQUIRED' in env)
node=textwrap.dedent(r'''const fs=require('fs'),vm=require('vm'),ts=require('/opt/nvm/versions/node/v22.16.0/lib/node_modules/typescript/lib/typescript.js');function load(p){const o=ts.transpileModule(fs.readFileSync(p,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS},reportDiagnostics:true,fileName:p});if((o.diagnostics||[]).some(x=>x.category===1))throw Error('transpile');const m={exports:{}};vm.runInNewContext('(function(require,module,exports){'+o.outputText+'})(()=>({}),m,m.exports)',{m,console,Set,Map,Number,String,Array,Object,Math,RegExp,JSON});return m.exports}const obj=load(process.argv[1]);process.stdout.write(JSON.stringify(obj.constructedObjectBinding('x','phone computer package')||null));''')
r=subprocess.run(['node','-e',node,str(OBJ)],text=True,capture_output=True,cwd=ROOT)
ck('Known noun also fails closed without explicit authored binding',r.returncode==0 and json.loads(r.stdout) is None,r.stderr[-500:])
# environment module compile proof (imports are type-only)
node2=textwrap.dedent(r'''const fs=require('fs'),ts=require('/opt/nvm/versions/node/v22.16.0/lib/node_modules/typescript/lib/typescript.js');for(const p of process.argv.slice(1)){const o=ts.transpileModule(fs.readFileSync(p,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS},reportDiagnostics:true,fileName:p});const e=(o.diagnostics||[]).filter(x=>x.category===1);if(e.length){console.error(e.map(x=>ts.flattenDiagnosticMessageText(x.messageText,' ')).join('\n'));process.exit(2)}}''')
r2=subprocess.run(['node','-e',node2,str(ENV),str(OBJ),str(ASSET)],text=True,capture_output=True,cwd=ROOT)
ck('Environment/object execution sources transpile',r2.returncode==0,r2.stderr[-1000:])
out={'schema':'EnvironmentObjectExecutionQAV3','pass':all(x['ok'] for x in checks),'passed':sum(x['ok'] for x in checks),'total':len(checks),'checks':checks,'commercialScoreEvidence':False,'truthBoundary':'Fail-closed execution-authority proof. Arbitrary worlds/objects require P8 production-scoped authored art or explicit approved bindings; no finite house catalogue is accepted as creative authority.','sourceHashes':{'environmentConstructor':hashlib.sha256(ENV.read_bytes()).hexdigest(),'constructedObject':hashlib.sha256(OBJ.read_bytes()).hexdigest()}}
(ROOT/'reports/ENVIRONMENT_OBJECT_EXECUTION_QA_V3.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2));raise SystemExit(0 if out['pass'] else 1)
