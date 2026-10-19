import json
import os
import re
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fetch_data as fd  # noqa: E402


class Formulas(unittest.TestCase):
    def test_pyth_even(self):
        exp, luck = fd.compute_pythagorean_luck(81, 162, 700, 700)
        self.assertEqual(exp, 81.0)
        self.assertEqual(luck, 0.0)

    def test_pyth_zero_runs(self):
        self.assertEqual(fd.compute_pythagorean_luck(0, 0, 0, 0), (0.0, 0.0))
        self.assertEqual(fd.compute_pythagorean_luck(0, 10, 0, 0), (0.0, 0.0))

    def test_close_luck(self):
        # 30-20 in close games, .500 overall -> (0.6-0.5)*50 = 5
        self.assertEqual(fd.compute_close_game_luck(30, 20, 81, 162), 5.0)

    def test_close_zero_games(self):
        self.assertEqual(fd.compute_close_game_luck(0, 0, 81, 162), 0.0)
        self.assertEqual(fd.compute_close_game_luck(1, 1, 0, 0), 0.0)


class Failure(unittest.TestCase):
    def test_partial_fetch_raises(self):
        with mock.patch.object(fd, "SEASONS", [2024]), \
             mock.patch.object(fd, "fetch_standings", side_effect=OSError("boom")), \
             mock.patch.object(fd, "fetch_schedule", return_value=(2024, {})), \
             mock.patch.object(fd, "fetch_postseason", return_value=(2024, {})):
            with self.assertRaises(RuntimeError):
                fd.build_data()

    def test_validate_rejects_incomplete(self):
        with self.assertRaises(ValueError):
            fd.validate({"metadata": {"seasons": [2024]}, "teams": []})


class Inline(unittest.TestCase):
    def test_inline_roundtrip(self):
        html = "a\n  const data = {\"x\":1};\nb\n"
        out = fd.inline_into_html(html, {"y": 2})
        self.assertIn('const data = {"y":2};', out)

    def test_inline_missing_marker(self):
        with self.assertRaises(ValueError):
            fd.inline_into_html("<html></html>", {})


class Committed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "data.json")) as f:
            cls.data = json.load(f)

    def test_complete(self):
        fd.validate(self.data)

    def test_composite(self):
        for t in self.data["teams"]:
            for y, s in t["seasons"].items():
                self.assertAlmostEqual(
                    s["compositeLuck"], 0.6 * s["pythLuck"] + 0.4 * s["closeLuck"], delta=0.02)
                self.assertLessEqual(s["wins"] + s["losses"], s["gamesPlayed"])

    def test_html_inline_matches_data_json(self):
        with open(os.path.join(ROOT, "index.html")) as f:
            html = f.read()
        m = re.search(r"^\s*const data = (.*);\s*$", html, re.M)
        self.assertIsNotNone(m)
        self.assertEqual(json.loads(m.group(1)), self.data)


if __name__ == "__main__":
    unittest.main()
