import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";
const require=createRequire(import.meta.url);
const localBuild=path.resolve("reports/policy-build");
const policyBuild=process.env.POLICY_BUILD || path.join(localBuild,"policies.js");
if(!fs.existsSync(policyBuild)){
  fs.mkdirSync(localBuild,{recursive:true});
  fs.writeFileSync(path.join(localBuild,"package.json"),'{"type":"commonjs"}\n');
  execFileSync("tsc",["src/studio-v1/memory/contracts.ts","src/studio-v1/memory/policies.ts","--target","ES2022","--module","commonjs","--moduleResolution","node","--outDir",localBuild,"--skipLibCheck","--esModuleInterop"],{stdio:"inherit"});
}
const policies=require(policyBuild);

const results={series:[],cast:[]};
const check=(bucket,name,ok,detail="")=>results[bucket].push({name,passed:Boolean(ok),detail});

const h=[
 {productionId:"p1",episodeOrdinal:1,environments:["office"],transitions:["shared-object-follow"],cameras:["push-in"],actorPositions:["left-right"],visualMetaphors:["bridge"],motifs:["amber-line"]},
 {productionId:"p2",episodeOrdinal:2,environments:["warehouse"],transitions:["semantic-morph"],cameras:["lateral-track"],actorPositions:["foreground-background"],visualMetaphors:["relay"],motifs:["amber-line"]},
];
let r=policies.evaluateSeriesAntiRepetition({candidate:{environments:["warehouse"],cameras:["lateral-track"]},history:h});
check("series","Blocks default repeated environment",!r.passes&&r.blockedDimensions.includes("environments"),JSON.stringify(r));
check("series","Blocks default repeated camera",r.blockedDimensions.includes("cameras"),JSON.stringify(r));
r=policies.evaluateSeriesAntiRepetition({candidate:{motifs:["amber-line"]},history:h,continuityReasons:{motifs:"The recurring line is the series identity motif and evolves in color/meaning."}});
check("series","Allows explicit continuity repetition",r.passes&&r.collisions[0]?.continuityReason!==null,JSON.stringify(r));
r=policies.evaluateSeriesAntiRepetition({candidate:{environments:["home"],transitions:["match-action"],cameras:["locked-wide"]},history:h});
check("series","Allows fresh candidate",r.passes&&r.collisions.length===0,JSON.stringify(r));
r=policies.evaluateSeriesAntiRepetition({candidate:{cardGrid:true},history:[{cardGrid:true}]});
check("series","Blocks repeated card-grid default",!r.passes&&r.blockedDimensions.includes("cardGrid"),JSON.stringify(r));
r=policies.evaluateSeriesAntiRepetition({candidate:{floatingObjects:true},history:[{floatingObjects:true}],continuityReasons:{floatingObjects:"Episode intentionally returns to the same established memory space."}});
check("series","Continuity reason can preserve a necessary repeated device",r.passes,JSON.stringify(r));
r=policies.evaluateSeriesAntiRepetition({candidate:{cameras:["push-in"]},history:[{cameras:["push-in"]},{cameras:["orbit"]},{cameras:["locked-wide"]}],historyWindow:2});
check("series","History window is bounded",r.passes,JSON.stringify(r));

const baseMem=[{itemId:"i1",scope:"CAST",scopeRefId:"c1",key:"cast.identity",category:"CAST_IDENTITY",versionId:"v1",versionNumber:1,effectiveState:"ACTIVE",content:{family:"adult-woman",hair:"braided-bob",clothing:{top:"navy-jacket"},pose:"hands-up",jointAngles:[1,2,3]},contentHash:"h1",provenance:{source:"CUSTOMER"},effectiveFrom:"2026-01-01",effectiveUntil:null,effectiveFromEpisodeOrdinal:null,effectiveUntilEpisodeOrdinal:null}];
const a=policies.compileStableCastIdentity({castMemberId:"c1",identityKey:"CHAR-ADA",name:"Ada",memories:baseMem});
const b=policies.compileStableCastIdentity({castMemberId:"c1",identityKey:"CHAR-ADA",name:"Ada",memories:baseMem});
check("cast","Stable identity fingerprint is deterministic",policies.castIdentityFingerprint(a)===policies.castIdentityFingerprint(b));
check("cast","Stored pose is stripped from stable identity",!JSON.stringify(a.identity).includes('hands-up'),JSON.stringify(a));
check("cast","Stored joint trajectory is stripped",!JSON.stringify(a.identity).includes('jointAngles'),JSON.stringify(a));
check("cast","Morphology remains stable",JSON.stringify(a.identity).includes('adult-woman'),JSON.stringify(a));
check("cast","Clothing identity remains stable",JSON.stringify(a.identity).includes('navy-jacket'),JSON.stringify(a));
check("cast","Performance is resolved fresh",a.performanceDirection==="RESOLVE_FRESH_FROM_CURRENT_SCENE_INTENT",JSON.stringify(a));
check("cast","V5.1 remains performance authority",a.performanceAuthority.performanceEngine==="NexPerformanceUnifiedV5@5.1.0-skin-safe-angular-continuity",JSON.stringify(a.performanceAuthority));
check("cast","V5.1 registry hash is exact",a.performanceAuthority.registrySha256==="64056fed5b4354e13fe945f71e0fa2f88db68d2be2b146bc3d1bc61d21844ef3",a.performanceAuthority.registrySha256);

for(const [bucket,items] of Object.entries(results)){
  const report={schema:bucket==="series"?"StudioSeriesAntiRepetitionTestsV1":"StudioCastContinuityTestsV1",passed:items.filter(x=>x.passed).length,total:items.length,implementationPass:items.every(x=>x.passed),checks:items};
  const out=process.env.TEST_OUT || path.resolve("reports"); fs.mkdirSync(out,{recursive:true});
  fs.writeFileSync(path.join(out,bucket==="series"?"SERIES_ANTI_REPETITION_TESTS.json":"CAST_CONTINUITY_TESTS.json"),JSON.stringify(report,null,2)+"\n");
  console.log(JSON.stringify(report,null,2));
  if(!report.implementationPass)process.exitCode=1;
}
