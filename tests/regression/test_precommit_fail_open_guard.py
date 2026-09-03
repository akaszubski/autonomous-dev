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
  uses ``scripts/hooks/pre-commit:73``, a real, live, correct ``|| true``:
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
``pre-commit`` lines 107-113, 126-132, 139-145 and 152-158 (re-measured
2026-09-03; the previous citation here was stale by three lines and by the
+21 shift the mode-pinned allowlist introduced). They refuse (the
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
        """NEGATIVE CONTROL: ``pre-commit:73`` is correct and must pass.

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
        ``pre-commit:15`` (file header), ``:70`` (a comment naming the prior
        workaround) and ``:92`` (the .claude/ staging gate) predate this work
        and belong to other gates.
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
# `.claude/settings.json.bak-20260903-081206` too. The gate now subtracts with
# `grep -vxF`, and the three tests below watch it PERMIT the one path that
# `.gitignore` un-ignores and REFUSE two paths that it does not.
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

    #: The refusal line the ``.claude/`` gate prints; see ``pre-commit:76``.
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
