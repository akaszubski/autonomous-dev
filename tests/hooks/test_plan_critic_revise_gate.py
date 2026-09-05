"""Test plan-critic REVISE gate enforcement (Issue #1417)."""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest


def test_check_plan_critic_revise_gate_basic(monkeypatch, tmp_path):
    """Basic test that the gate function exists and can be called.

    The "no verdict file" arm is HERMETIC: it points the gate at a path that
    provably does not exist. Before Issue #1417's path fix this assertion read
    the repo's live ``.claude/plan_critic_verdict.json`` — which meant it was
    ``allow`` only while no real verdict happened to be on disk, and it flipped
    to ``deny`` the moment plan-critic actually ran. It was also DOUBLY
    accidentally-true: ``allow`` is what the gate's fail-open ``except`` returns
    as well, so the assertion could not distinguish "no file" from "crashed".
    """
    # Add hook directory to path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins/autonomous-dev/hooks"))
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins/autonomous-dev/lib"))

    # Import the function
    import unified_pre_tool
    from unified_pre_tool import check_plan_critic_revise_gate, AGENT_TOOL_NAMES

    # Test with non-agent tool (should allow)
    decision, reason = check_plan_critic_revise_gate("Write", {})
    assert decision == "allow"
    assert "Not an agent invocation" in reason

    # Test with non-implementer agent (should allow)
    decision, reason = check_plan_critic_revise_gate("Agent", {"subagent_type": "reviewer"})
    assert decision == "allow"
    assert "Not implementer dispatch" in reason

    # Test with implementer but no verdict file (should allow)
    absent = tmp_path / "no_such_verdict.json"
    assert not absent.exists()
    monkeypatch.setattr(unified_pre_tool, "PLAN_CRITIC_VERDICT_PATH", str(absent))
    decision, reason = check_plan_critic_revise_gate("Agent", {"subagent_type": "implementer"})
    assert decision == "allow"
    # Pin the REASON, not just the decision — this is what separates the
    # genuine no-file allow from the fail-open except's allow.
    assert reason == "No plan-critic verdict file", reason


def test_revise_gate_with_verdict_file():
    """Test gate behavior with actual verdict file."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins/autonomous-dev/hooks"))
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins/autonomous-dev/lib"))
    
    from unified_pre_tool import check_plan_critic_revise_gate
    
    # Create temporary directory structure
    with tempfile.TemporaryDirectory() as tmpdir:
        claude_dir = Path(tmpdir) / ".claude"
        claude_dir.mkdir()
        
        # Save original cwd and change to tmpdir
        orig_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            
            # Test 1: PROCEED verdict (should allow)
            verdict_file = claude_dir / "plan_critic_verdict.json"
            verdict_file.write_text(json.dumps({
                "verdict": "PROCEED",
                "timestamp": "2024-12-20T10:00:00Z",
                "composite_score": 80
            }))
            
            decision, reason = check_plan_critic_revise_gate(
                "Agent", {"subagent_type": "implementer"}
            )
            assert decision == "allow"
            assert "PROCEED" in reason
            
            # Test 2: BLOCKED verdict (should allow - coordinator handles)
            verdict_file.write_text(json.dumps({
                "verdict": "BLOCKED",
                "timestamp": "2024-12-20T10:00:00Z",
                "composite_score": 30
            }))
            
            decision, reason = check_plan_critic_revise_gate(
                "Agent", {"subagent_type": "implementer"}
            )
            assert decision == "allow"
            assert "BLOCKED" in reason
            
            # Test 3: REVISE verdict without timestamp (should allow - error case)
            verdict_file.write_text(json.dumps({
                "verdict": "REVISE",
                "composite_score": 60
            }))
            
            decision, reason = check_plan_critic_revise_gate(
                "Agent", {"subagent_type": "implementer"}
            )
            assert decision == "allow"
            assert "No timestamp" in reason or "Error" in reason
            
        finally:
            os.chdir(orig_cwd)


def test_revise_gate_integration_mock():
    """Test REVISE gate with mocked planner completion count."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins/autonomous-dev/hooks"))
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins/autonomous-dev/lib"))
    
    # We need to mock get_planner_completion_count before importing the hook
    import pipeline_completion_state
    original_func = pipeline_completion_state.get_planner_completion_count if hasattr(pipeline_completion_state, 'get_planner_completion_count') else None
    
    # Create mock function
    def mock_get_planner_completion_count(session_id, since_timestamp):
        # Return 0 for first test (no re-invoke), 1 for second test (re-invoked)
        return getattr(mock_get_planner_completion_count, 'return_value', 0)
    
    pipeline_completion_state.get_planner_completion_count = mock_get_planner_completion_count
    
    try:
        from unified_pre_tool import check_plan_critic_revise_gate
        
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            
            orig_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                
                # Create REVISE verdict file
                verdict_file = claude_dir / "plan_critic_verdict.json"
                verdict_file.write_text(json.dumps({
                    "verdict": "REVISE",
                    "timestamp": "2024-12-20T10:00:00Z",
                    "composite_score": 60,
                    "reasoning": "Plan needs improvements"
                }))
                
                # Test 1: No planner re-invocation (should deny)
                mock_get_planner_completion_count.return_value = 0
                decision, reason = check_plan_critic_revise_gate(
                    "Agent", {"subagent_type": "implementer"}
                )
                assert decision == "deny"
                assert "planner was not re-invoked" in reason
                
                # Test 2: Planner was re-invoked (should allow)
                mock_get_planner_completion_count.return_value = 1
                decision, reason = check_plan_critic_revise_gate(
                    "Agent", {"subagent_type": "implementer"}
                )
                assert decision == "allow"
                assert "Planner re-invoked 1 time(s)" in reason
                
            finally:
                os.chdir(orig_cwd)
    finally:
        # Restore original function if it existed
        if original_func:
            pipeline_completion_state.get_planner_completion_count = original_func


# ---------------------------------------------------------------------------
# PLAN_CRITIC_VERDICT_PATH — sourced constant, both gate arms, bypass refusal
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_SRC = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "unified_pre_tool.py"

sys.path.insert(0, str(REPO_ROOT / "plugins/autonomous-dev/hooks"))
sys.path.insert(0, str(REPO_ROOT / "plugins/autonomous-dev/lib"))


def _write_verdict(path: Path, verdict: str, timestamp: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "verdict": verdict,
                "timestamp": timestamp,
                "composite_score": 2.5,
                "reasoning": "x" * 120,
                "axis_scores": {"a": 3, "b": 2, "c": 4},
            }
        )
    )


def test_verdict_path_is_sourced_from_the_writing_module():
    """The reader's default IS the writer's constant — not a parallel literal."""
    import unified_pre_tool
    import plan_critic_verdict

    assert unified_pre_tool._PC_DEFAULT is plan_critic_verdict.DEFAULT_VERDICT_PATH
    # Production default unchanged by the refactor.
    assert unified_pre_tool.PLAN_CRITIC_VERDICT_PATH == ".claude/plan_critic_verdict.json"


def test_import_fallback_literal_has_not_drifted():
    """Drift assert, aimed ONLY at the ``except ImportError`` fallback literal.

    The fallback is unreachable while lib/ is importable, so nothing else can
    notice it going stale.
    """
    import re

    import plan_critic_verdict

    src = HOOK_SRC.read_text()
    m = re.search(r'_PC_DEFAULT = Path\("([^"]+)"\)', src)
    assert m is not None, "the except-ImportError fallback literal is gone"
    assert m.group(1) == str(plan_critic_verdict.DEFAULT_VERDICT_PATH)


def test_env_override_is_honoured_at_module_import(tmp_path):
    """PLAN_CRITIC_VERDICT_PATH is read from the environment.

    Exercised in a subprocess because the constant is resolved at import time;
    an in-process ``monkeypatch.setenv`` on an already-imported module would
    assert nothing.
    """
    import subprocess

    target = str(tmp_path / "isolated_verdict.json")
    env = dict(os.environ, PLAN_CRITIC_VERDICT_PATH=target)
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path[:0] = ["
            f"{str(REPO_ROOT / 'plugins/autonomous-dev/hooks')!r}, "
            f"{str(REPO_ROOT / 'plugins/autonomous-dev/lib')!r}]\n"
            "import unified_pre_tool as u; print(u.PLAN_CRITIC_VERDICT_PATH)",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == target


def test_revise_gate_refuses_without_planner_reinvocation(monkeypatch, tmp_path):
    """REFUSE arm, through the constant (no chdir, no relative-path accident)."""
    import pipeline_completion_state
    import unified_pre_tool
    from unified_pre_tool import check_plan_critic_revise_gate

    verdict = tmp_path / "verdict.json"
    _write_verdict(verdict, "REVISE", "2026-09-05T08:58:56+00:00")
    monkeypatch.setattr(unified_pre_tool, "PLAN_CRITIC_VERDICT_PATH", str(verdict))
    monkeypatch.setattr(
        pipeline_completion_state, "get_planner_completion_count", lambda *a, **k: 0
    )

    decision, reason = check_plan_critic_revise_gate(
        "Agent", {"subagent_type": "implementer"}
    )
    assert decision == "deny", reason
    assert "planner was not re-invoked" in reason


def test_revise_gate_permits_after_planner_reinvocation(monkeypatch, tmp_path):
    """PERMIT arm — same call, one planner completion after the timestamp."""
    import pipeline_completion_state
    import unified_pre_tool
    from unified_pre_tool import check_plan_critic_revise_gate

    verdict = tmp_path / "verdict.json"
    _write_verdict(verdict, "REVISE", "2026-09-05T08:58:56+00:00")
    monkeypatch.setattr(unified_pre_tool, "PLAN_CRITIC_VERDICT_PATH", str(verdict))
    monkeypatch.setattr(
        pipeline_completion_state, "get_planner_completion_count", lambda *a, **k: 1
    )

    decision, reason = check_plan_critic_revise_gate(
        "Agent", {"subagent_type": "implementer"}
    )
    assert decision == "allow", reason
    assert "Planner re-invoked 1 time(s)" in reason


def test_verdict_path_env_var_cannot_be_spoofed_inline():
    """Bypass-refusal arm, a DIFFERENT shape from the gate itself.

    The cure introduced an env override; without protection,
    ``PLAN_CRITIC_VERDICT_PATH=/dev/null <cmd>`` would disable the REVISE
    refusal outright. This asserts the cure did not become the bypass.
    """
    import unified_pre_tool

    assert "PLAN_CRITIC_VERDICT_PATH" in unified_pre_tool.PROTECTED_ENV_VARS
    inline = unified_pre_tool._detect_env_spoofing(
        "PLAN_CRITIC_VERDICT_PATH=/dev/null python3 -c 'print(1)'"
    )
    assert inline is not None, "inline PLAN_CRITIC_VERDICT_PATH override was allowed"
    assert "PLAN_CRITIC_VERDICT_PATH" in inline
    assert (
        unified_pre_tool._detect_env_spoofing("export PLAN_CRITIC_VERDICT_PATH=/dev/null")
        is not None
    )
    # Negative control: the spoofing detector is not blocking everything.
    assert (
        unified_pre_tool._detect_env_spoofing(
            "PLAN_CRITIC_NOTES=/tmp/x python3 -c 'print(1)'"
        )
        is None
    )