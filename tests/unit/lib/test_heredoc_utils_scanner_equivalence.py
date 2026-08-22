"""Differential + growth tests for Issue #1620 — linear heredoc scanner.

``heredoc_utils`` used to strip heredoc bodies with::

    re.compile(r"<<-?\\s*['\\\"]?(\\w+)['\\\"]?.*?\\n(.*?\\n)*?[ \\t]*\\1\\b", re.DOTALL)

``(.*?\\n)*?`` nests a quantifier inside a lazy repeat, so an unterminated
heredoc makes the engine enumerate every partition of the body — exponential in
body-line count. Measured through the real hook subprocess: 147 characters at
N=21 body lines cost 6.65 s against the deployed ``"timeout": 5`` budget for
``unified_pre_tool.py`` (controls from the same run: terminated heredoc 0.086 s,
``echo hello`` 0.083 s). Exceeding that budget is a *bypass*, not just latency —
measured in a sandbox, both arms, two runs each: an instant-deny hook BLOCKED,
the identical deny behind ``sleep 8`` PROCEEDED.

The replacement is a linear line scanner that emulates the regex
**byte-for-byte**. Its output feeds 7 security gates, so drift silently changes
what they block. This module is the equivalence oracle for that claim.

Why not the house ``{1,N}`` bound used by the four prior ReDoS fixes (#1194,
#1220, #1221, #1222)? Those all bounded a *character class*. This is a
quantifier over a *group*: ``{0,N}`` stays exponential in N **and** silently
stops stripping heredocs past N body lines, weakening the gates the strip
protects. See the ``heredoc_utils`` module docstring.

Test inventory:

A. ``test_differential_equivalence_over_seeded_corpus`` — 50,000 seeded inputs,
   full ``sub("", s)`` output compared against the ORIGINAL regex. Equality,
   never a length inequality. Also asserts the corpus actually covers the
   emulated ``(\\w+)``-backtracking class.
B. ``test_non_emulating_scanner_diverges`` — negative control #1: a scanner
   without the prefix loop MUST diverge on the same corpus, which is the
   justification-of-record that the prefix loop is load-bearing.
C. ``test_old_pattern_still_blows_up`` — negative control #2: the original
   regex must still fail the growth ceilings on the growth-curve input. If it
   goes green the harness stopped measuring.
D. ``test_growth_curve_is_flat`` — the AC ceiling.
E. Nine behaviour pins, exact outputs.

HARD GATE (from the plan): on ANY differential mismatch it is FORBIDDEN to
adjust the oracle, narrow the alphabet, reduce iterations, add an exclusion, or
mark anything xfail/skip. REQUIRED: stop and report the minimal failing input
and both outputs verbatim. A mismatch means an emulation rule is wrong — a
design finding, not a test-tuning problem.

Issue: #1620
"""

from __future__ import annotations

import logging
import random
import re
import sys
import time
from bisect import bisect_left
from pathlib import Path
from typing import Callable, Iterator

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"

if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import heredoc_utils  # noqa: E402
from heredoc_utils import strip_heredoc_content  # noqa: E402

# ---------------------------------------------------------------------------
# The oracle. Defined verbatim HERE, not imported, so it survives deletion of
# ``_HEREDOC_PATTERN`` from the module under test (which AC1 requires).
# ---------------------------------------------------------------------------
_OLD_PATTERN = re.compile(
    r"<<-?\s*['\"]?(\w+)['\"]?.*?\n(.*?\n)*?[ \t]*\1\b",
    re.DOTALL,
)

_WORD_CHAR_RE = re.compile(r"\w")
_WORD_RUN_RE = re.compile(r"\w+")
_WS_RUN_RE = re.compile(r"\s*")
_LEADING_WS_RE = re.compile(r"[ \t]*")

FUZZ_ITERATIONS = 50_000
FUZZ_SEED = 1620
MAX_LINES = 8

# Ceilings from the plan's acceptance criteria.
GROWTH_RATIO_CEILING = 4.0
GROWTH_ABSOLUTE_CEILING_S = 0.05
NON_EMULATING_DIVERGENCE_FLOOR = 0.05
EMULATED_CLASS_HITS_FLOOR = 500


# ---------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------
# THE ALPHABET REQUIREMENT IS LOAD-BEARING — DO NOT TRIM IT.
#
# The emulated behaviour (the regex's ``(\w+)`` giving back characters and
# retrying with a successively shorter PROPER PREFIX of the delimiter) fires
# only when a proper prefix of the delimiter in use appears ALONE as a line
# token: delimiter ``EOF`` closed by a line ``EO`` or ``E``, or delimiter
# ``EOF2`` closed by a line ``EOF``. It does NOT fire on the reverse — a line
# ``EOFX`` never closes ``EOF``, because ``X`` is a word character so ``\b``
# fails.
#
# MEASURED: with the ``EO``-shaped tokens removed, 50,000 iterations cover the
# emulated class ZERO times regardless of iteration count. An alphabet without
# proper prefixes makes this entire module prove nothing, and it would still be
# green. ``test_differential_equivalence_over_seeded_corpus`` therefore asserts
# a coverage floor on the emulated class, not just "no mismatches".
_LINE_ALPHABET = (
    # Heredoc openers — every quoting form the pattern accepts.
    "cat <<EOF > f",
    "cat <<-EOF",
    "cat <<'EOF'",
    'cat <<"EOF"',
    "cat <<EOF2",
    "cat << EOF",
    "cat <<<EOF",
    "x<<E",
    # Closing-line candidates, INCLUDING PROPER PREFIXES (see above).
    "EOF",
    "EO",
    "E",
    "EOF2",
    "\tEOF",
    "  EO",
    "EOF trailing",
    "EOFX",
    # Inert filler.
    "echo hi",
    "print(1)",
    "",
    "  ",
)

_CORPUS_CACHE: list[str] = []


def _corpus() -> list[str]:
    """Build (once) the seeded differential corpus.

    Returns:
        ``FUZZ_ITERATIONS`` command strings of at most ``MAX_LINES`` lines,
        drawn deterministically from ``_LINE_ALPHABET``.
    """
    if _CORPUS_CACHE:
        return _CORPUS_CACHE
    rng = random.Random(FUZZ_SEED)
    for _ in range(FUZZ_ITERATIONS):
        lines = [rng.choice(_LINE_ALPHABET) for _ in range(rng.randint(1, MAX_LINES))]
        text = "\n".join(lines)
        if rng.random() < 0.5:
            text += "\n"
        _CORPUS_CACHE.append(text)
    return _CORPUS_CACHE


def _emulated_class_hits(command: str) -> int:
    """Count oracle matches that closed on a PROPER PREFIX of the delimiter.

    ``group(1)`` is the delimiter the engine actually settled on. The regex is
    greedy on ``(\\w+)``, so ``group(1)`` is a proper prefix of the maximal word
    run at the opener exactly when the character immediately after ``group(1)``
    is itself a word character.

    Args:
        command: The command string to inspect with the ORIGINAL regex.

    Returns:
        Number of matches in ``command`` that used a proper-prefix delimiter.
    """
    hits = 0
    for match in _OLD_PATTERN.finditer(command):
        after = match.end(1)
        if after < len(command) and _WORD_CHAR_RE.match(command, after):
            hits += 1
    return hits


# ---------------------------------------------------------------------------
# Negative control #1: a scanner WITHOUT the prefix loop.
# ---------------------------------------------------------------------------
def _non_emulating_strip(command: str) -> str:
    """Strip heredocs using ONLY the maximal delimiter token — no prefix loop.

    This is the implementation the plan was originally tempted by, and it is
    the control that proves the prefix loop is load-bearing rather than
    defensive decoration. Everything else matches the real scanner; the only
    difference is that the candidate loop is fixed at the full token.

    Args:
        command: The raw Bash command string.

    Returns:
        ``command`` with heredoc bodies removed under the non-emulating rule.
    """
    if not command:
        return command
    n = len(command)

    tok_index: dict[str, list[int]] = {}
    tok_span: dict[int, int] = {}
    line_start = 0
    while True:
        ws_end = _LEADING_WS_RE.match(command, line_start).end()
        word = _WORD_RUN_RE.match(command, ws_end)
        if word is not None:
            tok_index.setdefault(word.group(), []).append(line_start)
            tok_span[line_start] = word.end() - line_start
        newline = command.find("\n", line_start)
        if newline == -1:
            break
        line_start = newline + 1

    out: list[str] = []
    emitted = 0
    pos = 0
    while True:
        start = command.find("<<", pos)
        if start == -1:
            break
        cursor = start + 2
        if cursor < n and command[cursor] == "-":
            cursor += 1
        cursor = _WS_RUN_RE.match(command, cursor).end()
        if cursor < n and command[cursor] in "'\"":
            cursor += 1
        word = _WORD_RUN_RE.match(command, cursor)
        if word is None:
            pos = start + 1
            continue
        starts = tok_index.get(word.group())  # <-- NO prefix loop. That is the point.
        if starts:
            index = bisect_left(starts, word.end())
            if index < len(starts):
                closing = starts[index]
                out.append(command[emitted:start])
                emitted = closing + tok_span[closing]
                pos = emitted
                continue
        pos = start + 1
    out.append(command[emitted:])
    return "".join(out)


# ---------------------------------------------------------------------------
# Timing helpers
# ---------------------------------------------------------------------------
def _unterminated_heredoc(body_lines: int) -> str:
    """Build the growth-curve input: an opener plus N body lines, NO closer.

    Args:
        body_lines: Number of body lines to emit.

    Returns:
        A Bash command string with an unterminated heredoc.
    """
    body = "".join(f"line{i}\n" for i in range(body_lines))
    return "cat <<EOF > f.txt\n" + body


def _measure(fn: Callable[[str], object], payload: str) -> float:
    """Return the best observed per-call wall time for ``fn(payload)``.

    Fast calls are amortised over a batch so timer granularity does not
    dominate; a call that already exceeds 5 ms is reported from a single
    observation, because repeating an exponential case costs seconds.

    Args:
        fn: The callable under measurement.
        payload: The single string argument to pass.

    Returns:
        Seconds per call.
    """
    best = float("inf")
    for _ in range(3):
        started = time.perf_counter()
        fn(payload)
        elapsed = time.perf_counter() - started
        if elapsed > 0.005:
            return elapsed
        best = min(best, elapsed)

    reps = 500
    for _ in range(3):
        started = time.perf_counter()
        for _ in range(reps):
            fn(payload)
        best = min(best, (time.perf_counter() - started) / reps)
    return best


def _iter_pins() -> Iterator[tuple[str, str]]:
    """Yield ``(input, expected_output)`` for the pins with literal outputs."""
    yield "cat <<EOF\nEO\nEOF\n", "cat \n"
    yield "cat <<EOF\necho hi\nEO\n", "cat \n"
    yield "cat <<EOF\nbody\nEOFX\n", "cat <<EOF\nbody\nEOFX\n"
    yield "cat <<EOF\nbody\nEOF trailing text\n", "cat  trailing text\n"
    yield "cat <<<EOF\nbody\nEOF\n", "cat <\n"
    yield "cat <<-EOF\nbody\n\tEOF\n", "cat \n"
    yield "cat <<EOF\nbody line\nanother\n", "cat <<EOF\nbody line\nanother\n"


# ---------------------------------------------------------------------------
# A. Differential equivalence
# ---------------------------------------------------------------------------
def test_differential_equivalence_over_seeded_corpus() -> None:
    """AC2: 50,000 seeded inputs, ZERO mismatches against the original regex.

    The comparison is on the FULL ``sub("", s)`` output, not just the first
    match, so every resume point is validated. The invariant is EQUALITY —
    never a length inequality, which would let the scanner strip more than the
    regex did and hide real command text from all 7 gates.
    """
    corpus = _corpus()
    mismatches: list[tuple[str, str, str]] = []
    emulated_hits = 0

    for command in corpus:
        expected = _OLD_PATTERN.sub("", command)
        actual = strip_heredoc_content(command)
        if actual != expected:
            mismatches.append((command, expected, actual))
        emulated_hits += _emulated_class_hits(command)

    if mismatches:
        worst = min(mismatches, key=lambda item: len(item[0]))
        pytest.fail(
            "STOP AND REPORT (#1620 HARD GATE): the linear scanner diverged "
            f"from the original regex on {len(mismatches)}/{len(corpus)} inputs. "
            "An emulation rule is WRONG. It is FORBIDDEN to adjust the oracle, "
            "narrow the alphabet, reduce iterations, add an exclusion, or "
            "xfail/skip this test.\n"
            f"minimal failing input : {worst[0]!r}\n"
            f"oracle  (old regex)   : {worst[1]!r}\n"
            f"scanner (new)         : {worst[2]!r}"
        )

    # Coverage: the corpus must actually EXERCISE the emulated class. Measured:
    # with the EO-shaped tokens gone this counter is 0 for any iteration count,
    # and the equality assertion above would still be green — proving nothing.
    print(f"[#1620] emulated_class_hits={emulated_hits} over {len(corpus)} inputs")
    assert emulated_hits > EMULATED_CLASS_HITS_FLOOR, (
        f"only {emulated_hits} oracle matches closed on a PROPER PREFIX of the "
        f"delimiter (floor {EMULATED_CLASS_HITS_FLOOR}). The alphabet has lost "
        "its proper-prefix tokens (EO / E / EOF-as-prefix-of-EOF2), so this run "
        "never entered the (\\w+)-backtracking class and PROVED NOTHING. Restore "
        "_LINE_ALPHABET rather than lowering this floor."
    )


# ---------------------------------------------------------------------------
# B. Negative control #1 — the prefix loop is load-bearing
# ---------------------------------------------------------------------------
def test_non_emulating_scanner_diverges() -> None:
    """Negative control #1: dropping the prefix loop MUST break equivalence.

    Without this the differential above is unfalsifiable — a trivially
    equivalent pair of implementations would also pass it. Measured divergence
    for the non-emulating scanner: 8367/50000 (1.67e-1) on this corpus.
    """
    corpus = _corpus()
    divergent = sum(
        1 for command in corpus if _non_emulating_strip(command) != _OLD_PATTERN.sub("", command)
    )
    rate = divergent / len(corpus)
    print(f"[#1620] non_emulating_divergence={divergent}/{len(corpus)} ({rate:.3e})")
    assert rate > NON_EMULATING_DIVERGENCE_FLOOR, (
        f"a scanner WITHOUT the prefix loop diverged on only {divergent}/"
        f"{len(corpus)} inputs ({rate:.3e}), below the {NON_EMULATING_DIVERGENCE_FLOOR} "
        "floor. Either the corpus stopped covering the emulated class or the "
        "control stopped being a control — in both cases the equivalence test "
        "above is no longer evidence."
    )


# ---------------------------------------------------------------------------
# C. Negative control #2 — the harness still measures a real blow-up
# ---------------------------------------------------------------------------
def test_old_pattern_still_blows_up() -> None:
    """Negative control #2: the ORIGINAL regex must fail the growth ceilings.

    If this goes green the growth curve below stopped measuring anything and
    would pass against a still-exponential implementation.

    The curve is taken at N=18 and N=21 rather than N=24: the original regex
    costs ~8.6 s at N=24 (measured), which is not a price a unit suite should
    pay every run. N=21 is already the first size measured OVER the 5 s hook
    budget end-to-end, and it already violates BOTH ceilings the linear
    scanner has to satisfy.
    """
    t18 = _measure(lambda s: _OLD_PATTERN.sub("", s), _unterminated_heredoc(18))
    t21 = _measure(lambda s: _OLD_PATTERN.sub("", s), _unterminated_heredoc(21))
    ratio = t21 / t18 if t18 else float("inf")
    print(f"[#1620] OLD regex t(18)={t18:.4f}s t(21)={t21:.4f}s ratio={ratio:.1f}")

    assert t21 > GROWTH_ABSOLUTE_CEILING_S, (
        f"the ORIGINAL regex took only {t21:.4f}s at N=21, under the "
        f"{GROWTH_ABSOLUTE_CEILING_S}s ceiling the FIXED implementation must meet. "
        "The exponential input stopped being exponential, so the growth curve "
        "test is no longer a measurement."
    )
    assert ratio > GROWTH_RATIO_CEILING, (
        f"the ORIGINAL regex grew only {ratio:.1f}x from N=18 to N=21, under the "
        f"{GROWTH_RATIO_CEILING}x ratio ceiling the FIXED implementation must meet. "
        "The harness is no longer measuring the blow-up it claims to measure."
    )


# ---------------------------------------------------------------------------
# D. Growth curve
# ---------------------------------------------------------------------------
def test_growth_curve_is_flat() -> None:
    """AC3 (library half): ``t(24)/t(18) < 4.0`` and ``t(24) < 0.05s``.

    N=21 is the size first measured over the 5 s hook budget with the old
    regex; N=24 cost ~8.6 s in-library. Both must now be flat.
    """
    t18 = _measure(strip_heredoc_content, _unterminated_heredoc(18))
    t21 = _measure(strip_heredoc_content, _unterminated_heredoc(21))
    t24 = _measure(strip_heredoc_content, _unterminated_heredoc(24))
    ratio = t24 / t18 if t18 else float("inf")
    print(
        f"[#1620] NEW scanner t(18)={t18:.6f}s t(21)={t21:.6f}s t(24)={t24:.6f}s ratio={ratio:.2f}"
    )

    assert t24 < GROWTH_ABSOLUTE_CEILING_S, (
        f"strip_heredoc_content took {t24:.4f}s on a 24-body-line unterminated "
        f"heredoc (ceiling {GROWTH_ABSOLUTE_CEILING_S}s). The PreToolUse budget is "
        "5s and Claude Code PROCEEDS past a timed-out hook, so this is a gate "
        "bypass, not latency."
    )
    assert ratio < GROWTH_RATIO_CEILING, (
        f"growth from N=18 to N=24 was {ratio:.2f}x (ceiling {GROWTH_RATIO_CEILING}x); "
        f"t(18)={t18:.6f}s t(21)={t21:.6f}s t(24)={t24:.6f}s. Superlinear growth in "
        "body-line count means the exponential class is back."
    )


# ---------------------------------------------------------------------------
# E. Behaviour pins (nine)
# ---------------------------------------------------------------------------
def test_pin_longer_prefix_on_later_line_wins() -> None:
    """Pin 1: candidate loop is OUTER, line scan is INNER.

    ``"cat <<EOF\\nEO\\nEOF\\n"`` — the regex prefers the FULL delimiter ``EOF``
    on the LATER line over the shorter prefix ``EO`` on the earlier one,
    because ``(\\w+)`` only gives back characters after every closing position
    has been tried for the current candidate. Oracle span: (4, 16).
    """
    command = "cat <<EOF\nEO\nEOF\n"
    assert _OLD_PATTERN.search(command).span() == (4, 16)
    assert strip_heredoc_content(command) == "cat \n"


def test_pin_shorter_prefix_closes_when_full_delimiter_absent() -> None:
    """Pin 2: with no ``EOF`` line, the prefix ``EO`` closes the heredoc.

    Exact output is ``'cat \\n'`` (5 characters) — the whole body plus the
    ``EO`` token is removed, and only the newline that followed ``EO``
    survives.
    """
    command = "cat <<EOF\necho hi\nEO\n"
    result = strip_heredoc_content(command)
    assert result == "cat \n"
    assert len(result) == 5


def test_pin_nested_openers_and_resume_point() -> None:
    """Pin 3: nested openers, leftmost match, exact resume point.

    NOTE FOR FUTURE READERS — DO NOT "correct" the 27 to 32.

    This value was challenged during plan review as "actually 32". The
    challenge was refuted by re-measurement: it had TRUNCATED the input by
    three lines. On the full 58-character input the oracle span is (13, 44) and
    ``len(sub) == 27``; on the truncated 32-character input the oracle finds no
    match and returns the input unchanged (length 32). Both statements are
    correct about DIFFERENT inputs. Independently reproduced twice.
    """
    command = "print(1)\ncat <<EOF\ncat <<EOF2\ncat <<'EOF'\nEO\necho hi\nEOF2\n"
    assert len(command) == 58
    assert _OLD_PATTERN.search(command).span() == (13, 44)

    result = strip_heredoc_content(command)
    assert result == "print(1)\ncat \necho hi\nEOF2\n"
    assert len(result) == 27
    # The resume point is real command text, not body: both survive.
    assert "echo hi" in result
    assert "EOF2" in result


def test_pin_suffixed_delimiter_does_not_close() -> None:
    """Pin 4: ``EOFX`` never closes ``EOF`` — guards a ``startswith`` shortcut.

    ``\\1\\b`` requires a word boundary after the delimiter and ``X`` is a word
    character, so the closing test is exact-token equality in BOTH directions.
    """
    command = "cat <<EOF\nbody\nEOFX\n"
    assert _OLD_PATTERN.search(command) is None
    assert strip_heredoc_content(command) == command


def test_pin_trailing_text_after_delimiter_survives() -> None:
    """Pin 5: ``\\1\\b`` consumes nothing past the delimiter.

    The rest of the closing line — and its newline — survive. Guards the
    ``match_end = line_start + leading_ws + len(delim)`` reconstruction of
    ``re.sub``'s resume point.
    """
    command = "cat <<EOF\nbody\nEOF trailing text\n"
    assert strip_heredoc_content(command) == "cat  trailing text\n"


def test_pin_overlapping_opener_starts_are_all_considered() -> None:
    """Pin 6: in ``<<<EOF`` the match starts at the SECOND ``<``.

    Guards against a non-overlapping ``str.find`` walk: the opener at the first
    ``<`` fails (``\\w+`` faces ``<``), and the scan must retry at index+1
    rather than skipping past the whole run. Oracle span starts at 5, i.e. the
    second character of the ``<<<`` run that begins at index 4.
    """
    command = "cat <<<EOF\nbody\nEOF\n"
    assert _OLD_PATTERN.search(command).span() == (5, 19)
    assert strip_heredoc_content(command) == "cat <\n"


def test_pin_indented_heredoc_with_tab_closer() -> None:
    """Pin 7: ``<<-`` with a tab-indented closing delimiter still strips.

    ``[ \\t]*`` before ``\\1`` is what makes the POSIX ``<<-`` form work; Bash
    strips leading tabs from the closer for that form.
    """
    command = "cat <<-EOF\nbody\n\tEOF\n"
    assert strip_heredoc_content(command) == "cat \n"


def test_pin_unterminated_heredoc_is_left_unchanged() -> None:
    """Pin 8: no closing delimiter means NO match — the input is unchanged.

    This refutes the ``(or EOF)`` claim the old module preamble made: the
    pattern does NOT strip to end-of-input when the delimiter never appears.
    AC5 also requires that claim to be gone from the source.
    """
    command = "cat <<EOF\nbody line\nanother\n"
    assert _OLD_PATTERN.search(command) is None
    assert strip_heredoc_content(command) == command

    source = (LIB_DIR / "heredoc_utils.py").read_text(encoding="utf-8")
    assert "or EOF" not in source, (
        "heredoc_utils.py still claims the pattern strips 'to the matching "
        "delimiter on its own line (or EOF)'. It does not — an unterminated "
        "heredoc yields no match at all (AC5, #1620)."
    )


def test_pin_fail_open_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin 9: empty input round-trips; an internal error returns input unchanged.

    The public contract is fail-OPEN: a strip failure must never crash the
    PreToolUse hook. The gates that consume the output fall back to the raw
    command, which over-blocks loudly rather than permitting silently.
    """
    assert strip_heredoc_content("") == ""

    def _boom(_: str) -> object:
        raise RuntimeError("injected scanner failure")

    monkeypatch.setattr(heredoc_utils, "_build_line_index", _boom)
    command = "cat <<EOF\nbody\nEOF\n"
    assert strip_heredoc_content(command) == command


def _scanner_failure_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Return only the DEBUG records emitted by ``heredoc_utils`` itself.

    Filtering on ``record.module`` keeps the assertion immune to unrelated
    DEBUG chatter from other libraries active during the test run.
    """
    return [record for record in caplog.records if record.module == "heredoc_utils"]


def test_fail_open_failure_emits_debug_log(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """FINDING-1: the fail-open path is fail-OPEN but not fail-SILENT.

    Positive control for the observability guard. A scanner that starts raising
    would otherwise degrade the strip to a permanent no-op with no signal —
    invisible to logs, metrics and alerts. The injection seam here is
    ``_scan_openers``, a DIFFERENT seam from the one
    ``test_pin_fail_open_contract`` uses, so the pair covers both halves of the
    scanner rather than the one function that happened to be convenient.
    """

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise IndexError("injected scanner failure")

    monkeypatch.setattr(heredoc_utils, "_scan_openers", _boom)
    command = "cat <<EOF\nbody\nEOF\n"

    with caplog.at_level(logging.DEBUG):
        result = strip_heredoc_content(command)

    # Fail-open behaviour is unchanged: the input round-trips untouched.
    assert result == command

    records = _scanner_failure_records(caplog)
    assert records, (
        "strip_heredoc_content swallowed a scanner failure without logging. "
        "A broken scanner must leave an observability trail (#1620 FINDING-1)."
    )
    assert all(record.levelno == logging.DEBUG for record in records)
    message = records[0].getMessage()
    assert "heredoc scanner failed" in message
    assert "injected scanner failure" in message
    assert records[0].exc_info is not None, "the log must carry exc_info=True"


def test_success_path_emits_no_debug_log(caplog: pytest.LogCaptureFixture) -> None:
    """Negative control: a healthy strip logs NOTHING.

    Without this arm the positive test above cannot distinguish "logs on
    failure" from "logs unconditionally", and a log that always fires carries
    no signal about scanner health.
    """
    command = "cat <<EOF\nbody\nEOF\ntail"

    with caplog.at_level(logging.DEBUG):
        result = strip_heredoc_content(command)
        empty = strip_heredoc_content("")

    # The strip actually did its job — this is a success path, not a no-op.
    assert result != command
    assert empty == ""
    assert _scanner_failure_records(caplog) == [], (
        "heredoc_utils logged on a SUCCESSFUL strip; the DEBUG record must "
        "mark scanner failure only (#1620 FINDING-1)."
    )


@pytest.mark.parametrize(("command", "expected"), list(_iter_pins()))
def test_pins_match_the_oracle_exactly(command: str, expected: str) -> None:
    """Every literal pin above is also what the ORIGINAL regex produces.

    Guards against a pin being written to match the implementation rather than
    the specification.
    """
    assert _OLD_PATTERN.sub("", command) == expected


# ---------------------------------------------------------------------------
# F. Structural ACs
# ---------------------------------------------------------------------------
def test_exponential_pattern_is_gone() -> None:
    """AC1: ``_HEREDOC_PATTERN`` no longer exists in the module."""
    assert not hasattr(heredoc_utils, "_HEREDOC_PATTERN"), (
        "_HEREDOC_PATTERN is still defined; the exponential regex must be "
        "deleted, not merely bypassed (#1620 AC1)."
    )
    source = (LIB_DIR / "heredoc_utils.py").read_text(encoding="utf-8")
    assert "(.*?\\n)*?" not in source


def test_public_surface_unchanged() -> None:
    """AC1: signature and ``__all__`` are preserved for all 7 call sites."""
    import inspect

    assert heredoc_utils.__all__ == ["strip_heredoc_content"]
    signature = inspect.signature(strip_heredoc_content)
    assert list(signature.parameters) == ["command"]
    assert signature.return_annotation in (str, "str")


def test_scanner_helpers_exist() -> None:
    """AC1: the linear scanner is what backs ``strip_heredoc_content``."""
    assert callable(heredoc_utils._build_line_index)
    assert callable(heredoc_utils._scan_openers)
