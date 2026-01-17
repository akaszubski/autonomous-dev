"""
Unit tests for Issue #90: Add timeout to test-master and reduce pytest verbosity.

Tests verify:
1. auto-implement.md includes timeout parameter for test-master
2. test-master.md uses minimal pytest verbosity flags
3. Timeout value is reasonable (1200 seconds = 20 minutes)
4. Pytest flags reduce output significantly

NOTE: auto-implement.md is now deprecated - redirects to /implement (Issue #203)
"""

from pathlib import Path
import re
import pytest


@pytest.mark.skip(reason="auto-implement.md deprecated - redirects to /implement")
def test_auto_implement_has_timeout_for_test_master():
    """Verify auto-implement.md specifies timeout for test-master agent."""
    auto_implement_path = Path("plugins/autonomous-dev/commands/auto-implement.md")
    assert auto_implement_path.exists(), "auto-implement.md must exist"

    content = auto_implement_path.read_text()

    # Check for timeout documentation in STEP 2 (test-master invocation)
    assert "timeout" in content.lower(), "auto-implement.md must mention timeout"
    assert "test-master" in content.lower(), "auto-implement.md must mention test-master"

    # Check for Issue #90 reference
    assert "#90" in content or "issue #90" in content.lower(), \
        "auto-implement.md must reference Issue #90 for timeout fix"


@pytest.mark.skip(reason="auto-implement.md deprecated - redirects to /implement")
def test_auto_implement_timeout_value_is_reasonable():
    """Verify timeout value is 1200 seconds (20 minutes) for test-master."""
    auto_implement_path = Path("plugins/autonomous-dev/commands/auto-implement.md")
    content = auto_implement_path.read_text()

    # Look for timeout value near test-master section
    # Pattern: mentions of "1200", "20 minutes", "timeout" near "test-master"
    test_master_section = content.lower()

    # Should mention 20 minutes or 1200 seconds
    has_timeout_value = (
        "1200" in content or
        "20 minutes" in content.lower() or
        "20-minute" in content.lower()
    )

    assert has_timeout_value, \
        "auto-implement.md must specify 1200 seconds or 20 minutes timeout"


def test_test_master_uses_minimal_pytest_flags():
    """Verify test-master.md uses --tb=line -q for minimal output."""
    test_master_path = Path("plugins/autonomous-dev/agents/test-master.md")
    assert test_master_path.exists(), "test-master.md must exist"

    content = test_master_path.read_text()

    # Check for pytest flags that reduce verbosity
    has_minimal_flags = (
        "--tb=line" in content or
        "--tb=no" in content or
        "-q" in content or
        "quiet" in content.lower()
    )

    assert has_minimal_flags, \
        "test-master.md must use minimal pytest verbosity flags (--tb=line -q or similar)"


def test_test_master_references_issue_90():
    """Verify test-master.md references Issue #90 for pytest flag changes."""
    test_master_path = Path("plugins/autonomous-dev/agents/test-master.md")
    content = test_master_path.read_text()

    # Check for Issue #90 reference
    has_issue_reference = (
        "#90" in content or
        "issue #90" in content.lower() or
        "freeze" in content.lower()
    )

    assert has_issue_reference, \
        "test-master.md must reference Issue #90 or mention freeze prevention"


def test_pytest_flags_prevent_verbose_output():
    """Verify pytest flags in test-master.md prevent verbose output."""
    test_master_path = Path("plugins/autonomous-dev/agents/test-master.md")
    content = test_master_path.read_text()

    # Should NOT use -v (verbose) flag
    # Pattern: look for pytest commands without -v
    pytest_pattern = re.compile(r'pytest.*-v(?!\S)', re.MULTILINE)
    verbose_matches = pytest_pattern.findall(content)

    # If -v is found, should also have -q to counteract it
    if verbose_matches:
        assert "-q" in content, \
            "test-master.md uses -v flag, must also use -q to reduce output"


@pytest.mark.skip(reason="auto-implement.md deprecated - redirects to /implement")
def test_auto_implement_timeout_prevents_indefinite_freeze():
    """Verify auto-implement.md documents timeout prevents indefinite freeze."""
    auto_implement_path = Path("plugins/autonomous-dev/commands/auto-implement.md")
    content = auto_implement_path.read_text()

    # Check for documentation about preventing freeze
    has_freeze_prevention_docs = (
        "prevent" in content.lower() and (
            "freeze" in content.lower() or
            "indefinite" in content.lower() or
            "hang" in content.lower()
        )
    )

    assert has_freeze_prevention_docs, \
        "auto-implement.md must document that timeout prevents indefinite freeze"


def test_timeout_allows_graceful_degradation():
    """Verify documentation mentions graceful degradation on timeout."""
    auto_implement_path = Path("plugins/autonomous-dev/commands/auto-implement.md")
    content = auto_implement_path.read_text()

    # Check for graceful degradation documentation
    has_graceful_docs = (
        "graceful" in content.lower() or
        "continue" in content.lower() or
        "partial results" in content.lower()
    )

    # If timeout is mentioned, should also mention what happens when it triggers
    if "timeout" in content.lower():
        assert has_graceful_docs, \
            "auto-implement.md must document graceful degradation on timeout"


def test_pytest_output_reduction_documented():
    """Verify test-master.md documents output reduction benefits."""
    test_master_path = Path("plugins/autonomous-dev/agents/test-master.md")
    content = test_master_path.read_text()

    # Check for documentation about output reduction
    has_output_docs = (
        "output" in content.lower() or
        "minimal" in content.lower() or
        "reduce" in content.lower()
    )

    assert has_output_docs, \
        "test-master.md must document pytest output reduction"


@pytest.mark.skip(reason="auto-implement.md deprecated - redirects to /implement")
def test_timeout_value_has_rationale():
    """Verify timeout value choice is explained."""
    auto_implement_path = Path("plugins/autonomous-dev/commands/auto-implement.md")
    content = auto_implement_path.read_text()

    # Look for explanation near timeout value
    # Should mention why 20 minutes / 1200 seconds
    has_rationale = (
        "5-15 minutes" in content.lower() or
        "safety" in content.lower() or
        "buffer" in content.lower() or
        "typical" in content.lower()
    )

    assert has_rationale, \
        "auto-implement.md should explain why 20-minute timeout was chosen"


def test_fixes_maintain_backward_compatibility():
    """Verify fixes don't break existing functionality."""
    # Test-master should still work for existing workflows
    test_master_path = Path("plugins/autonomous-dev/agents/test-master.md")
    content = test_master_path.read_text()

    # Core functionality should remain
    assert "pytest" in content.lower(), "test-master must still use pytest"
    assert "tests" in content.lower(), "test-master must still write tests"
    assert "TDD" in content or "test-driven" in content.lower(), \
        "test-master must still follow TDD"


def test_timeout_not_too_short():
    """Verify timeout is not too short (minimum 10 minutes)."""
    auto_implement_path = Path("plugins/autonomous-dev/commands/auto-implement.md")
    content = auto_implement_path.read_text()

    # Check for timeout values
    timeout_pattern = re.compile(r'(\d+)\s*(?:seconds?|s\b)', re.IGNORECASE)
    matches = timeout_pattern.findall(content)

    if matches:
        timeout_values = [int(m) for m in matches]
        # Filter to reasonable timeout values (300s to 3600s range)
        agent_timeouts = [t for t in timeout_values if 300 <= t <= 3600]

        if agent_timeouts:
            # test-master timeout should be >= 600 seconds (10 minutes)
            max_timeout = max(agent_timeouts)
            assert max_timeout >= 600, \
                f"test-master timeout should be at least 10 minutes, found {max_timeout}s"


def test_timeout_not_too_long():
    """Verify timeout is not too long (maximum 30 minutes)."""
    auto_implement_path = Path("plugins/autonomous-dev/commands/auto-implement.md")
    content = auto_implement_path.read_text()

    # Check for timeout values
    timeout_pattern = re.compile(r'(\d+)\s*(?:seconds?|s\b)', re.IGNORECASE)
    matches = timeout_pattern.findall(content)

    if matches:
        timeout_values = [int(m) for m in matches]
        # Filter to reasonable timeout values (300s to 3600s range)
        agent_timeouts = [t for t in timeout_values if 300 <= t <= 3600]

        if agent_timeouts:
            # test-master timeout should be <= 1800 seconds (30 minutes)
            max_timeout = max(agent_timeouts)
            assert max_timeout <= 1800, \
                f"test-master timeout should be at most 30 minutes, found {max_timeout}s"
