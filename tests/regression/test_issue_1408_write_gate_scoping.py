"""Regression tests for Issue #1408 — write-pipeline gate scoping + Hybrid bash surface.

Covers the corrected (plan-critic reviewed) design:

A. Scratchpad root-cause fix — ``edit_tier_classifier._is_temp_path`` now
   recognises ``/private/tmp/``, ``/var/folders/`` and ``$SCRATCHPAD``.
B. Git-worktree-aware scoping — ``_is_gated_repo_source`` gates only
   in-worktree, non-ignored source; fails open on git errors, never raises.
C. Pure helpers — ``_is_scratch_path`` and ``_extract_git_checkout_targets``.
D. Hybrid bash surface — protected-infra bash (incl. ``git checkout`` /
   ``git apply``) stays HARD; general bash-code writes are now advisory.
E. Scoped escape — bypass sentinel reason is logged.

Issue: #1408
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(HOOK_DIR))
sys.path.insert(0, str(LIB_DIR))

import edit_tier_classifier as etc  # noqa: E402
import unified_pre_tool as upt  # noqa: E402


# ---------------------------------------------------------------------------
# A. _is_scratch_path
# ---------------------------------------------------------------------------


class TestIsScratchPath:
    """The pure scratch-path classifier (Issue #1408)."""

    @pytest.mark.parametrize(
        "path",
        [
            "/tmp/foo.py",
            "/private/tmp/foo.py",
            "/private/tmp/claude-501/sess/scratchpad/note.py",
            "/tmp/claude-abc/helper.sh",
            "/var/folders/zz/abc/T/x.py",
        ],
    )
    def test_absolute_scratch_paths(self, path: str) -> None:
        assert upt._is_scratch_path(path) is True

    def test_dot_claude_tmp_substring(self) -> None:
        assert upt._is_scratch_path("/Users/x/repo/.claude/tmp/scratch.py") is True

    def test_scratchpad_env_subtree(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SCRATCHPAD", "/private/tmp/claude-501/sess/scratchpad")
        assert (
            upt._is_scratch_path("/private/tmp/claude-501/sess/scratchpad/x.py") is True
        )

    def test_real_source_is_not_scratch(self) -> None:
        assert (
            upt._is_scratch_path(str(LIB_DIR / "tool_intent.py")) is False
        )

    def test_unset_scratchpad_no_crash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SCRATCHPAD", raising=False)
        # Must not raise and must classify a normal source path as non-scratch.
        assert upt._is_scratch_path(str(LIB_DIR / "tool_intent.py")) is False

    def test_empty_path_no_crash(self) -> None:
        assert upt._is_scratch_path("") is False


# ---------------------------------------------------------------------------
# A. edit_tier_classifier._is_temp_path (the scratchpad-FIRING root cause)
# ---------------------------------------------------------------------------


class TestEditTierClassifierTempPath:
    """_is_temp_path must now recognise the macOS/scratchpad temp roots (#1408)."""

    @pytest.mark.parametrize(
        "path",
        [
            "/tmp/foo.py",              # pre-existing
            "/private/tmp/foo.py",      # macOS canonical (NEW #1408)
            "/var/folders/zz/abc/T/x.py",  # macOS mkdtemp (NEW #1408)
        ],
    )
    def test_temp_paths_true(self, path: str) -> None:
        assert etc._is_temp_path(path) is True

    def test_scratchpad_env_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SCRATCHPAD", "/private/tmp/claude-501/scratchpad")
        assert etc._is_temp_path("/private/tmp/claude-501/scratchpad/x.py") is True

    def test_repo_source_false(self) -> None:
        assert etc._is_temp_path(str(LIB_DIR / "tool_intent.py")) is False

    def test_empty_no_crash(self) -> None:
        assert etc._is_temp_path("") is False


# ---------------------------------------------------------------------------
# C. _extract_git_checkout_targets
# ---------------------------------------------------------------------------


class TestExtractGitCheckoutTargets:
    """Pure parser for git checkout/restore working-tree overwrites (#1408)."""

    def test_checkout_double_dash_single(self) -> None:
        assert upt._extract_git_checkout_targets("git checkout -- lib/x.py") == ["lib/x.py"]

    def test_checkout_ref_double_dash_multi(self) -> None:
        assert upt._extract_git_checkout_targets("git checkout main -- a b") == ["a", "b"]

    def test_restore_matched(self) -> None:
        assert "x" in upt._extract_git_checkout_targets("git restore x")

    def test_non_checkout_empty(self) -> None:
        assert upt._extract_git_checkout_targets("git status") == []
        assert upt._extract_git_checkout_targets("ls -la") == []

    def test_empty_command_no_crash(self) -> None:
        assert upt._extract_git_checkout_targets("") == []


# ---------------------------------------------------------------------------
# B. _is_gated_repo_source — functional with a real tmp git repo
# ---------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=str(cwd), check=True,
        capture_output=True, text=True,
    )


@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    """A real git worktree with one tracked file and a .gitignore."""
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@t.t")
    _git(tmp_path, "config", "user.name", "t")
    src = tmp_path / "src"
    src.mkdir()
    tracked = src / "tracked.py"
    tracked.write_text("x = 1\n")
    (tmp_path / ".gitignore").write_text("ignored.py\nbuild/\n")
    _git(tmp_path, "add", "src/tracked.py", ".gitignore")
    _git(tmp_path, "commit", "-m", "init")
    return tmp_path


class TestIsGatedRepoSource:
    """Worktree-aware scoping (#1408)."""

    def test_in_worktree_tracked_is_gated(self, tmp_repo: Path) -> None:
        assert upt._is_gated_repo_source(str(tmp_repo / "src" / "tracked.py")) is True

    def test_new_untracked_non_ignored_stays_gated(self, tmp_repo: Path) -> None:
        new = tmp_repo / "src" / "new_feature.py"
        new.write_text("def f(): pass\n")
        assert upt._is_gated_repo_source(str(new)) is True

    def test_gitignored_not_gated(self, tmp_repo: Path) -> None:
        ignored = tmp_repo / "ignored.py"
        ignored.write_text("y = 2\n")
        assert upt._is_gated_repo_source(str(ignored)) is False

    def test_outside_worktree_not_gated(self, tmp_path: Path) -> None:
        # tmp_path here is a fresh (non-git) dir.
        stray = tmp_path / "stray.py"
        stray.write_text("z = 3\n")
        assert upt._is_gated_repo_source(str(stray)) is False

    def test_scratch_inside_repo_not_gated(self, tmp_repo: Path) -> None:
        scratch = tmp_repo / ".claude" / "tmp"
        scratch.mkdir(parents=True)
        f = scratch / "scratch.py"
        f.write_text("w = 4\n")
        assert upt._is_gated_repo_source(str(f)) is False

    def test_subprocess_raise_fails_open_no_raise(
        self, tmp_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(*_a, **_k):  # noqa: ANN002, ANN003
            raise OSError("git unavailable")

        monkeypatch.setattr(subprocess, "run", _boom)
        # Fails open to _is_autonomous_dev_repo — must NOT raise.
        result = upt._is_gated_repo_source(str(tmp_repo / "src" / "tracked.py"))
        assert result in (True, False)


# ---------------------------------------------------------------------------
# C/E. End-to-end: Write/Edit gate scoping
# ---------------------------------------------------------------------------


class TestWriteEditGateScoping:
    """_check_write_pipeline_required honours scratch + out-of-tree scoping."""

    def _big_new(self) -> str:
        return "\n".join(f"def f_{i}(): pass" for i in range(20))

    def test_scratch_path_allows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: False)
        block, tier, _ = upt._check_write_pipeline_required(
            "Write", "/private/tmp/claude-501/x.py", "", self._big_new()
        )
        assert block is False
        assert tier == "tier0_scratch_path"

    def test_out_of_tree_allows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: False)
        monkeypatch.setattr(upt, "_is_scratch_path", lambda _p: False)
        monkeypatch.setattr(upt, "_is_gated_repo_source", lambda _p: False)
        block, tier, _ = upt._check_write_pipeline_required(
            "Write", "/home/user/app/models.py", "", self._big_new()
        )
        assert block is False
        assert tier == "tier0_out_of_tree"

    def test_in_tree_source_still_blocks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: False)
        monkeypatch.setattr(upt, "_is_scratch_path", lambda _p: False)
        monkeypatch.setattr(upt, "_is_gated_repo_source", lambda _p: True)
        # Ensure no operator bypass sentinel interferes.
        sf = Path("/tmp/skip_write_pipeline_gate")
        if sf.exists():
            sf.unlink()
        block, tier, _ = upt._check_write_pipeline_required(
            "Write", "/home/user/app/models.py", "", self._big_new()
        )
        assert block is True
        assert tier in ("fix", "light", "full")


# ---------------------------------------------------------------------------
# D. Bash infra surface — protected-infra stays HARD (git checkout / apply)
# ---------------------------------------------------------------------------


class TestBashInfraSurfaceHard:
    """_check_bash_infra_writes blocks git checkout/apply to protected infra."""

    def test_git_checkout_to_protected_lib_blocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: False)
        monkeypatch.setattr(upt, "_is_protected_infrastructure", lambda _p: True)
        result = upt._check_bash_infra_writes(
            "git checkout -- plugins/autonomous-dev/lib/x.py"
        )
        assert result is not None
        assert "BLOCKED" in result[1]

    def test_git_apply_with_hooks_segment_blocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: False)
        result = upt._check_bash_infra_writes(
            "git apply < /tmp/patch.diff  # touches hooks/unified_pre_tool.py"
        )
        assert result is not None
        assert "BLOCKED" in result[1]

    def test_patch_with_lib_segment_blocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: False)
        result = upt._check_bash_infra_writes("patch lib/pipeline_state.py < p.diff")
        assert result is not None
        assert "BLOCKED" in result[1]

    def test_benign_git_checkout_branch_not_blocked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: False)
        # No protected segment present -> allow (None).
        result = upt._check_bash_infra_writes("git checkout main")
        assert result is None


# ---------------------------------------------------------------------------
# D. _check_bash_code_file_pipeline_required scoping
# ---------------------------------------------------------------------------


class TestBashCodeFileScoping:
    """The (now-advisory) bash-code gate must not fire on scratch/out-of-tree."""

    def test_scratch_target_not_flagged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(upt, "_is_pipeline_active", lambda: False)
        block, tier, _d, _t = upt._check_bash_code_file_pipeline_required(
            "cat > /private/tmp/claude-501/helper.py << 'EOF'\nx = 1\nEOF"
        )
        assert block is False
        assert tier in ("tier0_scratch_path", "no_code_target", "detector_unavailable")


# ---------------------------------------------------------------------------
# E. #803 cross-tool: denied Edit then git checkout same path still blocked
# ---------------------------------------------------------------------------


class TestCrossToolGitCheckout:
    """git checkout must be in the #803 write-target union (#1408)."""

    def test_git_checkout_target_in_union(self) -> None:
        # The extractor feeds the #803 union; a denied-Edit path that matches
        # a git-checkout target is what the wired check compares against.
        targets = upt._extract_git_checkout_targets(
            "git checkout -- plugins/autonomous-dev/lib/x.py"
        )
        assert "plugins/autonomous-dev/lib/x.py" in targets


# ---------------------------------------------------------------------------
# E. Scoped escape — bypass sentinel reason logged
# ---------------------------------------------------------------------------


class TestBypassReasonLogging:
    """_log_write_gate_bypass_consumed records the scoped-escape reason (#1408)."""

    def _read_last_entry(self, log_dir: Path) -> dict:
        import json
        from datetime import datetime

        log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        lines = [ln for ln in log_file.read_text().splitlines() if ln.strip()]
        return json.loads(lines[-1])

    def test_reason_from_sentinel_body(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))
        monkeypatch.delenv("WRITE_GATE_BYPASS_REASON", raising=False)
        skip = tmp_path / "skip_write_pipeline_gate"
        skip.write_text("hotfix #1408")
        upt._log_write_gate_bypass_consumed("/x/y.py", skip)
        entry = self._read_last_entry(tmp_path / ".claude" / "logs" / "activity")
        assert entry["reason"] == "hotfix #1408"

    def test_reason_unspecified_when_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))
        monkeypatch.delenv("WRITE_GATE_BYPASS_REASON", raising=False)
        skip = tmp_path / "skip_write_pipeline_gate"
        skip.write_text("")
        upt._log_write_gate_bypass_consumed("", skip)
        entry = self._read_last_entry(tmp_path / ".claude" / "logs" / "activity")
        assert entry["reason"] == "unspecified"

    def test_reason_from_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))
        monkeypatch.setenv("WRITE_GATE_BYPASS_REASON", "env-driven reason")
        skip = tmp_path / "skip_write_pipeline_gate"
        skip.write_text("")  # empty body -> falls through to env var
        upt._log_write_gate_bypass_consumed("", skip)
        entry = self._read_last_entry(tmp_path / ".claude" / "logs" / "activity")
        assert entry["reason"] == "env-driven reason"
