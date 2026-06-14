"""Hook PWD inheritance tests — central #1206 closing test.

The core insight behind Issue #1206 is that hook subprocesses inherit the
coordinator session's CWD via ``subprocess.run(..., cwd=...)``. When the
sentinel path is resolved relative to that inherited CWD (rather than from a
machine-global ``/tmp/`` literal), cross-repo concurrent /implement sessions
stay isolated by construction.

These tests prove the inheritance contract by spawning a small Python harness
under each hook's process and asserting that the resolved sentinel path
anchors under the cwd we passed in.

Issue: #1206
"""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
HOOKS_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"


def _make_fake_repo(tmp_path: Path, name: str) -> Path:
    """Create a tmp directory acting as an isolated repo with a .git marker."""
    repo = tmp_path / name
    repo.mkdir()
    (repo / ".git").mkdir()
    return repo


class TestHookPwdInheritance:
    """Hook subprocesses must resolve the sentinel under the inherited CWD."""

    def test_python_resolver_inherits_cwd(self, tmp_path):
        """When a Python subprocess runs with cwd=repo_a, sentinel anchors there.

        This is the foundation: if Python's get_legacy_sentinel_path() does NOT
        track the cwd of the subprocess, ALL the downstream guarantees collapse.
        We spawn a minimal Python harness that imports the resolver and prints
        the path, then assert it falls under ``repo_a``.
        """
        repo_a = _make_fake_repo(tmp_path, "repo_a")

        harness = textwrap.dedent(
            f"""
            import sys
            sys.path.insert(0, {str(LIB_DIR)!r})
            import path_utils
            path_utils.reset_project_root_cache()
            from pipeline_state import get_legacy_sentinel_path
            print(get_legacy_sentinel_path())
            """
        )

        result = subprocess.run(
            [sys.executable, "-c", harness],
            cwd=str(repo_a),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"harness failed: {result.stderr}"

        printed = Path(result.stdout.strip())
        # The sentinel must anchor under repo_a, not under any other repo.
        assert repo_a.resolve() in printed.resolve().parents, (
            f"Subprocess sentinel {printed} did not anchor under cwd {repo_a}"
        )

    def test_unified_pre_tool_inherits_cwd(self, tmp_path):
        """unified_pre_tool.py's LEGACY_SENTINEL_LITERALS reflects subprocess cwd.

        Imports unified_pre_tool in a subprocess started with cwd=repo_a and
        verifies the tuple's per-repo entry anchors there.
        """
        repo_a = _make_fake_repo(tmp_path, "repo_a")

        harness = textwrap.dedent(
            f"""
            import sys
            sys.path.insert(0, {str(LIB_DIR)!r})
            sys.path.insert(0, {str(HOOKS_DIR)!r})
            import path_utils
            path_utils.reset_project_root_cache()
            import unified_pre_tool
            # The tuple has two entries: legacy /tmp literal + per-repo path.
            # Print just the per-repo path (the second element).
            print(unified_pre_tool.LEGACY_SENTINEL_LITERALS[1])
            """
        )

        result = subprocess.run(
            [sys.executable, "-c", harness],
            cwd=str(repo_a),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"harness failed: {result.stderr}"

        per_repo_literal = Path(result.stdout.strip())
        assert repo_a.resolve() in per_repo_literal.resolve().parents, (
            f"unified_pre_tool sentinel {per_repo_literal} did not "
            f"anchor under inherited cwd {repo_a}"
        )

    def test_session_tracker_inherits_cwd(self, tmp_path):
        """unified_session_tracker's resolver picks up subprocess cwd."""
        repo_a = _make_fake_repo(tmp_path, "repo_a")

        harness = textwrap.dedent(
            f"""
            import sys
            sys.path.insert(0, {str(LIB_DIR)!r})
            sys.path.insert(0, {str(HOOKS_DIR)!r})
            import path_utils
            path_utils.reset_project_root_cache()
            from unified_session_tracker import get_legacy_sentinel_path
            print(get_legacy_sentinel_path())
            """
        )

        result = subprocess.run(
            [sys.executable, "-c", harness],
            cwd=str(repo_a),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"harness failed: {result.stderr}"

        sentinel = Path(result.stdout.strip())
        assert repo_a.resolve() in sentinel.resolve().parents, (
            f"session_tracker sentinel {sentinel} did not anchor under {repo_a}"
        )

    def test_bash_session_start_inherits_cwd(self, tmp_path):
        """Bash _default_sentinel() echoes a path under the subprocess cwd."""
        repo_a = _make_fake_repo(tmp_path, "repo_a")
        sentinel_helper = HOOKS_DIR / "lib" / "_sentinel.sh"
        assert sentinel_helper.exists(), f"helper missing: {sentinel_helper}"

        result = subprocess.run(
            ["bash", "-c", f"source {sentinel_helper} && _default_sentinel"],
            cwd=str(repo_a),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"bash helper failed: {result.stderr}"

        path = Path(result.stdout.strip())
        assert repo_a.resolve() in path.resolve().parents, (
            f"bash sentinel {path} did not anchor under cwd {repo_a}"
        )

    def test_bash_and_python_resolve_to_same_path(self, tmp_path):
        """Bash _default_sentinel and Python get_legacy_sentinel_path agree.

        Bash parity gate: the two resolvers MUST produce the same path so a
        Python-coordinator session and a bash-hook subprocess (running in the
        same cwd) share the same sentinel.
        """
        repo_a = _make_fake_repo(tmp_path, "repo_a")
        sentinel_helper = HOOKS_DIR / "lib" / "_sentinel.sh"

        py_harness = textwrap.dedent(
            f"""
            import sys
            sys.path.insert(0, {str(LIB_DIR)!r})
            import path_utils
            path_utils.reset_project_root_cache()
            from pipeline_state import get_legacy_sentinel_path
            print(get_legacy_sentinel_path())
            """
        )
        py_result = subprocess.run(
            [sys.executable, "-c", py_harness],
            cwd=str(repo_a),
            capture_output=True,
            text=True,
            timeout=30,
        )
        bash_result = subprocess.run(
            ["bash", "-c", f"source {sentinel_helper} && _default_sentinel"],
            cwd=str(repo_a),
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert py_result.returncode == 0, py_result.stderr
        assert bash_result.returncode == 0, bash_result.stderr

        py_path = Path(py_result.stdout.strip()).resolve()
        bash_path = Path(bash_result.stdout.strip()).resolve()
        assert py_path == bash_path, (
            f"Bash/Python parity broken:\n  py={py_path}\n  bash={bash_path}"
        )
