---
description: Interactive setup wizard for autonomous-dev plugin (hooks, templates, GitHub)
---

# Setup Autonomous Development Plugin

Interactive wizard to configure hooks, templates, and GitHub integration after plugin installation.

## Usage

```bash
/setup
```

This will guide you through:
1. **Plugin File Copy** - Copy hooks and templates from plugin to project
2. **Hook Configuration** - Enable automatic formatting, testing, security
3. **Template Installation** - Set up PROJECT.md from template
4. **GitHub Integration** - Configure GitHub authentication (optional)
5. **Settings Validation** - Verify everything is configured correctly

---

## What This Command Does

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

Helps you create PROJECT.md from template:
```
1. Copies template to PROJECT.md
2. Opens in editor for you to fill in
3. Validates structure
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
  echo "✅ PROJECT.md exists - skipping creation"
else
  echo "⚠️ No PROJECT.md found!"
  # Show options menu
fi
```

**If PROJECT.md missing**, user sees:

```
⚠️ No PROJECT.md found!

How would you like to create it?

[1] Generate from codebase (recommended)
    → AI analyzes your repo and creates comprehensive PROJECT.md
    → 300-500 lines, 80-90% complete
    → Ready in 30-60 seconds
    → Best for: existing projects with code

[2] Create from template
    → Basic structure with examples and TODOs
    → You fill in all content manually
    → Best for: new projects or non-standard structure

[3] Interactive wizard
    → Answer questions, AI generates PROJECT.md
    → Guided experience, customized output
    → Best for: first-time users

[4] Skip (not recommended)
    → You can run /create-project-md later
    → Many autonomous-dev features won't work until then

Your choice [1-4]:
```

#### Option 1: Generate from Codebase

```
🔍 Analyzing codebase...

✅ Found README.md (extracting project vision)
✅ Found package.json (extracting tech stack)
✅ Analyzing src/ structure (12 files)
✅ Analyzing tests/ structure (unit + integration detected)
✅ Analyzing docs/ organization (4 categories)

🧠 Architecture pattern detected: {Pattern}

✅ Generated PROJECT.md (427 lines)

📋 Sections Created:
✅ Project Vision
✅ Architecture Overview (with ASCII diagram)
✅ File Organization Standards
✅ Development Workflow
✅ Testing Strategy
✅ Documentation Map

📝 Only 3 TODO sections need your input (10%)

Next steps:
1. Review PROJECT.md
2. Fill in TODO sections (marked clearly)
3. Continue with setup

✅ PROJECT.md ready!
```

#### Option 2: Template Mode

```
✅ Created PROJECT.md from template (312 lines)

Each section includes:
- TODO placeholder
- Example of what to write
- Explanation of why it matters

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
- Architecture type
- Detail level desired

Then generates PROJECT.md based on responses + codebase analysis.

```
✅ Generated PROJECT.md (365 lines)

Based on your responses:
  - Goal: Production application
  - Architecture: Translation layer
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

You can create it later:
  → Run: /create-project-md

Setup will continue, but with reduced functionality.

Continue? [Y/n]
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

**File**: `PROJECT.md`
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
cp .claude/templates/PROJECT.md PROJECT.md
# Then edit PROJECT.md
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

Run the interactive setup wizard to configure the plugin.

```bash
python "$(dirname "$0")/../scripts/setup.py"
```

---

**Pro Tip**: Start with slash commands, then enable hooks once comfortable with the workflow!
