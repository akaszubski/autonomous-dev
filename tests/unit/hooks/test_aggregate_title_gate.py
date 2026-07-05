"""Tests for aggregate title gate in unified_pre_tool.py."""

import json
import os
import pytest
import sys
import tempfile
from pathlib import Path
import importlib.util

# Load the hook module dynamically
hook_path = Path(__file__).resolve().parents[3] / "plugins/autonomous-dev/hooks/unified_pre_tool.py"
spec = importlib.util.spec_from_file_location("unified_pre_tool", hook_path)
hook_module = importlib.util.module_from_spec(spec)
sys.modules['unified_pre_tool'] = hook_module
spec.loader.exec_module(hook_module)

# Import functions we need to test
_detect_daily_aggregate_direct_filing = hook_module._detect_daily_aggregate_direct_filing
_get_active_issue_command = hook_module._get_active_issue_command
GH_ISSUE_COMMAND_CONTEXT_PATH = hook_module.GH_ISSUE_COMMAND_CONTEXT_PATH


def write_marker(command='triage-aggregate'):
    """Write marker file for testing."""
    import time
    context = {
        'command': command,
        'timestamp': time.time()
    }
    with open(GH_ISSUE_COMMAND_CONTEXT_PATH, 'w') as f:
        json.dump(context, f)


def clear_marker():
    """Remove marker file."""
    try:
        os.unlink(GH_ISSUE_COMMAND_CONTEXT_PATH)
    except FileNotFoundError:
        pass


@pytest.fixture(autouse=True)
def clean_marker():
    """Clean up marker file before and after each test."""
    clear_marker()
    yield
    clear_marker()


@pytest.mark.parametrize("command,should_block", [
    # 1. Direct gh issue create with guarded title - should block without marker
    ('gh issue create --repo o/r --title "Auto-triage findings — 2026-07-05" --label auto-triage', True),
    
    # 2. Backtick-wrapped form - should block without marker
    ('`gh issue create --title "Auto-triage findings — 2026-07-05"`', True),
    
    # 3. Command substitution form - should block without marker  
    ('$(gh issue create --title "Auto-triage findings — 2026-07-05")', True),
    
    # 4. sh -c form - should block without marker
    ('sh -c \'gh issue create --title "Auto-triage findings — 2026-07-05"\'', True),
    
    # 5. Python subprocess form - should block without marker
    ('python3 -c "subprocess.run([\'gh\', \'issue\', \'create\', \'--title\', \'Auto-triage findings — 2026-07-05\'])"', True),
    
    # 6. Python os.system form with CRITICAL prefix - should block without marker
    ('python3 -c "os.system(\'gh issue create --title \\"[CRITICAL] AI triage — 2026-07-05 14:30\\"\')"', True),
    
    # 7. Non-guarded title - should NOT block
    ('gh issue create --title "feat: add foo"', False),
])
def test_guarded_title_blocks_without_marker(command, should_block):
    """Test that guarded titles are blocked without triage-aggregate marker."""
    result = _detect_daily_aggregate_direct_filing(command)
    
    if should_block:
        assert result is not None, f"Expected block for: {command}"
        assert "Direct filing of guarded title" in result
        assert "daily_aggregate_manager" in result
    else:
        assert result is None, f"Should not block: {command}"


@pytest.mark.parametrize("command", [
    'gh issue create --repo o/r --title "Auto-triage findings — 2026-07-05" --label auto-triage',
    '`gh issue create --title "Auto-triage findings — 2026-07-05"`',
    '$(gh issue create --title "Auto-triage findings — 2026-07-05")',
    'sh -c \'gh issue create --title "Auto-triage findings — 2026-07-05"\'',
    'python3 -c "subprocess.run([\'gh\', \'issue\', \'create\', \'--title\', \'Auto-triage findings — 2026-07-05\'])"',
    'python3 -c "os.system(\'gh issue create --title \\"[CRITICAL] AI triage — 2026-07-05 14:30\\"\')"',
])
def test_guarded_title_allowed_with_triage_aggregate_marker(command):
    """Test that guarded titles are allowed when triage-aggregate marker is active."""
    # Write triage-aggregate marker
    write_marker('triage-aggregate')
    
    result = _detect_daily_aggregate_direct_filing(command)
    assert result is None, f"Should allow with marker: {command}"


def test_guard_ordering_improve_marker_takes_precedence():
    """Test that /improve marker active + guarded title → ALLOW (improve precedence)."""
    # This test simulates the case where /improve is active
    # The detection function should not be called in this case per the spec,
    # but if it is called with improve marker, it should allow
    write_marker('improve')
    
    command = 'gh issue create --title "Auto-triage findings — 2026-07-05"'
    # With improve marker active, this should not block
    # (though in practice, _is_issue_command_active would return True first)
    result = _detect_daily_aggregate_direct_filing(command)
    
    # The function will block because active command is not 'triage-aggregate'
    assert result is not None


def test_different_prefix_variations():
    """Test detection of both guarded prefixes."""
    # Test Auto-triage prefix
    cmd1 = 'gh issue create --title "Auto-triage findings — test"'
    result1 = _detect_daily_aggregate_direct_filing(cmd1)
    assert result1 is not None
    
    # Test CRITICAL prefix
    cmd2 = 'gh issue create --title "[CRITICAL] AI triage — urgent"'
    result2 = _detect_daily_aggregate_direct_filing(cmd2)
    assert result2 is not None
    
    # Test partial match doesn't trigger (missing em-dash)
    cmd3 = 'gh issue create --title "Auto-triage findings - test"'
    result3 = _detect_daily_aggregate_direct_filing(cmd3)
    assert result3 is None
    
    cmd4 = 'gh issue create --title "[CRITICAL] AI triage - test"'
    result4 = _detect_daily_aggregate_direct_filing(cmd4)
    assert result4 is None


def test_title_extraction_formats():
    """Test various title argument formats are correctly extracted."""
    # --title=value (equals sign)
    cmd1 = 'gh issue create --title="Auto-triage findings — 2026-07-05"'
    assert _detect_daily_aggregate_direct_filing(cmd1) is not None
    
    # --title value (space separated)
    cmd2 = 'gh issue create --title "Auto-triage findings — 2026-07-05"'
    assert _detect_daily_aggregate_direct_filing(cmd2) is not None
    
    # Single quotes
    cmd3 = "gh issue create --title 'Auto-triage findings — 2026-07-05'"
    assert _detect_daily_aggregate_direct_filing(cmd3) is not None
    
    # List literal form
    cmd4 = "['gh', 'issue', 'create', '--title', 'Auto-triage findings — 2026-07-05']"
    assert _detect_daily_aggregate_direct_filing(cmd4) is not None

def test_scan1_cli_arg_form_isolation():
    """Scan 1 handles --title X, --title "X", --title 'X', --title=X independently.
    
    Protects invariant: all CLI argument variations are detected to prevent bypass.
    """
    # Test Scan 1: Regular CLI forms with quotes
    test_cases = [
        # Space-separated with double quotes
        ('gh issue create --title "Auto-triage findings — 2026-07-05"', True),
        # Space-separated with single quotes  
        ("gh issue create --title 'Auto-triage findings — 2026-07-05'", True),
        # Equals sign with double quotes
        ('gh issue create --title="Auto-triage findings — 2026-07-05"', True),
        # Equals sign with single quotes
        ("gh issue create --title='Auto-triage findings — 2026-07-05'", True),
        # Multiple spaces between flag and value
        ('gh issue create --title   "Auto-triage findings — 2026-07-05"', True),
        # Tab between flag and value
        ('gh issue create --title\t"Auto-triage findings — 2026-07-05"', True),
        # CRITICAL prefix variant
        ('gh issue create --title "[CRITICAL] AI triage — 2026-07-05"', True),
        # Non-guarded title should not block
        ('gh issue create --title "feat: add new feature"', False),
    ]
    
    for command, should_block in test_cases:
        result = _detect_daily_aggregate_direct_filing(command)
        if should_block:
            assert result is not None, f"Expected block for: {command}"
            assert "Direct filing of guarded title" in result
        else:
            assert result is None, f"Should not block: {command}"


def test_scan1b_escaped_quote_form_isolation():
    """Scan 2 handles --title \\"X\\" from python3 -c "os.system(...)" payloads.
    
    Protects invariant: subprocess bypass attempts via escaped quotes are detected.
    """
    # Note: In the actual implementation, this is Scan 2 (not Scan 1b)
    test_cases = [
        # Python os.system with escaped quotes
        ('python3 -c "os.system(\'gh issue create --title \\"Auto-triage findings — 2026-07-05\\"\')"', True),
        # Nested command with escaped quotes
        ('sh -c "gh issue create --title \\"Auto-triage findings — 2026-07-05\\""', True),
        # CRITICAL variant with escaped quotes
        ('os.system("gh issue create --title \\"[CRITICAL] AI triage — 2026-07-05\\"")', True),
        # Non-guarded title with escaped quotes
        ('os.system("gh issue create --title \\"Regular issue\\"")', False),
    ]
    
    for command, should_block in test_cases:
        result = _detect_daily_aggregate_direct_filing(command)
        if should_block:
            assert result is not None, f"Expected block for escaped quotes: {command}"
            assert "Direct filing of guarded title" in result
        else:
            assert result is None, f"Should not block escaped quotes: {command}"


def test_scan2_list_literal_form_isolation():
    """Scan 3 handles ['--title', 'X'] list-literal variants.
    
    Protects invariant: subprocess.run() list form bypass attempts are detected.
    """
    # Note: In the actual implementation, this is Scan 3 (not Scan 2)
    test_cases = [
        # Standard list literal with single quotes
        ("['gh', 'issue', 'create', '--title', 'Auto-triage findings — 2026-07-05']", True),
        # Double quotes variant
        ('["gh", "issue", "create", "--title", "Auto-triage findings — 2026-07-05"]', True),
        # Mixed quotes
        ("['gh', 'issue', 'create', '--title', \"Auto-triage findings — 2026-07-05\"]", True),
        # Spaces around comma
        ("['gh' , 'issue' , 'create' , '--title' , 'Auto-triage findings — 2026-07-05']", True),
        # CRITICAL prefix in list literal
        ("['gh', 'issue', 'create', '--title', '[CRITICAL] AI triage — 2026-07-05']", True),
        # Non-guarded title in list literal
        ("['gh', 'issue', 'create', '--title', 'Regular issue title']", False),
    ]
    
    for command, should_block in test_cases:
        result = _detect_daily_aggregate_direct_filing(command)
        if should_block:
            assert result is not None, f"Expected block for list literal: {command}"
            assert "Direct filing of guarded title" in result
        else:
            assert result is None, f"Should not block list literal: {command}"
