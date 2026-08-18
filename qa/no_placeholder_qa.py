import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
files=['src/studio-v1/react/StudioPublicExperience.tsx','src/studio-v1/react/StudioWorkExperience.tsx','src/studio-v1/react/StudioPricingExperience.tsx','src/studio-v1/react/NewProductionBrief.tsx','src/studio-v1/react/ProductionWorkspace.tsx','app/page.tsx','app/work/page.tsx','app/pricing/page.tsx']
blob='\n'.join((ROOT/f).read_text() for f in files)
forbidden=['Preview pending verification','is-pending','Lorem ipsum','sample project','example project','synthetic preview','fake progress','placeholder media']
hits={term:[f for f in files if term.lower() in (ROOT/f).read_text().lower()] for term in forbidden};hits={k:v for k,v in hits.items() if v}
input_hints=sum(len(re.findall(r'placeholder=',(ROOT/f).read_text())) for f in files)
cert=json.loads((ROOT/'src/studio-v1/public/certification/four-family-capability-registry.json').read_text());subtypes=[s for fam in cert['families'].values() for s in fam['subtypes']];attached=[s['id'] for s in subtypes if s.get('publicAssets',{}).get('previewVideo') or s.get('publicAssets',{}).get('posterFrame')]
report={'schema':'StudioPublicExperienceNoPlaceholderQA V1','pass':not hits and not attached,'fabricatedContentMarkers':hits,'uncertifiedSubtypeMediaAttached':attached,'inputHintPlaceholders':input_hints,'inputHintPolicy':'Native form placeholders are permitted only as field-entry hints; they are not showcase, project, production, poster or film content.','qaHarnessPolicy':'The browser QA harness is test-only and is not part of the customer application or public media registry.'}
out=ROOT/'reports/public-experience/NO_PLACEHOLDER_QA.json';out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));sys.exit(0 if report['pass'] else 1)
