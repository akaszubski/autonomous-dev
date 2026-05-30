"""Unit tests for enforce_file_organization.py (Issue #1034).

Tests are in-process: the hook module is loaded via importlib and its
internal functions are exercised directly. Subprocess-level regression
coverage lives in tests/regression/test_enforce_file_organization_regression.py.

All tests run against a tmp_path fake repo (git init + project-structure.json
sandbox) so they never depend on the real autonomous-dev tree.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Module loading
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK_PATH = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "enforce_file_organization.py"
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"


def _load_hook_module():
    """Load enforce_file_organization.py as an importable module."""
    # Ensure lib/ is importable so hook_bypass/hook_safety resolve.
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    spec = importlib.util.spec_from_file_location(
        "enforce_file_organization_under_test", str(HOOK_PATH)
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = _load_hook_module()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_bypass_env(monkeypatch):
    """Make sure no leaked AUTONOMOUS_DEV_BYPASS interferes with tests."""
    monkeypatch.delenv("AUTONOMOUS_DEV_BYPASS", raising=False)


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """Initialize a tmp_path as a real git repo and return its root path.

    The repo is empty; tests stage their own files / project-structure.json.
    """
    subprocess.run(
        ["git", "init", "--quiet", str(tmp_path)],
        check=True,
        capture_output=True,
    )
    return tmp_path.resolve()


def _write_project_structure(repo: Path, allowed_files: list[str]) -> None:
    """Write a project-structure.json under the canonical templates path."""
    templates_dir = repo / "plugins" / "autonomous-dev" / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "structure": {
            "Root directory": {
                "allowed_files": allowed_files,
            }
        }
    }
    (templates_dir / "project-structure.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Pure-function tests (no I/O, no monkeypatch)
# ---------------------------------------------------------------------------


class TestPureHelpers:
    """Exercises _is_allowed and _suggest_folder directly."""

    def test_is_allowed_exact_name(self):
        assert hook._is_allowed("CLAUDE.md", {"CLAUDE.md"}) is True

    def test_is_allowed_hidden(self):
        # Empty allow-set; hidden files always pass.
        assert hook._is_allowed(".envrc", set()) is True

    def test_is_allowed_extension(self):
        assert hook._is_allowed("anything.toml", set()) is True

    def test_is_allowed_rejects_unknown(self):
        assert hook._is_allowed("notes.md", set()) is False

    def test_suggest_folder_py(self):
        assert hook._suggest_folder("foo.py") == "scripts/"

    def test_suggest_folder_test_prefix(self):
        assert hook._suggest_folder("test_foo.py") == "tests/unit/"

    def test_suggest_folder_test_suffix(self):
        assert hook._suggest_folder("foo_test.py") == "tests/unit/"

    def test_suggest_folder_unknown_returns_none(self):
        assert hook._suggest_folder("data.bin") is None


# ---------------------------------------------------------------------------
# End-to-end main() tests via stdin monkeypatching
# ---------------------------------------------------------------------------


def _run_main(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict,
    *,
    cwd: Path,
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, dict | None]:
    """Invoke hook.main() with ``payload`` on stdin and ``cwd`` as the CWD.

    Returns (exit_code, parsed_stdout_json_or_None).
    """
    import io

    monkeypatch.chdir(cwd)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    rc = hook.main()
    captured = capsys.readouterr()
    out = captured.out.strip()
    parsed: Any = None
    if out:
        try:
            parsed = json.loads(out)
        except json.JSONDecodeError:
            parsed = None
    return rc, parsed


class TestMainAllowList:
    """Files explicitly in the allow-list MUST be allowed at root."""

    def test_exact_name_allowed_readme(
        self, monkeypatch, capsys, fake_repo: Path
    ) -> None:
        _write_project_structure(fake_repo, ["README.md"])
        rc, out = _run_main(
            monkeypatch,
            {"tool_name": "Write", "tool_input": {"file_path": str(fake_repo / "README.md")}},
            cwd=fake_repo,
            capsys=capsys,
        )
        assert rc == 0
        assert out is None, f"Expected silent allow, got: {out}"

    def test_extension_allowed_pyproject_toml(
        self, monkeypatch, capsys, fake_repo: Path
    ) -> None:
        _write_project_structure(fake_repo, [])  # rely on extension fallback
        rc, out = _run_main(
            monkeypatch,
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(fake_repo / "pyproject.toml")},
            },
            cwd=fake_repo,
            capsys=capsys,
        )
        assert rc == 0
        assert out is None

    def test_hidden_file_allowed(
        self, monkeypatch, capsys, fake_repo: Path
    ) -> None:
        _write_project_structure(fake_repo, [])
        rc, out = _run_main(
            monkeypatch,
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(fake_repo / ".envrc")},
            },
            cwd=fake_repo,
            capsys=capsys,
        )
        assert rc == 0
        assert out is None


class TestMainBlock:
    """Root files outside the allow-list MUST be denied with a suggestion."""

    def test_root_py_blocked(self, monkeypatch, capsys, fake_repo: Path) -> None:
        _write_project_structure(fake_repo, [])
        rc, out = _run_main(
            monkeypatch,
            {"tool_name": "Write", "tool_input": {"file_path": str(fake_repo / "foo.py")}},
            cwd=fake_repo,
            capsys=capsys,
        )
        assert rc == 0
        assert out is not None, "expected deny JSON envelope"
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        assert "foo.py" in reason
        assert "scripts/" in reason

    def test_root_md_blocked(self, monkeypatch, capsys, fake_repo: Path) -> None:
        _write_project_structure(fake_repo, [])
        rc, out = _run_main(
            monkeypatch,
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(fake_repo / "notes.md")},
            },
            cwd=fake_repo,
            capsys=capsys,
        )
        assert rc == 0
        assert out is not None
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "docs/" in out["hookSpecificOutput"]["permissionDecisionReason"]

    def test_root_sh_blocked(self, monkeypatch, capsys, fake_repo: Path) -> None:
        _write_project_structure(fake_repo, [])
        rc, out = _run_main(
            monkeypatch,
            {"tool_name": "Write", "tool_input": {"file_path": str(fake_repo / "run.sh")}},
            cwd=fake_repo,
            capsys=capsys,
        )
        assert rc == 0
        assert out is not None
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "scripts/" in out["hookSpecificOutput"]["permissionDecisionReason"]


class TestSuggestedFolder:
    """The suggested-folder mapping must be accurate for each extension."""

    def test_suggest_tests_for_test_prefix(
        self, monkeypatch, capsys, fake_repo: Path
    ) -> None:
        _write_project_structure(fake_repo, [])
        rc, out = _run_main(
            monkeypatch,
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(fake_repo / "test_foo.py")},
            },
            cwd=fake_repo,
            capsys=capsys,
        )
        assert rc == 0
        assert out is not None
        assert "tests/unit/" in out["hookSpecificOutput"]["permissionDecisionReason"]

    def test_suggest_logs_for_jsonl(
        self, monkeypatch, capsys, fake_repo: Path
    ) -> None:
        _write_project_structure(fake_repo, [])
        rc, out = _run_main(
            monkeypatch,
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(fake_repo / "run.jsonl")},
            },
            cwd=fake_repo,
            capsys=capsys,
        )
        assert rc == 0
        assert out is not None
        assert "logs/" in out["hookSpecificOutput"]["permissionDecisionReason"]

    def test_suggest_none_for_unknown_ext(
        self, monkeypatch, capsys, fake_repo: Path
    ) -> None:
        _write_project_structure(fake_repo, [])
        rc, out = _run_main(
            monkeypatch,
            {"tool_name": "Write", "tool_input": {"file_path": str(fake_repo / "data.bin")}},
            cwd=fake_repo,
            capsys=capsys,
        )
        assert rc == 0
        assert out is not None, "expected deny even without folder suggestion"
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        # No folder suggestion present in reason text
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        assert "Suggested location:" not in reason
        assert "appropriate subdirectory" in reason


class TestSubdirectoryAllowed:
    """Files written into subdirectories MUST always be allowed."""

    def test_subdir_write_allowed(
        self, monkeypatch, capsys, fake_repo: Path
    ) -> None:
        _write_project_structure(fake_repo, [])
        scripts = fake_repo / "scripts"
        scripts.mkdir()
        rc, out = _run_main(
            monkeypatch,
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(scripts / "foo.py")},
            },
            cwd=fake_repo,
            capsys=capsys,
        )
        assert rc == 0
        assert out is None


class TestExtensibility:
    """project-structure.json's allowed_files extends the built-in allow-list."""

    def test_reads_allowed_files_from_project_structure_json(
        self, monkeypatch, capsys, fake_repo: Path
    ) -> None:
        # custom_root_doc.xyz is not in built-in allow, not a config extension,
        # not hidden — only the custom allowed_files entry can rescue it.
        _write_project_structure(fake_repo, ["custom_root_doc.xyz"])
        rc, out = _run_main(
            monkeypatch,
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(fake_repo / "custom_root_doc.xyz")},
            },
            cwd=fake_repo,
            capsys=capsys,
        )
        assert rc == 0
        assert out is None, f"expected allow, got: {out}"


class TestEdgeCases:
    """Bypass, missing template, malformed template, non-Write tools."""

    def test_bypass_env_var_skips_hook(
        self, monkeypatch, capsys, fake_repo: Path
    ) -> None:
        _write_project_structure(fake_repo, [])
        monkeypatch.setenv("AUTONOMOUS_DEV_BYPASS", "1")
        rc, out = _run_main(
            monkeypatch,
            {"tool_name": "Write", "tool_input": {"file_path": str(fake_repo / "foo.py")}},
            cwd=fake_repo,
            capsys=capsys,
        )
        assert rc == 0
        assert out is None, "bypass should produce no deny output"

    def test_missing_project_structure_json_uses_builtin_defaults(
        self, monkeypatch, capsys, fake_repo: Path
    ) -> None:
        # No project-structure.json at all — built-in allow-list + extensions
        # must still permit CLAUDE.md and a hidden file, but block foo.py.
        rc_md, out_md = _run_main(
            monkeypatch,
            {"tool_name": "Write", "tool_input": {"file_path": str(fake_repo / "CLAUDE.md")}},
            cwd=fake_repo,
            capsys=capsys,
        )
        assert rc_md == 0
        assert out_md is None

        rc_py, out_py = _run_main(
            monkeypatch,
            {"tool_name": "Write", "tool_input": {"file_path": str(fake_repo / "foo.py")}},
            cwd=fake_repo,
            capsys=capsys,
        )
        assert rc_py == 0
        assert out_py is not None
        assert out_py["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_malformed_project_structure_json_does_not_crash(
        self, monkeypatch, capsys, fake_repo: Path
    ) -> None:
        # Write a malformed JSON; hook must fall back gracefully.
        templates_dir = fake_repo / "plugins" / "autonomous-dev" / "templates"
        templates_dir.mkdir(parents=True, exist_ok=True)
        (templates_dir / "project-structure.json").write_text("{", encoding="utf-8")

        rc, out = _run_main(
            monkeypatch,
            {"tool_name": "Write", "tool_input": {"file_path": str(fake_repo / "foo.py")}},
            cwd=fake_repo,
            capsys=capsys,
        )
        # Built-in allow-list still active; foo.py still blocked.
        assert rc == 0
        assert out is not None
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
