"""display_units/chunk_beats regressions — beat clause merging must keep the
clause list and its (text, start-word) pairs in lock-step or the unit
anchor pass indexes pairs out of range (production crash, xr-0161708a)."""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine_sources/explainer-locks/tools"))
sys.path.insert(0, str(ROOT / "services/studio-family-engines"))

import make_reel  # noqa: E402


def w(text, start, end):
    return {"text": text, "start_ms": start, "end_ms": end}


class DisplayUnitsTest(unittest.TestCase):
    def test_short_trailing_clause_merges_without_desync(self):
        # Final clause begins <500ms (HOLD_MIN_MS) before the beat ends ->
        # merged into the previous clause; clauses/pairs must stay aligned.
        words = [w("Agents", 0, 300), w("pay,", 300, 600),
                 w("get", 600, 800), w("paid.", 800, 1050)]
        units = make_reel.display_units(words)
        self.assertTrue(units)
        beats = make_reel.chunk_beats(words)
        self.assertTrue(beats)

    def test_multiple_trailing_clauses_cascade(self):
        # Two clauses inside the hold window merge one at a time.
        words = [w("One", 0, 300), w("two,", 300, 600),
                 w("three,", 600, 700), w("four.", 700, 900)]
        units = make_reel.display_units(words)
        self.assertTrue(units)

    def test_normal_clause_spacing_unchanged(self):
        words = [w("Agents", 0, 400), w("pay,", 400, 800),
                 w("get", 1200, 1500), w("paid.", 1500, 2000)]
        units = make_reel.display_units(words)
        self.assertTrue(units)
        self.assertTrue(all(u["anchor_word"] for u in units))


if __name__ == "__main__":
    unittest.main()
