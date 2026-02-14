# Setup Wizard - Detailed Phase Instructions

Complete phase-by-phase instructions for the setup wizard.

---

## Phase 0: GenAI Installation (Optional)

**Purpose**: Detect and execute GenAI-first installation if staging directory exists.

### 0.1 Check for Staging Directory

```bash
python plugins/autonomous-dev/scripts/genai_install_wrapper.py check-staging "$HOME/.autonomous-dev-staging"
```

**Expected Output**:
```json
{
  "status": "valid",
  "staging_path": "/Users/user/.autonomous-dev-staging",
  "fallback_needed": false
}
```

**If `fallback_needed: true`** → Skip Phase 0, go to Phase 1

### 0.2 Analyze Installation Type

```bash
python plugins/autonomous-dev/scripts/genai_install_wrapper.py analyze "$(pwd)"
```

**Installation Types**:
- **fresh**: No .claude/ directory (new installation)
- **brownfield**: Has PROJECT.md or user artifacts (preserve user files)
- **upgrade**: Has existing plugin files (create backups)

### 0.3 Execute Installation

```bash
python plugins/autonomous-dev/scripts/genai_install_wrapper.py execute \
  "$HOME/.autonomous-dev-staging" \
  "$(pwd)" \
  "[install_type]"
```

### 0.4 Validate Critical Directories

```bash
for dir in "plugins/autonomous-dev/commands" \
           "plugins/autonomous-dev/agents" \
           "plugins/autonomous-dev/hooks" \
           "plugins/autonomous-dev/lib" \
           "plugins/autonomous-dev/skills" \
           ".claude"; do
  if [ ! -d "$dir" ]; then
    echo "Missing: $dir"
    exit 1
  fi
done
```

### 0.5 Cleanup Staging

```bash
python plugins/autonomous-dev/scripts/genai_install_wrapper.py cleanup "$HOME/.autonomous-dev-staging"
```

### Error Recovery

If any step fails, gracefully fall back to Phase 1 (manual setup).

---

## Phase 1: Welcome & Tech Stack Detection

### 1.1 Welcome Message

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Autonomous Development Plugin Setup
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This wizard will configure:
- PROJECT.md (strategic direction)
- Hooks (quality automation)
- GitHub integration (optional)

Takes 2-3 minutes. Ready? [Y/n]
```

### 1.2 Tech Stack Detection Commands

```bash
# Languages
ls -R | grep -E '\.(py|js|ts|go|rs|java)$' | wc -l

# Package managers
ls package.json pyproject.toml go.mod Cargo.toml pom.xml 2>/dev/null

# Architecture patterns
find . -type d -name "src" -o -name "lib" -o -name "cmd" -o -name "api" | head -10

# Git analysis
git log --oneline --all | wc -l
git log --format="%an" | sort -u | wc -l

# README analysis
cat README.md | grep -E "^#|goals?|features?|architecture" -i
```

**Output Format**:
```json
{
  "tech_stack": {
    "languages": ["Python", "TypeScript"],
    "primary": "Python",
    "frameworks": ["FastAPI", "React"],
    "test_frameworks": ["pytest", "jest"]
  },
  "project_info": {
    "has_readme": true,
    "has_tests": true,
    "git_commits": 213,
    "architecture_pattern": "Layered"
  }
}
```

---

## Phase 2: PROJECT.md Setup

### 2.1 Check if PROJECT.md Exists

```bash
if [ -f PROJECT.md ]; then
  echo "PROJECT.md exists at root"
  # Go to 2.3 (Maintain Existing)
else
  echo "No PROJECT.md found!"
  # Go to 2.2 (Create New)
fi
```

### 2.2 Create New - Options

**Use AskUserQuestion with 4 options**:

1. **Generate from codebase** (recommended for existing projects)
2. **Create from template** (recommended for new projects)
3. **Interactive wizard** (recommended for first-time users)
4. **Skip** (not recommended)

### 2.3 Maintain Existing PROJECT.md

Options:
1. Keep existing (no changes)
2. Update PROJECT.md (detect drift, suggest improvements)
3. Refactor PROJECT.md (regenerate from current codebase)
4. Validate PROJECT.md (check structure and alignment)

---

## Phase 3: Workflow Selection

**Use AskUserQuestion**:

Options:
- **Slash Commands**: Manual control - run /format, /test when you want
- **Automatic Hooks**: Auto-format on save, auto-test on commit
- **Custom**: Configure manually later

**If Automatic Hooks selected**, create `.claude/settings.local.json`:

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

---

## Phase 4: GitHub Integration (Optional)

**Use AskUserQuestion**:

Options:
- **Yes**: Enable milestone tracking, issues, PRs
- **No**: Skip GitHub integration

If Yes: Guide token creation and setup .env

---

## Phase 4.5: CLAUDE.md Enhancement (Auto)

Runs automatically without user prompts:

```python
from pathlib import Path
import sys

lib_dir = Path(".claude/lib")
if not lib_dir.exists():
    lib_dir = Path("plugins/autonomous-dev/lib")
sys.path.insert(0, str(lib_dir))

try:
    from claude_md_updater import ClaudeMdUpdater

    claude_md = Path("CLAUDE.md")
    if claude_md.exists():
        updater = ClaudeMdUpdater(claude_md)
        if not updater.section_exists("autonomous-dev"):
            template_paths = [
                Path(".claude/templates/claude_md_section.md"),
                Path("plugins/autonomous-dev/templates/claude_md_section.md"),
            ]
            for path in template_paths:
                if path.exists():
                    if updater.inject_section(path.read_text(), "autonomous-dev"):
                        print("Added autonomous-dev section to CLAUDE.md")
                    break
except ImportError:
    pass
```

---

## Phase 5: Validation & Summary

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Setup Complete!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Configuration Summary:

PROJECT.md:
  - Location: PROJECT.md (project root)
  - Status: Generated from codebase analysis

Workflow:
  - Mode: [Slash Commands OR Automatic Hooks]

GitHub:
  - Integration: [Enabled OR Skipped]

Next Steps:

1. Review PROJECT.md - fill in TODO sections
2. Test: /align-project
3. Try: /auto-implement for a feature
4. When done: /clear

Documentation:
  - Plugin docs: plugins/autonomous-dev/README.md
  - PROJECT.md guide: docs/PROJECT_MD_GUIDE.md
```
