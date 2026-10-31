import subprocess, sys
from pathlib import Path
SRC = Path(__file__).parent.parent / "src" / "faceless_qc_lite.py"

def run(*args):
    return subprocess.run([sys.executable, str(SRC), *args], capture_output=True, text=True)

def test_missing_file_is_clean_error():
    r = run("nope-does-not-exist.mp4")
    assert r.returncode == 1 and "file not found" in r.stdout

def test_help_works():
    r = subprocess.run([sys.executable, str(SRC), "--help"], capture_output=True, text=True)
    assert r.returncode == 0 and "3 free checks" in r.stdout

if __name__ == "__main__":
    test_missing_file_is_clean_error(); test_help_works(); print("2/2 PASS")
