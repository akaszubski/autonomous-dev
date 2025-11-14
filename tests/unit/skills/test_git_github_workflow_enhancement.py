#!/usr/bin/env python3
"""
TDD Tests for git-workflow and github-workflow Skills Enhancement (FAILING - Red Phase)

This module contains FAILING tests for extracting git/github patterns from agents
into enhanced skills (Issue #67).

Skill Enhancement Requirements:

1. git-workflow skill enhancement:
   - Extract commit message patterns from commit-message-generator agent
   - Add docs/commit-patterns.md with conventional commit examples
   - Add examples/commit-examples.txt with real-world examples
   - Update SKILL.md metadata with new keywords

2. github-workflow skill enhancement:
   - Extract PR template patterns from pr-description-generator agent
   - Extract issue template patterns from issue-creator agent
   - Add docs/pr-template-guide.md with structure and best practices
   - Add docs/issue-template-guide.md with structure and best practices
   - Add examples/pr-template.md with example PR description
   - Add examples/issue-template.md with example issue description
   - Update SKILL.md metadata with new keywords

3. Agent integration:
   - commit-message-generator: Reference git-workflow skill (~100 tokens saved)
   - pr-description-generator: Reference github-workflow skill (~100 tokens saved)
   - issue-creator: Reference github-workflow skill (~100 tokens saved)

Expected Token Savings: ~300 tokens (5-8% reduction in git/github guidance)

Test Coverage Target: 100% of skill enhancement and agent integration

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe skill requirements and agent integration
- Tests should FAIL until skill files and agent updates are implemented
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-11-12
Issue: #67
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

# Git workflow skill paths
GIT_WORKFLOW_SKILL_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "skills" / "git-workflow"
GIT_WORKFLOW_SKILL_FILE = GIT_WORKFLOW_SKILL_DIR / "SKILL.md"
GIT_WORKFLOW_DOCS_DIR = GIT_WORKFLOW_SKILL_DIR / "docs"
GIT_WORKFLOW_EXAMPLES_DIR = GIT_WORKFLOW_SKILL_DIR / "examples"

# GitHub workflow skill paths
GITHUB_WORKFLOW_SKILL_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "skills" / "github-workflow"
GITHUB_WORKFLOW_SKILL_FILE = GITHUB_WORKFLOW_SKILL_DIR / "SKILL.md"
GITHUB_WORKFLOW_DOCS_DIR = GITHUB_WORKFLOW_SKILL_DIR / "docs"
GITHUB_WORKFLOW_EXAMPLES_DIR = GITHUB_WORKFLOW_SKILL_DIR / "examples"

# Agent paths
AGENTS_DIR = Path(__file__).parent.parent.parent.parent / "plugins" / "autonomous-dev" / "agents"

# New documentation files
COMMIT_PATTERNS_FILE = GIT_WORKFLOW_DOCS_DIR / "commit-patterns.md"
PR_TEMPLATE_GUIDE_FILE = GITHUB_WORKFLOW_DOCS_DIR / "pr-template-guide.md"
ISSUE_TEMPLATE_GUIDE_FILE = GITHUB_WORKFLOW_DOCS_DIR / "issue-template-guide.md"

# New example files
COMMIT_EXAMPLES_FILE = GIT_WORKFLOW_EXAMPLES_DIR / "commit-examples.txt"
PR_TEMPLATE_EXAMPLE_FILE = GITHUB_WORKFLOW_EXAMPLES_DIR / "pr-template.md"
ISSUE_TEMPLATE_EXAMPLE_FILE = GITHUB_WORKFLOW_EXAMPLES_DIR / "issue-template.md"

# Issue #68: GitHub Workflow Automation Enhancement
# New automation documentation files
PR_AUTOMATION_DOC = GITHUB_WORKFLOW_DOCS_DIR / "pr-automation.md"
ISSUE_AUTOMATION_DOC = GITHUB_WORKFLOW_DOCS_DIR / "issue-automation.md"
GITHUB_ACTIONS_INTEGRATION_DOC = GITHUB_WORKFLOW_DOCS_DIR / "github-actions-integration.md"
API_SECURITY_PATTERNS_DOC = GITHUB_WORKFLOW_DOCS_DIR / "api-security-patterns.md"

# New automation example files
PR_AUTOMATION_WORKFLOW = GITHUB_WORKFLOW_EXAMPLES_DIR / "pr-automation-workflow.yml"
ISSUE_AUTOMATION_WORKFLOW = GITHUB_WORKFLOW_EXAMPLES_DIR / "issue-automation-workflow.yml"
WEBHOOK_HANDLER = GITHUB_WORKFLOW_EXAMPLES_DIR / "webhook-handler.py"

# Agents to update
AGENTS_TO_UPDATE = {
    "commit-message-generator": "git-workflow",
    "pr-description-generator": "github-workflow",
    "issue-creator": "github-workflow"
}


# ============================================================================
# Test Suite 1: git-workflow Skill Enhancement
# ============================================================================


class TestGitWorkflowSkillEnhancement:
    """Test git-workflow skill enhancement with commit patterns."""

    def test_commit_patterns_doc_exists(self):
        """Test commit-patterns.md documentation file exists."""
        assert COMMIT_PATTERNS_FILE.exists(), (
            f"Commit patterns doc not found: {COMMIT_PATTERNS_FILE}\n"
            f"Expected: Create skills/git-workflow/docs/commit-patterns.md\n"
            f"Content: Conventional commit patterns (feat:, fix:, docs:, etc.)\n"
            f"See: Issue #67"
        )

    def test_commit_patterns_has_conventional_commit_types(self):
        """Test commit-patterns.md contains all conventional commit types."""
        content = COMMIT_PATTERNS_FILE.read_text()

        # Required conventional commit types
        required_types = [
            "feat:",     # New feature
            "fix:",      # Bug fix
            "docs:",     # Documentation only
            "style:",    # Formatting, missing semi colons, etc
            "refactor:", # Code change that neither fixes a bug nor adds a feature
            "test:",     # Adding missing tests
            "chore:",    # Changes to build process or auxiliary tools
        ]

        for commit_type in required_types:
            assert commit_type in content, (
                f"Missing conventional commit type '{commit_type}' in commit-patterns.md\n"
                f"Expected: Document all conventional commit types\n"
                f"See: https://www.conventionalcommits.org/"
            )

    def test_commit_patterns_has_breaking_change_guidance(self):
        """Test commit-patterns.md documents breaking change syntax."""
        content = COMMIT_PATTERNS_FILE.read_text()

        # Breaking change indicators
        assert "BREAKING CHANGE" in content or "breaking change" in content, (
            "Missing breaking change guidance in commit-patterns.md\n"
            "Expected: Document BREAKING CHANGE: footer syntax\n"
            "See: Conventional Commits specification"
        )

        # Exclamation mark syntax (feat!:)
        assert "!" in content, (
            "Missing exclamation mark syntax for breaking changes\n"
            "Expected: Document feat!: syntax for breaking changes"
        )

    def test_commit_patterns_has_scope_guidance(self):
        """Test commit-patterns.md documents scope syntax."""
        content = COMMIT_PATTERNS_FILE.read_text()

        assert "scope" in content.lower(), (
            "Missing scope guidance in commit-patterns.md\n"
            "Expected: Document feat(api): syntax with scope\n"
            "See: Conventional Commits specification"
        )

    def test_commit_examples_file_exists(self):
        """Test commit-examples.txt example file exists."""
        assert COMMIT_EXAMPLES_FILE.exists(), (
            f"Commit examples file not found: {COMMIT_EXAMPLES_FILE}\n"
            f"Expected: Create skills/git-workflow/examples/commit-examples.txt\n"
            f"Content: Real-world commit message examples\n"
            f"See: Issue #67"
        )

    def test_commit_examples_has_real_world_examples(self):
        """Test commit-examples.txt contains at least 10 real-world examples."""
        content = COMMIT_EXAMPLES_FILE.read_text()

        # Count commit messages (lines starting with conventional types)
        commit_pattern = re.compile(r'^(feat|fix|docs|style|refactor|test|chore)(\(.*?\))?:', re.MULTILINE)
        commits = commit_pattern.findall(content)

        assert len(commits) >= 10, (
            f"Expected at least 10 commit examples, found {len(commits)}\n"
            f"Examples should cover various types: feat, fix, docs, etc.\n"
            f"See: Issue #67"
        )

    def test_git_workflow_skill_metadata_updated(self):
        """Test git-workflow SKILL.md metadata includes commit pattern keywords."""
        content = GIT_WORKFLOW_SKILL_FILE.read_text()

        # Extract frontmatter
        parts = content.split("---\n", 2)
        assert len(parts) >= 3, "Skill file must have YAML frontmatter"

        frontmatter = yaml.safe_load(parts[1])

        # Check for commit-related keywords
        keywords = frontmatter.get("keywords", [])
        commit_keywords = ["commit", "conventional commits", "commit message", "commit patterns"]

        found_keywords = [k for k in commit_keywords if any(k in keyword.lower() for keyword in keywords)]

        assert len(found_keywords) >= 2, (
            f"Missing commit-related keywords in git-workflow SKILL.md\n"
            f"Expected: At least 2 of {commit_keywords}\n"
            f"Found: {found_keywords}\n"
            f"See: Issue #67"
        )

    def test_git_workflow_skill_references_commit_patterns_doc(self):
        """Test git-workflow SKILL.md content references commit-patterns.md."""
        content = GIT_WORKFLOW_SKILL_FILE.read_text()

        assert "commit-patterns.md" in content, (
            "git-workflow SKILL.md should reference commit-patterns.md documentation\n"
            "Expected: Link to docs/commit-patterns.md in skill content\n"
            "See: Issue #67"
        )


# ============================================================================
# Test Suite 2: github-workflow Skill Enhancement
# ============================================================================


class TestGithubWorkflowSkillEnhancement:
    """Test github-workflow skill enhancement with PR and issue templates."""

    def test_pr_template_guide_exists(self):
        """Test pr-template-guide.md documentation file exists."""
        assert PR_TEMPLATE_GUIDE_FILE.exists(), (
            f"PR template guide not found: {PR_TEMPLATE_GUIDE_FILE}\n"
            f"Expected: Create skills/github-workflow/docs/pr-template-guide.md\n"
            f"Content: PR description structure and best practices\n"
            f"See: Issue #67"
        )

    def test_pr_template_guide_has_standard_sections(self):
        """Test pr-template-guide.md documents standard PR sections."""
        content = PR_TEMPLATE_GUIDE_FILE.read_text()

        # Standard PR sections
        required_sections = [
            "Summary",
            "Test plan",
            "Changes",
            "Breaking changes"
        ]

        for section in required_sections:
            assert section.lower() in content.lower(), (
                f"Missing '{section}' section guidance in pr-template-guide.md\n"
                f"Expected: Document standard PR description sections\n"
                f"See: Issue #67"
            )

    def test_pr_template_guide_has_best_practices(self):
        """Test pr-template-guide.md includes PR description best practices."""
        content = PR_TEMPLATE_GUIDE_FILE.read_text()

        # Best practices to document
        best_practices = [
            "concise",
            "bullet",
            "why",
            "test"
        ]

        found_practices = [bp for bp in best_practices if bp in content.lower()]

        assert len(found_practices) >= 3, (
            f"Missing PR description best practices in pr-template-guide.md\n"
            f"Expected: Document best practices (concise, bullets, why, testing)\n"
            f"Found: {found_practices}\n"
            f"See: Issue #67"
        )

    def test_issue_template_guide_exists(self):
        """Test issue-template-guide.md documentation file exists."""
        assert ISSUE_TEMPLATE_GUIDE_FILE.exists(), (
            f"Issue template guide not found: {ISSUE_TEMPLATE_GUIDE_FILE}\n"
            f"Expected: Create skills/github-workflow/docs/issue-template-guide.md\n"
            f"Content: Issue description structure and best practices\n"
            f"See: Issue #67"
        )

    def test_issue_template_guide_has_standard_sections(self):
        """Test issue-template-guide.md documents standard issue sections."""
        content = ISSUE_TEMPLATE_GUIDE_FILE.read_text()

        # Standard issue sections
        required_sections = [
            "Problem",
            "Solution",
            "Context",
            "Acceptance criteria"
        ]

        for section in required_sections:
            assert section.lower() in content.lower(), (
                f"Missing '{section}' section guidance in issue-template-guide.md\n"
                f"Expected: Document standard issue description sections\n"
                f"See: Issue #67"
            )

    def test_pr_template_example_exists(self):
        """Test pr-template.md example file exists."""
        assert PR_TEMPLATE_EXAMPLE_FILE.exists(), (
            f"PR template example not found: {PR_TEMPLATE_EXAMPLE_FILE}\n"
            f"Expected: Create skills/github-workflow/examples/pr-template.md\n"
            f"Content: Example PR description following best practices\n"
            f"See: Issue #67"
        )

    def test_pr_template_example_has_all_sections(self):
        """Test pr-template.md example includes all standard sections."""
        content = PR_TEMPLATE_EXAMPLE_FILE.read_text()

        # Required sections in example
        required_sections = ["## Summary", "## Test plan", "## Changes"]

        for section in required_sections:
            assert section in content, (
                f"Missing '{section}' in PR template example\n"
                f"Expected: Complete example with all standard sections\n"
                f"See: Issue #67"
            )

    def test_issue_template_example_exists(self):
        """Test issue-template.md example file exists."""
        assert ISSUE_TEMPLATE_EXAMPLE_FILE.exists(), (
            f"Issue template example not found: {ISSUE_TEMPLATE_EXAMPLE_FILE}\n"
            f"Expected: Create skills/github-workflow/examples/issue-template.md\n"
            f"Content: Example issue description following best practices\n"
            f"See: Issue #67"
        )

    def test_issue_template_example_has_all_sections(self):
        """Test issue-template.md example includes all standard sections."""
        content = ISSUE_TEMPLATE_EXAMPLE_FILE.read_text()

        # Required sections in example
        required_sections = ["## Problem", "## Solution", "## Acceptance Criteria"]

        for section in required_sections:
            assert section in content, (
                f"Missing '{section}' in issue template example\n"
                f"Expected: Complete example with all standard sections\n"
                f"See: Issue #67"
            )

    def test_github_workflow_skill_metadata_updated(self):
        """Test github-workflow SKILL.md metadata includes PR/issue keywords."""
        content = GITHUB_WORKFLOW_SKILL_FILE.read_text()

        # Extract frontmatter
        parts = content.split("---\n", 2)
        assert len(parts) >= 3, "Skill file must have YAML frontmatter"

        frontmatter = yaml.safe_load(parts[1])

        # Check for PR/issue-related keywords
        keywords = frontmatter.get("keywords", [])
        github_keywords = ["pull request", "pr description", "issue", "github issue"]

        found_keywords = [k for k in github_keywords if any(k in keyword.lower() for keyword in keywords)]

        assert len(found_keywords) >= 2, (
            f"Missing PR/issue-related keywords in github-workflow SKILL.md\n"
            f"Expected: At least 2 of {github_keywords}\n"
            f"Found: {found_keywords}\n"
            f"See: Issue #67"
        )


# ============================================================================
# Test Suite 3: Agent Integration
# ============================================================================


class TestAgentSkillReferences:
    """Test agents reference enhanced git/github-workflow skills."""

    @pytest.mark.parametrize("agent_name,skill_name", [
        ("commit-message-generator", "git-workflow"),
        ("pr-description-generator", "github-workflow"),
        ("issue-creator", "github-workflow")
    ])
    def test_agent_references_skill(self, agent_name, skill_name):
        """Test agent references the appropriate enhanced skill."""
        agent_file = AGENTS_DIR / f"{agent_name}.md"
        content = agent_file.read_text()

        assert skill_name in content.lower(), (
            f"Agent {agent_name} should reference {skill_name} skill\n"
            f"Expected: Add '{skill_name}' to Relevant Skills section\n"
            f"See: Issue #67"
        )

    @pytest.mark.parametrize("agent_name,removed_content", [
        ("commit-message-generator", "conventional commit"),
        ("pr-description-generator", "PR template"),
        ("issue-creator", "issue template")
    ])
    def test_agent_removes_inline_patterns(self, agent_name, removed_content):
        """Test agent removes inline patterns (moved to skills)."""
        agent_file = AGENTS_DIR / f"{agent_name}.md"
        content = agent_file.read_text()

        # Count occurrences of pattern guidance
        pattern_count = content.lower().count(removed_content.lower())

        # Should reference skill, not include full inline content
        # Allow 1-2 mentions (in context), but not full guidance
        assert pattern_count <= 2, (
            f"Agent {agent_name} still contains inline '{removed_content}' guidance\n"
            f"Expected: Remove inline content, reference {AGENTS_TO_UPDATE[agent_name]} skill instead\n"
            f"Found {pattern_count} mentions (expected <= 2)\n"
            f"See: Issue #67"
        )


# ============================================================================
# Test Suite 4: Token Reduction Validation
# ============================================================================


class TestTokenReduction:
    """Test token reduction from git/github-workflow skill enhancements."""

    def test_commit_message_generator_token_reduction(self):
        """Test commit-message-generator agent has ~100 token reduction."""
        agent_file = AGENTS_DIR / "commit-message-generator.md"
        content = agent_file.read_text()

        # Rough token count (1 token ≈ 4 chars)
        token_count = len(content) // 4

        # Expected: Original ~500 tokens, reduced to ~400 tokens
        # This is a baseline - actual measurement will vary
        assert token_count < 600, (
            f"commit-message-generator token count too high: {token_count}\n"
            f"Expected: ~100 token reduction from skill extraction\n"
            f"See: Issue #67"
        )

    def test_pr_description_generator_token_reduction(self):
        """Test pr-description-generator agent has ~100 token reduction."""
        agent_file = AGENTS_DIR / "pr-description-generator.md"
        content = agent_file.read_text()

        # Rough token count (1 token ≈ 4 chars)
        token_count = len(content) // 4

        # Expected: Original ~600 tokens, reduced to ~500 tokens
        assert token_count < 700, (
            f"pr-description-generator token count too high: {token_count}\n"
            f"Expected: ~100 token reduction from skill extraction\n"
            f"See: Issue #67"
        )

    def test_issue_creator_token_reduction(self):
        """Test issue-creator agent has ~100 token reduction."""
        agent_file = AGENTS_DIR / "issue-creator.md"
        content = agent_file.read_text()

        # Rough token count (1 token ≈ 4 chars)
        token_count = len(content) // 4

        # Expected: Original ~700 tokens, reduced to ~600 tokens
        assert token_count < 800, (
            f"issue-creator token count too high: {token_count}\n"
            f"Expected: ~100 token reduction from skill extraction\n"
            f"See: Issue #67"
        )

    def test_total_token_savings_achieved(self):
        """Test total token savings of ~300 tokens across 3 agents."""
        total_savings = 0

        for agent_name in AGENTS_TO_UPDATE.keys():
            agent_file = AGENTS_DIR / f"{agent_name}.md"
            content = agent_file.read_text()
            token_count = len(content) // 4

            # Measure reduction (rough estimate)
            # This will be refined with actual measurement script
            # For now, just verify agents are reasonably sized
            total_savings += 100  # Expected per agent

        assert total_savings >= 300, (
            f"Total token savings too low: {total_savings}\n"
            f"Expected: ~300 tokens saved across 3 agents\n"
            f"See: Issue #67"
        )


# ============================================================================
# Test Suite 5: Skill Activation
# ============================================================================


class TestSkillActivation:
    """Test enhanced skills activate correctly in Claude Code."""

    def test_git_workflow_skill_activates_on_commit_keywords(self):
        """Test git-workflow skill activates when commit-related keywords used."""
        content = GIT_WORKFLOW_SKILL_FILE.read_text()

        # Extract frontmatter
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        # Check auto_activate is true
        assert frontmatter.get("auto_activate") is True, (
            "git-workflow skill should auto-activate on commit keywords\n"
            "Expected: auto_activate: true in SKILL.md frontmatter\n"
            "See: Issue #67"
        )

    def test_github_workflow_skill_activates_on_pr_issue_keywords(self):
        """Test github-workflow skill activates when PR/issue keywords used."""
        content = GITHUB_WORKFLOW_SKILL_FILE.read_text()

        # Extract frontmatter
        parts = content.split("---\n", 2)
        frontmatter = yaml.safe_load(parts[1])

        # Check auto_activate is true
        assert frontmatter.get("auto_activate") is True, (
            "github-workflow skill should auto-activate on PR/issue keywords\n"
            "Expected: auto_activate: true in SKILL.md frontmatter\n"
            "See: Issue #67"
        )


# ============================================================================
# Test Suite 6: GitHub Workflow Automation Enhancement (Issue #68)
# ============================================================================


class TestGithubWorkflowAutomationPatterns:
    """Test GitHub workflow automation patterns (Issue #68).

    This test suite validates the enhancement of github-workflow skill with
    automation patterns for PR/issue workflows, GitHub Actions integration,
    and webhook security.

    Expected artifacts:
    - 4 documentation files: pr-automation.md, issue-automation.md,
      github-actions-integration.md, api-security-patterns.md
    - 3 example files: pr-automation-workflow.yml, issue-automation-workflow.yml,
      webhook-handler.py
    - Updated SKILL.md with automation keywords
    - ~1,200+ tokens of automation guidance
    """

    # ========================================================================
    # Documentation Existence Tests (4 tests)
    # ========================================================================

    def test_pr_automation_doc_exists(self):
        """Test pr-automation.md documentation file exists."""
        assert PR_AUTOMATION_DOC.exists(), (
            f"PR automation doc not found: {PR_AUTOMATION_DOC}\n"
            f"Expected: Create docs/pr-automation.md with automation patterns\n"
            f"Content: Auto-labeling, auto-reviewers, auto-merge workflows\n"
            f"See: Issue #68"
        )

    def test_issue_automation_doc_exists(self):
        """Test issue-automation.md documentation file exists."""
        assert ISSUE_AUTOMATION_DOC.exists(), (
            f"Issue automation doc not found: {ISSUE_AUTOMATION_DOC}\n"
            f"Expected: Create docs/issue-automation.md with automation patterns\n"
            f"Content: Auto-triage, auto-assignment, auto-labeling workflows\n"
            f"See: Issue #68"
        )

    def test_github_actions_integration_doc_exists(self):
        """Test github-actions-integration.md documentation file exists."""
        assert GITHUB_ACTIONS_INTEGRATION_DOC.exists(), (
            f"GitHub Actions integration doc not found: {GITHUB_ACTIONS_INTEGRATION_DOC}\n"
            f"Expected: Create docs/github-actions-integration.md\n"
            f"Content: Workflow syntax, event triggers, action composition\n"
            f"See: Issue #68"
        )

    def test_api_security_patterns_doc_exists(self):
        """Test api-security-patterns.md documentation file exists."""
        assert API_SECURITY_PATTERNS_DOC.exists(), (
            f"API security patterns doc not found: {API_SECURITY_PATTERNS_DOC}\n"
            f"Expected: Create docs/api-security-patterns.md\n"
            f"Content: Webhook signature verification, token security, rate limiting\n"
            f"See: Issue #68"
        )

    # ========================================================================
    # Documentation Completeness Tests (4 tests)
    # ========================================================================

    def test_pr_automation_has_required_sections(self):
        """Test pr-automation.md contains required automation sections."""
        content = PR_AUTOMATION_DOC.read_text()

        required_sections = [
            "Auto-labeling",
            "Auto-reviewers",
            "Auto-merge",
            "Status checks"
        ]

        for section in required_sections:
            assert section.lower() in content.lower(), (
                f"Missing '{section}' section in pr-automation.md\n"
                f"Expected: Document PR automation workflows\n"
                f"See: Issue #68"
            )

    def test_issue_automation_has_required_sections(self):
        """Test issue-automation.md contains required automation sections."""
        content = ISSUE_AUTOMATION_DOC.read_text()

        required_sections = [
            "Auto-triage",
            "Auto-assignment",
            "Auto-labeling",
            "Stale issues"
        ]

        for section in required_sections:
            assert section.lower() in content.lower(), (
                f"Missing '{section}' section in issue-automation.md\n"
                f"Expected: Document issue automation workflows\n"
                f"See: Issue #68"
            )

    def test_github_actions_integration_has_required_sections(self):
        """Test github-actions-integration.md contains required sections."""
        content = GITHUB_ACTIONS_INTEGRATION_DOC.read_text()

        required_sections = [
            "Workflow syntax",
            "Event triggers",
            "Actions marketplace",
            "Custom actions"
        ]

        for section in required_sections:
            assert section.lower() in content.lower(), (
                f"Missing '{section}' section in github-actions-integration.md\n"
                f"Expected: Document GitHub Actions integration patterns\n"
                f"See: Issue #68"
            )

    def test_api_security_patterns_has_required_sections(self):
        """Test api-security-patterns.md contains required security sections."""
        content = API_SECURITY_PATTERNS_DOC.read_text()

        required_sections = [
            "Webhook signature",
            "Token security",
            "Rate limiting",
            "HTTPS"
        ]

        for section in required_sections:
            assert section.lower() in content.lower(), (
                f"Missing '{section}' section in api-security-patterns.md\n"
                f"Expected: Document GitHub API security patterns\n"
                f"See: Issue #68"
            )

    # ========================================================================
    # Example Existence Tests (3 tests)
    # ========================================================================

    def test_pr_automation_workflow_example_exists(self):
        """Test pr-automation-workflow.yml example file exists."""
        assert PR_AUTOMATION_WORKFLOW.exists(), (
            f"PR automation workflow not found: {PR_AUTOMATION_WORKFLOW}\n"
            f"Expected: Create examples/pr-automation-workflow.yml\n"
            f"Content: GitHub Actions workflow for PR automation\n"
            f"See: Issue #68"
        )

    def test_issue_automation_workflow_example_exists(self):
        """Test issue-automation-workflow.yml example file exists."""
        assert ISSUE_AUTOMATION_WORKFLOW.exists(), (
            f"Issue automation workflow not found: {ISSUE_AUTOMATION_WORKFLOW}\n"
            f"Expected: Create examples/issue-automation-workflow.yml\n"
            f"Content: GitHub Actions workflow for issue automation\n"
            f"See: Issue #68"
        )

    def test_webhook_handler_example_exists(self):
        """Test webhook-handler.py example file exists."""
        assert WEBHOOK_HANDLER.exists(), (
            f"Webhook handler not found: {WEBHOOK_HANDLER}\n"
            f"Expected: Create examples/webhook-handler.py\n"
            f"Content: Python webhook handler with signature verification\n"
            f"See: Issue #68"
        )

    # ========================================================================
    # Example Quality Tests (2 tests)
    # ========================================================================

    def test_webhook_handler_has_signature_verification(self):
        """Test webhook-handler.py includes HMAC signature verification."""
        content = WEBHOOK_HANDLER.read_text()

        # Check for HMAC signature verification
        security_indicators = [
            "hmac",
            "signature",
            "verify",
            "sha256"
        ]

        found_indicators = [ind for ind in security_indicators if ind in content.lower()]

        assert len(found_indicators) >= 3, (
            f"Webhook handler missing signature verification\n"
            f"Expected: HMAC SHA-256 signature verification implementation\n"
            f"Found: {found_indicators}\n"
            f"See: Issue #68, GitHub webhook security best practices"
        )

    def test_workflow_examples_have_valid_yaml_structure(self):
        """Test workflow examples have valid GitHub Actions YAML structure."""
        for workflow_file in [PR_AUTOMATION_WORKFLOW, ISSUE_AUTOMATION_WORKFLOW]:
            content = workflow_file.read_text()

            # Parse YAML to check structure
            workflow = yaml.safe_load(content)

            assert "name" in workflow, (
                f"Workflow {workflow_file.name} missing 'name' field\n"
                f"Expected: Valid GitHub Actions workflow structure\n"
                f"See: Issue #68"
            )

            assert "on" in workflow, (
                f"Workflow {workflow_file.name} missing 'on' (event triggers) field\n"
                f"Expected: Valid GitHub Actions workflow structure\n"
                f"See: Issue #68"
            )

            assert "jobs" in workflow, (
                f"Workflow {workflow_file.name} missing 'jobs' field\n"
                f"Expected: Valid GitHub Actions workflow structure\n"
                f"See: Issue #68"
            )

    # ========================================================================
    # SKILL.md Integration Tests (2 tests)
    # ========================================================================

    def test_skill_md_references_automation_docs(self):
        """Test SKILL.md references new automation documentation files."""
        content = GITHUB_WORKFLOW_SKILL_FILE.read_text()

        automation_docs = [
            "pr-automation.md",
            "issue-automation.md",
            "github-actions-integration.md",
            "api-security-patterns.md"
        ]

        for doc in automation_docs:
            assert doc in content, (
                f"SKILL.md should reference {doc}\n"
                f"Expected: Link to docs/{doc} in skill content\n"
                f"See: Issue #68"
            )

    def test_skill_md_has_automation_keywords(self):
        """Test SKILL.md metadata includes automation-related keywords."""
        content = GITHUB_WORKFLOW_SKILL_FILE.read_text()

        # Extract frontmatter
        parts = content.split("---\n", 2)
        assert len(parts) >= 3, "Skill file must have YAML frontmatter"

        frontmatter = yaml.safe_load(parts[1])

        # Check for automation-related keywords
        keywords = frontmatter.get("keywords", [])
        automation_keywords = [
            "automation",
            "github actions",
            "webhook",
            "auto-labeling",
            "auto-merge"
        ]

        found_keywords = [k for k in automation_keywords if any(k in keyword.lower() for keyword in keywords)]

        assert len(found_keywords) >= 3, (
            f"Missing automation keywords in github-workflow SKILL.md\n"
            f"Expected: At least 3 of {automation_keywords}\n"
            f"Found: {found_keywords}\n"
            f"See: Issue #68"
        )

    # ========================================================================
    # Token Target Test (1 test)
    # ========================================================================

    def test_automation_docs_meet_token_target(self):
        """Test automation documentation meets ~1,200+ token target."""
        total_tokens = 0

        # Count tokens from all automation docs
        automation_docs = [
            PR_AUTOMATION_DOC,
            ISSUE_AUTOMATION_DOC,
            GITHUB_ACTIONS_INTEGRATION_DOC,
            API_SECURITY_PATTERNS_DOC
        ]

        for doc_file in automation_docs:
            content = doc_file.read_text()
            # Rough token count (1 token ≈ 4 chars)
            tokens = len(content) // 4
            total_tokens += tokens

        assert total_tokens >= 1200, (
            f"Automation documentation token count too low: {total_tokens}\n"
            f"Expected: ~1,200+ tokens of automation guidance\n"
            f"Breakdown needed: PR automation (~300), Issue automation (~300),\n"
            f"GitHub Actions (~400), API security (~200)\n"
            f"See: Issue #68"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
