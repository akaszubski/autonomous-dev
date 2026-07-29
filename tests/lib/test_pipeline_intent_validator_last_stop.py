"""Test detect_doc_verdict_missing uses last SubagentStop (Issue #1417)."""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any

import pytest

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins/autonomous-dev/lib"))


def test_detect_doc_verdict_missing_basic():
    """Basic test that the function exists and handles empty input."""
    from pipeline_intent_validator import detect_doc_verdict_missing
    
    # Test with empty list
    findings = detect_doc_verdict_missing([])
    assert findings == []


def test_detect_doc_verdict_missing_with_events():
    """Test detection with actual events."""
    from pipeline_intent_validator import (
        detect_doc_verdict_missing,
        PipelineEvent,
        MIN_DOC_VERDICT_WORDS,
    )
    
    base_time = datetime.now()
    
    # Create a successful doc-master flow
    events = [
        PipelineEvent(
            timestamp=base_time.isoformat(),
            tool="Agent",
            agent="main",
            pipeline_action="agent_invocation",
            subagent_type="doc-master",
            result_word_count=0,  # Invocations always have 0
            success=True,
            agent_transcript_path=None,
        ),
        PipelineEvent(
            timestamp=(base_time + timedelta(seconds=30)).isoformat(),
            tool="",
            agent="doc-master",
            pipeline_action="agent_completion",
            subagent_type="doc-master",
            result_word_count=MIN_DOC_VERDICT_WORDS + 50,  # Sufficient words
            success=True,
            agent_transcript_path=".claude/agent_transcripts/doc-master.md",
        ),
    ]
    
    findings = detect_doc_verdict_missing(events)
    assert len(findings) == 0  # Should not flag - completion is good


def test_detect_doc_verdict_missing_insufficient_words():
    """Test flagging when word count is insufficient."""
    from pipeline_intent_validator import (
        detect_doc_verdict_missing,
        PipelineEvent,
        MIN_DOC_VERDICT_WORDS,
    )
    
    base_time = datetime.now()
    
    events = [
        PipelineEvent(
            timestamp=base_time.isoformat(),
            tool="Agent",
            agent="main",
            pipeline_action="agent_invocation",
            subagent_type="doc-master",
            result_word_count=0,
            success=True,
            agent_transcript_path=None,
        ),
        PipelineEvent(
            timestamp=(base_time + timedelta(seconds=30)).isoformat(),
            tool="",
            agent="doc-master",
            pipeline_action="agent_completion",
            subagent_type="doc-master",
            result_word_count=5,  # Too low
            success=True,
            agent_transcript_path=None,  # No transcript path either
        ),
    ]
    
    findings = detect_doc_verdict_missing(events)
    assert len(findings) == 1
    assert "output too short" in findings[0].description
    assert "5 words" in findings[0].description


def test_detect_doc_verdict_missing_multiple_completions():
    """Test that last completion is used when multiple exist."""
    from pipeline_intent_validator import (
        detect_doc_verdict_missing,
        PipelineEvent,
        MIN_DOC_VERDICT_WORDS,
    )
    
    base_time = datetime.now()
    
    # Multiple completions for same invocation
    events = [
        PipelineEvent(
            timestamp=base_time.isoformat(),
            tool="Agent",
            agent="main",
            pipeline_action="agent_invocation",
            subagent_type="doc-master",
            result_word_count=0,
            success=True,
            agent_transcript_path=None,
        ),
        # First completion - low words (would flag if used)
        PipelineEvent(
            timestamp=(base_time + timedelta(seconds=10)).isoformat(),
            tool="",
            agent="doc-master",
            pipeline_action="agent_completion",
            subagent_type="doc-master",
            result_word_count=5,
            success=True,
            agent_transcript_path=None,
        ),
        # Second completion - still low but has transcript
        PipelineEvent(
            timestamp=(base_time + timedelta(seconds=20)).isoformat(),
            tool="",
            agent="doc-master",
            pipeline_action="agent_completion",
            subagent_type="doc-master",
            result_word_count=10,
            success=True,
            agent_transcript_path=".claude/agent_transcripts/doc-master.md",  # Has path
        ),
        # Third completion - good word count (should be used)
        PipelineEvent(
            timestamp=(base_time + timedelta(seconds=30)).isoformat(),
            tool="",
            agent="doc-master",
            pipeline_action="agent_completion",
            subagent_type="doc-master",
            result_word_count=MIN_DOC_VERDICT_WORDS + 100,
            success=True,
            agent_transcript_path=".claude/agent_transcripts/doc-master-final.md",
        ),
    ]
    
    findings = detect_doc_verdict_missing(events)
    # Should NOT flag - last completion has sufficient words
    assert len(findings) == 0


def test_detect_doc_verdict_missing_failed_completion():
    """Test flagging when completion has success=False."""
    from pipeline_intent_validator import (
        detect_doc_verdict_missing,
        PipelineEvent,
        MIN_DOC_VERDICT_WORDS,
    )
    
    base_time = datetime.now()
    
    events = [
        PipelineEvent(
            timestamp=base_time.isoformat(),
            tool="Agent",
            agent="main",
            pipeline_action="agent_invocation",
            subagent_type="doc-master",
            result_word_count=0,
            success=True,
            agent_transcript_path=None,
        ),
        PipelineEvent(
            timestamp=(base_time + timedelta(seconds=30)).isoformat(),
            tool="",
            agent="doc-master",
            pipeline_action="agent_completion",
            subagent_type="doc-master",
            result_word_count=MIN_DOC_VERDICT_WORDS + 50,  # Word count is fine
            success=False,  # But failed
            agent_transcript_path=None,
        ),
    ]
    
    findings = detect_doc_verdict_missing(events)
    assert len(findings) == 1
    assert "failed (success=False)" in findings[0].description