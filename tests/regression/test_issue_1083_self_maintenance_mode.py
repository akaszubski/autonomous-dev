"""Regression tests for Issue #1083: Self-maintenance mode.

When operating inside the canonical autonomous-dev source tree (detected by
the presence of ``plugins/autonomous-dev/.claude-plugin/marketplace.json`` in
cwd or any ancestor), the state-deletion guard (#803) relaxes so maintainers
can clean up stuck pipeline state without env-var bypasses (which don't
propagate mid-session per Issue #779).

These tests exercise the detector and the relaxation. The full hook block
behavior is covered by the subprocess-level tests in
``test_universal_hook_bypass.py``; here we test the unit-level function and
the cwd walk semantics.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
if str(HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(HOOK_DIR))


@pytest.fixture(autouse=True)
def _clear_self_maint_cache():
    """Reset the per-cwd cache between tests so each test starts fresh."""
    import unified_pre_tool as upt
    upt._SELF_MAINT_CACHE.clear()
    yield
    upt._SELF_MAINT_CACHE.clear()


def _make_canonical_source_tree(root: Path) -> None:
    """Create the canonical-source marker so a cwd looks like autonomous-dev."""
    marker_dir = root / "plugins" / "autonomous-dev" / ".claude-plugin"
    marker_dir.mkdir(parents=True, exist_ok=True)
    (marker_dir / "marketplace.json").write_text('{"name": "autonomous-dev"}')


class TestIsSelfMaintenanceMode:
    """AC: detector identifies autonomous-dev source repo vs consumer repo."""

    def test_returns_true_at_repo_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """cwd == autonomous-dev source root -> True."""
        _make_canonical_source_tree(tmp_path)
        monkeypatch.chdir(tmp_path)
        from unified_pre_tool import _is_self_maintenance_mode
        assert _is_self_maintenance_mode() is True

    def test_returns_true_from_subdir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """cwd inside an autonomous-dev subdirectory -> True (walks up)."""
        _make_canonical_source_tree(tmp_path)
        sub = tmp_path / "plugins" / "autonomous-dev" / "lib"
        sub.mkdir(parents=True, exist_ok=True)
        monkeypatch.chdir(sub)
        from unified_pre_tool import _is_self_maintenance_mode
        assert _is_self_maintenance_mode() is True

    def test_returns_false_in_consumer_repo(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """cwd in a repo WITHOUT the canonical marker -> False."""
        # Simulate a consumer repo: has .claude/ from installed plugin but no
        # plugins/autonomous-dev/.claude-plugin/marketplace.json source marker.
        (tmp_path / ".claude" / "hooks").mkdir(parents=True, exist_ok=True)
        monkeypatch.chdir(tmp_path)
        from unified_pre_tool import _is_self_maintenance_mode
        assert _is_self_maintenance_mode() is False

    def test_returns_false_at_filesystem_root_without_marker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty directory tree with no marker anywhere -> False (no infinite loop)."""
        monkeypatch.chdir(tmp_path)
        from unified_pre_tool import _is_self_maintenance_mode
        assert _is_self_maintenance_mode() is False

    def test_result_cached_per_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Second call from the same cwd hits the cache (no re-walk)."""
        _make_canonical_source_tree(tmp_path)
        monkeypatch.chdir(tmp_path)
        from unified_pre_tool import _is_self_maintenance_mode, _SELF_MAINT_CACHE
        assert _is_self_maintenance_mode() is True
        # Cache populated for this cwd.
        assert str(tmp_path.resolve()) in _SELF_MAINT_CACHE
        # Remove the marker file — cache should still report True.
        (tmp_path / "plugins" / "autonomous-dev" / ".claude-plugin" / "marketplace.json").unlink()
        assert _is_self_maintenance_mode() is True  # cached result

    def test_canonical_repo_returns_true_for_actual_cwd(self) -> None:
        """Sanity check against the real repo: pytest runs from autonomous-dev itself."""
        from unified_pre_tool import _is_self_maintenance_mode
        # When tests run from the autonomous-dev repo, the detector must fire.
        assert _is_self_maintenance_mode() is True


class TestStateDeletionRelaxation:
    """AC: state-deletion guard relaxes in self-maintenance mode."""

    def test_check_bash_state_deletion_still_detects_rm(self) -> None:
        """Sanity: the underlying detector still catches rm of state files."""
        from unified_pre_tool import _check_bash_state_deletion
        result = _check_bash_state_deletion("rm /tmp/implement_pipeline_state.json")
        assert result is not None
        target, reason = result
        assert "/tmp/implement_pipeline_state.json" in target

    def test_deny_reason_mentions_bypass_file_first(self) -> None:
        """The updated deny message advertises `.claude/.bypass` as the
        primary bypass route, ahead of env-var bypasses that don't propagate
        mid-session per Issue #779.
        """
        import unified_pre_tool as upt
        source = Path(upt.__file__).read_text()
        # The exact deny-message phrasing must mention .claude/.bypass before
        # PIPELINE_CLEANUP_PHASE so future maintainers see the working path.
        idx_bypass = source.find("touch .claude/.bypass")
        idx_envvar = source.find("export PIPELINE_CLEANUP_PHASE=1")
        assert idx_bypass != -1, "deny message must reference .claude/.bypass"
        assert idx_envvar != -1, "deny message must reference PIPELINE_CLEANUP_PHASE (kept for documentation)"
        assert idx_bypass < idx_envvar, (
            "`.claude/.bypass` MUST appear before `PIPELINE_CLEANUP_PHASE` "
            "in the deny message — file-based bypass works mid-session, env "
            "vars do not (Issue #779)."
        )
