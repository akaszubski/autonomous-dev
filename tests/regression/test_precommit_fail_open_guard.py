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
  uses ``scripts/hooks/pre-commit:30``, a real, live, correct ``|| true``:
  a command substitution whose pipeline ends in ``grep``, guarding against
  grep's no-match exit under ``set -e``, with an ``if [ -n ... ]`` on the
  next line rather than a ``$?`` capture. Different shape from the bug, so
  the guard is proven scoped to the class and not to the instance.

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
``pre-commit`` lines 57-63, 76-82, 89-95 and 102-108. They refuse (the
script exits non-zero) but print nothing. That is a different defect,
deliberately out of scope here, and left untouched.
"""

import os
import re
import shutil
import subprocess
import sys
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
        """NEGATIVE CONTROL: ``pre-commit:30`` is correct and must pass.

        A DIFFERENT shape from the bug: a command substitution whose
        pipeline ends in ``grep``, where ``|| true`` exists to stop grep's
        no-match status aborting the script under ``set -e``. The result is
        tested with ``[ -n "$..." ]`` on the next line — there is no ``$?``
        capture at all. A guard that flagged this would be scoped to the
        string ``|| true`` rather than to the fail-open class.
        """
        source = PRE_COMMIT.read_text(encoding="utf-8")
        lines = source.split("\n")

        # A NAIVE matcher — "any line containing `|| true`" — is what this
        # control discriminates against. If no such line exists, the control
        # is inert and proves nothing.
        naive_hits = [
            (num, line)
            for num, line in enumerate(lines, 1)
            if "|| true" in _SHELL_COMMENT.sub("", line)
        ]
        assert naive_hits, (
            "NEGATIVE CONTROL VOID: scripts/hooks/pre-commit no longer "
            "contains any `|| true` line, so this control is not exercising "
            "anything. Re-point it at another live legitimate use, or delete "
            "it — do not leave a control that cannot fail."
        )

        line_num, line_text = naive_hits[0]
        assert "grep" in line_text, (
            f"NEGATIVE CONTROL VOID: pre-commit:{line_num} is no longer the "
            f"grep-guarding `|| true` this control was written against: "
            f"{line_text.strip()!r}"
        )
        # It is legitimate for two independent reasons, both different from
        # the bug: the `|| true` is INSIDE a command substitution (so it is
        # not even at end-of-line), and the next line is `if [ -n ... ]`,
        # not a `$?` capture.
        assert line_text.rstrip().endswith(")"), (
            f"NEGATIVE CONTROL VOID: pre-commit:{line_num} is no longer a "
            f"command substitution: {line_text.strip()!r}"
        )
        assert not _RC_CAPTURE.search(lines[line_num]), (
            f"NEGATIVE CONTROL VOID: pre-commit:{line_num + 1} is now a $? "
            f"capture, which would make this a REAL defect, not a control."
        )

        findings = find_fail_open_captures(source)
        assert not findings, (
            "NEGATIVE CONTROL FAILED: the guard flagged a legitimate "
            "`|| true`:\n"
            + "\n".join(
                f"  - pre-commit:{f.line_number}: {f.masking_line} / "
                f"{f.capture_line}"
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
        ``pre-commit:15`` (file header) and ``:42`` (the .claude/ staging
        gate) predate this work and belong to other gates.
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
    # but must never be STAGED — the hook's own .claude/ gate at lines 30-43
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
