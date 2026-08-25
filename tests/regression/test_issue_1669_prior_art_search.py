"""Regression tests for Issue #1669: prior-art search library.

The mechanism is watched refusing (surfacing a shipped closed issue) AND
permitting (returning empty for a genuinely novel topic) AND degrading
(gh unavailable, timeout, malformed output) — one arm alone is not proof.

Wiring into ``commands/implement.md`` remains OPEN — #1669 stays open
until that wiring lands. This test locks the mechanism contract so
wiring later cannot silently regress the shape.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

_LIB = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import prior_art_search  # noqa: E402


def _fake_run(returncode=0, stdout="", side_effect=None):
    """Build a ``subprocess.run`` replacement that returns a fixed result."""

    def _runner(*args, **kwargs):
        if side_effect is not None:
            raise side_effect
        return subprocess.CompletedProcess(
            args=args[0] if args else [],
            returncode=returncode,
            stdout=stdout,
            stderr="",
        )

    return _runner


# ---------------------------------------------------------------------------
# REFUSAL arm — a real prior-art hit surfaces.
# ---------------------------------------------------------------------------
def test_refuses_novel_claim_when_prior_art_exists(tmp_path: Path) -> None:
    """The #770 regression: 'mutation testing' must surface issue #770."""

    fake_gh_output = json.dumps(
        [
            {
                "number": 770,
                "title": "Add mutation testing (mutmut) to validate test quality on lib/",
                "state": "CLOSED",
                "closedAt": "2026-04-11T00:00:00Z",
            }
        ]
    )
    with patch.object(
        prior_art_search.subprocess,
        "run",
        side_effect=_fake_run(returncode=0, stdout=fake_gh_output),
    ):
        hits = prior_art_search.search_prior_art(["mutation testing"], tmp_path)
    assert len(hits) == 1
    assert hits[0]["number"] == 770
    assert hits[0]["state"] == "CLOSED"


# ---------------------------------------------------------------------------
# PERMIT arm — novel topics return empty without raising.
# ---------------------------------------------------------------------------
def test_permits_novel_topic_with_empty_result(tmp_path: Path) -> None:
    with patch.object(
        prior_art_search.subprocess,
        "run",
        side_effect=_fake_run(returncode=0, stdout="[]"),
    ):
        hits = prior_art_search.search_prior_art(["nonsense-xyz-123"], tmp_path)
    assert hits == []


def test_permits_empty_keywords_input(tmp_path: Path) -> None:
    """Empty input must not touch subprocess at all and must not raise."""

    called = {"n": 0}

    def _tracker(*args, **kwargs):
        called["n"] += 1
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="[]")

    with patch.object(prior_art_search.subprocess, "run", side_effect=_tracker):
        assert prior_art_search.search_prior_art([], tmp_path) == []
        assert prior_art_search.search_prior_art(["   ", ""], tmp_path) == []
    assert called["n"] == 0


# ---------------------------------------------------------------------------
# GRACEFUL DEGRADE — gh missing / non-zero / timeout / malformed → [].
# ---------------------------------------------------------------------------
def test_degrades_when_gh_binary_missing(tmp_path: Path) -> None:
    with patch.object(
        prior_art_search.subprocess,
        "run",
        side_effect=_fake_run(side_effect=FileNotFoundError("gh not on PATH")),
    ):
        hits = prior_art_search.search_prior_art(["mutation"], tmp_path)
    assert hits == []


def test_degrades_when_gh_returns_nonzero(tmp_path: Path) -> None:
    with patch.object(
        prior_art_search.subprocess,
        "run",
        side_effect=_fake_run(returncode=1, stdout=""),
    ):
        hits = prior_art_search.search_prior_art(["mutation"], tmp_path)
    assert hits == []


def test_degrades_when_gh_times_out(tmp_path: Path) -> None:
    with patch.object(
        prior_art_search.subprocess,
        "run",
        side_effect=_fake_run(
            side_effect=subprocess.TimeoutExpired(cmd=["gh"], timeout=15)
        ),
    ):
        hits = prior_art_search.search_prior_art(["mutation"], tmp_path)
    assert hits == []


def test_degrades_when_gh_returns_malformed_json(tmp_path: Path) -> None:
    # First call = gh (malformed JSON → _GhFailure → fallback to git-log).
    # Second call = git-log (return empty stdout so no synthetic hits).
    calls = iter(
        [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="{not json"),
            subprocess.CompletedProcess(args=[], returncode=0, stdout=""),
        ]
    )

    def _sequential_run(*args, **kwargs):
        return next(calls)

    with patch.object(prior_art_search.subprocess, "run", side_effect=_sequential_run):
        hits = prior_art_search.search_prior_art(["mutation"], tmp_path)
    assert hits == []


# ---------------------------------------------------------------------------
# Deduplication — same issue surfaced by multiple keywords appears once.
# ---------------------------------------------------------------------------
def test_deduplicates_hits_across_keywords(tmp_path: Path) -> None:
    hit_json = json.dumps(
        [
            {
                "number": 770,
                "title": "Mutation testing",
                "state": "CLOSED",
                "closedAt": "2026-04-11T00:00:00Z",
            }
        ]
    )
    with patch.object(
        prior_art_search.subprocess,
        "run",
        side_effect=_fake_run(returncode=0, stdout=hit_json),
    ):
        hits = prior_art_search.search_prior_art(
            ["mutation", "mutmut", "kill mutants"], tmp_path
        )
    numbers = [h["number"] for h in hits]
    assert numbers == [770]


# ---------------------------------------------------------------------------
# Contract: never raises. Broad-brush safety net.
# ---------------------------------------------------------------------------
def test_never_raises_for_arbitrary_bad_input(tmp_path: Path) -> None:
    # None entries, non-strings, weird types — must be silently ignored.
    with patch.object(
        prior_art_search.subprocess,
        "run",
        side_effect=_fake_run(returncode=0, stdout="[]"),
    ):
        hits = prior_art_search.search_prior_art(
            ["ok", None, 42, {"weird": "type"}, ""],  # type: ignore[list-item]
            tmp_path,
        )
    assert hits == []
