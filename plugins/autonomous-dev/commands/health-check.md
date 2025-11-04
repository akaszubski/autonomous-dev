---
description: Validate all plugin components are working correctly (agents, skills, hooks, commands)
---

## Implementation

```bash
python "$(dirname "$0")/../lib/health_check.py"
```

# Health Check - Plugin Component Validation

Validates all autonomous-dev plugin components to ensure the system is functioning correctly.

## Usage

```bash
/health-check
```

**Time**: < 5 seconds
**Scope**: All plugin components (agents, skills, hooks, commands)

## What This Does

Validates 3 critical component types:

1. **Agents** (18 specialist agents - orchestrator removed in v3.2.2)
   - Core workflow: planner, researcher, test-master, implementer, reviewer, security-auditor, doc-master
   - Utility: advisor, alignment-validator, alignment-analyzer, commit-message-generator
   - Advanced: pr-description-generator, project-bootstrapper, project-progress-tracker
   - Extended: project-status-analyzer, quality-validator, setup-wizard, sync-validator

2. **Hooks** (8 automation hooks)
   - auto_format.py, auto_test.py, auto_generate_tests.py
   - auto_tdd_enforcer.py, auto_add_to_regression.py
   - auto_enforce_coverage.py, auto_update_docs.py, security_scan.py

3. **Commands** (18 active commands per GitHub #44)
   - Core: auto-implement, align-project, align-claude, setup, sync-dev, status, health-check, pipeline-status
   - Individual agents: research, plan, test-feature, implement, review, security-scan, update-docs
   - Utility: test, uninstall, update-plugin

Note: Skills are active (19 skills) but not validated by health check - they use progressive disclosure in Claude Code 2.0+

## Expected Output

```
Running plugin health check...

============================================================
PLUGIN HEALTH CHECK REPORT
============================================================

Agents: 18/18 loaded
  advisor ....................... PASS
  alignment-analyzer ............ PASS
  alignment-validator ........... PASS
  commit-message-generator ...... PASS
  doc-master .................... PASS
  implementer ................... PASS
  planner ....................... PASS
  pr-description-generator ...... PASS
  project-bootstrapper .......... PASS
  project-progress-tracker ...... PASS
  project-status-analyzer ....... PASS
  quality-validator ............. PASS
  researcher .................... PASS
  reviewer ...................... PASS
  security-auditor .............. PASS
  setup-wizard .................. PASS
  sync-validator ................ PASS
  test-master ................... PASS

Hooks: 8/8 executable
  auto_format.py ................ PASS
  auto_test.py .................. PASS
  auto_generate_tests.py ........ PASS
  auto_tdd_enforcer.py .......... PASS
  auto_add_to_regression.py ..... PASS
  auto_enforce_coverage.py ...... PASS
  auto_update_docs.py ........... PASS
  security_scan.py .............. PASS

Commands: 18/18 present
  /align-claude .................. PASS
  /align-project ................. PASS
  /auto-implement ................ PASS
  /health-check .................. PASS
  /implement ..................... PASS
  /pipeline-status ............... PASS
  /plan .......................... PASS
  /research ...................... PASS
  /review ........................ PASS
  /security-scan ................. PASS
  /setup ......................... PASS
  /status ........................ PASS
  /sync-dev ...................... PASS
  /test .......................... PASS
  /test-feature .................. PASS
  /uninstall ..................... PASS
  /update-docs ................... PASS
  /update-plugin ................. PASS

============================================================
OVERALL STATUS: HEALTHY
============================================================

✅ All plugin components are functioning correctly!
```

## Failure Example

```
Running plugin health check...

============================================
PLUGIN HEALTH CHECK REPORT
============================================

Agents: 17/18 loaded
  advisor ..................... PASS
  alignment-analyzer .......... PASS
  alignment-validator ......... PASS
  commit-message-generator .... PASS
  doc-master .................. PASS
  implementer ................. FAIL (file missing: implementer.md)
  planner ..................... PASS
  [... other agents ...]

Hooks: 8/8 executable
  [all pass]

Commands: 17/18 present
  /test ....................... PASS
  /health-check ............... FAIL (file missing)
  [... other commands ...]

============================================
OVERALL STATUS: DEGRADED (2 issues found)
============================================

⚠️  Issues detected:
  1. Agent 'implementer' missing: ~/.claude/plugins/autonomous-dev/agents/implementer.md
  2. Command '/health-check' missing: ~/.claude/plugins/autonomous-dev/commands/health-check.md

Action: Reinstall plugin with /plugin uninstall autonomous-dev && /plugin install autonomous-dev
```

## When to Use

- After plugin installation (verify setup)
- Before starting a new feature (validate environment)
- After plugin updates (ensure compatibility)
- When debugging plugin issues (identify missing components)
- Regular system validation (weekly/monthly checks)

## Related Commands

- `/setup` - Interactive setup wizard
- `/align-project` - Validate PROJECT.md alignment
- `/test` - Run all automated tests

---

**Invoke the health check script to validate plugin component integrity.**

```bash
python "$(dirname "$0")/../scripts/health_check.py"
```
