"""Unit tests for extract_and_label_intent_corpus.py.

Tests PII scrubbing, dedup, length filtering, two-judge agreement logic,
and cost cap enforcement. All LLM calls are mocked.

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
    filter_and_dedup,
    label_prompts_with_two_judges,
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
# Two-judge agreement logic tests (mocked LLM)
# ---------------------------------------------------------------------------


def _make_judge_result(intent: str, confidence: float = 0.9) -> Dict[str, Any]:
    return {"intent": intent, "confidence": confidence}


def test_both_judges_agree_writes_entry() -> None:
    """When both judges agree, the entry is added to agreed list."""
    prompts = ["implement pagination for the user list endpoint"]
    tracker = CostTracker()

    with (
        patch(
            "extract_and_label_intent_corpus._call_anthropic_judge",
            return_value=_make_judge_result("implement"),
        ),
        patch(
            "extract_and_label_intent_corpus._call_openrouter_judge",
            return_value=_make_judge_result("implement"),
        ),
    ):
        agreed, disagreements = label_prompts_with_two_judges(
            prompts,
            judge_a_model="claude-haiku",
            judge_b_model="openai/gpt-4o-mini",
            anthropic_api_key="test-key",
            openrouter_api_key="test-key",
            cost_tracker=tracker,
        )

    assert len(agreed) == 1
    assert agreed[0]["label"] == "implement"
    assert agreed[0]["source"] == "sqlite"


def test_judges_disagree_drops_entry() -> None:
    """When judges disagree, the entry is dropped and counted in disagreements."""
    prompts = ["update the README with new flags"]
    tracker = CostTracker()

    with (
        patch(
            "extract_and_label_intent_corpus._call_anthropic_judge",
            return_value=_make_judge_result("doc"),
        ),
        patch(
            "extract_and_label_intent_corpus._call_openrouter_judge",
            return_value=_make_judge_result("implement"),
        ),
    ):
        agreed, disagreements = label_prompts_with_two_judges(
            prompts,
            judge_a_model="claude-haiku",
            judge_b_model="openai/gpt-4o-mini",
            anthropic_api_key="test-key",
            openrouter_api_key="test-key",
            cost_tracker=tracker,
        )

    assert len(agreed) == 0
    assert any("doc->implement" in k or "implement->doc" in k for k in disagreements)


def test_judge_low_confidence_drops_entry() -> None:
    """Entry is dropped when judge confidence is below threshold (0.70)."""
    prompts = ["implement something"]
    tracker = CostTracker()

    with (
        patch(
            "extract_and_label_intent_corpus._call_anthropic_judge",
            return_value=_make_judge_result("implement", confidence=0.50),  # below 0.70
        ),
        patch(
            "extract_and_label_intent_corpus._call_openrouter_judge",
            return_value=_make_judge_result("implement", confidence=0.90),
        ),
    ):
        agreed, disagreements = label_prompts_with_two_judges(
            prompts,
            judge_a_model="claude-haiku",
            judge_b_model="openai/gpt-4o-mini",
            anthropic_api_key="test-key",
            openrouter_api_key="test-key",
            cost_tracker=tracker,
        )

    assert len(agreed) == 0


def test_judge_returns_invalid_intent_drops_entry() -> None:
    """Entry is dropped when judge returns an invalid intent class."""
    prompts = ["implement something"]
    tracker = CostTracker()

    with (
        patch(
            "extract_and_label_intent_corpus._call_anthropic_judge",
            return_value=None,  # invalid/failure
        ),
        patch(
            "extract_and_label_intent_corpus._call_openrouter_judge",
            return_value=_make_judge_result("implement"),
        ),
    ):
        agreed, disagreements = label_prompts_with_two_judges(
            prompts,
            judge_a_model="claude-haiku",
            judge_b_model="openai/gpt-4o-mini",
            anthropic_api_key="test-key",
            openrouter_api_key="test-key",
            cost_tracker=tracker,
        )

    assert len(agreed) == 0


# ---------------------------------------------------------------------------
# Cost cap tests
# ---------------------------------------------------------------------------


def test_cost_cap_enforced_stops_labeling() -> None:
    """When cost cap would be exceeded, labeling stops early."""
    # Set cap very low so it's exceeded immediately after first prompt
    tracker = CostTracker(cap_usd=0.001, cost_per_call_usd=0.005)
    prompts = ["prompt one", "prompt two", "prompt three"]

    # Tracker's would_exceed_cap should return True before any calls
    assert tracker.would_exceed_cap(additional_calls=2)

    with (
        patch("extract_and_label_intent_corpus._call_anthropic_judge") as mock_a,
        patch("extract_and_label_intent_corpus._call_openrouter_judge") as mock_b,
    ):
        agreed, _ = label_prompts_with_two_judges(
            prompts,
            judge_a_model="claude-haiku",
            judge_b_model="openai/gpt-4o-mini",
            anthropic_api_key="test-key",
            openrouter_api_key="test-key",
            cost_tracker=tracker,
        )

    # No calls should have been made since cap was already exceeded
    mock_a.assert_not_called()
    mock_b.assert_not_called()
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
