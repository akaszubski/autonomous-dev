#!/usr/bin/env python3
"""Unit tests for ``scripts/uninstall_unregister_plugin.py`` — Issue #951.

Covers:
    - Strip autonomous-dev entry from installed_plugins.json (dict shape)
    - Strip autonomous-dev entry from marketplaces.json (list shape)
    - Both files missing -> stripped=False, success=True (no-op)
    - Dry-run mode makes no writes
    - Backup is created under the requested backup_root before mutation
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


# Make the script importable as a module.
_SCRIPTS_DIR = (
    Path(__file__).resolve().parents[3]
    / "plugins"
    / "autonomous-dev"
    / "scripts"
)
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import uninstall_unregister_plugin as uup  # type: ignore  # noqa: E402


# ---------------------------------------------------------------------------
# Tests (5 required)
# ---------------------------------------------------------------------------


def test_strip_plugin_from_dict_shape(tmp_path: Path) -> None:
    """installed_plugins.json keyed by plugin id -> autonomous-dev removed."""
    plugins_file = tmp_path / "installed_plugins.json"
    marketplaces_file = tmp_path / "marketplaces.json"
    backup_root = tmp_path / "backup"

    plugins_data = {
        "autonomous-dev": {"version": "1.0.0", "source": "github"},
        "other-plugin": {"version": "2.0.0", "source": "local"},
    }
    plugins_file.write_text(json.dumps(plugins_data, indent=2))

    result = uup.unregister_plugin(
        plugins_file, marketplaces_file, backup_root, dry_run=False
    )

    assert result["success"] is True
    assert result["stripped"] is True
    assert result["plugins_changed"] is True
    assert result["marketplaces_changed"] is False

    post = json.loads(plugins_file.read_text())
    assert "autonomous-dev" not in post
    assert post["other-plugin"]["version"] == "2.0.0"


def test_strip_marketplace_from_list_shape(tmp_path: Path) -> None:
    """marketplaces.json as list of dicts -> matching entry removed."""
    plugins_file = tmp_path / "installed_plugins.json"
    marketplaces_file = tmp_path / "marketplaces.json"
    backup_root = tmp_path / "backup"

    marketplaces_data = [
        {"name": "autonomous-dev", "url": "https://example.com/x"},
        {"name": "other-marketplace", "url": "https://example.com/y"},
    ]
    marketplaces_file.write_text(json.dumps(marketplaces_data, indent=2))

    result = uup.unregister_plugin(
        plugins_file, marketplaces_file, backup_root, dry_run=False
    )

    assert result["success"] is True
    assert result["stripped"] is True
    assert result["plugins_changed"] is False
    assert result["marketplaces_changed"] is True

    post = json.loads(marketplaces_file.read_text())
    assert isinstance(post, list)
    names = [entry.get("name") for entry in post if isinstance(entry, dict)]
    assert "autonomous-dev" not in names
    assert "other-marketplace" in names


def test_both_files_missing_is_noop(tmp_path: Path) -> None:
    """Both files absent -> success=True, stripped=False, no error."""
    plugins_file = tmp_path / "installed_plugins.json"
    marketplaces_file = tmp_path / "marketplaces.json"
    backup_root = tmp_path / "backup"
    assert not plugins_file.exists()
    assert not marketplaces_file.exists()

    result = uup.unregister_plugin(
        plugins_file, marketplaces_file, backup_root, dry_run=False
    )

    assert result["success"] is True
    assert result["stripped"] is False
    assert result["plugins_changed"] is False
    assert result["marketplaces_changed"] is False
    assert result["error"] is None
    # No backup dir created.
    assert not backup_root.exists() or not any(backup_root.iterdir())


def test_dry_run_makes_no_writes(tmp_path: Path) -> None:
    """Dry-run identifies entries to strip but writes nothing."""
    plugins_file = tmp_path / "installed_plugins.json"
    marketplaces_file = tmp_path / "marketplaces.json"
    backup_root = tmp_path / "backup"

    plugins_data = {"autonomous-dev": {"version": "1.0.0"}}
    pre_text = json.dumps(plugins_data, indent=2)
    plugins_file.write_text(pre_text)

    result = uup.unregister_plugin(
        plugins_file, marketplaces_file, backup_root, dry_run=True
    )

    assert result["success"] is True
    # In dry-run, stripped is False but would_strip is True.
    assert result["stripped"] is False
    assert result["would_strip"] is True
    assert result["plugins_changed"] is True
    # File unchanged.
    assert plugins_file.read_text() == pre_text
    # No backup created.
    assert not backup_root.exists() or not any(backup_root.iterdir())


def test_backup_created_before_mutate(tmp_path: Path) -> None:
    """A backup of plugins_file is created in backup_root before write."""
    plugins_file = tmp_path / "installed_plugins.json"
    marketplaces_file = tmp_path / "marketplaces.json"
    backup_root = tmp_path / "uninstall-20260101-000000"

    plugins_data = {
        "autonomous-dev": {"version": "1.0.0"},
        "kept-plugin": {"version": "9.9.9"},
    }
    pre_text = json.dumps(plugins_data, indent=2)
    plugins_file.write_text(pre_text)

    result = uup.unregister_plugin(
        plugins_file, marketplaces_file, backup_root, dry_run=False
    )

    assert result["success"] is True
    assert result["stripped"] is True
    assert result["plugins_backup"] is not None
    backup_path = Path(result["plugins_backup"])
    assert backup_path.exists()
    # Backup contains the pre-call bytes.
    assert backup_path.read_text() == pre_text
    # Backup is inside backup_root.
    assert backup_root in backup_path.parents or backup_path.parent == backup_root
