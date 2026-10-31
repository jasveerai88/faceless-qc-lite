# Changelog

## v1.2.0 — 2026-10-31
- NEW 5th check: resolution + orientation — reads the frame size; WARN when the short side is below 1080, HOLD below 720. Catches the classic "rendered at the wrong size" mistake before upload.
- Tests now 7/7 (full-HD PASS, low-res HOLD added).
- Real runs: a 1280x720 file rated WARN; a 640x360 file rated HOLD.

## v1.1.0 — 2026-10-31
- NEW 4th check: caption speed — median chars/sec from a .srt/.vtt sidecar (auto-detected beside the video, or --captions). Warn >17 CPS, HOLD median >20 or any line >30. No sidecar = SKIP, never a fake pass.
- Tests now 5/5 (caption parser: slow PASS, fast HOLD, missing sidecar SKIP).
- Real run: sidecar with a racing first caption measured median 38.1 CPS, max 68.0 → HOLD.
- CI fix: the v1.0 workflow's smoke step died under bash -e before it could check the exit code — that is why Actions run #1 showed Failure. Step rewritten to capture the code safely.

## v1.0.0 — 2026-10-31
- First public release: 3 checks (loudness vs −14 LUFS ±2, dead air, black frames ≥0.5s).
- Exit codes for pipelines: 0 PASS, 2 HOLD, 1 error.
- Local only: Python 3.10+ stdlib + FFmpeg, no dependencies, no network, no telemetry.
- Verified: unit tests 2/2; real run caught a −21.6 LUFS file before upload.
