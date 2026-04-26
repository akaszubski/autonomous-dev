"""Unit tests for ``scripts/audit_hook_recovery.py`` (Issue #970)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "audit_hook_recovery.py"


@pytest.fixture(scope="module")
def audit_module():
    """Load the audit script as an importable module."""
    spec = importlib.util.spec_from_file_location(
        "audit_hook_recovery", str(SCRIPT_PATH)
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so @dataclass can resolve the module via sys.modules
    # (Python 3.14 dataclass resolver requirement).
    sys.modules["audit_hook_recovery"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def fake_target(tmp_path: Path) -> Path:
    """Write a synthetic source file with one unjustified deny site."""
    target = tmp_path / "fake_unified_pre_tool.py"
    target.write_text(
        '''
def gate_one(tool_name, tool_input):
    if tool_name == "Bad":
        output_decision("deny", "blocked: bad tool")
        return

def gate_two(tool_name):
    if True:
        log_block_with_recovery(
            hook_name="x", tool_name=tool_name,
            block_reason="x", recovery_hint="y",
        )
        output_decision("deny", "blocked: covered")
'''.lstrip()
    )
    return target


class TestAuditHookRecovery:
    def test_audit_file_importable_api(self, audit_module, fake_target):
        """The module must expose ``audit_file`` callable."""
        assert callable(audit_module.audit_file)
        violations = audit_module.audit_file(fake_target)
        assert isinstance(violations, list)
        # gate_one is uncovered; gate_two has a log call
        assert len(violations) == 1
        assert violations[0].function_name == "gate_one"

    def test_warn_only_mode_default_exits_zero(
        self, audit_module, fake_target, capsys
    ):
        rc = audit_module.main(["--target", str(fake_target)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "1 unjustified" in out

    def test_strict_mode_exits_one_on_violation(
        self, audit_module, fake_target, capsys
    ):
        rc = audit_module.main(["--strict", "--target", str(fake_target)])
        assert rc == 1

    def test_strict_mode_exits_zero_when_clean(
        self, audit_module, tmp_path, capsys
    ):
        clean = tmp_path / "clean.py"
        clean.write_text(
            '''
def gate(tool_name):
    log_block_with_recovery(
        hook_name="x", tool_name=tool_name,
        block_reason="x", recovery_hint="y",
    )
    output_decision("deny", "ok")
'''.lstrip()
        )
        rc = audit_module.main(["--strict", "--target", str(clean)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "clean" in out

    def test_exemption_registry_respected(
        self, audit_module, tmp_path, monkeypatch, capsys
    ):
        # Create a target with one deny line containing the exempted phrase.
        target = tmp_path / "exempt_target.py"
        target.write_text(
            '''
def gate(tool_name):
    output_decision("deny", "EXEMPT-PHRASE: rationale")
'''.lstrip()
        )
        # Monkeypatch the registry path to a tmp file with the exemption.
        registry = tmp_path / "exemptions.json"
        registry.write_text(
            json.dumps(
                {
                    "version": 1,
                    "exemptions": [
                        {
                            "hook_name": "anything",
                            "block_reason_contains": "EXEMPT-PHRASE",
                        }
                    ],
                }
            )
        )
        monkeypatch.setattr(audit_module, "EXEMPTION_REGISTRY", registry)

        violations = audit_module.audit_file(target)
        assert violations == []

    def test_missing_target_file_handled_gracefully(
        self, audit_module, tmp_path, capsys
    ):
        missing = tmp_path / "does_not_exist.py"
        violations = audit_module.audit_file(missing)
        assert violations == []
        rc = audit_module.main(["--target", str(missing)])
        # Default WARN-ONLY -> exit 0 even if target missing.
        assert rc == 0
