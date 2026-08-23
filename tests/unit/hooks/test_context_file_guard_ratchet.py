"""Per-repo ratchet arms for the context-file size guard (Issue #1648).

The guard shipped in #1639 enforces ABSOLUTE size limits. In a repo that
inherited an oversized context file that is a permanently-red check: realign's
``.claude/PROJECT.md`` is 456 lines against a 225 ceiling, so every edit to it
was refused, forever, with no edit able to clear the refusal.

#1648 makes the effective block limit ``max(hard_ceiling, line_count_at_git_HEAD)``
— *you may not make this file worse than it already is at HEAD*. These are the
arms that prove it, and the ones that prove it cannot go wrong quietly:

* The ratchet RELAXES (permits at the committed size) and REFUSES (one line above).
* It can never TIGHTEN — a mark below the ceiling changes nothing.
* Every one of the eleven fallback paths lands on the ABSOLUTE ceiling, never
  on a relaxed one, each proven inside a fixture where a working ratchet would
  have permitted.
* The ``--git-dir`` pin is load-bearing: unpinned, git walks PAST an invalid
  ``.git`` into an ancestor repo and reports THAT repository's HEAD.
* Four source-level mutations each flip a named arm, so none of the above can
  be passing for the wrong reason.

Fixtures are real ``git init`` + commit under ``tmp_path``, and the hook is
invoked as a SUBPROCESS — which also sidesteps the ``lru_cache`` staleness
boundary by construction. The in-process arms clear that cache in a fixture.

**No arm in this file writes outside ``tmp_path``.** The hook records every
refusal to ``.claude/logs/hook-blocks.jsonl`` resolved against its own cwd
(``hook_telemetry._resolve_log_path``), so an arm run with ``cwd`` inside a
real repository appends a real row to that repository's real log. The
cross-repo arms therefore run against an alternates-backed READ-ONLY view of
the target repo built under ``tmp_path`` — see :func:`_readonly_view_of` — and
``TestAC2CrossRepoConfirmation`` carries a standing fingerprint fixture that
fails if the real repo moved at all.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from .test_context_file_guard_enforcement import (
    HOOK_PATH,
    _decision,
    _run_hook,
    _write_lines,
    hook,
)

#: The reproducer's shape, from realign: 456 lines committed against a 225
#: absolute ceiling and a 150 target. Measured 2026-08-23 with the hook's own
#: ``splitlines()`` counter (``git ls-tree`` mode ``100644`` — a regular file,
#: so unlike THIS repo's symlinked copy it does carry a usable mark).
REPRODUCER_HEAD_LINES = 456

#: The size finding's discriminator, distinguishing it from the overlap half.
SIZE_DISCRIMINATOR = ".claude/PROJECT.md is "


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_head_mark_cache():
    """``_head_line_count`` is process-global and memoised.

    Subprocess arms are immune, but the in-process arms below re-commit files
    under paths pytest may reuse. Clearing on both sides makes a stale mark
    impossible rather than merely unlikely.
    """
    hook._head_line_count.cache_clear()
    yield
    hook._head_line_count.cache_clear()


@pytest.fixture
def home(tmp_path: Path) -> Path:
    """A ``$HOME`` with no global CLAUDE.md and no MEMORY.md.

    Without this the machine's real context files leak into every arm.
    """
    path = tmp_path / "home"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    """Run a git command inside ``root``, failing loudly."""
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _git_init(root: Path) -> Path:
    """Create a real git repository at ``root``.

    ``-c`` is a GIT-level option and must precede the subcommand: measured,
    ``git init -c init.defaultBranch=main`` fails with
    ``error: unknown switch `c'``.
    """
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "-c", "init.defaultBranch=main", "init", "-q", str(root)],
        check=True,
        capture_output=True,
        text=True,
    )
    return root


def _git_commit(root: Path, message: str = "base") -> None:
    """Stage everything and commit, with signing and identity pinned off."""
    _git(root, "add", "-A")
    _git(
        root,
        "-c",
        "commit.gpgsign=false",
        "-c",
        "user.email=t@t",
        "-c",
        "user.name=t",
        "commit",
        "-q",
        "-m",
        message,
    )


def _repo_with_committed_project_md(root: Path, head_lines: int) -> Path:
    """A repo whose ``.claude/PROJECT.md`` is committed at ``head_lines``."""
    _git_init(root)
    _write_lines(root / ".claude" / "PROJECT.md", head_lines)
    _git_commit(root)
    return root


def _edit(path: Path) -> dict:
    """A PostToolUse Edit payload targeting ``path``."""
    return {"tool_name": "Edit", "tool_input": {"file_path": str(path)}}


def _run_hook_at(
    hook_path: Path,
    cwd: Path,
    home_dir: Path,
    payload: dict | None,
    *,
    extra_env: dict | None = None,
) -> subprocess.CompletedProcess:
    """Invoke an ARBITRARY copy of the hook as a subprocess.

    Delegates to the shared ``_run_hook`` for the ordinary case so the two
    files cannot drift apart; the explicit form exists only for the arms that
    need a different hook copy (mutants) or a doctored ``PATH``.
    """
    if hook_path == HOOK_PATH and extra_env is None:
        return _run_hook(cwd, home_dir, payload)

    env = dict(os.environ)
    env["HOME"] = str(home_dir)
    env.pop("AUTONOMOUS_DEV_BYPASS", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(hook_path)],
        cwd=str(cwd),
        env=env,
        input=json.dumps(payload) if payload is not None else "",
        capture_output=True,
        text=True,
        timeout=60,
    )


def _project_run(
    repo: Path,
    home_dir: Path,
    working_lines: int,
    *,
    cwd: Path | None = None,
    hook_path: Path = HOOK_PATH,
    extra_env: dict | None = None,
) -> subprocess.CompletedProcess:
    """Set ``.claude/PROJECT.md`` to ``working_lines`` and run the hook on it."""
    project = repo / ".claude" / "PROJECT.md"
    _write_lines(project, working_lines)
    return _run_hook_at(
        hook_path, cwd or repo, home_dir, _edit(project), extra_env=extra_env
    )


def _refused(result: subprocess.CompletedProcess) -> bool:
    """Did the hook emit a SIZE refusal for PROJECT.md?

    Keyed on the size finding's own discriminator so an overlap block — a
    different half of this hook — can never be miscounted as a size refusal.
    """
    decision = _decision(result)
    if decision is None:
        return False
    return SIZE_DISCRIMINATOR in decision.get("reason", "")


# ---------------------------------------------------------------------------
# AC1 — the reproducer, hermetically. Both arms.
# ---------------------------------------------------------------------------


class TestAC1Reproducer:
    """The sentence #1648 exists to delete: an edit refused with no way out."""

    def test_permits_at_the_committed_size_and_refuses_one_line_above(
        self, tmp_path: Path, home: Path
    ) -> None:
        """Both arms in one test, against one fixture.

        At 456 the file is exactly as bad as it already is at HEAD, so the
        guard has nothing to say. At 457 it got worse, and that is the whole
        rule.
        """
        repo = _repo_with_committed_project_md(tmp_path / "repo", REPRODUCER_HEAD_LINES)

        permitted = _project_run(repo, home, REPRODUCER_HEAD_LINES)
        refused = _project_run(repo, home, REPRODUCER_HEAD_LINES + 1)

        assert not _refused(permitted), (
            "a file at exactly its committed size must be permitted; "
            f"stdout={permitted.stdout!r}"
        )
        assert _refused(refused), (
            "one line above the committed size must refuse; "
            f"stdout={refused.stdout!r} stderr={refused.stderr!r}"
        )

    def test_absolute_ceiling_still_refuses_a_repo_with_no_mark(
        self, tmp_path: Path, home: Path
    ) -> None:
        """The ratchet must not become a licence: an unmarked repo is unchanged.

        Same working size that the fixture above PERMITS, in a repo that has
        committed nothing. Without this, "permitted at 456" is indistinguishable
        from "the size guard was switched off".
        """
        repo = _git_init(tmp_path / "repo")
        result = _project_run(repo, home, REPRODUCER_HEAD_LINES)
        assert _refused(result), "no mark means the 225 ceiling still governs"


# ---------------------------------------------------------------------------
# AC4 — a mark can never TIGHTEN
# ---------------------------------------------------------------------------


class TestAC4MarkNeverTightens:
    """``max`` semantics: a mark below the ceiling is clamped away entirely."""

    def test_small_mark_does_not_narrow_the_band(
        self, tmp_path: Path, home: Path
    ) -> None:
        """PROJECT.md committed at 100. The 225 ceiling must still govern.

        A ``min`` in place of the ``max`` would set the limit to 100 and refuse
        the 200-line working copy — a guard that got STRICTER because the file
        used to be small.
        """
        repo = _repo_with_committed_project_md(tmp_path / "repo", 100)

        permitted = _project_run(repo, home, 200)
        refused = _project_run(repo, home, 226)

        assert not _refused(permitted), (
            "200 is under the 225 ceiling and must be permitted despite the "
            f"100-line mark; stdout={permitted.stdout!r}"
        )
        assert _refused(refused), "226 is over the 225 ceiling and must refuse"


# ---------------------------------------------------------------------------
# AC5 — every fallback lands STRICT
# ---------------------------------------------------------------------------

#: A working copy one line over the absolute PROJECT.md ceiling (225). Every
#: fallback row must refuse it: a fallback that relaxed would permit.
OVER_CEILING = 226


def _fallback_git_absent(root: Path) -> tuple[Path, dict | None]:
    """D3 row 1 — the ``git`` binary is not on PATH.

    The repo DOES carry a 456-line mark, so a ratchet that survived the missing
    binary would permit 226. It must not.
    """
    repo = _repo_with_committed_project_md(root / "repo", REPRODUCER_HEAD_LINES)
    empty = root / "empty-path"
    empty.mkdir()
    return repo, {"PATH": str(empty)}


def _fallback_invalid_git_dir(root: Path) -> tuple[Path, dict | None]:
    """D3 row 2 — ``.git`` is a directory but not a valid repository."""
    repo = _repo_with_committed_project_md(root / "repo", REPRODUCER_HEAD_LINES)
    for child in sorted((repo / ".git").rglob("*"), reverse=True):
        child.unlink() if child.is_file() or child.is_symlink() else child.rmdir()
    return repo, None


def _fallback_no_commits(root: Path) -> tuple[Path, dict | None]:
    """D3 row 4 — a real repository with zero commits."""
    return _git_init(root / "repo"), None


def _fallback_untracked_at_head(root: Path) -> tuple[Path, dict | None]:
    """D3 row 5 — the file exists on disk but was never committed.

    The bootstrap case answers itself: a brand-new 226-line PROJECT.md is bloat
    being introduced right now, not history being inherited.
    """
    repo = _git_init(root / "repo")
    (repo / "README.md").write_text("readme\n")
    _git_commit(repo)
    return repo, None


def _fallback_shallow_clone(root: Path) -> tuple[Path, dict | None]:
    """D3 row 6 — a depth-1 clone still carries the HEAD tree.

    The mark reads as 100, below the ceiling, so 226 must still refuse.
    """
    origin = _repo_with_committed_project_md(root / "origin", 100)
    dest = root / "shallow"
    subprocess.run(
        ["git", "clone", "--depth", "1", "-q", f"file://{origin}", str(dest)],
        check=True,
        capture_output=True,
        text=True,
    )
    return dest, None


def _fallback_squashed_history(root: Path) -> tuple[Path, dict | None]:
    """D3 row 7 — HEAD holds current content; a squash cannot RAISE the mark.

    The file was 456 lines in an earlier commit and is 100 at HEAD. The mark is
    100, so the 225 ceiling governs and 226 refuses. If history rather than HEAD
    were consulted, the orphaned 456 would relax the limit.
    """
    repo = _repo_with_committed_project_md(root / "repo", REPRODUCER_HEAD_LINES)
    _write_lines(repo / ".claude" / "PROJECT.md", 100)
    _git_commit(repo, "shrink")
    _git(repo, "reset", "--soft", "HEAD~1")
    _git_commit(repo, "squashed")
    return repo, None


def _fallback_non_utf8_blob(root: Path) -> tuple[Path, dict | None]:
    """D3 row 8 — the committed blob is not valid UTF-8.

    ``text=True`` raises ``UnicodeDecodeError``, which is a ``ValueError`` and
    NOT an ``OSError`` — it is caught by name, and this row is why.
    """
    repo = _git_init(root / "repo")
    project = repo / ".claude" / "PROJECT.md"
    project.parent.mkdir(parents=True, exist_ok=True)
    project.write_bytes(b"\xff\xfe binary not text \x00\n" * 400)
    _git_commit(repo)
    return repo, None


def _fallback_git_file_worktree(root: Path) -> tuple[Path, dict | None]:
    """D3 row 9 — ``.git`` is a FILE, as in a worktree or submodule.

    ``--git-dir`` does not accept one, so the ratchet is unavailable by design.
    The repo carries a 456-line mark, so this row is discriminating.
    """
    repo = _repo_with_committed_project_md(root / "repo", REPRODUCER_HEAD_LINES)
    real_git = root / "real-git-dir"
    (repo / ".git").rename(real_git)
    (repo / ".git").write_text(f"gitdir: {real_git}\n")
    return repo, None


def _fallback_git_hangs(root: Path) -> tuple[Path, dict | None]:
    """D3 row 11 — the subprocess exceeds ``timeout=2``.

    A ``git`` that never returns is the failure mode the timeout exists for,
    and the one that would otherwise get the hook killed by the sidecar. The
    repo carries a 456-line mark, so a ratchet that somehow completed would
    permit 226.
    """
    repo = _repo_with_committed_project_md(root / "repo", REPRODUCER_HEAD_LINES)
    fake_bin = root / "fake-bin"
    fake_bin.mkdir()
    fake_git = fake_bin / "git"
    fake_git.write_text("#!/bin/sh\nsleep 5\n")
    fake_git.chmod(0o755)
    return repo, {"PATH": f"{fake_bin}:{os.environ.get('PATH', '')}"}


#: The D3 fallback matrix. Rows 3 (nested repo) and 10 (symlink) are NEW and
#: get dedicated arms below — row 3 must be built inside a real repository and
#: row 10's working size is not 226.
FALLBACK_ROWS = {
    "row1_git_binary_absent": _fallback_git_absent,
    "row2_invalid_git_dir": _fallback_invalid_git_dir,
    "row4_zero_commits": _fallback_no_commits,
    "row5_untracked_at_head": _fallback_untracked_at_head,
    "row6_shallow_clone": _fallback_shallow_clone,
    "row7_squashed_history": _fallback_squashed_history,
    "row8_non_utf8_blob": _fallback_non_utf8_blob,
    "row9_git_is_a_file": _fallback_git_file_worktree,
    "row11_git_hangs": _fallback_git_hangs,
}


class TestAC5EveryFallbackLandsStrict:
    """A missing mark is not a reset. It can only refuse MORE."""

    @pytest.mark.parametrize("row_name", sorted(FALLBACK_ROWS))
    def test_fallback_refuses_over_ceiling(
        self, tmp_path: Path, home: Path, row_name: str
    ) -> None:
        repo, extra_env = FALLBACK_ROWS[row_name](tmp_path)
        result = _project_run(
            repo, home, OVER_CEILING, extra_env=extra_env
        )
        assert _refused(result), (
            f"{row_name}: a fallback must land on the ABSOLUTE ceiling, so "
            f"{OVER_CEILING} lines must refuse; stdout={result.stdout!r} "
            f"stderr={result.stderr[-400:]!r}"
        )

    # -- Positive controls, same class: an always-None parser cannot pass ----

    def test_positive_control_real_repo_permits_at_its_committed_size(
        self, tmp_path: Path, home: Path
    ) -> None:
        """Every row above asserts a REFUSAL. Without this arm they would all
        pass against a ``_head_line_count`` that returned None unconditionally.
        """
        repo = _repo_with_committed_project_md(tmp_path / "repo", REPRODUCER_HEAD_LINES)
        result = _project_run(repo, home, REPRODUCER_HEAD_LINES)
        assert not _refused(result), (
            "the mark must be readable in an ordinary repo, or every strict "
            f"row above proves nothing; stdout={result.stdout!r}"
        )

    def test_positive_control_permits_when_run_from_a_subdirectory(
        self, tmp_path: Path, home: Path
    ) -> None:
        """Pins the path resolution empirically, whatever the explanation.

        ``HEAD:<rel>`` is resolved relative to the TOP OF THE TREE, not to the
        process's cwd — measured, and NOT because ``--git-dir`` implies bare
        mode (``--is-bare-repository`` returns ``false`` and ``--show-toplevel``
        returns the cwd).
        """
        repo = _repo_with_committed_project_md(tmp_path / "repo", REPRODUCER_HEAD_LINES)
        subdir = repo / "deep" / "nested"
        subdir.mkdir(parents=True)

        result = _project_run(repo, home, REPRODUCER_HEAD_LINES, cwd=subdir)
        assert not _refused(result), (
            "the mark must resolve identically from a subdirectory; "
            f"stdout={result.stdout!r}"
        )


class TestAC5N2NestedRepoIsPinned:
    """D3 row 3 — the bug REV 1 shipped as a passing row.

    ``get_repo_root`` stops at the first ancestor where ``.git`` EXISTS. Git
    does not stop there: it walks PAST an invalid ``.git`` into an ancestor
    repository and returns THAT repository's HEAD. Reproduced directly —
    ``git show HEAD:CLAUDE.md`` from inside an empty nested ``.git`` returns the
    OUTER repo's content with returncode 0.

    Unpinned, a repo with a malformed ``.git`` reads a FOREIGN repository's file
    as its own size mark. This arm is built INSIDE a real repository so it fails
    against the unpinned version rather than passing on an accident of where
    pytest happens to put ``tmp_path``.
    """

    @staticmethod
    def _nested(tmp_path: Path) -> tuple[Path, Path]:
        """Outer real repo at 456; inner dir with an EMPTY ``.git`` directory."""
        outer = _repo_with_committed_project_md(
            tmp_path / "outer", REPRODUCER_HEAD_LINES
        )
        inner = outer / "inner"
        (inner / ".git").mkdir(parents=True)
        _write_lines(inner / ".claude" / "PROJECT.md", OVER_CEILING)
        return outer, inner

    def test_inner_repo_does_not_inherit_the_outer_mark(
        self, tmp_path: Path, home: Path
    ) -> None:
        """The inner file is 226 against a 225 ceiling and MUST be refused.

        Under the unpinned version the outer repo's 456-line mark is read
        instead, 226 falls under it, and the edit is wrongly permitted.
        """
        _outer, inner = self._nested(tmp_path)
        result = _run_hook_at(
            HOOK_PATH, inner, home, _edit(inner / ".claude" / "PROJECT.md")
        )
        assert _refused(result), (
            "an invalid .git must fail CLOSED, not inherit an ancestor "
            f"repository's HEAD; stdout={result.stdout!r}"
        )

    def test_positive_control_the_outer_repo_itself_still_ratchets(
        self, tmp_path: Path, home: Path
    ) -> None:
        """Same tree, valid ``.git``: the outer repo permits at its own 456.

        Proves the refusal above comes from the PIN and not from the fixture
        being unreadable in some general way.
        """
        outer, _inner = self._nested(tmp_path)
        result = _project_run(outer, home, REPRODUCER_HEAD_LINES)
        assert not _refused(result), (
            f"the outer repo must still ratchet; stdout={result.stdout!r}"
        )


class TestAC5SymlinkGetsNoRatchet:
    """D3 row 10 — a committed SYMLINK context file gets NO ratchet.

    ``git show HEAD:`` does not resolve symlinks: it returns the link TARGET
    (one line, no trailing newline), while the hook's own reader follows the
    link and measures the content. The two sides measure different objects, so
    the mark is 1, and every ceiling is at least 200 — the ceiling always wins.
    Strict BY CONSTRUCTION, not by luck.

    THIS repo is that repo: ``.claude/PROJECT.md`` here is mode ``120000``.
    The limitation is asserted rather than left silent.
    """

    def test_symlinked_project_md_is_refused_at_its_target_size(
        self, tmp_path: Path, home: Path
    ) -> None:
        repo = _git_init(tmp_path / "repo")
        target = repo / "PROJECT.md"
        _write_lines(target, REPRODUCER_HEAD_LINES)
        link = repo / ".claude" / "PROJECT.md"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(Path("..") / "PROJECT.md")
        _git_commit(repo)

        # The symlink is committed as a symlink, not as content.
        listing = _git(repo, "ls-tree", "HEAD", ".claude/PROJECT.md").stdout
        assert listing.startswith("120000"), f"fixture is not a symlink: {listing!r}"

        result = _run_hook_at(HOOK_PATH, repo, home, _edit(link))
        assert _refused(result), (
            "a symlinked context file gets no ratchet: the mark is the link "
            "target's length, so the absolute ceiling governs"
        )

    def test_the_mark_for_a_symlink_is_the_link_target_not_the_content(
        self, tmp_path: Path
    ) -> None:
        """The mechanism, asserted directly rather than inferred from a refusal."""
        repo = _git_init(tmp_path / "repo")
        _write_lines(repo / "PROJECT.md", REPRODUCER_HEAD_LINES)
        link = repo / ".claude" / "PROJECT.md"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(Path("..") / "PROJECT.md")
        _git_commit(repo)

        mark = hook._head_line_count(link, repo)
        assert mark == 1, (
            f"expected the one-line link target as the mark, got {mark} — if "
            "this is 456 the two sides now measure the same object and the "
            "symlink limitation has been fixed"
        )
        assert mark < hook.BLOCK_PROJECT_LINES, "the ceiling must still win"


# ---------------------------------------------------------------------------
# AC6 — repo-tracked files only
# ---------------------------------------------------------------------------


class TestAC6OutsideTheRepoGetsNoMark:
    """``~/.claude/CLAUDE.md`` and ``MEMORY.md`` are outside every repo.

    ``path.relative_to(repo_root)`` raises, so no mark exists and the absolute
    limits are untouched. No per-repo mark could fix a file shared by every
    repo anyway.
    """

    def test_global_claude_md_over_ceiling_is_still_refused(
        self, tmp_path: Path, home: Path
    ) -> None:
        repo = _repo_with_committed_project_md(tmp_path / "repo", REPRODUCER_HEAD_LINES)
        global_md = _write_lines(home / ".claude" / "CLAUDE.md", 400)

        result = _run_hook_at(HOOK_PATH, repo, home, _edit(global_md))
        decision = _decision(result)
        assert decision is not None, f"expected a refusal; stderr={result.stderr!r}"
        assert "global" in decision["reason"]

    def test_memory_md_over_ceiling_is_still_refused(
        self, tmp_path: Path, home: Path
    ) -> None:
        repo = _repo_with_committed_project_md(tmp_path / "repo", REPRODUCER_HEAD_LINES)
        slug = str(repo.resolve()).replace("/", "-")
        memory_md = _write_lines(
            home / ".claude" / "projects" / slug / "memory" / "MEMORY.md", 400
        )

        result = _run_hook_at(HOOK_PATH, repo, home, _edit(memory_md))
        decision = _decision(result)
        assert decision is not None, f"expected a refusal; stderr={result.stderr!r}"
        assert "MEMORY.md is 400 lines" in decision["reason"]

    def test_positive_control_repo_claude_md_in_the_same_repo_does_ratchet(
        self, tmp_path: Path, home: Path
    ) -> None:
        """Same repo, same 400 lines — but a REPO-tracked file, so it ratchets.

        Without this the two refusals above would be satisfied by a ratchet that
        never worked for anything.
        """
        repo = _git_init(tmp_path / "repo")
        _write_lines(repo / "CLAUDE.md", 400)
        _git_commit(repo)

        result = _run_hook_at(HOOK_PATH, repo, home, _edit(repo / "CLAUDE.md"))
        assert _decision(result) is None, (
            "CLAUDE.md committed at 400 must be permitted at 400; "
            f"stdout={result.stdout!r}"
        )


# ---------------------------------------------------------------------------
# AC7 — no permanent yellow
# ---------------------------------------------------------------------------


class TestAC7NoPermanentYellow:
    """A permanently-yellow check trains everyone to ignore the whole class.

    When the mark is in force BOTH bands move to it, so the outcome is binary:
    at-or-below the committed size is silent, one line above refuses.
    """

    def test_at_the_mark_the_hook_is_completely_silent(
        self, tmp_path: Path, home: Path
    ) -> None:
        repo = _repo_with_committed_project_md(tmp_path / "repo", REPRODUCER_HEAD_LINES)
        result = _project_run(repo, home, REPRODUCER_HEAD_LINES)

        assert result.stdout.strip() == "", f"stdout must be empty: {result.stdout!r}"
        assert "WARNING" not in result.stderr, (
            "a repo permanently above target must not warn on every single "
            f"edit forever; stderr={result.stderr!r}"
        )

    def test_positive_control_a_mark_below_the_ceiling_still_warns(
        self, tmp_path: Path, home: Path
    ) -> None:
        """The warn band is suppressed ONLY in the ratcheted case.

        Mark 200 is below the 225 ceiling, so the ratchet is not in force and
        the ordinary 150-line target still advises. Without this arm, "silent"
        above is indistinguishable from a hook that never warns.
        """
        repo = _repo_with_committed_project_md(tmp_path / "repo", 200)
        result = _project_run(repo, home, 200)

        assert not _refused(result), "200 is under the ceiling and must not refuse"
        assert "WARNING" in result.stderr, (
            f"the unratcheted warn band must still fire; stderr={result.stderr!r}"
        )


# ---------------------------------------------------------------------------
# AC8 — the refusal names the ratchet, and does not say "trim to your size"
# ---------------------------------------------------------------------------


class TestAC8RatchetedMessage:
    """With ``warn_limit == block_limit`` the pre-#1648 text renders the same
    integer three times and tells the developer to trim to the size they are
    one line above. The ratcheted variant carries four DISTINCT integers.
    """

    @staticmethod
    def _project_message(
        repo: Path, monkeypatch: pytest.MonkeyPatch, working_lines: int
    ) -> str:
        """The PROJECT.md block message, in process, with $HOME neutralised."""
        _write_lines(repo / ".claude" / "PROJECT.md", working_lines)
        monkeypatch.setattr(
            hook, "global_claude_md_path", lambda: repo / "nope" / "CLAUDE.md"
        )
        monkeypatch.setattr(
            hook, "derive_memory_path", lambda: repo / "nope" / "MEMORY.md"
        )
        hook._head_line_count.cache_clear()
        blocking = [
            f.message
            for f in hook.collect_size_findings(repo)
            if f.severity == hook.BLOCK and f.label == "PROJECT.md"
        ]
        assert len(blocking) == 1, f"expected one PROJECT.md block, got {blocking}"
        return blocking[0]

    def test_ratcheted_block_names_count_mark_ceiling_target_and_owner(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = _repo_with_committed_project_md(tmp_path / "repo", REPRODUCER_HEAD_LINES)
        message = self._project_message(repo, monkeypatch, REPRODUCER_HEAD_LINES + 1)

        # Four DISTINCT integers, so no two roles collapse into one number.
        assert "457" in message, "the measured count"
        assert "456" in message, "the in-force mark"
        assert "225" in message, "the ORIGINAL absolute ceiling, displaced by the mark"
        assert "150" in message, "the ORIGINAL target, still the real goal"

        assert "committed" in message, "the refusal must name its own provenance"
        assert "HEAD" in message, "and where that provenance lives"
        assert "REQUIRED NEXT ACTION" in message
        assert "realign#1681" in message, "the refusal must point at its owner"

    def test_ratcheted_block_does_not_tell_you_to_trim_to_your_current_size(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The specific nonsense the pre-#1648 text would render here."""
        repo = _repo_with_committed_project_md(tmp_path / "repo", REPRODUCER_HEAD_LINES)
        message = self._project_message(repo, monkeypatch, REPRODUCER_HEAD_LINES + 1)

        assert "over the hard ceiling of 456 (target 456)" not in message
        assert "trim .claude/PROJECT.md back to 456 lines or fewer" not in message

    def test_negative_control_unratcheted_block_is_byte_identical(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A NON-ratcheted refusal must be the pre-#1648 message, byte for byte.

        This is what makes the whole change additive: the empty ``ceiling_note``
        default selects today's text exactly, which is why all 59 pre-existing
        arms pass unedited.
        """
        repo = _repo_with_committed_project_md(tmp_path / "repo", 100)
        message = self._project_message(repo, monkeypatch, OVER_CEILING)

        expected = (
            "BLOCKED: .claude/PROJECT.md is 226 lines — over the hard ceiling of "
            "225 (target 150). This file loads into context on "
            "every turn, so every line above target is paid for permanently.\n"
            "REQUIRED NEXT ACTION: trim .claude/PROJECT.md back to 150 lines or "
            "fewer before continuing. Move detail into docs/ and link to it; "
            "keep the context file a map, not a datasheet.\n"
            f"File: {repo / '.claude' / 'PROJECT.md'}"
        )
        assert message == expected
        assert "HEAD" not in message, "an unratcheted refusal must not mention HEAD"
        assert "committed" not in message


# ---------------------------------------------------------------------------
# AC9 — the two classify paths agree
# ---------------------------------------------------------------------------

#: ``(mark_at_head, working_lines, expected_band)``.
#:
#: ``collect_size_findings`` bands a second time, from the ``specs`` map, and
#: that path is gated on ``if not message: continue`` — so the OK band never
#: reaches it and a divergence there could ship green under every other arm.
#: The OK rows are included for exactly that reason.
#:
#: There is no WARN row for a mark ABOVE the ceiling: when the ratchet is in
#: force both bands sit on the mark, so the warn band is empty BY DESIGN. That
#: emptiness is asserted separately below rather than left as a missing row.
AGREEMENT_ROWS = [
    (None, 100, "ok"),
    (None, 200, "warn"),
    (None, 226, "block"),
    (100, 100, "ok"),
    (100, 200, "warn"),
    (100, 226, "block"),
    (REPRODUCER_HEAD_LINES, REPRODUCER_HEAD_LINES, "ok"),
    (REPRODUCER_HEAD_LINES, REPRODUCER_HEAD_LINES + 1, "block"),
]


class TestAC9BothClassifyPathsAgree:
    """``_size_finding`` bands internally; ``collect_size_findings`` bands again.

    Both must read the SAME spec. They do by construction — one dict — and this
    asserts it rather than assuming it.
    """

    @pytest.mark.parametrize("mark,working,expected_band", AGREEMENT_ROWS)
    def test_severity_matches_a_second_classify_from_the_same_spec(
        self, tmp_path: Path, mark: int | None, working: int, expected_band: str
    ) -> None:
        if mark is None:
            repo = _git_init(tmp_path / "repo")
        else:
            repo = _repo_with_committed_project_md(tmp_path / "repo", mark)
        _write_lines(repo / ".claude" / "PROJECT.md", working)

        hook._head_line_count.cache_clear()
        spec = hook._project_md_spec(repo)
        count, severity, _message = hook._size_finding(**spec)

        assert count == working
        assert severity == expected_band, (
            f"mark={mark} working={working}: expected {expected_band}, got "
            f"{severity} (limits {spec['warn_limit']}/{spec['block_limit']})"
        )
        assert severity == hook.classify_size(
            count, spec["warn_limit"], spec["block_limit"]
        ), "the two classify paths must agree, including in the OK band"

    def test_the_warn_band_is_empty_when_the_mark_is_in_force(
        self, tmp_path: Path
    ) -> None:
        """The missing AGREEMENT_ROWS entry, asserted rather than omitted."""
        repo = _repo_with_committed_project_md(tmp_path / "repo", REPRODUCER_HEAD_LINES)
        hook._head_line_count.cache_clear()
        spec = hook._project_md_spec(repo)

        assert spec["warn_limit"] == spec["block_limit"] == REPRODUCER_HEAD_LINES
        assert spec["ceiling_note"] == "absolute ceiling 225, target 150"


# ---------------------------------------------------------------------------
# AC10 — the hook writes nothing
# ---------------------------------------------------------------------------


#: The ONE file this hook may create, and it is not #1648's. Measured: a
#: refusal writes ``.claude/logs/hook-blocks.jsonl`` and nothing else. That is
#: the sanctioned refusal sink wired in #1639 (INV-1: a refusal that is not
#: recorded is not evidence), and it is also the observer the per-commit-drift
#: revisit trigger is keyed to. It predates #1648 and is asserted, not excused.
REFUSAL_SINK = ".claude/logs/hook-blocks.jsonl"


class TestAC10RatchetCreatesNoArtifact:
    """There is no baseline file. The mark IS the repository's own history.

    The rejected designs all committed a baseline — a ``.context-budget`` TSV,
    a ``.claude/``-resident config, an in-source constant table. Each needed a
    format, a writer, a bootstrap step and a stale-detector, and each added a
    second representation of something git already stores. This asserts that
    none of them came back.
    """

    @staticmethod
    def _snapshot(repo: Path) -> tuple[str, list[str]]:
        status = _git(repo, "status", "--porcelain").stdout
        tree = sorted(
            str(p.relative_to(repo))
            for p in repo.rglob("*")
            if ".git" not in p.relative_to(repo).parts
        )
        return status, tree

    def test_a_permit_writes_absolutely_nothing(
        self, tmp_path: Path, home: Path
    ) -> None:
        repo = _repo_with_committed_project_md(tmp_path / "repo", REPRODUCER_HEAD_LINES)

        # Snapshot AFTER the working copy is set, so only the HOOK's writes
        # (if any) can move the needle.
        _write_lines(repo / ".claude" / "PROJECT.md", REPRODUCER_HEAD_LINES)
        before = self._snapshot(repo)
        permitted = _run_hook_at(
            HOOK_PATH, repo, home, _edit(repo / ".claude" / "PROJECT.md")
        )

        assert self._snapshot(repo) == before, "a permit must write nothing at all"
        # Or "wrote nothing" is the trivial property of a hook that did nothing.
        assert not _refused(permitted)

    def test_a_refusal_writes_only_the_sanctioned_refusal_sink(
        self, tmp_path: Path, home: Path
    ) -> None:
        """The refusal sink is the ONLY new file, and no mark is persisted.

        MEASURED rather than assumed: the sink appears, carries this gate's own
        metadata, and is the sole addition. A ratchet that quietly wrote its
        baseline somewhere would show up here as a second entry.
        """
        repo = _repo_with_committed_project_md(tmp_path / "repo", REPRODUCER_HEAD_LINES)
        _write_lines(repo / ".claude" / "PROJECT.md", REPRODUCER_HEAD_LINES + 1)
        status_before, tree_before = self._snapshot(repo)

        refused = _run_hook_at(
            HOOK_PATH, repo, home, _edit(repo / ".claude" / "PROJECT.md")
        )
        assert _refused(refused), "the refusing arm must actually refuse"

        _status_after, tree_after = self._snapshot(repo)
        new_paths = {
            path for path in set(tree_after) - set(tree_before)
            if not (repo / path).is_dir()
        }
        assert new_paths == {REFUSAL_SINK}, (
            "#1648 introduces NO artifact: the only file a refusal may create "
            f"is the #1639 refusal sink, got {sorted(new_paths)}"
        )

        # No tracked file changed: the ratchet never rewrites the repo's own
        # context files, and the sink lands under gitignored .claude/logs/.
        assert _git(repo, "status", "--porcelain", "--untracked-files=no").stdout == (
            status_before
        )

        rows = [
            json.loads(line)
            for line in (repo / REFUSAL_SINK).read_text().splitlines()
            if line.strip()
        ]
        assert rows, "the refusal must be recorded, or it is not evidence"
        assert any(
            row.get("metadata", {}).get("gate") == "context-file-size-and-overlap"
            for row in rows
        ), f"the sink must carry this gate's metadata: {rows}"

    @pytest.mark.parametrize(
        "rejected_artifact",
        [
            # Alternative (b): a committed TSV baseline plus a CLI to write it.
            ".context-budget",
            # Alternative (c): a per-repo mark resident under .claude/.
            ".claude/.context-budget",
            ".claude/context-budget.json",
        ],
    )
    def test_no_rejected_baseline_artifact_is_created(
        self, tmp_path: Path, home: Path, rejected_artifact: str
    ) -> None:
        """Lock the rejected designs out by name, in both arms.

        Each of these was a real earlier draft. A future author reviving one
        trips this instead of shipping a second source of truth.
        """
        repo = _repo_with_committed_project_md(tmp_path / "repo", REPRODUCER_HEAD_LINES)
        _project_run(repo, home, REPRODUCER_HEAD_LINES)
        _project_run(repo, home, REPRODUCER_HEAD_LINES + 1)

        assert not (repo / rejected_artifact).exists(), (
            f"{rejected_artifact} was created — the mark must remain a pure "
            "function of git HEAD, with no second representation"
        )


# ---------------------------------------------------------------------------
# The memoisation is a CORRECTNESS property, not a performance one
# ---------------------------------------------------------------------------


class TestSubprocessBudget:
    """Uncached, this hook would fail OPEN under a hung ``git``.

    Each repo-tracked spec is built TWICE per invocation — once via its
    ``check_*`` wrapper and once in ``collect_size_findings``'s ``specs`` map.
    Two files x two builds is four lookups. Uncached that is four subprocesses
    at ``timeout=2`` each = 8s against the sidecar's 5s, and a PostToolUse hook
    killed mid-run emits nothing while silence is read as APPROVAL. Memoised it
    is 2 x 2s = 4s, back inside the budget.

    So the cache is not an optimisation that may be dropped for clarity.
    """

    def test_four_lookups_collapse_to_two_subprocesses(self, tmp_path: Path) -> None:
        repo = _repo_with_committed_project_md(tmp_path / "repo", REPRODUCER_HEAD_LINES)
        _write_lines(repo / "CLAUDE.md", 50)

        hook._head_line_count.cache_clear()
        hook.collect_size_findings(repo)
        info = hook._head_line_count.cache_info()

        assert info.hits + info.misses == 4, (
            f"expected four lookups (2 files x 2 spec builds), got {info}"
        )
        assert info.misses == 2, (
            f"expected exactly two git subprocesses, got {info.misses}. Four "
            "would be 8s worst case against a 5s sidecar, and a killed "
            "PostToolUse hook fails OPEN."
        )

    def test_the_git_call_is_bounded_by_a_timeout(self) -> None:
        """The other half of the bound: no single call may run unbounded.

        A cache with no timeout still hangs forever on one call.
        """
        source = HOOK_PATH.read_text()
        head_body = source.split("def _head_line_count", 1)[1].split("\ndef ", 1)[0]
        assert "timeout=2" in head_body, (
            "the git subprocess must carry an explicit timeout, or the worst "
            "case is unbounded rather than 4s"
        )
        assert "stdin=subprocess.DEVNULL" in head_body, (
            "stdin carries the hook payload and must not be inherited by git"
        )


# ---------------------------------------------------------------------------
# AC11 — the ratchet is load-bearing, proven by mutation
# ---------------------------------------------------------------------------

#: ``name -> (anchor, replacement, why)``. Each anchor must appear EXACTLY once
#: in the hook source; a mutation that does not apply is a harness failure, not
#: a pass.
MUTATIONS = {
    "M1_max_becomes_min": (
        "effective_limit = max(",
        "effective_limit = min(",
        "transposing the ratchet's algebra must break the permitting arm",
    ),
    "M2_mark_always_none": (
        '    git_dir = repo_root / ".git"',
        '    return None\n    git_dir = repo_root / ".git"',
        "a mark that never resolves must fall back to the absolute ceiling",
    ),
    "M3_in_force_comparison_inverted": (
        'if effective_limit > spec["block_limit"]:',
        'if effective_limit < spec["block_limit"]:',
        "the in-force test must decide whether the mark is applied at all",
    ),
    "M4_git_dir_pin_dropped": (
        'f"--git-dir={git_dir}", ',
        "",
        "without the pin git walks into an ancestor repo and reads ITS HEAD",
    ),
}


def _hook_copy(dest_dir: Path, *, anchor: str = "", replacement: str = "") -> Path:
    """Copy the hook, optionally applying one source-level mutation."""
    source = HOOK_PATH.read_text()
    if anchor:
        assert source.count(anchor) == 1, (
            f"mutation anchor {anchor!r} appears {source.count(anchor)} times; "
            "the harness can only mutate a unique site"
        )
        mutated = source.replace(anchor, replacement)
        assert mutated != source, "mutation did not change the source"
        source = mutated
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "validate_claude_md_size.py"
    dest.write_text(source)
    return dest


class TestAC11MutationsFlipNamedArms:
    """Copy the hook, break one thing, watch a named arm flip. The real hook is
    never edited.

    M1, M2 and M3 all flip the SAME arm, and that is a finding rather than an
    oversight: under the ``max(ceiling, mark)`` formulation an inverted in-force
    test cannot make the guard STRICTER — the clamp has already discarded any
    mark below the ceiling — so every way of breaking the ratchet collapses to
    "the ratchet stops applying". AC4's tightening arm therefore holds by
    construction, not merely by test.
    """

    def test_pristine_copy_reproduces_the_permitting_arm(
        self, tmp_path: Path, home: Path
    ) -> None:
        """Verify the instrument BEFORE trusting any mutation result.

        The copy runs outside the plugin tree, so it resolves none of the
        optional ``lib/`` imports. If that alone changed the outcome, every
        mutation below would be attributing a copy artefact to its mutation.
        """
        repo = _repo_with_committed_project_md(tmp_path / "repo", REPRODUCER_HEAD_LINES)
        pristine = _hook_copy(tmp_path / "pristine")

        permitted = _project_run(
            repo, home, REPRODUCER_HEAD_LINES, hook_path=pristine
        )
        refused = _project_run(
            repo, home, REPRODUCER_HEAD_LINES + 1, hook_path=pristine
        )

        assert not _refused(permitted), "the pristine copy must permit at the mark"
        assert _refused(refused), "the pristine copy must refuse one line above"

    @pytest.mark.parametrize("name", ["M1_max_becomes_min", "M2_mark_always_none",
                                      "M3_in_force_comparison_inverted"])
    def test_breaking_the_ratchet_makes_the_committed_size_refuse(
        self, tmp_path: Path, home: Path, name: str
    ) -> None:
        """Named arm: AC1's permitting arm. Must flip PERMIT -> REFUSE."""
        anchor, replacement, why = MUTATIONS[name]
        repo = _repo_with_committed_project_md(tmp_path / "repo", REPRODUCER_HEAD_LINES)
        mutant = _hook_copy(tmp_path / name, anchor=anchor, replacement=replacement)

        result = _project_run(repo, home, REPRODUCER_HEAD_LINES, hook_path=mutant)
        assert _refused(result), (
            f"{name} changed nothing — {why}. A mutation that does not flip its "
            f"named arm is a harness failure; stdout={result.stdout!r}"
        )

    def test_dropping_the_git_dir_pin_makes_the_nested_repo_permit(
        self, tmp_path: Path, home: Path
    ) -> None:
        """Named arm: 5-N2. Must flip REFUSE -> PERMIT.

        This is the mutation that proves the pin is not decoration. Without
        ``--git-dir`` the inner repo silently adopts the OUTER repository's
        456-line mark and permits its own 226-line file.
        """
        anchor, replacement, why = MUTATIONS["M4_git_dir_pin_dropped"]
        _outer, inner = TestAC5N2NestedRepoIsPinned._nested(tmp_path)
        mutant = _hook_copy(
            tmp_path / "M4", anchor=anchor, replacement=replacement
        )

        payload = _edit(inner / ".claude" / "PROJECT.md")
        pristine_result = _run_hook_at(
            _hook_copy(tmp_path / "M4-control"), inner, home, payload
        )
        mutant_result = _run_hook_at(mutant, inner, home, payload)

        assert _refused(pristine_result), (
            "control: the unmutated copy must refuse here, or the flip below "
            "is not attributable to the mutation"
        )
        assert not _refused(mutant_result), (
            f"M4 changed nothing — {why}; stdout={mutant_result.stdout!r}"
        )


# ---------------------------------------------------------------------------
# AC2 — the reproducer against the real repo, READ-ONLY
# ---------------------------------------------------------------------------


def _readonly_view_of(source_repo: Path, dest: Path) -> Path:
    """Build a sandboxed repo under ``dest`` that reads ``source_repo``'s HEAD.

    ``dest`` is an ordinary ``git init`` repo with two things borrowed from
    ``source_repo``, both read-only:

    * ``.git/objects/info/alternates`` naming ``source_repo``'s object store,
      so every object resolves out of the REAL repository — no copy, no
      ``clone`` of a 44 GB history, and nothing written on the source side;
    * ``HEAD`` pointed at ``source_repo``'s real HEAD commit.

    So ``git --git-dir=<dest>/.git show HEAD:<path>`` returns the SAME blob,
    at the same mode, that the same command returns inside ``source_repo``.
    Verified 2026-08-23: blob ``adee3700`` / 456 lines / mode ``100644``,
    identical from both sides.

    **Why this exists.** The hook writes its refusals to
    ``.claude/logs/hook-blocks.jsonl`` resolved against ITS OWN cwd. Running
    it with ``cwd`` inside a real developer repo therefore appends a real row
    to that repo's real log the moment anything blocks — a write outside the
    test sandbox. Prevention beats snapshot-and-restore here: with cwd inside
    ``tmp_path`` there is no window in which the write exists, and the
    protection holds for any future writer, not just this one sink.

    **What is preserved and what is not.** The mark still comes from the
    source repository's own committed history — its real object store, its
    real HEAD, its real tree entry (so a symlinked or untracked context file
    would still fall back strict). What a view cannot carry is the source
    repo's own directory layout: whether its ``.git`` is a directory rather
    than a worktree gitfile, and whether it carries ``.claude/.bypass``. Both
    are asserted directly by the caller instead of being traded away.

    Args:
        source_repo: A real git repository, read but never written.
        dest: Path under ``tmp_path`` to create the view at.

    Returns:
        ``dest``.
    """
    _git_init(dest)
    alternates = dest / ".git" / "objects" / "info" / "alternates"
    alternates.parent.mkdir(parents=True, exist_ok=True)
    alternates.write_text(f"{source_repo / '.git' / 'objects'}\n")
    head = _git(source_repo, "rev-parse", "HEAD").stdout.strip()
    _git(dest, "update-ref", "HEAD", head)
    return dest


def _write_bytes(path: Path, payload: bytes) -> Path:
    """Write ``payload`` to ``path``, creating parents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


class TestAC2CrossRepoConfirmation:
    """realign is the ONLY repo where this guard can currently refuse anything.

    Read-only in every consumer repo — and read-only *by construction*, not by
    intent: no arm here uses a real repo as the hook's cwd, so no refusal this
    class provokes can reach a real repo's telemetry log. The 456/457 arms run
    against an alternates-backed view of realign's real HEAD built under
    ``tmp_path`` (:func:`_readonly_view_of`).

    The DEPLOYED copy is updated by ``deploy-all.sh`` in a later step. Until
    then these arms assert against the SOURCE copy — which is the copy the
    change lives in — and report the deployed copy's state rather than
    manufacturing a red that no code change here could clear.
    """

    REALIGN = Path.home() / "Dev" / "realign"
    DEPLOYED = Path.home() / ".claude" / "hooks" / "validate_claude_md_size.py"

    @pytest.fixture(autouse=True)
    def _realign_is_untouched(self):
        """Standing proof that the prevention above actually holds.

        Fingerprints realign's refusal log and working tree around EVERY arm
        in this class, including arms added later. ``--no-optional-locks``
        keeps the check itself read-only: a plain ``git status`` may refresh
        and rewrite ``.git/index``, which would make the instrument the very
        thing it is watching for.
        """
        before = self._realign_fingerprint()
        yield
        after = self._realign_fingerprint()
        assert after == before, (
            "an arm in this class wrote into the real ~/Dev/realign tree. "
            "Cross-repo arms must run against a tmp_path view, never with a "
            f"real repo as cwd.\nbefore={before}\nafter={after}"
        )

    @classmethod
    def _realign_fingerprint(cls) -> dict:
        """Digest of realign's refusal log plus its working-tree status."""
        if not (cls.REALIGN / ".git").is_dir():
            return {"present": False}
        log = cls.REALIGN / ".claude" / "logs" / "hook-blocks.jsonl"
        return {
            "present": True,
            "log_sha256": (
                hashlib.sha256(log.read_bytes()).hexdigest() if log.exists() else None
            ),
            "status": _git(
                cls.REALIGN, "--no-optional-locks", "status", "--porcelain"
            ).stdout,
        }

    def test_ac2a_realign_project_md_edit_is_not_refused_on_size(
        self, tmp_path: Path, home: Path
    ) -> None:
        """The ONLY discriminating cross-repo arm. Both arms, nothing written.

        The permitting arm is realign's real committed content at its real
        committed size: it must draw no SIZE finding. The refusing arm is that
        same content plus one line: it must block — and that block is what
        proves the sandbox, because the row it records has to land in the
        view's ``.claude/logs/`` and realign's log has to be byte-identical
        afterwards (asserted by ``_realign_is_untouched``).
        """
        project = self.REALIGN / ".claude" / "PROJECT.md"
        if not project.exists():
            print(f"AC2a vacuous: {project} is absent on this machine")
            return

        # The two properties a cwd-inside-realign run carried and a view does
        # not. Restored directly rather than silently dropped.
        assert (self.REALIGN / ".git").is_dir(), (
            "realign's .git is no longer a directory — it is a worktree or "
            "submodule, D3 row 9, and gets no ratchet at all"
        )
        assert not (self.REALIGN / ".claude" / ".bypass").exists(), (
            "realign now carries .claude/.bypass, so main() short-circuits "
            "before any check runs and this guard is inert there — the "
            "one-repo blast radius this plan is scoped to no longer holds"
        )

        # Positive control FIRST: the instrument must be able to emit the very
        # discriminator whose absence is asserted below. Without it, "absent"
        # is indistinguishable from a hook that cannot produce it at all.
        control_repo = _git_init(tmp_path / "control")
        control = _project_run(control_repo, home, OVER_CEILING)
        assert _refused(control), (
            "positive control failed: the size discriminator is unreachable, "
            "so its absence against realign would prove nothing"
        )

        view = _readonly_view_of(self.REALIGN, tmp_path / "realign-view")
        view_project = view / ".claude" / "PROJECT.md"
        real_bytes = project.read_bytes()

        for label, hook_path in self._copies_under_test():
            _write_bytes(view_project, real_bytes)
            permitted = _run_hook_at(hook_path, view, home, _edit(view_project))
            reason = (_decision(permitted) or {}).get("reason", "")
            assert SIZE_DISCRIMINATOR not in reason, (
                f"{label}: realign's PROJECT.md is at its own committed size "
                f"and must no longer be refused on size; reason={reason[:400]!r}"
            )

            _write_bytes(view_project, real_bytes + b"one line more\n")
            refused = _run_hook_at(hook_path, view, home, _edit(view_project))
            assert _refused(refused), (
                f"{label}: one line above realign's real committed size must "
                f"refuse; stdout={refused.stdout!r}"
            )

        # The sink is LIVE and landed inside the sandbox. Without this the
        # "realign untouched" assertion would also pass on a hook whose
        # telemetry import degraded to a silent no-op (the instrument error
        # recorded under AC10), which proves nothing about isolation.
        sink = view / ".claude" / "logs" / "hook-blocks.jsonl"
        assert sink.exists(), (
            "no refusal row was recorded anywhere: hook_telemetry is not "
            "importable for this hook copy, so the isolation assertion below "
            "is measuring a dead sink rather than a redirected one"
        )
        rows = [json.loads(line) for line in sink.read_text().splitlines() if line.strip()]
        assert any(
            row.get("metadata", {}).get("gate") == "context-file-size-and-overlap"
            for row in rows
        ), f"the refusal landed in the sandbox but under no known gate: {rows!r}"

    def test_ac2b_both_arms_against_a_throwaway_repo_not_realign(
        self, tmp_path: Path, home: Path
    ) -> None:
        """Both arms at realign's exact size, without writing to realign.

        Runs the DEPLOYED copy once it carries the ratchet, and the source copy
        always — so the arm is never vacuous. cwd is the ``tmp_path`` repo
        throughout; realign is only ever ``read_text``-ed for a version probe,
        and ``_realign_is_untouched`` holds that to account.
        """
        repo = _repo_with_committed_project_md(tmp_path / "repo", REPRODUCER_HEAD_LINES)

        for label, hook_path in self._copies_under_test():
            permitted = _project_run(
                repo, home, REPRODUCER_HEAD_LINES, hook_path=hook_path
            )
            refused = _project_run(
                repo, home, REPRODUCER_HEAD_LINES + 1, hook_path=hook_path
            )
            assert not _refused(permitted), f"{label}: must permit at 456"
            assert _refused(refused), f"{label}: must refuse at 457"

    def _copies_under_test(self) -> list[tuple[str, Path]]:
        copies = [("source", HOOK_PATH)]
        if self.DEPLOYED.exists() and "_head_line_count" in self.DEPLOYED.read_text():
            copies.append(("deployed", self.DEPLOYED))
        else:
            print(
                "AC2b: deployed copy predates #1648 — source copy asserted; "
                "re-run after `bash scripts/deploy-all.sh`"
            )
        return copies

    def test_the_other_repos_are_inert_because_they_are_bypassed(self) -> None:
        """Coverage claimed honestly: three of five repos carry ``.claude/.bypass``.

        ``main()`` short-circuits on ``is_bypassed()`` before any check runs, so
        this guard cannot act there at all. No arm anywhere claims five-repo or
        three-repo coverage, and this one names why.
        """
        bypassed = []
        for name in ("spektiv", "homeassistant", "vllm-mlx"):
            repo = Path.home() / "Dev" / name
            if not repo.exists():
                continue
            bypassed.append((name, (repo / ".claude" / ".bypass").exists()))

        if not bypassed:
            print("no consumer repos present on this machine; arm is vacuous")
            return
        for name, has_bypass in bypassed:
            assert has_bypass, (
                f"{name} no longer carries .claude/.bypass, so the guard is now "
                "live there — this plan's one-repo blast radius no longer holds"
            )
