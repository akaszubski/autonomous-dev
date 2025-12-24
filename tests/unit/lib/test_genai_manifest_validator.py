#!/usr/bin/env python3
"""
TDD Tests for GenAI Manifest Validator (FAILING - Red Phase)

This module contains FAILING tests for genai_manifest_validator.py which validates
manifest alignment using LLM-powered structured output validation.

Requirements:
1. GenAI validation with structured output (JSON schema validation)
2. Detect count mismatches (agents, commands, skills, hooks)
3. API key absence handling (returns None for fallback)
4. Token budget enforcement (max 8K tokens per validation)
5. Rate limit/timeout error handling
6. Schema validation of LLM outputs

Test Coverage Target: 95%+ of GenAI validation logic

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe GenAI validation requirements
- Tests should FAIL until genai_manifest_validator.py is implemented
- Each test validates ONE validation requirement

Author: test-master agent
Date: 2025-12-24
Related: Issue #160 - GenAI manifest alignment validation
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# This import will FAIL until genai_manifest_validator.py is created
from plugins.autonomous_dev.lib.genai_manifest_validator import (
    GenAIManifestValidator,
    ManifestValidationResult,
    ManifestIssue,
    IssueLevel,
)


class TestGenAIManifestValidatorInitialization:
    """Test GenAI manifest validator initialization."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository with manifest."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Create plugin.json
        plugin_dir = repo_root / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        manifest = {
            "name": "autonomous-dev",
            "version": "3.44.0",
            "agents": 8,
            "skills": 28,
            "commands": ["/auto-implement", "/batch-implement"],
            "hooks": {"core": 11, "optional": 20}
        }

        (plugin_dir / "plugin.json").write_text(json.dumps(manifest, indent=2))

        # Create CLAUDE.md
        claude_md = repo_root / "CLAUDE.md"
        claude_md.write_text("""
# Claude Code Bootstrap

**Version**: v3.44.0

## Component Versions

| Component | Version | Count | Status |
|-----------|---------|-------|--------|
| Skills | 1.0.0 | 28 | ✅ Compliant |
| Commands | 1.0.0 | 7 | ✅ Compliant |
| Agents | 1.0.0 | 8 | ✅ Compliant |
| Hooks | 1.0.0 | 11 core | ✅ Compliant |
        """)

        return repo_root

    def test_initialization_with_valid_repo(self, temp_repo):
        """Test validator initializes with valid repository.

        REQUIREMENT: Initialize validator with repository path.
        Expected: Validator created with correct paths.
        """
        validator = GenAIManifestValidator(temp_repo)

        assert validator.repo_root == temp_repo
        assert validator.manifest_path == temp_repo / "plugins" / "autonomous-dev" / "plugin.json"
        assert validator.claude_md_path == temp_repo / "CLAUDE.md"

    def test_initialization_missing_api_key(self, temp_repo):
        """Test validator handles missing API key gracefully.

        REQUIREMENT: Return None when API key absent (enables fallback).
        Expected: Validator initializes but has_api_key=False.
        """
        with patch.dict(os.environ, {}, clear=True):
            validator = GenAIManifestValidator(temp_repo)

            assert validator.has_api_key is False
            assert validator.client is None

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"})
    def test_initialization_with_api_key(self, temp_repo):
        """Test validator initializes with API key.

        REQUIREMENT: Initialize LLM client when API key present.
        Expected: Validator has_api_key=True and client configured.
        """
        with patch("anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client

            validator = GenAIManifestValidator(temp_repo)

            assert validator.has_api_key is True
            assert validator.client is not None
            mock_anthropic.assert_called_once_with(api_key="sk-ant-test123")


class TestSuccessfulValidation:
    """Test successful validation with aligned documentation."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository with aligned manifest."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        plugin_dir = repo_root / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        manifest = {
            "name": "autonomous-dev",
            "version": "3.44.0",
            "agents": 8,
            "skills": 28,
            "commands": ["/auto-implement", "/batch-implement"],
            "hooks": {"core": 11}
        }

        (plugin_dir / "plugin.json").write_text(json.dumps(manifest, indent=2))

        claude_md = repo_root / "CLAUDE.md"
        claude_md.write_text("""
**Version**: v3.44.0

| Component | Count |
|-----------|-------|
| Skills | 28 |
| Commands | 2 |
| Agents | 8 |
| Hooks | 11 core |
        """)

        return repo_root

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"})
    @patch("anthropic.Anthropic")
    def test_validation_all_components_aligned(self, mock_anthropic, temp_repo):
        """Test validation passes when all components aligned.

        REQUIREMENT: Detect aligned documentation.
        Expected: ValidationResult with is_valid=True, no issues.
        """
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        # Mock LLM response with structured output
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "is_aligned": True,
            "issues": [],
            "summary": "All component counts match between manifest and documentation"
        })
        mock_client.messages.create.return_value = mock_response

        validator = GenAIManifestValidator(temp_repo)
        result = validator.validate()

        assert result.is_valid is True
        assert len(result.issues) == 0
        assert "aligned" in result.summary.lower() or "match" in result.summary.lower()

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"})
    @patch("anthropic.Anthropic")
    def test_validation_uses_correct_model(self, mock_anthropic, temp_repo):
        """Test validation uses Claude Sonnet 4.5.

        REQUIREMENT: Use latest Sonnet model for accuracy.
        Expected: API call uses claude-sonnet-4-5-20250929.
        """
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "is_aligned": True,
            "issues": [],
            "summary": "Aligned"
        })
        mock_client.messages.create.return_value = mock_response

        validator = GenAIManifestValidator(temp_repo)
        validator.validate()

        # Verify model used
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-sonnet-4-5-20250929"


class TestCountMismatchDetection:
    """Test detection of count mismatches."""

    @pytest.fixture
    def temp_repo_mismatched(self, tmp_path):
        """Create repository with count mismatches."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        plugin_dir = repo_root / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        # Manifest says 8 agents
        manifest = {
            "name": "autonomous-dev",
            "version": "3.44.0",
            "agents": 8,
            "skills": 28,
            "commands": ["/auto-implement", "/batch-implement"],
            "hooks": {"core": 11}
        }

        (plugin_dir / "plugin.json").write_text(json.dumps(manifest, indent=2))

        # CLAUDE.md says 21 agents (mismatch!)
        claude_md = repo_root / "CLAUDE.md"
        claude_md.write_text("""
**Version**: v3.44.0

| Component | Count |
|-----------|-------|
| Skills | 28 |
| Agents | 21 |
| Hooks | 11 core |
        """)

        return repo_root

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"})
    @patch("anthropic.Anthropic")
    def test_detect_agent_count_mismatch(self, mock_anthropic, temp_repo_mismatched):
        """Test detection of agent count mismatch.

        REQUIREMENT: Detect when manifest and CLAUDE.md disagree on counts.
        Expected: ValidationResult with is_valid=False, issue reported.
        """
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        # Mock LLM response detecting mismatch
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "is_aligned": False,
            "issues": [
                {
                    "component": "agents",
                    "level": "ERROR",
                    "message": "Agent count mismatch",
                    "details": "Manifest declares 8 agents but CLAUDE.md shows 21 agents",
                    "location": "CLAUDE.md:Component Versions table"
                }
            ],
            "summary": "Found 1 alignment issue: agent count mismatch"
        })
        mock_client.messages.create.return_value = mock_response

        validator = GenAIManifestValidator(temp_repo_mismatched)
        result = validator.validate()

        assert result.is_valid is False
        assert len(result.issues) == 1
        assert result.issues[0].component == "agents"
        assert result.issues[0].level == IssueLevel.ERROR
        assert "8" in result.issues[0].details
        assert "21" in result.issues[0].details

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"})
    @patch("anthropic.Anthropic")
    def test_detect_multiple_mismatches(self, mock_anthropic, temp_repo_mismatched):
        """Test detection of multiple component mismatches.

        REQUIREMENT: Report all mismatches found.
        Expected: ValidationResult with multiple issues.
        """
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "is_aligned": False,
            "issues": [
                {
                    "component": "agents",
                    "level": "ERROR",
                    "message": "Agent count mismatch",
                    "details": "Manifest: 8, CLAUDE.md: 21",
                    "location": "CLAUDE.md:7"
                },
                {
                    "component": "skills",
                    "level": "WARNING",
                    "message": "Skills count minor discrepancy",
                    "details": "Manifest: 28, CLAUDE.md: 27 (likely typo)",
                    "location": "CLAUDE.md:5"
                }
            ],
            "summary": "Found 2 alignment issues"
        })
        mock_client.messages.create.return_value = mock_response

        validator = GenAIManifestValidator(temp_repo_mismatched)
        result = validator.validate()

        assert result.is_valid is False
        assert len(result.issues) == 2
        assert result.issues[0].component == "agents"
        assert result.issues[1].component == "skills"


class TestAPIKeyAbsenceHandling:
    """Test handling of missing API keys."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        plugin_dir = repo_root / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        manifest = {"name": "autonomous-dev", "version": "3.44.0", "agents": 8}
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest))

        return repo_root

    def test_validation_without_api_key_returns_none(self, temp_repo):
        """Test validation returns None when API key absent.

        REQUIREMENT: Return None for fallback to regex validator.
        Expected: validate() returns None (not an exception).
        """
        with patch.dict(os.environ, {}, clear=True):
            validator = GenAIManifestValidator(temp_repo)
            result = validator.validate()

            assert result is None

    def test_has_api_key_property(self, temp_repo):
        """Test has_api_key property for external checks.

        REQUIREMENT: Allow hybrid validator to check API availability.
        Expected: has_api_key=False when no key present.
        """
        with patch.dict(os.environ, {}, clear=True):
            validator = GenAIManifestValidator(temp_repo)

            assert validator.has_api_key is False


class TestTokenBudgetEnforcement:
    """Test token budget enforcement (max 8K tokens)."""

    @pytest.fixture
    def temp_repo_large(self, tmp_path):
        """Create repository with large CLAUDE.md."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        plugin_dir = repo_root / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        manifest = {"name": "autonomous-dev", "version": "3.44.0", "agents": 8}
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest))

        # Create 20KB CLAUDE.md (exceeds 8K token budget)
        large_content = "# Documentation\n" + ("This is filler content. " * 1000) + "\n"
        (repo_root / "CLAUDE.md").write_text(large_content * 10)

        return repo_root

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"})
    @patch("anthropic.Anthropic")
    def test_truncate_large_files(self, mock_anthropic, temp_repo_large):
        """Test large files truncated to stay under token budget.

        REQUIREMENT: Enforce 8K token budget.
        Expected: Files truncated, validation proceeds.
        """
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "is_aligned": True,
            "issues": [],
            "summary": "Validated (truncated due to size)"
        })
        mock_client.messages.create.return_value = mock_response

        validator = GenAIManifestValidator(temp_repo_large)
        result = validator.validate()

        # Should complete without error
        assert result is not None

        # Verify prompt was truncated
        call_kwargs = mock_client.messages.create.call_args[1]
        prompt = call_kwargs["messages"][0]["content"]

        # Estimate tokens (rough: 1 token ≈ 4 chars)
        estimated_tokens = len(prompt) / 4
        assert estimated_tokens < 8000


class TestRateLimitAndTimeoutHandling:
    """Test rate limit and timeout error handling."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        plugin_dir = repo_root / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        manifest = {"name": "autonomous-dev", "version": "3.44.0", "agents": 8}
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest))

        (repo_root / "CLAUDE.md").write_text("# Docs\n")

        return repo_root

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"})
    @patch("anthropic.Anthropic")
    def test_handle_rate_limit_error(self, mock_anthropic, temp_repo):
        """Test graceful handling of rate limit errors.

        REQUIREMENT: Handle API rate limits gracefully.
        Expected: Returns None for fallback (not exception).
        """
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        # Simulate rate limit error
        import anthropic
        mock_client.messages.create.side_effect = anthropic.RateLimitError("Rate limit exceeded")

        validator = GenAIManifestValidator(temp_repo)
        result = validator.validate()

        # Should return None for fallback
        assert result is None

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"})
    @patch("anthropic.Anthropic")
    def test_handle_timeout_error(self, mock_anthropic, temp_repo):
        """Test graceful handling of timeout errors.

        REQUIREMENT: Handle API timeouts gracefully.
        Expected: Returns None for fallback.
        """
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        # Simulate timeout
        import anthropic
        mock_client.messages.create.side_effect = anthropic.APITimeoutError("Request timeout")

        validator = GenAIManifestValidator(temp_repo)
        result = validator.validate()

        assert result is None

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"})
    @patch("anthropic.Anthropic")
    def test_handle_generic_api_error(self, mock_anthropic, temp_repo):
        """Test graceful handling of generic API errors.

        REQUIREMENT: Handle unexpected API errors.
        Expected: Returns None for fallback.
        """
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        # Simulate generic error
        mock_client.messages.create.side_effect = Exception("Unexpected API error")

        validator = GenAIManifestValidator(temp_repo)
        result = validator.validate()

        assert result is None


class TestSchemaValidation:
    """Test schema validation of LLM outputs."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        plugin_dir = repo_root / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        manifest = {"name": "autonomous-dev", "version": "3.44.0", "agents": 8}
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest))

        (repo_root / "CLAUDE.md").write_text("# Docs\n")

        return repo_root

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"})
    @patch("anthropic.Anthropic")
    def test_reject_invalid_json_response(self, mock_anthropic, temp_repo):
        """Test rejection of invalid JSON responses.

        REQUIREMENT: Validate LLM response schema.
        Expected: Returns None when JSON invalid.
        """
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        # Mock invalid JSON response
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = "This is not JSON at all!"
        mock_client.messages.create.return_value = mock_response

        validator = GenAIManifestValidator(temp_repo)
        result = validator.validate()

        # Should return None when response invalid
        assert result is None

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"})
    @patch("anthropic.Anthropic")
    def test_reject_missing_required_fields(self, mock_anthropic, temp_repo):
        """Test rejection of responses missing required fields.

        REQUIREMENT: Validate required fields in response.
        Expected: Returns None when required fields missing.
        """
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        # Mock response missing 'is_aligned' field
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "issues": [],
            "summary": "Missing is_aligned field"
        })
        mock_client.messages.create.return_value = mock_response

        validator = GenAIManifestValidator(temp_repo)
        result = validator.validate()

        assert result is None

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"})
    @patch("anthropic.Anthropic")
    def test_validate_issue_schema(self, mock_anthropic, temp_repo):
        """Test validation of issue object schema.

        REQUIREMENT: Validate issue fields (component, level, message, details, location).
        Expected: Accepts valid issue schema.
        """
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        # Valid issue schema
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "is_aligned": False,
            "issues": [
                {
                    "component": "agents",
                    "level": "ERROR",
                    "message": "Count mismatch",
                    "details": "Manifest: 8, CLAUDE.md: 21",
                    "location": "CLAUDE.md:7"
                }
            ],
            "summary": "Found 1 issue"
        })
        mock_client.messages.create.return_value = mock_response

        validator = GenAIManifestValidator(temp_repo)
        result = validator.validate()

        assert result is not None
        assert len(result.issues) == 1
        assert result.issues[0].component == "agents"
        assert result.issues[0].level == IssueLevel.ERROR


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_missing_manifest_file(self, tmp_path):
        """Test handling of missing manifest file.

        REQUIREMENT: Handle missing plugin.json gracefully.
        Expected: Initialization succeeds, validation returns None.
        """
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"}):
            validator = GenAIManifestValidator(repo_root)
            result = validator.validate()

            assert result is None

    def test_missing_claude_md_file(self, tmp_path):
        """Test handling of missing CLAUDE.md file.

        REQUIREMENT: Handle missing CLAUDE.md gracefully.
        Expected: Validation returns None.
        """
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        plugin_dir = repo_root / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        manifest = {"name": "autonomous-dev", "version": "3.44.0"}
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest))

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"}):
            validator = GenAIManifestValidator(repo_root)
            result = validator.validate()

            assert result is None

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"})
    @patch("anthropic.Anthropic")
    def test_manifest_missing_components_key(self, mock_anthropic, tmp_path):
        """Test handling of manifest without component counts.

        REQUIREMENT: Handle manifest with missing component keys.
        Expected: Validation proceeds with available data.
        """
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        plugin_dir = repo_root / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        # Manifest with minimal fields (no agents/skills/etc)
        manifest = {
            "name": "autonomous-dev",
            "version": "3.44.0"
        }
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest))

        (repo_root / "CLAUDE.md").write_text("# Docs\n")

        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "is_aligned": True,
            "issues": [],
            "summary": "No component counts to validate"
        })
        mock_client.messages.create.return_value = mock_response

        validator = GenAIManifestValidator(repo_root)
        result = validator.validate()

        assert result is not None

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"})
    @patch("anthropic.Anthropic")
    def test_version_format_variations(self, mock_anthropic, tmp_path):
        """Test handling of version format variations (v3.44.0 vs 3.44.0).

        REQUIREMENT: Handle version prefix variations.
        Expected: Accepts both formats as equivalent.
        """
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        plugin_dir = repo_root / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        manifest = {"name": "autonomous-dev", "version": "3.44.0"}  # No 'v' prefix
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest))

        # CLAUDE.md uses 'v' prefix
        (repo_root / "CLAUDE.md").write_text("**Version**: v3.44.0\n")

        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "is_aligned": True,
            "issues": [],
            "summary": "Version formats normalized and match"
        })
        mock_client.messages.create.return_value = mock_response

        validator = GenAIManifestValidator(repo_root)
        result = validator.validate()

        assert result.is_valid is True

    def test_empty_component_lists(self, tmp_path):
        """Test handling of empty component lists.

        REQUIREMENT: Handle empty arrays/objects gracefully.
        Expected: Validation proceeds.
        """
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        plugin_dir = repo_root / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        manifest = {
            "name": "autonomous-dev",
            "version": "3.44.0",
            "commands": [],  # Empty list
            "hooks": {}  # Empty object
        }
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest))

        (repo_root / "CLAUDE.md").write_text("# Docs\n")

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"}):
            validator = GenAIManifestValidator(repo_root)
            # Should initialize without error
            assert validator is not None


class TestOpenRouterIntegration:
    """Test OpenRouter integration for GenAI validation."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary repository with manifest."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        plugin_dir = repo_root / "plugins" / "autonomous-dev"
        plugin_dir.mkdir(parents=True)

        manifest = {
            "name": "autonomous-dev",
            "version": "3.44.0",
            "agents": 8,
            "skills": 28,
        }
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest, indent=2))
        (repo_root / "CLAUDE.md").write_text("# Claude Code\n**Version**: v3.44.0\n")

        return repo_root

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test123"}, clear=True)
    @patch("openai.OpenAI")
    def test_openrouter_initialization(self, mock_openai, temp_repo):
        """Test validator initializes with OpenRouter API key.

        REQUIREMENT: Support OpenRouter as alternative to Anthropic.
        Expected: Validator uses OpenRouter client when OPENROUTER_API_KEY set.
        """
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        validator = GenAIManifestValidator(temp_repo)

        assert validator.has_api_key is True
        assert validator.client_type == "openrouter"
        mock_openai.assert_called_once_with(
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-or-test123",
        )

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test123"}, clear=True)
    @patch("openai.OpenAI")
    def test_openrouter_uses_default_model(self, mock_openai, temp_repo):
        """Test OpenRouter uses cheap default model.

        REQUIREMENT: Default to Gemini Flash for cost efficiency.
        Expected: Model set to google/gemini-2.0-flash-exp.
        """
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        validator = GenAIManifestValidator(temp_repo)

        assert validator.model == "google/gemini-2.0-flash-exp"

    @patch.dict(os.environ, {
        "OPENROUTER_API_KEY": "sk-or-test123",
        "OPENROUTER_MODEL": "anthropic/claude-3-haiku"
    }, clear=True)
    @patch("openai.OpenAI")
    def test_openrouter_model_override(self, mock_openai, temp_repo):
        """Test OpenRouter model can be overridden via env var.

        REQUIREMENT: Allow model selection via OPENROUTER_MODEL.
        Expected: Uses specified model instead of default.
        """
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        validator = GenAIManifestValidator(temp_repo)

        assert validator.model == "anthropic/claude-3-haiku"

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test123"}, clear=True)
    @patch("openai.OpenAI")
    def test_openrouter_validation_success(self, mock_openai, temp_repo):
        """Test successful validation via OpenRouter.

        REQUIREMENT: Complete validation flow with OpenRouter.
        Expected: Returns valid ManifestValidationResult.
        """
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        # Mock OpenRouter response (OpenAI-compatible format)
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "is_aligned": True,
            "issues": [],
            "summary": "All components aligned"
        })
        mock_client.chat.completions.create.return_value = mock_response

        validator = GenAIManifestValidator(temp_repo)
        result = validator.validate()

        assert result is not None
        assert result.is_valid is True
        assert len(result.issues) == 0

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test123"}, clear=True)
    @patch("openai.OpenAI")
    def test_openrouter_detects_mismatches(self, mock_openai, temp_repo):
        """Test OpenRouter detects component mismatches.

        REQUIREMENT: GenAI validation detects issues via OpenRouter.
        Expected: Returns issues when counts don't match.
        """
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "is_aligned": False,
            "issues": [
                {
                    "component": "agents",
                    "level": "ERROR",
                    "message": "Agent count mismatch",
                    "details": "Manifest: 8, CLAUDE.md: 10",
                    "location": "CLAUDE.md:15"
                }
            ],
            "summary": "1 component mismatch found"
        })
        mock_client.chat.completions.create.return_value = mock_response

        validator = GenAIManifestValidator(temp_repo)
        result = validator.validate()

        assert result is not None
        assert result.is_valid is False
        assert len(result.issues) == 1
        assert result.issues[0].component == "agents"

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test123"}, clear=True)
    @patch("openai.OpenAI")
    def test_openrouter_api_error_returns_none(self, mock_openai, temp_repo):
        """Test OpenRouter API errors return None for fallback.

        REQUIREMENT: Graceful degradation on API errors.
        Expected: Returns None (not exception) for regex fallback.
        """
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        # Simulate API error
        mock_client.chat.completions.create.side_effect = Exception("OpenRouter API error")

        validator = GenAIManifestValidator(temp_repo)
        result = validator.validate()

        assert result is None

    @patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "sk-ant-test123",
        "OPENROUTER_API_KEY": "sk-or-test123"
    }, clear=True)
    @patch("anthropic.Anthropic")
    def test_anthropic_takes_priority_over_openrouter(self, mock_anthropic, temp_repo):
        """Test Anthropic API key takes priority over OpenRouter.

        REQUIREMENT: Prefer Anthropic when both keys available.
        Expected: Uses Anthropic client when both keys set.
        """
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        validator = GenAIManifestValidator(temp_repo)

        assert validator.client_type == "anthropic"
