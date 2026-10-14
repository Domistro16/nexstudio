"""A stacked type column stays inside its text zone (xr-ba9ac66e b09, 16x9)."""
from pathlib import Path
import copy
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine_sources/explainer-locks/compiler'))
from editorial_plan_compiler.text_layout import fit_column  # noqa: E402

ZONE = {'x': 110, 'y': 62, 'w': 988, 'h': 288.0}


def block(unit, y, h, font, floor, width, w=988.0, x=110.0):
    return {'unit_index': unit, 'bbox': {'x': x, 'y': y, 'w': w, 'h': h},
            'fit': {'font_px': font, 'height_px': h, 'width_px': width, 'floor_px': floor, 'status': 'FIT'}}


def overflowing_column():
    return [block(0, 62.0, 54.7, 55.82, 33.1, 392.0),
            block(1, 136.4, 54.7, 55.82, 33.1, 812.8),
            block(3, 263.7, 126.6, 129.18, 33.1, 986.8),
            block(2, 204.5, 46.0, 37.7, 19.4, 367.5, w=849.6, x=179.2)]


def inside(box, zone):
    return (box['x'] >= zone['x'] - 0.1 and box['y'] >= zone['y'] - 0.1
            and box['x'] + box['w'] <= zone['x'] + zone['w'] + 0.1
            and box['y'] + box['h'] <= zone['y'] + zone['h'] + 0.1)


def overlap(a, b):
    return (min(a['x'] + a['w'], b['x'] + b['w']) > max(a['x'], b['x'])
            and min(a['y'] + a['h'], b['y'] + b['h']) > max(a['y'], b['y']))


class TextColumnFit(unittest.TestCase):
    def test_overflowing_column_is_reset_inside_the_zone_above_its_floors(self):
        blocks = overflowing_column()
        self.assertTrue(fit_column(blocks, {}, ZONE, 0.24))
        for b in blocks:
            self.assertTrue(inside(b['bbox'], ZONE), b)
            self.assertGreaterEqual(b['fit']['font_px'], b['fit']['floor_px'])
        ordered = sorted(blocks, key=lambda b: b['unit_index'])
        for upper, lower in zip(ordered, ordered[1:]):
            self.assertLessEqual(upper['bbox']['y'] + upper['bbox']['h'], lower['bbox']['y'])
        self.assertFalse(any(overlap(a['bbox'], b['bbox']) for i, a in enumerate(blocks) for b in blocks[i + 1:]))

    def test_a_column_already_inside_the_zone_is_untouched(self):
        blocks = [block(0, 70.0, 54.7, 55.82, 33.1, 392.0), block(1, 140.0, 54.7, 55.82, 33.1, 600.0)]
        before = copy.deepcopy(blocks)
        self.assertTrue(fit_column(blocks, {}, ZONE, 0.24))
        self.assertEqual(blocks, before)

    def test_an_impossible_fit_leaves_the_blocks_for_the_gates(self):
        blocks = [block(i, 62.0 + i * 130, 126.6, 129.18, 120.0, 900.0) for i in range(3)]
        before = copy.deepcopy(blocks)
        self.assertFalse(fit_column(blocks, {}, ZONE, 0.24))
        self.assertEqual(blocks, before)

    def test_side_by_side_layouts_are_not_restacked(self):
        blocks = [block(0, 62.0, 300.0, 55.82, 33.1, 400.0, w=450.0),
                  block(1, 62.0, 54.7, 55.82, 33.1, 400.0, w=450.0, x=640.0)]
        before = copy.deepcopy(blocks)
        self.assertFalse(fit_column(blocks, {}, ZONE, 0.24))
        self.assertEqual(blocks, before)


if __name__ == '__main__':
    unittest.main()
