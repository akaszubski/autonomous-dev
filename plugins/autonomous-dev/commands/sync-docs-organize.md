---
description: Organize documentation files - move .md files from root to docs/
---

# Organize Documentation Files

**Move and organize .md files into docs/ directory**

---

## Usage

```bash
/sync-docs-organize
```

**Scope**: File organization only
**Time**: < 30 seconds
**Changes**: Moves files, updates links

---

## What This Does

Organizes documentation filesystem:
1. Scan root directory for .md files
2. Categorize by type (guides, api, research, archive)
3. Move to appropriate docs/ subdirectory
4. Update internal links
5. Keep root clean

**Only moves files** - doesn't sync API docs or update CHANGELOG.

---

## Expected Output

```
Organizing documentation files...

Scanning root directory...
  Found 5 markdown files in root

Categorizing files...
  ✅ GUIDE.md → guides/
  ✅ INSTALL.md → guides/
  ✅ API.md → api/
  ✅ RESEARCH.md → research/
  ✅ OLD_NOTES.md → archive/

Moving files...
  ✅ Moved GUIDE.md → docs/guides/GUIDE.md
  ✅ Moved INSTALL.md → docs/guides/INSTALL.md
  ✅ Moved API.md → docs/api/API.md
  ✅ Moved RESEARCH.md → docs/research/RESEARCH.md
  ✅ Moved OLD_NOTES.md → docs/archive/OLD_NOTES.md

Updating internal links...
  ✅ Updated 3 cross-references in README.md
  ✅ Updated 2 cross-references in CLAUDE.md

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Files moved: 5
Links updated: 5
Root directory clean ✅
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Directory Structure

**Root** (only essential files):
```
├── README.md           ✅ Keep in root
├── CHANGELOG.md        ✅ Keep in root
├── LICENSE             ✅ Keep in root
├── CLAUDE.md           ✅ Keep in root
└── .claude/            ✅ Keep in root
```

**docs/** (all other .md files):
```
docs/
├── guides/             User guides, tutorials
│   ├── GUIDE.md
│   ├── INSTALL.md
│   └── QUICKSTART.md
├── api/                API reference
│   ├── API.md
│   └── functions.md
├── research/           Research notes, design docs
│   ├── RESEARCH.md
│   └── DECISIONS.md
└── archive/            Old/deprecated docs
    └── OLD_NOTES.md
```

---

## Categorization Logic

**Guides** (`docs/guides/`):
- User-facing documentation
- Installation guides
- Tutorials
- Quickstarts
- Keywords: "guide", "install", "tutorial", "quickstart", "getting started"

**API** (`docs/api/`):
- API reference
- Function documentation
- Class documentation
- Keywords: "api", "reference", "functions", "classes"

**Research** (`docs/research/`):
- Design documents
- Research notes
- Architecture decisions
- Keywords: "research", "design", "architecture", "decision", "adr"

**Archive** (`docs/archive/`):
- Old documentation
- Deprecated guides
- Historical notes
- Keywords: "old", "deprecated", "archive", "legacy"

---

## Link Updating

**Automatically updates links**:

**Before move**:
```markdown
See [API Documentation](API.md) for details.
```

**After move**:
```markdown
See [API Documentation](docs/api/API.md) for details.
```

**Updates links in**:
- README.md
- CLAUDE.md
- Other .md files
- .claude/PROJECT.md

---

## When to Use

- ✅ After creating new documentation
- ✅ When root directory cluttered
- ✅ Before releases (clean repo)
- ✅ In `/align-project` workflows
- ✅ Periodic cleanup

---

## Safety

**Never moves**:
- README.md (stays in root)
- CHANGELOG.md (stays in root)
- LICENSE (stays in root)
- CLAUDE.md (stays in root)
- Files in .claude/ (stays as-is)

**Creates backups**:
- `.backup/` directory with originals
- Can be restored if needed

---

## Configuration (.env)

```bash
# File organization settings
DOCS_AUTO_ORGANIZE=true             # Auto-organize on sync
DOCS_CREATE_BACKUPS=true            # Create backups before moving
DOCS_UPDATE_LINKS=true              # Update cross-references
```

---

## Related Commands

- `/sync-docs` - Sync all documentation
- `/sync-docs-api` - API docs only
- `/sync-docs-changelog` - CHANGELOG only
- `/align-project` - Includes file organization

---

**Use this to keep root directory clean and documentation well-organized.**
