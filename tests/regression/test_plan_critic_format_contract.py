"""Regression test for plan-critic output format contract (Issue #1237)."""

from pathlib import Path


def test_plan_critic_format_contract():
    """Verify plan-critic.md contains the output format contract with required elements."""
    # Find the plan-critic agent file
    plan_critic_file = Path(__file__).resolve().parents[2] / "plugins/autonomous-dev/agents/plan-critic.md"
    assert plan_critic_file.exists(), f"plan-critic.md not found at {plan_critic_file}"
    
    # Read the file content
    content = plan_critic_file.read_text()
    
    # Check for the key elements of the output format contract
    assert "verdict line" in content.lower(), "plan-critic.md must mention 'verdict line'"
    assert "paragraphs" in content.lower(), "plan-critic.md must mention 'paragraphs'"
    
    # Check for the exact rejection sentence (Issue #1237)
    assert "A response consisting only of a verdict line is INVALID" in content, \
        "plan-critic.md must contain the exact rejection sentence for verdict-only responses"
    
    # Check that verdict-line-LAST requirement is present
    assert "MUST appear LAST" in content or "must appear last" in content.lower(), \
        "plan-critic.md must specify that verdict line must appear LAST"
    
    # Check for the Output Format Contract header
    assert "Output Format Contract" in content, \
        "plan-critic.md must have an 'Output Format Contract' section"