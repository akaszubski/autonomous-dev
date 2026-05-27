"""
Unit tests for the validate_claude_md_size.py hook.

Validates that:
1. CLAUDE.md under 200 lines produces no warning
2. CLAUDE.md at exactly 200 lines produces no warning
3. CLAUDE.md at 201 lines produces a warning (non-blocking, exit 0)
4. CLAUDE.md at 300 lines produces a warning (non-blocking, exit 0)
5. Missing CLAUDE.md is a silent pass
6. Warning includes current line count
7. Warning includes 200-line target
8. Real CLAUDE.md is <= 200 lines (regression guard)
"""

import sys
from pathlib import Path

import pytest

# Add hook directory to path for import
HOOK_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(HOOK_DIR))

import validate_claude_md_size as hook


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_claude_md(tmp_path: Path, line_count: int) -> Path:
    """Create a CLAUDE.md file with exactly line_count lines."""
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("\n".join(f"line {i}" for i in range(line_count)))
    return claude_md


# ---------------------------------------------------------------------------
# check_claude_md_size() unit tests
# ---------------------------------------------------------------------------

class TestCheckClaudeMdSize:
    """Unit tests for check_claude_md_size()."""

    def test_under_200_lines_no_warning(self, tmp_path: Path) -> None:
        """CLAUDE.md with 100 lines should produce no warning."""
        _make_claude_md(tmp_path, 100)
        count, warning = hook.check_claude_md_size(tmp_path)
        assert count == 100
        assert warning == ""

    def test_exactly_200_lines_no_warning(self, tmp_path: Path) -> None:
        """CLAUDE.md at exactly 200 lines should produce no warning."""
        _make_claude_md(tmp_path, 200)
        count, warning = hook.check_claude_md_size(tmp_path)
        assert count == 200
        assert warning == ""

    def test_201_lines_produces_warning(self, tmp_path: Path) -> None:
        """CLAUDE.md at 201 lines should produce a warning."""
        _make_claude_md(tmp_path, 201)
        count, warning = hook.check_claude_md_size(tmp_path)
        assert count == 201
        assert warning != ""

    def test_300_lines_produces_warning(self, tmp_path: Path) -> None:
        """CLAUDE.md at 300 lines should produce a warning."""
        _make_claude_md(tmp_path, 300)
        count, warning = hook.check_claude_md_size(tmp_path)
        assert count == 300
        assert warning != ""

    def test_missing_file_silent_pass(self, tmp_path: Path) -> None:
        """Missing CLAUDE.md should result in silent pass (count=0, no warning)."""
        # No CLAUDE.md created in tmp_path
        count, warning = hook.check_claude_md_size(tmp_path)
        assert count == 0
        assert warning == ""

    def test_warning_includes_line_count(self, tmp_path: Path) -> None:
        """Warning message should include the current line count."""
        _make_claude_md(tmp_path, 250)
        _, warning = hook.check_claude_md_size(tmp_path)
        assert "250" in warning

    def test_warning_includes_200_target(self, tmp_path: Path) -> None:
        """Warning message should mention the 200-line limit."""
        _make_claude_md(tmp_path, 201)
        _, warning = hook.check_claude_md_size(tmp_path)
        assert "200" in warning


# ---------------------------------------------------------------------------
# main() exit code tests
# ---------------------------------------------------------------------------

class TestMain:
    """Tests that main() always exits 0 (non-blocking)."""

    def test_exit_0_when_over_limit(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """main() should exit 0 even when CLAUDE.md is over the limit."""
        _make_claude_md(tmp_path, 250)
        monkeypatch.chdir(tmp_path)
        # Mock get_repo_root to return tmp_path
        monkeypatch.setattr(hook, "get_repo_root", lambda: tmp_path)
        exit_code = hook.main()
        assert exit_code == 0

    def test_exit_0_when_under_limit(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """main() should exit 0 when CLAUDE.md is under the limit."""
        _make_claude_md(tmp_path, 50)
        monkeypatch.setattr(hook, "get_repo_root", lambda: tmp_path)
        exit_code = hook.main()
        assert exit_code == 0

    def test_exit_0_when_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """main() should exit 0 when CLAUDE.md is missing."""
        monkeypatch.setattr(hook, "get_repo_root", lambda: tmp_path)
        exit_code = hook.main()
        assert exit_code == 0

    def test_warning_printed_to_stderr(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Warning should be printed to stderr, not stdout."""
        _make_claude_md(tmp_path, 250)
        monkeypatch.setattr(hook, "get_repo_root", lambda: tmp_path)
        hook.main()
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert captured.out == ""

    def test_no_output_when_under_limit(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """No output should be produced when CLAUDE.md is under the limit."""
        _make_claude_md(tmp_path, 50)
        monkeypatch.setattr(hook, "get_repo_root", lambda: tmp_path)
        hook.main()
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""


# ---------------------------------------------------------------------------
# Real CLAUDE.md regression guard
# ---------------------------------------------------------------------------

class TestRealClaudeMdRegression:
    """Regression guard: ensure this repo's CLAUDE.md stays under 200 lines."""

    def test_repo_claude_md_under_200_lines(self) -> None:
        """The actual CLAUDE.md in the repo root must be <= 200 lines."""
        repo_root = Path(__file__).resolve().parents[3]
        claude_md = repo_root / "CLAUDE.md"

        assert claude_md.exists(), (
            f"CLAUDE.md not found at {claude_md}. "
            "This test expects the repo to have a CLAUDE.md at root."
        )

        line_count = len(claude_md.read_text(encoding="utf-8").splitlines())
        assert line_count <= 200, (
            f"CLAUDE.md is {line_count} lines — over the 200-line Anthropic best practice limit.\n"
            f"Action required: trim CLAUDE.md to <= 200 lines.\n"
            f"File: {claude_md}"
        )


# ---------------------------------------------------------------------------
# derive_memory_path() unit tests
# ---------------------------------------------------------------------------

class TestDeriveMemoryPath:
    """Unit tests for derive_memory_path()."""

    def test_slug_derived_from_cwd(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Slug must be the absolute cwd with '/' replaced by '-'."""
        monkeypatch.setattr(hook.Path, "cwd", staticmethod(lambda: Path("/Users/foo/Dev/bar")))
        expected = Path.home() / ".claude" / "projects" / "-Users-foo-Dev-bar" / "memory" / "MEMORY.md"
        assert hook.derive_memory_path() == expected

    def test_slug_includes_leading_dash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The slug segment in the derived path must start with '-' (from leading '/')."""
        monkeypatch.setattr(hook.Path, "cwd", staticmethod(lambda: Path("/Users/foo/Dev/bar")))
        result = hook.derive_memory_path()
        # The slug is the parent-of-memory directory name.
        slug = result.parent.parent.name
        assert slug.startswith("-"), f"slug {slug!r} should start with '-'"

    def test_returns_path_under_home(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The derived path must live under ~/.claude/."""
        monkeypatch.setattr(hook.Path, "cwd", staticmethod(lambda: Path("/Users/foo/Dev/bar")))
        result = hook.derive_memory_path()
        claude_dir = Path.home() / ".claude"
        # Path.is_relative_to is available on Python 3.9+
        assert str(result).startswith(str(claude_dir)), (
            f"{result} should live under {claude_dir}"
        )


# ---------------------------------------------------------------------------
# check_project_md_size() unit tests
# ---------------------------------------------------------------------------

def _make_project_md(tmp_path: Path, line_count: int) -> Path:
    """Create tmp_path/.claude/PROJECT.md with exactly line_count lines."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    project_md = claude_dir / "PROJECT.md"
    project_md.write_text("\n".join(f"line {i}" for i in range(line_count)))
    return project_md


class TestCheckProjectMdSize:
    """Unit tests for check_project_md_size()."""

    def test_under_150_lines_no_warning(self, tmp_path: Path) -> None:
        """PROJECT.md with 100 lines should produce no warning."""
        _make_project_md(tmp_path, 100)
        count, warning = hook.check_project_md_size(tmp_path)
        assert count == 100
        assert warning == ""

    def test_exactly_150_lines_no_warning(self, tmp_path: Path) -> None:
        """PROJECT.md at exactly 150 lines should produce no warning."""
        _make_project_md(tmp_path, 150)
        count, warning = hook.check_project_md_size(tmp_path)
        assert count == 150
        assert warning == ""

    def test_151_lines_produces_warning(self, tmp_path: Path) -> None:
        """PROJECT.md at 151 lines should produce a warning."""
        _make_project_md(tmp_path, 151)
        count, warning = hook.check_project_md_size(tmp_path)
        assert count == 151
        assert warning != ""

    def test_missing_file_silent_pass(self, tmp_path: Path) -> None:
        """Missing PROJECT.md (no .claude/ dir) should be a silent pass."""
        # No .claude/ dir created
        count, warning = hook.check_project_md_size(tmp_path)
        assert count == 0
        assert warning == ""

    def test_warning_includes_150_target_and_count(self, tmp_path: Path) -> None:
        """Warning must mention both the 150 target and the actual line count."""
        _make_project_md(tmp_path, 175)
        _, warning = hook.check_project_md_size(tmp_path)
        assert "150" in warning
        assert "175" in warning


# ---------------------------------------------------------------------------
# check_memory_md_size() unit tests
# ---------------------------------------------------------------------------

class TestCheckMemoryMdSize:
    """Unit tests for check_memory_md_size()."""

    def test_under_200_lines_no_warning(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MEMORY.md with 100 lines should produce no warning."""
        memory_path = tmp_path / "MEMORY.md"
        memory_path.write_text("\n".join(f"line {i}" for i in range(100)))
        monkeypatch.setattr(hook, "derive_memory_path", lambda: memory_path)
        count, warning = hook.check_memory_md_size()
        assert count == 100
        assert warning == ""

    def test_exactly_200_lines_no_warning(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MEMORY.md at exactly 200 lines should produce no warning."""
        memory_path = tmp_path / "MEMORY.md"
        memory_path.write_text("\n".join(f"line {i}" for i in range(200)))
        monkeypatch.setattr(hook, "derive_memory_path", lambda: memory_path)
        count, warning = hook.check_memory_md_size()
        assert count == 200
        assert warning == ""

    def test_201_lines_produces_warning(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MEMORY.md at 201 lines should produce a warning."""
        memory_path = tmp_path / "MEMORY.md"
        memory_path.write_text("\n".join(f"line {i}" for i in range(201)))
        monkeypatch.setattr(hook, "derive_memory_path", lambda: memory_path)
        count, warning = hook.check_memory_md_size()
        assert count == 201
        assert warning != ""

    def test_missing_file_silent_pass(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing MEMORY.md at the redirected path is a silent pass."""
        memory_path = tmp_path / "MEMORY.md"  # not created
        monkeypatch.setattr(hook, "derive_memory_path", lambda: memory_path)
        count, warning = hook.check_memory_md_size()
        assert count == 0
        assert warning == ""


# ---------------------------------------------------------------------------
# main() combined-warning tests
# ---------------------------------------------------------------------------

class TestMainCombinedWarnings:
    """Tests that main() runs all three checks and accumulates warnings."""

    def test_all_three_over_limit_prints_three_warnings(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """When all three files exceed limits, all three warnings must be printed."""
        _make_claude_md(tmp_path, 250)
        _make_project_md(tmp_path, 175)
        memory_path = tmp_path / "MEMORY.md"
        memory_path.write_text("\n".join(f"line {i}" for i in range(250)))

        monkeypatch.setattr(hook, "get_repo_root", lambda: tmp_path)
        monkeypatch.setattr(hook, "derive_memory_path", lambda: memory_path)

        exit_code = hook.main()
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "CLAUDE.md" in captured.err
        assert "PROJECT.md" in captured.err
        assert "MEMORY.md" in captured.err

    def test_only_project_over_limit_prints_one_warning(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Only PROJECT.md over limit → only PROJECT.md warning."""
        _make_claude_md(tmp_path, 50)
        _make_project_md(tmp_path, 175)
        # No MEMORY.md
        memory_path = tmp_path / "MEMORY.md"  # not created

        monkeypatch.setattr(hook, "get_repo_root", lambda: tmp_path)
        monkeypatch.setattr(hook, "derive_memory_path", lambda: memory_path)

        hook.main()
        captured = capsys.readouterr()

        assert "PROJECT.md" in captured.err
        # CLAUDE.md is under limit, so its warning string must not appear.
        assert "CLAUDE.md is" not in captured.err

    def test_memory_check_failure_does_not_suppress_others(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """If MEMORY.md check raises OSError, CLAUDE.md warning still prints."""
        _make_claude_md(tmp_path, 250)

        def boom() -> tuple:
            raise OSError("simulated failure")

        monkeypatch.setattr(hook, "get_repo_root", lambda: tmp_path)
        monkeypatch.setattr(hook, "check_memory_md_size", boom)

        exit_code = hook.main()
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "CLAUDE.md" in captured.err

    def test_exit_0_even_when_all_three_over(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """main() must return 0 even when every file is over its limit."""
        _make_claude_md(tmp_path, 250)
        _make_project_md(tmp_path, 175)
        memory_path = tmp_path / "MEMORY.md"
        memory_path.write_text("\n".join(f"line {i}" for i in range(250)))

        monkeypatch.setattr(hook, "get_repo_root", lambda: tmp_path)
        monkeypatch.setattr(hook, "derive_memory_path", lambda: memory_path)

        assert hook.main() == 0
