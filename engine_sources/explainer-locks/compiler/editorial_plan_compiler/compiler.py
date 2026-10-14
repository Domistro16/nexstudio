"""Treatment -> EditorialPlan compiler.

Input: a ``NexStudioEditorialTreatmentV2`` document authored by NexMind P8.
Output: one ``NexStudioEditorialPlanV2`` per requested aspect, fully resolved
to pixels and milliseconds, plus a film-level gate report. The renderer
executes a plan verbatim; if the compiler cannot satisfy the treatment inside
the bounded vocabulary it fails with a coded reason for P8 to replan.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .authorities import editorial_motion_ensemble_director_v1 as ens
from .authorities import kinetic_typography_performance_authority_v3 as ktp
from .authorities import native_three_aspect_composition_authority_v2 as native
from .chassis import chassis_aspect, housing
from .contracts import MOTION_PROFILES, WORD_GLYPHS, BeatTreatment, FilmTreatment, TreatmentError
from .atmosphere import beat_atmosphere, brand_failures, film_atmosphere
from .figures import resolve_figure
from .groove import fit_phase, groove_stagger
from .illustration import IllustrationRegistry, IllustrationSolver, carried_copy
from .evidence import PhotoEvidence
from .lexicon import AssetFinder, NounLexicon, Resolution
from .media import NormalisedMedia, normalise_media
from .motion import camera_move, transition_window_ms
from .sound import MIX, SoundLibrary, bind_beat_sound, bind_film_music, community_surface, library_root
from .master_timeline import MasterTimeline, extend_tail, resolve_master
from .timing import BeatClock, CASCADE_SETTLE_MS, EXIT_MS, LAND_SETTLE_MS, LEAD_IN_MS, MIN_HOLD_MS, beat_clock, find_landing, normalise, readable_close_floor, retime_choreography, window_clock
from .typefit import fit_text
from .text_layout import fit_column
from .voice import VoiceSegment, resolve_voice
from .show import bands as show_bands, resolve as resolve_show


def _cascade_settle_ms(finish: str) -> int:
    """Word-cascade settle budget — must equal the runtime's per-profile landing
    duration ('rise' lands a word in 300ms, 'tonal' in 260)."""
    return 300 if MOTION_PROFILES[finish]['word_landing'] == 'rise' else CASCADE_SETTLE_MS


COMPILER_VERSION = 'EDITORIAL_PLAN_COMPILER_V3.0'
PLAN_SCHEMA = 'NexStudioEditorialPlanV2'
FONTS = Path(__file__).resolve().parents[2] / 'assets' / 'fonts'

# Grammar pattern -> native composition treatment authored per aspect.
NATIVE_TREATMENT = {
    'PROGRESSIVE_HERO_BUILD': 'PROGRESSIVE_HERO_BUILD',
    'PHRASE_REPLACEMENT': 'PROGRESSIVE_HERO_BUILD',
    'HERO_SCALE_PROMOTION': 'PROGRESSIVE_HERO_BUILD',
    'HERO_TO_EVIDENCE_HANDOFF': 'HERO_TO_EVIDENCE_HANDOFF',
    'EVIDENCE_PERSISTENCE_CARRIER': 'HERO_TO_EVIDENCE_HANDOFF',
    'ANCHORED_SCREENSHOT_PROOF': 'ANCHORED_SCREENSHOT_PROOF',
    'SEQUENTIAL_SUPPORT_LIST': 'PROCESS_RAIL',
    'QUIET_SUPPORT_AFTER_HERO': 'CONTROLLED_EMPTY_SPACE',
    'CONTRAST_RECONFIGURATION': 'CONTRAST_RECONFIGURATION',
    'PROCESS_RAIL': 'PROCESS_RAIL',
    'WORD_OBJECT_BRIDGE': 'HERO_TO_EVIDENCE_HANDOFF',
    'OBJECT_LED_TRANSITION': 'HERO_TO_EVIDENCE_HANDOFF',
    'PAYOFF_LOCKUP': 'PAYOFF_LOCKUP',
    'CTA_LOCKUP': 'CTA_LOCKUP',
    'CONTROLLED_EMPTY_SPACE': 'CONTROLLED_EMPTY_SPACE',
}
SHOT_ROLE = {'TEXT': 'TEXT_LED', 'ILLUSTRATION': 'HYBRID', 'HYBRID': 'HYBRID', 'EVIDENCE': 'HYBRID', 'FIGURE': 'CHARACTER_EMPHASIS', 'DATA': 'HYBRID', 'QUIET': 'TEXT_LED'}
# Native treatments whose visual field is too small to stage a visual argument; an illustration-led beat is
# re-composed on the aspect's evidence or process field instead (still authored natively per aspect).
SMALL_FIELD_TREATMENTS = {'PROGRESSIVE_HERO_BUILD', 'CONTROLLED_EMPTY_SPACE', 'PAYOFF_LOCKUP', 'CTA_LOCKUP'}
PROCESS_FORMS = {'PROCESS_PIPELINE', 'CALLOUT_LENS'}
WORD_CASCADE_MIN_STEP_MS = 70
# Delivery sizes; authority canvases are the native authoring spaces they scale from uniformly.
OUTPUT = {'9x16': (1080, 1920), '1x1': (1080, 1080), '16x9': (1920, 1080)}
BACKGROUND_RENDER = {'SOFT_FIELD': 'SOFT_FIELD', 'GRID_FIELD': 'GRID_FIELD', 'SPOTLIGHT_STAGE': 'SPOTLIGHT_STAGE', 'CARD_STAGE': 'CARD_STAGE',
                     'DOCUMENT_STAGE': 'CARD_STAGE', 'PRODUCT_STAGE': 'CARD_STAGE', 'LAYERED_PLANE': 'CARD_STAGE'}
MAX_LINES = {'support': 2, 'label': 1}
HERO_SUPPORT_MIN_RATIO = 1.65
DESCENDER_EM = 0.24       # how far a line's descenders hang below its line box (Black sans)
# Ladder rungs a photograph of the concept outranks: anything that stops naming the thing itself.
PHOTO_BELOW = ('hypernym', 'composite', 'typographic')


def _sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _box(x: float, y: float, w: float, h: float) -> Dict[str, float]:
    return {'x': round(x, 1), 'y': round(y, 1), 'w': round(max(0.0, w), 1), 'h': round(max(0.0, h), 1)}


def _inside(a: Dict[str, float], b: Dict[str, float], tol: float = 1.0) -> bool:
    return a['x'] >= b['x'] - tol and a['y'] >= b['y'] - tol and a['x'] + a['w'] <= b['x'] + b['w'] + tol and a['y'] + a['h'] <= b['y'] + b['h'] + tol


def _background_layers(render_bg: str, authored: str, stage: Dict[str, float], safe: Dict[str, float], canvas: Tuple[int, int], beat_index: int = 0,
                       finish: str = 'EDITORIAL_FLAT') -> List[Dict[str, Any]]:
    """Structural stage furniture under the content, derived from the authored background template.

    The runtime renders these verbatim; `kind` selects the draw recipe and all geometry is absolute
    canvas coordinates so the layers land exactly under the zones they dress."""
    W, H = canvas
    st = dict(stage)
    layers: List[Dict[str, Any]] = []
    if finish in ('PRODUCT_COLLAGE', 'FLOAT_FIELD'):
        # Free canvas: no lifted panel, no rules. Objects float on the field; the light (bloom behind the
        # hero) and the far-plane depth shapes are added by `atmosphere.beat_atmosphere` once the beat is placed.
        return layers
    has_panel = authored in {'CARD_STAGE', 'DOCUMENT_STAGE', 'PRODUCT_STAGE', 'LAYERED_PLANE'} or render_bg in {'CARD_STAGE', 'SPOTLIGHT_STAGE'}
    if has_panel:
        layers.append({'kind': 'panel', 'bbox': _box(st['x'], st['y'], st['w'], st['h']), 'fill': 'paper_lift', 'radius_frac': 0.032,
                       'shadow': {'opacity': 0.13, 'blur_frac': 0.022, 'dy_frac': 0.013}, 'opacity': 1.0})
        layers.append({'kind': 'hairline', 'bbox': _box(st['x'] + st['w'] * 0.045, st['y'] + st['h'] * 0.045, st['w'] * 0.91, st['h'] * 0.91), 'opacity': 0.10})
    if authored == 'LAYERED_PLANE':
        layers.append({'kind': 'plane', 'bbox': _box(st['x'] + st['w'] * 0.06, st['y'] + st['h'] * 0.05, st['w'] * 0.88, st['h'] * 0.9), 'rotation_deg': -1.1, 'opacity': 0.45})
        layers.append({'kind': 'plane', 'bbox': _box(st['x'] + st['w'] * 0.11, st['y'] + st['h'] * 0.09, st['w'] * 0.78, st['h'] * 0.82), 'rotation_deg': 1.3, 'opacity': 0.3})
    if authored == 'GRID_FIELD':
        layers.append({'kind': 'dotgrid', 'bbox': _box(st['x'], st['y'], st['w'], st['h']), 'opacity': 0.5, 'spacing_frac': 0.055, 'radius_frac': 0.0022})
    elif render_bg == 'STAGE_FIELD' and not has_panel:
        # Bare field: a sparse texture inside the safe frame keeps the cut from reading empty.
        # Texture cycles per beat so successive bare-field cuts feel deliberately re-dressed.
        v = beat_index % 4
        if v == 1:
            layers.append({'kind': 'ruled', 'bbox': dict(safe), 'opacity': 0.5, 'spacing_frac': 0.075})
        elif v == 2:
            layers.append({'kind': 'wash', 'bbox': _box(st['x'], st['y'], st['w'], st['h']), 'align': 'left' if beat_index % 2 else 'right'})
        elif v == 3:
            # A tonal wash, never a free-floating arc: an unexplained curve on the field is a stray mark.
            layers.append({'kind': 'wash', 'bbox': _box(st['x'], st['y'], st['w'], st['h']), 'align': 'right' if beat_index % 2 else 'left'})
        else:
            layers.append({'kind': 'dotgrid', 'bbox': dict(safe), 'opacity': 0.32, 'spacing_frac': 0.08, 'radius_frac': 0.0018})
    if render_bg == 'SPOTLIGHT_STAGE':
        layers.append({'kind': 'spotlight', 'bbox': _box(st['x'], st['y'] + st['h'] * 0.05, st['w'], st['h']), 'radius_frac': 0.9, 'opacity': 0.5})
    if not layers:
        # SOFT_FIELD text beats still get a faint field texture so a quiet cut never reads as dead paper.
        v = beat_index % 3
        if v == 1:
            layers.append({'kind': 'ruled', 'bbox': dict(safe), 'opacity': 0.3, 'spacing_frac': 0.095})
        elif v == 2:
            layers.append({'kind': 'wash', 'bbox': dict(safe), 'align': 'center'})
        else:
            layers.append({'kind': 'dotgrid', 'bbox': dict(safe), 'opacity': 0.18, 'spacing_frac': 0.095, 'radius_frac': 0.0016})
    return layers


def _overlap(a: Dict[str, float], b: Dict[str, float]) -> float:
    x = max(0.0, min(a['x'] + a['w'], b['x'] + b['w']) - max(a['x'], b['x']))
    y = max(0.0, min(a['y'] + a['h'], b['y'] + b['h']) - max(a['y'], b['y']))
    return x * y


def _contain(zone: Dict[str, float], aspect_ratio: float, scale: float = 1.0, anchor: str = 'center') -> Dict[str, float]:
    w = zone['w'] * scale
    h = w / aspect_ratio
    if h > zone['h'] * scale:
        h = zone['h'] * scale
        w = h * aspect_ratio
    x = zone['x'] + (zone['w'] - w) / 2
    y = zone['y'] + (zone['h'] - h) / 2
    if anchor == 'bottom':
        y = zone['y'] + zone['h'] - h
    elif anchor == 'top':
        y = zone['y']
    return _box(x, y, w, h)


def _carve(text: Dict[str, float], visual: Dict[str, float], gap: float = 40.0) -> Dict[str, float]:
    """Shrink the text zone so it never shares pixels with an occupied visual zone."""
    if _overlap(text, visual) <= 0:
        return text
    tcx, vcx = text['x'] + text['w'] / 2, visual['x'] + visual['w'] / 2
    tcy, vcy = text['y'] + text['h'] / 2, visual['y'] + visual['h'] / 2
    horizontal = abs(vcx - tcx) / max(1.0, text['w']) >= abs(vcy - tcy) / max(1.0, text['h'])
    if horizontal and vcx >= tcx:
        return _box(text['x'], text['y'], visual['x'] - gap - text['x'], text['h'])
    if horizontal:
        nx = visual['x'] + visual['w'] + gap
        return _box(nx, text['y'], text['x'] + text['w'] - nx, text['h'])
    if vcy >= tcy:
        return _box(text['x'], text['y'], text['w'], visual['y'] - gap - text['y'])
    ny = visual['y'] + visual['h'] + gap
    return _box(text['x'], ny, text['w'], text['y'] + text['h'] - ny)


def _remap(bbox: Dict[str, float], src: Dict[str, float], dst: Dict[str, float]) -> Dict[str, float]:
    sx = dst['w'] / max(1.0, src['w'])
    sy = dst['h'] / max(1.0, src['h'])
    return _box(dst['x'] + (bbox['x'] - src['x']) * sx, dst['y'] + (bbox['y'] - src['y']) * sy, bbox['w'] * sx, bbox['h'] * sy)


def _fonts() -> Dict[str, Any]:
    files = {'display': 'InterVariable.woff2', 'display_italic': 'InterVariable-Italic.woff2', 'data': 'JetBrainsMono-SemiBold.ttf'}
    return {k: {'file': f, 'sha256': _sha_file(FONTS / f)} for k, f in files.items()} | {
        'licenses': ['INTER-LICENSE-OFL.txt', 'JETBRAINS-MONO-LICENSE-APACHE2.txt'], 'families': {'display': 'Inter Display', 'text': 'Inter', 'data': 'JetBrains Mono'}}


class BeatCompiler:
    def __init__(self, film: FilmTreatment, aspect: str, lib: Optional[SoundLibrary], media: Optional[Dict[str, NormalisedMedia]] = None,
                 stagger_ms: Optional[int] = None, show_map: Optional[Dict[str, Any]] = None):
        self.film = film
        self.aspect = aspect
        self.lib = lib
        self.show_map = show_map
        self.media_files: Dict[str, NormalisedMedia] = media or {}
        self.W, self.H = native.ASPECTS[aspect]['size']
        sx, sy, sx2, sy2 = native.ASPECTS[aspect]['safe']
        self.safe = _box(sx, sy, sx2 - sx, sy2 - sy)
        # Evidence and figures may use the field beyond the caption-safe text frame, but never clip the canvas.
        self.frame = _box(24, 24, self.W - 48, self.H - 48)
        self.bands = None
        if show_map is not None:
            # The show's chrome owns the top and bottom margins: authored zones clamp to
            # the inner band, while the frame keeps its canvas margin so natural overshoot
            # (labels, strokes) may lean into the gutters without tripping the frame gate.
            self.bands = show_bands(aspect)
            self.safe = dict(self.bands['inner'])
        self.hero_max_lines = native.ASPECTS[aspect]['hero_max_lines']
        self.prev_motif: Optional[str] = None
        self.carried_media: Optional[Dict[str, Any]] = None  # media persisting from an earlier beat
        self.carried_illustration: Optional[Dict[str, Any]] = None  # illustration persisting from an earlier beat
        self.illustrations: Dict[str, Dict[str, Any]] = {}  # beat_id -> compiled illustration (carry-over source)
        self.solver = IllustrationSolver(aspect, (self.W, self.H), IllustrationRegistry(), film.media_library, self.media_files, film.brand.accent,
                                         collage=film.brand.finish in ('PRODUCT_COLLAGE', 'FLOAT_FIELD'),
                                         stagger_ms=stagger_ms or MOTION_PROFILES[film.brand.finish]['stagger_ms'], motion=MOTION_PROFILES[film.brand.finish],
                                         finish=film.brand.finish)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _layout_variant(b: BeatTreatment, base: str, n: int) -> str:
        # rotate the zone skeleton per beat so consecutive scenes never repeat
        # the same composition — the format keeps its grammar, not its template
        digits = ''.join(ch for ch in b.beat_id if ch.isdigit())
        idx = (int(digits) - 1) if digits else 0
        return f'{base}_{"ABCDEF"[idx % n]}'

    def _native_treatment(self, b: BeatTreatment) -> str:
        t = NATIVE_TREATMENT[b.pattern]
        il = b.illustration
        if self.film.brand.finish == 'PRODUCT_COLLAGE':
            has_visual = bool(il or b.media or b.data or b.figure or self.carried_illustration or self.carried_media)
            return 'COLLAGE_STAGE' if has_visual else 'COLLAGE_LOCKUP'
        if self.film.brand.finish == 'FLOAT_FIELD':
            has_visual = bool(il or b.media or b.data or b.figure or self.carried_illustration or self.carried_media)
            return self._layout_variant(b, 'FLOAT_STAGE' if has_visual else 'FLOAT_LOCKUP', 3 if has_visual else 2)
        if self.film.brand.finish == 'CENTER_DECK':
            has_visual = bool(il or b.media or b.data or b.figure or self.carried_illustration or self.carried_media)
            return self._layout_variant(b, 'DECK_STAGE' if has_visual else 'DECK_LOCKUP', 3 if has_visual else 2)
        if il is None and not self.carried_illustration:
            return t
        if il is not None and il.form in PROCESS_FORMS:
            return 'PROCESS_RAIL'
        if t in SMALL_FIELD_TREATMENTS or self.carried_illustration:
            return 'HERO_TO_EVIDENCE_HANDOFF' if b.dominant_layer in ('ILLUSTRATION', 'HYBRID') or self.carried_illustration else t
        return t

    @staticmethod
    def _text_share(b: BeatTreatment) -> float:
        """How much of the stacked stage the copy needs: grows with hero count and word load, shrinks for illustration-led beats."""
        heroes = sum(u.role == 'hero' for u in b.units)
        words = sum(len(u.text.split()) for u in b.units)
        share = 0.34 + 0.09 * max(0, heroes - 1) + 0.012 * max(0, words - 4)
        if b.dominant_layer == 'ILLUSTRATION':
            share -= 0.04
        return max(0.28, min(0.5, share))

    def _visual_kind(self, b: BeatTreatment) -> str:
        if b.illustration:
            return 'PROCESS_RAIL' if b.illustration.form in PROCESS_FORMS else 'EVIDENCE_CARD'
        if b.media:
            kind = self.film.media_library[b.media.asset_id].kind
            return {'SCREENSHOT': 'SCREENSHOT', 'DOCUMENT': 'DOCUMENT', 'IMAGE': 'EVIDENCE_CARD', 'VIDEO': 'EVIDENCE_CARD'}[kind]
        if b.figure:
            return 'HUMAN'
        if b.data:
            return 'EVIDENCE_CARD' if b.data.kind != 'SEQUENCE' else 'PROCESS_RAIL'
        return 'NONE'

    def _typography(self, b: BeatTreatment, clock: BeatClock, comp: Dict[str, Any], object_present: bool, shot_role: str) -> Tuple[Dict[str, Any], List[str], List[str]]:
        failures: List[str] = []
        warnings: List[str] = []
        units = [u.ktp_unit() for u in b.units]
        if not units:
            return {'motif': None, 'blocks': [], 'events': [], 'performance_events': [], 'transition_carrier': None, 'reading_order': [], 'focal_order': []}, failures, warnings
        perf = ktp.compile_performance(b.beat_type, self.aspect, clock.duration_ms, units, shot_role=shot_role, object_present=object_present,
                                       prev_motif=self.prev_motif, energy=b.energy, complexity=b.complexity)
        self.prev_motif = perf['motif']
        text_load = ktp.clamp(sum(ktp.token_count(u['text']) for u in units) / 28, .15, 1)
        ktp_zone = ktp._zones(self.aspect, shot_role, object_present, text_load).text_zone
        native_zone = comp['text_zone']
        # The composition authority may return a text zone that bleeds past the
        # safe frame bottom (legal for illustration, never for text). Clamp it
        # so remapped blocks cannot land outside the safe area.
        zx2 = min(native_zone['x'] + native_zone['w'], self.safe['x'] + self.safe['w'])
        zy2 = min(native_zone['y'] + native_zone['h'], self.safe['y'] + self.safe['h'])
        native_zone = {'x': max(native_zone['x'], self.safe['x']),
                       'y': max(native_zone['y'], self.safe['y']),
                       'w': zx2 - max(native_zone['x'], self.safe['x']),
                       'h': zy2 - max(native_zone['y'], self.safe['y'])}
        blocks: List[Dict[str, Any]] = []
        grown: List[int] = []
        for blk in perf['text_blocks']:
            bbox = _remap(blk['bbox'], ktp_zone, native_zone)
            # Edge-crop heroes may reach the safe edge but never leave the safe frame.
            bbox['x'] = max(self.safe['x'], bbox['x'])
            bbox['w'] = min(bbox['w'], self.safe['x'] + self.safe['w'] - bbox['x'])
            max_lines = self.hero_max_lines if blk['role'] == 'hero' else MAX_LINES[blk['role']]
            stress = b.units[blk['unit_index']].stress
            fit = fit_text(blk['text'], bbox, blk['role'], blk['weight'], (self.W, self.H), max_lines=max_lines, stress=stress)
            if fit.status == 'FLOOR_BREACH':
                # The authority's proportional box is a starting point; the legibility floor is the law. Grow the
                # box to the floor requirement inside the text zone and let the collision gate judge the result.
                bbox = _grow(bbox, fit.width_px * 1.04, fit.height_px * 1.06, native_zone, self.safe)
                fit = fit_text(blk['text'], bbox, blk['role'], blk['weight'], (self.W, self.H), max_lines=max_lines, stress=stress)
                grown.append(len(blocks))
            blocks.append({**blk, 'bbox': bbox, 'fit': asdict(fit)})
        def _others(k: int) -> List[Dict[str, float]]:
            rg = b.units[blocks[k]['unit_index']].replace_group
            return [bl['bbox'] for j, bl in enumerate(blocks) if j != k and not (rg and b.units[bl['unit_index']].replace_group == rg)]
        for gi in grown:
            blocks[gi]['bbox'] = _nudge_clear(blocks[gi]['bbox'], _others(gi), native_zone)
            # If the grown block has nowhere to go, the neighbour it hits may have the slack instead.
            for j, bl in enumerate(blocks):
                if j != gi and _overlap(bl['bbox'], blocks[gi]['bbox']) > 0:
                    blocks[j]['bbox'] = _nudge_clear(bl['bbox'], _others(j), native_zone)
        self._stack_in_narration_order(b, blocks, self.safe)
        groups = {i: unit.replace_group for i, unit in enumerate(b.units)}
        if not fit_column(blocks, groups, native_zone, DESCENDER_EM):
            fit_column(blocks, groups, self._free_band(native_zone, comp.get('visual_zone')), DESCENDER_EM)
        if comp.get('typography_hints', {}).get('text_align') == 'center':
            # Centred lockup: every block sits on the zone's vertical axis and sets its lines centred.
            lo = max(native_zone['x'], self.safe['x'])
            hi = min(native_zone['x'] + native_zone['w'], self.safe['x'] + self.safe['w'])
            for bl in blocks:
                bl['alignment'] = 'center'
                w = min(bl['bbox']['w'], hi - lo)
                bl['bbox'] = _box((lo + hi - w) / 2, bl['bbox']['y'], w, bl['bbox']['h'])
        hero_px = max((bl['fit']['font_px'] for bl in blocks if bl['role'] == 'hero'), default=0.0)
        for bl in blocks:
            f = bl['fit']
            if bl['role'] == 'support' and hero_px and f['font_px'] > hero_px / HERO_SUPPORT_MIN_RATIO:
                refit = fit_text(bl['text'], {**bl['bbox'], 'h': hero_px / HERO_SUPPORT_MIN_RATIO * f['line_height'] * len(f['lines'])}, 'support', bl['weight'], (self.W, self.H), max_lines=MAX_LINES['support'], stress=b.units[bl['unit_index']].stress)
                bl['fit'] = asdict(refit)
                f = bl['fit']
            if f['status'] == 'WORD_TOO_WIDE':
                failures.append(f"TYPE_WORD_TOO_WIDE:{bl['unit_index']}")
            elif f['status'] == 'FLOOR_BREACH':
                failures.append(f"TYPE_FLOOR_BREACH:{bl['unit_index']}")
            if not _inside(bl['bbox'], self.safe):
                failures.append(f"TEXT_OUTSIDE_SAFE:{bl['unit_index']}")
        for i in range(len(blocks)):
            for j in range(i + 1, len(blocks)):
                ui, uj = b.units[blocks[i]['unit_index']], b.units[blocks[j]['unit_index']]
                if ui.replace_group and ui.replace_group == uj.replace_group:
                    continue
                if _overlap(blocks[i]['bbox'], blocks[j]['bbox']) > 0:
                    failures.append(f"TEXT_COLLISION:{blocks[i]['unit_index']}:{blocks[j]['unit_index']}")
        events = retime_choreography(perf['choreography']['base']['events'], clock.landings_ms, clock.duration_ms, clock.exit_ms)
        events = self._resolve_replacements(b, blocks, events, clock)
        events = self._reveal_orphans(b, blocks, events, clock)
        # Performance events follow their unit's retimed reveal.
        reveal_start = {e['unit_index']: e['start_ms'] for e in reversed(events) if e['unit_index'] >= 0}
        perf_events = []
        for pe in perf['choreography']['performance_events']:
            shift = 0
            if pe['unit_index'] >= 0 and pe['unit_index'] in reveal_start:
                base = next((e for e in perf['choreography']['base']['events'] if e['unit_index'] == pe['unit_index']), None)
                shift = reveal_start[pe['unit_index']] - (base['start_ms'] if base else pe['start_ms'])
            perf_events.append({**pe, 'start_ms': max(0, pe['start_ms'] + shift), 'end_ms': min(clock.duration_ms, pe['end_ms'] + shift)})
        warnings += [w for w in perf['warnings'] if not w.startswith('TEXT_BLOCK_COLLISION')]
        if not perf['pass_gate'] and not failures:
            failures.append('TYPOGRAPHY_AUTHORITY_GATE_FAIL')
        self._word_cascade(b, blocks, events, clock)
        typ = {
            'motif': perf['motif'], 'spatial_preset': perf['spatial_preset'], 'blocks': blocks, 'events': events, 'performance_events': perf_events,
            'reveal_mode': self.film.typography.reveal, 'tonal_ink': self.film.typography.tonal_ink,
            'transition_carrier': perf['transition_carrier'], 'reading_order': perf['reading_order'], 'focal_order': perf['focal_order'], 'metrics': perf['metrics'],
        }
        return typ, failures, warnings

    def _free_band(self, zone: Dict[str, float], visual: Optional[Dict[str, float]]) -> Dict[str, float]:
        top, bottom = self.safe['y'], self.safe['y'] + self.safe['h']
        if visual and min(zone['x'] + zone['w'], visual['x'] + visual['w']) > max(zone['x'], visual['x']):
            if visual['y'] + visual['h'] <= zone['y']:
                top = max(top, visual['y'] + visual['h'])
            elif visual['y'] >= zone['y'] + zone['h']:
                bottom = min(bottom, visual['y'])
            else:
                return zone
        top, bottom = min(top, zone['y']), max(bottom, zone['y'] + zone['h'])
        return {'x': zone['x'], 'y': top, 'w': zone['w'], 'h': bottom - top}

    @staticmethod
    def _stack_in_narration_order(b: BeatTreatment, blocks: List[Dict[str, Any]], safe: Dict[str, float]) -> None:
        """Blocks that share a column read top-down in the order the voice says them.

        The authority sizes the hero and its supports; it does not know which unit is spoken
        first. The vertical slots it chose are kept (top edge and gaps) and refilled by unit
        order, so a lead-in never sits under the phrase it introduces. Replace-group stages
        share one slot and are left alone."""
        idx = [k for k, bl in enumerate(blocks) if not b.units[bl['unit_index']].replace_group]
        if len(idx) < 2:
            return
        def _same_column(a: Dict[str, float], c: Dict[str, float]) -> bool:
            return min(a['x'] + a['w'], c['x'] + c['w']) - max(a['x'], c['x']) > min(a['w'], c['w']) * 0.5
        if not all(_same_column(blocks[i]['bbox'], blocks[j]['bbox']) for i in idx for j in idx if i < j):
            return
        by_y = sorted(idx, key=lambda k: blocks[k]['bbox']['y'])
        by_unit = sorted(idx, key=lambda k: blocks[k]['unit_index'])
        if by_y == by_unit:
            return
        gaps = sorted((blocks[by_y[i + 1]]['bbox']['y'] - (blocks[by_y[i]]['bbox']['y'] + blocks[by_y[i]]['bbox']['h']) for i in range(len(by_y) - 1)), reverse=True)
        # The widest gap the authority drew goes under the hero, whose descenders reach below
        # its box; the next to the pair above it; the tight ones stay between supports.
        pairs = list(range(len(by_unit) - 1))
        def need(i: int) -> int:
            upper, lower = blocks[by_unit[i]]['role'], blocks[by_unit[i + 1]]['role']
            return 0 if upper == 'hero' else 1 if lower == 'hero' else 2
        order = sorted(pairs, key=lambda i: (need(i), i))
        gap_at = {i: gaps[n] for n, i in enumerate(order)}
        y = blocks[by_y[0]]['bbox']['y']
        for i, k in enumerate(by_unit):
            blocks[k]['bbox'] = {**blocks[k]['bbox'], 'y': round(y, 1)}
            # A block's box ends at its last baseline's line box; the descenders hang below it.
            y += blocks[k]['bbox']['h'] + max(gap_at.get(i, 0.0), DESCENDER_EM * blocks[k]['fit']['font_px'] if i < len(by_unit) - 1 else 0.0)
        # The restack uses true fitted heights (grown boxes can be taller than the slots the
        # authority drew), so the column can end lower than planned — slide it back inside
        # the safe frame with its gaps intact when there's room above.
        lim_b = safe['y'] + safe['h']
        bottom = max(blocks[k]['bbox']['y'] + blocks[k]['bbox']['h'] for k in idx)
        overflow = bottom - lim_b
        if overflow > 0:
            top = min(blocks[k]['bbox']['y'] for k in idx)
            shift = min(overflow, max(0.0, top - safe['y']))
            for k in idx:
                blocks[k]['bbox'] = {**blocks[k]['bbox'], 'y': round(blocks[k]['bbox']['y'] - shift, 1)}

    def _word_cascade(self, b: BeatTreatment, blocks: List[Dict[str, Any]], events: List[Dict[str, Any]], clock: BeatClock) -> None:
        """Per-word landing times for every block: a word arrives when the voice says it.

        Words are matched sequentially from the unit's landing word; words the voice does not
        say (display copy is authored, not transcribed) are spread evenly across the gap to the
        next spoken word. Stressed words are flagged for full-ink weight; the rest read tonal
        until the unit is complete."""
        reveal_start = {e['unit_index']: e['start_ms'] for e in reversed(events) if e['unit_index'] >= 0 and e['event'] not in ('HOLD', 'EXIT')}
        for bl in blocks:
            i = bl['unit_index']
            unit = b.units[i]
            mode = unit.reveal or self.film.typography.reveal
            bl['reveal'] = mode
            stress = {normalise(w) for w in unit.stress}
            muted = {normalise(w) for w in unit.mute}
            tokens = [t for line in bl['fit']['lines'] for t in line.split()]
            line_of = [li for li, line in enumerate(bl['fit']['lines']) for _ in line.split()]
            start = reveal_start.get(i, clock.landings_ms[i])
            times: List[Optional[int]] = [None] * len(tokens)
            if clock.landing_source[i] == 'WORD' and clock.words:
                cursor = max(0, find_landing(clock.words, unit.anchor_word or tokens[0], 0) or 0)
                for k, tok in enumerate(tokens):
                    idx = find_landing(clock.words, tok, cursor)
                    if idx is not None and idx >= cursor and (idx - cursor) <= 3:
                        times[k] = clock.words[idx].start_ms
                        cursor = idx + 1
            # Fill unmatched words evenly between their spoken neighbours.
            if times and times[0] is None:
                times[0] = start
            k = 0
            while k < len(times):
                if times[k] is not None:
                    k += 1
                    continue
                j = k
                while j < len(times) and times[j] is None:
                    j += 1
                lo = times[k - 1]
                hi = times[j] if j < len(times) else lo + WORD_CASCADE_MIN_STEP_MS * (j - k + 1) * 1.6
                n = j - k + 1
                for m in range(k, j):
                    times[m] = int(lo + (hi - lo) * (m - k + 1) / n)
                k = j
            # Monotonic, never before the unit reveal, never past the settle window.
            words = []
            prev = start - WORD_CASCADE_MIN_STEP_MS
            for k, tok in enumerate(tokens):
                t = max(int(times[k]), prev + WORD_CASCADE_MIN_STEP_MS, start)
                prev = t
                w = {'text': tok, 'line': line_of[k], 'start_ms': t, 'stress': normalise(tok) in stress}
                if normalise(tok) in muted:
                    w['tone'] = 'mute'
                words.append(w)
            if words:
                last = words[-1]['start_ms']
                settle = _cascade_settle_ms(self.film.brand.finish)
                bl['cascade_end_ms'] = last + settle
                limit = bl['exit_ms'] - 360 if bl.get('exit_ms') else clock.duration_ms - (clock.exit_ms + 40 if clock.fixed_window else 760)
                if last > limit:
                    # Compress the cascade so the phrase finishes reading before it leaves or the beat ends.
                    span = max(1, last - start)
                    room = max(WORD_CASCADE_MIN_STEP_MS * len(words), limit - start)
                    for w in words:
                        w['start_ms'] = int(start + (w['start_ms'] - start) * room / span)
                    bl['cascade_end_ms'] = words[-1]['start_ms'] + settle
                    bl['cascade_compression'] = round(room / span, 3)
            bl['words'] = words
            bl['has_stress'] = any(w['stress'] for w in words)

    @staticmethod
    def _resolve_replacements(b: BeatTreatment, blocks: List[Dict[str, Any]], events: List[Dict[str, Any]], clock: BeatClock) -> List[Dict[str, Any]]:
        """Stage B of a replace group only exists through PHRASE_REPLACE; stage A leaves as B arrives."""
        groups: Dict[str, List[int]] = {}
        for i, u in enumerate(b.units):
            if u.replace_group and u.role == 'hero':
                groups.setdefault(u.replace_group, []).append(i)
        stage_b = {ixs[1] for ixs in groups.values() if len(ixs) >= 2}
        out = list(events)
        for e in out:
            if e['event'] == 'PHRASE_REPLACE' and e['unit_index'] not in stage_b:
                e['event'] = 'MASK_REVEAL'  # a replacement needs a partner; alone it is just a reveal
        for ixs in groups.values():
            if len(ixs) < 2:
                continue
            a, bb = ixs[0], ixs[1]
            rep = next((e for e in out if e['event'] == 'PHRASE_REPLACE' and e['unit_index'] == bb), None)
            out = [e for e in out if not (e['unit_index'] == bb and e['event'] != 'PHRASE_REPLACE')]
            if rep is None:
                a_end = max((e['end_ms'] for e in out if e['unit_index'] == a), default=LEAD_IN_MS)
                rep = {'unit_index': bb, 'role': 'hero', 'event': 'PHRASE_REPLACE', 'start_ms': a_end + 420, 'end_ms': a_end + 750, 'strength': 0.94, 'note': 'replace_group'}
                out.append(rep)
            land = clock.landings_ms[bb]
            if clock.landing_source[bb] == 'WORD':
                a_end = max((e['end_ms'] for e in out if e['unit_index'] == a), default=LEAD_IN_MS)
                dur = rep['end_ms'] - rep['start_ms']
                rep['end_ms'] = max(a_end + 360 + dur, min(land, clock.duration_ms - 700))
                rep['start_ms'] = rep['end_ms'] - dur
            for bl in blocks:
                if bl['unit_index'] == a:
                    bl['replace_partner'] = bb
                    bl['exit_ms'] = rep['start_ms']
                if bl['unit_index'] == bb:
                    bl['replace_partner'] = a
        hold = next((e for e in out if e['event'] == 'HOLD'), None)
        latest = max((e['end_ms'] for e in out if e['event'] not in ('HOLD', 'EXIT')), default=0)
        if hold and hold['start_ms'] < latest:
            hold['start_ms'] = min(latest, hold['end_ms'])
        out.sort(key=lambda e: (e['start_ms'], e['end_ms'], e['unit_index']))
        return out

    @staticmethod
    def _reveal_orphans(b: BeatTreatment, blocks: List[Dict[str, Any]], events: List[Dict[str, Any]], clock: BeatClock) -> List[Dict[str, Any]]:
        """Units the grammar gives no choreography (labels) still land on their word."""
        revealed = {e['unit_index'] for e in events if e['unit_index'] >= 0}
        out = list(events)
        for bl in blocks:
            i = bl['unit_index']
            if i in revealed:
                continue
            land = min(clock.landings_ms[i], clock.duration_ms - 800)
            out.append({'unit_index': i, 'role': bl['role'], 'event': 'FADE_SCALE_SETTLE', 'start_ms': max(0, land - 240), 'end_ms': land, 'strength': 0.5, 'note': 'orphan_reveal'})
        out.sort(key=lambda e: (e['start_ms'], e['end_ms'], e['unit_index']))
        return out

    def _media(self, b: BeatTreatment, comp: Dict[str, Any], clock: BeatClock, typ: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not b.media and not self.carried_media:
            return None
        zone = comp['visual_zone']
        if b.media and self.carried_media and b.media.asset_id == self.carried_media['asset_id']:
            self.carried_media['persist_to'] = b.media.persist_to or b.beat_id
            b = replace(b, media=None)
        if b.media:
            asset = self.film.media_library[b.media.asset_id]
            house = housing(asset.kind, asset.width, asset.height, asset.asset_id, MOTION_PROFILES[self.film.brand.finish])
            ar = chassis_aspect(house['chassis'], asset.width / asset.height)
            bbox = _contain(zone, ar, min(1.0, comp['visual_hints']['evidence_scale']))
            proof_units = [i for i, u in enumerate(b.units) if u.semantic_role in ('proof', 'evidence')]
            hero_land = max((clock.landings_ms[i] for i, u in enumerate(b.units) if u.role == 'hero'), default=LEAD_IN_MS)
            enter = clock.landings_ms[proof_units[0]] if proof_units else hero_land + 180
            enter = min(enter, clock.duration_ms - 900)
            nm = self.media_files.get(asset.asset_id)
            media = {
                'asset_id': asset.asset_id, 'kind': asset.kind,
                'path': nm.render_path if nm else asset.path, 'sha256': nm.render_sha256 if nm else (_sha_file(Path(asset.path)) if Path(asset.path).exists() else None),
                'original_path': asset.path, 'original_sha256': nm.original_sha256 if nm else None, 'render_codec': nm.render_codec if nm else None,
                'role': b.media.role, 'bbox': bbox, 'zone': zone, 'focus': b.media.focus, 'trim': b.media.trim, 'audio': 'MUTE',
                'enter_ms': int(enter), 'enter_duration_ms': 360, 'carried_from': None, 'persist_to': b.media.persist_to, 'frame': 'EVIDENCE_PANEL',
                'source_size': {'w': asset.width, 'h': asset.height}, 'rights': asset.rights,
                **house,
                # A housing is the object's own body: it lands with its content, never as an empty
                # card waiting for the exhibit.
                'chrome_ms': None,
            }
            self.carried_media = media if b.media.persist_to and b.media.persist_to != b.beat_id else None
            return media
        carried = dict(self.carried_media)
        asset = self.film.media_library[carried['asset_id']]
        bbox = _contain(zone, chassis_aspect(carried['chassis'], asset.width / asset.height), min(1.0, comp['visual_hints']['evidence_scale']))
        carried.update({'bbox': bbox, 'zone': zone, 'enter_ms': 0, 'enter_duration_ms': 0, 'chrome_ms': None, 'carried_from': carried.get('carried_from') or self.carried_media['asset_id'],
                        'reframe': {'from': self.carried_media['bbox'], 'start_ms': 0, 'end_ms': 420} if self.carried_media['bbox'] != bbox else None})
        if carried['persist_to'] == b.beat_id:
            self.carried_media = None
        else:
            self.carried_media = carried
        return carried

    def _figure(self, b: BeatTreatment, comp: Dict[str, Any], clock: BeatClock, ensemble: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not b.figure:
            return None
        zone = comp['visual_zone']
        text_cx = comp['text_zone']['x'] + comp['text_zone']['w'] / 2
        zone_cx = zone['x'] + zone['w'] / 2
        # Library artwork faces the viewer's left; mirror when the copy sits to the figure's right.
        facing_left = not (b.figure.facing == 'TOWARD_TEXT' and text_cx > zone_cx + 40)
        if b.figure.facing == 'AWAY':
            facing_left = text_cx > zone_cx
        fig = resolve_figure(b.figure, b.beat_id, self.film.film_id, self.film.brand, facing_left=facing_left)
        bbox = _contain(zone, fig['composition']['aspect'], 1.0, anchor='bottom')
        ev = next((e for e in ensemble['events'] if e['channel'] == 'CHARACTER'), None)
        enter = ev['start_ms'] if ev else min(clock.duration_ms - 900, max(clock.landings_ms or [LEAD_IN_MS]) + 200)
        # A performer is part of the stage, not a payload: when the character event sits late the figure
        # still arrives inside the lead-in rather than leaving the stage empty.
        enter = max(LEAD_IN_MS // 4 + 20, min(int(enter), LEAD_IN_MS + 220))
        fig.update({'bbox': bbox, 'zone': zone, 'enter_ms': int(enter), 'enter_duration_ms': 300, 'entrance': 'SETTLE_RISE', 'ground_line': round(bbox['y'] + bbox['h'], 1)})
        return fig

    def _data(self, b: BeatTreatment, comp: Dict[str, Any], clock: BeatClock) -> Optional[Dict[str, Any]]:
        if not b.data:
            return None
        zone = comp['visual_zone']
        d = b.data
        canvas = (self.W, self.H)
        if d.kind == 'STAT':
            vbox = _box(zone['x'], zone['y'], zone['w'], zone['h'] * 0.62)
            lbox = _box(zone['x'], zone['y'] + zone['h'] * 0.68, zone['w'], zone['h'] * 0.22)
            blocks = [{'role': 'value', 'text': d.value, 'bbox': vbox, 'fit': asdict(fit_text(d.value, vbox, 'data', 'SemiBold', canvas, 1, mono=True))}]
            if d.label:
                blocks.append({'role': 'label', 'text': d.label, 'bbox': lbox, 'fit': asdict(fit_text(d.label, lbox, 'support', 'SemiBold', canvas, 2))})
        elif d.kind == 'COMPARISON':
            half = zone['w'] / 2 - 12
            blocks = []
            for i, (val, lab) in enumerate(((d.value, d.label), (d.secondary or '', ''))):
                if not val:
                    continue
                vbox = _box(zone['x'] + i * (half + 24), zone['y'], half, zone['h'] * 0.58)
                blocks.append({'role': 'value', 'side': i, 'text': val, 'bbox': vbox, 'fit': asdict(fit_text(val, vbox, 'data', 'SemiBold', canvas, 1, mono=True))})
            if d.label:
                lbox = _box(zone['x'], zone['y'] + zone['h'] * 0.7, zone['w'], zone['h'] * 0.2)
                blocks.append({'role': 'label', 'text': d.label, 'bbox': lbox, 'fit': asdict(fit_text(d.label, lbox, 'support', 'SemiBold', canvas, 2))})
        else:  # SEQUENCE: steps separated by ' | '
            steps = [s.strip() for s in d.value.split('|') if s.strip()][:5]
            blocks = []
            step_h = zone['h'] / max(1, len(steps))
            for i, s in enumerate(steps):
                sbox = _box(zone['x'] + 56, zone['y'] + i * step_h + step_h * 0.18, zone['w'] - 56, step_h * 0.64)
                blocks.append({'role': 'step', 'index': i, 'text': s, 'bbox': sbox, 'fit': asdict(fit_text(s, sbox, 'support', 'SemiBold', canvas, 2)),
                               'marker': _box(zone['x'], zone['y'] + i * step_h + step_h * 0.18, 40, 40)})
        hero_land = max((clock.landings_ms[i] for i, u in enumerate(b.units) if u.role == 'hero'), default=LEAD_IN_MS)
        enter = min(hero_land + 160, clock.duration_ms - 900)
        stagger = 160 if d.kind == 'SEQUENCE' else 0
        return {'kind': d.kind, 'zone': zone, 'blocks': blocks, 'enter_ms': int(enter), 'enter_duration_ms': 340, 'stagger_ms': stagger, 'style': 'COUNT_IN' if d.kind == 'STAT' else 'SETTLE',
                # A hairline table rail enters inside the lead-in when the figures themselves land late.
                'chrome_ms': LEAD_IN_MS // 4 + 40 if enter > LEAD_IN_MS + 340 else None}

    # ------------------------------------------------------------------ beat
    def _illustration(self, b: BeatTreatment, comp: Dict[str, Any], clock: BeatClock) -> Tuple[Optional[Dict[str, Any]], List[str]]:
        il = b.illustration
        if il is None:
            if self.carried_illustration:
                plan = carried_copy(self.carried_illustration)
                if self.carried_illustration.get('persist_to') == b.beat_id:
                    self.carried_illustration = None
                return plan, []
            return None, []
        src = self.illustrations.get(il.carry_from) if il.carry_from else None
        plan, failures = self.solver.compile(il, comp['visual_zone'], clock, b.beat_id, src)
        if self.show_map is not None:
            # The collage register's synthesized confirmation ring reads as a stray circle on the
            # flat show field — the section cut IS the confirmation.
            plan['ops'] = [o for o in plan.get('ops', []) if not (o.get('op') == 'EMIT' and o.get('synthesized'))]
        self.illustrations[b.beat_id] = plan
        self.carried_illustration = plan if il.persist_to else None
        return plan, failures

    def compile(self, b: BeatTreatment, clock: BeatClock, beat_offset_ms: int, beat_index: int = 0) -> Dict[str, Any]:
        failures: List[str] = []
        warnings: List[str] = []
        comp = native.compose(self.aspect, self._native_treatment(b), self._visual_kind(b))
        if b.illustration is not None and not (b.illustration.carry_from and b.illustration.carry_from in self.illustrations):
            _rebalance(comp, self._text_share(b))
        if self.carried_illustration and b.illustration is None:
            comp['visual_zone'] = dict(self.carried_illustration['zone'])  # persisted argument keeps its stage
        elif b.illustration is not None and b.illustration.carry_from and b.illustration.carry_from in self.illustrations:
            # Float beats keep their own composition: the carried entity travels
            # stage-to-stage (that IS the momentum), while locking the whole zone
            # to the source beat would starve this beat's text split.
            if self.film.brand.finish != 'FLOAT_FIELD':
                comp['visual_zone'] = dict(self.illustrations[b.illustration.carry_from]['zone'])
        if self.show_map is not None and b.illustration is not None:
            _SHOW_WIDGETS = {'DATA_BARS', 'DATA_TABLE', 'TIMELINE', 'VS_CARDS', 'LOGO_GRID', 'FLOW_STEPS', 'PROGRESS', 'SQUIGGLE', 'MAGNIFY'}
            if {e.glyph for e in b.illustration.entities} & _SHOW_WIDGETS:
                inner = self.bands['inner']
                vz = comp['visual_zone']
                nx = max(inner['x'], vz['x'] - vz['w'] * 0.08)
                nx2 = min(inner['x'] + inner['w'], vz['x'] + vz['w'] * 1.08)
                nb = inner['y'] + inner['h']
                comp['visual_zone'] = {'x': nx, 'y': vz['y'], 'w': nx2 - nx, 'h': max(vz['h'], (nb - vz['y']) * 0.72)}
        object_present = bool(b.media or b.figure or b.data or b.illustration or self.carried_media or self.carried_illustration)
        if object_present:
            comp['text_zone'] = _carve(comp['text_zone'], comp['visual_zone'])
            if comp['text_zone']['w'] < 200 or comp['text_zone']['h'] < 90:
                failures.append('TEXT_ZONE_TOO_SMALL_AFTER_CARVE')
        shot_role = 'PAYOFF' if b.beat_type in ('PAYOFF', 'CTA') else SHOT_ROLE[b.dominant_layer]
        typ, tf, tw = self._typography(b, clock, comp, object_present, shot_role)
        failures += tf
        warnings += tw

        ensemble_plan = ens.EditorialMotionEnsembleDirectorV1().plan(ens.EnsembleRequest(
            duration_ms=clock.duration_ms, shot_role=shot_role,
            hero_motion_count=sum(u.role == 'hero' for u in b.units), support_motion_count=sum(u.role != 'hero' for u in b.units),
            illustration_motion_count=(len(b.illustration.program) if b.illustration else 0) + (1 if (b.media or b.data or self.carried_media) else 0),
            character_present=b.figure is not None,
            transition_mode='TEXT_CARRIER' if (typ['transition_carrier'] and not b.media and not b.illustration) else 'OBJECT_OR_TEXT_CARRIER',
            beat_energy=b.energy, audio_accent_times=[l for l in clock.landings_ms if 0 < l < clock.duration_ms]))
        ensemble = asdict(ensemble_plan)
        warnings += ensemble['warnings']

        media = self._media(b, comp, clock, typ)
        figure = self._figure(b, comp, clock, ensemble)
        data = self._data(b, comp, clock)
        illustration, ilf = self._illustration(b, comp, clock)
        failures += ilf
        if illustration:
            if not _inside(illustration['zone'], self.frame, 2):
                failures.append('ILLUSTRATION_OUTSIDE_FRAME')
            for ent in illustration['entities']:
                boxes = [ent['art_bbox']] + ([ent['label']['bbox']] if ent.get('label') else [])
                for bx in boxes:
                    for bl in typ['blocks']:
                        if _overlap(bx, bl['bbox']) > 0:
                            failures.append(f"ILLUSTRATION_COLLIDES_TEXT:{ent['id']}:{bl['unit_index']}")
            if figure and any(_overlap(figure['bbox'], e['art_bbox']) > 0 for e in illustration['entities']):
                failures.append('FIGURE_COLLIDES_ILLUSTRATION')
            if not illustration['carried'] and illustration['state_changes'] == 0 and b.dominant_layer in ('ILLUSTRATION', 'HYBRID'):
                warnings.append('ILLUSTRATION_WITHOUT_STATE_CHANGE')
            for rel in illustration['relations']:
                if rel.get('stub'):
                    warnings.append(f"CONNECTOR_STUB_ADJACENT:{rel['id']}")

        # Ownership: nothing visual may sit on text, and every element stays in the safe frame.
        for name, el in (('MEDIA', media), ('FIGURE', figure)):
            if el:
                if not _inside(el['bbox'], self.frame, 2):
                    failures.append(f'{name}_OUTSIDE_FRAME')
                for bl in typ['blocks']:
                    if _overlap(el['bbox'], bl['bbox']) > 0:
                        failures.append(f"{name}_COLLIDES_TEXT:{bl['unit_index']}")
        if data:
            for db in data['blocks']:
                if db['fit']['status'] != 'FIT':
                    failures.append(f"DATA_{db['fit']['status']}")
                for bl in typ['blocks']:
                    if _overlap(db['bbox'], bl['bbox']) > 0:
                        failures.append(f"DATA_COLLIDES_TEXT:{bl['unit_index']}")
        # Transition: media persisting into the next beat carries the cut; otherwise the type carrier or a plain settle-cut.
        # The camera move on top of it is one grammar for the film, picked from the energy either side of the cut.
        next_beat = self.film.beats[beat_index + 1] if beat_index + 1 < len(self.film.beats) else None
        if media and media.get('persist_to') and media['persist_to'] != b.beat_id:
            transition = {'mode': 'EVIDENCE_PERSISTENCE', 'owner': 'MEDIA', 'start_ms': clock.duration_ms - clock.exit_ms, 'end_ms': clock.duration_ms}
        elif illustration and illustration.get('persist_to') and illustration['persist_to'] != b.beat_id:
            transition = {'mode': 'ILLUSTRATION_PERSISTENCE', 'owner': 'ILLUSTRATION', 'start_ms': clock.duration_ms - clock.exit_ms, 'end_ms': clock.duration_ms}
        elif typ['transition_carrier']:
            transition = {**typ['transition_carrier'], 'owner': 'TEXT'}
            if clock.fixed_window:
                transition['start_ms'] = max(transition['start_ms'], clock.duration_ms - clock.exit_ms)
        else:
            transition = {'mode': 'SETTLE_CUT', 'owner': 'NONE', 'start_ms': clock.duration_ms - transition_window_ms(b, next_beat, clock.exit_ms), 'end_ms': clock.duration_ms}
        camera = camera_move(b, next_beat, transition['mode'], beat_index, MOTION_PROFILES[self.film.brand.finish]['transition'] == 'scale_through')
        if camera is not None:
            transition['camera'] = camera
            if camera['move'] == 'cut':
                transition['start_ms'] = transition['end_ms']

        # The settled hold is the window in which every authored element has finished arriving and nothing has
        # started leaving; typography, ensemble and object channels are reconciled to that single window.
        settled = [e['end_ms'] for e in typ['events'] + typ['performance_events'] if e['unit_index'] != -1]
        if media:
            settled.append(media['enter_ms'] + media['enter_duration_ms'])
        if figure:
            settled.append(figure['enter_ms'] + figure['enter_duration_ms'])
        if data:
            settled.append(data['enter_ms'] + data['enter_duration_ms'] + data['stagger_ms'] * max(0, len(data['blocks']) - 1))
        if illustration:
            settled.append(illustration['settled_ms'])
        settled += [bl['cascade_end_ms'] for bl in typ['blocks'] if bl.get('cascade_end_ms') and not bl.get('exit_ms')]
        leaving = [transition['start_ms']]
        leaving += [e['start_ms'] for e in typ['events'] if e['event'] == 'EXIT']
        hold_start, hold_end = int(max(settled)), int(min(leaving))
        ensemble['hold_window'] = {'start_ms': hold_start, 'end_ms': hold_end}
        hold = next((e for e in typ['events'] if e['event'] == 'HOLD'), None)
        if hold:
            hold['start_ms'], hold['end_ms'] = hold_start, hold_end
        if clock.fixed_window:
            # Speech sets the window. Copy cascades with the spoken words, so the viewer reads the phrase as it is
            # said; what must survive is the hero in its settled state and every visual state change, legible for
            # a floor that scales with the beat, and no cascade still landing while the beat leaves.
            hero_units = {i for i, u in enumerate(b.units) if u.role == 'hero'}
            core = [e['end_ms'] for e in typ['events'] if e['unit_index'] in hero_units and e['event'] not in ('HOLD', 'EXIT')]
            core += [bl['cascade_end_ms'] for bl in typ['blocks'] if bl['unit_index'] in hero_units and bl.get('cascade_end_ms')]
            if illustration:
                # Decorations ride the hold; only authored state changes claim reading time.
                core += [o['end_ms'] for o in illustration.get('ops', []) if o.get('state_change') and not o.get('synthesized')]
            for el in (media, figure):
                if el:
                    core.append(el['enter_ms'] + el['enter_duration_ms'])
            legible = hold_end - (max(core) if core else hold_start)
            floor = readable_close_floor(clock.pause_after_ms) if clock.pause_after_ms >= 0 else MIN_HOLD_MS
            if legible < floor:
                (warnings if legible >= floor * 0.6 else failures).append(f'LEGIBLE_HOLD_{legible}MS_UNDER_{floor}MS')
            overrun = max((bl['cascade_end_ms'] - hold_end for bl in typ['blocks'] if bl.get('cascade_end_ms')), default=0)
            if overrun > 1000 // self.film.fps:
                failures.append(f'CASCADE_OVERRUNS_EXIT:{overrun}ms')
            for bl in typ['blocks']:
                if bl.get('cascade_compression', 1.0) < 0.8:
                    warnings.append(f"CASCADE_COMPRESSED:{bl['unit_index']}:{bl['cascade_compression']}")
            # Under MASTER the speaker's pause is the settled-hold budget: warn only when the
            # window couldn't afford even the pause-scaled readable close. The flat MIN_HOLD
            # floor stays on free-running beats (HOLD_TOO_SHORT below).
            settled_floor = readable_close_floor(clock.pause_after_ms)
            if hold_end - hold_start < settled_floor:
                warnings.append(f"SETTLED_HOLD:{hold_end - hold_start}ms")
        elif hold_end - hold_start < MIN_HOLD_MS:
            failures.append(f"HOLD_TOO_SHORT:{hold_end - hold_start}ms")
        if b.dominant_layer == 'FIGURE' and not figure:
            failures.append('FIGURE_UNRESOLVED')

        candidates = [{'event': pe['event'], 'at_ms': pe['end_ms'] if pe['event'] != 'SPATIAL_RECONFIGURE' else pe['start_ms'], 'strength': pe['strength']}
                      for pe in typ['performance_events'] if pe['event'] != 'SUPPORT_ITALIC_DRIFT']
        for e in typ['events']:
            if e['event'] == 'KEYWORD_HIT':
                candidates.append({'event': 'KEYWORD_HIT', 'at_ms': e['end_ms'], 'strength': e['strength']})
        if media and media['enter_duration_ms']:
            candidates.append({'event': 'EVIDENCE_LAND', 'at_ms': media['enter_ms'] + media['enter_duration_ms'], 'strength': 0.86, 'glyph': 'MEDIA'})
        if media and media.get('reframe'):
            candidates.append({'event': 'SPATIAL_RECONFIGURE', 'at_ms': 0, 'strength': 0.7})
        if data:
            candidates.append({'event': 'DATA_LAND', 'at_ms': data['enter_ms'] + data['enter_duration_ms'], 'strength': 0.8, 'glyph': 'COUNTER'})
        if illustration and not illustration['carried']:
            # Furniture lands audibly: a pop on each element's arrival. Under the collage's 'pop'
            # entrance the landing wave is the film's signature sound — it wins any window it
            # shares with a text hit (they are one fused moment, so it plays with pop texture),
            # and the 220ms-gap law takes every ~3rd landing of an 80ms-staggered wave.
            # Elsewhere it stays a subordinate furniture click. The accent caps decide the rest.
            pop_entrance = MOTION_PROFILES[self.film.brand.finish]['entrance'] == 'pop'
            for e in illustration['entities']:
                if not e.get('carried') and e.get('enter_duration_ms'):
                    candidates.append({'event': 'ELEMENT_LAND', 'at_ms': e['enter_ms'] + e['enter_duration_ms'], 'strength': 0.99 if pop_entrance else 0.34, 'glyph': e['glyph']})
            for r in illustration['relations']:
                if not r.get('drawn_by_op') and r.get('enter_duration_ms'):
                    candidates.append({'event': 'ELEMENT_LAND', 'at_ms': r['enter_ms'] + r['enter_duration_ms'], 'strength': 0.3, 'glyph': 'CONNECTOR'})
            glyph_of = {e['id']: e['glyph'] for e in illustration['entities']}
            for o in illustration['ops']:
                if o['state_change'] and o['op'] != 'INK':
                    candidates.append({'event': 'KEYWORD_HIT' if o['op'] == 'STRIKE' else 'EVIDENCE_LAND', 'at_ms': o['end_ms'], 'strength': 0.7, 'glyph': glyph_of.get(o['target'])})
                if o['op'] == 'INK':
                    candidates.append({'event': 'INK_WRITE', 'at_ms': o['start_ms'], 'strength': 0.72})
                if o['op'] in ('DRAW', 'CONNECT', 'TRACE'):
                    if (o.get('params') or {}).get('wipe'):
                        # A wiped stroke sweeps the stage — a whoosh at mid-sweep, not the line-draw
                        # scratch. It is the beat's authored event, so it outranks carriers.
                        candidates.append({'event': 'WIPE_SWEEP', 'at_ms': o['start_ms'] + (o['end_ms'] - o['start_ms']) // 3, 'strength': 0.62})
                    else:
                        candidates.append({'event': 'LINE_DRAW', 'at_ms': o['end_ms'], 'strength': 0.5})
                if o['op'] == 'EMIT':
                    candidates.append({'event': 'EMIT_CONFIRM', 'at_ms': o['end_ms'], 'strength': 0.75, 'glyph': glyph_of.get(o['target'])})
                if o['op'] == 'COUNT':
                    candidates.append({'event': 'COUNT_TICK', 'at_ms': o['end_ms'], 'strength': 0.5, 'glyph': glyph_of.get(o['target'])})
                    candidates.append({'event': 'COUNT_RISE', 'at_ms': o['start_ms'], 'strength': 0.38})
                if o['op'] == 'TRAVEL':
                    candidates.append({'event': 'LOUPE_TRAVEL', 'at_ms': o['end_ms'], 'strength': 0.55})
        if transition['mode'] in ('TEXT_MASK_WIPE', 'LABEL_EXPAND_WIPE'):
            candidates.append({'event': 'TRANSITION_CARRIER', 'at_ms': transition['start_ms'], 'strength': 0.6})
        # Camera moves are cuts with motion: a push, pull or drift takes a full whoosh; a dissolve
        # stays a subordinate fabric sound; a hard cut is silent.
        if transition.get('camera') and transition['end_ms'] > transition['start_ms']:
            sweep = {'push_through': 0.78, 'pull_back': 0.7, 'drift': 0.74, 'dissolve': 0.32}.get(transition['camera']['move'])
            if sweep:
                candidates.append({'event': 'TRANSITION_SWEEP', 'at_ms': transition['start_ms'], 'strength': sweep})
        sound = bind_beat_sound(self.lib, self.film.film_id, b.beat_id, beat_offset_ms, b.dominant_layer, b.energy, candidates,
                                profile=self.film.sfx)
        if self.lib is None and candidates and b.dominant_layer != 'QUIET':
            warnings.append('SOUND_LIBRARY_MISSING')

        bg = (comp.get('authentic_v2_plan') or {}).get('background_template') or 'SOFT_FIELD'
        render_bg = 'SPOTLIGHT_STAGE' if figure else ('CARD_STAGE' if (media or data or self.film.brand.finish == 'CENTER_DECK') else ('STAGE_FIELD' if illustration else 'SOFT_FIELD'))
        stage_zone = (media or figure or data or illustration or {}).get('zone') or self.safe
        if self.show_map is not None:
            # The show beat: the section field owns the base, the faint grid is its first
            # background layer, and the shade owns the illustration accent for the beat.
            rec = self.show_map['beats'][b.beat_id]
            shade = rec['shade']
            comp['background_base'] = shade['bg']
            chrome = {'ink': shade['on'], 'accent': shade['accent'] or self.film.brand.accent or '#ffffff', 'bg': shade['bg']}
            if illustration is not None:
                illustration['accent'] = chrome['accent']
        # Every beat must carry visible content inside its lead-in window: stage, chrome or first words.
        firsts = [w['start_ms'] for w in [{'text': w.text, 'start_ms': w.start_ms, 'end_ms': w.end_ms} for w in clock.words]]
        firsts += [e['start_ms'] for e in typ['events'] if e['unit_index'] >= 0]
        if illustration:
            firsts += [e['enter_ms'] for e in illustration['entities']] + [r['enter_ms'] for r in illustration['relations']]
        if media:
            firsts += [media['chrome_ms'] or media['enter_ms']]
        if data:
            firsts += [data['chrome_ms'] or data['enter_ms']]
        if figure:
            firsts += [figure['enter_ms']]
        if firsts and min(firsts) > LEAD_IN_MS + 420:
            warnings.append(f'EMPTY_LEAD:{min(firsts)}ms')
        background = {'template': bg, 'render': render_bg, 'stage': stage_zone,
                      'layers': _background_layers(render_bg, bg, stage_zone, self.safe, (self.W, self.H), beat_index, self.film.brand.finish),
                      'finish': self.film.brand.finish}
        if self.show_map is not None:
            background['base'] = comp.get('background_base')
            background['layers'] = [{'kind': 'grid', 'bbox': {'x': 0, 'y': 0, 'w': self.W, 'h': self.H}, 'tone': chrome['ink']}]
        return {
            'beat_id': b.beat_id, 'beat_type': b.beat_type, 'pattern': b.pattern, 'dominant_layer': b.dominant_layer, 'shot_role': shot_role,
            'start_ms': beat_offset_ms, 'duration_ms': clock.duration_ms, 'energy': b.energy,
            'narration': b.narration, 'words': [{'text': w.text, 'start_ms': w.start_ms, 'end_ms': w.end_ms} for w in clock.words],
            'landings': [{'unit_index': i, 'at_ms': l, 'source': s} for i, (l, s) in enumerate(zip(clock.landings_ms, clock.landing_source))],
            'composition': {
                'layout_family': comp['layout_family'], 'treatment': comp['treatment'], 'text_zone': comp['text_zone'], 'visual_zone': comp['visual_zone'],
                'safe_area': self.safe, 'background': background,
                'native_profile': comp['native_profile'], 'derived_by_scaling': comp['derived_by_scaling'], 'authority': comp['authority_version'],
            },
            'typography': typ, 'ensemble': {'events': ensemble['events'], 'dominant_sequence': ensemble['dominant_sequence'], 'hold_window': ensemble['hold_window'], 'transition_window': ensemble['transition_window']},
            'media': media, 'figure': figure, 'data': data, 'illustration': illustration,
            'show': ({'idx': rec['idx'], 'name': rec['name']} if self.show_map is not None else None),
            'chrome': (chrome if self.show_map is not None else None),
            'transition': transition, 'sound': sound,
            'gate': {'status': 'FAIL' if failures else 'PASS', 'failures': failures, 'warnings': sorted(set(warnings))},
        }


def _film_pack(film: FilmTreatment, registry: IllustrationRegistry) -> Optional[str]:
    """The colour pack the film's authored native marks come from (most used wins), if any."""
    tally: Dict[str, int] = {}
    for b in film.beats:
        for e in (b.illustration.entities if b.illustration else []):
            item = registry.items.get(e.asset_ref or '')
            if item and item.get('colour') == 'native' and item.get('family') != 'brand':
                pack = AssetFinder.pack_of(e.asset_ref)
                tally[pack] = tally.get(pack, 0) + 1
    return max(sorted(tally), key=lambda k: tally[k]) if tally else None


def settle_descriptors(plans: Dict[str, Any]) -> None:
    """A tile drawn by a mark or photograph over the concept's own name owes that name the label
    floor. The solver records per aspect whether the well leaves room for it; a name that is short
    of the floor in any aspect is settled once for all of them, so the film keeps one answer: a
    photograph fills the well alone (it *is* the concept), while an ancestor's mark gives way to
    the name set as the mark (a mark the viewer cannot read back is worth less than the word).
    The recorded resolution follows, so the audit says what is drawn."""
    short = set()
    for plan in plans.values():
        for bt in plan['beats']:
            for e in ((bt.get('illustration') or {}).get('entities') or []):
                if e['params'].get('descriptor_fit') is False:
                    short.add((bt['beat_id'], e['id']))
    for plan in plans.values():
        for bt in plan['beats']:
            for e in ((bt.get('illustration') or {}).get('entities') or []):
                if 'descriptor_fit' not in e['params']:
                    continue
                e['params'].pop('descriptor_fit')
                if (bt['beat_id'], e['id']) not in short:
                    continue
                res = dict(e['params'].get('resolution') or {})
                if e.get('photo'):
                    e['params'].pop('word', None)
                    e['params'].pop('word_kind', None)
                    e['params']['descriptor'] = 'photo_fills'
                    res['word'] = None
                else:
                    e['asset'] = None
                    e['params']['descriptor'] = 'word_alone'
                    res.update(via='typographic', asset_ref=None, path=[])
                e['params']['resolution'] = res


def _resolve_concepts(film: FilmTreatment, registry: IllustrationRegistry) -> List[str]:
    """Turn every entity `concept` into an asset_ref and/or a typeset word before any aspect is
    solved, so all aspects draw the same answer. The ladder is pinned to the film's colour pack:
    authored marks set it, otherwise the first pass's most common pack does. Returns film-level
    warnings (a photo catalogue that would not answer, so a lower rung stood in)."""
    todo = [(b, e) for b in film.beats if b.illustration for e in b.illustration.entities if e.concept and not e.asset_ref]
    if not todo:
        return []
    finder = AssetFinder(registry.items, NounLexicon(), registry.quarantined)
    pack = _film_pack(film, registry)
    if pack is None:
        tally: Dict[str, int] = {}
        for _b, e in todo:
            r = finder.resolve(e.concept, None, e.glyph in WORD_GLYPHS)
            item = registry.items.get(r.asset_ref or '')
            if item and item.get('colour') == 'native' and item.get('family') != 'brand':
                p = AssetFinder.pack_of(r.asset_ref)
                tally[p] = tally.get(p, 0) + 1
        pack = max(sorted(tally), key=lambda k: tally[k]) if tally else None
    # With a colour pack in play a flat mono icon among colour art is the mix the film forbids,
    # so the ladder only offers native marks and otherwise typesets.
    native_only = pack is not None
    evidence = PhotoEvidence(lexicon=finder.lexicon)
    for b, e in todo:
        named = e.glyph == 'CHIP' and e.label is not None
        r = finder.resolve(e.concept, pack, e.glyph in WORD_GLYPHS, native_only, named)
        if r.via in PHOTO_BELOW and e.glyph in WORD_GLYPHS:
            # No mark names the concept itself: a rights-clean photograph of it, set in the housing's
            # well, beats an ancestor's mark or the bare word. The name still rides with it unless
            # the housing already carries it.
            rec = evidence.find(e.concept)
            if rec is not None:
                word = None if (named or e.glyph == 'BADGE') else e.concept
                r = Resolution(e.concept, 'photo', asset_ref=None, word=word, path=[e.concept, rec.title])
                e.params['photo'] = evidence.as_plan(rec)
        if e.glyph == 'CHIP' and not named and r.via in ('composite', 'photo'):
            # A chip's peg holds the mark or photograph and its inside label the name: an unlabelled
            # chip drawn by an ancestor or a photograph takes its concept as that label, so the
            # descriptor is typeset through the label fit rather than squeezed into the peg.
            e.label = e.concept
            r = replace(r, via='hypernym' if r.via == 'composite' else r.via, word=None)
        if r.via == 'composite' and e.glyph == 'BADGE':
            # A disc is too small for a mark and a word: it takes its own name (or monogram)
            # rather than an ancestor's mark the viewer cannot read back to the concept.
            r = replace(r, via='typographic', asset_ref=None, path=[])
        if r.via == 'unresolved':
            # Only a bare ICON can end here (every housing typesets). Nothing stands in for it.
            raise TreatmentError('CONCEPT_UNRESOLVED', f'{e.id}: no mark in the registry draws {e.concept!r} and {e.glyph} cannot typeset it', b.beat_id)
        e.asset_ref = r.asset_ref
        if r.word:
            e.params['word'] = r.word
            e.params['word_kind'] = 'numeric' if r.via == 'numeric' else 'name'
        e.params['resolution'] = r.as_dict()
    return [f'EVIDENCE_UNAVAILABLE:{u}' for u in evidence.unavailable]


def _asset_pack_mix(film: FilmTreatment, registry: IllustrationRegistry) -> List[str]:
    """One colour pack per film. Native-colour art from different packs (3D emoji next to flat
    icons) reads as assembled, not designed; brand marks are exempt since each is its own mark."""
    by_pack: Dict[str, List[str]] = {}
    for b in film.beats:
        if not b.illustration:
            continue
        for e in b.illustration.entities:
            item = registry.items.get(e.asset_ref or '')
            if not item or item.get('colour') != 'native' or item.get('family') == 'brand':
                continue
            by_pack.setdefault('.'.join(e.asset_ref.split('.')[:2]), []).append(f'{b.beat_id}:{e.asset_ref}')
    if len(by_pack) <= 1:
        return []
    packs = sorted(by_pack, key=lambda k: (-len(by_pack[k]), k))
    strays = [ref for k in packs[1:] for ref in by_pack[k]]
    return [f'ASSET_PACK_MIX:{packs[0]}!={ref}' for ref in strays]


def _captions(beats: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    caps = []
    for bt in beats:
        for w in bt['words']:
            caps.append({'beat_id': bt['beat_id'], 'text': w['text'], 'start_ms': bt['start_ms'] + w['start_ms'], 'end_ms': bt['start_ms'] + w['end_ms']})
    return caps


def _grow(bbox: Dict[str, float], need_w: float, need_h: float, zone: Dict[str, float], safe: Dict[str, float]) -> Dict[str, float]:
    """Enlarge a box about its centre to at least need_w x need_h, staying inside the text zone and safe frame."""
    lim_x = max(zone['x'], safe['x'])
    lim_r = min(zone['x'] + zone['w'], safe['x'] + safe['w'])
    lim_y = max(zone['y'], safe['y'])
    lim_b = min(zone['y'] + zone['h'], safe['y'] + safe['h'])
    w = min(max(bbox['w'], need_w), lim_r - lim_x)
    h = min(max(bbox['h'], need_h), lim_b - lim_y)
    cx, cy = bbox['x'] + bbox['w'] / 2, bbox['y'] + bbox['h'] / 2
    x = min(max(cx - w / 2, lim_x), lim_r - w)
    y = min(max(cy - h / 2, lim_y), lim_b - h)
    return {'x': round(x, 1), 'y': round(y, 1), 'w': round(w, 1), 'h': round(h, 1)}


def _nudge_clear(bbox: Dict[str, float], others: List[Dict[str, float]], zone: Dict[str, float]) -> Dict[str, float]:
    """Slide a box vertically inside the zone to the nearest position clear of every other box; unchanged if none exists."""
    if not any(_overlap(bbox, o) > 0 for o in others):
        return bbox
    lo, hi = zone['y'], zone['y'] + zone['h'] - bbox['h']
    candidates: List[float] = []
    for o in others:
        candidates += [o['y'] - bbox['h'] - 6, o['y'] + o['h'] + 6]
    best = None
    for y in sorted(c for c in candidates if lo - 0.5 <= c <= hi + 0.5):
        trial = {**bbox, 'y': round(y, 1)}
        if not any(_overlap(trial, o) > 0 for o in others):
            if best is None or abs(y - bbox['y']) < abs(best['y'] - bbox['y']):
                best = trial
    return best or bbox


def _rebalance(comp: Dict[str, Any], text_share: float) -> None:
    """Re-split a stacked (text over visual) or side-by-side (text beside visual) stage so the copy gets `text_share` of the axis."""
    t, v = comp['text_zone'], comp['visual_zone']
    gap_y = v['y'] - (t['y'] + t['h'])
    gap_x = v['x'] - (t['x'] + t['w'])
    if gap_y >= 0 and _overlap({**t, 'y': 0, 'h': 1}, {**v, 'y': 0, 'h': 1}) > 0:
        top, bottom = t['y'], v['y'] + v['h']
        span = bottom - top - gap_y
        th = round(span * text_share, 1)
        t['h'] = th
        v['y'] = round(top + th + gap_y, 1)
        v['h'] = round(bottom - v['y'], 1)
    elif gap_x >= 0 and _overlap({**t, 'x': 0, 'w': 1}, {**v, 'x': 0, 'w': 1}) > 0:
        left, right = t['x'], v['x'] + v['w']
        span = right - left - gap_x
        tw = round(span * max(text_share, 0.4), 1)
        t['w'] = tw
        v['x'] = round(left + tw + gap_x, 1)
        v['w'] = round(right - v['x'], 1)


def _extend_for_program(clock: BeatClock, b: BeatTreatment) -> BeatClock:
    """An illustration op that lands on a late word must still finish, settle and be read before the cut.

    A MASTER window cannot grow: the deficit is folded into ``budget_met`` and gated there."""
    if not b.illustration:
        return clock
    cursor = 0
    latest = 0
    for op in b.illustration.program:
        if 'word' in op.at:
            idx = find_landing(clock.words, op.at['word'], cursor)
            if idx is None:
                continue
            start = clock.words[idx].start_ms - 60
            cursor = idx
        elif 'unit' in op.at:
            start = clock.landings_ms[op.at['unit']]
        else:
            start = LEAD_IN_MS + op.at['offset_ms']
        latest = max(latest, start + op.duration_ms)
    needed = latest + MIN_HOLD_MS + EXIT_MS + 80
    if needed <= clock.duration_ms:
        return clock
    if clock.fixed_window:
        met = max(0.0, (clock.duration_ms - latest) / (MIN_HOLD_MS + EXIT_MS + 80))
        return replace(clock, budget_met=round(min(clock.budget_met, met), 3))
    return replace(clock, duration_ms=int(needed))


def _master_clocks(film: FilmTreatment, base_dir: Path) -> Tuple[MasterTimeline, List[BeatClock], List[int], List[VoiceSegment]]:
    """Beats take their windows from the continuous speech timeline; the last spoken beat gets a silent readable close."""
    tl = resolve_master(film.beats, film.voice, base_dir)
    by_id = {w.beat_id: w for w in tl.windows}
    clocks: List[BeatClock] = []
    for b in film.beats:
        w = by_id[b.beat_id]
        clocks.append(_extend_for_program(window_clock(b.beat_id, [u.text for u in b.units], [u.anchor_word for u in b.units], w.local_words(), w.duration_ms, 'MASTER', w.pause_after_ms), b))
    last = next((i for i in range(len(film.beats) - 1, -1, -1) if by_id[film.beats[i].beat_id].speech_start_ms >= 0), None)
    if last is not None and clocks[last].budget_met < 1.0:
        c = clocks[last]
        need = max((max(c.landings_ms) + LAND_SETTLE_MS) if c.landings_ms else 0, (c.words[-1].start_ms + _cascade_settle_ms(film.brand.finish)) if c.words else 0) + MIN_HOLD_MS + EXIT_MS
        extend_tail(tl, need - c.duration_ms)
        w = by_id[film.beats[last].beat_id]
        clocks[last] = _extend_for_program(window_clock(c.beat_id, [u.text for u in film.beats[last].units], [u.anchor_word for u in film.beats[last].units], w.local_words(), w.duration_ms, 'MASTER', w.pause_after_ms), film.beats[last])
    offsets = [by_id[b.beat_id].start_ms for b in film.beats]
    seg = VoiceSegment('MASTER', 'MASTER', None, tl.audio_path, hashlib.sha256(Path(tl.audio_path).read_bytes()).hexdigest(), tl.audio_ms,
                       {'alignment_path': str((base_dir / film.voice['alignment_path']).resolve()), 'head_pad_ms': tl.head_pad_ms, 'tail_silence_ms': tl.tail_silence_ms,
                        'tempo': tl.tempo, 'windows': [{'beat_id': w.beat_id, 'start_ms': w.start_ms, 'end_ms': w.end_ms, 'speech_start_ms': w.speech_start_ms,
                                                         'speech_end_ms': w.speech_end_ms, 'pause_before_ms': w.pause_before_ms, 'pause_after_ms': w.pause_after_ms,
                                                         'match_ratio': w.match_ratio} for w in tl.windows]})
    return tl, clocks, offsets, [seg]


def compile_film(treatment: Dict[str, Any], work_dir: Path, base_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Compile every requested aspect. Returns {'plans': {aspect: plan}, 'gate': {...}, 'voice': [...]}."""
    film = FilmTreatment.parse(treatment)
    base_dir = base_dir or work_dir
    work_dir.mkdir(parents=True, exist_ok=True)
    for m in film.media_library.values():
        p = Path(m.path)
        m.path = str(p if p.is_absolute() else (base_dir / p).resolve())
        if not Path(m.path).exists():
            raise TreatmentError('MEDIA_ASSET_FILE_MISSING', m.path)
    normalised = {m.asset_id: normalise_media(m, work_dir) for m in film.media_library.values()}
    treatment_sha = hashlib.sha256(json.dumps(treatment, sort_keys=True).encode()).hexdigest()
    voice_source = str(film.voice.get('source') or 'FIXTURE').upper()
    timeline: Optional[MasterTimeline] = None
    if voice_source == 'MASTER':
        timeline, clocks, offsets, segments = _master_clocks(film, base_dir)
        total_ms = timeline.film_ms
        segment_starts = [timeline.head_pad_ms]
    else:
        segments = resolve_voice(film.beats, film.voice, work_dir, base_dir, film.film_id)
        seg_by_id: Dict[str, VoiceSegment] = {s.beat_id: s for s in segments}
        clocks = []
        for b in film.beats:
            seg = seg_by_id[b.beat_id]
            clock = beat_clock(b.beat_id, [u.text for u in b.units], [u.anchor_word for u in b.units], seg.alignment, seg.source, b.min_duration_ms, b.energy)
            clocks.append(_extend_for_program(clock, b))
        offsets = []
        t = 0
        for c in clocks:
            offsets.append(t)
            t += c.duration_ms
        total_ms = t
        segment_starts = [o + LEAD_IN_MS for o in offsets]

    show_map = resolve_show(film)
    root = library_root()
    lib = SoundLibrary(root) if root else None
    plans: Dict[str, Any] = {}
    registry = IllustrationRegistry()
    film_warnings: List[str] = _resolve_concepts(film, registry)
    film_failures: List[str] = _asset_pack_mix(film, registry)
    atmosphere = film_atmosphere(asdict(film.brand))
    film_failures += brand_failures(atmosphere)
    # The bed is chosen before any beat is laid out: its tempo sets the landing-wave stagger, and once
    # the beats exist its playback phase is fitted to their landings. Every aspect shares the one bed.
    spoken = [b for b in film.beats if b.dominant_layer != 'QUIET'] or film.beats
    music = bind_film_music(film.film_id, film.mood, total_ms, sum(b.energy for b in spoken) / len(spoken))
    profile = MOTION_PROFILES[film.brand.finish]
    stagger_ms, subdivision = groove_stagger(profile['stagger_ms'], music.get('bpm'))
    for aspect in film.aspects:
        bc = BeatCompiler(film, aspect, lib, normalised, stagger_ms=stagger_ms, show_map=show_map)
        beats = [bc.compile(b, c, o, i) for i, (b, c, o) in enumerate(zip(film.beats, clocks, offsets))]
        W, H = native.ASPECTS[aspect]['size']
        # The field is dressed once the content is placed: the bloom follows each beat's hero from the
        # previous beat's light, the far-plane shapes take whatever room the content leaves.
        prev_bloom = None
        for bt in beats:
            atmo_layers = beat_atmosphere(film.film_id, bt, (W, H), bc.safe, prev_bloom, atmosphere)
            prev_bloom = next(L['at'] for L in atmo_layers if L['kind'] == 'bloom')
            if show_map is None:
                # Flat show field: the rotating shade + grid IS the field — no bloom/depth blobs.
                bt['composition']['background']['layers'] += atmo_layers
        phase = fit_phase(music, beats)
        aspect_music = {**music, 'start_offset_ms': phase['start_offset_ms'],
                        'groove': {**phase, 'stagger_ms': stagger_ms, 'stagger_subdivision': subdivision, 'authored_stagger_ms': profile['stagger_ms']}}
        if bc.carried_media:
            film_failures.append(f'{aspect}:MEDIA_PERSISTENCE_UNTERMINATED')
        if bc.carried_illustration:
            film_failures.append(f'{aspect}:ILLUSTRATION_PERSISTENCE_UNTERMINATED')
        motifs = [bt['typography']['motif'] for bt in beats if bt['typography']['motif']]
        if len(motifs) >= 4 and len(set(motifs)) < 2:
            film_warnings.append(f'{aspect}:MOTIF_MONOTONY')
        fails = [f"{bt['beat_id']}:{f}" for bt in beats for f in bt['gate']['failures']]
        film_failures += [f'{aspect}:{f}' for f in fails]
        film_warnings += [f"{aspect}:{bt['beat_id']}:{w}" for bt in beats for w in bt['gate']['warnings']]
        ow, oh = OUTPUT[aspect]
        plans[aspect] = {
            'schema': PLAN_SCHEMA, 'compiler': COMPILER_VERSION, 'film_id': film.film_id, 'aspect': aspect, 'fps': film.fps,
            'canvas': {'w': W, 'h': H}, 'output': {'w': ow, 'h': oh, 'scale': round(ow / W, 4)},
            'brand': asdict(film.brand), 'motion': {**profile, 'stagger_ms': stagger_ms}, 'typography': asdict(film.typography), 'fonts': _fonts(), 'duration_ms': total_ms,
            'illustration_registry': {'path': str(bc.solver.registry.path), 'version': bc.solver.registry.version},
            'voice': {'source': voice_source, 'segments': [
                {'beat_id': s.beat_id, 'source': s.source, 'audio_path': s.audio_path, 'sha256': s.audio_sha256, 'start_ms': o, 'duration_ms': s.duration_ms, 'evidence': s.evidence}
                for s, o in zip(segments, segment_starts)]},
            'timeline': None if timeline is None else {'source': 'MASTER', 'audio_ms': timeline.audio_ms, 'head_pad_ms': timeline.head_pad_ms, 'tail_silence_ms': timeline.tail_silence_ms,
                                                       'tempo': timeline.tempo, 'beats': [{'beat_id': w.beat_id, 'start_ms': w.start_ms, 'end_ms': w.end_ms, 'speech_start_ms': w.speech_start_ms,
                                                                                          'speech_end_ms': w.speech_end_ms, 'budget_met': c.budget_met} for w, c in zip(timeline.windows, clocks)]},
            'music': aspect_music, 'mix': MIX, 'atmosphere': atmosphere,
            'surfaces': {'grain': community_surface('surface', 'grain-fine'), 'paper': community_surface('texture', 'paper006-color')},
            'beats': beats, 'captions': [] if show_map is not None else _captions(beats),
            'captions_policy': 'none' if show_map is not None else ('kinetic' if film.brand.finish in ('PRODUCT_COLLAGE', 'FLOAT_FIELD', 'CENTER_DECK') else 'burned'),
            'show': ({'format': show_map['format'], 'subject': show_map['subject'],
                      'sections': [{'idx': i, 'name': n} for i, n in enumerate(show_map['sections'])],
                      'bands': show_bands(aspect)} if show_map is not None else None),
            'gate': {'status': 'FAIL' if fails else 'PASS', 'failures': fails},
            'provenance': {
                'treatment_sha256': treatment_sha, 'creative_authority': 'NEXMIND_P8', 'compiler_role': 'DETERMINISTIC_PLAN_COMPILER', 'renderer_role': 'EXECUTION_ONLY',
                'voice_timing': voice_source, 'commercial_certification': False if voice_source == 'FIXTURE' else None,
                'authorities': json.loads((Path(__file__).parent / 'authorities' / 'AUTHORITY_PROVENANCE.json').read_text())['files'],
                'sound_library': {'root': str(root) if root else None, 'version': lib.version if lib else None},
                'media_assets': [{'asset_id': m.asset_id, 'kind': m.kind, 'rights': m.rights, 'original_path': nm.original_path, 'original_sha256': nm.original_sha256,
                                  'render_path': nm.render_path, 'render_sha256': nm.render_sha256, 'render_codec': nm.render_codec, 'normalised': nm.normalised}
                                 for m in film.media_library.values() for nm in [normalised[m.asset_id]]],
            },
        }
    settle_descriptors(plans)
    gate = {'status': 'FAIL' if film_failures else 'PASS', 'failures': film_failures, 'warnings': sorted(set(film_warnings)), 'duration_ms': total_ms,
            'aspects': list(plans), 'voice_source': voice_source, 'beats': len(film.beats)}
    return {'plans': plans, 'gate': gate, 'voice': [asdict(s) for s in segments]}


def write_outputs(result: Dict[str, Any], out_dir: Path) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    for aspect, plan in result['plans'].items():
        p = out_dir / f'plan_{aspect}.json'
        p.write_text(json.dumps(plan, indent=1))
        written[aspect] = str(p)
    g = out_dir / 'gate_report.json'
    g.write_text(json.dumps(result['gate'], indent=1))
    written['gate'] = str(g)
    return written
