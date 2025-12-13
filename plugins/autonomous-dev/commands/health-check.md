---
description: Validate all plugin components are working correctly (agents, hooks, commands)
---

## Implementation

```bash
PYTHONPATH=. python "$(dirname "$0")/../hooks/health_check.py"
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

1. **Agents** (20 specialist agents)
   - Core workflow: planner, researcher, test-master, implementer, reviewer, security-auditor, doc-master
   - Utility: advisor, alignment-validator, alignment-analyzer, commit-message-generator
   - Advanced: pr-description-generator, project-bootstrapper, project-progress-tracker
   - Extended: project-status-analyzer, quality-validator, setup-wizard, sync-validator
   - Brownfield: brownfield-analyzer, issue-creator

2. **Hooks** (13 core automation hooks)
   - auto_format.py, auto_test.py, auto_git_workflow.py
   - detect_feature_request.py, enforce_file_organization.py
   - enforce_pipeline_complete.py, enforce_tdd.py, pre_tool_use.py
   - security_scan.py, session_tracker.py, validate_claude_alignment.py
   - validate_command_file_ops.py, validate_project_alignment.py

3. **Commands** (7 active commands)
   - Core: auto-implement, batch-implement, align, setup, sync, health-check, create-issue

4. **Marketplace Version** (optional)
   - Detects version differences between marketplace and project plugin
   - Shows available upgrades/downgrades

## Expected Output

```
Running plugin health check...

============================================================
PLUGIN HEALTH CHECK REPORT
============================================================

Agents: 20/20 loaded
  advisor ....................... PASS
  alignment-analyzer ............ PASS
  alignment-validator ........... PASS
  brownfield-analyzer ........... PASS
  commit-message-generator ...... PASS
  doc-master .................... PASS
  implementer ................... PASS
  issue-creator ................. PASS
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

Hooks: 13/13 executable
  auto_format.py ................ PASS
  auto_test.py .................. PASS
  auto_git_workflow.py .......... PASS
  detect_feature_request.py ..... PASS
  enforce_file_organization.py .. PASS
  enforce_pipeline_complete.py .. PASS
  enforce_tdd.py ................ PASS
  pre_tool_use.py ............... PASS
  security_scan.py .............. PASS
  session_tracker.py ............ PASS
  validate_claude_alignment.py .. PASS
  validate_command_file_ops.py .. PASS
  validate_project_alignment.py . PASS

Commands: 7/7 present
  /align ......................... PASS
  /auto-implement ................ PASS
  /batch-implement ............... PASS
  /create-issue .................. PASS
  /health-check .................. PASS
  /setup ......................... PASS
  /sync .......................... PASS

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

Agents: 19/20 loaded
  advisor ..................... PASS
  implementer ................. FAIL (file missing: implementer.md)
  [... other agents ...]

Commands: 6/7 present
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
- To check for marketplace updates

## Related Commands

- `/setup` - Interactive setup wizard
- `/align` - Validate PROJECT.md alignment
- `/sync` - Sync plugin files

---

**Validates plugin component integrity with pass/fail status for each component.**
