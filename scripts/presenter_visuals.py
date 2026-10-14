"""Sparse explainer visuals for presenter videos.

A card pops in beside the presenter only when the script names something the
explainer library can draw (a bike, a leaf, a wallet) or states a number with
a unit ("three thousand miles"). At most one card on screen, cards at least
MIN_GAP seconds apart, never on a word the caption already turned into an icon.
"""
import json, math, re, shutil, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ASSETS = Path(__file__).resolve().parents[1] / 'engine_sources/editorial-motion-v2/assets'
DRAWABLE = {'objects', 'food', 'nature', 'transport', 'tech', 'finance', 'time', 'health', 'audio', 'comms'}
MIN_GAP, HOLD, LEAD = 8.0, 3.2, 0.15
NUMBERS = {w: i for i, w in enumerate('zero one two three four five six seven eight nine ten eleven twelve'.split())}
NUMBERS.update({'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90})
SCALES = {'hundred': 100, 'thousand': 1000, 'million': 1000000, 'billion': 1000000000}
UNITS = {'minute': 'min', 'minutes': 'min', 'second': 'sec', 'seconds': 'sec', 'hour': 'hr', 'hours': 'hr',
         'percent': '%', 'mile': 'miles', 'miles': 'miles', 'kilometres': 'km', 'kilometers': 'km', 'km': 'km',
         'days': 'days', 'day': 'day', 'weeks': 'weeks', 'years': 'years', 'dollars': '$', 'degrees': '°'}


def norm(w):
    return re.sub(r"[^a-z0-9'%]+", '', w.lower())


TOPICS = {'crypto': r'\b(crypto|blockchain|token|tokens|onchain|wallet|defi|bitcoin|ethereum|solana)\b',
          'ai': r'\b(ai|agent|agents|model|models|llm|prompt|machine learning)\b'}


def library(text=''):
    """label -> svg path; curated explainer art first, then licence-clean community packs.
    Curated crypto/AI art (a 'chain' is a blockchain there) only joins when the script is about that topic."""
    bad = set(json.loads((ASSETS / 'community/preflight.json').read_text()).get('quarantined', {}))
    out = {}
    cur = json.loads((ASSETS / 'illustration/registry.json').read_text())['assets']
    for a in cur:
        topic = TOPICS.get(a['domain'])
        if topic and not re.search(topic, text.lower()):
            continue
        if a['family'] in ('icon', 'literal-prop') and a['id'] not in bad:
            out.setdefault(a['label'].lower(), ASSETS / 'illustration' / a['path'])
    com = json.loads((ASSETS / 'community/icons-registry.json').read_text())['assets']
    for a in com:
        if a['domain'] in DRAWABLE and a['id'] not in bad and ' ' not in a['label']:
            out.setdefault(a['label'].lower(), ASSETS / 'community' / a['path'])
    return out


def lemma_keys(w):
    w = norm(w)
    keys = [w]
    if w.endswith('ies'):
        keys.append(w[:-3] + 'y')
    if w.endswith('ves'):
        keys += [w[:-3] + 'f', w[:-3] + 'fe']
    if w.endswith('es'):
        keys.append(w[:-2])
    if w.endswith('s'):
        keys.append(w[:-1])
    return keys


def number_at(words, i):
    """(value, end index) when a spoken number starts at i."""
    total, cur, j = 0, None, i
    while j < len(words):
        t = norm(words[j]['word'])
        if t.replace(',', '').isdigit():
            cur = (cur or 0) + int(t.replace(',', ''))
        elif t in NUMBERS:
            cur = (cur or 0) + NUMBERS[t]
        elif t in SCALES and cur is not None:
            total += cur * SCALES[t]
            cur = 0
        else:
            break
        j += 1
    if cur is None and total == 0:
        return None
    return total + (cur or 0), j


def plan(words, skip_words, concrete=None, dur=None):
    """Timed cards [{'at', 'kind', 'label', 'svg'|None}], sparse by construction."""
    lib = library(' '.join(w['word'] for w in words))
    cands = []
    i = 0
    while i < len(words):
        num = number_at(words, i)
        if num and num[1] < len(words) and norm(words[num[1]]['word']) in UNITS:
            v, j = num
            unit = UNITS[norm(words[j]['word'])]
            label = f'{v:,}{unit}' if unit in ('%', '°') else (f'${v:,}' if unit == '$' else f'{v:,} {unit}')
            cands.append((words[i]['start'], 2, {'kind': 'stat', 'label': label, 'svg': None, 'span': (i, j)}))
            i = j + 1
            continue
        w = words[i]['word']
        if norm(w) not in skip_words and len(norm(w)) >= 3:
            key = next((k for k in lemma_keys(w) if k in lib), None)
            if key and (concrete is None or concrete(key)):
                cands.append((words[i]['start'], 1, {'kind': 'icon', 'label': key, 'svg': lib[key], 'span': (i, i)}))
        i += 1
    out, used, last = [], set(), -1e9
    end = dur if dur is not None else (words[-1]['end'] if words else 0)
    for t, _, c in sorted(cands, key=lambda c: (c[0], -c[1])):
        if t - last < MIN_GAP or c['label'] in used or t < 0.8 or t + HOLD > end + 0.5:
            continue
        out.append({**c, 'at': max(0.0, t - LEAD)})
        used.add(c['label'])
        last = t
    return out


def raster(svg, side, ink, cache):
    cache.mkdir(parents=True, exist_ok=True)
    png = cache / f'{svg.stem}-{side}.png'
    if not png.exists():
        src = cache / f'{svg.stem}.svg'
        src.write_text(svg.read_text().replace('currentColor', '#%02x%02x%02x' % ink))
        # inkscape lives on dev boxes but not the render image; the shipped
        # cairosvg (cairo+rsvg are installed) covers the same simple icon art.
        if shutil.which('inkscape'):
            subprocess.run(['inkscape', str(src), '--export-type=png', f'--export-width={side}', '-o', str(png)],
                           check=True, capture_output=True)
        else:
            import cairosvg
            cairosvg.svg2png(url=str(src), write_to=str(png), output_width=side)
    return Image.open(png).convert('RGBA')


def ease_back(p, s=1.6):
    p = max(0.0, min(1.0, p)) - 1
    return 1 + p * p * ((s + 1) * p + s)


def region(aspect, W, H, pres):
    """Card centre and size: beside the presenter, clear of captions and promos."""
    if aspect == '16:9':
        free = pres[0]
        return (int(free * 0.5), int(H * 0.36)), int(H * 0.30)
    if aspect == '1:1':
        return (int(W * 0.17), int(H * 0.24)), int(W * 0.22)
    return (int(W * 0.24), int(H * 0.14)), int(W * 0.30)


class Cards:
    def __init__(self, cards, aspect, W, H, pres, ktr, accent, cache):
        self.cards, self.ktr, self.accent = cards, ktr, accent
        self.centre, self.side = region(aspect, W, H, pres)
        ink = (24, 24, 26)
        for c in cards:
            c['img'] = raster(c['svg'], int(self.side * 0.62), ink, cache) if c['svg'] else None
        self.tiles = [self.tile(c) for c in cards]

    def tile(self, c):
        s = self.side
        im = Image.new('RGBA', (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, s - 1, s - 1), int(s * 0.16), fill=(252, 252, 250, 244))
        d.rounded_rectangle((0, s - max(6, s // 28), s - 1, s - 1), int(s * 0.02), fill=self.accent + (255,))
        if c['img'] is not None:
            g = c['img']
            g.thumbnail((int(s * 0.6), int(s * 0.52)), Image.LANCZOS)
            im.alpha_composite(g, ((s - g.width) // 2, int(s * 0.10) + (int(s * 0.52) - g.height) // 2))
            f = self.ktr._font('grotesk', True, max(14, int(s * 0.12)))
            txt, y = c['label'].capitalize(), int(s * 0.70)
            fill = (24, 24, 26, 255)
        else:
            size = int(s * 0.30)
            f = self.ktr._font('grotesk', True, size)
            while d.textlength(c['label'], font=f) > s * 0.84 and size > 14:
                size -= 2
                f = self.ktr._font('grotesk', True, size)
            txt, y, fill = c['label'], int((s - size) * 0.45), self.accent + (255,)
        d.text(((s - d.textlength(txt, font=f)) / 2, y), txt, font=f, fill=fill)
        return im

    def draw(self, frame, t):
        for c, tile in zip(self.cards, self.tiles):
            age = t - c['at']
            if not 0 <= age < HOLD + 0.35:
                continue
            k = ease_back(age / 0.38) if age < HOLD else 1.0
            a = 1.0 if age < HOLD else max(0.0, 1 - (age - HOLD) / 0.35)
            s = max(2, int(self.side * (0.6 + 0.4 * k) if age < HOLD else self.side * (1 - 0.08 * (1 - a))))
            im = tile.resize((s, s), Image.LANCZOS)
            al = im.getchannel('A').point(lambda v: int(v * min(1.0, a, age / 0.12)))
            im.putalpha(al)
            sh = Image.new('RGBA', (s + 40, s + 40), (0, 0, 0, 0))
            sh.paste(Image.new('RGBA', (s, s), (0, 0, 0, 255)), (20, 20), al.point(lambda v: int(v * 0.22)))
            sh = sh.filter(ImageFilter.GaussianBlur(10))
            x, y = self.centre[0] - s // 2, self.centre[1] - s // 2
            frame.alpha_composite(sh, (x - 18, y - 12))
            frame.alpha_composite(im, (x, y))
        return frame
