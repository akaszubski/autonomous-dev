# W0 Telemetry — Per-Hook Timing Observability

**Issue**: #1012
**Status**: Shipped
**Owner**: Pipeline maintainers

This document is the source of truth for the per-hook timing telemetry
introduced in milestone W0. It establishes a baseline for hook latency so
the W0 baseline publisher (#1022) can detect performance regressions and
operators can triage slow hooks.

## 1. Schema

Every hook invocation under `plugins/autonomous-dev/hooks/*.py` emits one
JSONL row to `~/.claude/logs/hook_timings_YYYY-MM-DD.jsonl` (UTC date).

Schema (stable, `schema_version: 1`):

| Field | Type | Description |
|-------|------|-------------|
| `ts` | string (ISO-8601, UTC) | Wall-clock timestamp at end of invocation. |
| `hook` | string | Hook filename (e.g. `"unified_pre_tool.py"`). |
| `dur_ns` | int | Wall-clock duration in nanoseconds (`time.perf_counter_ns`). |
| `decision_shape` | string | Outcome of the invocation; see table below. |
| `schema_version` | int | Schema version. Always `1` in W0. |

### `decision_shape` values

| Shape | Meaning |
|-------|---------|
| `allow` | Hook did not block the underlying decision. The default if the body did not call `set_decision_shape()`. |
| `tuple` | Hook returned a `("deny", reason)` tuple via `output_decision`. |
| `dict` | Hook returned `{"decision": "block", ...}` (UserPromptSubmit shape). |
| `exit2` | Hook called `sys.exit(2)` (pre-commit-style block). |
| `legacy_recovery` | Back-compat shim for the deprecated `hook_recovery` surface. |
| `mode_skip` | Session-mode enforcement gate skipped this hook. |
| `exception` | The hook body raised an unhandled exception. The exception still propagates. |

Readers MUST treat the field as opaque and tolerate unknown values —
new shapes may be added without a schema bump.

### File rotation

Logs rotate at UTC midnight by filename suffix (`hook_timings_2026-05-07.jsonl`).
Rotation is transparent to readers: globbing `hook_timings_*.jsonl` yields
all available days. There is no compression, no deletion, no retention
policy in W0 — that is deferred to a follow-up.

### On-disk path

- Default: `~/.claude/logs/hook_timings_YYYY-MM-DD.jsonl`
- Override: set `HOOK_TIMING_DIR=/some/path` (used by tests and the
  baseline capture script).

## 2. How to read the data

### Quick triage with `jq`

```bash
# Count rows per hook for today.
jq -r '.hook' ~/.claude/logs/hook_timings_$(date -u +%Y-%m-%d).jsonl \
  | sort | uniq -c | sort -rn

# Print rows where a hook took >100ms.
jq -c 'select(.dur_ns > 100_000_000)' \
  ~/.claude/logs/hook_timings_$(date -u +%Y-%m-%d).jsonl

# Top 5 slowest invocations.
jq -s 'sort_by(-.dur_ns) | .[:5] | .[]' \
  ~/.claude/logs/hook_timings_$(date -u +%Y-%m-%d).jsonl
```

### `scripts/hook_perf_report.py`

```bash
# Default: last day, top 20 by p95.
python scripts/hook_perf_report.py

# Last 6 hours, JSON output for piping.
python scripts/hook_perf_report.py --last 6h --json

# Filter by ISO timestamp.
python scripts/hook_perf_report.py --since 2026-05-07T00:00:00Z

# Top 5 only.
python scripts/hook_perf_report.py --top 5

# Read from a custom directory (e.g. baseline capture).
python scripts/hook_perf_report.py --start-dir baselines/
```

Expected output (text mode):

```
hook                                  count    p50ms    p95ms    p99ms   allow   block  b_ratio
-----------------------------------------------------------------------------------------------
unified_pre_tool.py                    412    2.314    8.103   12.502     411       1   0.0024
unified_prompt_validator.py            104    1.892    4.103    7.501     104       0   0.0000
auto_format.py                          39    1.103    3.501    4.892      39       0   0.0000
```

`b_ratio` is `block_count / max(1, allow_count + block_count)`. A hook
with no `allow`/`block` rows reports `0.0000`.

## 3. Disabling

Set `HOOK_TIMING_DISABLED=1` to disable all timing emission immediately
(rollback switch). Acceptable truthy values: any non-empty string except
`""`, `"0"`, `"false"`, `"no"`, `"off"`.

```bash
HOOK_TIMING_DISABLED=1 claude code  # disabled for one session
```

The fast-path is `O(1)` env var check + early return; disabled overhead
is below 1µs per invocation.

## 4. Forward compatibility

`schema_version: 1` is the contract. Future enhancements that change the
shape of existing fields MUST bump `schema_version`. Adding new optional
fields does not require a bump — readers MUST ignore unknown fields.

The W0 baseline publisher (#1022) consumes this schema; any breaking
change must be coordinated with the publisher.

## 5. Rollback

Three independent layers protect against regressions:

1. **Env switch**: `HOOK_TIMING_DISABLED=1` disables emission with no
   restart.
2. **Module bypass**: Each hook ships with a no-op `class HookTimer`
   fallback. If `hook_timing.py` is missing or broken, hooks load and
   run normally — they just don't emit timing.
3. **Revert**: The mass-edit at `plugins/autonomous-dev/hooks/*.py`
   `__main__` blocks is mechanical and can be reverted via
   `git revert <wrap commit>`.

## 6. Performance contract

- p50 overhead per invocation: **≤ +1 ms** vs no-op baseline.
- p99 overhead per invocation: **≤ +5 ms** vs no-op baseline.
- Disabled-mode overhead: **≤ +1 ms p99** (env-var check only).

Validated by `tests/perf/test_telemetry_overhead.py` (mark `perf`,
excluded from default test runs because shared CI is too noisy for
sub-millisecond budgets). Run on production-class hardware (M3 Ultra
Mac Studio, M4 Max).

## 7. Downstream consumers

Scripts that read the schema defined in Section 1:

| Consumer | Location | What it reads |
|----------|----------|---------------|
| `hook_perf_report.py` | `scripts/hook_perf_report.py` | Streams rows from `~/.claude/logs/hook_timings_*.jsonl`; computes p50/p95/p99 per hook. Used by both `capture_baseline.py` and `publish_hook_baseline.py` for aggregation. |
| `capture_baseline.py` | `scripts/capture_baseline.py` | Drives synthetic invocations; writes raw JSONL to `baselines/`. |
| `publish_hook_baseline.py` | `scripts/publish_hook_baseline.py` (Issue #1022) | Reads a baseline JSONL; emits `<stem>.summary.json` and `<stem>.summary.md`; optionally cross-posts to a GitHub issue. See `docs/SCRIPTS.md` for full usage. |

Any breaking change to the schema (new mandatory fields, removed fields, changed field types) MUST be coordinated with these consumers and MUST bump `schema_version`.

## 8. Out of scope

- Real-time dashboards / Grafana / Prometheus / OpenTelemetry exports.
- Cross-machine aggregation.
- Alerting / paging on regressions.
- Historical backfill from `.claude/logs/activity/*.jsonl`.

These are explicit non-goals for W0. The schema is intentionally minimal
so downstream consumers can add their own enrichment without coordinating
with this surface.
