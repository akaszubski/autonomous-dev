#!/usr/bin/env python3
"""
Unit tests for _run_extensions() in unified_pre_tool.py.

Tests extension discovery, loading, execution, error handling,
and the HOOK_EXTENSIONS_ENABLED kill-switch.

Date: 2026-03-18
Agent: implementer
"""

import os
import sys
import textwrap

import pytest
from pathlib import Path
from unittest.mock import patch

# Add hooks directory to path
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "hooks"
    ),
)

import unified_pre_tool as upt


class TestRunExtensions:
    """Tests for _run_extensions() hook extension mechanism."""

    def test_no_extensions_dir(self, tmp_path: Path) -> None:
        """Returns allow when extension directories don't exist."""
        fake_hook = tmp_path / "hooks" / "unified_pre_tool.py"
        fake_hook.parent.mkdir(parents=True)
        fake_hook.touch()

        with patch.object(upt, "__file__", str(fake_hook)), \
             patch("os.getcwd", return_value=str(tmp_path / "nonexistent_project")):
            decision, reason = upt._run_extensions("Bash", {"command": "ls"})

        assert decision == "allow"
        assert reason == ""

    def test_empty_extensions_dir(self, tmp_path: Path) -> None:
        """Returns allow when extension directory exists but is empty."""
        fake_hook = tmp_path / "hooks" / "unified_pre_tool.py"
        fake_hook.parent.mkdir(parents=True)
        fake_hook.touch()
        (fake_hook.parent / "extensions").mkdir()

        with patch.object(upt, "__file__", str(fake_hook)), \
             patch("os.getcwd", return_value=str(tmp_path / "nonexistent_project")):
            decision, reason = upt._run_extensions("Read", {"file_path": "/tmp/x"})

        assert decision == "allow"
        assert reason == ""

    def test_extension_allows(self, tmp_path: Path) -> None:
        """Extension returning allow passes through."""
        fake_hook = tmp_path / "hooks" / "unified_pre_tool.py"
        fake_hook.parent.mkdir(parents=True)
        fake_hook.touch()
        ext_dir = fake_hook.parent / "extensions"
        ext_dir.mkdir()

        ext_file = ext_dir / "allow_all.py"
        ext_file.write_text(textwrap.dedent("""\
            def check(tool_name, tool_input):
                return ("allow", "")
        """))

        with patch.object(upt, "__file__", str(fake_hook)), \
             patch("os.getcwd", return_value=str(tmp_path / "nonexistent_project")):
            decision, reason = upt._run_extensions("Bash", {"command": "ls"})

        assert decision == "allow"
        assert reason == ""

    def test_extension_denies(self, tmp_path: Path) -> None:
        """Extension returning deny blocks with reason."""
        fake_hook = tmp_path / "hooks" / "unified_pre_tool.py"
        fake_hook.parent.mkdir(parents=True)
        fake_hook.touch()
        ext_dir = fake_hook.parent / "extensions"
        ext_dir.mkdir()

        ext_file = ext_dir / "block_danger.py"
        ext_file.write_text(textwrap.dedent("""\
            def check(tool_name, tool_input):
                return ("deny", "Dangerous operation blocked")
        """))

        with patch.object(upt, "__file__", str(fake_hook)), \
             patch("os.getcwd", return_value=str(tmp_path / "nonexistent_project")):
            decision, reason = upt._run_extensions("Bash", {"command": "rm -rf /"})

        assert decision == "deny"
        assert "Dangerous operation blocked" in reason
        assert "block_danger.py" in reason

    def test_multiple_extensions_all_allow(self, tmp_path: Path) -> None:
        """Multiple extensions all returning allow passes through."""
        fake_hook = tmp_path / "hooks" / "unified_pre_tool.py"
        fake_hook.parent.mkdir(parents=True)
        fake_hook.touch()
        ext_dir = fake_hook.parent / "extensions"
        ext_dir.mkdir()

        for name in ["aaa_first.py", "bbb_second.py", "ccc_third.py"]:
            (ext_dir / name).write_text(textwrap.dedent("""\
                def check(tool_name, tool_input):
                    return ("allow", "")
            """))

        with patch.object(upt, "__file__", str(fake_hook)), \
             patch("os.getcwd", return_value=str(tmp_path / "nonexistent_project")):
            decision, reason = upt._run_extensions("Read", {})

        assert decision == "allow"

    def test_multiple_extensions_one_deny(self, tmp_path: Path) -> None:
        """First deny short-circuits - remaining extensions are not called."""
        fake_hook = tmp_path / "hooks" / "unified_pre_tool.py"
        fake_hook.parent.mkdir(parents=True)
        fake_hook.touch()
        ext_dir = fake_hook.parent / "extensions"
        ext_dir.mkdir()

        (ext_dir / "aaa_allow.py").write_text(textwrap.dedent("""\
            def check(tool_name, tool_input):
                return ("allow", "")
        """))

        (ext_dir / "bbb_deny.py").write_text(textwrap.dedent("""\
            def check(tool_name, tool_input):
                return ("deny", "blocked by bbb")
        """))

        # ccc should never run - write a file to prove it
        marker = tmp_path / "ccc_ran.marker"
        (ext_dir / "ccc_should_not_run.py").write_text(
            f'from pathlib import Path\n'
            f'def check(tool_name, tool_input):\n'
            f'    Path("{marker}").touch()\n'
            f'    return ("allow", "")\n'
        )

        with patch.object(upt, "__file__", str(fake_hook)), \
             patch("os.getcwd", return_value=str(tmp_path / "nonexistent_project")):
            decision, reason = upt._run_extensions("Bash", {"command": "test"})

        assert decision == "deny"
        assert "blocked by bbb" in reason
        assert not marker.exists(), "ccc extension should not have run (short-circuit)"

    def test_extension_crash_resilience(self, tmp_path: Path) -> None:
        """Exception in extension doesn't crash the hook."""
        fake_hook = tmp_path / "hooks" / "unified_pre_tool.py"
        fake_hook.parent.mkdir(parents=True)
        fake_hook.touch()
        ext_dir = fake_hook.parent / "extensions"
        ext_dir.mkdir()

        (ext_dir / "crasher.py").write_text(textwrap.dedent("""\
            def check(tool_name, tool_input):
                raise RuntimeError("I crashed!")
        """))

        with patch.object(upt, "__file__", str(fake_hook)), \
             patch("os.getcwd", return_value=str(tmp_path / "nonexistent_project")):
            decision, reason = upt._run_extensions("Bash", {"command": "ls"})

        assert decision == "allow"
        assert reason == ""

    def test_extension_missing_check(self, tmp_path: Path) -> None:
        """Extension without check() function is skipped silently."""
        fake_hook = tmp_path / "hooks" / "unified_pre_tool.py"
        fake_hook.parent.mkdir(parents=True)
        fake_hook.touch()
        ext_dir = fake_hook.parent / "extensions"
        ext_dir.mkdir()

        (ext_dir / "no_check.py").write_text(textwrap.dedent("""\
            def some_other_function():
                return True
        """))

        with patch.object(upt, "__file__", str(fake_hook)), \
             patch("os.getcwd", return_value=str(tmp_path / "nonexistent_project")):
            decision, reason = upt._run_extensions("Bash", {"command": "ls"})

        assert decision == "allow"
        assert reason == ""

    def test_extension_bad_return(self, tmp_path: Path) -> None:
        """Extension returning wrong type is handled gracefully."""
        fake_hook = tmp_path / "hooks" / "unified_pre_tool.py"
        fake_hook.parent.mkdir(parents=True)
        fake_hook.touch()
        ext_dir = fake_hook.parent / "extensions"
        ext_dir.mkdir()

        # Returns a string instead of tuple
        (ext_dir / "bad_return.py").write_text(textwrap.dedent("""\
            def check(tool_name, tool_input):
                return "allow"
        """))

        with patch.object(upt, "__file__", str(fake_hook)), \
             patch("os.getcwd", return_value=str(tmp_path / "nonexistent_project")):
            decision, reason = upt._run_extensions("Bash", {"command": "ls"})

        assert decision == "allow"
        assert reason == ""

    def test_extensions_disabled_env_var(self, tmp_path: Path) -> None:
        """HOOK_EXTENSIONS_ENABLED=false skips all extensions."""
        fake_hook = tmp_path / "hooks" / "unified_pre_tool.py"
        fake_hook.parent.mkdir(parents=True)
        fake_hook.touch()
        ext_dir = fake_hook.parent / "extensions"
        ext_dir.mkdir()

        # Write a deny extension that should NOT run
        (ext_dir / "always_deny.py").write_text(textwrap.dedent("""\
            def check(tool_name, tool_input):
                return ("deny", "should not fire")
        """))

        with patch.object(upt, "__file__", str(fake_hook)), \
             patch("os.getcwd", return_value=str(tmp_path / "nonexistent_project")), \
             patch.dict(os.environ, {"HOOK_EXTENSIONS_ENABLED": "false"}):
            decision, reason = upt._run_extensions("Bash", {"command": "rm -rf /"})

        assert decision == "allow"
        assert reason == ""

    def test_symlink_skipped(self, tmp_path: Path) -> None:
        """Symlinked extension file is skipped."""
        fake_hook = tmp_path / "hooks" / "unified_pre_tool.py"
        fake_hook.parent.mkdir(parents=True)
        fake_hook.touch()
        ext_dir = fake_hook.parent / "extensions"
        ext_dir.mkdir()

        # Create a real file outside extensions dir
        real_file = tmp_path / "real_ext.py"
        real_file.write_text(textwrap.dedent("""\
            def check(tool_name, tool_input):
                return ("deny", "symlink attack")
        """))

        # Symlink into extensions dir
        symlink = ext_dir / "symlinked_ext.py"
        symlink.symlink_to(real_file)

        with patch.object(upt, "__file__", str(fake_hook)), \
             patch("os.getcwd", return_value=str(tmp_path / "nonexistent_project")):
            decision, reason = upt._run_extensions("Bash", {"command": "ls"})

        assert decision == "allow"
        assert reason == ""

    def test_sorted_execution_order(self, tmp_path: Path) -> None:
        """Extensions run in alphabetical order."""
        fake_hook = tmp_path / "hooks" / "unified_pre_tool.py"
        fake_hook.parent.mkdir(parents=True)
        fake_hook.touch()
        ext_dir = fake_hook.parent / "extensions"
        ext_dir.mkdir()

        order_file = tmp_path / "order.txt"

        for name in ["zzz_last.py", "aaa_first.py", "mmm_middle.py"]:
            (ext_dir / name).write_text(
                f'from pathlib import Path\n'
                f'def check(tool_name, tool_input):\n'
                f'    with open("{order_file}", "a") as f:\n'
                f'        f.write("{name}\\n")\n'
                f'    return ("allow", "")\n'
            )

        with patch.object(upt, "__file__", str(fake_hook)), \
             patch("os.getcwd", return_value=str(tmp_path / "nonexistent_project")):
            upt._run_extensions("Bash", {"command": "ls"})

        lines = order_file.read_text().strip().split("\n")
        assert lines == ["aaa_first.py", "mmm_middle.py", "zzz_last.py"]

    def test_deduplication_by_filename(self, tmp_path: Path) -> None:
        """Same filename in global and project dirs - global wins (first occurrence)."""
        fake_hook = tmp_path / "hooks" / "unified_pre_tool.py"
        fake_hook.parent.mkdir(parents=True)
        fake_hook.touch()

        # Global extensions dir (alongside hook)
        global_ext_dir = fake_hook.parent / "extensions"
        global_ext_dir.mkdir()

        # Project extensions dir
        project_dir = tmp_path / "project" / ".claude" / "hooks" / "extensions"
        project_dir.mkdir(parents=True)

        marker = tmp_path / "which_ran.txt"

        # Same filename in both - global should win
        global_ext_dir.joinpath("shared.py").write_text(
            f'from pathlib import Path\n'
            f'def check(tool_name, tool_input):\n'
            f'    Path("{marker}").write_text("global")\n'
            f'    return ("allow", "")\n'
        )

        project_dir.joinpath("shared.py").write_text(
            f'from pathlib import Path\n'
            f'def check(tool_name, tool_input):\n'
            f'    Path("{marker}").write_text("project")\n'
            f'    return ("allow", "")\n'
        )

        with patch.object(upt, "__file__", str(fake_hook)), \
             patch("os.getcwd", return_value=str(tmp_path / "project")):
            upt._run_extensions("Bash", {"command": "ls"})

        assert marker.read_text() == "global"

    def test_project_level_extensions(self, tmp_path: Path) -> None:
        """Project-level extensions are discovered and run."""
        fake_hook = tmp_path / "hooks" / "unified_pre_tool.py"
        fake_hook.parent.mkdir(parents=True)
        fake_hook.touch()
        # No global extensions dir

        project_dir = tmp_path / "project" / ".claude" / "hooks" / "extensions"
        project_dir.mkdir(parents=True)

        project_dir.joinpath("project_rule.py").write_text(textwrap.dedent("""\
            def check(tool_name, tool_input):
                return ("deny", "project rule says no")
        """))

        with patch.object(upt, "__file__", str(fake_hook)), \
             patch("os.getcwd", return_value=str(tmp_path / "project")):
            decision, reason = upt._run_extensions("Bash", {"command": "ls"})

        assert decision == "deny"
        assert "project rule says no" in reason

    def test_extension_bad_return_three_elements(self, tmp_path: Path) -> None:
        """Extension returning tuple with wrong length is skipped."""
        fake_hook = tmp_path / "hooks" / "unified_pre_tool.py"
        fake_hook.parent.mkdir(parents=True)
        fake_hook.touch()
        ext_dir = fake_hook.parent / "extensions"
        ext_dir.mkdir()

        (ext_dir / "three_tuple.py").write_text(textwrap.dedent("""\
            def check(tool_name, tool_input):
                return ("deny", "reason", "extra")
        """))

        with patch.object(upt, "__file__", str(fake_hook)), \
             patch("os.getcwd", return_value=str(tmp_path / "nonexistent_project")):
            decision, reason = upt._run_extensions("Bash", {"command": "ls"})

        assert decision == "allow"
        assert reason == ""


def _census_reconciles(claim, executed, disk):
    """SINGLE acceptance predicate: the frozen census claim must equal BOTH
    independently observed surfaces (executed markers, files on disk).

    Used by BOTH arms of the completeness control below. It is EQUALITY, so an
    incomplete claim (a dropped inventory row) makes this identical predicate
    RAISE -- that raise is the omitted-entry counterexample.
    """
    assert set(claim) == set(executed) == set(disk)


class TestExtensionCensusCompleteness:
    """WA-O3 row 4: extension census-completeness (omitted-entry) control.

    ONE real _run_extensions run yields two observed surfaces -- EXECUTED
    (markers the hook wrote) and DISK (files on disk) -- reconciled against an
    INDEPENDENTLY authored census claim. Native activation stays UNMEASURED (no
    claim here); runtime-selection omission (symlink/dedup/order) is a DISTINCT
    concern owned by the existing symlink/dedup/order tests, not touched here.
    """

    # Two INDEPENDENT literals: the fixture files actually written, and the
    # census claim. Equal by intent, authored separately -- so DISK/EXECUTED
    # (from the run + filesystem) never mirror a mutation of the claim.
    FIXTURE_EXTENSIONS = ("aaa_ext.py", "bbb_ext.py", "ccc_ext.py")
    CLAIMED_SELECTED = ["aaa_ext.py", "bbb_ext.py", "ccc_ext.py"]

    def test_census_completeness_is_load_bearing(self, tmp_path: Path) -> None:
        """Dropping one claimed row makes the SAME equality predicate raise,
        with the single run's markers/decision/files unchanged (never re-run).
        """
        fake_hook = tmp_path / "hooks" / "unified_pre_tool.py"
        fake_hook.parent.mkdir(parents=True)
        fake_hook.touch()
        ext_dir = fake_hook.parent / "extensions"
        ext_dir.mkdir()
        markers_dir = tmp_path / "markers"
        markers_dir.mkdir()

        # Fixture population is authored from FIXTURE_EXTENSIONS, NOT the claim.
        for name in self.FIXTURE_EXTENSIONS:
            marker = markers_dir / (name + ".ran")
            (ext_dir / name).write_text(
                "from pathlib import Path\n"
                "def check(tool_name, tool_input):\n"
                f"    Path({str(marker)!r}).write_text('ran')\n"
                "    return ('allow', '')\n"
            )

        # ONE real run over the hook-adjacent extensions/ dir only. Bind the
        # enabled state explicitly so ambient HOOK_EXTENSIONS_ENABLED=false
        # cannot short-circuit discovery and starve the positive arm.
        with patch.dict(os.environ, {"HOOK_EXTENSIONS_ENABLED": "true"}), \
             patch.object(upt, "__file__", str(fake_hook)), \
             patch("os.getcwd", return_value=str(tmp_path / "nonexistent_project")):
            decision, reason = upt._run_extensions("Bash", {"command": "ls"})

        # EXECUTED from the real run's markers; DISK from the filesystem.
        executed = {p.name[:-4] for p in markers_dir.glob("*.ran")}
        disk = {p.name for p in ext_dir.glob("*.py")}

        # POSITIVE: full claim satisfies the acceptance predicate; run permits.
        _census_reconciles(self.CLAIMED_SELECTED, executed, disk)
        assert decision == "allow"
        assert reason == ""

        # NEGATIVE: SAME snapshot -- runtime is structurally unchanged because
        # we never re-run and never touch files/markers/env; drop exactly one
        # claimed row and require the IDENTICAL predicate that just passed to
        # RAISE. This is the omitted-entry counterexample (not a bespoke !=).
        reduced = [n for n in self.CLAIMED_SELECTED if n != "bbb_ext.py"]
        with pytest.raises(AssertionError):
            _census_reconciles(reduced, executed, disk)
