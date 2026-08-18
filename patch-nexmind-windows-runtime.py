#!/usr/bin/env python3
from __future__ import annotations
import os, sys
from pathlib import Path

ROOT = Path.cwd()

def read(p: Path) -> str:
    return p.read_text(encoding='utf-8')

def write(p: Path, text: str):
    p.write_text(text, encoding='utf-8', newline='\n')
    print('PATCHED:', p)

def patch_worker():
    p = ROOT/'services/studio-family-engines/worker.py'
    t = read(p)
    t = t.replace('from stickman_adapter import build_internal_evidence as build_stickman_evidence\n','')
    old='        elif family=="STICKMAN": out=build_stickman_evidence(request)'
    new='''        elif family=="STICKMAN":\n            from stickman_adapter import build_internal_evidence as build_stickman_evidence\n            out=build_stickman_evidence(request)'''
    if old in t:
        t=t.replace(old,new,1)
    write(p,t)

def patch_standalone_qa():
    p=ROOT/'scripts/standalone-qa.py'; t=read(p)
    t=t.replace("(ROOT/'package.json').read_text()", "(ROOT/'package.json').read_text(encoding='utf-8')")
    t=t.replace("(ROOT/'src/studio-v1/react/StudioPublicExperience.tsx').read_text()", "(ROOT/'src/studio-v1/react/StudioPublicExperience.tsx').read_text(encoding='utf-8')")
    t=t.replace("(ROOT/'src/studio-v1/react/ProductionWorkspace.tsx').read_text()", "(ROOT/'src/studio-v1/react/ProductionWorkspace.tsx').read_text(encoding='utf-8')")
    write(p,t)

def patch_editorial_browser():
    p=ROOT/'services/studio-family-engines/editorial_adapter.py'; t=read(p)
    if 'def _browser_executable()->str:' not in t:
        anchor='def _capture(html:Path,frames:Path,duration:float,ratio:str,fps:int=8)->dict:\n'
        if anchor not in t: raise SystemExit('Could not find Editorial _capture()')
        resolver=r'''def _browser_executable()->str:
 candidates=[]
 explicit=(os.environ.get('STUDIO_CHROMIUM_PATH') or os.environ.get('CHROMIUM_EXECUTABLE_PATH') or os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH') or '').strip()
 if explicit:candidates.append(Path(explicit))
 if os.name=='nt':
  pf=os.environ.get('ProgramFiles',r'C:\Program Files')
  pfx86=os.environ.get('ProgramFiles(x86)',r'C:\Program Files (x86)')
  local=os.environ.get('LOCALAPPDATA','')
  candidates += [
   Path(pfx86)/'Microsoft/Edge/Application/msedge.exe',
   Path(pf)/'Microsoft/Edge/Application/msedge.exe',
   Path(pf)/'Google/Chrome/Application/chrome.exe',
   Path(pfx86)/'Google/Chrome/Application/chrome.exe',
  ]
  if local:
   candidates += [Path(local)/'Microsoft/Edge/Application/msedge.exe',Path(local)/'Google/Chrome/Application/chrome.exe']
 else:
  candidates += [Path('/usr/bin/chromium'),Path('/usr/bin/chromium-browser'),Path('/usr/bin/google-chrome')]
  if sys.platform=='darwin':
   candidates += [Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),Path('/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge')]
 for candidate in candidates:
  if candidate and candidate.exists():return str(candidate)
 raise AdapterBlocked('EDITORIAL_CHROMIUM_NOT_FOUND','Set STUDIO_CHROMIUM_PATH to Chrome/Edge/Chromium executable.')

'''
        t=t.replace(anchor,resolver+anchor,1)
    old="browser=p.chromium.launch(executable_path=os.environ.get('STUDIO_CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--disable-gpu','--no-sandbox'])"
    if old in t:
        t=t.replace(old,"browser=p.chromium.launch(executable_path=_browser_executable(),headless=True,args=['--disable-gpu','--no-sandbox'])",1)
    write(p,t)

def patch_explainer_tsx():
    p=ROOT/'services/studio-family-engines/explainer_adapter.py'; t=read(p)
    old='''def _tsx(root:Path)->Path:\n raw=os.environ.get('STUDIO_EXPLAINER_TSX_BIN','').strip()\n candidates=[Path(raw)] if raw else []\n candidates += [Path.cwd()/'node_modules'/'.bin'/'tsx',root/'node_modules'/'.bin'/'tsx']\n for p in candidates:\n  if str(p) and p.exists(): return p.resolve()\n raise AdapterBlocked('EXPLAINER_EXECUTION_BODY_DEPENDENCIES_NOT_INSTALLED','tsx not found. Install Standalone Studio production dependencies before rendering.')\n'''
    new='''def _tsx(root:Path)->list[str]:\n raw=os.environ.get('STUDIO_EXPLAINER_TSX_BIN','').strip()\n if raw:\n  p=Path(raw)\n  if p.exists():\n   if os.name=='nt' and p.suffix.lower() in {'.cmd','.bat'}: return [os.environ.get('COMSPEC','cmd.exe'),'/d','/s','/c',str(p.resolve())]\n   return [str(p.resolve())]\n for cli in [Path.cwd()/'node_modules'/'tsx'/'dist'/'cli.mjs',root/'node_modules'/'tsx'/'dist'/'cli.mjs']:\n  if cli.exists(): return ['node',str(cli.resolve())]\n for p in [Path.cwd()/'node_modules'/'.bin'/'tsx',root/'node_modules'/'.bin'/'tsx',Path.cwd()/'node_modules'/'.bin'/'tsx.cmd',root/'node_modules'/'.bin'/'tsx.cmd']:\n  if p.exists():\n   if os.name=='nt' and p.suffix.lower() in {'.cmd','.bat'}: return [os.environ.get('COMSPEC','cmd.exe'),'/d','/s','/c',str(p.resolve())]\n   return [str(p.resolve())]\n raise AdapterBlocked('EXPLAINER_EXECUTION_BODY_DEPENDENCIES_NOT_INSTALLED','tsx not found. Install Standalone Studio production dependencies before rendering.')\n'''
    if old in t: t=t.replace(old,new,1)
    oldcall="proc=subprocess.run([str(_tsx(root)),str(root/'scripts'/'studio-p8-explainer-runner.ts')],cwd=root,env=child_env,input=json.dumps(runner_request),text=True,capture_output=True)"
    if oldcall in t:
        t=t.replace(oldcall,"proc=subprocess.run([*_tsx(root),str(root/'scripts'/'studio-p8-explainer-runner.ts')],cwd=root,env=child_env,input=json.dumps(runner_request),text=True,capture_output=True)",1)
    write(p,t)

def patch_helper():
    p=ROOT/'nexmind-local-render.py'
    if not p.exists():
        print('NOTE: nexmind-local-render.py not found; helper patch skipped')
        return
    t=read(p)
    old="chromium = args.chromium or shutil.which('chromium') or shutil.which('chromium-browser') or ''"
    if old in t:
        new=r'''chromium = args.chromium or shutil.which('chromium') or shutil.which('chromium-browser') or ''
    if not chromium and os.name == 'nt':
        candidates = [
            Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe',
            Path(os.environ.get('ProgramFiles', r'C:\Program Files'))/'Microsoft/Edge/Application/msedge.exe',
            Path(os.environ.get('ProgramFiles', r'C:\Program Files'))/'Google/Chrome/Application/chrome.exe',
            Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'))/'Google/Chrome/Application/chrome.exe',
        ]
        chromium = next((str(x) for x in candidates if x.exists()), '')'''
        t=t.replace(old,new,1)
    oldenv="""    if chromium:\n        env['STUDIO_CHROMIUM_PATH'] = chromium\n"""
    newenv="""    if chromium:\n        env['STUDIO_CHROMIUM_PATH'] = chromium\n        env['CHROMIUM_EXECUTABLE_PATH'] = chromium\n        env['PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH'] = chromium\n"""
    if oldenv in t: t=t.replace(oldenv,newenv,1)
    write(p,t)

def main():
    if not (ROOT/'services/studio-family-engines/worker.py').exists():
        raise SystemExit('Run this from the NexStudio root folder.')
    patch_worker(); patch_standalone_qa(); patch_editorial_browser(); patch_explainer_tsx(); patch_helper()
    wb1=ROOT/'engines/whiteboard/Whiteboard_Execution_Body_V2/explainer-motion/benchmarks-stress-v1/runtime/benchmark_renderer.py'
    wb2=ROOT/'engines/whiteboard/Whiteboard_Execution_Body_V2/explainer-motion/whiteboard-v1/runtime/whiteboard_pil_adapter.py'
    if not (wb1.exists() and wb2.exists() and '_first_font' in read(wb1) and '_first_font' in read(wb2)):
        print('WARNING: Whiteboard font compatibility patch is not present in both files. Apply patch-whiteboard-fonts.py too.')
    else:
        print('OK: Whiteboard Windows font patch already present.')
    print('\nWindows runtime compatibility patch complete.')
    print('NOTE: STICKMAN still requires native Cairo on Windows. This is optional for the non-Character NexMind repair.')

if __name__=='__main__': main()
