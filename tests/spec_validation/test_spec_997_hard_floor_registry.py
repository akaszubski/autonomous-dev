"""Spec-blind validation for Issue #997 — Phase C: hard-floor hook registry.

Tests are written against the acceptance criteria ONLY. The validator does not
read implementer output, code diffs, or reviewer feedback. Each test maps to a
single acceptance criterion and produces a binary pass/fail result.

Acceptance criteria recap:
1. hard_floor_hooks.json exists with required structure.
2. lib/hard_floor.py exposes is_hard_floor() and get_observability_hooks().
3. is_hard_floor("security_scan.py") -> True.
4. is_hard_floor("unified_pre_tool.py", "_detect_git_bypass") -> True.
5. is_hard_floor("plan_gate.py") -> False.
6. Malformed JSON config -> fail-closed behavior.
7. Missing config file -> fail-closed.
8. Tests pass: pytest tests/unit/lib/test_hard_floor.py -v.
9. No production caller imports hard_floor (zero-blast-radius Phase C).
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

# Repo root resolved relative to this file: tests/spec_validation/<file>.py.
REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "plugins" / "autonomous-dev" / "config" / "hard_floor_hooks.json"
LIB_PATH = REPO_ROOT / "plugins" / "autonomous-dev" / "lib" / "hard_floor.py"
LIB_DIR = str(REPO_ROOT / "plugins" / "autonomous-dev" / "lib")
UNIT_TEST_PATH = REPO_ROOT / "tests" / "unit" / "lib" / "test_hard_floor.py"


@pytest.fixture
def hard_floor_module():
    """Import the hard_floor module fresh for each test (so monkeypatch is clean)."""
    if LIB_DIR not in sys.path:
        sys.path.insert(0, LIB_DIR)
    if "hard_floor" in sys.modules:
        importlib.reload(sys.modules["hard_floor"])
    import hard_floor  # noqa: WPS433  (runtime import is intentional)

    return hard_floor


# ---------------------------------------------------------------------------
# AC #1 — config JSON exists with required structure
# ---------------------------------------------------------------------------


class TestSpec997Criterion1ConfigStructure:
    """AC #1: config file exists with version, _doc, hard_floor_hooks (5),
    _doc_observability, always_run_observability (3)."""

    def test_spec_997_1a_config_file_exists(self):
        assert CONFIG_PATH.is_file(), f"Expected config at {CONFIG_PATH}"

    def test_spec_997_1b_config_has_required_keys(self):
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        required = {
            "version",
            "_doc",
            "hard_floor_hooks",
            "_doc_observability",
            "always_run_observability",
        }
        missing = required - set(data.keys())
        assert not missing, f"Missing required keys: {missing}"

    def test_spec_997_1c_hard_floor_hooks_has_five_entries(self):
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        entries = data["hard_floor_hooks"]
        assert isinstance(entries, list), "hard_floor_hooks must be a list"
        assert len(entries) == 5, f"Expected 5 entries, found {len(entries)}"

    def test_spec_997_1d_observability_has_three_entries(self):
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        obs = data["always_run_observability"]
        assert isinstance(obs, list), "always_run_observability must be a list"
        assert len(obs) == 3, f"Expected 3 observability entries, found {len(obs)}"


# ---------------------------------------------------------------------------
# AC #2 — public API exists and is callable
# ---------------------------------------------------------------------------


class TestSpec997Criterion2PublicAPI:
    """AC #2: lib/hard_floor.py exposes is_hard_floor and get_observability_hooks."""

    def test_spec_997_2a_module_file_exists(self):
        assert LIB_PATH.is_file(), f"Expected module at {LIB_PATH}"

    def test_spec_997_2b_is_hard_floor_callable(self, hard_floor_module):
        assert callable(getattr(hard_floor_module, "is_hard_floor", None)), \
            "is_hard_floor must be a callable public API"

    def test_spec_997_2c_get_observability_hooks_callable(self, hard_floor_module):
        assert callable(getattr(hard_floor_module, "get_observability_hooks", None)), \
            "get_observability_hooks must be a callable public API"

    def test_spec_997_2d_get_observability_hooks_returns_list(self, hard_floor_module):
        result = hard_floor_module.get_observability_hooks()
        assert isinstance(result, list), f"Expected list, got {type(result).__name__}"


# ---------------------------------------------------------------------------
# AC #3 — is_hard_floor("security_scan.py") returns True
# ---------------------------------------------------------------------------


class TestSpec997Criterion3SecurityScanIsHardFloor:
    def test_spec_997_3_security_scan_is_hard_floor(self, hard_floor_module):
        assert hard_floor_module.is_hard_floor("security_scan.py") is True


# ---------------------------------------------------------------------------
# AC #4 — is_hard_floor("unified_pre_tool.py", "_detect_git_bypass") -> True
# ---------------------------------------------------------------------------


class TestSpec997Criterion4DangerousBashIsHardFloor:
    def test_spec_997_4_dangerous_bash_is_hard_floor(self, hard_floor_module):
        result = hard_floor_module.is_hard_floor(
            "unified_pre_tool.py", "_detect_git_bypass"
        )
        assert result is True


# ---------------------------------------------------------------------------
# AC #5 — is_hard_floor("plan_gate.py") returns False (not in registry)
# ---------------------------------------------------------------------------


class TestSpec997Criterion5PlanGateNotHardFloor:
    def test_spec_997_5_plan_gate_not_hard_floor(self, hard_floor_module):
        assert hard_floor_module.is_hard_floor("plan_gate.py") is False


# ---------------------------------------------------------------------------
# AC #6 — malformed JSON -> fail-closed (security-critical hooks still True)
# ---------------------------------------------------------------------------


class TestSpec997Criterion6MalformedJSONFailClosed:
    """Fail-closed semantics: even if config is corrupted, the security-critical
    entries (security_scan, dangerous_bash) MUST still be classified as
    hard-floor. The implementation may achieve this via a fallback constant or
    by treating unknown state as hard-floor — either is acceptable as long as
    catastrophe-prevention checks remain True."""

    def test_spec_997_6a_malformed_json_security_scan_still_hard_floor(
        self, hard_floor_module, tmp_path, monkeypatch
    ):
        bad_path = tmp_path / "hard_floor_hooks.json"
        bad_path.write_text("{this is not valid json", encoding="utf-8")

        monkeypatch.setattr(hard_floor_module, "_get_config_path", lambda: bad_path)

        assert hard_floor_module.is_hard_floor("security_scan.py") is True, (
            "FAIL-CLOSED violation: security_scan.py must remain hard-floor "
            "when config is malformed"
        )

    def test_spec_997_6b_malformed_json_dangerous_bash_still_hard_floor(
        self, hard_floor_module, tmp_path, monkeypatch
    ):
        bad_path = tmp_path / "hard_floor_hooks.json"
        bad_path.write_text("[oh no", encoding="utf-8")

        monkeypatch.setattr(hard_floor_module, "_get_config_path", lambda: bad_path)

        assert hard_floor_module.is_hard_floor(
            "unified_pre_tool.py", "_detect_git_bypass"
        ) is True, "dangerous_bash must remain hard-floor when config is malformed"

    def test_spec_997_6c_malformed_json_lookup_does_not_raise(
        self, hard_floor_module, tmp_path, monkeypatch
    ):
        bad_path = tmp_path / "hard_floor_hooks.json"
        bad_path.write_text("not json at all !!", encoding="utf-8")

        monkeypatch.setattr(hard_floor_module, "_get_config_path", lambda: bad_path)

        # Lookup must be exception-safe under a corrupted config.
        try:
            hard_floor_module.is_hard_floor("plan_gate.py")
            hard_floor_module.get_observability_hooks()
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"Lookup raised under malformed JSON: {exc!r}")


# ---------------------------------------------------------------------------
# AC #7 — missing config -> fail-closed
# ---------------------------------------------------------------------------


class TestSpec997Criterion7MissingConfigFailClosed:
    def test_spec_997_7a_missing_config_security_scan_still_hard_floor(
        self, hard_floor_module, tmp_path, monkeypatch
    ):
        missing = tmp_path / "does_not_exist.json"
        assert not missing.exists()

        monkeypatch.setattr(hard_floor_module, "_get_config_path", lambda: missing)

        assert hard_floor_module.is_hard_floor("security_scan.py") is True, (
            "FAIL-CLOSED violation: security_scan.py must remain hard-floor "
            "when config file is missing"
        )

    def test_spec_997_7b_missing_config_dangerous_bash_still_hard_floor(
        self, hard_floor_module, tmp_path, monkeypatch
    ):
        missing = tmp_path / "absent.json"
        monkeypatch.setattr(hard_floor_module, "_get_config_path", lambda: missing)

        assert hard_floor_module.is_hard_floor(
            "unified_pre_tool.py", "_detect_git_bypass"
        ) is True

    def test_spec_997_7c_missing_config_lookup_does_not_raise(
        self, hard_floor_module, tmp_path, monkeypatch
    ):
        missing = tmp_path / "no_such_config.json"
        monkeypatch.setattr(hard_floor_module, "_get_config_path", lambda: missing)

        try:
            hard_floor_module.is_hard_floor("plan_gate.py")
            hard_floor_module.get_observability_hooks()
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"Lookup raised under missing config: {exc!r}")

    def test_spec_997_7d_missing_config_observability_still_returns_list(
        self, hard_floor_module, tmp_path, monkeypatch
    ):
        missing = tmp_path / "absent.json"
        monkeypatch.setattr(hard_floor_module, "_get_config_path", lambda: missing)
        result = hard_floor_module.get_observability_hooks()
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# AC #8 — implementer's unit tests pass
# ---------------------------------------------------------------------------


class TestSpec997Criterion8ImplementerTestsPass:
    def test_spec_997_8_unit_tests_pass(self):
        assert UNIT_TEST_PATH.is_file(), f"Expected unit tests at {UNIT_TEST_PATH}"
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(UNIT_TEST_PATH), "-v", "--tb=short"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            f"pytest exit code = {result.returncode}\n"
            f"STDOUT:\n{result.stdout[-3000:]}\n"
            f"STDERR:\n{result.stderr[-1500:]}"
        )


# ---------------------------------------------------------------------------
# AC #9 — Phase C registry-only had ZERO callers; Phase E (#999) adds the
# expected consumer enforcement_decision.py. The allowlist below is the
# explicit approved set — anything outside it is still an offender.
# ---------------------------------------------------------------------------


# Approved Phase E consumers. Every entry MUST point to a real file. A new
# consumer is added only after a planning artifact justifies it.
PHASE_E_APPROVED_PLUGIN_CALLERS = frozenset(
    {
        # Phase E (#999) — pure policy layer that gates non-hard-floor checks.
        "plugins/autonomous-dev/lib/enforcement_decision.py",
    }
)

PHASE_E_APPROVED_TEST_REFS = frozenset(
    {
        # Phase E integration test exercises the hard_floor invariant from
        # the consumer side — explicit regression lock that hard-floor
        # functions still report True after Phase E wires the gate.
        "tests/unit/hooks/test_phase_e_integration.py",
    }
)


class TestSpec997Criterion9NoProductionCallers:
    """After Phase E (#999), exactly one production caller is allowed —
    enforcement_decision.py. Any other plugin import of hard_floor is still
    an unapproved consumer and fails this test."""

    def test_spec_997_9_zero_callers_in_plugins(self):
        plugins_dir = REPO_ROOT / "plugins"
        assert plugins_dir.is_dir(), f"Missing {plugins_dir}"
        offenders: list[str] = []
        for py in plugins_dir.rglob("*.py"):
            # The module itself is allowed to define `from __future__ import ...`
            # and its own name; we only forbid OTHER unapproved files.
            if py.resolve() == LIB_PATH.resolve():
                continue
            try:
                text = py.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if "from hard_floor" in text or "import hard_floor" in text:
                rel = str(py.relative_to(REPO_ROOT))
                if rel in PHASE_E_APPROVED_PLUGIN_CALLERS:
                    continue  # explicitly approved
                offenders.append(rel)
        assert not offenders, (
            "Unapproved plugin consumer of hard_floor. Add to "
            f"PHASE_E_APPROVED_PLUGIN_CALLERS only with a planning artifact. "
            f"Offenders: {offenders}"
        )

    def test_spec_997_9_only_expected_test_files_reference_module(self):
        tests_dir = REPO_ROOT / "tests"
        # The new unit test file (implementer-owned) and this spec-validation
        # file are the only legal references inside tests/, plus the Phase E
        # integration test that locks the hard-floor invariant.
        allowed_paths = {
            UNIT_TEST_PATH.resolve(),
            Path(__file__).resolve(),
        }
        allowed_rels = PHASE_E_APPROVED_TEST_REFS
        offenders: list[str] = []
        for py in tests_dir.rglob("*.py"):
            if py.resolve() in allowed_paths:
                continue
            try:
                text = py.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if "from hard_floor" in text or "import hard_floor" in text:
                rel = str(py.relative_to(REPO_ROOT))
                if rel in allowed_rels:
                    continue
                offenders.append(rel)
        assert not offenders, (
            "Unapproved test reference to hard_floor. Offenders: "
            f"{offenders}"
        )


# ---------------------------------------------------------------------------
# AC #1004 — function-name drift guard (cross-validate registry vs. source)
# ---------------------------------------------------------------------------


def _load_unified_pre_tool_module():
    """Dynamically load unified_pre_tool.py as a module for inspection."""
    hook_path = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks" / "unified_pre_tool.py"
    spec = importlib.util.spec_from_file_location("unified_pre_tool", hook_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_json_registry():
    """Load function-level entries from hard_floor_hooks.json."""
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return [
        (entry["hook"], entry["function"])
        for entry in data["hard_floor_hooks"]
        if "function" in entry
    ]


def _load_fallback_constant():
    """Load function-level entries from _FALLBACK_HARD_FLOOR_HOOKS constant."""
    if LIB_DIR not in sys.path:
        sys.path.insert(0, LIB_DIR)
    if "hard_floor" in sys.modules:
        importlib.reload(sys.modules["hard_floor"])
    import hard_floor  # noqa: WPS433
    return [
        (hook, fn) for (hook, fn) in hard_floor._FALLBACK_HARD_FLOOR_HOOKS if fn is not None
    ]


class TestSpec1004RegistryFunctionNamesExistInSource:
    """AC #1004: every function-level hard-floor entry must name a real
    `def` in its hook source file. Catches the latent correctness hole that
    Phase E (#999) would otherwise silently skip hard-floor checks.
    """

    @pytest.mark.parametrize(
        "source_name,loader",
        [
            ("json", _load_json_registry),
            ("fallback", _load_fallback_constant),
        ],
    )
    def test_registry_function_names_exist_in_source(self, source_name, loader):
        """Every function-level entry in {source} must name a real function in unified_pre_tool.py."""
        entries = loader()
        # Group by hook file
        by_hook: dict[str, list[str]] = {}
        for hook_filename, fn_name in entries:
            by_hook.setdefault(hook_filename, []).append(fn_name)

        offenders: list[str] = []
        for hook_filename, fn_names in by_hook.items():
            if hook_filename != "unified_pre_tool.py":
                continue  # only validate unified_pre_tool entries here
            module = _load_unified_pre_tool_module()
            actual_funcs = {
                name for name, _ in inspect.getmembers(module, inspect.isfunction)
            }
            for fn in fn_names:
                if fn not in actual_funcs:
                    offenders.append(f"{hook_filename}::{fn}")

        assert not offenders, (
            f"Registry source '{source_name}' references function names that "
            f"do not exist in source. Phase E enforcement will silently skip "
            f"these checks. Offenders: {offenders}"
        )
