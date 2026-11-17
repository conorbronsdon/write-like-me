import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from voice_stats import build_profile, compare, edit_diff, export_style, infer_quotes, measure  # noqa: E402

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

    def test_first_person_counts_sentence_initial_my_and_me(self):
        m = measure("My team shipped it. Me too. I agree.")
        self.assertAlmostEqual(m["first_person_per_1k"], 3000 / 8, places=1)

    def test_lowercase_i_is_not_first_person(self):
        self.assertEqual(measure("Press i to insert text here.")["first_person_per_1k"], 0)

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

    def test_short_draft_missing_one_expected_use_is_not_drift(self):
        # Profile uses parentheses at ~4 per 1,000 words; a 150-word draft
        # would expect well under one, so having none is not drift.
        text = ("We moved the service in a weekend and it held. (Mostly.) " +
                "The tests caught two bugs before launch and the rest were small. " * 20)
        prof = build_profile({"a": text, "b": text, "c": text})
        draft = "The tests caught two bugs before launch and the rest were small. " * 12
        feats = {d["feature"] for d in compare(draft, prof)["drifts"]}
        self.assertNotIn("paren_per_1k", feats)

    def test_long_draft_missing_a_frequent_feature_still_drifts(self):
        feats = {d["feature"] for d in compare(EVEN * 3, self.profile)["drifts"]}
        self.assertIn("first_person_per_1k", feats)
        self.assertIn("em_dash_per_1k", feats)

    def test_ranges_are_rounded(self):
        res = compare("One two three four five. " * 7, self.profile)
        for d in res["drifts"]:
            for v in d["range"]:
                self.assertEqual(v, round(v, 2))

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

    def test_one_word_edits_are_noise(self):
        long_s = "The deploy finished and the team went home early that day " * 3
        pairs = [(long_s + "quickly.", long_s + "."), (long_s + "honestly.", long_s + ".")]
        self.assertEqual(edit_diff(pairs)["features"], {})

    def test_identical_pair_reports_nothing(self):
        res = edit_diff([(SENT, SENT)])
        self.assertEqual(res["features"], {})
        self.assertEqual(res["words_cut"], [])


# Vendored from avoid-ai-writing at commit 465d00e0a6004851564e4ca1781eec11d582652e:
#   examples/prose.json -> tests/fixtures/avoid-ai-writing-prose.json (verbatim)
#   scripts/check-style.js KNOWN -> STYLE_MECHANICS below
# https://github.com/conorbronsdon/avoid-ai-writing/tree/465d00e0a6004851564e4ca1781eec11d582652e
STYLE_EXAMPLE = os.path.join(HERE, "fixtures", "avoid-ai-writing-prose.json")
STYLE_MECHANICS = {
    "quotes": ["straight", "curly"],
    "headings": ["sentence", "title"],
    "latinAbbrev": ["parentheses", "never", "any"],
    "emDash": ["sparing", "deliberate", "never"],
    "colons": ["never", "any"],
    "semicolons": ["never", "any"],
    "spellNumbersUpTo": int,
    "serialComma": bool,
}

VOICE_MD = """# Voice profile: Sam

## Summary (hold this in mind while drafting)

1. Says the point first, then the evidence.
2. Short punches between long explanations; spread 9.8 words.
3. States positions flatly; rarely hedges.
4. Names the specific tool, person, and number.
5. No em dashes.

## Never (hard rules: confirmed)
{never}

## Probably never (provisional: absent from the samples, not yet confirmed)
{probably}
"""
NO_DASH = PUNCHY.replace(" — ", ", ").replace("I tried", "I'd tried")  # 0 em dashes
ONE_DASH = NO_DASH + " Then — finally — done. "  # 2 dashes in 723 words
LOW_DASH = NO_DASH * 2 + " Then — done. "  # 1 dash in 1,442 words


def voice_md(never="", probably=""):
    return VOICE_MD.format(never=never, probably=probably)


class ExportStyle(unittest.TestCase):
    def mech(self, samples, md=None):
        return export_style(build_profile(samples), md)["style"]["mechanics"]

    def test_confirmed_em_dash_absence_exports_never(self):
        md = voice_md(never="- Em dashes. Evidence: writer said (2026-11-01).")
        self.assertEqual(self.mech({"a": NO_DASH}, md)["emDash"], "never")

    def test_writer_edited_absence_exports_never(self):
        md = voice_md(never="- Semicolons. Evidence: writer edited: cut in 3 of 3 pairs.\n"
                            "- Colons in prose. Evidence: writer said.")
        mech = self.mech({"a": NO_DASH}, md)
        self.assertEqual(mech["semicolons"], "never")
        self.assertEqual(mech["colons"], "never")
        self.assertNotIn("emDash", mech)

    def test_provisional_absence_exports_nothing(self):
        md = voice_md(probably="- Em dashes. Evidence: 0 of 3 samples.\n"
                               "- Semicolons. Evidence: 0 of 3 samples.")
        mech = self.mech({"a": NO_DASH}, md)
        self.assertNotIn("emDash", mech)
        self.assertNotIn("semicolons", mech)

    def test_never_without_confirming_evidence_is_not_exported(self):
        md = voice_md(never="- Em dashes. Evidence: 0 of 3 samples.")
        res = export_style(build_profile({"a": NO_DASH}), md)
        self.assertNotIn("emDash", res["style"]["mechanics"])
        self.assertEqual(len(res["notes"]), 1)
        self.assertIn("emDash", res["notes"][0])

    def test_semicolon_rule_does_not_imply_colons(self):
        md = voice_md(never="- Semicolons. Evidence: writer said.")
        self.assertNotIn("colons", self.mech({"a": NO_DASH}, md))

    def test_low_nonzero_rate_exports_sparing(self):
        prof = build_profile({"a": LOW_DASH})
        self.assertEqual(prof["pooled"]["em_dash_per_1k"], 0.69)
        self.assertEqual(export_style(prof)["style"]["mechanics"]["emDash"], "sparing")

    def test_normal_rate_exports_no_em_dash_key(self):
        prof = build_profile({"a": ONE_DASH})
        self.assertEqual(prof["pooled"]["em_dash_per_1k"], 2.77)
        self.assertNotIn("emDash", export_style(prof)["style"]["mechanics"])
        self.assertNotIn("emDash", self.mech({"a": PUNCHY}))

    def test_zero_rate_alone_is_not_never(self):
        self.assertNotIn("emDash", self.mech({"a": NO_DASH}))

    def test_summary_becomes_register(self):
        style = export_style(build_profile({"a": NO_DASH}, "newsletter"), voice_md())["style"]
        self.assertEqual(style["register"][0], "Says the point first, then the evidence.")
        self.assertEqual(len(style["register"]), 5)
        self.assertEqual(style["name"], "Voice profile: Sam")
        self.assertEqual(style["genre"], "newsletter")

    def test_unfilled_template_summary_is_skipped(self):
        with open(os.path.join(ROOT, "templates", "voice.md")) as fh:
            style = export_style(build_profile({"a": NO_DASH}), fh.read())["style"]
        self.assertNotIn("register", style)
        self.assertEqual(style["mechanics"], {"quotes": "straight"})

    def test_quotes_inferred_from_samples(self):
        self.assertEqual(infer_quotes("He said “no” and didn’t."),
                         {"double": "curly", "single": "curly"})
        self.assertEqual(infer_quotes("He's 5'11\" tall."), {"double": None, "single": "straight"})
        self.assertEqual(self.mech({"a": "It’s “fine,” she said. " * 30})["quotes"], "curly")
        self.assertEqual(self.mech({"a": NO_DASH})["quotes"], "straight")

    def test_mixed_quote_styles_export_nothing(self):
        self.assertNotIn("quotes", self.mech({"a": "It's “fine,” she said. " * 30}))

    def test_old_profile_without_quotes_still_exports(self):
        prof = build_profile({"a": LOW_DASH})
        del prof["quotes"]
        res = export_style(prof)
        self.assertEqual(res["style"]["mechanics"], {"emDash": "sparing"})
        self.assertIn("quotes", res["notes"][0])

    def test_output_matches_avoid_ai_writing_shape(self):
        with open(STYLE_EXAMPLE) as fh:
            example = json.load(fh)
        md = voice_md(never="- Em dashes, semicolons and colons. Evidence: writer said.")
        style = export_style(build_profile({"a": NO_DASH}, "newsletter"), md)["style"]
        self.assertEqual(style["mechanics"], {"emDash": "never", "semicolons": "never",
                                              "colons": "never", "quotes": "straight"})
        self.assertLessEqual(set(style), set(example))
        for key in style:
            self.assertIs(type(style[key]), type(example[key]), key)
        self.assertTrue(all(isinstance(r, str) for r in style["register"]))
        self.assertLessEqual(set(example["mechanics"]), set(STYLE_MECHANICS))
        for key, value in style["mechanics"].items():
            allowed = STYLE_MECHANICS[key]
            if isinstance(allowed, list):
                self.assertIn(value, allowed, key)
            else:
                self.assertIs(type(value), allowed, key)


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
            empty = os.path.join(d, "empty.md")
            open(empty, "w").close()
            self.assertEqual(self.run_cli("diff", a, empty).returncode, 2)

    def test_empty_draft_is_2(self):
        with tempfile.TemporaryDirectory() as d:
            prof, empty = os.path.join(d, "v.json"), os.path.join(d, "e.md")
            with open(prof, "w") as fh:
                json.dump(build_profile({"a": PUNCHY}), fh)
            open(empty, "w").close()
            r = self.run_cli("compare", empty, "--profile", prof)
            self.assertEqual(r.returncode, 2)
            self.assertIn("no words", r.stderr)

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

    def test_export_style_cli(self):
        with tempfile.TemporaryDirectory() as d:
            paths = []
            for i in range(3):
                p = os.path.join(d, f"s{i}.md")
                with open(p, "w") as fh:
                    fh.write(NO_DASH)
                paths.append(p)
            prof = os.path.join(d, "voice.json")
            self.assertEqual(self.run_cli("profile", *paths, "--out", prof).returncode, 0)
            # The .md beside voice.json is read by default.
            with open(os.path.join(d, "voice.md"), "w") as fh:
                fh.write(voice_md(never="- Em dashes. Evidence: writer said.",
                                  probably="- Semicolons. Evidence: 0 of 3 samples."))
            out = os.path.join(d, "style.json")
            r = self.run_cli("export-style", prof, "--out", out)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(out) as fh:
                style = json.load(fh)
            self.assertEqual(style["mechanics"], {"emDash": "never", "quotes": "straight"})
            self.assertEqual(len(style["register"]), 5)
            empty_md = os.path.join(d, "empty.md")
            open(empty_md, "w").close()
            r = self.run_cli("export-style", prof, "--md", empty_md)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)["mechanics"], {"quotes": "straight"})
            self.assertEqual(self.run_cli("export-style", empty_md).returncode, 2)
            self.assertEqual(self.run_cli("export-style", "nope.json").returncode, 2)

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
