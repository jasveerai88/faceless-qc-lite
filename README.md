# Faceless QC Lite

**Free pre-upload checker for AI / faceless videos.** Drop in a finished MP4 — get a plain-English PASS / HOLD in seconds. Local only: your video is never uploaded anywhere.

## The 3 free checks
1. **Loudness** — integrated LUFS vs the −14 streaming target (±2).
2. **Dead air** — longest in-story silence (warn >2.5s, HOLD >4s; outro fade excluded).
3. **Black frames** — black segments ≥0.5s in the story.

## Use
Needs Python 3.10+ and FFmpeg on PATH. No accounts, no API keys.
```
python3 src/faceless_qc_lite.py my-video.mp4
```
Exit codes: 0 PASS, 2 HOLD, 1 error — drop it straight into a publish pipeline.

## Why this exists
Built from measured failure data on real faceless channels: videos most often die because they are too quiet, have a dead gap mid-story, or flash black frames — and most creators only find out after upload.

## Lite vs full Faceless QC
Lite (this repo, free forever, MIT) is the 3 checks above.
The full Faceless QC adds: too-few-pauses intelligence, caption-speed checking, dynamics (LRA), an HTML report naming the worst 3 moments with timestamps, and one-click launchers.

## Sponsor this work
If Lite saves you one bad upload, consider sponsoring — sponsorships fund new checks and keep Lite free: use the **Sponsor** button above (GitHub Sponsors: @jasveerai88).

## Privacy
Runs 100% locally. No telemetry, no accounts, no tracking, nothing uploaded.
