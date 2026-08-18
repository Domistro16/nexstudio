import base64,json,subprocess,time
from pathlib import Path
import requests, websocket
ROOT=Path(__file__).resolve().parents[1]
HARNESS=ROOT/'qa/public-experience-harness.html'
css=(ROOT/'app/studio-v1.css').read_text()
html=HARNESS.read_text().replace('<link rel="stylesheet" href="../app/studio-v1.css">',f'<style>{css}</style>')
OUT=ROOT/'qa/screenshots'
REPORT=ROOT/'reports/public-experience/BROWSER_QA.json'
PERF=ROOT/'reports/public-experience/PERFORMANCE_QA.json'
viewports={'desktop':(1440,1000),'tablet':(1024,1366),'mobile':(390,844)}
surfaces=['home','family','work','pricing','brief','context','auth','planning','plan','quote','lowbalance','production','screening','historical','revision']
port=9333
proc=subprocess.Popen(['/usr/bin/chromium','--headless=new','--no-sandbox','--disable-gpu','--remote-allow-origins=*',f'--remote-debugging-port={port}','--user-data-dir=/tmp/studio-public-qa','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
ws=None
try:
  data=None
  for _ in range(60):
    try:
      data=requests.get(f'http://127.0.0.1:{port}/json',timeout=.2).json();break
    except Exception: time.sleep(.1)
  if not data: raise RuntimeError('Chromium debug endpoint unavailable')
  ws=websocket.create_connection(data[0]['webSocketDebuggerUrl'],timeout=5)
  next_id=0
  def cmd(method,params=None):
    global next_id
    next_id+=1; ws.send(json.dumps({'id':next_id,'method':method,'params':params or {}}))
    while True:
      msg=json.loads(ws.recv())
      if msg.get('id')==next_id:
        if 'error' in msg: raise RuntimeError(msg['error'])
        return msg.get('result',{})
  cmd('Page.enable');cmd('Runtime.enable');cmd('Accessibility.enable');cmd('Performance.enable')
  frame_id=cmd('Page.getFrameTree')['frameTree']['frame']['id']
  cmd('Page.setDocumentContent',{'frameId':frame_id,'html':html});time.sleep(.35)
  checks=[]; perf_rows=[]
  for vp,(w,h) in viewports.items():
    cmd('Emulation.setDeviceMetricsOverride',{'width':w,'height':h,'deviceScaleFactor':1,'mobile':False})
    for surface in surfaces:
      cmd('Runtime.evaluate',{'expression':f'render({json.dumps(surface)})'});time.sleep(.16)
      metrics=cmd('Runtime.evaluate',{'expression':'JSON.stringify({w:innerWidth,h:innerHeight,scrollWidth:document.documentElement.scrollWidth,scrollHeight:document.documentElement.scrollHeight,buttons:[...document.querySelectorAll("button,a.sv1-action-link,input,textarea,select")].map(e=>{const r=e.getBoundingClientRect();return {tag:e.tagName,w:r.width,h:r.height,name:(e.innerText||e.getAttribute("aria-label")||e.getAttribute("placeholder")||"").trim()}}),h1:[...document.querySelectorAll("h1")].map(e=>e.innerText),landmarks:{header:!!document.querySelector("header"),main:!!document.querySelector("main"),nav:!!document.querySelector("nav")}})','returnByValue':True})
      m=json.loads(metrics['result']['value'])
      overflow=m['scrollWidth']>w+1
      tiny=[b for b in m['buttons'] if b['tag'] in ('BUTTON','A','INPUT','SELECT') and b['w']>0 and (b['h']<40 or b['w']<32)]
      checks.append({'viewport':vp,'surface':surface,'overflow':overflow,'tinyTargets':tiny,'landmarks':m['landmarks'],'h1':m['h1'],'pass':not overflow and not tiny and all(m['landmarks'].values())})
      layout=cmd('Page.getLayoutMetrics'); size=layout['cssContentSize']; cap=cmd('Page.captureScreenshot',{'format':'png','captureBeyondViewport':True,'clip':{'x':0,'y':0,'width':min(size['width'],w),'height':size['height'],'scale':1}})
      path=OUT/vp/f'{surface}.png';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(base64.b64decode(cap['data']))
      if surface=='home':
        perf=cmd('Runtime.evaluate',{'expression':'JSON.stringify({resources:performance.getEntriesByType("resource").length,htmlBytes:document.documentElement.outerHTML.length,domNodes:document.getElementsByTagName("*").length})','returnByValue':True})
        perf_rows.append({'viewport':vp,**json.loads(perf['result']['value'])})
  cmd('Runtime.evaluate',{'expression':'render("home")'});time.sleep(.1)
  ax=cmd('Accessibility.getFullAXTree')
  unnamed=[]
  for n in ax.get('nodes',[]):
    role=n.get('role',{}).get('value');name=n.get('name',{}).get('value','')
    if role in ('button','textbox','combobox','link') and not str(name).strip(): unnamed.append({'role':role,'nodeId':n.get('nodeId')})
  report={'schema':'StudioPublicExperienceBrowserQA V1','pass':all(c['pass'] for c in checks) and not unnamed,'viewports':viewports,'checks':checks,'accessibilityTree':{'unnamedInteractiveNodes':unnamed,'pass':not unnamed},'note':'Chromium renders the exact production stylesheet and customer copy through Page.setDocumentContent because local file/localhost navigation is blocked by the execution policy. This is browser evidence for the UI layer, not a dependency-complete Next.js deployment certification.'}
  REPORT.parent.mkdir(parents=True,exist_ok=True);REPORT.write_text(json.dumps(report,indent=2)+'\n')
  PERF.write_text(json.dumps({'schema':'StudioPublicExperiencePerformanceQA V1','harnessEvidence':perf_rows,'networkRequests':0,'pass':all(r.get('resources',0)==0 for r in perf_rows),'deploymentBuildStatus':'BLOCKED_BY_NODE24_DEPENDENCY_ENVIRONMENT','note':'Performance evidence covers the dependency-free production-CSS harness. Production Next.js metrics must be rerun under repository-required Node >=24 with installed dependencies.'},indent=2)+'\n')
  print(json.dumps({'pass':report['pass'],'checks':len(checks),'unnamed':len(unnamed),'perfRows':len(perf_rows)},indent=2))
finally:
  try:
    if ws: ws.close()
  except Exception: pass
  proc.terminate()
  try: proc.wait(timeout=3)
  except Exception: proc.kill()
