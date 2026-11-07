---
name: faceless-qc-lite
description: Pre-upload QC suite for faceless / AI-narrated video — the anchor's 5 checks (loudness, dead air, black frames, caption speed, resolution) plus caption structural QA, thumbnail checks, retention/platform-spec checks, Shorts title packaging and an offline description-link audit, as one command with one combined `suite` receipt. Use on a finished video (and its captions, thumbnail, title, catalogue) before uploading it.
---

# faceless-qc-lite — agent skill (v2.0.0 suite)

## Purpose

One pre-upload gate for a faceless video and everything that
ships with it. The anchor checks the video file itself;
the five absorbed modules check the captions file, the
thumbnail, the retention shape, the Shorts title line and
the channel's description links. Every module keeps its
source tool's verdict words and honesty limits; the `suite`
run combines them into one receipt without upgrading any
module's verdict.

## When to use / not use

Use when:
- A video is finished and about to be uploaded; you need
  one verdict over the video + captions + thumbnail +
  title (+ link catalogue) before it goes public.
- You need any single module's measurement as data
  (LUFS, silence timestamps, caption CPS, thumbnail
  dimensions, title fit, link classes).

Do not use when:
- You need transcription, caption writing, thumbnail
  editing, or title rewriting — the suite measures and
  packages; it does not create (caption `fix`/`repair`
  adjust timing/structure only, never wording).
- You need link liveness — `links` is structural and
  offline by design; it never fetches anything.
- ffmpeg/ffprobe are not installed — the anchor and
  retention checks then cannot measure (loudness etc.
  report SKIP / the retention tool ERRORs by design); the
  suite will not guess.

## Commands

```bash
# The anchor, exactly as in v1.x (exit 0 PASS, 2 HOLD, 1 error)
faceless-qc-lite video.mp4 [--captions video.srt]
faceless-qc-lite check video.mp4 [--captions video.srt]

# Modules (each accepts --json; run <command> --help)
faceless-qc-lite captions check|fix|lint|repair|convert FILE...
faceless-qc-lite thumbnail thumb.png
faceless-qc-lite retention video.mp4 [--captions F] [--title T] [--platform P]
faceless-qc-lite package --title "Title" [--hashtags "#a #b"]
faceless-qc-lite links audit|links CATALOGUE.json

# The combined pre-upload run
faceless-qc-lite suite video.mp4 [--captions F] [--thumbnail IMG] \
    [--title T] [--hashtags H] [--platform P] [--catalogue F] [--json]
```

## The `suite` receipt

- JSON mode: one object — `tool`, `version`, `command`
  (`"suite"`), `video`, `sections`, `summary`, `verdict`,
  `exit_code`. Each section is the module's **own** JSON
  object (the anchor's section is built from its own check
  functions: `checks` with name/status/value/note plus its
  `verdict`), each with its `exit_code` added.
- A module with nothing to run on is
  `{"status": "skipped", "reason": ..., "verdict": null}` —
  thumbnail without `--thumbnail`, package without
  `--title`, links without `--catalogue`, captions with no
  file and no sidecar. `summary` counts `modules_run` /
  `modules_skipped` and lists the skipped names.
- Suite verdict ranking (the only new logic): a module
  HOLD or FAIL, or an errored module, makes the suite
  HOLD (exit 2); any WARN — including a packager
  TRUNCATED and link-rot findings (exit 1 there) — makes
  it PASS WITH WARNINGS (exit 0); else PASS (exit 0).
  A missing video file is an error (exit 1, the anchor's
  own convention).

## Limits & honesty rules the agent must respect

- **A HOLD is a hold, a SKIP is not a pass.** Never present
  an upload as ready when the suite (or any module) HOLDs
  or FAILs it, and never count a skipped module as
  evidence — say what was not checked.
- **Each module's words stay its own.** Quote a module's
  verdict in its own vocabulary (thumbnail FAIL is not a
  "hold"; link-rot's buckets are "cannot work as written"
  vs "worth checking live", never "dead" / "works").
- **The suite never upgrades or softens.** The combined
  verdict is a ranking of the modules' verdicts, not a
  re-judgement; if you quote numbers, quote the module
  section they came from.
- **Read-only.** The suite never modifies the video, its
  sidecars or the catalogue. caption `fix`/`repair` write
  only when run directly as module commands.
- Local only: everything is measured on this machine;
  nothing is sent anywhere.
