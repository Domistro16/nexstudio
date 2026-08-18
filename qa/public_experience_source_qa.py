import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
checks=[]
def add(name,ok,detail=''): checks.append({'name':name,'ok':bool(ok),'detail':detail})
def text(rel): return (ROOT/rel).read_text()
public=text('src/studio-v1/react/StudioPublicExperience.tsx');work=text('src/studio-v1/react/StudioWorkExperience.tsx');pricing=text('src/studio-v1/react/StudioPricingExperience.tsx');workspace=text('src/studio-v1/react/ProductionWorkspace.tsx');newbrief=text('src/studio-v1/react/NewProductionBrief.tsx');css=text('app/studio-v1.css');draft_route=text('app/api/v1/studio/production-drafts/route.ts');recommend=text('app/api/v1/studio/recommendation/route.ts');versions=text('app/api/v1/studio/productions/[productionId]/versions/route.ts');output=text('app/api/v1/productions/[id]/output/route.ts')
cert=json.loads(text('src/studio-v1/public/certification/four-family-capability-registry.json'));subtypes=[s for f in cert['families'].values() for s in f['subtypes']];enabled=[s for s in subtypes if s.get('publicEnabledRecommendation')];media=[s for s in subtypes if s.get('publicAssets',{}).get('previewVideo') or s.get('publicAssets',{}).get('posterFrame')]
add('Public shell routes include Home, Work and Pricing',all((ROOT/p).exists() for p in ['app/page.tsx','app/work/page.tsx','app/pricing/page.tsx']))
add('Exactly four public production families retained',set(cert['families'])=={'explainer','whiteboard','stickman','editorial-motion'})
add('All 24 subtype contracts retained',len(subtypes)==24)
add('Current certification remains fail-closed',len(enabled)==0,f'{len(enabled)}/24 public-enabled')
add('No uncertified showcase media is attached',len(media)==0,f'{len(media)} subtype media records')
add('No development-only unverified public bypass remains','allowUnverifiedTypes' not in public+text('app/page.tsx'))
add('Direct public draft creation enforces certified subtype','isPublicVideoType(publicType)' in draft_route and 'PUBLIC_PRODUCTION_TYPE_NOT_CERTIFIED' in draft_route)
add('New-production URL cannot bypass public gate','isPublicVideoType(item)' in newbrief)
add('Studio recommendation chooses only public-certified candidates','getPublicVideoTypes(PRODUCTION_REGISTRY' in recommend and 'candidates.length' in recommend)
add('Recommendation fails closed instead of inventing a type','status:"unavailable"' in recommend and 'RECOMMENDATION_UNAVAILABLE' in recommend)
add('Work gallery renders only public-certified video types','getPublicVideoTypes(PRODUCTION_REGISTRY' in work)
add('No placeholder preview remains','Preview pending verification' not in public+work and 'is-pending' not in public+work)
legacy_theatre=['sv1-orbit','sv1-production-light','sv1-live-dot']
keyframes=re.findall(r'@keyframes\s+([A-Za-z0-9_-]+)',css)
add('Decorative AI theatre removed',all(x not in css+workspace for x in legacy_theatre) and all(name in {'nxs-bloom-a','nxs-bloom-b'} for name in keyframes),f'approved ambient keyframes: {keyframes}')
prod_segment=workspace[workspace.find('sv1-production-room'):workspace.find('state === "FINAL_REVIEW"')]
add('Production status has no fabricated percentage','No percentage or finish time is invented.' in workspace and 'setInterval' not in prod_segment)
add('Pricing page uses canonical base rate','$2' in pricing and 'per finished minute' in pricing)
add('Homepage does not lead with price','$2' not in public)
add('Complimentary plan remains pre-payment','Complimentary plan' in workspace and 'Approve plan' in workspace)
add('Low-balance continuation exists','Add balance & continue' in workspace)
add('Screening room supports revision and approval','Screening room' in workspace and 'Request changes' in workspace and 'Approve current version' in workspace)
add('Version history is owner-scoped','ownerUserId:auth.session!.userId' in versions and 'currentVersionNumber' in versions)
add('Historical output is owner-scoped and version-addressable','requestedVersion' in output and 'ownerUserId:auth.session!.userId' in output)
add('Revision stays in same paid production','same paid production' in workspace.lower())
add('Public copy does not expose internal creative authorities',not re.search(r'\b(NexMind|P8|Showrunner|DirectorV\d|Creative Lock|renderer)\b',public+work+pricing+newbrief,re.I))
add('Public sign-in dialog has focus trap','aria-modal="true"' in public and 'event.key !== "Tab"' in public and 'event.key === "Escape"' in public)
add('Production auth continuation has focus trap','authDialogRef' in workspace and 'event.key !== "Tab"' in workspace and 'event.key === "Escape"' in workspace)
add('Reduced-motion path remains','prefers-reduced-motion: reduce' in css)
add('Responsive breakpoints retained',all(x in css for x in ['max-width:1100px','max-width:760px','max-width:480px']))
add('Header/compact action targets are 44px minimum','min-height:2.75rem' in css)
report={'schema':'StudioPublic10PublicExperienceSourceQA V1','pass':all(c['ok'] for c in checks),'passed':sum(c['ok'] for c in checks),'total':len(checks),'checks':checks,'currentPublicState':{'publicEnabledSubtypes':len(enabled),'certifiedShowcaseMedia':len(media)}}
out=ROOT/'reports/public-experience/SOURCE_QA.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'pass':report['pass'],'passed':report['passed'],'total':report['total'],'failed':[c['name'] for c in checks if not c['ok']]},indent=2));sys.exit(0 if report['pass'] else 1)
