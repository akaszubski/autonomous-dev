# Hook timing baseline — 2026-05-pre-refactor

<!-- hook-timing-baseline:2026-05-pre-refactor -->

| Field            | Value                                  |
| ---------------- | -------------------------------------- |
| captured_at      | 2026-05-07T15:03:00.842079+00:00       |
| generated_at     | 2026-05-07T21:26:12+00:00              |
| git_sha          | 827f493                                |
| platform         | darwin-arm64                           |
| schema_version   | 1                                      |
| source_jsonl     | baselines/2026-05-pre-refactor.jsonl   |
| row_count        | 119                                    |
| data_kind        | synthetic-v0                           |

> **Methodology note**: This baseline was produced by `scripts/capture_baseline.py` (synthetic stdin payloads, ~5 invocations × 24 hooks). It is a v0 reference for regression detection only — it is NOT a real-workday capture and does not satisfy AC1 of issue #1022. A real-workday refresh (≥4h active session, real tool traffic) is operational follow-up.

## Top-5 slowest hooks (by p95)

| Hook | Count | p50 ms | p95 ms | p99 ms |
|------|-------|--------|--------|--------|
| auto_test.py | 4 | 8895.648 | 8943.321 | 8943.321 |
| stop_quality_gate.py | 5 | 8756.254 | 8832.838 | 8832.838 |
| enforce_prunable_threshold.py | 5 | 60.905 | 68.516 | 68.516 |
| unified_session_tracker.py | 5 | 10.299 | 23.722 | 23.722 |
| validate_command_file_ops.py | 5 | 21.094 | 22.941 | 22.941 |

## Top-5 most-blocked gates (by block ratio)

| Hook | Allow | Block | Block ratio |
|------|-------|-------|-------------|
| auto_fix_docs.py | 5 | 0 | 0.0000 |
| auto_format.py | 5 | 0 | 0.0000 |
| auto_test.py | 0 | 0 | 0.0000 |
| conversation_archiver.py | 0 | 0 | 0.0000 |
| enforce_orchestrator.py | 0 | 0 | 0.0000 |

## Baseline policy

Refresh triggers:

- Before any change that may alter hook latency.
- After a confirmed regression.
- Quarterly, to track latency drift.
- **Pending**: Real-workday capture (#1022 AC1) — requires ≥4h active session traffic.

## Source

- Raw JSONL: [baselines/2026-05-pre-refactor.jsonl](2026-05-pre-refactor.jsonl)
- Aggregated JSON: [2026-05-pre-refactor.summary.json](2026-05-pre-refactor.summary.json)
- Generator: [scripts/publish_hook_baseline.py](../scripts/publish_hook_baseline.py)
