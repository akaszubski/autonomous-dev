"""Regression test for Issue #1174: Post-Dispatch Completion Recording Protocol.

Issue #1174 widens the bug-class first documented in #852 (doc-master) to ALL
foreground agents: SubagentStop fires asynchronously, so the next pre-dispatch
ordering check (which is synchronous) reads stale state and the gate falsely
sees the just-returned agent as "not yet run". The symptom is manual
``record_agent_completion()`` injections scattered through coordinator
transcripts.

Fix: a Post-Dispatch Completion Recording Protocol section added to
``commands/implement.md`` and ``commands/implement-batch.md`` instructs the
coordinator to synchronously call ``record_agent_completion()`` after EVERY
Agent tool returns. This is idempotent with SubagentStop's later async call
(fcntl-locked, tri-scope, last-write-wins per Issue #1046).

Tests:

1. ``implement.md`` contains the literal Post-Dispatch section header.
2. ``implement-batch.md`` contains the same symmetric section.
3. The ``implement.md`` section reuses the session-ID fallback chain
   (Issue #904 consistency).
4. The ``implement.md`` section invokes ``record_agent_completion(``.
5. Runtime invariant: ``record_agent_completion()`` writes are observable
   in all three scope keys (issue-scoped, ``"0"``, ``"unscoped"``) per the
   #1046 tri-scope contract — closes the operational-integration-test gap
   per Issue #1064.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

# Path constants — parents[2] = regression -> tests -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
IMPLEMENT_MD = REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"
IMPLEMENT_BATCH_MD = (
    REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement-batch.md"
)

POST_DISPATCH_HEADER = "### Post-Dispatch Completion Recording Protocol"


@pytest.fixture()
def pcs(tmp_path, monkeypatch):
    """Import ``pipeline_completion_state`` with state files redirected to tmp_path.

    Mirrors the isolation pattern used by ``test_issue_852_doc_verdict_completion``.
    No mocking of ``record_agent_completion`` itself — we exercise the real
    code path so the tri-scope invariant is verified end-to-end.
    """
    monkeypatch.syspath_prepend(str(LIB_DIR))

    module_name = "pipeline_completion_state"
    if module_name in sys.modules:
        del sys.modules[module_name]

    mod = importlib.import_module(module_name)

    # Redirect state file paths into tmp_path so we never touch real /tmp state.
    def patched_state_file_path(session_id: str, *, run_id=None) -> Path:
        import hashlib

        h = hashlib.sha256(session_id.encode()).hexdigest()[:8]
        return tmp_path / f"pipeline_agent_completions_{h}.json"

    monkeypatch.setattr(mod, "_state_file_path", patched_state_file_path)

    yield mod

    if module_name in sys.modules:
        del sys.modules[module_name]


class TestIssue1174PostDispatchProtocol:
    """Verify the Post-Dispatch Completion Recording Protocol (Issue #1174)."""

    def test_implement_md_has_post_dispatch_section(self) -> None:
        """``commands/implement.md`` must contain the Post-Dispatch section header.

        This is the primary structural assertion: the section is the entire
        deliverable for the single-issue coordinator path.
        """
        assert IMPLEMENT_MD.exists(), f"implement.md not found at {IMPLEMENT_MD}"
        content = IMPLEMENT_MD.read_text()
        assert POST_DISPATCH_HEADER in content, (
            f"implement.md must contain the literal section header "
            f"{POST_DISPATCH_HEADER!r} (Issue #1174)"
        )
        # The section must also reference Issue #1174 so future readers can
        # trace the rationale.
        assert "1174" in content, (
            "implement.md must reference Issue #1174 in the Post-Dispatch section"
        )

    def test_implement_batch_md_has_post_dispatch_section(self) -> None:
        """``commands/implement-batch.md`` must contain a symmetric Post-Dispatch section."""
        assert IMPLEMENT_BATCH_MD.exists(), (
            f"implement-batch.md not found at {IMPLEMENT_BATCH_MD}"
        )
        content = IMPLEMENT_BATCH_MD.read_text()
        assert POST_DISPATCH_HEADER in content, (
            f"implement-batch.md must contain the literal section header "
            f"{POST_DISPATCH_HEADER!r} (Issue #1174)"
        )
        assert "1174" in content, (
            "implement-batch.md must reference Issue #1174 in the Post-Dispatch section"
        )

    def test_post_dispatch_uses_session_fallback_chain(self) -> None:
        """The Post-Dispatch section must reuse the Issue #904 session-ID fallback chain.

        Visual symmetry between Pre-Dispatch and Post-Dispatch is required so
        the two protocols are obviously paired. The section must either inline
        the fallback chain (env -> sentinel -> 'unknown') or reference the
        ``resolve_session_id`` helper from ``pipeline_completion_state``.
        """
        content = IMPLEMENT_MD.read_text()
        # Locate the post-dispatch section so we only assert against its body.
        idx = content.find(POST_DISPATCH_HEADER)
        assert idx >= 0, "Post-Dispatch section header not found in implement.md"
        # Slice from the header to the ARGUMENTS marker (the section ends there).
        section = content[idx : content.find("ARGUMENTS:", idx)]

        assert "CLAUDE_SESSION_ID" in section, (
            "Post-Dispatch section must reference CLAUDE_SESSION_ID "
            "(Issue #904 fallback chain consistency)"
        )
        assert (
            "resolve_session_id" in section or "_resolve_session_id" in section
        ), (
            "Post-Dispatch section must reference resolve_session_id "
            "(either the helper or the inline equivalent)"
        )

    def test_post_dispatch_invokes_record_agent_completion(self) -> None:
        """The Post-Dispatch section must show a literal ``record_agent_completion(`` call."""
        content = IMPLEMENT_MD.read_text()
        idx = content.find(POST_DISPATCH_HEADER)
        assert idx >= 0
        section = content[idx : content.find("ARGUMENTS:", idx)]

        assert "record_agent_completion(" in section, (
            "Post-Dispatch section must contain a literal record_agent_completion( call "
            "(Issue #1174 — the entire point of the protocol)"
        )
        # Sanity: the call must come from pipeline_completion_state.
        assert "pipeline_completion_state" in section, (
            "Post-Dispatch section must import record_agent_completion from "
            "pipeline_completion_state"
        )

    def test_record_agent_completion_runtime_invariant(self, pcs) -> None:
        """Runtime invariant — closes the OIT gap per Issue #1064.

        ``record_agent_completion()`` MUST write under THREE scope keys per the
        Issue #1046 tri-scope contract:

        - ``str(issue_number)`` — primary key (here ``"42"``)
        - ``"0"`` — unscoped/default key
        - ``"unscoped"`` — stable issue-agnostic key

        ``get_completed_agents`` reads via the issue-keyed path; the
        ``"unscoped"`` key is verified by reading the state dict directly
        because ``get_completed_agents`` does not expose a ``scope=`` parameter.
        """
        session_id = "test-session-1174"
        agent_type = "implementer"
        issue_number = 42

        pcs.record_agent_completion(
            session_id,
            agent_type,
            issue_number=issue_number,
            success=True,
        )

        # Scope #1: issue-scoped read (issue_number=42)
        completed_issue_scoped = pcs.get_completed_agents(
            session_id, issue_number=issue_number
        )
        assert agent_type in completed_issue_scoped, (
            f"{agent_type} must appear under issue-scoped key '{issue_number}' "
            f"(tri-scope contract — Issue #1046)"
        )

        # Scope #2: unscoped/default read (issue_number=0 -> reads key '0')
        completed_zero_scoped = pcs.get_completed_agents(
            session_id, issue_number=0
        )
        assert agent_type in completed_zero_scoped, (
            f"{agent_type} must appear under the default key '0' "
            f"(tri-scope contract — Issue #1046)"
        )

        # Scope #3: 'unscoped' string key — read raw state because
        # get_completed_agents does not expose a scope= parameter.
        state = pcs._read_state(session_id)
        unscoped_completions = state.get("completions", {}).get("unscoped", {})
        assert agent_type in unscoped_completions, (
            f"{agent_type} must appear under the 'unscoped' key in raw state "
            f"(tri-scope contract — Issue #1046). "
            f"Got completions keys: {list(state.get('completions', {}).keys())}"
        )
        assert unscoped_completions[agent_type] is True or (
            isinstance(unscoped_completions[agent_type], dict)
            and unscoped_completions[agent_type].get("success") is True
        ), (
            f"'unscoped' entry for {agent_type} must indicate success "
            f"(got {unscoped_completions[agent_type]!r})"
        )
