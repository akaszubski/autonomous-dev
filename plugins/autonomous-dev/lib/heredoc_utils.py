"""Shared heredoc-stripping utility used by hook + classifier code paths.

Extracted from ``unified_pre_tool.py:_strip_heredoc_content`` (Phase 2, Issue
#1153) so the same single source of truth is used everywhere a Bash command is
inspected for risky patterns. Mirrors the extraction precedent set by
``hook_bypass.py`` (lifted from ``unified_pre_tool.py`` and now imported by
many hooks).

This module is intentionally tiny — one public pure function — and has zero
runtime dependencies beyond the standard library. It must remain importable
from both the hook subprocess (where ``plugins/autonomous-dev/hooks/`` is on
``sys.path``) and from ``edit_tier_classifier.py`` (which is loaded by
``importlib.util`` from the hook).

Why a hand-written scanner instead of a regex (Issue #1620)
-----------------------------------------------------------
The original implementation was::

    _HEREDOC_PATTERN = re.compile(
        r"<<-?\\s*['\\\"]?(\\w+)['\\\"]?.*?\\n(.*?\\n)*?[ \\t]*\\1\\b",
        re.DOTALL,
    )

``(.*?\\n)*?`` nests a quantifier inside a lazy repeat. When the closing
delimiter is never found, the engine enumerates every partition of the body —
exponential in body-line count. Measured end-to-end through the real hook
subprocess: a 147-character command with 21 unterminated body lines cost
6.65 s, against ``"timeout": 5`` for ``unified_pre_tool.py`` in the deployed
``.claude/settings.json`` (controls from the same run: an identical-size
TERMINATED heredoc 0.086 s, ``echo hello`` 0.083 s).

Exceeding that budget is a **gate bypass, not latency**. Measured in a sandbox,
both arms, two runs each: an instant-deny PreToolUse hook BLOCKED; the
identical deny behind ``sleep 8`` PROCEEDED. So one over-budget command skips
every gate in ``unified_pre_tool.py`` at once, including the #1435
protected-infrastructure hard floor. The production timing corpus holds 16
historical over-budget events for that hook across five days (max 12.719 s),
predating any probing.

**Do NOT "restore consistency" with the four prior ReDoS fixes.** #1194, #1220,
#1221 and #1222 all bounded a *character class* with ``{1,N}``. That precedent
does NOT transfer here: this was a quantifier over a *group*, so ``{0,N}``
stays exponential in N **and** silently stops stripping heredocs past N body
lines — weakening the 7 security gates that consume this output. The class is
removed, not tuned.

Near-twin left alone deliberately: ``edit_tier_classifier.py``'s
``_HEREDOC_BODY_RE`` uses ``[^\\n]*`` on the opener plus a SINGLE
un-quantified ``(.*?\\n)``; it was verified NOT to be in the exponential class.

How the scanner reproduces the regex byte-for-byte
--------------------------------------------------
The regex's residual freedom, enumerated:

1. ``\\s*`` — FORCED greedy max. Giving back leaves whitespace where ``\\w+``
   needs a word character.
2. First ``['\\"]?`` — FORCED. Backtracking makes ``\\w+`` face a quote.
3. ``(\\w+)`` — FREE, and therefore EMULATED: greedy max, then successively
   shorter proper prefixes (``EOF`` -> ``EO`` -> ``E``).
4. Second ``['\\"]?`` — FREE but empirically harmless, so it is not parsed at
   all. In ``<<EOF'`` the quote may be taken by the optional class or absorbed
   by ``.*?``; both converge on the same first newline because a quote is
   never a newline. 150,000 differential inputs found zero divergence. This is
   NOT "forced" — an earlier draft claimed that and was wrong.
5. ``.*?\\n(.*?\\n)*?`` — subsumed by the position argument below.

Each ``(.*?\\n)`` repetition must end immediately after a ``\\n``, i.e. at a
line start. So the positions reachable after ``.*?\\n(.*?\\n)*?`` are exactly
the line starts strictly greater than the cursor left by the opener, and the
lazy ordering enumerates them in increasing order. Hence ``[ \\t]*\\1\\b`` is
tested at line starts, earliest first, and the exponential partition
enumeration was pure wasted work: it never reached a position the linear scan
does not.

Behaviours that MUST be preserved (each has a pinned test in
``tests/unit/lib/test_heredoc_utils_scanner_equivalence.py``):

1. Prefix emulation, longest prefix first.
2. Candidate loop OUTER, line scan INNER — a longer prefix on a LATER line
   beats a shorter prefix on an EARLIER line, because ``(\\w+)`` only gives
   back after every closing position has been tried for the current candidate.
3. The closing-line test is exact-token equality. ``EOF2`` does not close
   ``EOF`` because ``2`` is a word character, so ``\\b`` fails.
4. ``match_end = line_start + leading_ws + len(delim)``. ``\\1\\b`` consumes
   nothing past the delimiter, so the rest of the closing line and its newline
   survive; this reconstructs ``re.sub``'s resume point.
5. Overlapping ``<<`` starts are all considered — in ``<<<EOF`` index 0 fails
   and index 1 succeeds.
6. Leftmost match wins regardless of length; scanning resumes at ``match_end``,
   non-overlapping. Matches are never empty.

Complexity: O(n) to index, plus O(openers x len(delimiter) x log n) to scan.
``len(delimiter)`` is bounded by the delimiter, not by body-line count — which
is why the exponential class is gone rather than merely bounded.

Issue: #1153, #1620
"""

from __future__ import annotations

import logging
import re
from bisect import bisect_left
from typing import Iterator

# Character classes taken verbatim from the original pattern. They are compiled
# rather than hand-coded (``str.isspace()`` and friends do NOT agree with ``re``
# on every Unicode code point) so the scanner stays byte-for-byte equivalent.
# Each is a single unnested run over a character class: linear, no backtracking.
_WS_RUN_RE = re.compile(r"\s*")  # the opener's ``\s*``
_LEADING_WS_RE = re.compile(r"[ \t]*")  # the closer's ``[ \t]*``
_WORD_RUN_RE = re.compile(r"\w+")  # the delimiter's ``(\w+)``

_QUOTE_CHARS = "'\""


def _build_line_index(command: str) -> tuple[dict[str, list[int]], dict[int, int]]:
    """Index every line of ``command`` by its closing-delimiter token.

    A closing line is ``[ \\t]*`` followed by a maximal ``\\w+`` run. Only that
    token can satisfy ``\\1\\b``, so one pass over the lines is enough to answer
    every later "where does delimiter D close?" query.

    Args:
        command: The raw Bash command string.

    Returns:
        A two-tuple ``(token_index, match_span)`` where ``token_index`` maps a
        line token to the ascending list of line-start offsets carrying it, and
        ``match_span`` maps a line-start offset to ``leading_ws + len(token)``
        — the amount ``\\1`` consumes, so ``line_start + match_span[line_start]``
        is ``re.sub``'s resume point.
    """
    token_index: dict[str, list[int]] = {}
    match_span: dict[int, int] = {}

    line_start = 0
    while True:
        after_ws = _LEADING_WS_RE.match(command, line_start).end()
        word = _WORD_RUN_RE.match(command, after_ws)
        if word is not None:
            token_index.setdefault(word.group(), []).append(line_start)
            match_span[line_start] = word.end() - line_start
        newline = command.find("\n", line_start)
        if newline == -1:
            return token_index, match_span
        line_start = newline + 1


def _scan_openers(
    command: str,
    token_index: dict[str, list[int]],
    match_span: dict[int, int],
) -> Iterator[tuple[int, int]]:
    """Yield ``(match_start, match_end)`` for each heredoc the regex would match.

    Matches are produced leftmost-first and non-overlapping, exactly as
    ``re.sub`` consumes them.

    Args:
        command: The raw Bash command string.
        token_index: Mapping from ``_build_line_index``.
        match_span: Mapping from ``_build_line_index``.

    Yields:
        Half-open ``(start, end)`` offsets of each heredoc match.
    """
    length = len(command)
    pos = 0

    while True:
        start = command.find("<<", pos)
        if start == -1:
            return

        cursor = start + 2
        if cursor < length and command[cursor] == "-":  # ``<<-`` indented form
            cursor += 1
        cursor = _WS_RUN_RE.match(command, cursor).end()  # forced greedy max
        if cursor < length and command[cursor] in _QUOTE_CHARS:  # forced
            cursor += 1

        word = _WORD_RUN_RE.match(command, cursor)
        if word is None:
            # No delimiter here. Advance by ONE so overlapping ``<<`` starts are
            # still considered: in ``<<<EOF`` index 0 fails and index 1 wins.
            pos = start + 1
            continue

        token = word.group()
        # ``word.end()`` is never itself a line start (the preceding character
        # is a word character), and the first line start after it is exactly the
        # position ``.*?\n`` reaches — for EVERY prefix candidate, since the
        # characters given back are word characters and the optional trailing
        # quote is not a newline. So one bisect key serves all candidates.
        body_key = word.end()

        match_end = -1
        # Candidate loop OUTER, line scan INNER: the regex exhausts every
        # closing position for the current delimiter before giving a character
        # back to ``(\w+)``.
        for size in range(len(token), 0, -1):
            starts = token_index.get(token[:size])
            if not starts:
                continue
            index = bisect_left(starts, body_key)
            if index >= len(starts):
                continue
            closing_line = starts[index]
            match_end = closing_line + match_span[closing_line]
            break

        if match_end < 0:
            pos = start + 1
            continue

        yield start, match_end
        pos = match_end


def strip_heredoc_content(command: str) -> str:
    """Remove heredoc bodies from a Bash command string.

    Used to prevent false positives when keyword-like content (commit
    messages, issue bodies, code examples in documentation) appears inside
    a heredoc body that itself sits inside a parent command we are scanning
    for risky patterns (``gh issue create``, ``cat > X.py``, etc.).

    The function is intentionally conservative: it accepts the broadest set
    of well-formed heredoc forms (``<<``, ``<<-``, single-quoted, double-
    quoted, unquoted) and returns the input unchanged on any internal error.
    An unterminated heredoc is NOT stripped — it produces no match at all.

    Args:
        command: The raw Bash command string.

    Returns:
        The command with heredoc body content (between the opening
        delimiter and its closing line) replaced by the empty string.
        Returns the input unchanged when the scanner raises — fail-open, so a
        strip failure can never crash the PreToolUse hook. The gates that
        consume this output then see the raw command, which over-blocks
        loudly rather than permitting silently. That fallback is not silent to
        the engineer: it is logged at DEBUG level with ``exc_info=True``, so a
        scanner regression leaves an observability trail instead of degrading
        the strip to a permanent no-op unnoticed. Check DEBUG logs first when
        diagnosing an apparent under-stripping regression.
    """
    if not command:
        return command
    try:
        token_index, match_span = _build_line_index(command)
        pieces: list[str] = []
        emitted = 0
        for start, end in _scan_openers(command, token_index, match_span):
            pieces.append(command[emitted:start])
            emitted = end
        pieces.append(command[emitted:])
        return "".join(pieces)
    except Exception as exc:
        # Broadened from ``re.error``: the scanner is no longer regex-driven, so
        # an IndexError or a KeyError must fail open the same way the regex
        # error did. Fail-OPEN is the correct behaviour for the 7 gates that
        # consume this output (see the Returns note above) — but it must not be
        # fail-SILENT for the engineer, or a broken scanner degrades the strip
        # to a permanent no-op with no signal. Same precedent as the fail-open
        # catch in ``unified_pre_tool.py`` (#1620).
        logging.debug(
            "heredoc scanner failed, falling back to raw command: %s",
            exc,
            exc_info=True,
        )
        return command


__all__ = ["strip_heredoc_content"]
