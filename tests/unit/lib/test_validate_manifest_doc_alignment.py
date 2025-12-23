"""
TDD tests for manifest-documentation alignment validation.

Tests that validate_manifest_doc_alignment.py:
1. Uses install_manifest.json as source of truth
2. Validates CLAUDE.md component counts
3. Validates PROJECT.md component counts
4. Validates health-check.py expected lists
5. Fails loudly on mismatch (no graceful degradation)
6. Provides actionable fix instructions

Issue #159: Prevent documentation drift after manifest completeness audit
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestManifestDocAlignmentValidator:
    """Test suite for manifest-documentation alignment validation."""

    @pytest.fixture
    def validator(self):
        """Import and return the validator module."""
        from plugins.autonomous_dev.lib import validate_manifest_doc_alignment
        return validate_manifest_doc_alignment

    @pytest.fixture
    def sample_manifest(self, tmp_path):
        """Create a sample manifest for testing."""
        manifest = {
            "version": "3.44.0",
            "agents": {
                "target": ".claude/agents",
                "files": [
                    "plugins/autonomous-dev/agents/advisor.md",
                    "plugins/autonomous-dev/agents/doc-master.md",
                    "plugins/autonomous-dev/agents/implementer.md",
                ]
            },
            "commands": {
                "target": ".claude/commands",
                "files": [
                    "plugins/autonomous-dev/commands/advise.md",
                    "plugins/autonomous-dev/commands/align.md",
                ]
            },
            "hooks": {
                "target": "~/.claude/hooks",
                "files": [
                    "plugins/autonomous-dev/hooks/hook1.py",
                    "plugins/autonomous-dev/hooks/hook2.py",
                    "plugins/autonomous-dev/hooks/hook3.py",
                    "plugins/autonomous-dev/hooks/hook4.py",
                ]
            },
            "libs": {
                "target": "~/.claude/lib",
                "files": [
                    "plugins/autonomous-dev/lib/lib1.py",
                    "plugins/autonomous-dev/lib/lib2.py",
                ]
            },
            "skills": {
                "target": ".claude/skills",
                "files": [
                    "plugins/autonomous-dev/skills/skill1/skill.md",
                ]
            }
        }
        manifest_path = tmp_path / "install_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))
        return manifest_path

    # =========================================================================
    # Test 1: Manifest is source of truth
    # =========================================================================

    def test_load_manifest_counts(self, validator, sample_manifest):
        """Manifest counts should be loaded correctly."""
        counts = validator.load_manifest_counts(sample_manifest)

        assert counts["agents"] == 3
        assert counts["commands"] == 2
        assert counts["hooks"] == 4
        assert counts["libs"] == 2
        assert counts["skills"] == 1
        assert counts["version"] == "3.44.0"

    def test_manifest_not_found_raises_error(self, validator, tmp_path):
        """Missing manifest should raise FileNotFoundError, not silently fail."""
        missing_path = tmp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError):
            validator.load_manifest_counts(missing_path)

    def test_invalid_manifest_json_raises_error(self, validator, tmp_path):
        """Invalid JSON should raise error, not silently fail."""
        bad_manifest = tmp_path / "bad.json"
        bad_manifest.write_text("not valid json {{{")

        with pytest.raises(json.JSONDecodeError):
            validator.load_manifest_counts(bad_manifest)

    # =========================================================================
    # Test 2: CLAUDE.md validation
    # =========================================================================

    def test_extract_claude_md_table_format(self, validator, tmp_path):
        """Extract counts from CLAUDE.md table format."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("""
# Header

| Component | Version | Count | Status |
|-----------|---------|-------|--------|
| Skills | 1.0.0 | 28 | ✅ Compliant |
| Commands | 1.0.0 | 8 | ✅ Compliant |
| Agents | 1.0.0 | 21 | ✅ Compliant |
| Hooks | 1.0.0 | 60 | ✅ Compliant |

More content...
""")
        counts = validator.extract_claude_md_counts(claude_md)

        assert counts["agents"] == 21
        assert counts["commands"] == 8
        assert counts["hooks"] == 60
        assert counts["skills"] == 28

    def test_extract_claude_md_version(self, validator, tmp_path):
        """Extract version from CLAUDE.md header."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("""
**Version**: v3.44.0 (Issue #159 - Manifest completeness)
""")
        version = validator.extract_claude_md_version(claude_md)
        assert version == "3.44.0"

    def test_claude_md_missing_table_raises_error(self, validator, tmp_path):
        """CLAUDE.md without component table should raise error."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Just a header\n\nNo table here.")

        with pytest.raises(validator.DocumentationDriftError) as exc:
            validator.extract_claude_md_counts(claude_md)

        assert "component table" in str(exc.value).lower()

    # =========================================================================
    # Test 3: PROJECT.md validation
    # =========================================================================

    def test_extract_project_md_table_format(self, validator, tmp_path):
        """Extract counts from PROJECT.md table format."""
        project_md = tmp_path / "PROJECT.md"
        project_md.write_text("""
### Current Components (v3.44.0)

| Component | Count | Purpose |
|-----------|-------|---------|
| Agents | 21 | Specialized AI assistants |
| Skills | 28 | Progressive disclosure |
| Commands | 8 | Slash commands |
| Hooks | 60 | Automation |
| Libraries | 74 | Python utilities |
""")
        counts = validator.extract_project_md_counts(project_md)

        assert counts["agents"] == 21
        assert counts["commands"] == 8
        assert counts["hooks"] == 60
        assert counts["libs"] == 74
        assert counts["skills"] == 28

    def test_extract_project_md_version(self, validator, tmp_path):
        """Extract version from PROJECT.md header."""
        project_md = tmp_path / "PROJECT.md"
        project_md.write_text("**Version**: v3.44.0\n")

        version = validator.extract_project_md_version(project_md)
        assert version == "3.44.0"

    # =========================================================================
    # Test 4: health_check.py validation
    # =========================================================================

    def test_extract_health_check_lists(self, validator, tmp_path):
        """Extract expected component lists from health_check.py."""
        health_check_py = tmp_path / "health_check.py"
        health_check_py.write_text('''
    EXPECTED_AGENTS = [
        "doc-master",
        "implementer",
        "reviewer",
    ]

    EXPECTED_HOOKS = [
        "auto_format.py",
        "auto_test.py",
    ]

    EXPECTED_COMMANDS = [
        "advise.md",
        "align.md",
        "auto-implement.md",
    ]
''')
        counts = validator.extract_health_check_counts(health_check_py)

        assert counts["agents"] == 3
        assert counts["hooks"] == 2
        assert counts["commands"] == 3

    # =========================================================================
    # Test 5: Mismatch detection
    # =========================================================================

    def test_detect_mismatch_returns_differences(self, validator):
        """Detect mismatches between manifest and docs."""
        manifest_counts = {"agents": 21, "commands": 8, "hooks": 60}
        doc_counts = {"agents": 8, "commands": 7, "hooks": 51}

        mismatches = validator.detect_mismatches(manifest_counts, doc_counts)

        assert len(mismatches) == 3
        assert mismatches["agents"] == {"expected": 21, "actual": 8}
        assert mismatches["commands"] == {"expected": 8, "actual": 7}
        assert mismatches["hooks"] == {"expected": 60, "actual": 51}

    def test_detect_mismatch_returns_empty_when_aligned(self, validator):
        """No mismatches when counts match."""
        manifest_counts = {"agents": 21, "commands": 8}
        doc_counts = {"agents": 21, "commands": 8}

        mismatches = validator.detect_mismatches(manifest_counts, doc_counts)
        assert len(mismatches) == 0

    def test_version_mismatch_detected(self, validator):
        """Version mismatch should be detected."""
        mismatches = validator.detect_version_mismatch("3.44.0", "3.41.0")

        assert mismatches["version"] == {"expected": "3.44.0", "actual": "3.41.0"}

    # =========================================================================
    # Test 6: Full validation
    # =========================================================================

    def test_validate_alignment_passes_when_aligned(self, validator, tmp_path, sample_manifest):
        """Full validation passes when all docs match manifest."""
        # Create aligned docs
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("""
**Version**: v3.44.0

| Component | Version | Count | Status |
|-----------|---------|-------|--------|
| Agents | 1.0.0 | 3 | ✅ |
| Commands | 1.0.0 | 2 | ✅ |
| Hooks | 1.0.0 | 4 | ✅ |
| Skills | 1.0.0 | 1 | ✅ |
""")

        result = validator.validate_alignment(
            manifest_path=sample_manifest,
            claude_md_path=claude_md,
        )

        assert result["status"] == "ALIGNED"
        assert len(result["mismatches"]) == 0

    def test_validate_alignment_fails_when_drifted(self, validator, tmp_path, sample_manifest):
        """Full validation fails when docs don't match manifest."""
        # Create misaligned docs
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("""
**Version**: v3.41.0

| Component | Version | Count | Status |
|-----------|---------|-------|--------|
| Agents | 1.0.0 | 8 | ✅ |
| Commands | 1.0.0 | 7 | ✅ |
| Hooks | 1.0.0 | 11 | ✅ |
| Skills | 1.0.0 | 28 | ✅ |
""")

        result = validator.validate_alignment(
            manifest_path=sample_manifest,
            claude_md_path=claude_md,
        )

        assert result["status"] == "DRIFTED"
        assert len(result["mismatches"]) > 0
        assert "claude_md_agents" in result["mismatches"]

    # =========================================================================
    # Test 7: Actionable fix instructions
    # =========================================================================

    def test_generate_fix_instructions(self, validator):
        """Generate actionable fix instructions for mismatches."""
        mismatches = {
            "agents": {"expected": 21, "actual": 8, "file": "CLAUDE.md"},
            "version": {"expected": "3.44.0", "actual": "3.41.0", "file": "PROJECT.md"},
        }

        instructions = validator.generate_fix_instructions(mismatches)

        assert "CLAUDE.md" in instructions
        assert "agents" in instructions.lower()
        assert "21" in instructions
        assert "8" in instructions
        assert "PROJECT.md" in instructions

    # =========================================================================
    # Test 8: CLI integration
    # =========================================================================

    def test_cli_returns_nonzero_on_drift(self, validator, tmp_path, sample_manifest):
        """CLI should return non-zero exit code on drift."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("""
**Version**: v3.41.0

| Component | Version | Count | Status |
|-----------|---------|-------|--------|
| Agents | 1.0.0 | 999 | ✅ |
""")

        exit_code = validator.main([
            "--manifest", str(sample_manifest),
            "--claude-md", str(claude_md),
        ])

        assert exit_code != 0

    def test_cli_returns_zero_on_aligned(self, validator, tmp_path, sample_manifest):
        """CLI should return zero exit code when aligned."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("""
**Version**: v3.44.0

| Component | Version | Count | Status |
|-----------|---------|-------|--------|
| Agents | 1.0.0 | 3 | ✅ |
| Commands | 1.0.0 | 2 | ✅ |
| Hooks | 1.0.0 | 4 | ✅ |
| Skills | 1.0.0 | 1 | ✅ |
""")
        # Create aligned PROJECT.md to avoid default path lookup
        project_md = tmp_path / "PROJECT.md"
        project_md.write_text("""
**Version**: v3.44.0

| Component | Count | Purpose |
|-----------|-------|---------|
| Agents | 3 | AI assistants |
| Commands | 2 | Slash commands |
| Hooks | 4 | Automation |
| Libraries | 2 | Python utils |
| Skills | 1 | Knowledge |
""")

        exit_code = validator.main([
            "--manifest", str(sample_manifest),
            "--claude-md", str(claude_md),
            "--project-md", str(project_md),
        ])

        assert exit_code == 0


class TestPreCommitHookIntegration:
    """Tests for pre-commit hook integration."""

    @pytest.fixture
    def validator(self):
        """Import and return the validator module."""
        from plugins.autonomous_dev.lib import validate_manifest_doc_alignment
        return validate_manifest_doc_alignment

    def test_hook_blocks_commit_on_drift(self, validator):
        """Pre-commit hook should block commits when drift detected."""
        # This tests the hook's interface - it should return blocking result
        result = {
            "status": "DRIFTED",
            "mismatches": {"agents": {"expected": 21, "actual": 8}},
        }

        should_block = validator.should_block_commit(result)
        assert should_block is True

    def test_hook_allows_commit_when_aligned(self, validator):
        """Pre-commit hook should allow commits when aligned."""
        result = {
            "status": "ALIGNED",
            "mismatches": {},
        }

        should_block = validator.should_block_commit(result)
        assert should_block is False
