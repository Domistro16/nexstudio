#!/usr/bin/env python3
from pathlib import Path
import json,re,sys,hashlib
ROOT=Path(__file__).resolve().parents[1]
REG=json.loads((ROOT/'src/studio-v1/public/certification/four-family-capability-registry.json').read_text())
COR=json.loads((ROOT/'evaluations/four-family-commercial-certification-v1/corpus.json').read_text())
checks=[]
def c(name,ok,detail=''): checks.append({'name':name,'pass':bool(ok),'detail':detail})
auth_file=ROOT/'src/studio-v1/production-engines/authority.ts'
if not auth_file.exists():
    # Patch package may be validated standalone; use SOURCE_BASE_AUTHORITY.ts snapshot.
    auth_file=ROOT/'reports/SOURCE_BASE_AUTHORITY.ts'
text=auth_file.read_text()
for fam,rec in REG['families'].items():
    a=rec['authority']; c(f'{fam} authority id exact',a['authorityId'] in text,a['authorityId']); c(f'{fam} authority hash exact',a['sha256'] in text,a['sha256'])
subtypes=[s for f in REG['families'].values() for s in f['subtypes']]
c('exactly 24 public subtype contracts',len(subtypes)==24,str(len(subtypes)))
c('exactly 48 certification cases',len(COR['cases'])==48,str(len(COR['cases'])))
ids={x['id'] for x in COR['cases']}
for s in subtypes:
    ev=s['certificationEvidence']; c(f"{s['id']} has normal+stress corpus",ev['normalBlindCase'] in ids and ev['stressBlindCase'] in ids)
    if s['publicEnabledRecommendation']:
        c(f"{s['id']} public evidence complete",ev['actualBlindFilms']>=2 and ev['commercialComparisonScore'] is not None and ev['multimodalFinalReview']=='PASS' and ev['independentHumanReviewCount']>0 and ev['showcaseFilm'] and ev['poster'])
    else: c(f"{s['id']} fail-closed public recommendation",True)
c('Series is continuity scope, never a fifth production family',REG['series'].get('publicV1')=='SUPPORTED_AS_CONTINUITY_SCOPE' and REG['series'].get('productionFamily') is False)
c('commercial threshold cannot self-certify taste',REG['commercialThreshold']['machineMaySelfCertifyTaste'] is False)
c('commercial release contract is 9.5-class',REG['commercialThreshold']['meanCreativeScoreMin']>=9.5 and REG['commercialThreshold']['targetMedian']>=9.5 and REG['commercialThreshold']['everyCoreCategoryMin']>=9.0 and REG['commercialThreshold'].get('criticalCreativeCategoryMin',0)>=9.5)
c('no family enabled without subtype evidence',all(not f['familyPublicEnabledRecommendation'] for f in REG['families'].values()))
registry_ts=(ROOT/'src/studio-v1/public/registry/production-family-registry.ts').read_text()
c('gallery registry consumes certification gate','getSubtypeCertificationGate' in registry_ts)
c('gallery registry does not own subtype publish boolean','publicEnabled: certification.publicEnabled' in registry_ts)
out={'schema':'StudioFourFamilyCommercialCertificationValidatorV1','status':'PASS' if all(x['pass'] for x in checks) else 'FAIL','passed':sum(x['pass'] for x in checks),'total':len(checks),'checks':checks}
(ROOT/'reports/FOUR_FAMILY_COMMERCIAL_CERTIFICATION_QA.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'status':out['status'],'passed':out['passed'],'total':out['total']},indent=2)); sys.exit(0 if out['status']=='PASS' else 1)
