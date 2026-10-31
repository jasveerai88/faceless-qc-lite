#!/usr/bin/env python3
"""Faceless QC Lite — free, open-source pre-upload checker for faceless videos.

5 checks, local only, no uploads, no accounts:
  1. Loudness   — integrated LUFS vs the -14 LUFS streaming target (+/-2)
  2. Dead air   — longest silence inside the story (ending excluded)
  3. Black frames — black segments >= 0.5s inside the story
  4. Caption speed — median chars/sec from a .srt/.vtt sidecar (SKIP if none)
  5. Resolution — frame size + orientation (HOLD if the short side < 720px)

Needs: Python 3.10+ and FFmpeg on PATH.
Exit codes: 0 PASS, 2 HOLD, 1 error.
The full Faceless QC (pause intelligence, full caption gates, dynamics,
HTML worst-3 report) is a separate paid product — Lite always stays free.
"""
import argparse, re, statistics, subprocess, sys
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

def _ts_to_sec(ts):
    ts = ts.replace(",", ".")
    parts = [float(x) for x in ts.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]

def parse_captions(path):
    """Return a list of CPS (chars per second) values, one per caption event."""
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    events = []
    for m in re.finditer(r"(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}|\d{1,2}:\d{2}[.,]\d{1,3})\s*-->\s*"
                         r"(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}|\d{1,2}:\d{2}[.,]\d{1,3})([^\n]*)\n(.*?)(?=\n\s*\n|\Z)",
                         text, re.S):
        start, end = _ts_to_sec(m.group(1)), _ts_to_sec(m.group(2))
        body = re.sub(r"<[^>]+>", "", m.group(4)).strip()
        body = "\n".join(l for l in body.splitlines() if "-->" not in l and not l.strip().isdigit())
        dur = end - start
        if dur > 0 and body:
            events.append(len(body.replace("\n", " ")) / dur)
    return events

def check_captions(video, captions_arg):
    cap = None
    if captions_arg:
        cap = Path(captions_arg)
        if not cap.is_file():
            return ("SKIP", None, f"captions file not found: {captions_arg}")
    else:
        for ext in (".srt", ".vtt"):
            side = video.with_suffix(ext)
            if side.is_file():
                cap = side
                break
    if cap is None:
        return ("SKIP", None, "no captions sidecar (.srt/.vtt) — skipped, not passed")
    cps = parse_captions(cap)
    if not cps:
        return ("SKIP", None, f"no caption events parsed from {cap.name}")
    med, mx = statistics.median(cps), max(cps)
    if med > 20 or mx > 30:
        return ("HOLD", med, f"caption speed median {med:.1f} CPS, max {mx:.1f} (HOLD: median >20 or max >30)")
    if med > 17:
        return ("WARN", med, f"caption speed median {med:.1f} CPS, max {mx:.1f} (warn >17)")
    return ("PASS", med, f"caption speed median {med:.1f} CPS, max {mx:.1f} ({len(cps)} captions)")

def classify_resolution(w, h):
    short = min(w, h)
    orient = "vertical" if h > w else ("landscape" if w > h else "square")
    if short < 720:
        return ("HOLD", short, f"{w}x{h} {orient} — short side {short}px is below 720p (HOLD)")
    if short < 1080:
        return ("WARN", short, f"{w}x{h} {orient} — usable, but below 1080p on the short side")
    return ("PASS", short, f"{w}x{h} {orient} — full HD or better")

def check_resolution(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        w, h = (int(x) for x in r.stdout.strip().split(",")[:2])
    except (ValueError, IndexError):
        return ("SKIP", None, "could not read frame size")
    return classify_resolution(w, h)

def probe_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None

def main(argv=None):
    ap = argparse.ArgumentParser(description="Faceless QC Lite — 5 free checks for faceless videos")
    ap.add_argument("video", help="video file to check")
    ap.add_argument("--captions", help="captions sidecar (.srt/.vtt); auto-detected beside the video when omitted")
    a = ap.parse_args(argv)
    p = Path(a.video)
    if not p.is_file():
        print(f"ERROR: file not found: {p}")
        return 1
    dur = probe_duration(p)
    checks = [("Loudness", check_loudness(p)),
              ("Dead air", check_dead_air(p, dur)),
              ("Black frames", check_black(p)),
              ("Caption speed", check_captions(p, a.captions)),
              ("Resolution", check_resolution(p))]
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
