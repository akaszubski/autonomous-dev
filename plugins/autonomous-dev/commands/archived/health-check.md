---
description: Validate all plugin components are working correctly (agents, hooks, commands)
---

# Health Check - Plugin Component Validation

Validates all autonomous-dev plugin components to ensure the system is functioning correctly.

## Usage

```bash
/health-check
```

**Time**: < 5 seconds
**Scope**: All plugin components (agents, hooks, commands)

**Note**: Skills removed per [Issue #5](https://github.com/akaszubski/autonomous-dev/issues/5) - PROJECT.md: "No skills/ directory - anti-pattern"

## What This Does

Validates 3 critical component types:

1. **Agents** (8 specialist agents)
   - orchestrator, planner, researcher, test-master
   - implementer, reviewer, security-auditor, doc-master

2. **Hooks** (8 automation hooks)
   - auto_format.py, auto_test.py, auto_generate_tests.py
   - auto_tdd_enforcer.py, auto_add_to_regression.py
   - auto_enforce_coverage.py, auto_update_docs.py, security_scan.py

3. **Commands** (8 core commands)
   - align-project, auto-implement, health-check, setup, status, sync-dev, test, uninstall

## Expected Output

```
Running plugin health check...

============================================================
PLUGIN HEALTH CHECK REPORT
============================================================

Agents: 8/8 loaded
  orchestrator .................. PASS
  planner ....................... PASS
  researcher .................... PASS
  test-master ................... PASS
  implementer ................... PASS
  reviewer ...................... PASS
  security-auditor .............. PASS
  doc-master .................... PASS

Hooks: 8/8 executable
  auto_format.py ................ PASS
  auto_test.py .................. PASS
  auto_generate_tests.py ........ PASS
  auto_tdd_enforcer.py .......... PASS
  auto_add_to_regression.py ..... PASS
  auto_enforce_coverage.py ...... PASS
  auto_update_docs.py ........... PASS
  security_scan.py .............. PASS

Commands: 8/8 present
  /align-project ................. PASS
  /auto-implement ................ PASS
  /health-check .................. PASS
  /setup ......................... PASS
  /status ........................ PASS
  /sync-dev ...................... PASS
  /test .......................... PASS
  /uninstall ..................... PASS

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

Agents: 7/8 loaded
  orchestrator ................ PASS
  planner ..................... PASS
  researcher .................. PASS
  test-master ................. PASS
  implementer ................. FAIL (file missing: implementer.md)
  reviewer .................... PASS
  security-auditor ............ PASS
  doc-master .................. PASS

Hooks: 8/8 executable
  [all pass]

Commands: 7/8 present
  /test ....................... PASS
  /health-check ............... FAIL (file missing)
  [... other commands ...]

============================================
OVERALL STATUS: DEGRADED (2 issues found)
============================================

Issues:
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

## Implementation

Invoke the health check script to validate plugin component integrity.

```bash
python "$(dirname "$0")/../scripts/health_check.py"
```
