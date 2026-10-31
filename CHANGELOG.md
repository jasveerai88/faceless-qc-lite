# Changelog

## v1.0.0 — 2026-10-31
- First public release: 3 checks (loudness vs −14 LUFS ±2, dead air, black frames ≥0.5s).
- Exit codes for pipelines: 0 PASS, 2 HOLD, 1 error.
- Local only: Python 3.10+ stdlib + FFmpeg, no dependencies, no network, no telemetry.
- Verified: unit tests 2/2; real run caught a −21.6 LUFS file before upload.
