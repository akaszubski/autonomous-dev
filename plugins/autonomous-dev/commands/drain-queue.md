---
name: drain-queue
description: "Autonomous queue drainer — picks the top /triage cluster, applies safety gates, drains via /implement --issues, pushes, deploys."
argument-hint: "[--dry-run]"
user-invocable: true
allowed-tools: [Bash, Read, SlashCommand, PushNotification]
---

# Drain Queue: Autonomous /triage → /implement → push → deploy wrapper

`/drain-queue` is a **thin orchestration wrapper around the existing executor**
(`/implement --issues`). It does NOT re-implement batch logic. It adds the
guardrails that `/implement --issues` does not have because the human picks
issues for `/implement`; `/drain-queue` picks them autonomously, so it needs an
extra safety layer.

> One invocation = one drain attempt. Recurrence is opt-in via the user-level
> `/loop` or `/schedule` skills. This command does NOT self-loop.

## Six guardrails

| # | Gate                                  | Threshold (module constant)      |
|---|---------------------------------------|----------------------------------|
| 1 | Daily drain-count + wall-clock budget | `MAX_DRAINS_PER_DAY=10`, `MAX_WALL_SECONDS_PER_DAY=14400` |
| 2 | Cluster severity                      | only `low`, `info` (`AUTO_DRAINABLE_SEVERITY`) |
| 3 | Hydrated cluster labels (tag gate)    | intersection with `HUMAN_GATE_TAGS` blocks |
| 4 | Cluster size                          | `MAX_CLUSTER_SIZE_AUTO_DRAINABLE=5` |
| 5 | Circuit breaker                       | 2 consecutive failures → 4h pause; 3 in 24h → 24h pause |
| 6 | Push / deploy gates                   | clean worktree + non-divergent remote required |

Module constants live in `plugins/autonomous-dev/lib/drain_queue_state.py`.
They are the single source of truth — never duplicate the value in the markdown.

## Implementation

Execute the 12 STEPs below in order. STEP 6 delegates to `/implement --issues N1,N2,...` (the existing batch executor at `commands/implement-batch.md`) — this command is a wrapper, not a new drainer. All Python helpers live in `plugins/autonomous-dev/lib/drain_runner.py` and `lib/drain_queue_state.py`. The markdown is the orchestration layer; Python helpers do the subprocess and state work.

```bash
# Each STEP in this command invokes the Python helpers below. STEP 1 example:
python3 -c "
import sys
sys.path.insert(0, 'plugins/autonomous-dev/lib')
from drain_runner import check_clean_worktree, default_branch
from drain_queue_state import PauseFlag, DrainBudget
from pathlib import Path
import os
repo = Path.cwd()
env = dict(os.environ)
# Pre-flight checks happen here; full 12-STEP playbook below
"
```

## ARGUMENTS

ARGUMENTS: {{ARGUMENTS}}

Recognized flags:

* `--dry-run` — run only the read-only pre-flight checks (worktree clean,
  default branch resolvable, budget within cap, pause flag absent) and report.
  No `gh`/`git` mutating calls; no state writes.

## STEP 1: Pre-flight checks

Run all four checks. **Any fail → STOP and emit notification.**

```bash
python3 - <<'PY'
import sys, time
from pathlib import Path
sys.path.insert(0, "plugins/autonomous-dev/lib")

from drain_queue_state import PauseFlag, DrainBudget
from drain_runner import check_clean_worktree, append_stop_notification, _build_env
from pipeline_state import get_legacy_sentinel_path

repo = Path.cwd().resolve()
env = _build_env(repo)
log_dir = repo / ".claude" / "local"
log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

# 1a. Working tree clean?
if not check_clean_worktree(repo, env):
    append_stop_notification("STEP 1: working tree not clean", log_dir)
    print("STOP: working tree not clean", flush=True)
    sys.exit(1)

# 1b. Universal bypass marker absent? (.claude/.bypass)
if (repo / ".claude" / ".bypass").exists():
    append_stop_notification("STEP 1: .claude/.bypass present — autonomous drain disabled", log_dir)
    print("STOP: .claude/.bypass present", flush=True)
    sys.exit(1)

# 1c. Pipeline-state sentinel fresh (within last 1h) → another /implement is in flight.
#     Uses the PER-REPO sentinel path (Issue #1206). DO NOT hardcode /tmp/...
sentinel = get_legacy_sentinel_path(repo)
if sentinel.exists():
    age = time.time() - sentinel.stat().st_mtime
    if age < 3600:
        append_stop_notification(
            f"STEP 1: /implement in-flight (sentinel age={int(age)}s)", log_dir
        )
        print(f"STOP: /implement in-flight (sentinel age={int(age)}s)", flush=True)
        sys.exit(1)

# 1d. PauseFlag active?
paused, reason = PauseFlag.load(repo).is_active()
if paused:
    append_stop_notification(f"STEP 1: pause flag active — {reason}", log_dir)
    print(f"STOP: pause flag active — {reason}", flush=True)
    sys.exit(1)

print("STEP 1: pre-flight passed", flush=True)
PY
```

If the snippet exited non-zero, emit a `PushNotification:` tool line based on
the stop reason just appended to `.claude/local/drain_notifications.jsonl` and
exit `/drain-queue`.

## STEP 2: Budget check (drain count + wall-clock)

```bash
python3 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, "plugins/autonomous-dev/lib")
from drain_queue_state import DrainBudget
from drain_runner import append_stop_notification

repo = Path.cwd().resolve()
log_dir = repo / ".claude" / "local"

budget = DrainBudget.load(repo)
blocked, reason = budget.check_or_block()
if blocked:
    append_stop_notification(f"STEP 2: daily budget — {reason}", log_dir)
    print(f"STOP: daily budget — {reason}", flush=True)
    sys.exit(1)
print(f"STEP 2: budget OK — today {budget.today_drains} drains, "
      f"{budget.today_wall_seconds:.0f}s used", flush=True)
PY
```

On STOP, emit `PushNotification:` and exit.

## STEP 3: Run `/triage --auto-improvement --json`

Use the analyzer's JSON output and select the top cluster by `rank_score`.

```bash
TRIAGE_JSON=$(python3 -m issue_triage_analyzer --auto-improvement --json 2>/dev/null || \
              python3 plugins/autonomous-dev/lib/issue_triage_analyzer.py --auto-improvement --json)
echo "$TRIAGE_JSON" > .claude/local/last_triage.json
```

If the JSON array is empty:

```bash
python3 - <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, "plugins/autonomous-dev/lib")
from drain_runner import append_stop_notification

data = json.loads(Path(".claude/local/last_triage.json").read_text())
if not data:
    append_stop_notification("STEP 3: queue drained completely", Path(".claude/local"))
    print("STOP: queue drained completely", flush=True)
    sys.exit(0)
PY
```

Note: queue-empty exits **zero** (success). Other STOPs exit non-zero.

## STEP 3.5: Hydrate cluster labels

`TriageFinding` has no `labels` field (v1 limitation). Hydrate from `gh issue
view` for each issue in the selected cluster (≤5 calls per cluster):

```bash
python3 - <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, "plugins/autonomous-dev/lib")
from drain_runner import hydrate_issue_labels, _build_env

repo = Path.cwd().resolve()
env = _build_env(repo)
data = json.loads(Path(".claude/local/last_triage.json").read_text())
cluster = data[0]  # top by rank_score
labels: set[str] = set()
for n in cluster["issue_numbers"]:
    labels.update(hydrate_issue_labels(int(n), repo, env))
Path(".claude/local/cluster_labels.json").write_text(json.dumps(sorted(labels)))
print(f"STEP 3.5: hydrated {len(labels)} labels across "
      f"{len(cluster['issue_numbers'])} issues", flush=True)
PY
```

`hydrate_issue_labels` returns `[]` on network or `gh` errors, so the gate
falls back to severity-only without crashing the drain.

## STEP 3.6: Write drain-pending marker (durability gate)

Once a cluster has been selected and labels hydrated, write the
`drain_pending.json` marker so the `unified_pre_tool.py` commit gate can
enforce `Closes #N` on every subsequent `git commit` invocation. This is the
hard floor that prevents the autonomous loop from freelancing a commit that
does not reference any cluster issue (the 2026-06-15T18:06Z failure mode that
motivated the durability plan).

The marker is cleared at STEP 12.5 only after post-push state=CLOSED
verification succeeds. **The hook NEVER consults the marker's TTL** — long
`/implement` runs (2h+ observed) MUST remain covered.

```bash
python3 - <<'PY'
import json, os, sys
from pathlib import Path
sys.path.insert(0, "plugins/autonomous-dev/lib")
from drain_pending import DrainPendingMarker

selected = json.loads(Path(".claude/local/selected_cluster.json").read_text())
DrainPendingMarker.write(
    issues=[int(n) for n in selected["issue_numbers"]],
    cluster_tag=selected["root_cause_tag"],
    session_id=os.environ.get("CLAUDE_SESSION_ID", "unknown"),
)
print(
    f"STEP 3.6: drain-pending marker written for "
    f"cluster {selected['root_cause_tag']} issues={list(selected['issue_numbers'])}",
    flush=True,
)
PY
```

## STEP 4: Safety gates (severity / tag / size / confidence / skip)

Apply gates in priority order. The first failing gate either STOPs or signals
a SKIP-to-next-cluster (3-attempt budget). Per ADR-002 Phase C (Issue #1291),
``confidence_gate`` (threshold 0.80) is the autonomy decision: severity remains
in the order for ranking/impact-tier reporting, but confidence is what gates
autonomous handling.

```bash
python3 - <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, "plugins/autonomous-dev/lib")
from drain_queue_state import evaluate_cluster_gates, skip_gate
from drain_runner import append_stop_notification

repo = Path.cwd().resolve()
log_dir = repo / ".claude" / "local"
clusters = json.loads(Path(".claude/local/last_triage.json").read_text())
labels = frozenset(json.loads(Path(".claude/local/cluster_labels.json").read_text()))

# v1 evaluates ONLY the top cluster (clusters[0]). Multi-attempt iteration
# across clusters[1:3] is deferred to v2 — the surrounding markdown only
# re-runs STEP 3.5 (hydrate labels) for a single cluster per run, so an
# enumerate(clusters[:3]) loop here would either re-evaluate the same
# labels (dead iterations) or require a coordinator-level re-hydration step
# that v1 does not have. Evaluate clusters[0] directly.
if not clusters:
    append_stop_notification("STEP 4: no clusters available", log_dir)
    print("STOP: no clusters available", flush=True)
    sys.exit(1)

cluster = clusters[0]

# Soft skip ("blocked"/"waiting") → v1 STOP. v2 will try clusters[1], clusters[2].
skip, skip_reason = skip_gate(labels)
if skip:
    append_stop_notification(
        f"STEP 4: top cluster has soft-skip label ({skip_reason}) — v1: single-attempt",
        log_dir,
    )
    print(f"STOP: soft-skip on top cluster ({skip_reason}) — v1 single-attempt",
          flush=True)
    sys.exit(1)

verdict, reason = evaluate_cluster_gates(
    cluster_severity=cluster["severity"],
    cluster_size=cluster["cluster_size"],
    cluster_labels=labels,
    cluster_confidence=float(cluster.get("confidence", 0.0)),
)
if verdict != "pass":
    append_stop_notification(f"STEP 4: gate stop — {reason}", log_dir)
    print(f"STOP: gate stop — {reason}", flush=True)
    sys.exit(1)

selected = cluster
Path(".claude/local/selected_cluster.json").write_text(json.dumps(selected))
print(f"STEP 4: selected cluster {selected['root_cause_tag']}#"
      f"{selected['sub_cluster_id']} "
      f"({selected['cluster_size']} issues, severity={selected['severity']})",
      flush=True)
PY
```

## STEP 5: Plan resolution

Search `.claude/plans/` (last 90 days) for a pre-validated plan that matches
the cluster theme:

```bash
python3 - <<'PY'
import json, subprocess, sys, time
from pathlib import Path

repo = Path.cwd().resolve()
cluster = json.loads(Path(".claude/local/selected_cluster.json").read_text())
keywords = [w.lower() for t in cluster["issue_titles"] for w in t.split() if len(w) > 3]
plans = sorted((repo / ".claude" / "plans").glob("*.md"))
cutoff = time.time() - 90 * 86400
found = None
for p in plans:
    if p.stat().st_mtime < cutoff:
        continue
    content = p.read_text(errors="ignore").lower()
    if "verdict: proceed" not in content:
        continue
    hits = sum(1 for k in keywords if k in content)
    if hits >= 3:
        found = p
        break
if found:
    print(f"STEP 5: pre-validated plan found at {found}", flush=True)
else:
    print(f"STEP 5: no pre-validated plan — will invoke /plan in STEP 6",
          flush=True)
    Path(".claude/local/needs_plan.flag").touch()
PY
```

If the `needs_plan.flag` was touched, invoke `/plan` via the SlashCommand tool
**before** STEP 6. Pass the cluster context. If `/plan` exits non-zero, STOP
with `append_stop_notification("STEP 5: /plan failed")`.

## STEP 6: Invoke `/implement --issues N1,N2,...` (the actual drainer)

This is where the batch executor at `commands/implement-batch.md` does the work.
`/drain-queue` does NOT re-implement batch logic — it delegates.

**Runtime detection**: Two execution paths exist (see issue #1258):
- **CI watchdog path** (GitHub Actions with `claude-code-action@beta`): SlashCommand tool is available.
- **Cloud-session path** (scheduled cron): SlashCommand is NOT available — must inline dispatch via Agent tool.

```bash
python3 - <<'PY'
import json, time, sys
from pathlib import Path
cluster = json.loads(Path(".claude/local/selected_cluster.json").read_text())
issues = ",".join(str(n) for n in cluster["issue_numbers"])
Path(".claude/local/drain_t0.txt").write_text(str(time.time()))
print(f"STEP 6: invoking /implement --issues {issues}", flush=True)
PY
```

### Path 1: CI watchdog (SlashCommand available)

If running in GitHub Actions with `claude-code-action@beta`, emit a SlashCommand tool line:

```
SlashCommand: /implement --issues <N1,N2,...>
```

### Path 2: Cloud-session (no SlashCommand)

If running in cloud-session cron, inline the `/implement --light` coordinator dispatch sequence via Agent tool:

1. **Alignment validation**: Invoke the `alignment-validator` agent to ensure PROJECT.md consistency.
2. **Planner**: Invoke the `planner` agent to create the implementation plan.
3. **Implementer**: Invoke the `implementer` agent to execute the plan.
4. **Spec-validator**: Invoke the `spec-validator` agent to verify requirements.
5. **Test-master**: Invoke the `test-master` agent to validate tests.
6. **Doc-master**: Invoke the `doc-master` agent to update documentation if needed.

Each Agent invocation passes the issue numbers and batch context forward. The sequence mirrors `/implement --light` step order.

Record the wall-seconds elapsed for STEP 12's budget accrual.

## STEP 6.5: Pre-push commit-message verification (`Closes #N`)

After `/implement` returns control, verify that EVERY pending commit on
`HEAD..origin/master` references at least one cluster issue via
`Closes #N` / `Fixes #N`. This is the second hard gate (the first is the
hook-level block in STEP 3.6's marker). If `/implement` produced a commit
without `Closes #N`, this STEP STOPs before push so the dirty commit cannot
leak to origin.

```bash
python3 - <<'PY'
import json, re, subprocess, sys
from pathlib import Path
sys.path.insert(0, "plugins/autonomous-dev/lib")
from drain_runner import _build_env, append_stop_notification

repo = Path.cwd().resolve()
env = _build_env(repo)
log_dir = repo / ".claude" / "local"
cluster = json.loads(Path(".claude/local/selected_cluster.json").read_text())
cluster_issues = set(int(n) for n in cluster["issue_numbers"])

r = subprocess.run(
    ["git", "log", "--pretty=format:%B", "origin/master..HEAD"],
    cwd=str(repo), env=env, capture_output=True, text=True, check=False,
)
if r.returncode != 0:
    append_stop_notification(
        f"STEP 6.5: git log failed: {r.stderr.strip()}", log_dir
    )
    print(f"STOP: git log failed: {r.stderr.strip()}", flush=True)
    sys.exit(1)

text = r.stdout or ""
refs = set(int(m.group(1)) for m in re.finditer(
    r"(?:Closes|Fixes)\s+#(\d+)", text, re.IGNORECASE
))
if not (refs & cluster_issues):
    append_stop_notification(
        f"STEP 6.5: no pending commit references any cluster issue "
        f"{sorted(cluster_issues)}; got refs={sorted(refs) or 'none'}",
        log_dir,
    )
    print(
        f"STOP STEP 6.5: pending commits do not reference any cluster issue "
        f"({sorted(cluster_issues)}); got refs={sorted(refs) or 'none'}",
        flush=True,
    )
    sys.exit(1)
print(
    f"STEP 6.5: commit-message verification passed — refs={sorted(refs)} "
    f"intersect cluster={sorted(cluster_issues)}",
    flush=True,
)
PY
```

## STEP 7: Verify drain succeeded

```bash
python3 - <<'PY'
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, "plugins/autonomous-dev/lib")
from drain_queue_state import CircuitBreaker
from drain_runner import append_stop_notification, _build_env

repo = Path.cwd().resolve()
env = _build_env(repo)
log_dir = repo / ".claude" / "local"
cluster = json.loads(Path(".claude/local/selected_cluster.json").read_text())

# Per-issue verification: closed via gh.
unclosed = []
for n in cluster["issue_numbers"]:
    r = subprocess.run(
        ["gh", "issue", "view", str(n), "--json", "state", "--jq", ".state"],
        cwd=str(repo), env=env, capture_output=True, text=True, check=False,
    )
    if r.returncode != 0 or r.stdout.strip().upper() != "CLOSED":
        unclosed.append(n)

if unclosed:
    CircuitBreaker.load(repo).record_failure()
    append_stop_notification(
        f"STEP 7: drain did not close {unclosed}", log_dir
    )
    print(f"STOP: drain did not close {unclosed}", flush=True)
    sys.exit(1)
print("STEP 7: all cluster issues closed", flush=True)
PY
```

## STEP 8: Push gate

```bash
python3 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, "plugins/autonomous-dev/lib")
from drain_runner import (
    check_clean_worktree, default_branch, fetch_remote,
    remote_diverged, append_stop_notification, _build_env,
)

repo = Path.cwd().resolve()
env = _build_env(repo)
log_dir = repo / ".claude" / "local"

if not check_clean_worktree(repo, env):
    append_stop_notification("STEP 8: worktree dirty after drain", log_dir)
    print("STOP: worktree dirty", flush=True)
    sys.exit(1)

branch = default_branch(repo, env)
Path(".claude/local/default_branch.txt").write_text(branch)

if not fetch_remote(branch, repo, env):
    append_stop_notification(f"STEP 8: git fetch failed for {branch}", log_dir)
    print(f"STOP: git fetch failed for {branch}", flush=True)
    sys.exit(1)

if remote_diverged(branch, repo, env):
    append_stop_notification(
        f"STEP 8: remote diverged on {branch}, manual merge needed", log_dir
    )
    print(f"STOP: remote diverged on {branch}", flush=True)
    sys.exit(1)

print(f"STEP 8: push gate passed (branch={branch})", flush=True)
PY
```

## STEP 9: Push

```bash
python3 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, "plugins/autonomous-dev/lib")
from drain_queue_state import CircuitBreaker
from drain_runner import push_to_default_branch, append_stop_notification, _build_env

repo = Path.cwd().resolve()
env = _build_env(repo)
log_dir = repo / ".claude" / "local"
branch = Path(".claude/local/default_branch.txt").read_text().strip()

if not push_to_default_branch(branch, repo, env):
    CircuitBreaker.load(repo).record_failure()
    append_stop_notification(f"STEP 9: git push to {branch} failed", log_dir)
    print(f"STOP: git push to {branch} failed", flush=True)
    sys.exit(1)
print(f"STEP 9: pushed to origin/{branch}", flush=True)
PY
```

## STEP 10: Deploy gate + deploy

Skip deploy when no files under `hooks/`, `lib/`, `commands/`, `agents/` (or
their `plugins/autonomous-dev/...` variants) changed.

```bash
python3 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, "plugins/autonomous-dev/lib")
from drain_runner import relevant_files_changed, invoke_deploy_all, _build_env

repo = Path.cwd().resolve()
env = _build_env(repo)

if not relevant_files_changed(repo, env):
    print("STEP 10: no functional files changed, skipping deploy", flush=True)
    sys.exit(0)

if not invoke_deploy_all(repo, env, extra_args=("--skip-validate",)):
    print("WARN: deploy-all.sh failed (non-fatal for drain success)", flush=True)
PY
```

Deploy failure is logged but does NOT trigger the circuit breaker — the drain
itself succeeded, and rolling back closed issues is worse than a stale deploy.

## STEP 11: Continuous improvement

Emit a SlashCommand tool line to invoke the improvement loop:

```
SlashCommand: /improve --auto-file
```

This macro-promotes new findings and may file new auto-improvement issues that
the next `/drain-queue` invocation can pick up.

## STEP 12: Log + exit

```bash
python3 - <<'PY'
import json, time, sys
from pathlib import Path
sys.path.insert(0, "plugins/autonomous-dev/lib")
from drain_queue_state import DrainBudget, CircuitBreaker, DrainHistory

repo = Path.cwd().resolve()
t0 = float(Path(".claude/local/drain_t0.txt").read_text())
elapsed = time.time() - t0
cluster = json.loads(Path(".claude/local/selected_cluster.json").read_text())

CircuitBreaker.load(repo).record_success()
DrainBudget.load(repo).add(elapsed)
# revert_status="pending" marks this drain as a candidate for the auto-revert checker (Issue #1292, gated on #1290 metrics)
DrainHistory.load(repo).append({
    "outcome": "success",
    "cluster_id": f"{cluster['root_cause_tag']}#{cluster['sub_cluster_id']}",
    "issue_numbers": list(cluster["issue_numbers"]),
    "wall_seconds": elapsed,
    "revert_status": "pending",
})
print(f"STEP 12: drain logged — cluster "
      f"{cluster['root_cause_tag']}#{cluster['sub_cluster_id']} "
      f"in {elapsed:.0f}s", flush=True)
PY
```

Final exit `0`. The markdown command MAY emit a final `PushNotification:` line
on success so headless operators know the cycle completed.

## STEP 12.5: Post-push state=CLOSED verification + marker clear

After the push has succeeded and the budget/breaker/history have been
recorded (STEP 12), independently verify with the GitHub API that EVERY
issue in the cluster is now `state=CLOSED`. This guards against the failure
mode where the commit referenced the issue with `Closes #N` but the merge
went to a non-default branch (so GitHub did not close the issue), or where
push-time webhooks dropped.

If ANY cluster issue is still OPEN: bump the circuit breaker, retain the
marker for operator inspection, exit non-zero. Otherwise clear the marker
so the next /drain-queue invocation starts clean.

```bash
python3 - <<'PY'
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, "plugins/autonomous-dev/lib")
from drain_pending import DrainPendingMarker
from drain_queue_state import CircuitBreaker
from drain_runner import _build_env, append_stop_notification

repo = Path.cwd().resolve()
env = _build_env(repo)
log_dir = repo / ".claude" / "local"
marker = DrainPendingMarker.read(repo_root=repo)
if marker is None or not marker.issues:
    print("STEP 12.5: no marker present; nothing to verify", flush=True)
    sys.exit(0)

unclosed: list[int] = []
for n in marker.issues:
    r = subprocess.run(
        ["gh", "issue", "view", str(n), "--json", "state", "--jq", ".state"],
        cwd=str(repo), env=env, capture_output=True, text=True, check=False,
    )
    if r.returncode != 0 or r.stdout.strip().upper() != "CLOSED":
        unclosed.append(n)

if unclosed:
    CircuitBreaker.load(repo).record_failure()
    append_stop_notification(
        f"STEP 12.5: post-push verification failed — issues still OPEN: {unclosed}",
        log_dir,
    )
    print(
        f"STOP STEP 12.5: post-push verification failed — issues still OPEN: "
        f"{unclosed}. Marker retained for operator inspection.",
        flush=True,
    )
    sys.exit(1)

DrainPendingMarker.clear(repo_root=repo)
print(
    f"STEP 12.5: all cluster issues CLOSED ({marker.issues}); marker cleared",
    flush=True,
)
PY
```

## Coordinator Bypass of plan-critic

When the coordinator classifies an issue as a "mechanical extension" and decides to skip plan-critic, it MUST record the bypass for audit trail purposes. This involves two function calls:

1. Record the skip in pipeline state with the bypass reason
2. Write a machine-readable verdict file for CIA and other consumers

Example code for the coordinator:

```python
from plugins.autonomous_dev.lib.pipeline_completion_state import (
    record_plan_critic_skipped,
    write_coordinator_bypass_verdict
)

# When bypassing plan-critic for mechanical extension
issue_number = 1279
bypass_reason = "mechanical extension: adding test coverage"
plan_summary = "Add regression tests for coordinator bypass logging"

# Record in pipeline state
record_plan_critic_skipped(
    session_id, 
    issue_number=issue_number,
    bypass_reason=bypass_reason
)

# Write the verdict file for audit trail
write_coordinator_bypass_verdict(
    issue_number,
    bypass_reason,
    plan_summary=plan_summary
)
```

The verdict file at `.claude/plan_critic_verdict.json` will contain a `"COORDINATOR_BYPASS"` verdict with structured metadata, allowing CIA to distinguish intentional skips from missed invocations.

## Notes for maintainers

* **STEP 6 delegates to `/implement --issues`** (see `commands/implement-batch.md`).
  Do NOT fork batch logic into this wrapper. If you find yourself
  re-implementing worktree creation, per-issue commits, or multi-issue PR
  opening, you are in the wrong file.
* **`PushNotification` is a Claude Code TOOL, not a Python symbol.** The
  Python helpers append JSONL to `.claude/local/drain_notifications.jsonl`;
  the markdown command emits the `PushNotification:` tool line itself.
* **State file paths**: every state file lives under
  `<repo_root>/.claude/local/`. No `/tmp/...` literals. The pipeline-state
  sentinel is resolved via `get_legacy_sentinel_path()` per Issue #1206.
* **Subprocess discipline (Issue #1064)**: every `subprocess.run` call in
  `drain_runner.py` passes explicit `cwd=` and `env=`. The regression test
  `tests/regression/test_drain_queue_runner_subprocess_kwargs.py` locks this
  contract. If you add a new subprocess helper, add a matching kwargs test.
* **Default branch is resolved, not hardcoded.** `drain_runner.default_branch()`
  parses `git remote show origin`, falls back to `git symbolic-ref`, then
  `"master"`. Repos on `main` work without changes.
