"""Tests for the anchor, Faceless QC Lite.

Ported from the anchor repo's tests/test_lite.py (7 checks).
The source file is a pytest-style function suite with a
__main__ runner; here the same seven checks, with the same
fixtures and the same assertions, are wrapped as unittest
methods so the whole suite runs under one
`python3 -m unittest discover -s tests`. Nothing about what
is asserted changed — only the harness.
"""
import importlib.util, subprocess, sys, tempfile, unittest
from pathlib import Path
SRC = Path(__file__).parent.parent / "src" / "faceless_qc_lite.py"
spec = importlib.util.spec_from_file_location("lite", SRC)
lite = importlib.util.module_from_spec(spec); spec.loader.exec_module(lite)

SLOW_SRT = """1
00:00:00,000 --> 00:00:04,000
Hello and welcome back

2
00:00:04,000 --> 00:00:08,000
This caption is easy to read
"""
FAST_SRT = """1
00:00:00,000 --> 00:00:01,000
This caption races past far too quickly for anyone to read it at all

2
00:00:01,000 --> 00:00:02,000
Another extremely fast caption that nobody could possibly finish reading
"""

def run(*args):
    return subprocess.run([sys.executable, str(SRC), *args], capture_output=True, text=True)

def _caption_status(srt_text):
    with tempfile.TemporaryDirectory() as d:
        cap = Path(d) / "caps.srt"; cap.write_text(srt_text)
        video = Path(d) / "v.mp4"; video.write_bytes(b"x")
        return lite.check_captions(video, str(cap))[0]

class AnchorTest(unittest.TestCase):
    def test_missing_file_is_clean_error(self):
        r = run("nope-does-not-exist.mp4")
        self.assertEqual(r.returncode, 1)
        self.assertIn("file not found", r.stdout)

    def test_help_works(self):
        r = subprocess.run([sys.executable, str(SRC), "--help"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("5 free checks", r.stdout)

    def test_captions_slow_passes(self):
        self.assertEqual(_caption_status(SLOW_SRT), "PASS")

    def test_captions_fast_holds(self):
        self.assertEqual(_caption_status(FAST_SRT), "HOLD")

    def test_captions_missing_sidecar_skips(self):
        with tempfile.TemporaryDirectory() as d:
            video = Path(d) / "v.mp4"; video.write_bytes(b"x")
            self.assertEqual(lite.check_captions(video, None)[0], "SKIP")

    def test_resolution_full_hd_passes(self):
        self.assertEqual(lite.classify_resolution(1080, 1920)[0], "PASS")

    def test_resolution_low_holds(self):
        self.assertEqual(lite.classify_resolution(640, 360)[0], "HOLD")

if __name__ == "__main__":
    unittest.main()
