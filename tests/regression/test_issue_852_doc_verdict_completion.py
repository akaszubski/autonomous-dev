"""Regression test for Issue #852: doc-master completion events missing.

11/14 doc-master invocations had no completion events recorded because
SubagentStop doesn't fire reliably for background agents. The coordinator
called record_doc_verdict() but NOT record_agent_completion() for 'doc-master'.

Fix: Add explicit record_agent_completion('doc-master', ...) calls alongside
record_doc_verdict() in implement.md, implement-batch.md.

This test file verifies:
1. Pre-fix gap: record_doc_verdict alone does NOT add 'doc-master' to completions.
2. Post-fix behavior: calling both functions adds both entries correctly.
3. Idempotency: duplicate record_agent_completion calls don't corrupt state.
4. Static verification: command files contain both calls in proximity.
"""

import importlib
import sys
from pathlib import Path

import pytest

# Path constants
REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
IMPLEMENT_MD = REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"
IMPLEMENT_BATCH_MD = REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement-batch.md"


@pytest.fixture()
def pcs(tmp_path, monkeypatch):
    """Import pipeline_completion_state with state files redirected to tmp_path."""
    monkeypatch.syspath_prepend(str(LIB_DIR))

    # Remove any cached import so we start fresh
    module_name = "pipeline_completion_state"
    if module_name in sys.modules:
        del sys.modules[module_name]

    mod = importlib.import_module(module_name)

    # Redirect state file paths to tmp_path for full isolation
    original_state_file_path = mod._state_file_path

    def patched_state_file_path(session_id: str, *, run_id=None) -> Path:
        import hashlib
        h = hashlib.sha256(session_id.encode()).hexdigest()[:8]
        return tmp_path / f"pipeline_agent_completions_{h}.json"

    monkeypatch.setattr(mod, "_state_file_path", patched_state_file_path)

    yield mod

    # Cleanup cached module so subsequent tests get a fresh import
    if module_name in sys.modules:
        del sys.modules[module_name]


class TestIssue852DocVerdictCompletion:
    """Verify that doc-master completion is recorded alongside doc verdicts."""

    def test_record_doc_verdict_does_not_record_agent_completion(self, pcs) -> None:
        """Calling record_doc_verdict alone must NOT add 'doc-master' to completed agents.

        This test documents the pre-fix gap: the coordinator only called
        record_doc_verdict, which persists the verdict string but does NOT
        add an entry to the completions dict for 'doc-master'. As a result,
        any hook checking get_completed_agents(...) would find 'doc-master' absent.

        Issue: #852
        """
        session_id = "test-session-852-a"
        issue_number = 123

        pcs.record_doc_verdict(session_id, issue_number, "PASS")

        completed = pcs.get_completed_agents(session_id, issue_number=issue_number)
        assert "doc-master" not in completed, (
            "record_doc_verdict alone should NOT add 'doc-master' to completed agents "
            "(this documents the pre-fix gap — Issue #852)"
        )

    def test_explicit_record_agent_completion_adds_doc_master(self, pcs) -> None:
        """Calling both record_agent_completion and record_doc_verdict produces both entries.

        This is the post-fix behavior: the coordinator now calls both functions,
        so 'doc-master' appears in the completed agents set AND the verdict is persisted.

        Issue: #852
        """
        session_id = "test-session-852-b"
        issue_number = 456
        verdict = "PASS"

        pcs.record_doc_verdict(session_id, issue_number, verdict)
        pcs.record_agent_completion(
            session_id,
            "doc-master",
            issue_number=issue_number,
            success=(verdict not in ("MISSING",)),
        )

        # Verify 'doc-master' now appears in completed agents
        completed = pcs.get_completed_agents(session_id, issue_number=issue_number)
        assert "doc-master" in completed, (
            "'doc-master' must appear in completed agents after record_agent_completion (Issue #852)"
        )

        # Verify the verdict is also persisted
        state = pcs._read_state(session_id)
        issue_key = str(issue_number)
        completions = state.get("completions", {}).get(issue_key, {})
        assert completions.get("doc-master-verdict") == "PASS", (
            "doc-master-verdict must be 'PASS' in completion state"
        )
        assert completions.get("doc-master") is True, (
            "doc-master completion flag must be True"
        )

    def test_idempotent_double_recording(self, pcs) -> None:
        """Calling record_agent_completion twice for 'doc-master' must not corrupt state.

        This simulates the scenario where both the SubagentStop hook AND the
        coordinator's explicit call both fire for the same session/issue.
        The second call must simply overwrite with the same value — no error,
        no list growth, no state corruption.

        Issue: #852
        """
        session_id = "test-session-852-c"
        issue_number = 789
        verdict = "FAIL"

        pcs.record_doc_verdict(session_id, issue_number, verdict)

        # Simulate hook firing first
        pcs.record_agent_completion(
            session_id,
            "doc-master",
            issue_number=issue_number,
            success=(verdict not in ("MISSING",)),
        )

        # Simulate coordinator also calling it (double-recording)
        pcs.record_agent_completion(
            session_id,
            "doc-master",
            issue_number=issue_number,
            success=(verdict not in ("MISSING",)),
        )

        completed = pcs.get_completed_agents(session_id, issue_number=issue_number)
        assert "doc-master" in completed, (
            "'doc-master' must still appear after double-recording (idempotency check)"
        )

        # State must not have duplicates — completions is a dict keyed by agent name
        state = pcs._read_state(session_id)
        issue_key = str(issue_number)
        completions = state.get("completions", {}).get(issue_key, {})

        # Dict keys are unique by definition; verify there is exactly one entry
        doc_master_entries = [k for k in completions if k == "doc-master"]
        assert len(doc_master_entries) == 1, (
            f"State dict must have exactly 1 'doc-master' key, got {len(doc_master_entries)}"
        )

    def test_command_files_contain_explicit_recording(self) -> None:
        """Static verification: implement.md and implement-batch.md contain both calls.

        Both record_doc_verdict and record_agent_completion must appear in proximity
        (same code block) in each command file. This ensures the coordinator instructions
        are actually present to prevent the Issue #852 regression.
        """
        assert IMPLEMENT_MD.exists(), f"implement.md not found at {IMPLEMENT_MD}"
        assert IMPLEMENT_BATCH_MD.exists(), f"implement-batch.md not found at {IMPLEMENT_BATCH_MD}"

        for filepath in (IMPLEMENT_MD, IMPLEMENT_BATCH_MD):
            content = filepath.read_text()

            assert "record_doc_verdict" in content, (
                f"{filepath.name} must contain 'record_doc_verdict' call"
            )
            assert "record_agent_completion" in content, (
                f"{filepath.name} must contain 'record_agent_completion' call (Issue #852)"
            )

            # Verify they appear within 10 lines of each other in at least one location
            lines = content.splitlines()
            verdict_lines = [i for i, ln in enumerate(lines) if "record_doc_verdict" in ln]
            completion_lines = [i for i, ln in enumerate(lines) if "record_agent_completion" in ln]

            assert verdict_lines, f"{filepath.name}: no lines with record_doc_verdict"
            assert completion_lines, f"{filepath.name}: no lines with record_agent_completion"

            close_pairs = [
                (v, c)
                for v in verdict_lines
                for c in completion_lines
                if abs(v - c) <= 10
            ]
            assert close_pairs, (
                f"{filepath.name}: record_doc_verdict and record_agent_completion must appear "
                f"within 10 lines of each other (Issue #852 co-location requirement). "
                f"record_doc_verdict at lines {verdict_lines}, "
                f"record_agent_completion at lines {completion_lines}"
            )

            # Verify the issue #852 reference is present
            assert "852" in content, (
                f"{filepath.name} must reference Issue #852"
            )
