#!/usr/bin/env python3
"""make_reel.py — one command: VO in, poster-framed reels out.

Pipeline: script/voice-file -> voice.mp3 + alignment.json -> auto-treatment
(style from styles.json, entities from entity_bank, customer media via
media_library) -> regression_pack render -> web file -> poster-framed file.

  python3 tools/make_reel.py --script "A few years ago, ..." --voice andrew \
      --style photo_story --media desk.png clip.mp4 --out out/my-reel
  python3 tools/make_reel.py --voice-file vo.mp3 --style sketch --aspects 1x1 --out out/r2
  python3 tools/make_reel.py --treatment fixtures/x/treatment.json --fixture-voice fixtures/x --out out/r3

Env: node must be on PATH for the renderer (nvm v24.x):
  export PATH=$HOME/.nvm/versions/node/v24.19.0/bin:$PATH
"""
import argparse, json, os, re, subprocess, sys, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parents[1] / 'services/studio-family-engines'))
from parallel_aspects import render_aspects
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
from generate_voice import synth, align, VOICES  # noqa: E402

STYLES = json.loads((ROOT / "styles.json").read_text())
STYLE_MAP = {s["id"]: s for s in STYLES["styles"]}
VARIANT_MAP = {f'{s["id"]}.{v["id"]}': (s, v) for s in STYLES["styles"] for v in s.get("variants", [])}
BANK = STYLES["entity_bank"]
_PHRASES_RAW = STYLES.get("entity_phrases", {})
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv"}

CLAUSE_END = re.compile(r"[.!?]$")
CLAUSE_MID = re.compile(r"[,;:]$")
STOPWORDS = set("the a an of to and or in on for with by at is are was were be been it its this that".split())
# function words that must never fuzzy-match into a drawable entity — the
# bank's exact vocabulary is unaffected (these never were keys anyway)
STOPWORDS |= set("""
i me my mine we us our ours you your yours he him his she her hers it its they
them their theirs this these those that there here when where who whom whose
which what how why all any both each few more most other others some such no
nor not only own same so than too very can will would could may might must
shall should ought just don doesnt didnt doesnt has have had do does did done
make made take took say said says go went gone come came see saw seen know
knew think thought want wanted let lets put set use used using find found
gave give gives tell told work worked works call called calls try tried tries
ask asked asks need needed needs feel felt become became leave left seem
seemed keep kept begin began now then also really much many less least every
everyone everything everybody anybody anyone someone somebody something
anything nothing none nobody once twice always never often sometimes usually
again still yet ever almost even about above across after against along among
around before behind below beneath beside between beyond down during except
inside into like off onto out outside over past since through throughout
toward towards under underneath until up upon within without via per near next
""".split())


def log(*a):
    print("[make_reel]", *a, flush=True)


def style_of(arg):
    if arg in VARIANT_MAP:
        s, v = VARIANT_MAP[arg]
        merged = dict(s); merged.update(v); merged.pop("variants", None)
        return merged
    if arg not in STYLE_MAP:
        sys.exit(f"unknown style '{arg}' — choices: {sorted(STYLE_MAP) + sorted(VARIANT_MAP)}")
    base = STYLE_MAP[arg]
    if base.get("show") and not base.get("shades") and base.get("variants"):
        return style_of(f'{arg}.{base["variants"][0]["id"]}')
    return base


# ---------- VO ----------
def _espeak_synth(text, out_wav, speed=1.0):
    """Free local fallback when the neural TTS stack isn't installed — espeak-ng
    voice at a brisk news pace. Returns duration in seconds."""
    wpm = max(120, int(175 * float(speed or 1.0)))
    subprocess.run(["espeak-ng", "-v", "en-us", "-s", str(wpm), "-w", str(out_wav), text], check=True)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", str(out_wav)],
                           capture_output=True, text=True, check=True)
    return float(probe.stdout.strip() or 1.0)


def _fake_align(wav_dur_s, text, out_json):
    """Deterministic word schedule (~330ms/word, +700ms after sentence end) stretched
    to fit the real wav — clause grouping and beat timing stay sane without whisper."""
    words = []
    t = 0.0
    for tok in text.split():
        w = re.sub(r"[^\w$%&.,!?'\"-]", "", tok)
        if not w:
            continue
        dur = 0.33
        words.append({"text": w, "start_ms": round(t * 1000), "end_ms": round((t + dur) * 1000)})
        t += dur + (0.70 if re.search(r"[.!?]$", tok) else 0.06)
    if words and t > wav_dur_s > 0:
        scale = (wav_dur_s - 0.05) / t
        for w in words:
            w["start_ms"] = round(w["start_ms"] * scale)
            w["end_ms"] = max(w["start_ms"] + 60, round(w["end_ms"] * scale))
    out_json.write_text(json.dumps({"words": words}, indent=1))


def _script_words(heard, text):
    import difflib
    key = lambda t: re.sub(r"[^a-z0-9]", "", t.lower())
    tokens = []
    for t in text.split():
        if key(t):
            tokens.append(t)
        elif tokens and re.search(r"[.!?,;:]", t):
            tokens[-1] += re.sub(r"[^.!?,;:]", "", t)
    hk, tk = [key(w["text"]) for w in heard], [key(t) for t in tokens]
    sm = difflib.SequenceMatcher(None, hk, tk, autojunk=False)
    if not tokens or not heard or sm.ratio() < 0.6:
        return heard
    out = []
    for op, h0, h1, t0, t1 in sm.get_opcodes():
        if op == "equal":
            out += [{"text": tokens[t0 + k], "start_ms": heard[h0 + k]["start_ms"],
                     "end_ms": heard[h0 + k]["end_ms"]} for k in range(t1 - t0)]
            continue
        if t1 == t0:
            continue
        if h1 > h0:
            start, end = heard[h0]["start_ms"], heard[h1 - 1]["end_ms"]
        else:
            start = out[-1]["end_ms"] if out else heard[0]["start_ms"]
            end = heard[h0]["start_ms"] if h0 < len(heard) else start
            end = max(end, start)
        weights = [max(1, len(tk[k])) for k in range(t0, t1)]
        at = float(start)
        for k, wgt in zip(range(t0, t1), weights):
            nxt = at + (end - start) * wgt / sum(weights)
            out.append({"text": tokens[k], "start_ms": round(at), "end_ms": max(round(at) + 1, round(nxt))})
            at = nxt
    return out


def _wav_dur_s(p):
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", str(p)],
                           capture_output=True, text=True, check=True)
    return float(probe.stdout.strip() or 1.0)


def make_voice(args, fixture_dir):
    out_wav, out_mp3, out_ali = fixture_dir / "voice.wav", fixture_dir / "voice.mp3", fixture_dir / "alignment.json"
    if args.voice_file:
        src = Path(args.voice_file)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), str(out_wav)], check=True)
        norm = fixture_dir / "voice_norm.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(out_wav),
                        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", str(norm)], check=True)
        out_wav = norm
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(out_wav), "-b:a", "160k", str(out_mp3)], check=True)
        log(f"aligning uploaded voice {src.name} ...")
        try:
            align(out_wav, out_ali)
        except Exception as e:
            log(f"whisper alignment unavailable ({e}) — using even word schedule")
            _fake_align(_wav_dur_s(out_wav), "", out_ali)
    else:
        text = args.script or (Path(args.script_file).read_text() if args.script_file else "")
        if not text.strip() and getattr(args, "brief", None):
            # brief -> authored narration via the local/key-gated writer
            from write_script import author_script
            data = author_script(args.brief, seconds=int(args.duration or 35))
            text = data.get("script", "").strip()
            log(f"authored script: {data.get('title', args.brief)} ({len(text.split())} words)")
        if not text.strip():
            sys.exit("need --script/--script-file/--brief or --voice-file")
        from write_script import normalize_tickers, plain_narration
        text = normalize_tickers(plain_narration(text))  # 'SOL' -> 'Solana' for TTS+captions
        if not text:
            sys.exit("need --script/--script-file/--brief or --voice-file")
        try:
            dur = synth(text.strip(), args.voice, out_wav, speed=float(args.speed or 1.0))
        except Exception as exc:
            log(f"voice synth failed ({exc}); falling back to espeak")
            dur = _espeak_synth(text.strip(), out_wav, speed=float(args.speed or 1.0))
        norm = fixture_dir / "voice_norm.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(out_wav),
                        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", str(norm)], check=True)
        out_wav = norm
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(out_wav), "-b:a", "160k", str(out_mp3)], check=True)
        log(f"synthesized {dur:.1f}s of VO ({args.voice}), aligning ...")
        try:
            align(out_wav, out_ali)
            heard = json.loads(out_ali.read_text())["words"]
            out_ali.write_text(json.dumps({"words": _script_words(heard, text)}, indent=1))
        except Exception as e:
            log(f"whisper alignment unavailable ({e}) — using even word schedule")
            _fake_align(dur, text.strip(), out_ali)
    return json.loads(out_ali.read_text())["words"]


# ---------- auto-treatment ----------
MAX_UNITS_PER_BEAT = 5  # compiler contract: TOO_MANY_DISPLAY_UNITS refuses above this


def _unit_count(gwords):
    return len(display_units(gwords))


def chunk_beats(words, max_beats=9):
    pieces, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt_gap = words[i + 1]["start_ms"] - w["end_ms"] if i + 1 < len(words) else 9999
        if CLAUSE_END.search(w["text"]) or nxt_gap >= 650:
            pieces.append(cur); cur = []
    if cur:
        pieces.append(cur)
    # A single clause can outgrow the display cap on its own (a long run-on
    # chunks into >5 units) — cut it at its widest legal mid-clause boundary,
    # falling back to a word cut when there is no comma to break on.
    fine = []
    for p in pieces:
        while _unit_count(p) > MAX_UNITS_PER_BEAT and len(p) > 1:
            commas = [i for i, w in enumerate(p) if CLAUSE_MID.search(w["text"]) and i + 1 < len(p)]
            cut = next((i for i in reversed(commas) if _unit_count(p[:i + 1]) <= MAX_UNITS_PER_BEAT), None)
            if cut is None:
                cut = min(10, len(p) - 1)
            fine.append(p[:cut + 1])
            p = p[cut + 1:]
        fine.append(p)
    # Merge fragments into beats under the cap: the contract is hard, the
    # beat-count target is only pacing.
    beats, cur = [], []
    for p in fine:
        if cur and _unit_count(cur + p) > MAX_UNITS_PER_BEAT:
            beats.append(cur); cur = []
        cur.extend(p)
    if cur:
        beats.append(cur)
    while len(beats) > max_beats:
        i = min(range(len(beats) - 1), key=lambda i: len(beats[i]) + len(beats[i + 1]))
        if _unit_count(beats[i] + beats[i + 1]) > MAX_UNITS_PER_BEAT:
            break
        beats[i:i + 2] = [beats[i] + beats[i + 1]]
    return beats


def clean(t):
    return t.strip()


def chunked_split(clauses):
    # asymmetric split for long clauses: support bboxes are narrow (≤~4 words
    # fit above the type floor), hero bboxes hold ~8. A 14-word clause becomes
    # [setup 3w] + [hero ≤8w] + [qualifier chunks ≤4w] instead of one hero
    # that breaches the legibility floor. Returns (piece, source_clause_index)
    # pairs so units can trace back to their clause's spoken start.
    chunked = []
    for ci, c in enumerate(clauses):
        ws = c.split()
        if len(ws) > 11:
            chunked.append((" ".join(ws[:3]), ci))
            ws = ws[3:]
            chunked.append((" ".join(ws[:8]), ci))
            ws = ws[8:]
            while ws:
                chunked.append((" ".join(ws[:4]), ci))
                ws = ws[4:]
        else:
            chunked.append((c, ci))
    return chunked


def _key_fragment(clause, entity_words):
    """Punchy keyword phrase for kinetic captions: the clause's longest run of
    content words (capped at 4), preferring runs that carry a matched entity —
    'Ethereum added, smart contracts that run themselves' → 'smart contracts'."""
    ws = [w.strip() for w in clause.split() if w.strip()]
    spans, cur = [], []
    for w in ws:
        if word_key(w) in STOPWORDS or len(word_key(w)) < 2:
            if cur:
                spans.append(cur); cur = []
        else:
            cur.append(w)
    if cur:
        spans.append(cur)
    if not spans:
        return " ".join(ws[:4])
    def hit(span):
        return any(word_key(w) in entity_words for w in span)
    spans.sort(key=lambda s: (hit(s), len(s)), reverse=True)
    frag = " ".join(spans[0][:4]).strip(" ,.;:!?")
    return frag or " ".join(ws[:4])


def display_units(gwords, entity_words=None):
    # kinetic keyword captions: every clause shows its key fragment in hero
    # weight — the kinetic type IS the caption, no small verbatim lines
    text = clean(" ".join(w["text"] for w in gwords))
    entity_words = entity_words or set()
    clauses, cstarts, buf = [], [], []
    for wi, w in enumerate(gwords):
        if not buf:
            cstarts.append(wi)
        buf.append(w["text"])
        if CLAUSE_MID.search(w["text"]):
            clauses.append(" ".join(buf)); buf = []
    if buf:
        clauses.append(" ".join(buf))
    pairs = [(c.strip(), s) for c, s in zip(clauses, cstarts) if c.strip()]
    clauses = [c for c, _ in pairs]
    beat_end = gwords[-1]["end_ms"]
    HOLD_MIN_MS = 500  # conservative: compiler floors observed at 100-200ms
    while len(clauses) > 1 and beat_end - gwords[pairs[-1][1]]["start_ms"] < HOLD_MIN_MS:
        clauses[-2] = clauses[-2] + " " + clauses[-1]
        clauses.pop()
        pairs.pop()
    chunked = chunked_split(clauses)
    units, seen = [], set()
    for i, (c, ci) in enumerate(chunked):
        frag = _key_fragment(c, entity_words)
        if not frag:
            continue
        # same key fragment twice reads as a typo, not emphasis — fall back to
        # the full clause tail so the second occurrence still says something
        if word_key(frag) in seen:
            tail = [w for w in c.split() if word_key(w) not in STOPWORDS]
            frag = " ".join(tail[-4:] if tail else c.split()[:4]).strip(" ,.;:!?")
        seen.add(word_key(frag))
        units.append({"text": frag, "role": "hero",
                      "anchor_word": frag.split()[0],
                      "emphasis": 0.9,
                      "semantic_role": "punch" if i == len(chunked) - 1 else "statement",
                      "_clause": ci})
    # A unit anchored on a word inside the beat's readable-close runway lands
    # too late to be read before the beat exits — re-anchor it to the first
    # word of its clause so the keyword arrives as the clause is spoken.
    RUNWAY_MS = 700
    for u in units:
        ci = u.pop("_clause")
        akey = word_key(u["anchor_word"])
        cstart = pairs[ci][1]
        aidx = next((k for k in range(cstart, len(gwords)) if word_key(gwords[k]["text"]) == akey), None)
        if aidx is not None and gwords[aidx]["start_ms"] > beat_end - RUNWAY_MS:
            u["anchor_word"] = gwords[cstart]["text"].strip(" ,.;:!?")
    # The contract caps a beat at three hero units — extra clauses keep their
    # words but step down to support weight.
    for u in units[2:-1]:
        u["role"] = "support"; u["emphasis"] = 0.55
    if not units:
        units.append({"text": text, "role": "hero", "anchor_word": text.split()[0],
                      "emphasis": 0.9, "semantic_role": "statement"})
    return units


def word_key(t):
    t = re.sub(r"[^a-z0-9'-]", "", t.lower())
    return t


def _norm_phrase(s):
    return " ".join(word_key(w) for w in s.split() if word_key(w))


# alias / multi-word surface form -> canonical bank key, normalized like toks
PHRASES = {_norm_phrase(k): v for k, v in _PHRASES_RAW.items()}
MAX_PHRASE_WORDS = max((len(p.split()) for p in PHRASES), default=1)

# a word that is itself a bank key is never a stopword — the function-word
# list must not block real vocabulary
STOPWORDS -= set(BANK)

# semantic fallback: nearest bank concept for words exact matching misses.
# Disabled automatically when transformers/torch or the model is unavailable.
try:
    from semantic_entities import init as _sem_init, lookup as _sem_lookup, embed_texts as _sem_embed
    _SEMANTIC = _sem_init(BANK, PHRASES)
except Exception:
    _sem_lookup, _sem_embed, _SEMANTIC = None, None, False

# neutral markers for beats whose narration names no drawable thing — every
# beat gets an entity (compiler requires >=1), and these read as discourse
# markers rather than a wrong metaphor. Question beats prefer 'question'.
FALLBACK_ENTITIES = [
    {"key": "question", "colour": "icon.icon-park-color.help",
     "mono": "icon.lucide.message-circle-question-mark",
     "emoji": "emoji.noto.red-question-mark", "photo": "question mark"},
    {"key": "point", "colour": "icon.icon-park-color.comment",
     "mono": "icon.mingcute.comment-line",
     "emoji": "emoji.noto.speech-balloon", "photo": "speech bubble"},
    {"key": "idea", "colour": "icon.icon-park-color.lightning",
     "mono": "icon.lucide.lightbulb",
     "emoji": "emoji.noto.light-bulb", "photo": "light bulb"},
    {"key": "highlight", "colour": "icon.icon-park-color.star",
     "mono": "icon.ant-design.star-outlined",
     "emoji": "emoji.noto.star", "photo": "abstract"},
    {"key": "note", "colour": "icon.icon-park-color.bookmark",
     "mono": "icon.mingcute.bookmark-line",
     "emoji": "emoji.noto.sparkles", "photo": "abstract"},
]


def fallback_entity(family, n, question=False):
    spec = (FALLBACK_ENTITIES[0] if question
            else FALLBACK_ENTITIES[(n % (len(FALLBACK_ENTITIES) - 1)) + 1])
    ref = spec.get(family) or spec.get("photo")
    if not ref:
        return None
    ent = {"id": f"e1_{spec['key']}{n}", "kind": "object", "glyph": "TILE",
           "phrase": spec["key"], "bank_key": spec["key"]}
    if family == "photos" or ref == spec.get("photo"):
        ent["concept"] = ref
    else:
        ent["asset_ref"] = ref
    return ent


# exact-key vetoes: a word that is a bank key still loses when a co-occurring
# word proves the everyday sense ("river bank" is not a financial bank)
_POLYSEME_VETO = {
    "bank": {"river", "shore", "canal", "stream", "bankside"},
    "base": {"statue", "bottom", "foundation", "bases"},
}


def pick_entities(gwords, family, already, ctx=None, max_n=4):
    seen = set()
    out = []
    toks = [word_key(w["text"]) for w in gwords]
    tokset = set(toks)
    i = 0
    while i < len(toks):
        tk = toks[i]
        key = None
        span = 1
        # context first: longest multi-word phrase wins over single words
        for n in range(min(MAX_PHRASE_WORDS, len(toks) - i), 1, -1):
            phrase = " ".join(toks[i:i + n])
            if phrase in PHRASES and PHRASES[phrase] in BANK:
                key = PHRASES[phrase]
                span = n
                break
        if not key:
            cands = [tk, tk[:-1] if tk.endswith("s") else tk, tk.rstrip("s'’")]
            key = next((c for c in cands if c in BANK), None)
            if not key:
                # single-word alias (e.g. ticker symbols: btc, eth)
                hit = next((c for c in cands if PHRASES.get(c) in BANK), None)
                if hit:
                    key = PHRASES[hit]
            if not key and _SEMANTIC and tk not in STOPWORDS:
                # nearest concept for vocabulary the bank doesn't spell out
                key = _sem_lookup(tk, BANK, family, already, ctx)
                if not key and i + 1 < len(toks) and toks[i + 1] not in STOPWORDS:
                    two = _sem_lookup(toks[i] + " " + toks[i + 1], BANK, family, already, ctx)
                    if two:
                        key, span = two, 2
        if not key or key in already or (span == 1 and tk in STOPWORDS):
            i += 1
            continue
        if _POLYSEME_VETO.get(key, set()) & tokset:
            i += 1
            continue
        spec = BANK[key]
        ref = spec.get(family) or (spec.get("photo") if family == "photos" else None) or spec.get("colour")
        if not ref or ref in seen:
            i += 1
            continue
        seen.add(ref); already.add(key)
        is_photo = family == "photos" or (family == "colour_icons" and ref == spec.get("photo")) or ref == spec.get("photo")
        ent = {"id": f"e{len(out)+1}_{key}", "kind": "object", "glyph": "TILE",
               "phrase": " ".join(toks[i:i + span]), "bank_key": key}
        if ref == spec.get("photo"):
            ent["concept"] = ref
        else:
            ent["asset_ref"] = ref
        out.append((ent, gwords[i]["text"]))
        i += span
        if len(out) >= max_n:
            break
    return out


def _label_ok(label, units):
    # An inside label must be a bare noun of at most three words and may not
    # restate a display unit already set in type on the same beat.
    ws = label.lower().split()
    if not ws or len(ws) > 3 or ws[0] in ("the", "a", "an"):
        return False
    uws = [u["text"].lower().split() for u in units]
    for u in uws:
        if ws == u or (len(ws) >= 2 and any(u[i:i + len(ws)] == ws for i in range(len(u) - len(ws) + 1))):
            return False
    return True


_NUMWORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
             "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
             "twelve": 12, "dozen": 12, "twenty": 20, "hundred": 100, "thousand": 1000,
             "million": 1_000_000, "billion": 1_000_000_000}


def dataviz_illustration(narration, g):
    """The data-viz look: a spoken number stages itself as a counter that counts
    up on its word, with a level bar growing under it (the frozen r5 layout).
    Digits and number words both qualify; no number → no staging."""
    toks = narration.split()
    value, vpos, unit = None, -1, ""
    for i, t in enumerate(toks):
        m = re.fullmatch(r"(\d[\d,]*(?:\.\d+)?)(%|percent|x)?", t.strip(",.;:!?"))
        if m:
            try:
                value = float(m.group(1).replace(",", ""))
                vpos, unit = i, m.group(2) or ""
                break
            except ValueError:
                continue
        w = t.strip(",.;:!?").lower()
        if w in _NUMWORDS and _NUMWORDS[w] >= 3:
            value, vpos = float(_NUMWORDS[w]), i
            break
    if value is None:
        return None
    caption = " ".join(toks[vpos + 1:vpos + 4]) or " ".join(toks[max(0, vpos - 2):vpos]) or "total"
    caption = re.sub(r"[^\w '&/-]", "", caption).strip() or "total"
    anchor = g[min(vpos, len(g) - 1)]["text"] if g else "one"
    last_word = g[-1]["text"] if g else anchor
    count = int(value) if value == int(value) else value
    level = min(0.98, count / 100.0) if unit in ("%", "percent") else min(0.95, max(0.18, count / 60.0))
    return {"form": "DATA_VISUAL",
            "entities": [
                {"id": "e1_counter", "kind": "object", "glyph": "COUNTER", "size": "hero",
                 "params": {"count": count, "caption": caption, "tone": "dark"}},
                {"id": "e2_bar", "kind": "evidence", "glyph": "BAR", "size": "support",
                 "params": {"level": round(level, 2), "caption": "trend"}}],
            "relations": [],
            "program": [
                {"op": "DRAW", "target": "e1_counter", "at": {"word": anchor}, "duration_ms": 600},
                {"op": "COUNT", "target": "e1_counter", "at": {"word": anchor},
                 "duration_ms": 900, "params": {"count": count}},
                {"op": "GROW", "target": "e2_bar", "at": {"word": last_word}, "duration_ms": 700}]}


def build_treatment(args, style, words, media_files, film_id):
    # Style knobs beyond the six visual families: which housing the entity icons
    # wear (TILE/BADGE/CHIP...) and how their connectors draw (solid/dash/arc).
    glyph = style.get("glyph", "TILE")
    link_style = style.get("link_style")
    groups = chunk_beats(words)
    if style.get("show") == "NEWSREEL":
        media_library = []
        for mi, p in enumerate(media_files):
            p = Path(p)
            kind = "VIDEO" if p.suffix.lower() in VIDEO_EXTS else "IMAGE"
            entry = {"asset_id": f"media{mi+1}", "kind": kind, "path": f"media/{p.name}"}
            wh = probe_dims(p, kind)
            if wh:
                entry["width"], entry["height"] = wh
                if kind == "VIDEO":
                    entry["duration_s"] = probe_dur(p)
            media_library.append(entry)
        return _newscast_treatment(args, style, words, groups, media_library, film_id)
    beats, used_kw, fallback_n, prev_keys = [], set(), 0, set()
    carry_id = carry_key = None
    fam = style["asset_family"]
    fam_key = {"colour_icons": "colour", "mono_icons": "mono", "emoji": "emoji", "photos": "photo"}[fam]
    # film-level topic vector: semantic matches rerank toward keys aligned
    # with what the narration is actually about
    ctx = None
    if _SEMANTIC:
        _ev = _sem_embed(" ".join(w["text"] for w in words))
        if _ev is not None:
            ctx = _ev[0]
    # Pre-pass: the film's ordered topic pool — every bank key any beat will
    # introduce, first-seen order. Float beats draw ambient members from it so
    # sparse narration still fills a cluster.
    film_keys: list = []
    if style.get("finish") == "FLOAT_FIELD":
        seen_k = set()
        for g in groups:
            for ent, _a in pick_entities(g, fam_key, set(), ctx, max_n=6):
                k = ent.get("bank_key")
                if k and k not in seen_k:
                    seen_k.add(k)
                    film_keys.append(k)
    media_iter = iter(enumerate(media_files))
    media_slots = {}
    for mi, mf in media_iter:
        slot = 1 + (mi % max(1, len(groups) - 2)) if len(groups) > 2 else mi % len(groups)
        media_slots.setdefault(slot, []).append((mi, mf))
    n = len(groups)
    for bi, g in enumerate(groups):
        bid = f"b{bi+1:02d}"
        narration = clean(" ".join(w["text"] for w in g))
        # Float scenes lead with visuals — a beat gets a denser cluster (up to six
        # drawable concepts) so the field never reads as a lone text line. Topic
        # keys may re-enter after one beat off (the film keeps returning to its
        # subject); only the previous beat's set is banned, so clusters evolve
        # instead of repeating identically.
        is_float = style.get("finish") == "FLOAT_FIELD"
        is_journey = bool(style.get("journey"))
        is_collage = bool(style.get("collage"))
        is_dataviz = bool(style.get("dataviz"))
        # Look tuning: journey keeps a leaner field so the carried hero reads as
        # the thing travelling; collage packs the field dense like a media board.
        max_picked = 4 if is_journey else 6
        fill_to = 3 if is_journey else (6 if is_collage else 4)
        picked = pick_entities(g, fam_key, prev_keys if is_float else used_kw, ctx,
                               max_n=max_picked if is_float else 4)
        beat_keys = {ent.get("bank_key") for ent, _a in picked if ent.get("bank_key")}
        if not picked:
            fe = fallback_entity(fam_key, fallback_n, question="?" in narration)
            if fe:
                picked = [(fe, g[0]["text"])]
                fallback_n += 1
        if is_float and len(picked) < fill_to:
            # Sparse narration still leads with visuals: the field fills to the
            # look's target with rotating ambient members of the film's own topic
            # pool — keys the film already introduced, minus the previous beat's,
            # so the cluster keeps evolving instead of going minimal while the
            # voice runs.
            pool = [k for k in film_keys if k not in prev_keys and k not in beat_keys]
            for k in pool[(bi * 2) % len(pool):] + pool[:(bi * 2) % len(pool)] if pool else []:
                if len(picked) >= fill_to:
                    break
                spec = BANK[k]
                ref = spec.get(fam_key) or spec.get("colour")
                if not ref:
                    continue
                ent = {"id": f"e{len(picked)+1}_{k}", "kind": "object", "glyph": "TILE",
                       "phrase": k, "bank_key": k}
                if ref == spec.get("photo"):
                    ent["concept"] = ref
                else:
                    ent["asset_ref"] = ref
                picked.append((ent, g[min(len(g) - 1, 2 + len(picked))]["text"]))
                beat_keys.add(k)
        film_keys = [k for k in film_keys if k not in beat_keys] + [k for k in film_keys if k in beat_keys]
        prev_keys = beat_keys
        # Momentum handoff: the previous beat's hub entity id carries into this
        # beat — if the same concept was picked it keeps its id, otherwise it
        # rides in as an ambient member, so something always travels into the
        # new field instead of the scene dissolving.
        carry = None
        if is_float and carry_id and bi > 0:
            # The carried concept keeps its id across beats — if this beat picked
            # it naturally, rename it onto the carry id; else it rides in as an
            # ambient member, so something always travels into the new field.
            same = next((ent for ent, _a in picked
                         if ent.get("bank_key") == carry_key), None)
            if same is not None:
                same["id"] = carry_id
            else:
                spec = BANK.get(carry_key or "", {})
                ref = spec.get(fam_key) or spec.get("colour")
                if ref:
                    ent = {"id": carry_id, "kind": "object", "glyph": "TILE",
                           "phrase": carry_key, "bank_key": carry_key}
                    if ref == spec.get("photo"):
                        ent["concept"] = ref
                    else:
                        ent["asset_ref"] = ref
                    picked.append((ent, g[0]["text"]))
                else:
                    carry_id = None
            if carry_id:
                carry = {"from_beat": f"b{bi:02d}", "entities": [carry_id]}
        ents = []
        for ent, anchor in picked:
            ents.append([ent, anchor])
        if is_journey and carry_id:
            # Journey staging: the carried object leads the field — it is the
            # thing travelling through the film, so it takes the hero slot.
            ents.sort(key=lambda ea: 0 if ea[0].get("id") == carry_id else 1)
        medias = media_slots.get(bi, [])
        for mi, mf in medias:
            ents.insert(0, ([{"id": f"media{mi+1}", "kind": "evidence", "glyph": "MEDIA",
                              "media_ref": f"media{mi+1}"}, g[0]["text"]]))
        sizes = ["hero", "support", "minor", "support", "minor", "support", "minor"]
        ent_words = set()
        for ent, _a in ents:
            for w in (ent.get("phrase") or "").split():
                k = word_key(w)
                if k:
                    ent_words.add(k)
        units = display_units(g, ent_words)
        entities, program = [], []
        hub_done = False
        for ei, (ent, anchor) in enumerate(ents):
            if is_float and ent["glyph"] == "TILE":
                # Float grammar (reference format): the first icon entity is the
                # hub, brand marks wear the glossy white disc, and every
                # other concept becomes the dark UI bar with its name inside.
                ref = ent.get("asset_ref") or ""
                if not hub_done:
                    # A white disc like the rest — a dark hero disc reads as a
                    # distracting void, not the format's hub.
                    ent["glyph"] = "BADGE"
                    hub_done = True
                elif ref.startswith("brand.") or ei % 2 == 0:
                    # Brand marks always keep the glossy disc; other concepts
                    # alternate — a white icon disc or the dark bar that carries
                    # its name inside, the mix the reference format uses.
                    ent["glyph"] = "BADGE"
                else:
                    ent["glyph"] = "CHIP"
                    lbl = (ent.get("bank_key") or "").replace("-", " ")
                    if lbl and _label_ok(lbl, units):
                        ent["label"] = lbl
            elif ent["glyph"] == "TILE":
                ent["glyph"] = glyph
            ent["size"] = sizes[min(ei, len(sizes) - 1)]
            entities.append(ent)
            if ent["id"] == carry_id and carry:
                # A carried body is already drawn — re-drawing it would flash;
                # it only travels to its new box.
                continue
            program.append({"op": "DRAW", "target": ent["id"], "at": {"word": anchor},
                            "duration_ms": 550})
        hub_id = next((e["id"] for e in entities if e.get("kind") != "evidence"),
                      entities[0]["id"]) if entities else None
        if is_float:
            # The chain continues: this beat's hub id is what the next beat
            # carries forward.
            carry_hub = next((e for e in entities if e.get("kind") != "evidence"), None)
            if carry_hub is not None:
                carry_id = carry_hub["id"]
                carry_key = carry_hub.get("bank_key")
        for ei in range(1, len(entities)):
            tgt = (f"{hub_id}->{entities[ei]['id']}" if is_float
                   else f"{entities[ei-1]['id']}->{entities[ei]['id']}")
            program.append({"op": "CONNECT",
                            "target": tgt,
                            "at": {"word": ents[ei][1]}, "duration_ms": 560})
        if is_float and entities:
            # Controlled masterclass: every float beat keeps animating after the
            # cluster assembles. Two flourishes rotate through the op vocabulary
            # per beat (icon writes itself in accent, accent fill rises, the hub
            # emits a ring, a state flip pops) so consecutive scenes never
            # choreograph the same way. Anchors ride mid/late narration words —
            # motion stays tied to the voice.
            flourishes = ["INK", "FILL", "EMIT", "SWAP"]
            f1 = flourishes[bi % len(flourishes)]
            f2 = flourishes[(bi + 2) % len(flourishes)]
            mid_word = g[len(g) // 2]["text"]
            last_word = g[-1]["text"]
            program.append({"op": f1, "target": hub_id,
                            "at": {"word": mid_word}, "duration_ms": 440})
            sats = [e["id"] for e in entities if e["id"] != hub_id]
            if sats:
                program.append({"op": f2, "target": sats[bi % len(sats)],
                                "at": {"word": last_word}, "duration_ms": 480})
        if is_float:
            relations = [{"type": "connects", "source": hub_id,
                          "target": e["id"], "style": "stem"}
                         for e in entities
                         if e["id"] != hub_id and e.get("kind") != "evidence"]
        else:
            relations = [{"type": "connects",
                          "source": entities[i - 1]["id"],
                          "target": entities[i]["id"],
                          **({"style": link_style} if link_style else {})}
                         for i in range(1, len(entities))]
        if len(program) > 10:
            # The contract caps a beat's program at ten authored ops — keep the
            # cluster's entrances, then its stems, then flourishes if room is left.
            order = {"DRAW": 0, "CONNECT": 1}
            program = sorted(program, key=lambda o: order.get(o["op"], 2))[:10]
        btype = "SETUP" if bi == 0 else ("PAYOFF" if bi == n - 1 else "EXPLANATION")
        illustration = {"form": "OBJECT_STAGE", "entities": entities,
                        "relations": relations,
                        "program": program,
                        **({"carry": carry} if carry else {})}
        if is_dataviz:
            # A spoken number gets the data-viz staging: the figure counts itself
            # up while its caption names what it measures, a level bar grows under.
            dv = dataviz_illustration(narration, g)
            if dv:
                illustration = dv
        beats.append({
            "beat_id": bid,
            "beat_type": btype,
            "pattern": "PAYOFF_LOCKUP" if bi == n - 1 else "PROGRESSIVE_HERO_BUILD",
            "dominant_layer": "TEXT" if style.get("reveal") == "BLOCK" else "HYBRID",
            "narration": narration,
            "energy": 0.55 if bi == 0 else (0.75 if bi == n - 1 else 0.65),
            "complexity": 0.5,
            "display_units": units,
            "illustration": illustration,
        })
    media_library = []
    for mi, p in enumerate(media_files):
        p = Path(p)
        kind = "VIDEO" if p.suffix.lower() in VIDEO_EXTS else "IMAGE"
        entry = {"asset_id": f"media{mi+1}", "kind": kind, "path": f"media/{p.name}"}
        wh = probe_dims(p, kind)
        if wh:
            entry["width"], entry["height"] = wh
            if kind == "VIDEO":
                entry["duration_s"] = probe_dur(p)
        media_library.append(entry)
    return {
        "schema": "NexStudioEditorialTreatmentV2",
        "film_id": film_id,
        "note": f"auto-authored by make_reel.py (style={style['id']})",
        "aspects": args.aspects.split(","),
        "fps": 30,
        "brand": {**style["palette"], "finish": style["finish"]},
        "typography": {"reveal": style["reveal"], "tonal_ink": 0.42, "min_visual_share": 0.6},
        "voice": {"source": "MASTER", "audio_path": "voice.mp3",
                  "alignment_path": "alignment.json", "head_pad_ms": 350},
        "media_library": media_library,
        "beats": beats,
        **({"mood": style["mood"]} if style.get("mood") else {}),
        **({"sfx": style["sfx"]} if style.get("sfx") else {}),
    }


# ---------------- newscast: the numbered-section data-news reel ----------------

_NUM_RE = re.compile(r"(\d[\d,.]*\s*(?:(?:%|percent|x|k|m|b|bn|gb|tb|ms|s)\b)?)|([\$\u20ac\u00a3]\s?\d[\d,.]*)", re.I)
_VS_RE = re.compile(r"\b(vs\.?|versus|head to head|against|compared to|compared with)\b", re.I)
_PRICE_RE = re.compile(r"[\$€£]|\b(dollars?|euros?|pounds?|cents?|price[sd]?|costs?|pricing|fee|fees|usd|msrp)\b", re.I)
_NC_STOP = {"a", "an", "the", "and", "or", "but", "of", "to", "in", "on", "for", "with", "at", "by", "is", "it", "its", "this", "that", "these", "those", "be", "are", "was", "were", "as", "if", "then", "than", "so", "no", "not", "your", "you", "we", "our", "their", "they", "he", "she", "i", "s",
            "against", "versus", "vs", "head", "about", "into", "onto", "upon", "toward", "towards", "via", "per", "between", "during", "through", "throughout", "over", "under", "around", "across", "along", "amid", "among", "within", "without", "beyond", "behind", "beside", "inside", "outside", "off", "out", "away", "back", "ahead", "down", "up", "here", "there", "where", "when", "why", "how", "what", "who", "whom", "whose", "which", "anyone", "everyone", "someone", "anything", "everything", "something", "much", "many", "more", "most", "very", "just", "even", "still", "really", "actually", "basically", "way", "thing", "things", "stuff", "lot", "kind", "sort", "part", "new", "old", "own", "same", "other", "another", "such", "like", "yeah", "uh", "um", "gonna", "well", "now", "then", "also", "too"}
_SEQ_RE = re.compile(r"\b(first|then|next|finally|steps?|stages?|phases?|process|pipeline|setup|install|unbox|assembly|how to)\b", re.I)
_DATE_RE = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*\d{0,2}|\b(19|20)\d{2}\b(?!\s*(?:watts?|hours?|percent|%|x|kb?|mb|gb|tb|ms|s|wh|kwh|volts?|hz|fps|bits?|bytes?|px|mm|cm|kg|lbs?)\b)|\bmonday|tuesday|wednesday|thursday|friday|saturday|sunday\b", re.I)
_GENERIC_SECTIONS = ["SETUP", "DETAILS", "NUMBERS", "COMPARE", "ROLE", "PROOF", "VERDICT"]


def _nc_section(g, picked, used_names, bi, last):
    """Name a beat's section from its own content first, the bank key second, and a
    rotating generic last. Names dedupe against sections already used — adjacent
    repeats are fine but a section word should never re-surface non-adjacently."""
    text = " ".join(w["text"] for w in g).upper()
    if bi == 0:
        cand = "THE DROP"
    elif last:
        cand = "VERDICT"
    elif _VS_RE.search(text):
        cand = "HEAD TO HEAD"
    elif _PRICE_RE.search(text):
        cand = "PRICE"
    elif _DATE_RE.search(text):
        cand = "TIMELINE"
    elif _NUM_RE.search(text):
        cand = "THE NUMBERS"
    elif _SEQ_RE.search(text):
        cand = "HOW IT WORKS"
    else:
        cand = None
    cands = [c for c in [cand] if c]
    cands += [((ent.get("bank_key") or "").replace("-", " ").upper())[:14] for ent, _a in picked]
    cands += _GENERIC_SECTIONS[bi % len(_GENERIC_SECTIONS):] + _GENERIC_SECTIONS[:bi % len(_GENERIC_SECTIONS)]
    for c in cands:
        c = re.sub(r"[^A-Z0-9+&%$ ]", "", c).strip()[:14]
        if c and c not in used_names:
            used_names.add(c)
            return c
    return f"PART {bi + 1}"


def _nc_numbers(g):
    """Numbers with a short label carved from the words just before them."""
    out = []
    words = [w["text"] for w in g]
    joined = " ".join(words)
    for m in _NUM_RE.finditer(joined):
        raw = m.group(0).strip()
        if re.search(r"(st|nd|rd|th)\b", raw, re.I) or re.match(r"\s*(st|nd|rd|th)\b", joined[m.end():], re.I):
            continue  # ordinals are dates and ranks, not data
        num_txt = raw.replace(",", "")
        mm = re.match(r"([\$\u20ac\u00a3]?)\s*(\d[\d.]*)\s*(%|percent|x|k|m|b|bn|gb|tb|ms|s)?\b", num_txt, re.I)
        if not mm:
            continue
        pre, digits, suf = mm.group(1) or "", mm.group(2), (mm.group(3) or "").lower()
        try:
            val = float(digits)
        except ValueError:
            continue
        mult = {"k": 1e3, "m": 1e6, "b": 1e9, "bn": 1e9}.get(suf, 1)
        # Label = the thing measured: up to 2 content words after the number
        # ('499 dollars' → 'dollars', '799 category average' → 'category average').
        label_words = []
        for w in joined[m.end():].split()[:4]:
            w2 = w.strip(" ,.;:!?")
            lw = w2.lower()
            if lw in ("a", "an", "the", "of", "at", "in", "on", "for", "to", "by", "and", "or", "is", "was",
                      "than", "under", "over", "out", "up", "full", "enough", "a", "it", "its", "with", "per"):
                if label_words:
                    break
                continue
            if lw.endswith("ing") or lw.endswith("ed") or not w2 or w2[0].isdigit():
                break
            label_words.append(w2)
            if len(label_words) >= 2:
                break
        label = " ".join(label_words) or "figure"
        if len(label) > 18:
            label = label_words[0] if label_words else label[:18]
        out.append({"label": label[:20], "value": val * mult, "pct": suf in ("%", "percent"),
                    "value_text": f"{pre}{digits}{('%' if suf in ('%', 'percent') else suf.upper())}"})
    # One axis one unit family: when plain measures and percents mix, the bars keep the measures.
    plain = [o for o in out if not o["pct"]]
    if len(plain) >= 2:
        out = plain
    for o in out:
        o.pop("pct", None)
    return out[:8]


def _nc_sides(text, subject=None):
    """Two contender names carved from a comparison sentence — the words either
    side of the pivot, or the phrases after each versus/against marker. Bare
    'than' sentences are verdicts, not matchups, so they never reach here."""
    m = re.search(r"\b(vs\.?|versus|against|compared to|compared with|head to head)\b", text, re.I)
    if not m:
        return None
    left = " ".join(text[:m.start()].split()[-3:]).strip(" ,.;:!?")
    left = re.sub(r"\b(head to head|stacked up|going up|face ?off)\b", "", left, flags=re.I).strip(" ,.;:!?")
    left = re.sub(r"^(it|he|she|they|we|this|that|these|those)\s+(is|are|was|were|has|have|gets?|feels?|runs?|comes?)\s+", "", left, flags=re.I).strip()
    left = re.sub(r"^(faster|slower|lighter|heavier|bigger|smaller|better|worse|cheaper|pricier|longer|shorter|stronger|weaker|brighter|darker|newer|older|cleaner|smarter|quicker|easier|harder)\b\s*", "", left, flags=re.I).strip()
    if not left:
        left = (subject or "OURS")
    right_m = re.search(r"\b(?:than|versus|vs\.?|against|over)\b\s+([^,.;:]+?)(?=\s+(?:than|versus|vs\.?|against|and|but|or|wins?|loses?|lost|ties?|leads?|beats?|trails?)\b|[,.;:]|$)", text, re.I)
    right = (right_m.group(1) if right_m else " ".join(text[m.end():].split()[:3])).strip(" ,.;:!?")
    right = re.sub(r"^(to|with)\s+", "", right, flags=re.I).strip()
    if subject:
        for sw_ in subject.split():
            right = re.sub(rf"\b{re.escape(sw_)}\b", "", right, flags=re.I).strip(" ,.;:!?")
    right = right or "THEIRS"
    return " ".join(left.split()[:4]), " ".join(right.split()[:4])


def _nc_segments(text):
    """Step/event labels split on sequence markers and punctuation."""
    parts = re.split(r",|;|\.|\bthen\b|\bnext\b|\bfinally\b|\bfirst\b", text, flags=re.I)
    out = []
    for p in parts:
        if ":" in p:
            p = p.split(":")[-1]
        p = p.strip(" ,.;:!?")
        if len(p) > 1:
            out.append(p)
    return out[:5]


def _nc_widget(bi, g, narration, picked, last, subject=None):
    """One hero widget entity per beat — the content decides which. Returns
    (entity, program_ops) or None for a plain hero-text beat."""
    text = narration
    nums = _nc_numbers(g)
    anchor = g[min(2, len(g) - 1)]["text"].strip(".,;:!?'\"-")
    # Reveal op lands on the first content word after the draw word — the
    # widget fills as soon as its clause opens, never after a dead pause.
    mid = next((w["text"].strip(".,;:!?'\"-") for w in g[3:] if w["text"].strip(".,;:!?-'").lower() not in _NC_STOP), g[min(4, len(g) - 1)]["text"].strip(".,;:!?'\"-"))
    end = g[-1]["text"].strip(".,;:!?'\"-")
    sides = _nc_sides(text, subject) if _VS_RE.search(text) else None
    if sides:
        left, right = sides
        return ({"id": "w1", "kind": "evidence", "glyph": "VS_CARDS", "size": "hero",
                 "params": {"cards": [{"title": left, "mark": left}, {"title": right, "mark": right}]}},
                [{"op": "DRAW", "target": "w1", "at": {"word": anchor}, "duration_ms": 350},
                 {"op": "GROW", "target": "w1", "at": {"word": mid}, "duration_ms": 720}])
    if len(nums) >= 2:
        series = [{"label": n2["label"], "value": n2["value"], "value_text": n2["value_text"]} for n2 in nums]
        if series:
            series[0]["tone"] = "accent"
        return ({"id": "w1", "kind": "evidence", "glyph": "DATA_BARS", "size": "hero",
                 "params": {"series": series}},
                [{"op": "DRAW", "target": "w1", "at": {"word": anchor}, "duration_ms": 350},
                 {"op": "GROW", "target": "w1", "at": {"word": mid}, "duration_ms": 800}])
    if len(_DATE_RE.findall(text)) >= 2:
        evs = ([{"label": (ent.get("phrase") or ent.get("bank_key") or "step"), "sub": ""} for ent, _a in picked[:4]]
               if len(picked) >= 2 else
               [{"label": s2[:16], "sub": ""} for s2 in _nc_segments(text)][:5])
        if len(evs) >= 2:
            return ({"id": "w1", "kind": "evidence", "glyph": "TIMELINE", "size": "hero", "params": {"events": evs}},
                    [{"op": "DRAW", "target": "w1", "at": {"word": anchor}, "duration_ms": 350},
                     {"op": "GROW", "target": "w1", "at": {"word": mid}, "duration_ms": 700}])
    segs = _nc_segments(text)
    if _SEQ_RE.search(text) or len(segs) >= 3:
        drop = {"", "one", "two", "three", "four", "five", "no", "a", "an", "the", "it", "its"}
        def _step(s):
            s = re.sub(r"^.*\b(?:steps?|stages?|phases?|process|how to|setup|install|assembly|stack)\b\s+", "", str(s), flags=re.I).strip()
            s = re.sub(r"\s+(?:that|which|who|it|its|shows?|has|have|had|draw|runs?|uses?|eats?|makes?|keeps?|gives?|takes?|gets?|costs?|sells?|ships?|lasts?)\b.*$", "", s, flags=re.I).strip()
            for _ in range(3):
                s = re.sub(r"^(this|these|those|that|it|is|are|was|were|and|but|or|with|a|an|the)\s+", "", s, flags=re.I).strip()
                s = re.sub(r"\s+(to|of|for|with|and|or|the|a|an|per|on|in|at|by)$", "", s, flags=re.I).strip()
            return " ".join(s.split()[:3])
        seg_steps = [s2 for s2 in (_step(s2) for s2 in segs) if s2.lower() not in drop][:5]
        pick_steps = [s2 for s2 in (_step(ent.get("phrase") or ent.get("bank_key") or "") for ent, _a in picked[:5])
                      if s2.lower() not in drop]
        if _SEQ_RE.search(text):
            steps = seg_steps if len(seg_steps) >= 2 else pick_steps
        else:
            steps = pick_steps if len(pick_steps) >= 2 else seg_steps
        if len(steps) >= 2:
            return ({"id": "w1", "kind": "evidence", "glyph": "FLOW_STEPS", "size": "hero", "params": {"steps": steps}},
                    [{"op": "DRAW", "target": "w1", "at": {"word": anchor}, "duration_ms": 350},
                     {"op": "GROW", "target": "w1", "at": {"word": mid}, "duration_ms": 760}])
    if len(nums) == 1:
        n0 = nums[0]
        mm = re.match(r"([\$\u20ac\u00a3]?)\s*(\d[\d.]*)(.*)", n0["value_text"])
        pre, digits, suf = (mm.group(1) or ""), mm.group(2), (mm.group(3) or "") if mm else ("", n0["value_text"], "")
        return ({"id": "w1", "kind": "evidence", "glyph": "COUNTER", "size": "hero",
                 "params": {"count": round(n0["value"], 2), "prefix": pre, "suffix": suf, "caption": n0["label"],
                            "sep": len(digits) >= 5}},
                [{"op": "DRAW", "target": "w1", "at": {"word": anchor}, "duration_ms": 400},
                 {"op": "COUNT", "target": "w1", "at": {"word": mid}, "duration_ms": 900}])
    if len(picked) >= 3 and bi % 2 == 1:
        cells = [{"name": str(ent.get("phrase") or ent.get("bank_key") or "item"), "sub": "", "concept": ent.get("bank_key") or ""} for ent, _a in picked[:6]]
        return ({"id": "w1", "kind": "evidence", "glyph": "LOGO_GRID", "size": "hero", "params": {"cells": cells, "cols": 3 if len(cells) > 4 else 2}},
                [{"op": "DRAW", "target": "w1", "at": {"word": anchor}, "duration_ms": 350},
                 {"op": "GROW", "target": "w1", "at": {"word": mid}, "duration_ms": 700}])
    if len(picked) >= 2 and bi % 3 == 2:
        rows = [[str(ent.get("phrase") or ent.get("bank_key") or "item"), str(i + 1)] for i, (ent, _a) in enumerate(picked[:4])]
        return ({"id": "w1", "kind": "evidence", "glyph": "DATA_TABLE", "size": "hero",
                 "params": {"header": ["item", "rank"], "rows": rows, "highlight": 0}},
                [{"op": "DRAW", "target": "w1", "at": {"word": anchor}, "duration_ms": 350},
                 {"op": "GROW", "target": "w1", "at": {"word": mid}, "duration_ms": 700}])
    if bi == 0 or len(picked) < 2:
        return ({"id": "w1", "kind": "object", "glyph": "SQUIGGLE", "size": "minor",
                 "params": {"waves": 3}},
                [{"op": "DRAW", "target": "w1", "at": {"word": anchor}, "duration_ms": 620}])
    return None


def _nc_scrub_echo_labels(ent, units):
    """Entity labels must add information, not restate the on-screen type — the compiler
    fails ENTITY_LABEL_ECHO otherwise. A label that collides with a display-unit word
    is dropped; the value/readout still carries the datum."""
    echo = set()
    for u in units:
        for w in re.split(r"\s+", str(u.get("text") or "")):
            echo.add(word_key(w))
    echo.discard("")
    def scrub(s):
        return not s or any(word_key(w) in echo for w in str(s).split())
    p = ent.get("params") or {}
    # Series/row/cell/event/step labels carry the widget's content; contracts require
    # them non-empty and do not echo-check them. Only the entity's own label and a
    # free caption can restate on-screen type, and neither is set on show widgets.
    if ent.get("label") and scrub(ent["label"]):
        ent.pop("label")
    if p.get("caption") and scrub(p["caption"]):
        p.pop("caption")


def _newscast_treatment(args, style, words, groups, media_library, film_id):
    """Keyword-path authorer for the NEWSREEL show grammar: one hero widget per beat,
    a section name per beat, the rotating shade family, and the masthead subject."""
    fam = style["asset_family"]
    fam_key = {"colour_icons": "colour", "mono_icons": "mono", "emoji": "emoji", "photos": "photo"}[fam]
    ctx = None
    if _SEMANTIC:
        _ev = _sem_embed(" ".join(w["text"] for w in words))
        if _ev is not None:
            ctx = _ev[0]
    subject = (getattr(args, "subject", None) or "").strip() or _nc_subject(words)
    beats, used_kw, used_sections, fallback_n = [], set(), set(), 0
    n = len(groups)
    for bi, g in enumerate(groups):
        bid = f"b{bi + 1:02d}"
        narration = clean(" ".join(w["text"] for w in g))
        picked = pick_entities(g, fam_key, used_kw, ctx, max_n=5)
        if not picked:
            fe = fallback_entity(fam_key, fallback_n, question="?" in narration)
            if fe:
                picked = [(fe, g[0]["text"])]
                fallback_n += 1
        for ent, _a in picked:
            if ent.get("bank_key"):
                used_kw.add(ent["bank_key"])
        widget = _nc_widget(bi, g, narration, picked, bi == n - 1, subject)
        entities = []
        program = []
        if widget:
            ent, program = widget
            entities.append(ent)
        # Hero words up top, widget below — the show's reading order.
        units = display_units(g, set())
        for u in units[1:]:
            # The punch is the hero; the rest of the sentence keeps landing as
            # small kinetic words on their anchors — the frame never sits dead
            # while the voice is still going.
            u["role"] = "support"
        if entities:
            _nc_scrub_echo_labels(entities[0], units)
        btype = "HOOK" if bi == 0 else ("PAYOFF" if bi == n - 1 else "PROOF")
        gph = (entities[0]["glyph"] if entities else "") if widget else ""
        pattern = ("PAYOFF_LOCKUP" if bi == n - 1 else
                   {"VS_CARDS": "CONTRAST_RECONFIGURATION",
                    "FLOW_STEPS": "PROCESS_RAIL", "TIMELINE": "SEQUENTIAL_SUPPORT_LIST",
                    "DATA_BARS": "HERO_TO_EVIDENCE_HANDOFF", "DATA_TABLE": "HERO_TO_EVIDENCE_HANDOFF",
                    "COUNTER": "EVIDENCE_PERSISTENCE_CARRIER", "LOGO_GRID": "EVIDENCE_PERSISTENCE_CARRIER",
                    "PROGRESS": "EVIDENCE_PERSISTENCE_CARRIER", "MAGNIFY": "OBJECT_LED_TRANSITION"}.get(gph, "PROGRESSIVE_HERO_BUILD"))
        beats.append({
            "beat_id": bid,
            "beat_type": btype,
            "pattern": pattern,
            "dominant_layer": "HYBRID" if widget else "TEXT",
            "section": _nc_section(g, picked, used_sections, bi, bi == n - 1),
            "narration": narration,
            "energy": 0.6 if bi == 0 else (0.8 if bi == n - 1 else 0.7),
            "complexity": 0.45,
            "display_units": units,
            **({"illustration": {"form": "OBJECT_STAGE", "entities": entities, "program": program}} if widget else {}),
        })
    return {
        "schema": "NexStudioEditorialTreatmentV2",
        "film_id": film_id,
        "note": f"auto-authored by make_reel.py (style={style['id']}, show=NEWSREEL)",
        "aspects": args.aspects.split(","),
        "fps": 30,
        "brand": {**style["palette"], "finish": style["finish"]},
        "typography": {"reveal": style["reveal"], "tonal_ink": 0.42, "min_visual_share": 0.55},
        "voice": {"source": "MASTER", "audio_path": "voice.mp3", "alignment_path": "alignment.json", "head_pad_ms": 350},
        "media_library": media_library,
        "show": {"format": "NEWSREEL", "subject": subject.upper()[:32],
                 "shades": style.get("shades") or style["palette"]},
        "beats": beats,
        "mood": "driving",
        "sfx": "bold",
    }


def _nc_subject(words):
    """Masthead word: the first noun-ish capital content words of the film."""
    txt = " ".join(w["text"] for w in words[:14])
    names = [t for t in re.findall(r"[A-Za-z][A-Za-z0-9.+-]*", txt) if len(t) > 2 and word_key(t) not in STOPWORDS]
    return " ".join(names[:2]).upper() if names else "THE STORY"


def probe_dims(p, kind):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    try:
        w, h = r.stdout.strip().split(",")[:2]
        return int(w), int(h)
    except Exception:
        return None


def probe_dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    try:
        return round(float(r.stdout.strip()), 3)
    except Exception:
        return 0


# ---------- poster ----------
def posterize(frames_dir, src_mp4, out_mp4, w, h, tmp):
    last = sorted(Path(frames_dir).glob("f*.jpg"))[-1]
    seg, vout = tmp / f"seg_{h}_{uuid.uuid4().hex[:6]}.mp4", tmp / f"v_{h}_{uuid.uuid4().hex[:6]}.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", "30", "-t", "1.6",
                    "-i", str(last), "-vf", f"scale={w}:{h},format=yuv420p",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-an", str(seg)], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(seg), "-i", str(src_mp4),
                    "-filter_complex",
                    "[0:v]fps=30,settb=AVTB,format=yuv420p[p];[1:v]fps=30,settb=AVTB,format=yuv420p[o];"
                    "[p][o]xfade=transition=fade:duration=0.6:offset=1.0[v]",
                    "-map", "[v]", "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-pix_fmt", "yuv420p", "-an", str(vout)], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(vout), "-i", str(src_mp4),
                    "-filter_complex", "[1:a]adelay=1000|1000,apad=whole_dur=99[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(out_mp4)], check=True)
    seg.unlink(missing_ok=True); vout.unlink(missing_ok=True)


def remux_nocaption(frames_dir, audio_wav, out_mp4):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", "15",
                    "-i", str(Path(frames_dir) / "f%05d.jpg"), "-i", str(audio_wav),
                    "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out_mp4)], check=True)


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script"); ap.add_argument("--script-file"); ap.add_argument("--voice-file")
    ap.add_argument("--brief", help="topic/brief — authored into a script by tools/write_script.py")
    ap.add_argument("--voice", default="andrew", choices=sorted(VOICES))
    ap.add_argument("--style", default="photo_story")
    ap.add_argument("--media", nargs="*", default=[])
    ap.add_argument("--duration", type=float, default=0,
                    help="target narration seconds (guides --brief script authoring)")
    ap.add_argument("--speed", type=float, default=1.0,
                    help="narration speed multiplier (edge voices)")
    ap.add_argument("--aspects", default="16x9,1x1,9x16")
    ap.add_argument("--out", required=True)
    ap.add_argument("--film-id")
    ap.add_argument("--subject", default=None, help="masthead subject for show styles (e.g. 'ORBIT DESK')")
    ap.add_argument("--treatment", help="use an existing treatment.json instead of auto-authoring")
    ap.add_argument("--fixture-voice", help="fixture dir already containing voice.mp3+alignment.json (with --treatment)")
    ap.add_argument("--no-poster", action="store_true")
    args = ap.parse_args()

    style = style_of(args.style)
    film_id = args.film_id or f"reel-{uuid.uuid4().hex[:8]}"
    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)

    if args.treatment:
        treatment_src = Path(args.treatment)
        voice_dir = Path(args.fixture_voice) if args.fixture_voice else treatment_src.parent
        fixture_dir = voice_dir
        words = json.loads((fixture_dir / "alignment.json").read_text())["words"]
        if fixture_dir.parent.resolve() != (ROOT / "fixtures").resolve():
            dst = ROOT / "fixtures" / fixture_dir.name
            if not dst.exists():
                subprocess.run(["cp", "-r", str(fixture_dir), str(dst)], check=True)
                log(f"copied fixture → {dst}")
            fixture_dir = dst
    else:
        fixture_dir = ROOT / "fixtures" / film_id
        fixture_dir.mkdir(parents=True, exist_ok=True)
        log(f"fixture → {fixture_dir}")
        words = make_voice(args, fixture_dir)
        for mf in args.media:
            dst = fixture_dir / "media" / Path(mf).name
            dst.parent.mkdir(exist_ok=True)
            subprocess.run(["cp", str(mf), str(dst)], check=True)
        media = [fixture_dir / "media" / Path(mf).name for mf in args.media]
        treatment = build_treatment(args, style, words, media, film_id)
        (fixture_dir / "treatment.json").write_text(json.dumps(treatment, indent=1))
        treatment_src = fixture_dir / "treatment.json"

    log(f"rendering {args.aspects} @ {style['id']} ...")
    env = dict(os.environ)
    node_bin = Path.home() / ".nvm/versions/node/v24.19.0/bin"
    if node_bin.is_dir():
        env["PATH"] = str(node_bin) + os.pathsep + env.get("PATH", "")
    r = subprocess.run([sys.executable, str(TOOLS / "regression_pack.py"),
                        "--fixture", fixture_dir.name, "--aspects", args.aspects,
                        "--out", str(out_dir.resolve())],
                       env=env, capture_output=True, text=True)
    print(r.stdout[-2500:] or r.stderr[-2500:])
    if r.returncode != 0:
        sys.exit(f"render failed ({r.returncode})")

    stem = fixture_dir.name
    dims = {"16x9": (1920, 1080), "1x1": (1080, 1080), "9x16": (1080, 1920)}
    manifest = {"film_id": film_id, "style": style["id"], "outputs": {}}
    def package_format(a):
        rd = out_dir / stem
        web = rd / f"{stem}_{a}_web.mp4"
        frames = rd / f"frames_{a}"
        audio = rd / f"audio_{a}.wav"
        if style.get("captions") == "burned" and frames.exists():
            web_nc = rd / f"{stem}_{a}_nocaption_web.mp4"
            remux_nocaption(frames, audio, web_nc)
            web = web_nc
        if not args.no_poster:
            w, h = dims[a]
            poster = rd / f"{stem}_{a}_poster.mp4"
            posterize(frames, web, poster, w, h, out_dir)
            return str(poster)
        else:
            return str(web)
    manifest["outputs"] = render_aspects(
        [a.strip() for a in args.aspects.split(",") if a.strip()], package_format)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1))
    log("done:")
    for a, p in manifest["outputs"].items():
        log(f"  {a}: {p}")


if __name__ == "__main__":
    main()
