#!/usr/bin/env python3
from pathlib import Path
import os
import re
import sys

ROOT = Path.cwd()

FILES = {
    "benchmark": ROOT / "engines" / "whiteboard" / "Whiteboard_Execution_Body_V2" / "explainer-motion" / "benchmarks-stress-v1" / "runtime" / "benchmark_renderer.py",
    "adapter": ROOT / "engines" / "whiteboard" / "Whiteboard_Execution_Body_V2" / "explainer-motion" / "whiteboard-v1" / "runtime" / "whiteboard_pil_adapter.py",
}

for name, path in FILES.items():
    if not path.exists():
        raise SystemExit(f"Missing expected file: {path}")

benchmark = FILES["benchmark"]
text = benchmark.read_text(encoding="utf-8")

old_block = """FONT_SANS='/usr/share/fonts/truetype/arimo/Arimo-Regular.ttf'
FONT_SANS_B='/usr/share/fonts/truetype/arimo/Arimo-Bold.ttf'
FONT_SERIF='/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf'
FONT_SERIF_B='/usr/share/fonts/truetype/noto/NotoSerif-Bold.ttf'
if not Path(FONT_SANS).exists(): FONT_SANS='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
if not Path(FONT_SANS_B).exists(): FONT_SANS_B='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
if not Path(FONT_SERIF).exists(): FONT_SERIF=FONT_SANS
if not Path(FONT_SERIF_B).exists(): FONT_SERIF_B=FONT_SANS_B
"""

new_block = """def _first_font(*candidates):
 for raw in candidates:
  if not raw: continue
  p=Path(raw)
  if p.exists(): return str(p)
 return None

_WINDIR=Path(os.environ.get('WINDIR', r'C:\\\\Windows'))
FONT_SANS=_first_font(
 _WINDIR/'Fonts'/'segoeui.ttf',
 _WINDIR/'Fonts'/'arial.ttf',
 _WINDIR/'Fonts'/'calibri.ttf',
 '/usr/share/fonts/truetype/arimo/Arimo-Regular.ttf',
 '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
 '/System/Library/Fonts/Supplemental/Arial.ttf',
)
FONT_SANS_B=_first_font(
 _WINDIR/'Fonts'/'segoeuib.ttf',
 _WINDIR/'Fonts'/'arialbd.ttf',
 _WINDIR/'Fonts'/'calibrib.ttf',
 '/usr/share/fonts/truetype/arimo/Arimo-Bold.ttf',
 '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
 '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
) or FONT_SANS
FONT_SERIF=_first_font(
 _WINDIR/'Fonts'/'times.ttf',
 _WINDIR/'Fonts'/'georgia.ttf',
 '/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf',
 '/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf',
 '/System/Library/Fonts/Supplemental/Times New Roman.ttf',
) or FONT_SANS
FONT_SERIF_B=_first_font(
 _WINDIR/'Fonts'/'timesbd.ttf',
 _WINDIR/'Fonts'/'georgiab.ttf',
 '/usr/share/fonts/truetype/noto/NotoSerif-Bold.ttf',
 '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf',
 '/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf',
) or FONT_SERIF
"""

if old_block not in text:
    raise SystemExit("benchmark_renderer.py font block did not match expected source.")
text = text.replace(old_block, new_block, 1)

old_func = "def font(sz,bold=False,serif=False): return ImageFont.truetype((FONT_SERIF_B if bold else FONT_SERIF) if serif else (FONT_SANS_B if bold else FONT_SANS),max(8,int(sz)))"
new_func = """def font(sz,bold=False,serif=False):
 size=max(8,int(sz))
 path=(FONT_SERIF_B if bold else FONT_SERIF) if serif else (FONT_SANS_B if bold else FONT_SANS)
 if path:
  try: return ImageFont.truetype(path,size)
  except OSError: pass
 return ImageFont.load_default()"""
if old_func not in text:
    raise SystemExit("benchmark_renderer.py font() did not match expected source.")
text = text.replace(old_func, new_func, 1)

# benchmark_renderer already imports many stdlib modules but not os.
text = text.replace("import json, math, re, textwrap, hashlib, random, io",
                    "import json, math, re, textwrap, hashlib, random, io, os", 1)
benchmark.write_text(text, encoding="utf-8", newline="\n")

adapter = FILES["adapter"]
text = adapter.read_text(encoding="utf-8")

old_block = """FONT='/usr/share/fonts/truetype/arimo/Arimo-Regular.ttf'
FONT_B='/usr/share/fonts/truetype/arimo/Arimo-Bold.ttf'
if not Path(FONT).exists(): FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
if not Path(FONT_B).exists(): FONT_B='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
"""

new_block = """def _first_font(*candidates):
 for raw in candidates:
  if not raw: continue
  p=Path(raw)
  if p.exists(): return str(p)
 return None

_WINDIR=Path(os.environ.get('WINDIR', r'C:\\\\Windows'))
FONT=_first_font(
 _WINDIR/'Fonts'/'segoeui.ttf',
 _WINDIR/'Fonts'/'arial.ttf',
 _WINDIR/'Fonts'/'calibri.ttf',
 '/usr/share/fonts/truetype/arimo/Arimo-Regular.ttf',
 '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
 '/System/Library/Fonts/Supplemental/Arial.ttf',
)
FONT_B=_first_font(
 _WINDIR/'Fonts'/'segoeuib.ttf',
 _WINDIR/'Fonts'/'arialbd.ttf',
 _WINDIR/'Fonts'/'calibrib.ttf',
 '/usr/share/fonts/truetype/arimo/Arimo-Bold.ttf',
 '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
 '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
) or FONT
"""

if old_block not in text:
    raise SystemExit("whiteboard_pil_adapter.py font block did not match expected source.")
text = text.replace(old_block, new_block, 1)

old_func = "def _font(sz,b=False): return ImageFont.truetype(FONT_B if b else FONT,max(8,int(sz)))"
new_func = """def _font(sz,b=False):
 size=max(8,int(sz))
 path=FONT_B if b else FONT
 if path:
  try: return ImageFont.truetype(path,size)
  except OSError: pass
 return ImageFont.load_default()"""
if old_func not in text:
    raise SystemExit("whiteboard_pil_adapter.py _font() did not match expected source.")
text = text.replace(old_func, new_func, 1)

text = text.replace("import json, math, random, re",
                    "import json, math, random, re, os", 1)
adapter.write_text(text, encoding="utf-8", newline="\n")

print("PATCHED:")
for path in FILES.values():
    print(path)
print()
print("Windows font candidates found:")
windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
for font in ("segoeui.ttf", "segoeuib.ttf", "arial.ttf", "arialbd.ttf", "times.ttf", "timesbd.ttf"):
    p = windir / "Fonts" / font
    print(f"{font}: {p.exists()} ({p})")
