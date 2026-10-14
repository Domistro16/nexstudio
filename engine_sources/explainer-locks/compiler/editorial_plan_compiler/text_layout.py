"""Keep a typography column inside its allocated stage at readable sizes."""
from __future__ import annotations


def fit_column(blocks, replace_groups, zone, descender_em):
    if not blocks:
        return True
    def overlaps(a, b):
        return (min(a['x'] + a['w'], b['x'] + b['w']) > max(a['x'], b['x'])
                and min(a['y'] + a['h'], b['y'] + b['h']) > max(a['y'], b['y']))
    def contained(box):
        return (box['x'] >= zone['x'] - 0.1 and box['y'] >= zone['y'] - 0.1
                and box['x'] + box['w'] <= zone['x'] + zone['w'] + 0.1
                and box['y'] + box['h'] <= zone['y'] + zone['h'] + 0.1)
    def same_stage(a, b):
        group = replace_groups.get(a['unit_index'])
        return bool(group) and group == replace_groups.get(b['unit_index'])
    conflict = any(not contained(block['bbox']) for block in blocks) or any(
        overlaps(a['bbox'], b['bbox']) and not same_stage(a, b)
        for index, a in enumerate(blocks) for b in blocks[index + 1:])
    if not conflict:
        return True
    # This authority produces columns as well as split layouts. Preserve
    # valid split layouts instead of silently changing their composition.
    if any(min(a['bbox']['x'] + a['bbox']['w'], b['bbox']['x'] + b['bbox']['w'])
           - max(a['bbox']['x'], b['bbox']['x'])
           <= min(a['bbox']['w'], b['bbox']['w']) * 0.5
           for index, a in enumerate(blocks) for b in blocks[index + 1:]):
        return False
    if any(block['fit']['status'] != 'FIT' for block in blocks):
        return False
    stages = {}
    for block in sorted(blocks, key=lambda item: item['unit_index']):
        key = replace_groups.get(block['unit_index']) or ('unit', block['unit_index'])
        stages.setdefault(key, []).append(block)
    rows = list(stages.values())
    minimum = max(block['fit']['floor_px'] / block['fit']['font_px'] for block in blocks)
    maximum = min([1.0] + [
        min(block['bbox']['w'], zone['w']) / block['fit']['width_px']
        for block in blocks if block['fit']['width_px'] > 0])
    gap_floor = 4.0
    def needed(scale):
        return sum(max(block['fit']['height_px'] for block in row) * scale for row in rows) + sum(
            max(gap_floor, descender_em * max(block['fit']['font_px'] for block in row) * scale)
            for row in rows[:-1])
    # Never shrink below a role's legibility floor or mask an impossible fit.
    available = zone['h'] - 1.0
    if minimum > maximum or needed(minimum) > available:
        return False
    low, high = minimum, maximum
    for _ in range(24):
        middle = (low + high) / 2
        if needed(middle) <= available:
            low = middle
        else:
            high = middle
    scale = low
    top = min(block['bbox']['y'] for block in blocks)
    y = min(max(top, zone['y']), zone['y'] + zone['h'] - needed(scale))
    for index, row in enumerate(rows):
        row_height = max(block['fit']['height_px'] for block in row) * scale
        for block in row:
            fit = dict(block['fit'])
            for key in ['font_px', 'width_px', 'height_px']:
                fit[key] *= scale
            width = min(block['bbox']['w'], zone['w'])
            x = min(max(block['bbox']['x'], zone['x']), zone['x'] + zone['w'] - width)
            block['fit'] = fit
            block['bbox'] = {'x': x, 'y': y, 'w': width, 'h': fit['height_px']}
        y += row_height
        if index < len(rows) - 1:
            y += max(gap_floor, descender_em * max(block['fit']['font_px'] for block in row))
    return True
