import fs from 'node:fs';
import path from 'node:path';
import ts from '/opt/nvm/versions/node/v22.16.0/lib/node_modules/typescript/lib/typescript.js';
const root=process.cwd();
const files=[
 'src/studio-v1/memory/contracts.ts','src/studio-v1/memory/policies.ts','src/studio-v1/memory/service.ts','src/studio-v1/memory/resolver.ts','src/studio-v1/memory/production-input.ts',
 'src/studio-v1/nexmind-p8/workflow.ts','src/studio-v1/production-engines/workflow.ts',
 'app/api/v1/studio/memory/route.ts','app/api/v1/studio/memory/[id]/route.ts','app/api/v1/studio/brands/route.ts','app/api/v1/studio/cast/route.ts','app/api/v1/studio/series/route.ts','app/api/v1/productions/[id]/memory/route.ts'
];
const checks=[];
for(const rel of files){
 const src=fs.readFileSync(path.join(root,rel),'utf8');
 const out=ts.transpileModule(src,{fileName:rel,reportDiagnostics:true,compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext,jsx:ts.JsxEmit.Preserve}});
 const diagnostics=(out.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error).map(d=>ts.flattenDiagnosticMessageText(d.messageText,' '));
 checks.push({file:rel,passed:diagnostics.length===0,diagnostics});
}
const report={schema:'StudioMemoryTypeScriptSyntaxQA V1',passed:checks.filter(x=>x.passed).length,total:checks.length,implementationPass:checks.every(x=>x.passed),typescriptVersion:ts.version,checks};
fs.mkdirSync(path.join(root,'reports'),{recursive:true});fs.writeFileSync(path.join(root,'reports/TYPESCRIPT_SYNTAX_QA.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));if(!report.implementationPass)process.exit(1);
