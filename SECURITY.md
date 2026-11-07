# Security Policy

## Reporting a vulnerability

Please report security issues privately through
GitHub's private vulnerability reporting on this
repository (Security → Report a vulnerability) rather
than a public issue.

## Scope notes

faceless-qc-lite is a local-only QC suite:

- It reads the video, captions, thumbnail and catalogue
  files it is handed and measures them with ffmpeg /
  ffprobe; it never uploads anything, makes no network
  calls, and collects no telemetry. link-rot in
  particular contains no network code at all — its audit
  is structural, and a clean audit means "well-formed as
  written", never "this link loads".
- The only commands that write are caption-toolkit's
  `fix` and `repair`, run directly by the user: they
  write the output file they name (or the documented
  sibling filename) and never touch the input. The
  combined `suite` run never calls them.
- A PASS verdict from any module means "none of the
  problems this module checks were found", within the
  limits each report prints. It is not a guarantee that
  a video will perform, comply with platform policy, or
  be safe in any broader sense.
