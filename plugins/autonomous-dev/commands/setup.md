---
description: Intelligent setup wizard - analyzes tech stack and guides plugin configuration with setup-wizard agent
---

# Setup Autonomous Development Plugin

GenAI-powered setup wizard that intelligently installs, configures, and validates the autonomous-dev plugin.

## Usage

```bash
/setup
```

## What This Command Does

### Phase 0: Plugin Installation (if staging files exist)

If `~/.autonomous-dev-staging/` exists (from running the curl installer), GenAI will:

1. **Analyze current state**:
   - Check if `.claude/` directory exists (brownfield vs greenfield)
   - Identify existing files and their versions
   - Detect user artifacts (PROJECT.md, .env, customized hooks)

2. **Smart installation decisions**:
   - **Protected files** (NEVER overwrite):
     - `PROJECT.md` - Your project definition
     - `.env` - Your secrets
     - Any file you've customized with project-specific logic
   - **Plugin files** (safe to update):
     - Agents, commands, hooks, lib, scripts, config, templates
   - **Customized plugin files** (ask or backup):
     - Hooks you've modified - backup and update, or keep yours

3. **Install/Update files**:
   - Copy from staging to `.claude/`
   - Preserve your customizations
   - Update outdated plugin files

4. **Post-install audit**:
   - Verify all files installed correctly
   - Check Python imports work
   - Validate hooks are executable
   - Report any issues with fixes

5. **Cleanup**:
   - Remove staging directory after successful install

### Phase 1-6: Configuration (existing wizard)

After installation, continues with:
1. **Hook Configuration** - Enable automatic formatting, testing, security
2. **Template Installation** - Set up PROJECT.md from template
3. **GitHub Integration** - Configure GitHub authentication (optional)
4. **Settings Validation** - Verify everything is configured correctly

---

## Installation Flow

```
┌─────────────────────────────────────────────────────────────┐
│  User runs: bash <(curl -sSL .../install.sh)                │
│  └─> Files downloaded to ~/.autonomous-dev-staging/         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  User runs: /setup                                          │
│                                                             │
│  GenAI analyzes:                                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Staging: ~/.autonomous-dev-staging/                  │   │
│  │   ├── manifest.json                                  │   │
│  │   ├── VERSION (3.40.0)                               │   │
│  │   └── files/                                         │   │
│  │       ├── plugins/autonomous-dev/agents/             │   │
│  │       ├── plugins/autonomous-dev/commands/           │   │
│  │       ├── plugins/autonomous-dev/hooks/              │   │
│  │       └── ...                                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Current: .claude/ (if exists)                        │   │
│  │   ├── PROJECT.md ← PROTECTED (user artifact)         │   │
│  │   ├── hooks/custom_hook.py ← PRESERVED (customized)  │   │
│  │   ├── agents/ ← UPDATE (v3.30 → v3.40)               │   │
│  │   └── VERSION (3.30.0)                               │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  GenAI decides:                                             │
│  • PROJECT.md: Skip (user artifact)                         │
│  • custom_hook.py: Keep yours (customized)                  │
│  • agents/*: Update all (outdated plugin files)             │
│  • lib/*: Update all (outdated plugin files)                │
│  • new_feature.py: Add (new in v3.40)                       │
│                                                             │
│  GenAI installs and validates:                              │
│  ✓ 128 files processed                                      │
│  ✓ Python imports working                                   │
│  ✓ Hooks executable                                         │
│  ✓ Ready to use                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Detailed Wizard Steps

### Phase 1: Hook Setup (Choose Your Workflow)

**Option A: Slash Commands (Recommended for Beginners)**
```bash
# Explicit control - run when needed
/format          # Format code manually
/test            # Run tests manually
/security-scan   # Security check manually
/full-check      # All checks manually
```

**Benefits**:
- ✅ Full control over when checks run
- ✅ See exactly what's happening
- ✅ Great for learning
- ✅ No surprises

**Option B: Automatic Hooks (Power Users)**

Enables automatic execution:
- Auto-format on file write/edit
- Auto-test on commit
- Auto-security scan on commit
- Auto-coverage enforcement

**Benefits**:
- ✅ Fully automated workflow
- ✅ Can't forget to run checks
- ✅ Maximum quality enforcement

### Phase 2: Template Setup

Helps you create PROJECT.md from template or codebase:
```
1. Analyzes existing codebase (README, structure, git history)
2. Generates comprehensive PROJECT.md at root (or uses template)
3. Validates structure and alignment
```

### Phase 3: GitHub Integration (Optional)

Sets up GitHub authentication:
```
1. Creates .env file
2. Guides you to create GitHub token
3. Tests authentication
4. Links to milestone setup
```

---

## Step-by-Step Interactive Wizard

### Step 1: Welcome

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 Autonomous Development Plugin Setup
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This wizard will help you configure:
✓ Hooks (automatic quality checks)
✓ Templates (PROJECT.md)
✓ GitHub integration (optional)

This takes about 2-3 minutes.
Ready to begin? [Y/n]
```

### Step 2: Choose Workflow

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Choose Your Workflow
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

How would you like to run quality checks?

[1] Slash Commands (Recommended for beginners)
    - Explicit control: run /format, /test when you want
    - Great for learning the workflow
    - No surprises or automatic changes

[2] Automatic Hooks (Power users)
    - Auto-format on save
    - Auto-test on commit
    - Auto-security scan
    - Fully automated quality enforcement

[3] Custom (I'll configure manually later)

Your choice [1/2/3]:
```

### Step 3A: If Slash Commands (Option 1)

```
✅ Slash Commands Mode Selected

You can run these commands anytime:

Quality Checks:
  /format          Format code (black, prettier, gofmt)
  /test            Run tests with coverage
  /security-scan   Scan for secrets and vulnerabilities
  /full-check      Run all checks (format + test + security)

Development:
  /auto-implement  Autonomous feature implementation
  /commit          Smart commit with conventional message
  /align-project   Validate PROJECT.md alignment

Tip: Run /full-check before committing!

✅ No additional configuration needed.
```

### Step 3B: If Automatic Hooks (Option 2)

```
⚙️  Configuring Automatic Hooks...

Creating .claude/settings.local.json with:

{
  "hooks": {
    "PostToolUse": {
      "Write": [
        "python .claude/hooks/auto_format.py"
      ],
      "Edit": [
        "python .claude/hooks/auto_format.py"
      ]
    },
    "PreCommit": {
      "*": [
        "python .claude/hooks/auto_test.py",
        "python .claude/hooks/security_scan.py"
      ]
    }
  }
}

✅ Hooks configured!

What will happen automatically:
  ✓ Code formatted after every write/edit
  ✓ Tests run before every commit
  ✓ Security scan before every commit
  ✓ Coverage enforced (80% minimum)

To disable later: Remove .claude/settings.local.json
```

### Step 4: PROJECT.md Setup

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 PROJECT.md Setup
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROJECT.md is ESSENTIAL for autonomous-dev to work.
It defines your project's strategic direction and standards.

Without PROJECT.md:
  ❌ /align-project won't work
  ❌ File organization validation disabled
  ❌ Agents lack project context
```

Check if PROJECT.md exists:

```bash
if [ -f PROJECT.md ]; then
  echo "✅ PROJECT.md exists at root"
  # Offer to update/maintain it
else
  echo "⚠️ No PROJECT.md found!"
  # Show options menu
fi
```

**If PROJECT.md missing**, user sees:

```
⚠️ No PROJECT.md found!

How would you like to create it?

[1] Generate from codebase (recommended for existing projects)
    → AI analyzes your repo and creates comprehensive PROJECT.md
    → Analyzes: README, structure, git history, dependencies
    → 300-500 lines, 80-90% complete
    → Ready in 30-60 seconds

[2] Create from template (recommended for new projects)
    → Basic structure with examples and TODOs
    → You fill in all content manually
    → Best for: greenfield projects

[3] Interactive wizard (recommended for first-time users)
    → Answer questions, AI generates PROJECT.md
    → Guided experience, customized output
    → Takes 2-3 minutes

[4] Skip (not recommended)
    → Many autonomous-dev features won't work
    → You can run /setup again later

Your choice [1-4]:
```

#### Option 1: Generate from Codebase

```
🔍 Analyzing codebase...

✅ Found README.md (extracting project vision)
✅ Found package.json (extracting tech stack: Node.js, TypeScript)
✅ Analyzing src/ structure (47 files, API + UI pattern detected)
✅ Analyzing tests/ structure (unit + integration detected)
✅ Analyzing docs/ organization (5 categories)
✅ Analyzing git history (213 commits, TDD workflow detected)

🧠 Architecture pattern detected: Layered Architecture (API + Frontend)

✅ Generated PROJECT.md (427 lines) at project root

📋 Sections Created:
✅ Project Vision (from README.md)
✅ Goals (inferred from roadmap + issues)
✅ Architecture Overview (with ASCII diagram)
✅ Tech Stack (Node.js, TypeScript, React, PostgreSQL)
✅ File Organization Standards (detected from existing structure)
✅ Development Workflow (git flow, testing patterns)
✅ Testing Strategy (unit, integration, coverage targets)
✅ Documentation Map (links to existing docs)

📝 Only 2 TODO sections need your input (5%):
  - CONSTRAINTS section (please specify performance/scale limits)
  - CURRENT SPRINT goals (please define active work)

Next steps:
1. Review PROJECT.md at project root
2. Fill in TODO sections (clearly marked)
3. Verify auto-detected goals match your vision
4. Save when ready

✅ PROJECT.md ready!
Run /align-project to validate.
```

#### Option 2: Template Mode

```
✅ Created PROJECT.md from template at project root (312 lines)

Each section includes:
- TODO placeholder
- Example of what to write
- Explanation of why it matters

Sections to fill in:
  📝 GOALS - What success looks like
  📝 SCOPE - What's in/out of scope
  📝 CONSTRAINTS - Technical limits
  📝 ARCHITECTURE - System design
  📝 CURRENT SPRINT - Active work

Next steps:
1. Open PROJECT.md in your editor
2. Replace TODO sections with your content
3. Follow examples provided
4. Save and continue

✅ Template ready for customization!
```

#### Option 3: Interactive Wizard

Uses AskUserQuestion to gather:
- Primary project goal
- Architecture type (monolith, microservices, library, etc.)
- Tech stack (if not detected)
- Team size and experience level
- Detail level desired

Then generates PROJECT.md based on responses + codebase analysis.

```
✅ Generated PROJECT.md (365 lines) at project root

Based on your responses:
  - Goal: Production API for e-commerce
  - Architecture: Microservices
  - Tech Stack: Go, PostgreSQL, Redis
  - Team: 3-5 developers
  - Detail: Comprehensive

Next steps:
1. Review generated content
2. Customize as needed
3. Continue with setup

✅ PROJECT.md ready!
```

#### Option 4: Skip

```
⚠️ Skipped PROJECT.md creation

Important: Many features won't work without PROJECT.md:
  ❌ /align-project
  ❌ /auto-implement
  ❌ File organization validation
  ❌ Agent context and alignment

You can create it later by running:
  /setup

Setup will continue, but with reduced functionality.

Continue anyway? [y/N]
```

**If PROJECT.md exists**, user sees:

```
✅ PROJECT.md exists at project root

Would you like to:

[1] Keep existing PROJECT.md (no changes)
[2] Update PROJECT.md (detect drift, suggest improvements)
[3] Refactor PROJECT.md (regenerate from current codebase)
[4] Validate PROJECT.md (check structure and alignment)

Your choice [1-4]:
```

**After any option completes**, setup continues to Step 5 (GitHub Integration).
```

### Step 5: GitHub Integration (Optional)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔗 GitHub Integration (Optional)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GitHub integration enables:
  ✓ Sprint tracking via Milestones
  ✓ Issue management
  ✓ PR automation

Setup GitHub integration? [y/N]

[If Yes]

Creating .env file...

✅ Created .env (gitignored)

📝 Next Steps:

1. Create GitHub Personal Access Token:
   → Go to: https://github.com/settings/tokens
   → Click: "Generate new token (classic)"
   → Select scopes: repo, workflow
   → Copy token

2. Add token to .env:
   → Open .env in editor
   → Set: GITHUB_TOKEN=ghp_your_token_here
   → Save and close

3. Create GitHub Milestone for current sprint:
   → Go to: https://github.com/YOUR_USER/YOUR_REPO/milestones
   → Click: "New milestone"
   → Title: "Sprint 1" (or current sprint name)
   → Set due date
   → Create milestone

4. Update PROJECT.md CURRENT SPRINT section:
   → Reference the milestone you created

[Wait for user]

Test GitHub connection? [Y/n]

[If Yes - runs test command]

✅ GitHub connection successful!
   Authenticated as: YOUR_USERNAME
   Repository: YOUR_REPO
   Milestone found: Sprint 1

[If No]
ℹ️  GitHub setup skipped. You can configure later:
   See: .claude/docs/GITHUB_AUTH_SETUP.md
```

### Step 6: Complete

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Setup Complete!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Your autonomous development environment is ready:

Configuration:
  ✓ Workflow: [Slash Commands OR Automatic Hooks]
  ✓ PROJECT.md: Configured
  ✓ GitHub: [Connected OR Skipped]

Quick Start:

  For Slash Commands workflow:
    1. Describe feature: "implement user authentication"
    2. Run: /auto-implement
    3. Before commit: /full-check
    4. Commit: /commit

  For Automatic Hooks workflow:
    1. Describe feature: "implement user authentication"
    2. Run: /auto-implement
    3. Commit: git commit (hooks run automatically)

Next Steps:

  1. Try a simple feature:
     "implement a hello world function"

  2. Run quality check:
     /full-check

  3. When done, clear context:
     /clear

  4. Check alignment anytime:
     /align-project

Documentation:
  - Plugin docs: .claude/README.md (installed)
  - GitHub setup: .claude/docs/GITHUB_AUTH_SETUP.md
  - Testing guide: tests/README.md

Need help? Run: /help

Happy coding! 🚀
```

---

## What Gets Created

### Always (First Run)

**Directory**: `.claude/hooks/`
- Copied from: `.claude/plugins/autonomous-dev/hooks/`
- Contains: All hook files (auto_format.py, auto_test.py, etc.)

**Directory**: `.claude/templates/`
- Copied from: `.claude/plugins/autonomous-dev/templates/`
- Contains: PROJECT.md template and other templates

### If Automatic Hooks Selected

**File**: `.claude/settings.local.json`
```json
{
  "hooks": {
    "PostToolUse": {
      "Write": ["python .claude/hooks/auto_format.py"],
      "Edit": ["python .claude/hooks/auto_format.py"]
    },
    "PreCommit": {
      "*": [
        "python .claude/hooks/auto_test.py",
        "python .claude/hooks/security_scan.py"
      ]
    }
  }
}
```

### If PROJECT.md Template Selected

**File**: `.claude/PROJECT.md`
- Copied from `.claude/templates/PROJECT.md`
- Ready for user to customize

### If GitHub Integration Selected

**File**: `.env`
```bash
# GitHub Personal Access Token
# Get yours at: https://github.com/settings/tokens
GITHUB_TOKEN=ghp_your_token_here
```

**File**: `.env` added to `.gitignore` (if not already)

---

## Manual Setup (Alternative)

If you prefer to configure manually:

### Enable Hooks Manually

Edit `.claude/settings.local.json`:
```json
{
  "hooks": {
    "PostToolUse": {
      "Write": ["python .claude/hooks/auto_format.py"]
    }
  }
}
```

### Copy PROJECT.md Template

```bash
cp .claude/templates/PROJECT.md .claude/PROJECT.md
# Then edit .claude/PROJECT.md
```

### Setup GitHub

```bash
# Create .env
echo "GITHUB_TOKEN=your_token_here" > .env

# Ensure .env is gitignored
echo ".env" >> .gitignore
```

---

## Troubleshooting

### "Hooks not running"
- Check: `.claude/settings.local.json` exists
- Check: Hooks are in `.claude/hooks/` directory
- Check: Python 3.11+ installed

### "GitHub authentication failed"
- Check: `.env` file exists
- Check: Token has `repo` scope
- Check: Token is valid (not expired)

### "PROJECT.md validation failed"
- Run: `/align-project` to see specific issues
- Check: Required sections exist (GOALS, SCOPE, CONSTRAINTS)

---

## Related Commands

After setup, use these commands:

- `/align-project` - Validate project alignment
- `/auto-implement` - Autonomous feature development
- `/format` - Format code
- `/test` - Run tests
- `/security-scan` - Security check
- `/full-check` - All quality checks
- `/commit` - Smart commit

---



## Implementation

Invoke the setup-wizard agent to intelligently configure your plugin.

The setup-wizard agent will:

1. **Analyze your codebase** - Detects tech stack, dependencies, architecture patterns
2. **Generate PROJECT.md** - Creates comprehensive PROJECT.md from existing code or template
3. **Configure hooks** - Recommends workflow based on your experience level
4. **Setup GitHub integration** - Optional sprint tracking and issue management
5. **Validate everything** - Tests all configurations work correctly

The agent analyzes:
- README.md, package.json, pyproject.toml, go.mod, Makefile
- Directory structure and architecture patterns
- Git history and development patterns
- Existing documentation
- Tech stack and testing frameworks

Based on analysis, it recommends:
- Python projects: black, isort, pytest, bandit
- JavaScript/TypeScript: prettier, eslint, jest
- Go projects: gofmt, go test, staticcheck
- Multi-language: all relevant tools

**Pro Tip**: The agent detects your tech stack and recommends the best workflow for your experience level!
