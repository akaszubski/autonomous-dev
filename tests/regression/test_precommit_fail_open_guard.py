#!/usr/bin/env python3
"""Guard: no ``|| true`` may mask an exit code that a shell hook then gates on.

Tracking issue: **to be filed post-merge** — this repair was made directly
from a plan, before an issue existed. Do not invent a number for it.

THE DEFECT THIS LOCKS OUT
-------------------------

``scripts/hooks/pre-commit`` carried this shape from ``0b00185f``
(2025-11-11, the same commit that introduced the check) until 2026-08-30::

    venv/bin/pytest tests/integration/test_documentation_references.py \\
        -q --tb=line 2>/dev/null || true
    TEST_EXIT=$?
    if [ $TEST_EXIT -ne 0 ]; then
        echo "Documentation tests failed..."
        exit $TEST_EXIT
    fi

``$?`` after ``cmd || true`` is the exit status of ``true``, which is
always 0. ``TEST_EXIT`` was therefore always 0, the ``if`` was unreachable,
and the ``exit`` was dead code. The gate refused nothing for 9.5 months
while ``10 failed, 5 passed`` printed to the committer's terminal.

WHAT THIS GUARD CHECKS
----------------------

Every file in ``scripts/hooks/`` is read as text and comment-stripped with
the ``#1588`` instrument ``_SHELL_COMMENT``. A finding is raised when a
line matching ``\\|\\|\\s*(true|:)\\s*$`` is the nearest preceding
non-blank, non-comment line before a ``\\w+=\\$\\?`` capture.

BOTH ARMS ARE EXERCISED
-----------------------

- **Positive control** — ``test_guard_refuses_the_original_defect``
  reconstructs the two offending lines verbatim in a synthetic fixture. The
  guard must flag it. Without this arm, "no findings" in the live tree
  would be indistinguishable from a regex that cannot match anything.
- **Negative control** — ``test_guard_permits_the_live_legitimate_or_true``
  was originally pointed at ``scripts/hooks/pre-commit:73``, a real, live,
  correct ``|| true`` ending a command substitution. That line NO LONGER
  EXISTS: the 2026-09-04 repair replaced the whole pipeline with
  ``claude_gate_scan`` and an if/else capture, so no EXECUTABLE ``|| true``
  survives anywhere in ``scripts/hooks/`` — the five remaining occurrences
  (``pre-commit`` lines 56, 77, 79, 284, 286) are all inside comments
  describing the defect, and ``_SHELL_COMMENT`` strips them. The control was
  RE-POINTED
  on 2026-09-04 at the live ``CLAUDE_SCAN_RC=$?`` inside an ``else`` branch —
  a ``$?`` capture whose nearest preceding line is ``else``, not ``|| true``.
  That is still a DIFFERENT shape from the bug (the bug's ``$?`` follows a
  masked command; this one follows an ``if`` that failed), so the guard stays
  proven scoped to the class rather than to the string ``|| true``. The
  original ``:73`` line survives as a *synthetic* negative control in
  ``test_guard_permits_the_original_line_shape_synthetically``, which pins
  the old text verbatim so re-pointing did not lose the shape it discriminated.

WHAT THIS GUARD CANNOT SEE — stated so nobody reads a green as more
-------------------------------------------------------------------

It is a text matcher, not a shell parser. It does **not** catch:

- a ``|| true`` separated from its ``$?`` capture by intervening commands;
- the pattern inside a shell function body invoked elsewhere;
- lines joined with a trailing ``\\`` continuation;
- ``set +e`` misuse, or a ``$?`` read after a pipeline where
  ``PIPESTATUS``/``pipefail`` is the actual bug;
- the equivalent fail-open written as ``cmd || rc=0``, ``cmd; rc=0``, or
  via a trap;
- anything outside ``scripts/hooks/``.

It also does not police the *other* fail-open in the same file: under
``set -e`` a bare ``cmd`` followed by ``RC=$?`` aborts the script AT the
failing command, so the capture is only ever reached on success and the
message block below it is unreachable. Four such blocks live at
``pre-commit`` lines 229-235, 248-254, 261-267 and 274-280 (re-measured
2026-09-04, after ``claude_gate_scan`` shifted everything below it by +121;
the previous citation of 107-113/126-132/139-145/152-158 was itself a
re-measurement of a stale one, which is why these numbers are re-derived
rather than carried forward). They refuse (the script exits non-zero) but
print nothing. That is a different defect, deliberately out of scope here,
and left untouched.

THE THREE GAPS CLOSED 2026-09-04, and which test watches each
--------------------------------------------------------------

- **GAP 1** — ``core.quotePath`` (ON by default) C-quotes any path holding a
  non-ASCII byte, so ``.claude/café-évil.json`` arrived as ``"..."`` and left
  the ``^\\.claude/`` selector's domain entirely. Watched end-to-end by
  ``test_refuse_arm_non_ascii_claude_path_blocked``.
- **GAP 2** — the selector was byte-exact while APFS folds case, so
  ``.Claude/settings.json`` was never selected. Watched end-to-end by
  ``test_refuse_arm_case_variant_of_allowlisted_name_blocked``, which builds
  its OWN repo with no ``.claude/`` on disk (see that test's docstring for
  why ``sandbox_repo`` cannot be used).
- **GAP 3** — the pipeline ended in ``|| true`` with no ``pipefail``, so a git
  failure was indistinguishable from "nothing staged" and PERMITTED. Watched
  at function level by ``test_scan_fails_closed_on_malformed_stream``.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

import pytest

# tests/regression/test_precommit_fail_open_guard.py
#   -> regression -> tests -> repo root = parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[2]

SHELL_HOOKS_DIR = PROJECT_ROOT / "scripts" / "hooks"
PRE_COMMIT = SHELL_HOOKS_DIR / "pre-commit"

# The #1588 comment-stripping instrument lives in tests/unit/hooks/. Import
# it; do NOT reimplement it. A second copy drifts from the first, and
# tests/unit/hooks/test_hook_reachability_ratchet.py:2345 already carries a
# ratchet against exactly that habit for the sibling instruments.
_REFUSAL_SINK_DIR = str(PROJECT_ROOT / "tests" / "unit" / "hooks")
if _REFUSAL_SINK_DIR not in sys.path:
    sys.path.insert(0, _REFUSAL_SINK_DIR)

from test_refusal_sink_ratchet import _SHELL_COMMENT  # noqa: E402

#: A line whose last effective token is ``|| true`` or ``|| :``.
_OR_TRUE = re.compile(r"\|\|\s*(?:true|:)\s*$")

#: An exit-status capture, e.g. ``TEST_EXIT=$?``.
_RC_CAPTURE = re.compile(r"\w+=\$\?")

#: The four documents the pre-commit doc gate is meant to police.
_DOC_RELPATHS = (
    "CLAUDE.md",
    "docs/LIBRARIES.md",
    "docs/PERFORMANCE.md",
    "docs/GIT-AUTOMATION.md",
)

_DOC_TEST_RELPATH = "tests/integration/test_documentation_references.py"


class FailOpenFinding(NamedTuple):
    """One ``|| true`` masking a subsequent ``$?`` capture.

    Attributes:
        line_number: 1-indexed line of the ``$?`` capture.
        masking_line: The offending ``|| true`` line, stripped.
        capture_line: The ``$?`` capture line, stripped.
    """

    line_number: int
    masking_line: str
    capture_line: str


def find_fail_open_captures(source: str) -> List[FailOpenFinding]:
    """Find ``$?`` captures whose preceding command was masked by ``|| true``.

    Args:
        source: Full text of a shell script.

    Returns:
        One :class:`FailOpenFinding` per masked capture, in document order.
    """
    raw_lines = source.split("\n")
    # Comment-stripped view: a whole-line comment collapses to "", so the
    # "nearest preceding non-blank, non-comment line" walk below gets the
    # non-comment part for free.
    stripped = [_SHELL_COMMENT.sub("", line) for line in raw_lines]

    findings: List[FailOpenFinding] = []
    for index, line in enumerate(stripped):
        if not _RC_CAPTURE.search(line):
            continue

        previous = index - 1
        while previous >= 0 and not stripped[previous].strip():
            previous -= 1
        if previous < 0:
            continue

        if _OR_TRUE.search(stripped[previous].rstrip()):
            findings.append(
                FailOpenFinding(
                    line_number=index + 1,
                    masking_line=raw_lines[previous].strip(),
                    capture_line=raw_lines[index].strip(),
                )
            )
    return findings


def _shell_hook_files() -> List[Path]:
    """Return every regular file in ``scripts/hooks/``.

    Not filtered by suffix: ``pre-commit`` and ``pre-push`` have none.

    Returns:
        Sorted list of paths.
    """
    return sorted(p for p in SHELL_HOOKS_DIR.iterdir() if p.is_file())


#: First line of the ``.claude/`` gate's scanner, matched whole-line-stripped.
_GATE_FN_HEADER = "claude_gate_scan() {"


def _extract_gate_scan_source() -> str:
    """Slice ``claude_gate_scan()`` out of the LIVE ``scripts/hooks/pre-commit``.

    The function is never re-typed here. A copy in the test file would drift
    from the hook silently, and every arm below would then be proving the
    copy rather than what executes on ``git commit``.

    Returns:
        The function definition, from its header line through the first
        line that is exactly ``}``.

    Raises:
        AssertionError: If the header cannot be found, if the closing brace
            cannot be found, or if the slice does not contain ``while true``.
            That last check is the EXTRACTOR'S POSITIVE CONTROL: an empty or
            truncated slice would otherwise run as a no-op function that
            returns 0 for every input, and every refuse arm below would go
            green while proving nothing.
    """
    lines = PRE_COMMIT.read_text(encoding="utf-8").split("\n")

    starts = [i for i, line in enumerate(lines) if line.strip() == _GATE_FN_HEADER]
    assert len(starts) == 1, (
        f"EXTRACTOR CONTROL FAILED: expected exactly one {_GATE_FN_HEADER!r} "
        f"line in {PRE_COMMIT}, found {len(starts)} at {starts!r}. A zero- or "
        f"multi-match anchor mutates nothing and proves nothing."
    )
    start = starts[0]

    ends = [i for i in range(start + 1, len(lines)) if lines[i] == "}"]
    assert ends, (
        f"EXTRACTOR CONTROL FAILED: no closing `}}` at column 0 after "
        f"{PRE_COMMIT}:{start + 1}."
    )
    body = "\n".join(lines[start : ends[0] + 1])

    assert "while true" in body, (
        "EXTRACTOR CONTROL FAILED: the extracted claude_gate_scan slice does "
        "not contain `while true`, so it is not the scanner loop. A truncated "
        "slice defines a function that returns 0 for every stream, which would "
        "turn every refuse arm below into a false green."
    )
    return body


def _run_gate_scan(stream: bytes) -> Tuple[int, bytes]:
    """Feed ``stream`` to the LIVE ``claude_gate_scan`` and return its verdict.

    The extracted function is written to a throwaway file and run with
    ``bash <file>``; ``stream`` goes to its stdin as RAW BYTES. ``text=True``
    is deliberately NOT used — the whole point of ``--raw -z`` is that paths
    are undecoded bytes, and a str round-trip would hide exactly the GAP 1
    failure this exercises. No PATH manipulation: nothing here shells out to
    ``git``.

    A private :class:`tempfile.TemporaryDirectory` is used rather than the
    ``tmp_path`` fixture so that the helper keeps the single-argument
    signature its call sites expect and can be used from non-test helpers.

    Args:
        stream: Raw bytes as ``git diff --cached --raw -z`` would emit them.

    Returns:
        ``(returncode, stdout_bytes)``. ``0`` with empty stdout is a PERMIT;
        ``0`` with non-empty stdout names the offenders; ``3`` is the
        fail-closed verdict for a stream the scanner could not account for.
    """
    script = "#!/bin/bash\n" + _extract_gate_scan_source() + "\nclaude_gate_scan\n"
    with tempfile.TemporaryDirectory(prefix="claude_gate_scan_") as tmpdir:
        script_path = Path(tmpdir) / "gate_scan.sh"
        script_path.write_text(script, encoding="utf-8")
        proc = subprocess.run(
            ["bash", str(script_path)],
            input=stream,
            capture_output=True,
            timeout=60,
        )
    return proc.returncode, proc.stdout


def _raw_z_record(
    newmode: str, path: str, *, status: str = "A", dest: Optional[str] = None
) -> bytes:
    """Build one ``git diff --cached --raw -z`` record.

    The real format is ``:<srcmode> <dstmode> <srcsha> <dstsha> <status>``,
    then NUL, then the path, then — for ``R``/``C`` statuses ONLY — a second
    NUL-terminated destination path.

    Args:
        newmode: The destination (staged) object mode, e.g. ``100644``.
        path: The first path field.
        status: The raw status letter(s), e.g. ``A``, ``M``, ``D``, ``R100``.
        dest: Second path field. Required for ``R``/``C``, ignored otherwise.

    Returns:
        The record as raw bytes, including its trailing NUL(s).
    """
    meta = f":100644 {newmode} 1111111 2222222 {status}"
    out = meta.encode("utf-8") + b"\0" + path.encode("utf-8") + b"\0"
    if dest is not None:
        out += dest.encode("utf-8") + b"\0"
    return out


class TestFailOpenRatchet:
    """The ratchet itself, plus both of its controls."""

    def test_guard_refuses_the_original_defect(self):
        """POSITIVE CONTROL: the two original lines, verbatim, must be flagged.

        Reconstructed from ``0b00185f``. If this arm ever goes green, the
        detector has stopped detecting and every other assertion in this
        module is worthless.
        """
        original_defect = (
            "#!/bin/bash\n"
            "set -e\n"
            'echo "Running documentation validation tests..."\n'
            'if [ -f "venv/bin/pytest" ]; then\n'
            "    venv/bin/pytest tests/integration/"
            "test_documentation_references.py -q --tb=line 2>/dev/null || true\n"
            "    TEST_EXIT=$?\n"
            "    if [ $TEST_EXIT -ne 0 ]; then\n"
            '        echo "Documentation tests failed."\n'
            "        exit $TEST_EXIT\n"
            "    fi\n"
            "fi\n"
        )

        findings = find_fail_open_captures(original_defect)

        assert findings, (
            "POSITIVE CONTROL FAILED: the guard did not flag the verbatim "
            "0b00185f defect. The detector is broken, so a clean result on "
            "the live tree means nothing."
        )
        assert findings[0].capture_line == "TEST_EXIT=$?"
        assert findings[0].masking_line.endswith("|| true")

    def test_guard_refuses_the_colon_spelling(self):
        """POSITIVE CONTROL (variant): ``|| :`` is the same fail-open.

        ``:`` is the shell no-op builtin and always succeeds, exactly like
        ``true``. Spelling the bug differently must not evade the guard.
        """
        variant = "make check || :\nBUILD_RC=$?\n"

        findings = find_fail_open_captures(variant)

        assert findings, "POSITIVE CONTROL FAILED: `|| :` was not flagged"
        assert findings[0].capture_line == "BUILD_RC=$?"

    def test_guard_permits_the_live_legitimate_or_true(self):
        """NEGATIVE CONTROL, RE-POINTED 2026-09-04. Name kept deliberately.

        WHY IT MOVED. This control used to read ``scripts/hooks/pre-commit:73``
        — a live ``|| true`` closing a command substitution whose pipeline
        ended in ``grep``. **That line no longer exists.** The 2026-09-04
        repair replaced the entire ``awk | grep | grep -vxF || true`` pipeline
        with ``claude_gate_scan`` plus a ``set -o pipefail`` if/else capture.
        No EXECUTABLE ``|| true`` survives under ``scripts/hooks/``: the five
        remaining occurrences are all inside comments, and ``_SHELL_COMMENT``
        strips comments before this control looks.
        The old assertions ("a `|| true` line exists", "it contains grep")
        would therefore fail at the VOID check — correctly: the control had
        become inert, and its own message said to re-point it rather than
        leave something that cannot fail.

        WHAT IT NOW READS. Every live ``\\w+=\\$\\?`` capture whose nearest
        preceding non-blank, comment-stripped line is exactly ``else``. That
        is the sanctioned replacement shape (``if cmd; then RC=0; else
        RC=$?; fi``) and it is a DIFFERENT shape from the bug: the bug's
        ``$?`` reads the status of a ``true`` that always succeeded; this
        one reads the status of a command that actually failed, which is the
        only reason the ``else`` branch was taken at all. A guard scoped to
        the string ``$?`` rather than to the fail-open class would flag it.

        The VOID CHECK is retained in the new shape: if no such capture
        exists the control is inert and this test says so instead of passing.
        ``CLAUDE_SCAN_RC=$?`` is named specifically because it is the capture
        the 2026-09-04 repair introduced — if a future edit reverts that
        capture to ``|| true``, this arm goes red rather than silently
        watching nothing.

        The ORIGINAL ``:73`` shape is not lost: it is pinned verbatim as a
        synthetic control in
        :meth:`test_guard_permits_the_original_line_shape_synthetically`.
        """
        source = PRE_COMMIT.read_text(encoding="utf-8")
        raw_lines = source.split("\n")
        stripped = [_SHELL_COMMENT.sub("", line) for line in raw_lines]

        else_captures: List[Tuple[int, str]] = []
        for index, line in enumerate(stripped):
            if not _RC_CAPTURE.search(line):
                continue
            previous = index - 1
            while previous >= 0 and not stripped[previous].strip():
                previous -= 1
            if previous < 0:
                continue
            if stripped[previous].strip() == "else":
                else_captures.append((index + 1, raw_lines[index].strip()))

        assert else_captures, (
            "NEGATIVE CONTROL VOID: scripts/hooks/pre-commit contains no "
            "`$?` capture whose preceding line is `else`, so this control is "
            "not exercising anything. Re-point it at another live legitimate "
            "capture, or delete it — do not leave a control that cannot fail."
        )
        captured_texts = [text for _, text in else_captures]
        assert "CLAUDE_SCAN_RC=$?" in captured_texts, (
            "NEGATIVE CONTROL VOID: `CLAUDE_SCAN_RC=$?` is no longer an "
            "else-branch capture in scripts/hooks/pre-commit. The .claude/ "
            "gate's rc handling has changed shape; re-read it before trusting "
            f"this control. Found instead: {captured_texts!r}"
        )

        findings = find_fail_open_captures(source)
        assert not findings, (
            "NEGATIVE CONTROL FAILED: the guard flagged a legitimate "
            "if/else `$?` capture:\n"
            + "\n".join(
                f"  - pre-commit:{f.line_number}: {f.masking_line} / "
                f"{f.capture_line}"
                for f in findings
            )
        )

    def test_guard_permits_the_original_line_shape_synthetically(self):
        """NEGATIVE CONTROL (synthetic): the deleted ``:73`` shape, pinned.

        The live control above had to be re-pointed because the line it read
        was deleted. Re-pointing must not silently DROP the shape the old
        control discriminated against, so the original two lines are pinned
        here verbatim, copied out of ``git show HEAD:scripts/hooks/pre-commit``
        before the change.

        This is the legitimate use of ``|| true``: it closes a command
        SUBSTITUTION (so it is not even at end-of-statement for the enclosing
        script), it exists to stop ``grep``'s no-match status aborting under
        ``set -e``, and the next line tests the RESULT with ``[ -n ... ]``
        rather than capturing ``$?``. A guard scoped to the string
        ``|| true`` instead of to the fail-open class would flag it.
        """
        original_shape = (
            'STAGED_CLAUDE_FILES=$(git diff --cached --raw | awk -F\'\\t\' '
            '\'{split($1,m," "); if (m[2]=="000000") next; '
            'print ($3==""?$2:$3) " " m[2]}\' | grep "^\\.claude/" '
            '| grep -vxF -e ".claude/PROJECT.md 120000" '
            '-e ".claude/settings.json 100644" '
            '-e ".claude/logs/cloud-runs.jsonl 100644" || true)\n'
            'if [ -n "$STAGED_CLAUDE_FILES" ]; then\n'
        )

        # Setup control: the fixture must actually END in `|| true)`, or this
        # is not the shape it claims to pin.
        assert original_shape.split("\n")[0].endswith("|| true)"), (
            "SETUP FAILED: the pinned :73 line no longer ends in `|| true)`, "
            "so it is not the shape this control exists to permit."
        )

        findings = find_fail_open_captures(original_shape)

        assert not findings, (
            "NEGATIVE CONTROL FAILED: the guard flagged the original, "
            "LEGITIMATE pre-commit:73 `|| true` — a command substitution "
            "followed by `if [ -n ... ]`, not by a `$?` capture. The guard "
            "has degenerated into a search for the string `|| true`:\n"
            + "\n".join(
                f"  - line {f.line_number}: {f.masking_line} / {f.capture_line}"
                for f in findings
            )
        )

    def test_no_shell_hook_masks_an_exit_code_with_or_true(self):
        """THE RATCHET: no file in ``scripts/hooks/`` may reintroduce it."""
        scanned: List[str] = []
        violations: List[str] = []

        for hook_file in _shell_hook_files():
            scanned.append(hook_file.name)
            source = hook_file.read_text(encoding="utf-8", errors="replace")
            for finding in find_fail_open_captures(source):
                violations.append(
                    f"{hook_file.name}:{finding.line_number}: "
                    f"`{finding.masking_line}` masks `{finding.capture_line}` "
                    f"— $? is the status of true/:, always 0, so every gate "
                    f"below this capture is dead code."
                )

        assert scanned, (
            f"Scanned no files: {SHELL_HOOKS_DIR} is empty or missing. A "
            f"guard over zero files is not a guard."
        )
        assert not violations, (
            "Fail-open `|| true` before a $? capture reintroduced:\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nREQUIRED NEXT ACTION — capture with if/else instead:\n"
            "    if cmd; then RC=0; else RC=$?; fi"
        )

    def test_doc_gate_failure_message_does_not_advertise_no_verify(self):
        """The gate's own failure message must not hand out the bypass.

        Scoped to the documentation-gate block only: ``--no-verify`` at
        ``pre-commit:15`` (file header), ``:112`` (a comment naming the prior
        workaround) and ``:213`` (the .claude/ staging gate's own refusal)
        predate this work and belong to other gates. Re-measured 2026-09-04
        after ``claude_gate_scan`` shifted the file; the prior citation of
        ``:70``/``:92`` was stale.
        """
        lines = PRE_COMMIT.read_text(encoding="utf-8").split("\n")

        start = next(
            (
                i
                for i, line in enumerate(lines)
                if "Running documentation validation tests" in line
            ),
            None,
        )
        assert start is not None, (
            "Could not locate the documentation-gate block in "
            "scripts/hooks/pre-commit"
        )

        block = "\n".join(lines[start:])
        assert "--no-verify" not in block, (
            "The documentation gate's failure message advertises "
            "`--no-verify`. A gate that ships its own bypass in the refusal "
            "text is a suggestion, not a gate."
        )
        assert "REQUIRED NEXT ACTION" in block, (
            "The documentation gate's refusal must carry a REQUIRED NEXT "
            "ACTION (stick+carrot): a blocked committer needs the reproduce "
            "command, not just a verdict."
        )


# ---------------------------------------------------------------------------
# Runtime proof: the hook is actually executed by git, both arms.
#
# Asserting on the hook's SOURCE cannot distinguish a hook that refuses from
# one that describes refusing. These two tests run `git commit` for real and
# assert on the observable outcome: the return code AND whether a commit
# object exists afterwards.
# ---------------------------------------------------------------------------


def _run(cmd: List[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a command in ``cwd``, capturing text output.

    Args:
        cmd: Argument vector.
        cwd: Working directory.

    Returns:
        The completed process.
    """
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=180,
    )


def _link_targets_of_governed_docs() -> List[str]:
    """Return repo-relative paths every governed doc links to.

    Computed from the live documents rather than hardcoded, so the sandbox
    stays complete when a doc gains a link.

    Paths are kept LOGICAL (not ``resolve()``d): ``.claude/PROJECT.md`` is a
    symlink to ``../PROJECT.md`` here, and resolving it would copy only the
    target, leaving the link that ``CLAUDE.md`` actually writes unsatisfied
    in the sandbox.

    Returns:
        Sorted repo-relative paths of existing link targets.
    """
    link_pattern = re.compile(r"\[[^\]]+\]\(([^\)]+)\)")
    targets = set()
    for relpath in _DOC_RELPATHS:
        doc = PROJECT_ROOT / relpath
        doc_dir = Path(relpath).parent
        for url in link_pattern.findall(doc.read_text(encoding="utf-8")):
            if url.startswith(("http://", "https://", "mailto:", "#")):
                continue
            file_part = url.split("#")[0]
            if not file_part:
                continue
            logical = os.path.normpath(str(doc_dir / file_part))
            if logical.startswith(".."):
                continue  # escapes the repo; nothing to copy
            if not (PROJECT_ROOT / logical).is_file():
                continue
            targets.add(logical)
    return sorted(targets)


def _build_sandbox_repo(root: Path) -> None:
    """Materialise a git repo that runs the real pre-commit doc gate.

    The sandbox carries the real hook, the real documentation test module,
    the four governed documents, and every file they link to. The other
    seven checks in the hook are inert here by their own ``if [ -f ... ]``
    guards (the archived validators are not copied); only
    ``scripts/validate_structure.py`` must exist, and is stubbed to exit 0
    so this fixture proves the *documentation* gate and nothing else.

    Args:
        root: Empty directory to build the repo in.
    """

    def copy_in(relpath: str) -> None:
        source = PROJECT_ROOT / relpath
        dest = root / relpath
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)

    _run(["git", "init", "-q", "-b", "main", "."], root)
    _run(["git", "config", "user.email", "guard@example.test"], root)
    _run(["git", "config", "user.name", "Fail-Open Guard"], root)
    _run(["git", "config", "commit.gpgsign", "false"], root)

    for relpath in ("CLAUDE.md", "README.md", "docs/ARCHITECTURE-OVERVIEW.md"):
        copy_in(relpath)
    for relpath in _DOC_RELPATHS:
        copy_in(relpath)
    for relpath in _link_targets_of_governed_docs():
        copy_in(relpath)
    copy_in(_DOC_TEST_RELPATH)

    structure_stub = root / "scripts" / "validate_structure.py"
    structure_stub.parent.mkdir(parents=True, exist_ok=True)
    structure_stub.write_text(
        "#!/usr/bin/env python3\n"
        '"""Sandbox stub — the structure gate is not the subject here."""\n'
        "raise SystemExit(0)\n",
        encoding="utf-8",
    )

    # A venv/bin/pytest shim so the hook's FIRST branch is the one taken,
    # bound to this interpreter rather than to whatever is on PATH.
    pytest_shim = root / "venv" / "bin" / "pytest"
    pytest_shim.parent.mkdir(parents=True, exist_ok=True)
    pytest_shim.write_text(
        f'#!/bin/sh\nexec "{sys.executable}" -m pytest "$@"\n', encoding="utf-8"
    )
    pytest_shim.chmod(0o755)

    hook_dest = root / ".git" / "hooks" / "pre-commit"
    hook_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PRE_COMMIT, hook_dest)
    hook_dest.chmod(0o755)

    # `.claude/` must exist on disk (CLAUDE.md links to .claude/PROJECT.md)
    # but must never be STAGED — the hook's own .claude/ gate at lines 73-94
    # would refuse for the wrong reason and mask the arm under test.
    (root / ".gitignore").write_text("venv/\n.claude/\n", encoding="utf-8")
    (root / "trivial.txt").write_text("a staged file\n", encoding="utf-8")


@pytest.fixture()
def sandbox_repo(tmp_path: Path) -> Path:
    """A git repo wired to the real ``scripts/hooks/pre-commit``.

    Args:
        tmp_path: pytest-provided temp directory.

    Returns:
        Path to the repo root.
    """
    root = tmp_path / "sandbox"
    root.mkdir()
    _build_sandbox_repo(root)
    return root


class TestHookActuallyRuns:
    """Run the real hook via ``git commit`` and watch both arms."""

    def test_refusing_arm_hook_blocks_the_commit(self, sandbox_repo: Path):
        """A planted documentation defect must stop the commit happening.

        The defect is a dead heading anchor pointing at a file that DOES
        exist — the exact shape a file-existence-only check reports green.
        """
        libraries = sandbox_repo / "docs" / "LIBRARIES.md"
        libraries.write_text(
            libraries.read_text(encoding="utf-8")
            + "\n\nSee [dead anchor](HOOKS.md#no-such-heading-anywhere).\n",
            encoding="utf-8",
        )

        _run(["git", "add", "-A"], sandbox_repo)
        commit = _run(
            ["git", "commit", "-m", "should be blocked"], sandbox_repo
        )

        combined = commit.stdout + commit.stderr

        assert commit.returncode != 0, (
            f"REFUSING ARM FAILED: git commit returned 0.\n{combined}"
        )

        head = _run(["git", "rev-parse", "HEAD"], sandbox_repo)
        assert head.returncode != 0, (
            "REFUSING ARM FAILED: a commit object exists, so the hook's "
            "non-zero exit did not actually prevent the commit. "
            f"HEAD={head.stdout.strip()}"
        )

        assert "Documentation tests failed" in combined, (
            f"Refusal did not name its cause.\n{combined}"
        )
        assert "REQUIRED NEXT ACTION" in combined, (
            f"Refusal did not carry the reproduce command.\n{combined}"
        )
        assert "test_documentation_references.py" in combined, (
            f"Refusal did not print a runnable reproduce command.\n{combined}"
        )

    def test_permitting_arm_clean_tree_commits(self, sandbox_repo: Path):
        """With no defect the same hook must let the commit through.

        Without this arm, a hook that refused unconditionally would sail
        through the refusing arm above and look correct.
        """
        _run(["git", "add", "-A"], sandbox_repo)
        commit = _run(["git", "commit", "-m", "should succeed"], sandbox_repo)

        combined = commit.stdout + commit.stderr

        assert commit.returncode == 0, (
            f"PERMITTING ARM FAILED: the hook blocked a clean tree.\n"
            f"{combined}"
        )

        head = _run(["git", "rev-parse", "HEAD"], sandbox_repo)
        assert head.returncode == 0 and head.stdout.strip(), (
            f"PERMITTING ARM FAILED: no commit object was created.\n"
            f"{combined}"
        )


# ---------------------------------------------------------------------------
# The .claude/ staging gate: its allowlist must be an EXACT whole-line match.
#
# Until 2026-09-03 the gate subtracted its allowlist with
# `grep -v "^\.claude/PROJECT.md"` — a PREFIX match with no end anchor. It
# silently permitted `.claude/PROJECT.md.bak`, and an entry for
# `.claude/settings.json` written the same way would have permitted
# `.claude/settings.json.bak-20260903-081206` too. On 2026-09-03 the gate
# moved to `grep -vxF`; on 2026-09-04 the whole pipeline was replaced by the
# `claude_gate_scan` shell function, which subtracts with an exact whole-line
# `case` over `<path> <mode>`. The tests below watch it PERMIT the paths that
# `.gitignore` un-ignores and REFUSE the ones it does not.
# ---------------------------------------------------------------------------


class TestClaudeAllowlistIsExactMatch:
    """Run the real hook through a real commit and watch both arms of the gate.

    Every test here stages with an explicit ``git add -f <path>`` and NEVER
    ``git add -A``. Two reasons, both about keeping the arms comparable:

    - The sandbox ``.gitignore`` is ``venv/\\n.claude/\\n`` (see
      :func:`_build_sandbox_repo`), which is BROADER than the real repo's
      ``.claude/*`` plus ``!`` negations. ``-f`` neutralises gitignore as a
      variable, so the only thing differing between the permit arm and the
      refuse arms is the FILENAME — which is exactly what the allowlist
      matches on.
    - ``git add -A`` would additionally sweep the sandbox's copied documents
      into the index. Every arm would then also be an arm of the documentation
      gate lower down in the same hook, and a refusal could not be attributed
      to the ``.claude/`` gate at all. That confusion is issue #1564's shape.

    :func:`_build_sandbox_repo` is deliberately NOT modified: its "``.claude/``
    exists on disk but is never staged" invariant protects the other tests in
    this module, and these tests stage ``.claude/`` themselves, in their own
    bodies.

    Assertions are on the OBSERVABLE outcome — the return code, whether a
    commit object exists, and the gate-specific refusal text — never on the
    hook's source. Source text cannot distinguish a hook that refuses from one
    that merely describes refusing (the #1612 lesson).
    """

    #: The refusal line the ``.claude/`` gate prints; see ``pre-commit:196``
    #: (re-measured 2026-09-04; the prior citation of ``:76`` was stale).
    CLAUDE_REFUSAL = "Attempting to commit .claude/ files"

    @staticmethod
    def _write_stage_commit(
        repo: Path, relpath: str, message: str
    ) -> Tuple[subprocess.CompletedProcess, str]:
        """Create ``relpath``, force-stage it alone, and attempt a commit.

        Args:
            repo: Sandbox repo root.
            relpath: Repo-relative path to create and stage.
            message: Commit message.

        Returns:
            ``(completed_process, combined_stdout_stderr)``.
        """
        target = repo / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('{"permissions": {"allow": []}}\n', encoding="utf-8")

        # -f, not -A: see the class docstring.
        add = _run(["git", "add", "-f", relpath], repo)
        assert add.returncode == 0, (
            f"SETUP FAILED: could not stage {relpath}:\n"
            f"{add.stdout}{add.stderr}"
        )
        staged = _run(["git", "diff", "--cached", "--name-only"], repo)
        assert staged.stdout.split() == [relpath], (
            f"SETUP FAILED: the index must hold exactly {relpath!r}, so that "
            f"a refusal can only be attributed to the .claude/ gate. Got: "
            f"{staged.stdout.split()!r}"
        )

        proc = _run(["git", "commit", "-m", message], repo)
        return proc, proc.stdout + proc.stderr

    @staticmethod
    def _symlink_stage_commit(
        repo: Path, relpath: str, link_target: str, message: str
    ) -> Tuple[subprocess.CompletedProcess, str]:
        """Create ``relpath`` as a SYMLINK, force-stage it alone, and commit.

        The regular-file twin is :meth:`_write_stage_commit`. The ONLY
        difference between the two is the git object mode that ends up in the
        index — ``120000`` here, ``100644`` there — which is precisely the
        variable the mode-pinned allowlist keys on.

        The staged mode is asserted BEFORE the commit is attempted. Without
        that, a REFUSE result could not be attributed to object type: a helper
        that silently produced a regular file would make the arm pass for the
        wrong reason.

        Args:
            repo: Sandbox repo root.
            relpath: Repo-relative path to create as a symlink and stage.
            link_target: Text the symlink points at. git never dereferences
                it — the link text itself becomes the blob.
            message: Commit message.

        Returns:
            ``(completed_process, combined_stdout_stderr)``.
        """
        target = repo / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink() or target.exists():
            target.unlink()
        os.symlink(link_target, target)

        # -f, not -A: see the class docstring.
        add = _run(["git", "add", "-f", relpath], repo)
        assert add.returncode == 0, (
            f"SETUP FAILED: could not stage {relpath}:\n"
            f"{add.stdout}{add.stderr}"
        )

        raw = _run(["git", "diff", "--cached", "--raw"], repo)
        staged_mode = raw.stdout.split("\t")[0].split()[1] if raw.stdout else ""
        assert staged_mode == "120000", (
            f"SETUP FAILED: {relpath} had to reach the index as a SYMLINK "
            f"(mode 120000) for this arm to be about object type at all. "
            f"git staged mode {staged_mode!r}. Raw: {raw.stdout!r}"
        )

        staged = _run(["git", "diff", "--cached", "--name-only"], repo)
        assert staged.stdout.split() == [relpath], (
            f"SETUP FAILED: the index must hold exactly {relpath!r}, so that "
            f"a refusal can only be attributed to the .claude/ gate. Got: "
            f"{staged.stdout.split()!r}"
        )

        proc = _run(["git", "commit", "-m", message], repo)
        return proc, proc.stdout + proc.stderr

    def _assert_claude_gate_refused(
        self,
        proc: subprocess.CompletedProcess,
        combined: str,
        offender: str,
        repo: Path,
    ) -> None:
        """Assert the ``.claude/`` gate — not something else — stopped this.

        The return code alone proves nothing: the documentation pytest step
        later in the same hook runs unconditionally on every commit, against
        working-tree files rather than staged ones, and would produce the same
        non-zero code. So the gate-specific refusal text and the offending
        path must both appear, and no commit object may exist.

        Args:
            proc: The completed commit process.
            combined: Its combined stdout+stderr.
            offender: The path that must be named in the refusal.
            repo: Sandbox repo root.
        """
        assert proc.returncode != 0, (
            f"REFUSE ARM FAILED: the commit succeeded for {offender}.\n"
            f"{combined}"
        )
        assert self.CLAUDE_REFUSAL in combined, (
            f"REFUSE ARM FAILED: something blocked the commit, but NOT the "
            f".claude/ gate — its refusal text is absent, so this non-zero "
            f"code proves nothing about the allowlist.\n{combined}"
        )
        assert offender in combined, (
            f"REFUSE ARM FAILED: the refusal did not name the offending "
            f"path {offender!r}.\n{combined}"
        )

        head = _run(["git", "rev-parse", "HEAD"], repo)
        assert head.returncode != 0, (
            f"REFUSE ARM FAILED: a commit object exists, so the non-zero "
            f"exit did not actually prevent it. HEAD={head.stdout.strip()}"
        )

    def test_refuse_arm_settings_json_as_symlink_blocked(
        self, sandbox_repo: Path
    ):
        """REFUSE: an allowlisted PATH staged as the wrong OBJECT TYPE.

        The direct reproducer for the A01 finding. ``git diff --cached
        --name-only`` emits only the link path, so a name-keyed allowlist
        exact-matched ``.claude/settings.json`` and permitted a symlink to
        anywhere on the filesystem — ``/etc/hosts`` here, but equally
        ``~/.ssh/id_rsa``, ``.claude/.bypass`` or ``.claude/hooks/*.py`` —
        under a name Claude Code loads as live configuration (hooks,
        ``permissions.allow``, MCP allow/deny) and CI parses as JSON.

        The class covered is "an allowlisted path staged with a mode other
        than the one it is legitimately tracked at", not this one filename.
        :meth:`test_refuse_arm_cloud_runs_jsonl_as_symlink_blocked` is a
        second member of that class, and
        :meth:`test_permit_arm_project_md_as_symlink_commits` is the arm
        proving the fix did not degenerate into "refuse every symlink".
        """
        offender = ".claude/settings.json"
        proc, combined = self._symlink_stage_commit(
            sandbox_repo, offender, "/etc/hosts", "smuggle a symlink"
        )
        self._assert_claude_gate_refused(
            proc, combined, offender, sandbox_repo
        )

    def test_refuse_arm_cloud_runs_jsonl_as_symlink_blocked(
        self, sandbox_repo: Path
    ):
        """REFUSE: the SAME defect at a DIFFERENT allowlist member.

        A guard written against the one reported path would leave this one
        open. ``cloud-runs.jsonl`` is the entry with no ``!`` negation in
        ``.gitignore`` and the one master appends to on every cloud drain —
        the least-watched of the three, and so the most attractive carrier.
        """
        offender = ".claude/logs/cloud-runs.jsonl"
        proc, combined = self._symlink_stage_commit(
            sandbox_repo, offender, "/etc/hosts", "smuggle via telemetry path"
        )
        self._assert_claude_gate_refused(
            proc, combined, offender, sandbox_repo
        )

    def test_permit_arm_project_md_as_symlink_commits(
        self, sandbox_repo: Path
    ):
        """PERMIT: ``.claude/PROJECT.md`` is a symlink BY DESIGN.

        The negative control on the negative control. The security finding's
        literal recommendation — "refuse if the newly-staged object is a
        symlink" — would refuse the allowlist's own FIRST entry: in the real
        repo ``.claude/PROJECT.md`` is ``lrwx------ ... -> ../PROJECT.md``,
        the alignment source of truth. This arm goes red on that
        over-correction, and it is the reason the fix pins a mode PER PATH
        rather than banning a mode outright.
        """
        link = sandbox_repo / ".claude" / "PROJECT.md"
        root_doc = sandbox_repo / "PROJECT.md"

        # Reproduce the real repo's shape: a root PROJECT.md with the link
        # pointing at it, so the hook's later documentation gate still
        # resolves the link CLAUDE.md writes and cannot refuse for an
        # unrelated reason.
        content = (
            link.read_text(encoding="utf-8")
            if link.is_file()
            else "# PROJECT\n\nSandbox alignment source of truth.\n"
        )
        if not root_doc.exists():
            root_doc.write_text(content, encoding="utf-8")

        allowed = ".claude/PROJECT.md"
        proc, combined = self._symlink_stage_commit(
            sandbox_repo, allowed, "../PROJECT.md", "alignment symlink"
        )

        assert proc.returncode == 0, (
            f"PERMIT ARM FAILED: the hook blocked {allowed}, which is "
            f"allowlisted precisely AS a symlink. A blanket symlink refusal "
            f"looks exactly like this.\n{combined}"
        )
        assert self.CLAUDE_REFUSAL not in combined, (
            f"PERMIT ARM FAILED: the .claude/ gate refused an allowlisted "
            f"(path, mode) pair.\n{combined}"
        )

        head = _run(["git", "rev-parse", "HEAD"], sandbox_repo)
        assert head.returncode == 0 and head.stdout.strip(), (
            f"PERMIT ARM FAILED: no commit object was created.\n{combined}"
        )

        # The committed object must STILL be a symlink — a hook that
        # "permitted" it by dereferencing the link would also satisfy every
        # assertion above.
        ls = _run(["git", "ls-files", "-s", allowed], sandbox_repo)
        assert ls.stdout.startswith("120000 "), (
            f"PERMIT ARM FAILED: {allowed} landed in the commit as "
            f"{(ls.stdout.split() or ['nothing'])[0]!r}, not as a symlink."
        )

    def test_permit_arm_settings_json_commits(self, sandbox_repo: Path):
        """PERMIT: ``.claude/settings.json`` is allowlisted and must go through.

        ``.gitignore:147`` carries ``!.claude/settings.json``, so the file is
        deliberately tracked. Before 2026-09-03 the hook refused it anyway and
        the two disagreed. This is the fail-before/pass-after arm.
        """
        proc, combined = self._write_stage_commit(
            sandbox_repo, ".claude/settings.json", "team settings"
        )

        assert proc.returncode == 0, (
            f"PERMIT ARM FAILED: the hook blocked an allowlisted path.\n"
            f"{combined}"
        )
        assert self.CLAUDE_REFUSAL not in combined, (
            f"PERMIT ARM FAILED: the .claude/ gate refused an allowlisted "
            f"path.\n{combined}"
        )

        head = _run(["git", "rev-parse", "HEAD"], sandbox_repo)
        assert head.returncode == 0 and head.stdout.strip(), (
            f"PERMIT ARM FAILED: no commit object was created.\n{combined}"
        )

        shown = _run(
            ["git", "show", "--name-only", "--format=", "HEAD"], sandbox_repo
        )
        assert ".claude/settings.json" in shown.stdout, (
            f"PERMIT ARM FAILED: the commit object does not contain the "
            f"file.\n{shown.stdout}"
        )

    def test_refuse_arm_settings_json_backup_still_blocked(
        self, sandbox_repo: Path
    ):
        """REFUSE (negative control): a ``.bak-`` suffix must NOT be allowed.

        A DIFFERENT shape from the bug that prompted the change: the bug was
        an allowlisted path being refused; this is a NON-allowlisted path that
        a prefix-matching allowlist would have silently permitted. Spelled as
        a real timestamped backup name because that is what editors and ``cp``
        actually leave next to ``settings.json``.

        The class covered is "any path carrying an allowlist entry as a proper
        prefix" — not the single filename below.

        The return code ALONE is not sufficient evidence: the documentation
        pytest step later in the same hook runs unconditionally on every
        commit, against working-tree files rather than staged ones, and would
        produce the same non-zero code. So this arm also asserts the
        ``.claude/``-specific refusal text AND that the refusal names the
        offending path — the way ``test_refusing_arm_hook_blocks_the_commit``
        disambiguates on ``"Documentation tests failed"``.
        """
        offender = ".claude/settings.json.bak-20260903-081206"
        proc, combined = self._write_stage_commit(
            sandbox_repo, offender, "backup must be blocked"
        )

        assert proc.returncode != 0, (
            f"REFUSE ARM FAILED: the commit succeeded for {offender}.\n"
            f"{combined}"
        )
        assert self.CLAUDE_REFUSAL in combined, (
            f"REFUSE ARM FAILED: something blocked the commit, but NOT the "
            f".claude/ gate — its refusal text is absent, so this non-zero "
            f"code proves nothing about the allowlist.\n{combined}"
        )
        assert offender in combined, (
            f"REFUSE ARM FAILED: the refusal did not name the offending "
            f"path {offender!r}.\n{combined}"
        )

        head = _run(["git", "rev-parse", "HEAD"], sandbox_repo)
        assert head.returncode != 0, (
            f"REFUSE ARM FAILED: a commit object exists, so the non-zero "
            f"exit did not actually prevent it. HEAD={head.stdout.strip()}"
        )

    def test_refuse_arm_other_claude_file_still_blocked(
        self, sandbox_repo: Path
    ):
        """REFUSE (unchanged behaviour): installed plugin files stay blocked.

        A generated/installed path sharing no prefix with any allowlist entry.
        This is the arm that goes red if a future widening replaces the
        allowlist with something like ``^\\.claude/settings`` or drops the gate
        altogether.
        """
        offender = ".claude/config/auto_approve_policy.json"
        proc, combined = self._write_stage_commit(
            sandbox_repo, offender, "installed file must be blocked"
        )

        assert proc.returncode != 0, (
            f"REFUSE ARM FAILED: the commit succeeded for {offender}.\n"
            f"{combined}"
        )
        assert self.CLAUDE_REFUSAL in combined, (
            f"REFUSE ARM FAILED: something blocked the commit, but NOT the "
            f".claude/ gate — its refusal text is absent.\n{combined}"
        )
        assert offender in combined, (
            f"REFUSE ARM FAILED: the refusal did not name the offending "
            f"path {offender!r}.\n{combined}"
        )

        head = _run(["git", "rev-parse", "HEAD"], sandbox_repo)
        assert head.returncode != 0, (
            f"REFUSE ARM FAILED: a commit object exists, so the non-zero "
            f"exit did not actually prevent it. HEAD={head.stdout.strip()}"
        )

    def test_refuse_arm_non_ascii_claude_path_blocked(self, sandbox_repo: Path):
        """REFUSE (GAP 1): a non-ASCII ``.claude/`` path must not escape the gate.

        ``core.quotePath`` defaults to ON. Under it, git wraps any path holding
        a non-ASCII byte, a backslash, a double quote or a control character in
        double quotes and C-escapes it. The old selector was ``grep
        "^\\.claude/"`` over the QUOTED stream, so ``.claude/café-évil.json``
        arrived as ``"\\.claude/caf\\303\\251-\\303\\251vil.json"`` — leading
        ``"``, escaped bytes — and did not match. It left the gate's DOMAIN
        rather than being permitted by the allowlist: the gate never saw it, so
        it had nothing to refuse, and the commit went through with rc=0.

        The class covered is "any staged ``.claude/`` path git chooses to
        C-quote", not this one filename. ``é`` is the cheapest member to
        construct; a backslash or a newline in the name is the same defect.

        THREE SETUP CONTROLS, all before the commit is attempted:

        1. ``core.quotePath`` is explicitly set to ``true`` in this repo, so
           the arm does not depend on the ambient default staying ON.
        2. ``git diff --cached --name-only`` must actually COME BACK QUOTED.
           If it does not, quoting is not happening and this arm is not about
           GAP 1 at all — it must fail at SETUP, not pass as a false green.
        3. ``git diff --cached --raw -z`` must carry the path VERBATIM as one
           NUL-delimited field. That is the property the fix relies on.
        """
        offender = ".claude/café-évil.json"

        set_quote = _run(
            ["git", "config", "core.quotePath", "true"], sandbox_repo
        )
        assert set_quote.returncode == 0, (
            f"SETUP FAILED: could not set core.quotePath:\n{set_quote.stderr}"
        )

        target = sandbox_repo / offender
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('{"permissions": {"allow": []}}\n', encoding="utf-8")

        # -f, not -A: see the class docstring.
        add = _run(["git", "add", "-f", offender], sandbox_repo)
        assert add.returncode == 0, (
            f"SETUP FAILED: could not stage {offender}:\n"
            f"{add.stdout}{add.stderr}"
        )

        # SETUP CONTROL 2 — quoting must really be happening.
        name_only = _run(
            ["git", "diff", "--cached", "--name-only"], sandbox_repo
        )
        assert name_only.stdout.strip().startswith('"'), (
            f"SETUP CONTROL FAILED: with core.quotePath=true, git did NOT "
            f"quote {offender!r} in --name-only. This arm exists to prove the "
            f"gate survives quoting; if quoting is not happening the arm is "
            f"vacuous. Got: {name_only.stdout!r}"
        )

        # SETUP CONTROL 3 — the -z stream must be verbatim and hold exactly
        # this one record, so a refusal can only be attributed to this path.
        raw_z = subprocess.run(
            ["git", "diff", "--cached", "--raw", "-z"],
            cwd=str(sandbox_repo),
            capture_output=True,
            timeout=60,
        )
        fields = [f for f in raw_z.stdout.split(b"\0") if f]
        assert fields[1:] == [offender.encode("utf-8")], (
            f"SETUP CONTROL FAILED: the --raw -z stream must hold exactly one "
            f"path field equal to the raw UTF-8 bytes of {offender!r}. If git "
            f"ever quotes or re-encodes under -z, the fix's premise is wrong "
            f"and this test must fail HERE rather than downstream. Got: "
            f"{raw_z.stdout!r}"
        )

        proc = _run(
            ["git", "commit", "-m", "non-ascii path must be blocked"],
            sandbox_repo,
        )
        combined = proc.stdout + proc.stderr
        self._assert_claude_gate_refused(
            proc, combined, offender, sandbox_repo
        )

    def test_refuse_arm_case_variant_of_allowlisted_name_blocked(
        self, tmp_path: Path
    ):
        """REFUSE (GAP 2): ``.Claude/settings.json`` must be refused, not missed.

        The strongest arm available for GAP 2: a case variant of an
        ALLOWLISTED name. The selector now folds case, so the path is SELECTED;
        the allowlist stays byte-exact, so it is then REFUSED. Folding the
        allowlist too would have permitted it and reopened the hole from the
        other side.

        WHY THIS TEST BUILDS ITS OWN REPO INSTEAD OF USING ``sandbox_repo``.
        Measured on this machine (APFS, ``core.ignorecase=true``), both arms:

        - Where ``.claude/`` ALREADY EXISTS on disk, ``printf > .Claude/x``
          lands in the existing directory, and ``git add -f .Claude/x`` stages
          it NORMALISED as ``.claude/x``.
        - Where no colliding directory exists, ``mkdir .Claude`` creates it
          with the requested case and git records ``.Claude/x`` VERBATIM.

        :func:`_build_sandbox_repo` deliberately creates ``.claude/`` on disk
        (``CLAUDE.md`` links to ``.claude/PROJECT.md``), so under that fixture
        the staged path would normalise to ``.claude/settings.json`` — an
        ALLOWLISTED pair — and this test would pass for entirely the wrong
        reason. That fixture is NOT modified; this test builds a minimal repo
        with no ``.claude/`` at all.

        SETUP CONTROL: the ``--raw -z`` stream must contain the MIXED-CASE
        spelling before the commit is attempted. If git ever normalises it,
        this test fails at SETUP rather than going green over nothing.
        """
        repo = tmp_path / "no_claude_dir"
        repo.mkdir()

        _run(["git", "init", "-q", "-b", "main", "."], repo)
        _run(["git", "config", "user.email", "guard@example.test"], repo)
        _run(["git", "config", "user.name", "Case Variant Guard"], repo)
        _run(["git", "config", "commit.gpgsign", "false"], repo)

        # The hook's FIRST step runs this unconditionally under `set -e`.
        # Stubbed to exit 0 so the structure gate is not the subject here.
        structure_stub = repo / "scripts" / "validate_structure.py"
        structure_stub.parent.mkdir(parents=True, exist_ok=True)
        structure_stub.write_text(
            "#!/usr/bin/env python3\n"
            '"""Sandbox stub — the structure gate is not the subject here."""\n'
            "raise SystemExit(0)\n",
            encoding="utf-8",
        )

        hook_dest = repo / ".git" / "hooks" / "pre-commit"
        hook_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PRE_COMMIT, hook_dest)
        hook_dest.chmod(0o755)

        offender = ".Claude/settings.json"
        (repo / ".Claude").mkdir()
        (repo / offender).write_text(
            '{"permissions": {"allow": []}}\n', encoding="utf-8"
        )

        # SETUP CONTROL A: the mixed-case directory is what is actually on
        # disk. If the filesystem folded it to `.claude`, say so here.
        on_disk = sorted(p.name for p in repo.iterdir() if p.name != ".git")
        assert ".Claude" in on_disk, (
            f"SETUP CONTROL FAILED: the mixed-case directory did not survive "
            f"creation on this filesystem. Directory listing: {on_disk!r}"
        )

        add = _run(["git", "add", "-f", offender], repo)
        assert add.returncode == 0, (
            f"SETUP FAILED: could not stage {offender}:\n"
            f"{add.stdout}{add.stderr}"
        )

        # SETUP CONTROL B: git must have RECORDED the mixed case. This is the
        # load-bearing one — where `.claude/` exists on disk git normalises
        # the spelling away, and the gate would then be matching an
        # allowlisted pair rather than a case variant.
        raw_z = subprocess.run(
            ["git", "diff", "--cached", "--raw", "-z"],
            cwd=str(repo),
            capture_output=True,
            timeout=60,
        )
        fields = [f for f in raw_z.stdout.split(b"\0") if f]
        assert fields[1:] == [offender.encode("utf-8")], (
            f"SETUP CONTROL FAILED: the index must hold exactly the "
            f"MIXED-CASE path {offender!r}. If git normalised it to "
            f".claude/settings.json, that is an ALLOWLISTED pair and this "
            f"test would pass without ever exercising the case-folding "
            f"selector. Got: {raw_z.stdout!r}"
        )

        proc = _run(["git", "commit", "-m", "case variant must be blocked"], repo)
        combined = proc.stdout + proc.stderr
        self._assert_claude_gate_refused(proc, combined, offender, repo)


# ---------------------------------------------------------------------------
# The scanner itself, driven directly on crafted `--raw -z` streams.
#
# These arms are FUNCTION-LEVEL: `claude_gate_scan` is sliced out of the live
# hook by `_extract_gate_scan_source` (which carries its own positive control)
# and run with its stream on stdin. There is no way to make `git` emit a
# deliberately malformed record stream, so the fail-closed behaviour GAP 3 is
# about cannot be reached end-to-end; driving the function is the only honest
# way to watch it refuse.
# ---------------------------------------------------------------------------


class TestGateScanStreamHandling:
    """Rename/copy bookkeeping and fail-closed behaviour, both arms."""

    def test_rename_record_does_not_desync_the_scan(self):
        """``R``/``C`` records carry TWO paths; consuming one desyncs the rest.

        ``--raw -z`` emits one NUL-terminated metadata field, then the path,
        then a SECOND path for rename/copy statuses ONLY. There is no
        disambiguating NUL before the first path, so a scanner that skips a
        record without consuming path2 will read path2 as the NEXT record's
        METADATA — silently dropping a genuinely staged ``.claude/`` file.
        That exact desync already bit this repo once
        (``plugins/autonomous-dev/lib/git_operations.py:532-541``).

        Arm (a) is the desync detector: a rename of two ordinary files
        followed by a real offender. If path2 is left in the stream the
        offender is misparsed and the scan reports something other than
        exactly that one path.

        Arm (b) pins WHICH path a rename is judged on: the DESTINATION. A
        rename INTO ``.claude/`` is a new ``.claude/`` file however it got
        there, and must be reported under its destination name.
        """
        # --- Arm (a): rename then offender ---------------------------------
        stream = _raw_z_record(
            "100644", "README.md", status="R100", dest="README-renamed.md"
        ) + _raw_z_record("100644", ".claude/evil.json")

        rc, out = _run_gate_scan(stream)

        assert rc == 0, (
            f"ARM (a) FAILED: a well-formed two-record stream must not be "
            f"rejected. rc={rc}, stdout={out!r}"
        )
        assert out == b".claude/evil.json 100644\n", (
            f"ARM (a) FAILED — DESYNC: the scan must report EXACTLY the "
            f"offender that followed the rename. Anything else means the "
            f"rename's second path was not consumed and the next record's "
            f"metadata was misread. Got: {out!r}"
        )

        # --- Arm (b): rename INTO .claude/ ---------------------------------
        into_claude = _raw_z_record(
            "100644", "notes.md", status="R100", dest=".claude/notes.md"
        )

        rc_b, out_b = _run_gate_scan(into_claude)

        assert rc_b == 0, (
            f"ARM (b) FAILED: a well-formed rename record must not be "
            f"rejected. rc={rc_b}, stdout={out_b!r}"
        )
        assert out_b == b".claude/notes.md 100644\n", (
            f"ARM (b) FAILED: a rename must be judged on its DESTINATION. "
            f"Judging the source would let `git mv notes.md .claude/notes.md` "
            f"through, because the source is not under .claude/. Got: {out_b!r}"
        )

        # --- Arm (b) negative control: the SOURCE must not be what matters --
        out_of_claude = _raw_z_record(
            "100644", ".claude/notes.md", status="R100", dest="notes.md"
        )
        rc_c, out_c = _run_gate_scan(out_of_claude)
        assert rc_c == 0 and out_c == b"", (
            f"ARM (b) CONTROL FAILED: a rename OUT OF .claude/ lands at a "
            f"destination outside the gate's domain and must be permitted. "
            f"A scan that reported it would be judging the SOURCE, which is "
            f"the mirror-image bug. rc={rc_c}, stdout={out_c!r}"
        )

        # --- Arm (c): the ORDERING constraint at its literal boundary -------
        #
        # Arms (a) and (b) are killed by moving the R/C consumption past the
        # SELECTOR `continue`, but NOT by moving it past the DELETION
        # `continue` alone — measured 2026-09-04, that weaker move is an
        # equivalent mutant against them. This arm closes that hole: a record
        # that is BOTH a rename AND carries destination mode 000000 reaches
        # the deletion `continue` with its second path still unread.
        #
        # git does not emit this shape (a deletion is status `D`, not `R`),
        # and that is precisely why it is here: the comment at pre-commit:87-94
        # states the second path must be consumed BEFORE *any* `continue`, and
        # that claim is only observable at a boundary git does not itself
        # produce. The scan is a parser over an untrusted stream, so the
        # constraint holds regardless of what git happens to emit.
        rename_deleted = _raw_z_record(
            "000000", "old.md", status="R100", dest=".claude/dest.json"
        ) + _raw_z_record("100644", ".claude/evil.json")

        rc_d, out_d = _run_gate_scan(rename_deleted)

        assert rc_d == 0 and out_d == b".claude/evil.json 100644\n", (
            f"ARM (c) FAILED — DESYNC AT THE DELETION SKIP: a rename record "
            f"whose destination mode is 000000 must still consume its second "
            f"path before continuing. It did not, so the following record's "
            f"metadata was misread and a genuinely staged .claude/ path was "
            f"dropped or the scan aborted. rc={rc_d}, stdout={out_d!r}"
        )

    @pytest.mark.parametrize(
        "label,stream",
        [
            (
                "metadata field with no path following it",
                b":100644 100644 1111111 2222222 A\0",
            ),
            (
                "metadata not NUL-terminated (truncated stream)",
                b":100644 100644 1111111 2222222 A",
            ),
            (
                "destination mode is not six octal digits",
                b":100644 12345x 1111111 2222222 A\0.claude/evil.json\0",
            ),
            (
                "status field absent from the metadata",
                b":100644 100644 1111111\0.claude/evil.json\0",
            ),
            (
                "rename record missing its destination path",
                b":100644 100644 1111111 2222222 R100\0old-name.md\0",
            ),
        ],
    )
    def test_scan_fails_closed_on_malformed_stream(
        self, label: str, stream: bytes
    ):
        """REFUSE (GAP 3): a stream the scan cannot account for returns 3.

        The pre-2026-09-04 form ended in ``|| true`` with no ``pipefail``, so
        an unreadable or truncated stream produced an empty capture that was
        indistinguishable from "nothing staged" — and the gate PERMITTED a
        commit it had never inspected. The scan now returns 3, never a partial
        answer, and the hook turns any non-zero status into a refusal.

        The class covered is "any record stream that does not parse", not one
        crafted string; each arm below breaks a DIFFERENT structural
        assumption (missing path, missing terminator, malformed mode, short
        metadata, missing rename destination).

        The permitting arm is
        :meth:`test_scan_permits_the_empty_stream` — without it, a scan
        hard-wired to ``return 3`` would satisfy every arm here.
        """
        rc, out = _run_gate_scan(stream)

        assert rc == 3, (
            f"FAIL-CLOSED ARM FAILED ({label}): the scan returned {rc}, not 3. "
            f"A malformed stream must produce a REFUSAL, never a partial "
            f"answer that reads as 'nothing staged'. stdout={out!r}"
        )

    def test_scan_permits_the_empty_stream(self):
        """PERMIT: an empty index is not a malformed one.

        The negative control on the five fail-closed arms above. A scan that
        simply ``return 3``-ed unconditionally would satisfy all of them and
        would block every commit in the repository; this arm is what
        distinguishes "fails closed on garbage" from "cannot succeed".
        """
        rc, out = _run_gate_scan(b"")

        assert rc == 0, (
            f"PERMIT ARM FAILED: an empty --raw -z stream means nothing is "
            f"staged and must return 0. Got rc={rc}, stdout={out!r}"
        )
        assert out == b"", (
            f"PERMIT ARM FAILED: an empty stream must name no offenders. "
            f"Got: {out!r}"
        )

    def test_scan_permits_well_formed_allowlisted_and_deleted_records(self):
        """PERMIT: the three allowlisted pairs, plus a deletion, in one stream.

        A second permitting arm at function level, and the one that pins the
        two deliberate holes in the scan: allowlisted ``(path, mode)`` pairs,
        and deletions (new mode ``000000``, which stage no object and so
        cannot carry smuggled content).
        """
        stream = (
            _raw_z_record("120000", ".claude/PROJECT.md")
            + _raw_z_record("100644", ".claude/settings.json", status="M")
            + _raw_z_record("100644", ".claude/logs/cloud-runs.jsonl", status="M")
            + _raw_z_record("000000", ".claude/config/policy.json", status="D")
            + _raw_z_record("100644", "docs/HOOKS.md", status="M")
        )

        rc, out = _run_gate_scan(stream)

        assert rc == 0, f"PERMIT ARM FAILED: rc={rc}, stdout={out!r}"
        assert out == b"", (
            f"PERMIT ARM FAILED: the three allowlisted pairs, a .claude/ "
            f"DELETION, and an unrelated path must all pass. Got: {out!r}"
        )

    def test_scan_refuses_allowlisted_path_at_the_wrong_mode(self):
        """REFUSE: the allowlist keys on the PAIR, not on the path.

        The function-level twin of
        :meth:`TestClaudeAllowlistIsExactMatch.test_refuse_arm_settings_json_as_symlink_blocked`.
        Kept here as the permitting arm's mirror: without it, the permit arm
        above is satisfied by a scan that allowlists on path alone.
        """
        stream = _raw_z_record("120000", ".claude/settings.json")

        rc, out = _run_gate_scan(stream)

        assert rc == 0, f"rc={rc}, stdout={out!r}"
        assert out == b".claude/settings.json 120000\n", (
            f"REFUSE ARM FAILED: .claude/settings.json is allowlisted ONLY at "
            f"mode 100644. Staged as a symlink (120000) it must be reported. "
            f"Got: {out!r}"
        )
