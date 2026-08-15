#!/usr/bin/env python3
"""Regression tests for Issue #1484 — sentinel path convergence.

The writer (PreToolUse), reader (unified_pre_tool) and clearer (SubagentStop)
all run as separate hook subprocesses. They MUST converge on one normalized
sentinel path even when the process cwd is a subdirectory of the repo. The
default (no-arg) ``_path()`` branch resolves the repo root via the blessed
``path_utils.find_project_root`` (NOT ``git rev-parse --git-common-dir``, which
is banned by hook_path_validator.py).

Issue: #1484
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_LIB = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import agent_dispatch_sentinel as ads  # noqa: E402


class TestIssue1484PathConvergence:
    def test_path_normalizes_from_subdirectory(self, tmp_path: Path, monkeypatch) -> None:
        """No-arg _path() from a subdirectory resolves to <repo>/.claude/....

        find_project_root walks up for a ``.git`` marker, so a hook subprocess
        launched with cwd inside <repo>/sub/dir still targets the repo-root
        sentinel — the writer/reader/clearer converge.
        """
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        subdir = repo / "sub" / "dir"
        subdir.mkdir(parents=True)
        monkeypatch.chdir(subdir)

        resolved = ads._path()
        expected = (repo / ".claude" / "local" / "active_agent_dispatch.json").resolve()
        assert resolved.resolve() == expected

    def test_worktree_isolation_distinct_paths(self, tmp_path: Path, monkeypatch) -> None:
        """Two fake repo roots each with their own .git get distinct sentinels."""
        repo_a = tmp_path / "repo_a"
        repo_b = tmp_path / "repo_b"
        (repo_a / ".git").mkdir(parents=True)
        (repo_b / ".git").mkdir(parents=True)

        monkeypatch.chdir(repo_a)
        path_a = ads._path().resolve()
        monkeypatch.chdir(repo_b)
        path_b = ads._path().resolve()

        assert path_a != path_b
        assert path_a == (repo_a / ".claude" / "local" / "active_agent_dispatch.json").resolve()
        assert path_b == (repo_b / ".claude" / "local" / "active_agent_dispatch.json").resolve()

    def test_no_git_common_dir_shellout(self) -> None:
        """The module MUST NOT shell out to git for path resolution (banned).

        We assert the ABSENCE of an actual shellout mechanism (subprocess /
        os.system), not the mere textual mention of the banned pattern — the
        module's docstring intentionally documents that ``git rev-parse
        --git-common-dir`` is banned by hook_path_validator.py, so a naive
        substring check for "rev-parse" would false-positive on that
        documentation.
        """
        source = (_LIB / "agent_dispatch_sentinel.py").read_text()
        import ast

        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert "subprocess" not in imported, "sentinel must not import subprocess"
        # No os.system / os.popen style shellout either.
        assert "os.system" not in source
        assert "os.popen" not in source
        # The banned string may appear ONLY inside the documenting docstring/comment,
        # never as an executable call. Strip docstrings + comments and re-check.
        code_only_lines = []
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            code_only_lines.append(line)
        # Remove triple-quoted docstrings crudely by AST: collect docstring nodes.
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                ds = ast.get_docstring(node, clean=False)
                if ds:
                    docstrings.add(ds)
        code_blob = "\n".join(code_only_lines)
        for ds in docstrings:
            code_blob = code_blob.replace(ds, "")
        assert "rev-parse" not in code_blob, "rev-parse appears in executable code"
        assert "--git-common-dir" not in code_blob
