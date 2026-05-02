"""Unit tests for plugins/autonomous-dev/lib/hard_floor.py.

Implements: Issue #997 (Phase C: hard-floor registry).

Test surface (six functions):
    1. test_config_file_exists_and_parses — JSON well-formed and schema-correct
    2. test_is_hard_floor_matrix          — parametrized lookup matrix
    3. test_get_observability_hooks_returns_three
    4. test_fallback_on_missing_config    — missing file -> fallback
    5. test_fallback_on_malformed_json    — garbage bytes -> fallback
    6. test_fallback_constant_matches_shipped_json — drift guard
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Add the plugin lib directory to the import path. Path arithmetic:
# tests/unit/lib/test_hard_floor.py -> parents[3] = repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_LIB_DIR = _REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
_CONFIG_PATH = _REPO_ROOT / "plugins" / "autonomous-dev" / "config" / "hard_floor_hooks.json"

if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

import hard_floor  # noqa: E402  (import after sys.path manipulation)


# ---------------------------------------------------------------------------
# 1. Config file structural validation
# ---------------------------------------------------------------------------


def test_config_file_exists_and_parses() -> None:
    """Shipped JSON must exist, parse, and match the documented schema."""
    assert _CONFIG_PATH.exists(), f"Missing config file: {_CONFIG_PATH}"
    data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))

    assert isinstance(data, dict)
    assert data["version"] == 1
    assert "_doc" in data
    assert "_doc_observability" in data

    hard_floor_hooks = data["hard_floor_hooks"]
    assert isinstance(hard_floor_hooks, list)
    assert len(hard_floor_hooks) == 5, "Expected exactly 5 hard-floor entries"

    for entry in hard_floor_hooks:
        assert isinstance(entry, dict)
        assert "hook" in entry
        assert "reason" in entry
        # 'function' is optional (file-level rules omit it).

    observability = data["always_run_observability"]
    assert isinstance(observability, list)
    assert len(observability) == 3, "Expected exactly 3 observability hooks"
    assert all(isinstance(h, str) for h in observability)


# ---------------------------------------------------------------------------
# 2. is_hard_floor lookup matrix (parametrized)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "hook,function,expected",
    [
        # File-level entry: matches None function.
        ("security_scan.py", None, True),
        # Function-level entries.
        ("unified_pre_tool.py", "_check_bash_state_deletion", True),
        ("unified_pre_tool.py", "_check_settings_json_writes", True),
        ("unified_pre_tool.py", "_check_protected_infrastructure", True),
        ("unified_pre_tool.py", "_check_dangerous_bash", True),
        # Negative cases.
        ("plan_gate.py", None, False),  # Unlisted hook entirely.
        ("unified_pre_tool.py", "unknown_function", False),  # Listed hook, unknown function.
        ("unified_pre_tool.py", None, False),  # Function-required entries don't match None.
        ("security_scan.py", "any_function", False),  # File-level entry doesn't match a function name.
        ("", None, False),  # Empty hook name.
        ("", "_check_dangerous_bash", False),  # Empty hook name with valid function.
    ],
)
def test_is_hard_floor_matrix(hook: str, function: str | None, expected: bool) -> None:
    """Every (hook, function) -> expected pair must hold."""
    assert hard_floor.is_hard_floor(hook, function) is expected


# ---------------------------------------------------------------------------
# 3. Observability list
# ---------------------------------------------------------------------------


def test_get_observability_hooks_returns_three() -> None:
    """Observability list must be exactly the three documented hooks, in order."""
    hooks = hard_floor.get_observability_hooks()
    assert hooks == [
        "session_activity_logger.py",
        "conversation_archiver.py",
        "unified_session_tracker.py",
    ]
    # Each call returns a fresh list so callers can mutate without affecting the module.
    hooks.append("mutated.py")
    assert hard_floor.get_observability_hooks() == [
        "session_activity_logger.py",
        "conversation_archiver.py",
        "unified_session_tracker.py",
    ]


# ---------------------------------------------------------------------------
# 4. Fallback when config is missing
# ---------------------------------------------------------------------------


def test_fallback_on_missing_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Missing config file must trigger fallback — without over-blocking."""
    nonexistent = tmp_path / "does_not_exist.json"
    monkeypatch.setattr(hard_floor, "_get_config_path", lambda: nonexistent)

    # Hard-floor entries (in fallback constant) still return True.
    assert hard_floor.is_hard_floor("security_scan.py") is True
    assert hard_floor.is_hard_floor("unified_pre_tool.py", "_check_dangerous_bash") is True
    assert hard_floor.is_hard_floor("unified_pre_tool.py", "_check_bash_state_deletion") is True

    # CRITICAL: arbitrary hooks must NOT be classified as hard-floor under fallback.
    assert hard_floor.is_hard_floor("random_hook.py") is False
    assert hard_floor.is_hard_floor("plan_gate.py") is False
    assert hard_floor.is_hard_floor("unified_pre_tool.py", "unknown_function") is False

    # Observability list falls back to the constant.
    assert hard_floor.get_observability_hooks() == [
        "session_activity_logger.py",
        "conversation_archiver.py",
        "unified_session_tracker.py",
    ]


# ---------------------------------------------------------------------------
# 5. Fallback when config is malformed
# ---------------------------------------------------------------------------


def test_fallback_on_malformed_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Malformed JSON must trigger fallback — same invariants as missing file."""
    bad_path = tmp_path / "broken.json"
    bad_path.write_bytes(b"\x00\xff{not really json: ::: [[")
    monkeypatch.setattr(hard_floor, "_get_config_path", lambda: bad_path)

    assert hard_floor.is_hard_floor("security_scan.py") is True
    assert hard_floor.is_hard_floor("unified_pre_tool.py", "_check_dangerous_bash") is True
    assert hard_floor.is_hard_floor("random_hook.py") is False
    assert hard_floor.is_hard_floor("unified_pre_tool.py", "unknown_function") is False
    assert hard_floor.get_observability_hooks() == [
        "session_activity_logger.py",
        "conversation_archiver.py",
        "unified_session_tracker.py",
    ]


# ---------------------------------------------------------------------------
# 6. Drift guard: fallback constants must equal shipped JSON content
# ---------------------------------------------------------------------------


def test_fallback_constant_matches_shipped_json() -> None:
    """The in-module fallback MUST equal the shipped JSON. If this fails, fix one source."""
    data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))

    json_pairs: set[tuple[str, str | None]] = set()
    for entry in data["hard_floor_hooks"]:
        json_pairs.add((entry["hook"], entry.get("function")))

    fallback_pairs = set(hard_floor._FALLBACK_HARD_FLOOR_HOOKS)
    assert json_pairs == fallback_pairs, (
        "Hard-floor drift: JSON-only="
        f"{json_pairs - fallback_pairs}, fallback-only={fallback_pairs - json_pairs}"
    )

    json_observability = list(data["always_run_observability"])
    fallback_observability = list(hard_floor._FALLBACK_OBSERVABILITY_HOOKS)
    assert json_observability == fallback_observability, (
        f"Observability drift: json={json_observability} fallback={fallback_observability}"
    )
