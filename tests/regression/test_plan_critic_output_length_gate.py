"""Regression test for plan-critic output-length gate in implement.md (Issue #1237)."""

from pathlib import Path


def test_implement_plan_critic_output_length_gate():
    """Verify implement.md STEP 5.5b contains the output-length gate for plan-critic."""
    # Find the implement.md command file
    implement_file = Path(__file__).resolve().parents[2] / "plugins/autonomous-dev/commands/implement.md"
    assert implement_file.exists(), f"implement.md not found at {implement_file}"
    
    # Read the file content
    content = implement_file.read_text()
    lines = content.split('\n')
    
    # Check that output-length gate is mentioned
    assert "Output-length gate" in content or "output-length gate" in content.lower(), \
        "implement.md must contain output-length gate for plan-critic"
    
    # Check for the word count threshold
    assert "word_count < 80" in content or "80 words" in content, \
        "implement.md must specify the 80-word threshold for plan-critic ghost output"
    
    # Check for retry mechanism
    assert "Auto-retry plan-critic ONCE" in content or "retry plan-critic" in content.lower(), \
        "implement.md must specify plan-critic retry on ghost output"
    
    # Find STEP 5.5b section and verify the gate is in the right context
    step_5_5b_found = False
    gate_found = False
    
    for i, line in enumerate(lines):
        if "5.5b" in line:
            step_5_5b_found = True
            # Look within 150 lines after STEP 5.5b for the output-length gate
            for j in range(i, min(i + 150, len(lines))):
                if "Output-length gate" in lines[j] or "word_count < 80" in lines[j]:
                    gate_found = True
                    break
            # Don't break here - keep searching for all 5.5b occurrences
    
    assert step_5_5b_found, "STEP 5.5b section not found in implement.md"
    assert gate_found, \
        "Output-length gate must appear within STEP 5.5b context (within 150 lines)"