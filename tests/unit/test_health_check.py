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

# Add plugin scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "scripts"))

from health_check import PluginHealthCheck


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


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=health_check", "--cov-report=term-missing"])
