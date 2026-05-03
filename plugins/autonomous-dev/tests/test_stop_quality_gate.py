"""Tests for stop_quality_gate.py auto pytest-gate recording — Issue #802 wiring."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_HERE = Path(__file__).resolve()
_PLUGIN_ROOT = _HERE.parents[1]
_LIB = _PLUGIN_ROOT / "lib"
_HOOKS = _PLUGIN_ROOT / "hooks"
for p in (str(_LIB), str(_HOOKS)):
    if p not in sys.path:
        sys.path.insert(0, p)

import stop_quality_gate


class TestPytestGateAutoRecord:
    def _passing_results(self):
        return {
            "pytest": {"ran": True, "passed": True, "stdout": "", "stderr": "", "error": None},
            "ruff": {"ran": False, "passed": None, "stdout": "", "stderr": "", "error": None},
            "mypy": {"ran": False, "passed": None, "stdout": "", "stderr": "", "error": None},
        }

    def _tools_pytest_only(self):
        return {
            "pytest": {"available": True, "config_file": "pytest.ini"},
            "ruff": {"available": False, "config_file": None},
            "mypy": {"available": False, "config_file": None},
        }

    def test_records_pytest_gate_when_session_real(self):
        with patch.object(stop_quality_gate, "should_enforce_quality_gate", return_value=True), \
             patch.object(stop_quality_gate, "detect_project_tools", return_value=self._tools_pytest_only()), \
             patch.object(stop_quality_gate, "run_quality_checks", return_value=self._passing_results()), \
             patch("hook_stdin.read_stdin_once", return_value={"session_id": "real-uuid"}), \
             patch("pipeline_completion_state.record_pytest_gate_passed") as record_mock:
            rc = stop_quality_gate.main()
            assert rc == 0
            record_mock.assert_called_once()
            args, kwargs = record_mock.call_args
            sid_arg = args[0] if args else kwargs.get("session_id")
            assert sid_arg == "real-uuid"

    def test_skips_record_when_session_unknown(self):
        with patch.object(stop_quality_gate, "should_enforce_quality_gate", return_value=True), \
             patch.object(stop_quality_gate, "detect_project_tools", return_value=self._tools_pytest_only()), \
             patch.object(stop_quality_gate, "run_quality_checks", return_value=self._passing_results()), \
             patch("hook_stdin.read_stdin_once", return_value=None), \
             patch("pipeline_completion_state.resolve_session_id", return_value="unknown"), \
             patch("pipeline_completion_state.record_pytest_gate_passed") as record_mock:
            rc = stop_quality_gate.main()
            assert rc == 0
            record_mock.assert_not_called()

    def test_skips_record_when_pytest_failed(self):
        results = self._passing_results()
        results["pytest"]["passed"] = False
        with patch.object(stop_quality_gate, "should_enforce_quality_gate", return_value=True), \
             patch.object(stop_quality_gate, "detect_project_tools", return_value=self._tools_pytest_only()), \
             patch.object(stop_quality_gate, "run_quality_checks", return_value=results), \
             patch("hook_stdin.read_stdin_once", return_value={"session_id": "real-uuid"}), \
             patch("pipeline_completion_state.record_pytest_gate_passed") as record_mock:
            rc = stop_quality_gate.main()
            assert rc == 0
            record_mock.assert_not_called()
