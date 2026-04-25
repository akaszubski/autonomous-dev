#!/usr/bin/env python3
"""Unit tests for ``scripts/migrate_mcp_to_repo.py`` — Issue #948.

Covers:
    - Migration of a named server from global to per-repo .mcp.json
    - Preservation of existing repo .mcp.json server entries
    - Server-name collision handling (overwrite)
    - Error JSON for missing server / missing global / missing repo
    - Secret detection (parametrized) — Anthropic / GitHub PAT / AWS keys
    - Secret detection inside nested env dict
    - No false-positives on ${VAR} env-var indirection
    - .gitignore append / create / no-duplicate behaviour
    - --dry-run produces no writes
    - File mode 0o600 when secrets present
    - --check-only mode reports secret status without migration
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Any, Dict

import pytest


# Make the script importable as a module — match other tests in this dir.
_SCRIPTS_DIR = (
    Path(__file__).resolve().parents[3]
    / "plugins"
    / "autonomous-dev"
    / "scripts"
)
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import migrate_mcp_to_repo as mig  # type: ignore  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _write_global_settings(
    global_path: Path,
    servers: Dict[str, Any],
    *,
    extra: Dict[str, Any] | None = None,
) -> None:
    """Write a global settings.json with the given mcpServers block."""
    content: Dict[str, Any] = {"mcpServers": servers}
    if extra:
        content.update(extra)
    global_path.parent.mkdir(parents=True, exist_ok=True)
    global_path.write_text(json.dumps(content, indent=2), encoding="utf-8")


def _make_layout(tmp_path: Path) -> tuple[Path, Path]:
    """Build (repo_dir, global_settings_path) under tmp_path."""
    repo = tmp_path / "repo"
    repo.mkdir()
    global_path = tmp_path / "home" / ".claude" / "settings.json"
    return repo, global_path


# ---------------------------------------------------------------------------
# Migration: success paths
# ---------------------------------------------------------------------------


def test_migrates_named_server_to_empty_repo_mcp(tmp_path: Path) -> None:
    repo, gp = _make_layout(tmp_path)
    _write_global_settings(
        gp,
        {
            "github": {"command": "docker", "args": ["run", "ghcr.io/github/mcp"]},
            "filesystem": {"command": "npx", "args": ["-y", "fs"]},
        },
    )

    result = mig.migrate(
        server_name="github", repo_path=repo, global_path=gp
    )

    assert result["success"] is True, result
    target = repo / ".mcp.json"
    assert target.exists()
    data = json.loads(target.read_text())
    assert set(data["mcpServers"].keys()) == {"github"}
    assert data["mcpServers"]["github"]["command"] == "docker"
    # Source mcpServers MUST NOT be modified (non-destructive).
    assert "github" in mig.load_global_mcp_servers(gp)
    assert "filesystem" in mig.load_global_mcp_servers(gp)


def test_preserves_existing_repo_mcp_servers(tmp_path: Path) -> None:
    repo, gp = _make_layout(tmp_path)
    # Pre-existing repo .mcp.json with a server already.
    existing = {"mcpServers": {"local-tool": {"command": "echo", "args": []}}}
    (repo / ".mcp.json").write_text(json.dumps(existing), encoding="utf-8")
    _write_global_settings(
        gp, {"github": {"command": "docker", "args": []}}
    )

    result = mig.migrate(
        server_name="github", repo_path=repo, global_path=gp
    )
    assert result["success"] is True

    data = json.loads((repo / ".mcp.json").read_text())
    assert set(data["mcpServers"].keys()) == {"local-tool", "github"}


def test_overwrites_same_named_server_in_repo(tmp_path: Path) -> None:
    repo, gp = _make_layout(tmp_path)
    existing = {
        "mcpServers": {
            "github": {"command": "OLD", "args": ["old"]},
        }
    }
    (repo / ".mcp.json").write_text(json.dumps(existing), encoding="utf-8")
    _write_global_settings(
        gp, {"github": {"command": "NEW", "args": ["new"]}}
    )

    result = mig.migrate(
        server_name="github", repo_path=repo, global_path=gp
    )
    assert result["success"] is True

    data = json.loads((repo / ".mcp.json").read_text())
    assert data["mcpServers"]["github"]["command"] == "NEW"
    assert data["mcpServers"]["github"]["args"] == ["new"]


# ---------------------------------------------------------------------------
# Migration: error paths
# ---------------------------------------------------------------------------


def test_server_not_found_returns_error_json(tmp_path: Path) -> None:
    repo, gp = _make_layout(tmp_path)
    _write_global_settings(
        gp, {"foo": {"command": "echo", "args": []}}
    )
    result = mig.migrate(
        server_name="bar", repo_path=repo, global_path=gp
    )
    assert result["success"] is False
    assert result["error"] == "server_not_found"
    assert "bar" in result["message"]


def test_global_settings_missing_returns_error_json(tmp_path: Path) -> None:
    repo, gp = _make_layout(tmp_path)
    # Don't create gp file.
    result = mig.migrate(
        server_name="github", repo_path=repo, global_path=gp
    )
    assert result["success"] is False
    assert result["error"] == "global_not_found"


def test_invalid_global_json_returns_error(tmp_path: Path) -> None:
    repo, gp = _make_layout(tmp_path)
    gp.parent.mkdir(parents=True, exist_ok=True)
    gp.write_text("{not valid json", encoding="utf-8")
    result = mig.migrate(
        server_name="github", repo_path=repo, global_path=gp
    )
    assert result["success"] is False
    assert result["error"] == "invalid_global_json"


def test_repo_path_missing_returns_error(tmp_path: Path) -> None:
    _, gp = _make_layout(tmp_path)
    _write_global_settings(gp, {"github": {"command": "x"}})
    fake_repo = tmp_path / "does_not_exist"
    result = mig.migrate(
        server_name="github", repo_path=fake_repo, global_path=gp
    )
    assert result["success"] is False
    assert result["error"] == "repo_not_found"


# ---------------------------------------------------------------------------
# Secret detection — parametrized over real-shape secrets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "server_cfg,expected_match_substring",
    [
        # Anthropic API key shape (sk- prefix)
        (
            {
                "command": "x",
                "args": ["--key", "sk-abcdef0123456789ABCDEFXYZ123"],
            },
            "Anthropic",
        ),
        # GitHub personal access token (ghp_ prefix, 36+ chars)
        (
            {
                "command": "x",
                "env": {"GITHUB_TOKEN": "ghp_" + "A" * 40},
            },
            "GitHub",
        ),
        # AWS access key ID (AKIA + 16 alphanum)
        (
            {
                "command": "x",
                "args": ["AKIAIOSFODNN7EXAMPLE"],
            },
            "AWS",
        ),
    ],
)
def test_secret_detection(
    server_cfg: Dict[str, Any], expected_match_substring: str
) -> None:
    detected, pattern = mig.contains_secret(server_cfg)
    assert detected is True
    assert expected_match_substring.lower() in pattern.lower()


def test_secret_detection_in_env_dict() -> None:
    cfg = {
        "command": "docker",
        "env": {
            "OUTER": {"NESTED": "ghp_" + "B" * 40},
        },
    }
    detected, pattern = mig.contains_secret(cfg)
    assert detected is True
    assert "github" in pattern.lower()


def test_no_false_positive_on_env_var_indirection() -> None:
    # ${GITHUB_TOKEN} is a placeholder, NOT a literal secret.
    cfg = {
        "command": "docker",
        "args": ["run", "-e", "GITHUB_TOKEN"],
        "env": {
            "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}",
            "BRAVE_API_KEY": "${BRAVE_API_KEY:-default}",
        },
    }
    detected, pattern = mig.contains_secret(cfg)
    assert detected is False, (
        f"False-positive on env placeholder. pattern={pattern!r}, cfg={cfg}"
    )


def test_no_false_positive_on_clean_config() -> None:
    cfg = {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"],
    }
    detected, _ = mig.contains_secret(cfg)
    assert detected is False


# ---------------------------------------------------------------------------
# Gitignore behaviour
# ---------------------------------------------------------------------------


def test_gitignore_appended_when_secrets_detected(tmp_path: Path) -> None:
    repo, gp = _make_layout(tmp_path)
    (repo / ".gitignore").write_text(".env\n", encoding="utf-8")
    _write_global_settings(
        gp,
        {
            "github": {
                "command": "docker",
                "env": {"GITHUB_TOKEN": "ghp_" + "X" * 40},
            }
        },
    )
    result = mig.migrate(
        server_name="github", repo_path=repo, global_path=gp
    )
    assert result["success"] is True
    assert result["secrets_detected"] is True
    assert result["gitignored"] is True
    body = (repo / ".gitignore").read_text()
    assert ".env" in body
    assert ".mcp.json" in body


def test_gitignore_creates_file_if_absent(tmp_path: Path) -> None:
    repo, gp = _make_layout(tmp_path)
    assert not (repo / ".gitignore").exists()
    _write_global_settings(
        gp,
        {
            "github": {
                "command": "docker",
                "env": {"TOKEN": "ghp_" + "Y" * 40},
            }
        },
    )
    result = mig.migrate(
        server_name="github", repo_path=repo, global_path=gp
    )
    assert result["success"] is True
    assert result["secrets_detected"] is True
    assert (repo / ".gitignore").exists()
    assert ".mcp.json" in (repo / ".gitignore").read_text()


def test_gitignore_not_duplicated(tmp_path: Path) -> None:
    repo, gp = _make_layout(tmp_path)
    (repo / ".gitignore").write_text(".mcp.json\n.env\n", encoding="utf-8")
    _write_global_settings(
        gp,
        {
            "github": {
                "command": "docker",
                "env": {"TOKEN": "ghp_" + "Z" * 40},
            }
        },
    )
    result = mig.migrate(
        server_name="github", repo_path=repo, global_path=gp
    )
    assert result["success"] is True
    assert result["secrets_detected"] is True
    body = (repo / ".gitignore").read_text()
    assert body.count(".mcp.json") == 1


def test_gitignore_unchanged_when_no_secrets(tmp_path: Path) -> None:
    repo, gp = _make_layout(tmp_path)
    _write_global_settings(
        gp,
        {
            "filesystem": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem"],
            }
        },
    )
    result = mig.migrate(
        server_name="filesystem", repo_path=repo, global_path=gp
    )
    assert result["success"] is True
    assert result["secrets_detected"] is False
    assert result["gitignored"] is False
    # No .gitignore should be created when no secrets.
    assert not (repo / ".gitignore").exists()


# ---------------------------------------------------------------------------
# Dry-run / file-mode / check-only
# ---------------------------------------------------------------------------


def test_dry_run_no_writes(tmp_path: Path) -> None:
    repo, gp = _make_layout(tmp_path)
    _write_global_settings(
        gp, {"github": {"command": "docker", "args": []}}
    )
    result = mig.migrate(
        server_name="github",
        repo_path=repo,
        global_path=gp,
        dry_run=True,
    )
    assert result["success"] is True
    assert result["dry_run"] is True
    assert not (repo / ".mcp.json").exists()
    assert not (repo / ".gitignore").exists()


def test_atomic_write_uses_secure_perms_when_secrets_present(
    tmp_path: Path,
) -> None:
    repo, gp = _make_layout(tmp_path)
    _write_global_settings(
        gp,
        {
            "github": {
                "command": "docker",
                "env": {"GITHUB_TOKEN": "ghp_" + "P" * 40},
            }
        },
    )
    result = mig.migrate(
        server_name="github", repo_path=repo, global_path=gp
    )
    assert result["success"] is True
    assert result["secrets_detected"] is True

    target = repo / ".mcp.json"
    file_mode = stat.S_IMODE(os.stat(target).st_mode)
    assert file_mode == 0o600, f"Expected 0o600 with secrets, got {oct(file_mode)}"


def test_atomic_write_uses_default_perms_without_secrets(
    tmp_path: Path,
) -> None:
    repo, gp = _make_layout(tmp_path)
    _write_global_settings(
        gp,
        {
            "filesystem": {
                "command": "npx",
                "args": ["-y", "fs"],
            }
        },
    )
    result = mig.migrate(
        server_name="filesystem", repo_path=repo, global_path=gp
    )
    assert result["success"] is True
    assert result["secrets_detected"] is False

    target = repo / ".mcp.json"
    file_mode = stat.S_IMODE(os.stat(target).st_mode)
    assert file_mode == 0o644, f"Expected 0o644 without secrets, got {oct(file_mode)}"


def test_check_only_mode_returns_secret_status_without_migration(
    tmp_path: Path,
) -> None:
    repo, _ = _make_layout(tmp_path)
    # Pre-populate .mcp.json with a literal secret.
    cfg = {
        "mcpServers": {
            "github": {
                "command": "docker",
                "env": {"TOKEN": "ghp_" + "Q" * 40},
            }
        }
    }
    (repo / ".mcp.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = mig.check_only(repo)
    assert result["success"] is True
    assert result["secrets_detected"] is True
    # No migration occurred — file content unchanged.
    assert json.loads((repo / ".mcp.json").read_text()) == cfg


def test_check_only_mode_no_mcp_json(tmp_path: Path) -> None:
    repo, _ = _make_layout(tmp_path)
    result = mig.check_only(repo)
    assert result["success"] is True
    assert result["secrets_detected"] is False


# ---------------------------------------------------------------------------
# CLI smoke tests via main()
# ---------------------------------------------------------------------------


def test_main_returns_zero_and_emits_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, gp = _make_layout(tmp_path)
    _write_global_settings(
        gp, {"github": {"command": "docker", "args": []}}
    )
    rc = mig.main(
        [
            "--server",
            "github",
            "--repo",
            str(repo),
            "--global",
            str(gp),
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["success"] is True
    assert parsed["server"] == "github"


def test_main_check_only(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, _ = _make_layout(tmp_path)
    rc = mig.main(["--check-only", "--repo", str(repo)])
    assert rc == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["success"] is True
    assert parsed["secrets_detected"] is False


def test_main_missing_server_arg_without_check_only(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, _ = _make_layout(tmp_path)
    rc = mig.main(["--repo", str(repo)])
    assert rc == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["success"] is False
    assert parsed["error"] == "missing_args"
