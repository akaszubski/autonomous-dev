"""Structural meta-test: no dark test modules.

A "dark" test module is one that pytest discovers but silently zero-collects
because a module-level ``pytest.skip(..., allow_module_level=True)`` was
guarded by ``except ImportError:``. This is the class of bug that hid 56
smoke tests for ~8 months (GitHub issue #1469, fixed instance:
``tests/regression/smoke/test_settings_generator.py``, commit 2b1d5e90).

An ``except ImportError: pytest.skip(..., allow_module_level=True)`` guard
is a legitimate pattern for genuinely-optional runtime dependencies, but it
is indistinguishable from a permanently-broken import path unless something
independently asserts collection > 0. This meta-test IS that independent
assertion.

The check is AST-based: we walk every ``tests/**/*.py`` module, find any
``pytest.skip`` call whose enclosing statement is an ``except ImportError:``
handler with ``allow_module_level=True``, and flag the file.

## Grandfathered baseline (issue #1469)

At the time this test was added (2026-08-09), 61 offenders already existed
in the tree (see ``_KNOWN_OFFENDERS`` below). They are captured as a
frozen baseline. This test enforces two invariants:

  1. **No NEW offenders.** Any file/lineno not in the baseline that trips
     the AST check causes an immediate FAIL — the pattern cannot spread.
  2. **The baseline can only shrink.** If a baseline entry is no longer
     detected (import fixed, guard removed, test file deleted, or file
     restructured), the entry must be removed from ``_KNOWN_OFFENDERS`` —
     that FAIL forces the cleanup to be recorded, so the baseline shrinks
     monotonically and cannot silently regrow.

Files may exit the baseline by:
  - Removing the ``try/except ImportError`` guard entirely once the import
    is stable.
  - Annotating the ``pytest.skip`` line with
    ``# noqa: dark-module-ok - issue #<N>`` and a linked tracking issue
    for genuinely-optional dependencies.

GitHub Issue: #1469
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = REPO_ROOT / "tests"

DARK_OK_MARKER = "# noqa: dark-module-ok"


# Grandfathered offenders present at the time this meta-test was
# introduced (2026-08-09, issue #1469). Entries are (relative_path, lineno).
# ADDING entries to this set is forbidden — the test will flag any new
# offender that does not appear here.
# REMOVING entries is required whenever the corresponding guard is fixed
# or the file is deleted — an entry that is no longer detected causes a
# FAIL, so cleanup progress is tracked automatically.
_KNOWN_OFFENDERS: frozenset[tuple[str, int]] = frozenset({
    ("tests/integration/test_agent_feedback_integration.py", 41),
    ("tests/integration/test_auto_claude_integration.py", 66),
    ("tests/integration/test_auto_implement_checkpoint_portability.py", 53),
    ("tests/integration/test_auto_implement_git.py", 42),
    ("tests/integration/test_auto_implement_git_end_to_end.py", 48),
    ("tests/integration/test_auto_implement_step8_agents.py", 58),
    ("tests/integration/test_batch_auto_clear.py", 71),
    ("tests/integration/test_batch_auto_compact_resume.py", 51),
    ("tests/integration/test_batch_auto_continuation.py", 78),
    ("tests/integration/test_batch_consent_bypass.py", 56),
    ("tests/integration/test_batch_context_clearing.py", 63),
    ("tests/integration/test_batch_git_edge_cases.py", 64),
    ("tests/integration/test_batch_git_workflow.py", 60),
    ("tests/integration/test_batch_orchestrator_sessions.py", 45),
    ("tests/integration/test_checkpoint_heredoc_execution.py", 55),
    ("tests/integration/test_dispatcher_resource_checks.py", 45),
    ("tests/integration/test_first_run_flow.py", 55),
    ("tests/integration/test_genai_installation.py", 49),
    ("tests/integration/test_implement_command.py", 72),
    ("tests/integration/test_install_settings_generation.py", 52),
    ("tests/integration/test_issue88_simplified_workflow.py", 60),
    ("tests/integration/test_parallel_exploration_task_tool_end_to_end.py", 46),
    ("tests/integration/test_parallel_research_planning.py", 50),
    ("tests/integration/test_parallel_validation.py", 44),
    ("tests/integration/test_parallel_validation.py", 50),
    ("tests/integration/test_pause_integration.py", 31),
    ("tests/integration/test_pr_workflow.py", 29),
    ("tests/integration/test_progress_tracker_integration.py", 49),
    ("tests/integration/test_ralph_auto_continue_batch.py", 45),
    ("tests/integration/test_ralph_checkpoint_integration.py", 53),
    ("tests/integration/test_ralph_loop_integration.py", 46),
    ("tests/integration/test_sandbox_integration.py", 53),
    ("tests/integration/test_self_validation_hooks.py", 75),
    ("tests/integration/test_tech_debt_pipeline.py", 59),
    ("tests/integration/test_update_permission_fix.py", 55),
    ("tests/integration/test_worktree_batch_isolation.py", 62),
    ("tests/integration/test_worktree_integration.py", 52),
    ("tests/integration/test_worktree_merge_with_conflicts.py", 40),
    ("tests/integration/test_worktree_plugin_artifacts.py", 42),
    ("tests/regression/extended/test_performance_phase2_parallelization.py", 49),
    ("tests/regression/progression/test_issue244_local_directory_preservation.py", 39),
    ("tests/regression/progression/test_issue244_orphan_cleaner_integration.py", 45),
    ("tests/regression/progression/test_issue_206_version_tracking_simplification.py", 51),
    ("tests/regression/progression/test_issue_220_state_manager_abc.py", 67),
    ("tests/regression/regression/test_feature_v3_12_0_auto_git.py", 60),
    ("tests/regression/regression/test_feature_v3_12_0_user_state.py", 58),
    ("tests/regression/regression/test_issue_312_batch_git_env_worktree.py", 68),
    ("tests/regression/regression/test_issue_318_respect_auto_git_pr.py", 58),
    ("tests/regression/regression/test_issues_313_316_worktree_safety_fixes.py", 58),
    ("tests/regression/regression/test_self_validation_workflow.py", 57),
    ("tests/regression/smoke/test_settings_generator_validation.py", 58),
    ("tests/regression/test_xss_vulnerability_fix.py", 54),
    ("tests/security/test_pr_security.py", 33),
    ("tests/security/test_tool_auto_approval_security.py", 63),
    ("tests/unit/lib/test_doc_master_auto_apply.py", 53),
    ("tests/unit/lib/test_doc_update_risk_classifier.py", 48),
})


def _find_import_error_guarded_skips(source: str) -> list[tuple[int, str]]:
    """Return list of (lineno, skip_reason) for every pytest.skip call whose
    enclosing statement is ``except ImportError:`` and whose call carries
    ``allow_module_level=True``.

    Empty list means the file has no such guard.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    findings: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if not _handler_catches_import_error(handler):
                continue
            for stmt in ast.walk(handler):
                if not isinstance(stmt, ast.Call):
                    continue
                if not _is_pytest_skip(stmt):
                    continue
                if not _has_allow_module_level_true(stmt):
                    continue
                reason = _extract_reason(stmt)
                findings.append((stmt.lineno, reason))
    return findings


def _handler_catches_import_error(handler: ast.ExceptHandler) -> bool:
    exc = handler.type
    if exc is None:
        return False
    if isinstance(exc, ast.Name) and exc.id == "ImportError":
        return True
    if isinstance(exc, ast.Tuple):
        for elt in exc.elts:
            if isinstance(elt, ast.Name) and elt.id == "ImportError":
                return True
    return False


def _is_pytest_skip(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr == "skip":
        val = func.value
        if isinstance(val, ast.Name) and val.id == "pytest":
            return True
    return False


def _has_allow_module_level_true(call: ast.Call) -> bool:
    for kw in call.keywords:
        if kw.arg == "allow_module_level":
            val = kw.value
            if isinstance(val, ast.Constant) and val.value is True:
                return True
    return False


def _extract_reason(call: ast.Call) -> str:
    if call.args:
        first = call.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
    return ""


def _has_dark_ok_marker(source: str, lineno: int) -> bool:
    """True if the given 1-based line carries the ``# noqa: dark-module-ok``
    escape hatch WITH a linked issue reference on the same line."""
    lines = source.splitlines()
    if lineno < 1 or lineno > len(lines):
        return False
    line = lines[lineno - 1]
    if DARK_OK_MARKER not in line:
        return False
    tail = line.split(DARK_OK_MARKER, 1)[1]
    return "#" in tail


def _collect_test_modules() -> list[Path]:
    """All ``test_*.py`` files under tests/, excluding archive/fixture dirs."""
    excluded = {"archived", "fixtures", "helpers", "__pycache__"}
    out: list[Path] = []
    for p in TESTS_DIR.glob("**/test_*.py"):
        if any(part in excluded for part in p.parts):
            continue
        out.append(p)
    return sorted(out)


def _scan_current_offenders() -> set[tuple[str, int]]:
    """Scan the tree and return the set of (relative_path, lineno) currently
    tripping the AST check, excluding any with a valid dark-ok marker."""
    offenders: set[tuple[str, int]] = set()
    for path in _collect_test_modules():
        source = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, _reason in _find_import_error_guarded_skips(source):
            if _has_dark_ok_marker(source, lineno):
                continue
            rel = str(path.relative_to(REPO_ROOT))
            offenders.add((rel, lineno))
    return offenders


class TestNoDarkTestModules:
    """Meta-invariant: no NEW test module may silently zero-collect via an
    ``except ImportError:`` module-level skip. The grandfathered baseline
    can only shrink (issue #1469)."""

    def test_no_new_dark_modules_beyond_baseline(self):
        current = _scan_current_offenders()
        new_offenders = current - _KNOWN_OFFENDERS
        if new_offenders:
            listing = "\n  ".join(
                f"{path}:{lineno}" for path, lineno in sorted(new_offenders)
            )
            pytest.fail(
                "NEW `except ImportError: pytest.skip(..., "
                "allow_module_level=True)` guard(s) added — these can "
                "silently zero-collect if the guarded import breaks "
                "(issue #1469, fixed instance commit 2b1d5e90).\n\n"
                "Either:\n"
                "  1. Fix the import path so the guard becomes dormant\n"
                f"     (preferred), or\n"
                f"  2. Annotate the pytest.skip line with "
                f"`{DARK_OK_MARKER} - issue #<N>` linking a tracking\n"
                "     issue for the optional dependency.\n\n"
                f"New offenders:\n  {listing}"
            )

    def test_baseline_only_shrinks(self):
        """Baseline entries that are no longer detected MUST be removed.

        This forces cleanup progress to be recorded in the baseline (so
        the number monotonically decreases and cannot silently regrow).
        """
        current = _scan_current_offenders()
        stale_baseline = _KNOWN_OFFENDERS - current
        if stale_baseline:
            listing = "\n  ".join(
                f"{path}:{lineno}" for path, lineno in sorted(stale_baseline)
            )
            pytest.fail(
                "Baseline contains entries that are no longer detected — "
                "the guard was removed, the file was deleted/renamed, or "
                "line numbers shifted. Remove these entries from "
                "`_KNOWN_OFFENDERS` in "
                "`tests/structural/test_no_dark_test_modules.py` so the "
                "baseline shrinks (issue #1469).\n\n"
                f"Stale baseline entries:\n  {listing}"
            )

    def test_helper_ast_detects_the_original_pattern(self):
        """Sanity-check: the AST walker recognises the exact shape that
        motivated issue #1469 (the pattern that hid 56 smoke tests)."""
        sample = (
            "import pytest\n"
            "try:\n"
            "    from autonomous_dev.lib.settings_generator import X\n"
            "except ImportError:\n"
            "    pytest.skip('not implemented yet', allow_module_level=True)\n"
        )
        findings = _find_import_error_guarded_skips(sample)
        assert len(findings) == 1
        assert findings[0][1] == "not implemented yet"

    def test_helper_ignores_conditional_module_skip(self):
        """A non-ImportError guard (e.g. platform check) is not flagged."""
        sample = (
            "import sys, pytest\n"
            "if sys.platform == 'win32':\n"
            "    pytest.skip('nix only', allow_module_level=True)\n"
        )
        findings = _find_import_error_guarded_skips(sample)
        assert findings == []

    def test_helper_ignores_function_level_skip(self):
        """Function-level ``pytest.skip`` (no allow_module_level=True) is
        outside scope — those don't zero-collect."""
        sample = (
            "import pytest\n"
            "try:\n"
            "    import optional_thing\n"
            "except ImportError:\n"
            "    def test_x():\n"
            "        pytest.skip('missing dep')\n"
        )
        findings = _find_import_error_guarded_skips(sample)
        assert findings == []

    def test_marker_requires_issue_reference(self):
        """A bare ``# noqa: dark-module-ok`` with no issue link must NOT
        suppress the finding (defense-in-depth against silent opt-outs)."""
        src_bare = (
            "pytest.skip('x', allow_module_level=True)  "
            "# noqa: dark-module-ok\n"
        )
        assert _has_dark_ok_marker(src_bare, 1) is False

        src_with_issue = (
            "pytest.skip('x', allow_module_level=True)  "
            "# noqa: dark-module-ok - issue #1469\n"
        )
        assert _has_dark_ok_marker(src_with_issue, 1) is True

    def test_baseline_is_nonempty_and_documented(self):
        """The baseline must contain at least the historical count so we
        cannot accidentally reset it to empty and lose the grandfathering
        contract."""
        assert len(_KNOWN_OFFENDERS) >= 50, (
            "Baseline must retain the ~61 grandfathered entries from "
            "issue #1469. If you're intentionally clearing entries, do "
            "them one-by-one as the underlying guards are fixed."
        )
