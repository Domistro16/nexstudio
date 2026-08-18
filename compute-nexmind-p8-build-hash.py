#!/usr/bin/env python3
from pathlib import Path
import hashlib

ROOT=Path.cwd()
roots=[
    ROOT/"vendor/nexmind-god-mode-p8/src/nexmind_god_mode",
    ROOT/"services/studio-nexmind-p8",
    ROOT/"src/studio-v1/nexmind-p8",
]
files=[]
for base in roots:
    if not base.exists():
        raise SystemExit(f"Missing P8 source root: {base}")
    for p in base.rglob("*"):
        if not p.is_file(): continue
        if "__pycache__" in p.parts or p.suffix in {".pyc",".pyo"}: continue
        files.append(p)
files.sort(key=lambda p:p.relative_to(ROOT).as_posix())

h=hashlib.sha256()
for p in files:
    rel=p.relative_to(ROOT).as_posix().encode("utf-8")
    digest=hashlib.sha256(p.read_bytes()).hexdigest().encode("ascii")
    h.update(rel); h.update(b"\0"); h.update(digest); h.update(b"\n")

value=h.hexdigest()
print(value)
print(f"Files bound: {len(files)}")
print("Set this exact value as NEXMIND_P8_BUILD_HASH in .env")
