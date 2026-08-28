"""Unit tests for the canonical hook budget loader (Issue #1704).

Covers the degradation paths the guards in
``tests/regression/regression/test_issue_1704_hook_time_budgets.py`` do not:
what happens when the canonical config is missing, malformed, or partial.

The governing rule is that a broken config must never break a hook. Hook
budgets degrade to a documented fail-safe; LIBRARY timeouts deliberately do
NOT, because silently substituting one would re-create the untracked constant
this module exists to remove.
"""

import json
import sys
from pathlib import Path

import pytest

# tests/unit/lib/<this file> -> lib -> unit -> tests -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import hook_budgets  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_budget_cache():
    """The loader caches the default path; a stale cache leaks across tests."""
    hook_budgets.clear_cache()
    yield
    hook_budgets.clear_cache()


def _write(tmp_path: Path, payload) -> Path:
    path = tmp_path / "budgets.json"
    path.write_text(json.dumps(payload) if not isinstance(payload, str) else payload)
    return path


class TestNormalizeHookName:
    """Callers pass either ``unified_pre_tool`` or ``unified_pre_tool.py``."""

    @pytest.mark.parametrize(
        "given,expected",
        [
            ("unified_pre_tool.py", "unified_pre_tool"),
            ("post_compact_enricher.sh", "post_compact_enricher"),
            ("plan_gate", "plan_gate"),
            ("SessionStart-batch-recovery.sh", "SessionStart-batch-recovery"),
        ],
    )
    def test_extension_is_stripped(self, given: str, expected: str) -> None:
        assert hook_budgets.normalize_hook_name(given) == expected

    def test_a_dot_that_is_not_an_extension_survives(self) -> None:
        """NEGATIVE CONTROL: it must not strip everything after any dot."""
        assert hook_budgets.normalize_hook_name("a.b.hook") == "a.b.hook"


class TestLoaderDegradation:
    """A broken config must never break a hook."""

    def test_missing_file_yields_the_failsafe(self, tmp_path: Path) -> None:
        config = hook_budgets.load_budget_config(tmp_path / "absent.json")
        assert config["hooks"] == {}
        assert config["libraries"] == {}
        assert (
            config["default"]["budget_seconds"]
            == hook_budgets.FALLBACK_DEFAULT_BUDGET_SECONDS
        )

    def test_malformed_json_yields_the_failsafe(self, tmp_path: Path) -> None:
        config = hook_budgets.load_budget_config(_write(tmp_path, "{not json"))
        assert config["hooks"] == {}

    def test_non_object_root_yields_the_failsafe(self, tmp_path: Path) -> None:
        config = hook_budgets.load_budget_config(_write(tmp_path, [1, 2, 3]))
        assert config["hooks"] == {}

    def test_comment_keys_are_stripped(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            {
                "default": {"budget_seconds": 5, "warning_pct": 0.8},
                "hooks": {
                    "_comment_hooks": "prose",
                    "real_hook": {"budget_seconds": 9, "warning_pct": 0.8},
                },
                "libraries": {"_comment_libs": "prose"},
            },
        )
        config = hook_budgets.load_budget_config(path)
        assert set(config["hooks"]) == {"real_hook"}
        assert config["libraries"] == {}

    def test_non_dict_hook_entries_are_dropped(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            {
                "default": {"budget_seconds": 5, "warning_pct": 0.8},
                "hooks": {"good": {"budget_seconds": 7}, "bad": "not-a-dict"},
            },
        )
        config = hook_budgets.load_budget_config(path)
        assert set(config["hooks"]) == {"good"}


class TestGetHookBudget:
    """Unknown hooks get the default; a typo must never disable a hook."""

    def test_known_hook_returns_its_budget(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            {
                "default": {"budget_seconds": 5, "warning_pct": 0.8},
                "hooks": {"h": {"budget_seconds": 33, "warning_pct": 0.8}},
            },
        )
        config = hook_budgets.load_budget_config(path)
        assert hook_budgets.get_hook_budget("h.py", config) == 33

    def test_unknown_hook_returns_the_default_never_zero(
        self, tmp_path: Path
    ) -> None:
        config = hook_budgets.load_budget_config(tmp_path / "absent.json")
        assert hook_budgets.get_hook_budget("typo", config) >= 1

    def test_non_integer_budget_falls_back_rather_than_raising(
        self, tmp_path: Path
    ) -> None:
        path = _write(
            tmp_path,
            {
                "default": {"budget_seconds": 5, "warning_pct": 0.8},
                "hooks": {"h": {"budget_seconds": "not-a-number"}},
            },
        )
        config = hook_budgets.load_budget_config(path)
        assert hook_budgets.get_hook_budget("h", config) == 5

    def test_has_hook_budget_distinguishes_default_from_absent(
        self, tmp_path: Path
    ) -> None:
        """The distinction that keeps unregistered processes out of the sink."""
        path = _write(
            tmp_path,
            {
                "default": {"budget_seconds": 5, "warning_pct": 0.8},
                "hooks": {"registered": {"budget_seconds": 5}},
            },
        )
        config = hook_budgets.load_budget_config(path)
        assert hook_budgets.has_hook_budget("registered.py", config) is True
        assert hook_budgets.has_hook_budget("mutation_witness_gate.py", config) is False
        # Both return a budget; only one is REGISTERED. That is the point.
        assert hook_budgets.get_hook_budget("mutation_witness_gate.py", config) == 5


class TestGetLibraryTimeout:
    """Library timeouts have NO safe default -- absence must be loud."""

    def test_missing_key_raises(self, tmp_path: Path) -> None:
        config = hook_budgets.load_budget_config(tmp_path / "absent.json")
        with pytest.raises(hook_budgets.BudgetConfigError) as exc:
            hook_budgets.get_library_timeout("nope", config)
        assert "hook_time_budgets.json" in str(exc.value)

    def test_malformed_value_raises(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            {
                "default": {"budget_seconds": 5, "warning_pct": 0.8},
                "libraries": {"k": {"timeout_seconds": "nope", "host_hooks": ["h"]}},
            },
        )
        config = hook_budgets.load_budget_config(path)
        with pytest.raises(hook_budgets.BudgetConfigError):
            hook_budgets.get_library_timeout("k", config)

    def test_library_timeout_or_degrades_instead_of_raising(self) -> None:
        """Import-time binding inside a hook must not raise."""
        assert hook_budgets.library_timeout_or("definitely-not-a-key", 7) == 7

    def test_library_timeout_or_prefers_the_canonical_value(self) -> None:
        """The fallback must be a fail-safe, not the value in normal operation."""
        canonical = hook_budgets.get_library_timeout("semantic_gate.TIMEOUT_S")
        assert hook_budgets.library_timeout_or("semantic_gate.TIMEOUT_S", 999) == canonical


class TestSchemaMaxSeconds:
    """The ceiling has one home: the schema that refuses a larger value."""

    def test_reads_the_real_schema(self) -> None:
        assert hook_budgets.schema_max_seconds() == 60

    def test_unreadable_schema_falls_back_without_widening(
        self, tmp_path: Path
    ) -> None:
        assert (
            hook_budgets.schema_max_seconds(tmp_path / "absent.json")
            == hook_budgets.FALLBACK_SCHEMA_MAX_SECONDS
        )

    def test_a_narrower_schema_is_honoured(self, tmp_path: Path) -> None:
        """NEGATIVE CONTROL: it reads the file rather than returning a constant."""
        path = tmp_path / "schema.json"
        path.write_text(
            json.dumps(
                {
                    "properties": {
                        "registrations": {
                            "items": {"properties": {"timeout": {"maximum": 12}}}
                        }
                    }
                }
            )
        )
        assert hook_budgets.schema_max_seconds(path) == 12


class TestRecordBudgetOverrun:
    """The recorder never raises, and never writes into a refusal count."""

    def test_writes_a_row_to_the_canonical_sink(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        assert hook_budgets.record_budget_overrun(
            hook_name="h.py", duration_ms=9000.0, budget_seconds=5
        )
        sink = tmp_path / ".claude" / "logs" / "hook-blocks.jsonl"
        row = json.loads(sink.read_text().splitlines()[0])
        assert row["decision_shape"] == hook_budgets.SHAPE_BUDGET_OVERRUN
        assert row["metadata"]["overrun_ms"] == 4000.0
        assert row["metadata"]["issue"] == 1704

    def test_never_raises_on_a_bad_duration(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        assert (
            hook_budgets.record_budget_overrun(
                hook_name="h.py", duration_ms="not-a-number", budget_seconds=5
            )
            is False
        )


class TestLiveConfigInvariants:
    """Properties of the shipped config that the guards depend on."""

    def test_every_library_names_a_host_that_exists(self) -> None:
        config = hook_budgets.load_budget_config()
        for key, entry in config["libraries"].items():
            for host in entry["host_hooks"]:
                assert hook_budgets.has_hook_budget(host, config), (
                    f"{key} names host {host!r}, which has no budget entry."
                )

    def test_every_measured_hook_carries_provenance(self) -> None:
        """A number without provenance becomes fact by attrition."""
        config = hook_budgets.load_budget_config()
        for name, entry in config["hooks"].items():
            assert entry.get("rationale"), f"{name} has no rationale"
            assert "measured_n" in entry, f"{name} has no measured_n"
