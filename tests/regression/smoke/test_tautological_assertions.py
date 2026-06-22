"""Smoke test: detect tautological `assert True` assertions in the test suite.

A test function whose ONLY assertion is `assert True` can never fail, making it
tautological. This smoke test scans the codebase for such patterns so they are
caught before merge rather than slipping through review.

Issue: #783
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Tuple

# Repo root: tests/regression/smoke/ -> parents[3]
REPO_ROOT = Path(__file__).resolve().parents[3]
TESTS_DIR = REPO_ROOT / "tests"

# Explicit allowlist of known tautological tests, tracked for future cleanup.
# Each entry is (relative_path_from_repo_root, function_or_method_name, issue_number).
ALLOWLIST: List[Tuple[str, str, str]] = [
    # --- tests/integration/ ---
    ("tests/integration/test_agent_tracker_cli_wrapper_issue79.py", "test_cli_shows_deprecation_warning_on_direct_use", "#783"),
    ("tests/integration/test_agent_tracker_cli_wrapper_issue79.py", "test_deprecation_warning_mentions_migration_path", "#783"),
    ("tests/integration/test_setup_wizard_genai_integration.py", "test_phase0_handles_read_only_project", "#783"),
    ("tests/integration/test_setup_wizard_genai_integration.py", "test_phase0_handles_disk_full", "#783"),
    ("tests/integration/test_setup_wizard_genai_integration.py", "test_phase0_partial_install_cleanup", "#783"),
    ("tests/integration/test_setup_wizard_genai_integration.py", "test_phase0_handles_symlinks", "#783"),
    ("tests/integration/test_uv_execution.py", "test_hook_handles_sigint", "#783"),
    # --- tests/regression/ ---
    ("tests/regression/progression/test_issue_216_escape_sequence_fix.py", "test_warning_detection_with_compile_simulation", "#783"),
    ("tests/regression/regression/test_issue_312_batch_git_env_worktree.py", "test_all_dotenv_loading_paths_covered", "#783"),
    ("tests/regression/regression/test_issue_312_batch_git_env_worktree.py", "test_all_security_scenarios_covered", "#783"),
    # --- tests/unit/ ---
    ("tests/unit/agents/test_issue_creator.py", "test_agent_has_required_frontmatter", "#783"),
    ("tests/unit/agents/test_issue_creator.py", "test_agent_instructions_clear", "#783"),
    ("tests/unit/agents/test_issue_creator.py", "test_agent_uses_relevant_skills", "#783"),
    ("tests/unit/hooks/test_enforce_tdd.py", "test_neither_found_gives_benefit", "#783"),
    ("tests/unit/lib/test_claude_md_updater.py", "test_summary", "#783"),
    ("tests/unit/scripts/test_genai_install_wrapper.py", "test_error_handling_permission_denied", "#783"),
    # NOTE: 7 entries for tests/unit/test_scripts_deprecation_issue79.py were
    # removed when the test file itself was deleted upstream.
]


def _is_assert_true_only(node: ast.Assert) -> bool:
    """Check if an assert statement is a bare `assert True` (no message, no compound)."""
    # Must be `assert True` — the test value must be the constant True
    if not isinstance(node.test, ast.Constant) or node.test.value is not True:
        return False
    # Allow `assert True, "reason message"` — these document intent even if tautological,
    # but still flag them as tautological since they can never fail.
    # Actually per the issue spec: `assert True,` with a message that documents WHY is allowed.
    if node.msg is not None:
        return False
    return True


def _get_all_asserts(body: list[ast.stmt]) -> list[ast.Assert]:
    """Recursively collect all assert statements from a function body."""
    asserts: list[ast.Assert] = []
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Assert):
            asserts.append(node)
    return asserts



def _scan_file_for_tautological_tests(
    filepath: Path,
) -> List[Tuple[str, str, int]]:
    """Scan a Python file for test functions whose only assertion is `assert True`.

    Returns list of (relative_path, function_name, line_number).
    """
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError, FileNotFoundError):
        return []

    findings: List[Tuple[str, str, int]] = []
    rel_path = str(filepath.relative_to(REPO_ROOT))

    for node in ast.walk(tree):
        # Match test functions (def test_*) and test methods inside classes
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("test_"):
                continue

            # Get all assert statements in the function body
            all_asserts = _get_all_asserts(node.body)

            if not all_asserts:
                # No asserts at all — not our concern here (could be import-as-test)
                continue

            # Check: are ALL asserts `assert True` (bare, no message)?
            all_are_assert_true = all(_is_assert_true_only(a) for a in all_asserts)

            if all_are_assert_true:
                # Also check there are no other meaningful verification calls
                # (e.g., pytest.raises, mock.assert_called, etc.)
                has_other_verification = _has_verification_call(node.body)
                if not has_other_verification:
                    findings.append((rel_path, node.name, node.lineno))

    return findings


def _has_verification_call(body: list[ast.stmt]) -> bool:
    """Check if function body contains verification calls beyond assert.

    This catches patterns like:
    - pytest.raises(...)
    - mock.assert_called_with(...)
    - with pytest.raises(...)
    """
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Call):
            # Check for pytest.raises
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in ("raises", "warns", "deprecated_call"):
                    return True
                # mock.assert_* methods
                if node.func.attr.startswith("assert_"):
                    return True
            # Check for direct calls like assert_that, assertEqual, etc.
            if isinstance(node.func, ast.Name):
                if node.func.id.startswith("assert"):
                    return True
        # Check for `with pytest.raises(...):`
        if isinstance(node, ast.With):
            for item in node.items:
                if isinstance(item.context_expr, ast.Call):
                    call = item.context_expr
                    if isinstance(call.func, ast.Attribute):
                        if call.func.attr in ("raises", "warns"):
                            return True
    return False


def _build_allowlist_set() -> set[Tuple[str, str]]:
    """Build a set of (relative_path, function_name) from the allowlist."""
    return {(path, func_name) for path, func_name, _ in ALLOWLIST}


def test_no_tautological_assert_true_in_tests() -> None:
    """Scan all test files for functions whose only assertion is bare `assert True`.

    A test function with `assert True` as its sole assertion can never fail,
    making it a tautological test that provides no verification value.
    """
    assert TESTS_DIR.is_dir(), f"Tests directory not found: {TESTS_DIR}"

    allowlist_set = _build_allowlist_set()
    all_findings: List[Tuple[str, str, int]] = []

    # Scan all test files, excluding archived/
    for test_file in sorted(TESTS_DIR.rglob("*.py")):
        # Skip archived tests
        if "archived" in test_file.parts:
            continue
        # Only scan test files
        if not test_file.name.startswith("test_"):
            continue

        findings = _scan_file_for_tautological_tests(test_file)

        for rel_path, func_name, lineno in findings:
            if (rel_path, func_name) not in allowlist_set:
                all_findings.append((rel_path, func_name, lineno))

    if all_findings:
        msg_lines = [
            f"Found {len(all_findings)} tautological `assert True` test(s) "
            f"(sole assertion is bare `assert True`):",
            "",
        ]
        for rel_path, func_name, lineno in all_findings:
            msg_lines.append(f"  {rel_path}:{lineno} - {func_name}")
        msg_lines.append("")
        msg_lines.append(
            "Fix: Replace `assert True` with a meaningful assertion, "
            "or add to ALLOWLIST in this file with a tracking issue number."
        )
        assert False, "\n".join(msg_lines)


def test_allowlist_entries_still_exist() -> None:
    """Verify allowlisted entries still exist — remove stale entries when fixed."""
    missing_entries: List[Tuple[str, str]] = []

    # Group allowlist by file for efficient scanning
    files_to_check: dict[str, list[str]] = {}
    for rel_path, func_name, _ in ALLOWLIST:
        files_to_check.setdefault(rel_path, []).append(func_name)

    for rel_path, func_names in files_to_check.items():
        filepath = REPO_ROOT / rel_path
        if not filepath.exists():
            # File removed — all its entries are stale
            for fn in func_names:
                missing_entries.append((rel_path, fn))
            continue

        findings = _scan_file_for_tautological_tests(filepath)
        found_funcs = {f[1] for f in findings}

        for fn in func_names:
            if fn not in found_funcs:
                missing_entries.append((rel_path, fn))

    if missing_entries:
        msg_lines = [
            f"Found {len(missing_entries)} stale ALLOWLIST entries "
            f"(tautological `assert True` was fixed or removed):",
            "",
        ]
        for rel_path, func_name in missing_entries:
            msg_lines.append(f"  ({rel_path!r}, {func_name!r})")
        msg_lines.append("")
        msg_lines.append("Remove these entries from ALLOWLIST in this file.")
        assert False, "\n".join(msg_lines)
