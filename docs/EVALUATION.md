---
covers:
  - plugins/autonomous-dev/commands/skill-eval.md
  - plugins/autonomous-dev/commands/improve.md
  - plugins/autonomous-dev/commands/retrospective.md
  - plugins/autonomous-dev/commands/autoresearch.md
  - plugins/autonomous-dev/agents/continuous-improvement-analyst.md
  - scripts/run_reviewer_benchmark.py
  - tests/benchmarks/reviewer/dataset.json
---

# Evaluation & Self-Improvement

autonomous-dev measures its own effectiveness and closes the loop: runtime data → weakness diagnosis → agent-prompt fix → benchmark verification → commit-or-revert. This is **Layer 4** of the three-layer architecture (see [ARCHITECTURE-OVERVIEW.md](ARCHITECTURE-OVERVIEW.md)).

## What Gets Measured

| Dimension | How | Where |
|-----------|-----|-------|
| **Agent output quality** | Labeled benchmark dataset, balanced-accuracy scoring | `tests/benchmarks/reviewer/dataset.json` |
| **Skill effectiveness** | Behavioral delta — model output with vs without the skill injected | `/skill-eval` |
| **Pipeline completeness** | Agents that ran vs agents required for the mode | `continuous-improvement-analyst` agent |
| **Gaming detection** | Test deletion, skip inflation, coverage narrowing across sessions | `continuous-improvement-analyst` |
| **Hook health** | Which hooks fired, which blocked, which regressed | session logs → `/improve` |
| **Per-category defect recall** | Does the reviewer catch bugs in category X? | `scripts/run_reviewer_benchmark.py` |

## Commands

### `/skill-eval` — Measure skill behavioral delta

```bash
/skill-eval                    # Full eval — all skills
/skill-eval --quick            # Fast mode (fewer prompts per skill)
/skill-eval --skill engineering-standards   # One skill only
/skill-eval --update           # Update baseline scores after confirmed improvement
```

**How it works**: For each skill, the runner sends the same prompt to the model twice — once with the skill injected in context, once without. The output delta is scored (deterministic structural assertions + LLM-as-judge semantic score). Negative delta > 0.10 means the skill is making output worse; positive delta = the skill adds value.

**Requires**: `OPENROUTER_API_KEY` environment variable. Skipped silently if unset.

**Sources**: `plugins/autonomous-dev/commands/skill-eval.md`, `scripts/skill-effectiveness-check.sh`, `plugins/autonomous-dev/lib/skill_evaluator.py`.

### Reviewer benchmark — Per-category agent accuracy

```bash
python3 scripts/run_reviewer_benchmark.py
# Outputs: balanced accuracy, FPR, FNR, per-category breakdown
```

**How it works**: 146+ labeled samples of real diffs (some buggy, some clean) are fed to the `reviewer` agent. Its APPROVE/REQUEST_CHANGES verdict is compared to the ground-truth label. Metrics tracked over time:

- **Balanced accuracy** — `(TPR + TNR) / 2`, unaffected by class imbalance
- **FPR** (False Positive Rate) — clean diffs flagged as problems (reviewer is too picky)
- **FNR** (False Negative Rate) — buggy diffs approved (reviewer missed it)
- **Per-category** — accuracy broken down by defect type (SQL injection, race condition, off-by-one, etc.)
- **Per-difficulty** — tier 0/1/2/3 difficulty

**Dataset**: `tests/benchmarks/reviewer/dataset.json`.

### `/improve` — Post-session quality analysis

```bash
/improve                       # Report findings
/improve --auto-file           # Create GitHub issues for systemic problems
```

**How it works**: The `continuous-improvement-analyst` agent reads the session activity log at `~/.claude/logs/activity/` and the session transcripts at `~/.claude/archive/conversations/`. It runs 15 quality checks:

1. **Pipeline completeness** — Did all required agents run for the mode?
2. **Gating integrity** — Were HARD GATEs bypassed?
3. **Gaming detection** — Tests deleted, skips added, coverage narrowed?
4. **Hook health** — Did hooks fire, did any regress?
5. **Agent output fidelity** — Did the coordinator truncate/summarize agent output before passing to the next stage?
6. **Known bypass patterns** — Patterns like "good enough" on failing tests
7. **Novel bypass detection** — Anomalies not in the known patterns file
8. **Deny-then-workaround detection** — Hook denies followed by equivalent Bash workarounds
9. **Doc-master verdict quality** — Did doc-master produce a real sweep or just update CHANGELOG?
10. **Extension health** — Silent crashes in `.claude/hooks/extensions/` hook extensions
11. **Pipeline timing analysis** — Ghost, wasteful, and slow agent invocations via `pipeline_timing_analyzer.py`
12. **Test lifecycle health** — Pruning candidates, untraced tests, tier imbalance
13. **Token efficiency analysis** — Tokens-per-word ratio and per-invocation budget
14. **Pipeline efficiency analysis** — Cross-run model tier recommendations and token trends via `pipeline_efficiency_analyzer.py`
15. **Validator diversity** — Jaccard overlap between reviewer and security-auditor findings; high overlap with ≥6 total findings emits `[VALIDATOR-OVERLAP]`

Findings are emitted as structured records (severity / root_cause_tag / title / evidence / file_refs / session_id / ts) to monthly JSONL files at `.claude/logs/findings/YYYY-MM.jsonl` via `cia_finding_store.append_finding()` (Issue #1200). Cross-session aggregation, deduplication, routing, and GitHub issue filing are handled by `/improve --auto-file` (the C3 promotion layer) — CIA does **not** file issues directly.

### `/retrospective` — Intent evolution detection

```bash
/retrospective                 # Analyze recent sessions for drift
```

**How it works**: The `retrospective-analyst` agent detects when the user's stated intent has evolved and proposes PROJECT.md or CLAUDE.md updates. Used after large multi-session efforts when the goal has shifted.

### `/autoresearch` — Closed-loop experimentation

```bash
/autoresearch --target skills/engineering-standards \
              --metric "clarity_score" \
              --iterations 5 \
              --min-improvement 0.05 \
              --dry-run
```

**How it works**: Hypothesis → modify (agent prompt, skill, etc.) → benchmark → commit on improvement, revert on regression. Iterates up to N times. Safe targets (agent prompts, skill files, benchmark data) run autonomously; unsafe targets (hooks, core code) file issues for human review.

## The Self-Improvement Closed Loop

```
  session logs
       ↓
  /improve → continuous-improvement-analyst (CIA, 15 checks)
       ↓
  findings emitted via append_finding() → .claude/logs/findings/YYYY-MM.jsonl
       ↓
  /improve --auto-file (C3 promotion layer — macro-promotion, Issue #1201)
       ↓
  collect_cia_findings() aggregates across 90-day window by root_cause_tag + title cluster
       ↓
  decide_promotions() applies macro-promotion gate per signal:
    volume+breadth gate: frequency >= 3 AND distinct_sessions >= 2
    error fast-path:     max_severity_label == "error" AND frequency >= 2
       ↓
       ├── gate crossed + open issue exists (same tag) → APPEND evidence comment
       ├── gate crossed + no matching open issue → CREATE new issue
       └── below threshold → HOLD (no side effect, surfaced in digest only)
       ↓
  format_digest() emits 5-section direction-guard digest every run
  (ACTIONS TAKEN / Recurrence-after-close / Match-rate /
   Findings-per-session / Error-without-other-channel)
       ↓
  benchmark run (before + after)
       ↓
       ├── improved? → commit, update baseline
       └── regressed? → revert
       ↓
  session logs (next cycle)
```

This is scheduled weekly via `/self-improve` (when invoked). Post-change hooks verify that agent prompt edits don't regress quality.

## Labeled Data

The reviewer benchmark dataset (`tests/benchmarks/reviewer/dataset.json`) is the ground truth for agent accuracy. Each sample has:

```json
{
  "id": "review-042",
  "diff": "...",
  "label": "BUG" | "CLEAN",
  "category": "sql_injection" | "race_condition" | ...,
  "difficulty": 0 | 1 | 2 | 3
}
```

New samples are added as real-world bugs are discovered. Balance is maintained (~50/50 BUG/CLEAN) to keep accuracy metrics meaningful.

## Running the Full Loop

```bash
# 1. Baseline
python3 scripts/run_reviewer_benchmark.py > /tmp/baseline.json

# 2. Make a change (e.g., tune reviewer.md)
# ... edit agents/reviewer.md ...

# 3. Re-benchmark
python3 scripts/run_reviewer_benchmark.py > /tmp/after.json

# 4. Diff
diff /tmp/baseline.json /tmp/after.json
```

Or let `/autoresearch` do all four steps autonomously.

## Related

- [ARCHITECTURE-OVERVIEW.md](ARCHITECTURE-OVERVIEW.md) — Layer 4 (self-improvement) in context
- [SESSION-ANALYTICS.md](SESSION-ANALYTICS.md) — the session data that feeds this loop
- [AGENTS.md](AGENTS.md) — `continuous-improvement-analyst`, `retrospective-analyst` agent specs
- [PROJECT.md](../.claude/PROJECT.md) — Layer 4 in the project scope

## Limitations

- **Skill-eval requires OPENROUTER_API_KEY**. Skipped silently if unset — you'll get a warning in `/implement` output.
- **Reviewer benchmark is English-only**. Multi-language bug patterns are not yet measured.
- **Closed-loop only runs on safe targets**. Hook or core-library changes are filed as issues, not auto-applied.
- **Benchmark dataset is small** (~146 samples). High variance between runs on rare categories. Use balanced accuracy and confidence intervals, not raw accuracy.

## History

The closed loop was introduced incrementally — Issues #579 through #584 cover the initial roadmap. See `docs/HARNESS-EVOLUTION.md` for release-over-release deltas.
