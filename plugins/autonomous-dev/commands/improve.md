---
name: improve
description: "Analyze recent sessions for improvement opportunities"
argument-hint: "[--auto-file] [--session <id>] [--date YYYY-MM-DD] [--trends]"
allowed-tools: [Task, Read, Bash, Glob, Grep]
user-invocable: true
user_facing: true
---

# Continuous Improvement Analysis

Analyze session activity logs to test whether autonomous-dev's automation is working correctly — hooks firing, pipeline executing, HARD GATEs enforcing.

## Usage

```bash
# Analyze today's sessions
/improve

# Also create GitHub issues for findings
/improve --auto-file

# Analyze specific session
/improve --session abc123

# Analyze specific date
/improve --date 2026-02-15

# Trend analysis across all sessions and CI issues
/improve --trends
```

## Arguments

- `--auto-file`: Create GitHub issues in `akaszubski/autonomous-dev` for detected problems (default: report only)
- `--session <id>`: Analyze a specific session ID
- `--date YYYY-MM-DD`: Analyze a specific date (default: today)
- `--trends`: Aggregate analysis across all auto-improvement issues and recent sessions. Identifies recurring patterns, worsening metrics, and systemic gaps.

## Implementation

### STEP 1: Load Activity Logs

Read session logs from `.claude/logs/activity/`:

```bash
# Find available logs
ls -la .claude/logs/activity/*.jsonl 2>/dev/null
```

If `--date` specified, load that date's log. Otherwise load today's.
If `--session` specified, filter entries to that session ID.

If no logs found, report: "No activity logs found. The session_activity_logger hook must be active to generate logs. Verify that your settings include all 4 hook layers (UserPromptSubmit, PreToolUse, PostToolUse, Stop)."

### STEP 2: Gather Ground Truth Context

Read autonomous-dev's source-of-truth documents to provide to the analyst:

1. **PROJECT.md**: Read `.claude/PROJECT.md` (or locate via `plugins/autonomous-dev/`) — extract GOALS and enforcement sections
2. **CLAUDE.md**: Read `CLAUDE.md` — extract Critical Rules section
3. **Known bypass patterns**: Read `plugins/autonomous-dev/config/known_bypass_patterns.json`
4. **Recent git history**: `git log --oneline -20`
5. **Repo context (registered hooks)**: Read the target repo's settings.json to calibrate expectations:
   ```bash
   cat .claude/settings.json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); hooks=d.get('hooks',{}); print(json.dumps({k: [h.get('command','') for h in v] if isinstance(v,list) else v for k,v in hooks.items()}))" 2>/dev/null || echo "{}"
   ```

### STEP 2.5: Skill Effectiveness Report

Scan skill baselines for weak, low-quality, or stale skills:

```bash
python3 -c "
import sys, json, os as _os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
    if _os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from skill_change_detector import get_weak_skills
from pathlib import Path

baselines_path = Path('tests/genai/skills/baselines/effectiveness.json')
weak = get_weak_skills(baselines_path, min_delta=0.10, min_pass_rate=0.80, stale_days=30)

if weak:
    print('WEAK SKILLS DETECTED:')
    for s in weak:
        print(f\"  - {s['skill_name']}: {s['reason']} (delta={s['delta']:+.2f}, pass_rate={s['pass_rate_with']:.2f})\")
else:
    print('All skills within acceptable thresholds.')
"
```

Pass the weak skill list to the CI analyst agent in STEP 3 so it can include skill health in its analysis. Skills flagged here are candidates for `/skill-eval --update` runs.

### STEP 2.7: Test Health Report

Run the TestLifecycleManager to generate a unified test health dashboard:

```bash
python3 -c "
import sys, os as _os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
    if _os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from test_lifecycle_manager import TestLifecycleManager
from pathlib import Path

manager = TestLifecycleManager(Path('.'))
report = manager.analyze()
print(manager.format_dashboard(report))
" 2>/dev/null || echo "Test health report unavailable"
```

Pass the dashboard output to the CI analyst agent in STEP 3 so it can include test lifecycle health in its analysis.

### STEP 2.8: Test Pruning Analysis (Weekly)

Run `/sweep --tests` analysis to surface prunable test candidates as part of the weekly cycle (root-cause Issue #908):

```bash
# Only run if last weekly run was ≥7 days ago (avoid redundant slow scans)
last_prune_log=$(find .claude/logs -name "sweep-tests-*.log" -mtime -7 2>/dev/null | head -1)
if [ -z "$last_prune_log" ]; then
    echo "Running weekly test pruning analysis (Issue #908)..."
    python3 -c "
import sys, os as _os
from datetime import datetime
from pathlib import Path
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', _os.path.expanduser('~/.claude/lib')):
    if _os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
try:
    from test_pruning_analyzer import TestPruningAnalyzer
    analyzer = TestPruningAnalyzer(Path('.'))
    report = analyzer.analyze()
    prunable = sum(1 for f in report.findings if f.prunable)
    total = len(report.findings)
    print(f'Pruning analysis: {prunable} prunable / {total} total findings across {report.files_scanned} files ({report.scan_duration_ms:.0f}ms)')
    # Persist weekly log for cycle tracking
    log_dir = Path('.claude/logs')
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d')
    (log_dir / f'sweep-tests-{stamp}.log').write_text(
        f'prunable={prunable} total={total} files={report.files_scanned} ms={report.scan_duration_ms:.0f}\\n'
    )
except Exception as e:
    print(f'Test pruning analysis unavailable: {e}')
" 2>&1
else
    echo "Test pruning analysis already run this week (last: $last_prune_log)"
fi
```

Pass the prunable-count summary to the CI analyst in STEP 3 so it can include test-pruning drift in its analysis. Drift target: prunable count should trend toward <500 (Issue #908 acceptance criterion).

### STEP 3: Analyze with Continuous Improvement Agent

Launch the `continuous-improvement-analyst` agent (Task tool, subagent_type: continuous-improvement-analyst) with:

1. **All 4 hook layer entries** from the logs:
   - `UserPromptSubmit` — command routing, workflow nudges
   - `PreToolUse` — tool validation, security checks
   - `PostToolUse` — error detection, activity logging
   - `Stop` — assistant output capture, session summary
2. **PROJECT.md** GOALS and enforcement sections
3. **CLAUDE.md** Critical Rules
4. **known_bypass_patterns.json** content
5. **Registered hooks context** from Step 2.5 (so the analyst can calibrate for consumer repos)
6. Instructions to run in full mode and scan for pipeline enforcement, gate integrity, suspicious agents, hook health, and rule bypasses

### STEP 4: Report Findings

Present the analysis report to the user with:
- Critical findings (broken enforcement, hook gaps, HARD GATE violations)
- Warnings (error handling gaps, command routing bypasses)
- Suggestions (optimization opportunities)
- Issue candidates (ready to file)

**TUNABLE THRESHOLDS**: The promotion thresholds applied below
(`PROMOTION_FREQUENCY_MIN=3`, `PROMOTION_DISTINCT_SESSIONS_MIN=2`,
`PROMOTION_ERROR_FREQUENCY_MIN=2`, `PROMOTION_WINDOW_DAYS=90`,
`MATCH_RATE_ALARM_THRESHOLD=0.50`, `CLOSED_LOOKBACK_DAYS=90`) live in
`plugins/autonomous-dev/lib/macro_promotion.py`. They are intentional and
documented (Sentry-style volume AND breadth, Google SRE dual-window
precedent). **Re-evaluation gate**: revisit these values after the user has
reviewed the first 2 digests. Do NOT change them inside individual /improve
runs.

### STEP 5: Auto-File Issues — Macro Promotion + Direction-Guard Digest (if --auto-file)

If `--auto-file` flag is set, run the macro-promotion coordinator. CIA
findings are NOT filed one-per-finding anymore — they are clustered cross-
session by `collect_cia_findings` (Issue #1200), gated by the macro-
promotion thresholds (Issue #1201), and either appended to an existing
matching open issue or created as a new issue. Non-promoted findings are
HELD (no side effect) and surfaced in the digest only.

**HARD GATE**:

> **FORBIDDEN** — one issue per finding / per-finding filing. Only
> threshold-crossing promoted clusters get issues.
>
> **REQUIRED** — Every /improve --auto-file run MUST end with a printed
> 5-section digest (ACTIONS TAKEN / Recurrence-after-close / Match-rate /
> Findings-per-session / Error-without-other-channel), persisted to
> `.claude/logs/aggregated_reports.jsonl`. The digest is anti-habituation:
> all 5 sections render even when their respective signal is empty.

Steps (run from the repo root resolved via `git rev-parse`):

1. Resolve the absolute findings directory (worktree safety, mirrors #1200):

   ```bash
   PROJECT_ROOT="$(git rev-parse --show-toplevel)"
   FINDINGS_DIR="${PROJECT_ROOT}/.claude/logs/findings"
   ```

2. Write the hook-contract context file BEFORE any `gh` call, in its OWN
   STANDALONE Bash tool call. The gh-filing hook expects this file to
   exist; create it once at the top of the step and clean it up at the
   end. **DO NOT REMOVE** — this contract is what marks the subsequent
   `gh issue create` calls as legitimate /improve side effects and is
   depended on by `unified_pre_tool.py`.

   **Prior-call ordering contract (Issue #1203)**: PreToolUse hook
   evaluates each Bash invocation BEFORE it runs. **FORBIDDEN: Do NOT
   bundle the context write and `gh issue create` into one Bash tool
   call** — the hook would not see the context at evaluation time and
   would block. The context write below MUST be its OWN Bash call,
   separate from the macro-promotion python3 block in Step 3 (which
   itself invokes `gh issue create`/`gh issue comment` via subprocess).

   ```bash
   python3 -c "
   import json
   from datetime import datetime, timezone
   with open('/tmp/autonomous_dev_cmd_context.json', 'w') as f:
       json.dump(
           {'command': 'improve', 'timestamp': datetime.now(timezone.utc).isoformat()},
           f,
       )
   "
   ```

3. Run the macro-promotion coordinator inline. The library does NO `gh`
   calls, NO filesystem writes — it returns a list of `PromotionDecision`
   records that this step executes.

   ```bash
   python3 - <<'PY'
   import json, os, sys, subprocess
   from datetime import datetime, timezone
   from pathlib import Path

   PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT",
                                       subprocess.check_output(
                                           ["git", "rev-parse", "--show-toplevel"],
                                           text=True).strip()))
   FINDINGS_DIR = PROJECT_ROOT / ".claude" / "logs" / "findings"

   for _p in ("plugins/autonomous-dev/lib", ".claude/lib"):
       full = PROJECT_ROOT / _p
       if full.is_dir():
           sys.path.insert(0, str(full))

   from runtime_data_aggregator import (
       AggregatedReport, collect_cia_findings, fetch_issues_with_label,
       persist_report,
   )
   from macro_promotion import (
       CLOSED_LOOKBACK_DAYS, PROMOTION_WINDOW_DAYS,
       build_digest, decide_promotions, detect_recurrence_after_close,
       format_digest,
   )

   # Collect cross-session CIA findings (Issue #1200 contract).
   signals, cia_health = collect_cia_findings(
       FINDINGS_DIR, window_days=PROMOTION_WINDOW_DAYS,
   )

   # Fetch open + recently-closed auto-improvement issues.
   open_issues, open_health = fetch_issues_with_label(state="open")
   closed_issues, closed_health = fetch_issues_with_label(
       state="closed", closed_within_days=CLOSED_LOOKBACK_DAYS,
   )

   decisions = decide_promotions(signals, open_issues)
   recurrence = detect_recurrence_after_close(signals, closed_issues)

   # Side effects per decision.
   create_failures = 0
   for d in decisions:
       # Check target_repo to determine if we should file the issue
       target_repo = d.signal.raw_data.get("target_repo", "autonomous-dev")
       if target_repo != "autonomous-dev":
           # Skip non-framework findings
           print(f"Skipping auto-file for target_repo={target_repo} (framework-only auto-file)")
           continue
       
       if d.route == "hold":
           continue
       evidence = (
           f"Cross-session CIA evidence ({datetime.now(timezone.utc).isoformat()}):\n"
           f"- root_cause_tag: {d.signal.signal_type}\n"
           f"- frequency (cluster size): {d.signal.frequency}\n"
           f"- distinct_sessions: {d.signal.raw_data.get('distinct_sessions', 0)}\n"
           f"- file_refs: "
           f"{', '.join(d.signal.raw_data.get('file_refs_union', [])) or '(none)'}\n"
           f"- max_severity_label: {d.signal.raw_data.get('max_severity_label', 'info')}\n"
       )
       if d.route == "append":
           # TOCTOU mitigation: re-classify immediately before each action to
           # catch a same-tag issue that opened/closed between fetch and now.
           from macro_promotion import classify_route
           fresh_open, _ = fetch_issues_with_label(state="open")
           route_now, matched_now = classify_route(d.signal, fresh_open)
           if route_now == "append" and matched_now is not None:
               target = matched_now
               rc = subprocess.call([
                   "gh", "issue", "comment", str(target),
                   "-R", "akaszubski/autonomous-dev",
                   "--body", evidence,
               ])
               if rc != 0:
                   create_failures += 1
           else:
               # FINDING-1 fix (Issue #1201 remediation): the originally
               # matched open issue has been closed in the window between
               # fetch and action. Pivot to CREATE instead of commenting on
               # a stale (closed) issue, which would silently route the
               # finding to a closed issue not surfaced in normal open views.
               tag = d.signal.signal_type
               max_label = d.signal.raw_data.get("max_severity_label", "info")
               title = f"[CI-{max_label}-{tag}] {d.signal.description}"[:200]
               rc = subprocess.call([
                   "gh", "issue", "create",
                   "-R", "akaszubski/autonomous-dev",
                   "--title", title,
                   "--label", "continuous-improvement,auto-improvement",
                   "--body", evidence,
               ])
               if rc != 0:
                   create_failures += 1
       elif d.route == "create":
           # TOCTOU mitigation before CREATE: re-fetch and re-classify; if a
           # matching open issue now exists, SWITCH to append.
           from macro_promotion import classify_route
           fresh_open, _ = fetch_issues_with_label(state="open")
           route_now, matched_now = classify_route(d.signal, fresh_open)
           if route_now == "append" and matched_now is not None:
               rc = subprocess.call([
                   "gh", "issue", "comment", str(matched_now),
                   "-R", "akaszubski/autonomous-dev",
                   "--body", evidence,
               ])
               if rc != 0:
                   create_failures += 1
               continue
           tag = d.signal.signal_type
           max_label = d.signal.raw_data.get("max_severity_label", "info")
           title = f"[CI-{max_label}-{tag}] {d.signal.description}"[:200]
           rc = subprocess.call([
               "gh", "issue", "create",
               "-R", "akaszubski/autonomous-dev",
               "--title", title,
               "--label", "continuous-improvement,auto-improvement",
               "--body", evidence,
           ])
           if rc != 0:
               create_failures += 1

   # Build digest. open_auto_improvement_count is the latest open count.
   open_count_for_digest = open_health.signal_count if open_health.status == "ok" else len(open_issues)
   # FINDING-2 fix (Issue #1201 remediation): summing per-cluster
   # distinct_sessions across all signals double-counts sessions that
   # appeared in multiple clusters. The aggregated signals do not preserve
   # the actual session-id set, so the union is not reconstructable from
   # this layer. Use max() as a lower-bound APPROXIMATION (the largest
   # single cluster's session count is guaranteed >= the union's lower
   # bound). This keeps the displayed findings-per-session ratio truthful
   # (slightly conservative) while still triggering the emission-failure
   # alarm correctly when the numerator is zero.
   distinct_sessions_observed = max(
       (int(s.raw_data.get("distinct_sessions", 0)) for s in signals),
       default=0,
   )
   counts = build_digest(
       decisions, recurrence,
       open_auto_improvement_count=open_count_for_digest,
       findings_observed=len(signals),
       distinct_sessions_observed=distinct_sessions_observed,
       create_failures=create_failures,
   )
   digest_body = format_digest(counts)

   # Print the digest body verbatim so the user sees it inline.
   print("\n=== /improve --auto-file digest (Issue #1201) ===")
   print(digest_body)
   print("=================================================\n")

   # Persist as a single JSONL line. We synthesize an AggregatedReport so
   # the persistence path mirrors aggregate().
   now = datetime.now(timezone.utc)
   report = AggregatedReport(
       signals=signals,
       source_health=[cia_health, open_health, closed_health],
       window_start=(now.replace(microsecond=0)).isoformat(),
       window_end=now.isoformat(),
       top_n=len(signals),
   )
   persist_report(report, PROJECT_ROOT / ".claude" / "logs" / "aggregated_reports.jsonl")

   # Issue #1204: clean up the hook-contract context file inside the same
   # Bash tool call (via this python3 block) so no standalone `rm` is needed.
   # The #1203 standalone-prior-write contract is preserved — the context
   # WRITE happened in its own Bash call (Step 2 above), and is consumed
   # here at the end of all `gh issue create`/`gh issue comment` side effects.
   try:
       (Path("/tmp/autonomous_dev_cmd_context.json")).unlink()
   except FileNotFoundError:
       pass
   PY
   ```

4. The hook-contract context file is cleaned up INSIDE the python3 block
   above. The `subprocess.call(["gh", "issue", ...])` invocations spawn
   `gh` directly (no Bash tool boundary involved), so the `rm` cleanup
   step that used to live here as a separate Bash invocation surfaced a
   user-visible permission prompt for no operational gain (Issue #1204).
   The python3 block ends with the context-file unlink so the cleanup runs
   in the same Bash tool call that drove the create/comment side effects.

5. Report appended/created issues with URLs. Surface any create_failures
   loudly (they appear in the digest's `Create failures:` line and reference
   `#1203`).

**Important**: Issues always go to `akaszubski/autonomous-dev` regardless of which repo this session ran in. The findings are about the automation tooling, not the user's project.

**Additional HARD GATE FORBIDDEN bullets**:
- FORBIDDEN: silently swallowing `gh issue create` failures. Surface them
  in the digest (`create_failures` field) and continue with remaining
  decisions.
- FORBIDDEN: filing a new issue without first re-classifying via
  `classify_route(signal, fresh_open_issues)` — TOCTOU mitigation against
  a race window between fetch and create.
- FORBIDDEN: changing the macro-promotion thresholds inside a single
  /improve run. They live in `macro_promotion.py` and are revisited per
  the re-evaluation gate documented in that module.

## What It Detects

| Category | Example | Severity |
|----------|---------|----------|
| Pipeline enforcement | Missing agents from pipeline | Critical |
| Gate integrity | Test failures when STEP 6 invoked, NotImplementedError stubs | Critical |
| Suspicious agent | Agent completed in <10s with zero file reads | Warning |
| Hook health | Missing hook layer, silent failures | Critical |
| Rule bypass | Raw edits instead of /implement, nudges ignored | Warning |

---

## Trends Mode (`--trends`)

If `--trends` is specified, skip the single-session analysis and do aggregate analysis instead.

### STEP T1: Gather all CI data

```bash
# All open auto-improvement issues
gh issue list -R akaszubski/autonomous-dev --label auto-improvement --state all --limit 100 --json number,title,state,createdAt,closedAt,labels

# Recent pipeline records
ls -t docs/sessions/*-pipeline.json | head -20
```

### STEP T2: Categorize issues by pattern

Group issues by their tag prefix (from CI analyst check types):
- `[INCOMPLETE]` — pipeline completeness failures
- `[GATE]` — gate violations
- `[GAMING]` — test gaming
- `[BYPASS]` / `[NEW-BYPASS]` — bypass patterns
- `[HOOK-REGRESSION]` — hook bugs
- `[DENY-WORKAROUND]` — enforcement holes
- `[DOC-SWEEP-*]` — doc-master sweep quality
- `[CIRCUMVENTION]` — constraint circumvention
- Other — uncategorized

### STEP T3: Identify trends

For each category, answer:
1. **Frequency**: How many times has this occurred? Is it increasing?
2. **Recurrence**: Same issue appearing after being closed? (fix didn't stick)
3. **Severity escalation**: Are findings getting worse over time?
4. **Batch vs single**: Does the pattern only appear in batch mode?
5. **Resolution rate**: What % of filed issues got closed (fixed)?

### STEP T4: Identify systemic gaps

Examine patterns that span categories:
- **Progressive degradation**: Later pipeline steps consistently weaker (context pressure)
- **Enforcement holes**: Same workaround pattern appearing repeatedly
- **Agent quality drift**: Specific agents consistently flagged (ghost invocations, shallow output)
- **Hook blind spots**: Types of violations that hooks never catch

### STEP T5: Report

```
TREND ANALYSIS
━━━━━━━━━━━━━━
Period: [date range of data analyzed]
Sessions analyzed: [N]
CI issues analyzed: [N open / N closed / N total]

TOP RECURRING PATTERNS:
1. [pattern] — [N occurrences] — [trend: improving/stable/worsening]
   Last seen: [date]. Resolution: [fixed/open/recurring]

2. [pattern] — [N occurrences] — [trend]
   ...

SYSTEMIC GAPS:
- [gap description] — [evidence across N sessions]

ENFORCEMENT PROMOTION CANDIDATES:
Rules that are currently nudges but should be hooks (recurring violations):
- [rule] — violated [N] times, suggest promoting to [hook type]

METRICS:
- Issue resolution rate: [N]%
- Mean time to close: [N] days
- Most common finding type: [type]
- Pipeline completion rate: [N]% (across recent sessions)
```

If `--auto-file` is also set, create a single summary issue. The
context-file WRITE MUST be a STANDALONE prior Bash call (#1203 contract);
the trailing `rm` cleanup MUST be chained onto the consuming
`gh issue create` via `;` so the single create-approval covers cleanup
(#1204).

First, as its OWN STANDALONE Bash call, write the hook-contract context
file:
```bash
python3 -c "
import json; from datetime import datetime, timezone
with open('/tmp/autonomous_dev_cmd_context.json', 'w') as f:
    json.dump({'command': 'improve', 'timestamp': datetime.now(timezone.utc).isoformat()}, f)
"
```

Then, as a separate Bash call, create the issue with the cleanup chained
via `;`:
```bash
gh issue create -R akaszubski/autonomous-dev   --title "[TRENDS] Aggregate analysis $(date +%Y-%m-%d)"   --label "auto-improvement,trends"   --body "{full trend report + **Plugin Version**: $(python3 -c "import sys,os;next((sys.path.insert(0,p) for p in ('.claude/lib','plugins/autonomous-dev/lib',os.path.expanduser('~/.claude/lib')) if os.path.isdir(p)),None);from version_reader import get_plugin_version;print(get_plugin_version())" 2>/dev/null || echo unknown)}"; rm -f /tmp/autonomous_dev_cmd_context.json
```
