"""Structural tests for the /triage command (AC#4 + AC#5).

These tests assert files / flags / docs exist without running any clustering. They are
the canonical "command and flag exist" gate from issue #1099 acceptance criteria.

GitHub Issue: #1099
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
COMMAND_FILE = REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "triage.md"
ANALYZER_FILE = REPO_ROOT / "plugins" / "autonomous-dev" / "lib" / "issue_triage_analyzer.py"
COMMANDS_DOC = REPO_ROOT / "plugins" / "autonomous-dev" / "docs" / "COMMANDS.md"


class TestTriageCommandStructure:
    def test_triage_command_file_exists(self):
        assert COMMAND_FILE.is_file(), f"Missing command shell at {COMMAND_FILE}"

    def test_triage_frontmatter_declares_flag(self):
        text = COMMAND_FILE.read_text()
        # Front-matter present
        assert text.startswith("---"), "Missing YAML frontmatter"
        # Must declare the --auto-improvement flag in argument-hint.
        assert "--auto-improvement" in text, "Frontmatter must declare --auto-improvement"
        # Must be user-invocable.
        assert "user-invocable: true" in text

    def test_analyzer_module_importable(self):
        lib_dir = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
        if str(lib_dir) not in sys.path:
            sys.path.insert(0, str(lib_dir))
        # Force fresh import to ensure module exposes the public API.
        if "issue_triage_analyzer" in sys.modules:
            del sys.modules["issue_triage_analyzer"]
        mod = importlib.import_module("issue_triage_analyzer")
        # Public API surface.
        for name in (
            "TriageFinding",
            "triage_auto_improvement",
            "extract_root_cause_tag",
            "extract_title_tokens",
            "cluster_within_tag",
            "compute_rank_score",
            "extract_shared_files",
            "detect_cross_cluster_dependencies",
            "render_json",
            "main",
        ):
            assert hasattr(mod, name), f"Public symbol {name} missing"

    def test_commands_md_documents_triage(self):
        text = COMMANDS_DOC.read_text()
        # /triage referenced in COMMANDS.md.
        assert "/triage" in text, "/triage not documented in COMMANDS.md"
        assert "--auto-improvement" in text, "--auto-improvement flag not documented"
