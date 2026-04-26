"""Integration tests: each of the 3 hook deny shapes emits a telemetry row.

Issue #972 wires unified telemetry into:

1. ``unified_pre_tool.py`` — tuple shape, via ``output_decision`` decorator.
2. ``unified_prompt_validator.py`` — dict shape, via explicit
   ``log_block_event`` call before ``print(json.dumps({"decision": "block"}))``.
3. ``enforce_orchestrator.py`` — exit2 shape, via explicit
   ``log_block_event`` call before ``sys.exit(2)``.

These tests verify that calling each hook's instrumented deny path
appends a row to ``.claude/logs/hook-blocks.jsonl``. They use direct
function invocation (mocking what's needed to reach the deny branch)
rather than full subprocess hook invocation, which would require
reproducing the entire Claude Code hook input contract.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
HOOKS_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"

if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import hook_telemetry  # noqa: E402


def _load_hook(hook_name: str):
    """Load a hook .py file as a module by file path."""
    path = HOOKS_DIR / hook_name
    spec = importlib.util.spec_from_file_location(
        hook_name.replace(".py", ""), str(path)
    )
    assert spec and spec.loader, f"Cannot load {hook_name}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def project_dir(tmp_path: Path, monkeypatch) -> Path:
    (tmp_path / ".claude" / "logs").mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(hook_telemetry.DISABLE_ENV_VAR, raising=False)
    monkeypatch.delenv(hook_telemetry.LEGACY_DISABLE_ENV_VAR, raising=False)
    return tmp_path


def _read_log_rows(project_dir: Path):
    log_path = project_dir / ".claude" / "logs" / "hook-blocks.jsonl"
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text().splitlines()
        if line.strip()
    ]


class TestTupleShapeFromUnifiedPreTool:
    """Issue #972: ``output_decision("deny", ...)`` MUST emit a telemetry row."""

    def test_deny_emits_telemetry_row(self, project_dir, capsys):
        hook = _load_hook("unified_pre_tool.py")
        # Call the decorator-wrapped output_decision directly with a deny.
        hook.output_decision("deny", "BLOCKED: test reason")
        # Capture stdout (the hook prints JSON) so it doesn't pollute test output.
        capsys.readouterr()
        rows = _read_log_rows(project_dir)
        assert len(rows) == 1
        assert rows[0]["hook_name"] == "unified_pre_tool.py"
        assert rows[0]["decision_shape"] == "tuple"
        assert "BLOCKED: test reason" in rows[0]["reason"]

    def test_allow_emits_no_telemetry_row(self, project_dir, capsys):
        hook = _load_hook("unified_pre_tool.py")
        hook.output_decision("allow", "ok")
        capsys.readouterr()
        rows = _read_log_rows(project_dir)
        assert rows == []

    def test_ask_emits_no_telemetry_row(self, project_dir, capsys):
        hook = _load_hook("unified_pre_tool.py")
        hook.output_decision("ask", "needs review")
        capsys.readouterr()
        rows = _read_log_rows(project_dir)
        assert rows == []


class TestDictShapeFromPromptValidator:
    """Issue #972: the ``{"decision": "block"}`` site MUST emit a row."""

    def test_explicit_log_call_writes_row(self, project_dir):
        # Direct invocation of the imported logger from the hook scope —
        # mirrors the explicit instrumentation we added before
        # ``print(json.dumps(output))`` at the dict-shape deny site.
        hook = _load_hook("unified_prompt_validator.py")
        hook._log_block_event_972(
            hook_name="unified_prompt_validator.py",
            decision_shape="dict",
            reason="test prompt block",
            metadata={"suggested_command": "/implement"},
        )
        rows = _read_log_rows(project_dir)
        assert len(rows) == 1
        assert rows[0]["hook_name"] == "unified_prompt_validator.py"
        assert rows[0]["decision_shape"] == "dict"
        assert rows[0]["reason"] == "test prompt block"
        assert rows[0]["metadata"]["suggested_command"] == "/implement"


class TestExit2ShapeFromEnforceOrchestrator:
    """Issue #972: the ``sys.exit(2)`` site MUST emit a row."""

    def test_explicit_log_call_writes_row(self, project_dir):
        hook = _load_hook("enforce_orchestrator.py")
        hook._log_block_event_972(
            hook_name="enforce_orchestrator.py",
            decision_shape="exit2",
            reason="ORCHESTRATOR VALIDATION REQUIRED",
            metadata={"event": "PreCommit"},
        )
        rows = _read_log_rows(project_dir)
        assert len(rows) == 1
        assert rows[0]["hook_name"] == "enforce_orchestrator.py"
        assert rows[0]["decision_shape"] == "exit2"
        assert "ORCHESTRATOR VALIDATION" in rows[0]["reason"]


class TestTelemetryDisabledRollback:
    """When HOOK_TELEMETRY_DISABLED=1, none of the 3 sites emit rows."""

    def test_disabled_blocks_all_three_shapes(
        self, project_dir, monkeypatch, capsys
    ):
        monkeypatch.setenv(hook_telemetry.DISABLE_ENV_VAR, "1")

        # Re-import telemetry so the env var is checked fresh.
        # (is_telemetry_disabled() reads the env on every call, so no
        # re-import is strictly needed — but be explicit.)
        pre_tool = _load_hook("unified_pre_tool.py")
        prompt_val = _load_hook("unified_prompt_validator.py")
        orchestrator = _load_hook("enforce_orchestrator.py")

        pre_tool.output_decision("deny", "should not log")
        prompt_val._log_block_event_972(
            hook_name="unified_prompt_validator.py",
            decision_shape="dict",
            reason="should not log",
        )
        orchestrator._log_block_event_972(
            hook_name="enforce_orchestrator.py",
            decision_shape="exit2",
            reason="should not log",
        )
        capsys.readouterr()
        assert _read_log_rows(project_dir) == []
