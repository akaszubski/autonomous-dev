"""Tests for daily_aggregate_manager.py."""

import json
import pytest
from datetime import date
from subprocess import CompletedProcess
from pathlib import Path
import sys

# Add lib to path
lib_path = Path(__file__).resolve().parents[3] / "plugins/autonomous-dev/lib"
sys.path.insert(0, str(lib_path))

from daily_aggregate_manager import open_or_supersede_daily_aggregate


class FakeGHRunner:
    """Mock gh CLI runner for testing."""
    
    def __init__(self, responses):
        self.calls = []
        self._responses = list(responses)
    
    def __call__(self, argv, **kwargs):
        self.calls.append({"argv": argv, "kwargs": kwargs})
        resp = self._responses.pop(0) if self._responses else CompletedProcess(argv, 0, "", "")
        return resp


def test_day_1_empty_state_creates():
    """No prior open issues → creates new aggregate."""
    responses = [
        # gh issue list returns empty
        CompletedProcess([], 0, "[]", ""),
        # gh issue create returns new issue URL
        CompletedProcess([], 0, "https://github.com/owner/repo/issues/101", ""),
    ]
    
    runner = FakeGHRunner(responses)
    result = open_or_supersede_daily_aggregate(
        repo="owner/repo",
        label="auto-triage",
        title_prefix="Auto-triage findings —",
        body="Test findings",
        today_utc=date(2026, 7, 5),
        gh_runner=runner
    )
    
    assert result['action'] == 'created'
    assert result['issue_number'] == 101
    assert result['superseded'] == []
    
    # Verify gh commands
    assert len(runner.calls) == 2
    
    # First call: list issues
    list_call = runner.calls[0]
    assert list_call['argv'][:3] == ['gh', 'issue', 'list']
    assert '--repo' in list_call['argv']
    assert 'owner/repo' in list_call['argv']
    assert '--label' in list_call['argv']
    assert 'auto-triage' in list_call['argv']
    
    # Second call: create issue
    create_call = runner.calls[1]
    assert create_call['argv'][:3] == ['gh', 'issue', 'create']
    assert '--repo' in create_call['argv']
    assert '--title' in create_call['argv']
    assert 'Auto-triage findings — 2026-07-05' in create_call['argv']


def test_day_2_prior_open_supersedes():
    """Day-1 issue open → close with superseded comment, then create new."""
    responses = [
        # gh issue list returns day-1 issue
        CompletedProcess([], 0, json.dumps([
            {'number': 100, 'title': 'Auto-triage findings — 2026-07-04', 'createdAt': '2026-07-04T12:00:00Z'}
        ]), ""),
        # gh issue create returns new issue
        CompletedProcess([], 0, "https://github.com/owner/repo/issues/101", ""),
        # gh issue close (supersede old)
        CompletedProcess([], 0, "", ""),
    ]
    
    runner = FakeGHRunner(responses)
    result = open_or_supersede_daily_aggregate(
        repo="owner/repo",
        label="auto-triage",
        title_prefix="Auto-triage findings —",
        body="Day 2 findings",
        today_utc=date(2026, 7, 5),
        gh_runner=runner
    )
    
    assert result['action'] == 'superseded_and_created'
    assert result['issue_number'] == 101
    assert result['superseded'] == [100]
    
    # Verify call order
    assert len(runner.calls) == 3
    
    # First: list
    assert runner.calls[0]['argv'][:3] == ['gh', 'issue', 'list']
    
    # Second: create NEW issue
    assert runner.calls[1]['argv'][:3] == ['gh', 'issue', 'create']
    assert 'Auto-triage findings — 2026-07-05' in runner.calls[1]['argv']
    
    # Third: close OLD issue with superseded comment
    close_call = runner.calls[2]
    assert close_call['argv'][:3] == ['gh', 'issue', 'close']
    assert '100' in close_call['argv']
    assert '--comment' in close_call['argv']
    comment_idx = close_call['argv'].index('--comment')
    assert 'Superseded by #101' == close_call['argv'][comment_idx + 1]


def test_same_day_second_call_edits():
    """Today's aggregate already open → edit it, no create."""
    responses = [
        # gh issue list returns today's issue
        CompletedProcess([], 0, json.dumps([
            {'number': 101, 'title': 'Auto-triage findings — 2026-07-05', 'createdAt': '2026-07-05T10:00:00Z'}
        ]), ""),
        # gh issue edit
        CompletedProcess([], 0, "", ""),
    ]
    
    runner = FakeGHRunner(responses)
    result = open_or_supersede_daily_aggregate(
        repo="owner/repo",
        label="auto-triage",
        title_prefix="Auto-triage findings —",
        body="Updated findings",
        today_utc=date(2026, 7, 5),
        gh_runner=runner
    )
    
    assert result['action'] == 'edited'
    assert result['issue_number'] == 101
    assert result['superseded'] == []
    
    # Verify only list and edit, no create
    assert len(runner.calls) == 2
    assert runner.calls[0]['argv'][:3] == ['gh', 'issue', 'list']
    assert runner.calls[1]['argv'][:3] == ['gh', 'issue', 'edit']
    assert '101' in runner.calls[1]['argv']
    assert '--body-file' in runner.calls[1]['argv']


def test_subprocess_kwargs():
    """Every gh call has correct subprocess kwargs."""
    responses = [
        CompletedProcess([], 0, "[]", ""),
        CompletedProcess([], 0, "https://github.com/owner/repo/issues/101", ""),
    ]
    
    runner = FakeGHRunner(responses)
    open_or_supersede_daily_aggregate(
        repo="owner/repo",
        label="auto-triage",
        title_prefix="Auto-triage findings —",
        body="Test",
        today_utc=date(2026, 7, 5),
        gh_runner=runner
    )
    
    for call in runner.calls:
        kwargs = call['kwargs']
        assert kwargs['check'] is True
        assert kwargs['text'] is True
        assert kwargs['capture_output'] is True
        assert kwargs['cwd'] is None
        
        # --repo must be in argv
        assert '--repo' in call['argv']
        assert 'owner/repo' in call['argv']


def test_today_utc_is_required_kwarg():
    """Calling without today_utc raises TypeError."""
    runner = FakeGHRunner([])
    
    with pytest.raises(TypeError) as exc_info:
        open_or_supersede_daily_aggregate(
            repo="owner/repo",
            label="auto-triage",
            title_prefix="Auto-triage findings —",
            body="Test",
            # missing today_utc
            gh_runner=runner
        )
    
    assert "today_utc" in str(exc_info.value)