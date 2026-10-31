import importlib.util, subprocess, sys, tempfile
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

def test_missing_file_is_clean_error():
    r = run("nope-does-not-exist.mp4")
    assert r.returncode == 1 and "file not found" in r.stdout

def test_help_works():
    r = subprocess.run([sys.executable, str(SRC), "--help"], capture_output=True, text=True)
    assert r.returncode == 0 and "4 free checks" in r.stdout

def _caption_status(srt_text):
    with tempfile.TemporaryDirectory() as d:
        cap = Path(d) / "caps.srt"; cap.write_text(srt_text)
        video = Path(d) / "v.mp4"; video.write_bytes(b"x")
        return lite.check_captions(video, str(cap))[0]

def test_captions_slow_passes():
    assert _caption_status(SLOW_SRT) == "PASS"

def test_captions_fast_holds():
    assert _caption_status(FAST_SRT) == "HOLD"

def test_captions_missing_sidecar_skips():
    with tempfile.TemporaryDirectory() as d:
        video = Path(d) / "v.mp4"; video.write_bytes(b"x")
        assert lite.check_captions(video, None)[0] == "SKIP"

if __name__ == "__main__":
    test_missing_file_is_clean_error(); test_help_works()
    test_captions_slow_passes(); test_captions_fast_holds(); test_captions_missing_sidecar_skips()
    print("5/5 PASS")
