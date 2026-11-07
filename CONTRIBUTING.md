# Contributing

Thanks for looking. faceless-qc-lite v2.0.0 is a merged
suite: one anchor checker with five absorbed check
modules, one dispatcher. Contributions that keep each
module's scope sharp — and the merge honest — are
welcome.

## Ground rules

- **Standard library only.** No third-party dependencies,
  no network calls, ever — in any module or in the
  dispatcher. (link-rot's defining rule: it never fetches
  a link; a test pins the absence of network code.)
- **The engines are ported, not rewritten.** Each
  module's checks, verdict words, thresholds, and honesty
  limits are its source tool's contract, and each engine
  file is byte-identical to its source. A behaviour change
  to a module belongs upstream in that module's own test
  suite first: its ported suite here must keep passing,
  and any intentional divergence must be named in
  CHANGELOG.md, never silent.
- **The anchor's command line is frozen.**
  `faceless-qc-lite VIDEO [--captions FILE]` keeps its
  v1.x behaviour and exit codes (0 PASS, 2 HOLD, 1 error).
  New capability goes in a subcommand or in `suite`.
- **Deterministic, always.** No LLM, no randomness, no
  timestamps in any receipt: the same inputs must produce
  a byte-identical report on every run.
- **Read-only checking, always.** No check (module or
  combined) may write to the video, its sidecars, or the
  catalogue it audits. The only writers are
  caption-toolkit's `fix` / `repair`, run directly by the
  user, exactly as in the source tool — and `suite` must
  never call them.
- **Skipped is not passed.** A module with nothing to
  check reports itself skipped with a reason. Never let
  the combined verdict count a skipped module as
  evidence an upload is ready.
- **Tests must not depend on the checkout.** The full
  suite must pass in a copy with every file's executable
  bit stripped: tests establish their own fixture
  permissions, generated media, and temp dirs, and never
  rely on $HOME state or machine-specific paths.
- **No tracebacks, ever.** Bad input is a clean
  `{"error": ...}` with the module's own error exit
  code — including argument errors in `--json` mode, at
  dispatcher and module level alike.

## Running the tests

```bash
python3 -m unittest discover -s tests
```

Needs Python 3.10+ and ffmpeg/ffprobe on PATH (the
anchor and retention tests generate and measure real
media files).
