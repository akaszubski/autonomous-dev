"""Self-heal propagation test for Issue #1409 via the existing sync path.

``sync_settings_hooks._replace_hooks`` already performs a *wholesale replace* of
``permissions.deny`` from the canonical ``DEFAULT_DENY_LIST``. Because Issue #1409
corrects that canonical list (``Write(/etc/**)`` -> ``Edit(//etc/**)``), a repo
whose settings still carry the legacy ``Write(/etc/**)`` rule is self-healed the
next time ``sync_repo`` runs — no new migration code required.

This test proves that propagation end-to-end against real tmp files (nothing in
the sync path is mocked), and proves the sync is idempotent (a second run is a
byte-stable no-op with ``deny_synced == False``).

Fixes #1409.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYNC_SCRIPT = (
    PROJECT_ROOT / "plugins/autonomous-dev/scripts/sync_settings_hooks.py"
)


def _load_sync_module():
    """Import sync_settings_hooks from its script path.

    Returns:
        The imported module exposing ``sync_repo`` and ``_get_canonical_deny_list``.
    """
    spec = importlib.util.spec_from_file_location(
        "sync_settings_hooks_1409", SYNC_SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def sync_mod():
    """Fresh import of the sync module for each test."""
    return _load_sync_module()


def _write_repo_settings(repo: Path, deny: list) -> Path:
    """Create <repo>/.claude/settings.json with a valid hooks + deny section.

    Args:
        repo: Repository root tmp dir.
        deny: Initial permissions.deny list to plant.

    Returns:
        Path to the written settings.json.
    """
    settings_path = repo / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": "echo legacy"}],
                }
            ]
        },
        "permissions": {"allow": ["Edit", "Read"], "deny": deny},
    }
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return settings_path


class TestSyncSelfHealIssue1409:
    """sync_repo self-heals a planted legacy Write(/etc/**) deny rule."""

    def test_canonical_deny_list_has_migrated_rule(self, sync_mod):
        """Sanity: the canonical list the sync path pulls from is migrated."""
        canonical = sync_mod._get_canonical_deny_list()
        assert "Edit(//etc/**)" in canonical
        assert "Write(/etc/**)" not in canonical

    def test_sync_repo_migrates_legacy_write_rule(self, sync_mod, tmp_path):
        """A planted Write(/etc/**) is replaced with Edit(//etc/**) on sync."""
        settings_path = _write_repo_settings(
            tmp_path, deny=["Write(/etc/**)", "Bash(rm -rf /)"]
        )

        result = sync_mod.sync_repo(str(tmp_path), dry_run=False)

        assert result["success"] is True
        assert result["deny_synced"] is True

        deny = json.loads(settings_path.read_text(encoding="utf-8"))[
            "permissions"
        ]["deny"]
        assert "Edit(//etc/**)" in deny, "Migrated rule not propagated"
        assert "Write(/etc/**)" not in deny, "Legacy ignored rule still present"

    def test_sync_repo_is_idempotent(self, sync_mod, tmp_path):
        """A second sync is a byte-stable no-op (deny_synced False)."""
        settings_path = _write_repo_settings(tmp_path, deny=["Write(/etc/**)"])

        first = sync_mod.sync_repo(str(tmp_path), dry_run=False)
        assert first["deny_synced"] is True
        after_first = settings_path.read_bytes()

        second = sync_mod.sync_repo(str(tmp_path), dry_run=False)
        assert second["deny_synced"] is False, "Second run should be a no-op"
        after_second = settings_path.read_bytes()

        assert after_first == after_second, "Second sync must be byte-stable"
