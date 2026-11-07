#!/usr/bin/env python3
"""Build the combined-suite fixture set in a target dir.

    python3 examples/make_fixture.py TARGET_DIR

One planted problem per module, so a `suite` run over the
set exercises every section:

- video.mp4 (8s, 640x360): a very quiet track (anchor
  loudness HOLD), a 3.5s black + silent gap mid-story
  (anchor black-frames WARN, dead-air WARN; retention dead
  zone), and a landscape frame for a Shorts spec check
  (retention platform spec).
- captions.srt: one readable cue and one cue far over
  30 CPS (anchor caption-speed HOLD, caption-toolkit HOLD).
- "My Video Thumb.png" (320x180): low resolution and
  spaces in the filename (thumbnail-checker findings).
- catalogue.json: a goo.gl link (dead-domain) and an
  example.com placeholder (link-rot findings, exit 1).
- title.txt: an over-100-character Shorts title with
  hashtags (shorts-packager overflow/truncation).

Needs ffmpeg on PATH. Everything is generated locally;
no file is downloaded.
"""
import json
import subprocess
import sys
from pathlib import Path


def build(target):
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)

    video = target / "video.mp4"
    filt = (
        "[1:a]volume=0.15[a1];"
        "[3:a]atrim=0:3.5,asetpts=N/SR/TB[a2];"
        "[5:a]volume=0.15[a3];"
        "[0:v][a1][2:v][a2][4:v][a3]concat=n=3:v=1:a=1[v][a]"
    )
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=2",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-f", "lavfi", "-i", "color=c=black:size=640x360:rate=30:duration=3.5",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=2.5",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2.5",
        "-filter_complex", filt,
        "-map", "[v]", "-map", "[a]",
        "-t", "8", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", str(video),
    ]
    subprocess.run(cmd, check=True)

    (target / "captions.srt").write_text(
        "1\n"
        "00:00:00,000 --> 00:00:02,000\n"
        "Welcome back to the channel.\n"
        "\n"
        "2\n"
        "00:00:06,000 --> 00:00:06,500\n"
        "This caption races past far too quickly for anyone to "
        "read it at all.\n",
        encoding="utf-8")

    thumb = target / "My Video Thumb.png"
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", "color=c=red:size=320x180",
         "-frames:v", "1", str(thumb)], check=True)

    catalogue = [{
        "id": "fixture-1",
        "title": "Fixture video",
        "description": (
            "Old sponsor link: https://goo.gl/abc123\n"
            "My training plan: https://example.com/plan\n"
            "A fine link: https://github.com/jasveerai88/faceless-qc-lite"
        ),
    }]
    (target / "catalogue.json").write_text(
        json.dumps(catalogue, indent=2), encoding="utf-8")

    (target / "title.txt").write_text(
        "I Tried the Hardest Faceless Video Challenge for "
        "Thirty Days and the Results Were Honestly Unbelievable",
        encoding="utf-8")
    print(f"fixture set built in {target}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    build(sys.argv[1])
