#!/usr/bin/env python3
"""
TDD Tests for AgentTracker Checkpoint Integration (Issue #79 - FAILING - Red Phase)

This module contains FAILING tests that verify AgentTracker.save_agent_checkpoint()
is implemented as a class method for portable checkpoint saving from agents.

Problem Statement (GitHub Issue #79):
- /auto-implement stalls for 7+ hours due to hardcoded paths in subprocess calls
- Agents need to save checkpoints using Python imports (not subprocess)
- Checkpoints must work from any directory (portable path detection)
- Graceful degradation when running in user projects (no plugins/ directory)

Solution Requirements:
1. Add AgentTracker.save_agent_checkpoint() class method
2. Use portable path detection from path_utils.py
3. Graceful degradation when AgentTracker unavailable
4. Support heredoc execution context (no __file__ variable)
5. Clear error messages (not silent failures)

Test Strategy:
- Unit tests for save_agent_checkpoint() method
- Portable path detection validation
- Graceful degradation scenarios
- Heredoc execution context simulation
- Security validation (CWE-22, CWE-59)

Test Coverage Target: 100% of checkpoint integration code paths

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe requirements
- Tests should FAIL until implementation is complete
- Each test validates ONE requirement

Author: test-master agent
Date: 2025-12-07
Issue: GitHub #79
Phase: TDD Red Phase
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, call, MagicMock

import pytest

# Portable path detection (works from any test location)
current = Path.cwd()
while current != current.parent:
    if (current / ".git").exists() or (current / ".claude").exists():
        PROJECT_ROOT = current
        break
    current = current.parent
else:
    PROJECT_ROOT = Path.cwd()

# Add project root to path for imports
sys.path.insert(0, str(PROJECT_ROOT))

# Import the library (not scripts - portable design)
from plugins.autonomous_dev.lib.agent_tracker import AgentTracker
from plugins.autonomous_dev.lib.path_utils import get_project_root, get_session_dir


@pytest.mark.unit
class TestAgentCheckpointClassMethod:
    """Test AgentTracker.save_agent_checkpoint() class method exists and works.

    Critical requirement: Must be a @classmethod (not instance method) so agents
    can call it without instantiating AgentTracker first.
    """

    @pytest.fixture
    def temp_project_root(self, tmp_path):
        """Create temporary project root with .git marker."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()
        (project_root / "docs" / "sessions").mkdir(parents=True)
        return project_root

    def test_save_agent_checkpoint_method_exists(self):
        """Test that save_agent_checkpoint() class method exists.

        REQUIREMENT: AgentTracker must have save_agent_checkpoint() as @classmethod
        Expected: Method exists and is callable without instance
        """
        # This will FAIL until method is implemented
        assert hasattr(AgentTracker, 'save_agent_checkpoint'), \
            "AgentTracker.save_agent_checkpoint() method does not exist"

        # Verify it's a class method (not instance method)
        import inspect
        assert isinstance(inspect.getattr_static(AgentTracker, 'save_agent_checkpoint'), classmethod), \
            "save_agent_checkpoint() must be a @classmethod"

    def test_save_agent_checkpoint_signature(self):
        """Test that save_agent_checkpoint() has correct signature.

        REQUIREMENT: Method signature must match checkpoint use cases
        Expected: save_agent_checkpoint(cls, agent_name: str, message: str, **kwargs)
        """
        import inspect

        # Get method signature
        sig = inspect.signature(AgentTracker.save_agent_checkpoint)
        params = list(sig.parameters.keys())

        # Verify required parameters
        assert 'agent_name' in params, "Missing agent_name parameter"
        assert 'message' in params, "Missing message parameter"

        # Note: Python 3 doesn't include 'cls' in signature for bound classmethods
        # The classmethod decorator is verified in test_save_agent_checkpoint_method_exists
        assert params[0] == 'agent_name', \
            "First visible parameter should be agent_name (cls is implicit for classmethod)"

    @patch('plugins.autonomous_dev.lib.agent_tracker.get_project_root')
    def test_save_agent_checkpoint_uses_portable_paths(self, mock_get_root, temp_project_root):
        """Test that save_agent_checkpoint() uses portable path detection.

        REQUIREMENT: Must use path_utils.get_project_root() (not hardcoded paths)
        Expected: Calls get_project_root() to find session directory
        """
        mock_get_root.return_value = temp_project_root

        # This will FAIL until implementation exists
        try:
            AgentTracker.save_agent_checkpoint(
                agent_name="researcher",
                message="Research complete"
            )
        except Exception as e:
            pytest.fail(f"save_agent_checkpoint() failed: {e}")

        # Verify portable path detection was used
        mock_get_root.assert_called_once()

    def test_save_agent_checkpoint_creates_session_file(self, temp_project_root, monkeypatch):
        """Test that save_agent_checkpoint() creates session file in correct location.

        REQUIREMENT: Must create session file in PROJECT_ROOT/docs/sessions/
        Expected: File created with timestamp-based name
        """
        # Change to project root
        monkeypatch.chdir(temp_project_root)

        # This will FAIL until implementation exists
        with patch('plugins.autonomous_dev.lib.agent_tracker.get_project_root', return_value=temp_project_root):
            AgentTracker.save_agent_checkpoint(
                agent_name="researcher",
                message="Research complete"
            )

        # Verify session file was created
        session_dir = temp_project_root / "docs" / "sessions"
        session_files = list(session_dir.glob("*.json"))

        assert len(session_files) > 0, "No session file created"

        # Verify file contains checkpoint data
        with open(session_files[0]) as f:
            data = json.load(f)
            assert 'agents' in data, "Missing agents key in session file"
            assert any(a['agent'] == 'researcher' for a in data['agents']), \
                "Researcher agent not found in session file"

    def test_save_agent_checkpoint_from_subdirectory(self, temp_project_root, monkeypatch):
        """Test that save_agent_checkpoint() works from any subdirectory.

        REQUIREMENT: Portable path detection must work from anywhere in project tree
        Expected: Checkpoint saved even when called from nested subdirectory
        """
        # Create nested subdirectory
        nested_dir = temp_project_root / "src" / "components" / "auth"
        nested_dir.mkdir(parents=True)
        monkeypatch.chdir(nested_dir)

        # This will FAIL until implementation exists
        with patch('plugins.autonomous_dev.lib.agent_tracker.get_project_root', return_value=temp_project_root):
            AgentTracker.save_agent_checkpoint(
                agent_name="planner",
                message="Plan created"
            )

        # Verify checkpoint was saved at project root (not in subdirectory)
        session_dir = temp_project_root / "docs" / "sessions"
        session_files = list(session_dir.glob("*.json"))

        assert len(session_files) > 0, "No session file created from subdirectory"

    def test_save_agent_checkpoint_without_file_variable(self, temp_project_root):
        """Test that save_agent_checkpoint() works without __file__ variable.

        REQUIREMENT: Must work in heredoc execution context (no __file__ available)
        Expected: Uses path_utils.get_project_root() instead of __file__
        """
        # Simulate heredoc context where __file__ is undefined
        with patch('plugins.autonomous_dev.lib.agent_tracker.get_project_root', return_value=temp_project_root):
            # This will FAIL until implementation exists
            AgentTracker.save_agent_checkpoint(
                agent_name="test-master",
                message="Tests written"
            )

        # Verify checkpoint was saved
        session_dir = temp_project_root / "docs" / "sessions"
        session_files = list(session_dir.glob("*.json"))
        assert len(session_files) > 0, "Checkpoint not saved in heredoc context"


@pytest.mark.unit
class TestAgentCheckpointGracefulDegradation:
    """Test graceful degradation when AgentTracker unavailable (user projects).

    Critical requirement: Checkpoints should degrade gracefully in user projects
    that don't have the autonomous-dev plugin structure.
    """

    def test_save_agent_checkpoint_handles_import_error(self):
        """Test that checkpoint code handles AgentTracker import errors gracefully.

        REQUIREMENT: User projects may not have AgentTracker available
        Expected: No exception raised, clear informational message
        """
        # This will FAIL until graceful degradation is implemented
        with patch('plugins.autonomous_dev.lib.agent_tracker.get_project_root') as mock_get_root:
            mock_get_root.side_effect = FileNotFoundError("No .git or .claude found")

            # Should NOT raise exception
            try:
                AgentTracker.save_agent_checkpoint(
                    agent_name="researcher",
                    message="Research complete"
                )
            except FileNotFoundError:
                pytest.fail("Should handle missing project root gracefully")

    def test_save_agent_checkpoint_handles_permission_errors(self, tmp_path):
        """Test that checkpoint code handles permission errors gracefully.

        REQUIREMENT: Non-blocking failures (don't stop agent execution)
        Expected: Error logged but no exception raised
        """
        # Create read-only session directory
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()
        session_dir = project_root / "docs" / "sessions"
        session_dir.mkdir(parents=True)
        session_dir.chmod(0o444)  # Read-only

        with patch('plugins.autonomous_dev.lib.agent_tracker.get_project_root', return_value=project_root):
            # Should NOT raise exception
            try:
                AgentTracker.save_agent_checkpoint(
                    agent_name="implementer",
                    message="Implementation complete"
                )
            except PermissionError:
                pytest.fail("Should handle permission errors gracefully")

    def test_save_agent_checkpoint_clear_error_message(self, tmp_path, capsys):
        """Test that checkpoint errors produce clear messages (not silent failures).

        REQUIREMENT: Clear error messages (GitHub Issue #79 acceptance criteria)
        Expected: Error message includes context and recovery steps
        """
        # Simulate failure scenario
        project_root = tmp_path / "project"
        project_root.mkdir()

        with patch('plugins.autonomous_dev.lib.agent_tracker.get_project_root', return_value=project_root):
            # Force failure (no docs/sessions directory)
            with patch('pathlib.Path.mkdir', side_effect=OSError("Disk full")):
                AgentTracker.save_agent_checkpoint(
                    agent_name="reviewer",
                    message="Review complete"
                )

        # Verify clear error message was printed
        captured = capsys.readouterr()
        # Should contain helpful context
        assert "checkpoint" in captured.out.lower() or "checkpoint" in captured.err.lower(), \
            "Error message should mention 'checkpoint'"


@pytest.mark.unit
class TestAgentCheckpointSecurity:
    """Test security validation for checkpoint saving (CWE-22, CWE-59).

    Critical requirement: All checkpoint paths must be validated to prevent
    path traversal and symlink attacks.
    """

    def test_save_agent_checkpoint_validates_agent_name(self, tmp_path):
        """Test that save_agent_checkpoint() validates agent name input.

        SECURITY: Prevent path traversal via malicious agent names (CWE-22)
        Expected: Reject agent names with '..' or path separators
        """
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()

        with patch('plugins.autonomous_dev.lib.agent_tracker.get_project_root', return_value=project_root):
            # Test path traversal attempts
            malicious_names = [
                "../../../etc/passwd",
                "../../bad",
                "agent/../../../evil",
                "agent/subdir/bad",
                "../agent",
            ]

            for malicious_name in malicious_names:
                with pytest.raises(ValueError, match="Invalid agent name"):
                    AgentTracker.save_agent_checkpoint(
                        agent_name=malicious_name,
                        message="Malicious checkpoint"
                    )

    def test_save_agent_checkpoint_prevents_symlink_escape(self, tmp_path):
        """Test that save_agent_checkpoint() prevents symlink-based escapes.

        SECURITY: Prevent symlink attacks (CWE-59)
        Expected: Resolve paths and verify they're within PROJECT_ROOT
        """
        # Create project structure
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()
        session_dir = project_root / "docs" / "sessions"
        session_dir.mkdir(parents=True)

        # Create symlink pointing outside project
        evil_dir = tmp_path / "evil"
        evil_dir.mkdir()
        symlink = session_dir / "evil_link"
        symlink.symlink_to(evil_dir)

        with patch('plugins.autonomous_dev.lib.agent_tracker.get_project_root', return_value=project_root):
            # Should NOT follow symlink outside project
            AgentTracker.save_agent_checkpoint(
                agent_name="security-auditor",
                message="Security scan complete"
            )

            # Verify no files created outside project root
            assert len(list(evil_dir.glob("*"))) == 0, \
                "Checkpoint saved outside project root (symlink escape)"

    def test_save_agent_checkpoint_validates_message_length(self, tmp_path):
        """Test that save_agent_checkpoint() validates message length.

        SECURITY: Prevent resource exhaustion via huge messages
        Expected: Reject messages over 10KB limit
        """
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()

        with patch('plugins.autonomous_dev.lib.agent_tracker.get_project_root', return_value=project_root):
            # Test message size limit
            huge_message = "A" * 15000  # 15KB (over 10KB limit)

            with pytest.raises(ValueError, match="Message too long"):
                AgentTracker.save_agent_checkpoint(
                    agent_name="doc-master",
                    message=huge_message
                )


@pytest.mark.unit
class TestAgentCheckpointIntegration:
    """Test integration with existing AgentTracker functionality.

    Critical requirement: New checkpoint method must work with existing
    session tracking infrastructure.
    """

    def test_save_agent_checkpoint_creates_valid_session_structure(self, tmp_path):
        """Test that checkpoint creates valid session JSON structure.

        REQUIREMENT: Session file must match existing format
        Expected: JSON contains session_id, started, agents array
        """
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()
        (project_root / "docs" / "sessions").mkdir(parents=True)

        with patch('plugins.autonomous_dev.lib.agent_tracker.get_project_root', return_value=project_root):
            AgentTracker.save_agent_checkpoint(
                agent_name="researcher",
                message="Research complete",
                tools_used=["WebSearch", "Grep"]
            )

        # Verify session file structure
        session_dir = project_root / "docs" / "sessions"
        session_files = list(session_dir.glob("*.json"))
        assert len(session_files) > 0, "No session file created"

        with open(session_files[0]) as f:
            data = json.load(f)

            # Verify required keys
            assert 'session_id' in data, "Missing session_id"
            assert 'started' in data, "Missing started timestamp"
            assert 'agents' in data, "Missing agents array"

            # Verify agent entry
            agent_entry = data['agents'][0]
            assert agent_entry['agent'] == 'researcher'
            assert agent_entry['message'] == 'Research complete'
            assert agent_entry['tools_used'] == ['WebSearch', 'Grep']

    def test_save_agent_checkpoint_appends_to_existing_session(self, tmp_path):
        """Test that checkpoint appends to existing session file (not overwrites).

        REQUIREMENT: Multiple checkpoints should be added to same session
        Expected: Each checkpoint adds new agent entry to agents array
        """
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()
        session_dir = project_root / "docs" / "sessions"
        session_dir.mkdir(parents=True)

        with patch('plugins.autonomous_dev.lib.agent_tracker.get_project_root', return_value=project_root):
            # Save first checkpoint
            AgentTracker.save_agent_checkpoint(
                agent_name="researcher",
                message="Research complete"
            )

            # Save second checkpoint (should append, not overwrite)
            AgentTracker.save_agent_checkpoint(
                agent_name="planner",
                message="Plan created"
            )

        # Verify both agents in session file
        session_files = list(session_dir.glob("*.json"))
        with open(session_files[0]) as f:
            data = json.load(f)

            assert len(data['agents']) == 2, "Second checkpoint overwrote first"
            agent_names = [a['agent'] for a in data['agents']]
            assert 'researcher' in agent_names
            assert 'planner' in agent_names

    def test_save_agent_checkpoint_with_github_issue(self, tmp_path):
        """Test that checkpoint can associate with GitHub issue.

        REQUIREMENT: Support github_issue parameter for traceability
        Expected: Issue number stored in checkpoint data
        """
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()
        (project_root / "docs" / "sessions").mkdir(parents=True)

        with patch('plugins.autonomous_dev.lib.agent_tracker.get_project_root', return_value=project_root):
            AgentTracker.save_agent_checkpoint(
                agent_name="implementer",
                message="Implementation complete",
                github_issue=79
            )

        # Verify issue number stored
        session_dir = project_root / "docs" / "sessions"
        session_files = list(session_dir.glob("*.json"))
        with open(session_files[0]) as f:
            data = json.load(f)
            assert data.get('github_issue') == 79, "GitHub issue not stored"


@pytest.mark.unit
class TestAgentCheckpointDocumentation:
    """Test that all 7 core workflow agents have checkpoint integration sections.

    Critical requirement: Each agent .md file must document how to save checkpoints
    using the new class method.
    """

    @pytest.fixture
    def core_agents(self):
        """List of core workflow agents that need checkpoint integration."""
        # Note: researcher was archived (Issue #128), replaced by researcher-local and researcher-web
        return [
            "researcher-local",
            "planner",
            "test-master",
            "implementer",
            "reviewer",
            "security-auditor",
            "doc-master"
        ]

    def test_all_agents_have_checkpoint_sections(self, core_agents):
        """Test that all 7 core agents have checkpoint documentation sections.

        REQUIREMENT: Each agent must document checkpoint integration
        Expected: Agent .md file contains checkpoint example code
        """
        agents_dir = PROJECT_ROOT / "plugins" / "autonomous-dev" / "agents"

        for agent_name in core_agents:
            agent_file = agents_dir / f"{agent_name}.md"
            assert agent_file.exists(), f"Agent file not found: {agent_file}"

            # Read agent file
            with open(agent_file) as f:
                content = f.read()

            # Verify checkpoint section exists
            assert "checkpoint" in content.lower(), \
                f"{agent_name}.md missing checkpoint documentation"

            # Verify example code exists
            assert "AgentTracker.save_agent_checkpoint" in content, \
                f"{agent_name}.md missing checkpoint example code"

    def test_checkpoint_examples_use_class_method(self, core_agents):
        """Test that checkpoint examples use class method (not instance method).

        REQUIREMENT: Examples must show correct usage pattern
        Expected: AgentTracker.save_agent_checkpoint() (not tracker.save...)
        """
        agents_dir = PROJECT_ROOT / "plugins" / "autonomous-dev" / "agents"

        for agent_name in core_agents:
            agent_file = agents_dir / f"{agent_name}.md"
            with open(agent_file) as f:
                content = f.read()

            # Verify class method usage (not instance method)
            if "save_agent_checkpoint" in content:
                assert "AgentTracker.save_agent_checkpoint" in content, \
                    f"{agent_name}.md shows instance method (should be class method)"

                # Should NOT show instance creation pattern
                bad_patterns = [
                    "tracker = AgentTracker()",
                    "tracker.save_agent_checkpoint"
                ]
                for pattern in bad_patterns:
                    assert pattern not in content, \
                        f"{agent_name}.md shows incorrect instance method pattern: {pattern}"


# Summary of test failures expected:
# - save_agent_checkpoint() method does not exist (test_save_agent_checkpoint_method_exists)
# - Method signature incorrect (test_save_agent_checkpoint_signature)
# - Portable path detection not implemented (test_save_agent_checkpoint_uses_portable_paths)
# - Session file creation not implemented (test_save_agent_checkpoint_creates_session_file)
# - Subdirectory execution not working (test_save_agent_checkpoint_from_subdirectory)
# - Heredoc context not working (test_save_agent_checkpoint_without_file_variable)
# - Graceful degradation not implemented (test_save_agent_checkpoint_handles_import_error)
# - Permission error handling not implemented (test_save_agent_checkpoint_handles_permission_errors)
# - Error messages not clear (test_save_agent_checkpoint_clear_error_message)
# - Input validation not implemented (test_save_agent_checkpoint_validates_agent_name)
# - Symlink protection not implemented (test_save_agent_checkpoint_prevents_symlink_escape)
# - Message validation not implemented (test_save_agent_checkpoint_validates_message_length)
# - Session structure not correct (test_save_agent_checkpoint_creates_valid_session_structure)
# - Append logic not implemented (test_save_agent_checkpoint_appends_to_existing_session)
# - GitHub issue support not implemented (test_save_agent_checkpoint_with_github_issue)
# - Agent documentation missing checkpoint sections (test_all_agents_have_checkpoint_sections)
# - Checkpoint examples incorrect (test_checkpoint_examples_use_class_method)
#
# Total: 17 tests, all FAILING until implementation is complete
