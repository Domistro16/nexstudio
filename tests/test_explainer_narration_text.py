"""Explainer narration never reaches text-to-speech with markdown in it."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine_sources/explainer-locks/tools'))
from write_script import plain_narration  # noqa: E402
import make_reel  # noqa: E402


def heard(*items):
    return [{'text': f' {t}', 'start_ms': s, 'end_ms': e} for t, s, e in items]


class PlainNarration(unittest.TestCase):
    def test_pasted_bold_is_not_spoken_as_asterisks(self):
        script = ("But **Zcash does something different.**\r\n\r\n"
                  "**The ability to keep their transactions private while still proving they're valid.**")
        self.assertEqual(plain_narration(script),
                         "But Zcash does something different.\n\n"
                         "The ability to keep their transactions private while still proving they're valid.")

    def test_lists_headings_links_and_code(self):
        self.assertEqual(plain_narration("## Why it matters\n- fast\n2) cheap\nSee [docs](https://x.y) and `npm`."),
                         "Why it matters.\nfast.\ncheap.\nSee docs and npm.")

    def test_plain_narration_is_unchanged(self):
        for text in ["5 * 3 is fifteen.", "snake_case stays.", "Bake at 350 degrees for fifty minutes!"]:
            self.assertEqual(plain_narration(text), text)
        self.assertEqual(plain_narration("It's *not* hard."), "It's not hard.")


class ScriptWords(unittest.TestCase):
    def test_script_punctuation_and_spelling_ride_the_heard_timings(self):
        words = make_reel._script_words(
            heard(('It', 0, 200), ('uses', 200, 400), ('zero', 400, 600), ('knowledge', 600, 900),
                  ('proof', 900, 1200), ('specifically', 1300, 1800), ('Zcasonarq', 1800, 2600),
                  ('here', 3000, 3200), ('it', 3200, 3300), ('is', 3300, 3500)),
            'It uses zero-knowledge proofs, specifically zk-SNARKs. Here it is.')
        self.assertEqual([w['text'] for w in words],
                         ['It', 'uses', 'zero-knowledge', 'proofs,', 'specifically', 'zk-SNARKs.', 'Here', 'it', 'is.'])
        self.assertEqual((words[2]['start_ms'], words[3]['end_ms']), (400, 1200))
        self.assertEqual((words[5]['start_ms'], words[5]['end_ms']), (1800, 2600))
        self.assertTrue(all(a['start_ms'] <= b['start_ms'] for a, b in zip(words, words[1:])))

    def test_unrelated_transcript_keeps_the_heard_words(self):
        words = heard(('completely', 0, 300), ('different', 300, 600), ('speech', 600, 900))
        self.assertEqual(make_reel._script_words(words, 'Nothing like what was said here.'), words)


class StyleResolution(unittest.TestCase):
    def test_every_site_style_resolves_with_what_its_treatment_needs(self):
        for style_id in make_reel.STYLE_MAP:
            with self.subTest(style=style_id):
                style = make_reel.style_of(style_id)
                if style.get('show'):
                    self.assertIsInstance(style.get('shades'), list)


if __name__ == '__main__':
    unittest.main()
