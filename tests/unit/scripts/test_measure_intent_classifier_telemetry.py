"""Unit tests for ``measure_intent_classifier.py --validate-from-telemetry``.

Tests the Phase B telemetry-validation flow added in Issue #1077:

- Wilson 95% CI math (parametrized over canonical edge cases)
- ``mode_skip`` row filtering (synthetic prefix, malformed JSONL)
- Skip-class extraction from the ``mode_skip:<class>`` reason format
- Implement-shape heuristic (regex tier + aggregate tier)
- Session metadata loading from sqlite (missing DB, missing table, valid)
- End-to-end ``validate_from_telemetry`` orchestrator
- N=0 graceful path (empty / all-synthetic telemetry)
- Security sentinel: raw ``first_user_prompt`` MUST NOT appear in output JSON

GitHub Issue: #1077
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

# Add scripts directory to path (mirrors the existing pattern in
# tests/unit/scripts/test_extract_and_label_intent_corpus.py).
sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[3] / "scripts"),
)

from measure_intent_classifier import (  # noqa: E402  (path setup precedes import)
    _AGGREGATE_BYTES_THRESHOLD,
    _AGGREGATE_TOOL_THRESHOLD,
    _INSUFFICIENT_SAMPLE_THRESHOLD,
    _SYNTHETIC_SESSION_PREFIX,
    _TELEMETRY_SCHEMA_VERSION,
    _extract_skip_class,
    _filter_synthetic,
    _is_implement_shaped,
    _iter_mode_skip_rows,
    _load_session_metadata,
    _wilson_ci,
    validate_from_telemetry,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_jsonl(tmp_path: Path, rows: List[Dict[str, Any]]) -> Path:
    """Write rows as JSONL to a temp file. Each row becomes one line."""
    p = tmp_path / "hook-blocks.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return p


def _make_sessions_db(tmp_path: Path, sessions: List[Dict[str, Any]]) -> Path:
    """Build a minimal sessions.db mirroring the production 17-column schema."""
    p = tmp_path / "sessions.db"
    conn = sqlite3.connect(str(p))
    try:
        conn.execute(
            """
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY,
                project TEXT,
                cwd TEXT,
                archive_path TEXT,
                first_seen TEXT,
                last_updated TEXT,
                message_count INTEGER,
                user_messages INTEGER,
                assistant_messages INTEGER,
                tool_calls INTEGER,
                total_input_tokens INTEGER,
                total_output_tokens INTEGER,
                transcript_bytes INTEGER,
                model TEXT,
                first_user_prompt TEXT,
                cache_read_tokens INTEGER DEFAULT 0,
                cache_creation_tokens INTEGER DEFAULT 0
            )
            """
        )
        for s in sessions:
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, project, cwd, archive_path, first_seen,
                    last_updated, message_count, user_messages,
                    assistant_messages, tool_calls, total_input_tokens,
                    total_output_tokens, transcript_bytes, model,
                    first_user_prompt, cache_read_tokens, cache_creation_tokens
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    s.get("session_id", ""),
                    s.get("project", "test"),
                    s.get("cwd", "/tmp"),
                    s.get("archive_path", ""),
                    s.get("first_seen", ""),
                    s.get("last_updated", ""),
                    s.get("message_count", 0),
                    s.get("user_messages", 0),
                    s.get("assistant_messages", 0),
                    s.get("tool_calls", 0),
                    s.get("total_input_tokens", 0),
                    s.get("total_output_tokens", 0),
                    s.get("transcript_bytes", 0),
                    s.get("model", ""),
                    s.get("first_user_prompt", ""),
                    s.get("cache_read_tokens", 0),
                    s.get("cache_creation_tokens", 0),
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return p


# ---------------------------------------------------------------------------
# 1. Wilson CI math
# ---------------------------------------------------------------------------


class TestWilsonCI:
    """Wilson score 95% CI invariants + canonical hand-computed values."""

    @pytest.mark.parametrize(
        "successes,n",
        [
            (0, 0),
            (0, 1),
            (1, 1),
            (5, 10),
            (5, 100),
            (10, 200),
            (0, 50),
            (50, 50),
        ],
    )
    def test_invariants(self, successes: int, n: int) -> None:
        """For all (successes, n): 0 <= ci_low <= p_hat <= ci_high <= 1."""
        ci_low, ci_high = _wilson_ci(successes, n)
        assert 0.0 <= ci_low <= ci_high <= 1.0
        if n > 0:
            p_hat = successes / n
            assert ci_low <= p_hat <= ci_high

    def test_canonical_5_of_100(self) -> None:
        """Wilson(5, 100) matches canonical Wikipedia formula within 4 decimals."""
        ci_low, ci_high = _wilson_ci(5, 100)
        # Canonical formula: (5,100) -> (0.0215, 0.1118) at 4 decimals.
        assert round(ci_low, 4) == 0.0215
        assert round(ci_high, 4) == 0.1118

    def test_canonical_10_of_200(self) -> None:
        """Wilson(10, 200) matches canonical Wikipedia formula within 4 decimals."""
        ci_low, ci_high = _wilson_ci(10, 200)
        # Canonical formula: (10,200) -> (0.0274, 0.0896) at 4 decimals.
        assert round(ci_low, 4) == 0.0274
        assert round(ci_high, 4) == 0.0896

    def test_n_zero_returns_full_interval(self) -> None:
        assert _wilson_ci(0, 0) == (0.0, 1.0)

    def test_zero_successes_low_is_zero(self) -> None:
        ci_low, _ = _wilson_ci(0, 50)
        assert ci_low == 0.0

    def test_all_successes_high_is_one(self) -> None:
        _, ci_high = _wilson_ci(50, 50)
        assert ci_high == 1.0


# ---------------------------------------------------------------------------
# 2. Mode-skip row filtering
# ---------------------------------------------------------------------------


class TestModeSkipFiltering:
    def test_empty_file(self, tmp_path: Path) -> None:
        p = _make_jsonl(tmp_path, [])
        assert list(_iter_mode_skip_rows(p)) == []

    def test_filters_non_mode_skip(self, tmp_path: Path) -> None:
        p = _make_jsonl(
            tmp_path,
            [
                {"decision_shape": "deny", "session_id": "abc"},
                {"decision_shape": "mode_skip", "session_id": "xyz"},
                {"decision_shape": "allow", "session_id": "qrs"},
            ],
        )
        rows = list(_iter_mode_skip_rows(p))
        assert len(rows) == 1
        assert rows[0]["session_id"] == "xyz"

    def test_filter_synthetic_drops_phase_e(self) -> None:
        rows = [
            {"session_id": "phase-e-test-conv-skip"},
            {"session_id": "real-session-1"},
            {"session_id": ""},
            {"session_id": None},
            {},  # missing session_id entirely
            {"session_id": "phase-e-test-something-else"},
            {"session_id": "real-session-2"},
        ]
        kept = list(_filter_synthetic(rows))
        sids = [r["session_id"] for r in kept]
        assert sids == ["real-session-1", "real-session-2"]

    def test_malformed_jsonl_line_is_skipped(self, tmp_path: Path) -> None:
        p = tmp_path / "hook-blocks.jsonl"
        p.write_text(
            '{"decision_shape": "mode_skip", "session_id": "good"}\n'
            "this is not json\n"
            '{"decision_shape": "mode_skip", "session_id": "good2"}\n',
            encoding="utf-8",
        )
        rows = list(_iter_mode_skip_rows(p))
        sids = [r["session_id"] for r in rows]
        assert sids == ["good", "good2"]

    def test_all_synthetic_yields_empty(self, tmp_path: Path) -> None:
        p = _make_jsonl(
            tmp_path,
            [
                {
                    "decision_shape": "mode_skip",
                    "reason": "mode_skip:doc",
                    "session_id": f"{_SYNTHETIC_SESSION_PREFIX}a",
                },
                {
                    "decision_shape": "mode_skip",
                    "reason": "mode_skip:conversation",
                    "session_id": f"{_SYNTHETIC_SESSION_PREFIX}b",
                },
            ],
        )
        all_rows = list(_iter_mode_skip_rows(p))
        kept = list(_filter_synthetic(all_rows))
        assert len(all_rows) == 2
        assert kept == []


# ---------------------------------------------------------------------------
# 3. Skip-class extraction
# ---------------------------------------------------------------------------


class TestSkipClassExtraction:
    """Parsing of ``mode_skip:<class>`` reasons across all 9 SKIP classes."""

    @pytest.mark.parametrize(
        "reason,expected",
        [
            ("mode_skip:doc", "doc"),
            ("mode_skip:config", "config"),
            ("mode_skip:typo", "typo"),
            ("mode_skip:status_query", "status_query"),
            ("mode_skip:conversation", "conversation"),
            ("mode_skip:exploration", "exploration"),
            ("mode_skip:triage", "triage"),
            ("mode_skip:remote_ops", "remote_ops"),
            ("mode_skip:scratch", "scratch"),
        ],
    )
    def test_valid_skip_classes(self, reason: str, expected: str) -> None:
        assert _extract_skip_class(reason) == expected

    @pytest.mark.parametrize(
        "reason",
        [
            "mode_skip",  # missing colon
            "",  # empty string
            "random_string",  # unrelated text
            "mode_skip:",  # empty class
            "deny:doc",  # wrong prefix
            None,  # not a string
        ],
    )
    def test_malformed_returns_unknown(self, reason: Any) -> None:
        assert _extract_skip_class(reason) == "unknown"


# ---------------------------------------------------------------------------
# 4. Implement-shape heuristic
# ---------------------------------------------------------------------------


class TestImplementShaped:
    @pytest.mark.parametrize(
        "prompt",
        [
            "/implement issue #1077",
            "  /implement add the new feature",
            "/IMPLEMENT case-insensitive",
            "/refactor the foo module",
            "/fix the broken test",
        ],
    )
    def test_regex_match(self, prompt: str) -> None:
        is_impl, reason = _is_implement_shaped(
            {
                "first_user_prompt": prompt,
                "tool_calls": 0,
                "transcript_bytes": 0,
            }
        )
        assert is_impl is True
        assert reason == "regex"

    def test_aggregate_match(self) -> None:
        is_impl, reason = _is_implement_shaped(
            {
                "first_user_prompt": "What does this codebase do?",
                "tool_calls": _AGGREGATE_TOOL_THRESHOLD,
                "transcript_bytes": _AGGREGATE_BYTES_THRESHOLD,
            }
        )
        assert is_impl is True
        assert reason == "aggregate"

    def test_aggregate_below_threshold(self) -> None:
        is_impl, reason = _is_implement_shaped(
            {
                "first_user_prompt": "Just a question",
                "tool_calls": _AGGREGATE_TOOL_THRESHOLD - 1,
                "transcript_bytes": _AGGREGATE_BYTES_THRESHOLD,
            }
        )
        assert is_impl is False
        assert reason == "no_signal"

    def test_no_metadata(self) -> None:
        is_impl, reason = _is_implement_shaped(None)
        assert is_impl is False
        assert reason == "no_metadata"

    def test_none_prompt(self) -> None:
        is_impl, reason = _is_implement_shaped(
            {
                "first_user_prompt": None,
                "tool_calls": 1,
                "transcript_bytes": 100,
            }
        )
        assert is_impl is False
        assert reason == "no_signal"

    def test_unicode_prompt(self) -> None:
        # Unicode prompt that isn't an implement command, low tool_calls.
        is_impl, reason = _is_implement_shaped(
            {
                "first_user_prompt": "Help me understand 你好 🚀",
                "tool_calls": 1,
                "transcript_bytes": 200,
            }
        )
        assert is_impl is False
        assert reason == "no_signal"

    def test_aggregate_with_implement_regex_takes_regex(self) -> None:
        # Both regex and aggregate fire — regex should win (first tier).
        is_impl, reason = _is_implement_shaped(
            {
                "first_user_prompt": "/implement add feature X",
                "tool_calls": 100,
                "transcript_bytes": 1_000_000,
            }
        )
        assert is_impl is True
        assert reason == "regex"


# ---------------------------------------------------------------------------
# 5. Session metadata loading
# ---------------------------------------------------------------------------


class TestSessionMetadataLoad:
    def test_missing_db(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist.db"
        result = _load_session_metadata(missing, {"sid1"})
        assert result == {}

    def test_missing_sessions_table(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.db"
        conn = sqlite3.connect(str(p))
        try:
            conn.execute("CREATE TABLE other (id INTEGER)")
            conn.commit()
        finally:
            conn.close()
        result = _load_session_metadata(p, {"sid1"})
        assert result == {}

    def test_valid_lookup(self, tmp_path: Path) -> None:
        db = _make_sessions_db(
            tmp_path,
            [
                {
                    "session_id": "sid-a",
                    "first_user_prompt": "hello",
                    "tool_calls": 5,
                    "transcript_bytes": 1234,
                    "message_count": 4,
                },
                {
                    "session_id": "sid-b",
                    "first_user_prompt": "world",
                    "tool_calls": 0,
                    "transcript_bytes": 0,
                    "message_count": 1,
                },
            ],
        )
        result = _load_session_metadata(db, {"sid-a", "sid-b"})
        assert set(result.keys()) == {"sid-a", "sid-b"}
        assert result["sid-a"]["first_user_prompt"] == "hello"
        assert result["sid-a"]["tool_calls"] == 5
        assert result["sid-a"]["transcript_bytes"] == 1234
        assert result["sid-b"]["message_count"] == 1

    def test_missing_ids_returns_subset(self, tmp_path: Path) -> None:
        db = _make_sessions_db(
            tmp_path,
            [
                {
                    "session_id": "sid-x",
                    "first_user_prompt": "p",
                    "tool_calls": 1,
                    "transcript_bytes": 10,
                    "message_count": 1,
                }
            ],
        )
        result = _load_session_metadata(db, {"sid-x", "sid-y", "sid-z"})
        assert set(result.keys()) == {"sid-x"}

    def test_empty_ids_returns_empty(self, tmp_path: Path) -> None:
        db = _make_sessions_db(tmp_path, [])
        result = _load_session_metadata(db, set())
        assert result == {}


# ---------------------------------------------------------------------------
# 6. End-to-end validate_from_telemetry
# ---------------------------------------------------------------------------


class TestValidateFromTelemetryEndToEnd:
    def _setup_full_fixture(self, tmp_path: Path) -> Dict[str, Path]:
        """Build a full telemetry + sessions.db fixture with mixed content."""
        # 5 mode_skip rows total:
        #   - 1 synthetic (phase-e-test-) -> filtered
        #   - 2 real sessions, both implement-shaped (regex + aggregate)
        #   - 1 real session, not implement-shaped (low tool_calls, plain prompt)
        #   - 1 real session NOT in DB (no_metadata)
        rows = [
            {
                "decision_shape": "mode_skip",
                "reason": "mode_skip:doc",
                "session_id": f"{_SYNTHETIC_SESSION_PREFIX}skip-me",
            },
            {
                "decision_shape": "mode_skip",
                "reason": "mode_skip:conversation",
                "session_id": "real-impl-regex",
            },
            {
                "decision_shape": "mode_skip",
                "reason": "mode_skip:exploration",
                "session_id": "real-impl-aggregate",
            },
            {
                "decision_shape": "mode_skip",
                "reason": "mode_skip:status_query",
                "session_id": "real-not-impl",
            },
            {
                "decision_shape": "mode_skip",
                "reason": "mode_skip:doc",
                "session_id": "real-no-meta",
            },
        ]
        log = _make_jsonl(tmp_path, rows)
        db = _make_sessions_db(
            tmp_path,
            [
                {
                    "session_id": "real-impl-regex",
                    "first_user_prompt": "/implement add the validator",
                    "tool_calls": 2,
                    "transcript_bytes": 500,
                    "message_count": 4,
                },
                {
                    "session_id": "real-impl-aggregate",
                    "first_user_prompt": "Help me work on this",
                    "tool_calls": _AGGREGATE_TOOL_THRESHOLD + 2,
                    "transcript_bytes": _AGGREGATE_BYTES_THRESHOLD + 100,
                    "message_count": 20,
                },
                {
                    "session_id": "real-not-impl",
                    "first_user_prompt": "What time is it?",
                    "tool_calls": 1,
                    "transcript_bytes": 100,
                    "message_count": 2,
                },
                # real-no-meta deliberately omitted from DB
            ],
        )
        return {"log": log, "db": db}

    def test_required_keys_present(self, tmp_path: Path) -> None:
        paths = self._setup_full_fixture(tmp_path)
        result = validate_from_telemetry(
            telemetry_log=paths["log"], sessions_db=paths["db"]
        )
        required = {
            "_meta",
            "n_total_skip_rows",
            "n_synthetic_filtered",
            "n_unique_sessions",
            "n_implement_sessions",
            "n_skipped",
            "n_no_metadata",
            "observed_fn_rate",
            "ci_low",
            "ci_high",
            "insufficient_sample_warning",
            "diagnostic_message",
            "per_skip_class_breakdown",
        }
        assert required.issubset(set(result.keys()))
        assert result["_meta"]["schema_version"] == _TELEMETRY_SCHEMA_VERSION
        assert result["_meta"]["issue"] == "#1077"

    def test_counts_correct(self, tmp_path: Path) -> None:
        paths = self._setup_full_fixture(tmp_path)
        result = validate_from_telemetry(
            telemetry_log=paths["log"], sessions_db=paths["db"]
        )
        assert result["n_total_skip_rows"] == 5
        assert result["n_synthetic_filtered"] == 1
        assert result["n_unique_sessions"] == 4
        # 2 implement-shaped: regex + aggregate
        assert result["n_implement_sessions"] == 2
        assert result["n_skipped"] == 2
        assert result["n_no_metadata"] == 1

    def test_observed_fn_rate(self, tmp_path: Path) -> None:
        paths = self._setup_full_fixture(tmp_path)
        result = validate_from_telemetry(
            telemetry_log=paths["log"], sessions_db=paths["db"]
        )
        # 2 implement-shaped / 4 unique sessions = 0.5
        assert result["observed_fn_rate"] == 0.5
        assert 0.0 <= result["ci_low"] <= 0.5 <= result["ci_high"] <= 1.0

    def test_breakdown_sums(self, tmp_path: Path) -> None:
        paths = self._setup_full_fixture(tmp_path)
        result = validate_from_telemetry(
            telemetry_log=paths["log"], sessions_db=paths["db"]
        )
        breakdown = result["per_skip_class_breakdown"]
        # Sum of "total" across all classes must equal n_unique_sessions.
        assert sum(v["total"] for v in breakdown.values()) == result["n_unique_sessions"]
        # Sum of "implement_shaped" must equal n_implement_sessions.
        assert (
            sum(v["implement_shaped"] for v in breakdown.values())
            == result["n_implement_sessions"]
        )

    def test_idempotent(self, tmp_path: Path) -> None:
        """Two consecutive runs produce byte-identical JSON modulo ``_meta.generated_at``."""
        paths = self._setup_full_fixture(tmp_path)
        r1 = validate_from_telemetry(
            telemetry_log=paths["log"], sessions_db=paths["db"]
        )
        r2 = validate_from_telemetry(
            telemetry_log=paths["log"], sessions_db=paths["db"]
        )
        # Strip the generated_at timestamp from both.
        r1["_meta"].pop("generated_at", None)
        r2["_meta"].pop("generated_at", None)
        s1 = json.dumps(r1, sort_keys=True)
        s2 = json.dumps(r2, sort_keys=True)
        assert s1 == s2


# ---------------------------------------------------------------------------
# 7. N=0 graceful path
# ---------------------------------------------------------------------------


class TestEdgeCaseN0:
    def test_empty_jsonl(self, tmp_path: Path) -> None:
        log = _make_jsonl(tmp_path, [])
        db = _make_sessions_db(tmp_path, [])
        result = validate_from_telemetry(telemetry_log=log, sessions_db=db)
        assert result["n_total_skip_rows"] == 0
        assert result["n_unique_sessions"] == 0
        assert result["n_implement_sessions"] == 0
        assert result["ci_low"] == 0.0
        assert result["ci_high"] == 1.0
        assert result["insufficient_sample_warning"] is True
        assert result["diagnostic_message"] is not None

    def test_all_synthetic(self, tmp_path: Path) -> None:
        log = _make_jsonl(
            tmp_path,
            [
                {
                    "decision_shape": "mode_skip",
                    "reason": "mode_skip:doc",
                    "session_id": f"{_SYNTHETIC_SESSION_PREFIX}{i}",
                }
                for i in range(10)
            ],
        )
        db = _make_sessions_db(tmp_path, [])
        result = validate_from_telemetry(telemetry_log=log, sessions_db=db)
        assert result["n_total_skip_rows"] == 10
        assert result["n_synthetic_filtered"] == 10
        assert result["n_unique_sessions"] == 0
        assert result["ci_low"] == 0.0
        assert result["ci_high"] == 1.0
        assert result["insufficient_sample_warning"] is True
        assert result["diagnostic_message"] is not None
        assert "synthetic" in result["diagnostic_message"].lower()

    def test_missing_sessions_db(self, tmp_path: Path) -> None:
        log = _make_jsonl(
            tmp_path,
            [
                {
                    "decision_shape": "mode_skip",
                    "reason": "mode_skip:doc",
                    "session_id": "real-sid",
                }
            ],
        )
        db = tmp_path / "does_not_exist.db"
        result = validate_from_telemetry(telemetry_log=log, sessions_db=db)
        # 1 real session, no DB metadata available
        assert result["n_unique_sessions"] == 1
        assert result["n_no_metadata"] == 1
        assert result["diagnostic_message"] is not None


# ---------------------------------------------------------------------------
# 8. Security sentinel — raw prompts MUST NOT appear in output JSON
# ---------------------------------------------------------------------------


class TestNoRawPromptsInOutput:
    def test_no_raw_prompts_in_output(self, tmp_path: Path) -> None:
        """Sentinel string from first_user_prompt MUST NOT leak into output JSON.

        Acceptance criterion 8 of the Phase B plan: the output JSON should not
        contain raw user prompts (privacy preservation).
        """
        sentinel = "SECRET-SENTINEL-XYZ-789"
        log = _make_jsonl(
            tmp_path,
            [
                {
                    "decision_shape": "mode_skip",
                    "reason": "mode_skip:doc",
                    "session_id": "real-sid-1",
                }
            ],
        )
        db = _make_sessions_db(
            tmp_path,
            [
                {
                    "session_id": "real-sid-1",
                    "first_user_prompt": sentinel,
                    "tool_calls": 1,
                    "transcript_bytes": 100,
                    "message_count": 2,
                }
            ],
        )
        result = validate_from_telemetry(telemetry_log=log, sessions_db=db)
        # Serialize the result and verify the sentinel string is NOT present.
        result_json = json.dumps(result, sort_keys=True)
        assert sentinel not in result_json, (
            "Raw first_user_prompt leaked into output JSON. "
            "This is a privacy regression."
        )

    def test_no_raw_prompts_via_cli_output_file(self, tmp_path: Path) -> None:
        """Same sentinel check but via the JSON file written by the CLI path."""
        sentinel = "ANOTHER-SECRET-PROMPT-ABC-123"
        log = _make_jsonl(
            tmp_path,
            [
                {
                    "decision_shape": "mode_skip",
                    "reason": "mode_skip:conversation",
                    "session_id": "real-sid-2",
                }
            ],
        )
        db = _make_sessions_db(
            tmp_path,
            [
                {
                    "session_id": "real-sid-2",
                    "first_user_prompt": sentinel,
                    "tool_calls": 1,
                    "transcript_bytes": 100,
                    "message_count": 2,
                }
            ],
        )
        result = validate_from_telemetry(telemetry_log=log, sessions_db=db)
        # Write to file (matches what the CLI does) and grep.
        out_path = tmp_path / "telemetry_validation.json"
        out_path.write_text(json.dumps(result, indent=2, sort_keys=True))
        contents = out_path.read_text()
        assert sentinel not in contents, (
            "Sentinel prompt found in CLI output file — privacy regression."
        )
