"""
Integration tests for manifest-doc alignment validator against REAL files.

These tests run against the actual CLAUDE.md, PROJECT.md, and install_manifest.json
to catch format drift that unit tests with mocks would miss.

Issue #159: Critical reliability check - validates the validator works on real data.
"""

import subprocess
import sys
from pathlib import Path

import pytest


class TestRealFileAlignment:
    """Test validator against actual repository files."""

    @pytest.fixture
    def project_root(self) -> Path:
        """Get the project root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def validator_path(self, project_root) -> Path:
        """Get the validator script path."""
        return project_root / "plugins" / "autonomous-dev" / "lib" / "validate_manifest_doc_alignment.py"

    def test_validator_script_exists(self, validator_path):
        """Validator script must exist."""
        assert validator_path.exists(), f"Validator not found at {validator_path}"

    def test_validator_runs_without_error(self, validator_path):
        """Validator must run without crashing."""
        result = subprocess.run(
            [sys.executable, str(validator_path)],
            capture_output=True,
            timeout=30
        )
        # Should exit cleanly (0 or 1), not crash
        assert result.returncode in (0, 1), f"Validator crashed: {result.stderr.decode()}"

    def test_validator_passes_on_aligned_docs(self, validator_path):
        """Validator should pass when docs are aligned with manifest.

        If this test fails, either:
        1. Documentation has drifted from manifest (fix the docs)
        2. Validator regex has drifted from doc format (fix the regex)
        """
        result = subprocess.run(
            [sys.executable, str(validator_path)],
            capture_output=True,
            timeout=30
        )
        stdout = result.stdout.decode()
        stderr = result.stderr.decode()

        assert result.returncode == 0, (
            f"Documentation is not aligned with manifest!\n"
            f"stdout: {stdout}\n"
            f"stderr: {stderr}\n\n"
            f"Fix: Update CLAUDE.md and PROJECT.md to match install_manifest.json counts"
        )

    def test_manifest_exists(self, project_root):
        """install_manifest.json must exist."""
        manifest_path = project_root / "plugins" / "autonomous-dev" / "config" / "install_manifest.json"
        assert manifest_path.exists(), f"Manifest not found at {manifest_path}"

    def test_claude_md_exists(self, project_root):
        """CLAUDE.md must exist at project root."""
        claude_md = project_root / "CLAUDE.md"
        assert claude_md.exists(), f"CLAUDE.md not found at {claude_md}"

    def test_project_md_exists(self, project_root):
        """PROJECT.md must exist at project root."""
        project_md = project_root / "PROJECT.md"
        assert project_md.exists(), f"PROJECT.md not found at {project_md}"

    def test_claude_md_has_component_table(self, project_root):
        """CLAUDE.md must have a component table the validator can parse."""
        claude_md = project_root / "CLAUDE.md"
        content = claude_md.read_text()

        # Check for table header
        assert "| Component |" in content, "CLAUDE.md missing component table"
        assert "| Agents |" in content or "| agents |" in content.lower(), "CLAUDE.md missing Agents row"

    def test_project_md_has_component_table(self, project_root):
        """PROJECT.md must have a component table the validator can parse."""
        project_md = project_root / "PROJECT.md"
        content = project_md.read_text()

        # Check for table
        assert "| Component |" in content or "| Agents |" in content, "PROJECT.md missing component table"


class TestValidatorFailsLoud:
    """Test that validator fails loudly, not silently."""

    @pytest.fixture
    def project_root(self) -> Path:
        return Path(__file__).parent.parent.parent

    def test_validator_detects_count_mismatch(self, project_root, tmp_path):
        """Validator must detect when counts don't match."""
        # Create a fake CLAUDE.md with wrong counts
        fake_claude = tmp_path / "CLAUDE.md"
        fake_claude.write_text("""
**Version**: v3.44.0

| Component | Version | Count | Status |
|-----------|---------|-------|--------|
| Agents | 1.0.0 | 999 | ✅ |
| Commands | 1.0.0 | 999 | ✅ |
| Hooks | 1.0.0 | 999 | ✅ |
| Skills | 1.0.0 | 999 | ✅ |
""")

        validator_path = project_root / "plugins" / "autonomous-dev" / "lib" / "validate_manifest_doc_alignment.py"
        manifest_path = project_root / "plugins" / "autonomous-dev" / "config" / "install_manifest.json"

        result = subprocess.run(
            [sys.executable, str(validator_path),
             "--manifest", str(manifest_path),
             "--claude-md", str(fake_claude)],
            capture_output=True,
            timeout=30
        )

        # Must fail (exit code 1), not pass silently
        assert result.returncode != 0, (
            "Validator should have detected count mismatch but passed!\n"
            f"stdout: {result.stdout.decode()}"
        )

    def test_validator_errors_on_missing_manifest(self, tmp_path):
        """Validator must error when manifest is missing."""
        from plugins.autonomous_dev.lib import validate_manifest_doc_alignment as validator

        missing_manifest = tmp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError):
            validator.load_manifest_counts(missing_manifest)

    def test_validator_errors_on_invalid_json(self, tmp_path):
        """Validator must error on invalid JSON, not silently pass."""
        import json
        from plugins.autonomous_dev.lib import validate_manifest_doc_alignment as validator

        bad_manifest = tmp_path / "bad.json"
        bad_manifest.write_text("not valid json {{{")

        with pytest.raises(json.JSONDecodeError):
            validator.load_manifest_counts(bad_manifest)
