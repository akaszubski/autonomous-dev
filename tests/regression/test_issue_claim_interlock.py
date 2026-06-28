"""Regression tests for cross-machine issue claim interlock (issue_claim.py).

All tests mock subprocess.run / _gh_run — NO live gh calls.

Covers race fix observed 2026-06-28 where local /implement --issues and
cloud-drain /drain-queue raced on the same cluster.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_PATH = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_PATH) not in sys.path:
    sys.path.insert(0, str(LIB_PATH))

import issue_claim  # noqa: E402
from issue_claim import (  # noqa: E402
    CLAIM_LABEL,
    _actor_string,
    _format_claim_comment,
    _format_release_comment,
    _parse_claim_comment,
    claim_issue,
    is_claimed,
    release_issue,
)


def _completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    """Build a CompletedProcess with the given fields (cmd irrelevant for tests)."""
    return subprocess.CompletedProcess(
        args=["gh", "stub"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _gh_issue_view_payload(
    *,
    has_label: bool = True,
    comments: list | None = None,
) -> str:
    """Build a JSON payload mimicking `gh issue view --json labels,comments`."""
    labels = [{"name": CLAIM_LABEL}] if has_label else []
    return json.dumps({"labels": labels, "comments": comments or []})


# -----------------------------------------------------------------------
# 1. _actor_string format
# -----------------------------------------------------------------------
class TestActorString:
    def test_actor_string_uses_supplied_host_and_pid(self):
        result = _actor_string("run-42", host="myhost", pid=1234)
        assert result == "myhost:1234:run-42"

    def test_actor_string_defaults_to_real_host_and_pid(self):
        result = _actor_string("run-x")
        parts = result.split(":")
        assert len(parts) == 3
        assert parts[2] == "run-x"
        assert parts[1].isdigit()
        assert parts[0]  # non-empty hostname


# -----------------------------------------------------------------------
# 2. _format_claim_comment + _parse_claim_comment roundtrip
# -----------------------------------------------------------------------
class TestFormatParseRoundtrip:
    def test_claim_comment_roundtrip_preserves_fields(self):
        ts = "2026-06-28T12:34:56+00:00"
        actor = "host123:9999:run-abc"
        body = _format_claim_comment(456, actor, ts=ts)
        parsed = _parse_claim_comment(body)
        assert parsed is not None
        assert parsed["issue"] == 456
        assert parsed["host"] == "host123"
        assert parsed["pid"] == 9999
        assert parsed["ts"] == datetime(2026, 6, 28, 12, 34, 56, tzinfo=timezone.utc)


# -----------------------------------------------------------------------
# 3. _parse_claim_comment rejects non-claim text and release markers
# -----------------------------------------------------------------------
class TestParseRejection:
    def test_parse_rejects_empty(self):
        assert _parse_claim_comment("") is None

    def test_parse_rejects_arbitrary_text(self):
        assert _parse_claim_comment("Just a normal comment") is None

    def test_parse_rejects_release_marker(self):
        body = _format_release_comment(7, "host:1:run-z", "completed")
        assert _parse_claim_comment(body) is None

    def test_parse_rejects_malformed_timestamp(self):
        bad = "🤖 Implementing #5 now [host=h, pid=2, ts=not-a-date]\n\nActor: h:2:x"
        assert _parse_claim_comment(bad) is None


# -----------------------------------------------------------------------
# 4. is_claimed returns False when label absent
# -----------------------------------------------------------------------
class TestIsClaimedLabel:
    def test_is_claimed_false_when_label_absent(self):
        payload = _gh_issue_view_payload(has_label=False, comments=[])
        with patch.object(issue_claim, "_gh_run", return_value=_completed(0, payload)):
            held, info = is_claimed(123)
        assert held is False
        assert info is None


# -----------------------------------------------------------------------
# 5. is_claimed returns True for fresh claim from different actor
# -----------------------------------------------------------------------
class TestIsClaimedFresh:
    def test_is_claimed_true_for_fresh_claim_different_actor(self):
        now = datetime(2026, 6, 28, 15, 0, 0, tzinfo=timezone.utc)
        claim_ts = (now - timedelta(minutes=10)).isoformat()
        body = _format_claim_comment(99, "other-host:111:run-other", ts=claim_ts)
        payload = _gh_issue_view_payload(
            has_label=True,
            comments=[{"body": body, "createdAt": claim_ts}],
        )
        with patch.object(issue_claim, "_gh_run", return_value=_completed(0, payload)):
            held, info = is_claimed(99, actor="myhost:222:run-me", now=now)
        assert held is True
        assert info is not None
        assert info["host"] == "other-host"
        assert info["pid"] == 111
        assert info["actor"] == "other-host:111"
        assert info["age_seconds"] == 600


# -----------------------------------------------------------------------
# 6. is_claimed returns False for self-actor
# -----------------------------------------------------------------------
class TestIsClaimedSelf:
    def test_is_claimed_false_for_self_actor(self):
        now = datetime(2026, 6, 28, 15, 0, 0, tzinfo=timezone.utc)
        claim_ts = (now - timedelta(minutes=5)).isoformat()
        body = _format_claim_comment(50, "myhost:333:run-me", ts=claim_ts)
        payload = _gh_issue_view_payload(
            has_label=True, comments=[{"body": body, "createdAt": claim_ts}]
        )
        with patch.object(issue_claim, "_gh_run", return_value=_completed(0, payload)):
            held, info = is_claimed(50, actor="myhost:333:run-me", now=now)
        assert held is False
        assert info is None


# -----------------------------------------------------------------------
# 7. is_claimed returns False for stale claim (> 4h)
# -----------------------------------------------------------------------
class TestIsClaimedStale:
    def test_is_claimed_false_for_stale_claim(self):
        now = datetime(2026, 6, 28, 15, 0, 0, tzinfo=timezone.utc)
        claim_ts = (now - timedelta(hours=5)).isoformat()
        body = _format_claim_comment(77, "other-host:444:run-old", ts=claim_ts)
        payload = _gh_issue_view_payload(
            has_label=True, comments=[{"body": body, "createdAt": claim_ts}]
        )
        with patch.object(issue_claim, "_gh_run", return_value=_completed(0, payload)):
            held, info = is_claimed(77, actor="me:1:run-me", now=now)
        assert held is False
        assert info is None


# -----------------------------------------------------------------------
# 8. is_claimed returns False when release comment is newer than claim
# -----------------------------------------------------------------------
class TestIsClaimedReleased:
    def test_is_claimed_false_when_released_after_claim(self):
        now = datetime(2026, 6, 28, 15, 0, 0, tzinfo=timezone.utc)
        claim_ts = (now - timedelta(minutes=20)).isoformat()
        release_ts = (now - timedelta(minutes=10)).isoformat()
        claim_body = _format_claim_comment(88, "other:55:run-x", ts=claim_ts)
        release_body = _format_release_comment(88, "other:55:run-x", "completed", ts=release_ts)
        payload = _gh_issue_view_payload(
            has_label=True,
            comments=[
                {"body": claim_body, "createdAt": claim_ts},
                {"body": release_body, "createdAt": release_ts},
            ],
        )
        with patch.object(issue_claim, "_gh_run", return_value=_completed(0, payload)):
            held, info = is_claimed(88, actor="me:1:run-me", now=now)
        assert held is False
        assert info is None


# -----------------------------------------------------------------------
# 9. is_claimed returns False gracefully on gh timeout / non-zero exit
# -----------------------------------------------------------------------
class TestIsClaimedGhFailure:
    def test_is_claimed_false_on_gh_timeout_returncode(self):
        # _gh_run returns 124 on TimeoutExpired
        with patch.object(
            issue_claim, "_gh_run", return_value=_completed(124, "", "timeout")
        ):
            held, info = is_claimed(99)
        assert held is False
        assert info is None

    def test_is_claimed_false_on_gh_nonzero_exit(self):
        with patch.object(
            issue_claim, "_gh_run", return_value=_completed(1, "", "auth error")
        ):
            held, info = is_claimed(99)
        assert held is False
        assert info is None

    def test_is_claimed_false_on_invalid_json(self):
        with patch.object(
            issue_claim, "_gh_run", return_value=_completed(0, "not-json", "")
        ):
            held, info = is_claimed(99)
        assert held is False
        assert info is None


# -----------------------------------------------------------------------
# 10. claim_issue calls comment THEN edit --add-label (in order)
# -----------------------------------------------------------------------
class TestClaimIssueOrder:
    def test_claim_issue_calls_comment_then_label_in_order(self):
        calls: list[list[str]] = []

        def fake_gh(args, **kwargs):
            calls.append(list(args))
            return _completed(0)

        with patch.object(issue_claim, "_gh_run", side_effect=fake_gh):
            ok = claim_issue(42, "host:1:run-A")
        assert ok is True
        assert len(calls) == 2
        # First call: issue comment
        assert calls[0][0] == "issue"
        assert calls[0][1] == "comment"
        assert calls[0][2] == "42"
        # Second call: issue edit --add-label
        assert calls[1][0] == "issue"
        assert calls[1][1] == "edit"
        assert calls[1][2] == "42"
        assert "--add-label" in calls[1]
        assert CLAIM_LABEL in calls[1]

    def test_claim_issue_returns_false_on_comment_failure(self):
        with patch.object(issue_claim, "_gh_run", return_value=_completed(1, "", "err")):
            ok = claim_issue(42, "host:1:run-A")
        assert ok is False

    def test_claim_issue_returns_false_when_label_add_fails(self):
        # First call (comment) succeeds; second (edit) fails.
        results = [_completed(0), _completed(1, "", "label err")]

        def fake_gh(args, **kwargs):
            return results.pop(0)

        with patch.object(issue_claim, "_gh_run", side_effect=fake_gh):
            ok = claim_issue(42, "host:1:run-A")
        assert ok is False


# -----------------------------------------------------------------------
# 11. release_issue calls edit --remove-label THEN comment
# -----------------------------------------------------------------------
class TestReleaseIssueOrder:
    def test_release_issue_calls_label_remove_then_comment_in_order(self):
        calls: list[list[str]] = []

        def fake_gh(args, **kwargs):
            calls.append(list(args))
            return _completed(0)

        with patch.object(issue_claim, "_gh_run", side_effect=fake_gh):
            ok = release_issue(7, "host:1:run-A", reason="completed")
        assert ok is True
        assert len(calls) == 2
        # First: issue edit --remove-label
        assert calls[0][0] == "issue"
        assert calls[0][1] == "edit"
        assert calls[0][2] == "7"
        assert "--remove-label" in calls[0]
        assert CLAIM_LABEL in calls[0]
        # Second: issue comment
        assert calls[1][0] == "issue"
        assert calls[1][1] == "comment"
        assert calls[1][2] == "7"

    def test_release_issue_returns_false_if_either_fails(self):
        results = [_completed(0), _completed(1, "", "comment err")]

        def fake_gh(args, **kwargs):
            return results.pop(0)

        with patch.object(issue_claim, "_gh_run", side_effect=fake_gh):
            ok = release_issue(7, "host:1:run-A")
        assert ok is False


# -----------------------------------------------------------------------
# 12. cluster_selector._is_cluster_in_progress skips claimed clusters
# -----------------------------------------------------------------------
class TestClusterSelectorInProgress:
    def test_is_cluster_in_progress_returns_true_when_any_issue_claimed(
        self, monkeypatch
    ):
        import cluster_selector

        fake_info = {
            "host": "h",
            "pid": 1,
            "ts": "2026-06-28T12:00:00+00:00",
            "actor": "h:1",
            "age_seconds": 60,
        }

        # Patch the symbol the function actually uses (imported lazily inside func).
        def fake_is_claimed(num, **kwargs):
            return (num == 200, fake_info if num == 200 else None)

        monkeypatch.setattr(
            "issue_claim.is_claimed", fake_is_claimed
        )
        cluster = {"issue_numbers": [199, 200, 201]}
        result, reason = cluster_selector._is_cluster_in_progress(cluster)
        assert result is True
        assert "issue_claimed_by:h:1" in reason

    def test_is_cluster_in_progress_returns_false_when_no_issues_claimed(
        self, monkeypatch
    ):
        import cluster_selector

        def fake_is_claimed(num, **kwargs):
            return (False, None)

        monkeypatch.setattr("issue_claim.is_claimed", fake_is_claimed)
        cluster = {"issue_numbers": [1, 2, 3]}
        result, reason = cluster_selector._is_cluster_in_progress(cluster)
        assert result is False
        assert reason == ""

    def test_is_cluster_in_progress_handles_empty_issue_numbers(self):
        import cluster_selector

        cluster = {"issue_numbers": []}
        result, reason = cluster_selector._is_cluster_in_progress(cluster)
        assert result is False
        assert reason == ""
