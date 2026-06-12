---
name: plan-to-issues
description: "Batch-convert plan mode output into GitHub issues (--quick for fast mode)"
argument-hint: "[--quick] (e.g., '/plan-to-issues' or '/plan-to-issues --quick')"
allowed-tools: [Agent, Read, Bash, Grep, Glob]
disable-model-invocation: false
user-invocable: true
---

# Batch-Convert Plan into GitHub Issues

Convert plan mode output (or any discussed plan) into individual, trackable GitHub issues.

> **Note**: `/plan` automatically runs issue creation in quick mode after plan-critic PROCEED. Use `/plan-to-issues` directly for thorough mode (full section templates) or if auto-creation was skipped (`--no-issues`).

## Modes

| Mode | Time | Description |
|------|------|-------------|
| **Default (thorough)** | 10-15 min | Full issue bodies with all sections |
| **--quick** | 5-8 min | Summary, Implementation, Acceptance Criteria only |

## Implementation

**CRITICAL**: Follow these steps in order. Each checkpoint validates before proceeding.

ARGUMENTS: {{ARGUMENTS}}

---

### STEP 0: Parse Arguments

Parse the `{{ARGUMENTS}}` placeholder for flags:

```
--quick       Fast mode (fewer sections per issue, no prompts)
```

If `--quick` is present, set quick_mode=true. Everything else is ignored (plan comes from context).

---

### STEP 0.5: Detect Plan Files

Detect whether `.claude/plans/` directory exists and contains plan files:

```bash
ls -la .claude/plans/*.md 2>/dev/null
```

If plan files are found, offer them as the input source instead of conversation context:

```
Found plan files in .claude/plans/:
  - feature-name.md (created 2h ago)
  - other-feature.md (created 1d ago)

Use plan file as input? (recommended if you just ran /plan)
1. Use latest plan file
2. Use conversation context (default)
```

If the user selects a plan file, read its contents and use that as the plan source for Step 1.

---

### STEP 1: Extract Plan Items

The plan is in the **current conversation context** (or from a `.claude/plans/` file selected in Step 0.5). Extract individual work items by scanning for structural markers:

**Patterns to match** (in order of specificity):
1. Numbered lists: `1. Item description`, `2. Another item`
2. Bold bullet items: `- **Phase 1: Name** -- description`
3. Section headers: `## Phase 1: Name`
4. Task items: `- [ ] Task description`, `- [x] Done task`
5. Unicode markers: `task description`
6. Phase/step labels: `Phase N:`, `Step N:`

**Each extracted item needs**:
- A short title (suitable for GitHub issue title, prefixed with `feat:`, `fix:`, `refactor:`, etc.)
- A description (the content/details associated with that item)

**Plan mode exit marker**: Detect `.claude/plan_mode_exit.json`. If it exists, note it as confirmation that plan mode was used. Read any `plan_content` field from the marker to supplement extraction.

**If no items can be extracted**: Prompt the user to describe the plan items explicitly. Do NOT proceed without items.

---

### CHECKPOINT: Validate Extraction

Verify:
- At least 1 item was extracted
- Cap at 20 issues maximum (if more than 20, warn the user and ask them to prioritize)
- Display the extracted items in a numbered list:

```
Extracted N plan items:

  1. feat: Project model system -- Core data model for projects
  2. feat: Recipe YAML configs -- Configuration file format
  3. refactor: CLI argument parser -- Modernize argument handling
  ...

Are these correct? Reply 'yes' to proceed, or describe corrections.
```

**REQUIRE** explicit user confirmation before proceeding. Do NOT auto-proceed.

---

### STEP 2: Generate Issue Bodies

For each extracted item, invoke the **issue-creator** agent (subagent_type="issue-creator") with:
- The item title and description
- Mode flag (quick or default)

**In --quick mode**: Tell the agent to include ONLY:
1. Summary (1-2 sentences)
2. Implementation Approach
3. Acceptance Criteria

**In default mode**: Tell the agent to include the full template (Summary, What Does NOT Work, Scenarios, Implementation Approach, Test Scenarios, Acceptance Criteria).

**CRITICAL**: Run issue-creator calls SEQUENTIALLY (one at a time), not in parallel. Parallel calls would explode context size.

Collect the generated title and body for each item.

---

### STEP 3: Preview Table

Display a dry-run table showing all issues that will be created:

```
Issues to create (N total):

  # | Title                              | Sections
  --|------------------------------------|---------
  1 | feat: Project model system          | 6
  2 | feat: Recipe YAML configs           | 6
  3 | refactor: CLI argument parser       | 3
  ...

Create these N issues? Reply 'yes' to proceed, 'no' to cancel.
```

**REQUIRE** explicit user confirmation. Do NOT proceed without it.

---

### STEP 4: Create Issues

For each confirmed item, use the Bash tool:

1. Write the issue body to a temp file (include `**Plugin Version**: $(python3 -c "import sys,os;next((sys.path.insert(0,p) for p in ('.claude/lib','plugins/autonomous-dev/lib',os.path.expanduser('~/.claude/lib')) if os.path.isdir(p)),None);from version_reader import get_plugin_version;print(get_plugin_version())" 2>/dev/null || echo unknown)` at the end of the body):
   ```bash
   cat > /tmp/plan_issue_N.md << 'ISSUE_EOF'
   <issue body content>
   ISSUE_EOF
   ```

2. Sanitize the title:
   - Strip backticks, semicolons, pipes, dollar signs
   - Limit to 256 characters
   - Escape double quotes

3. Before the first issue, create the command context file to allow gh
   issue create (Issue #599). **MUST be its OWN STANDALONE Bash tool
   call**, run BEFORE any `gh issue create` invocation:
   ```bash
   python3 -c "
   import json; from datetime import datetime, timezone
   with open('/tmp/autonomous_dev_cmd_context.json', 'w') as f:
       json.dump({'command': 'plan-to-issues', 'timestamp': datetime.now(timezone.utc).isoformat()}, f)
   "
   ```

   **Prior-call ordering contract (Issue #1203)**: the PreToolUse hook
   evaluates each Bash invocation BEFORE it runs. **FORBIDDEN: Do NOT
   bundle the context write and `gh issue create` into one Bash tool
   call** — the hook would not see the context at evaluation time and
   would block (see #1203).

4. Create the issue (separate Bash call from step 3). Each `gh issue create`
   call MUST end with `; rm -f /tmp/plan_issue_${N}.md` (per-issue temp file);
   the final call also chains `/tmp/autonomous_dev_cmd_context.json` (context
   file). Standalone `rm` calls re-introduce a user-visible permission prompt
   (Issue #1204). The #1203 standalone-prior-write contract is preserved —
   the context-file WRITE in step 3 stays its own call; only the cleanup rides
   the final create.

   Mid-loop iterations (every iteration EXCEPT the last):
   ```bash
   gh issue create --title "SANITIZED_TITLE" --body-file /tmp/plan_issue_N.md; rm -f /tmp/plan_issue_N.md
   ```

   Final iteration of the loop (chains context-file cleanup):
   ```bash
   gh issue create --title "SANITIZED_TITLE" --body-file /tmp/plan_issue_N.md; rm -f /tmp/plan_issue_N.md /tmp/autonomous_dev_cmd_context.json
   ```

5. Sleep 1 second between calls (GitHub rate limiting)

6. Collect created issue numbers and URLs

**Error handling**: If `gh issue create` fails for one issue, log the error and continue with the remaining issues. Report failures in the summary. The trailing `; rm -f ...` clause runs even when `gh issue create` fails, so per-issue cleanup happens on partial failure paths too. Note: if the FINAL create fails, the context-file cleanup ALSO runs (via the same `;`-chain), so the context never leaks across runs.

---

### STEP 5: Output Summary

Display the final summary:

```
Created N issues:
  #101: feat: Project model system
  #102: feat: Recipe YAML configs
  #103: refactor: CLI argument parser
  ...

Ready to implement:
  /implement --issues #101,#102,#103

Research cached for reuse by /implement.
```

**Cleanup**:
- Per-issue temp files (`/tmp/plan_issue_${N}.md`) and the context file (`/tmp/autonomous_dev_cmd_context.json`) are removed inline via the `; rm -f ...` clauses chained onto each `gh issue create` call in STEP 4 (Issue #1204). No separate cleanup call is needed.
- Consume plan_mode_exit marker if present: delete `.claude/plan_mode_exit.json`

If any issues failed to create, list them separately:

```
Failed to create (N):
  - "feat: Widget system" -- Error: gh: not authenticated
```

---

## Prerequisites

**Required**:
- gh CLI installed: https://cli.github.com/
- gh CLI authenticated: `gh auth login`
- Git repository with GitHub remote

---

## Error Handling

### gh CLI Not Installed

```
Error: gh CLI is not installed

Install gh CLI:
  macOS: brew install gh
  Linux: See https://cli.github.com/
  Windows: Download from https://cli.github.com/

After installing, authenticate:
  gh auth login
```

### No Plan Items Found

```
No plan items detected in the current conversation.

Please describe the items you want to create issues for, either:
1. As a numbered list: "1. Feature A  2. Feature B  3. Feature C"
2. Or describe the plan and I'll extract items from it
```

### Too Many Items

```
Warning: Extracted 25 items (max 20 per batch).

Please prioritize -- which items should be created first?
Or split into multiple /plan-to-issues runs.
```

---

## Usage

```bash
# Default mode (thorough, all sections)
/plan-to-issues

# Quick mode (fewer sections, faster)
/plan-to-issues --quick
```

---

## Technical Details

**Agents Used**:
- **issue-creator**: Generate structured issue body (sequential calls)

**Tools Used**:
- gh CLI: Issue creation
- Bash: File operations and gh commands

**Security**:
- CWE-78: Command injection prevention (title sanitization)
- CWE-20: Input validation (length limits, character filtering)

---

**Part of**: Core workflow commands
**Related**: `/create-issue`, `/implement --issues`
**Introduced in**: v3.51.0 (GitHub Issue #488)
