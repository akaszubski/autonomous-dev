#!/usr/bin/env python3
"""Regression: the block log was wrong in BOTH directions at once (Issue #1611).

``.claude/logs/hook-blocks.jsonl`` is the evidence base for whether enforcement
works. Measured at the time of filing:

* **Over-counting.** 574 of 10,966 rows (5.2%) carried
  ``decision_shape: "mode_skip"`` — enforcement *skipped*, the opposite of a
  refusal. One of three readers filtered them out. The other two did not, and
  ``scripts/hook_block_summary.py`` ranked ``plan_mode_exit_detector.py`` —
  a hook whose own docstring says it cannot block — fifth among blockers.
* **Under-counting.** ``plan_gate.py`` refused via two
  ``_output_decision("block", ...)`` calls and recorded nothing. All 287 of
  its rows were ``mode_skip``; not one refusal it ever made left a trace.

An instrument wrong in one direction can be corrected with a filter. One wrong
in both directions, differently per hook, cannot be corrected from the data it
produces.

Each class below is one fix, and each names the state it reproduces.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# tests/regression/test_issue_1611_...py -> regression -> tests -> repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
HOOKS_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "hooks"

if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import hook_telemetry  # noqa: E402


def _run_summary(args, *, cwd: Path) -> subprocess.CompletedProcess:
    """Drive the real summary script as a subprocess. Verify what EXECUTES."""
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "hook_block_summary.py"), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
    )


def _row(**overrides) -> str:
    base = {
        "ts": "2026-08-22T00:00:00+00:00",
        "hook_name": "h.py",
        "decision_shape": "tuple",
        "reason": "r",
        "metadata": {},
        "session_id": "",
        "cwd": "/tmp",
    }
    base.update(overrides)
    return json.dumps(base)


class TestSharedVocabularyIsExportedOnce:
    """AC: ``BLOCK_SHAPES`` is exported once and imported by every reader.

    RED BEFORE: the constant was DEFINED in ``scripts/hook_perf_report.py``
    and existed nowhere else. ``hook_telemetry.BLOCK_SHAPES`` did not exist,
    so the identity assertions below raised ``AttributeError``.
    """

    def test_canonical_constant_lives_beside_the_writer(self):
        assert hasattr(hook_telemetry, "BLOCK_SHAPES"), (
            "the refusal vocabulary must live next to log_block_event, the "
            "only thing that writes the log"
        )
        assert hook_telemetry.BLOCK_SHAPES == {
            "tuple",
            "dict",
            "exit2",
            "legacy_recovery",
        }
        assert "mode_skip" not in hook_telemetry.BLOCK_SHAPES
        assert "allow" not in hook_telemetry.BLOCK_SHAPES

    def test_perf_report_imports_rather_than_redefines(self):
        """IDENTITY, not equality — equality passes for a drifting copy."""
        sys.path.insert(0, str(SCRIPTS_DIR))
        try:
            import hook_perf_report
        finally:
            sys.path.remove(str(SCRIPTS_DIR))
        assert hook_perf_report.BLOCK_SHAPES is hook_telemetry.BLOCK_SHAPES, (
            "hook_perf_report defines its own BLOCK_SHAPES again. A second "
            "definition is a second thing that can drift, which is the defect "
            "Issue #1611 removes."
        )

    def test_block_summary_imports_rather_than_redefines(self):
        sys.path.insert(0, str(SCRIPTS_DIR))
        try:
            import hook_block_summary
        finally:
            sys.path.remove(str(SCRIPTS_DIR))
        assert hook_block_summary.BLOCK_SHAPES is hook_telemetry.BLOCK_SHAPES

    def test_timing_analyzer_imports_the_shared_classifier(self):
        import pipeline_timing_analyzer

        assert (
            pipeline_timing_analyzer.is_refusal_row
            is hook_telemetry.is_refusal_row
        )

    def test_no_reader_redefines_the_literal_set(self):
        """Derived from disk: grep the readers for a local re-definition."""
        readers = [
            SCRIPTS_DIR / "hook_perf_report.py",
            SCRIPTS_DIR / "hook_block_summary.py",
            LIB_DIR / "pipeline_timing_analyzer.py",
        ]
        for path in readers:
            source = path.read_text(encoding="utf-8")
            assert "BLOCK_SHAPES = frozenset" not in source, (
                f"{path.name} redefines BLOCK_SHAPES locally. Import it from "
                f"hook_telemetry instead."
            )


class TestRowsCarryAnExplicitRefusalBoolean:
    """AC: rows carry an explicit refusal boolean written from the shape.

    RED BEFORE: ``log_block_event`` wrote seven fields and none of them was
    ``refused``; ``row["refused"]`` raised ``KeyError``.

    The structural half of the fix. A reader that ignores an explicit field is
    making a visible choice; one that omits a filter is making an invisible
    omission.
    """

    @pytest.mark.parametrize(
        "shape,expected",
        [
            ("tuple", True),
            ("dict", True),
            ("exit2", True),
            ("legacy_recovery", True),
            ("mode_skip", False),
            ("allow", False),
            ("a_shape_invented_tomorrow", False),
        ],
    )
    def test_refused_is_derived_from_the_shape(self, tmp_path, shape, expected):
        hook_telemetry.log_block_event(
            hook_name="probe.py",
            decision_shape=shape,
            reason="r",
            start_dir=tmp_path,
        )
        log = tmp_path / hook_telemetry.LOG_FILE_RELATIVE
        row = json.loads(log.read_text(encoding="utf-8").strip())
        assert row["refused"] is expected, (
            f"decision_shape={shape!r} produced refused={row['refused']!r}"
        )
        # Boundary: the field must not replace the shape, only annotate it.
        assert row["decision_shape"] == shape

    def test_is_refusal_row_falls_back_to_shape_for_pre_1611_rows(self):
        """Historical rows have no ``refused`` field and must still classify.

        A fix that only worked on new rows would zero the entire historical
        record, which is worse than the over-count it replaced.
        """
        legacy_block = {"decision_shape": "tuple", "hook_name": "h.py"}
        legacy_skip = {"decision_shape": "mode_skip", "hook_name": "h.py"}
        assert hook_telemetry.is_refusal_row(legacy_block) is True
        assert hook_telemetry.is_refusal_row(legacy_skip) is False

    def test_non_bool_refused_field_does_not_assert_its_own_status(self):
        """A hand-edited row must not be able to launder itself."""
        forged = {"decision_shape": "mode_skip", "refused": "true"}
        assert hook_telemetry.is_refusal_row(forged) is False


class TestSummaryReportsRefusalsAndSkipsSeparately:
    """AC: ``hook_block_summary.py`` reports both figures, separately labelled.

    RED BEFORE: the script had no shape filter. ``total_events`` was the only
    figure, ``refusals`` / ``non_refusal_events`` did not exist in the JSON,
    and ``top_hooks`` mixed skips into a blocker ranking.
    """

    @pytest.fixture
    def project_dir(self, tmp_path: Path) -> Path:
        (tmp_path / ".claude" / "logs").mkdir(parents=True)
        return tmp_path

    def _write_log(self, project_dir: Path, rows) -> None:
        (project_dir / ".claude" / "logs" / "hook-blocks.jsonl").write_text(
            "\n".join(rows) + "\n", encoding="utf-8"
        )

    def test_reproducer_a_non_blocking_hook_is_not_ranked_as_a_blocker(
        self, project_dir
    ):
        """THE REPRODUCER. ``plan_mode_exit_detector.py`` cannot block.

        It contributed 287 ``mode_skip`` rows and was ranked fifth among
        blockers. It must not appear in a refusal ranking at all.
        """
        # Distinct reasons: the script dedups on (ts, hook_name, reason), so
        # five identical rows would collapse to one and the assertion below
        # would be measuring dedup rather than the shape filter.
        self._write_log(
            project_dir,
            [
                _row(
                    hook_name="plan_mode_exit_detector.py",
                    decision_shape="mode_skip",
                    reason=f"phase-e skip {i}",
                )
                for i in range(5)
            ]
            + [_row(hook_name="unified_pre_tool.py", decision_shape="tuple")],
        )
        result = _run_summary(["--json"], cwd=project_dir)
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)

        assert payload["refusals"] == 1
        assert payload["non_refusal_events"] == 5
        assert payload["total_events"] == 6, (
            "refusals + non_refusal_events must partition the rows exactly; "
            "no row may be dropped"
        )
        ranked = dict(payload["top_hooks"])
        assert "plan_mode_exit_detector.py" not in ranked, (
            "a hook that cannot block appears in the refusal ranking again"
        )
        assert ranked["unified_pre_tool.py"] == 1

    def test_negative_control_genuine_refusals_still_count(self, project_dir):
        """A filter that zeroes the real signal is worse than no filter."""
        self._write_log(
            project_dir,
            [
                _row(hook_name="a.py", decision_shape="tuple"),
                _row(hook_name="b.py", decision_shape="dict", reason="r2"),
                _row(hook_name="c.py", decision_shape="exit2", reason="r3"),
                _row(hook_name="d.py", decision_shape="legacy_recovery", reason="r4"),
            ],
        )
        payload = json.loads(_run_summary(["--json"], cwd=project_dir).stdout)
        assert payload["refusals"] == 4
        assert payload["non_refusal_events"] == 0

    def test_unknown_future_shape_is_reported_not_dropped(self, project_dir):
        """Fail visible, not closed."""
        self._write_log(
            project_dir,
            [_row(hook_name="future.py", decision_shape="quantum_veto")],
        )
        payload = json.loads(_run_summary(["--json"], cwd=project_dir).stdout)
        assert payload["refusals"] == 0
        assert payload["non_refusal_events"] == 1
        assert payload["by_decision_shape"]["quantum_veto"] == 1, (
            "an unrecognised shape vanished from the report entirely"
        )
        assert dict(payload["top_non_refusal_hooks"])["future.py"] == 1

    def test_text_output_labels_both_figures(self, project_dir):
        """The human-readable path must carry the distinction too."""
        self._write_log(
            project_dir,
            [
                _row(hook_name="skipper.py", decision_shape="mode_skip"),
                _row(hook_name="blocker.py", decision_shape="tuple"),
            ],
        )
        stdout = _run_summary([], cwd=project_dir).stdout
        assert "REFUSALS" in stdout
        assert "NON-REFUSAL" in stdout
        assert "not a refusal" in stdout, (
            "the by-shape table must mark which shapes are not refusals"
        )

    def test_explicit_refused_field_is_honoured_over_the_shape(
        self, project_dir
    ):
        """The structural half is load-bearing, not decorative."""
        self._write_log(
            project_dir,
            [_row(hook_name="x.py", decision_shape="tuple", refused=False)],
        )
        payload = json.loads(_run_summary(["--json"], cwd=project_dir).stdout)
        assert payload["refusals"] == 0
        assert payload["non_refusal_events"] == 1


class TestTimingAnalyzerFilters:
    """AC: ``pipeline_timing_analyzer.py`` filters.

    RED BEFORE: ``load_prompt_integrity_events`` admitted any row whose
    ``metadata.event_type`` started with ``prompt_integrity_``, regardless of
    shape, so a ``mode_skip`` block row counted as enforcement.
    """

    @staticmethod
    def _write(tmp_path: Path, rows) -> Path:
        path = tmp_path / "hook-blocks.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        return path

    def _pi_row(self, event_type: str, *, shape: str, eid: str) -> dict:
        return {
            "ts": "2026-08-22T00:00:00+00:00",
            "hook_name": "unified_pre_tool.py",
            "decision_shape": shape,
            "reason": "r",
            "metadata": {
                "event_type": event_type,
                "block_event_id": eid,
                "agent_type": "implementer",
                "timestamp": "2026-08-22T00:00:00+00:00",
            },
            "session_id": "",
            "cwd": "/tmp",
        }

    def test_block_row_with_a_skip_shape_is_not_counted_as_a_block(
        self, tmp_path
    ):
        import pipeline_timing_analyzer

        log = self._write(
            tmp_path,
            [self._pi_row("prompt_integrity_block", shape="mode_skip", eid="e1")],
        )
        assert pipeline_timing_analyzer.load_prompt_integrity_events(log) == [], (
            "a block-typed row carrying mode_skip was admitted as a block"
        )

    def test_negative_control_real_blocks_and_recoveries_survive(self, tmp_path):
        """The permitting arm — and the asymmetry, stated.

        Recovery rows record a subsequent ALLOW. They are admitted regardless
        of shape, because filtering them would delete the second half of every
        pair and silently zero the recovery-latency metric.
        """
        import pipeline_timing_analyzer

        log = self._write(
            tmp_path,
            [
                self._pi_row("prompt_integrity_block", shape="dict", eid="e1"),
                self._pi_row("prompt_integrity_recovery", shape="dict", eid="e1"),
                self._pi_row("prompt_integrity_recovery", shape="mode_skip", eid="e2"),
            ],
        )
        events = pipeline_timing_analyzer.load_prompt_integrity_events(log)
        types = [e["metadata"]["event_type"] for e in events]
        assert types.count("prompt_integrity_block") == 1
        assert types.count("prompt_integrity_recovery") == 2, (
            "recovery rows were filtered out; the pairing metric is now zero"
        )
        pairs, unpaired = (
            pipeline_timing_analyzer.extract_prompt_integrity_recoveries(events)
        )
        assert len(pairs) == 1
        assert unpaired == 0


class TestPlanGateRecordsItsRefusals:
    """AC: plan_gate's enforce path records by construction.

    RED BEFORE: driving the hook through either block path produced the deny
    envelope and ZERO telemetry rows. Measured directly, both paths, as a
    subprocess.

    Non-negotiable, asserted here: the emitted envelope must be UNCHANGED.
    A refusal that stopped refusing because it started recording would be a
    catastrophic trade, so the envelope is pinned field-by-field alongside the
    row assertion.
    """

    BIG_CONTENT = "x = 1\n" * 200  # over SIMPLE_EDIT_LINE_THRESHOLD

    def _drive(self, *, plan_text: "str | None", file_path: str = "src/f.py"):
        workdir = Path(tempfile.mkdtemp(prefix="plan_gate_1611_"))
        try:
            (workdir / ".git").mkdir()
            plans = workdir / ".claude" / "plans"
            plans.mkdir(parents=True)
            if plan_text is not None:
                (plans / "PLAN-t.md").write_text(plan_text, encoding="utf-8")

            env = dict(os.environ)
            env.pop("SKIP_PLAN_CHECK", None)
            env.pop("CLAUDE_SESSION_ID", None)
            proc = subprocess.run(
                [sys.executable, str(HOOKS_DIR / "plan_gate.py")],
                input=json.dumps(
                    {
                        "tool_name": "Write",
                        "tool_input": {
                            "file_path": file_path,
                            "content": self.BIG_CONTENT,
                        },
                        "session_id": "",
                    }
                ),
                capture_output=True,
                text=True,
                cwd=str(workdir),
                env=env,
                timeout=60,
            )
            log = workdir / ".claude" / "logs" / "hook-blocks.jsonl"
            rows = (
                [json.loads(x) for x in log.read_text().splitlines() if x.strip()]
                if log.exists()
                else []
            )
            return proc, rows
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def test_reproducer_no_plan_file_block_is_recorded(self):
        proc, rows = self._drive(plan_text=None)
        envelope = json.loads(proc.stdout)
        hso = envelope["hookSpecificOutput"]

        # The refusal still reaches Claude Code, byte-for-byte as before.
        assert hso["hookEventName"] == "PreToolUse"
        assert hso["permissionDecision"] == "block", (
            "plan_gate's emitted decision value changed. Whether 'block' is "
            "correct on a PreToolUse event is Issue #1589's question; "
            "changing it HERE alters live enforcement behaviour."
        )
        assert hso["permissionDecisionReason"] == "Plan gate: no plan file found"
        assert "REQUIRED NEXT ACTION" in envelope["systemMessage"]

        # ...and now it leaves a trace.
        assert len(rows) == 1, (
            f"expected exactly one telemetry row for one refusal, got {rows}"
        )
        assert rows[0]["hook_name"] == "plan_gate.py"
        assert rows[0]["decision_shape"] == "dict"
        assert rows[0]["refused"] is True
        assert rows[0]["reason"] == "Plan gate: no plan file found"

    def test_reproducer_invalid_plan_block_is_recorded(self):
        proc, rows = self._drive(plan_text="# Plan\n\nno required sections\n")
        hso = json.loads(proc.stdout)["hookSpecificOutput"]
        assert hso["permissionDecision"] == "block"
        assert hso["permissionDecisionReason"].startswith(
            "Plan gate: plan missing sections:"
        )
        assert len(rows) == 1
        assert rows[0]["refused"] is True
        assert rows[0]["decision_shape"] == "dict"

    @pytest.mark.parametrize(
        "name,plan_text,file_path",
        [
            (
                "valid_plan",
                "# P\n\n## WHY + SCOPE\nw\n\n## Existing Solutions\ne\n\n"
                "## Minimal Path\nm\n",
                "src/f.py",
            ),
            ("doc_file", None, "docs/notes.md"),
        ],
    )
    def test_permitting_arm_allows_still_record_nothing(
        self, name, plan_text, file_path
    ):
        """The recorder must DISCRIMINATE, not fire on every decision.

        Without this, a hook that logged a row on every call would satisfy
        the refusing arm above while making the log useless in the other
        direction — which is precisely the over-count half of this issue.
        """
        proc, rows = self._drive(plan_text=plan_text, file_path=file_path)
        hso = json.loads(proc.stdout)["hookSpecificOutput"]
        assert hso["permissionDecision"] == "allow", name
        assert rows == [], (
            f"the {name} ALLOW path wrote a telemetry row: {rows}. The "
            f"recorder is not discriminating."
        )


class TestPerfReportOutputIsUnchanged:
    """AC: ``hook_perf_report.py`` output is byte-identical after the refactor.

    Byte-identity is the claim, and it holds: if the refactor changed this
    reader's output, the refactor would be wrong. This is a lock, not a
    reproducer — it was green before and must stay green.

    What this does NOT establish, corrected after review: that the reader was
    "already correct". It was the only reader that HAD the shape filter, which
    is a different and weaker statement. Its ``block_count`` / ``b_ratio``
    columns are in fact structurally dead — no hook ever sets a block shape on
    a timing row — and the corpus below is SYNTHETIC precisely because no
    production writer can produce one. See
    ``TestPerfReportBlockColumnIsDead`` for the measurement and its controls.
    """

    def test_report_over_a_fixed_corpus_is_stable(self, tmp_path):
        # SYNTHETIC CORPUS. The ``tuple`` and ``dict`` rows below cannot occur
        # in a real hook_timings_*.jsonl file: measured across 408,254
        # production rows, zero carry a block shape, because
        # HookTimer.set_decision_shape has zero real call sites. They exist
        # here to exercise the CLASSIFIER after the constant was moved, and
        # must not be read as evidence that the block column runs.
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        rows = []
        for shape, n in (
            ("allow", 5),
            ("exception", 2),
            ("tuple", 3),
            ("dict", 1),
            ("mode_skip", 4),
        ):
            for i in range(n):
                rows.append(
                    {
                        "ts": f"2026-08-22T00:00:{i:02d}+00:00",
                        "hook": "probe.py",
                        "dur_ns": 1_000_000 + i,
                        "decision_shape": shape,
                        "schema_version": 1,
                    }
                )
        (log_dir / "hook_timings_2026-08-22.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
        )

        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "hook_perf_report.py"),
                "--start-dir",
                str(log_dir),
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        probe = payload["hooks"]["probe.py"]
        assert probe["allow_count"] == 5
        assert probe["block_count"] == 4, (
            "tuple + dict are refusals; mode_skip, allow and exception are "
            "not. The imported vocabulary must classify exactly as the "
            "in-file literal did. NOTE: 4 here is a property of the SYNTHETIC "
            "corpus above, not an observation about production, where this "
            "column is always 0."
        )

    def test_perf_report_shape_classification_matches_the_shared_constant(self):
        """Cross-validation, both directions — no third copy in the test."""
        sys.path.insert(0, str(SCRIPTS_DIR))
        try:
            import hook_perf_report
        finally:
            sys.path.remove(str(SCRIPTS_DIR))
        assert (
            hook_perf_report.BLOCK_SHAPES - hook_telemetry.BLOCK_SHAPES == set()
        )
        assert (
            hook_telemetry.BLOCK_SHAPES - hook_perf_report.BLOCK_SHAPES == set()
        )


class TestDecoratorSinkDidNotChangeExistingCallers:
    """The parameterised decorator must be a strict superset of the old one.

    ``block_event_decorator`` gained ``decision_shape`` and ``refusal_values``
    so ``plan_gate`` could fuse without its envelope changing. Both default to
    the pre-#1611 behaviour, so no existing caller moves. Measured here rather
    than asserted, because ``unified_pre_tool.py`` — the repo's largest
    refuser — is decorated by it and is under separate review (#1619).
    """

    def test_default_behaviour_is_unchanged(self, tmp_path):
        @hook_telemetry.block_event_decorator("legacy.py")
        def output_decision(decision, reason, **kwargs):
            return (decision, reason)

        log = tmp_path / hook_telemetry.LOG_FILE_RELATIVE
        cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            output_decision("allow", "ok")
            assert not log.exists(), "an allow wrote a row"
            output_decision("ask", "sure?")
            assert not log.exists(), (
                "the DEFAULT refusal vocabulary changed. 'ask' rows would "
                "newly appear for unified_pre_tool.py, which has 3 ask call "
                "sites — a live telemetry change outside this issue's scope."
            )
            output_decision("deny", "blocked because")
            rows = [
                json.loads(x) for x in log.read_text().splitlines() if x.strip()
            ]
        finally:
            os.chdir(cwd)

        assert len(rows) == 1
        assert rows[0]["decision_shape"] == "tuple", (
            "the default shape label changed; existing rows would be "
            "attributed to a different shape"
        )
        assert rows[0]["refused"] is True

    def test_opt_in_vocabulary_records_the_out_of_enum_value(self, tmp_path):
        """The plan_gate case: ``"block"`` on a PreToolUse event.

        Recorded because it IS a refusal in this hook's vocabulary. Whether
        that vocabulary is correct is #1589's question — refusing to record it
        would just restore the silent zero.
        """

        @hook_telemetry.block_event_decorator(
            "opt_in.py",
            decision_shape="dict",
            refusal_values=frozenset({"block"}),
        )
        def emit(decision, reason):
            return decision

        cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            emit("allow", "fine")
            emit("block", "nope")
            log = tmp_path / hook_telemetry.LOG_FILE_RELATIVE
            rows = [
                json.loads(x) for x in log.read_text().splitlines() if x.strip()
            ]
        finally:
            os.chdir(cwd)

        assert len(rows) == 1, "the allow was recorded, or the block was not"
        assert rows[0]["decision_shape"] == "dict"
        assert rows[0]["refused"] is True


class TestRecorderWrittenAllowsAreNotRefusals:
    """AC (remediation): the two readers agree about the 57 recovery rows.

    RED BEFORE: ``hook_telemetry.NON_REFUSAL_EVENT_TYPES`` did not exist and
    ``is_refusal_row`` had no event-type arm, so a ``prompt_integrity_recovery``
    row — an ALLOW, written through the refusal recorder on the allow path and
    therefore carrying ``decision_shape: "dict"`` and ``refused: true`` —
    classified as a REFUSAL. Measured on the live log at the time: 57 such
    rows, 57 of them counted as refusals by ``scripts/hook_block_summary.py``,
    which had just started asserting ``Top hooks by REFUSAL`` over the total.
    ``pipeline_timing_analyzer.py`` treated the same rows as a separate class.

    Two readers of one file, edited in one changeset, disagreeing about the
    same rows. The fix is one carve-out in the ONE classifier, not a second
    filter in the second reader.
    """

    RECOVERY = "prompt_integrity_recovery"

    def _recovery_row(self, **overrides) -> dict:
        row = {
            "ts": "2026-08-22T00:00:00+00:00",
            "hook_name": "unified_pre_tool.py",
            "decision_shape": "dict",
            "refused": True,
            "reason": "recovered",
            "metadata": {
                "event_type": self.RECOVERY,
                "block_event_id": "e1",
                "agent_type": "implementer",
            },
            "session_id": "",
            "cwd": "/tmp",
        }
        row.update(overrides)
        return row

    def test_the_carve_out_beats_both_the_shape_and_the_boolean(self):
        """THE REPRODUCER, at the classifier.

        The row wears BOTH refusal labels — a ``dict`` shape and an explicit
        ``refused: true`` — because the writer derives the boolean from the
        shape and the shape is what is wrong. The event type must win, or the
        already-written rows can never be reclassified.
        """
        row = self._recovery_row()
        assert row["decision_shape"] in hook_telemetry.BLOCK_SHAPES, (
            "premise: the row really does carry a refusal SHAPE"
        )
        assert row["refused"] is True, (
            "premise: the row really does carry an explicit refusal BOOLEAN"
        )
        assert hook_telemetry.is_refusal_row(row) is False, (
            "a prompt_integrity_recovery row — an ALLOW — classified as a "
            "REFUSAL. Every reader of the block log now over-counts by the "
            "number of recoveries."
        )

    def test_permitting_arm_a_genuine_block_row_still_counts(self):
        """The filter must not zero the real signal.

        Same hook, same shape, same boolean, same file — only the event type
        differs. Without this arm, a carve-out that dropped every
        ``prompt_integrity_*`` row would satisfy the refusing arm above while
        deleting the block half of every pair.
        """
        block = self._recovery_row(
            metadata={
                "event_type": "prompt_integrity_block",
                "block_event_id": "e1",
                "agent_type": "implementer",
            }
        )
        assert hook_telemetry.is_refusal_row(block) is True, (
            "a genuine prompt_integrity_block row stopped counting as a "
            "refusal; the carve-out is scoped too widely"
        )

    @pytest.mark.parametrize(
        "metadata",
        [
            {},
            {"event_type": ""},
            {"event_type": None},
            {"event_type": 7},
            {"event_type": "prompt_integrity_recovery_extended"},
            "not-a-dict",
            None,
        ],
    )
    def test_boundary_only_the_exact_event_type_is_carved_out(self, metadata):
        """One case past the boundary, in both directions.

        A prefix match would silently carve out future
        ``prompt_integrity_*`` types; a missing or malformed ``metadata`` must
        fall through to the shape rather than raise.
        """
        row = self._recovery_row(metadata=metadata)
        assert hook_telemetry.is_refusal_row(row) is True, (
            f"metadata={metadata!r} was carved out. Only the exact literal "
            f"membership of NON_REFUSAL_EVENT_TYPES may be."
        )

    def test_both_readers_classify_the_same_row_identically(self):
        """CROSS-VALIDATION: the two readers must not diverge again.

        Not two hardcoded expectations — the two real modules are asked about
        the same row and their answers compared to each other.
        """
        sys.path.insert(0, str(SCRIPTS_DIR))
        try:
            import hook_block_summary
        finally:
            sys.path.remove(str(SCRIPTS_DIR))
        import pipeline_timing_analyzer

        assert (
            hook_block_summary.is_refusal_row
            is pipeline_timing_analyzer.is_refusal_row
        ), (
            "the two readers no longer share one classifier, which is how "
            "they came to disagree about the same 57 rows"
        )
        row = self._recovery_row()
        assert (
            hook_block_summary._normalize_row(row)[
                hook_telemetry.REFUSED_FIELD
            ]
            is False
        ), "the summary reader still counts a recovery row as a refusal"

    def test_summary_end_to_end_excludes_recoveries_from_the_ranking(
        self, tmp_path
    ):
        """Verify the copy that EXECUTES: drive the real script."""
        (tmp_path / ".claude" / "logs").mkdir(parents=True)
        rows = [
            json.dumps(self._recovery_row(reason=f"recovered {i}"))
            for i in range(3)
        ] + [_row(hook_name="unified_pre_tool.py", decision_shape="tuple")]
        (tmp_path / ".claude" / "logs" / "hook-blocks.jsonl").write_text(
            "\n".join(rows) + "\n", encoding="utf-8"
        )
        payload = json.loads(_run_summary(["--json"], cwd=tmp_path).stdout)

        assert payload["refusals"] == 1, (
            f"expected only the tuple row to be a refusal, got "
            f"{payload['refusals']}"
        )
        assert payload["non_refusal_events"] == 3
        assert payload["total_events"] == 4, "the partition must stay exact"
        assert payload["non_refusal_event_types"] == [self.RECOVERY], (
            "the report must NAME what it excludes; an unnamed exclusion is "
            "the invisible omission this issue exists to remove"
        )

    def test_the_heading_names_its_exclusion(self, tmp_path):
        """The text path asserts REFUSAL positively — it must qualify it."""
        (tmp_path / ".claude" / "logs").mkdir(parents=True)
        (tmp_path / ".claude" / "logs" / "hook-blocks.jsonl").write_text(
            json.dumps(self._recovery_row()) + "\n", encoding="utf-8"
        )
        stdout = _run_summary([], cwd=tmp_path).stdout
        assert self.RECOVERY in stdout, (
            "the REFUSALS line does not say what it excludes, so a reader "
            "cannot tell the count is narrower than the shape set it names"
        )


class TestPlanGateRefusalsAreSeparableFromHonouredOnes:
    """AC (remediation): a plan_gate row records WHICH value it emitted.

    RED BEFORE: the recorded row carried ``hook_name``, ``decision_shape``,
    ``reason`` and ``refused`` — and ``metadata: {}``. Nothing on it recorded
    that the emitted ``permissionDecision`` was the out-of-enum ``"block"``
    rather than an honoured ``"deny"``, so a plan_gate row was byte-comparable
    to a genuine refusal from ``unified_pre_tool.py``.

    Why that is a defect and not a nicety: before #1611 plan_gate's refusals
    were an unknowable ZERO, which reads honestly as *no evidence*. Recording
    them without this metadata converts that into a confident positive count
    that may be counting nothing — a THIRD direction of error, in an issue
    about an instrument wrong in two.
    """

    def test_decorator_stamps_constant_metadata_on_refusals(self, tmp_path):
        @hook_telemetry.block_event_decorator(
            "m.py",
            decision_shape="dict",
            refusal_values=frozenset({"block"}),
            metadata={"permission_decision": "block", "honoured": "unverified"},
        )
        def emit(decision, reason):
            return decision

        cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            emit("allow", "fine")
            emit("block", "nope")
            rows = [
                json.loads(x)
                for x in (tmp_path / hook_telemetry.LOG_FILE_RELATIVE)
                .read_text()
                .splitlines()
                if x.strip()
            ]
        finally:
            os.chdir(cwd)

        assert len(rows) == 1, "the allow was recorded, or the block was not"
        assert rows[0]["metadata"]["permission_decision"] == "block"
        assert rows[0]["metadata"]["honoured"] == "unverified"

    def test_permitting_arm_metadata_defaults_to_empty_for_every_other_caller(
        self, tmp_path
    ):
        """A passthrough that changed the default would move every row."""

        @hook_telemetry.block_event_decorator("legacy.py")
        def emit(decision, reason):
            return decision

        cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            emit("deny", "nope")
            rows = [
                json.loads(x)
                for x in (tmp_path / hook_telemetry.LOG_FILE_RELATIVE)
                .read_text()
                .splitlines()
                if x.strip()
            ]
        finally:
            os.chdir(cwd)
        assert rows[0]["metadata"] == {}, (
            "an undecorated-for-metadata caller started emitting metadata; "
            "the passthrough is not additive"
        )

    def test_plan_gate_declares_the_divergence_at_its_call_site(self):
        """The hook must actually USE the passthrough, not merely permit it."""
        sys.path.insert(0, str(HOOKS_DIR))
        try:
            import plan_gate
        finally:
            sys.path.remove(str(HOOKS_DIR))
        meta = plan_gate.REFUSAL_METADATA
        assert meta["permission_decision"] == "block", (
            "the recorded metadata must name the value actually emitted"
        )
        assert meta["honoured"] == "unverified", (
            "claiming a refusal is honoured is exactly what #1589 has not "
            "yet established"
        )
        assert meta["issue"] == 1589, "the open question must be traceable"

    def test_end_to_end_a_real_refusal_row_carries_the_divergence(self):
        """Verify the copy that EXECUTES. Drive the hook as a subprocess."""
        workdir = Path(tempfile.mkdtemp(prefix="plan_gate_1611_meta_"))
        try:
            (workdir / ".git").mkdir()
            (workdir / ".claude" / "plans").mkdir(parents=True)
            env = dict(os.environ)
            env.pop("SKIP_PLAN_CHECK", None)
            env.pop("CLAUDE_SESSION_ID", None)
            proc = subprocess.run(
                [sys.executable, str(HOOKS_DIR / "plan_gate.py")],
                input=json.dumps(
                    {
                        "tool_name": "Write",
                        "tool_input": {
                            "file_path": "src/f.py",
                            "content": "x = 1\n" * 200,
                        },
                        "session_id": "",
                    }
                ),
                capture_output=True,
                text=True,
                cwd=str(workdir),
                env=env,
                timeout=60,
            )
            hso = json.loads(proc.stdout)["hookSpecificOutput"]
            log = workdir / ".claude" / "logs" / "hook-blocks.jsonl"
            rows = [
                json.loads(x)
                for x in log.read_text().splitlines()
                if x.strip()
            ]
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        # The envelope is still byte-for-byte the pre-#1611 one.
        assert hso["permissionDecision"] == "block"
        assert len(rows) == 1
        meta = rows[0]["metadata"]
        assert meta["permission_decision"] == hso["permissionDecision"], (
            "the row must record the value that actually crossed the wire, "
            "read from the same run"
        )
        assert meta["honoured"] == "unverified"
        assert meta["issue"] == 1589


class TestDecoratorConfigurationCannotBeSilentlyDiscarded:
    """AC (remediation): W-3. Idempotency must not swallow a DIFFERENT config.

    RED BEFORE: ``block_event_decorator`` returned an already-wrapped function
    unchanged with no signal, so a second decoration asking for a different
    ``decision_shape`` / ``refusal_values`` / ``metadata`` was discarded in
    silence and the caller believed a configuration was in effect that was
    not. And ``refusal_values`` was untyped: a bare ``"block"`` string made
    ``decision in values`` a SUBSTRING test, so a decision of ``"loc"`` would
    have recorded as a refusal.
    """

    def test_a_bare_string_refusal_value_is_refused(self):
        with pytest.raises(TypeError, match="SUBSTRING"):
            hook_telemetry.block_event_decorator("x.py", refusal_values="block")

    def test_the_substring_hazard_is_real_and_named(self):
        """Premise for the guard above: prove the hazard it prevents.

        A guard whose hazard is only asserted in prose is unfalsifiable.
        """
        assert "loc" in "block", (
            "premise: 'loc' is a substring of 'block', so an unvalidated "
            "string would have made a 'loc' decision record as a refusal"
        )

    def test_permitting_arm_a_frozenset_is_accepted(self, tmp_path):
        decorator = hook_telemetry.block_event_decorator(
            "x.py", refusal_values=frozenset({"block"})
        )
        assert callable(decorator), "a legitimate set-valued config was refused"

    def test_re_decoration_with_a_different_config_warns(self, capsys):
        def emit(decision, reason):
            return decision

        wrapped = hook_telemetry.block_event_decorator(
            "x.py", decision_shape="dict"
        )(emit)
        again = hook_telemetry.block_event_decorator(
            "x.py", decision_shape="tuple"
        )(wrapped)

        assert again is wrapped, "idempotency itself must be preserved"
        err = capsys.readouterr().err
        assert "DISCARDED" in err, (
            "a re-decoration asking for a DIFFERENT shape was swallowed in "
            "silence; the caller believes a config is live that is not"
        )

    def test_permitting_arm_identical_re_decoration_stays_quiet(self, capsys):
        """The warning must DISCRIMINATE, not fire on every re-decoration.

        Defensive double-imports re-apply the same configuration; warning on
        those would train the reader to ignore the whole class.
        """

        def emit(decision, reason):
            return decision

        wrapped = hook_telemetry.block_event_decorator(
            "x.py", decision_shape="dict"
        )(emit)
        capsys.readouterr()
        hook_telemetry.block_event_decorator("x.py", decision_shape="dict")(
            wrapped
        )
        assert capsys.readouterr().err == "", (
            "an identical re-decoration warned; the signal cries wolf"
        )


class TestTimingAnalyzerSurvivesAStaleInstall:
    """AC (remediation): W-1. The deployed siblings do not move together.

    RED BEFORE: ``from hook_telemetry import is_refusal_row`` was a hard
    import of a symbol added in this changeset, in a module that is DEPLOYED
    to ``.claude/lib/``. Measured on this machine at the time:
    ``.claude/lib/hook_telemetry.py`` dated 20 Aug against
    ``.claude/lib/pipeline_timing_analyzer.py`` dated 15 June — the exact skew
    that makes a hard import fail. ``plan_gate.py`` got a fallback; its
    sibling did not.

    The fallback is ``None``, not a local copy of the vocabulary. The first
    remediation draft DID write a local ``frozenset`` here and
    ``test_no_reader_redefines_the_literal_set`` went red at it — correctly.
    Two instruments disagreed and the guard was right: a second definition
    inside a reader is the defect, so the degradation is "apply no filter"
    (the pre-#1611 behaviour) rather than "apply a different rule".
    """

    def test_the_module_still_imports_when_the_symbol_is_absent(self, tmp_path):
        """Drive the real failure: import the module against a stub lib.

        A subprocess with a shadowing ``hook_telemetry`` that lacks the symbol
        reproduces a stale install exactly, rather than simulating one.
        """
        stub_dir = tmp_path / "stub"
        stub_dir.mkdir()
        (stub_dir / "hook_telemetry.py").write_text(
            '"""Pre-#1611 stale install: no is_refusal_row."""\n'
            "def log_block_event(**kwargs):\n    return None\n",
            encoding="utf-8",
        )
        log = tmp_path / "hook-blocks.jsonl"
        log.write_text(
            json.dumps(
                {
                    "ts": "2026-08-22T00:00:00+00:00",
                    "hook_name": "unified_pre_tool.py",
                    "decision_shape": "dict",
                    "reason": "r",
                    "metadata": {
                        "event_type": "prompt_integrity_block",
                        "block_event_id": "e1",
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        probe = (
            "import sys\n"
            f"sys.path.insert(0, {str(stub_dir)!r})\n"
            f"sys.path.insert(1, {str(LIB_DIR)!r})\n"
            "import hook_telemetry\n"
            "assert not hasattr(hook_telemetry, 'is_refusal_row'), "
            "'premise: the stub really is missing the symbol'\n"
            "import pipeline_timing_analyzer as p\n"
            "assert p.is_refusal_row is None, "
            "'the fallback must be None, never a local rule copy'\n"
            "from pathlib import Path\n"
            f"rows = p.load_prompt_integrity_events(Path({str(log)!r}))\n"
            "assert len(rows) == 1, "
            "'a stale install must degrade to the pre-#1611 unfiltered "
            "behaviour, not to dropping every row'\n"
            "print('OK')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"pipeline_timing_analyzer failed to import against a stale "
            f"hook_telemetry — the skew measured on this machine.\n"
            f"{result.stdout}\n{result.stderr}"
        )
        assert "OK" in result.stdout

    def test_permitting_arm_a_healthy_install_uses_the_shared_classifier(self):
        """The fallback must not shadow the real one when it is available.

        IDENTITY, not equality: a fallback that always won would pass every
        behavioural assertion while silently reverting the carve-out.
        """
        import pipeline_timing_analyzer

        assert (
            pipeline_timing_analyzer.is_refusal_row
            is hook_telemetry.is_refusal_row
        ), "the stale-install fallback is shadowing the shared classifier"


class TestPerfReportBlockColumnIsDead:
    """AC (remediation): the 'already correct' claim was false, two ways.

    Byte-identity of the perf report before and after the refactor is TRUE and
    was confirmed. The correctness claim built on top of it was not.

    Measured, with controls:

    * 408,254 rows across 33 ``hook_timings_*.jsonl`` files carry exactly
      ``exception`` / ``allow`` / ``exit_nonzero``. Rows matching
      ``BLOCK_SHAPES``: **0**. The counting probe was controlled — a synthetic
      ``tuple`` corpus counts 3/3, a synthetic ``allow`` corpus counts 0 — so
      the zero is a measurement, not a broken query.
    * ``HookTimer.set_decision_shape`` has **zero** real call sites across
      ``hooks/``; all 25 grep hits are the no-op fallback stub.

    So ``block_count`` and ``b_ratio`` are structurally 0 for every hook,
    always. This class locks the second measurement — the one a future change
    could silently invalidate — rather than the prose.
    """

    STUB = "def set_decision_shape(self, _): pass"

    @staticmethod
    def _real_call_sites(hooks_dir: Path) -> "list[str]":
        """Files with a real ``set_decision_shape`` CALL, stub defs excluded.

        Args:
            hooks_dir: Directory of hook scripts to scan.

        Returns:
            Sorted filenames containing at least one call.
        """
        import ast

        found = []
        for path in sorted(hooks_dir.glob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "set_decision_shape"
                ):
                    found.append(path.name)
                    break
        return sorted(set(found))

    def test_positive_control_the_scanner_finds_a_real_call(self, tmp_path):
        """Verify the instrument before trusting its zero."""
        (tmp_path / "synthetic_caller.py").write_text(
            "def main(timer):\n    timer.set_decision_shape('tuple')\n",
            encoding="utf-8",
        )
        assert self._real_call_sites(tmp_path) == ["synthetic_caller.py"], (
            "the scanner cannot see a real call, so its zero below would be "
            "an instrument failure rather than a finding"
        )

    def test_negative_control_the_scanner_ignores_the_stub_definition(
        self, tmp_path
    ):
        """The 25 live hits are all definitions. They must not count."""
        (tmp_path / "synthetic_stub.py").write_text(
            "class _T:\n    " + self.STUB + "\n", encoding="utf-8"
        )
        assert self._real_call_sites(tmp_path) == [], (
            "the no-op fallback DEFINITION was counted as a call; the live "
            "measurement would then read as 25 callers instead of 0"
        )

    def test_no_hook_ever_sets_a_block_shape_on_a_timing_row(self):
        """THE FINDING, locked. Goes red the day someone wires it up.

        That red is the CORRECT outcome: at that moment the perf report's
        block column stops being dead and the comment describing it has to be
        rewritten. This test is where that requirement is recorded.
        """
        callers = self._real_call_sites(HOOKS_DIR)
        assert callers == [], (
            f"{callers} now call HookTimer.set_decision_shape. The perf "
            f"report's block_count / b_ratio columns are no longer "
            f"structurally zero.\n"
            f"REQUIRED NEXT ACTION: update the BLOCK_SHAPES comment in "
            f"scripts/hook_perf_report.py, which currently states that no row "
            f"in the timing log carries a block shape, and re-measure the "
            f"live corpus."
        )

    def test_the_perf_report_comment_does_not_claim_a_live_column(self):
        """The prose must not describe a dead column as a live one.

        Locked because that exact mechanism — a confident sentence that stops
        the reader looking further — is what hid plan_gate for months.
        """
        source = (SCRIPTS_DIR / "hook_perf_report.py").read_text(
            encoding="utf-8"
        )
        assert 'Decision shapes that count as "block" outcomes' not in source, (
            "the comment states as live behaviour a thing measured to be "
            "structurally impossible. Say WOULD count, and say none does."
        )
        assert "Rows matching BLOCK_SHAPES: 0" in source, (
            "the measurement that makes the column dead is not recorded "
            "beside the constant, so the next reader has to re-derive it"
        )

    def test_the_synthetic_corpus_test_says_it_is_synthetic(self):
        """A fixture no production writer can produce must say so.

        ``test_report_over_a_fixed_corpus_is_stable`` asserts
        ``block_count == 4`` over rows carrying ``tuple`` and ``dict`` shapes.
        That corpus cannot occur in production, and unlabelled it makes the
        dead column look exercised.
        """
        source = Path(__file__).read_text(encoding="utf-8")
        marker = "SYNTHETIC CORPUS"
        assert marker in source, (
            f"the byte-identity lock's corpus is not labelled {marker!r}; a "
            f"reader would take block_count == 4 as evidence the column runs"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
