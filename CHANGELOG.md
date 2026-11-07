# Changelog

## v2.0.0 — 2026-11-07

- **The merge story, honestly.** The fleet audit
  (FLEET-AUDIT-2026-11-04) ordered 18 quiet tools merged
  into 4 flagships; flagship B2 makes faceless-qc-lite
  the anchor of a video-QC suite. Five tools that used
  to be separate installs — **caption-toolkit**,
  **thumbnail-checker**, **retention-checker**,
  **shorts-packager** and **link-rot** — are now check
  modules of this suite: one install, one pre-upload
  run, one QC receipt, instead of six separate tools
  answering one question ("is this upload ready?") in
  six places.
- **Engines ported byte-identical.** No check, verdict,
  threshold, or honesty limit changed in the merge. The
  anchor's engine file is byte-identical to the one
  that has shipped in this repo since v1.2.0, and each
  module's engine file is byte-identical to its source
  tool's. Each module still reports its own source
  version inside its own output (caption-toolkit
  v0.3.0, thumbnail-checker v0.2.0, retention-checker
  v0.2.0, shorts-packager v0.2.0, link-rot v0.1.0) —
  2.0.0 is the suite's version.
- **The anchor's command line is untouched.**
  `faceless-qc-lite VIDEO [--captions FILE]` (and
  `python3 src/faceless_qc_lite.py VIDEO ...` from a
  checkout) behaves exactly as v1.x did, same exit
  codes (0 PASS, 2 HOLD, 1 error). The new subcommands
  — captions, thumbnail, retention, package, links —
  and the combined `suite` run are additions, not
  changes.
- **The combined `suite` run** runs the anchor check
  plus every module that applies to the inputs given
  and prints one receipt. A module with nothing to run
  on reports SKIPPED with its reason and is never
  counted as a pass. Suite levels are ranked from each
  module's own verdict words; only the ranking is new.
- **241 tests: 220 carried + 21 new.** The six source
  suites carried over (anchor 7, caption-toolkit 50,
  thumbnail-checker 28, retention-checker 53,
  shorts-packager 22, link-rot 60) plus 21 new
  dispatcher/suite tests. The one harness conversion,
  named plainly: the anchor's tests were pytest-style
  functions with a `__main__` runner; the same seven
  checks with the same assertions are now unittest
  methods so one discover run covers everything. The
  ported test files for caption-toolkit, link-rot and
  retention-checker differ from their sources by their
  example-path lines only (examples now live
  per-module under `examples/<module>/`);
  thumbnail-checker's and shorts-packager's test files
  are byte-identical.
- **First PyPI release.** The distribution name is
  unchanged — `faceless-qc-lite` — and v2.0.0 is its
  first publication on PyPI, via Trusted Publishing
  (OIDC, no stored tokens). The console command is
  `faceless-qc-lite`, now routed through the suite
  dispatcher; the anchor behaviour behind it is the
  v1.x behaviour.
- **No upload side effects.** The suite never modifies
  the video or its sidecars. caption-toolkit's fix and
  repair still write when you run them directly,
  exactly as they always did; `suite` never calls
  them.
- SPONSOR-REWARDS.md is carried over unchanged.

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
