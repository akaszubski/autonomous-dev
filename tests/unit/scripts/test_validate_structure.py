"""Unit tests for component-count drift check in scripts/validate_structure.py (Issue #1140)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "validate_structure.py"


@pytest.fixture(scope="module")
def validate_module() -> Any:
    """Load validate_structure.py as an importable module."""
    spec = importlib.util.spec_from_file_location(
        "validate_structure", str(SCRIPT_PATH)
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["validate_structure"] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_fake_plugin(
    tmp_path: Path,
    *,
    agents: int = 3,
    commands: int = 4,
    skills: int = 2,
    hooks: int = 5,
    libraries: int = 7,
) -> Path:
    """Build a minimal plugin directory tree for testing."""
    plugin = tmp_path / "plugins" / "autonomous-dev"
    # agents
    (plugin / "agents").mkdir(parents=True)
    for i in range(agents):
        (plugin / "agents" / f"agent{i}.md").write_text("x")
    # commands
    (plugin / "commands").mkdir(parents=True)
    for i in range(commands):
        (plugin / "commands" / f"cmd{i}.md").write_text("x")
    # skills (each is a subdir with SKILL.md)
    (plugin / "skills").mkdir(parents=True)
    for i in range(skills):
        d = plugin / "skills" / f"skill{i}"
        d.mkdir()
        (d / "SKILL.md").write_text("x")
    # hooks
    (plugin / "hooks").mkdir(parents=True)
    for i in range(hooks):
        (plugin / "hooks" / f"hook{i}.py").write_text("x")
    # lib (flat)
    (plugin / "lib").mkdir(parents=True)
    for i in range(libraries):
        (plugin / "lib" / f"lib{i}.py").write_text("x")
    return plugin


def _write_claude_md(
    tmp_path: Path,
    *,
    agents: int,
    skills: int,
    commands: int,
    hooks: int,
    libraries: int,
) -> Path:
    """Write a CLAUDE.md with the canonical Component counts line."""
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text(
        f"# autonomous-dev\n\n"
        f"Component counts: {agents} agents, {skills} skills, "
        f"{commands} commands, {hooks} hooks, {libraries} libraries. "
        f"Full diagram and layer breakdown in docs/ARCHITECTURE-OVERVIEW.md.\n"
    )
    return claude_md


class TestComponentCountDriftCheck:
    """Tests for check_component_count_drift() — Issue #1140."""

    def test_component_count_check_passes_when_counts_match(
        self, validate_module: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No errors when CLAUDE.md counts match the fake plugin tree exactly."""
        plugin = _make_fake_plugin(
            tmp_path, agents=3, commands=4, skills=2, hooks=5, libraries=7
        )
        claude_md = _write_claude_md(
            tmp_path, agents=3, skills=2, commands=4, hooks=5, libraries=7
        )
        monkeypatch.setattr(validate_module, "PLUGIN", plugin)
        monkeypatch.setattr(validate_module, "CLAUDE_MD", claude_md)

        errors = validate_module.check_component_count_drift()

        assert errors == [], f"Expected no errors, got: {errors}"

    def test_component_count_check_reports_each_drifted_component(
        self, validate_module: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two drifted components each produce a distinct error naming the component."""
        # Actual tree: 3 agents, 4 commands, 2 skills, 5 hooks, 7 libraries
        plugin = _make_fake_plugin(
            tmp_path, agents=3, commands=4, skills=2, hooks=5, libraries=7
        )
        # CLAUDE.md claims wrong counts for agents (999) and hooks (999)
        claude_md = _write_claude_md(
            tmp_path, agents=999, skills=2, commands=4, hooks=999, libraries=7
        )
        monkeypatch.setattr(validate_module, "PLUGIN", plugin)
        monkeypatch.setattr(validate_module, "CLAUDE_MD", claude_md)

        errors = validate_module.check_component_count_drift()

        assert len(errors) == 2, f"Expected exactly 2 errors, got {len(errors)}: {errors}"
        # Each error must name the component
        assert any("agents" in e for e in errors), "Expected an error mentioning 'agents'"
        assert any("hooks" in e for e in errors), "Expected an error mentioning 'hooks'"

    def test_component_count_check_handles_missing_summary_line(
        self, validate_module: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CLAUDE.md exists but has no Component counts: line → one specific error."""
        plugin = _make_fake_plugin(tmp_path)
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# autonomous-dev\n\nNo component summary here.\n")
        monkeypatch.setattr(validate_module, "PLUGIN", plugin)
        monkeypatch.setattr(validate_module, "CLAUDE_MD", claude_md)

        errors = validate_module.check_component_count_drift()

        assert len(errors) == 1, f"Expected exactly 1 error, got {len(errors)}: {errors}"
        assert "summary line missing" in errors[0] or "missing or malformed" in errors[0], (
            f"Error should mention missing summary line, got: {errors[0]}"
        )

    def test_validate_structure_main_includes_count_check(
        self,
        validate_module: Any,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """main() includes component-count check: sentinel error → exit 1 + printed error."""
        # Stub existing checks to return no errors
        monkeypatch.setattr(validate_module, "check_doc_locations", lambda: [])
        monkeypatch.setattr(validate_module, "check_no_duplicates", lambda: [])
        monkeypatch.setattr(validate_module, "check_root_cleanliness", lambda: [])
        monkeypatch.setattr(validate_module, "check_claude_not_tracked", lambda: [])
        # Stub count check to return a sentinel error
        monkeypatch.setattr(
            validate_module,
            "check_component_count_drift",
            lambda: ["sentinel error from count drift"],
        )

        exit_code = validate_module.main()
        captured = capsys.readouterr()

        assert exit_code == 1, f"Expected exit code 1 when drift detected, got {exit_code}"
        assert "sentinel error from count drift" in captured.out, (
            f"Sentinel error not in stdout. Output was:\n{captured.out}"
        )
