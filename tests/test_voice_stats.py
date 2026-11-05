import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from voice_stats import build_profile, compare, edit_diff, measure  # noqa: E402

PUNCHY = ("I tried it. It broke. So I read the logs for an hour, and the answer was "
          "sitting in line three the whole time — a typo in a config file nobody "
          "had touched since March. Fixed. ") * 20
EVEN = ("The system processes incoming requests in a consistent manner. "
        "The team reviews each result against the documented criteria. "
        "The process ensures quality across every stage of delivery. ") * 20


class Measure(unittest.TestCase):
    def test_counts_words_and_sentences(self):
        m = measure("One two three. Four five? Six!")
        self.assertEqual(m["words"], 6)
        self.assertEqual(m["sentences"], 3)
        self.assertEqual(m["sentence_mean"], 2.0)

    def test_spread_separates_varied_from_even(self):
        self.assertGreater(measure(PUNCHY)["sentence_spread"], 5)
        self.assertLess(measure(EVEN)["sentence_spread"], 1)

    def test_punctuation_rates(self):
        m = measure("I can't stop — really; it's fine (mostly). Is it? Yes! " * 10)
        for key in ("em_dash_per_1k", "semicolon_per_1k", "paren_per_1k",
                    "question_per_1k", "exclaim_per_1k", "contraction_per_1k",
                    "first_person_per_1k"):
            self.assertGreater(m[key], 0, key)

    def test_ignores_code_frontmatter_urls_headings(self):
        text = ("---\ntitle: x; y\n---\n# Heading; here\n\n```\na; b; c — d\n```\n\n"
                "See [docs](https://e.com/a;b) and `x;y` now.\n")
        m = measure(text)
        self.assertEqual(m["semicolon_per_1k"], 0)
        self.assertEqual(m["em_dash_per_1k"], 0)
        self.assertEqual(m["colon_per_1k"], 0)

    def test_paragraph_mean(self):
        self.assertEqual(measure("A b. C d.\n\nE f.")["paragraph_mean"], 1.5)

    def test_empty(self):
        self.assertEqual(measure("")["words"], 0)


class ProfileAndCompare(unittest.TestCase):
    def setUp(self):
        self.profile = build_profile({"a": PUNCHY, "b": PUNCHY.replace("March", "May"),
                                      "c": PUNCHY.replace("hour", "afternoon")})

    def test_low_confidence_when_small(self):
        self.assertEqual(build_profile({"a": "Short text here."})["confidence"], "low")

    def test_on_voice_draft_has_no_drift(self):
        self.assertEqual(compare(PUNCHY, self.profile)["drifts"], [])

    def test_off_voice_draft_drifts_on_rhythm(self):
        feats = {d["feature"] for d in compare(EVEN, self.profile)["drifts"]}
        self.assertIn("sentence_spread", feats)
        self.assertIn("first_person_per_1k", feats)

    def test_zero_rate_tolerates_one_stray_use(self):
        prof = build_profile({"a": EVEN, "b": EVEN, "c": EVEN})
        draft = EVEN + "One more; really."
        feats = {d["feature"] for d in compare(draft, prof)["drifts"]}
        self.assertNotIn("semicolon_per_1k", feats)

    def test_short_flag(self):
        self.assertTrue(compare("Too short.", self.profile)["short"])

    def test_register_label_stored(self):
        self.assertEqual(build_profile({"a": PUNCHY}, "newsletter")["register"], "newsletter")


class Registers(unittest.TestCase):
    """Holdout check: a sample in another register must warn; one register must not."""

    def test_mixed_register_warns_on_the_odd_sample(self):
        prof = build_profile({"a": PUNCHY, "b": PUNCHY.replace("March", "May"),
                              "c": PUNCHY.replace("hour", "afternoon"), "memo": EVEN})
        self.assertEqual(len(prof["warnings"]), 1)
        self.assertIn("memo", prof["warnings"][0])
        self.assertGreaterEqual(len(prof["samples"]["memo"]["holdout_drifts"]), 3)

    def test_one_register_does_not_warn(self):
        prof = build_profile({"a": PUNCHY, "b": PUNCHY.replace("March", "May"),
                              "c": PUNCHY.replace("hour", "afternoon")})
        self.assertEqual(prof["warnings"], [])

    def test_short_odd_sample_records_drift_but_does_not_warn(self):
        short_even = EVEN[:len(EVEN) // 4]  # about 70 words: too noisy to warn on
        prof = build_profile({"a": PUNCHY, "b": PUNCHY, "c": PUNCHY, "memo": short_even})
        self.assertEqual(prof["warnings"], [])
        self.assertTrue(prof["samples"]["memo"]["holdout_drifts"])

    def test_two_samples_skip_holdout(self):
        self.assertEqual(build_profile({"a": PUNCHY, "b": EVEN})["warnings"], [])


AI_DRAFT = ("In today's landscape, teams must leverage robust tooling to navigate complexity. "
            "This comprehensive approach ensures seamless delivery and empowers developers. ") * 5
SENT = ("Teams need better tools. I've watched three migrations stall on one config bug. "
        "Fix that first. ") * 5


class EditDiff(unittest.TestCase):
    def test_reports_direction_and_pair_counts(self):
        res = edit_diff([(AI_DRAFT, SENT), (AI_DRAFT, SENT)])
        self.assertEqual(res["pairs"], 2)
        self.assertEqual(res["features"]["first_person_per_1k"]["pairs_up"], 2)
        self.assertEqual(res["features"]["sentence_mean"]["pairs_down"], 2)
        self.assertIn(("leverage", 2), res["words_cut"])
        self.assertIn(("config", 2), res["words_added"])

    def test_stopwords_and_unchanged_features_are_not_reported(self):
        res = edit_diff([(AI_DRAFT, SENT)])
        cut = {w for w, _ in res["words_cut"]}
        self.assertNotIn("to", cut)
        self.assertNotIn("semicolon_per_1k", res["features"])

    def test_identical_pair_reports_nothing(self):
        res = edit_diff([(SENT, SENT)])
        self.assertEqual(res["features"], {})
        self.assertEqual(res["words_cut"], [])


class CLI(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "voice_stats.py"), *args],
                              capture_output=True, text=True)

    def test_round_trip_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            paths = []
            for i, text in enumerate([PUNCHY, PUNCHY, PUNCHY]):
                p = os.path.join(d, f"s{i}.md")
                with open(p, "w") as fh:
                    fh.write(text)
                paths.append(p)
            prof = os.path.join(d, "voice.json")
            r = self.run_cli("profile", *paths, "--out", prof)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(prof) as fh:
                self.assertEqual(json.load(fh)["version"], 2)
            self.assertEqual(self.run_cli("compare", paths[0], "--profile", prof).returncode, 0)
            even = os.path.join(d, "even.md")
            with open(even, "w") as fh:
                fh.write(EVEN)
            r = self.run_cli("compare", even, "--profile", prof)
            self.assertEqual(r.returncode, 1)
            self.assertIn("drift:", r.stdout)

    def test_diff_cli(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = os.path.join(d, "ai.md"), os.path.join(d, "sent.md")
            for p, text in ((a, AI_DRAFT), (b, SENT)):
                with open(p, "w") as fh:
                    fh.write(text)
            r = self.run_cli("diff", a, b)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("words cut: ", r.stdout)
            self.assertIn("leverage", r.stdout)
            self.assertEqual(self.run_cli("diff", a).returncode, 2)

    def test_profile_warning_goes_to_stderr(self):
        with tempfile.TemporaryDirectory() as d:
            paths = []
            for i, text in enumerate([PUNCHY, PUNCHY, PUNCHY, EVEN]):
                p = os.path.join(d, f"s{i}.md")
                with open(p, "w") as fh:
                    fh.write(text)
                paths.append(p)
            r = self.run_cli("profile", *paths, "--out", os.path.join(d, "v.json"))
            self.assertEqual(r.returncode, 0)
            self.assertIn("s3.md", r.stderr)
            self.assertIn("different register", r.stderr)

    def test_missing_file_is_2(self):
        self.assertEqual(self.run_cli("compare", "nope.md", "--profile", "nope.json").returncode, 2)

    def test_example_profile_and_draft(self):
        ex = os.path.join(ROOT, "examples")
        samples = sorted(os.path.join(ex, "samples", f) for f in os.listdir(os.path.join(ex, "samples")))
        with tempfile.TemporaryDirectory() as d:
            prof = os.path.join(d, "voice.json")
            self.assertEqual(self.run_cli("profile", *samples, "--out", prof).returncode, 0)
            r = self.run_cli("compare", os.path.join(ex, "off-voice-draft.md"), "--profile", prof)
            self.assertEqual(r.returncode, 1, r.stdout)


if __name__ == "__main__":
    unittest.main()
