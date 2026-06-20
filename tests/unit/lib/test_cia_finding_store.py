"""Unit tests for cia_finding_store + the cia_findings collector.

Covers:
* ``append_finding`` atomic write semantics, fail-open behavior, secret
  scrubbing, length clamping, and symlink refusal.
* ``collect_cia_findings`` aggregation across monthly files, the absolute-path
  guard, severity contract, distinct-session tracking, and window filtering.
* A guard test that the continuous-improvement-analyst.md prompt contains zero
  occurrences of ``gh issue create`` / ``gh issue comment`` (Issue #1200 C2
  routing change).

GitHub Issue: #1200
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List
from unittest.mock import patch

import pytest

# Add lib to path so the flat-import style works in tests.
_LIB_DIR = Path(__file__).resolve().parents[3] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(_LIB_DIR))

from cia_finding_store import (
    append_finding,
    ALLOWED_SEVERITIES,
    MAX_EVIDENCE_LENGTH,
    MAX_TITLE_LENGTH,
    FILE_MODE,
    DIR_MODE,
)
from runtime_data_aggregator import collect_cia_findings, SourceHealth


# =============================================================================
# Helpers
# =============================================================================


def _now_iso(offset_days: int = 0) -> str:
    """Return an ISO UTC timestamp offset by ``offset_days``."""
    return (datetime.now(timezone.utc) - timedelta(days=offset_days)).isoformat()


def _make_record(
    *,
    severity: str = "warning",
    tag: str = "GAMING",
    title: str = "Tests weakened with assert True",
    evidence: str = "tests/test_x.py:42 changed assert x == 5 to assert True",
    file_refs: List[str] = None,
    session_id: str = "sess-abc",
    ts: str = None,
) -> dict:
    """Build a sample CIA finding record."""
    return {
        "severity": severity,
        "root_cause_tag": tag,
        "title": title,
        "evidence": evidence,
        "file_refs": file_refs if file_refs is not None else ["tests/test_x.py:42"],
        "session_id": session_id,
        "ts": ts if ts is not None else _now_iso(0),
    }


# =============================================================================
# TestAppendFinding
# =============================================================================


class TestAppendFinding:
    """Tests for ``append_finding`` direct write semantics."""

    def test_append_finding_writes_jsonl_record(self, tmp_path: Path) -> None:
        """All 7 required fields are preserved verbatim in the written line."""
        findings_dir = tmp_path / "findings"
        record = _make_record()

        result = append_finding(record, findings_dir=findings_dir)
        assert result is True

        files = list(findings_dir.glob("*.jsonl"))
        assert len(files) == 1
        lines = files[0].read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1

        parsed = json.loads(lines[0])
        for key in (
            "severity", "root_cause_tag", "title", "evidence",
            "file_refs", "session_id", "ts",
        ):
            assert key in parsed, f"missing field {key!r}"
        assert parsed["severity"] == "warning"
        assert parsed["root_cause_tag"] == "GAMING"
        assert parsed["title"] == record["title"]
        assert parsed["session_id"] == "sess-abc"
        assert parsed["file_refs"] == ["tests/test_x.py:42"]

    @pytest.mark.skipif(os.name == "nt", reason="POSIX mode bits not applicable on Windows")
    def test_append_finding_file_mode_0600(self, tmp_path: Path) -> None:
        """File mode is 0o600 after first write AND after a second append."""
        findings_dir = tmp_path / "findings"

        assert append_finding(_make_record(), findings_dir=findings_dir) is True
        monthly = next(findings_dir.glob("*.jsonl"))
        mode = monthly.stat().st_mode & 0o777
        assert mode == FILE_MODE, f"expected 0o600, got {oct(mode)}"

        # Re-append: backstop chmod should keep the mode at 0600.
        assert append_finding(_make_record(), findings_dir=findings_dir) is True
        mode = monthly.stat().st_mode & 0o777
        assert mode == FILE_MODE, f"after second append: {oct(mode)}"


    def test_append_finding_dir_mode_0700_backstop(self, tmp_path: Path) -> None:
        """Directory mode is forced to 0o700 even if pre-created with looser permissions."""
        findings_dir = tmp_path / "findings"
        # Pre-create the directory with loose permissions
        findings_dir.mkdir(mode=0o755)
        initial_mode = findings_dir.stat().st_mode & 0o777
        assert initial_mode == 0o755, f"expected 0o755, got {oct(initial_mode)}"
        
        # Call append_finding which should fix the permissions
        assert append_finding(_make_record(), findings_dir=findings_dir) is True
        
        # Verify the directory mode was tightened to 0o700
        final_mode = findings_dir.stat().st_mode & 0o777
        assert final_mode == DIR_MODE, f"expected 0o700, got {oct(final_mode)}"
    @pytest.mark.skipif(os.name == "nt", reason="flock POSIX-only")
    def test_append_finding_atomic_under_concurrent_appends(
        self, tmp_path: Path
    ) -> None:
        """5 threads x 20 records produce 100 valid JSON lines, no torn data."""
        findings_dir = tmp_path / "findings"

        # Pre-create with a long evidence string to ensure each line crosses
        # PIPE_BUF (512B on macOS) so the lock matters.
        long_evidence = "x" * 1500

        def worker(thread_id: int) -> None:
            for i in range(20):
                rec = _make_record(
                    title=f"thread{thread_id}-record{i}",
                    evidence=long_evidence,
                    session_id=f"sess-{thread_id}",
                )
                append_finding(rec, findings_dir=findings_dir)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        monthly = next(findings_dir.glob("*.jsonl"))
        lines = monthly.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 100, f"expected 100 lines, got {len(lines)}"

        # Every line must be valid JSON (no torn writes).
        for idx, line in enumerate(lines):
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError as exc:  # pragma: no cover
                pytest.fail(f"line {idx} is torn JSON: {line[:80]!r} ({exc})")
            assert "title" in parsed

    def test_append_finding_fail_open_on_oserror(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """When ``open`` raises, the function returns False and logs to stderr."""
        findings_dir = tmp_path / "findings"
        findings_dir.mkdir(parents=True, exist_ok=True)

        def boom(*args, **kwargs):
            raise PermissionError("simulated EACCES")

        with patch("cia_finding_store.open", side_effect=boom):
            result = append_finding(_make_record(), findings_dir=findings_dir)
        assert result is False

        captured = capsys.readouterr()
        assert "[cia-finding-store]" in captured.err

    def test_append_finding_redacts_secrets_in_evidence(self, tmp_path: Path) -> None:
        """Secrets in evidence are redacted by ``scrub_secrets`` before write."""
        findings_dir = tmp_path / "findings"
        record = _make_record(
            evidence="leaked token: ghp_aaaaaaaaaaaaaaaaaaaaaaaa in config",
            title="config leak ghp_bbbbbbbbbbbbbbbbbbbb",
        )

        assert append_finding(record, findings_dir=findings_dir) is True
        line = next(findings_dir.glob("*.jsonl")).read_text(encoding="utf-8")
        assert "ghp_aaaaaaaaaaaaaaaaaaaaaaaa" not in line
        assert "ghp_bbbbbbbbbbbbbbbbbbbb" not in line
        # scrub_secrets replaces with [REDACTED].
        assert "[REDACTED]" in line

    def test_append_finding_clamps_oversized_evidence(self, tmp_path: Path) -> None:
        """Oversized evidence is clamped to ``MAX_EVIDENCE_LENGTH`` chars."""
        findings_dir = tmp_path / "findings"
        record = _make_record(evidence="A" * 5000)

        assert append_finding(record, findings_dir=findings_dir) is True
        parsed = json.loads(next(findings_dir.glob("*.jsonl")).read_text())
        assert len(parsed["evidence"]) <= MAX_EVIDENCE_LENGTH
        # Verify also the title clamp.
        record2 = _make_record(title="B" * 1000, evidence="ok")
        assert append_finding(record2, findings_dir=findings_dir) is True

    @pytest.mark.skipif(os.name == "nt", reason="symlinks not portable on Windows")
    def test_append_finding_rejects_symlinked_monthly_file(
        self, tmp_path: Path
    ) -> None:
        """A symlinked monthly file is refused; the symlink target is not written."""
        findings_dir = tmp_path / "findings"
        findings_dir.mkdir(parents=True, exist_ok=True)
        # Pre-create the monthly file as a symlink to a sentinel file.
        sentinel = tmp_path / "sentinel.txt"
        sentinel.write_text("DO NOT TOUCH\n")
        sentinel_initial = sentinel.read_text()

        now = datetime.now(timezone.utc)
        monthly = findings_dir / f"{now.strftime('%Y-%m')}.jsonl"
        os.symlink(sentinel, monthly)

        result = append_finding(_make_record(), findings_dir=findings_dir, now=now)
        assert result is False
        # The sentinel target must NOT have been written to.
        assert sentinel.read_text() == sentinel_initial


# =============================================================================
# TestCollectCIAFindings
# =============================================================================


class TestCollectCIAFindings:
    """Tests for ``collect_cia_findings`` aggregator."""

    def test_collect_cia_findings_returns_empty_when_dir_missing(
        self, tmp_path: Path
    ) -> None:
        """Non-existent absolute path → empty signals, status=empty."""
        missing = tmp_path / "does-not-exist"
        signals, health = collect_cia_findings(missing)
        assert signals == []
        assert isinstance(health, SourceHealth)
        assert health.source == "cia_findings"
        assert health.status == "empty"
        assert health.signal_count == 0

    def test_collect_cia_findings_requires_absolute_findings_dir(self) -> None:
        """Relative path raises ``ValueError`` (worktree-safety regression)."""
        with pytest.raises(ValueError, match="absolute"):
            collect_cia_findings(Path("relative/findings"))

    def test_collect_cia_findings_groups_by_tag_and_token_cluster(
        self, tmp_path: Path
    ) -> None:
        """3 same-tag shared-token records cluster → 1 signal freq=3; +2 distinct → 2nd signal."""
        findings_dir = tmp_path / "findings"

        # Three records sharing the tokens "tests weakened".
        for i in range(3):
            rec = _make_record(
                title=f"tests weakened assertion {i}",
                evidence=f"file{i}.py",
                session_id=f"sess-shared-{i}",
            )
            assert append_finding(rec, findings_dir=findings_dir) is True

        # Two records same tag but distinct tokens (no shared tokens with cluster A).
        for i in range(2):
            rec = _make_record(
                title=f"coverage scope narrowed pyproject {i}",
                evidence=f"pyproject.toml change {i}",
                session_id=f"sess-other-{i}",
            )
            assert append_finding(rec, findings_dir=findings_dir) is True

        signals, health = collect_cia_findings(findings_dir)
        assert health.status == "ok"
        # Tag is shared, so we expect 2 sub-clusters within tag "GAMING".
        assert len(signals) == 2, (
            f"expected 2 sub-cluster signals, got {len(signals)}: "
            f"{[(s.signal_type, s.description, s.frequency) for s in signals]}"
        )
        freqs = sorted(s.frequency for s in signals)
        assert freqs == [2, 3], freqs
        for s in signals:
            assert s.signal_type == "GAMING"
            assert s.source == "cia_findings"

    def test_collect_cia_findings_window_excludes_old_records(
        self, tmp_path: Path
    ) -> None:
        """Records older than ``window_days`` are excluded; source untouched."""
        findings_dir = tmp_path / "findings"

        old_rec = _make_record(ts=_now_iso(120))
        recent_rec = _make_record(ts=_now_iso(30))
        # Use distinct months for the two records to exercise file-month
        # filtering AND in-record ts filtering.
        old_dt = datetime.now(timezone.utc) - timedelta(days=120)
        recent_dt = datetime.now(timezone.utc) - timedelta(days=30)
        assert append_finding(old_rec, findings_dir=findings_dir, now=old_dt) is True
        assert append_finding(recent_rec, findings_dir=findings_dir, now=recent_dt) is True

        # Snapshot file contents BEFORE collect.
        files_before = {p.name: p.read_text(encoding="utf-8") for p in findings_dir.glob("*.jsonl")}

        signals, health = collect_cia_findings(findings_dir, window_days=90)
        assert health.status == "ok"
        # Only the recent record survives.
        assert len(signals) == 1, signals
        assert signals[0].frequency == 1

        # Verify collect_cia_findings did not delete or rewrite the source files.
        files_after = {p.name: p.read_text(encoding="utf-8") for p in findings_dir.glob("*.jsonl")}
        assert files_after == files_before, "source files mutated during collect"

    def test_collect_cia_findings_tracks_distinct_sessions(
        self, tmp_path: Path
    ) -> None:
        """5 records across 3 distinct sessions → distinct_sessions=3, frequency=5."""
        findings_dir = tmp_path / "findings"
        session_ids = ["s1", "s1", "s2", "s2", "s3"]
        for sid in session_ids:
            rec = _make_record(
                title="tests weakened with assert True",
                evidence=f"event from {sid}",
                session_id=sid,
            )
            assert append_finding(rec, findings_dir=findings_dir) is True

        signals, health = collect_cia_findings(findings_dir)
        assert health.status == "ok"
        assert len(signals) == 1, signals
        sig = signals[0]
        assert sig.frequency == 5
        assert sig.raw_data["distinct_sessions"] == 3
        assert sig.raw_data["sub_cluster_size"] == 5
        assert sig.raw_data["root_cause_tag"] == "GAMING"

    def test_collect_cia_findings_severity_contract(self, tmp_path: Path) -> None:
        """Severity float follows CIA_FINDING_SEVERITY_MAP and lies in [0, 1]."""
        # Mixed cluster (info+warning+error) → max severity = error → 1.0
        d_mixed = tmp_path / "mixed"
        for sev in ("info", "warning", "error"):
            rec = _make_record(
                severity=sev,
                title="tests weakened assert true now",
                session_id=f"s-{sev}",
            )
            assert append_finding(rec, findings_dir=d_mixed) is True
        signals, _ = collect_cia_findings(d_mixed)
        assert len(signals) == 1
        assert signals[0].severity == pytest.approx(1.0)
        assert 0.0 <= signals[0].severity <= 1.0
        assert signals[0].raw_data["max_severity_label"] == "error"

        # Pure info cluster → 0.33
        d_info = tmp_path / "info_only"
        for i in range(2):
            rec = _make_record(
                severity="info",
                title=f"tests weakened low severity {i}",
                session_id=f"i-{i}",
            )
            assert append_finding(rec, findings_dir=d_info) is True
        signals, _ = collect_cia_findings(d_info)
        assert len(signals) == 1
        assert signals[0].severity == pytest.approx(0.33)
        assert signals[0].raw_data["max_severity_label"] == "info"

        # Pure warning cluster → 0.66
        d_warn = tmp_path / "warn_only"
        for i in range(2):
            rec = _make_record(
                severity="warning",
                title=f"tests weakened mid severity {i}",
                session_id=f"w-{i}",
            )
            assert append_finding(rec, findings_dir=d_warn) is True
        signals, _ = collect_cia_findings(d_warn)
        assert len(signals) == 1
        assert signals[0].severity == pytest.approx(0.66)
        assert signals[0].raw_data["max_severity_label"] == "warning"


# =============================================================================
# TestCIAPromptInvariants
# =============================================================================


class TestCIAPromptInvariants:
    """Structural guards on the continuous-improvement-analyst.md prompt."""

    def test_cia_prompt_contains_zero_gh_issue_create(self) -> None:
        """The CIA prompt MUST NOT contain ``gh issue create`` / ``gh issue comment``.

        Issue #1200 (C2) moved direct-filing out of the CIA path; the agent
        now emits records via :func:`append_finding` and the routing/filing
        decision lives in ``/improve --auto-file`` (C3).
        """
        repo_root = Path(__file__).resolve().parents[3]
        prompt = (
            repo_root
            / "plugins"
            / "autonomous-dev"
            / "agents"
            / "continuous-improvement-analyst.md"
        ).read_text(encoding="utf-8")

        create_count = prompt.count("gh issue create")
        comment_count = prompt.count("gh issue comment")
        assert create_count == 0, (
            f"continuous-improvement-analyst.md still has {create_count} "
            f"`gh issue create` occurrences — Issue #1200 (C2) requires zero."
        )
        assert comment_count == 0, (
            f"continuous-improvement-analyst.md still has {comment_count} "
            f"`gh issue comment` occurrences — Issue #1200 (C2) requires zero."
        )
