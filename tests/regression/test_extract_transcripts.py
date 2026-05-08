"""Regression tests for `extract_prompts_from_transcripts` (Issue #1072).

Verifies the 7 filter conditions, dedup, mtime cutoff, defensive paths
(missing dir, malformed JSON), and the CLI ``--source`` flag wiring. All
tests use ``tmp_path`` to write controlled JSONL fixtures — no test reads
real ``~/.claude/archive/`` data.

GitHub Issue: #1072
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

# Add scripts to path for import
_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from extract_and_label_intent_corpus import (  # noqa: E402
    MAX_PROMPT_LEN,
    MIN_PROMPT_LEN,
    _JUDGE_PROMPT_PREFIX,
    extract_prompts_from_transcripts,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    """Write a list of dicts as JSONL to ``path`` (parent dirs created)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _user_row(content: Any, *, type_: str = "user", role: str = "user") -> Dict[str, Any]:
    """Build a transcript row resembling ``~/.claude/archive/conversations/*.jsonl``."""
    return {
        "type": type_,
        "message": {"role": role, "content": content},
    }


# ---------------------------------------------------------------------------
# Filter condition tests (7 conditions in extract_prompts_from_transcripts)
# ---------------------------------------------------------------------------


def test_filters_out_queue_operation_type(tmp_path: Path) -> None:
    """Filter 1: rows with ``type != "user"`` are skipped (e.g., 'queue', 'assistant')."""
    jsonl = tmp_path / "2026-05" / "session.jsonl"
    rows = [
        {"type": "queue", "message": {"role": "user", "content": "this is a queued op"}},
        {"type": "assistant", "message": {"role": "assistant", "content": "an assistant reply that is long enough"}},
        _user_row("a real user prompt that is long enough"),
    ]
    _write_jsonl(jsonl, rows)

    out = extract_prompts_from_transcripts(tmp_path, days=30, max_prompts=100)

    assert out == ["a real user prompt that is long enough"], (
        f"Only the type=user row should pass; got {out!r}"
    )


def test_filters_out_non_user_role(tmp_path: Path) -> None:
    """Filter 2: rows where nested ``message.role != "user"`` are skipped."""
    jsonl = tmp_path / "2026-05" / "session.jsonl"
    rows = [
        # Outer type=user but inner role=assistant — should be filtered
        {"type": "user", "message": {"role": "assistant", "content": "this should be filtered out due to role"}},
        # Outer type=user, inner role=tool — also filtered
        {"type": "user", "message": {"role": "tool", "content": "another row that should be filtered"}},
        _user_row("a real user prompt that is long enough"),
    ]
    _write_jsonl(jsonl, rows)

    out = extract_prompts_from_transcripts(tmp_path, days=30, max_prompts=100)

    assert out == ["a real user prompt that is long enough"], (
        f"Only the role=user row should pass; got {out!r}"
    )


def test_filters_out_tool_result_list_content(tmp_path: Path) -> None:
    """Filter 3: rows where ``message.content`` is not a string are skipped.

    Claude Code tool_result envelopes have ``content`` as a list of dicts;
    those are NOT user-typed text and must be excluded.
    """
    jsonl = tmp_path / "2026-05" / "session.jsonl"
    rows = [
        # tool_result: content is a list (Claude Code envelope shape)
        _user_row([{"type": "tool_result", "tool_use_id": "x", "content": "result"}]),
        # content is a dict (some other envelope) — also filtered
        _user_row({"unexpected": "shape"}),
        # content is None — filtered
        _user_row(None),
        _user_row("a real user prompt that is long enough"),
    ]
    _write_jsonl(jsonl, rows)

    out = extract_prompts_from_transcripts(tmp_path, days=30, max_prompts=100)

    assert out == ["a real user prompt that is long enough"], (
        f"Only string-content user rows should pass; got {out!r}"
    )


def test_filters_out_local_command_caveat(tmp_path: Path) -> None:
    """Filter 4: content starting with ``<local-command-caveat>`` is skipped."""
    jsonl = tmp_path / "2026-05" / "session.jsonl"
    rows = [
        _user_row("<local-command-caveat>internal Claude Code wrapper text</local-command-caveat>"),
        _user_row("a real user prompt that is long enough"),
    ]
    _write_jsonl(jsonl, rows)

    out = extract_prompts_from_transcripts(tmp_path, days=30, max_prompts=100)

    assert out == ["a real user prompt that is long enough"], (
        f"local-command-caveat rows must be filtered; got {out!r}"
    )


def test_filters_out_claude_p_self_traffic(tmp_path: Path) -> None:
    """Filter 5: corpus-script's own judge prompts are skipped.

    Without this guard, running the extractor while a labeling job is
    underway would feed our own ``Classify this user prompt:`` text back
    into the corpus.
    """
    jsonl = tmp_path / "2026-05" / "session.jsonl"
    self_traffic = (
        f"{_JUDGE_PROMPT_PREFIX}\n<prompt>some inner prompt</prompt>"
    )
    rows = [
        _user_row(self_traffic),
        _user_row("a real user prompt that is long enough"),
    ]
    _write_jsonl(jsonl, rows)

    out = extract_prompts_from_transcripts(tmp_path, days=30, max_prompts=100)

    assert out == ["a real user prompt that is long enough"], (
        f"Self-traffic judge prompts must be filtered; got {out!r}"
    )


def test_filters_out_below_min_length(tmp_path: Path) -> None:
    """Filter 6: content shorter than ``MIN_PROMPT_LEN`` is skipped."""
    jsonl = tmp_path / "2026-05" / "session.jsonl"
    too_short = "hi"  # 2 chars
    assert len(too_short) < MIN_PROMPT_LEN
    rows = [
        _user_row(too_short),
        _user_row("a real user prompt that is long enough"),
    ]
    _write_jsonl(jsonl, rows)

    out = extract_prompts_from_transcripts(tmp_path, days=30, max_prompts=100)

    assert out == ["a real user prompt that is long enough"], (
        f"Short prompts must be filtered; got {out!r}"
    )


def test_filters_out_above_max_length(tmp_path: Path) -> None:
    """Filter 7: content longer than ``MAX_PROMPT_LEN`` is skipped."""
    jsonl = tmp_path / "2026-05" / "session.jsonl"
    too_long = "a" * (MAX_PROMPT_LEN + 1)
    rows = [
        _user_row(too_long),
        _user_row("a real user prompt that is long enough"),
    ]
    _write_jsonl(jsonl, rows)

    out = extract_prompts_from_transcripts(tmp_path, days=30, max_prompts=100)

    assert out == ["a real user prompt that is long enough"], (
        f"Long prompts must be filtered; got {out!r}"
    )


# ---------------------------------------------------------------------------
# Dedup, time window, defensive paths
# ---------------------------------------------------------------------------


def test_deduplication_by_content_hash(tmp_path: Path) -> None:
    """Identical content from two transcripts collapses to one entry."""
    jsonl_a = tmp_path / "2026-05" / "session_a.jsonl"
    jsonl_b = tmp_path / "2026-05" / "session_b.jsonl"
    duplicate = "this is a duplicate prompt across two sessions"
    _write_jsonl(jsonl_a, [_user_row(duplicate)])
    _write_jsonl(jsonl_b, [_user_row(duplicate), _user_row("a unique second prompt")])

    out = extract_prompts_from_transcripts(tmp_path, days=30, max_prompts=100)

    assert sorted(out) == sorted([duplicate, "a unique second prompt"]), (
        f"Dedup by content hash failed; got {out!r}"
    )


def test_days_window_cutoff(tmp_path: Path) -> None:
    """Transcript files older than ``days`` are skipped via mtime check."""
    fresh = tmp_path / "2026-05" / "fresh.jsonl"
    stale = tmp_path / "2025-01" / "stale.jsonl"
    _write_jsonl(fresh, [_user_row("a fresh user prompt that is long enough")])
    _write_jsonl(stale, [_user_row("a stale user prompt that should be skipped")])

    # Backdate the stale file to 100 days ago (well outside a 30-day window)
    one_hundred_days_ago = time.time() - (100 * 86400)
    os.utime(stale, (one_hundred_days_ago, one_hundred_days_ago))

    out = extract_prompts_from_transcripts(tmp_path, days=30, max_prompts=100)

    assert out == ["a fresh user prompt that is long enough"], (
        f"Stale (>30d mtime) jsonls must be skipped; got {out!r}"
    )


def test_passes_valid_user_message(tmp_path: Path) -> None:
    """A clean, valid user message is returned as-is (positive control)."""
    jsonl = tmp_path / "2026-05" / "session.jsonl"
    valid = "implement pagination for the user list endpoint"
    _write_jsonl(jsonl, [_user_row(valid)])

    out = extract_prompts_from_transcripts(tmp_path, days=30, max_prompts=100)

    assert out == [valid], f"Valid prompt was not extracted; got {out!r}"


def test_transcripts_dir_does_not_exist(tmp_path: Path) -> None:
    """Missing transcripts dir returns ``[]`` without raising."""
    nonexistent = tmp_path / "does_not_exist"
    assert not nonexistent.exists()

    out = extract_prompts_from_transcripts(nonexistent, days=30, max_prompts=100)

    assert out == [], f"Missing dir must return []; got {out!r}"


def test_malformed_jsonl_line_skipped(tmp_path: Path) -> None:
    """Malformed JSON lines are skipped; valid lines in the same file are still returned."""
    jsonl = tmp_path / "2026-05" / "session.jsonl"
    jsonl.parent.mkdir(parents=True, exist_ok=True)
    with open(jsonl, "w") as f:
        f.write("this is not valid json at all\n")
        f.write(json.dumps(_user_row("a valid user prompt that is long enough")) + "\n")
        f.write("{not closed json\n")
        f.write(json.dumps(_user_row("another valid user prompt")) + "\n")

    out = extract_prompts_from_transcripts(tmp_path, days=30, max_prompts=100)

    assert sorted(out) == sorted(
        ["a valid user prompt that is long enough", "another valid user prompt"]
    ), f"Malformed lines must be skipped without losing valid lines; got {out!r}"


# ---------------------------------------------------------------------------
# CLI flag wiring (#1072 acceptance criterion 8)
# ---------------------------------------------------------------------------


def test_cli_source_flag_routes_to_transcripts(monkeypatch, tmp_path: Path) -> None:
    """``--source transcripts`` flows through main() into build_corpus()."""
    from extract_and_label_intent_corpus import main as _main

    output_path = tmp_path / "test_corpus.json"
    captured_kwargs: Dict[str, Any] = {}

    def fake_build_corpus(db_path, **kwargs):  # type: ignore[no-untyped-def]
        captured_kwargs.update(kwargs)
        return {
            "_schema_version": 1,
            "_extracted_at": "x",
            "_methodology": "test",
            "entries": [],
        }

    monkeypatch.setattr(
        "extract_and_label_intent_corpus.build_corpus", fake_build_corpus
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "script",
            "--source",
            "transcripts",
            "--output",
            str(output_path),
            "--dry-run",
        ],
    )
    _main()

    assert captured_kwargs.get("source") == "transcripts", (
        f"--source transcripts must propagate to build_corpus (#1072). "
        f"Got: {captured_kwargs.get('source')!r}"
    )
