---
description: Create GitHub issue with automated research and structured content
argument-hint: Feature request or issue title (e.g., "Add JWT authentication")
---

# Create GitHub Issue with Research Integration

Automate GitHub issue creation with research-backed, well-structured content.

## Modes

| Mode | Time | Description |
|------|------|-------------|
| **Default (fast)** | 3-5 min | Async scan, smart sections, no prompts |
| **--thorough** | 8-12 min | Full analysis, blocking duplicate check |

## Implementation

**CRITICAL**: Follow these steps in order. Each checkpoint validates before proceeding.

ARGUMENTS: {{ARGUMENTS}}

---

### STEP 0: Parse Arguments and Mode

Parse the ARGUMENTS to detect mode flags:

```
--thorough    Full analysis mode (blocking duplicate check, all sections)
```

**Default mode**: Fast mode with async scan, smart sections, no blocking prompts.

Extract the feature request (everything except flags).

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
- Look for semantic similarity to the feature request
- Confidence threshold: >80% for duplicate, >50% for related

**CRITICAL**: Use a single message with TWO Task tool calls to run in parallel.

---

### CHECKPOINT 1: Validate Research Completion

Verify the researcher agent completed successfully:
- Research findings documented
- Patterns identified
- Security considerations noted (if relevant)

If research failed, stop and report error. Do NOT proceed to STEP 2.

**Note**: Issue scan runs in background - results retrieved in STEP 3.

---

### STEP 2: Generate Issue with Smart Sections

Use the Task tool to invoke the **issue-creator** agent (subagent_type="issue-creator") with:
- Original feature request (from ARGUMENTS)
- Research findings (from STEP 1)
- Mode flag (default or thorough)

**Smart Sections Logic** (issue-creator should follow):

**ALWAYS include**:
- **Summary**: 1-2 sentences describing the feature/fix
- **Acceptance Criteria**: Testable requirements (3-8 items)
- **Implementation Approach**: Brief technical plan

**Include IF relevant** (detect from research):
- **Security Considerations**: Only if security-related (auth, crypto, input validation)
- **Breaking Changes**: Only if API/behavior changes
- **Dependencies**: Only if new packages/services needed
- **Edge Cases**: Only if complex logic with corner cases

**NEVER include** (remove these filler sections):
- ~~Limitations~~ (usually empty)
- ~~Complexity Estimate~~ (usually inaccurate)
- ~~Estimated LOC~~ (usually wrong)
- ~~Timeline~~ (scheduling not documentation)

**--thorough mode**: Include ALL sections regardless of relevance.

---

### CHECKPOINT 2: Validate Issue Content

Verify the issue-creator agent completed successfully:
- Issue body generated
- Required sections present (Summary, Acceptance Criteria, Implementation Approach)
- Content is well-structured markdown
- Body length < 65,000 characters (GitHub limit)
- No empty sections ("Breaking Changes: None" - remove these)

If issue creation failed, stop and report error. Do NOT proceed to STEP 3.

---

### STEP 3: Retrieve Scan Results + Create Issue

**3A: Retrieve async scan results**

Use TaskOutput tool to retrieve the issue-scanner results (non-blocking, timeout 5s).

If scan found results:
- **Duplicates** (>80% similarity): Store for post-creation info
- **Related** (>50% similarity): Store for post-creation info

**--thorough mode only**: If duplicates found, prompt user before creating:
```
Potential duplicate detected:
  #45: "Implement JWT authentication" (92% similar)

Options:
1. Create anyway (may be intentional)
2. Skip and link to existing issue
3. Show me the existing issue first

Reply with option number.
```

**Default mode**: No prompts. Create issue, show info after.

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
| Research + Scan | 2-3 min | Parallel: patterns + issue scan |
| Generate Issue | 1-2 min | Smart sections only |
| Create + Info | 15-30 sec | gh CLI + related issues |
| **Total** | **3-5 min** | Default mode |

---

## Usage

```bash
# Default mode (fast, smart sections)
/create-issue Add JWT authentication for API endpoints

# Thorough mode (all sections, blocking duplicate check)
/create-issue Add JWT authentication --thorough

# Bug report
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

### Duplicate Detected (--thorough mode)

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
- **Explore**: Quick issue scan for duplicates/related (background, <30 sec)

**Tools Used**:
- gh CLI: Issue listing and creation
- TaskOutput: Retrieve background scan results

**Security**:
- CWE-78: Command injection prevention (no shell metacharacters in title)
- CWE-20: Input validation (length limits, format validation)

**Performance**:
- Default mode: 3-5 minutes (no prompts)
- Thorough mode: 8-12 minutes (with prompts)

---

**Part of**: Core workflow commands
**Related**: `/auto-implement`, `/align`
**Enhanced in**: v3.41.0 (GitHub Issue #122)
