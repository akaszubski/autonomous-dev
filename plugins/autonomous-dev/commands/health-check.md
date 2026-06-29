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

exit $(( STRUCT_RC | HOOK_RC | PLUGIN_REGISTERED ))
```
```

# Health Check - Plugin Component Validation

Validates all autonomous-dev plugin components to ensure the system is functioning correctly.

## Usage

```bash
/health-check
```

**Time**: < 5 seconds
**Scope**: All plugin components (agents, hooks, commands)

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
