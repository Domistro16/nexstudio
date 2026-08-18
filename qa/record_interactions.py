import base64,json,shutil,subprocess,time
from pathlib import Path
import requests,websocket
ROOT=Path(__file__).resolve().parents[1]
css=(ROOT/'app/studio-v1.css').read_text();html=(ROOT/'qa/public-experience-harness.html').read_text().replace('<link rel="stylesheet" href="../app/studio-v1.css">',f'<style>{css}</style>')
port=9444
proc=subprocess.Popen(['/usr/bin/chromium','--headless=new','--no-sandbox','--disable-gpu','--remote-allow-origins=*',f'--remote-debugging-port={port}','--user-data-dir=/tmp/studio-public-recording','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
ws=None
try:
  data=None
  for _ in range(60):
    try:data=requests.get(f'http://127.0.0.1:{port}/json',timeout=.2).json();break
    except Exception:time.sleep(.1)
  if not data:raise RuntimeError('Chromium unavailable')
  ws=websocket.create_connection(data[0]['webSocketDebuggerUrl'],timeout=5);seq_id=0
  def cmd(method,params=None):
    global seq_id
    seq_id+=1;ws.send(json.dumps({'id':seq_id,'method':method,'params':params or {}}))
    while True:
      msg=json.loads(ws.recv())
      if msg.get('id')==seq_id:return msg.get('result',{})
  cmd('Page.enable');cmd('Runtime.enable');cmd('Emulation.setDeviceMetricsOverride',{'width':1440,'height':900,'deviceScaleFactor':1,'mobile':False});frame=cmd('Page.getFrameTree')['frameTree']['frame']['id'];cmd('Page.setDocumentContent',{'frameId':frame,'html':html});time.sleep(.3)
  def make(name,states,fps=8,dwell=1.1):
    frame_dir=ROOT/f'qa/recordings/.frames-{name}';shutil.rmtree(frame_dir,ignore_errors=True);frame_dir.mkdir(parents=True)
    n=0;per=max(1,int(fps*dwell))
    for state in states:
      cmd('Runtime.evaluate',{'expression':f'render({json.dumps(state)})'})
      for _ in range(per):
        time.sleep(1/fps)
        shot=cmd('Page.captureScreenshot',{'format':'jpeg','quality':88,'fromSurface':True})
        (frame_dir/f'{n:05d}.jpg').write_bytes(base64.b64decode(shot['data']));n+=1
    out=ROOT/f'qa/recordings/{name}-interaction-qa.mp4'
    subprocess.run(['/usr/bin/ffmpeg','-y','-framerate',str(fps),'-i',str(frame_dir/'%05d.jpg'),'-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-r','24',str(out)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    shutil.rmtree(frame_dir,ignore_errors=True);return out
  print(make('public',['home','family','work','pricing','home']))
  print(make('workspace',['brief','context','auth','brief','planning','plan','quote','lowbalance','production','screening','historical','screening','revision','screening']))
finally:
  try:
    if ws:ws.close()
  except:pass
  proc.terminate()
  try:proc.wait(timeout=3)
  except:proc.kill()
