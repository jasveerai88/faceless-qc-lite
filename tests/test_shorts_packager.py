import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from shorts_packager import (
    EmptyTitleError,
    __version__,
    format_result,
    grapheme_len,
    main,
    pack,
    truncate_at_word_boundary,
    LIMIT,
)


class TestShortsPackager(unittest.TestCase):
    def test_short_title_all_fits(self):
        r = pack("Cats React to Cucumbers", "#shorts #cats #funny")
        self.assertLessEqual(len(r["title"]), LIMIT)
        self.assertEqual(r["hashtags_overflow"], [])
        self.assertEqual(r["hashtags_in_title"], ["#shorts", "#cats", "#funny"])
        self.assertIn("Cats React to Cucumbers", r["title"])
        self.assertFalse(r["truncated"])
        self.assertEqual(r["verdict"], "PASS")
        self.assertIn("Credits:", r["description"])

    def test_long_title_hashtags_overflow_to_description(self):
        title = "This Goalkeeper Made The Most Impossible Save You Will Ever See In Football History"
        r = pack(title, "#shorts #football #goalkeeper #viral #amazing")
        self.assertLessEqual(len(r["title"]), LIMIT)
        self.assertTrue(len(r["hashtags_overflow"]) >= 1, r)
        # Overflow hashtags must appear in the description
        for tag in r["hashtags_overflow"]:
            self.assertIn(tag, r["description"])
        # Title wording itself is unchanged (base title is a prefix of the result)
        self.assertTrue(r["title"].startswith(title[:20]))

    def test_overlong_title_flagged_and_not_mid_word(self):
        title = ("word " * 30).strip()  # 149 chars, no hashtags needed to overflow
        self.assertGreater(len(title), LIMIT)
        r = pack(title, "#shorts")
        self.assertTrue(r["truncated"])
        self.assertEqual(r["verdict"], "TRUNCATED")
        self.assertTrue(r["warnings"])
        self.assertLessEqual(len(r["base_title"]), LIMIT)
        # Truncation at a word boundary: base title must not end mid-word —
        # the original continues with a space after the truncated text.
        self.assertTrue(title[len(r["base_title"])] == " " or r["base_title"] == title[:LIMIT])

    def test_truncate_helper_never_mid_word(self):
        text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau upsilon phi chi psi omega extra"
        out, was = truncate_at_word_boundary(text, 50)
        self.assertTrue(was)
        self.assertLessEqual(len(out), 50)
        self.assertEqual(text[len(out)], " ")

    def test_custom_hook_and_bare_hashtags(self):
        r = pack("My Title", "shorts viral", hook="You will not believe this save")
        self.assertEqual(r["hashtags_in_title"], ["#shorts", "#viral"])
        self.assertTrue(r["description"].startswith("You will not believe this save"))

    def test_no_hashtags(self):
        r = pack("Simple Title")
        self.assertEqual(r["title"], "Simple Title")
        self.assertEqual(r["verdict"], "PASS")
        self.assertIn("Credits:", r["description"])


class TestBugFixRegressions(unittest.TestCase):
    # ---- SP-1: empty/blank title is an ERROR (exit 2), never a PASS ----
    def test_empty_title_is_error_not_pass(self):
        with self.assertRaises(EmptyTitleError):
            pack("")
        err = io.StringIO()
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            code = main(["--title", ""])
        self.assertEqual(code, 2)
        self.assertIn("empty", err.getvalue().lower())

    def test_blank_and_hashtags_only_title_is_error(self):
        with self.assertRaises(EmptyTitleError):
            pack("   ")
        # Hashtags must not rescue an empty title into a hashtags-only PASS.
        with self.assertRaises(EmptyTitleError):
            pack("", "#shorts #cats")
        err = io.StringIO()
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            code = main(["--title", "   ", "--hashtags", "#shorts"])
        self.assertEqual(code, 2)

    def test_hashtags_inside_title_alone_are_error(self):
        # Mini-fix regression (v0.1.2, SP-1b): hashtags typed INTO --title
        # itself ("#cats #dogs") used to PASS — hashtags alone are not a
        # title no matter which argument they arrive in. Same clean error.
        with self.assertRaises(EmptyTitleError):
            pack("#cats #dogs")
        with self.assertRaises(EmptyTitleError):
            pack("#shorts")
        err = io.StringIO()
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            code = main(["--title", "#cats #dogs"])
        self.assertEqual(code, 2)
        self.assertIn("hashtags alone are not a title", err.getvalue())
        # A real title that merely CONTAINS a hashtag keeps passing.
        r = pack("My cats video #cats")
        self.assertEqual(r["verdict"], "PASS")

    # ---- SP-2: truncation warning must tell the truth ----
    def test_single_word_mid_word_cut_warning_is_honest(self):
        r = pack("a" * 150)
        self.assertTrue(r["truncated"])
        self.assertTrue(r["mid_word_cut"])
        self.assertEqual(r["verdict"], "TRUNCATED")
        joined = " ".join(r["warnings"])
        self.assertIn("cut mid-word", joined)
        self.assertIn("no word boundary available", joined)
        self.assertNotIn("truncated at a word boundary", joined)

    def test_boundary_truncation_warning_says_boundary(self):
        title = ("word " * 30).strip()
        r = pack(title)
        self.assertTrue(r["truncated"])
        self.assertFalse(r["mid_word_cut"])
        self.assertIn("truncated at a word boundary", " ".join(r["warnings"]))

    # ---- SP-3: grapheme-cluster (visible character) counting ----
    def test_grapheme_len_counts_visible_characters(self):
        self.assertEqual(grapheme_len("abc"), 3)
        self.assertEqual(grapheme_len("\U0001F1E8\U0001F1E6"), 1)  # flag: 2 code points, 1 visible char
        self.assertEqual(
            grapheme_len("\U0001F468\u200d\U0001F469\u200d\U0001F467"), 1
        )  # ZWJ family: 5 code points, 1 visible char
        self.assertEqual(grapheme_len("e\u0301"), 1)  # combining accent: 2 code points, 1 visible char
        self.assertEqual(grapheme_len("\U0001F44D\U0001F3FD"), 1)  # skin-tone modifier
        self.assertEqual(grapheme_len("a\U0001F1E8\U0001F1E6b"), 3)

    def test_grapheme_counting_applies_to_100_char_rule(self):
        flags = "\U0001F1E8\U0001F1E6" * 60  # 120 code points, 60 visible chars
        r = pack(flags)
        self.assertFalse(r["truncated"])
        self.assertEqual(r["verdict"], "PASS")
        self.assertEqual(r["title_length"], 60)
        accented = "e\u0301" * 90  # 180 code points, 90 visible chars
        r2 = pack(accented)
        self.assertFalse(r2["truncated"])
        self.assertEqual(r2["title_length"], 90)

    # ---- SP-4: hashtag validation + case-insensitive dedupe ----
    def test_invalid_hashtags_dropped_and_normalised(self):
        r = pack("My Title", "# ##double # ___ #ok!")
        self.assertEqual(r["hashtags_in_title"], ["#double"])
        self.assertIn("#", r["hashtags_rejected"])
        self.assertIn("___", " ".join(r["hashtags_rejected"]))

    def test_hashtag_dedupe_case_insensitive_keeps_first(self):
        r = pack("My Title", "#Cats #cats #CATS #dogs")
        self.assertEqual(r["hashtags_in_title"], ["#Cats", "#dogs"])

    # ---- SP-5: control characters never reach a printed title ----
    def test_control_characters_replaced_in_title(self):
        r = pack("Hello\nWorld\tNow")
        self.assertNotIn("\n", r["title"])
        self.assertNotIn("\t", r["title"])
        self.assertEqual(r["title"], "Hello World Now")
        self.assertTrue(
            any("Control characters" in w for w in r["warnings"]), r["warnings"]
        )
        title_line = format_result(r).splitlines()[0]
        self.assertNotIn("\t", title_line)

    def test_control_only_title_is_empty_error(self):
        with self.assertRaises(EmptyTitleError):
            pack("\n\t\r")


class TestJsonMode(unittest.TestCase):
    """v0.2.0 agent-ready mode: --json emits one JSON object whose
    verdict agrees with human mode; errors are JSON objects, exit 2."""

    def _run_json(self, argv):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = main(argv)
        return code, json.loads(out.getvalue())

    def test_json_parses_with_verdict_and_key_fields(self):
        code, data = self._run_json(
            ["--title", "Cats React to Cucumbers",
             "--hashtags", "#shorts #cats #funny", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(data["tool"], "shorts-packager")
        self.assertEqual(data["version"], __version__)
        self.assertEqual(data["verdict"], "PASS")
        self.assertEqual(data["title_length"], 44)
        self.assertEqual(data["limit"], LIMIT)
        self.assertEqual(data["hashtags_in_title"],
                         ["#shorts", "#cats", "#funny"])
        self.assertEqual(data["hashtags_overflow"], [])
        self.assertEqual(data["warnings"], [])
        self.assertTrue(data["checks"])
        for c in data["checks"]:
            self.assertIn("name", c)
            self.assertIn("status", c)
            self.assertIn("message", c)

    def test_json_verdict_agrees_with_pack_and_human(self):
        title = ("This Goalkeeper Made The Most Impossible Save You Will "
                 "Ever See In Football History")
        tags = "#shorts #football #goalkeeper #viral #amazing"
        code, data = self._run_json(
            ["--title", title, "--hashtags", tags, "--json"])
        expected = pack(title, tags)
        self.assertEqual(code, 0)
        self.assertEqual(data["verdict"], expected["verdict"])
        self.assertEqual(data["verdict"], "PASS_WITH_OVERFLOW")
        self.assertEqual(data["hashtags_overflow"],
                         expected["hashtags_overflow"])
        self.assertEqual(data["title"], expected["title"])
        self.assertEqual(data["description"], expected["description"])

    def test_json_error_case_is_json_object_exit2(self):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = main(["--title", "", "--json"])
        self.assertEqual(code, 2)
        data = json.loads(out.getvalue())  # must parse — never plain text
        self.assertIn("title is empty", data["error"])
        self.assertNotIn("Verdict", out.getvalue())

    def test_json_usage_error_is_json_object_exit2(self):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                main(["--json"])  # missing required --title
        self.assertEqual(cm.exception.code, 2)
        data = json.loads(out.getvalue())
        self.assertIn("error", data)

    def test_human_output_byte_identical_without_json(self):
        argv = ["--title", "Cats React to Cucumbers",
                "--hashtags", "#shorts #cats #funny"]
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = main(argv)
        self.assertEqual(code, 0)
        expected = format_result(
            pack("Cats React to Cucumbers", "#shorts #cats #funny")) + "\n"
        self.assertEqual(out.getvalue(), expected)


if __name__ == "__main__":
    unittest.main()
