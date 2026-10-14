"""Compiler-side type fitting from real font metrics.

The kinetic typography authority hands out zones; this decides the exact
font size and line breaks that fill them using the shipped Inter / JetBrains
Mono advance widths. The renderer sets these values verbatim and measures the
result; disagreement beyond tolerance is a gate failure, never a silent shrink.
Wording is never altered — only where lines break.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

METRICS = json.loads((Path(__file__).resolve().parents[2] / 'assets' / 'fonts' / 'metrics.json').read_text())

WEIGHT_NUM = {'Regular': 400, 'Medium': 500, 'SemiBold': 600, 'Bold': 700, 'ExtraBold': 800, 'Black': 900}
TRACKING = {'hero': -0.032, 'support': -0.012, 'label': 0.06, 'data': -0.02}
LINE_HEIGHT = {'hero': 0.98, 'support': 1.22, 'label': 1.0, 'data': 0.94}
# Legibility floors as a fraction of the canvas short side (sound-off phone viewing).
FLOOR_FRACTION = {'hero': 0.046, 'support': 0.027, 'label': 0.024, 'data': 0.05}


def _face(role: str, weight: str, mono: bool = False) -> Dict:
    if mono:
        return METRICS['mono_600']
    w = WEIGHT_NUM.get(weight, 700)
    bucket = min((400, 600, 800, 900), key=lambda b: abs(b - w))
    return METRICS[f"inter_{'display' if role in ('hero', 'data') else 'text'}_{bucket}"]


# A stressed word is set this much larger than its line; the fit reserves the width so the
# runtime can size it for real instead of scaling it into the word space.
STRESS_SCALE = 1.045


def _token_key(token: str) -> str:
    return re.sub(r"[^a-z0-9%]", '', token.lower().replace('’', "'"))


def _advance(text: str, face: Dict, font_px: float, tracking_em: float) -> float:
    adv = face['advance']
    total = 0.0
    for ch in text:
        total += adv.get(ch, adv.get('n', 0.55))
    return font_px * (total + tracking_em * max(0, len(text) - 1))


def measure(text: str, face: Dict, font_px: float, tracking_em: float, stress: Optional[Set[str]] = None) -> float:
    if not stress:
        return _advance(text, face, font_px, tracking_em)
    total = 0.0
    tokens = text.split(' ')
    for k, tok in enumerate(tokens):
        scale = STRESS_SCALE if _token_key(tok) in stress else 1.0
        total += _advance(tok, face, font_px * scale, tracking_em)
        if k:
            total += _advance(' ', face, font_px, tracking_em)
    return total


def wrap(text: str, face: Dict, font_px: float, width: float, tracking_em: float, stress: Optional[Set[str]] = None) -> Optional[List[str]]:
    lines: List[str] = []
    cur = ''
    for tok in text.split():
        if measure(tok, face, font_px, tracking_em, stress) > width:
            return None  # a single word cannot break mid-word
        cand = f'{cur} {tok}'.strip()
        if not cur or measure(cand, face, font_px, tracking_em, stress) <= width:
            cur = cand
        else:
            lines.append(cur)
            cur = tok
    if cur:
        lines.append(cur)
    return lines


@dataclass
class Fit:
    font_px: float
    lines: List[str]
    width_px: float
    height_px: float
    tracking_em: float
    line_height: float
    floor_px: float
    status: str  # FIT | FLOOR_BREACH | WORD_TOO_WIDE


def fit_text(text: str, bbox: Dict[str, float], role: str, weight: str, canvas: Tuple[int, int],
             max_lines: int = 4, mono: bool = False, authored_lines: Optional[List[str]] = None,
             stress: Optional[Iterable[str]] = None) -> Fit:
    face = _face(role, weight, mono)
    stressed = {_token_key(s) for s in (stress or ())} or None
    tracking = TRACKING.get(role, -0.01)
    lh = LINE_HEIGHT.get(role, 1.1)
    floor = FLOOR_FRACTION.get(role, 0.03) * min(canvas)
    w, h = float(bbox['w']), float(bbox['h'])
    size = h / lh  # one-line maximum
    while size >= floor * 0.999:
        if authored_lines:
            lines = authored_lines if all(measure(l, face, size, tracking, stressed) <= w for l in authored_lines) else None
        else:
            lines = wrap(text, face, size, w, tracking, stressed)
        if lines and len(lines) <= max_lines and len(lines) * size * lh <= h + 0.5:
            width = max(measure(l, face, size, tracking, stressed) for l in lines)
            return Fit(round(size, 2), lines, round(width, 1), round(len(lines) * size * lh, 1), tracking, lh, round(floor, 1), 'FIT')
        size -= max(0.5, size * 0.03)
    # Report what the floor size would need so the gate can explain the failure.
    lines = wrap(text, face, floor, w, tracking, stressed)
    if lines is None:
        return Fit(round(floor, 2), [text], round(measure(text, face, floor, tracking, stressed), 1), round(floor * lh, 1), tracking, lh, round(floor, 1), 'WORD_TOO_WIDE')
    # The decrement loop can step over the narrow window just above the floor
    # where the wrap first fits — the floor itself is still a legal size, so
    # a floor wrap that satisfies the box and line cap is a fit, not a breach.
    if len(lines) <= max_lines and len(lines) * floor * lh <= h + 0.5:
        return Fit(round(floor, 2), lines, round(max(measure(l, face, floor, tracking, stressed) for l in lines), 1), round(len(lines) * floor * lh, 1), tracking, lh, round(floor, 1), 'FIT')
    return Fit(round(floor, 2), lines, round(max(measure(l, face, floor, tracking, stressed) for l in lines), 1), round(len(lines) * floor * lh, 1), tracking, lh, round(floor, 1), 'FLOOR_BREACH')
