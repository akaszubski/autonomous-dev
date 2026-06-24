"""Unit tests for component-count drift check in scripts/validate_structure.py (Issue #1140)."""

from __future__ import annotations

import importlib.util
import subprocess
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


class TestSummaryRegex:
    """Tests for SUMMARY_RE regex — bare and 'user-facing' qualifier variants."""

    def test_summary_re_matches_bare_commands(self, validate_module: Any) -> None:
        """SUMMARY_RE matches a line with bare 'commands' (no qualifier)."""
        line = "Component counts: 16 agents, 20 skills, 25 commands, 25 hooks, 232 libraries"
        m = validate_module.SUMMARY_RE.search(line)
        assert m is not None, "SUMMARY_RE should match bare 'commands'"
        assert m.group("commands") == "25"

    def test_summary_re_matches_user_facing_commands(self, validate_module: Any) -> None:
        """SUMMARY_RE matches a line with 'user-facing commands' qualifier."""
        line = "Component counts: 16 agents, 20 skills, 22 user-facing commands, 25 hooks, 232 libraries"
        m = validate_module.SUMMARY_RE.search(line)
        assert m is not None, "SUMMARY_RE should match 'user-facing commands'"
        assert m.group("commands") == "22"

    def test_summary_re_rejects_malformed_line(self, validate_module: Any) -> None:
        """SUMMARY_RE returns None for a line with non-numeric command count."""
        line = "Component counts: 16 agents, 20 skills, NO commands, 25 hooks, 232 libraries"
        m = validate_module.SUMMARY_RE.search(line)
        assert m is None, "SUMMARY_RE should not match a non-numeric command count"

    def test_component_counts_validation_passes_against_current_claude_md(
        self, validate_module: Any
    ) -> None:
        """check_component_count_drift() returns no 'summary line missing or malformed' error
        against the actual repo CLAUDE.md (end-to-end path the pre-commit hook exercises)."""
        errors = validate_module.check_component_count_drift()
        malformed_errors = [
            e for e in errors if "missing or malformed" in e or "summary line missing" in e
        ]
        assert malformed_errors == [], (
            "Canonical 'Component counts:' line in CLAUDE.md is missing or malformed.\n"
            f"Errors: {malformed_errors}"
        )


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


class TestUserFacingCommandCount:
    """Tests for _count_user_facing_commands() and its dispatch in check_component_count_drift().

    Added in Issue #1159 follow-up: CLAUDE.md uses 'X user-facing commands' qualifier so the
    counter must only count files with user_facing: true in their YAML front-matter.
    """

    def test_count_user_facing_commands_matches_front_matter(
        self, validate_module: Any
    ) -> None:
        """_count_user_facing_commands() equals grep count of files with user_facing: true."""
        # Ground-truth via subprocess grep (anchored to start of line per YAML convention)
        commands_dir = (
            Path(__file__).resolve().parents[3]
            / "plugins"
            / "autonomous-dev"
            / "commands"
        )
        result = subprocess.run(
            ["grep", "-rl", "^user_facing: true", str(commands_dir)],
            capture_output=True,
            text=True,
            check=False,
        )
        grep_count = len([l for l in result.stdout.splitlines() if l.strip()])

        module_count = validate_module._count_user_facing_commands()

        assert module_count == grep_count, (
            f"_count_user_facing_commands() returned {module_count} but "
            f"grep found {grep_count} files with 'user_facing: true'"
        )

    def test_count_commands_total_at_least_user_facing(
        self, validate_module: Any
    ) -> None:
        """_count_commands() >= _count_user_facing_commands(): total >= user-facing subset."""
        total = validate_module._count_commands()
        user_facing = validate_module._count_user_facing_commands()
        assert total >= user_facing, (
            f"_count_commands() ({total}) must be >= _count_user_facing_commands() ({user_facing})"
        )

    def test_check_component_count_drift_passes_against_current_claude_md_with_user_facing_qualifier(
        self, validate_module: Any
    ) -> None:
        """End-to-end: check_component_count_drift() reports no commands drift against
        the actual CLAUDE.md which uses the 'user-facing commands' qualifier."""
        errors = validate_module.check_component_count_drift()
        commands_drift_errors = [e for e in errors if "'commands'" in e]
        assert commands_drift_errors == [], (
            "check_component_count_drift() reports commands drift against actual CLAUDE.md.\n"
            "CLAUDE.md uses 'user-facing commands' qualifier so _count_user_facing_commands() "
            "should be dispatched.\n"
            f"Commands drift errors: {commands_drift_errors}"
        )
