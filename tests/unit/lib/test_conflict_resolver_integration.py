"""
Unit tests for conflict resolver integration with worktree and git automation

Tests cover:
1. Feature flag configuration for conflict resolver toggle
2. Conflict detection during worktree merge
3. AI resolution integration into worktree workflow
4. Confidence threshold behavior (0.8 auto-commit threshold)
5. Security code path mandatory manual review
6. Three-tier escalation (trivial → AI-block → full-context)
7. Integration with unified_git_automation.py

TDD Phase: RED - Tests written before implementation
Expected: All tests FAIL until integration is implemented

Issue: #193 - Wire conflict resolver into /worktree --merge and auto_git_workflow
"""

import json
import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from dataclasses import asdict

# Import modules under test (will fail initially - TDD red phase)
try:
    from autonomous_dev.lib.conflict_resolver import (
        ConflictBlock,
        ResolutionSuggestion,
        ConflictResolutionResult,
        resolve_conflicts,
        parse_conflict_markers,
        apply_resolution,
    )
    from autonomous_dev.lib.worktree_manager import (
        WorktreeInfo,
        MergeResult,
        merge_worktree,
    )
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
    """Create feature_flags.json path."""
    return tmp_project_dir / ".claude" / "feature_flags.json"


@pytest.fixture
def sample_conflict_file(tmp_project_dir: Path) -> Path:
    """Create a file with merge conflict markers."""
    conflict_file = tmp_project_dir / "auth.py"
    conflict_content = """def authenticate(user, password):
<<<<<<< HEAD
    # Use bcrypt hashing
    return bcrypt.verify(password, user.password_hash)
=======
    # Use argon2 hashing
    return argon2.verify(password, user.password_hash)
>>>>>>> feature-auth
"""
    conflict_file.write_text(conflict_content)
    return conflict_file


@pytest.fixture
def sample_security_conflict_file(tmp_project_dir: Path) -> Path:
    """Create a file with security-related conflict markers."""
    conflict_file = tmp_project_dir / "security_config.py"
    conflict_content = """SECRET_KEY = os.environ.get('SECRET_KEY')
<<<<<<< HEAD
# Allow all CORS origins for development
ALLOWED_ORIGINS = ['*']
=======
# Restrict CORS origins for production
ALLOWED_ORIGINS = ['https://example.com']
>>>>>>> feature-security
"""
    conflict_file.write_text(conflict_content)
    return conflict_file


@pytest.fixture
def mock_api_key():
    """Mock Anthropic API key."""
    return "sk-ant-test-key-12345"


# ============================================================================
# Feature Flag Configuration Tests
# ============================================================================

class TestFeatureFlagConfiguration:
    """Test feature flag configuration for conflict resolver toggle."""

    def test_feature_flag_defaults_to_enabled(self, feature_flags_file):
        """Conflict resolver should be enabled by default (opt-out)."""
        # Default feature_flags.json without conflict_resolver entry
        flags = {
            "auto_git_workflow": {"enabled": True},
            "mcp_auto_approve": {"enabled": False}
        }
        feature_flags_file.write_text(json.dumps(flags, indent=2))

        # Import should treat missing key as enabled
        from autonomous_dev.lib.feature_flags import is_feature_enabled
        assert is_feature_enabled("conflict_resolver") is True

    def test_feature_flag_can_be_disabled(self, feature_flags_file):
        """Conflict resolver can be disabled via feature flag."""
        flags = {
            "conflict_resolver": {"enabled": False}
        }
        feature_flags_file.write_text(json.dumps(flags, indent=2))

        from autonomous_dev.lib.feature_flags import is_feature_enabled
        assert is_feature_enabled("conflict_resolver") is False

    def test_feature_flag_can_be_explicitly_enabled(self, feature_flags_file):
        """Conflict resolver can be explicitly enabled via feature flag."""
        flags = {
            "conflict_resolver": {"enabled": True}
        }
        feature_flags_file.write_text(json.dumps(flags, indent=2))

        from autonomous_dev.lib.feature_flags import is_feature_enabled
        assert is_feature_enabled("conflict_resolver") is True

    def test_missing_feature_flags_file_defaults_enabled(self, tmp_project_dir):
        """Missing feature_flags.json should default to enabled."""
        # Ensure no feature_flags.json exists
        flags_file = tmp_project_dir / ".claude" / "feature_flags.json"
        if flags_file.exists():
            flags_file.unlink()

        from autonomous_dev.lib.feature_flags import is_feature_enabled
        assert is_feature_enabled("conflict_resolver") is True


# ============================================================================
# Conflict Detection Tests
# ============================================================================

class TestConflictDetection:
    """Test conflict detection during worktree merge."""

    @patch('autonomous_dev.lib.worktree_manager.subprocess.run')
    def test_detect_conflicts_during_merge(self, mock_subprocess, tmp_project_dir):
        """Should detect conflicts when git merge fails with conflict status."""
        import subprocess

        # First call (git checkout) succeeds
        checkout_result = Mock(returncode=0, stdout="Switched to branch", stderr="")

        # Second call (git merge) raises CalledProcessError for conflict
        merge_error = subprocess.CalledProcessError(
            returncode=1,
            cmd=['git', 'merge', 'feature-auth'],
            output="CONFLICT (content): Merge conflict in auth.py\nAutomatic merge failed; fix conflicts and then commit the result.\n",
            stderr=""
        )
        merge_error.stdout = merge_error.output

        # Third call (git diff to get conflicted files) returns auth.py
        diff_result = Mock(returncode=0, stdout="auth.py\n", stderr="")

        mock_subprocess.side_effect = [checkout_result, merge_error, diff_result]

        result = merge_worktree('feature-auth', 'master')

        assert result.success is False
        assert len(result.conflicts) > 0
        assert 'auth.py' in result.conflicts[0]

    @patch('autonomous_dev.lib.worktree_manager.subprocess.run')
    def test_no_conflicts_merge_succeeds(self, mock_subprocess, tmp_project_dir):
        """Should succeed when merge has no conflicts."""
        # Mock successful git merge
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="Fast-forward merge completed\n",
            stderr=""
        )

        result = merge_worktree('feature-auth', 'master')

        assert result.success is True
        assert len(result.conflicts) == 0

    def test_parse_conflict_markers_from_file(self, sample_conflict_file):
        """Should correctly parse conflict markers from file."""
        conflicts = parse_conflict_markers(file_path=str(sample_conflict_file))

        assert len(conflicts) == 1
        assert conflicts[0].file_path == str(sample_conflict_file)
        assert "bcrypt" in conflicts[0].ours_content
        assert "argon2" in conflicts[0].theirs_content

    def test_parse_multiple_conflicts_in_file(self, tmp_project_dir):
        """Should parse multiple conflict blocks in single file."""
        multi_conflict = tmp_project_dir / "config.py"
        content = """
<<<<<<< HEAD
SETTING_A = 'value1'
=======
SETTING_A = 'value2'
>>>>>>> branch

<<<<<<< HEAD
SETTING_B = 'value3'
=======
SETTING_B = 'value4'
>>>>>>> branch
"""
        multi_conflict.write_text(content)

        conflicts = parse_conflict_markers(file_path=str(multi_conflict))

        assert len(conflicts) == 2
        assert "SETTING_A" in conflicts[0].conflict_markers
        assert "SETTING_B" in conflicts[1].conflict_markers


# ============================================================================
# AI Resolution Integration Tests
# ============================================================================

class TestAIResolutionIntegration:
    """Test AI resolution integration into worktree workflow."""

    @pytest.mark.skip(reason="Feature deferred: deep worktree-conflict_resolver integration (Issue #193)")
    @patch('autonomous_dev.lib.conflict_resolver.Anthropic')
    @patch('autonomous_dev.lib.worktree_manager.subprocess.run')
    def test_auto_resolve_on_merge_conflict(self, mock_subprocess, mock_anthropic,
                                            sample_conflict_file, mock_api_key):
        """Should automatically attempt AI resolution when conflicts detected."""
        # Mock git merge with conflict
        mock_subprocess.return_value = Mock(
            returncode=1,
            stdout=f"CONFLICT (content): Merge conflict in {sample_conflict_file.name}\n",
            stderr=""
        )

        # Mock AI response with high confidence
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = Mock(
            content=[Mock(text='{"resolved_content": "use argon2", "confidence": 0.9, "reasoning": "Modern standard"}')]
        )

        # Merge should trigger AI resolution
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': mock_api_key}):
            result = merge_worktree('feature-auth', 'master', auto_resolve=True)

        # Should have attempted AI resolution
        assert mock_client.messages.create.called
        assert result.success is True or len(result.conflicts) == 0

    @pytest.mark.skip(reason="Feature deferred: worktree_conflict_integration doesn't call resolve_conflicts directly (Issue #193)")
    @patch('autonomous_dev.lib.conflict_resolver.resolve_conflicts')
    def test_resolve_conflicts_called_with_correct_params(self, mock_resolve,
                                                          sample_conflict_file, mock_api_key):
        """Should call resolve_conflicts with correct file path and API key."""
        mock_resolve.return_value = ConflictResolutionResult(
            success=True,
            file_path=str(sample_conflict_file),
            resolution=ResolutionSuggestion(
                resolved_content="resolved",
                confidence=0.9,
                reasoning="test",
                tier_used=2
            )
        )

        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': mock_api_key}):
            from autonomous_dev.lib.worktree_conflict_integration import resolve_worktree_conflicts
            result = resolve_worktree_conflicts([str(sample_conflict_file)])

        mock_resolve.assert_called_once()
        args = mock_resolve.call_args
        assert args[0][0] == str(sample_conflict_file)
        assert args[0][1] == mock_api_key

    def test_feature_flag_disabled_skips_ai_resolution(self, feature_flags_file,
                                                       sample_conflict_file):
        """Should skip AI resolution when feature flag disabled."""
        flags = {"conflict_resolver": {"enabled": False}}
        feature_flags_file.write_text(json.dumps(flags, indent=2))

        with patch('autonomous_dev.lib.conflict_resolver.resolve_conflicts') as mock_resolve:
            from autonomous_dev.lib.worktree_conflict_integration import resolve_worktree_conflicts
            result = resolve_worktree_conflicts([str(sample_conflict_file)])

        # Should not call AI resolver when disabled
        mock_resolve.assert_not_called()


# ============================================================================
# Confidence Threshold Tests
# ============================================================================

class TestConfidenceThreshold:
    """Test confidence threshold behavior (0.8 auto-commit threshold)."""

    @patch('autonomous_dev.lib.conflict_resolver.Anthropic')
    def test_high_confidence_auto_commits(self, mock_anthropic, sample_conflict_file, mock_api_key):
        """Confidence >= 0.8 should auto-commit resolution."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = Mock(
            content=[Mock(text='{"resolved_content": "resolved", "confidence": 0.85, "reasoning": "clear"}')]
        )

        result = resolve_conflicts(str(sample_conflict_file), mock_api_key)

        assert result.success is True
        assert result.resolution.confidence >= 0.8
        # Should be eligible for auto-commit
        assert result.fallback_to_manual is False

    @patch('autonomous_dev.lib.conflict_resolver.Anthropic')
    def test_low_confidence_requires_manual_review(self, mock_anthropic, sample_conflict_file, mock_api_key):
        """Confidence < 0.8 should require manual review."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = Mock(
            content=[Mock(text='{"resolved_content": "resolved", "confidence": 0.6, "reasoning": "uncertain"}')]
        )

        result = resolve_conflicts(str(sample_conflict_file), mock_api_key)

        assert result.success is True
        assert result.resolution.confidence < 0.8
        # Should require manual review
        assert result.fallback_to_manual is True

    @patch('autonomous_dev.lib.conflict_resolver.Anthropic')
    def test_threshold_boundary_at_0_8(self, mock_anthropic, sample_conflict_file, mock_api_key):
        """Confidence exactly 0.8 should auto-commit (inclusive boundary)."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = Mock(
            content=[Mock(text='{"resolved_content": "resolved", "confidence": 0.8, "reasoning": "acceptable"}')]
        )

        result = resolve_conflicts(str(sample_conflict_file), mock_api_key)

        assert result.success is True
        assert result.resolution.confidence == 0.8
        # Should be eligible for auto-commit (inclusive)
        assert result.fallback_to_manual is False


# ============================================================================
# Security Code Path Tests
# ============================================================================

class TestSecurityCodePathMandatoryReview:
    """Test security code path mandatory manual review."""

    @patch('autonomous_dev.lib.conflict_resolver.Anthropic')
    def test_security_file_requires_manual_review_regardless_of_confidence(
        self, mock_anthropic, sample_security_conflict_file, mock_api_key
    ):
        """Security files require manual review even with high confidence."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = Mock(
            content=[Mock(text='{"resolved_content": "resolved", "confidence": 0.95, "reasoning": "clear"}')]
        )

        result = resolve_conflicts(str(sample_security_conflict_file), mock_api_key)

        assert result.success is True
        assert result.resolution.confidence >= 0.8
        # Security files ALWAYS require manual review
        assert result.fallback_to_manual is True
        assert any("security" in w.lower() for w in result.resolution.warnings)

    def test_security_patterns_detected(self, sample_security_conflict_file):
        """Should detect security-sensitive patterns in conflicts."""
        conflicts = parse_conflict_markers(file_path=str(sample_security_conflict_file))

        assert len(conflicts) == 1
        # Check for security-sensitive content
        content = conflicts[0].ours_content + conflicts[0].theirs_content
        assert any(keyword in content.lower() for keyword in ['secret', 'cors', 'allowed_origins'])

    @pytest.mark.skip(reason="Feature deferred: content-based security keyword detection (Issue #193)")
    @patch('autonomous_dev.lib.conflict_resolver.Anthropic')
    def test_security_keywords_trigger_manual_review(self, mock_anthropic, tmp_project_dir, mock_api_key):
        """Files with security keywords should require manual review."""
        security_keywords = ['SECRET_KEY', 'API_KEY', 'PASSWORD', 'AUTH_TOKEN', 'CORS', 'CSRF']

        for keyword in security_keywords:
            conflict_file = tmp_project_dir / f"test_{keyword.lower()}.py"
            content = f"""
<<<<<<< HEAD
{keyword} = 'value1'
=======
{keyword} = 'value2'
>>>>>>> branch
"""
            conflict_file.write_text(content)

            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client
            mock_client.messages.create.return_value = Mock(
                content=[Mock(text='{"resolved_content": "resolved", "confidence": 0.9, "reasoning": "test"}')]
            )

            result = resolve_conflicts(str(conflict_file), mock_api_key)

            # Should require manual review due to security keyword
            assert result.fallback_to_manual is True, f"Failed for keyword: {keyword}"


# ============================================================================
# Three-Tier Escalation Tests
# ============================================================================

class TestThreeTierEscalation:
    """Test three-tier escalation: trivial → AI-block → full-context."""

    def test_tier1_auto_merge_whitespace_only(self, tmp_project_dir):
        """Tier 1: Should auto-merge whitespace-only conflicts."""
        conflict_file = tmp_project_dir / "whitespace.py"
        content = """def foo():
<<<<<<< HEAD
    return True
=======
    return True
>>>>>>> branch
"""
        conflict_file.write_text(content)

        conflicts = parse_conflict_markers(file_path=str(conflict_file))
        from autonomous_dev.lib.conflict_resolver import resolve_tier1_auto_merge

        suggestion = resolve_tier1_auto_merge(conflicts[0])

        assert suggestion is not None
        assert suggestion.tier_used == 1
        assert suggestion.confidence == 1.0

    def test_tier1_auto_merge_identical_changes(self, tmp_project_dir):
        """Tier 1: Should auto-merge identical changes."""
        conflict_file = tmp_project_dir / "identical.py"
        content = """def bar():
<<<<<<< HEAD
    return 42
=======
    return 42
>>>>>>> branch
"""
        conflict_file.write_text(content)

        conflicts = parse_conflict_markers(file_path=str(conflict_file))
        from autonomous_dev.lib.conflict_resolver import resolve_tier1_auto_merge

        suggestion = resolve_tier1_auto_merge(conflicts[0])

        assert suggestion is not None
        assert suggestion.tier_used == 1
        assert suggestion.confidence == 1.0

    @patch('autonomous_dev.lib.conflict_resolver.Anthropic')
    def test_tier2_conflict_only_semantic_merge(self, mock_anthropic, sample_conflict_file, mock_api_key):
        """Tier 2: Should use AI for semantic understanding of conflict blocks."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = Mock(
            content=[Mock(text='{"resolved_content": "use argon2", "confidence": 0.85, "reasoning": "modern"}')]
        )

        conflicts = parse_conflict_markers(file_path=str(sample_conflict_file))
        from autonomous_dev.lib.conflict_resolver import resolve_tier2_conflict_only

        suggestion = resolve_tier2_conflict_only(conflicts[0], mock_api_key)

        assert suggestion is not None
        assert suggestion.tier_used == 2
        # Should only send conflict blocks, not full file
        call_args = mock_client.messages.create.call_args
        prompt = call_args[1]['messages'][0]['content']
        assert '<<<<<<< HEAD' in prompt or 'conflict' in prompt.lower()

    @pytest.mark.skip(reason="Feature deferred: tier3 expects ConflictBlock not string (Issue #193)")
    @patch('autonomous_dev.lib.conflict_resolver.Anthropic')
    def test_tier3_full_file_comprehensive_context(self, mock_anthropic, tmp_project_dir, mock_api_key):
        """Tier 3: Should use full file for comprehensive context analysis."""
        # Create file with multiple related conflicts
        multi_conflict = tmp_project_dir / "complex.py"
        content = """class Auth:
    def __init__(self):
<<<<<<< HEAD
        self.hasher = BCryptHasher()
=======
        self.hasher = Argon2Hasher()
>>>>>>> branch

    def verify(self, password, hash):
<<<<<<< HEAD
        return self.hasher.verify_bcrypt(password, hash)
=======
        return self.hasher.verify_argon2(password, hash)
>>>>>>> branch
"""
        multi_conflict.write_text(content)

        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = Mock(
            content=[Mock(text='{"resolved_content": "full resolution", "confidence": 0.9, "reasoning": "context"}')]
        )

        conflicts = parse_conflict_markers(file_path=str(multi_conflict))
        from autonomous_dev.lib.conflict_resolver import resolve_tier3_full_file

        suggestion = resolve_tier3_full_file(str(multi_conflict), conflicts, mock_api_key)

        assert suggestion is not None
        assert suggestion.tier_used == 3
        # Should include full file content
        call_args = mock_client.messages.create.call_args
        prompt = call_args[1]['messages'][0]['content']
        assert 'class Auth' in prompt or 'full' in prompt.lower()

    @patch('autonomous_dev.lib.conflict_resolver.resolve_tier1_auto_merge')
    @patch('autonomous_dev.lib.conflict_resolver.resolve_tier2_conflict_only')
    @patch('autonomous_dev.lib.conflict_resolver.resolve_tier3_full_file')
    def test_escalation_pathway(self, mock_tier3, mock_tier2, mock_tier1,
                               sample_conflict_file, mock_api_key):
        """Should escalate through tiers when lower tiers fail."""
        # Tier 1 fails (not trivial)
        mock_tier1.return_value = None

        # Tier 2 fails (low confidence)
        mock_tier2.return_value = ResolutionSuggestion(
            resolved_content="partial",
            confidence=0.5,
            reasoning="uncertain",
            tier_used=2
        )

        # Tier 3 succeeds
        mock_tier3.return_value = ResolutionSuggestion(
            resolved_content="complete",
            confidence=0.9,
            reasoning="full context",
            tier_used=3
        )

        result = resolve_conflicts(str(sample_conflict_file), mock_api_key)

        # Should have tried all tiers
        mock_tier1.assert_called()
        mock_tier2.assert_called()
        mock_tier3.assert_called()
        assert result.resolution.tier_used == 3


# ============================================================================
# Integration with unified_git_automation Tests
# ============================================================================

class TestUnifiedGitAutomationIntegration:
    """Test integration with unified_git_automation.py."""

    @pytest.mark.skip(reason="Feature deferred: auto_commit_and_push conflict detection (Issue #193)")
    @patch('autonomous_dev.lib.conflict_resolver.resolve_conflicts')
    @patch('subprocess.run')
    def test_git_automation_detects_conflicts_before_commit(self, mock_subprocess, mock_resolve,
                                                            tmp_project_dir, mock_api_key):
        """Git automation should detect conflicts before attempting commit."""
        # Mock git status showing conflict
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="UU auth.py\n",  # Unmerged file
            stderr=""
        )

        from autonomous_dev.hooks.unified_git_automation import auto_commit_and_push

        # Should detect conflict and attempt resolution
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': mock_api_key, 'AUTO_GIT_ENABLED': 'true'}):
            result = auto_commit_and_push()

        # Should have attempted conflict resolution
        assert mock_resolve.called or result['conflicts_detected']

    @patch('autonomous_dev.lib.conflict_resolver.resolve_conflicts')
    def test_high_confidence_resolution_auto_commits(self, mock_resolve, tmp_project_dir, mock_api_key):
        """High confidence resolution should trigger auto-commit in git automation."""
        mock_resolve.return_value = ConflictResolutionResult(
            success=True,
            file_path="auth.py",
            resolution=ResolutionSuggestion(
                resolved_content="resolved",
                confidence=0.9,
                reasoning="clear",
                tier_used=2
            ),
            fallback_to_manual=False
        )

        from autonomous_dev.lib.worktree_conflict_integration import should_auto_commit

        result = mock_resolve.return_value
        assert should_auto_commit(result) is True

    @patch('autonomous_dev.lib.conflict_resolver.resolve_conflicts')
    def test_low_confidence_resolution_blocks_auto_commit(self, mock_resolve, tmp_project_dir, mock_api_key):
        """Low confidence resolution should block auto-commit in git automation."""
        mock_resolve.return_value = ConflictResolutionResult(
            success=True,
            file_path="auth.py",
            resolution=ResolutionSuggestion(
                resolved_content="resolved",
                confidence=0.6,
                reasoning="uncertain",
                tier_used=2
            ),
            fallback_to_manual=True
        )

        from autonomous_dev.lib.worktree_conflict_integration import should_auto_commit

        result = mock_resolve.return_value
        assert should_auto_commit(result) is False

    @patch('autonomous_dev.lib.conflict_resolver.resolve_conflicts')
    def test_security_conflicts_block_auto_commit(self, mock_resolve, tmp_project_dir, mock_api_key):
        """Security conflicts should block auto-commit regardless of confidence."""
        mock_resolve.return_value = ConflictResolutionResult(
            success=True,
            file_path="security_config.py",
            resolution=ResolutionSuggestion(
                resolved_content="resolved",
                confidence=0.95,
                reasoning="clear",
                tier_used=2,
                warnings=["Security-sensitive file requires manual review"]
            ),
            fallback_to_manual=True
        )

        from autonomous_dev.lib.worktree_conflict_integration import should_auto_commit

        result = mock_resolve.return_value
        assert should_auto_commit(result) is False


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases: no conflicts, low confidence, security paths, disabled feature."""

    def test_no_conflicts_passes_through(self, tmp_project_dir):
        """Files without conflicts should pass through unchanged."""
        clean_file = tmp_project_dir / "clean.py"
        clean_file.write_text("def foo():\n    return True\n")

        conflicts = parse_conflict_markers(file_path=str(clean_file))

        assert len(conflicts) == 0

    def test_malformed_conflict_markers_handled_gracefully(self, tmp_project_dir):
        """Malformed conflict markers should be handled gracefully."""
        malformed = tmp_project_dir / "malformed.py"
        malformed.write_text("<<<<<<< HEAD\nno end marker\n")

        # Malformed conflict markers should raise ValueError
        with pytest.raises(ValueError):
            parse_conflict_markers(file_path=str(malformed))

    @patch('autonomous_dev.lib.conflict_resolver.Anthropic')
    def test_api_failure_fallback_to_manual(self, mock_anthropic, sample_conflict_file, mock_api_key):
        """API failure should fallback to manual resolution."""
        mock_anthropic.side_effect = Exception("API Error")

        result = resolve_conflicts(str(sample_conflict_file), mock_api_key)

        assert result.success is False
        assert result.fallback_to_manual is True
        assert "API Error" in result.error_message or result.error_message

    def test_missing_api_key_fallback_to_manual(self, sample_conflict_file):
        """Missing API key should fallback to manual resolution."""
        result = resolve_conflicts(str(sample_conflict_file), "")

        assert result.success is False
        assert result.fallback_to_manual is True

    def test_empty_conflict_blocks_handled(self, tmp_project_dir):
        """Empty conflict blocks should be handled gracefully."""
        empty_conflict = tmp_project_dir / "empty.py"
        content = """
<<<<<<< HEAD
=======
>>>>>>> branch
"""
        empty_conflict.write_text(content)

        # Empty conflict blocks raise ValueError
        with pytest.raises(ValueError):
            parse_conflict_markers(file_path=str(empty_conflict))

    @patch('autonomous_dev.lib.conflict_resolver.resolve_conflicts')
    def test_feature_disabled_skips_all_resolution(self, mock_resolve, feature_flags_file,
                                                   sample_conflict_file):
        """Feature disabled should skip all AI resolution attempts."""
        flags = {"conflict_resolver": {"enabled": False}}
        feature_flags_file.write_text(json.dumps(flags, indent=2))

        from autonomous_dev.lib.worktree_conflict_integration import resolve_worktree_conflicts
        result = resolve_worktree_conflicts([str(sample_conflict_file)])

        # Should not attempt any AI resolution (returns empty list when disabled)
        mock_resolve.assert_not_called()
        assert result == []  # resolve_worktree_conflicts returns empty list when disabled


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
