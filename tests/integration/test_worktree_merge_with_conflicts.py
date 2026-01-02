"""
Integration tests for worktree merge with conflict resolution

Tests the complete workflow:
1. Create worktree with feature branch
2. Make conflicting changes in worktree and main branch
3. Attempt merge that triggers conflicts
4. AI conflict resolver automatically resolves
5. Git automation commits if confidence >= 0.8
6. Manual review required for security paths or low confidence

TDD Phase: RED - Tests written before implementation
Expected: All tests FAIL until integration is implemented

Issue: #193 - Wire conflict resolver into /worktree --merge and auto_git_workflow
"""

import json
import os
import pytest
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Import modules under test (will fail initially - TDD red phase)
try:
    from autonomous_dev.lib.worktree_manager import (
        create_worktree,
        merge_worktree,
        list_worktrees,
        delete_worktree,
    )
    from autonomous_dev.lib.conflict_resolver import (
        resolve_conflicts,
        ConflictResolutionResult,
        ResolutionSuggestion,
    )
except ImportError:
    pytest.skip("worktree_manager.py or conflict_resolver.py not implemented yet", allow_module_level=True)


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def git_repo(tmp_path: Path):
    """Create a real git repository for integration testing."""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()

    # Save original directory
    original_dir = os.getcwd()
    os.chdir(repo_dir)

    # Initialize git repo
    subprocess.run(['git', 'init'], check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], check=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], check=True)

    # Create initial commit
    (repo_dir / "README.md").write_text("# Test Repo\n")
    subprocess.run(['git', 'add', 'README.md'], check=True)
    subprocess.run(['git', 'commit', '-m', 'Initial commit'], check=True)

    # Create .claude directory
    (repo_dir / ".claude").mkdir()

    yield repo_dir

    # Restore original directory
    os.chdir(original_dir)


@pytest.fixture
def feature_flags_enabled(git_repo: Path):
    """Create feature_flags.json with conflict resolver enabled."""
    flags = {
        "conflict_resolver": {"enabled": True},
        "auto_git_workflow": {"enabled": True}
    }
    flags_file = git_repo / ".claude" / "feature_flags.json"
    flags_file.write_text(json.dumps(flags, indent=2))
    return flags_file


@pytest.fixture
def mock_api_key():
    """Mock Anthropic API key."""
    return "sk-ant-test-key-integration"


# ============================================================================
# Full Workflow Integration Tests
# ============================================================================

class TestWorktreeMergeWithConflictResolution:
    """Test complete worktree merge workflow with conflict resolution."""

    def test_create_worktree_make_conflicting_changes_merge(self, git_repo, feature_flags_enabled):
        """
        Complete workflow:
        1. Create worktree for feature
        2. Make conflicting changes in worktree and main
        3. Merge worktree (should detect conflicts)
        """
        os.chdir(git_repo)

        # Step 1: Create worktree
        success, worktree_path = create_worktree('feature-conflict-test', 'master')
        assert success is True
        assert worktree_path.exists()

        # Step 2: Make changes in main branch
        main_file = git_repo / "auth.py"
        main_file.write_text("def auth():\n    return 'bcrypt'\n")
        subprocess.run(['git', 'add', 'auth.py'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Add bcrypt auth'], check=True)

        # Step 3: Make conflicting changes in worktree
        worktree_file = worktree_path / "auth.py"
        worktree_file.write_text("def auth():\n    return 'argon2'\n")
        subprocess.run(['git', '-C', str(worktree_path), 'add', 'auth.py'], check=True)
        subprocess.run(['git', '-C', str(worktree_path), 'commit', '-m', 'Add argon2 auth'], check=True)

        # Step 4: Merge worktree (should detect conflicts)
        result = merge_worktree('feature-conflict-test', 'master')

        # Should detect conflicts
        assert result.success is False or len(result.conflicts) > 0
        assert 'auth.py' in str(result.conflicts)

    @patch('autonomous_dev.lib.conflict_resolver.Anthropic')
    def test_ai_resolution_auto_applies_high_confidence(self, mock_anthropic, git_repo,
                                                        feature_flags_enabled, mock_api_key):
        """AI resolution with high confidence should auto-apply."""
        os.chdir(git_repo)

        # Setup: Create conflict
        success, worktree_path = create_worktree('feature-high-conf', 'master')
        main_file = git_repo / "config.py"
        main_file.write_text("SETTING = 'value1'\n")
        subprocess.run(['git', 'add', 'config.py'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Set value1'], check=True)

        worktree_file = worktree_path / "config.py"
        worktree_file.write_text("SETTING = 'value2'\n")
        subprocess.run(['git', '-C', str(worktree_path), 'add', 'config.py'], check=True)
        subprocess.run(['git', '-C', str(worktree_path), 'commit', '-m', 'Set value2'], check=True)

        # Mock AI response with high confidence
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = Mock(
            content=[Mock(text='{"resolved_content": "SETTING = \'value2\'", "confidence": 0.9, "reasoning": "Use newer value"}')]
        )

        # Merge with auto-resolve enabled
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': mock_api_key}):
            result = merge_worktree('feature-high-conf', 'master', auto_resolve=True)

        # Should have attempted resolution
        assert mock_client.messages.create.called
        # Should auto-apply with high confidence
        assert result.success is True or result.resolution_applied

    @patch('autonomous_dev.lib.conflict_resolver.Anthropic')
    def test_low_confidence_requires_manual_review(self, mock_anthropic, git_repo,
                                                   feature_flags_enabled, mock_api_key):
        """Low confidence resolution should require manual review."""
        os.chdir(git_repo)

        # Setup: Create conflict
        success, worktree_path = create_worktree('feature-low-conf', 'master')
        main_file = git_repo / "logic.py"
        main_file.write_text("def process():\n    return method_a()\n")
        subprocess.run(['git', 'add', 'logic.py'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Use method_a'], check=True)

        worktree_file = worktree_path / "logic.py"
        worktree_file.write_text("def process():\n    return method_b()\n")
        subprocess.run(['git', '-C', str(worktree_path), 'add', 'logic.py'], check=True)
        subprocess.run(['git', '-C', str(worktree_path), 'commit', '-m', 'Use method_b'], check=True)

        # Mock AI response with low confidence
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = Mock(
            content=[Mock(text='{"resolved_content": "def process():\\n    return method_b()", "confidence": 0.5, "reasoning": "Uncertain"}')]
        )

        # Merge with auto-resolve enabled
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': mock_api_key}):
            result = merge_worktree('feature-low-conf', 'master', auto_resolve=True)

        # Should have attempted resolution but not auto-applied
        assert mock_client.messages.create.called
        assert result.fallback_to_manual is True or result.manual_review_required

    @patch('autonomous_dev.lib.conflict_resolver.Anthropic')
    def test_security_files_always_require_manual_review(self, mock_anthropic, git_repo,
                                                         feature_flags_enabled, mock_api_key):
        """Security files require manual review regardless of confidence."""
        os.chdir(git_repo)

        # Setup: Create conflict in security-sensitive file
        success, worktree_path = create_worktree('feature-security', 'master')
        main_file = git_repo / "security_config.py"
        main_file.write_text("SECRET_KEY = 'key1'\n")
        subprocess.run(['git', 'add', 'security_config.py'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Set key1'], check=True)

        worktree_file = worktree_path / "security_config.py"
        worktree_file.write_text("SECRET_KEY = 'key2'\n")
        subprocess.run(['git', '-C', str(worktree_path), 'add', 'security_config.py'], check=True)
        subprocess.run(['git', '-C', str(worktree_path), 'commit', '-m', 'Set key2'], check=True)

        # Mock AI response with HIGH confidence (should still require manual review)
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = Mock(
            content=[Mock(text='{"resolved_content": "SECRET_KEY = \'key2\'", "confidence": 0.95, "reasoning": "Clear"}')]
        )

        # Merge with auto-resolve enabled
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': mock_api_key}):
            result = merge_worktree('feature-security', 'master', auto_resolve=True)

        # Should ALWAYS require manual review for security files
        assert result.fallback_to_manual is True or result.manual_review_required


# ============================================================================
# Git Automation Integration Tests
# ============================================================================

class TestGitAutomationWithConflictResolution:
    """Test git automation integration with conflict resolution."""

    @patch('autonomous_dev.lib.conflict_resolver.Anthropic')
    @patch('subprocess.run')
    def test_auto_commit_after_high_confidence_resolution(self, mock_subprocess, mock_anthropic,
                                                          git_repo, feature_flags_enabled, mock_api_key):
        """High confidence resolution should trigger auto-commit."""
        os.chdir(git_repo)

        # Mock conflict file
        conflict_file = git_repo / "feature.py"
        conflict_content = """
<<<<<<< HEAD
def feature():
    return 'v1'
=======
def feature():
    return 'v2'
>>>>>>> branch
"""
        conflict_file.write_text(conflict_content)

        # Mock AI response with high confidence
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = Mock(
            content=[Mock(text='{"resolved_content": "def feature():\\n    return \'v2\'", "confidence": 0.9, "reasoning": "Use v2"}')]
        )

        # Mock git commands
        mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

        # Trigger git automation
        from autonomous_dev.hooks.unified_git_automation import auto_commit_and_push

        with patch.dict(os.environ, {
            'ANTHROPIC_API_KEY': mock_api_key,
            'AUTO_GIT_ENABLED': 'true',
            'AUTO_GIT_PUSH': 'false'
        }):
            result = auto_commit_and_push()

        # Should have committed the resolution
        git_add_calls = [call for call in mock_subprocess.call_args_list if 'git add' in str(call)]
        git_commit_calls = [call for call in mock_subprocess.call_args_list if 'git commit' in str(call)]

        assert len(git_add_calls) > 0 or result['committed']
        assert len(git_commit_calls) > 0 or result['committed']

    @patch('autonomous_dev.lib.conflict_resolver.Anthropic')
    @patch('subprocess.run')
    def test_no_auto_commit_for_low_confidence(self, mock_subprocess, mock_anthropic,
                                               git_repo, feature_flags_enabled, mock_api_key):
        """Low confidence resolution should NOT trigger auto-commit."""
        os.chdir(git_repo)

        # Mock conflict file
        conflict_file = git_repo / "uncertain.py"
        conflict_content = """
<<<<<<< HEAD
def uncertain():
    return algo_a()
=======
def uncertain():
    return algo_b()
>>>>>>> branch
"""
        conflict_file.write_text(conflict_content)

        # Mock AI response with low confidence
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = Mock(
            content=[Mock(text='{"resolved_content": "def uncertain():\\n    return algo_b()", "confidence": 0.4, "reasoning": "Unsure"}')]
        )

        # Mock git commands
        mock_subprocess.return_value = Mock(returncode=0, stdout="UU uncertain.py\n", stderr="")

        # Trigger git automation
        from autonomous_dev.hooks.unified_git_automation import auto_commit_and_push

        with patch.dict(os.environ, {
            'ANTHROPIC_API_KEY': mock_api_key,
            'AUTO_GIT_ENABLED': 'true',
            'AUTO_GIT_PUSH': 'false'
        }):
            result = auto_commit_and_push()

        # Should NOT have committed (low confidence)
        git_commit_calls = [call for call in mock_subprocess.call_args_list if 'git commit' in str(call)]
        assert len(git_commit_calls) == 0 or result['manual_review_required']


# ============================================================================
# Feature Flag Toggle Tests
# ============================================================================

class TestFeatureFlagToggle:
    """Test feature flag toggling for conflict resolver."""

    @patch('autonomous_dev.lib.conflict_resolver.resolve_conflicts')
    def test_feature_disabled_skips_ai_resolution(self, mock_resolve, git_repo):
        """Feature disabled should skip AI resolution entirely."""
        os.chdir(git_repo)

        # Disable feature flag
        flags = {"conflict_resolver": {"enabled": False}}
        flags_file = git_repo / ".claude" / "feature_flags.json"
        flags_file.write_text(json.dumps(flags, indent=2))

        # Setup: Create conflict
        success, worktree_path = create_worktree('feature-disabled', 'master')
        main_file = git_repo / "test.py"
        main_file.write_text("VALUE = 'main'\n")
        subprocess.run(['git', 'add', 'test.py'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Main value'], check=True)

        worktree_file = worktree_path / "test.py"
        worktree_file.write_text("VALUE = 'worktree'\n")
        subprocess.run(['git', '-C', str(worktree_path), 'add', 'test.py'], check=True)
        subprocess.run(['git', '-C', str(worktree_path), 'commit', '-m', 'Worktree value'], check=True)

        # Merge (should skip AI resolution)
        result = merge_worktree('feature-disabled', 'master', auto_resolve=True)

        # Should NOT have called AI resolver
        mock_resolve.assert_not_called()
        # Should report conflicts without attempting resolution
        assert len(result.conflicts) > 0


# ============================================================================
# Multiple Conflicts Tests
# ============================================================================

class TestMultipleConflictResolution:
    """Test handling multiple conflicts in single merge."""

    @patch('autonomous_dev.lib.conflict_resolver.Anthropic')
    def test_resolve_multiple_conflicts_in_one_file(self, mock_anthropic, git_repo,
                                                    feature_flags_enabled, mock_api_key):
        """Should handle multiple conflicts in single file."""
        os.chdir(git_repo)

        # Setup: Create file with multiple conflicts
        success, worktree_path = create_worktree('feature-multi', 'master')

        main_file = git_repo / "multi.py"
        main_file.write_text("A = 1\nB = 2\n")
        subprocess.run(['git', 'add', 'multi.py'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Main values'], check=True)

        worktree_file = worktree_path / "multi.py"
        worktree_file.write_text("A = 10\nB = 20\n")
        subprocess.run(['git', '-C', str(worktree_path), 'add', 'multi.py'], check=True)
        subprocess.run(['git', '-C', str(worktree_path), 'commit', '-m', 'Worktree values'], check=True)

        # Mock AI responses
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = Mock(
            content=[Mock(text='{"resolved_content": "A = 10\\nB = 20", "confidence": 0.85, "reasoning": "Use worktree"}')]
        )

        # Merge
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': mock_api_key}):
            result = merge_worktree('feature-multi', 'master', auto_resolve=True)

        # Should resolve all conflicts in file
        assert mock_client.messages.create.called

    @patch('autonomous_dev.lib.conflict_resolver.Anthropic')
    def test_resolve_conflicts_across_multiple_files(self, mock_anthropic, git_repo,
                                                     feature_flags_enabled, mock_api_key):
        """Should handle conflicts across multiple files."""
        os.chdir(git_repo)

        # Setup: Create conflicts in multiple files
        success, worktree_path = create_worktree('feature-multi-files', 'master')

        for filename in ['file1.py', 'file2.py', 'file3.py']:
            main_file = git_repo / filename
            main_file.write_text(f"{filename.upper()} = 'main'\n")
            subprocess.run(['git', 'add', filename], check=True)

        subprocess.run(['git', 'commit', '-m', 'Main files'], check=True)

        for filename in ['file1.py', 'file2.py', 'file3.py']:
            worktree_file = worktree_path / filename
            worktree_file.write_text(f"{filename.upper()} = 'worktree'\n")
            subprocess.run(['git', '-C', str(worktree_path), 'add', filename], check=True)

        subprocess.run(['git', '-C', str(worktree_path), 'commit', '-m', 'Worktree files'], check=True)

        # Mock AI responses
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = Mock(
            content=[Mock(text='{"resolved_content": "resolved", "confidence": 0.9, "reasoning": "Use worktree"}')]
        )

        # Merge
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': mock_api_key}):
            result = merge_worktree('feature-multi-files', 'master', auto_resolve=True)

        # Should have attempted resolution for each file
        assert mock_client.messages.create.call_count >= 3 or len(result.resolved_files) >= 3


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test error handling in conflict resolution workflow."""

    @patch('autonomous_dev.lib.conflict_resolver.Anthropic')
    def test_api_error_fallback_to_manual(self, mock_anthropic, git_repo,
                                         feature_flags_enabled, mock_api_key):
        """API errors should fallback to manual resolution."""
        os.chdir(git_repo)

        # Setup: Create conflict
        success, worktree_path = create_worktree('feature-api-error', 'master')
        main_file = git_repo / "test.py"
        main_file.write_text("VALUE = 'main'\n")
        subprocess.run(['git', 'add', 'test.py'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Main'], check=True)

        worktree_file = worktree_path / "test.py"
        worktree_file.write_text("VALUE = 'worktree'\n")
        subprocess.run(['git', '-C', str(worktree_path), 'add', 'test.py'], check=True)
        subprocess.run(['git', '-C', str(worktree_path), 'commit', '-m', 'Worktree'], check=True)

        # Mock API error
        mock_anthropic.side_effect = Exception("API rate limit exceeded")

        # Merge
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': mock_api_key}):
            result = merge_worktree('feature-api-error', 'master', auto_resolve=True)

        # Should fallback to manual
        assert result.fallback_to_manual is True or result.manual_review_required

    def test_missing_api_key_fallback_to_manual(self, git_repo, feature_flags_enabled):
        """Missing API key should fallback to manual resolution."""
        os.chdir(git_repo)

        # Setup: Create conflict
        success, worktree_path = create_worktree('feature-no-key', 'master')
        main_file = git_repo / "test.py"
        main_file.write_text("VALUE = 'main'\n")
        subprocess.run(['git', 'add', 'test.py'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Main'], check=True)

        worktree_file = worktree_path / "test.py"
        worktree_file.write_text("VALUE = 'worktree'\n")
        subprocess.run(['git', '-C', str(worktree_path), 'add', 'test.py'], check=True)
        subprocess.run(['git', '-C', str(worktree_path), 'commit', '-m', 'Worktree'], check=True)

        # Merge without API key
        with patch.dict(os.environ, {}, clear=True):
            result = merge_worktree('feature-no-key', 'master', auto_resolve=True)

        # Should fallback to manual
        assert result.fallback_to_manual is True or result.manual_review_required


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
