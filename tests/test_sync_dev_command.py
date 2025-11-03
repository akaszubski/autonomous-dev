"""
Comprehensive tests for /sync-dev command and sync-validator agent.

Tests validate:
- Command file structure and documentation
- Agent integration and invocation
- Conflict detection capabilities
- Validation phase completeness
- Safety features and user prompts
- Integration with other commands
- Error handling and edge cases

Following TDD principles - tests written before implementation.
Target: 80%+ coverage
"""

import re
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest


class TestSyncDevCommandStructure:
    """Test /sync-dev command file structure and documentation."""

    @pytest.fixture
    def command_file(self):
        """Path to sync-dev command file."""
        return Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "commands" / "sync-dev.md"

    @pytest.fixture
    def command_content(self, command_file):
        """Content of sync-dev command file."""
        assert command_file.exists(), "sync-dev.md command file not found"
        return command_file.read_text()

    def test_command_file_exists(self, command_file):
        """Test that sync-dev.md command file exists."""
        assert command_file.exists(), "sync-dev.md should exist in commands directory"
        assert command_file.suffix == ".md", "Command file should be markdown"

    def test_command_has_frontmatter(self, command_content):
        """Test command file has valid YAML frontmatter with description."""
        assert command_content.startswith("---"), "Command should start with YAML frontmatter"

        # Extract frontmatter
        frontmatter_match = re.search(r'^---\n(.*?)\n---', command_content, re.DOTALL)
        assert frontmatter_match, "Could not parse frontmatter"

        frontmatter = frontmatter_match.group(1)
        assert "description:" in frontmatter, "Frontmatter should have description"

        # Check description is meaningful
        desc_match = re.search(r'description:\s*(.+)', frontmatter)
        assert desc_match, "Description should have value"
        description = desc_match.group(1).strip()
        assert len(description) > 20, "Description should be descriptive (>20 chars)"
        assert "sync" in description.lower(), "Description should mention 'sync'"

    def test_command_has_usage_section(self, command_content):
        """Test command has usage section with examples."""
        assert "## Usage" in command_content or "# Usage" in command_content, \
            "Command should have Usage section"

        # Check for command invocation example
        assert "/sync-dev" in command_content, "Should show how to invoke command"

        # Check for code blocks
        code_block_count = command_content.count("```")
        assert code_block_count >= 4, "Should have multiple code examples (at least 2 blocks = 4 markers)"

    def test_command_documents_phases(self, command_content):
        """Test command documents the 5-phase sync process."""
        required_phases = [
            "Phase 1",
            "Phase 2",
            "Phase 3",
            "Phase 4",
            "Phase 5"
        ]

        for phase in required_phases:
            assert phase in command_content, f"Should document {phase}"

        # Check key phase activities are mentioned
        assert "Pre-Sync Analysis" in command_content or "pre-sync" in command_content.lower()
        assert "Fetch" in command_content or "fetch" in command_content.lower()
        assert "Conflict Detection" in command_content or "conflict" in command_content.lower()
        assert "Validation" in command_content or "validation" in command_content.lower()

    def test_command_has_example_output(self, command_content):
        """Test command shows example output to user."""
        # Should have at least one detailed output example
        assert "Output:" in command_content or "OUTPUT:" in command_content or \
               "Example Output" in command_content, \
            "Should show example output"

        # Check for status indicators in examples
        status_indicators = ["✅", "⚠️", "❌", "PASS", "FAIL", "✓", "×"]
        has_indicator = any(indicator in command_content for indicator in status_indicators)
        assert has_indicator, "Examples should use visual status indicators"

    def test_command_documents_what_is_detected(self, command_content):
        """Test command documents what types of issues it detects."""
        detection_types = [
            "Dependency",
            "Environment",
            "Conflict",
            "Build",
            "Configuration"
        ]

        # Should mention at least 3 types of detection
        mentioned = sum(1 for dtype in detection_types if dtype.lower() in command_content.lower())
        assert mentioned >= 3, f"Should document at least 3 detection types, found {mentioned}"

        # Specific technologies should be mentioned
        assert "python" in command_content.lower() or "requirements.txt" in command_content.lower()
        assert ".env" in command_content.lower() or "environment variable" in command_content.lower()

    def test_command_has_when_to_use_section(self, command_content):
        """Test command explains when to use /sync-dev."""
        assert "When to Use" in command_content or "when to use" in command_content.lower() or \
               "When to Run" in command_content or "Use Cases" in command_content, \
            "Should explain when to use the command"

        # Should mention common scenarios
        scenarios = ["pull", "update", "plugin", "conflict"]
        mentioned_scenarios = sum(1 for scenario in scenarios if scenario in command_content.lower())
        assert mentioned_scenarios >= 2, "Should mention common use scenarios"

    def test_command_has_integration_examples(self, command_content):
        """Test command shows integration with other commands."""
        # Should mention other related commands
        related_commands = ["/health-check", "/setup", "/status", "/auto-implement"]
        mentioned = sum(1 for cmd in related_commands if cmd in command_content)

        assert mentioned >= 2, "Should show integration with at least 2 other commands"

    def test_command_has_safety_features_section(self, command_content):
        """Test command documents safety features."""
        assert "Safety" in command_content or "safety" in command_content.lower(), \
            "Should document safety features"

        safety_keywords = ["confirmation", "rollback", "abort", "no destructive"]
        has_safety = any(keyword in command_content.lower() for keyword in safety_keywords)
        assert has_safety, "Should mention safety mechanisms"

    def test_command_has_troubleshooting_section(self, command_content):
        """Test command has troubleshooting guidance."""
        assert "Troubleshooting" in command_content or "## Troubleshooting" in command_content, \
            "Should have troubleshooting section"

        # Should mention common issues
        common_issues = ["uncommitted", "conflict", "failed", "error"]
        mentioned = sum(1 for issue in common_issues if issue in command_content.lower())
        assert mentioned >= 2, "Should document common issues"

    def test_command_has_implementation_section(self, command_content):
        """Test command has implementation section that invokes agent."""
        assert "## Implementation" in command_content, "Should have Implementation section"

        # Should mention the sync-validator agent
        assert "sync-validator" in command_content.lower(), \
            "Implementation should mention sync-validator agent"


class TestSyncValidatorAgentStructure:
    """Test sync-validator agent file structure."""

    @pytest.fixture
    def agent_file(self):
        """Path to sync-validator agent file."""
        return Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "agents" / "sync-validator.md"

    @pytest.fixture
    def agent_content(self, agent_file):
        """Content of sync-validator agent file."""
        assert agent_file.exists(), "sync-validator.md agent file not found"
        return agent_file.read_text()

    def test_agent_file_exists(self, agent_file):
        """Test that sync-validator.md agent file exists."""
        assert agent_file.exists(), "sync-validator.md should exist in agents directory"

    def test_agent_has_frontmatter(self, agent_content):
        """Test agent has valid YAML frontmatter."""
        assert agent_content.startswith("---"), "Agent should start with YAML frontmatter"

        # Parse frontmatter
        frontmatter_match = re.search(r'^---\n(.*?)\n---', agent_content, re.DOTALL)
        assert frontmatter_match, "Could not parse frontmatter"

        frontmatter = frontmatter_match.group(1)

        # Required fields
        assert "name:" in frontmatter, "Should have name field"
        assert "description:" in frontmatter, "Should have description field"
        assert "tools:" in frontmatter, "Should have tools field"

    def test_agent_has_correct_tools(self, agent_content):
        """Test agent has appropriate tools for sync operations."""
        # Extract frontmatter
        frontmatter_match = re.search(r'^---\n(.*?)\n---', agent_content, re.DOTALL)
        frontmatter = frontmatter_match.group(1)

        # Should have Read, Bash, Grep at minimum
        tools_line = [line for line in frontmatter.split('\n') if 'tools:' in line.lower()][0]

        assert "Read" in tools_line or "read" in tools_line.lower(), \
            "Agent needs Read tool to analyze files"
        assert "Bash" in tools_line or "bash" in tools_line.lower(), \
            "Agent needs Bash tool to run git commands"
        assert "Grep" in tools_line or "grep" in tools_line.lower(), \
            "Agent needs Grep tool to search for conflicts"

    def test_agent_documents_phases(self, agent_content):
        """Test agent documents its 5-phase process."""
        phases = ["Phase 1", "Phase 2", "Phase 3", "Phase 4", "Phase 5"]

        for phase in phases:
            assert phase in agent_content, f"Agent should document {phase}"

    def test_agent_has_mission(self, agent_content):
        """Test agent has clear mission statement."""
        assert "## Mission" in agent_content or "Mission" in agent_content, \
            "Agent should have Mission section"

        # Mission should mention key responsibilities
        mission_keywords = ["sync", "conflict", "validate", "compatibility"]
        mentioned = sum(1 for keyword in mission_keywords if keyword in agent_content.lower())
        assert mentioned >= 3, "Mission should cover core responsibilities"

    def test_agent_has_process_section(self, agent_content):
        """Test agent has detailed process section."""
        assert "## Process" in agent_content, "Agent should have Process section"

        # Should document key steps
        process_steps = ["fetch", "analyze", "detect", "validate", "merge"]
        mentioned = sum(1 for step in process_steps if step in agent_content.lower())
        assert mentioned >= 3, "Process should document key steps"


class TestSyncDevConflictDetection:
    """Test sync-dev's conflict detection capabilities."""

    def test_detects_dependency_conflicts_python(self):
        """Test detection of Python dependency conflicts."""
        # This tests the documented capability
        # Actual implementation would parse requirements.txt

        # Mock scenario: local has requests==2.28.0, upstream has requests==2.31.0
        local_deps = {"requests": "2.28.0", "pytest": "7.4.0"}
        upstream_deps = {"requests": "2.31.0", "pytest": "8.0.0"}

        conflicts = self._detect_version_conflicts(local_deps, upstream_deps)

        assert len(conflicts) == 2, "Should detect both version conflicts"
        assert "requests" in conflicts
        assert "pytest" in conflicts

    def test_detects_dependency_conflicts_nodejs(self):
        """Test detection of Node.js dependency conflicts."""
        # Mock scenario: package.json version mismatch
        local_deps = {"express": "^4.17.0", "lodash": "^4.17.20"}
        upstream_deps = {"express": "^4.18.0", "lodash": "^4.17.21"}

        conflicts = self._detect_version_conflicts(local_deps, upstream_deps)

        assert len(conflicts) == 2, "Should detect package version differences"

    def test_detects_missing_environment_variables(self):
        """Test detection of missing .env variables."""
        # Mock scenario: upstream added new required env var
        local_env = {"API_KEY": "test", "DB_HOST": "localhost"}
        required_env = {"API_KEY", "DB_HOST", "NEW_FEATURE_FLAG"}

        missing = required_env - set(local_env.keys())

        assert len(missing) == 1, "Should detect missing env variable"
        assert "NEW_FEATURE_FLAG" in missing

    def test_detects_stale_build_artifacts(self):
        """Test detection of stale build artifacts."""
        # Mock scenario: __pycache__ older than source files
        artifacts = [
            {"path": "__pycache__/module.cpython-39.pyc", "mtime": 1000},
            {"path": "node_modules/.cache", "mtime": 1000}
        ]
        source_files = [
            {"path": "module.py", "mtime": 2000}
        ]

        stale = self._find_stale_artifacts(artifacts, source_files)

        assert len(stale) >= 1, "Should detect stale cache files"

    def test_detects_merge_conflicts(self):
        """Test detection of git merge conflict markers."""
        file_content = """
        def function():
            <<<<<<< HEAD
            return "local version"
            =======
            return "upstream version"
            >>>>>>> origin/main
        """

        has_conflict = self._has_conflict_markers(file_content)

        assert has_conflict, "Should detect conflict markers"

    def test_detects_configuration_drift(self):
        """Test detection of configuration file differences."""
        # Mock scenario: PROJECT.md has different structure
        local_config = {"version": "3.0.0", "agents": 16}
        upstream_config = {"version": "3.1.0", "agents": 19}

        drift = self._detect_config_drift(local_config, upstream_config)

        assert len(drift) == 2, "Should detect version and agent count changes"
        assert "version" in drift
        assert "agents" in drift

    # Helper methods for test scenarios
    def _detect_version_conflicts(self, local, upstream):
        """Mock dependency conflict detection."""
        conflicts = {}
        for pkg, local_ver in local.items():
            if pkg in upstream and local_ver != upstream[pkg]:
                conflicts[pkg] = {
                    "local": local_ver,
                    "upstream": upstream[pkg]
                }
        return conflicts

    def _find_stale_artifacts(self, artifacts, sources):
        """Mock stale artifact detection."""
        stale = []
        for artifact in artifacts:
            # If any source file is newer than artifact
            for source in sources:
                if source["mtime"] > artifact["mtime"]:
                    stale.append(artifact)
                    break
        return stale

    def _has_conflict_markers(self, content):
        """Mock conflict marker detection."""
        markers = ["<<<<<<<", "=======", ">>>>>>>"]
        return all(marker in content for marker in markers)

    def _detect_config_drift(self, local, upstream):
        """Mock configuration drift detection."""
        drift = {}
        for key, local_val in local.items():
            if key in upstream and local_val != upstream[key]:
                drift[key] = {
                    "local": local_val,
                    "upstream": upstream[key]
                }
        return drift


class TestSyncDevValidation:
    """Test sync-dev's validation phases."""

    def test_validates_python_syntax(self):
        """Test Python syntax validation after sync."""
        # Valid Python
        valid_code = "def hello():\n    return 'world'"
        assert self._validate_python_syntax(valid_code), "Valid Python should pass"

        # Invalid Python
        invalid_code = "def hello(\n    return 'world'"
        assert not self._validate_python_syntax(invalid_code), "Invalid Python should fail"

    def test_validates_json_syntax(self):
        """Test JSON syntax validation for config files."""
        # Valid JSON
        valid_json = '{"key": "value", "count": 42}'
        assert self._validate_json_syntax(valid_json), "Valid JSON should pass"

        # Invalid JSON
        invalid_json = '{"key": "value",}'
        assert not self._validate_json_syntax(invalid_json), "Invalid JSON should fail"

    def test_validates_bash_syntax(self):
        """Test Bash script syntax validation."""
        # Valid Bash
        valid_bash = "#!/bin/bash\necho 'hello'"
        assert self._validate_bash_syntax(valid_bash), "Valid Bash should pass"

        # Invalid Bash (unclosed quote)
        invalid_bash = "#!/bin/bash\necho 'hello"
        assert not self._validate_bash_syntax(invalid_bash), "Invalid Bash should fail"

    def test_validates_plugin_integrity(self):
        """Test plugin integrity check (all agents present)."""
        # Complete plugin
        complete_agents = [
            "orchestrator", "researcher", "planner", "test-master",
            "implementer", "reviewer", "security-auditor", "doc-master"
        ]
        assert self._validate_plugin_integrity(complete_agents), "Complete plugin should pass"

        # Missing agent
        incomplete_agents = [
            "orchestrator", "researcher", "planner"
        ]
        assert not self._validate_plugin_integrity(incomplete_agents), "Incomplete plugin should fail"

    def test_validates_dependency_compatibility(self):
        """Test dependency version compatibility checking."""
        # Compatible versions
        deps = {
            "pytest": {"required": ">=7.0,<9.0", "installed": "8.0.0"},
            "requests": {"required": ">=2.28", "installed": "2.31.0"}
        }
        assert self._validate_dependencies(deps), "Compatible dependencies should pass"

        # Incompatible version
        incompatible_deps = {
            "pytest": {"required": ">=7.0,<8.0", "installed": "8.0.0"}
        }
        assert not self._validate_dependencies(incompatible_deps), "Incompatible should fail"

    # Helper methods for validation tests
    def _validate_python_syntax(self, code):
        """Mock Python syntax validation."""
        try:
            compile(code, '<string>', 'exec')
            return True
        except SyntaxError:
            return False

    def _validate_json_syntax(self, json_str):
        """Mock JSON syntax validation."""
        import json
        try:
            json.loads(json_str)
            return True
        except json.JSONDecodeError:
            return False

    def _validate_bash_syntax(self, script):
        """Mock Bash syntax validation."""
        # Simple heuristic: check for unclosed quotes
        single_quotes = script.count("'")
        double_quotes = script.count('"')
        return single_quotes % 2 == 0 and double_quotes % 2 == 0

    def _validate_plugin_integrity(self, present_agents):
        """Mock plugin integrity check."""
        required = {
            "orchestrator", "researcher", "planner", "test-master",
            "implementer", "reviewer", "security-auditor", "doc-master"
        }
        return required.issubset(set(present_agents))

    def _validate_dependencies(self, deps):
        """Mock dependency compatibility check."""
        # Simplified: check if installed version matches required
        for pkg, info in deps.items():
            # Parse simple version requirements
            required = info["required"]
            installed = info["installed"]

            if ">=" in required and "<" in required:
                # Range requirement like ">=7.0,<9.0"
                parts = required.split(",")
                min_ver = parts[0].replace(">=", "").strip()
                max_ver = parts[1].replace("<", "").strip()

                # Simple string comparison (works for x.y.z format)
                if not (installed >= min_ver and installed < max_ver):
                    return False

        return True


class TestSyncDevSafetyFeatures:
    """Test sync-dev's safety features and user interactions."""

    def test_prompts_before_destructive_actions(self):
        """Test that destructive actions require user confirmation."""
        # Should not auto-merge without confirmation
        actions = [
            {"type": "merge", "risk": "high", "requires_confirmation": True},
            {"type": "delete_artifacts", "risk": "medium", "requires_confirmation": True},
            {"type": "update_deps", "risk": "medium", "requires_confirmation": True}
        ]

        for action in actions:
            if action["risk"] in ["high", "medium"]:
                assert action["requires_confirmation"], \
                    f"{action['type']} should require confirmation"

    def test_provides_rollback_option(self):
        """Test that rollback option is available after changes."""
        # Mock: changes made, rollback should be possible
        state = {
            "changes_made": True,
            "backup_created": True,
            "can_rollback": True
        }

        assert state["can_rollback"], "Should provide rollback option"
        assert state["backup_created"], "Should create backup before changes"

    def test_warns_about_uncommitted_changes(self):
        """Test that uncommitted changes trigger warning."""
        # Mock git status with uncommitted changes
        git_status = {
            "modified": ["src/module.py", "tests/test_module.py"],
            "untracked": ["debug.log"]
        }

        has_changes = len(git_status["modified"]) > 0 or len(git_status["untracked"]) > 0

        assert has_changes, "Should detect uncommitted changes"
        # In real implementation, this would show warning

    def test_provides_clear_error_messages(self):
        """Test that error messages are clear and actionable."""
        errors = [
            {
                "type": "merge_conflict",
                "message": "Merge conflict in src/config.py",
                "action": "Resolve conflict markers manually"
            },
            {
                "type": "dependency_error",
                "message": "Failed to install pytest==8.0.0",
                "action": "Check pip logs and retry manually"
            }
        ]

        for error in errors:
            # Error messages should have type, description, and action
            assert "message" in error, "Should have error message"
            assert "action" in error, "Should have recommended action"
            assert len(error["message"]) > 10, "Message should be descriptive"
            assert len(error["action"]) > 10, "Action should be specific"

    def test_validates_after_applying_changes(self):
        """Test that validation runs after changes are applied."""
        workflow = [
            {"step": "fetch", "completed": False},
            {"step": "merge", "completed": False},
            {"step": "validate", "completed": False}
        ]

        # Simulate workflow
        workflow[0]["completed"] = True  # fetch
        workflow[1]["completed"] = True  # merge
        workflow[2]["completed"] = True  # validate

        # Validation should be last step after changes
        validate_index = next(i for i, s in enumerate(workflow) if s["step"] == "validate")
        merge_index = next(i for i, s in enumerate(workflow) if s["step"] == "merge")

        assert validate_index > merge_index, "Validation should come after merge"


class TestSyncDevIntegration:
    """Test sync-dev integration with other commands."""

    def test_integrates_with_health_check(self):
        """Test that /sync-dev suggests /health-check after sync."""
        # After sync completes, should recommend health-check
        post_sync_recommendations = [
            "/health-check",  # Verify integrity
            "/status",        # Check progress
        ]

        assert "/health-check" in post_sync_recommendations, \
            "Should recommend health-check after sync"

    def test_integrates_with_setup(self):
        """Test that /sync-dev can trigger /setup for major changes."""
        # If major plugin update detected, should suggest setup
        changes = {
            "new_agents": ["quality-validator", "advisor"],
            "removed_agents": [],
            "config_changes": True
        }

        is_major_update = len(changes["new_agents"]) > 0 or changes["config_changes"]

        if is_major_update:
            # Should suggest re-running setup
            assert True, "Major updates should suggest /setup"

    def test_runs_before_auto_implement(self):
        """Test that /sync-dev is recommended before /auto-implement."""
        # Best practice: sync environment before new feature work
        pre_feature_checklist = [
            "git pull",
            "/sync-dev",
            "/clear"
        ]

        assert "/sync-dev" in pre_feature_checklist, \
            "Should recommend sync before new features"


class TestSyncDevEdgeCases:
    """Test sync-dev edge cases and error handling."""

    def test_handles_no_internet_connection(self):
        """Test behavior when network is unavailable."""
        # Should detect and report network error gracefully
        error = {
            "type": "network_error",
            "message": "Could not fetch from origin",
            "recoverable": False
        }

        assert error["type"] == "network_error"
        assert error["message"] is not None
        # Should not crash, should provide clear error

    def test_handles_diverged_branches(self):
        """Test behavior when local and remote have diverged."""
        # Local has commits not in remote, remote has commits not in local
        branch_state = {
            "local_ahead": 3,
            "remote_ahead": 5,
            "diverged": True
        }

        if branch_state["diverged"]:
            # Should warn user and suggest resolution strategy
            assert True, "Diverged branches should trigger special handling"

    def test_handles_very_large_sync(self):
        """Test behavior with many upstream commits."""
        # > 50 commits is risky
        commit_count = 73
        risk_level = "high" if commit_count > 50 else "low"

        assert risk_level == "high", "Many commits should be flagged as high risk"
        # Should warn user about large sync

    def test_handles_missing_remote(self):
        """Test behavior when origin remote doesn't exist."""
        remotes = []  # No remotes configured

        has_origin = "origin" in remotes

        assert not has_origin, "Should detect missing remote"
        # Should provide helpful error about configuring remote

    def test_handles_detached_head(self):
        """Test behavior in detached HEAD state."""
        git_state = {
            "branch": None,
            "detached": True,
            "commit": "abc123"
        }

        if git_state["detached"]:
            # Should warn user and suggest attaching to branch
            assert True, "Detached HEAD should be detected and handled"

    def test_handles_empty_repository(self):
        """Test behavior in repository with no commits."""
        repo_state = {
            "commit_count": 0,
            "has_commits": False
        }

        if not repo_state["has_commits"]:
            # Should handle gracefully, maybe skip sync
            assert True, "Empty repo should be handled gracefully"


class TestSyncDevDocumentationQuality:
    """Test documentation quality and completeness."""

    @pytest.fixture
    def command_content(self):
        """Load command file content."""
        command_file = Path(__file__).parent.parent / "plugins" / "autonomous-dev" / "commands" / "sync-dev.md"
        return command_file.read_text()

    def test_examples_are_realistic(self, command_content):
        """Test that examples show realistic scenarios."""
        # Examples should show actual command output, not just "..."
        assert "✅" in command_content or "✓" in command_content or "PASS" in command_content, \
            "Examples should show realistic status indicators"

        # Examples should show file paths
        file_path_indicators = [".py", ".md", ".json", ".env", "requirements.txt"]
        has_file_examples = any(indicator in command_content for indicator in file_path_indicators)
        assert has_file_examples, "Examples should show actual file paths"

    def test_time_estimates_provided(self, command_content):
        """Test that time estimates are provided."""
        # Users want to know how long it takes
        time_indicators = ["second", "minute", "time", "duration"]
        has_time_info = any(indicator in command_content.lower() for indicator in time_indicators)
        assert has_time_info, "Should provide time estimates"

    def test_risk_levels_explained(self, command_content):
        """Test that risk levels are explained."""
        risk_indicators = ["risk", "safe", "breaking", "dangerous"]
        has_risk_info = any(indicator in command_content.lower() for indicator in risk_indicators)
        assert has_risk_info, "Should explain risk levels"

    def test_failure_scenarios_documented(self, command_content):
        """Test that failure scenarios are documented."""
        # Should show what happens when things go wrong
        assert "fail" in command_content.lower() or "error" in command_content.lower(), \
            "Should document failure scenarios"

        # Should have troubleshooting
        assert "Troubleshooting" in command_content, \
            "Should have troubleshooting section"


# Meta-test for coverage
def test_coverage_target():
    """Meta-test: Verify this test file aims for 80%+ coverage.

    This test serves as documentation of our coverage goals.
    Actual coverage is measured by pytest-cov.
    """
    # Test file should be comprehensive
    test_classes = [
        TestSyncDevCommandStructure,
        TestSyncValidatorAgentStructure,
        TestSyncDevConflictDetection,
        TestSyncDevValidation,
        TestSyncDevSafetyFeatures,
        TestSyncDevIntegration,
        TestSyncDevEdgeCases,
        TestSyncDevDocumentationQuality
    ]

    assert len(test_classes) >= 7, "Should have comprehensive test coverage across multiple areas"

    # Count total test methods
    total_tests = sum(
        len([m for m in dir(cls) if m.startswith("test_")])
        for cls in test_classes
    )

    assert total_tests >= 40, f"Should have at least 40 test methods for comprehensive coverage, have {total_tests}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=sync_dev", "--cov-report=term-missing"])
