"""Regression test for pytest-gate auto-record wiring in implement.md (Issue #1238)."""

from pathlib import Path


def test_implement_step8_pytest_gate_recording():
    """Verify implement.md STEP 8 contains the auto-record instruction for pytest-gate."""
    # Find the implement.md command file
    implement_file = Path(__file__).resolve().parents[2] / "plugins/autonomous-dev/commands/implement.md"
    assert implement_file.exists(), f"implement.md not found at {implement_file}"
    
    # Read the file content
    content = implement_file.read_text()
    lines = content.split('\n')
    
    # Check that record_pytest_gate_passed is mentioned
    assert "record_pytest_gate_passed" in content, \
        "implement.md must contain 'record_pytest_gate_passed' function call"
    
    # Find STEP 8 section and verify the call is in the right context
    step8_found = False
    record_call_found = False
    
    for i, line in enumerate(lines):
        if "STEP 8:" in line or "### STEP 8:" in line:
            step8_found = True
            # Look within 200 lines after STEP 8 for the record call
            for j in range(i, min(i + 200, len(lines))):
                if "record_pytest_gate_passed" in lines[j]:
                    record_call_found = True
                    break
            break
    
    assert step8_found, "STEP 8 section not found in implement.md"
    assert record_call_found, \
        "record_pytest_gate_passed call must appear within STEP 8 context (within 200 lines)"
    
    # Verify it mentions the correct module
    assert "pipeline_completion_state.py" in content, \
        "implement.md should reference pipeline_completion_state.py module"
    
    # Verify it mentions Issue #1238
    assert "#1238" in content, \
        "implement.md should reference Issue #1238 for the auto-record fix"


def test_implement_light_mode_pytest_gate_recording():
    """Verify implement.md Light mode (STEP L3) contains the auto-record instruction."""
    # Find the implement.md command file  
    implement_file = Path(__file__).resolve().parents[2] / "plugins/autonomous-dev/commands/implement.md"
    assert implement_file.exists(), f"implement.md not found at {implement_file}"
    
    # Read the file content
    content = implement_file.read_text()
    lines = content.split('\n')
    
    # Find STEP L3 section and verify the call is in the right context
    step_l3_found = False
    record_call_found = False
    
    for i, line in enumerate(lines):
        if "STEP L3:" in line or "### STEP L3:" in line:
            step_l3_found = True
            # Look within 50 lines after STEP L3 for the record call
            for j in range(i, min(i + 50, len(lines))):
                if "record_pytest_gate_passed" in lines[j]:
                    record_call_found = True
                    break
            break
    
    assert step_l3_found, "STEP L3 section not found in implement.md"
    assert record_call_found, \
        "record_pytest_gate_passed call must appear within STEP L3 context (within 50 lines)"