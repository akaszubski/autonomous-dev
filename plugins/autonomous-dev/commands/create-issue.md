---
name: create-issue
description: "Create GitHub issue with automated research (--quick for fast mode)"
argument-hint: "Issue title [--quick] (e.g., 'Add JWT authentication' or 'Add JWT authentication --quick')"
allowed-tools: [Task, Read, Bash, Grep, Glob]
disable-model-invocation: false
user-invocable: true
user_facing: true
---

# Create GitHub Issue with Research Integration

Automate GitHub issue creation with research-backed, well-structured content.

## Modes

| Mode | Time | Description |
|------|------|-------------|
| **Default (thorough)** | 8-12 min | Full analysis, blocking duplicate check |
| **--quick** | 30-60 sec | Inline scan + generation, 0 agents, no prompts |

## Implementation

**CRITICAL**: Follow these steps in order. Each checkpoint validates before proceeding.

ARGUMENTS: {{ARGUMENTS}}

---

### Argument Handling

The `{{ARGUMENTS}}` placeholder is replaced with user input at runtime.

**Parsing strategy**:
1. Scan for flags: `--quick`, `--thorough` (deprecated, now default)
2. Everything remaining after flags = feature request text
3. If no text provided, prompt user for feature description

**Examples**:
- `/create-issue Add JWT authentication` → feature="Add JWT authentication", mode=default
- `/create-issue Add JWT auth --quick` → feature="Add JWT auth", mode=quick
- `/create-issue --quick Fix login bug` → feature="Fix login bug", mode=quick

---

### STEP 0: Parse Arguments and Mode

Parse the ARGUMENTS to detect mode flags:

```
--quick       Fast mode (inline scan + generation, 0 agents, no prompts)
--thorough    (Deprecated - silently accepted, now default behavior)
```

**Default mode**: Thorough mode with full analysis, blocking duplicate check, all sections.

Extract the feature request (everything except flags).

**Create command context file immediately, in its OWN separate Bash tool
call** (before any agents are spawned and before any `gh issue create`
calls):
```bash
python3 -c "
import json; from datetime import datetime, timezone
with open('/tmp/autonomous_dev_cmd_context.json', 'w') as f:
    json.dump({'command': 'create-issue', 'timestamp': datetime.now(timezone.utc).isoformat()}, f)
"
```
This context file allows the `issue-creator` agent to run `gh issue create` later. It MUST be created here, before STEP 1, because agents spawned in STEP 1-2 may need it. The context file is cleaned up at CHECKPOINT 3 or on early exit.

**Prior-call ordering contract (Issue #1203)**: The PreToolUse hook
evaluates each Bash invocation BEFORE it runs. The context-file write
above MUST be a STANDALONE Bash tool call. **FORBIDDEN: Do NOT bundle the
context write and `gh issue create` into one Bash tool call** — at hook
evaluation time the context file would not yet exist on disk and the
`gh issue create` call would be blocked. See #1203. The cleanup of the
context file MAY ride the same call as the last `gh issue create` only
when no further `gh issue create` calls follow in this command run.

---

### QUICK MODE FAST PATH (0 agents, 30-60 sec)

**HARD GATE**: If `--quick` flag is set, execute the steps below inline. Do NOT proceed to STEP 1.

**Quick Step 1: Create context file** (already done in STEP 0 above)

**Quick Step 2: Inline duplicate scan**

Run via Bash tool (no agent):
```bash
gh issue list --state open --limit 50 --json number,title
```
Compare issue titles against the feature request by keyword overlap. Store any matches for display after creation (no blocking prompt).

**Quick Step 3: Generate issue body inline**

Generate a markdown body with EXACTLY these 4 sections (no more, no less):

1. **Summary**: 1-2 sentences describing the feature/fix
2. **Implementation Approach**: Brief technical plan
3. **Test Scenarios**: 3-5 test cases (happy path, error cases, edge cases)
4. **Acceptance Criteria**: Checkboxes for verifiable conditions
5. **Plugin Version**: Include the plugin version stamp: `$(python3 -c "import sys,os;next((sys.path.insert(0,p) for p in ('.claude/lib','plugins/autonomous-dev/lib',os.path.expanduser('~/.claude/lib')) if os.path.isdir(p)),None);from version_reader import get_plugin_version;print(get_plugin_version())" 2>/dev/null || echo unknown)`

Capture a collision-safe Unix timestamp (nanoseconds — unique even across concurrent runs):
```bash
RUN_TS=$(date +%s%N)
```

Temp files use the `RUN_TS=$(date +%s%N)` unique suffix for collision-safety across concurrent runs.

Write the body to a temp file (CWE-78 prevention — never inline body as shell argument):
```bash
cat > /tmp/create_issue_body_${RUN_TS}.md << 'ISSUE_EOF'
[generated body here]
ISSUE_EOF
```

**Quick Step 4: Create the issue (chained cleanup — #1204)**

The trailing `rm` is chained onto the `gh issue create` call via `;` so the single Bash approval covers the cleanup AND the cleanup runs even on failure paths. The context-file WRITE above (in STEP 0) remains a separate prior call, preserving the #1203 contract.
```bash
gh issue create --title "TITLE" --body-file /tmp/create_issue_body_${RUN_TS}.md; rm -f /tmp/autonomous_dev_cmd_context.json /tmp/create_issue_body_${RUN_TS}.md
```

**Quick Step 5: Display result**

Show the created issue URL. If the duplicate scan in Quick Step 2 found matching issues, display them as informational below the URL (no prompt, no blocking). Cleanup already happened as part of Quick Step 4.

**END** — Do not proceed to STEP 1 or any subsequent steps.

---

### STEP 1: Research + Async Issue Scan (Parallel)

Launch TWO agents in parallel using the Task tool:

**Agent 1: researcher** (subagent_type="researcher")
- Search codebase for similar patterns
- Research best practices and security considerations
- Identify recommended approaches

**Agent 2: issue-scanner** (subagent_type="Explore", run_in_background=true)
- Quick scan of existing issues for duplicates/related
- Use: `gh issue list --state all --limit 100 --json number,title,body,state`
- Identify semantic similarity to the feature request
- Confidence threshold: >80% for duplicate, >50% for related

**CRITICAL**: Use a single message with TWO Task tool calls to run in parallel.

---

### CHECKPOINT 1: Validate Research Completion

Verify the researcher agent completed successfully:
- Research findings documented
- Patterns identified
- Security considerations noted (if relevant)

If research failed, clean up the context file and stop:
```bash
rm -f /tmp/autonomous_dev_cmd_context.json  # unavoidable: no preceding Bash call to chain onto (error-exit path)
```
Do NOT proceed to STEP 2.

**Note**: Issue scan runs in background - results retrieved in STEP 3.

---

### STEP 2: Generate Issue with Deep Thinking Methodology

Use the Task tool to invoke the **issue-creator** agent (subagent_type="issue-creator") with:
- Original feature request (from ARGUMENTS)
- Research findings (from STEP 1)
- Mode flag (default or thorough)

**Deep Thinking Template** (issue-creator should follow - GitHub Issue #118):

**ALWAYS include** (also include `**Plugin Version**: $(python3 -c "import sys,os;next((sys.path.insert(0,p) for p in ('.claude/lib','plugins/autonomous-dev/lib',os.path.expanduser('~/.claude/lib')) if os.path.isdir(p)),None);from version_reader import get_plugin_version;print(get_plugin_version())" 2>/dev/null || echo unknown)` at the end of the body):

1. **Summary**: 1-2 sentences describing the feature/fix

2. **What Does NOT Work** (negative requirements):
   - Document patterns/approaches that fail
   - Prevents future developers from re-attempting failed approaches
   - Example: "Pattern X fails because of Y"

3. **Scenarios** (update vs fresh install):
   - **Fresh Install**: What happens on new system
   - **Update/Upgrade**: What happens on existing system
     - Valid existing data: preserve/merge
     - Invalid existing data: fix/replace with backup
     - User customizations: never overwrite

4. **Implementation Approach**: Brief technical plan

5. **Test Scenarios** (multiple paths, not just happy path):
   - Fresh install (no existing data)
   - Update with valid existing data
   - Update with invalid/broken data
   - Update with user customizations
   - Rollback after failure

6. **Acceptance Criteria** (categorized):
   - **Fresh Install**: [ ] Creates correct files, [ ] No prompts needed
   - **Updates**: [ ] Preserves valid config, [ ] Fixes broken config
   - **Validation**: [ ] Reports issues clearly, [ ] Provides fix commands
   - **Security**: [ ] Blocks dangerous ops, [ ] Protects sensitive files

**Include IF relevant** (detect from research):
- **Security Considerations**: Only if security-related
- **Breaking Changes**: Only if API/behavior changes
- **Dependencies**: Only if new packages/services needed
- **Environment Requirements**: Tool versions, language versions where verified
- **Source of Truth**: Where the solution was verified, date, attempts

**NEVER include** (remove these filler sections):
- ~~Limitations~~ (usually empty)
- ~~Complexity Estimate~~ (usually inaccurate)
- ~~Estimated LOC~~ (usually wrong)
- ~~Timeline~~ (scheduling not documentation)

**--quick mode**: Include only essential sections (Summary, Implementation, Test Scenarios, Acceptance Criteria).

**Default mode**: Include ALL sections with full detail.

---

### CHECKPOINT 2: Validate Issue Content (Deep Thinking)

Verify the issue-creator agent completed successfully:
- Issue body generated
- **Required sections present**:
  - Summary (1-2 sentences)
  - What Does NOT Work (negative requirements)
  - Scenarios (fresh install + update behaviors)
  - Implementation Approach
  - Test Scenarios (multiple paths)
  - Acceptance Criteria (categorized)
- Content is well-structured markdown
- Body length < 65,000 characters (GitHub limit)
- No empty sections ("Breaking Changes: None" - remove these)
- No filler (no "TBD", "N/A" unless truly not applicable)

If issue creation failed, clean up the context file and stop:
```bash
rm -f /tmp/autonomous_dev_cmd_context.json  # unavoidable: no preceding Bash call to chain onto (error-exit path)
```
Do NOT proceed to STEP 3.

---

### STEP 3: Retrieve Scan Results + Create Issue

**3A: Retrieve async scan results**

Use TaskOutput tool to retrieve the issue-scanner results (non-blocking, timeout 5s).

If scan found results:
- **Duplicates** (>80% similarity): Store for post-creation info
- **Related** (>50% similarity): Store for post-creation info

**Default mode**: If duplicates found, prompt user before creating:
```
Potential duplicate detected:
  #45: "Implement JWT authentication" (92% similar)

Options:
1. Create anyway (may be intentional)
2. Skip and link to existing issue
3. Show me the existing issue first

Reply with option number.
```

**If user chooses option 2 (skip)**: Clean up the context file before exiting:
```bash
rm -f /tmp/autonomous_dev_cmd_context.json  # unavoidable: no preceding Bash call to chain onto (user-cancel exit path)
```

**--quick mode**: No prompts. Create issue, show info after.

**3B: Create GitHub issue via gh CLI (chained cleanup — #1204)**

Extract the issue title and body from the issue-creator agent output.

Use the Bash tool to execute. The trailing `rm` is chained onto the same call via `;` so the single Bash approval covers cleanup AND the cleanup runs on failure paths (the context-file WRITE in STEP 0 remains a standalone prior call per the #1203 contract):

```bash
gh issue create --title "TITLE_HERE" --body "BODY_HERE"; rm -f /tmp/autonomous_dev_cmd_context.json
```

**Security**: Title and body are validated by issue-creator agent. If gh CLI fails, provide manual fallback.

---

### CHECKPOINT 3: Validate Issue Creation

The context file was cleaned up as part of STEP 3B (chained `; rm -f ...`), so no separate cleanup is needed here.

Verify the gh CLI command succeeded:
- Issue created successfully
- Issue number returned (e.g., #123)
- Issue URL returned

---

### STEP 4: Post-Creation Info + Research Cache

**4A: Display related issues (informational)**

If the async scan found related/duplicate issues, display them AFTER creation:

```
Issue #123 created successfully!
  https://github.com/owner/repo/issues/123

Related issues found (consider linking):
  #12: "Add user authentication" (65% similar)
  #45: "OAuth2 integration" (58% similar)

Tip: Link related issues with:
  gh issue edit 123 --body "Related: #12, #45"
```

**4B: Cache research for /auto-implement reuse**

Save research findings to `.claude/cache/research_<issue_number>.json`:

```json
{
  "issue_number": 123,
  "feature": "JWT authentication",
  "research": {
    "patterns": [...],
    "best_practices": [...],
    "security_considerations": [...]
  },
  "created_at": "2025-12-13T10:30:00Z",
  "expires_at": "2025-12-14T10:30:00Z"
}
```

This cache is used by `/auto-implement` to skip duplicate research.

---

### STEP 5 (MANDATORY): Validation and Review

**STOP**: Before proceeding, the user MUST validate and review the created issue.

Display the following message:

```
Issue #123 created successfully!
  https://github.com/owner/repo/issues/123

**MANDATORY NEXT STEP**: Review and validate the issue before implementation

Please review the issue content at the URL above and confirm:
- [ ] Summary is accurate
- [ ] Implementation approach is correct
- [ ] Test scenarios cover all paths
- [ ] Acceptance criteria are complete

Once you've reviewed the issue, you can proceed with implementation:
  /auto-implement "#123"

This workflow ensures:
- ✅ Issue is validated before work begins
- ✅ Research is cached and reused (saves 2-5 min)
- ✅ Full traceability from issue to implementation

**Estimated implementation time**: 15-25 minutes

Wait for confirmation before proceeding. User must confirm they have reviewed the issue.
```

**Why This Is Mandatory**:
- Prevents implementing issues with incorrect requirements
- Ensures user validates research findings before committing to implementation
- Provides opportunity to revise issue before starting work
- Maintains audit trail from issue to implementation

**DO NOT** automatically proceed to /auto-implement without explicit user confirmation.

User must approve before continuing. Require confirmation that the issue has been validated.

---

## What This Does

| Step | Time | Description |
|------|------|-------------|
| Research + Scan | 2-3 min | Parallel: patterns + issue scan |
| Generate Issue | 5-8 min | All sections with full detail |
| Duplicate Check | 1-2 min | Blocking user prompt (if duplicates found) |
| Create + Info | 15-30 sec | gh CLI + related issues |
| **Total** | **8-12 min** | Default mode (thorough) |
| **Quick: Duplicate scan** | ~5 sec | gh issue list (inline, no agent) |
| **Quick: Body generation** | ~15 sec | Inline LLM call (no agent spawn) |
| **Quick: Issue creation** | ~5 sec | gh CLI with temp file |
| **Total (--quick)** | **30-60 sec** | Fast mode (0 agents, inline only) |

---

## Usage

```bash
# Default mode (thorough, all sections, blocking duplicate check)
/create-issue Add JWT authentication for API endpoints

# Quick mode (fast, smart sections, no prompts)
/create-issue Add JWT authentication --quick

# Bug report (thorough by default)
/create-issue Fix memory leak in background job processor
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

### gh CLI Not Authenticated

```
Error: gh CLI is not authenticated

Run: gh auth login
```

### Duplicate Detected (default mode)

```
Potential duplicate detected:
  #45: "Implement JWT authentication" (92% similar)

Options:
1. Create anyway
2. Skip and link to existing
3. Show existing issue

Reply with option number.
```

**Note**: Use `--quick` flag to skip this prompt and create immediately.

---

## Integration with /auto-implement

When `/auto-implement "#123"` runs on an issue created by `/create-issue`:

1. **Check research cache**: `.claude/cache/research_123.json`
2. **If found and not expired** (24h TTL):
   - Skip researcher agent (saves 2-5 min)
   - Use cached patterns, best practices, security considerations
   - Start directly with planner agent
3. **If not found or expired**:
   - Run researcher as normal

This integration saves 2-5 minutes when issues are implemented soon after creation.

---

## Technical Details

**Agents Used**:
- **researcher**: Research patterns and best practices (Haiku model, 2-3 min)
- **issue-creator**: Generate structured issue body (Sonnet model, 1-2 min)
- **Explore**: Quick issue scan for duplicates/related (background, <30 sec)

**Tools Used**:
- gh CLI: Issue listing and creation
- TaskOutput: Retrieve background scan results

**Security**:
- CWE-78: Command injection prevention (no shell metacharacters in title)
- CWE-20: Input validation (length limits, format validation)

**Performance**:
- Default mode: 8-12 minutes (thorough, with prompts)
- Quick mode: 30-60 seconds (0 agents, inline scan + generation, no prompts)

---

**Part of**: Core workflow commands
**Related**: `/auto-implement`, `/align`
**Enhanced in**: v3.41.0 (GitHub Issues #118, #122)
