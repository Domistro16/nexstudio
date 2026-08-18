import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
css=(ROOT/'app/studio-v1.css').read_text();public=(ROOT/'src/studio-v1/react/StudioPublicExperience.tsx').read_text();workspace=(ROOT/'src/studio-v1/react/ProductionWorkspace.tsx').read_text();browser=json.loads((ROOT/'reports/public-experience/BROWSER_QA.json').read_text())
def lum(h):
 c=[int(h[i:i+2],16)/255 for i in (1,3,5)];c=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in c];return .2126*c[0]+.7152*c[1]+.0722*c[2]
def contrast(a,b):
 x,y=lum(a),lum(b);return round((max(x,y)+.05)/(min(x,y)+.05),2)
pairs=[('calm primary','#191a18','#f2eee4',4.5),('calm secondary','#585a55','#f2eee4',4.5),('calm quiet','#686b64','#f2eee4',4.5),('production primary','#f2efe7','#101210',4.5),('production secondary','#b6b8b0','#101210',4.5),('production quiet','#7f847b','#101210',4.5),('calm focus','#315e54','#f2eee4',3.0),('production focus','#8eb6aa','#101210',3.0)]
contrast_rows=[{'pair':n,'foreground':a,'background':b,'ratio':contrast(a,b),'required':req,'pass':contrast(a,b)>=req} for n,a,b,req in pairs]
checks=[
 {'name':'Text/focus contrast','ok':all(x['pass'] for x in contrast_rows),'detail':contrast_rows},
 {'name':'Browser accessibility tree has no unnamed interactive nodes','ok':browser['accessibilityTree']['pass'],'detail':browser['accessibilityTree']},
 {'name':'33 responsive surfaces have no undersized tested controls','ok':all(not c['tinyTargets'] for c in browser['checks']),'detail':'44px header/primary target gate + >=40px browser target audit'},
 {'name':'Sign-in modal supports Escape and trapped Tab navigation','ok':'event.key === "Escape"' in public and 'event.key !== "Tab"' in public,'detail':''},
 {'name':'Production auth continuation supports Escape and trapped Tab navigation','ok':'event.key === "Escape"' in workspace and 'event.key !== "Tab"' in workspace,'detail':''},
 {'name':'Reduced-motion path removes nonessential transition duration','ok':'prefers-reduced-motion: reduce' in css and 'animation-duration:1ms' in css and 'transition-duration:1ms' in css,'detail':''},
 {'name':'Focus-visible styling covers buttons, fields, selects and links','ok':'select:focus-visible' in css and 'a:focus-visible' in css and 'button:focus-visible' in css,'detail':''},
 {'name':'Screening version selector is labeled','ok':'htmlFor="sv1-version-select"' in workspace,'detail':''},
 {'name':'Revision fields are explicitly labeled','ok':'htmlFor="sv1-revision-time"' in workspace and 'htmlFor="sv1-revision-note"' in workspace,'detail':''},
]
report={'schema':'StudioPublicExperienceAccessibilityQA V1','pass':all(c['ok'] for c in checks),'passed':sum(c['ok'] for c in checks),'total':len(checks),'checks':checks,'standard':'WCAG 2.2-oriented implementation audit; not a third-party conformance certification'}
out=ROOT/'reports/public-experience/ACCESSIBILITY_QA.json';out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'pass':report['pass'],'passed':report['passed'],'total':report['total'],'contrast':contrast_rows},indent=2));sys.exit(0 if report['pass'] else 1)
