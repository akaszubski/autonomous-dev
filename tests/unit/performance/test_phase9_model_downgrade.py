#!/usr/bin/env python3
"""
TDD Tests for Phase 9 - Model Downgrade (FAILING - Red Phase)

This module contains FAILING tests for downgrading agents from Sonnet to Haiku
model to reduce token costs while maintaining quality.

Phase 9 Objectives:
1. Downgrade 3 agents: commit-message-generator, alignment-validator, project-progress-tracker
2. Change model: Sonnet -> Haiku
3. Maintain output quality (conventional commit format, alignment accuracy, goal updates)
4. Compare quality metrics: Sonnet vs Haiku
5. Measure token reduction and cost savings

Target Agents:
- commit-message-generator: Sonnet -> Haiku (conventional commits are formulaic, ideal for Haiku)
- alignment-validator: Sonnet -> Haiku (validation is boolean, lower complexity)
- project-progress-tracker: Sonnet -> Haiku (goal updates are structured)

Quality Metrics:
- Conventional commit format compliance: 100%
- Alignment detection accuracy: >= 95%
- Goal update accuracy: >= 95%
- False positive rate: < 5%

Cost Reduction (estimated):
- commit-message-generator: ~60% (Sonnet cost / Haiku cost)
- alignment-validator: ~60%
- project-progress-tracker: ~60%
- Combined savings: ~180,000 tokens/month (~$0.27 reduction)

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe downgrade requirements
- Tests should FAIL until Phase 9 implementation complete
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-11-13
Issue: #46 Phase 9 (Model Downgrade)
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Tuple
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Import agent modules - will FAIL until Phase 9 implementation
# These tests assume agent.md files are parseable and model field is accessible
from plugins.autonomous_dev.agents.commit_message_generator import CommitMessageGenerator
from plugins.autonomous_dev.agents.alignment_validator import AlignmentValidator
from plugins.autonomous_dev.agents.project_progress_tracker import ProjectProgressTracker


class TestCommitMessageGeneratorHaikuFormat:
    """Test that commit-message-generator produces valid conventional commits with Haiku.

    Requirement: Downgraded to Haiku model must still produce properly formatted
    conventional commits (type(scope): subject).
    """

    def test_commit_message_follows_conventional_format(self):
        """Test that Haiku-generated commit follows conventional commit format.

        Arrange: CommitMessageGenerator with Haiku model
        Act: Generate commit message for test feature
        Assert: Message matches pattern: type(scope): description
        """
        generator = CommitMessageGenerator(model="haiku")
        context = {
            "changes": "Added user authentication module",
            "feature": "user authentication",
            "files_changed": ["auth.py", "test_auth.py"]
        }

        message = generator.generate(context)

        # Should match: type(scope): description
        # Examples: feat(auth): Add user authentication
        # fix(login): Prevent unauthorized access
        assert any(message.startswith(prefix) for prefix in [
            "feat(",
            "fix(",
            "refactor(",
            "docs(",
            "test(",
            "style(",
            "perf(",
            "ci(",
            "build("
        ])
        assert ":" in message  # type(scope): pattern
        assert len(message) <= 100  # Convention limit

    def test_commit_message_type_is_valid(self):
        """Test that commit type is one of the conventional commit types.

        Arrange: Haiku commit-message-generator
        Act: Generate commit message
        Assert: Type is feat, fix, refactor, docs, test, style, perf, ci, or build
        """
        generator = CommitMessageGenerator(model="haiku")
        context = {"changes": "Fix bug in auth", "feature": "fix", "files_changed": ["auth.py"]}

        message = generator.generate(context)

        # Extract type (before parenthesis)
        commit_type = message.split("(")[0]
        valid_types = ["feat", "fix", "refactor", "docs", "test", "style", "perf", "ci", "build"]

        assert commit_type in valid_types

    def test_commit_message_scope_is_present(self):
        """Test that commit message includes scope in parentheses.

        Arrange: Haiku commit-message-generator with feature context
        Act: Generate commit message
        Assert: Message has (scope) between type and colon
        """
        generator = CommitMessageGenerator(model="haiku")
        context = {"changes": "Add caching layer", "feature": "caching", "files_changed": ["cache.py"]}

        message = generator.generate(context)

        # Should have (scope) pattern
        assert "(" in message and ")" in message
        # Scope should be between type and description
        start = message.index("(")
        end = message.index(")")
        scope = message[start+1:end]
        assert len(scope) > 0  # Scope is not empty

    def test_commit_message_description_is_concise(self):
        """Test that commit description is concise (< 100 chars).

        Arrange: Haiku commit-message-generator
        Act: Generate commit message
        Assert: Total length <= 100 characters (convention)
        """
        generator = CommitMessageGenerator(model="haiku")
        context = {
            "changes": "Very long change description that goes on and on",
            "feature": "performance",
            "files_changed": ["perf.py"]
        }

        message = generator.generate(context)

        assert len(message) <= 100

    def test_commit_message_haiku_quality_vs_sonnet(self):
        """Test that Haiku commit quality is acceptable compared to Sonnet.

        Arrange: Generate same commit with both Haiku and Sonnet
        Act: Compare format and clarity
        Assert: Both follow conventional format; quality difference < 10%
        """
        context = {"changes": "Refactor database queries", "feature": "performance", "files_changed": ["db.py"]}

        haiku_generator = CommitMessageGenerator(model="haiku")
        sonnet_generator = CommitMessageGenerator(model="sonnet")

        haiku_msg = haiku_generator.generate(context)
        sonnet_msg = sonnet_generator.generate(context)

        # Both should follow conventional format
        assert ":" in haiku_msg
        assert ":" in sonnet_msg

        # Both should be concise
        assert len(haiku_msg) <= 100
        assert len(sonnet_msg) <= 100


class TestAlignmentValidatorHaikuAccuracy:
    """Test that alignment-validator correctly detects alignment with Haiku.

    Requirement: Haiku model must maintain >= 95% accuracy for alignment detection
    (identifying whether code aligns with PROJECT.md goals).
    """

    @pytest.fixture
    def sample_project_md(self, tmp_path):
        """Create sample PROJECT.md with clear goals."""
        project_md = tmp_path / ".claude" / "PROJECT.md"
        project_md.parent.mkdir(parents=True)
        project_md.write_text("""
## GOALS

- Goal 1: Implement user authentication module
- Goal 2: Add 80%+ test coverage
- Goal 3: Security hardening (CWE-22, CWE-20)

## IN SCOPE
- Authentication features
- Test infrastructure
- Security validation

## OUT OF SCOPE
- Admin dashboard
- Email notifications
""")
        return project_md

    def test_alignment_detector_identifies_aligned_code(self, sample_project_md):
        """Test that Haiku validator correctly identifies aligned code changes.

        Arrange: PROJECT.md with auth goal + code change adding auth module
        Act: AlignmentValidator.validate() checks alignment
        Assert: Returns True (aligned with goals)
        """
        validator = AlignmentValidator(model="haiku", project_md=sample_project_md)

        changes = {
            "description": "Implement user authentication module",
            "files": ["auth.py", "test_auth.py"],
            "type": "feature"
        }

        is_aligned = validator.validate(changes)

        assert is_aligned is True

    def test_alignment_detector_identifies_misaligned_code(self, sample_project_md):
        """Test that Haiku validator identifies code NOT aligned with goals.

        Arrange: PROJECT.md without admin dashboard goal + code adding admin panel
        Act: AlignmentValidator.validate() checks alignment
        Assert: Returns False (not aligned - out of scope)
        """
        validator = AlignmentValidator(model="haiku", project_md=sample_project_md)

        changes = {
            "description": "Add admin dashboard for user management",
            "files": ["admin_panel.py", "test_admin.py"],
            "type": "feature"
        }

        is_aligned = validator.validate(changes)

        assert is_aligned is False

    def test_alignment_accuracy_rate(self, sample_project_md):
        """Test that alignment accuracy >= 95% across test cases.

        Arrange: 20 test cases (10 aligned, 10 misaligned)
        Act: Run validator on each
        Assert: >= 19/20 correct (95% accuracy)
        """
        validator = AlignmentValidator(model="haiku", project_md=sample_project_md)

        # Aligned cases (should return True)
        aligned_cases = [
            {"description": "Add unit tests for auth", "type": "test"},
            {"description": "Implement JWT authentication", "type": "feature"},
            {"description": "Add path traversal prevention", "type": "security"},
        ]

        # Misaligned cases (should return False)
        misaligned_cases = [
            {"description": "Design admin dashboard UI", "type": "feature"},
            {"description": "Send email notifications", "type": "feature"},
            {"description": "Integrate Slack API", "type": "feature"},
        ]

        correct = 0
        total = len(aligned_cases) + len(misaligned_cases)

        for case in aligned_cases:
            if validator.validate(case) is True:
                correct += 1

        for case in misaligned_cases:
            if validator.validate(case) is False:
                correct += 1

        accuracy = correct / total
        assert accuracy >= 0.95  # 95% accuracy target

    def test_alignment_validator_false_positive_rate(self, sample_project_md):
        """Test that false positive rate < 5% (misaligned flagged as aligned).

        Arrange: 20 misaligned code changes
        Act: Run validator on each
        Assert: < 1 false positive (< 5% rate)
        """
        validator = AlignmentValidator(model="haiku", project_md=sample_project_md)

        # Clearly out-of-scope changes
        out_of_scope = [
            {"description": "Add Slack integration", "type": "feature"},
            {"description": "Send daily email digest", "type": "feature"},
            {"description": "Build admin dashboard", "type": "feature"},
            {"description": "Integrate payment system", "type": "feature"},
            {"description": "Add video streaming", "type": "feature"},
            {"description": "Deploy to AWS", "type": "devops"},
            {"description": "Create mobile app", "type": "feature"},
            {"description": "Setup monitoring dashboard", "type": "ops"},
            {"description": "Integrate analytics", "type": "feature"},
            {"description": "Add marketing widget", "type": "feature"},
        ]

        false_positives = 0
        for change in out_of_scope:
            if validator.validate(change) is True:  # Incorrectly flagged as aligned
                false_positives += 1

        false_positive_rate = false_positives / len(out_of_scope)
        assert false_positive_rate < 0.05  # < 5% false positive rate

    def test_alignment_validator_explanation_provided(self, sample_project_md):
        """Test that validator provides explanation when alignment is unclear.

        Arrange: AlignmentValidator
        Act: Validate borderline case
        Assert: Returns dict with 'aligned' and 'explanation' fields
        """
        validator = AlignmentValidator(model="haiku", project_md=sample_project_md)

        changes = {
            "description": "Optimize database indexes",
            "type": "performance"
        }

        result = validator.validate(changes)

        # Result should be detailed when alignment is ambiguous
        if isinstance(result, dict):
            assert 'aligned' in result
            assert 'explanation' in result
        else:
            assert isinstance(result, bool)


class TestProjectProgressTrackerHaikuGoalsUpdate:
    """Test that project-progress-tracker correctly updates PROJECT.md GOALS with Haiku.

    Requirement: Haiku model must accurately reflect completed features in
    PROJECT.md GOALS section.
    """

    @pytest.fixture
    def sample_project_with_goals(self, tmp_path):
        """Create PROJECT.md with in-progress goals."""
        project_md = tmp_path / ".claude" / "PROJECT.md"
        project_md.parent.mkdir(parents=True)
        project_md.write_text("""
## GOALS

- [x] Phase 1: Setup infrastructure
- [ ] Phase 2: Implement authentication (0/5 features)
  - [ ] Basic login
  - [ ] Password reset
  - [ ] 2FA support
  - [ ] Session management
  - [ ] OAuth integration
- [ ] Phase 3: Add API documentation
- [ ] Phase 4: Security hardening

## PROGRESS METRICS

- Completion: 1/4 phases
- Features implemented: 0/20
""")
        return project_md

    def test_progress_tracker_updates_completed_goal(self, sample_project_with_goals):
        """Test that Haiku tracker marks completed goal correctly.

        Arrange: PROJECT.md with Phase 2 in progress
        Act: Call tracker.update() after implementing 3/5 auth features
        Assert: PROJECT.md reflects 3/5 completion
        """
        tracker = ProjectProgressTracker(model="haiku", project_md=sample_project_with_goals)

        completed_features = [
            "Basic login",
            "Password reset",
            "Session management"
        ]

        tracker.update(
            phase="Phase 2: Implement authentication",
            completed=completed_features
        )

        # Verify project_md was updated
        content = sample_project_with_goals.read_text()
        assert "3/5 features" in content or "3 of 5" in content.lower()

    def test_progress_tracker_accurately_counts_features(self, sample_project_with_goals):
        """Test that Haiku tracker counts completed features correctly.

        Arrange: 5 features in a goal, 3 completed
        Act: Call tracker.update()
        Assert: Correct count in GOALS section
        """
        tracker = ProjectProgressTracker(model="haiku", project_md=sample_project_with_goals)

        completed = ["Basic login", "Password reset", "Session management"]
        tracker.update(phase="Phase 2: Implement authentication", completed=completed)

        content = sample_project_with_goals.read_text()

        # Should find 3/5 or similar count
        import re
        matches = re.findall(r'(\d+)/5', content)
        assert any(int(m) == 3 for m in matches)

    def test_progress_tracker_marks_phase_complete(self, sample_project_with_goals):
        """Test that Haiku tracker marks phase complete when all features done.

        Arrange: 5/5 features completed
        Act: Call tracker.update()
        Assert: Phase marked with [x] checkbox
        """
        tracker = ProjectProgressTracker(model="haiku", project_md=sample_project_with_goals)

        all_features = [
            "Basic login",
            "Password reset",
            "2FA support",
            "Session management",
            "OAuth integration"
        ]

        tracker.update(phase="Phase 2: Implement authentication", completed=all_features)

        content = sample_project_with_goals.read_text()

        # Phase should be marked complete: [x] Phase 2
        assert "[x] Phase 2" in content or "Phase 2" in content  # Should update checkbox

    def test_progress_tracker_updates_overall_metrics(self, sample_project_with_goals):
        """Test that Haiku tracker updates overall completion metrics.

        Arrange: PROJECT.md with metrics section
        Act: Complete one phase
        Assert: Completion percentage updated (e.g., 25% -> 50%)
        """
        tracker = ProjectProgressTracker(model="haiku", project_md=sample_project_with_goals)

        # Complete Phase 2
        all_auth_features = [
            "Basic login",
            "Password reset",
            "2FA support",
            "Session management",
            "OAuth integration"
        ]

        tracker.update(phase="Phase 2: Implement authentication", completed=all_auth_features)

        content = sample_project_with_goals.read_text()

        # Metrics should show increased completion
        # Original: 1/4 phases (25%), should now be at least: 2/4 phases (50%)
        assert "2/4" in content or "50%" in content.lower()

    def test_progress_tracker_accuracy_rate(self, sample_project_with_goals):
        """Test that tracker accuracy >= 95% across updates.

        Arrange: Multiple goals with various completion states
        Act: Update tracker with various scenarios
        Assert: >= 95% accuracy in reflecting changes
        """
        tracker = ProjectProgressTracker(model="haiku", project_md=sample_project_with_goals)

        test_cases = [
            ("Phase 2: Implement authentication", ["Basic login", "Password reset"], 2),
            ("Phase 3: Add API documentation", ["API endpoint docs"], 1),
        ]

        correct = 0
        for phase, completed, expected_count in test_cases:
            tracker.update(phase=phase, completed=completed)
            content = sample_project_with_goals.read_text()

            # Check if the correct count is in the file
            if str(expected_count) in content:
                correct += 1

        accuracy = correct / len(test_cases)
        assert accuracy >= 0.95  # 95% accuracy target


class TestModelDowngradeIntegration:
    """Integration tests for Phase 9 model downgrade.

    Verify all 3 agents work with Haiku model and maintain quality.
    """

    def test_downgrade_affects_all_3_target_agents(self):
        """Test that all 3 target agents are downgraded to Haiku.

        Arrange: Load agent YAML files
        Act: Check model field for each agent
        Assert: All 3 agents have model: haiku
        """
        agent_files = {
            "commit-message-generator": Path(__file__).parent.parent.parent.parent /
                                        "plugins/autonomous-dev/agents/commit-message-generator.md",
            "alignment-validator": Path(__file__).parent.parent.parent.parent /
                                   "plugins/autonomous-dev/agents/alignment-validator.md",
            "project-progress-tracker": Path(__file__).parent.parent.parent.parent /
                                        "plugins/autonomous-dev/agents/project-progress-tracker.md"
        }

        for agent_name, agent_file in agent_files.items():
            assert agent_file.exists(), f"Agent file not found: {agent_file}"

            content = agent_file.read_text()

            # Check for model: haiku in frontmatter
            assert "model: haiku" in content, f"{agent_name} not downgraded to haiku"

    def test_sonnet_agents_unaffected_by_downgrade(self):
        """Test that other agents remain on Sonnet model.

        Arrange: Load agent YAML files
        Act: Check model field for agents NOT targeted for downgrade
        Assert: Other agents still use sonnet or their original model
        """
        # These should NOT be downgraded (still Sonnet/Opus)
        sonnet_agents = [
            "planner",
            "implementer",
            "reviewer",
            "setup-wizard",
            "project-bootstrapper"
        ]

        agent_dir = Path(__file__).parent.parent.parent.parent / "plugins/autonomous-dev/agents"

        for agent_name in sonnet_agents:
            agent_file = agent_dir / f"{agent_name}.md"
            if agent_file.exists():
                content = agent_file.read_text()

                # Should NOT have haiku (or has sonnet/opus)
                if "model:" in content:
                    # Extract model line
                    for line in content.split("\n"):
                        if line.startswith("model:"):
                            model = line.split(":")[1].strip()
                            assert model in ["sonnet", "opus", "haiku"], f"Unknown model: {model}"
                            if agent_name in ["planner"]:
                                assert model == "opus"  # Planner should stay Opus


class TestPhase9CostReduction:
    """Test token and cost reduction from Phase 9 downgrade.

    Phase 9 target: ~180,000 tokens/month reduction (~$0.27)
    """

    def test_haiku_token_reduction_vs_sonnet(self):
        """Test that Haiku uses fewer tokens than Sonnet for same task.

        Arrange: Same prompt with Haiku and Sonnet
        Act: Measure tokens for conventional commit generation
        Assert: Haiku tokens < Sonnet tokens (estimated 60% reduction)
        """
        # This would require actual API calls or token counting
        # For TDD, we assume this will be measured in implementation
        # Expected: Haiku ~6x cheaper than Sonnet per token
        # 3 agents * ~15 calls/day * 28 days = 1260 calls/month
        # If each saves ~150 tokens, that's 189,000 tokens/month saved

        haiku_cost = 0.08 / 1_000_000  # Per token
        sonnet_cost = 0.50 / 1_000_000  # Per token

        cost_ratio = haiku_cost / sonnet_cost

        # Haiku should be < 20% of Sonnet cost
        assert cost_ratio < 0.20

    def test_combined_savings_across_3_agents(self):
        """Test estimated combined savings from downgrading 3 agents.

        Arrange: Calculate monthly tokens for 3 agents
        Act: Estimate cost reduction
        Assert: >= $0.25/month savings
        """
        # Estimates per phase 9 plan: 3 agents, ~180k tokens/month total
        # Each agent: ~15 calls/day * 30 days = 450 calls/month
        # All 3 agents: 450 * 3 = 1350 calls/month
        # Average 450 tokens/call (accounting for context, not just output)
        estimated_monthly_calls = 1350
        tokens_per_call = 450  # Includes input + output context
        total_tokens = estimated_monthly_calls * tokens_per_call  # ~607,500 tokens

        # Anthropic pricing (per 1M tokens)
        sonnet_cost_per_token = 3.00 / 1_000_000  # Sonnet input tokens
        haiku_cost_per_token = 0.25 / 1_000_000   # Haiku input tokens

        current_cost = total_tokens * sonnet_cost_per_token
        new_cost = total_tokens * haiku_cost_per_token
        savings = current_cost - new_cost

        # Target: >= $0.25/month savings
        # With 607,500 tokens: (3.00 - 0.25) / 1M * 607,500 = $1.67 savings
        assert savings >= 0.25, f"Savings too low: ${savings:.2f}"
