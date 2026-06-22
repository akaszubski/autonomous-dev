"""
Unit tests for Phase 2 classifier-robustness gates.

Three test classes — one per Phase 2 success criterion:
  1. ``TestSlidingWindowMultiEdit`` — AC1, Issue #1146.
     Five consecutive Tier-1 (`fix`) Edits to the same .py file totalling
     >=20 lines within 60 s escalate the 5th to ``tier=light`` with reason
     containing ``cumulative_sliding_window``. The 4th call (cumulative=16
     lines) returns the normal Phase 1 ``tier=fix`` decision unescalated.

  2. ``TestHeredocFalsePositive`` — AC2, Issue #1153.
     ``gh issue create --body-file`` whose body content contains a
     heredoc + code-file redirect example MUST NOT be classified as a
     write-to-code-file. Uses a subprocess invocation of the hook entry
     point so we exercise the actual stdin payload code path.

  3. ``TestDynamicHeredocChained`` — AC3, Issue #1154.
     ``OUT=foo.py; cat > "$OUT" << EOF\\nclass X: pass\\nEOF`` blocks
     with ``tier=full`` (new-class trigger). ``OUT=notes.txt; cat > "$OUT"``
     does NOT block (non-code extension). ``OUT=$(echo foo).py; cat > "$OUT"``
     does NOT block (acknowledged residual — command substitution
     intentionally out of scope per the Phase 2 plan).

Phase 1 regression suite is in ``test_write_pipeline_gate.py``; this file
adds *new* coverage and does not duplicate those tests.

Issues: #1146, #1153, #1154
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

# Path setup — same convention as test_write_pipeline_gate.py
REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
HOOK_ENTRY = HOOK_DIR / "unified_pre_tool.py"

sys.path.insert(0, str(HOOK_DIR))
sys.path.insert(0, str(LIB_DIR))

import edit_tier_classifier as etc  # noqa: E402
import pipeline_completion_state as pcs  # noqa: E402
import unified_pre_tool as hook  # noqa: E402


# ---------------------------------------------------------------------------
# Subprocess harness — AC2
# ---------------------------------------------------------------------------


def _invoke_hook(
    payload: Dict[str, Any],
    tmp_path: Path,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the hook entry point in a fresh subprocess with a controlled env.

    Strips bypass-related env vars from the parent environment so the
    test reliably exercises the actual gate path. Specifically excluded:
      - AUTONOMOUS_DEV_BYPASS
      - ENFORCEMENT_LEVEL
      - SKIP_AGENT_COMPLETENESS_GATE
      - PIPELINE_CLEANUP_PHASE
      - PIPELINE_STATE_FILE
      - PIPELINE_COMPLETION_STATE_FILE
      - HOOK_BYPASS_* / .bypass-related vars

    Args:
        payload: The hook stdin JSON payload.
        tmp_path: cwd for the subprocess; also where any .bypass markers
            would land if the test wanted to inspect them.
        session_id: Optional CLAUDE_SESSION_ID injected into the
            subprocess env. When None a per-test random id is used.

    Returns:
        The parsed stdout JSON. Empty dict when stdout is not JSON.
    """
    # Build a clean env: start from parent's PATH only, then add the bare
    # minimum the hook needs.
    allowed_env: Dict[str, str] = {
        "PATH": os.environ.get("PATH", ""),
    }
    if session_id is None:
        session_id = f"phase2-test-{uuid.uuid4().hex[:8]}"
    allowed_env["CLAUDE_SESSION_ID"] = session_id
    allowed_env["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    # Python interpreter resolution needs HOME for ~ expansion in some
    # ``site-packages`` lookup paths, and SystemRoot on Windows. We are
    # macOS/Linux so HOME is enough.
    allowed_env["HOME"] = os.environ.get("HOME", str(tmp_path))

    # Explicitly DO NOT propagate any of the following:
    #   AUTONOMOUS_DEV_BYPASS, ENFORCEMENT_LEVEL,
    #   SKIP_AGENT_COMPLETENESS_GATE, PIPELINE_CLEANUP_PHASE,
    #   PIPELINE_STATE_FILE, PIPELINE_COMPLETION_STATE_FILE,
    #   HOOK_BYPASS_* — the allowed_env dict is the entire env.

    # session_id is also baked into the payload (the hook reads from stdin
    # JSON preferentially over the env var).
    payload = dict(payload)
    payload.setdefault("session_id", session_id)

    proc = subprocess.run(
        [sys.executable, str(HOOK_ENTRY)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env=allowed_env,
        timeout=30,
    )
    stdout = proc.stdout.strip()
    if not stdout:
        # When stdout is empty, check if the subprocess failed
        if proc.returncode != 0:
            # This is a real failure - the hook crashed or errored out
            raise AssertionError(
                f"Hook subprocess failed with returncode {proc.returncode}. "
                f"stderr: {proc.stderr.strip() or '(empty)'}"
            )
        # Returncode is 0 but stdout is empty - genuinely vacuous behavior
        # Return diagnostic info so callers can see what happened
        return {
            "_returncode": 0,
            "_stderr": proc.stderr.strip() or "(empty)",
            "_warning": "empty stdout but exit 0"
        }
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        # The hook prints JSON to stdout via output_decision; any non-JSON
        # output is a sign of test setup error.
        return {"_raw_stdout": stdout, "_returncode": proc.returncode,
                "_stderr": proc.stderr}

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def session_id() -> str:
    """Per-test unique session id so ring buffers do not collide across runs."""
    return f"phase2-{uuid.uuid4().hex[:12]}"


@pytest.fixture(autouse=True)
def pipeline_inactive(monkeypatch):
    """Default: pipeline is NOT active, so the gate actually runs."""
    monkeypatch.setattr(hook, "_is_pipeline_active", lambda: False)
    # Also drop any leftover skip-bypass file across test runs.
    skip_file = Path("/tmp/skip_write_pipeline_gate")
    if skip_file.exists():
        skip_file.unlink()


@pytest.fixture(autouse=True)
def clean_session(session_id):
    """Clear any pre-existing pipeline state for this session id."""
    pcs.clear_session(session_id)
    yield
    pcs.clear_session(session_id)


# ---------------------------------------------------------------------------
# AC1 — Sliding-window cumulative escalation (#1146)
# ---------------------------------------------------------------------------


class TestSlidingWindowMultiEdit:
    """5 consecutive Tier-1 Edits to same file escalate on the 5th call."""

    def _make_4_line_edit(self, i: int) -> str:
        """4 new lines, no AST significance, classifies as `fix`."""
        return f"# edit {i}\nx_{i} = 1\ny_{i} = 2\nz_{i} = 3"

    def test_fifth_edit_escalates_to_light_with_reason_marker(self, session_id):
        """5 × 4-line `fix` edits => 5th deny has tier=light + cumulative marker."""
        file_path = "/home/user/app/foo.py"

        for i in range(1, 5):
            new = self._make_4_line_edit(i)
            block, tier, directive = hook._check_write_pipeline_required(
                "Edit", file_path, "", new, session_id=session_id
            )
            assert block is True, f"Edit {i}: expected block=True"
            assert tier == "fix", (
                f"Edit {i}: expected unescalated tier=fix, got {tier!r}"
            )
            assert "cumulative_sliding_window" not in directive, (
                f"Edit {i}: should not be escalated yet"
            )

        # Edit 5: cumulative = 16 (prior) + 4 (this) = 20 >= threshold.
        new5 = self._make_4_line_edit(5)
        block5, tier5, directive5 = hook._check_write_pipeline_required(
            "Edit", file_path, "", new5, session_id=session_id
        )
        assert block5 is True
        assert tier5 == "light", f"Edit 5: expected escalated tier=light, got {tier5!r}"
        assert "cumulative_sliding_window" in directive5, (
            f"Edit 5: directive must contain 'cumulative_sliding_window', got: {directive5}"
        )

    def test_fourth_edit_returns_unescalated_fix_tier(self, session_id):
        """Boundary check: 4th edit (cumulative=16) does NOT trigger escalation."""
        file_path = "/home/user/app/bar.py"

        for i in range(1, 5):  # 1..4
            new = self._make_4_line_edit(i)
            block, tier, directive = hook._check_write_pipeline_required(
                "Edit", file_path, "", new, session_id=session_id
            )
            # Phase 1 contract: fix tier still blocks. AC1's "allow" wording
            # refers to "no escalation" — not "block=False".
            assert tier == "fix", f"Edit {i}: expected fix, got {tier!r}"

    def test_cross_file_isolation(self, session_id):
        """Edits to DIFFERENT files do NOT cross-pollute each other's buffers."""
        for fp_letter in "abcde":
            file_path = f"/home/user/app/file_{fp_letter}.py"
            new = self._make_4_line_edit(1)
            block, tier, directive = hook._check_write_pipeline_required(
                "Edit", file_path, "", new, session_id=session_id
            )
            # Each file gets its own buffer; all 5 stay at fix tier.
            assert tier == "fix", (
                f"file_{fp_letter}.py: expected fix tier (per-file), got {tier!r}"
            )

    def test_cross_session_isolation(self):
        """Edits in DIFFERENT sessions do NOT share ring buffers."""
        file_path = "/home/user/app/baz.py"
        edits_per_session = 4  # 16 lines each; under threshold

        for sess_letter in "abcde":
            sid = f"phase2-session-{sess_letter}-{uuid.uuid4().hex[:6]}"
            pcs.clear_session(sid)
            try:
                for i in range(1, edits_per_session + 1):
                    new = self._make_4_line_edit(i)
                    _, tier, _ = hook._check_write_pipeline_required(
                        "Edit", file_path, "", new, session_id=sid
                    )
                    assert tier == "fix", (
                        f"sess={sess_letter} edit {i}: expected fix, got {tier!r}"
                    )
            finally:
                pcs.clear_session(sid)

    def test_ttl_eviction_resets_window(self, session_id, monkeypatch):
        """Entries older than 60 s are dropped — a slow burst doesn't escalate."""
        file_path = "/home/user/app/slow.py"

        # Record 4 entries simulated as being >60 s ago.
        import pipeline_completion_state as pcs_mod

        # Use the public API to record, then directly poke the timestamp.
        for i in range(4):
            pcs_mod.record_tier1_allow(session_id, file_path, 4)
        # Backdate them by tampering with the state file.
        state = pcs_mod._read_state(session_id)
        buf = state[pcs_mod._TIER1_RING_BUFFER_KEY][file_path]
        for entry in buf:
            entry["ts"] -= 120  # 2 minutes ago — well outside 60 s window
        pcs_mod._write_state(session_id, state)

        # New 4-line edit: cumulative WITHIN the 60s window is 0, not 16.
        new = "# edit\nx = 1\ny = 2\nz = 3"
        block, tier, directive = hook._check_write_pipeline_required(
            "Edit", file_path, "", new, session_id=session_id
        )
        assert tier == "fix", (
            f"Stale entries should not count — expected fix, got {tier!r}"
        )
        assert "cumulative_sliding_window" not in directive

    def test_no_session_id_skips_sliding_window(self):
        """When session_id is None the sliding-window is a no-op."""
        file_path = "/home/user/app/nosid.py"
        # 5 × 4-line edits without session id — should NEVER escalate.
        for i in range(1, 6):
            new = f"# edit {i}\nx_{i} = 1\ny_{i} = 2\nz_{i} = 3"
            _, tier, directive = hook._check_write_pipeline_required(
                "Edit", file_path, "", new
                # session_id intentionally omitted
            )
            assert tier == "fix", (
                f"Edit {i}: no session_id => no escalation, got {tier!r}"
            )
            assert "cumulative_sliding_window" not in directive

    def test_post_escalation_ring_buffer_is_cleared(self, session_id):
        """After an escalation the buffer resets so the NEXT edit is fix again."""
        file_path = "/home/user/app/reset.py"
        # Push 4 entries (cumulative = 16)
        for i in range(1, 5):
            new = f"# edit {i}\nx_{i} = 1\ny_{i} = 2\nz_{i} = 3"
            _, tier, _ = hook._check_write_pipeline_required(
                "Edit", file_path, "", new, session_id=session_id
            )
            assert tier == "fix"

        # 5th: escalates to light.
        new5 = "# edit 5\nx_5 = 1\ny_5 = 2\nz_5 = 3"
        _, tier5, _ = hook._check_write_pipeline_required(
            "Edit", file_path, "", new5, session_id=session_id
        )
        assert tier5 == "light"

        # 6th: ring buffer was cleared by the escalation, so cumulative
        # resets to just THIS edit (4 lines, under threshold) — stays at fix.
        new6 = "# edit 6\nx_6 = 1\ny_6 = 2\nz_6 = 3"
        _, tier6, directive6 = hook._check_write_pipeline_required(
            "Edit", file_path, "", new6, session_id=session_id
        )
        assert tier6 == "fix", (
            f"Post-escalation reset: expected fix on next edit, got {tier6!r}"
        )
        assert "cumulative_sliding_window" not in directive6


# ---------------------------------------------------------------------------
# AC2 — Heredoc false-positive fix (#1153)
# ---------------------------------------------------------------------------


class TestHeredocFalsePositive:
    """``gh issue create --body-file`` with heredoc-bodied code examples MUST pass."""

    def test_gh_issue_create_with_nested_heredoc_body_not_blocked(self, tmp_path):
        """The exact #1152-shape payload: heredoc body contains a code-file redirect."""
        command = (
            "gh issue create --title 'test' --body-file - <<HEREDOC_OUTER\n"
            "Example shown here:\n"
            "cat > /tmp/x.py <<HEREDOC_INNER\n"
            "class X: pass\n"
            "HEREDOC_INNER\n"
            "HEREDOC_OUTER\n"
        )
        result = _invoke_hook(
            {
                "tool_name": "Bash",
                "tool_input": {"command": command},
            },
            tmp_path,
        )
        # The hook output may or may not include a permissionDecision —
        # absence of "deny" is the acceptance criterion. The gh-issue
        # gate may itself deny if certain conditions are met; we only
        # assert the Bash code-file gate did NOT fire spuriously.
        hook_out = result.get("hookSpecificOutput", {}) or result
        decision = hook_out.get("permissionDecision", "")
        reason = hook_out.get("permissionDecisionReason", "")
        # If the decision is deny, the reason must NOT mention the
        # code-file Bash gate (the bug we are fixing). Other deny paths
        # — like ``gh issue create`` blocking — are allowed and unrelated.
        if decision == "deny":
            assert "bash_code_file_gate" not in reason, (
                f"Heredoc body code-file false positive still firing. "
                f"Reason: {reason}"
            )
            assert "/tmp/x.py" not in reason or "issue create" in reason.lower(), (
                f"Code-file gate matched heredoc body content. Reason: {reason}"
            )

    def test_simple_heredoc_body_with_cat_redirect_not_blocked(self, tmp_path):
        """Heredoc body mentioning ``cat > foo.py`` should be ignored."""
        command = (
            "gh issue create --title 'test' --body-file - <<HEREDOC\n"
            "This is the issue body. Example: cat > /tmp/x.py\n"
            "HEREDOC\n"
        )
        result = _invoke_hook(
            {
                "tool_name": "Bash",
                "tool_input": {"command": command},
            },
            tmp_path,
        )
        hook_out = result.get("hookSpecificOutput", {}) or result
        decision = hook_out.get("permissionDecision", "")
        reason = hook_out.get("permissionDecisionReason", "")
        if decision == "deny":
            assert "bash_code_file_gate" not in reason, (
                f"Heredoc body false positive: {reason}"
            )

    def test_indented_heredoc_body_not_blocked(self, tmp_path):
        """``<<-`` indented heredoc form is also covered."""
        command = (
            "\tgh issue create --title 'test' --body-file - <<-HEREDOC\n"
            "\tExample: cat > /tmp/x.py\n"
            "\tHEREDOC\n"
        )
        result = _invoke_hook(
            {
                "tool_name": "Bash",
                "tool_input": {"command": command},
            },
            tmp_path,
        )
        hook_out = result.get("hookSpecificOutput", {}) or result
        decision = hook_out.get("permissionDecision", "")
        reason = hook_out.get("permissionDecisionReason", "")
        if decision == "deny":
            assert "bash_code_file_gate" not in reason, (
                f"Indented heredoc false positive: {reason}"
            )

    def test_quoted_delimiter_heredoc_body_not_blocked(self, tmp_path):
        """``<<'HEREDOC'`` quoted-delimiter heredoc form."""
        command = (
            "gh issue create --title 'test' --body-file - <<'HEREDOC'\n"
            "cat > /tmp/x.py\n"
            "HEREDOC\n"
        )
        result = _invoke_hook(
            {
                "tool_name": "Bash",
                "tool_input": {"command": command},
            },
            tmp_path,
        )
        hook_out = result.get("hookSpecificOutput", {}) or result
        decision = hook_out.get("permissionDecision", "")
        reason = hook_out.get("permissionDecisionReason", "")
        if decision == "deny":
            assert "bash_code_file_gate" not in reason, (
                f"Quoted-delim heredoc false positive: {reason}"
            )

    # Pure-function checks — exercise the classifier directly. Faster than
    # subprocess and gives sharper failure messages.
    def test_classifier_does_not_match_heredoc_body_cat_redirect(self):
        cmd = (
            "gh issue create --body-file - <<HEREDOC\n"
            "Example: cat > /tmp/x.py\n"
            "HEREDOC\n"
        )
        target, pattern = etc.detect_bash_code_file_write(cmd)
        assert target == "", (
            f"Classifier matched heredoc-body content: target={target!r} "
            f"pattern={pattern!r}"
        )

    def test_classifier_still_matches_actual_cat_redirect(self):
        """Regression: the real outside-heredoc redirect still classifies."""
        cmd = "cat > /tmp/real.py <<EOF\nclass X: pass\nEOF\n"
        target, pattern = etc.detect_bash_code_file_write(cmd)
        assert target == "/tmp/real.py", (
            f"Lost detection of actual cat>: target={target!r}"
        )

    def test_classifier_handles_inner_heredoc_inside_outer_body(self):
        """Outer heredoc with INNER `<<HD > X.py` mention inside body."""
        cmd = (
            "gh issue create --body-file - <<HEREDOC_OUTER\n"
            "Example shown here:\n"
            "cat > /tmp/x.py <<HEREDOC_INNER\n"
            "class X: pass\n"
            "HEREDOC_INNER\n"
            "HEREDOC_OUTER\n"
        )
        target, pattern = etc.detect_bash_code_file_write(cmd)
        assert target == "", (
            f"Nested heredoc false positive: target={target!r}, pattern={pattern!r}"
        )


# ---------------------------------------------------------------------------
# AC3 — Dynamic-heredoc chained-assignment resolution (#1154)
# ---------------------------------------------------------------------------


class TestDynamicHeredocChained:
    """Chained-statement variable assignments are resolved before pattern matching."""

    def test_chained_var_resolves_to_code_file_match(self):
        """``OUT=foo.py; cat > "$OUT" << EOF \\nclass X: pass\\nEOF`` matches."""
        cmd = 'OUT=foo.py; cat > "$OUT" << EOF\nclass X: pass\nEOF\n'
        target, pattern = etc.detect_bash_code_file_write(cmd)
        assert target == "foo.py", (
            f"Chained-assignment resolution failed: target={target!r}"
        )

    def test_chained_var_non_code_extension_does_not_match(self):
        """``OUT=notes.txt; cat > "$OUT"`` MUST NOT block (.txt is not code)."""
        cmd = 'OUT=notes.txt; cat > "$OUT"'
        target, pattern = etc.detect_bash_code_file_write(cmd)
        assert target == "", (
            f".txt extension should not match — got target={target!r}, "
            f"pattern={pattern!r}"
        )

    def test_command_substitution_rhs_acknowledged_residual(self):
        """``OUT=$(echo foo).py; cat > "$OUT"`` does NOT match — documented residual."""
        cmd = 'OUT=$(echo foo).py; cat > "$OUT"'
        target, pattern = etc.detect_bash_code_file_write(cmd)
        assert target == "", (
            f"Command substitution RHS should be left unresolved (residual). "
            f"target={target!r}, pattern={pattern!r}"
        )

    @pytest.mark.parametrize(
        "deref_form",
        [
            '"$OUT"',     # double-quoted
            "${OUT}",     # brace-form
            "$OUT",       # bare
        ],
    )
    def test_all_three_dereference_forms_resolve(self, deref_form):
        """``"$OUT"``, ``${OUT}``, ``$OUT`` all resolve identically."""
        cmd = f"OUT=foo.py; cat > {deref_form}"
        target, pattern = etc.detect_bash_code_file_write(cmd)
        assert target == "foo.py", (
            f"Deref form {deref_form!r} failed to resolve: target={target!r}"
        )

    def test_newline_separator_works(self):
        """``OUT=foo.py\\ncat > "$OUT"`` — newline separator is in-scope."""
        cmd = 'OUT=foo.py\ncat > "$OUT"'
        target, pattern = etc.detect_bash_code_file_write(cmd)
        assert target == "foo.py"

    def test_single_quoted_rhs_resolves(self):
        """``OUT='foo.py'`` single-quoted literal RHS resolves."""
        cmd = "OUT='foo.py'; cat > \"$OUT\""
        target, pattern = etc.detect_bash_code_file_write(cmd)
        assert target == "foo.py"

    def test_double_quoted_rhs_without_substitution_resolves(self):
        """``OUT="foo.py"`` double-quoted literal RHS (no $) resolves."""
        cmd = 'OUT="foo.py"; cat > "$OUT"'
        target, pattern = etc.detect_bash_code_file_write(cmd)
        assert target == "foo.py"

    def test_dollar_in_double_quoted_rhs_is_not_resolved(self):
        """``OUT="$X.py"`` is out of scope — contains expansion."""
        cmd = 'OUT="$X.py"; cat > "$OUT"'
        target, pattern = etc.detect_bash_code_file_write(cmd)
        # OUT remains unresolved because RHS has $; cat > "$OUT" target is
        # literal "$OUT" — _path_is_code_file strips quotes but $OUT has no
        # .py suffix → no match.
        assert target == "", (
            f"Expansion in RHS should not resolve. target={target!r}"
        )

    def test_unrelated_assignments_do_not_match(self):
        """Variable that is not dereferenced in a write context is harmless."""
        cmd = 'NAME=foo.py; echo "hello"'
        target, pattern = etc.detect_bash_code_file_write(cmd)
        assert target == ""

    def test_chained_full_class_block_is_tier_full(self):
        """A full chained command with a new class classifies as tier=full.

        Issue #1154 remediation: the hook extracts the heredoc body from the
        Bash command and re-runs the AST classifier with the body as
        ``new_string``. The body ``class X: pass`` contains a new class,
        so the AST classifier returns ``tier=full``. This is the literal AC3
        sub-criterion from the Phase 2 plan.
        """
        cmd = 'OUT=foo.py; cat > "$OUT" << EOF\nclass X: pass\nEOF\n'
        target, pattern = etc.detect_bash_code_file_write(cmd)
        assert target == "foo.py"
        # Tier check via the hook public path: _check_bash_code_file_pipeline_required.
        block, tier, directive, target2 = hook._check_bash_code_file_pipeline_required(cmd)
        assert block is True, "Detected chained code-file write must block"
        # AC3 literal spec: chained-assignment heredoc with a new class body
        # MUST classify as tier=full (not the line-count default of light).
        assert tier == "full", (
            f"AC3 (Issue #1154): chained heredoc with `class X: pass` body "
            f"must classify as tier=full (new class). Got tier={tier!r}."
        )
        assert target2 == "foo.py"
