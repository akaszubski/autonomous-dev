# Troubleshooting Guide

**Last Updated**: 2026-06-28
**For**: Users and developers encountering common issues

---

## Issue stuck with `in-progress` label — `/implement --issues` aborts with exit 2

**Symptom**: Running `/implement --issues N` (or `/drain-queue → /implement --issues`) immediately aborts with a message like:

```
ABORT: Issue #N is being implemented by mac-studio:12345 (age=1800s).
Remediation: wait for completion, or run
  gh issue edit N --remove-label in-progress
if the other run is known dead (claim auto-expires after 4h).
```

**Cause**: A cross-machine claim mutex (Issue #1335) prevents two concurrent runs — e.g., a local `/implement --issues` and a cloud-drain `/drain-queue → /implement --issues` — from processing the same GH issue in parallel. The claim is a `in-progress` GH Issue label plus a marker comment `🤖 Implementing #N now [host=…, pid=…, ts=…]`. If the previous run completed normally, `release_issue` removed the label. If it crashed or was killed before release, the label persists.

**Claims auto-expire**: `is_claimed()` treats any claim older than 4 hours as stale and ignores it — no label removal required. If the stuck claim is less than 4 hours old and the holder is known dead, remove it manually:

```bash
# Remove the in-progress label manually
gh issue edit N --remove-label in-progress
```

**Expected flow** (no action needed): When a run completes or fails normally, `release_issue(N, actor, reason="completed"|"failed")` removes the label and posts a `🤖 Released #N [...]` comment. You should only see the stuck state if the pipeline crashed (OOM, `kill -9`, or Mac sleep) mid-run.

**Verify whether the claim is stale** (older than 4h = safe to remove):

```bash
# Show the in-progress comment timestamp
gh issue view N --json comments --jq '.comments[] | select(.body | startswith("🤖 Implementing")) | {createdAt, body}'
```

**Why this exists**: Race observed 2026-06-28 where a local `/implement --issues` and cloud-drain ran simultaneously on cluster #1331+#1334, producing duplicate implementation commits. Local-filesystem sentinels (`.claude/local/*`) cannot be read from a different machine checkout; GH Issue labels are globally visible.

---

## `git commit` blocked by drain-pending marker — missing `Closes #N` reference

**Symptom**: A `git commit` inside a `/drain-queue` run is blocked with a message like:

```
BLOCKED: drain marker active (issues=[1234, 1235]) — commit message must include
'Closes #N' (or 'Fixes #N') for at least one cluster issue. Got refs: none.
Add 'Closes #1234' to the commit body.
```

Or for uninspectable payloads (no `-m` flag, stdin, process substitution):

```
BLOCKED: drain marker active (issues=[1234, 1235]) — commit payload uninspectable
(no -m/-F, stdin, process substitution, missing file, or unresolved shell expansion).
Use 'git commit -m "... Closes #1234"' with a literal message that closes a cluster issue.
```

**Cause**: `/drain-queue` STEP 3.6 wrote a `.claude/local/drain_pending.json` marker when it selected a cluster. The `_check_drain_pending_commit_gate` in `unified_pre_tool.py` now enforces that every `git commit` during an active drain references at least one cluster issue via `Closes #N` or `Fixes #N`. This implements OWASP LLM06 (Excessive Agency) downstream enforcement — the hook blocks freelancing commits that are unrelated to the draining cluster.

**Fix options**:

1. **Correct fix — add the required reference** (recommended):
   ```bash
   git commit -m "fix: implement issue logic

   Closes #1234"
   ```
   For a batch-cluster commit, ALL cluster issues must appear:
   ```bash
   git commit -m "fix: drain cluster

   Closes #1234
   Closes #1235"
   ```

2. **Clear a stale marker** (if `/drain-queue` crashed mid-run and you are NOT inside a drain session):
   ```bash
   python3 -c "
   import sys; sys.path.insert(0, 'plugins/autonomous-dev/lib')
   from drain_pending import DrainPendingMarker
   cleared = DrainPendingMarker.clear()
   print('marker cleared' if cleared else 'no marker present')
   "
   ```
   The marker is also reaped automatically at SessionStart if it is older than 4 hours (`STALE_MINUTES=240`).

3. **Universal bypass** (emergency only — disables ALL hook enforcement):
   ```bash
   AUTONOMOUS_DEV_BYPASS=1 git commit -m "..."
   ```

**Normal `/drain-queue` flow (Issue #1226)**: When `/drain-queue` invokes `/implement --issues N`, the pipeline coordinator routes the final commit through `create_commit_with_agent_message()` at STEP 12.7 (full pipeline) or STEP L4.7 (light pipeline). This helper auto-injects `Closes #N` into the commit body, so the drain-pending gate is satisfied automatically. You should only encounter this block if running a bare `git commit` outside the pipeline, using a custom commit message that omits the reference, or if the pipeline coordinator bypasses the helper step.

**Why this exists**: The 2026-06-15 autonomous fire (commit 8b3b582) ignored the triage cluster and committed an unrelated fix with no `Closes #N` reference. The gate prevents the same pattern going forward.

**Not applicable when**: The drain marker is absent (no active `/drain-queue` run). The gate fails open — if `drain_pending.json` is missing, unreadable, or contains an empty issue list, the gate does not fire.

---

## Worktree-gitignore deadlock — use `--no-worktree` (Issue #1133)

**Symptom**: `/implement --batch features.txt` or `/implement --issues 1 2 3` fails with PreToolUse hook denials immediately after `git worktree add`. The worktree's `.claude/hooks/` directory is empty; the hook stack cannot find the gates and refuses to allow the pipeline to proceed.

**Cause**: `git worktree add` only copies tracked files. If your repo gitignores `.claude/*` (autonomous-dev itself does — its `.claude/` is the install target, not source), the new worktree has NO hooks, NO config, and the PreToolUse fallback denies every tool call.

**Fix**: Pass `--no-worktree` to skip worktree creation and run the cluster in-place on the current branch:

```bash
/implement --issues 1131 1132 1133 --no-worktree
/implement --batch features.txt --no-worktree
```

In `--no-worktree` mode the batch runs serially on the current branch (one commit per issue), then opens a single multi-issue PR. The `BATCH_NO_WORKTREE=1` env var keeps batch hook gates (CIA / doc-master / agent-completeness) active. Pre-condition: working tree MUST be clean (both staged and unstaged), because the failure-cleanup path runs `git reset --hard HEAD` between issues.

When to use: any repo where `.claude/*` is gitignored. For the autonomous-dev source repo itself, prefer `bash scripts/drain-all.sh --cluster-mode` (which invokes `--no-worktree` automatically against the top triage cluster) or `bash scripts/triage-and-implement.sh` (cluster mode is the default; pass `--no-cluster` for the legacy per-issue loop).

---

## Stale worktrees accumulating in `.worktrees/` — run `cleanup-worktrees.sh` {#stale-worktrees-cleanup}

**Symptom**: `.worktrees/` contains many entries (e.g. 30–50 directories) left over from previous `/implement --batch` or `/implement --issues` sessions. `git worktree list` shows dozens of rows; disk usage is elevated. No active pipeline is running.

**Cause**: Each batch issue gets its own worktree under `.worktrees/<branch-name>/`. After the batch PR is merged, the worktrees for merged branches are not automatically pruned — they persist until explicitly cleaned up.

**Fix**: Run the recovery script from the repo root:

```bash
bash scripts/cleanup-worktrees.sh --dry-run   # preview: shows removed=N skipped=M
bash scripts/cleanup-worktrees.sh             # remove merged-branch worktrees
```

The script removes worktrees whose branch is merged into `master`. It skips the main worktree, unmerged branches, and detached HEADs that are not reachable from `master`. Idempotent — safe to re-run.

**Not to be confused with**: the worktree-gitignore deadlock (Issue #1133) above, which prevents worktree creation. The stale-worktree symptom is disk accumulation AFTER successful batches, not a pipeline failure.

---

## Hook Recovery Telemetry (Issue #970)

When a `unified_pre_tool.py` deny gate blocks a tool call, it now emits a
structured JSONL row at `.claude/logs/hook-recovery.jsonl` describing what
was blocked and an actionable recovery hint. Tail this file when you are
unsure why a tool call was rejected:

```bash
tail -n 5 .claude/logs/hook-recovery.jsonl | jq .
```

Each row has the shape:

```json
{
  "timestamp": "2026-04-26T...",
  "hook_name": "unified_pre_tool.py",
  "tool_name": "Bash",
  "block_reason": "WORKFLOW ENFORCEMENT: ...",
  "recovery_hint": "Delegate the change to a pipeline agent...",
  "session_id": "..."
}
```

**Rollback switch**: set `HOOK_RECOVERY_DISABLED=1` to make telemetry a
no-op without redeploying. The deny decision itself is unaffected — the
hook gate continues to function normally; only the JSONL log and the
stale-state cleanup helper are silenced.

**Audit script**: `python scripts/audit_hook_recovery.py` reports any
literal `output_decision("deny", ...)` site in `unified_pre_tool.py` that
lacks a paired `log_block_with_recovery()` call. Default mode is WARN-ONLY
(exit 0); pass `--strict` (or set `AUDIT_HOOK_RECOVERY_STRICT=1`) to make
unjustified deny sites fail CI.

---

## Hook Block Telemetry (Issue #972)

The `hook_recovery.jsonl` log shipped with #970 was the first step. As of
#972, every deny decision across the harness — `output_decision("deny",
...)` (tuple), `{"decision": "block"}` (dict), and `sys.exit(2)`
(exit2) — now writes one structured JSONL row to a single canonical
location: `.claude/logs/hook-blocks.jsonl`. This lets you reconstruct
per-hook block counts, category breakdowns (matching the #942 buckets:
plan-exit, pipeline-state, agent-gates, settings-write), and decision-
shape distributions WITHOUT grepping individual session transcripts.

**Where**: `.claude/logs/hook-blocks.jsonl`

**Schema** (per row):

```json
{
  "ts": "2026-04-26T...",
  "hook_name": "unified_pre_tool.py",
  "decision_shape": "tuple",
  "reason": "WORKFLOW ENFORCEMENT: ...",
  "metadata": {"tool_name": "Bash", ...},
  "session_id": "...",
  "cwd": "/Users/.../repo"
}
```

**Triage script**: `python scripts/hook_block_summary.py --last 7d --top 10`
(also supports `--since <ISO>` and `--json`). Reads BOTH `hook-blocks.jsonl`
(new) AND `hook-recovery.jsonl` (legacy from #970) for one release cycle so
historical data is preserved without manual migration. Rows are
deduplicated by `(timestamp, hook_name, reason)`.

**Rollback switch**: `HOOK_TELEMETRY_DISABLED=1` makes all telemetry a
no-op. The hook decisions themselves are unaffected — only the JSONL
log is silenced. The deprecated `HOOK_RECOVERY_DISABLED=1` env var is
honored as an alias (with a one-time stderr warning) so existing
rollback procedures continue to work.

**Verbose mode** (Issue #1178): `HOOK_TELEMETRY_VERBOSE=1` adds a
`block_reason_detail` field to `prompt_integrity_block` event metadata,
containing the raw deny-reason string from the prompt-integrity gate.
Omitted by default for privacy (deny reasons may contain fragments of
agent prompts). Safe to enable in local debugging sessions; do not set
permanently in shared or CI environments.

**Deprecation timeline for `hook-recovery.jsonl`**:

- Now (Wave 1 — #972): Writes go to `hook-blocks.jsonl`; reads check
  both files for backwards compatibility.
- One release cycle later: Summary script will warn when reading the
  legacy file.
- Two release cycles later: Legacy file will no longer be read.

**Cross-link**: see [`docs/HOOK-COMPOSITION.md`](../../docs/HOOK-COMPOSITION.md)
for the full hook-composition contract and the checklist for adding new
hooks.

---

## Production-Code Edit Blocked Outside /implement (Issue #1142 + Phase 1)

**Symptom**: A Write or Edit to a `.py`, `.ts`, `.js`, `.go`, `.rs`, or similar production-code file is denied with a message like:

```
BLOCKED: Write/Edit to code file '<name>' requires the /implement pipeline.
File: <path>
Tier: <fix|light|full>.
REQUIRED NEXT ACTION: Run /implement [--fix|--light] "<brief description of change>".
Per-repo opt-out: touch .claude/.bypass && git commit.
```

**Cause**: Phase 1 (Issue #1142+) flipped the gate to default-on. `unified_pre_tool.py` now blocks non-trivial direct edits to production-code files unless `/implement` is active OR the repo has committed `.claude/.bypass`. The classifier returns one of three tiers (`fix` / `light` / `full`) each mapped to the matching `/implement` variant.

**Fix options** (choose the appropriate level):

1. **Recommended — route through the pipeline** (enforces full SDLC):
   ```bash
   /implement --fix "describe the fix"     # tier=fix (<20 lines, no AST signal)
   /implement --light "describe the change" # tier=light (new func / control-flow / 20-99 lines)
   /implement "describe the feature"       # tier=full (new class OR ≥100 lines)
   ```

2. **One-shot bypass** (allows a single edit, file consumed on first check):
   ```bash
   touch /tmp/skip_write_pipeline_gate
   # Now retry the Write/Edit — bypass is consumed and gate re-enables
   ```

3. **Durable per-repo opt-out** (consumer repo that does not want SDLC enforcement):
   ```bash
   touch .claude/.bypass
   git add .claude/.bypass
   git commit -m "chore: opt out of autonomous-dev SDLC enforcement"
   ```

4. **Emergency universal bypass** (disables ALL hook enforcement):
   ```bash
   AUTONOMOUS_DEV_BYPASS=1 <your command>
   ```

**Not applicable when**: `.claude/.bypass` is present (gate skipped), or the pipeline is already active (gate is a no-op). Test files (`test_*.py`, files under `tests/` or `test/`) are always excluded from this gate. Bash commands writing to code files (`cat > X.py`, `sed -i X.py`, `tee X.py`, heredocs) are subject to the same gate; `git apply` and `patch < diff` are excluded as user-driven patch tooling.


## Coordinator Cannot Directly Edit Protected Path (Issue #1296)

**Symptom**: During a `/implement` pipeline run, the coordinator is blocked from editing infrastructure files with:

```
BLOCKED: Coordinator cannot directly edit protected path '<filename>' mid-pipeline.
Re-dispatch the implementer agent with this change as a remediation cycle. (Issue #1296)
```

**Cause**: Issue #1296 introduced the agent-dispatch sentinel mechanism to prevent coordinators from bypassing the implementer agent for protected infrastructure paths (`agents/*.md`, `commands/*.md`, `hooks/*.py`, `lib/*.py`, `skills/*/SKILL.md`). The sentinel file (`.claude/local/active_agent_dispatch.json`) tracks when an agent-dispatched edit is in flight. If the pipeline is active but no sentinel exists, the coordinator's direct edit attempt is blocked.

**Fix**: The coordinator must re-dispatch the implementer agent:

1. **In coordinator context** — include the required change in your remediation instructions:
   ```
   "Re-dispatch the implementer agent to add the missing import/function/etc."
   ```

2. **Sentinel lifecycle** — the sentinel is automatically:
   - Written when an agent is dispatched (via Task tool)
   - Cleared after the agent completes (PostToolUse hook)
   - Expires after 30 seconds (TTL safety)

**When this doesn't apply**: 
- Outside `/implement` pipeline (no pipeline active)
- When editing user-facing docs (`README.md`, `CHANGELOG.md`, `docs/*.md`)
- When `.claude/.bypass` is present (universal escape hatch)
- When the sentinel is active (agent-dispatched edit in progress)

**Debug**: Check if a sentinel is active:
```bash
if [ -f .claude/local/active_agent_dispatch.json ]; then
  cat .claude/local/active_agent_dispatch.json
else
  echo "No active agent dispatch"
fi
```

---
---

## Universal Escape: Unstick Any Blocked Hook (Issue #969)

**When to use**: A hook is blocking your work and you cannot run a slash command
to bypass it (e.g., the bypass mechanism for that specific hook is itself
broken, or you are in a project where autonomous-dev is not installed but
its global hooks fire anyway).

**Two equivalent signals — either one is sufficient.** Both fall through to
`allow` for every hook in the harness, with a structured bypass event written
to `.claude/logs/hook-bypass.jsonl` for later audit.

### Option A — Env var (process-scoped, recommended for one-shot use)

```bash
# Bypass for the next command only (subshell scope):
AUTONOMOUS_DEV_BYPASS=1 git commit -m "fix: emergency"

# Bypass for the whole shell session:
export AUTONOMOUS_DEV_BYPASS=1
# ... do whatever was blocked ...
unset AUTONOMOUS_DEV_BYPASS    # IMPORTANT: re-enable enforcement when done
```

Truthy values: `1`, `true`, `yes`, `on` (case-insensitive). Falsy values
(`0`, `false`, `no`, `off`, empty) do NOT trigger bypass.

### Option B — File flag (project-scoped, persists across sessions)

```bash
# Create the flag from the project root:
touch .claude/.bypass

# ... do whatever was blocked ...

# Re-enable enforcement:
rm .claude/.bypass
```

The flag is also honored when present in any **ancestor** directory of your
current working directory (so dropping `.claude/.bypass` at the repo root
works from any subdirectory). The walk is bounded by 30 levels and does NOT
follow symlinks.

### What gets logged

Every bypass-allowed hook call appends one JSON line to
`.claude/logs/hook-bypass.jsonl`:

```json
{"timestamp": "2026-04-26T12:34:56.789012+00:00", "hook_name": "plan_gate.py", "tool_name": "Write", "reason": "env_or_file"}
```

If `.claude/logs/` cannot be created (read-only filesystem, permission
denied), the line is written to stderr prefixed with `[hook-bypass]`. The
bypass itself never fails on telemetry errors.

### Important caveats

- **The bypass is not a security control.** Anyone with write access to your
  cwd or env can disable enforcement. Use it as a developer convenience, not
  a permission boundary.
- **Re-enable enforcement when done.** A forgotten `export
  AUTONOMOUS_DEV_BYPASS=1` in your `~/.zshrc` will silently disable every
  hook for every session.
- **Coexists with per-hook env vars.** `SKIP_PLAN_CHECK`,
  `AUTONOMOUS_DEV_SKIP_PLAN_REVIEW`, `MCP_AUTO_APPROVE`, etc. continue to
  work as additional independent paths.

---

## Quick Fixes

| Problem | Solution |
|---------|----------|
| Commands not appearing | Run `/reload-plugins` to reload commands/agents/skills. If hooks or settings changed, do a full restart (Cmd+Q / Ctrl+Q) instead |
| ModuleNotFoundError in hooks | Re-run `install.sh` or copy libs to `~/.claude/lib/` (see below) |
| ModuleNotFoundError in commands | Commands auto-resolve libs via multi-candidate resolver (`.claude/lib` → `plugins/autonomous-dev/lib` → `~/.claude/lib`) — re-run `install.sh` if libs are missing |
| Hook not running | Check `~/.claude/settings.json` |
| No hooks fire after fresh install (all events) | Settings file may have been silently skipped at load due to a schema-invalid template. Reinstall from a current template (`install.sh`) — see "Hooks silently disabled after install" below |
| Context exceeded | Run `/clear` |
| Plugin changes not visible | Run `/sync --plugin-dev` then `/reload-plugins` (or full restart if hooks/settings changed) |
| Pipeline stuck mid-run (auto-compact, crash) | Run `/implement --resume <run_id>` — run_id is printed at STEP 0 |
| "Agent completeness gate BLOCKED" | Don't bypass — run the missing agents. If you must escape: (1) `touch /tmp/skip_agent_completeness_gate` as a separate command, then retry (file-based, works mid-session); (2) `export SKIP_AGENT_COMPLETENESS_GATE=1` BEFORE launching claude (env vars don't propagate mid-session — Issue #779). Audit-logged either way. |
| "Ordering violation: X requires Y" | The hook enforces pipeline sequence. Run the prerequisite agent first, or if it already ran, the session-state tracker has the wrong key (see "Session ID mismatch" below) |
| Deploy timed out to Mac Studio | Check `tailscale status`; if peer is on DERP relay, SSH handshake may exceed the 5s probe timeout — wait for P2P or deploy via LAN IP |
| sessions.db missing token counts | Pre-fix hook bug (Issue #901). Deploy latest, then re-run a session to repopulate. Existing rows can be backfilled by re-parsing `~/.claude/archive/conversations/**/*.jsonl` |
| doc-master returned empty verdict | Known background-agent race — the coordinator retries once with reduced context. If it still fails, the verdict is logged as `MISSING` and the pipeline proceeds with warning |

---

## Hooks Silently Disabled After Install

**Symptom**: After `install.sh` completes, no hooks fire — not on Write, not on Bash, not on Stop. Claude Code appears to work but all enforcement, formatting, and quality gates are absent. There are no error messages.

**Cause (Issues #1103/1104/1105)**: Claude Code silently discards a `settings.local.json` file when it contains keys or values that violate the settings schema. Three classes of schema violation were present in the shipped templates prior to the fix:

1. **`PreCommit` hook event key**: `PreCommit` is not a recognized Claude Code hook lifecycle event. Its presence caused the entire hooks block to be rejected.
2. **Object-typed matcher**: `{"tools": ["Write", "Edit"]}` is not a valid matcher value — matchers must be plain strings. The correct form is `"Write|Edit"`.
3. **`Bash(:*)` in `permissions.allow`**: The colon-prefixed glob syntax is not recognized in the allow list. The correct form is `"Bash"`.

Any one of these caused the settings file to be silently skipped, disabling every hook for every session — with no warning.

**Who is affected**: Users who installed autonomous-dev before 2026-05-21 and have not re-run `install.sh` since. The defect was present in `settings.local.json`, `settings.autonomous-dev.json`, `settings.strict-mode.json`, and `settings.permission-batching.json`.

**Fix**:
```bash
# Re-run install to regenerate settings from the corrected templates:
bash install.sh

# Full restart of Claude Code is required after settings change:
# Cmd+Q (Mac) or Ctrl+Q, wait 5 seconds, reopen

# Verify hooks are active — this prompt should show hook output:
/health-check
```

**Verify the fix manually** (check your `.claude/settings.local.json` does NOT contain):
- A top-level `"PreCommit"` key inside the `hooks` block
- Matcher objects like `{"tools": [...]}` — all matchers must be strings
- `"Bash(:*)"` in the `permissions.allow` array

---

## Installation Issues

### "Commands not found after installation"

**Symptom**: After running `install.sh`, commands like `/implement` don't appear.

**Cause**: Claude Code caches commands at startup.

**Solution**:
```bash
# Option A: Run /reload-plugins (reloads commands, agents, skills — ~5 seconds)
/reload-plugins

# Option B: Full restart (required if hooks or settings changed)
# 1. Fully quit Claude Code
#    Press Cmd+Q (Mac) or Ctrl+Q (Windows/Linux)
# 2. Verify process is dead
ps aux | grep -i claude | grep -v grep
# Should return nothing
# 3. Wait 5 seconds, then reopen Claude Code

# Verify commands appear
/health-check
```

### "install.sh fails or incomplete"

**Symptom**: Installation script errors or missing components.

**Solution**:
```bash
# 1. Check what was installed
ls -la ~/.claude/hooks/ | wc -l    # Should be ~50 hooks
ls -la ~/.claude/lib/ | wc -l      # Should be ~69 libs

# 2. Re-run installation
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh)

# 3. Run /reload-plugins (or full restart if hooks/settings changed)
```

### "How do I uninstall?"

**Solution**: Use the `/sync --uninstall` command (added in v3.41.0):

```bash
# Preview what will be removed
/sync --uninstall

# Confirm with --force flag
/sync --uninstall --force

# Keep global ~/.claude/ files (only remove project files)
/sync --uninstall --force --local-only
```

Creates automatic backup before removal. Rollback available if needed.

---

## Recovery from Broken Hooks

**Symptom**: Every prompt to Claude Code is blocked with hook errors. Common causes are missing hook scripts (deleted or never installed), infinite loops in hook logic, syntax errors in hook commands, or references to libraries that no longer exist on disk. Because hooks fire on every `UserPromptSubmit`, `PreToolUse`, and `Stop` event, even typing a recovery command inside Claude Code is impossible — the hooks block the prompt before it reaches the model.

**Cause**: One or more entries in `~/.claude/settings.json` under the `hooks` block reference a script or command that fails. The historical workaround was `mv ~/.claude ~/.claude.old`, but that loses session state, projects, the archive database, and per-project `.claude/` overrides.

**Three recovery options** — pick the one that matches your situation:

### Option 1: `install.sh --reset-hooks` (recommended)

Strips the entire `hooks` block from `~/.claude/settings.json` while preserving every other top-level key (permissions, mcpServers, env, model, output style). A backup is written to `~/.claude/settings.json.preglobal-hooks-strip` before the in-place rewrite.

```bash
# From a terminal OUTSIDE Claude Code (since Claude Code is bricked):
bash <(curl -sSL https://raw.githubusercontent.com/akaszubski/autonomous-dev/master/install.sh) --reset-hooks

# Or, if you have the repo cloned locally:
bash /path/to/autonomous-dev/install.sh --reset-hooks

# Then restart Claude Code (Cmd+Q / Ctrl+Q) and verify the next prompt works.
```

Behavior notes:
- Idempotent: a second invocation with no `hooks` key is a no-op (no backup created).
- Re-running while a previous backup exists OVERWRITES the backup with the current pre-strip state. If you need to preserve multiple recovery checkpoints, copy `settings.json.preglobal-hooks-strip` to a timestamped name before re-running.
- Malformed JSON in `settings.json` (unparseable file) causes the helper to refuse — it will not risk overwriting an unparseable file. Fix the JSON syntax manually first, or restore from a backup.

### Option 2: Manual `python3 -c "..."` one-liner

Use this when you can't or don't want to fetch `install.sh` (offline machine, cautious environment, or simply faster). Self-contained — no install required.

This version is preferred over a naive `write_text` approach because it is atomic under SIGINT (a temp file is renamed, so no partial writes), preserves dotfiles-manager symlinks by resolving to the real target before writing, and never widens file permissions.

```bash
python3 -c "
import json, os, sys, tempfile
from pathlib import Path
p = Path.home() / '.claude' / 'settings.json'
if not p.exists():
    print('settings.json not present — nothing to do'); sys.exit(0)
data = json.loads(p.read_text())
if 'hooks' not in data:
    print('no hooks block to remove — nothing to do'); sys.exit(0)
backup = p.with_suffix(p.suffix + '.preglobal-hooks-strip')
backup.write_bytes(p.read_bytes()); os.chmod(str(backup), 0o600)
removed = list(data['hooks'].keys()) if isinstance(data.get('hooks'), dict) else []
data.pop('hooks')
try:
    real_p = p.resolve() if p.is_symlink() else p
except OSError:
    real_p = p
fd, tmp = tempfile.mkstemp(dir=str(real_p.parent), prefix='.settings.', suffix='.tmp')
os.write(fd, json.dumps(data, indent=2).encode()); os.close(fd)
os.chmod(tmp, 0o600); os.replace(tmp, real_p)
print(f'Stripped {len(removed)} hook event(s); backup: {backup}')
"
```

This produces the same result as Option 1 (preserves all other keys, writes the same backup file). Restart Claude Code afterward.

### Option 3: Soft alternative — `disableAllHooks: true`

If you want to disable hooks WITHOUT deleting the configuration (e.g., to debug which hook is failing later), add a single key to `~/.claude/settings.json`:

```json
{
  "disableAllHooks": true,
  "hooks": { ... }
}
```

Trade-offs:
- **Pro**: Reversible — flip back to `false` (or remove the key) once the underlying issue is fixed.
- **Con**: Cruft remains — the broken hooks entries are still in the file, and you must remember to fix them later.
- **Pro**: One-line surgical edit — no helper script needed.

For a brick recovery where the user can't even open Claude Code, Option 1 or Option 2 are usually faster. Option 3 is best when hooks are working but a single new hook is suspect, and you want to disable everything for diagnosis without losing the configuration.

### Restoring after recovery

The backup file (`~/.claude/settings.json.preglobal-hooks-strip`) preserves the pre-strip state. If you want to restore the hooks block (e.g., once the broken hook is fixed):

```bash
cp ~/.claude/settings.json.preglobal-hooks-strip ~/.claude/settings.json
```

Or merge the `hooks` field back manually if you've made other edits since the strip.

---

## Development Issues

### ModuleNotFoundError: No module named 'autonomous_dev'

**Symptom**: When running tests or importing:
```python
ModuleNotFoundError: No module named 'autonomous_dev'
```

**Cause**: Python can't use hyphens in package names. Directory is `autonomous-dev` but imports need `autonomous_dev`.

**Solution**: Create a symlink:

```bash
# macOS/Linux
cd plugins
ln -s autonomous-dev autonomous_dev

# Windows (Command Prompt as Admin)
cd plugins
mklink /D autonomous_dev autonomous-dev

# Verify
python3 -c "from autonomous_dev.lib import security_utils; print('OK')"
```

### "Plugin changes don't appear when testing"

**Symptom**: Edit agent/command files but changes don't show up.

**Cause**: Claude Code reads from `~/.claude/` not your development directory.

**Solution**:
```bash
# 1. Make your changes
vim plugins/autonomous-dev/agents/implementer.md

# 2. Sync to installed location
/sync --plugin-dev

# 3. Reload or restart:
#    Changed commands/agents/skills → /reload-plugins (~5 seconds)
#    Changed hooks/settings/.env/Python libs → Full restart (Cmd+Q / Ctrl+Q)

# 4. Test changes
/health-check
```

### "Lib files not found by hooks"

**Symptom**: Hooks fail with import errors:
```
ModuleNotFoundError: No module named 'security_utils'
```

**Cause**: Lib files not copied to `~/.claude/lib/`.

**Solution**:
```bash
# 1. Check lib directory
ls ~/.claude/lib/*.py | wc -l
# Should show ~69 files

# 2. If missing, re-run install or copy manually
cp plugins/autonomous-dev/lib/*.py ~/.claude/lib/

# 3. Verify imports work
python3 -c "import sys; sys.path.insert(0, '$HOME/.claude/lib'); import security_utils; print('OK')"
```

**Note**: Commands (`/implement`, `/sweep`, etc.) now use a multi-candidate path resolver that automatically finds libs in `.claude/lib`, `plugins/autonomous-dev/lib`, or `~/.claude/lib` — in that priority order. Creating a symlink is no longer required for commands to work in consumer repos; the resolver handles both dev and installed layouts.

---

## Runtime Issues

### "Context budget exceeded"

**Symptom**: Token limit errors, truncated responses.

**Cause**: Too many features in one session without clearing context.

**Solution**:
```bash
# Clear context after each feature
/clear

# Best practice workflow:
# 1. Complete feature with /implement
# 2. Run /clear
# 3. Start next feature
```

### "Hooks not running"

**Symptom**: Expected hooks (auto-format, validation) don't trigger.

**Solution**:
```bash
# 1. Check hooks are installed
ls ~/.claude/hooks/*.py | head -5

# 2. Check settings configuration
cat ~/.claude/settings.json | grep -A 10 '"hooks"'

# 3. Check hook is executable
chmod +x ~/.claude/hooks/*.py

# 4. Test hook manually
python3 ~/.claude/hooks/auto_format.py
echo "Exit code: $?"
```

If hooks are running but actively blocking every prompt, see [Recovery from Broken Hooks](#recovery-from-broken-hooks).

### "Feature doesn't align with PROJECT.md"

**Symptom**: Warning about feature not matching project goals.

**Solution**:
```bash
# Option 1: Modify feature to align with PROJECT.md goals

# Option 2: Update PROJECT.md if direction changed
vim .claude/PROJECT.md
# Update GOALS, SCOPE sections

# Option 3: Run alignment check
/align
```

---

## Command-Specific Issues

### "/implement stops mid-way"

**Symptom**: Pipeline doesn't complete all 8 steps.

**Solutions**:
1. Check for test failures (step 4) - fix failing tests
2. Check for security issues (step 6) - address vulnerabilities
3. Context may be full - run `/clear` and retry
4. Check agent output for specific errors

### "/implement --batch crashes"

**Symptom**: Batch processing stops unexpectedly.

**Solution**:
```bash
# Resume from where it stopped
/implement --resume <batch-id>

# Check batch state
cat .claude/batch_state.json
```

### "/sync fails"

**Symptom**: Sync command errors.

**Solutions**:
```bash
# Check which mode is failing
/sync --github    # Fetch from GitHub
/sync --env       # Environment sync
/sync --plugin-dev # Dev sync (requires being in autonomous-dev repo)

# For GitHub sync, ensure git remote is configured
git remote -v
```

### "/sync tries to fetch URL instead of executing script"

**Symptom**: When you run `/sync`, Claude attempts to fetch content from a URL (e.g., GitHub) instead of executing the script locally.

**Cause**: The sync.md command file should have a strong "Do NOT fetch" directive to prevent Claude from web requests. If missing or incorrectly placed, Claude may interpret the script as needing external resources.

**Solution**:
```bash
# 1. Verify the directive is in place
grep "Do NOT fetch" .claude/commands/sync.md
# Should output: Do NOT fetch any URLs or documentation. Execute the script below directly.

# 2. If directive is missing or incorrect, re-sync
/sync --plugin-dev

# 3. Run /reload-plugins to reload commands (or full restart if hooks/settings changed)

# 4. Test the command again
/sync --github

# 5. If still failing, check installed version
cat ~/.claude/commands/sync.md | head -15
# Should see "Do NOT fetch" in lines 1-10
```

**Note**: The "Do NOT fetch" directive must appear BEFORE the bash code block to ensure Claude reads and respects it immediately.

---

## Diagnostic Commands

```bash
# Environment check
echo "=== Environment ==="
python3 --version
which python3

# Installation check
echo "=== Installation ==="
echo "Hooks: $(ls ~/.claude/hooks/*.py 2>/dev/null | wc -l)"
echo "Libs: $(ls ~/.claude/lib/*.py 2>/dev/null | wc -l)"
echo "Commands: $(ls .claude/commands/*.md 2>/dev/null | wc -l)"
echo "Agents: $(ls .claude/agents/*.md 2>/dev/null | wc -l)"

# Test a hook
echo "=== Hook Test ==="
python3 ~/.claude/hooks/validate_commands.py
echo "Exit code: $?"

# Check settings
echo "=== Settings ==="
cat ~/.claude/settings.json | python3 -m json.tool | head -20
```

---

## Uninstalling autonomous-dev

Two uninstall paths exist; pick the one that matches your situation.

### When to use which path

| Situation | Recommended | Why |
|---|---|---|
| Claude Code still launches; you want a clean removal | `/sync --uninstall` | Python orchestrator; richer preview, rollback support |
| Claude Code refuses prompts, hooks are bricked, or `/sync` itself fails | `bash install.sh --uninstall` | Shell-only; survives a broken install, no Claude CLI required |

### Shell-only uninstall — `install.sh --uninstall`

The shell path is intentionally self-contained: it parses only the
install manifest, uses two small Python helpers for JSON mutation, and
NEVER imports from `uninstall_orchestrator.py` (which may itself be
part of a broken install).

**What it removes** (manifest-driven):
- Files in `~/.claude/hooks/`, `~/.claude/lib/`, `~/.claude/commands/`,
  `~/.claude/agents/`, `~/.claude/scripts/` that are listed in
  `install_manifest.json`.
- The `hooks` block in `~/.claude/settings.json` (preserves
  permissions, mcpServers, env, model, custom extensions).
- autonomous-dev entries in `~/.claude/plugins/installed_plugins.json`
  and `~/.claude/plugins/marketplaces.json`.

**What it PRESERVES** (never touched):
- `~/.claude/PROJECT.md`, `~/.claude/CLAUDE.md`, `~/.claude/.env`
- `~/.claude/logs/`, `~/.claude/archive/`, `~/.claude/memory/`
- `~/.claude/hooks/extensions/` (user-added hooks)
- Any file in those directories NOT listed in the manifest

**Backup location**: every removal/strip is copied first to
`~/.claude/backups/uninstall-YYYYMMDD-HHMMSS/<mirror-tree>/`. To
recover, restore the files from that directory.

### Usage

```bash
# Preview what would happen (no mutations).
bash install.sh --uninstall --dry-run

# Real uninstall.
bash install.sh --uninstall

# Also strip autonomous-dev hooks from specific repos' settings.json.
bash install.sh --uninstall --repos "/path/to/repo1,/path/to/repo2"

# Combine: dry-run with per-repo strip preview.
bash install.sh --uninstall --dry-run --repos "/path/to/repo1"
```

**Idempotency**: re-running on a clean state is a no-op — exits 0,
emits "Nothing to remove", and does NOT create a new backup root.

**Recovery**: if you need to roll back, the backup root is printed at
the end of every real run. Copy files from
`~/.claude/backups/uninstall-YYYYMMDD-HHMMSS/` back into place, or
re-run `bash install.sh` to reinstall fresh.

---

## Getting Help

1. **Run health check**: `/health-check` validates plugin integrity
2. **Check CLAUDE.md**: Project instructions and troubleshooting section
3. **Search issues**: [GitHub Issues](https://github.com/akaszubski/autonomous-dev/issues)
4. **Open new issue**: Include error messages, OS, Python version

---

## Version Info

- **Agents**: 15 specialists
- **Hooks**: 22 active hooks
- **Commands**: 22 active (see CLAUDE.md for full list)
- **Skills**: 17 domain packages
- **Libraries**: 196 Python utilities
