# Baselines

Hook timing baseline snapshots used by the W0 baseline publisher (#1022)
and consumed by `tests/integration/test_baseline_artifact_present.py` to
guard against accidental deletion.

## Artifacts

Each baseline run produces three files. All three are committed.

| File                                  | Purpose                                        |
| ------------------------------------- | ---------------------------------------------- |
| `<YYYY-MM>-<label>.jsonl`             | Raw rows (one JSON object per hook invocation) |
| `<YYYY-MM>-<label>.summary.json`      | Aggregated stats with metadata (machine-readable, diffable) |
| `<YYYY-MM>-<label>.summary.md`        | Human-readable report (Top-5 slowest + Top-5 most-blocked) |

The `.jsonl` is the source of truth — the `.summary.*` files are derived
from it by `scripts/publish_hook_baseline.py` and can always be
regenerated.

## File naming

`YYYY-MM-<label>.jsonl`

Examples:
- `2026-05-pre-refactor.jsonl` — captured before W0 refactor.
- `2026-06-post-refactor.jsonl` — captured after a major change for A/B comparison.

## Schema

Each line is a single JSON object emitted by `hook_timing.HookTimer`:

```json
{
  "ts": "2026-05-07T15:03:00.842079+00:00",
  "hook": "auto_fix_docs.py",
  "dur_ns": 5510750,
  "decision_shape": "allow",
  "schema_version": 1
}
```

See `docs/research/W0_TELEMETRY.md` for the full schema specification.

## Publishing

After capturing a fresh baseline, run the publisher to produce the
`.summary.json` and `.summary.md` artifacts and (optionally) cross-post
to a tracking issue:

```bash
# Default: dry-run, write summary artifacts only.
python scripts/publish_hook_baseline.py \
    --jsonl baselines/2026-05-pre-refactor.jsonl

# Cross-post to GitHub issue #943 (idempotent via sentinel marker).
python scripts/publish_hook_baseline.py \
    --jsonl baselines/2026-05-pre-refactor.jsonl \
    --post --issue 943
```

The publisher reuses `scripts/hook_perf_report.py` for aggregation and
never modifies the source `.jsonl`. The `--post` codepath uses `gh api`
list-arg invocations only (no `shell=True`) and locates an existing
comment via the embedded sentinel `<!-- hook-timing-baseline:<label> -->`,
so re-running the publisher updates the existing comment in place.

## BASELINE_POLICY

Refresh triggers:

- Before any change that may alter hook latency (new lib, new
  validation, new dependency).
- After a confirmed regression — to capture the new "after" state.
- Quarterly, to track latency drift over time.
- **Pending**: Real-workday capture (#1022 AC1) — requires ≥4h active
  session with real tool traffic. Synthetic captures from
  `scripts/capture_baseline.py` are flagged `data_kind: synthetic-v0`
  and do NOT satisfy AC1.

The `data_kind` field in `<label>.summary.json` distinguishes synthetic
v0 baselines from real-workday captures. A baseline is classified
`synthetic-v0` when `row_count < 500` OR the timespan between the
earliest and latest rows is less than one hour.

## Refresh procedure

```bash
# Capture a fresh baseline (~5 invocations × 24 hooks = ~120 rows).
python scripts/capture_baseline.py \
    --output baselines/$(date -u +%Y-%m)-<label>.jsonl \
    --runs 5 \
    --verbose

# Verify it parses cleanly.
python -c "
import json
from pathlib import Path
rows = [json.loads(l) for l in Path('baselines/...').read_text().splitlines() if l]
print(f'{len(rows)} rows, {len({r[\"hook\"] for r in rows})} unique hooks')
"
```

## When to refresh

- Before any change that may alter hook latency (new lib, new validation,
  new dependency).
- After a confirmed regression — to capture the new "after" state.
- Quarterly, to track latency drift over time.

## Retention

Keep all historical baselines in this directory. They are small (~30 KB
each) and provide a longitudinal view of hook performance. There is no
deletion policy.
