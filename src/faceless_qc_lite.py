#!/usr/bin/env python3
"""Faceless QC Lite — free, open-source pre-upload checker for faceless videos.

3 checks, local only, no uploads, no accounts:
  1. Loudness   — integrated LUFS vs the -14 LUFS streaming target (+/-2)
  2. Dead air   — longest silence inside the story (ending excluded)
  3. Black frames — black segments >= 0.5s inside the story

Needs: Python 3.10+ and FFmpeg on PATH.
Exit codes: 0 PASS, 2 HOLD, 1 error.
The full Faceless QC (pause intelligence, caption speed, HTML worst-3
report) is a separate paid product — this Lite tool always stays free.
"""
import argparse, re, subprocess, sys
from pathlib import Path

def run_ffmpeg(args):
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args],
                          capture_output=True, text=True)

def check_loudness(path):
    r = run_ffmpeg(["-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"])
    m = re.findall(r"I:\s+(-?\d+(?:\.\d+)?) LUFS", r.stderr)
    if not m:
        return ("SKIP", None, "could not measure loudness")
    i = float(m[-1])
    status = "PASS" if -16 <= i <= -12 else "HOLD"
    return (status, i, f"integrated loudness {i:.1f} LUFS (target -14 +/-2)")

def check_dead_air(path, duration):
    r = run_ffmpeg(["-i", str(path), "-af",
                    "silencedetect=noise=-35dB:d=0.5", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    longest, where = 0.0, None
    for s, e in zip(starts, ends):
        # exclude trailing silence in the last 1.5s (outro fade is normal)
        if duration and s > duration - 1.5:
            continue
        if e - s > longest:
            longest, where = e - s, s
    if longest > 4:
        return ("HOLD", longest, f"dead air {longest:.1f}s at {where:.1f}s (HOLD > 4s)")
    if longest > 2.5:
        return ("WARN", longest, f"silence {longest:.1f}s at {where:.1f}s (warn > 2.5s)")
    return ("PASS", longest, f"longest in-story silence {longest:.1f}s")

def check_black(path):
    r = run_ffmpeg(["-i", str(path), "-vf",
                    "blackdetect=d=0.5:pix_th=0.10", "-an", "-f", "null", "-"])
    hits = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", r.stderr)
    if hits:
        s, e = hits[0]
        return ("WARN", len(hits), f"{len(hits)} black segment(s), first {float(s):.1f}s-{float(e):.1f}s")
    return ("PASS", 0, "no black segments >= 0.5s")

def probe_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None

def main(argv=None):
    ap = argparse.ArgumentParser(description="Faceless QC Lite — 3 free checks for faceless videos")
    ap.add_argument("video", help="video file to check")
    a = ap.parse_args(argv)
    p = Path(a.video)
    if not p.is_file():
        print(f"ERROR: file not found: {p}")
        return 1
    dur = probe_duration(p)
    checks = [("Loudness", check_loudness(p)),
              ("Dead air", check_dead_air(p, dur)),
              ("Black frames", check_black(p))]
    verdict = "PASS"
    print(f"Faceless QC Lite — {p.name}")
    for name, (status, _val, note) in checks:
        print(f"  [{status}] {name}: {note}")
        if status == "HOLD":
            verdict = "HOLD"
        elif status == "WARN" and verdict == "PASS":
            verdict = "PASS WITH WARNINGS"
    print(f"Verdict: {verdict}")
    return 2 if verdict == "HOLD" else 0

if __name__ == "__main__":
    sys.exit(main())
