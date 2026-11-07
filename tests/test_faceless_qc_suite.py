"""Tests for the faceless_qc_suite dispatcher (new in v2.0.0).

Routing, the anchor's frozen command line, and the combined
`suite` run: sections, honest skips, verdict ranking, JSON
shape. Media tests generate a tiny video with ffmpeg and
skip cleanly when ffmpeg is absent.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[1]
SRC = PACK_ROOT / "src" / "faceless_qc_suite.py"
sys.path.insert(0, str(PACK_ROOT / "src"))

import faceless_qc_suite as suite  # noqa: E402

FAST_SRT = """1
00:00:00,000 --> 00:00:00,500
This caption races past far too quickly for anyone to read it at all.
"""

HAS_FFMPEG = shutil.which("ffmpeg") and shutil.which("ffprobe")


def run_cli(*argv):
    return subprocess.run([sys.executable, str(SRC), *argv],
                          capture_output=True, text=True)


def make_video(path, seconds=2):
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"testsrc2=size=320x240:rate=30:duration={seconds}",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", str(path)], check=True)


class RoutingTest(unittest.TestCase):
    def test_help(self):
        r = run_cli()
        self.assertEqual(r.returncode, 0)
        self.assertIn("suite", r.stdout)
        self.assertIn("captions", r.stdout)

    def test_version(self):
        r = run_cli("--version")
        self.assertEqual(r.returncode, 0)
        self.assertIn("faceless-qc-lite v2.0.0", r.stdout)

    def test_anchor_bare_route_missing_file(self):
        # The anchor's own v1.x behaviour: exit 1, clean error.
        r = run_cli("nope-does-not-exist.mp4")
        self.assertEqual(r.returncode, 1)
        self.assertIn("file not found", r.stdout)

    def test_check_route_missing_file(self):
        r = run_cli("check", "nope-does-not-exist.mp4")
        self.assertEqual(r.returncode, 1)
        self.assertIn("file not found", r.stdout)

    def test_anchor_help_via_check(self):
        r = run_cli("check", "--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("5 free checks", r.stdout)

    def test_module_route_package_json(self):
        r = run_cli("package", "--title", "Cats React", "--json")
        self.assertEqual(r.returncode, 0)
        data = json.loads(r.stdout)
        self.assertEqual(data["tool"], "shorts-packager")
        self.assertEqual(data["verdict"], "PASS")

    def test_module_route_links_error_json(self):
        r = run_cli("links", "audit", "nope-missing.json", "--json")
        self.assertEqual(r.returncode, 2)
        self.assertIn("error", json.loads(r.stdout))

    def test_module_help_delegates(self):
        r = run_cli("captions", "--help")
        self.assertEqual(r.returncode, 0)

    def test_unknown_option_json_error(self):
        r = run_cli("--bogus", "--json")
        self.assertEqual(r.returncode, 2)
        self.assertIn("error", json.loads(r.stdout))

    def test_suite_missing_video_json(self):
        r = run_cli("suite", "nope-does-not-exist.mp4", "--json")
        self.assertEqual(r.returncode, 1)
        self.assertIn("error", json.loads(r.stdout))

    def test_suite_usage_error_json(self):
        r = run_cli("suite", "--json")
        self.assertEqual(r.returncode, 2)
        self.assertIn("error", json.loads(r.stdout))


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg/ffprobe not on PATH")
class SuiteRunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.video = self.dir / "clip.mp4"
        make_video(self.video)

    def tearDown(self):
        self.tmp.cleanup()

    def suite_json(self, *extra):
        r = run_cli("suite", str(self.video), "--json", *extra)
        return r, json.loads(r.stdout)

    def test_skips_are_honest(self):
        r, data = self.suite_json()
        self.assertEqual(data["tool"], "faceless-qc-lite")
        self.assertEqual(data["command"], "suite")
        skipped = data["summary"]["skipped"]
        for name in ("caption-toolkit", "thumbnail-checker",
                     "shorts-packager", "link-rot"):
            self.assertIn(name, skipped)
            self.assertEqual(data["sections"][name]["status"], "skipped")
            self.assertTrue(data["sections"][name]["reason"])
        self.assertEqual(data["summary"]["modules_skipped"], 4)
        self.assertEqual(data["summary"]["modules_run"], 2)

    def test_anchor_section_shape(self):
        _r, data = self.suite_json()
        sec = data["sections"]["faceless-qc-lite"]
        self.assertEqual([c["name"] for c in sec["checks"]],
                         ["Loudness", "Dead air", "Black frames",
                          "Caption speed", "Resolution"])
        self.assertIn(sec["verdict"],
                      ("PASS", "PASS WITH WARNINGS", "HOLD"))

    def test_fast_captions_hold_the_suite(self):
        (self.dir / "clip.srt").write_text(FAST_SRT)
        r, data = self.suite_json()
        self.assertEqual(data["sections"]["caption-toolkit"]["verdict"], "HOLD")
        self.assertEqual(data["verdict"], "HOLD")
        self.assertEqual(r.returncode, 2)

    def test_text_receipt_renders(self):
        r = run_cli("suite", str(self.video))
        self.assertIn("suite receipt", r.stdout)
        self.assertIn("[SKIP] thumbnail-checker:", r.stdout)
        self.assertIn("Suite verdict:", r.stdout)

    def test_repeat_json_byte_identical(self):
        r1 = run_cli("suite", str(self.video), "--json")
        r2 = run_cli("suite", str(self.video), "--json")
        self.assertEqual(r1.stdout, r2.stdout)

    def test_title_runs_packager(self):
        _r, data = self.suite_json("--title", "A Perfectly Fine Title")
        self.assertNotIn("shorts-packager", data["summary"]["skipped"])
        self.assertEqual(data["sections"]["shorts-packager"]["verdict"], "PASS")

    def test_missing_catalogue_is_an_error_section(self):
        r, data = self.suite_json("--catalogue",
                                  str(self.dir / "nope.json"))
        self.assertIn("error", data["sections"]["link-rot"])
        self.assertEqual(data["verdict"], "HOLD")
        self.assertEqual(r.returncode, 2)

    def test_missing_thumbnail_is_the_checkers_own_fail(self):
        _r, data = self.suite_json("--thumbnail",
                                   str(self.dir / "nope.png"))
        self.assertEqual(
            data["sections"]["thumbnail-checker"]["verdict"], "FAIL")

    def test_missing_captions_file_skips_honestly(self):
        _r, data = self.suite_json("--captions",
                                   str(self.dir / "nope.srt"))
        sec = data["sections"]["caption-toolkit"]
        self.assertEqual(sec["status"], "skipped")
        self.assertIn("not found", sec["reason"])
        anchor_cap = [c for c in
                      data["sections"]["faceless-qc-lite"]["checks"]
                      if c["name"] == "Caption speed"][0]
        self.assertEqual(anchor_cap["status"], "SKIP")

    def test_text_receipt_byte_identical(self):
        r1 = run_cli("suite", str(self.video))
        r2 = run_cli("suite", str(self.video))
        self.assertEqual(r1.stdout, r2.stdout)


if __name__ == "__main__":
    unittest.main()
