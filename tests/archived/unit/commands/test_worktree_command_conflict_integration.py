"""
Unit tests for /worktree command conflict resolver integration

Tests the /worktree --merge command integration with conflict resolver:
1. Conflict detection in --merge flow
2. Automatic AI resolution triggering
3. Confidence threshold enforcement (0.8)
4. Security path mandatory manual review
5. Feature flag toggling
6. User prompts for manual review
7. Success/failure reporting

TDD Phase: RED - Tests written before implementation
Expected: All tests FAIL until worktree command integration is implemented

Issue: #193 - Wire conflict resolver into /worktree --merge and auto_git_workflow
"""

import json
import os
import pytest

# TDD red-phase tests - Issue #193 worktree_command not implemented
pytestmark = pytest.mark.skip(reason="TDD red-phase: Issue #193 worktree_command integration not implemented")
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

# Import modules under test (will fail initially - TDD red phase)
try:
    from autonomous_dev.lib.conflict_resolver import (
        ConflictResolutionResult,
        ResolutionSuggestion,
    )
    from autonomous_dev.lib.worktree_manager import MergeResult
except ImportError:
    pytest.skip("conflict_resolver.py or worktree_manager.py not implemented yet", allow_module_level=True)


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def tmp_project_dir(tmp_path: Path) -> Path:
    """Create temporary project directory with .claude and .git."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    git_dir = tmp_path / ".git"
    git_dir.mkdir(parents=True, exist_ok=True)

    # Save original directory
    original_dir = os.getcwd()
    os.chdir(tmp_path)

    yield tmp_path

    # Restore original directory
    os.chdir(original_dir)


@pytest.fixture
def feature_flags_file(tmp_project_dir: Path) -> Path:
    """Create feature_flags.json with conflict resolver enabled."""
    flags = {"conflict_resolver": {"enabled": True}}
    flags_file = tmp_project_dir / ".claude" / "feature_flags.json"
    flags_file.write_text(json.dumps(flags, indent=2))
    return flags_file


@pytest.fixture
def mock_api_key():
    """Mock Anthropic API key."""
    return "sk-ant-test-key-worktree"


# ============================================================================
# Worktree Command --merge Integration Tests
# ============================================================================

class TestWorktreeCommandMergeIntegration:
    """Test /worktree --merge command integration with conflict resolver."""

    @patch('autonomous_dev.lib.worktree_manager.merge_worktree')
    @patch('autonomous_dev.lib.conflict_resolver.resolve_conflicts')
    def test_merge_detects_conflicts_and_triggers_ai(self, mock_resolve, mock_merge,
                                                     tmp_project_dir, feature_flags_file, mock_api_key):
        """--merge should detect conflicts and automatically trigger AI resolution."""
        # Mock merge result with conflicts
        mock_merge.return_value = MergeResult(
            success=False,
            conflicts=['auth.py', 'config.py'],
            merged_files=[],
            error_message="Merge conflicts detected"
        )

        # Mock AI resolution
        mock_resolve.return_value = ConflictResolutionResult(
            success=True,
            file_path="auth.py",
            resolution=ResolutionSuggestion(
                resolved_content="resolved",
                confidence=0.9,
                reasoning="clear",
                tier_used=2
            )
        )

        # Execute worktree merge command
        from autonomous_dev.commands.worktree_command import execute_worktree_merge

        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': mock_api_key}):
            result = execute_worktree_merge('feature-auth', 'master', auto_resolve=True)

        # Should have detected conflicts
        assert mock_merge.called
        # Should have attempted AI resolution for each conflict
        assert mock_resolve.call_count >= 1

    @patch('autonomous_dev.lib.worktree_manager.merge_worktree')
    @patch('autonomous_dev.lib.conflict_resolver.resolve_conflicts')
    def test_high_confidence_auto_applies_resolution(self, mock_resolve, mock_merge,
                                                     tmp_project_dir, feature_flags_file, mock_api_key):
        """High confidence (>= 0.8) should auto-apply resolution without prompting."""
        # Mock merge with conflicts
        mock_merge.return_value = MergeResult(
            success=False,
            conflicts=['feature.py'],
            merged_files=[],
            error_message="Conflicts"
        )

        # Mock high confidence resolution
        mock_resolve.return_value = ConflictResolutionResult(
            success=True,
            file_path="feature.py",
            resolution=ResolutionSuggestion(
                resolved_content="auto resolved",
                confidence=0.9,
                reasoning="clear choice",
                tier_used=2
            ),
            fallback_to_manual=False
        )

        from autonomous_dev.commands.worktree_command import execute_worktree_merge

        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': mock_api_key}):
            result = execute_worktree_merge('feature-auth', 'master', auto_resolve=True)

        # Should auto-apply without user prompt
        assert result['auto_applied'] is True or result['success'] is True

    @patch('autonomous_dev.lib.worktree_manager.merge_worktree')
    @patch('autonomous_dev.lib.conflict_resolver.resolve_conflicts')
    @patch('builtins.input')
    def test_low_confidence_prompts_user(self, mock_input, mock_resolve, mock_merge,
                                        tmp_project_dir, feature_flags_file, mock_api_key):
        """Low confidence (< 0.8) should prompt user before applying."""
        # Mock merge with conflicts
        mock_merge.return_value = MergeResult(
            success=False,
            conflicts=['uncertain.py'],
            merged_files=[],
            error_message="Conflicts"
        )

        # Mock low confidence resolution
        mock_resolve.return_value = ConflictResolutionResult(
            success=True,
            file_path="uncertain.py",
            resolution=ResolutionSuggestion(
                resolved_content="uncertain resolution",
                confidence=0.6,
                reasoning="not sure",
                tier_used=2
            ),
            fallback_to_manual=True
        )

        # User accepts resolution
        mock_input.return_value = 'y'

        from autonomous_dev.commands.worktree_command import execute_worktree_merge

        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': mock_api_key}):
            result = execute_worktree_merge('feature-auth', 'master', auto_resolve=True)

        # Should have prompted user
        assert mock_input.called
        prompt_text = mock_input.call_args[0][0]
        assert 'confidence' in prompt_text.lower() or '0.6' in prompt_text

    @patch('autonomous_dev.lib.worktree_manager.merge_worktree')
    @patch('autonomous_dev.lib.conflict_resolver.resolve_conflicts')
    @patch('builtins.input')
    def test_security_files_always_prompt_user(self, mock_input, mock_resolve, mock_merge,
                                               tmp_project_dir, feature_flags_file, mock_api_key):
        """Security files should always prompt user, even with high confidence."""
        # Mock merge with security file conflict
        mock_merge.return_value = MergeResult(
            success=False,
            conflicts=['security_config.py'],
            merged_files=[],
            error_message="Conflicts"
        )

        # Mock HIGH confidence resolution (should still prompt)
        mock_resolve.return_value = ConflictResolutionResult(
            success=True,
            file_path="security_config.py",
            resolution=ResolutionSuggestion(
                resolved_content="security resolved",
                confidence=0.95,  # High confidence
                reasoning="clear",
                tier_used=2,
                warnings=["Security-sensitive file requires manual review"]
            ),
            fallback_to_manual=True  # Force manual review
        )

        # User accepts resolution
        mock_input.return_value = 'y'

        from autonomous_dev.commands.worktree_command import execute_worktree_merge

        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': mock_api_key}):
            result = execute_worktree_merge('feature-auth', 'master', auto_resolve=True)

        # Should have prompted user DESPITE high confidence
        assert mock_input.called
        prompt_text = mock_input.call_args[0][0]
        assert 'security' in prompt_text.lower() or 'manual review' in prompt_text.lower()

    @patch('autonomous_dev.lib.worktree_manager.merge_worktree')
    def test_no_conflicts_skips_ai_resolution(self, mock_merge, tmp_project_dir, feature_flags_file):
        """Successful merge with no conflicts should skip AI resolution."""
        # Mock successful merge
        mock_merge.return_value = MergeResult(
            success=True,
            conflicts=[],
            merged_files=['feature.py', 'test.py'],
            error_message=""
        )

        from autonomous_dev.commands.worktree_command import execute_worktree_merge

        with patch('autonomous_dev.lib.conflict_resolver.resolve_conflicts') as mock_resolve:
            result = execute_worktree_merge('feature-auth', 'master', auto_resolve=True)

        # Should NOT call AI resolver (no conflicts)
        mock_resolve.assert_not_called()
        assert result['success'] is True


# ============================================================================
# Feature Flag Toggling Tests
# ============================================================================

class TestWorktreeCommandFeatureFlagToggle:
    """Test feature flag toggling in /worktree command."""

    @patch('autonomous_dev.lib.worktree_manager.merge_worktree')
    @patch('autonomous_dev.lib.conflict_resolver.resolve_conflicts')
    def test_feature_disabled_skips_ai_resolution(self, mock_resolve, mock_merge, tmp_project_dir):
        """Feature disabled should skip AI resolution and report conflicts."""
        # Disable feature flag
        flags = {"conflict_resolver": {"enabled": False}}
        flags_file = tmp_project_dir / ".claude" / "feature_flags.json"
        flags_file.write_text(json.dumps(flags, indent=2))

        # Mock merge with conflicts
        mock_merge.return_value = MergeResult(
            success=False,
            conflicts=['auth.py'],
            merged_files=[],
            error_message="Conflicts"
        )

        from autonomous_dev.commands.worktree_command import execute_worktree_merge

        result = execute_worktree_merge('feature-auth', 'master', auto_resolve=True)

        # Should NOT call AI resolver
        mock_resolve.assert_not_called()
        # Should report conflicts
        assert len(result['conflicts']) > 0

    @patch('autonomous_dev.lib.worktree_manager.merge_worktree')
    @patch('autonomous_dev.lib.conflict_resolver.resolve_conflicts')
    def test_auto_resolve_flag_false_skips_ai(self, mock_resolve, mock_merge, tmp_project_dir, feature_flags_file):
        """auto_resolve=False should skip AI resolution even if feature enabled."""
        # Mock merge with conflicts
        mock_merge.return_value = MergeResult(
            success=False,
            conflicts=['auth.py'],
            merged_files=[],
            error_message="Conflicts"
        )

        from autonomous_dev.commands.worktree_command import execute_worktree_merge

        result = execute_worktree_merge('feature-auth', 'master', auto_resolve=False)

        # Should NOT call AI resolver (auto_resolve=False)
        mock_resolve.assert_not_called()


# ============================================================================
# User Prompt Tests
# ============================================================================

class TestWorktreeCommandUserPrompts:
    """Test user prompts for manual review in /worktree command."""

    @patch('autonomous_dev.lib.worktree_manager.merge_worktree')
    @patch('autonomous_dev.lib.conflict_resolver.resolve_conflicts')
    @patch('builtins.input')
    def test_user_accepts_resolution(self, mock_input, mock_resolve, mock_merge,
                                     tmp_project_dir, feature_flags_file, mock_api_key):
        """User accepting resolution should apply it."""
        mock_merge.return_value = MergeResult(
            success=False,
            conflicts=['test.py'],
            merged_files=[],
            error_message="Conflicts"
        )

        mock_resolve.return_value = ConflictResolutionResult(
            success=True,
            file_path="test.py",
            resolution=ResolutionSuggestion(
                resolved_content="resolved",
                confidence=0.7,
                reasoning="reasonable",
                tier_used=2
            ),
            fallback_to_manual=True
        )

        # User accepts
        mock_input.return_value = 'y'

        from autonomous_dev.commands.worktree_command import execute_worktree_merge

        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': mock_api_key}):
            with patch('autonomous_dev.lib.conflict_resolver.apply_resolution') as mock_apply:
                result = execute_worktree_merge('feature-auth', 'master', auto_resolve=True)

        # Should have applied resolution
        assert mock_apply.called

    @patch('autonomous_dev.lib.worktree_manager.merge_worktree')
    @patch('autonomous_dev.lib.conflict_resolver.resolve_conflicts')
    @patch('builtins.input')
    def test_user_rejects_resolution(self, mock_input, mock_resolve, mock_merge,
                                    tmp_project_dir, feature_flags_file, mock_api_key):
        """User rejecting resolution should leave conflict for manual resolution."""
        mock_merge.return_value = MergeResult(
            success=False,
            conflicts=['test.py'],
            merged_files=[],
            error_message="Conflicts"
        )

        mock_resolve.return_value = ConflictResolutionResult(
            success=True,
            file_path="test.py",
            resolution=ResolutionSuggestion(
                resolved_content="resolved",
                confidence=0.7,
                reasoning="reasonable",
                tier_used=2
            ),
            fallback_to_manual=True
        )

        # User rejects
        mock_input.return_value = 'n'

        from autonomous_dev.commands.worktree_command import execute_worktree_merge

        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': mock_api_key}):
            with patch('autonomous_dev.lib.conflict_resolver.apply_resolution') as mock_apply:
                result = execute_worktree_merge('feature-auth', 'master', auto_resolve=True)

        # Should NOT have applied resolution
        mock_apply.assert_not_called()
        # Should report manual resolution needed
        assert result['manual_review_required'] is True

    @patch('autonomous_dev.lib.worktree_manager.merge_worktree')
    @patch('autonomous_dev.lib.conflict_resolver.resolve_conflicts')
    @patch('builtins.input')
    def test_prompt_shows_confidence_and_reasoning(self, mock_input, mock_resolve, mock_merge,
                                                   tmp_project_dir, feature_flags_file, mock_api_key):
        """Prompt should show AI confidence and reasoning to user."""
        mock_merge.return_value = MergeResult(
            success=False,
            conflicts=['test.py'],
            merged_files=[],
            error_message="Conflicts"
        )

        mock_resolve.return_value = ConflictResolutionResult(
            success=True,
            file_path="test.py",
            resolution=ResolutionSuggestion(
                resolved_content="resolved",
                confidence=0.75,
                reasoning="Prefer newer implementation pattern",
                tier_used=2
            ),
            fallback_to_manual=True
        )

        mock_input.return_value = 'y'

        from autonomous_dev.commands.worktree_command import execute_worktree_merge

        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': mock_api_key}):
            result = execute_worktree_merge('feature-auth', 'master', auto_resolve=True)

        # Check prompt content
        prompt_text = mock_input.call_args[0][0]
        assert '0.75' in prompt_text or '75%' in prompt_text
        assert 'Prefer newer implementation pattern' in prompt_text or 'reasoning' in prompt_text.lower()


# ============================================================================
# Success/Failure Reporting Tests
# ============================================================================

class TestWorktreeCommandReporting:
    """Test success/failure reporting in /worktree command."""

    @patch('autonomous_dev.lib.worktree_manager.merge_worktree')
    @patch('autonomous_dev.lib.conflict_resolver.resolve_conflicts')
    def test_successful_auto_resolution_reported(self, mock_resolve, mock_merge,
                                                 tmp_project_dir, feature_flags_file, mock_api_key):
        """Successful auto-resolution should be clearly reported."""
        mock_merge.return_value = MergeResult(
            success=False,
            conflicts=['test.py'],
            merged_files=[],
            error_message="Conflicts"
        )

        mock_resolve.return_value = ConflictResolutionResult(
            success=True,
            file_path="test.py",
            resolution=ResolutionSuggestion(
                resolved_content="resolved",
                confidence=0.9,
                reasoning="clear",
                tier_used=2
            ),
            fallback_to_manual=False
        )

        from autonomous_dev.commands.worktree_command import execute_worktree_merge

        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': mock_api_key}):
            result = execute_worktree_merge('feature-auth', 'master', auto_resolve=True)

        # Check success reporting
        assert result['success'] is True
        assert 'auto_resolved' in result or 'auto_applied' in result
        assert result['conflicts_resolved'] >= 1

    @patch('autonomous_dev.lib.worktree_manager.merge_worktree')
    @patch('autonomous_dev.lib.conflict_resolver.resolve_conflicts')
    def test_failed_resolution_reported(self, mock_resolve, mock_merge,
                                       tmp_project_dir, feature_flags_file, mock_api_key):
        """Failed resolution should be clearly reported with manual steps."""
        mock_merge.return_value = MergeResult(
            success=False,
            conflicts=['complex.py'],
            merged_files=[],
            error_message="Conflicts"
        )

        mock_resolve.return_value = ConflictResolutionResult(
            success=False,
            file_path="complex.py",
            error_message="Too complex for AI",
            fallback_to_manual=True
        )

        from autonomous_dev.commands.worktree_command import execute_worktree_merge

        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': mock_api_key}):
            result = execute_worktree_merge('feature-auth', 'master', auto_resolve=True)

        # Check failure reporting
        assert result['success'] is False
        assert result['manual_review_required'] is True
        assert 'conflicts' in result
        assert len(result['conflicts']) > 0

    @patch('autonomous_dev.lib.worktree_manager.merge_worktree')
    @patch('autonomous_dev.lib.conflict_resolver.resolve_conflicts')
    def test_partial_resolution_reported(self, mock_resolve, mock_merge,
                                        tmp_project_dir, feature_flags_file, mock_api_key):
        """Partial resolution (some conflicts resolved, some failed) should be reported."""
        mock_merge.return_value = MergeResult(
            success=False,
            conflicts=['file1.py', 'file2.py', 'file3.py'],
            merged_files=[],
            error_message="Conflicts"
        )

        # Mock: First two succeed, third fails
        mock_resolve.side_effect = [
            ConflictResolutionResult(
                success=True,
                file_path="file1.py",
                resolution=ResolutionSuggestion(
                    resolved_content="resolved",
                    confidence=0.9,
                    reasoning="clear",
                    tier_used=2
                ),
                fallback_to_manual=False
            ),
            ConflictResolutionResult(
                success=True,
                file_path="file2.py",
                resolution=ResolutionSuggestion(
                    resolved_content="resolved",
                    confidence=0.85,
                    reasoning="clear",
                    tier_used=2
                ),
                fallback_to_manual=False
            ),
            ConflictResolutionResult(
                success=False,
                file_path="file3.py",
                error_message="Failed",
                fallback_to_manual=True
            ),
        ]

        from autonomous_dev.commands.worktree_command import execute_worktree_merge

        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': mock_api_key}):
            result = execute_worktree_merge('feature-auth', 'master', auto_resolve=True)

        # Check partial resolution reporting
        assert result['conflicts_resolved'] == 2
        assert result['conflicts_remaining'] == 1
        assert result['success'] is False  # Not fully successful
        assert result['manual_review_required'] is True


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
