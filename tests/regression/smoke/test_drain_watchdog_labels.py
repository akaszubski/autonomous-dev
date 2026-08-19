"""Regression tests for the drain-watchdog alert-labelling contract.

Issue #1275 (self-loop): drain-watchdog.yml labelled stuck-drain alert issues
with BOTH "drain-stuck" AND "auto-improvement". The watchdog's own detection
logic then picked up those alert issues as drainable auto-improvement work,
creating a fixed-point loop where each heal cycle drained only watchdog
bookkeeping issues while the real backlog never moved.

Issue #1303: the selector-stall alert step reuses the 4h debounce pattern.

Transport note (commit 004b2640, "route [drain-stuck] alerts through
daily_aggregate_manager"): alert-issue creation moved from a raw
``gh issue create --label "drain-stuck"`` shell block to a ``python3``
heredoc calling ``open_or_supersede_daily_aggregate(..., label="drain-stuck")``
(``.github/workflows/drain-watchdog.yml:184-190``). The library still applies
the label via ``gh issue create --label`` (``lib/daily_aggregate_manager.py:158``)
and still keys the duplicate-suppression listing on it (``:76``), so the
behaviour is unchanged — only the syntax moved. The assertions below are
therefore scoped to the *call site*, not to the old CLI string, so they
survive the next transport change and, critically, still fail when the
behaviour is actually removed.

Scoping-generality note: "scoped to the call site" must mean *every* call
site and *every* rendering of the kwarg, not the first one that happens to
exist today. An earlier revision of this file scanned only
``content.find(AGGREGATE_CALL)`` (first match) and captured label values with
a line-bounded ``[^\\n]*``. Both narrowings let a real reintroduction of #1275
pass green: a second aggregate call — the obvious next step for the
selector-stall alert at ``drain-watchdog.yml:285-287``, still a raw
``gh issue create --label "selector-stall,high-priority"`` — was invisible,
and a ``labels=[...]`` literal rendered across lines (what any standard
formatter produces for a 2-element list inside an already-multi-line call)
captured only ``"["``. The helpers below enumerate all call sites and scan
brackets and quotes structurally instead.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

import pytest

# Use parents[3] to walk up: smoke/ -> regression/ -> tests/ -> repo root
WORKFLOW_FILE = (
    Path(__file__).resolve().parents[3] / ".github" / "workflows" / "drain-watchdog.yml"
)

#: The library call that creates/supersedes the daily [drain-stuck] alert issue.
AGGREGATE_CALL = "open_or_supersede_daily_aggregate("

#: Start of a ``label=``/``labels=`` kwarg. The *value* is not captured by regex
#: — see ``_label_kwarg_values`` — because a value may be a multi-line list
#: literal or a quoted string containing commas, neither of which a
#: line-bounded or comma-bounded character class can span.
LABEL_KWARG_RE = re.compile(r"\blabels?\s*=\s*")

#: Opening bracket -> closing bracket, for structural value scanning.
_BRACKET_PAIRS = {"[": "]", "(": ")", "{": "}"}

#: Quote openers, longest-first so triple quotes win over single ones.
_QUOTES = ("'''", '"""', "'", '"')

#: The selector-stall step's own debounce: a ``gh issue list`` scoped to the
#: selector-stall label. Deliberately NOT ``re.DOTALL`` — see
#: ``_has_selector_stall_debounce``.
SELECTOR_STALL_LIST_RE = re.compile(r"gh issue list\b.*?--label\s+selector-stall\b")

#: The debounce window the selector-stall query must search.
SELECTOR_STALL_WINDOW = "4 hours ago"


def _read_workflow() -> str:
    """Return the drain-watchdog workflow source."""
    return WORKFLOW_FILE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Structural scanning helpers
# ---------------------------------------------------------------------------


def _find_matching(text: str, start: int, opener: str, closer: str) -> int | None:
    """Return the index of the closer matching an already-consumed opener.

    The scan is quote-aware: brackets inside quoted Python literals do not
    affect nesting depth. This matters because the workflow passes
    ``title_prefix="[drain-stuck] watchdog"``. A naive depth counter treats a
    ``)`` inside such a literal as a terminator, silently truncating the
    argument blob and hiding every kwarg after it — so
    ``title_prefix="[drain-stuck) watchdog"`` followed by
    ``labels=["auto-improvement"]`` would scan clean.

    Args:
        text: Source to scan.
        start: Index of the first character *after* the opener.
        opener: Opening bracket character.
        closer: Closing bracket character.

    Returns:
        Index of the matching closer, or None if the brackets never balance.
    """
    depth = 1
    cursor = start
    quote: str | None = None
    while cursor < len(text):
        if quote is not None:
            if text[cursor] == "\\":
                cursor += 2
                continue
            if text.startswith(quote, cursor):
                cursor += len(quote)
                quote = None
                continue
            cursor += 1
            continue
        for candidate in _QUOTES:
            if text.startswith(candidate, cursor):
                quote = candidate
                cursor += len(candidate)
                break
        else:
            char = text[cursor]
            if char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if depth == 0:
                    return cursor
            cursor += 1
    return None


def _scan_plain_value(text: str, start: int) -> str:
    """Return an unbracketed kwarg value, stopping at a top-level comma/newline.

    Quote-aware for the same reason as ``_find_matching``: the original #1275
    shape is ``label="drain-stuck,auto-improvement"``, where the comma sits
    *inside* the literal. A comma-bounded character class would truncate it to
    ``"drain-stuck`` and lose the very substring the guard searches for.

    Args:
        text: Source to scan.
        start: Index of the first character of the value.

    Returns:
        The raw value text (unstripped).
    """
    cursor = start
    quote: str | None = None
    while cursor < len(text):
        char = text[cursor]
        if quote is not None:
            if char == "\\":
                cursor += 2
                continue
            if text.startswith(quote, cursor):
                cursor += len(quote)
                quote = None
                continue
            cursor += 1
            continue
        if char in ",\n":
            break
        if char in "'\"":
            quote = char
            cursor += 1
            continue
        cursor += 1
    return text[start:cursor]


def _aggregate_call_arg_blobs(content: str) -> list[str]:
    """Return the argument text of *every* ``open_or_supersede_daily_aggregate`` call.

    Enumerating all call sites (not just the first) is the point: a second
    aggregate call reintroducing the #1275 label pair would otherwise be
    invisible to every guard below.

    Args:
        content: Full drain-watchdog.yml source.

    Returns:
        One argument blob per call site, in source order. Returns ``[]`` when
        the call is absent *and* when any call site fails to balance, so the
        live ``assert label_values`` preconditions fail loudly rather than
        scanning a truncated blob.
    """
    blobs: list[str] = []
    for match in re.finditer(re.escape(AGGREGATE_CALL), content):
        end = _find_matching(content, match.end(), "(", ")")
        if end is None:
            return []
        blobs.append(content[match.end() : end])
    return blobs


def _label_kwarg_values(args: str) -> list[str]:
    """Return every ``label=``/``labels=`` value in one argument blob.

    Args:
        args: Argument text of a single call site.

    Returns:
        Stripped kwarg values. A bracketed value is returned whole, including
        its brackets and any newlines inside it.
    """
    values: list[str] = []
    for match in LABEL_KWARG_RE.finditer(args):
        start = match.end()
        if start >= len(args):
            continue
        opener = args[start]
        if opener in _BRACKET_PAIRS:
            end = _find_matching(args, start + 1, opener, _BRACKET_PAIRS[opener])
            if end is None:
                continue
            values.append(args[start : end + 1])
        else:
            values.append(_scan_plain_value(args, start).strip().rstrip(",").strip())
    return values


def _aggregate_label_values(content: str) -> list[str]:
    """Return every ``label=``/``labels=`` value across all aggregate call sites.

    Scoping to the call sites matters: "auto-improvement" occurs 6 times
    legitimately elsewhere in the workflow (queue queries, prose, triage
    instructions), so an unscoped substring check would fail on contact.

    Args:
        content: Full drain-watchdog.yml source.

    Returns:
        Stripped kwarg values (each may be a quoted string or a list literal).
        Empty list if no call site is present or any is malformed.
    """
    return [
        value
        for blob in _aggregate_call_arg_blobs(content)
        for value in _label_kwarg_values(blob)
    ]


def _step_section(content: str, step_name: str) -> str:
    """Return the YAML body of a named workflow step, or "" if not found."""
    match = re.search(
        rf"- name: {re.escape(step_name)}.*?(?=\n      - name:|\Z)",
        content,
        re.DOTALL,
    )
    return match.group(0) if match else ""


def _logical_commands(section: str) -> list[str]:
    """Collapse backslash-continued shell lines into single logical commands.

    Args:
        section: A workflow step body.

    Returns:
        One entry per logical shell line.
    """
    return re.sub(r"\\\n[ \t]*", " ", section).split("\n")


def _has_selector_stall_debounce(content: str) -> bool:
    """Return True if the selector-stall step carries its own 4h debounce.

    The label query and the 4h window must appear in the *same* backslash-
    continued command. Matching them across the step with ``re.DOTALL`` let
    the window come from anywhere in the 137-line step — the issue-body prose
    is a natural place — so deleting the real ``--search`` line and mentioning
    "4 hours ago" later still read as a debounce.

    Args:
        content: Full drain-watchdog.yml source.

    Returns:
        True when one logical command both lists selector-stall issues and
        searches the 4h window.
    """
    section = _step_section(content, "Detect selector stall")
    if not section:
        return False
    return any(
        SELECTOR_STALL_LIST_RE.search(command) and SELECTOR_STALL_WINDOW in command
        for command in _logical_commands(section)
    )


# ---------------------------------------------------------------------------
# Live assertions — the real workflow file
#
# The three guards controlled below take an optional ``content`` argument
# defaulting to the real file. Controls pass a mutated copy so they exercise
# *the guard*, not a re-implementation of it. pytest ignores parameters that
# have defaults when collecting fixtures, so these still run as plain tests.
# ---------------------------------------------------------------------------


def test_drain_watchdog_does_not_label_stuck_as_auto_improvement(
    content: str | None = None,
) -> None:
    """No label applied to the drain-stuck alert may be 'auto-improvement'.

    Applying 'auto-improvement' to watchdog alert issues causes the watchdog to
    pick them up as drainable work, creating a self-loop: watchdog fires,
    creates a 'drain-stuck' alert issue labelled 'auto-improvement', the next
    heal cycle drains that alert issue, commits a trivial change, but the real
    backlog never moves — and the next cron fire repeats the cycle (Issue #1275).

    Scoped to every aggregate-manager call site. The previous form asserted the
    CLI string "drain-stuck,auto-improvement", which the current code path can
    no longer produce in any circumstance — a guard that could not fail.

    Args:
        content: Workflow source to check. Defaults to the real file; controls
            pass a mutated copy to watch this guard refuse.
    """
    content = _read_workflow() if content is None else content
    label_values = _aggregate_label_values(content)
    assert label_values, (
        f"No label=/labels= kwarg found at {AGGREGATE_CALL} in drain-watchdog.yml — "
        "alert labelling moved again (or a call site is malformed); repoint this "
        "guard to the new call site rather than letting it pass vacuously "
        "(Issue #1275)"
    )
    offenders = [value for value in label_values if "auto-improvement" in value]
    assert not offenders, (
        f"drain-watchdog.yml must not label drain-stuck alert issues as "
        f"auto-improvement (Issue #1275 — causes self-loop). Offending kwarg "
        f"value(s) at the aggregate-manager call site(s): {offenders}"
    )


def test_drain_watchdog_drain_stuck_label_present(content: str | None = None) -> None:
    """The alert issue must still carry the 'drain-stuck' label.

    Positive control: verifies the watchdog label was not removed entirely.
    'drain-stuck' drives the duplicate-suppression listing in
    ``daily_aggregate_manager.open_or_supersede_daily_aggregate`` (``:76``)
    and is applied to the issue at ``:158``.

    Args:
        content: Workflow source to check. Defaults to the real file; controls
            pass a mutated copy to watch this guard refuse.
    """
    content = _read_workflow() if content is None else content
    label_values = _aggregate_label_values(content)
    assert any("drain-stuck" in value for value in label_values), (
        "drain-watchdog.yml must pass label=\"drain-stuck\" to "
        f"{AGGREGATE_CALL} — required for the supersede/debounce filter that "
        f"suppresses duplicate watchdog alerts. Found label kwargs: {label_values}"
    )


def test_drain_watchdog_emits_selector_stall_label() -> None:
    """Issue #1303 — selector-stall alert step labels with selector-stall + high-priority."""
    content = _read_workflow()
    # Accept either inline list or separate label flags
    assert (
        "selector-stall,high-priority" in content
        or ('"selector-stall"' in content and '"high-priority"' in content)
        or ("'selector-stall'" in content and "'high-priority'" in content)
        or ("--label selector-stall" in content and "--label high-priority" in content)
    ), (
        "drain-watchdog.yml must label selector-stall alerts with both "
        "'selector-stall' and 'high-priority' (Issue #1303)"
    )


def test_drain_watchdog_imports_selector_stall_detector() -> None:
    """Issue #1303 — workflow must invoke the selector_stall_detector module."""
    content = _read_workflow()
    assert "selector_stall_detector" in content, (
        "drain-watchdog.yml must import/invoke selector_stall_detector "
        "(Issue #1303 Phase E sub-D)"
    )


def test_drain_watchdog_selector_stall_debounce_present(content: str | None = None) -> None:
    """AC2 — the selector-stall step carries its own 4h debounce.

    Asserts the selector-stall step's debounce directly. The previous form
    counted occurrences of "4 hours ago" across the whole file and required
    ``>= 2``, borrowing the neighbouring drain-stuck debounce as evidence for
    this one. When drain-stuck labelling moved into the aggregate manager that
    neighbour disappeared, and the test failed while its own subject
    (``drain-watchdog.yml:274-283``) was present and correct.

    Args:
        content: Workflow source to check. Defaults to the real file; controls
            pass a mutated copy to watch this guard refuse.
    """
    content = _read_workflow() if content is None else content
    assert _has_selector_stall_debounce(content), (
        "drain-watchdog.yml 'Detect selector stall' step must debounce on its "
        "own label with a 4h window — expected a `gh issue list ... --label "
        "selector-stall` query searching `created:>...4 hours ago` in the same "
        "command (Issue #1303 AC2)"
    )


def test_drain_watchdog_log_lines_bounded_by_head_c() -> None:
    """Issue #1314 LOW-1: LOG_LINES bounded by `head -c 65536` to prevent
    runaway memory on pathologically long commit subjects."""
    content = _read_workflow()
    assert "head -c 65536" in content


def test_drain_watchdog_normalizes_tool_failure_exit_tokens() -> None:
    """Issue #1314 FINDING-2: tool-failure exit tokens (exit=*, *_unavailable)
    are normalized to empty cluster so they don't break the stall streak."""
    content = _read_workflow()
    assert "TOOL_FAILURE_PREFIXES" in content or "'exit='" in content
    assert "TOOL_FAILURE_SUFFIXES" in content or "'_unavailable'" in content


def test_drain_watchdog_selector_stall_step_has_timeout() -> None:
    """Issue #1314 LOW-4: the Detect selector stall step has timeout-minutes
    to prevent runaway hangs."""
    content = _read_workflow()
    step_section = _step_section(content, "Detect selector stall")
    assert step_section, "Could not find 'Detect selector stall' step"
    assert re.search(r"^\s*timeout-minutes:\s*5\s*", step_section, re.MULTILINE), (
        "timeout-minutes: 5 not found in step"
    )


# ---------------------------------------------------------------------------
# Controls — three guards watched both refusing AND permitting
#
# Controlled here: the self-loop guard
# (``test_drain_watchdog_does_not_label_stuck_as_auto_improvement``), the
# positive-label guard (``test_drain_watchdog_drain_stuck_label_present``) and
# the selector-stall debounce guard
# (``test_drain_watchdog_selector_stall_debounce_present``). The other five
# live tests above are plain substring checks with no control — do not read
# this block as covering them.
#
# Each control invokes the guard function itself, so weakening a live
# assertion breaks its control too. Controls that re-derive the offender
# computation inline would stay green through exactly that edit, which is the
# defect class this file exists to close. The real file is never written to.
# ---------------------------------------------------------------------------

#: A realistic second aggregate call site, of the shape migrating
#: ``drain-watchdog.yml:285-287`` off raw ``gh issue create`` would produce.
SECOND_CALL_SITE = (
    "      - name: Alert on selector stall via aggregate manager\n"
    "        run: |\n"
    "          python3 - <<'PY'\n"
    "          from daily_aggregate_manager import open_or_supersede_daily_aggregate\n"
    "          open_or_supersede_daily_aggregate(\n"
    "              repo=repo,\n"
    '              label="selector-stall,auto-improvement",\n'
    '              title_prefix="[selector-stall] watchdog",\n'
    "              body=body,\n"
    "              today_utc=now.date(),\n"
    "          )\n"
    "          PY\n"
    "\n"
)

_SELECTOR_STALL_ANCHOR = "      - name: Detect selector stall"


def _watch_both_ways(
    guard: Callable[[str], None], mutated: str, *, mutation: str
) -> None:
    """Watch a guard permit the real workflow and refuse a planted violation.

    Args:
        guard: A live test function accepting a ``content`` argument.
        mutated: Workflow source carrying the planted violation.
        mutation: Human description of the mutation, for vacuity messages.

    Raises:
        AssertionError: If the mutation did not apply, if the guard rejects
            the real file, or if the guard fails to refuse the violation.
    """
    real = _read_workflow()
    assert mutated != real, f"mutation '{mutation}' did not apply — control is vacuous"
    guard(real)  # watched permitting — must not raise
    with pytest.raises(AssertionError):  # watched refusing
        guard(mutated)


def test_control_drain_stuck_label_guard_fails_when_kwarg_changed() -> None:
    """Negative control: renaming the label kwarg value trips the positive guard."""
    mutated = _read_workflow().replace('label="drain-stuck"', 'label="watchdog-alert"')
    _watch_both_ways(
        test_drain_watchdog_drain_stuck_label_present,
        mutated,
        mutation="rename label value to watchdog-alert",
    )


def test_control_drain_stuck_label_guard_fails_when_call_site_removed() -> None:
    """Negative control, different shape: the whole call site disappearing.

    This is the failure mode the old ``--label "drain-stuck"`` string assertion
    could not distinguish from a transport change. With the call site gone,
    ``_aggregate_label_values`` yields nothing and both live guards fail on the
    ``assert label_values`` precondition instead of passing vacuously.
    """
    mutated = _read_workflow().replace(AGGREGATE_CALL, "some_other_helper(")
    assert _aggregate_label_values(mutated) == []
    _watch_both_ways(
        test_drain_watchdog_drain_stuck_label_present,
        mutated,
        mutation="remove the aggregate call site",
    )


def test_control_label_guard_fails_loudly_when_call_site_is_malformed() -> None:
    """Negative control: an unbalanced call site must fail loud, not scan short.

    A truncated argument blob is indistinguishable from a clean one to a
    substring check, so a partially-parsed call would hide every kwarg after
    the truncation point. ``_aggregate_call_arg_blobs`` returns ``[]`` instead,
    tripping the ``assert label_values`` precondition.
    """
    real = _read_workflow()
    mutated = real.replace(
        "              today_utc=now.date(),\n          )\n",
        "              today_utc=now.date(),\n",
        1,
    )
    assert _aggregate_call_arg_blobs(mutated) == [], "call site still balances — control is vacuous"
    _watch_both_ways(
        test_drain_watchdog_drain_stuck_label_present,
        mutated,
        mutation="delete the aggregate call's closing paren",
    )


def test_control_self_loop_guard_detects_comma_joined_label() -> None:
    """Negative control: the original #1275 shape, expressed as a kwarg value.

    The comma sits inside the quoted literal, so a comma-bounded value scan
    would truncate it to ``"drain-stuck`` and miss the offender entirely.
    """
    mutated = _read_workflow().replace(
        'label="drain-stuck"', 'label="drain-stuck,auto-improvement"'
    )
    _watch_both_ways(
        test_drain_watchdog_does_not_label_stuck_as_auto_improvement,
        mutated,
        mutation="comma-join auto-improvement into the label value",
    )


def test_control_self_loop_guard_detects_single_line_list_labels() -> None:
    """Negative control, different shape: a plural list-literal on one line.

    The #1275 bug arrived as a comma-joined CLI flag. If the aggregate manager
    ever grows a ``labels=[...]`` parameter, the same defect returns in a shape
    no comma-joined-string check would see. The guard must catch it too.
    """
    mutated = _read_workflow().replace(
        'label="drain-stuck",', 'labels=["drain-stuck", "auto-improvement"],'
    )
    _watch_both_ways(
        test_drain_watchdog_does_not_label_stuck_as_auto_improvement,
        mutated,
        mutation="single-line labels list literal",
    )


def test_control_self_loop_guard_detects_multi_line_list_labels() -> None:
    """Negative control, different shape: the SAME list literal wrapped.

    This is the rendering any standard formatter produces for a 2-element list
    inside an already-multi-line call, and it is the shape the previous
    line-bounded ``[^\\n]*`` capture reduced to ``"["`` — offenders empty,
    guard green, bug shipped. Testing only the single-line rendering certified
    coverage this file did not have.
    """
    mutated = _read_workflow().replace(
        '              label="drain-stuck",\n',
        "              labels=[\n"
        '                  "drain-stuck",\n'
        '                  "auto-improvement",\n'
        "              ],\n",
        1,
    )
    _watch_both_ways(
        test_drain_watchdog_does_not_label_stuck_as_auto_improvement,
        mutated,
        mutation="multi-line labels list literal",
    )


def test_control_self_loop_guard_detects_second_call_site() -> None:
    """Negative control, different shape: the offender at a *second* call site.

    ``content.find(AGGREGATE_CALL)`` returns only the first match, so a second
    aggregate call reintroducing #1275 scanned clean. This is not hypothetical:
    ``drain-watchdog.yml:285-287`` is still a raw
    ``gh issue create --label "selector-stall,high-priority"``, and migrating it
    to the aggregate manager would land a second call site right here.
    """
    mutated = _read_workflow().replace(
        _SELECTOR_STALL_ANCHOR, SECOND_CALL_SITE + _SELECTOR_STALL_ANCHOR, 1
    )
    assert len(_aggregate_call_arg_blobs(mutated)) == 2, (
        "second call site not planted — control is vacuous"
    )
    _watch_both_ways(
        test_drain_watchdog_does_not_label_stuck_as_auto_improvement,
        mutated,
        mutation="second aggregate call site carrying auto-improvement",
    )


def test_control_self_loop_guard_detects_offender_after_bracket_in_string() -> None:
    """Negative control, different shape: a ``)`` inside a quoted kwarg value.

    A string-blind paren scan treats the ``)`` in
    ``title_prefix="[drain-stuck) watchdog"`` as the end of the call, truncating
    the argument blob so every later kwarg — including the offending
    ``labels=`` — is invisible. Offenders empty, guard green.
    """
    mutated = _read_workflow().replace(
        '              title_prefix="[drain-stuck] watchdog",\n',
        '              title_prefix="[drain-stuck) watchdog",\n'
        '              labels=["auto-improvement"],\n',
        1,
    )
    _watch_both_ways(
        test_drain_watchdog_does_not_label_stuck_as_auto_improvement,
        mutated,
        mutation="close-paren inside title_prefix hiding a later labels kwarg",
    )


def test_control_self_loop_guard_permits_legitimate_auto_improvement() -> None:
    """Watched permitting: legitimate auto-improvement mentions must not trip it.

    'auto-improvement' appears 6 times legitimately in drain-watchdog.yml
    (backlog queries, drain invocation, triage prose). Planting a 7th outside
    the aggregate-manager call site must stay clean — this is what distinguishes
    a scoped guard from a substring grep over the whole file.
    """
    mutated = _read_workflow().replace(
        _SELECTOR_STALL_ANCHOR,
        "      - name: Extra legitimate query\n"
        "        run: gh issue list --label auto-improvement\n"
        "\n" + _SELECTOR_STALL_ANCHOR,
        1,
    )
    assert mutated != _read_workflow(), "mutation did not apply — control is vacuous"
    assert "auto-improvement" in mutated
    assert _aggregate_label_values(mutated), "mutation destroyed the call site — control is vacuous"
    test_drain_watchdog_does_not_label_stuck_as_auto_improvement(mutated)  # must not raise


def test_control_selector_stall_debounce_guard_fails_when_debounce_removed() -> None:
    """Negative control: deleting the selector-stall debounce query trips the guard."""
    mutated = _read_workflow().replace("--label selector-stall", "--label ''")
    _watch_both_ways(
        test_drain_watchdog_selector_stall_debounce_present,
        mutated,
        mutation="drop the selector-stall label from the debounce query",
    )


def test_control_selector_stall_debounce_not_satisfied_by_a_neighbour_step() -> None:
    """Negative control, different shape: a 4h window belonging to another step.

    The old assertion counted ``"4 hours ago"`` file-wide and required ``>= 2``,
    so an unrelated step's debounce could satisfy — or, once removed, break — a
    check about the selector-stall step. Here the selector-stall debounce is
    deleted while two "4 hours ago" occurrences are planted elsewhere.
    """
    content = _read_workflow()
    section = _step_section(content, "Detect selector stall")
    assert section, "could not isolate the selector-stall step — control is vacuous"
    stripped_section = re.sub(
        r"\n\s*RECENT_STALL=.*?fi\n", "\n", section, count=1, flags=re.DOTALL
    )
    assert stripped_section != section, "debounce block not removed — control is vacuous"
    mutated = content.replace(section, stripped_section).replace(
        "- name: Detect STUCK",
        "- name: Neighbour A\n        run: echo '4 hours ago'\n\n"
        "      - name: Neighbour B\n        run: echo '4 hours ago'\n\n"
        "      - name: Detect STUCK",
    )
    assert mutated.count("4 hours ago") >= 2, "planted neighbours missing — control is vacuous"
    _watch_both_ways(
        test_drain_watchdog_selector_stall_debounce_present,
        mutated,
        mutation="debounce deleted, two 4h windows planted in neighbouring steps",
    )


def test_control_selector_stall_debounce_not_satisfied_from_within_own_step() -> None:
    """Negative control, different shape: the window borrowed from the SAME step.

    The neighbour control above plants *outside* the step, so a step-scoped but
    ``re.DOTALL`` match still passed it. The step is 137 lines and its issue
    body is prose, so the ``.*?`` could reach a "4 hours ago" that has nothing
    to do with the debounce query. Here the real ``--search`` line is deleted
    and the phrase reappears in the step's own prose: still not a debounce.
    """
    content = _read_workflow()
    section = _step_section(content, "Detect selector stall")
    assert section, "could not isolate the selector-stall step — control is vacuous"
    stripped = re.sub(r"[ \t]*--search[^\n]*4 hours ago[^\n]*\n", "", section, count=1)
    assert stripped != section, "--search line not removed — control is vacuous"
    planted = stripped.replace(
        "- **Reason**: $REASON",
        "- **Reason**: $REASON (no alert filed since 4 hours ago)",
        1,
    )
    assert planted != stripped, "prose not planted — control is vacuous"
    mutated = content.replace(section, planted)
    assert SELECTOR_STALL_WINDOW in _step_section(mutated, "Detect selector stall"), (
        "planted 4h phrase not inside the step — control is vacuous"
    )
    _watch_both_ways(
        test_drain_watchdog_selector_stall_debounce_present,
        mutated,
        mutation="debounce --search deleted, 4h phrase planted in the step's own prose",
    )
