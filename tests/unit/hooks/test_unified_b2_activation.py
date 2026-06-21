"""Tests for Phase 1 default-on tier-aware Write Gate (Issue #1142+).

This test module covers the polarity flip of `_check_write_pipeline_required`
in `unified_pre_tool.py` plus the new `classify_edit_tier()` library that
replaces the old line-count heuristic.

Acceptance criteria (verbatim from plan):
- AC1: `.bypass` present -> existing line-4532 check skips all gates.
- AC2: pipeline active -> gate passes.
- AC3: Write/Edit, no `.bypass`, no pipeline, code file, not test -> blocked.
- AC4: test file edit -> pass.
- AC5: Bash command writing to code file -> blocked same as Write/Edit.
- AC6: tier `fix` (1-19 lines, no AST signal) -> directive `/implement --fix`.
- AC7: tier `light` (new func / control-flow / 20-99 lines) -> directive
       `/implement --light`.
- AC8: tier `full` (new class OR >=100 lines) -> directive `/implement`.
- AC9: new-file Write (empty old_string) classified by content lines.
- AC10: non-Python code file -> line-count fallback returns `light` (safe
        default).
- AC11: AST classifier edge cases (comment / format / import-reorder /
        type-hint / docstring-only) all classify as `fix`.

Issue: #1142 (Phase 1 polarity flip).
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

# Path setup: load hook + lib via sys.path manipulation.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_HOOK_DIR = _REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
_LIB_DIR = _REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
for p in (str(_LIB_DIR), str(_HOOK_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import edit_tier_classifier as etc  # noqa: E402
import unified_pre_tool as hook  # noqa: E402


def _run_main_with_tool(tool_name: str, tool_input: dict, monkeypatch, capsys) -> dict:
    """Drive ``hook.main()`` end-to-end with a synthesized PreToolUse payload.

    The hook reads JSON from stdin, writes its decision JSON to stdout, and
    calls ``sys.exit(0)``. This helper mocks stdin, captures stdout via the
    ``capsys`` fixture, swallows ``SystemExit``, and returns the parsed
    ``hookSpecificOutput`` dict so tests can assert on
    ``permissionDecision`` and ``permissionDecisionReason``.
    """
    payload = {
        "session_id": "test_b2_session",
        "tool_name": tool_name,
        "tool_input": tool_input,
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    try:
        hook.main()
    except SystemExit:
        pass  # main() always exits; we just need its stdout
    captured = capsys.readouterr()
    # Hook may emit multiple lines (e.g. telemetry); decision JSON is the
    # last non-empty line on stdout.
    for line in reversed(captured.out.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "hookSpecificOutput" in parsed:
            return parsed["hookSpecificOutput"]
    raise AssertionError(
        f"hook.main() produced no decision JSON. stdout={captured.out!r} "
        f"stderr={captured.err!r}"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pipeline_active(monkeypatch) -> None:
    monkeypatch.setattr(hook, "_is_pipeline_active", lambda: True)


def _make_pipeline_inactive(monkeypatch) -> None:
    monkeypatch.setattr(hook, "_is_pipeline_active", lambda: False)


@pytest.fixture(autouse=True)
def default_state(monkeypatch):
    """Each test starts with the pipeline NOT active and the one-shot skip
    file absent. .bypass is NOT installed (callers use it explicitly).
    """
    _make_pipeline_inactive(monkeypatch)
    skip_file = Path("/tmp/skip_write_pipeline_gate")
    if skip_file.exists():
        try:
            skip_file.unlink()
        except OSError:
            pass


# ===========================================================================
# AC1: Universal bypass kill switch (end-to-end via hook entrypoint)
# ===========================================================================


class TestUniversalBypassShortCircuit:
    """AC1: when the universal bypass is active (`.claude/.bypass` marker OR
    ``AUTONOMOUS_DEV_BYPASS=1`` env var), the default-on tier-aware Write/Edit
    gate MUST be short-circuited and the edit MUST be allowed — even when the
    edit would otherwise be a ``full`` tier block.

    These are END-TO-END integration tests that drive ``hook.main()`` through
    the same stdin/stdout protocol Claude Code uses at runtime. The
    classifier-level coverage in ``TestDefaultOnGate`` exercises
    ``_check_write_pipeline_required`` directly; this class proves the
    universal-bypass short-circuit at line ~4632 actually wins over the
    downstream Write/Edit gate.
    """

    def _full_tier_payload(self) -> dict:
        """Build a Write payload that — absent the bypass — would block as
        ``full`` tier (new class added to app.py). If the bypass is broken
        and the gate runs, the assertion ``decision == "allow"`` fails
        loudly and the test surfaces a real regression.
        """
        new_class = (
            "import os\n"
            "\n"
            "class NewFeature:\n"
            "    def __init__(self):\n"
            "        self.x = 1\n"
            "\n"
            "    def run(self):\n"
            "        return self.x\n"
        )
        return {
            "file_path": "/repo/src/app.py",
            "old_string": "",
            "new_string": new_class,
            "content": new_class,
        }

    def test_bypass_marker_skips_gate(self, tmp_path, monkeypatch, capsys):
        """AC1: ``.claude/.bypass`` marker in cwd short-circuits the gate."""
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / ".bypass").touch()
        monkeypatch.chdir(tmp_path)
        # Ensure the env-var path is NOT what causes the bypass — we are
        # validating the marker file specifically.
        monkeypatch.delenv("AUTONOMOUS_DEV_BYPASS", raising=False)

        result = _run_main_with_tool(
            "Write", self._full_tier_payload(), monkeypatch, capsys,
        )
        assert result["permissionDecision"] == "allow", (
            f"`.claude/.bypass` marker MUST short-circuit the default-on "
            f"Write gate even for a `full` tier edit. "
            f"Got: {result!r}"
        )

    def test_autonomous_dev_bypass_env_skips_gate(
        self, tmp_path, monkeypatch, capsys,
    ):
        """AC1: ``AUTONOMOUS_DEV_BYPASS=1`` env var short-circuits the gate.

        Independent path from the marker file: even with NO `.bypass` file
        present, the env var alone MUST be sufficient.
        """
        monkeypatch.chdir(tmp_path)  # No .claude/.bypass marker installed.
        monkeypatch.setenv("AUTONOMOUS_DEV_BYPASS", "1")

        result = _run_main_with_tool(
            "Write", self._full_tier_payload(), monkeypatch, capsys,
        )
        assert result["permissionDecision"] == "allow", (
            f"AUTONOMOUS_DEV_BYPASS=1 MUST short-circuit the default-on "
            f"Write gate even for a `full` tier edit. "
            f"Got: {result!r}"
        )


# ===========================================================================
# AC5: Bash dispatch integration (end-to-end via hook entrypoint)
# ===========================================================================


class TestBashDispatchIntegration:
    """AC5: Bash commands that write to code files MUST block end-to-end via
    the hook entrypoint, not merely via the standalone classifier function.

    ``TestBashCodeFileDetection`` covers ``detect_bash_code_file_write()`` in
    isolation. This class exercises the full main() -> Bash dispatch ->
    ``_check_bash_code_file_pipeline_required`` -> ``output_decision("deny")``
    chain that the runtime hook actually walks.
    """

    def test_bash_cat_redirect_blocked_with_tier_directive(
        self, tmp_path, monkeypatch, capsys,
    ):
        """AC5: heredoc cat-redirect to a code file blocks with a tier
        directive that points at /implement.
        """
        # Run from a directory that has NO `.claude/.bypass` marker installed
        # so the gate is allowed to fire. Also clear the env-var bypass.
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("AUTONOMOUS_DEV_BYPASS", raising=False)

        cat_heredoc = (
            "cat > /tmp/foo.py <<EOF\n"
            "class X:\n"
            "    pass\n"
            "EOF"
        )
        result = _run_main_with_tool(
            "Bash", {"command": cat_heredoc}, monkeypatch, capsys,
        )
        assert result["permissionDecision"] == "deny", (
            f"Bash heredoc redirect into a .py file with a new class MUST "
            f"deny via the hook entrypoint (AC5 end-to-end). "
            f"Got: {result!r}"
        )
        assert "/implement" in result["permissionDecisionReason"], (
            f"Deny reason MUST include the /implement tier directive. "
            f"Got reason: {result['permissionDecisionReason']!r}"
        )


# ===========================================================================
# AC1 + AC2: Pre-existing fast paths (already covered indirectly; smoke test)
# ===========================================================================


class TestPipelineActiveAllows:
    """AC2: pipeline-active is a fast path that allows all edits."""

    def test_pipeline_active_allows_substantive_edit(self, monkeypatch):
        _make_pipeline_active(monkeypatch)
        big = "\n".join(f"def f_{i}(): pass" for i in range(50))
        block, tier, directive = hook._check_write_pipeline_required(
            "Write", "/repo/src/app.py", "", big,
        )
        assert block is False
        assert tier == "pipeline_active"
        assert directive == ""


# ===========================================================================
# AC3 + AC8: Default-on — substantive edits to code files block by default
# ===========================================================================


class TestDefaultOnGate:
    """AC3: without .bypass and without pipeline, code-file edits block."""

    def test_full_tier_blocks_with_full_directive(self):
        # New class definition with >=100 lines triggers `full` tier.
        new = "class NewThing:\n" + "\n".join(f"    x_{i} = {i}" for i in range(120))
        block, tier, directive = hook._check_write_pipeline_required(
            "Write", "/repo/src/models.py", "", new,
        )
        assert block is True
        assert tier == "full"
        assert "/implement" in directive
        # `full` tier must use the bare /implement (not --fix / --light).
        assert "--fix" not in directive
        assert "--light" not in directive

    def test_new_class_alone_blocks_full(self):
        old = "x = 1\n"
        new = "x = 1\n\nclass Brand:\n    pass\n"
        block, tier, directive = hook._check_write_pipeline_required(
            "Edit", "/repo/src/handlers.py", old, new,
        )
        assert block is True
        assert tier == "full"
        assert "/implement" in directive

    def test_light_tier_blocks_with_light_directive(self):
        # New function alone -> light
        old = "x = 1\n"
        new = "x = 1\n\ndef new_handler():\n    return 1\n"
        block, tier, directive = hook._check_write_pipeline_required(
            "Edit", "/repo/src/handlers.py", old, new,
        )
        assert block is True
        assert tier == "light"
        assert "/implement --light" in directive

    def test_fix_tier_blocks_with_fix_directive(self):
        # Small constant change <20 lines, no AST signal -> fix
        old = "TIMEOUT = 30\n"
        new = "TIMEOUT = 60\nRETRY = 3\n"
        block, tier, directive = hook._check_write_pipeline_required(
            "Edit", "/repo/src/settings.py", old, new,
        )
        # diff = 1 line; AST identical structure (just const changes) => fix
        assert block is True
        assert tier == "fix"
        assert "/implement --fix" in directive


# ===========================================================================
# AC4: Test files always pass
# ===========================================================================


class TestTestFileExclusion:
    @pytest.mark.parametrize("file_path", [
        "/repo/tests/test_models.py",
        "/repo/test/unit_test.py",
        "/repo/src/test_service.py",
        "/repo/src/service_test.py",
    ])
    def test_test_files_pass(self, file_path):
        big = "\n".join(f"def test_x_{i}(): pass" for i in range(50))
        block, tier, _ = hook._check_write_pipeline_required(
            "Edit", file_path, "", big,
        )
        assert block is False
        assert tier == "tier0_test_file"


# ===========================================================================
# AC5: Bash detection
# ===========================================================================


class TestBashCodeFileDetection:
    """Bash patterns that write to code files must be detected."""

    @pytest.mark.parametrize("command,expected_pattern", [
        ("cat > app.py", "cat redirect"),
        ("cat >> app.py", "cat redirect"),
        ("tee app.py", "tee"),
        ("tee -a app.py", "tee"),
        ("sed -i 's/old/new/g' app.py", "sed -i"),
        ("python -c \"open('app.py', 'w').write('x')\"", "python -c open()"),
        ("python3 -c \"open('app.py', 'w').write('x')\"", "python -c open()"),
        ("cat > app.py << 'EOF'\nfoo\nEOF", "cat redirect"),
        ("echo 'aGVsbG8=' | base64 -d > app.py", "base64 decode redirect"),
        ("awk '{print $1}' input.txt > out.py", "awk redirect"),
    ])
    def test_bash_pattern_detected(self, command, expected_pattern):
        target, pattern = etc.detect_bash_code_file_write(command)
        assert target != "", f"expected detection for {command!r}"
        assert pattern == expected_pattern

    @pytest.mark.parametrize("command", [
        "git apply patch.diff",
        "patch < some.diff",
        "patch -p1 < changes.diff",
        # Non-code files: README writes pass through.
        "cat > README.md",
        "echo foo > log.txt",
        # Pure read operations.
        "cat app.py",
        "grep foo app.py",
    ])
    def test_bash_excluded_or_irrelevant(self, command):
        target, _ = etc.detect_bash_code_file_write(command)
        assert target == "", f"unexpected detection for {command!r}"


# ===========================================================================
# AC9: New-file Write classification (empty old_string)
# ===========================================================================


class TestNewFileWriteClassification:
    def test_new_file_under_20_lines_is_fix(self):
        new = "\n".join(f"x_{i} = {i}" for i in range(10))
        tier, _ = etc.classify_edit_tier("/repo/app.py", "", new)
        assert tier == "fix"

    def test_new_file_20_to_99_lines_is_light(self):
        new = "\n".join(f"x_{i} = {i}" for i in range(50))
        tier, _ = etc.classify_edit_tier("/repo/app.py", "", new)
        assert tier == "light"

    def test_new_file_100_plus_lines_is_full(self):
        new = "\n".join(f"x_{i} = {i}" for i in range(150))
        tier, _ = etc.classify_edit_tier("/repo/app.py", "", new)
        assert tier == "full"

    def test_new_file_with_class_is_full(self):
        new = "class Thing:\n    pass\n"
        tier, _ = etc.classify_edit_tier("/repo/app.py", "", new)
        assert tier == "full"


# ===========================================================================
# AC10: Non-Python code files
# ===========================================================================


class TestNonPythonFallback:
    @pytest.mark.parametrize("path,added", [
        ("/repo/app.ts", "let x = 1;"),
        ("/repo/app.go", "package main\nfunc main(){}"),
        ("/repo/app.rs", "fn main(){}"),
        ("/repo/app.js", "const a = 1;"),
        ("/repo/app.cpp", "int main(){return 0;}"),
    ])
    def test_non_python_returns_light_safe_default(self, path, added):
        tier, _ = etc.classify_edit_tier(path, "", added)
        assert tier == "light"

    def test_non_python_100_plus_lines_is_full(self):
        new = "\n".join(f"line_{i};" for i in range(150))
        tier, _ = etc.classify_edit_tier("/repo/app.ts", "", new)
        assert tier == "full"


# ===========================================================================
# AC11: AST classifier edge cases all -> fix
# ===========================================================================


class TestASTEdgeCasesAllFix:
    """Comment-only / format-only / import-reorder / type-hint / docstring
    edits must all classify as `fix` because they introduce no behavioral
    change."""

    def test_comment_only_edit_is_fix(self):
        old = "x = 1\ny = 2\n"
        new = "x = 1\n# explanation\ny = 2\n"
        tier, reason = etc.classify_edit_tier("/repo/app.py", old, new)
        assert tier == "fix", f"got {tier} ({reason})"

    def test_formatting_only_edit_is_fix(self):
        old = "x=1\ny=2\n"
        new = "x = 1\ny = 2\n"
        tier, _ = etc.classify_edit_tier("/repo/app.py", old, new)
        assert tier == "fix"

    def test_import_reorder_is_fix(self):
        old = "import os\nimport sys\nimport json\n"
        new = "import json\nimport os\nimport sys\n"
        tier, _ = etc.classify_edit_tier("/repo/app.py", old, new)
        assert tier == "fix"

    def test_type_hint_only_is_fix(self):
        old = "def f(x):\n    return x\n"
        new = "def f(x: int) -> int:\n    return x\n"
        tier, _ = etc.classify_edit_tier("/repo/app.py", old, new)
        assert tier == "fix"

    def test_docstring_only_is_fix(self):
        old = 'def f():\n    return 1\n'
        new = 'def f():\n    """new docstring"""\n    return 1\n'
        tier, _ = etc.classify_edit_tier("/repo/app.py", old, new)
        assert tier == "fix"


# ===========================================================================
# AC6 + AC7 + AC8 direct AST tier tests
# ===========================================================================


class TestTierBoundaries:
    """Direct tests of classify_edit_tier without going through the gate."""

    def test_new_function_is_light(self):
        old = "x = 1\n"
        new = "x = 1\n\ndef f():\n    return 1\n"
        tier, _ = etc.classify_edit_tier("/repo/app.py", old, new)
        assert tier == "light"

    def test_control_flow_added_is_light(self):
        old = "def f(x):\n    return x\n"
        new = "def f(x):\n    if x:\n        return x\n    return 0\n"
        tier, _ = etc.classify_edit_tier("/repo/app.py", old, new)
        assert tier == "light"

    def test_signature_change_is_light(self):
        old = "def f(x):\n    return x\n"
        new = "def f(x, y):\n    return x + y\n"
        tier, _ = etc.classify_edit_tier("/repo/app.py", old, new)
        assert tier == "light"

    def test_new_class_is_full(self):
        old = "x = 1\n"
        new = "x = 1\n\nclass Brand:\n    pass\n"
        tier, _ = etc.classify_edit_tier("/repo/app.py", old, new)
        assert tier == "full"

    def test_100_plus_lines_is_full(self):
        old = ""
        new = "\n".join(f"x_{i} = {i}" for i in range(120))
        tier, _ = etc.classify_edit_tier("/repo/app.py", old, new)
        assert tier == "full"

    def test_20_to_99_lines_no_ast_is_light(self):
        old = ""
        new = "\n".join(f"x_{i} = {i}" for i in range(40))
        tier, _ = etc.classify_edit_tier("/repo/app.py", old, new)
        assert tier == "light"

    def test_small_constant_change_is_fix(self):
        old = "VAL = 1\n"
        new = "VAL = 2\n"
        tier, _ = etc.classify_edit_tier("/repo/app.py", old, new)
        assert tier == "fix"


# ===========================================================================
# Gate path tests: tier_label produced by gate matches AC6/7/8
# ===========================================================================


class TestGateTierLabel:
    def test_gate_fix_tier_label(self):
        block, tier, directive = hook._check_write_pipeline_required(
            "Edit", "/repo/src/app.py", "x = 1\n", "x = 2\n",
        )
        assert block is True
        assert tier == "fix"
        assert "/implement --fix" in directive

    def test_gate_light_tier_label_new_function(self):
        old = "x = 1\n"
        new = "x = 1\n\ndef helper():\n    return 1\n"
        block, tier, directive = hook._check_write_pipeline_required(
            "Edit", "/repo/src/app.py", old, new,
        )
        assert block is True
        assert tier == "light"
        assert "/implement --light" in directive

    def test_gate_full_tier_label_new_class(self):
        old = "x = 1\n"
        new = "x = 1\n\nclass Brand:\n    pass\n"
        block, tier, directive = hook._check_write_pipeline_required(
            "Edit", "/repo/src/app.py", old, new,
        )
        assert block is True
        assert tier == "full"
        # `full` tier directive is bare /implement, not --fix or --light.
        assert "--fix" not in directive
        assert "--light" not in directive
        assert "/implement" in directive


# ===========================================================================
# No-path and non-code path
# ===========================================================================


class TestPassthroughs:
    def test_empty_path_no_block(self):
        block, tier, _ = hook._check_write_pipeline_required(
            "Edit", "", "old", "new",
        )
        assert block is False
        assert tier == "no_path"

    def test_non_code_extension_no_block(self):
        big = "\n".join(f"line {i}" for i in range(100))
        block, tier, _ = hook._check_write_pipeline_required(
            "Write", "/repo/README.md", "", big,
        )
        assert block is False
        assert tier == "tier0_non_code"


# ===========================================================================
# Hook module integrity: no stale .enforce references
# ===========================================================================


class TestNoEnforceReferences:
    """Regression lock: the polarity flip deletes the .enforce mechanism.
    These tests ensure the module-level bindings and wrapper function are
    gone so a future agent doesn't accidentally re-introduce them.
    """

    def test_no_check_enforce_marker_attribute(self):
        assert not hasattr(hook, "_check_enforce_marker"), (
            "_check_enforce_marker was removed by the polarity flip — "
            "see Issue #1142 Phase 1 plan."
        )

    def test_no_enforce_marker_fn_attribute(self):
        assert not hasattr(hook, "_enforce_marker_fn"), (
            "_enforce_marker_fn module-level binding was removed — "
            "see Issue #1142 Phase 1 plan."
        )

    def test_classify_edit_tier_available(self):
        """The gate must be able to import classify_edit_tier."""
        # If the hook can locate it (via lib path), the symbol exists in the
        # classifier module.
        assert hasattr(etc, "classify_edit_tier")


# ===========================================================================
# Issue #1152: No duplicate opt-out hints
# ===========================================================================


class TestNoDuplicateOptOutHints:
    """Regression test for Issue #1152: opt-out hint appears only once."""
    
    def test_write_denial_has_single_opt_out_hint(self, tmp_path, monkeypatch, capsys):
        """Write/Edit denial reason must contain exactly one opt-out hint."""
        # Run from a directory that has NO `.claude/.bypass` marker
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("AUTONOMOUS_DEV_BYPASS", raising=False)
        
        # Make pipeline inactive to trigger the deny path
        _make_pipeline_inactive(monkeypatch)
        
        # Create a substantial edit that will trigger full tier
        new_content = "class NewThing:\n" + "\n".join(f"    x_{i} = {i}" for i in range(120))
        
        result = _run_main_with_tool(
            "Write", 
            {"file_path": "/repo/src/models.py", "content": new_content},
            monkeypatch, 
            capsys,
        )
        
        assert result["permissionDecision"] == "deny", (
            f"Write to code file without pipeline must deny. Got: {result!r}"
        )
        
        reason = result.get("permissionDecisionReason", "")
        opt_out_count = reason.count("Per-repo opt-out: touch .claude/.bypass && git commit.")
        assert opt_out_count == 1, (
            f"Opt-out hint must appear exactly ONCE in denial reason (Issue #1152). "
            f"Found {opt_out_count} occurrences in: {reason!r}"
        )
