#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXPECTED={
 'WHITEBOARD_ENGINE_SOURCE.zip':'25f87cb57d4a8ca99d004b443c0bd8df85a13d667596ddb0780d2c8f3884002c',
 'EXPLAINER_ENGINE_SOURCE.zip':'b2782b1557515d43db78a2c1507aeebb1cae99458104c450ed63ef752a675f1b',
 'EDITORIAL_MOTION_ENGINE_SOURCE.zip':'b123325962778da3e1eed66cdc48cba3c396a092b3455baf8d032ed0115e3660',
 'STICKMAN_V5_1_ENGINE_SOURCE.zip':'67b49cc7275cd741a70f5851bf1f98d0a8cc7dbd3b1a884f458ddac789a21178',
 'SOUND_LIBRARY_V2_SOURCE.zip':'ad60805d725b74e3e208b621b1334b8f55dee5bfbe7e517ecd05279821953428'}
def sha(p):
 h=hashlib.sha256();
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
 return h.hexdigest()
def source_files():
 roots=['app','src','services','scripts','prisma'];out=[]
 for name in roots:
  p=ROOT/name
  if p.exists():out += [x for x in p.rglob('*') if x.is_file() and x.suffix.lower() not in {'.pyc','.zip','.png','.jpg','.jpeg','.mp4','.wav','.webp'}]
 out += [p for p in [ROOT/'README.md',ROOT/'package.json',ROOT/'.env.example'] if p.exists()];return out
texts={p:p.read_text(errors='ignore') for p in source_files()}
forbidden=['Nex'+'Markets','nex'+'markets','NEX'+'MARKETS','nex'+'_session','Robinhood'+' Chain','Debut'+' Edition','marketplace'+' shell']
brand_hits=[{'file':str(p.relative_to(ROOT)),'term':term} for p,t in texts.items() for term in forbidden if term in t]
browser_mount=[]
for p,t in texts.items():
 if p.suffix not in {'.ts','.tsx','.js','.jsx'}:continue
 for i,line in enumerate(t.splitlines(),1):
  if re.search(r'(router\.(?:push|replace)|location\.(?:href|assign|replace)|href\s*=).*?["\'`]\/studio(?:\/|["\'`])',line) and '/api/v1/studio' not in line:
   browser_mount.append({'file':str(p.relative_to(ROOT)),'line':i,'text':line.strip()[:180]})
hashes={name:{'expected':want,'actual':sha(ROOT/'engine_sources'/name),'ok':(ROOT/'engine_sources'/name).exists() and sha(ROOT/'engine_sources'/name)==want} for name,want in EXPECTED.items() if (ROOT/'engine_sources'/name).exists()}
required=['app/page.tsx','app/dashboard/page.tsx','app/production/new/page.tsx','app/production/[id]/page.tsx','src/studio-v1/react/StudioPublicExperience.tsx','src/studio-v1/react/ProductionWorkspace.tsx','services/studio-family-engines/worker.py','services/studio-nexmind-p8/orchestrator.py','vendor/nexmind-god-mode-p8']
checks=[]
def add(name,ok,detail=''):checks.append({'name':name,'ok':bool(ok),'detail':detail})
add('Standalone package identity',(json.loads((ROOT/'package.json').read_text(encoding='utf-8')).get('name')=='studio-v1-standalone'))
add('No legacy host application/source/session references',not brand_hits,json.dumps(brand_hits[:8]))
add('No browser route mounted at /studio',not browser_mount,json.dumps(browser_mount[:8]))
add('Root Studio application routes present',all((ROOT/x).exists() for x in required))
add('All five authoritative engine archives present',len(hashes)==5 and all(x['ok'] for x in hashes.values()),json.dumps(hashes))
add('P8 vendor snapshot present',(ROOT/'vendor/nexmind-god-mode-p8/src/nexmind_god_mode').exists())
home=(ROOT/'src/studio-v1/react/StudioPublicExperience.tsx').read_text(encoding='utf-8')
add('Public homepage does not lead with $2 pricing','$2' not in home and '$2/min' not in home)
add('Public navigation has Dashboard, not Projects','>Dashboard<' in home and '>Projects<' not in home)
workspace=(ROOT/'src/studio-v1/react/ProductionWorkspace.tsx').read_text(encoding='utf-8')
add('Pricing is disclosed subtly at saved brief/payment boundary','current rate is $2 per minute' in workspace and 'Saved brief' in workspace)
add('Customer review/revision path is present',('Approve film' in workspace or 'Approve current version' in workspace) and 'Request changes' in workspace and 'timestampSeconds' in workspace)
report={'schema':'StudioStandaloneSourceQA V1','pass':all(x['ok'] for x in checks),'checks':checks,'engineArchives':hashes,'environment':{'python':sys.version.split()[0],'node':subprocess.run(['node','-v'],capture_output=True,text=True).stdout.strip()}}
(ROOT/'reports').mkdir(exist_ok=True);(ROOT/'reports/STANDALONE_SOURCE_QA.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));raise SystemExit(0 if report['pass'] else 1)
