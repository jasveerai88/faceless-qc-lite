#!/usr/bin/env python3
"""shorts-packager — fit a YouTube Shorts title into 100 characters.

Rule (standing): a Shorts title line (title + any hashtags placed in it)
must be <= 100 characters. Characters are counted the way a viewer sees
them — one visible character (a grapheme cluster) = 1. A flag emoji, a
ZWJ family emoji, a skin-tone emoji, or a letter with a combining accent
each count as 1, not as their raw Unicode code points.

The title's own wording is never altered to make hashtags fit — hashtags
that do not fit move to the description. If the title alone is already
>100 chars, it is truncated at a word boundary when one exists and a
warning says so; if no word boundary exists (a single word longer than
the limit), it is cut mid-word and the warning says exactly that —
a boundary cut is never claimed when a mid-word cut happened.

An empty or blank title is an error (exit 2), never a PASS — including
when hashtags are supplied, since hashtags alone are not a title.

Stdlib only. No network, no files written, no data leaves the machine.
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata

__version__ = "0.2.0"

LIMIT = 100
CREDITS_PLACEHOLDER = "Credits: [add your sources / credits here]"


class EmptyTitleError(ValueError):
    """Raised when the title is empty or blank — a clean error, not a PASS."""


# --------------------------------------------------------------------------
# Grapheme-cluster counting (SP-3): count what a viewer sees.
# Pure stdlib approximation of UAX #29 covering the cases in the spec:
# combining marks, variation selectors, ZWJ sequences, regional-indicator
# (flag) pairs, and skin-tone modifiers.
# --------------------------------------------------------------------------

def _is_cluster_extend(ch: str) -> bool:
    cp = ord(ch)
    if unicodedata.category(ch) in ("Mn", "Mc", "Me"):
        return True  # combining marks (incl. keycap U+20E3, category Me)
    if 0xFE00 <= cp <= 0xFE0F or 0xE0100 <= cp <= 0xE01EF:
        return True  # variation selectors
    if 0x1F3FB <= cp <= 0x1F3FF:
        return True  # skin-tone modifiers
    if 0xE0020 <= cp <= 0xE007F:
        return True  # tag characters
    return False


def _is_regional_indicator(ch: str) -> bool:
    return 0x1F1E6 <= ord(ch) <= 0x1F1FF


def grapheme_clusters(text: str) -> list[str]:
    """Split text into visible-character (grapheme) clusters."""
    clusters: list[str] = []
    prev_zwj = False
    for ch in text:
        if not clusters:
            clusters.append(ch)
            prev_zwj = ch == "\u200d"
            continue
        join = False
        if _is_cluster_extend(ch):
            join = True
        elif ch == "\u200d":
            join = True  # the ZWJ itself belongs to the current cluster
        elif prev_zwj:
            join = True  # the char after a ZWJ joins the sequence
        elif (
            _is_regional_indicator(ch)
            and len(clusters[-1]) == 1
            and _is_regional_indicator(clusters[-1])
        ):
            join = True  # two regional indicators pair up into one flag
        if join:
            clusters[-1] += ch
        else:
            clusters.append(ch)
        prev_zwj = ch == "\u200d"
    return clusters


def grapheme_len(text: str) -> int:
    """Number of visible characters in text (grapheme clusters)."""
    return len(grapheme_clusters(text))


# --------------------------------------------------------------------------
# Control characters (SP-5): a printed title never contains a raw newline.
# --------------------------------------------------------------------------

def _replace_control_chars(text: str) -> tuple[str, bool]:
    """Replace control characters (category Cc: \\n, \\t, \\r, ...) with a
    space. Returns (cleaned_text, was_changed)."""
    out: list[str] = []
    changed = False
    for ch in text:
        if unicodedata.category(ch) == "Cc":
            out.append(" ")
            changed = True
        else:
            out.append(ch)
    return "".join(out), changed


# --------------------------------------------------------------------------
# Hashtags (SP-4): valid tokens only, single leading #, case-insensitive
# dedupe keeping the first form.
# --------------------------------------------------------------------------

def _is_valid_hashtag_core(core: str) -> bool:
    """A hashtag body must be letters/digits/underscore and contain at
    least one letter or digit ('_' alone is not a hashtag)."""
    if not core:
        return False
    if not all(c.isalnum() or c == "_" for c in core):
        return False
    return any(c.isalnum() for c in core)


def _normalize_hashtags(raw) -> tuple[list[str], list[str]]:
    """Accept a string ('#a #b' or '#a,#b') or a list.

    Returns (tags, rejected). Each tag is normalised to a single leading
    '#'; invalid tokens ('#' alone, punctuation, ...) are returned in
    `rejected` instead of being silently accepted. Duplicates are removed
    case-insensitively, keeping the first form seen.
    """
    if raw is None:
        return [], []
    if isinstance(raw, str):
        parts = raw.replace(",", " ").split()
    else:
        parts = []
        for item in raw:
            parts.extend(str(item).replace(",", " ").split())
    tags: list[str] = []
    rejected: list[str] = []
    seen: set[str] = set()
    for p in parts:
        p = p.strip()
        if not p:
            continue
        core = p.lstrip("#")  # normalise to exactly one leading '#'
        if not _is_valid_hashtag_core(core):
            rejected.append(p)
            continue
        key = core.casefold()
        if key not in seen:
            seen.add(key)
            tags.append("#" + core)
    return tags, rejected


# --------------------------------------------------------------------------
# Truncation (SP-2): the warning must tell the truth about how it cut.
# --------------------------------------------------------------------------

def _truncate_detail(text: str, limit: int = LIMIT) -> tuple[str, bool, bool]:
    """Return (truncated, was_truncated, mid_word_cut).

    Lengths are grapheme (visible-character) counts. A mid-word cut is
    reported as such — never dressed up as a word-boundary cut.
    """
    if grapheme_len(text) <= limit:
        return text, False, False
    clusters = grapheme_clusters(text)
    cut_clusters = clusters[:limit]
    cut = "".join(cut_clusters)
    # If the next cluster is a space or we are exactly at a boundary, fine.
    if clusters[limit] == " " or cut.endswith(" "):
        return cut.rstrip(), True, False
    # Back off to the last space inside the limit.
    idx = -1
    for i, cl in enumerate(cut_clusters):
        if cl == " ":
            idx = i
    if idx > 0:
        return "".join(cut_clusters[:idx]).rstrip(), True, False
    # Single word longer than the limit: hard cut is unavoidable, flag it.
    return cut, True, True


def truncate_at_word_boundary(text: str, limit: int = LIMIT) -> tuple[str, bool]:
    """Return (truncated, was_truncated).

    Cuts at a word boundary when one exists inside the limit; only when
    no boundary exists (one word longer than the limit) does it cut
    mid-word. Kept for backward compatibility — pack() uses
    _truncate_detail() so its warning can say which kind of cut happened.
    """
    truncated, was_truncated, _mid_word = _truncate_detail(text, limit)
    return truncated, was_truncated


# --------------------------------------------------------------------------
# Packing
# --------------------------------------------------------------------------

def pack(title: str, hashtags=None, hook: str | None = None) -> dict:
    raw_title = title or ""
    cleaned_title, had_control = _replace_control_chars(raw_title)
    title = cleaned_title.strip()
    if not title:
        # SP-1: empty/blank title (incl. hashtags-only) is an error.
        raise EmptyTitleError(
            "title is empty — provide a non-empty title "
            "(hashtags alone are not a title)"
        )
    if all(tok.startswith("#") and _is_valid_hashtag_core(tok.lstrip("#"))
           for tok in title.split()):
        # SP-1b: hashtags typed INTO the title itself ("#cats #dogs")
        # are still hashtags alone — no word content, same empty error.
        raise EmptyTitleError(
            "title is empty — provide a non-empty title "
            "(hashtags alone are not a title)"
        )
    tags, rejected_tags = _normalize_hashtags(hashtags)
    warnings: list[str] = []
    verdict = "PASS"

    if had_control:
        warnings.append(
            "Control characters (newline, tab or other control characters) "
            "in the title were replaced with spaces — a printed title never "
            "contains a raw newline or tab."
        )
    for bad in rejected_tags:
        warnings.append(
            f"Ignored invalid hashtag {bad!r}: a hashtag must be letters, "
            "digits or underscore with at least one letter or digit, "
            "after a single '#'."
        )

    original_title = title
    was_truncated = False
    mid_word_cut = False
    if grapheme_len(title) > LIMIT:
        title, was_truncated, mid_word_cut = _truncate_detail(title, LIMIT)
        if mid_word_cut:
            warnings.append(
                f"Title alone is {grapheme_len(original_title)} chars (> {LIMIT}) even without hashtags: "
                f"cut mid-word — no word boundary available — to {grapheme_len(title)} chars. "
                "Edit the title wording yourself for a better fit."
            )
        else:
            warnings.append(
                f"Title alone is {grapheme_len(original_title)} chars (> {LIMIT}) even without hashtags: "
                f"truncated at a word boundary to {grapheme_len(title)} chars. "
                "Edit the title wording yourself for a better fit."
            )
        verdict = "TRUNCATED"

    in_title: list[str] = []
    overflow: list[str] = []
    current = title
    # Preserve hashtag order: fill the title in order; once one does not
    # fit, it and every later hashtag go to the description (no reordering).
    filling = True
    for tag in tags:
        candidate = f"{current} {tag}" if current else tag
        if filling and grapheme_len(candidate) <= LIMIT:
            in_title.append(tag)
            current = candidate
        else:
            filling = False
            overflow.append(tag)

    if overflow and verdict == "PASS":
        verdict = "PASS_WITH_OVERFLOW"

    hook_cleaned, _hook_control = _replace_control_chars(hook or "")
    hook_line = hook_cleaned.strip() or title
    desc_lines = [hook_line, ""]
    # Description carries overflow hashtags; if none overflowed, repeat all
    # hashtags there too so the description is still discoverable.
    desc_tags = overflow if overflow else tags
    if desc_tags:
        desc_lines.append(" ".join(desc_tags))
        desc_lines.append("")
    desc_lines.append(CREDITS_PLACEHOLDER)
    description = "\n".join(desc_lines)

    return {
        "title": current,
        "title_length": grapheme_len(current),
        "limit": LIMIT,
        "base_title": title,
        "original_title": original_title,
        "truncated": was_truncated,
        "mid_word_cut": mid_word_cut,
        "hashtags_in_title": in_title,
        "hashtags_overflow": overflow,
        "hashtags_rejected": rejected_tags,
        "description": description,
        "hook": hook_line,
        "warnings": warnings,
        "verdict": verdict,
    }


def format_result(r: dict) -> str:
    lines = []
    lines.append(f"Title ({r['title_length']}/{r['limit']}): {r['title']}")
    lines.append(f"Verdict: {r['verdict']}")
    lines.append(
        f"Hashtags in title: {len(r['hashtags_in_title'])}"
        + (f" ({' '.join(r['hashtags_in_title'])})" if r["hashtags_in_title"] else "")
    )
    lines.append(
        f"Hashtags overflow to description: {len(r['hashtags_overflow'])}"
        + (f" ({' '.join(r['hashtags_overflow'])})" if r["hashtags_overflow"] else "")
    )
    for w in r["warnings"]:
        lines.append(f"WARNING: {w}")
    lines.append("")
    lines.append("Description:")
    lines.append("---")
    lines.append(r["description"])
    lines.append("---")
    return "\n".join(lines)


def result_as_json(r: dict) -> dict:
    """The pack() result as one JSON-ready object for --json mode.

    Mirrors exactly what format_result() shows a human: the same
    verdict, the same numbers, the same warnings — nothing added,
    nothing softened.
    """
    return {
        "tool": "shorts-packager",
        "version": __version__,
        "verdict": r["verdict"],
        "title": r["title"],
        "title_length": r["title_length"],
        "limit": r["limit"],
        "original_title": r["original_title"],
        "base_title": r["base_title"],
        "truncated": r["truncated"],
        "mid_word_cut": r["mid_word_cut"],
        "hashtags_in_title": r["hashtags_in_title"],
        "hashtags_overflow": r["hashtags_overflow"],
        "hashtags_rejected": r["hashtags_rejected"],
        "hook": r["hook"],
        "description": r["description"],
        "checks": [
            {
                "name": "Title length",
                "status": "TRUNCATED" if r["truncated"] else "PASS",
                "title_length": r["title_length"],
                "limit": r["limit"],
                "message": (
                    f"final title is {r['title_length']}/{r['limit']} "
                    "visible characters"
                ),
            },
            {
                "name": "Hashtag placement",
                "status": "PASS_WITH_OVERFLOW" if r["hashtags_overflow"] else "PASS",
                "in_title": len(r["hashtags_in_title"]),
                "overflow_to_description": len(r["hashtags_overflow"]),
                "rejected": len(r["hashtags_rejected"]),
                "message": (
                    f"{len(r['hashtags_in_title'])} hashtag(s) in the title, "
                    f"{len(r['hashtags_overflow'])} overflow to the description, "
                    f"{len(r['hashtags_rejected'])} rejected as invalid"
                ),
            },
        ],
        "warnings": r["warnings"],
    }


class _JsonAwareParser(argparse.ArgumentParser):
    """ArgumentParser that reports usage errors as JSON in --json mode.

    An agent driving this tool with --json must never be handed plain
    text or a traceback: a usage error becomes {"error": ...} on
    stdout with the same exit code (2) argparse would have used.
    """

    json_mode = False

    def error(self, message):
        if self.json_mode:
            print(json.dumps({"error": message}))
            self.exit(2)
        super().error(message)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ap = _JsonAwareParser(description="Fit a YouTube Shorts title into 100 characters.")
    ap.json_mode = "--json" in argv
    ap.add_argument("--title", required=True, help="Video title (exact wording is preserved)")
    ap.add_argument("--hashtags", default="", help='Hashtags, e.g. "#shorts #viral" or "#shorts,#viral"')
    ap.add_argument("--hook", default=None, help="Optional first line for the description")
    ap.add_argument("--json", action="store_true",
                    help="Print one JSON object (verdict, checks, warnings) "
                         "instead of the human-readable report")
    args = ap.parse_args(argv)
    try:
        result = pack(args.title, args.hashtags, hook=args.hook)
    except EmptyTitleError as e:
        if args.json:
            print(json.dumps({"error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result_as_json(result), indent=2, ensure_ascii=False))
    else:
        print(format_result(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
