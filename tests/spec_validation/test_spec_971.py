"""Spec-blind validation tests for GitHub Issue #971.

These tests validate the acceptance criteria from the issue spec WITHOUT
referencing the implementation's internal structure. Each test exercises an
observable behavior described in the spec.

Acceptance Criteria (verbatim):
1. tool_intent.py provides classify(tool_name, tool_input) -> {READ, WRITE, EXEC}
2. Settings-write protection routes through tool_intent.classify (no command
   substring searches outside the legacy fallback).
3. python3 -c source is parsed with ast (not regex).
4. Bash classifier handles shlex.split, env-var prefixes, redirections,
   pipes, and bash -c / sh -c nesting.
5. scripts/audit_tool_intent_coverage.py exists and is wired to the test suite.
6. No regression in existing settings-write tests.
7. False-positive rate for json.load-style reads is zero.

Plus the 8 test scenarios from the issue body:
1. READ on settings.json passes (json.load(open('settings.json')))
2. WRITE on settings.json blocks (json.dump(..., open('settings.json','w')))
3. sed -i blocks
4. Plain cat passes
5. Heredoc redirect blocks
6. Edit tool on settings.json blocks; Read tool passes (tool name dispatch)
7. bash -c / sh -c recursion
8. Audit script CI gate
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Repository layout discovery (do NOT borrow from implementation files).
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
HOOKS_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
SCRIPTS_DIR = REPO_ROOT / "scripts"
TESTS_DIR = REPO_ROOT / "tests"

TOOL_INTENT_PATH = LIB_DIR / "tool_intent.py"
HOOK_PATH = HOOKS_DIR / "unified_pre_tool.py"
AUDIT_SCRIPT_PATH = SCRIPTS_DIR / "audit_tool_intent_coverage.py"


@pytest.fixture(scope="module")
def tool_intent_mod():
    """Load tool_intent module by absolute file path (no package install needed)."""
    if not TOOL_INTENT_PATH.exists():
        pytest.fail(
            f"AC1: tool_intent.py not found at {TOOL_INTENT_PATH}"
        )
    spec = importlib.util.spec_from_file_location("tool_intent", str(TOOL_INTENT_PATH))
    assert spec and spec.loader, "Failed to make spec for tool_intent.py"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def hook_mod():
    """Load unified_pre_tool by absolute path so we can call _detect_settings_json_write."""
    if not HOOK_PATH.exists():
        pytest.fail(f"unified_pre_tool.py not found at {HOOK_PATH}")
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    return importlib.import_module("unified_pre_tool")


# ---------------------------------------------------------------------------
# AC1: classify(tool_name, tool_input) -> {READ, WRITE, EXEC}
# ---------------------------------------------------------------------------


class TestAC1_ClassifyAPI:
    """AC1: classify() exists with the documented signature and return values."""

    def test_classify_is_callable(self, tool_intent_mod):
        """classify must exist and be callable."""
        assert hasattr(tool_intent_mod, "classify"), (
            "AC1: tool_intent module must export `classify`"
        )
        assert callable(tool_intent_mod.classify), (
            "AC1: tool_intent.classify must be callable"
        )

    def test_classify_returns_one_of_three_values(self, tool_intent_mod):
        """Return value must be one of READ / WRITE / EXEC for any well-formed input."""
        cases = [
            ("Read", {"file_path": "settings.json"}),
            ("Write", {"file_path": "settings.json"}),
            ("Bash", {"command": "rm settings.json"}),
            ("Bash", {"command": "echo hi"}),
            ("Task", {"description": "thing"}),
        ]
        allowed = {"READ", "WRITE", "EXEC"}
        for tool_name, tool_input in cases:
            result = tool_intent_mod.classify(tool_name, tool_input)
            assert result in allowed, (
                f"AC1: classify({tool_name!r}, ...) returned {result!r}, "
                f"expected one of {allowed}"
            )


# ---------------------------------------------------------------------------
# AC2: Settings-write protection routes through tool_intent.classify
# (i.e., the live primary code path no longer uses ad-hoc command substring
# searches against settings file names; the legacy regex fallback is allowed).
# ---------------------------------------------------------------------------


class TestAC2_RoutesThroughToolIntent:
    """AC2: hook delegates write-target extraction to tool_intent.write_targets."""

    def test_hook_imports_tool_intent_module(self, hook_mod):
        """Hook must have a tool_intent module reference (loaded defensively)."""
        # The hook should attempt to load tool_intent. We don't care HOW it's
        # named internally, only that there's a module-level attribute that
        # exposes the loaded module.
        candidates = [
            getattr(hook_mod, "_tool_intent", None),
            getattr(hook_mod, "tool_intent", None),
        ]
        loaded = [c for c in candidates if c is not None]
        assert loaded, (
            "AC2: hook must load the tool_intent module (no _tool_intent/"
            "tool_intent attribute found at module level)"
        )

    def test_extract_bash_writes_uses_tool_intent_for_python_read(self, hook_mod):
        """A read-only python -c snippet against settings.json must NOT be in write list.

        This is a behavioral assertion: regardless of HOW the hook is wired,
        if it's truly delegating to an AST classifier, json.load(open(...))
        cannot appear as a write target.
        """
        cmd = "python3 -c \"import json; json.load(open('settings.json'))\""
        targets = hook_mod._extract_bash_file_writes(cmd)
        assert "settings.json" not in targets, (
            f"AC2: _extract_bash_file_writes({cmd!r}) returned {targets!r} — "
            f"settings.json should NOT be flagged as a write target for json.load"
        )

    def test_no_substring_search_for_settings_in_live_path(self, hook_mod):
        """The live _detect_settings_json_write path must not flag json.load reads.

        This is the most important behavioral check: AC2 says no command
        substring search. The user-visible symptom of a substring search is
        a false positive on `json.load(open('settings.json'))`. If the live
        path returns None for that input, the substring search has been
        removed (or made harmless via the AST gate).
        """
        cmd = "python3 -c \"import json; json.load(open('settings.json'))\""
        result = hook_mod._detect_settings_json_write(cmd)
        assert result is None, (
            f"AC2: _detect_settings_json_write({cmd!r}) returned {result!r}; "
            f"a read-only json.load must not be classified as a write"
        )


# ---------------------------------------------------------------------------
# AC3: python3 -c source is parsed with ast (not regex)
# ---------------------------------------------------------------------------


class TestAC3_AstNotRegex:
    """AC3: python -c source goes through ast (directly or via python_write_detector)."""

    def test_python_write_detector_module_loadable(self):
        """The AST-based python_write_detector must exist (named or referenced)."""
        # tool_intent.py docstring mentions delegation to python_write_detector;
        # whichever file does the AST parsing, it must use `ast`.
        candidates = list(LIB_DIR.glob("python_write_detector*.py"))
        assert candidates, (
            f"AC3: python_write_detector module not found in {LIB_DIR}; "
            f"tool_intent claims to delegate AST parsing to it"
        )

    def test_python_write_detector_uses_ast(self):
        """python_write_detector source must contain `import ast` and use ast.parse."""
        path = LIB_DIR / "python_write_detector.py"
        if not path.exists():
            pytest.skip(
                "python_write_detector.py not found; AC3 may be satisfied via direct ast usage in tool_intent"
            )
        src = path.read_text()
        # Behavioral: it must use the ast module.
        assert "ast.parse" in src or "import ast" in src, (
            "AC3: python_write_detector must use the `ast` module"
        )

    def test_ast_classifies_write_correctly(self, tool_intent_mod):
        """Behavioral proof of AST: distinguishes json.load (read) from json.dump (write)."""
        read_cmd = "python3 -c \"import json; json.load(open('foo.json'))\""
        write_cmd = "python3 -c \"import json; json.dump({}, open('foo.json','w'))\""
        # Read must NOT yield a write target for foo.json:
        read_targets = tool_intent_mod.write_targets("Bash", {"command": read_cmd})
        assert "foo.json" not in read_targets, (
            f"AC3: AST classifier must not report json.load as writing — "
            f"got targets {read_targets!r}"
        )
        # Write MUST yield a write target for foo.json:
        write_targets = tool_intent_mod.write_targets("Bash", {"command": write_cmd})
        assert "foo.json" in write_targets, (
            f"AC3: AST classifier must report json.dump(..., 'w') as writing — "
            f"got targets {write_targets!r}"
        )


# ---------------------------------------------------------------------------
# AC4: Bash classifier handles shlex.split, env-vars, redirections,
# pipes, heredocs, and bash -c / sh -c nesting.
# ---------------------------------------------------------------------------


class TestAC4_BashFeatures:
    """AC4: tool_intent.classify on Bash handles all shell idioms."""

    def test_env_prefix_python_read(self, tool_intent_mod):
        cmd = "FOO=bar python3 -c \"import json; json.load(open('settings.json'))\""
        intent = tool_intent_mod.classify("Bash", {"command": cmd})
        assert intent == "READ", (
            f"AC4: env-prefixed read should classify as READ; got {intent!r}"
        )

    def test_pipe_passes_as_read(self, tool_intent_mod):
        cmd = "cat settings.json | jq .hooks"
        intent = tool_intent_mod.classify("Bash", {"command": cmd})
        assert intent == "READ", (
            f"AC4: pipe of read commands should classify as READ; got {intent!r}"
        )

    def test_redirection_classifies_as_write(self, tool_intent_mod):
        cmd = "echo {} > settings.json"
        intent = tool_intent_mod.classify("Bash", {"command": cmd})
        targets = tool_intent_mod.write_targets("Bash", {"command": cmd})
        assert intent == "WRITE", (
            f"AC4: redirection should classify as WRITE; got {intent!r}"
        )
        assert "settings.json" in targets, (
            f"AC4: redirection target must be detected; got {targets!r}"
        )

    def test_heredoc_redirect_classifies_as_write(self, tool_intent_mod):
        cmd = "cat <<EOF > settings.json\n{}\nEOF"
        intent = tool_intent_mod.classify("Bash", {"command": cmd})
        targets = tool_intent_mod.write_targets("Bash", {"command": cmd})
        assert intent == "WRITE", (
            f"AC4: heredoc redirect should classify as WRITE; got {intent!r}"
        )
        assert "settings.json" in targets, (
            f"AC4: heredoc target must be detected; got {targets!r}"
        )

    def test_bash_c_nested_read(self, tool_intent_mod):
        cmd = "bash -c \"cat settings.json\""
        intent = tool_intent_mod.classify("Bash", {"command": cmd})
        assert intent == "READ", (
            f"AC4: bash -c \"cat ...\" must recurse and classify as READ; got {intent!r}"
        )

    def test_bash_c_nested_write(self, tool_intent_mod):
        cmd = "bash -c \"rm settings.json\""
        intent = tool_intent_mod.classify("Bash", {"command": cmd})
        targets = tool_intent_mod.write_targets("Bash", {"command": cmd})
        assert intent == "WRITE", (
            f"AC4: bash -c \"rm ...\" must recurse and classify as WRITE; got {intent!r}"
        )
        assert "settings.json" in targets, (
            f"AC4: bash -c nested write target must be detected; got {targets!r}"
        )

    def test_sh_c_nested_write(self, tool_intent_mod):
        cmd = "sh -c \"echo {} > settings.json\""
        intent = tool_intent_mod.classify("Bash", {"command": cmd})
        assert intent == "WRITE", (
            f"AC4: sh -c with redirection must recurse to WRITE; got {intent!r}"
        )

    def test_classifier_uses_shlex(self):
        """Source-level structural check: tool_intent imports shlex."""
        src = TOOL_INTENT_PATH.read_text()
        assert "import shlex" in src or "from shlex" in src, (
            "AC4: tool_intent must use shlex (per spec)"
        )


# ---------------------------------------------------------------------------
# AC5: audit_tool_intent_coverage.py exists and is wired to the test suite.
# ---------------------------------------------------------------------------


class TestAC5_AuditScript:
    """AC5: audit script exists, is runnable, and is exercised by the test suite."""

    def test_audit_script_exists(self):
        assert AUDIT_SCRIPT_PATH.exists(), (
            f"AC5: {AUDIT_SCRIPT_PATH} must exist"
        )

    def test_audit_script_is_executable_as_module(self):
        """Run the script with --help to prove it's a working CLI."""
        result = subprocess.run(
            [sys.executable, str(AUDIT_SCRIPT_PATH), "--help"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, (
            f"AC5: audit script --help failed: {result.stderr}"
        )

    def test_audit_script_runs_against_logs(self):
        """The audit script must run end-to-end without crashing."""
        logs_dir = REPO_ROOT / ".claude" / "logs" / "activity"
        if not logs_dir.exists():
            pytest.skip(f"No activity logs at {logs_dir}; skipping live audit run")
        result = subprocess.run(
            [sys.executable, str(AUDIT_SCRIPT_PATH), "--logs-dir", str(logs_dir)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Non-strict mode must always exit 0 (per spec exit-code table).
        assert result.returncode == 0, (
            f"AC5: audit script (non-strict) must exit 0; "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )

    def test_audit_script_wired_to_test_suite(self):
        """A test file under tests/ must exist that exercises the audit script."""
        candidates = list(TESTS_DIR.rglob("test_audit_tool_intent_coverage*.py"))
        assert candidates, (
            "AC5: a test file matching test_audit_tool_intent_coverage*.py "
            "must exist under tests/ to gate the audit"
        )


# ---------------------------------------------------------------------------
# AC6: No regression in existing settings-write tests.
# We assert pre-existing settings-protection test files still exist with at
# least their original test density (>= some `def test_` count).
# ---------------------------------------------------------------------------


class TestAC6_NoRegression:
    """AC6: existing settings-write protection tests still exist and have content."""

    def test_python_settings_bypass_tests_present(self):
        path = REPO_ROOT / "tests" / "regression" / "smoke" / "test_python_settings_bypass.py"
        assert path.exists(), (
            f"AC6: pre-existing regression test {path} must still exist"
        )
        src = path.read_text()
        n = src.count("def test_")
        # The original file (per Issue #768) had at least 10 tests.
        assert n >= 10, (
            f"AC6: {path} must have >= 10 test functions (found {n})"
        )

    def test_infrastructure_protection_tests_present(self):
        path = REPO_ROOT / "tests" / "unit" / "hooks" / "test_infrastructure_protection.py"
        assert path.exists(), (
            f"AC6: pre-existing test {path} must still exist"
        )
        src = path.read_text()
        n = src.count("def test_")
        assert n >= 5, (
            f"AC6: {path} must have >= 5 test functions (found {n})"
        )

    def test_settings_blocking_writes_still_block(self, hook_mod):
        """Sanity: real write commands still get blocked by the hook function."""
        write_cmd = "python3 -c \"import json; json.dump({}, open('settings.json','w'))\""
        result = hook_mod._detect_settings_json_write(write_cmd)
        assert result is not None, (
            f"AC6: regression — json.dump write to settings.json must still be blocked, "
            f"got result={result!r}"
        )
        sed_cmd = "sed -i 's/foo/bar/' settings.json"
        result2 = hook_mod._detect_settings_json_write(sed_cmd)
        assert result2 is not None, (
            f"AC6: regression — sed -i on settings.json must still be blocked, "
            f"got result={result2!r}"
        )


# ---------------------------------------------------------------------------
# AC7: False-positive rate for json.load-style reads is zero.
# ---------------------------------------------------------------------------


class TestAC7_NoFalsePositiveOnReads:
    """AC7: read-only operations against settings.json must never block."""

    @pytest.mark.parametrize(
        "cmd",
        [
            "python3 -c \"import json; json.load(open('settings.json'))\"",
            "python3 -c \"import json; data = json.load(open('settings.json')); print(data)\"",
            "python3 -c 'import json; json.load(open(\"settings.json\"))'",
            "cat settings.json",
            "cat settings.json | jq .hooks",
            "grep hooks settings.json",
            "head -n 5 settings.json",
            "wc -l settings.json",
        ],
    )
    def test_pure_reads_are_not_blocked(self, hook_mod, cmd):
        result = hook_mod._detect_settings_json_write(cmd)
        assert result is None, (
            f"AC7: false positive — read-only command was blocked!\n"
            f"  cmd: {cmd!r}\n"
            f"  block reason: {result!r}"
        )


# ---------------------------------------------------------------------------
# 8 issue-body scenarios (cross-reference to acceptance criteria)
# ---------------------------------------------------------------------------


class TestIssueScenarios:
    """The 8 explicit test scenarios from the issue body."""

    # Scenario 1: READ on settings.json passes
    def test_scenario_1_read_settings_passes(self, hook_mod):
        cmd = "python3 -c \"import json; json.load(open('settings.json'))\""
        assert hook_mod._detect_settings_json_write(cmd) is None

    # Scenario 2: WRITE on settings.json blocks
    def test_scenario_2_write_settings_blocks(self, hook_mod):
        cmd = "python3 -c \"import json; json.dump({}, open('settings.json','w'))\""
        assert hook_mod._detect_settings_json_write(cmd) is not None

    # Scenario 3: sed -i blocks
    def test_scenario_3_sed_i_blocks(self, hook_mod):
        cmd = "sed -i 's/foo/bar/' settings.json"
        assert hook_mod._detect_settings_json_write(cmd) is not None

    # Scenario 4: Plain cat passes
    def test_scenario_4a_plain_cat_passes(self, hook_mod):
        assert hook_mod._detect_settings_json_write("cat settings.json") is None

    def test_scenario_4b_cat_pipe_jq_passes(self, hook_mod):
        assert hook_mod._detect_settings_json_write("cat settings.json | jq .hooks") is None

    # Scenario 5: Heredoc redirect blocks
    def test_scenario_5_heredoc_redirect_blocks(self, hook_mod):
        cmd = "cat <<EOF > settings.json\n{}\nEOF"
        assert hook_mod._detect_settings_json_write(cmd) is not None

    # Scenario 6: Edit tool on settings.json blocks; Read tool passes (via classify)
    def test_scenario_6a_edit_tool_classified_as_write(self, tool_intent_mod):
        intent = tool_intent_mod.classify("Edit", {"file_path": "settings.json"})
        assert intent == "WRITE"

    def test_scenario_6b_read_tool_classified_as_read(self, tool_intent_mod):
        intent = tool_intent_mod.classify("Read", {"file_path": "settings.json"})
        assert intent == "READ"

    # Scenario 7: bash -c / sh -c recursion
    def test_scenario_7a_bash_c_cat_reads(self, tool_intent_mod):
        intent = tool_intent_mod.classify("Bash", {"command": "bash -c \"cat settings.json\""})
        assert intent == "READ"

    def test_scenario_7b_bash_c_rm_blocks(self, hook_mod):
        cmd = "bash -c \"rm settings.json\""
        assert hook_mod._detect_settings_json_write(cmd) is not None

    # Scenario 8: Audit script CI gate (covered by TestAC5)
    def test_scenario_8_audit_script_passes_in_strict_mode(self):
        """Per AC8: 'passes when every observed tool name has a defined classification'."""
        logs_dir = REPO_ROOT / ".claude" / "logs" / "activity"
        if not logs_dir.exists():
            pytest.skip("No activity logs available")
        result = subprocess.run(
            [sys.executable, str(AUDIT_SCRIPT_PATH),
             "--logs-dir", str(logs_dir),
             "--strict"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Strict mode passes iff every observed tool is covered.
        assert result.returncode == 0, (
            f"Scenario 8: audit --strict failed (uncovered tools observed): "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
