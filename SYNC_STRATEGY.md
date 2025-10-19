---
version: 1.0.0
created: 2025-10-19
purpose: Keep bootstrap template in sync with ReAlign improvements
---

# Bootstrap Template Synchronization Strategy

## Problem

**Challenge**: ReAlign will continue evolving with improvements, but the bootstrap template needs to stay:
1. **Generic** (no project-specific content)
2. **Up-to-date** (incorporate proven improvements)
3. **Documented** (explain what everything does)

## Solution: 3-Layer Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Layer 1: ReAlign Production (Source of Truth)          │
│ - Actual working code                                   │
│ - Project-specific (MLX, LoRA, etc.)                    │
│ - Continuously evolving                                 │
└──────────────────┬──────────────────────────────────────┘
                   │
                   │ Extract & Generalize
                   ↓
┌─────────────────────────────────────────────────────────┐
│ Layer 2: Bootstrap Template (Universal)                │
│ - Generic, language-agnostic                            │
│ - Placeholders ([PROJECT_NAME], etc.)                   │
│ - Multi-language examples                               │
└──────────────────┬──────────────────────────────────────┘
                   │
                   │ Apply to New Project
                   ↓
┌─────────────────────────────────────────────────────────┐
│ Layer 3: New Project (Customized Instance)             │
│ - Bootstrap applied                                      │
│ - Project-specific customizations                       │
│ - Inherits improvements via re-sync                     │
└─────────────────────────────────────────────────────────┘
```

---

## Auto-Sync Mechanism

### Approach 1: Git-Based Sync (Recommended)

**Setup (One-Time)**:

```bash
# In ReAlign project
cd .claude/bootstrap-template

# Initialize as separate git-tracked directory
git add -f .  # Force add even if in .gitignore

# Tag stable versions
git tag bootstrap-v1.0.0

# Track changes
git log --follow bootstrap-template/
```

**Workflow**:

1. **Make improvements in ReAlign** (business as usual)
2. **Periodic sync** (weekly/monthly):
   ```bash
   # Run automated sync script
   ./scripts/sync_bootstrap_template.sh
   ```
3. **Review diff**, ensure no project-specific content leaked
4. **Commit generalized version**
5. **Tag new version**: `git tag bootstrap-v1.1.0`

**Sync Script** (`./scripts/sync_bootstrap_template.sh`):

```bash
#!/bin/bash
# Auto-sync ReAlign improvements to bootstrap template

set -e

echo "🔄 Syncing ReAlign → Bootstrap Template"

# 1. Detect changes to tracked files
CHANGED_FILES=$(git diff --name-only HEAD~10 .claude/ scripts/hooks/ .github/workflows/)

# 2. For each changed file, check if it affects bootstrap
for file in $CHANGED_FILES; do
    case $file in
        .claude/agents/*.md)
            echo "📝 Agent definition changed: $file"
            echo "   → Update .claude/bootstrap-template/agents/"
            ;;
        .claude/skills/*/SKILL.md)
            echo "📝 Skill changed: $file"
            echo "   → Update .claude/bootstrap-template/skills/"
            ;;
        scripts/hooks/*.py)
            echo "📝 Hook changed: $file"
            echo "   → Update .claude/bootstrap-template/hooks/"
            ;;
        .github/workflows/*.yml)
            echo "📝 Workflow changed: $file"
            echo "   → Update .claude/bootstrap-template/github/workflows/"
            ;;
    esac
done

# 3. Run generalization script
python scripts/generalize_for_bootstrap.py

# 4. Validate no project-specific content
echo "🔍 Validating generic content..."
if grep -r "ReAlign\|MLX\|LoRA" .claude/bootstrap-template/; then
    echo "❌ FAIL: Project-specific content detected!"
    exit 1
fi

echo "✅ Bootstrap template synced successfully"
echo "📦 Ready to tag new version: git tag bootstrap-v1.X.0"
```

**Generalization Script** (`scripts/generalize_for_bootstrap.py`):

```python
#!/usr/bin/env python3
"""
Automatically generalize ReAlign-specific content for bootstrap template.
"""

import re
from pathlib import Path

# Replacement mappings
REPLACEMENTS = {
    # Project-specific → Generic
    r'\bReAlign\b': '[PROJECT_NAME]',
    r'\breAlign\b': '[project_name]',
    r'src/realign/': '[SOURCE_DIR]/',
    r'from realign': 'from [project_name]',

    # MLX-specific → Generic or remove
    r'import mlx\.core as mx': '# Language-specific imports',
    r'mx\.eval\([^)]+\)': '# Force computation (language-specific)',
    r'mx\.metal\.clear_cache\(\)': '# Clear memory (language-specific)',
    r'model\.model\.layers': 'model.layers  # Check PATTERNS.md for framework-specific access',

    # Training-specific → Generic
    r'\bLoRA\b': '[TRAINING_METHOD]',
    r'\bDPO\b': '[TRAINING_METHOD]',
    r'mlx-community/': '[MODEL_REPO]/',
}

def generalize_file(file_path: Path) -> bool:
    """Apply generalizations to a file. Returns True if modified."""
    content = file_path.read_text()
    original = content

    for pattern, replacement in REPLACEMENTS.items():
        content = re.sub(pattern, replacement, content)

    if content != original:
        file_path.write_text(content)
        return True
    return False

def main():
    template_dir = Path('.claude/bootstrap-template')
    modified_count = 0

    for file_path in template_dir.rglob('*.md'):
        if generalize_file(file_path):
            print(f"✏️  Generalized: {file_path}")
            modified_count += 1

    print(f"\n✅ Modified {modified_count} files")

if __name__ == '__main__':
    main()
```

---

### Approach 2: Diff-Based Sync (Alternative)

**Use Case**: Track what changed conceptually, not code directly.

**Setup**:

Create `.claude/bootstrap-template/CHANGELOG_BOOTSTRAP.md`:

```markdown
# Bootstrap Template Changelog

## [Unreleased]

### Improvements from ReAlign
- None yet

## [1.1.0] - 2025-11-01

### Improved
- **Agent: test-master** - Added progression baseline auto-update logic
  - Source: `.claude/agents/test-master.md` (lines 250-265)
  - Benefit: Baselines update automatically when metrics improve >2%
  - Generic: Works for any metric (accuracy, speed, memory)

- **Skill: pattern-curator** - Enhanced pattern confidence scoring
  - Source: `.claude/skills/pattern-curator/learn_patterns.py`
  - Benefit: Only promotes patterns seen 3+ times
  - Generic: Language-agnostic pattern detection

- **Hook: auto_format** - Added Go formatting support
  - Source: `scripts/hooks/auto_format.py`
  - Benefit: Now supports Python, JS, Go
  - Generic: Auto-detects language from file extensions

### Fixed
- **Security: Secrets detection** - Improved regex for API keys
  - Source: `scripts/hooks/security_scan.py`
  - Benefit: Catches more secret patterns
  - Generic: Works across all languages

## [1.0.0] - 2025-10-19

### Initial Release
- 7 specialized agents
- 8 automation skills
- Multi-language support (Python, JS, Go)
- Extracted from ReAlign production system
```

**Sync Workflow**:

1. When you improve ReAlign, document in `CHANGELOG_BOOTSTRAP.md`
2. Periodically apply documented changes to bootstrap template
3. Tag new version

---

## Documentation Auto-Sync

### Problem
Bootstrap template needs clear documentation of what each component does, but ReAlign docs are project-specific.

### Solution: Dual Documentation

**In ReAlign** (`.claude/agents/planner.md`):
```markdown
---
name: planner
description: Architecture planning for ReAlign
---

# Planner Subagent

You are the planner for ReAlign, the MLX training toolkit.

## ReAlign-Specific Context
- Use MLX patterns (model.model.layers)
- Consider LoRA, DPO, etc.
...
```

**In Bootstrap** (`.claude/bootstrap-template/agents/planner.md`):
```markdown
---
name: planner
description: Architecture planning (read-only). Creates detailed implementation plans.
universal: true
source: ReAlign production system
---

# Planner Subagent

You are the planner for [PROJECT_NAME].

## What This Agent Does
**Purpose**: Plan complex features BEFORE implementation to avoid mistakes.

**When invoked**:
- User asks "how should I..." or "design a..."
- Complex features (>3 files)
- Architecture changes

**What it returns**:
- File-by-file implementation plan
- Step-by-step guide
- Risk analysis
- Test strategy

**Tools**: Read, Grep, Glob, Bash (read-only)

**Example**:
User: "Add user authentication"
Planner:
  1. Researches existing auth patterns in codebase
  2. Creates plan:
     - File: auth.py - JWT token generation
     - File: middleware.py - Auth middleware
     - File: test_auth.py - 10 test cases
  3. Notes risks: Token expiry, refresh logic

## Language-Specific Guidance
- Python: Check existing class patterns
- JavaScript: Check existing module patterns
- Go: Check existing package patterns

See full agent definition below for implementation details.

---

[Rest of agent definition with placeholders]
```

### Auto-Generate Documentation

**Script**: `scripts/generate_bootstrap_docs.py`

```python
#!/usr/bin/env python3
"""
Generate user-friendly documentation for bootstrap template components.
"""

from pathlib import Path

def document_agent(agent_path: Path) -> str:
    """Extract agent purpose and create user documentation."""

    content = agent_path.read_text()

    # Parse frontmatter
    name = extract_frontmatter(content, 'name')
    description = extract_frontmatter(content, 'description')
    tools = extract_frontmatter(content, 'tools')

    # Generate docs
    docs = f"""
# {name.title()} Agent - What It Does

## Quick Summary
{description}

## When You'll See This Agent
[Auto-extracted from "When You're Invoked" section]

## What It Returns
[Auto-extracted from "Output Format" section]

## Example Usage
[Auto-extracted from examples]

## Tools It Uses
{', '.join(tools)}

## Read More
See `agents/{name}.md` for full technical details.
"""
    return docs

def main():
    # Generate user-friendly docs for each component
    docs_dir = Path('.claude/bootstrap-template/docs/')
    docs_dir.mkdir(exist_ok=True)

    # Document agents
    for agent_file in Path('.claude/bootstrap-template/agents/').glob('*.md'):
        docs_content = document_agent(agent_file)
        (docs_dir / f"{agent_file.stem}_guide.md").write_text(docs_content)

    print("✅ Generated user documentation")

if __name__ == '__main__':
    main()
```

---

## Version Management

### Semantic Versioning for Bootstrap

```
bootstrap-vMAJOR.MINOR.PATCH

MAJOR: Breaking changes (agent removed, structure changed)
MINOR: New features (new agent, new skill)
PATCH: Bug fixes, doc improvements
```

**Examples**:
- `bootstrap-v1.0.0`: Initial extraction from ReAlign
- `bootstrap-v1.1.0`: Added Go support to hooks
- `bootstrap-v1.1.1`: Fixed typo in planner.md
- `bootstrap-v2.0.0`: Restructured skills (breaking change)

### Upgrading Existing Projects

**Script**: `scripts/upgrade_from_bootstrap.sh`

```bash
#!/bin/bash
# Upgrade an existing project's .claude/ setup from bootstrap template

CURRENT_VERSION="v1.0.0"
TARGET_VERSION="v1.2.0"

echo "Upgrading .claude/ from $CURRENT_VERSION to $TARGET_VERSION"

# 1. Backup current setup
cp -r .claude/ .claude.backup/

# 2. Fetch new bootstrap version
curl -O https://github.com/you/bootstrap/releases/download/$TARGET_VERSION/bootstrap.tar.gz
tar -xzf bootstrap.tar.gz

# 3. Selective merge (keep customizations, update core files)
# - agents/*.md: REPLACE (core logic)
# - skills/*.md: REPLACE (core logic)
# - PROJECT.md: KEEP (user customization)
# - PATTERNS.md: KEEP (project-specific learned patterns)
# - settings.json: MERGE (update structure, keep custom values)

# 4. Show diff
git diff .claude/

echo "✅ Upgrade complete. Review changes and commit."
```

---

## Recommended Workflow

### Daily (in ReAlign)
- Work normally
- Make improvements
- Document notable changes in `CHANGELOG_BOOTSTRAP.md` if they're generalizable

### Weekly
- Run `./scripts/sync_bootstrap_template.sh`
- Review diff to bootstrap template
- Ensure no project-specific content leaked
- Commit changes to bootstrap

### Monthly
- Review bootstrap changelog
- Tag new version: `git tag bootstrap-v1.X.0`
- Test bootstrap on dummy project
- Publish updated archive

### Quarterly
- Review universal principles (STANDARDS.md)
- Update based on Claude updates or major lessons learned
- Major version bump if breaking changes

---

## Testing Sync Quality

**Validation Checklist**:

```bash
# 1. No project-specific content
grep -r "ReAlign\|MLX\|LoRA" .claude/bootstrap-template/
# Should return NOTHING

# 2. Has placeholders
grep -r "\[PROJECT_NAME\]\|\[LANGUAGE\]\|\[SOURCE_DIR\]" .claude/bootstrap-template/
# Should find many matches

# 3. Multi-language support
grep -rE "python.*javascript.*go|js.*py.*go" .claude/bootstrap-template/
# Should find language examples

# 4. Test on new project
mkdir /tmp/test-bootstrap
cp -r .claude/bootstrap-template /tmp/test-bootstrap/.claude
cd /tmp/test-bootstrap
./.claude/bootstrap.sh
# Should work without errors
```

---

## Distribution Strategy

### Option 1: Git Repository
```bash
# Standalone repo
git clone https://github.com/you/claude-code-bootstrap.git
cd claude-code-bootstrap
./bootstrap.sh
```

### Option 2: GitHub Releases
```bash
# Download specific version
curl -LO https://github.com/you/bootstrap/releases/download/v1.2.0/bootstrap.tar.gz
tar -xzf bootstrap.tar.gz
./bootstrap-template/bootstrap.sh
```

### Option 3: NPM Package (if JavaScript-focused)
```bash
npx create-claude-project my-project
```

### Option 4: Python Package (if Python-focused)
```bash
pip install claude-code-bootstrap
claude-bootstrap init my-project
```

---

## Success Metrics

**Bootstrap template sync is working when**:

1. ✅ ReAlign improvements auto-flow to bootstrap (weekly sync)
2. ✅ Bootstrap stays 100% generic (validation passes)
3. ✅ New projects bootstrap successfully
4. ✅ Documentation clearly explains what each component does
5. ✅ Existing projects can upgrade easily
6. ✅ Version history is clear and traceable

**Bootstrap template sync has failed if**:

- ❌ ReAlign-specific content in bootstrap template
- ❌ Bootstrap template diverges from ReAlign (no updates)
- ❌ Documentation is outdated
- ❌ New projects fail to bootstrap
- ❌ No clear upgrade path for existing projects

---

## File Structure for Sync

```
realign/
├── .claude/
│   ├── bootstrap-template/          # Generic, universal version
│   │   ├── SYNC_STRATEGY.md         # This file
│   │   ├── CHANGELOG_BOOTSTRAP.md   # What improved and when
│   │   ├── agents/                  # Generic agent definitions
│   │   ├── skills/                  # Generic skills
│   │   ├── hooks/                   # Language-agnostic hooks
│   │   └── docs/                    # User-friendly explanations
│   ├── agents/                      # ReAlign-specific agents
│   ├── skills/                      # ReAlign-specific skills
│   └── PROJECT.md                   # ReAlign-specific
│
├── scripts/
│   ├── sync_bootstrap_template.sh   # Auto-sync script
│   ├── generalize_for_bootstrap.py  # Content generalization
│   └── generate_bootstrap_docs.py   # User documentation generator
│
└── .github/
    └── workflows/
        └── sync-bootstrap.yml       # Auto-sync on schedule
```

---

## GitHub Action for Auto-Sync

`.github/workflows/sync-bootstrap.yml`:

```yaml
name: Sync Bootstrap Template

on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday
  workflow_dispatch:  # Manual trigger

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run sync script
        run: ./scripts/sync_bootstrap_template.sh

      - name: Validate generic content
        run: |
          if grep -r "ReAlign\|MLX\|LoRA" .claude/bootstrap-template/; then
            echo "ERROR: Project-specific content detected"
            exit 1
          fi

      - name: Create PR if changes
        uses: peter-evans/create-pull-request@v5
        with:
          title: "chore: sync bootstrap template from ReAlign improvements"
          body: "Automated sync of improvements to bootstrap template"
          branch: "sync-bootstrap-$(date +%Y%m%d)"
```

---

## Summary: Keep Bootstrap Updated Strategy

| What | How | Frequency |
|------|-----|-----------|
| **Extract improvements** | `sync_bootstrap_template.sh` | Weekly |
| **Generalize content** | `generalize_for_bootstrap.py` | Weekly |
| **Validate generic** | Grep checks | Every sync |
| **Document changes** | `CHANGELOG_BOOTSTRAP.md` | When notable |
| **Tag versions** | `git tag bootstrap-vX.Y.Z` | Monthly |
| **Test bootstrap** | Apply to dummy project | Before tag |
| **Publish** | GitHub release | Monthly |

**Result**: Bootstrap template stays in sync with ReAlign improvements while remaining 100% generic and usable for any new project.
