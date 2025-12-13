---
description: "Create GitHub issue with automated research and duplicate detection (--quick for fast mode)"
argument_hint: "Issue title [--quick] (e.g., 'Add JWT authentication' or 'Add JWT authentication --quick')"
---

# Create GitHub Issue with Research Integration

Automate GitHub issue creation with research-backed, well-structured content and duplicate detection.

## Modes

| Mode | Time | Description |
|------|------|-------------|
| **Default (thorough)** | 8-12 min | Full analysis, blocking duplicate check |
| **--quick** | 3-5 min | Async scan, smart sections, no prompts |

## Implementation

**CRITICAL**: Follow these steps in order. Each checkpoint validates before proceeding.

ARGUMENTS: {{ARGUMENTS}}

---

### STEP 0: Parse Arguments and Mode

Parse the ARGUMENTS to detect mode flags:

```
--quick    Fast mode (async scan, smart sections, no blocking prompts)
```

**Default mode**: Thorough mode with full analysis, blocking duplicate check, all sections.

Extract the feature request (everything except flags).

---

### STEP 1: Research + Issue Scan (Parallel)

Launch TWO agents in parallel using the Task tool:

**Agent 1: researcher** (subagent_type="researcher")
- Search codebase for similar patterns
- Research best practices and security considerations
- Identify recommended approaches

**Agent 2: issue-scanner** (subagent_type="Explore", run_in_background for --quick mode only)
- Scan existing issues for duplicates/related
- Use: `gh issue list --state all --limit 100 --json number,title,body,state`
- Look for semantic similarity to the feature request
- Confidence threshold: >80% for duplicate, >50% for related

**CRITICAL**: Use a single message with TWO Task tool calls to run in parallel.

**Default mode**: Issue scan runs in foreground (blocking) - results used in STEP 1.5
**--quick mode**: Issue scan runs in background - results retrieved in STEP 3

---

### STEP 1.5: Duplicate Check (Default Mode Only)

**Skip this step if --quick mode.**

After issue scan completes, check for duplicates:

If **duplicates found** (>80% similarity), prompt user before continuing:
```
Potential duplicate detected:
  #45: "Implement JWT authentication" (92% similar)

Options:
1. Create anyway (may be intentional)
2. Skip and link to existing issue
3. Show me the existing issue first

Reply with option number.
```

If user selects option 2, stop here and provide link to existing issue.
If user selects option 3, show the existing issue body and ask again.
If user selects option 1, continue to STEP 2.

If **related issues found** (>50% similarity but <80%), note them for later display but continue.

---

### CHECKPOINT 1: Validate Research Completion

Verify the researcher agent completed successfully:
- Research findings documented
- Patterns identified
- Security considerations noted (if relevant)

If research failed, stop and report error. Do NOT proceed to STEP 2.

---

### STEP 2: Generate Issue with Deep Thinking Methodology

Use the Task tool to invoke the **issue-creator** agent (subagent_type="issue-creator") with:
- Original feature request (from ARGUMENTS)
- Research findings (from STEP 1)
- Mode flag (default or quick)

**Deep Thinking Template** (issue-creator should follow - GitHub Issue #118):

**ALWAYS include**:

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

**--quick mode**: Include only essential sections (Summary, Implementation Approach, Acceptance Criteria).

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

If issue creation failed, stop and report error. Do NOT proceed to STEP 3.

---

### STEP 3: Create Issue (+ Retrieve Scan for --quick)

**3A: For --quick mode only - Retrieve async scan results**

Use TaskOutput tool to retrieve the issue-scanner results (non-blocking, timeout 5s).

If scan found results:
- **Duplicates** (>80% similarity): Store for post-creation info
- **Related** (>50% similarity): Store for post-creation info

**Default mode**: Duplicate check already done in STEP 1.5.

**3B: Create GitHub issue via gh CLI**

Extract the issue title and body from the issue-creator agent output.

Use the Bash tool to execute:

```bash
gh issue create --title "TITLE_HERE" --body "BODY_HERE"
```

**Security**: Title and body are validated by issue-creator agent. If gh CLI fails, provide manual fallback.

---

### CHECKPOINT 3: Validate Issue Creation

Verify the gh CLI command succeeded:
- Issue created successfully
- Issue number returned (e.g., #123)
- Issue URL returned

---

### STEP 4: Post-Creation Info + Research Cache

**4A: Display related issues (informational)**

If the scan found related issues (or duplicates in --quick mode), display them AFTER creation:

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

### STEP 5 (Optional): Offer Auto-Implement

```
Would you like to start implementing this feature now?

/auto-implement "#123"

This will use the research already completed (saves 2-5 min).
Estimated time: 15-25 minutes

Reply 'yes' to proceed, or 'no' to stop here.
```

---

## What This Does

| Step | Time | Description |
|------|------|-------------|
| Research + Scan | 2-4 min | Parallel: patterns + duplicate detection |
| Duplicate Check | 0-2 min | Blocking prompt if duplicates found (default mode) |
| Generate Issue | 1-2 min | Full sections with deep thinking |
| Create + Info | 15-30 sec | gh CLI + related issues |
| **Total** | **8-12 min** | Default mode (thorough) |
| **Total** | **3-5 min** | --quick mode |

---

## Usage

```bash
# Default mode (thorough, blocking duplicate check)
/create-issue Add JWT authentication for API endpoints

# Quick mode (fast, async scan, no blocking prompts)
/create-issue Add JWT authentication --quick

# Bug report (default thorough mode)
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

### Duplicate Detected (Default Mode)

```
Potential duplicate detected:
  #45: "Implement JWT authentication" (92% similar)

Options:
1. Create anyway
2. Skip and link to existing
3. Show existing issue

Reply with option number.
```

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
- **Explore**: Issue scan for duplicates/related (foreground default, background --quick)

**Tools Used**:
- gh CLI: Issue listing and creation
- TaskOutput: Retrieve background scan results (--quick mode)

**Security**:
- CWE-78: Command injection prevention (no shell metacharacters in title)
- CWE-20: Input validation (length limits, format validation)

**Performance**:
- Default mode: 8-12 minutes (blocking duplicate check)
- Quick mode: 3-5 minutes (no blocking prompts)

---

**Part of**: Core workflow commands
**Related**: `/auto-implement`, `/align`
**Enhanced in**: v3.42.0 (thorough default, --quick flag - GitHub Issue #122)
