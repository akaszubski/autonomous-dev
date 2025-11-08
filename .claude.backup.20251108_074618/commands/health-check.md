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

Validates 4 critical component types:

1. **Agents** (8 specialist agents)
   - orchestrator, planner, researcher, test-master
   - implementer, reviewer, security-auditor, doc-master

2. **Skills** (14 core skills)
   - python-standards, testing-guide, security-patterns
   - documentation-guide, research-patterns, consistency-enforcement
   - architecture-patterns, api-design, database-design
   - code-review, git-workflow, github-workflow, project-management, observability

3. **Hooks** (8 automation hooks)
   - auto_format.py, auto_test.py, auto_generate_tests.py
   - auto_tdd_enforcer.py, auto_add_to_regression.py
   - auto_enforce_coverage.py, auto_update_docs.py, security_scan.py

4. **Commands** (7 active commands)
   - align-project, auto-implement, health-check, setup, status, test, uninstall

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

Skills: 14/14 loaded
  python-standards .............. PASS
  testing-guide ................. PASS
  security-patterns ............. PASS
  documentation-guide ........... PASS
  research-patterns ............. PASS
  consistency-enforcement ....... PASS
  architecture-patterns ......... PASS
  api-design .................... PASS
  database-design ............... PASS
  code-review ................... PASS
  git-workflow .................. PASS
  github-workflow ............... PASS
  project-management ............ PASS
  observability ................. PASS

Hooks: 8/8 executable
  auto_format.py ................ PASS
  auto_test.py .................. PASS
  auto_generate_tests.py ........ PASS
  auto_tdd_enforcer.py .......... PASS
  auto_add_to_regression.py ..... PASS
  auto_enforce_coverage.py ...... PASS
  auto_update_docs.py ........... PASS
  security_scan.py .............. PASS

Commands: 7/7 present
  /align-project ................. PASS
  /auto-implement ................ PASS
  /health-check .................. PASS
  /setup ......................... PASS
  /status ........................ PASS
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

Skills: 13/13 loaded
  [all pass]

Hooks: 8/8 executable
  [all pass]

Commands: 20/21 present
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

**Invoke the health check script to validate plugin component integrity.**

```bash
python "$(dirname "$0")/../scripts/health_check.py"
```
