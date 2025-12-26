# Environment Configuration

All environment variables for autonomous-dev, with defaults and examples.

## Quick Setup

```bash
# Copy template to .env
cp .env.example .env

# Edit with your values
vim .env
```

**IMPORTANT**: Never commit `.env` to git. It should be in `.gitignore`.

---

## API Keys (Required)

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | Yes | GitHub Personal Access Token for gh CLI, issue tracking, PR creation |
| `ANTHROPIC_API_KEY` | No | Anthropic API key for GenAI-powered features (security scan, test gen) |

### GITHUB_TOKEN

```bash
GITHUB_TOKEN=ghp_your_token_here
```

**Create at**: https://github.com/settings/tokens

**Required scopes**:
- `repo` - Full control of private repositories
- `read:org` - Read org membership (for private repos)
- `workflow` - Update GitHub Action workflows (optional)

**Used by**:
- `/create-issue` - Create GitHub issues
- `/auto-implement` - Close issues automatically
- `/batch-implement --issues` - Fetch issue titles
- Auto-tracking hooks

### ANTHROPIC_API_KEY (Optional)

```bash
ANTHROPIC_API_KEY=sk-ant-your_key_here
```

**Get from**: https://console.anthropic.com/

**Used by**:
- `GENAI_SECURITY_SCAN` - AI-powered security scanning
- `GENAI_TEST_GENERATION` - Smart test case generation
- `GENAI_DOC_AUTOFIX` - Automatic documentation fixes

**Note**: Optional. Most GenAI features work through Claude Code directly (uses your Max subscription). Consider using OpenRouter instead for standalone scripts (cheaper).

### OPENROUTER_API_KEY (Recommended for CI/automation)

```bash
OPENROUTER_API_KEY=sk-or-v1-your_key_here
```

**Get from**: https://openrouter.ai/keys

**Used by**:
- CI Pipeline - GenAI validation in GitHub Actions
- `/align` command - Manifest alignment validation
- Standalone validation scripts

**Why OpenRouter?**
- Much cheaper: ~$0.10/1M tokens (Gemini Flash) vs $3/1M (Claude Sonnet)
- One API key for 400+ models
- Perfect for automated validation tasks

**Model selection** (optional):
```bash
OPENROUTER_MODEL=google/gemini-2.0-flash-exp  # Default (cheapest)
OPENROUTER_MODEL=anthropic/claude-3-haiku     # Fast Claude
OPENROUTER_MODEL=openai/gpt-4o-mini           # OpenAI alternative
```

#### CI/CD Integration (GitHub Actions)

To enable GenAI validation in CI:

1. Go to repository **Settings → Secrets and variables → Actions**
2. Click **New repository secret**
3. Name: `OPENROUTER_API_KEY`
4. Value: Your OpenRouter API key (sk-or-v1-...)
5. Click **Add secret**

**Cost**: ~$0.001 per CI run (virtually free)

---

## Git Automation

Controls automatic git operations after `/auto-implement` completes.

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTO_GIT_ENABLED` | `true` | Master switch for all git automation |
| `AUTO_GIT_PUSH` | `true` | Auto-push commits to remote |
| `AUTO_GIT_PR` | `false` | Auto-create pull request after push |
| `AUTO_CLOSE_ISSUES` | `true` | Auto-close issues when commit contains "Closes #N" |

### Example: Full Automation

```bash
# Commit, push, and close issues automatically
AUTO_GIT_ENABLED=true
AUTO_GIT_PUSH=true
AUTO_GIT_PR=false
AUTO_CLOSE_ISSUES=true
```

### Example: Local Only

```bash
# Commit locally, but don't push
AUTO_GIT_ENABLED=true
AUTO_GIT_PUSH=false
AUTO_GIT_PR=false
```

### Example: Disabled

```bash
# Manual git operations only
AUTO_GIT_ENABLED=false
```

**Trigger**: Git automation triggers when `doc-master` agent completes (SubagentStop hook).

---

## Tool Auto-Approval

Reduces permission prompts during `/auto-implement` and `/batch-implement`.

| Variable | Default | Values | Description |
|----------|---------|--------|-------------|
| `MCP_AUTO_APPROVE` | `false` | `true`, `false`, `subagent_only` | Auto-approve safe tool calls |

### Values

- `true` - Auto-approve everywhere (main conversation + subagents)
- `false` - Always prompt for permission
- `subagent_only` - Only auto-approve in subagent workflows

### Example: Full Auto-Approval

```bash
# Eliminates 50+ permission prompts per /auto-implement
MCP_AUTO_APPROVE=true
```

**Security**: Uses blacklist-first policy. Dangerous commands (rm -rf, force push, etc.) are always blocked.

---

## Workflow Discipline (Issue #137, v3.41.0+)

Enforces proper command-based workflows to prevent vibe coding and ensure validation pipelines.

| Variable | Default | Values | Description |
|----------|---------|--------|-------------|
| `ENFORCE_WORKFLOW` | `true` | `true`, `false` | Enable/disable workflow enforcement |

### What It Enforces

The `detect_feature_request.py` hook (UserPromptSubmit lifecycle) enforces these workflows:

**Feature Requests** (Exit code 1 - WARN):
- Detects: "implement X", "add X", "create X", "build X"
- Action: Suggests using `/auto-implement` instead
- Reason: Ensures PROJECT.md alignment and full TDD pipeline

**Bypass Attempts** (Exit code 2 - BLOCK):
- Detects: "gh issue create", "create issue", "skip /create-issue", "make issue"
- Action: BLOCKS the prompt and requires `/create-issue` command
- Reason: Ensures all issues go through research + duplicate detection + cache

**Normal Prompts** (Exit code 0 - PASS):
- Questions, queries, non-feature requests
- Action: Proceeds normally without intervention

### Opt-Out (Not Recommended)

```bash
# Disable all workflow enforcement
ENFORCE_WORKFLOW=false
```

**Why keep it enabled**:
- Prevents accidental vibe coding (direct implementation without validation)
- Ensures all issues go through research pipeline (no duplicate work)
- Maintains audit trail from issue to implementation
- Forces proper workflows (tested and proven to work)

### Example Scenarios

**Scenario 1: Feature Request (Warned)**
```bash
User: "implement JWT authentication"
Hook: Exit 1 (WARN) - Suggests /auto-implement "#123"
```

**Scenario 2: Bypass Attempt (Blocked)**
```bash
User: "gh issue create --title JWT auth"
Hook: Exit 2 (BLOCK) - Requires /create-issue "JWT auth"
```

**Scenario 3: Normal Prompt (Passed)**
```bash
User: "What is JWT and how does it work?"
Hook: Exit 0 (PASS) - Proceeds normally
```

**Scenario 4: Correct Workflow (Passed)**
```bash
User: "/create-issue Add JWT authentication"
Hook: Exit 0 (PASS) - Correct command, proceeds normally
```

### See Also

- CLAUDE.md: Workflow Discipline section (explains philosophy)
- `/create-issue` command: Proper GitHub issue creation workflow
- `/auto-implement` command: Feature implementation with alignment validation
- plugins/autonomous-dev/hooks/detect_feature_request.py: Hook implementation

---

## Batch Processing

Controls `/batch-implement` behavior.

| Variable | Default | Description |
|----------|---------|-------------|
| `BATCH_RETRY_ENABLED` | `false` | Auto-retry transient failures (network, timeout, rate limit) |

### Retry Behavior

When enabled:
- **Transient failures** (network, timeout, API rate limit) → Retry up to 3x
- **Permanent failures** (syntax error, import error) → Never retry
- **Circuit breaker** → Pause after 5 consecutive failures

```bash
# Enable automatic retry
BATCH_RETRY_ENABLED=true
```

---

## GitHub Issue Tracking

Automatic issue creation from test failures and GenAI findings.

| Variable | Default | Description |
|----------|---------|-------------|
| `GITHUB_AUTO_TRACK_ISSUES` | `false` | Enable automatic issue tracking |
| `GITHUB_TRACK_ON_PUSH` | `true` | Create issues before git push |
| `GITHUB_TRACK_ON_COMMIT` | `false` | Create issues on each commit |
| `GITHUB_TRACK_THRESHOLD` | `high` | Minimum priority: `low`, `medium`, `high` |
| `GITHUB_DRY_RUN` | `false` | Preview mode (don't actually create issues) |

### Threshold Levels

- `high` - Only critical bugs auto-tracked
- `medium` - Bugs and important findings
- `low` - Everything auto-tracked (creates many issues)

### Example: Conservative Tracking

```bash
GITHUB_AUTO_TRACK_ISSUES=true
GITHUB_TRACK_ON_PUSH=true
GITHUB_TRACK_THRESHOLD=high
GITHUB_DRY_RUN=false
```

---

## GenAI Features

AI-powered enhancements. All default to `true` (opt-out model).

| Variable | Default | Description |
|----------|---------|-------------|
| `GENAI_SECURITY_SCAN` | `true` | AI-powered security vulnerability detection |
| `GENAI_TEST_GENERATION` | `true` | Smart test case generation |
| `GENAI_DOC_AUTOFIX` | `true` | Automatic documentation fixes |
| `GENAI_DOC_UPDATE` | `true` | AI-powered documentation updates |
| `GENAI_DOCS_VALIDATE` | `true` | Documentation consistency validation |

### Disable for Speed

```bash
# Faster but less intelligent checks
GENAI_SECURITY_SCAN=false
GENAI_TEST_GENERATION=false
GENAI_DOC_AUTOFIX=false
```

**Note**: Requires `ANTHROPIC_API_KEY` to be set for GenAI features to work.

---

## Debug Flags

Development and troubleshooting flags.

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG_GENAI` | `false` | Verbose GenAI operation output |
| `DEBUG_SECURITY_SCAN` | `false` | Verbose security scan output |
| `STRICT_PIPELINE` | `0` | Fail on any warning (`1` to enable) |

### Example: Debug Mode

```bash
DEBUG_GENAI=true
DEBUG_SECURITY_SCAN=true
```

---

## Fully Autonomous / Unattended Operation

**For `/batch-implement` to run without ANY prompts**, you need these settings:

```bash
# =============================================================================
# FULLY AUTONOMOUS MODE - No prompts, no questions, complete automation
# =============================================================================

# Required: Prevent MCP tool approval prompts
MCP_AUTO_APPROVE=true

# Required: Prevent git automation prompts
AUTO_GIT_ENABLED=true
AUTO_GIT_PUSH=true
AUTO_GIT_PR=true
AUTO_CLOSE_ISSUES=true

# Required: Prevent batch retry prompts
BATCH_RETRY_ENABLED=true

# Optional: Skip workflow enforcement (not recommended)
# ENFORCE_WORKFLOW=false
```

**What this enables**:
- `/batch-implement` runs overnight without human intervention
- All git operations execute automatically
- Transient failures (network, timeout) auto-retry
- PRs created and issues closed automatically

**What still happens**:
- Tests MUST pass 100% (not 80%) before proceeding
- Security vulnerabilities still block if CRITICAL
- Failed features are marked as failed (batch continues)

---

## Complete Example

Here's a fully configured `.env` for autonomous development:

```bash
# =============================================================================
# API Keys
# =============================================================================
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxx

# =============================================================================
# Git Automation (full auto)
# =============================================================================
AUTO_GIT_ENABLED=true
AUTO_GIT_PUSH=true
AUTO_GIT_PR=false
AUTO_CLOSE_ISSUES=true

# =============================================================================
# Tool Auto-Approval (reduce prompts)
# =============================================================================
MCP_AUTO_APPROVE=true

# =============================================================================
# Batch Processing
# =============================================================================
BATCH_RETRY_ENABLED=true

# =============================================================================
# Issue Tracking (conservative)
# =============================================================================
GITHUB_AUTO_TRACK_ISSUES=true
GITHUB_TRACK_ON_PUSH=true
GITHUB_TRACK_THRESHOLD=high

# =============================================================================
# GenAI Features (all enabled)
# =============================================================================
GENAI_SECURITY_SCAN=true
GENAI_TEST_GENERATION=true
GENAI_DOC_AUTOFIX=true
```

---

## Precedence

Environment variables override other configuration sources:

1. **`.env` file** (highest priority)
2. **User state** (`~/.autonomous-dev/user_state.json`)
3. **Default values** (lowest priority)

---

## See Also

- [GIT-AUTOMATION.md](GIT-AUTOMATION.md) - Detailed git automation documentation
- [TOOL-AUTO-APPROVAL.md](TOOL-AUTO-APPROVAL.md) - MCP auto-approval security details
- [BATCH-PROCESSING.md](BATCH-PROCESSING.md) - Batch processing documentation
