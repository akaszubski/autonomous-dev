#!/usr/bin/env python3
"""
TDD Tests for api-integration-patterns Skill (FAILING - Red Phase)

This module contains FAILING tests for the api-integration-patterns skill that will
extract duplicated API integration code from libraries that interact with external
services (Issue #78 Phase 8.8).

Skill Requirements:
1. YAML frontmatter with name, type, description, keywords, auto_activate
2. Progressive disclosure architecture (metadata in frontmatter, content loads on-demand)
3. Standardized API integration patterns:
   - Subprocess safety (command injection prevention)
   - GitHub CLI (gh) integration patterns
   - Retry logic with exponential backoff
   - API authentication and credentials
   - Rate limiting and quota handling
4. Example integrations and patterns (examples/ directory)
5. Token reduction: ~40-50 tokens per library × 8 libraries = ~320-400 tokens

Test Coverage Target: 20 tests (SKILL.md format, patterns, examples, library integration)

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe skill requirements and library integration
- Tests should FAIL until skill file and library updates are implemented
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-11-16
Issue: #78 Phase 8.8
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import re

import pytest
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

SKILL_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "skills" / "api-integration-patterns"
SKILL_FILE = SKILL_DIR / "SKILL.md"
DOCS_DIR = SKILL_DIR / "docs"
EXAMPLES_DIR = SKILL_DIR / "examples"
TEMPLATES_DIR = SKILL_DIR / "templates"
LIB_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "lib"


class TestSkillCreation:
    """Test api-integration-patterns skill file structure and metadata."""

    def test_skill_file_exists(self):
        """Test SKILL.md file exists in skills/api-integration-patterns/ directory."""
        assert SKILL_FILE.exists(), (
            f"Skill file not found: {SKILL_FILE}\n"
            f"Expected: Create skills/api-integration-patterns/SKILL.md\n"
            f"See: Issue #78 Phase 8.8"
        )

    def test_skill_has_valid_yaml_frontmatter(self):
        """Test skill file has valid YAML frontmatter with required fields."""
        content = SKILL_FILE.read_text()

        # Check frontmatter exists
        assert content.startswith("---\n"), (
            "Skill file must start with YAML frontmatter (---)\n"
            "Expected format:\n"
            "---\n"
            "name: api-integration-patterns\n"
            "type: knowledge\n"
            "...\n"
        )

        # Extract frontmatter
        parts = content.split("---\n", 2)
        assert len(parts) >= 3, "Skill file must have closing --- for frontmatter"

        frontmatter = yaml.safe_load(parts[1])

        # Validate required fields
        assert frontmatter.get("name") == "api-integration-patterns", (
            "Skill name must be 'api-integration-patterns'"
        )
        assert frontmatter.get("type") == "knowledge", (
            "Skill type must be 'knowledge'"
        )
        assert "description" in frontmatter, (
            "Skill must have 'description' field"
        )
        assert "keywords" in frontmatter, (
            "Skill must have 'keywords' field for auto-activation"
        )
        assert frontmatter.get("auto_activate") is True, (
            "Skill must have 'auto_activate: true' for progressive disclosure"
        )

    def test_skill_keywords_cover_api_terms(self):
        """Test skill keywords include API integration terms."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        keywords = frontmatter.get("keywords", "")
        if isinstance(keywords, list):
            keywords = " ".join(keywords)

        expected_keywords = [
            "api", "subprocess", "github", "gh cli",
            "retry", "backoff", "authentication", "rate limit"
        ]

        for keyword in expected_keywords:
            assert keyword.lower() in keywords.lower(), (
                f"Skill keywords must include '{keyword}' for auto-activation\n"
                f"Current keywords: {keywords}"
            )

    def test_skill_defines_subprocess_safety(self):
        """Test skill defines subprocess safety pattern."""
        content = SKILL_FILE.read_text()

        assert "subprocess" in content.lower() and ("injection" in content.lower() or "safety" in content.lower()), (
            "Skill must define subprocess safety pattern\n"
            "Expected: Prevent command injection (CWE-78)\n"
            "Example: Use list arguments, avoid shell=True\n"
            "Benefits: Security, reliability"
        )

    def test_skill_defines_github_cli_integration(self):
        """Test skill defines GitHub CLI integration pattern."""
        content = SKILL_FILE.read_text()

        assert "gh cli" in content.lower() or "github cli" in content.lower(), (
            "Skill must define GitHub CLI (gh) integration pattern\n"
            "Expected: gh pr create, gh issue create, error handling\n"
            "Example: subprocess.run(['gh', 'pr', 'create', ...])\n"
            "Benefits: Automation, integration"
        )

    def test_skill_defines_retry_logic(self):
        """Test skill defines retry logic pattern."""
        content = SKILL_FILE.read_text()

        assert "retry" in content.lower() or "backoff" in content.lower(), (
            "Skill must define retry logic pattern\n"
            "Expected: Exponential backoff, max retries, timeout\n"
            "Example: Retry on network errors, 429 rate limits\n"
            "Benefits: Resilience, reliability"
        )

    def test_skill_defines_authentication_patterns(self):
        """Test skill defines API authentication pattern."""
        content = SKILL_FILE.read_text()

        assert "auth" in content.lower() or "credential" in content.lower(), (
            "Skill must define API authentication pattern\n"
            "Expected: Token management, .env files, gh auth status\n"
            "Example: GitHub token from environment or gh CLI\n"
            "Benefits: Security, integration"
        )

    def test_skill_defines_rate_limiting(self):
        """Test skill defines rate limiting pattern."""
        content = SKILL_FILE.read_text()

        assert "rate limit" in content.lower() or "quota" in content.lower(), (
            "Skill must define rate limiting pattern\n"
            "Expected: Detect 429 responses, exponential backoff, headers\n"
            "Example: Check X-RateLimit-Remaining header\n"
            "Benefits: API compliance, reliability"
        )

    def test_skill_defines_error_handling(self):
        """Test skill defines API error handling pattern."""
        content = SKILL_FILE.read_text()

        assert "error" in content.lower() and ("api" in content.lower() or "http" in content.lower()), (
            "Skill must define API error handling pattern\n"
            "Expected: HTTP status codes, timeout handling, network errors\n"
            "Example: Retry on 5xx, fail on 4xx (except 429)\n"
            "Benefits: Resilience, debugging"
        )


class TestSkillDocumentation:
    """Test api-integration-patterns skill documentation structure."""

    def test_docs_directory_exists(self):
        """Test docs/ directory exists with detailed pattern documentation."""
        assert DOCS_DIR.exists(), (
            f"Documentation directory not found: {DOCS_DIR}\n"
            f"Expected: Create skills/api-integration-patterns/docs/\n"
            f"Purpose: Detailed pattern documentation"
        )

    def test_subprocess_safety_doc_exists(self):
        """Test subprocess-safety.md documentation exists."""
        doc_file = DOCS_DIR / "subprocess-safety.md"
        assert doc_file.exists(), (
            f"Subprocess safety doc not found: {doc_file}\n"
            f"Expected: Detailed documentation of command injection prevention\n"
            f"Should include: CWE-78 prevention, list args vs shell, examples"
        )

    def test_github_cli_doc_exists(self):
        """Test github-cli-integration.md documentation exists."""
        doc_file = DOCS_DIR / "github-cli-integration.md"
        assert doc_file.exists(), (
            f"GitHub CLI doc not found: {doc_file}\n"
            f"Expected: Detailed documentation of gh CLI patterns\n"
            f"Should include: Authentication, commands, error handling"
        )

    def test_retry_logic_doc_exists(self):
        """Test retry-logic.md documentation exists."""
        doc_file = DOCS_DIR / "retry-logic.md"
        assert doc_file.exists(), (
            f"Retry logic doc not found: {doc_file}\n"
            f"Expected: Detailed documentation of retry strategies\n"
            f"Should include: Exponential backoff, max retries, jitter"
        )

    def test_authentication_doc_exists(self):
        """Test authentication-patterns.md documentation exists."""
        doc_file = DOCS_DIR / "authentication-patterns.md"
        assert doc_file.exists(), (
            f"Authentication doc not found: {doc_file}\n"
            f"Expected: Detailed documentation of auth strategies\n"
            f"Should include: Token storage, .env files, gh auth status"
        )


class TestSkillTemplates:
    """Test api-integration-patterns skill provides code templates."""

    def test_templates_directory_exists(self):
        """Test templates/ directory exists with reusable templates."""
        assert TEMPLATES_DIR.exists(), (
            f"Templates directory not found: {TEMPLATES_DIR}\n"
            f"Expected: Create skills/api-integration-patterns/templates/\n"
            f"Purpose: Reusable API integration templates"
        )

    def test_subprocess_executor_template_exists(self):
        """Test subprocess-executor-template.py exists."""
        template_file = TEMPLATES_DIR / "subprocess-executor-template.py"
        assert template_file.exists(), (
            f"Subprocess executor template not found: {template_file}\n"
            f"Expected: Template showing safe subprocess execution\n"
            f"Should include: List args, error handling, timeout"
        )

    def test_retry_decorator_template_exists(self):
        """Test retry-decorator-template.py exists."""
        template_file = TEMPLATES_DIR / "retry-decorator-template.py"
        assert template_file.exists(), (
            f"Retry decorator template not found: {template_file}\n"
            f"Expected: Template showing retry decorator pattern\n"
            f"Should include: Exponential backoff, max attempts, exceptions"
        )

    def test_github_api_template_exists(self):
        """Test github-api-template.py exists."""
        template_file = TEMPLATES_DIR / "github-api-template.py"
        assert template_file.exists(), (
            f"GitHub API template not found: {template_file}\n"
            f"Expected: Template showing gh CLI integration\n"
            f"Should include: Auth check, command execution, error handling"
        )


class TestSkillExamples:
    """Test api-integration-patterns skill provides example implementations."""

    def test_examples_directory_exists(self):
        """Test examples/ directory exists with real-world examples."""
        assert EXAMPLES_DIR.exists(), (
            f"Examples directory not found: {EXAMPLES_DIR}\n"
            f"Expected: Create skills/api-integration-patterns/examples/\n"
            f"Purpose: Real-world API integration examples"
        )

    def test_github_issue_example_exists(self):
        """Test github-issue-example.py shows issue creation."""
        example_file = EXAMPLES_DIR / "github-issue-example.py"
        assert example_file.exists(), (
            f"GitHub issue example not found: {example_file}\n"
            f"Expected: Example based on github_issue_automation.py\n"
            f"Should include: gh issue create, body formatting, labels"
        )

    def test_github_pr_example_exists(self):
        """Test github-pr-example.py shows PR creation."""
        example_file = EXAMPLES_DIR / "github-pr-example.py"
        assert example_file.exists(), (
            f"GitHub PR example not found: {example_file}\n"
            f"Expected: Example showing gh pr create pattern\n"
            f"Should include: Title, body, base branch, error handling"
        )

    def test_safe_subprocess_example_exists(self):
        """Test safe-subprocess-example.py shows command injection prevention."""
        example_file = EXAMPLES_DIR / "safe-subprocess-example.py"
        assert example_file.exists(), (
            f"Safe subprocess example not found: {example_file}\n"
            f"Expected: Example showing list args vs shell=True\n"
            f"Should include: Good and bad patterns, CWE-78 reference"
        )


class TestLibraryIntegration:
    """Test libraries with external API calls reference skill."""

    LIBRARIES_USING_SKILL = [
        "github_issue_automation.py",
        "github_issue_fetcher.py",
        "auto_implement_git_integration.py",
        "git_operations.py",
        "subprocess_executor.py",
        "plugin_updater.py",  # gh CLI for PR creation
        "brownfield_retrofit.py",  # git operations
        "health_check.py",  # subprocess for validation
    ]

    @pytest.mark.parametrize("library_file", LIBRARIES_USING_SKILL)
    def test_library_has_skill_reference(self, library_file):
        """Test library has comment referencing api-integration-patterns skill."""
        library_path = LIB_DIR / library_file

        # Skip if library doesn't exist yet
        if not library_path.exists():
            pytest.skip(f"Library {library_file} not yet created")

        content = library_path.read_text()

        # Check for skill reference in module docstring
        assert "api-integration-patterns" in content.lower(), (
            f"Library {library_file} must reference 'api-integration-patterns' skill\n"
            f"Expected: Add to module docstring or API function\n"
            f"Format: See api-integration-patterns skill for subprocess safety\n"
            f"See: Issue #78 Phase 8.8"
        )

    def test_total_library_count_using_skill(self):
        """Test at least 8 libraries use api-integration-patterns skill."""
        count = 0
        for library_file in self.LIBRARIES_USING_SKILL:
            library_path = LIB_DIR / library_file
            if library_path.exists():
                content = library_path.read_text()
                if "api-integration-patterns" in content.lower():
                    count += 1

        assert count >= 8, (
            f"Expected at least 8 libraries to reference api-integration-patterns skill, found {count}\n"
            f"Target: All libraries with subprocess/GitHub API integration\n"
            f"See: Issue #78 Phase 8.8"
        )


class TestAPIIntegrationPatterns:
    """Test specific API integration patterns defined in skill."""

    def test_skill_documents_command_injection_prevention(self):
        """Test skill documents command injection prevention (CWE-78)."""
        content = SKILL_FILE.read_text()

        assert "cwe-78" in content.lower() or "command injection" in content.lower(), (
            "Skill must document command injection prevention\n"
            "Expected: Use list args instead of string, avoid shell=True\n"
            "Example: subprocess.run(['gh', 'pr', 'create']) not 'gh pr create'\n"
            "Security: CWE-78 prevention"
        )

    def test_skill_documents_timeout_handling(self):
        """Test skill documents timeout handling pattern."""
        content = SKILL_FILE.read_text()

        assert "timeout" in content.lower(), (
            "Skill must document timeout handling pattern\n"
            "Expected: Set timeout for subprocess calls\n"
            "Example: subprocess.run(..., timeout=30)\n"
            "Benefits: Prevent hanging operations"
        )

    def test_skill_documents_error_output_capture(self):
        """Test skill documents error output capture pattern."""
        content = SKILL_FILE.read_text()

        assert "stderr" in content.lower() or "capture_output" in content.lower(), (
            "Skill must document error output capture pattern\n"
            f"Expected: Capture stdout/stderr for debugging\n"
            f"Example: subprocess.run(..., capture_output=True)\n"
            f"Benefits: Debugging, error messages"
        )

    def test_skill_documents_gh_auth_check(self):
        """Test skill documents gh auth status check pattern."""
        content = SKILL_FILE.read_text()

        assert "gh auth status" in content.lower() or "authentication check" in content.lower(), (
            "Skill must document gh auth status check pattern\n"
            "Expected: Check authentication before API calls\n"
            "Example: subprocess.run(['gh', 'auth', 'status'])\n"
            "Benefits: Better error messages, user guidance"
        )


class TestTokenSavings:
    """Test token reduction from skill extraction."""

    def test_token_reduction_per_library(self):
        """Test each library saves ~40-50 tokens by using skill reference."""
        # Expected savings calculation:
        # Before: ~80-100 tokens for inline API integration docs
        # After: ~30-40 tokens for skill reference
        # Savings: ~40-50 tokens per library

        pytest.skip(
            "Token counting requires implementation\n"
            "Expected: Use tiktoken or similar to count tokens\n"
            "Baseline: Measure tokens before/after skill extraction\n"
            "Target: 40-50 tokens saved per library"
        )

    def test_total_token_reduction(self):
        """Test total token savings across all API integration libraries."""
        # Expected total savings: 45 tokens × 8 libraries = 360 tokens

        pytest.skip(
            "Token counting requires implementation\n"
            "Expected: Aggregate token savings across all libraries\n"
            "Target: 320-400 tokens total reduction\n"
            "See: Issue #78 Phase 8.8"
        )


class TestProgressiveDisclosure:
    """Test progressive disclosure functionality."""

    def test_skill_metadata_small_for_context(self):
        """Test skill metadata (frontmatter) is small enough to keep in context."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)
        frontmatter = parts[1]

        # Frontmatter should be < 200 tokens (very rough estimate: ~4 chars per token)
        assert len(frontmatter) < 800, (
            f"Skill frontmatter too large: {len(frontmatter)} chars\n"
            f"Expected: < 800 chars (~200 tokens) for efficient context usage\n"
            f"Progressive disclosure keeps metadata small, loads full content on-demand"
        )

    def test_skill_full_content_loads_on_demand(self):
        """Test skill full content (after frontmatter) is available when needed."""
        content = SKILL_FILE.read_text()
        parts = content.split("---\n", 2)

        assert len(parts) >= 3, "Skill must have content after frontmatter"

        full_content = parts[2]

        # Full content should have detailed API integration patterns
        assert len(full_content) > 1500, (
            f"Skill content too small: {len(full_content)} chars\n"
            f"Expected: Detailed API integration patterns, examples, templates\n"
            f"Progressive disclosure: Metadata always loaded, content loaded when keywords match"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
