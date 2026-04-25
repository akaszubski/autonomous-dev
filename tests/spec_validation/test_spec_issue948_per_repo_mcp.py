"""Spec validation tests for Issue #948: Per-repo .mcp.json by default.

These tests validate observable behavior against the acceptance criteria from
GitHub issue #948 ONLY. They are written without reference to implementer
output, code diffs, reviewer feedback, or planner rationale.

Acceptance Criteria (verbatim):
    1. /setup writes per-repo .mcp.json by default.
    2. Docs explain the token-bleed cost of global MCP servers.
    3. Migration helper for users with existing global config:
       install.sh --migrate-mcp-to-repo <repo> lifts a server config from
       global to the named repo's .mcp.json.
    4. Each per-repo .mcp.json is gitignored when it contains inline secrets.

Additional behavioral guards (per spec-validator checklist):
    - ${VAR} placeholders MUST NOT trigger secret detection (false positive).
    - Migration is non-destructive: source global mcpServers entry stays.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

# Worktree root resolution: the test file lives in tests/spec_validation/;
# ascend two levels to reach the worktree root. Using __file__ keeps the test
# robust to pytest's CWD behaviour.
WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent

# Spec-relevant file paths (read-only — we never inspect implementation logic).
SETUP_MD = WORKTREE_ROOT / "plugins" / "autonomous-dev" / "commands" / "setup.md"
MCP_ARCH_DOC = WORKTREE_ROOT / "docs" / "MCP-ARCHITECTURE.md"
INSTALL_SH = WORKTREE_ROOT / "install.sh"
MIGRATE_HELPER = (
    WORKTREE_ROOT
    / "plugins"
    / "autonomous-dev"
    / "scripts"
    / "migrate_mcp_to_repo.py"
)


# ---------------------------------------------------------------------------
# AC1: /setup writes per-repo .mcp.json by default
# ---------------------------------------------------------------------------


class TestAC1SetupWritesPerRepoMcpJson:
    """AC1: /setup must produce a per-repo .mcp.json by default."""

    def test_spec_issue948_ac1_setup_md_has_step_initializing_mcp_json(self) -> None:
        """setup.md must contain a step that initializes a per-repo .mcp.json."""
        assert SETUP_MD.exists(), f"Missing: {SETUP_MD}"
        content = SETUP_MD.read_text(encoding="utf-8")
        # The step must mention .mcp.json AND describe creating it.
        assert ".mcp.json" in content, "setup.md does not reference .mcp.json"
        # It must describe writing/creating the file.
        creation_terms = ["Created .mcp.json", "Initialize per-repo", "Create .mcp.json"]
        assert any(term in content for term in creation_terms), (
            "setup.md must include a step that creates per-repo .mcp.json. "
            f"Looked for any of: {creation_terms}"
        )

    def test_spec_issue948_ac1_setup_md_uses_template_or_placeholder(self) -> None:
        """The /setup step must source from a template OR fall back to a placeholder."""
        content = SETUP_MD.read_text(encoding="utf-8")
        # Template fallback path
        has_template_fallback = bool(re.search(r"\.mcp/config\.template\.json", content))
        # Placeholder fallback (empty mcpServers object)
        has_placeholder = '{"mcpServers": {}}' in content or '"mcpServers"' in content
        assert has_template_fallback and has_placeholder, (
            "setup.md must reference both a template path "
            "(.mcp/config.template.json) and a placeholder fallback "
            f'(\'{{"mcpServers": {{}}}}\'). '
            f"template_fallback={has_template_fallback}, placeholder={has_placeholder}"
        )

    def test_spec_issue948_ac1_setup_md_preserves_existing_mcp_json(self) -> None:
        """The /setup step must be non-destructive — never overwrite existing .mcp.json."""
        content = SETUP_MD.read_text(encoding="utf-8")
        # Look for the conditional guard pattern.
        # Either an "if [ -f .mcp.json ]" check or a "Preserving" message.
        preserves = bool(
            re.search(r'if\s*\[\s*-f\s*"?\.mcp\.json"?\s*\]', content)
            or "Preserving existing .mcp.json" in content
        )
        assert preserves, (
            "setup.md must guard against overwriting an existing .mcp.json "
            "(via either an `if [ -f .mcp.json ]` check or a 'Preserving' message)."
        )


# ---------------------------------------------------------------------------
# AC2: Docs explain token-bleed cost of global MCP servers
# ---------------------------------------------------------------------------


class TestAC2DocsExplainTokenBleed:
    """AC2: Documentation must explain the token-bleed cost of global MCP servers."""

    def test_spec_issue948_ac2_mcp_architecture_has_per_repo_section(self) -> None:
        """docs/MCP-ARCHITECTURE.md must have a 'Per-repo vs Global' section."""
        assert MCP_ARCH_DOC.exists(), f"Missing: {MCP_ARCH_DOC}"
        content = MCP_ARCH_DOC.read_text(encoding="utf-8")
        # Must have a heading or section that compares per-repo vs global.
        per_repo_section = re.search(
            r"(?im)^#+\s*Per[- ]repo.*Global", content
        ) or re.search(r"(?im)^#+\s*Global.*Per[- ]repo", content)
        assert per_repo_section, (
            "docs/MCP-ARCHITECTURE.md must contain a heading comparing per-repo "
            "vs global MCP configuration."
        )

    def test_spec_issue948_ac2_docs_quote_concrete_token_costs(self) -> None:
        """The docs must include concrete token-cost numbers, per spec-validator note."""
        content = MCP_ARCH_DOC.read_text(encoding="utf-8")
        # Spec checklist: "concrete numbers like '500-2000 tokens per server'".
        # Be tolerant on the exact wording — accept any per-server range and
        # any aggregate. We require BOTH a per-server number and an aggregate.
        per_server = bool(re.search(r"500[\s-]*2000\s*tokens?", content, re.IGNORECASE))
        aggregate = bool(re.search(r"5[\s-]*10[Kk]\s*tokens?", content, re.IGNORECASE))
        assert per_server, (
            "docs must quote a concrete per-server token cost like "
            "'500-2000 tokens per server'."
        )
        assert aggregate, (
            "docs must quote a concrete aggregate token cost like "
            "'5-10K tokens per turn'."
        )

    def test_spec_issue948_ac2_docs_describe_token_bleed(self) -> None:
        """The docs must explicitly describe the cost as affecting every prompt/turn."""
        content = MCP_ARCH_DOC.read_text(encoding="utf-8").lower()
        # We expect language about every prompt / every project / regardless.
        signals = ["every prompt", "every turn", "every project", "regardless"]
        assert any(s in content for s in signals), (
            "docs must describe that the cost is paid even when the tools are "
            f"not used. Looked for any of: {signals}"
        )


# ---------------------------------------------------------------------------
# AC3: Migration helper for global → per-repo
# ---------------------------------------------------------------------------


class TestAC3MigrationHelper:
    """AC3: install.sh --migrate-mcp-to-repo <repo> --server <name> must work."""

    def test_spec_issue948_ac3_install_sh_accepts_migrate_flag(self) -> None:
        """install.sh --help must document --migrate-mcp-to-repo and --server."""
        assert INSTALL_SH.exists(), f"Missing: {INSTALL_SH}"
        result = subprocess.run(
            ["bash", str(INSTALL_SH), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"install.sh --help failed: {result.stderr}"
        out = result.stdout + result.stderr
        assert "--migrate-mcp-to-repo" in out, (
            "install.sh --help must document --migrate-mcp-to-repo flag."
        )
        assert "--server" in out, (
            "install.sh --help must document --server flag (paired with "
            "--migrate-mcp-to-repo)."
        )

    def test_spec_issue948_ac3_helper_script_exists_and_is_invocable(self) -> None:
        """The migration helper script must exist and accept --help."""
        assert MIGRATE_HELPER.exists(), f"Missing: {MIGRATE_HELPER}"
        result = subprocess.run(
            [sys.executable, str(MIGRATE_HELPER), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"migrate_mcp_to_repo.py --help failed: {result.stderr}"
        )

    def test_spec_issue948_ac3_helper_copies_server_from_global_to_repo(
        self, tmp_path: Path
    ) -> None:
        """End-to-end: helper migrates a named server into <repo>/.mcp.json."""
        # Construct a fake global settings.json
        global_settings = tmp_path / "global_settings.json"
        global_settings.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "demo": {
                            "command": "npx",
                            "args": ["-y", "@example/demo-server"],
                            "env": {"DEMO_VAR": "${DEMO_VAR}"},
                        },
                        "other": {"command": "echo", "args": ["other"]},
                    }
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        repo_path = tmp_path / "myrepo"
        repo_path.mkdir()

        result = subprocess.run(
            [
                sys.executable,
                str(MIGRATE_HELPER),
                "--server",
                "demo",
                "--repo",
                str(repo_path),
                "--global",
                str(global_settings),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"migrate helper failed: stdout={result.stdout} stderr={result.stderr}"
        )

        # Parse the JSON status output
        status = json.loads(result.stdout)
        assert status.get("success") is True, f"helper reported failure: {status}"

        # Verify the .mcp.json was created
        mcp_json = repo_path / ".mcp.json"
        assert mcp_json.exists(), "Helper did not create <repo>/.mcp.json"

        data = json.loads(mcp_json.read_text(encoding="utf-8"))
        assert "mcpServers" in data, ".mcp.json must have mcpServers key"
        assert "demo" in data["mcpServers"], "demo server not migrated"
        # The migrated config should match the source
        assert (
            data["mcpServers"]["demo"]["command"] == "npx"
        ), "command field not preserved on migration"


# ---------------------------------------------------------------------------
# AC4: .mcp.json is gitignored when it contains inline secrets
# ---------------------------------------------------------------------------


class TestAC4GitignoreOnInlineSecrets:
    """AC4: When inline secrets are present, the file MUST be gitignored."""

    def test_spec_issue948_ac4_gitignore_appended_when_secrets_detected(
        self, tmp_path: Path
    ) -> None:
        """A real inline secret in the migrated server must add .mcp.json to .gitignore."""
        # The test name matches the spec-validator checklist exactly.
        global_settings = tmp_path / "global_settings.json"
        # A fake-but-pattern-matching GitHub PAT (40 hex chars after "ghp_").
        # This must look like a real token format to trigger pattern matching.
        fake_pat = "ghp_" + "a" * 36  # Standard GitHub PAT format (40 chars total)
        global_settings.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "github": {
                            "command": "docker",
                            "args": ["run", "ghcr.io/github/github-mcp-server"],
                            "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": fake_pat},
                        }
                    }
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        repo_path = tmp_path / "secret_repo"
        repo_path.mkdir()

        result = subprocess.run(
            [
                sys.executable,
                str(MIGRATE_HELPER),
                "--server",
                "github",
                "--repo",
                str(repo_path),
                "--global",
                str(global_settings),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        status = json.loads(result.stdout)
        assert status.get("success") is True, f"helper failed: {status}"
        assert (
            status.get("secrets_detected") is True
        ), f"Inline secret was NOT detected: {status}"

        # The crucial assertion: .gitignore must contain .mcp.json
        gitignore = repo_path / ".gitignore"
        assert gitignore.exists(), (
            "Inline secrets present but .gitignore was not created/updated."
        )
        content = gitignore.read_text(encoding="utf-8")
        assert re.search(r"^\.mcp\.json$", content, re.MULTILINE), (
            f".mcp.json missing from .gitignore. Contents:\n{content}"
        )

    def test_spec_issue948_ac4_no_gitignore_when_only_env_var_placeholder(
        self, tmp_path: Path
    ) -> None:
        """${VAR} placeholders MUST NOT trigger secret detection (false positive guard).

        Per the spec-validator checklist edge case:
            ${VAR} placeholders MUST NOT trigger secret detection.
        """
        global_settings = tmp_path / "global_settings.json"
        global_settings.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "github": {
                            "command": "docker",
                            "args": ["run", "ghcr.io/github/github-mcp-server"],
                            "env": {
                                "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}",
                                "BRAVE_API_KEY": "${BRAVE_API_KEY}",
                            },
                        }
                    }
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        repo_path = tmp_path / "envvar_repo"
        repo_path.mkdir()

        result = subprocess.run(
            [
                sys.executable,
                str(MIGRATE_HELPER),
                "--server",
                "github",
                "--repo",
                str(repo_path),
                "--global",
                str(global_settings),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        status = json.loads(result.stdout)
        assert status.get("success") is True, f"helper failed: {status}"
        assert status.get("secrets_detected") is False, (
            f"${{VAR}} placeholders MUST NOT be flagged as secrets. status={status}"
        )

        # Crucially: .gitignore should NOT have been created with .mcp.json
        gitignore = repo_path / ".gitignore"
        if gitignore.exists():
            content = gitignore.read_text(encoding="utf-8")
            assert not re.search(r"^\.mcp\.json$", content, re.MULTILINE), (
                "${VAR} placeholders should NOT trigger gitignore. "
                f"Contents:\n{content}"
            )


# ---------------------------------------------------------------------------
# Non-destructive migration guard
# ---------------------------------------------------------------------------


class TestNonDestructiveMigration:
    """Migration is a copy, not a move from global."""

    def test_spec_issue948_migration_is_non_destructive(self, tmp_path: Path) -> None:
        """The source ~/.claude/settings.json mcpServers entry must remain intact."""
        global_settings = tmp_path / "global_settings.json"
        original = {
            "mcpServers": {
                "demo": {
                    "command": "npx",
                    "args": ["-y", "@example/demo"],
                },
                "other": {"command": "echo"},
            }
        }
        global_settings.write_text(json.dumps(original, indent=2), encoding="utf-8")

        repo_path = tmp_path / "non_destructive_repo"
        repo_path.mkdir()

        result = subprocess.run(
            [
                sys.executable,
                str(MIGRATE_HELPER),
                "--server",
                "demo",
                "--repo",
                str(repo_path),
                "--global",
                str(global_settings),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        status = json.loads(result.stdout)
        assert status.get("success") is True, f"helper failed: {status}"

        # The source global file must be unchanged.
        after = json.loads(global_settings.read_text(encoding="utf-8"))
        assert after == original, (
            "Migration must be non-destructive — source mcpServers entry was modified.\n"
            f"Before: {original}\nAfter: {after}"
        )
