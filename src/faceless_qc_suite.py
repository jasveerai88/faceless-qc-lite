#!/usr/bin/env python3
"""Faceless QC Lite — the suite (v2.0.0).

One pre-upload QC gate for faceless / AI-narrated video. The
anchor is Faceless QC Lite itself — the 5 free checks that
have shipped as faceless-qc-lite since v1.0.0, unchanged —
and five tools that used to be separate installs are now
its check library (FLEET-AUDIT-2026-11-04, flagship B2):

    faceless-qc-lite VIDEO [--captions FILE]
        The anchor's own command line, exactly as it has
        always worked (also spelled `check VIDEO ...`):
        loudness, dead air, black frames, caption speed,
        resolution. Exit 0 PASS, 2 HOLD, 1 error.
    faceless-qc-lite captions check|fix|lint|repair|convert ...
        caption-toolkit: caption speed gates plus the
        structural lint/repair for raw transcription output.
    faceless-qc-lite thumbnail IMAGE
        thumbnail-checker: real dimensions, data integrity,
        aspect, file size, filename SEO for the thumbnail.
    faceless-qc-lite retention VIDEO [--captions F] [--title T]
                                  [--platform P]
        retention-checker: hook window, dead zones, pacing,
        loudness, platform spec on the finished video.
    faceless-qc-lite package --title T [--hashtags H]
        shorts-packager: fit a Shorts title + hashtags into
        the 100-visible-character cap, wording untouched.
    faceless-qc-lite links audit|links CATALOGUE
        link-rot: structural, offline audit of a channel's
        description-link catalogue. It never fetches a link.
    faceless-qc-lite suite VIDEO [--captions F] [--thumbnail IMG]
                                 [--title T] [--hashtags H]
                                 [--platform P] [--catalogue F]
                                 [--json]
        The combined pre-upload run: the anchor check plus
        every module that applies to the inputs given, as
        ONE QC receipt. A module with nothing to run on
        reports SKIPPED with its reason — a skip is never
        counted as a pass.

Every module keeps its source tool's checks, verdict words
and honesty limits — the engines are ported byte-identical,
not rewritten, and each still reports its own source
version inside its own output. Read-only: the suite never
modifies the video or its sidecars (caption-toolkit's fix /
repair write only when you run them yourself, exactly as
they always did; `suite` never calls them).

Needs Python 3.10+ and FFmpeg on PATH (the anchor and
retention checks measure with ffmpeg/ffprobe).
(stdlib only, local only, no network.)
"""

import argparse
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import caption_toolkit
import faceless_qc_lite
import link_rot
import retention_checker
import shorts_packager
import thumbnail_checker

__version__ = "2.0.0"

TOOL = "faceless-qc-lite"

MODULES = {
    "captions": caption_toolkit,
    "thumbnail": thumbnail_checker,
    "retention": retention_checker,
    "package": shorts_packager,
    "links": link_rot,
}

HELP = """usage: faceless-qc-lite <command> [args...]

Faceless QC Lite — the pre-upload QC suite for faceless
video. The anchor check runs exactly as it always has:

  faceless-qc-lite VIDEO [--captions FILE]
  faceless-qc-lite check VIDEO [--captions FILE]
                                 the 5 anchor checks (loudness,
                                 dead air, black frames, caption
                                 speed, resolution); exit 0 PASS,
                                 2 HOLD, 1 error

commands:
  captions  check|fix|lint|repair|convert FILE...
                                 caption speed + structural QA
  thumbnail IMAGE                thumbnail dimensions, integrity,
                                 aspect, size, filename SEO
  retention VIDEO [options]      hook window, dead zones, pacing,
                                 loudness, platform spec
  package   --title T [--hashtags H]
                                 fit a Shorts title into 100 chars
  links     audit|links CATALOGUE
                                 description-link rot audit (offline)
  suite     VIDEO [options]      all of the above that apply, as
                                 one combined QC receipt

Run `faceless-qc-lite <command> --help` for a module's own
options. Every module accepts --json (one JSON object).
Read-only: nothing here modifies your video (captions fix /
repair write only when you run them directly)."""

_LEVEL_RANK = {"pass": 0, "warn": 1, "hold": 2, "error": 3}
_LEVEL_WORD = {"pass": "PASS", "warn": "PASS WITH WARNINGS",
               "hold": "HOLD", "error": "HOLD"}


class ToolError(Exception):
    """A user-facing failure: printed without a traceback.
    Exit code follows the anchor: 1 for a bad input file."""


class _JsonAwareParser(argparse.ArgumentParser):
    """ArgumentParser that reports usage errors as JSON in
    --json mode ({"error": ...} on stdout, exit code 2) —
    the modules' own convention. The flag lives on the
    class so subparsers share it."""

    json_mode = False

    def error(self, message):
        if self.json_mode:
            print(json.dumps({"error": message}))
            self.exit(2)
        super().error(message)


# ---------------------------------------------------------------------------
# In-process module runs
# ---------------------------------------------------------------------------

def _run_capture(module_main, args):
    """Run a module's own CLI in-process and capture what it
    prints. Returns (exit_code, stdout_text). The module's
    main() may raise SystemExit (argparse errors, --help);
    its code is honoured either way."""
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            code = module_main(args)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 2
    return code, buf.getvalue()


def _run_json_section(module_main, args):
    """Run a module in --json mode; its section is the exact
    object the module itself prints, plus its exit code."""
    code, text = _run_capture(module_main, args + ["--json"])
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = {"error": "module produced no JSON output",
                   "raw": text.strip()[:500]}
    payload = dict(payload)
    payload["exit_code"] = code
    return payload


def _skipped_section(reason):
    return {"status": "skipped", "reason": reason,
            "verdict": None, "exit_code": None}


# ---------------------------------------------------------------------------
# The anchor, run through its own check functions
# ---------------------------------------------------------------------------

def _anchor_run(video, captions_arg):
    """Run the anchor's five checks via the anchor module's
    own functions, in its own order, and render both the
    JSON section and the anchor's exact text block from
    that single run. Returns (section, text_block, level).
    """
    p = Path(video)
    dur = faceless_qc_lite.probe_duration(p)
    checks = [("Loudness", faceless_qc_lite.check_loudness(p)),
              ("Dead air", faceless_qc_lite.check_dead_air(p, dur)),
              ("Black frames", faceless_qc_lite.check_black(p)),
              ("Caption speed", faceless_qc_lite.check_captions(p, captions_arg)),
              ("Resolution", faceless_qc_lite.check_resolution(p))]
    verdict = "PASS"
    for _name, (status, _val, _note) in checks:
        if status == "HOLD":
            verdict = "HOLD"
        elif status == "WARN" and verdict == "PASS":
            verdict = "PASS WITH WARNINGS"
    lines = [f"Faceless QC Lite — {p.name}"]
    for name, (status, _val, note) in checks:
        lines.append(f"  [{status}] {name}: {note}")
    lines.append(f"Verdict: {verdict}")
    section = {
        "tool": "faceless-qc-lite",
        "file": p.name,
        "checks": [{"name": name, "status": status,
                    "value": val, "note": note}
                   for name, (status, val, note) in checks],
        "verdict": verdict,
        "exit_code": 2 if verdict == "HOLD" else 0,
    }
    level = "hold" if verdict == "HOLD" else (
        "warn" if verdict == "PASS WITH WARNINGS" else "pass")
    return section, "\n".join(lines), level


# ---------------------------------------------------------------------------
# Combined suite run
# ---------------------------------------------------------------------------

def _module_level(section):
    """Map one module's own verdict words to a suite level.
    The words are the module's; only the ranking is ours."""
    if section.get("status") == "skipped":
        return "skipped"
    if "error" in section:
        return "error"
    verdict = section.get("verdict")
    if verdict in ("HOLD", "FAIL"):
        return "hold"
    if verdict in ("WARN", "TRUNCATED"):
        return "warn"
    if verdict is not None:  # PASS, PASS_WITH_OVERFLOW
        return "pass"
    # link-rot carries no verdict word; its exit code speaks:
    # 1 = actionable findings (attention), 0 = clean.
    return "warn" if section.get("exit_code") == 1 else "pass"


_LABELS = {"faceless-qc-lite": "faceless-qc-lite — the anchor's 5 checks",
           "retention-checker": "retention-checker",
           "caption-toolkit": "caption-toolkit — check",
           "thumbnail-checker": "thumbnail-checker",
           "shorts-packager": "shorts-packager",
           "link-rot": "link-rot — audit"}


def _resolve_captions(video, captions_arg):
    """The captions file the suite can actually use, in the
    anchor's own detection order. Returns (path_or_None,
    missing_note_or_None): an explicitly passed path that
    does not exist is reported, never silently replaced."""
    if captions_arg:
        if Path(captions_arg).is_file():
            return captions_arg, None
        return None, f"captions file not found: {captions_arg}"
    for ext in (".srt", ".vtt"):
        side = Path(video).with_suffix(ext)
        if side.is_file():
            return str(side), None
    return None, None


def suite_run(a):
    """The combined pre-upload run. Returns
    (payload_dict, text_receipt, exit_code)."""
    video = Path(a.video)
    if not video.is_file():
        raise ToolError(f"file not found: {video}")
    want_json = bool(a.json)
    sections, texts, levels = {}, {}, {}

    # The anchor always runs on the video.
    sec, text, level = _anchor_run(video, a.captions)
    sections["faceless-qc-lite"] = sec
    texts["faceless-qc-lite"] = text
    levels["faceless-qc-lite"] = level

    cap_path, cap_missing = _resolve_captions(video, a.captions)

    def add(key, module_main, args):
        # The level always comes from the module's own JSON
        # object — never from parsing its prose. In text mode
        # the module runs a second time for its own human
        # words (every module here is read-only, so the
        # second run is identical, just slower).
        sections[key] = _run_json_section(module_main, args)
        levels[key] = _module_level(sections[key])
        if want_json:
            texts[key] = None
        else:
            _code, text = _run_capture(module_main, args)
            texts[key] = text.rstrip("\n")

    def skip(key, reason):
        sections[key] = _skipped_section(reason)
        texts[key] = f"  [SKIP] {_LABELS[key]}: {reason}"
        levels[key] = "skipped"

    # retention-checker: measures the same video. An explicit
    # captions path is passed only when it exists — retention
    # errors hard on a missing explicit path by design, and
    # its own sidecar auto-detection covers the rest.
    rargs = [str(video)]
    if cap_path:
        rargs += ["--captions", cap_path]
    if a.title is not None:
        rargs += ["--title", a.title]
    if a.platform:
        rargs += ["--platform", a.platform]
    add("retention-checker", retention_checker.main, rargs)

    # caption-toolkit: the `check` gate on the captions file.
    if cap_path:
        add("caption-toolkit", caption_toolkit.main,
            ["check", cap_path])
    elif cap_missing:
        skip("caption-toolkit", cap_missing)
    else:
        skip("caption-toolkit",
             "no captions file supplied and no .srt/.vtt "
             "sidecar beside the video")

    # thumbnail-checker: runs whenever a thumbnail was named
    # (a missing file is its own FAIL verdict, by design).
    if a.thumbnail:
        add("thumbnail-checker", thumbnail_checker.main,
            [a.thumbnail])
    else:
        skip("thumbnail-checker", "no --thumbnail supplied")

    # shorts-packager: runs whenever a title was named.
    if a.title is not None:
        pargs = ["--title", a.title]
        if a.hashtags:
            pargs += ["--hashtags", a.hashtags]
        add("shorts-packager", shorts_packager.main, pargs)
    else:
        skip("shorts-packager", "no --title supplied")

    # link-rot: the catalogue audit, whenever one was named.
    if a.catalogue:
        add("link-rot", link_rot.main, ["audit", a.catalogue])
    else:
        skip("link-rot", "no --catalogue supplied")

    ran = [k for k, lv in levels.items() if lv != "skipped"]
    skipped = [k for k, lv in levels.items() if lv == "skipped"]
    worst = max((_LEVEL_RANK[levels[k]] for k in ran), default=0)
    verdict = _LEVEL_WORD[
        {v: k for k, v in _LEVEL_RANK.items()}[worst]]
    exit_code = 2 if worst >= _LEVEL_RANK["hold"] else 0

    payload = {
        "tool": TOOL,
        "version": __version__,
        "command": "suite",
        "video": video.name,
        "sections": sections,
        "summary": {
            "modules_run": len(ran),
            "modules_skipped": len(skipped),
            "skipped": skipped,
            "attention": [k for k in ran
                          if levels[k] in ("warn", "hold", "error")],
        },
        "verdict": verdict,
        "exit_code": exit_code,
    }

    lines = [f"Faceless QC Lite — suite receipt for {video.name}", ""]
    for key in ("faceless-qc-lite", "retention-checker",
                "caption-toolkit", "thumbnail-checker",
                "shorts-packager", "link-rot"):
        if key != "faceless-qc-lite":
            lines.append(f"== {_LABELS[key]} ==")
        lines.append(texts[key] if texts[key] is not None else "")
        lines.append("")
    att = payload["summary"]["attention"]
    tail = f"Suite verdict: {verdict}"
    if att:
        tail += f" — needs attention: {', '.join(att)}"
    if skipped:
        tail += (f" (skipped, not passed: "
                 f"{', '.join(skipped)})")
    lines.append(tail)
    return payload, "\n".join(lines), exit_code


def _suite_parser():
    ap = _JsonAwareParser(
        prog="faceless-qc-lite suite",
        description="Combined pre-upload QC: the anchor check "
                    "plus every module that applies, one receipt.")
    ap.add_argument("video", help="video file to check")
    ap.add_argument("--captions",
                    help="captions sidecar (.srt/.vtt); "
                         "auto-detected beside the video when omitted")
    ap.add_argument("--thumbnail", help="thumbnail image (PNG/JPEG) to check")
    ap.add_argument("--title", help="planned upload title (retention "
                                    "echo check + Shorts packaging)")
    ap.add_argument("--hashtags", help="hashtags for the Shorts title line")
    ap.add_argument("--platform",
                    help="retention platform spec: youtube-shorts "
                         "(default), youtube-long, tiktok")
    ap.add_argument("--catalogue",
                    help="description-link catalogue (JSON/CSV) to audit")
    ap.add_argument("--json", action="store_true",
                    help="print one JSON object")
    return ap


def cmd_suite(a):
    payload, text, exit_code = suite_run(a)
    if a.json:
        print(json.dumps(payload, indent=2))
    else:
        print(text)
    return exit_code


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(HELP)
        return 0
    if argv[0] in ("-v", "--version"):
        print(f"{TOOL} v{__version__}")
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd in MODULES:
        return MODULES[cmd].main(rest)
    if cmd == "check":
        return faceless_qc_lite.main(rest)
    if cmd == "suite":
        _JsonAwareParser.json_mode = "--json" in rest
        ap = _suite_parser()
        a = ap.parse_args(rest)
        try:
            return cmd_suite(a)
        except ToolError as exc:
            if a.json:
                print(json.dumps({"error": str(exc)}))
            else:
                print(f"ERROR: {exc}")
            return 1
    if cmd.startswith("-"):
        if "--json" in argv:
            print(json.dumps({"error": f"unknown option: {cmd}"}))
        else:
            print(f"ERROR: unknown option: {cmd}")
            print()
            print(HELP)
        return 2
    # Anything else is the anchor's own command line, exactly
    # as it has always worked: faceless-qc-lite VIDEO [--captions F].
    return faceless_qc_lite.main(argv)


if __name__ == "__main__":
    sys.exit(main())
