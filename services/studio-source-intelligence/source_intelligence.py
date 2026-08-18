#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, re, sys, zipfile, posixpath, shutil, subprocess, tempfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

MAX_SEGMENT_CHARS = 6_000  # chunk size only; never a corpus truncation limit


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def add_segment(out: list[dict[str, Any]], *, locator: str, text: str, kind: str, index: int | None = None) -> None:
    value = norm(text)
    if not value:
        return
    for start in range(0, len(value), MAX_SEGMENT_CHARS):
        chunk = value[start:start + MAX_SEGMENT_CHARS]
        out.append({
            "segmentId": f"seg-{len(out)+1:04d}",
            "locator": locator if start == 0 else f"{locator} / continuation {start // MAX_SEGMENT_CHARS + 1}",
            "kind": kind,
            "index": index,
            "text": chunk,
            "sha256": hashlib.sha256(chunk.encode("utf-8")).hexdigest(),
        })


def cap_segments(segments: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    # Historical API retained for callers, but extraction never destroys evidence.
    # Context windows are handled later by relevance/batching with explicit omissions.
    return list(segments), False


def extract_text_file(path: Path, mime: str) -> dict[str, Any]:
    raw = path.read_bytes()
    text = raw.decode("utf-8", "replace")
    segments: list[dict[str, Any]] = []
    if mime == "application/json":
        try:
            obj = json.loads(text)
            rendered = json.dumps(obj, ensure_ascii=False, indent=2)
            add_segment(segments, locator="JSON document", text=rendered, kind="json")
        except Exception:
            add_segment(segments, locator="Text document", text=text, kind="text")
    else:
        lines = text.splitlines()
        block: list[str] = []
        block_start = 1
        for line_no, line in enumerate(lines, 1):
            if not block: block_start = line_no
            block.append(line)
            if sum(len(x) + 1 for x in block) >= 4_000:
                add_segment(segments, locator=f"lines {block_start}-{line_no}", text="\n".join(block), kind="text")
                block=[]
        if block:
            add_segment(segments, locator=f"lines {block_start}-{len(lines)}", text="\n".join(block), kind="text")
    return {"segments": segments, "pageCount": None, "visualOnlyPages": []}


def safe_zip(path: Path) -> zipfile.ZipFile:
    z = zipfile.ZipFile(path)
    infos = z.infolist()
    if len(infos) > 20_000:
        raise RuntimeError("SOURCE_ARCHIVE_TOO_MANY_ENTRIES")
    total = sum(max(0, i.file_size) for i in infos)
    if total > 300 * 1024 * 1024:
        raise RuntimeError("SOURCE_ARCHIVE_UNCOMPRESSED_TOO_LARGE")
    for i in infos:
        if i.file_size > 80 * 1024 * 1024:
            raise RuntimeError("SOURCE_ARCHIVE_ENTRY_TOO_LARGE")
        name = i.filename.replace("\\", "/")
        if name.startswith("/") or "../" in name:
            raise RuntimeError("SOURCE_ARCHIVE_UNSAFE_PATH")
    return z


def xml_text(xml: bytes, tags: set[str] | None = None) -> list[str]:
    root = ET.fromstring(xml)
    values=[]
    for el in root.iter():
        local = el.tag.rsplit("}",1)[-1]
        if (tags is None or local in tags) and el.text:
            t=norm(el.text)
            if t: values.append(t)
    return values


def image_mime(name: str, data: bytes) -> str | None:
    lower=name.lower()
    if data.startswith(b"\x89PNG\r\n\x1a\n") or lower.endswith(".png"): return "image/png"
    if data[:3] == b"\xff\xd8\xff" or lower.endswith((".jpg",".jpeg")): return "image/jpeg"
    if (len(data)>=12 and data[:4]==b"RIFF" and data[8:12]==b"WEBP") or lower.endswith(".webp"): return "image/webp"
    if lower.endswith(".svg") or data.lstrip().startswith(b"<svg") or b"<svg" in data[:512].lower(): return "image/svg+xml"
    return None


def _safe_svg_to_png(data: bytes) -> bytes:
    # OOXML can legally contain SVG. Treat it as untrusted declarative artwork:
    # no scripts, foreignObject, or external/file/data URL dereferences are allowed.
    root=ET.fromstring(data)
    if root.tag.rsplit("}",1)[-1].lower()!="svg": raise RuntimeError("SOURCE_SVG_ROOT_INVALID")
    for el in root.iter():
        local=el.tag.rsplit("}",1)[-1].lower()
        if local in {"script","foreignobject"}: raise RuntimeError("SOURCE_SVG_ACTIVE_CONTENT_BLOCKED")
        for k,v in el.attrib.items():
            if k.rsplit("}",1)[-1].lower() in {"href","src"}:
                val=str(v or "").strip().lower()
                if val.startswith(("http:","https:","file:","data:","//")): raise RuntimeError("SOURCE_SVG_EXTERNAL_REFERENCE_BLOCKED")
    try:
        import cairosvg
        return cairosvg.svg2png(bytestring=data,unsafe=False,output_width=1280)
    except Exception as e:
        raise RuntimeError(f"SOURCE_SVG_RASTERIZATION_FAILED:{type(e).__name__}") from e

def write_visual_asset(z: zipfile.ZipFile, member: str, output_dir: Path, *, locator: str, index: int, page: int | None = None, role: str = "EMBEDDED_IMAGE") -> dict[str, Any] | None:
    if member not in z.namelist(): return None
    data=z.read(member); mime=image_mime(member,data)
    if not mime: return None
    target_dir=output_dir/"visual-evidence"; target_dir.mkdir(parents=True,exist_ok=True)
    if mime=="image/svg+xml":
        png=_safe_svg_to_png(data); target=target_dir/f"visual-{index:04d}.png"; target.write_bytes(png)
        return {"page":page,"locator":locator,"role":role,"path":str(target),"mimeType":"image/png","sha256":hashlib.sha256(png).hexdigest(),"sourceMimeType":"image/svg+xml","sourceSha256":hashlib.sha256(data).hexdigest()}
    ext={"image/png":"png","image/jpeg":"jpg","image/webp":"webp"}[mime]
    target=target_dir/f"visual-{index:04d}.{ext}"; target.write_bytes(data)
    return {"page":page,"locator":locator,"role":role,"path":str(target),"mimeType":mime,"sha256":hashlib.sha256(data).hexdigest()}


def rel_targets(z: zipfile.ZipFile, rel_member: str, base_member: str) -> dict[str, tuple[str,str]]:
    if rel_member not in z.namelist(): return {}
    root=ET.fromstring(z.read(rel_member)); out={}
    for rel in root.iter():
        if rel.tag.rsplit("}",1)[-1] != "Relationship": continue
        rid=rel.attrib.get("Id"); target=rel.attrib.get("Target"); kind=rel.attrib.get("Type","")
        if not rid or not target or rel.attrib.get("TargetMode")=="External": continue
        member=posixpath.normpath(posixpath.join(posixpath.dirname(base_member),target)).lstrip("/")
        if member.startswith("../"): continue
        out[rid]=(member,kind)
    return out


def extract_docx(path: Path, output_dir: Path) -> dict[str, Any]:
    segments=[]; visuals=[]; warnings=[]
    with safe_zip(path) as z:
        names=set(z.namelist())
        if "word/document.xml" not in names:
            raise RuntimeError("SOURCE_DOCX_DOCUMENT_XML_MISSING")
        root=ET.fromstring(z.read("word/document.xml"))
        body=next((x for x in root.iter() if x.tag.rsplit("}",1)[-1]=="body"),root)
        rels=rel_targets(z,"word/_rels/document.xml.rels","word/document.xml")
        p_index=0; table_index=0; visual_index=0; seen_visual=set()
        def capture_images(node, locator):
            nonlocal visual_index
            for el in node.iter():
                if el.tag.rsplit("}",1)[-1] != "blip": continue
                rid=next((v for k,v in el.attrib.items() if k.rsplit("}",1)[-1]=="embed"),None)
                if not rid or rid not in rels: continue
                member,kind=rels[rid]
                if "image" not in kind.lower() or member in seen_visual: continue
                seen_visual.add(member); visual_index+=1
                item=write_visual_asset(z,member,output_dir,locator=locator,index=visual_index)
                if item: visuals.append(item)
                else: warnings.append(f"UNSUPPORTED_EMBEDDED_VISUAL:{member}")
        for child in list(body):
            local=child.tag.rsplit("}",1)[-1]
            if local=="p":
                vals=[norm(x.text or "") for x in child.iter() if x.tag.rsplit("}",1)[-1]=="t" and norm(x.text or "")]
                p_index+=1
                if vals: add_segment(segments, locator=f"paragraph {p_index}", text=" ".join(vals), kind="paragraph", index=p_index)
                capture_images(child,f"paragraph {p_index}")
            elif local=="tbl":
                table_index+=1; rows=[]
                for tr in child.iter():
                    if tr.tag.rsplit("}",1)[-1]!="tr": continue
                    cells=[]
                    for tc in list(tr):
                        if tc.tag.rsplit("}",1)[-1]!="tc": continue
                        vals=[norm(x.text or "") for x in tc.iter() if x.tag.rsplit("}",1)[-1]=="t" and norm(x.text or "")]
                        cells.append(" ".join(vals))
                    if any(cells): rows.append(" | ".join(cells))
                if rows: add_segment(segments, locator=f"table {table_index}", text="\n".join(rows), kind="table", index=table_index)
                capture_images(child,f"table {table_index}")
        for name in sorted(n for n in names if re.fullmatch(r"word/(header|footer)\d+\.xml", n)):
            vals=xml_text(z.read(name), {"t"})
            if vals: add_segment(segments, locator=name.replace("word/", ""), text=" ".join(vals), kind="header_footer")
    return {"segments": segments, "pageCount": None, "visualOnlyPages": [], "visualPreviews": visuals, "warnings": warnings}


def _render_composed_document_pages(source: Path, output_dir: Path, *, prefix: str, role: str) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    binary = shutil.which("libreoffice") or shutil.which("soffice")
    if not binary:
        return [], ["COMPOSED_PAGE_RENDERER_UNAVAILABLE"]
    render_root=output_dir/f".{prefix}-composed-render"; render_root.mkdir(parents=True,exist_ok=True)
    try:
        proc=subprocess.run([binary,"--headless","--convert-to","pdf","--outdir",str(render_root),str(source)],capture_output=True,text=True,timeout=90)
        if proc.returncode!=0:
            return [], ["COMPOSED_PAGE_RENDER_FAILED:"+(proc.stderr or proc.stdout)[-500:]]
        pdfs=sorted(render_root.glob("*.pdf"))
        if not pdfs: return [], ["COMPOSED_PAGE_RENDER_PDF_MISSING"]
        import fitz
        doc=fitz.open(str(pdfs[0])); target_dir=output_dir/f"{prefix}-composed-pages"; target_dir.mkdir(parents=True,exist_ok=True)
        out=[]
        for zero in range(len(doc)):
            pix=doc.load_page(zero).get_pixmap(matrix=fitz.Matrix(1.35,1.35),alpha=False)
            target=target_dir/f"{prefix}-{zero+1:04d}.png"; pix.save(str(target)); raw=target.read_bytes()
            out.append({"page":zero+1,"locator":f"{prefix} {zero+1}","role":role,"path":str(target),"mimeType":"image/png","sha256":hashlib.sha256(raw).hexdigest(),"composed":True})
        doc.close(); return out,warnings
    except subprocess.TimeoutExpired:
        return [], ["COMPOSED_PAGE_RENDER_TIMEOUT"]
    except Exception as e:
        return [], [f"COMPOSED_PAGE_RENDER_FAILED:{type(e).__name__}"]


def extract_pptx(path: Path, output_dir: Path) -> dict[str, Any]:
    segments=[]; visuals=[]; warnings=[]
    with safe_zip(path) as z:
        names=set(z.namelist())
        slides=sorted((n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)), key=lambda n:int(re.search(r"(\d+)",Path(n).stem).group(1)))
        if not slides: raise RuntimeError("SOURCE_PPTX_SLIDES_MISSING")
        visual_index=0; seen_visual=set()
        for index,name in enumerate(slides,1):
            vals=xml_text(z.read(name), {"t"})
            if vals: add_segment(segments, locator=f"slide {index}", text="\n".join(vals), kind="slide", index=index)
            rel_member=f"ppt/slides/_rels/{Path(name).name}.rels"; rels=rel_targets(z,rel_member,name)
            for _,(member,kind) in rels.items():
                k=kind.lower()
                if "image" in k and member not in seen_visual:
                    seen_visual.add(member); visual_index+=1
                    item=write_visual_asset(z,member,output_dir,locator=f"slide {index} embedded image",index=visual_index,page=index)
                    if item: visuals.append(item)
                    else: warnings.append(f"UNSUPPORTED_EMBEDDED_VISUAL:{member}")
                elif "chart" in k and member in names:
                    chart_vals=xml_text(z.read(member), {"v","f"})
                    if chart_vals: add_segment(segments, locator=f"slide {index} chart data", text=" | ".join(chart_vals), kind="chart_data", index=index)
        notes=sorted(n for n in names if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml",n))
        for name in notes:
            index=int(re.search(r"(\d+)",Path(name).stem).group(1)); vals=xml_text(z.read(name), {"t"})
            if vals: add_segment(segments, locator=f"slide {index} speaker notes", text="\n".join(vals), kind="speaker_notes", index=index)
    composed, composed_warnings=_render_composed_document_pages(path,output_dir,prefix="slide",role="SLIDE_RENDER")
    warnings.extend(composed_warnings); visuals.extend(composed)
    if len(composed)!=len(slides): warnings.append(f"PPTX_COMPOSED_SLIDE_COVERAGE_PARTIAL:{len(composed)}/{len(slides)}")
    return {"segments":segments,"pageCount":len(slides),"visualOnlyPages":[],"visualPreviews":visuals,"composedPageCount":len(composed),"warnings":warnings}


def extract_pdf(path: Path, output_dir: Path) -> dict[str, Any]:
    try:
        from pypdf import PdfReader
    except Exception as e:
        raise RuntimeError(f"SOURCE_PDF_PARSER_UNAVAILABLE:{type(e).__name__}")
    reader=PdfReader(str(path), strict=False)
    if reader.is_encrypted:
        try:
            if reader.decrypt("") == 0: raise RuntimeError("SOURCE_PDF_ENCRYPTED")
        except Exception: raise RuntimeError("SOURCE_PDF_ENCRYPTED")
    segments=[]; visual_only=[]; visual_evidence_pages=[]
    page_text=[]
    for idx,page in enumerate(reader.pages,1):
        try: text=page.extract_text() or ""
        except Exception: text=""
        text=norm(text); page_text.append(text)
        if text: add_segment(segments, locator=f"page {idx}", text=text, kind="pdf_page", index=idx)
        else: visual_only.append(idx)
    previews=[]
    try:
        import fitz
        doc=fitz.open(str(path)); count=len(doc)
        if count:
            preview_dir=output_dir/"page-previews"; preview_dir.mkdir(parents=True,exist_ok=True)
            # Render every page. Resource control is batched by the caller/provider later;
            # ingestion must not silently discard page evidence.
            for zero in range(count):
                page=doc.load_page(zero)
                try:
                    visually_complex=bool(page.get_images(full=True)) or len(page.get_drawings()) >= 3 or (zero+1) in visual_only
                except Exception:
                    visually_complex=(zero+1) in visual_only
                if visually_complex: visual_evidence_pages.append(zero+1)
                pix=page.get_pixmap(matrix=fitz.Matrix(1.25,1.25), alpha=False)
                target=preview_dir/f"page-{zero+1:04d}.png"; pix.save(str(target))
                previews.append({"page":zero+1,"locator":f"page {zero+1}","role":"PAGE_RENDER","path":str(target),"mimeType":"image/png","sha256":hashlib.sha256(target.read_bytes()).hexdigest(),"visuallyComplex":visually_complex})
            doc.close()
    except Exception:
        # Text extraction remains useful; the output explicitly records missing visual coverage.
        previews=[]
    return {"segments":segments,"pageCount":len(reader.pages),"visualOnlyPages":visual_only,"visualEvidencePages":visual_evidence_pages,"visualPreviews":previews}


def extract_image(path: Path, output_dir: Path, mime: str) -> dict[str, Any]:
    target_dir=output_dir/"native-media-previews"; target_dir.mkdir(parents=True,exist_ok=True)
    raw=path.read_bytes(); target=target_dir/("image"+path.suffix.lower())
    target.write_bytes(raw)
    width=height=None
    try:
        from PIL import Image
        with Image.open(path) as im: width,height=im.size
    except Exception: pass
    return {"segments":[],"pageCount":1,"visualOnlyPages":[1],"visualPreviews":[{"page":1,"locator":"native image","role":"NATIVE_IMAGE","path":str(target),"mimeType":mime,"sha256":hashlib.sha256(raw).hexdigest(),"width":width,"height":height}],"composedPageCount":1,"warnings":[]}


def _ffprobe(path: Path) -> dict[str, Any]:
    proc=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration,size,format_name:stream=index,codec_type,codec_name,width,height,sample_rate,channels,r_frame_rate","-of","json",str(path)],capture_output=True,text=True,timeout=30)
    if proc.returncode!=0: raise RuntimeError("SOURCE_MEDIA_FFPROBE_FAILED:"+(proc.stderr or "")[-400:])
    return json.loads(proc.stdout or "{}")


def extract_video(path: Path, output_dir: Path, mime: str) -> dict[str, Any]:
    probe=_ffprobe(path); duration=float((probe.get("format") or {}).get("duration") or 0)
    target_dir=output_dir/"native-video-frames"; target_dir.mkdir(parents=True,exist_ok=True)
    # Temporal keyframes are an index into the complete retained native video, not a
    # replacement for it. The source hash/path remain first-class evidence.
    fractions=(0.0,.25,.5,.75,.99) if duration>0 else (0.0,)
    visuals=[]
    for i,f in enumerate(fractions,1):
        at=max(0.0,duration*f); target=target_dir/f"frame-{i:02d}.jpg"
        proc=subprocess.run(["ffmpeg","-y","-loglevel","error","-ss",f"{at:.3f}","-i",str(path),"-frames:v","1","-q:v","2",str(target)],capture_output=True,text=True,timeout=30)
        if proc.returncode==0 and target.exists():
            raw=target.read_bytes(); visuals.append({"page":i,"locator":f"video t={at:.3f}s","role":"VIDEO_KEYFRAME","path":str(target),"mimeType":"image/jpeg","sha256":hashlib.sha256(raw).hexdigest(),"timeSeconds":at})
    metadata=json.dumps({"durationSeconds":duration,"streams":probe.get("streams") or []},ensure_ascii=False)
    seg=[]; add_segment(seg,locator="native video technical metadata",text=metadata,kind="video_metadata")
    warnings=[] if visuals else ["VIDEO_KEYFRAME_EXTRACTION_UNAVAILABLE"]
    warnings.append("VIDEO_TRANSCRIPT_REQUIRES_CONFIGURED_SOURCE_AUDIO_TRANSCRIPTION_ROUTE")
    return {"segments":seg,"pageCount":None,"visualOnlyPages":[],"visualPreviews":visuals,"nativeMedia":{"path":str(path),"mimeType":mime,"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"durationSeconds":duration,"probe":probe},"warnings":warnings}


def extract_audio(path: Path, output_dir: Path, mime: str) -> dict[str, Any]:
    probe=_ffprobe(path); duration=float((probe.get("format") or {}).get("duration") or 0)
    seg=[]; add_segment(seg,locator="native audio technical metadata",text=json.dumps({"durationSeconds":duration,"streams":probe.get("streams") or []},ensure_ascii=False),kind="audio_metadata")
    return {"segments":seg,"pageCount":None,"visualOnlyPages":[],"visualPreviews":[],"nativeMedia":{"path":str(path),"mimeType":mime,"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"durationSeconds":duration,"probe":probe},"warnings":["AUDIO_TRANSCRIPT_REQUIRES_CONFIGURED_SOURCE_AUDIO_TRANSCRIPTION_ROUTE"]}

def extract(req: dict[str, Any]) -> dict[str, Any]:
    path=Path(req["path"]); mime=str(req.get("mimeType") or "application/octet-stream"); name=str(req.get("name") or path.name)
    output_dir=Path(req.get("outputDirectory") or path.parent); output_dir.mkdir(parents=True,exist_ok=True)
    if mime=="application/pdf": result=extract_pdf(path,output_dir); kind="PDF"
    elif mime=="application/vnd.openxmlformats-officedocument.wordprocessingml.document": result=extract_docx(path,output_dir); kind="DOCX"
    elif mime=="application/vnd.openxmlformats-officedocument.presentationml.presentation": result=extract_pptx(path,output_dir); kind="PPTX"
    elif mime in {"text/plain","text/csv","application/json"}: result=extract_text_file(path,mime); kind="TEXT"
    elif mime.startswith("image/"): result=extract_image(path,output_dir,mime); kind="IMAGE"
    elif mime.startswith("video/"): result=extract_video(path,output_dir,mime); kind="VIDEO"
    elif mime.startswith("audio/"): result=extract_audio(path,output_dir,mime); kind="AUDIO"
    else:
        return {"schema":"StudioSourceIntelligenceV1","status":"UNSUPPORTED_MEDIA","name":name,"mimeType":mime,"documentKind":"UNSUPPORTED_MEDIA","segments":[],"visualPreviews":[],"warnings":["SOURCE_MEDIA_TYPE_UNSUPPORTED_EXPLICITLY"]}
    segments,truncated=cap_segments(result.get("segments") or [])
    total_chars=sum(len(s["text"]) for s in segments)
    content_hash=hashlib.sha256(path.read_bytes()).hexdigest()
    visual_previews=result.get("visualPreviews") or []
    page_count=result.get("pageCount")
    warnings=list(result.get("warnings") or [])
    if truncated: raise RuntimeError("SOURCE_INTELLIGENCE_INTERNAL_TRUNCATION_FORBIDDEN")
    if result.get("visualOnlyPages"): warnings.append("SOURCE_CONTAINS_VISUAL_ONLY_PAGES")
    if mime=="application/pdf" and not visual_previews: warnings.append("PDF_PAGE_PREVIEW_RENDERING_UNAVAILABLE")
    composed_count=result.get("composedPageCount")
    if mime=="application/pdf": composed_count=len([v for v in visual_previews if v.get("role")=="PAGE_RENDER"])
    if mime.startswith("image/"): composed_count=1
    if page_count is None:
        visual_coverage="INDEXED" if visual_previews else ("NATIVE_MEDIA" if result.get("nativeMedia") else "NONE")
    else:
        visual_coverage="FULL" if composed_count==page_count else ("PARTIAL" if visual_previews else "NONE")
    return {
        "schema":"StudioSourceIntelligenceV1","status":"EXTRACTED","name":name,"mimeType":mime,"documentKind":kind,
        "contentHash":content_hash,"segmentCount":len(segments),"totalExtractedChars":total_chars,"segments":segments,
        "pageCount":page_count,"visualOnlyPages":result.get("visualOnlyPages") or [],"visualEvidencePages":result.get("visualEvidencePages") or [],"visualPreviews":visual_previews,
        "visualCoverage":visual_coverage,"composedPageCount":composed_count,"nativeMedia":result.get("nativeMedia"),
        "warnings":warnings,
        "provenanceLaw":"Every extracted segment retains a source-local locator and hash. Extraction does not invent claims or reconcile contradictions.",
    }

try:
    request=json.load(sys.stdin); response=extract(request); json.dump(response,sys.stdout,ensure_ascii=False,separators=(",",":"));sys.stdout.write("\n")
except Exception as e:
    json.dump({"schema":"StudioSourceIntelligenceV1","status":"BLOCKED","code":"SOURCE_INTELLIGENCE_EXTRACTION_FAILED","detail":str(e)},sys.stdout,separators=(",",":"));sys.stdout.write("\n");sys.exit(2)
