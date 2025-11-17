---
description: Create GitHub issue with automated research and structured content
argument-hint: Feature request or issue title (e.g., "Add JWT authentication")
---

# Create GitHub Issue with Research Integration

Automate GitHub issue creation with research-backed, well-structured content.

## Implementation

**CRITICAL**: Follow these steps in order. Each checkpoint validates before proceeding.

ARGUMENTS: {{ARGUMENTS}}

---

### STEP 1: Research Patterns and Best Practices

Use the Task tool to invoke the **researcher** agent (subagent_type="researcher") with the feature request from ARGUMENTS.

The researcher will:
- Search codebase for similar patterns
- Research best practices and security considerations
- Identify recommended approaches

---

### CHECKPOINT 1: Validate Research Completion

Verify the researcher agent completed successfully:
- ✓ Research findings documented
- ✓ Patterns identified
- ✓ Security considerations noted

If research failed, stop and report error. Do NOT proceed to STEP 2.

---

### STEP 2: Generate Issue Description

Use the Task tool to invoke the **issue-creator** agent (subagent_type="issue-creator") with:
- Original feature request (from ARGUMENTS)
- Research findings (from STEP 1)

The issue-creator will generate a structured GitHub issue body with:
- Description
- Research findings
- Implementation plan
- Acceptance criteria
- References

---

### CHECKPOINT 2: Validate Issue Content

Verify the issue-creator agent completed successfully:
- ✓ Issue body generated
- ✓ All required sections present (Description, Research Findings, Implementation Plan, Acceptance Criteria, References)
- ✓ Content is well-structured markdown
- ✓ Body length < 65,000 characters (GitHub limit)

If issue creation failed, stop and report error. Do NOT proceed to STEP 3.

---

### STEP 3: Create GitHub Issue via gh CLI

Extract the issue title and body from the issue-creator agent output.

**Title**: Use the original ARGUMENTS as the issue title (or extract from issue-creator if provided)

**Body**: Use the complete markdown output from issue-creator agent

Use the Bash tool to execute the gh CLI command with inline validation:

```bash
# Validation function
validate_and_create_issue() {
  local title="$1"
  local body="$2"

  # Check gh CLI is installed
  if ! command -v gh >/dev/null 2>&1; then
    echo "Error: gh CLI is not installed"
    echo ""
    echo "Install gh CLI:"
    echo "  macOS: brew install gh"
    echo "  Linux: See https://cli.github.com/"
    echo "  Windows: Download from https://cli.github.com/"
    echo ""
    echo "After installing, authenticate:"
    echo "  gh auth login"
    return 1
  fi

  # Check gh CLI is authenticated
  if ! gh auth status >/dev/null 2>&1; then
    echo "Error: gh CLI is not authenticated"
    echo ""
    echo "Run this command to authenticate:"
    echo "  gh auth login"
    echo ""
    echo "Follow the prompts to complete authentication."
    return 1
  fi

  # Validate title is not empty
  if [ -z "$title" ]; then
    echo "Error: Title cannot be empty"
    return 1
  fi

  # Validate title length (GitHub limit: 256 characters)
  if [ ${#title} -gt 256 ]; then
    echo "Error: Title exceeds maximum length of 256 characters"
    echo "Current length: ${#title}"
    return 1
  fi

  # Validate title does not contain shell metacharacters (CWE-78)
  if echo "$title" | grep -q '[;|`$]'; then
    echo "Error: Title contains invalid shell metacharacters"
    echo "Invalid characters: ; | \` $ && ||"
    echo "Valid characters: A-Z a-z 0-9 space - _ : . ( ) [ ]"
    return 1
  fi

  # Validate body is not empty
  if [ -z "$body" ]; then
    echo "Error: Body cannot be empty"
    return 1
  fi

  # Validate body length (GitHub limit: 65000 characters)
  if [ ${#body} -gt 65000 ]; then
    echo "Error: Body exceeds maximum length of 65000 characters"
    echo "Current length: ${#body}"
    return 1
  fi

  # Create the issue using gh CLI
  local output
  if ! output=$(gh issue create --title "$title" --body "$body" 2>&1); then
    echo "Error: Failed to create GitHub issue"
    echo "$output"
    return 1
  fi

  # Extract issue number from URL (format: https://github.com/owner/repo/issues/123)
  local issue_url="$output"
  local issue_number=$(echo "$issue_url" | grep -o 'issues/[0-9]*' | cut -d'/' -f2)

  # Display success message
  echo "✓ Issue created successfully"
  echo "  Issue #$issue_number: $issue_url"

  # Log to session tracker
  python plugins/autonomous-dev/scripts/session_tracker.py "create-issue" \
    "Created GitHub issue #$issue_number: $title"

  return 0
}

# Call validation function with title and body
validate_and_create_issue "TITLE_HERE" "BODY_HERE"
```

**Security Notes**:
- Validates all inputs before gh CLI execution (CWE-78, CWE-20)
- Checks for shell metacharacters (;|`$&&||) to prevent command injection
- Validates title/body length limits (GitHub API constraints)
- Rejects empty title/body
- Uses quoted variables to prevent word splitting
- No shell=True equivalent (gh CLI subprocess is safe)

---

### CHECKPOINT 3: Validate Issue Creation

Verify the gh CLI command succeeded:
- ✓ Issue created successfully
- ✓ Issue number returned (e.g., #123)
- ✓ Issue URL returned (e.g., https://github.com/owner/repo/issues/123)

If issue creation failed, provide manual fallback instructions:

**Manual Fallback (if gh CLI fails)**:

1. **Check gh CLI installation**:
   ```bash
   gh --version
   ```
   If not installed, see: https://cli.github.com/

2. **Check authentication**:
   ```bash
   gh auth status
   ```
   If not authenticated:
   ```bash
   gh auth login
   ```

3. **Create issue manually**:
   - Go to GitHub repository in browser
   - Click "Issues" → "New Issue"
   - Copy/paste the title and body generated by issue-creator agent

---

### STEP 4 (Optional): Auto-Implement Feature

If the user wants to immediately start implementing the feature, offer to run `/auto-implement` with the same feature request:

```
The issue has been created successfully!

Would you like me to start implementing this feature now using /auto-implement?

This will:
- Research patterns (already done)
- Plan architecture
- Write TDD tests
- Implement code
- Review quality
- Scan security
- Update documentation

Estimated time: 20-30 minutes

Reply 'yes' to proceed, or 'no' to stop here.
```

---

## What This Does

You provide a feature request. The command will:

1. **Research** (2-5 min): Find patterns and best practices
2. **Generate Issue** (1-2 min): Create structured GitHub issue body
3. **Create Issue** (10-30 sec): Submit to GitHub via gh CLI

**Total Time**: 3-8 minutes

**Output**: GitHub issue URL with research-backed content

## Usage

```bash
# Basic usage
/create-issue Add JWT authentication for API endpoints

# Feature with specific requirements
/create-issue Implement rate limiting with Redis sliding window algorithm

# Bug report with research
/create-issue Fix memory leak in background job processor
```

## Prerequisites

**Required**:
- gh CLI installed: https://cli.github.com/
- gh CLI authenticated: `gh auth login`
- Git repository with GitHub remote

**Optional**:
- Labels: Will use default labels from repository
- Assignee: Can be set manually after creation

## Output

The command provides:

1. **Research Summary**: Patterns found, best practices, security considerations
2. **Issue Preview**: Generated issue body (markdown formatted)
3. **GitHub Issue**: Created issue with number and URL
4. **Next Steps**: Option to start implementation with `/auto-implement`

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

Run this command to authenticate:
  gh auth login

Follow the prompts to complete authentication.
```

### Network Timeout

```
Error: gh issue create command timed out

Troubleshooting:
- Check your internet connection
- Verify GitHub is accessible: https://status.github.com/
- Try again in a few moments

Manual fallback:
1. Copy the issue body below
2. Go to your GitHub repository in browser
3. Create issue manually
```

### Invalid Input

```
Error: Title contains invalid characters

Troubleshooting:
- Remove shell metacharacters: ; && || | ` $
- Keep title under 256 characters
- Use alphanumeric + basic punctuation only

Valid characters: A-Z a-z 0-9 space - _ : . ( ) [ ]
```

## When to Use

Use `/create-issue` when you need:

- **Research-backed issues**: Issues with patterns and best practices included
- **Structured content**: Well-organized issue body with all sections
- **Quick issue creation**: Faster than manual research + writing
- **Consistent format**: All issues follow same structure

## Comparison

| Command | Time | What It Does |
|---------|------|--------------|
| `/create-issue` | 3-8 min | Research + generate issue + create on GitHub |
| `/research` | 2-5 min | Research only (no issue created) |
| `/auto-implement` | 20-30 min | Full pipeline (issue optional) |

## Technical Details

**Agents Used**:
- **researcher**: Research patterns and best practices (Haiku model, 2-5 min)
- **issue-creator**: Generate structured issue body (Sonnet model, 1-2 min)

**Tools Used**:
- gh CLI: GitHub issue creation (direct invocation via Bash tool)
- Bash validation: Inline security checks before gh CLI execution

**Security**:
- CWE-78: Command injection prevention (shell metacharacter validation, quoted variables)
- CWE-20: Input validation (length limits, empty checks, format validation)
- Bash validation: Inline checks for dangerous characters (;|`$&&||)

**Permissions**:
- Read-only during research phase
- Write access to GitHub repository for issue creation

## Examples

### Example 1: New Feature

```bash
/create-issue Add OAuth2 authentication with Google and GitHub providers
```

**Output**:
```
✓ Research completed (3 min)
  - Found 2 similar patterns in codebase
  - Identified best practices for OAuth2 flow
  - Security considerations: PKCE, state parameter validation

✓ Issue body generated (1 min)
  - Description: OAuth2 authentication integration
  - Research: Existing patterns, best practices, security
  - Implementation plan: 4 components (~800 LOC)
  - Acceptance criteria: 8 testable requirements

✓ Issue created on GitHub (15 sec)
  - Issue #123: https://github.com/owner/repo/issues/123
  - Labels: enhancement, security
  - Ready for implementation

Would you like to start implementing with /auto-implement? (yes/no)
```

### Example 2: Bug Fix

```bash
/create-issue Fix race condition in concurrent file uploads
```

**Output**:
```
✓ Research completed (2 min)
  - Found similar concurrency patterns
  - Best practices: file locking, atomic operations
  - Security: CWE-362 (concurrent execution using shared resource)

✓ Issue body generated (1 min)
  - Description: Race condition in upload handler
  - Research: Concurrency patterns, locking mechanisms
  - Implementation plan: Add file locking with timeout
  - Acceptance criteria: Concurrent upload tests pass

✓ Issue created on GitHub (12 sec)
  - Issue #124: https://github.com/owner/repo/issues/124
  - Labels: bug, concurrency
  - Ready for investigation

Manual steps to reproduce included in issue body.
```

---

**Part of**: Individual agent commands (GitHub #44)
**Related**: `/research`, `/plan`, `/auto-implement`
**New in**: v3.9.0 (GitHub Issue #58)
