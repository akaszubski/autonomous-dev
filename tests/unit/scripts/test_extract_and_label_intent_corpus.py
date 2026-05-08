"""Unit tests for extract_and_label_intent_corpus.py.

Tests PII scrubbing, dedup, length filtering, single-judge labeling logic
(via ``claude -p`` subprocess wrapper), and cost cap enforcement. All
subprocess calls are mocked.

GitHub Issue: #1043
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

# Add scripts directory to path
sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[3] / "scripts"),
)

from extract_and_label_intent_corpus import (
    CostTracker,
    VALID_INTENT_CLASSES,
    _build_synthetic_fallback_corpus,
    _RE_AWS_ACCOUNT,
    _RE_BASE64,
    _RE_EMAIL,
    _RE_INTERNAL_IP,
    _RE_JWT,
    _RE_LOCAL_CAVEAT,
    _RE_PHONE,
    _RE_RFC1918_IP,
    _RE_SSH_USER_AT_HOST,
    _RE_UUID,
    _call_claude_p_judge,
    filter_and_dedup,
    label_prompts_with_single_judge,
    scrub_pii,
)


# ---------------------------------------------------------------------------
# PII scrubbing tests — parametrized over 10 pattern types
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pattern_name, raw_text, expected_redaction",
    [
        # 1. Email address
        (
            "email",
            "contact me at user@example.com for help",
            "email",
        ),
        # 2. SSH user@host (IP address host)
        (
            "ssh_user_at_host",
            "ssh andrewkaszubski@10.55.0.2 to check disk",
            "ssh_user_at_host",
        ),
        # 3. Phone number (10-digit US format)
        (
            "phone",
            "call me at 555-867-5309 anytime",
            "phone",
        ),
        # 4. UUID
        (
            "uuid",
            "session id is 550e8400-e29b-41d4-a716-446655440000",
            "uuid",
        ),
        # 5. AWS account ID (12 digits)
        (
            "aws_account",
            "account 123456789012 needs the permission",
            "aws_account",
        ),
        # 6. JWT token
        (
            "jwt",
            "token: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
            "jwt",
        ),
        # 7. Base64 blob >40 chars
        (
            "base64",
            "encoded: dGhpcyBpcyBhIGxvbmcgYmFzZTY0IGVuY29kZWQgc3RyaW5nIHRoYXQgZXhjZWVkcw==",
            "base64",
        ),
        # 8. <local-command-caveat> block
        (
            "local_caveat",
            "some text <local-command-caveat>internal caveat goes here</local-command-caveat> more text",
            "local-command-caveat",
        ),
        # 9. Mac Studio internal IP
        (
            "internal_ip",
            "server at 10.55.1.42 is unreachable",
            "internal_ip",
        ),
        # 10. RFC1918 private IP (192.168.x.x)
        (
            "rfc1918_ip",
            "router at 192.168.1.1 needs config",
            "rfc1918_ip",
        ),
    ],
)
def test_pii_scrubbing_parametrized(
    pattern_name: str, raw_text: str, expected_redaction: str
) -> None:
    """PII scrubbing removes expected patterns and records redaction type."""
    scrubbed, redactions = scrub_pii(raw_text)
    assert expected_redaction in redactions, (
        f"Expected redaction type {expected_redaction!r} not found in {redactions}"
    )
    # The redacted marker should appear in the scrubbed text (or the original text
    # must differ from scrubbed)
    assert scrubbed != raw_text, (
        f"scrub_pii did not modify the text for pattern {pattern_name!r}"
    )


def test_pii_scrubbing_clean_text_unchanged() -> None:
    """Clean text with no PII passes through unmodified with empty redactions."""
    clean = "implement pagination for the user list endpoint"
    scrubbed, redactions = scrub_pii(clean)
    assert scrubbed == clean
    assert redactions == []


def test_pii_scrubbing_multiple_patterns_in_one_prompt() -> None:
    """Multiple PII patterns in one prompt are all redacted."""
    text = "email user@example.com via 555-123-4567 using token eyJhbGciOiJIUzI1NiJ9.ey.sig"
    scrubbed, redactions = scrub_pii(text)
    assert "email" in redactions
    assert "phone" in redactions
    assert "jwt" in redactions
    # Verify none of the original sensitive strings remain
    assert "user@example.com" not in scrubbed
    assert "555-123-4567" not in scrubbed
    assert "eyJhbGciOiJIUzI1NiJ9" not in scrubbed


def test_local_caveat_block_stripped_entirely() -> None:
    """<local-command-caveat> blocks are stripped entirely, not just replaced."""
    text = "prefix <local-command-caveat>This should disappear completely</local-command-caveat> suffix"
    scrubbed, redactions = scrub_pii(text)
    assert "local-command-caveat" in redactions
    assert "<local-command-caveat>" not in scrubbed
    assert "This should disappear" not in scrubbed
    assert "prefix" in scrubbed
    assert "suffix" in scrubbed


# ---------------------------------------------------------------------------
# Dedup and length filter tests
# ---------------------------------------------------------------------------


def test_dedup_removes_exact_duplicates() -> None:
    """Exact duplicate prompts are collapsed to one."""
    prompts = [
        "implement pagination for users",
        "implement pagination for users",  # duplicate
        "add CSV export feature",
    ]
    result = filter_and_dedup(prompts)
    assert len(result) == 2


def test_dedup_removes_case_insensitive_near_duplicates() -> None:
    """Case-insensitive near-duplicates are collapsed."""
    prompts = [
        "Implement Pagination For Users",
        "implement pagination for users",  # same when lowercased
    ]
    result = filter_and_dedup(prompts)
    assert len(result) == 1


def test_length_filter_rejects_too_short() -> None:
    """Prompts below MIN_PROMPT_LEN (10) are filtered out."""
    prompts = [
        "hi",  # too short
        "ok do it",  # borderline short
        "implement pagination for the user list endpoint",  # OK
    ]
    result = filter_and_dedup(prompts)
    # Only the long enough prompt should pass
    assert all(len(p) >= 10 for p in result)


def test_length_filter_rejects_too_long() -> None:
    """Prompts above MAX_PROMPT_LEN (2000) are filtered out."""
    long_prompt = "a" * 2001
    short_prompt = "implement pagination for users"
    result = filter_and_dedup([long_prompt, short_prompt])
    assert len(result) == 1
    assert result[0] == short_prompt


# ---------------------------------------------------------------------------
# Single-judge labeling tests (mocked subprocess)
# ---------------------------------------------------------------------------


def _make_judge_result(intent: str, confidence: float = 0.9) -> Dict[str, Any]:
    return {"intent": intent, "confidence": confidence}


def test_judge_returns_valid_intent_writes_entry() -> None:
    """When the judge returns a valid intent above threshold, the entry is added."""
    prompts = ["implement pagination for the user list endpoint"]
    tracker = CostTracker()

    with patch(
        "extract_and_label_intent_corpus._call_claude_p_judge",
        return_value=_make_judge_result("implement"),
    ):
        agreed, drops = label_prompts_with_single_judge(
            prompts,
            judge_model="claude-haiku-4-5-20251001",
            cost_tracker=tracker,
        )

    assert len(agreed) == 1
    assert agreed[0]["label"] == "implement"
    assert agreed[0]["source"] == "sqlite"
    assert agreed[0]["judge"] == "claude-haiku-4-5-20251001"
    # Schema check: legacy fields must NOT exist on entries
    assert "judge_a" not in agreed[0]
    assert "judge_b" not in agreed[0]


def test_judge_low_confidence_drops_entry() -> None:
    """Entry is dropped when judge confidence is below threshold (0.70)."""
    prompts = ["implement something"]
    tracker = CostTracker()

    with patch(
        "extract_and_label_intent_corpus._call_claude_p_judge",
        return_value=_make_judge_result("implement", confidence=0.50),  # below 0.70
    ):
        agreed, drops = label_prompts_with_single_judge(
            prompts,
            judge_model="claude-haiku-4-5-20251001",
            cost_tracker=tracker,
        )

    assert len(agreed) == 0
    assert drops.get("low_confidence", 0) == 1


def test_judge_returns_invalid_intent_drops_entry() -> None:
    """Entry is dropped when judge returns None (failure / invalid intent)."""
    prompts = ["implement something"]
    tracker = CostTracker()

    with patch(
        "extract_and_label_intent_corpus._call_claude_p_judge",
        return_value=None,  # subprocess error / parse failure / invalid intent
    ):
        agreed, drops = label_prompts_with_single_judge(
            prompts,
            judge_model="claude-haiku-4-5-20251001",
            cost_tracker=tracker,
        )

    assert len(agreed) == 0
    assert drops.get("judge_failure", 0) == 1


# ---------------------------------------------------------------------------
# Cost cap tests
# ---------------------------------------------------------------------------


def test_cost_cap_enforced_stops_labeling() -> None:
    """When cost cap would be exceeded, labeling stops early."""
    # Set cap very low so it's exceeded immediately after first prompt
    tracker = CostTracker(cap_usd=0.001, cost_per_call_usd=0.005)
    prompts = ["prompt one", "prompt two", "prompt three"]

    # Tracker's would_exceed_cap should return True before any calls
    # (single-judge mode plans 1 additional call per prompt)
    assert tracker.would_exceed_cap(additional_calls=1)

    with patch("extract_and_label_intent_corpus._call_claude_p_judge") as mock_judge:
        agreed, _ = label_prompts_with_single_judge(
            prompts,
            judge_model="claude-haiku-4-5-20251001",
            cost_tracker=tracker,
        )

    # No calls should have been made since cap was already exceeded
    mock_judge.assert_not_called()
    assert len(agreed) == 0


def test_cost_tracker_records_calls() -> None:
    """CostTracker accumulates call counts and estimated cost correctly."""
    tracker = CostTracker(cap_usd=1.0, cost_per_call_usd=0.01)
    assert not tracker.would_exceed_cap(additional_calls=2)
    tracker.record_calls(2)
    assert tracker.total_calls == 2
    assert abs(tracker.estimated_cost_usd - 0.02) < 1e-9


def test_cost_cap_at_limit() -> None:
    """would_exceed_cap is True when projected cost exceeds cap."""
    tracker = CostTracker(cap_usd=0.10, cost_per_call_usd=0.04)
    tracker.record_calls(2)  # $0.08 spent
    # Two more calls = $0.08 projected, total $0.16 > $0.10 cap
    assert tracker.would_exceed_cap(additional_calls=2)


# ---------------------------------------------------------------------------
# Synthetic fallback corpus tests
# ---------------------------------------------------------------------------


def test_synthetic_fallback_corpus_has_all_13_classes() -> None:
    """Synthetic fallback corpus covers all 13 intent classes."""
    entries = _build_synthetic_fallback_corpus()
    labels = {e["label"] for e in entries}
    expected_classes = {
        "security_critical", "implement", "refactor", "test", "doc",
        "config", "typo", "status_query", "conversation", "exploration",
        "triage", "remote_ops", "scratch",
    }
    missing = expected_classes - labels
    assert not missing, f"Missing classes in synthetic fallback: {missing}"


def test_synthetic_fallback_corpus_minimum_size() -> None:
    """Synthetic fallback corpus has at least 100 entries."""
    entries = _build_synthetic_fallback_corpus()
    assert len(entries) >= 100, f"Only {len(entries)} entries in synthetic fallback"


def test_synthetic_fallback_entries_use_judge_field() -> None:
    """Synthetic-fallback entries use the single ``judge`` field, not judge_a/b."""
    entries = _build_synthetic_fallback_corpus()
    assert entries, "Synthetic fallback returned no entries"
    for entry in entries:
        assert entry.get("judge") == "synthetic-fallback", (
            f"Entry {entry.get('id')!r} has unexpected judge field: {entry.get('judge')!r}"
        )
        assert "judge_a" not in entry, (
            f"Entry {entry.get('id')!r} still has legacy judge_a field"
        )
        assert "judge_b" not in entry, (
            f"Entry {entry.get('id')!r} still has legacy judge_b field"
        )


# ---------------------------------------------------------------------------
# `_call_claude_p_judge` envelope and subprocess behavior tests
# ---------------------------------------------------------------------------


def _make_envelope(intent: str = "implement", confidence: float = 0.92) -> str:
    """Build the JSON envelope claude -p emits with `--output-format json`."""
    inner = json.dumps({"intent": intent, "confidence": confidence})
    return json.dumps(
        {
            "subtype": "success",
            "is_error": False,
            "result": inner,
        }
    )


def test_call_claude_p_judge_handles_missing_cli() -> None:
    """When `claude` CLI is absent, subprocess.run raises FileNotFoundError -> None."""
    with patch(
        "extract_and_label_intent_corpus.subprocess.run",
        side_effect=FileNotFoundError("claude not on PATH"),
    ):
        result = _call_claude_p_judge(
            "implement pagination", model="claude-haiku-4-5-20251001"
        )
    assert result is None


def test_call_claude_p_judge_handles_timeout() -> None:
    """When subprocess.run times out, the helper returns None."""
    import subprocess as _subprocess

    with patch(
        "extract_and_label_intent_corpus.subprocess.run",
        side_effect=_subprocess.TimeoutExpired(cmd=["claude"], timeout=60),
    ):
        result = _call_claude_p_judge(
            "implement pagination", model="claude-haiku-4-5-20251001"
        )
    assert result is None


def test_call_claude_p_judge_parses_envelope() -> None:
    """A well-formed claude -p JSON envelope yields a parsed intent + confidence."""
    fake = MagicMock()
    fake.returncode = 0
    fake.stdout = _make_envelope(intent="doc", confidence=0.88)
    fake.stderr = ""

    with patch(
        "extract_and_label_intent_corpus.subprocess.run",
        return_value=fake,
    ) as mock_run:
        result = _call_claude_p_judge(
            "Update the README with new flags",
            model="claude-haiku-4-5-20251001",
        )

    assert result == {"intent": "doc", "confidence": 0.88}
    # Validate the subprocess invocation shape
    args, kwargs = mock_run.call_args
    cmd = args[0]
    assert cmd[0] == "claude"
    assert cmd[1] == "-p"
    assert "--output-format" in cmd
    assert "json" in cmd
    assert "--model" in cmd
    assert "claude-haiku-4-5-20251001" in cmd
    assert "--max-turns" in cmd
    assert "1" in cmd
    assert "--system-prompt" in cmd
    assert kwargs.get("capture_output") is True
    assert kwargs.get("text") is True
    assert "input" in kwargs


def test_call_claude_p_judge_rejects_invalid_intent_in_envelope() -> None:
    """When the envelope's inner result contains an unknown intent, return None."""
    fake = MagicMock()
    fake.returncode = 0
    inner = json.dumps({"intent": "not_a_real_class", "confidence": 0.95})
    fake.stdout = json.dumps(
        {"subtype": "success", "is_error": False, "result": inner}
    )

    with patch(
        "extract_and_label_intent_corpus.subprocess.run",
        return_value=fake,
    ):
        result = _call_claude_p_judge(
            "investigate session lifecycle",
            model="claude-haiku-4-5-20251001",
        )

    assert result is None


def test_call_claude_p_judge_rejects_error_envelope() -> None:
    """When `is_error=True` or `subtype != success`, helper returns None."""
    fake = MagicMock()
    fake.returncode = 0
    fake.stdout = json.dumps(
        {"subtype": "error", "is_error": True, "result": None}
    )

    with patch(
        "extract_and_label_intent_corpus.subprocess.run",
        return_value=fake,
    ):
        result = _call_claude_p_judge(
            "any prompt", model="claude-haiku-4-5-20251001"
        )

    assert result is None


def test_call_claude_p_judge_rejects_nonzero_exit() -> None:
    """A non-zero subprocess returncode yields None."""
    fake = MagicMock()
    fake.returncode = 1
    fake.stdout = ""
    fake.stderr = "boom"

    with patch(
        "extract_and_label_intent_corpus.subprocess.run",
        return_value=fake,
    ):
        result = _call_claude_p_judge(
            "any prompt", model="claude-haiku-4-5-20251001"
        )

    assert result is None


def test_call_claude_p_judge_rejects_confidence_out_of_range() -> None:
    """Confidence outside [0.0, 1.0] returns None (defense in depth)."""
    fake = MagicMock()
    fake.returncode = 0
    inner = json.dumps({"intent": "implement", "confidence": 1.5})
    fake.stdout = json.dumps(
        {"subtype": "success", "is_error": False, "result": inner}
    )

    with patch(
        "extract_and_label_intent_corpus.subprocess.run",
        return_value=fake,
    ):
        result = _call_claude_p_judge(
            "any prompt", model="claude-haiku-4-5-20251001"
        )

    assert result is None


def test_call_claude_p_judge_passes_cwd_to_avoid_project_context(monkeypatch) -> None:
    """Regression test for #1064: must pass cwd= to subprocess.run so the
    spawned ``claude -p`` session does not inherit the parent's CWD and load
    this project's CLAUDE.md + hooks (which causes ``prompt_too_long``).

    Without ``cwd=``, the subprocess inherits the parent's current working
    directory. When the corpus extractor runs from inside the autonomous-dev
    repo, the spawned ``claude -p`` session loads the project's CLAUDE.md,
    auto-memory, hooks, and skills — pushing the cumulative system prompt
    over the API limit and causing every label call to fail with
    ``terminal_reason: "prompt_too_long"``. Pinning ``cwd`` to a neutral
    directory (``Path.home()``) prevents that context bleed.
    """
    import subprocess as _subprocess

    captured_kwargs: Dict[str, Any] = {}
    fake_envelope = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": '{"intent": "implement", "confidence": 0.9}',
    }

    def fake_run(cmd, **kwargs):
        captured_kwargs.update(kwargs)
        return _subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=json.dumps(fake_envelope),
            stderr="",
        )

    monkeypatch.setattr(
        "extract_and_label_intent_corpus.subprocess.run", fake_run
    )

    out = _call_claude_p_judge(
        "classify this", model="claude-haiku-4-5-20251001"
    )

    assert out == {"intent": "implement", "confidence": 0.9}
    assert "cwd" in captured_kwargs, (
        "subprocess.run must receive cwd= to prevent #1064 project-context bleed"
    )
    assert captured_kwargs["cwd"] == str(Path.home()), (
        f"cwd must be Path.home() (got {captured_kwargs['cwd']!r}) — #1064"
    )
