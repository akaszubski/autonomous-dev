#!/usr/bin/env python3
"""
Unit tests for batch_permission_approver hook (Issue #323).

Tests for MCP_AUTO_APPROVE propagation to batch subagents.

Date: 2026-02-06
Issue: GitHub #323
Agent: test-master
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add hooks directory to path
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "hooks"
    ),
)


class TestIsBatchingEnabled:
    """Test is_batching_enabled function with env var support (Issue #323)."""

    @pytest.fixture(autouse=True)
    def cleanup_env(self):
        """Clean up environment variables before and after each test."""
        # Save original values
        saved = {}
        for var in ['BATCH_AUTO_APPROVE', 'MCP_AUTO_APPROVE']:
            if var in os.environ:
                saved[var] = os.environ[var]
                del os.environ[var]

        yield

        # Restore original values
        for var in ['BATCH_AUTO_APPROVE', 'MCP_AUTO_APPROVE']:
            if var in os.environ:
                del os.environ[var]
        for var, value in saved.items():
            os.environ[var] = value

    def test_is_batching_enabled_with_batch_auto_approve_true(self):
        """Test BATCH_AUTO_APPROVE=true enables batching."""
        # Import after path setup
        import importlib
        import batch_permission_approver
        importlib.reload(batch_permission_approver)

        os.environ['BATCH_AUTO_APPROVE'] = 'true'
        result = batch_permission_approver.is_batching_enabled()
        assert result is True

    def test_is_batching_enabled_with_batch_auto_approve_false(self):
        """Test BATCH_AUTO_APPROVE=false disables batching."""
        import importlib
        import batch_permission_approver
        importlib.reload(batch_permission_approver)

        os.environ['BATCH_AUTO_APPROVE'] = 'false'
        result = batch_permission_approver.is_batching_enabled()
        assert result is False

    def test_is_batching_enabled_with_mcp_auto_approve_true(self):
        """Test MCP_AUTO_APPROVE=true enables batching (Issue #323)."""
        import importlib
        import batch_permission_approver
        importlib.reload(batch_permission_approver)

        os.environ['MCP_AUTO_APPROVE'] = 'true'
        result = batch_permission_approver.is_batching_enabled()
        assert result is True

    def test_is_batching_enabled_with_mcp_auto_approve_everywhere(self):
        """Test MCP_AUTO_APPROVE=everywhere enables batching."""
        import importlib
        import batch_permission_approver
        importlib.reload(batch_permission_approver)

        os.environ['MCP_AUTO_APPROVE'] = 'everywhere'
        result = batch_permission_approver.is_batching_enabled()
        assert result is True

    def test_is_batching_enabled_with_mcp_auto_approve_false(self):
        """Test MCP_AUTO_APPROVE=false disables batching."""
        import importlib
        import batch_permission_approver
        importlib.reload(batch_permission_approver)

        os.environ['MCP_AUTO_APPROVE'] = 'false'
        result = batch_permission_approver.is_batching_enabled()
        assert result is False

    def test_is_batching_enabled_batch_takes_precedence(self):
        """Test BATCH_AUTO_APPROVE takes precedence over MCP_AUTO_APPROVE."""
        import importlib
        import batch_permission_approver
        importlib.reload(batch_permission_approver)

        os.environ['BATCH_AUTO_APPROVE'] = 'false'
        os.environ['MCP_AUTO_APPROVE'] = 'true'
        result = batch_permission_approver.is_batching_enabled()
        assert result is False  # BATCH takes precedence

    @patch('pathlib.Path.exists')
    @patch('builtins.open')
    def test_is_batching_enabled_falls_back_to_settings(self, mock_open, mock_exists):
        """Test fallback to settings.local.json when no env vars set."""
        import importlib
        import batch_permission_approver
        importlib.reload(batch_permission_approver)

        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps({
            'permissionBatching': {'enabled': True}
        })

        result = batch_permission_approver.is_batching_enabled()
        assert result is True

    @patch('pathlib.Path.exists')
    def test_is_batching_enabled_default_false(self, mock_exists):
        """Test default is False when no env vars and no settings file."""
        import importlib
        import batch_permission_approver
        importlib.reload(batch_permission_approver)

        mock_exists.return_value = False

        result = batch_permission_approver.is_batching_enabled()
        assert result is False
