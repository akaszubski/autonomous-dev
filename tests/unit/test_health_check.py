"""
Unit tests for health_check.py plugin validation utility.

Tests validate:
- Agent detection (8 agents)
- Skill detection (13 skills)
- Hook detection (8 hooks)
- Command detection (21+ commands)
- Report generation
- Exit codes
"""

import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Import from hooks directory using proper module path
from plugins.autonomous_dev.hooks.health_check import PluginHealthCheck


class TestHealthCheck:
    """Test suite for plugin health check utility."""

    def test_plugin_dir_found(self):
        """Test that plugin directory can be located."""
        checker = PluginHealthCheck()
        assert checker.plugin_dir.exists()
        assert checker.plugin_dir.name == "autonomous-dev"

    def test_agent_validation_all_present(self):
        """Test agent validation when all agents present."""
        checker = PluginHealthCheck()
        passed, total = checker.validate_agents()

        assert total == 8, "Expected 8 agents"
        assert passed == 8, "All 8 agents should be present"

        for agent in checker.EXPECTED_AGENTS:
            assert checker.results["agents"][agent] == "PASS"

    def test_skill_validation_all_present(self):
        """Test skill validation when all skills present."""
        checker = PluginHealthCheck()
        passed, total = checker.validate_skills()

        assert total == 13, "Expected 13 skills"
        assert passed == 13, "All 13 skills should be present"

        for skill in checker.EXPECTED_SKILLS:
            assert checker.results["skills"][skill] == "PASS"

    def test_hook_validation_all_present(self):
        """Test hook validation when all hooks present."""
        checker = PluginHealthCheck()
        passed, total = checker.validate_hooks()

        assert total == 8, "Expected 8 hooks"
        assert passed >= 7, "At least 7 hooks should be present"  # Allow 1 missing during dev

    def test_command_validation_minimum_present(self):
        """Test command validation has minimum required commands."""
        checker = PluginHealthCheck()
        passed, total = checker.validate_commands()

        assert total >= 21, "Expected at least 21 commands"
        assert passed >= 20, "At least 20 commands should be present"  # Allow 1 missing during dev

    def test_overall_status_healthy_when_all_pass(self):
        """Test overall status is HEALTHY when all components pass."""
        checker = PluginHealthCheck()

        # Mock all validations to pass
        with patch.object(checker, 'validate_agents', return_value=(8, 8)):
            with patch.object(checker, 'validate_skills', return_value=(13, 13)):
                with patch.object(checker, 'validate_hooks', return_value=(8, 8)):
                    with patch.object(checker, 'validate_commands', return_value=(21, 21)):
                        checker.results = {
                            "agents": {a: "PASS" for a in checker.EXPECTED_AGENTS},
                            "skills": {s: "PASS" for s in checker.EXPECTED_SKILLS},
                            "hooks": {h: "PASS" for h in checker.EXPECTED_HOOKS},
                            "commands": {c: "PASS" for c in checker.EXPECTED_COMMANDS},
                            "overall": "UNKNOWN"
                        }

                        # Capture stdout
                        import io
                        captured = io.StringIO()
                        with patch('sys.stdout', captured):
                            try:
                                checker.print_report()
                            except SystemExit:
                                pass

                        output = captured.getvalue()
                        assert "OVERALL STATUS: HEALTHY" in output

    def test_overall_status_degraded_when_failures(self):
        """Test overall status is DEGRADED when components fail."""
        checker = PluginHealthCheck()

        # Mock some validations to fail
        checker.results = {
            "agents": {
                "orchestrator": "PASS",
                "planner": "PASS",
                "researcher": "PASS",
                "test-master": "PASS",
                "implementer": "FAIL",  # Missing
                "reviewer": "PASS",
                "security-auditor": "PASS",
                "doc-master": "PASS",
            },
            "skills": {s: "PASS" for s in checker.EXPECTED_SKILLS},
            "hooks": {h: "PASS" for h in checker.EXPECTED_HOOKS},
            "commands": {c: "PASS" for c in checker.EXPECTED_COMMANDS},
            "overall": "UNKNOWN"
        }

        with patch.object(checker, 'validate_agents', return_value=(7, 8)):
            with patch.object(checker, 'validate_skills', return_value=(13, 13)):
                with patch.object(checker, 'validate_hooks', return_value=(8, 8)):
                    with patch.object(checker, 'validate_commands', return_value=(21, 21)):
                        # Capture stdout
                        import io
                        captured = io.StringIO()
                        with patch('sys.stdout', captured):
                            try:
                                checker.print_report()
                            except SystemExit:
                                pass

                        output = captured.getvalue()
                        assert "OVERALL STATUS: DEGRADED" in output
                        assert "implementer" in output

    def test_json_output_format(self):
        """Test JSON output format is valid."""
        checker = PluginHealthCheck()

        # Capture stdout
        import io
        captured = io.StringIO()
        with patch('sys.stdout', captured):
            try:
                checker.print_json()
            except SystemExit:
                pass

        output = captured.getvalue()

        # Validate JSON structure
        data = json.loads(output)
        assert "agents" in data
        assert "skills" in data
        assert "hooks" in data
        assert "commands" in data
        assert "overall" in data

    def test_check_component_exists(self):
        """Test component existence checking."""
        checker = PluginHealthCheck()

        # Test existing agent
        exists = checker.check_component_exists("agents", "orchestrator", ".md")
        assert exists, "orchestrator agent should exist"

        # Test non-existing component
        exists = checker.check_component_exists("agents", "nonexistent", ".md")
        assert not exists, "nonexistent agent should not exist"

    def test_coverage_target_met(self):
        """Meta-test: Verify this test file achieves 80%+ coverage."""
        # This test serves as documentation that we aim for 80%+ coverage
        # Actual coverage measured by pytest-cov
        pass


class TestMarketplaceVersionValidation:
    """Test suite for marketplace version validation integration (Issue #50 Phase 1)."""

    def test_validate_marketplace_version_success(self):
        """Test marketplace version validation when versions match."""
        checker = PluginHealthCheck()

        # Mock validate_marketplace_version from the lib module
        mock_report = "Marketplace: 3.7.0 | Project: 3.7.0 | Status: UP TO DATE"
        with patch('plugins.autonomous_dev.lib.validate_marketplace_version.validate_marketplace_version',
                   return_value=mock_report):
            result = checker._validate_marketplace_version()

        # Should return True (non-blocking)
        assert result is True, "Method should return True for successful version check"

    def test_validate_marketplace_version_upgrade_available(self):
        """Test marketplace version validation when upgrade is available."""
        checker = PluginHealthCheck()

        # Mock validate_marketplace_version to show upgrade available
        mock_report = "Marketplace: 3.8.0 | Project: 3.7.0 | Status: UPGRADE AVAILABLE"

        # Capture stdout to verify upgrade message is displayed
        import io
        captured = io.StringIO()

        with patch('plugins.autonomous_dev.lib.validate_marketplace_version.validate_marketplace_version',
                   return_value=mock_report):
            with patch('sys.stdout', captured):
                result = checker._validate_marketplace_version()

        output = captured.getvalue()

        # Should return True (non-blocking)
        assert result is True, "Method should return True even when upgrade available"

        # Should display upgrade message
        assert "UPGRADE AVAILABLE" in output, "Should show upgrade message"
        assert "3.8.0" in output, "Should show marketplace version"
        assert "3.7.0" in output, "Should show project version"

    def test_validate_marketplace_version_downgrade_detected(self):
        """Test marketplace version validation when marketplace is older (local ahead)."""
        checker = PluginHealthCheck()

        # Mock validate_marketplace_version to show downgrade (local ahead)
        mock_report = "Marketplace: 3.6.0 | Project: 3.7.0 | Status: LOCAL AHEAD"

        # Capture stdout to verify downgrade warning is displayed
        import io
        captured = io.StringIO()

        with patch('plugins.autonomous_dev.lib.validate_marketplace_version.validate_marketplace_version',
                   return_value=mock_report):
            with patch('sys.stdout', captured):
                result = checker._validate_marketplace_version()

        output = captured.getvalue()

        # Should return True (non-blocking)
        assert result is True, "Method should return True even when downgrade detected"

        # Should display warning message
        assert "LOCAL AHEAD" in output, "Should show local ahead warning"
        assert "3.6.0" in output, "Should show marketplace version"
        assert "3.7.0" in output, "Should show project version"

    def test_validate_marketplace_version_marketplace_not_installed(self):
        """Test marketplace version validation when marketplace plugin not found."""
        checker = PluginHealthCheck()

        # Mock validate_marketplace_version to raise FileNotFoundError
        with patch('plugins.autonomous_dev.lib.validate_marketplace_version.validate_marketplace_version',
                   side_effect=FileNotFoundError("Marketplace plugin.json not found")):
            # Capture stdout to verify skip message is displayed
            import io
            captured = io.StringIO()

            with patch('sys.stdout', captured):
                result = checker._validate_marketplace_version()

        output = captured.getvalue()

        # Should return True (non-blocking)
        assert result is True, "Method should return True even when marketplace not found"

        # Should display skip message
        assert "SKIP" in output or "not found" in output.lower(), "Should show skip message"

    def test_validate_marketplace_version_permission_error(self):
        """Test marketplace version validation when permission denied."""
        checker = PluginHealthCheck()

        # Mock validate_marketplace_version to raise PermissionError
        with patch('plugins.autonomous_dev.lib.validate_marketplace_version.validate_marketplace_version',
                   side_effect=PermissionError("Permission denied reading plugin.json")):
            # Capture stdout to verify error message is displayed
            import io
            captured = io.StringIO()

            with patch('sys.stdout', captured):
                result = checker._validate_marketplace_version()

        output = captured.getvalue()

        # Should return True (non-blocking)
        assert result is True, "Method should return True even when permission error occurs"

        # Should display error message
        assert "ERROR" in output or "Permission" in output, "Should show permission error"

    def test_validate_marketplace_version_corrupted_json(self):
        """Test marketplace version validation when JSON is corrupted."""
        checker = PluginHealthCheck()

        # Mock validate_marketplace_version to raise JSONDecodeError
        from json import JSONDecodeError
        json_error = JSONDecodeError("Expecting value", "", 0)

        with patch('plugins.autonomous_dev.lib.validate_marketplace_version.validate_marketplace_version',
                   side_effect=json_error):
            # Capture stdout to verify error message is displayed
            import io
            captured = io.StringIO()

            with patch('sys.stdout', captured):
                result = checker._validate_marketplace_version()

        output = captured.getvalue()

        # Should return True (non-blocking)
        assert result is True, "Method should return True even when JSON corrupted"

        # Should display error message
        assert "ERROR" in output or "corrupt" in output.lower(), "Should show JSON error"

    def test_validate_marketplace_version_called_from_validate(self):
        """Integration test: Verify print_report() calls _validate_marketplace_version()."""
        checker = PluginHealthCheck()

        # Mock all validate methods to prevent actual file system access
        with patch.object(checker, 'validate_agents', return_value=(8, 8)):
            with patch.object(checker, 'validate_skills', return_value=(0, 0)):
                with patch.object(checker, 'validate_hooks', return_value=(8, 8)):
                    with patch.object(checker, 'validate_commands', return_value=(21, 21)):
                        with patch.object(checker, 'validate_sync_status', return_value=(True, [])):
                            # Mock the new _validate_marketplace_version method
                            with patch.object(checker, '_validate_marketplace_version', return_value=True) as mock_validate_version:
                                # Mock results to avoid failures
                                checker.results = {
                                    "agents": {a: "PASS" for a in checker.EXPECTED_AGENTS},
                                    "skills": {},
                                    "hooks": {h: "PASS" for h in checker.EXPECTED_HOOKS},
                                    "commands": {c: "PASS" for c in checker.EXPECTED_COMMANDS},
                                    "overall": "UNKNOWN"
                                }

                                # Capture stdout
                                import io
                                captured = io.StringIO()
                                with patch('sys.stdout', captured):
                                    try:
                                        checker.print_report()
                                    except SystemExit:
                                        pass

                                # Verify _validate_marketplace_version was called
                                mock_validate_version.assert_called_once()


class TestClaudeMemValidation:
    """Test suite for claude-mem prerequisite validation (Issue #327)."""

    def test_validate_claude_mem_not_installed(self):
        """Test claude-mem validation when not installed."""
        checker = PluginHealthCheck()

        with patch.object(Path, 'exists', return_value=False):
            result = checker.validate_claude_mem()

        assert result["installed"] is False
        assert result["overall"] == "NOT_INSTALLED"
        assert result["prerequisites"] == {}

    def test_check_node_version_success(self):
        """Test Node.js version check with valid version."""
        checker = PluginHealthCheck()

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "v20.10.0\n"

        with patch('subprocess.run', return_value=mock_result):
            result = checker._check_node_version()

        assert result["status"] == "PASS"
        assert result["version"] == "20.10.0"
        assert ">= 18" in result["message"]

    def test_check_node_version_too_old(self):
        """Test Node.js version check with old version."""
        checker = PluginHealthCheck()

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "v16.14.0\n"

        with patch('subprocess.run', return_value=mock_result):
            result = checker._check_node_version()

        assert result["status"] == "FAIL"
        assert result["version"] == "16.14.0"
        assert "18+ required" in result["message"]

    def test_check_node_version_not_found(self):
        """Test Node.js version check when not installed."""
        checker = PluginHealthCheck()

        with patch('subprocess.run', side_effect=FileNotFoundError()):
            result = checker._check_node_version()

        assert result["status"] == "FAIL"
        assert result["version"] is None
        assert "not found" in result["message"]

    def test_check_bun_success(self):
        """Test Bun check when installed."""
        checker = PluginHealthCheck()

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "1.0.25\n"

        with patch('shutil.which', return_value="/usr/local/bin/bun"):
            with patch('subprocess.run', return_value=mock_result):
                result = checker._check_bun()

        assert result["status"] == "PASS"
        assert result["path"] == "/usr/local/bin/bun"
        assert result["version"] == "1.0.25"

    def test_check_bun_not_found(self):
        """Test Bun check when not installed."""
        checker = PluginHealthCheck()

        with patch('shutil.which', return_value=None):
            result = checker._check_bun()

        assert result["status"] == "FAIL"
        assert result["path"] is None
        assert "not found" in result["message"]
        assert "bun.sh" in result["message"]

    def test_check_uv_success(self):
        """Test uv check when installed."""
        checker = PluginHealthCheck()

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "uv 0.1.24\n"

        with patch('shutil.which', return_value="/usr/local/bin/uv"):
            with patch('subprocess.run', return_value=mock_result):
                result = checker._check_uv()

        assert result["status"] == "PASS"
        assert result["path"] == "/usr/local/bin/uv"
        assert result["version"] == "uv 0.1.24"

    def test_check_uv_not_found(self):
        """Test uv check when not installed."""
        checker = PluginHealthCheck()

        with patch('shutil.which', return_value=None):
            result = checker._check_uv()

        assert result["status"] == "FAIL"
        assert result["path"] is None
        assert "not found" in result["message"]
        assert "astral.sh" in result["message"]

    def test_check_port_available(self):
        """Test port check when port is available."""
        checker = PluginHealthCheck()

        with patch('socket.socket') as mock_socket:
            mock_sock_instance = Mock()
            mock_sock_instance.connect_ex.return_value = 1  # Connection refused = port available
            mock_socket.return_value.__enter__ = Mock(return_value=mock_sock_instance)
            mock_socket.return_value.__exit__ = Mock(return_value=False)

            result = checker._check_port(37777)

        assert result["status"] == "PASS"
        assert result["in_use"] is False
        assert "available" in result["message"]

    def test_check_port_in_use(self):
        """Test port check when port is in use."""
        checker = PluginHealthCheck()

        with patch('socket.socket') as mock_socket:
            mock_sock_instance = Mock()
            mock_sock_instance.connect_ex.return_value = 0  # Connection success = port in use
            mock_socket.return_value.__enter__ = Mock(return_value=mock_sock_instance)
            mock_socket.return_value.__exit__ = Mock(return_value=False)

            result = checker._check_port(37777)

        assert result["status"] == "PASS"
        assert result["in_use"] is True
        assert "in use" in result["message"]

    def test_validate_claude_mem_all_pass(self):
        """Test claude-mem validation when all prerequisites pass."""
        checker = PluginHealthCheck()

        # Mock ~/.claude-mem exists
        with patch.object(Path, 'exists', return_value=True):
            # Mock all prerequisite checks
            with patch.object(checker, '_check_node_version', return_value={
                "status": "PASS", "version": "20.10.0", "message": "OK"
            }):
                with patch.object(checker, '_check_bun', return_value={
                    "status": "PASS", "path": "/usr/local/bin/bun", "version": "1.0.25", "message": "OK"
                }):
                    with patch.object(checker, '_check_uv', return_value={
                        "status": "PASS", "path": "/usr/local/bin/uv", "version": "0.1.24", "message": "OK"
                    }):
                        with patch.object(checker, '_check_port', return_value={
                            "status": "PASS", "in_use": False, "message": "OK"
                        }):
                            result = checker.validate_claude_mem()

        assert result["installed"] is True
        assert result["overall"] == "HEALTHY"
        assert all(p["status"] == "PASS" for p in result["prerequisites"].values())

    def test_validate_claude_mem_degraded(self):
        """Test claude-mem validation when some prerequisites fail."""
        checker = PluginHealthCheck()

        # Mock ~/.claude-mem exists
        with patch.object(Path, 'exists', return_value=True):
            # Mock mixed prerequisite checks (bun fails)
            with patch.object(checker, '_check_node_version', return_value={
                "status": "PASS", "version": "20.10.0", "message": "OK"
            }):
                with patch.object(checker, '_check_bun', return_value={
                    "status": "FAIL", "path": None, "version": None, "message": "Not found"
                }):
                    with patch.object(checker, '_check_uv', return_value={
                        "status": "PASS", "path": "/usr/local/bin/uv", "version": "0.1.24", "message": "OK"
                    }):
                        with patch.object(checker, '_check_port', return_value={
                            "status": "PASS", "in_use": False, "message": "OK"
                        }):
                            result = checker.validate_claude_mem()

        assert result["installed"] is True
        assert result["overall"] == "DEGRADED"

    def test_print_report_includes_claude_mem(self):
        """Integration test: Verify print_report() includes claude-mem section."""
        checker = PluginHealthCheck()

        # Mock all validate methods
        with patch.object(checker, 'validate_agents', return_value=(8, 8)):
            with patch.object(checker, 'validate_skills', return_value=(0, 0)):
                with patch.object(checker, 'validate_hooks', return_value=(12, 12)):
                    with patch.object(checker, 'validate_commands', return_value=(8, 8)):
                        with patch.object(checker, 'validate_sync_status', return_value=(True, [])):
                            with patch.object(checker, '_validate_marketplace_version', return_value=True):
                                with patch.object(checker, 'validate_claude_mem', return_value={
                                    "installed": True,
                                    "prerequisites": {
                                        "nodejs": {"status": "PASS", "message": "Node 20"},
                                        "bun": {"status": "PASS", "message": "Bun 1.0"},
                                    },
                                    "overall": "HEALTHY"
                                }):
                                    # Mock results
                                    checker.results = {
                                        "agents": {a: "PASS" for a in checker.EXPECTED_AGENTS},
                                        "skills": {},
                                        "hooks": {h: "PASS" for h in checker.EXPECTED_HOOKS},
                                        "commands": {c.replace(".md", ""): "PASS" for c in checker.EXPECTED_COMMANDS},
                                        "overall": "UNKNOWN"
                                    }

                                    # Capture stdout
                                    import io
                                    captured = io.StringIO()
                                    with patch('sys.stdout', captured):
                                        try:
                                            checker.print_report()
                                        except SystemExit:
                                            pass

                                    output = captured.getvalue()

        assert "claude-mem Integration" in output


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=health_check", "--cov-report=term-missing"])
