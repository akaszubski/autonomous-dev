---
name: health-check
description: Validate all plugin components are working correctly (agents, hooks, commands)
argument-hint: "[--verbose]"
allowed-tools: [Read, Bash, Grep, Glob]
disable-model-invocation: true
user-invocable: true
user_facing: true
---

## Implementation

```bash
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
PYTHONPATH="$PROJECT_ROOT/plugins/autonomous-dev/lib:$PYTHONPATH" \
  python "$PROJECT_ROOT/scripts/validate_structure.py"
STRUCT_RC=$?
PYTHONPATH="$PROJECT_ROOT/plugins/autonomous-dev/lib:$PYTHONPATH" \
  python -m hook_path_validator \
    --global-settings "$HOME/.claude/settings.json" \
    --local-settings "$PROJECT_ROOT/.claude/settings.local.json" \
    --project-root "$PROJECT_ROOT"
HOOK_RC=$?

# Check plugin registration (Issue #945)
PLUGIN_REGISTERED=0
if [[ -f "$HOME/.claude/plugins/installed_plugins.json" ]]; then
  if python3 -c "import json; data=json.load(open('$HOME/.claude/plugins/installed_plugins.json')); plugins=[p for p in data.get('plugins',[]) if p.get('name')=='autonomous-dev']; exit(0 if plugins else 1)" 2>/dev/null; then
    echo "✓ Plugin registered in installed_plugins.json"
    PLUGIN_REGISTERED=0
  else
    echo "⚠ Plugin NOT registered - slash commands won't work"
    echo "  Run: /plugin marketplace add akaszubski/autonomous-dev"
    echo "  Then: /plugin install autonomous-dev"
    PLUGIN_REGISTERED=1
  fi
else
  echo "⚠ No installed_plugins.json found - plugin not registered"
  PLUGIN_REGISTERED=1
fi

# Proof-of-block (Issue #1586): the ONLY per-repo invocation point that
# demonstrates a guard REFUSING the bad case and PERMITTING the legitimate one.
# Resolves across both layouts: installed (.claude/scripts) and source
# (plugins/autonomous-dev/scripts).
#
# --no-fault is a MEASURED branch, not a preference. Measured 2026-08-21 on
# this repo: full run 22.9s, --no-fault 10.2s. The rest of this command runs in
# under 1s and the doc below budgets the whole thing. --no-fault still drives
# both control arms for every guard (positive must refuse / negative must
# permit), so the REFUSING+PERMITTING evidence is intact; only the fault
# CLASSIFICATION arm is skipped, and that arm's consumer is the CI ratchet,
# which passes --check-silent-regression and never runs here.
#
# Deliberately NOT part of the exit OR below. A consumer-side check that turns
# /health-check permanently red would train bypass of the whole command -- the
# failure mode already visible in a committed .claude/.bypass elsewhere. The
# machine reader is --log-activity, which appends one `"type": "proof_of_block"`
# row to .claude/logs/activity/ for continuous-improvement-analyst and /improve.
POB=""
for CANDIDATE in \
  "$PROJECT_ROOT/.claude/scripts/proof_of_block.py" \
  "$PROJECT_ROOT/plugins/autonomous-dev/scripts/proof_of_block.py"; do
  if [[ -f "$CANDIDATE" ]]; then POB="$CANDIDATE"; break; fi
done
if [[ -n "$POB" ]]; then
  python3 "$POB" --no-fault --log-activity
  echo "PROOF-OF-BLOCK: exit $?"
else
  echo "PROOF-OF-BLOCK: not installed (run /sync)"
fi

# Deploy provenance (Issue #1610): deploy-all.sh copies the WORKING TREE, so
# code that no validator approved can be the code that enforces. This reports
# the commit the executing .claude/ tree came from and NAMES any file running
# uncommitted content or drifting from the deploy record.
#
# Resolves across both layouts, same as proof-of-block above: installed
# (.claude/scripts) and source (plugins/autonomous-dev/scripts). Pure stdlib,
# no git required in the consumer repo — it reads .claude/.deploy-state.json.
#
# Deliberately NOT part of the exit OR below, for the same reason as
# proof-of-block: a consumer-side check that turns /health-check permanently
# red trains bypass of the whole command. On a correctly deployed tree it
# prints one OK line and nothing else.
DEPLOY_STATE_CHECK=""
for CANDIDATE in \
  "$PROJECT_ROOT/.claude/scripts/deploy_state.py" \
  "$PROJECT_ROOT/plugins/autonomous-dev/scripts/deploy_state.py"; do
  if [[ -f "$CANDIDATE" ]]; then DEPLOY_STATE_CHECK="$CANDIDATE"; break; fi
done
if [[ -n "$DEPLOY_STATE_CHECK" ]]; then
  python3 "$DEPLOY_STATE_CHECK" check --repo "$PROJECT_ROOT"
  echo "DEPLOY-STATE: exit $?"
else
  echo "DEPLOY-STATE: not installed (run /sync)"
fi

exit $(( STRUCT_RC | HOOK_RC | PLUGIN_REGISTERED ))
```
```

# Health Check - Plugin Component Validation

Validates all autonomous-dev plugin components to ensure the system is functioning correctly.

## Usage

```bash
/health-check
```

**Time**: ~12 seconds (component validation < 1s, plus a ~10s proof-of-block run — measured 2026-08-21)
**Scope**: All plugin components (agents, hooks, commands) plus live guard enforcement

## What This Does

Validates 3 critical component types:

1. **Agents** (8 active agents - Issue #147)
   - Pipeline: researcher-local, planner, test-master, implementer, reviewer, security-auditor, doc-master
   - Utility: issue-creator

2. **Hooks** (12 core automation hooks - Issue #144)
   - auto_format.py, auto_test.py, enforce_tdd.py, security_scan.py
   - unified_pre_tool.py, unified_prompt_validator.py
   - validate_command_file_ops.py, validate_project_alignment.py, session_activity_logger.py

3. **Commands** (8 active commands)
   - Core: advise, auto-implement, batch-implement, align, setup, sync, health-check, create-issue

4. **Marketplace Version** (optional)
   - Detects version differences between marketplace and project plugin
   - Shows available upgrades/downgrades

5. **Hook Path Validation** (Issue #950)
   - REQUIRED: every `hooks.<event>[].hooks[].command` in `~/.claude/settings.json` and `.claude/settings.local.json` MUST resolve to an existing file
   - REQUIRED: shell scripts (`.sh`, `.bash`, `.zsh`) MUST have the execute bit set
   - FORBIDDEN: the same canonical hook path registered in BOTH global and local settings (warning — fires twice)
   - FORBIDDEN: hook commands referencing undefined environment variables (e.g. `$UNDEFINED_VAR`)
   - Exit code 1 indicates required action; exit code 0 means all hook paths are healthy


6. **Plugin Registration** (Issue #945)
   - Verifies autonomous-dev entry exists in ~/.claude/plugins/installed_plugins.json
   - Reports if plugin is not registered (slash commands won't work)
   - Shows registered version and source path

7. **Proof-of-Block** (Issue #1586)
   - Drives each block-capable guard END-TO-END as a subprocess and watches it
     REFUSE a realistic bad action and PERMIT the closest legitimate one
   - A guard is not enforcement until it has been watched refusing something;
     unit tests prove a function runs, not that a guard is registered, reachable
     and loaded from the copy production uses
   - Prints `PROOF-OF-BLOCK: exit N`. **Does NOT affect this command's exit
     status** — a permanently-red consumer check would train bypass of the whole
     command
   - Appends one `"type": "proof_of_block"` row to `.claude/logs/activity/` so
     `continuous-improvement-analyst` and `/improve` can see a repo's enforcement
     state without a new channel. Filter on `type == "proof_of_block"`
   - Prints resolved `REPO`/`HOOKS`/`ARTIFACTS` and `bypass: present|absent`
     first. Under a committed `.claude/.bypass` every guard legitimately allows,
     and that must be distinguishable from breakage

8. **Deploy Provenance** (Issue #1610)
   - `deploy-all.sh` copies the **working tree**, not `HEAD`, so uncommitted
     code can be the code that enforces. Measured instance: a hook library
     executing at 684 lines that existed in no commit — `git` could not revert it
   - Reports the commit the executing `.claude/` tree was deployed from, and
     NAMES any file running uncommitted content, drifting from
     `.claude/.deploy-state.json`, or **present in the executing tree but
     absent from the record** — the reverse direction, which is how a file
     dropped into `.claude/lib/` after the deploy gets caught (hooks insert
     that directory at `sys.path[0]`)
   - Prints `DEPLOY-STATE: exit N`. **Does NOT affect this command's exit
     status** — same no-cry-wolf reasoning as proof-of-block
   - Also names files that were **already in the target when the deploy was
     stamped** and that no source file accounts for. The reverse comparison
     above cannot see those: the stamp walks the target, so a stray already
     present is adopted into the record as legitimate and `executing − recorded`
     is empty by construction. This arm compares against the **source** instead
   - `exit 0` = executing tree matches a clean deploy record (one OK line, no
     noise); `exit 1` = uncommitted, drifted, missing or unrecorded files, files
     no source accounts for, or a recorded symlink pointing outside the deployed
     tree — all named; `exit 2` = provenance unknown — no deploy record, a
     record that is unparseable, or a record whose digest map is empty and
     therefore verifies nothing. An empty record NEVER reports OK
   - Files recorded as uncommitted **at deploy time** that have since been
     committed, with the executing bytes untouched, are re-verified against the
     source repo when it is reachable and stop being reported. A check that
     stays red after the operator did the right thing is the one people learn
     to skip
   - Pure stdlib and git-free in the consumer repo: it reads the stamped
     artifact, so it works from an installed tree with no plugin source

## Expected Output

```
Running plugin health check...

============================================================
PLUGIN HEALTH CHECK REPORT
============================================================

Agents: 8/8 loaded
  doc-master .................... PASS
  implementer ................... PASS
  issue-creator ................. PASS
  planner ....................... PASS
  researcher-local .............. PASS
  reviewer ...................... PASS
  security-auditor .............. PASS
  test-master ................... PASS

Hooks: 12/12 executable
  auto_format.py ................ PASS
  auto_test.py .................. PASS
  enforce_tdd.py ................. PASS
  enforce_orchestrator.py ....... PASS
  enforce_tdd.py ................ PASS
  security_scan.py .............. PASS
  unified_pre_tool.py ........... PASS
  unified_prompt_validator.py ... PASS
  stop_quality_gate.py .......... PASS
  validate_project_alignment.py . PASS
  validate_command_file_ops.py .. PASS
  validate_project_alignment.py . PASS

Commands: 8/8 present
  /advise ....................... PASS
  /align ........................ PASS
  /auto-implement ............... PASS
  /batch-implement .............. PASS
  /create-issue ................. PASS
  /health-check ................. PASS
  /setup ........................ PASS
  /sync ......................... PASS

Marketplace: N/A | Project: N/A | Status: UNKNOWN

============================================================
OVERALL STATUS: HEALTHY
============================================================

All plugin components are functioning correctly!
```

## Failure Example

```
Running plugin health check...

============================================
PLUGIN HEALTH CHECK REPORT
============================================

Agents: 7/8 loaded
  doc-master .................. PASS
  implementer ................. FAIL (file missing: implementer.md)
  [... other agents ...]

Commands: 7/8 present
  /sync ....................... FAIL (file missing)
  [... other commands ...]

============================================
OVERALL STATUS: DEGRADED (2 issues found)
============================================

Issues detected:
  1. Agent 'implementer' missing
  2. Command '/sync' missing

Action: Run /sync --marketplace to reinstall
```

## When to Use

- After plugin installation (verify setup)
- Before starting a new feature (validate environment)
- After plugin updates (ensure compatibility)
- When debugging plugin issues (identify missing components)
- When marketplace updates MUST be detected

## Related Commands

- `/setup` - Interactive setup wizard
- `/align` - Validate PROJECT.md alignment
- `/sync` - Sync plugin files

---

**Validates plugin component integrity with pass/fail status for each component.**
