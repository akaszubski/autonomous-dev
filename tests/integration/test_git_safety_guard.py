"""Both-arms proof for the integration-tier git safety guard (Issue #1638).

A guard is unproven until watched REFUSING and PERMITTING. Observed only passing,
it is indistinguishable from a guard that cannot fail; observed only blocking, it
is indistinguishable from a blanket ban on subprocess use.

The refusing cases here are deliberately authored to shapes OTHER than the
reproducer that prompted the guard (``subprocess.run(['git','commit',...])`` with
no ``cwd=``): ``git add``, ``git reset --hard``, a relative ``git -C``, a
``bash -c`` wrapper, ``check_output``, and ``Popen``. The guard covers the class
"git subcommand that can mutate repository state, reached through any stdlib
subprocess entry point, that names no safe explicit working directory" -- not the
single call site that fired.

The permitting cases prove the guard did not simply block all subprocess use:
read-only git is untouched even with no ``cwd=``, and mutating git is untouched
when it names a scratch directory.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.helpers.git_safety_guard import (
    REAL_REPO_ROOT,
    UnsafeGitInvocation,
    assess_git_invocation,
)


@pytest.fixture
def scratch_repo(tmp_path: Path) -> Path:
    """Create a throwaway git repository. Every call names ``cwd`` explicitly."""
    repo = tmp_path / "scratch"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "guard@example.test"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Guard Test"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (repo / "README.md").write_text("# scratch\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "initial"], cwd=repo, check=True, capture_output=True
    )
    return repo


# ---------------------------------------------------------------------------
# ARM 1 + 2: REFUSING
# ---------------------------------------------------------------------------


class TestGuardRefuses:
    """The guard must fire loudly, naming the call and the required fix."""

    def test_refuses_commit_without_cwd(self) -> None:
        """The reproducer shape: git commit with no explicit working directory."""
        with pytest.raises(UnsafeGitInvocation) as excinfo:
            subprocess.run(["git", "commit", "-m", "should never happen"], capture_output=True)
        message = str(excinfo.value)
        assert "git 'commit'" in message
        assert "cwd=" in message, "refusal must name the required fix"
        assert str(REAL_REPO_ROOT) in message, "refusal must name the repo at risk"

    @pytest.mark.parametrize(
        "argv",
        [
            pytest.param(["git", "add", "-A"], id="add"),
            pytest.param(["git", "reset", "--hard"], id="reset"),
            pytest.param(["git", "checkout", "-b", "x"], id="checkout"),
            pytest.param(["git", "merge", "feature"], id="merge"),
            pytest.param(["git", "rebase", "main"], id="rebase"),
            pytest.param(["git", "stash"], id="stash"),
            pytest.param(["git", "push", "origin", "master"], id="push"),
            pytest.param(["git", "tag", "v1.0.0"], id="tag"),
            pytest.param(["git", "rm", "README.md"], id="rm"),
            pytest.param(["git", "mv", "a", "b"], id="mv"),
            pytest.param(["git", "config", "user.email", "x@y.z"], id="config-write"),
            pytest.param(["git", "clean", "-fd"], id="clean"),
            pytest.param(["git", "worktree", "add", "wt"], id="worktree-add"),
        ],
    )
    def test_refuses_every_mutating_verb_without_cwd(self, argv: list[str]) -> None:
        """Shapes other than the reproducer are refused too -- this is a class guard."""
        with pytest.raises(UnsafeGitInvocation):
            subprocess.run(argv, capture_output=True)

    def test_refuses_cwd_pointing_at_real_repo_root(self) -> None:
        """Explicit cwd is not enough: it must not be the real repository."""
        with pytest.raises(UnsafeGitInvocation) as excinfo:
            subprocess.run(
                ["git", "add", "-A"], cwd=str(REAL_REPO_ROOT), capture_output=True
            )
        assert "real repository" in str(excinfo.value)

    def test_refuses_cwd_pointing_inside_real_repo(self) -> None:
        """A subdirectory of the real repo is still the real repo."""
        with pytest.raises(UnsafeGitInvocation):
            subprocess.run(
                ["git", "commit", "-m", "nope"],
                cwd=str(REAL_REPO_ROOT / "tests"),
                capture_output=True,
            )

    def test_refuses_relative_dash_c(self) -> None:
        """A relative ``git -C`` still resolves against the process CWD."""
        with pytest.raises(UnsafeGitInvocation) as excinfo:
            subprocess.run(["git", "-C", "subdir", "commit", "-m", "x"], capture_output=True)
        assert "relative" in str(excinfo.value)

    def test_refuses_git_smuggled_through_shell_wrapper(self) -> None:
        """``bash -c 'git reset --hard'`` is unwrapped and judged on its payload."""
        with pytest.raises(UnsafeGitInvocation):
            subprocess.run(["bash", "-c", "git reset --hard HEAD~1"], capture_output=True)

    def test_refuses_via_check_output_entry_point(self) -> None:
        """``check_output`` resolves ``run`` through module globals -- also covered."""
        with pytest.raises(UnsafeGitInvocation):
            subprocess.check_output(["git", "commit", "-m", "via check_output"])

    def test_refuses_via_popen_entry_point(self) -> None:
        """``Popen`` is patched independently of ``run``."""
        with pytest.raises(UnsafeGitInvocation):
            subprocess.Popen(["git", "commit", "-m", "via Popen"], stdout=subprocess.PIPE)

    def test_refuses_shell_true_string_command(self) -> None:
        """A ``shell=True`` string command is tokenised before judging."""
        with pytest.raises(UnsafeGitInvocation):
            subprocess.run("git add -A", shell=True, capture_output=True)


# ---------------------------------------------------------------------------
# ARM 3 + 4: PERMITTING
# ---------------------------------------------------------------------------


class TestGuardPermits:
    """The guard must not become a blanket ban on subprocess use."""

    def test_permits_mutating_git_in_tmpdir(self, scratch_repo: Path) -> None:
        """git commit with cwd=<tmpdir> runs normally and actually commits."""
        (scratch_repo / "feature.txt").write_text("hello\n")
        subprocess.run(["git", "add", "feature.txt"], cwd=scratch_repo, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "add feature"], cwd=scratch_repo, check=True
        )
        log = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=scratch_repo,
            check=True,
            capture_output=True,
            text=True,
        )
        assert "add feature" in log.stdout, "the permitted call must really have run"

    def test_permits_read_only_git_without_cwd(self) -> None:
        """``git status`` with no cwd is NOT blocked -- tests inspect real repo state."""
        result = subprocess.run(
            ["git", "status", "--short"], capture_output=True, text=True, check=True
        )
        assert result.returncode == 0

    @pytest.mark.parametrize(
        "argv",
        [
            pytest.param(["git", "status"], id="status"),
            pytest.param(["git", "log", "--oneline", "-1"], id="log"),
            pytest.param(["git", "rev-parse", "HEAD"], id="rev-parse"),
            pytest.param(["git", "diff", "--stat"], id="diff"),
            pytest.param(["git", "show", "--stat", "HEAD"], id="show"),
            pytest.param(["git", "stash", "list"], id="stash-list"),
            pytest.param(["git", "config", "--get", "user.email"], id="config-get"),
            pytest.param(["git", "branch", "--list"], id="branch-list"),
            pytest.param(["git", "worktree", "list"], id="worktree-list"),
            pytest.param(["git", "--version"], id="version"),
        ],
    )
    def test_permits_every_read_only_verb_without_cwd(self, argv: list[str]) -> None:
        """Classification-level check: read-only git is never refused."""
        assert assess_git_invocation(argv, {}) is None, f"{argv} must be permitted"

    def test_permits_non_git_subprocess_without_cwd(self) -> None:
        """Non-git subprocesses are untouched entirely."""
        result = subprocess.run(
            ["echo", "guard-permits-this"], capture_output=True, text=True, check=True
        )
        assert result.stdout.strip() == "guard-permits-this"

    def test_permits_absolute_dash_c_outside_real_repo(self, scratch_repo: Path) -> None:
        """``git -C <absolute tmpdir>`` names its directory explicitly and is safe."""
        assert (
            assess_git_invocation(["git", "-C", str(scratch_repo), "commit", "-m", "x"], {})
            is None
        )


# ---------------------------------------------------------------------------
# Instrument controls: the guard's own probe must be shown to work both ways
# ---------------------------------------------------------------------------


class TestRegressionIssue1638ChdirIsolation:
    """Reproduce the exact hazard shape: ``os.chdir()`` then an unqualified git write.

    This is the pattern that produced the fixture-titled commits. Both variants must
    be refused: the one where the chdir held (so the call is merely fragile) and the
    one where it did not hold (so the call is actively pointed at the real repo).
    Without the guard both variants execute git; with it, neither does.
    """

    def test_regression_issue_1638_chdir_then_unqualified_commit_is_refused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The chdir HELD, and the call is still refused -- fragility is the defect."""
        repo = tmp_path / "chdir_repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True, capture_output=True)
        monkeypatch.chdir(repo)

        # Exactly the original fixture shape: no cwd=, isolation via chdir alone.
        with pytest.raises(UnsafeGitInvocation):
            subprocess.run(["git", "add", "README.md"], check=True)
        with pytest.raises(UnsafeGitInvocation):
            subprocess.run(["git", "commit", "-m", "Initial commit"], check=True)

    def test_regression_issue_1638_chdir_not_held_targets_real_repo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The chdir did NOT hold: the interpreter sits in the real repo. Refused."""
        monkeypatch.chdir(REAL_REPO_ROOT)
        head_before = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REAL_REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        with pytest.raises(UnsafeGitInvocation):
            subprocess.run(["git", "commit", "-am", "would sweep the real tree"], check=True)

        head_after = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REAL_REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert head_before == head_after, "the real repository must not have moved"


class TestClassificationControls:
    """Positive and negative controls for ``assess_git_invocation`` itself."""

    def test_positive_control_known_bad_input_is_flagged(self) -> None:
        """An input known to be dangerous must produce a refusal reason."""
        reason = assess_git_invocation(["git", "commit", "-m", "x"], {})
        assert reason is not None and "commit" in reason

    def test_negative_control_known_good_input_is_cleared(self) -> None:
        """An input known to be safe must produce no refusal reason."""
        assert assess_git_invocation(["git", "status"], {}) is None

    def test_real_repo_root_points_at_this_checkout(self) -> None:
        """A misresolved root would make every 'inside real repo' check vacuous."""
        assert (REAL_REPO_ROOT / ".git").exists()
        assert (REAL_REPO_ROOT / "CLAUDE.md").exists()
        assert REAL_REPO_ROOT == Path(__file__).resolve().parents[2]


class TestPositionalTargetIsAnExplicitDirectory:
    """A positional target directory is as explicit as ``-C`` (2026-09-02).

    ``git init <dir>`` and ``git clone <repo> <dir>`` name their target as a
    POSITIONAL operand, not via ``-C``/``--git-dir``/``--work-tree``. The parser
    read only the flag forms, so ``git init --quiet /abs/tmp/repo`` -- a call that
    cannot resolve against the process CWD -- was refused.

    Measured cost of that false positive: ``tests/regression/
    test_protect_sensitive_regression.py`` passes 76/76 on its own and produced
    **64 failures** whenever it ran after ``tests/integration/``, because this
    tier's guard fixture is ``scope="session"`` and stays installed for every
    later directory. That single false positive was ~6% of the whole suite's
    failure count, and it was indistinguishable from 64 real defects.

    The refusals below are the point: the fix routes the positional target
    through the SAME checks as ``-C``, so nothing the guard existed to catch has
    become permitted.
    """

    # --- the fix: CWD-independent calls are permitted -----------------------

    def test_git_init_with_absolute_positional_target_is_permitted(self) -> None:
        """``git init /abs/path`` initialises that path from any CWD."""
        assert assess_git_invocation(["git", "init", "--quiet", "/tmp/gsg_repo"], {}) is None

    def test_git_clone_with_absolute_destination_is_permitted(self) -> None:
        """``git clone <repo> /abs/dest`` writes to dest from any CWD."""
        reason = assess_git_invocation(
            ["git", "clone", "https://example.com/r.git", "/tmp/gsg_clone"], {}
        )
        assert reason is None

    def test_the_real_call_site_that_regressed_is_permitted(self) -> None:
        """The exact argv from ``test_protect_sensitive_regression._init_repo``."""
        argv = ["git", "init", "--quiet", "/tmp/pytest-of-x/test_x0/repo"]
        assert assess_git_invocation(argv, {}) is None

    # --- controls: the hazard is still refused ------------------------------

    def test_control_absolute_positional_inside_real_repo_is_still_refused(self) -> None:
        """The #1638 hazard itself. An absolute path is not automatically safe."""
        reason = assess_git_invocation(["git", "init", str(REAL_REPO_ROOT)], {})
        assert reason is not None

    def test_control_relative_positional_target_is_still_refused(self) -> None:
        """``git init subdir`` remains chdir-dependent, so it stays refused."""
        reason = assess_git_invocation(["git", "init", "--quiet", "subdir"], {})
        assert reason is not None

    def test_control_git_init_naming_no_directory_is_still_refused(self) -> None:
        """No operand means the CWD is the target -- the original hazard."""
        assert assess_git_invocation(["git", "init", "--quiet"], {}) is not None

    def test_control_git_clone_without_destination_is_still_refused(self) -> None:
        """One operand is the source; the destination is CWD-derived."""
        reason = assess_git_invocation(["git", "clone", "https://example.com/r.git"], {})
        assert reason is not None

    # --- control of a DIFFERENT shape than the bug --------------------------

    def test_control_subcommand_with_no_positional_target_is_unaffected(self) -> None:
        """``git commit`` takes no target dir; its operands must not be read as one.

        Different shape from the bug on purpose: a fix that treated ANY absolute
        operand as a directory would wrongly clear this, since ``-m`` messages and
        pathspecs are operands too.
        """
        reason = assess_git_invocation(["git", "commit", "-m", "/tmp/looks_like_a_path"], {})
        assert reason is not None

    def test_control_the_table_is_the_only_source_of_truth(self) -> None:
        """A tenth subcommand cannot hide in an ``if``; it must be in the table."""
        from tests.helpers.git_safety_guard import _POSITIONAL_TARGET_SUBCOMMANDS

        assert set(_POSITIONAL_TARGET_SUBCOMMANDS) == {"init", "clone"}
