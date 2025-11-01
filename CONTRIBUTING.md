# Contributing to Claude Code Bootstrap

**This repository builds Claude Code automation tools for distribution.**

---

## Important: File Locations (CRITICAL!)

**This repository serves TWO audiences:**
1. **Contributors** (building the plugin) → ROOT level
2. **Users** (using the plugin) → `plugins/autonomous-dev/`

### 🎯 The Golden Rule

**Ask yourself 3 questions:**

1️⃣ **WHO** is this for?
   - Contributors/Developers → ROOT
   - End users → PLUGIN

2️⃣ **WHEN** do they need it?
   - While building the plugin → ROOT
   - While using the plugin → PLUGIN

3️⃣ **WHAT** is it?
   - Development tool/doc → ROOT
   - Plugin feature/doc → PLUGIN

---

### ✅ ROOT LEVEL (Development)

**For:** Contributors building the plugin
**Distributed:** ❌ NO (stays on GitHub)

```
ROOT/
├── docs/                         DEV/CONTRIBUTOR DOCS
│   ├── CONTRIBUTING.md           How to contribute
│   ├── DEVELOPMENT.md            Development workflow
│   ├── CODE-REVIEW-WORKFLOW.md  Code review process
│   ├── IMPLEMENTATION-STATUS.md Build status
│   └── ... (dev docs only)
│
├── scripts/                      BUILD/DEV SCRIPTS
│   └── session_tracker.py        Dev session tracking
│
├── tests/                        REPO TESTS
│   ├── unit/                     Test build scripts
│   └── integration/              Test repo functionality
│
└── Root files
    ├── README.md                 About the repository
    ├── CONTRIBUTING.md           Contributor guide
    ├── CLAUDE.md                 Instructions for Claude
    └── CHANGELOG.md              Version history
```

**Examples:**
- ✅ "How to add a new command" → `docs/DEVELOPMENT.md`
- ✅ "Build script to sync docs" → `scripts/sync_docs.py`
- ✅ "Test that build works" → `tests/integration/`

---

### ✅ PLUGIN LEVEL (Distribution)

**For:** End users installing the plugin
**Distributed:** ✅ YES (via `/plugin install`)

```
plugins/autonomous-dev/
├── docs/                         USER DOCS (22 files)
│   ├── COMMANDS.md               Command reference
│   ├── TROUBLESHOOTING.md        User troubleshooting
│   ├── GITHUB_AUTH_SETUP.md      GitHub setup guide
│   └── ... (user docs only)
│
├── agents/                       AI AGENTS (8 files)
│   ├── orchestrator.md           Master coordinator
│   ├── planner.md                Architecture planner
│   └── ...
│
├── commands/                     SLASH COMMANDS (33 files)
│   ├── test.md                   /test command
│   ├── format.md                 /format command
│   └── ...
│
├── skills/                       SKILLS (6 directories)
│   ├── python-standards/         Python best practices
│   ├── testing-guide/            Testing methodology
│   └── ...
│
├── hooks/                        AUTOMATION HOOKS (8 files)
│   ├── auto_format.py            Auto-format on save
│   ├── auto_test.py              Auto-test on commit
│   └── ...
│
├── scripts/                      USER SCRIPTS
│   └── setup.py                  Setup wizard for users
│
├── templates/                    TEMPLATES
│   ├── PROJECT.md                PROJECT.md template
│   └── settings.local.json       Settings template
│
├── tests/                        PLUGIN TESTS
│   ├── test_uat.py               User acceptance tests
│   └── test_architecture.py     Architecture validation
│
└── Plugin files
    ├── README.md                 Plugin documentation
    ├── QUICKSTART.md             User quick start
    └── .claude-plugin/           Plugin metadata
```

**Examples:**
- ✅ "How to use /test command" → `plugins/autonomous-dev/docs/COMMANDS.md`
- ✅ "Setup wizard for users" → `plugins/autonomous-dev/hooks/setup.py`
- ✅ "Test plugin features" → `plugins/autonomous-dev/tests/`

---

### ❌ NEVER Edit

**Personal config (NOT in git):**
```
~/.claude/                        Your personal config
├── CLAUDE.md                     Your personal instructions
└── settings.json                 Your personal settings
```

---

---

## ⚠️ Common Mistakes (Don't Do This!)

### ❌ Wrong: User docs in ROOT
```bash
# DON'T put user documentation in root docs/
docs/how-to-use-commands.md  ❌
```
✅ **Correct:**
```bash
plugins/autonomous-dev/docs/how-to-use-commands.md  ✅
```

### ❌ Wrong: Dev docs in PLUGIN
```bash
# DON'T put development docs in plugin
plugins/autonomous-dev/docs/CONTRIBUTING.md  ❌
```
✅ **Correct:**
```bash
docs/CONTRIBUTING.md  ✅ (or root CONTRIBUTING.md)
```

### ❌ Wrong: Build scripts in PLUGIN
```bash
# DON'T put build/sync scripts in plugin hooks directory
# (User-facing scripts like setup.py are OK, but build/development scripts belong in root)
plugins/autonomous-dev/hooks/sync_docs.py  ❌ (if it's a development build script)
```
✅ **Correct:**
```bash
scripts/sync_docs.py  ✅ (for development/build scripts)
plugins/autonomous-dev/hooks/setup.py  ✅ (for user-facing scripts)
```

---

## ✅ Validation

### Manual Validation

**Before committing, validate structure:**

```bash
# Run structure validation manually
python scripts/validate_structure.py
```

**What it checks:**
- User docs in plugin only
- Dev docs in root only
- No duplicates between root and plugin
- All user-facing content in plugin
- All dev content in root

### Automatic Validation (Recommended)

**Install pre-commit hook** to automatically validate structure:

```bash
# Install the hook (one-time setup)
ln -sf ../../scripts/hooks/pre-commit .git/hooks/pre-commit

# Now validation runs automatically before each commit
git commit -m "your changes"
```

**To bypass hook** (emergency only):
```bash
git commit --no-verify
```

---

## Workflow for Changes

### Adding/Updating Commands

**Always edit in BOTH locations**:

```bash
# 1. Edit project config
vim .claude/commands/my-command.md

# 2. Copy to plugin
cp .claude/commands/my-command.md plugins/autonomous-dev/commands/

# 3. Commit to git
git add .claude/commands/ plugins/autonomous-dev/commands/
git commit -m "feat: add my-command"

# 4. Push to GitHub
git push

# 5. Test by reloading plugin
# In Claude Code:
# /plugin uninstall autonomous-dev
# /plugin install autonomous-dev
```

### Adding/Updating Agents

```bash
# Edit in plugin directory only
vim plugins/autonomous-dev/agents/my-agent.md

# Commit and push
git add plugins/autonomous-dev/agents/
git commit -m "feat: add my-agent"
git push
```

### Adding/Updating Skills

```bash
# Edit in plugin directory only
vim plugins/autonomous-dev/skills/my-skill.md

# Commit and push
git add plugins/autonomous-dev/skills/
git commit -m "feat: add my-skill"
git push
```

---

## Before Committing

**Checklist**:
- [ ] Changes are in `.claude/` or `plugins/autonomous-dev/`
- [ ] NOT in `~/.claude/` (personal config)
- [ ] Commands synced to both `.claude/commands/` and `plugins/autonomous-dev/commands/`
- [ ] Committed to git
- [ ] Pushed to GitHub
- [ ] Tested by reloading plugin

---

## Testing Changes

After making changes:

1. **Commit and push to GitHub**:
   ```bash
   git add .
   git commit -m "feat: your change"
   git push
   ```

2. **Reload plugin in Claude Code**:
   ```bash
   /plugin uninstall autonomous-dev
   /plugin install autonomous-dev
   ```

3. **Test the changes**:
   ```bash
   /your-new-command
   ```

---

## Directory Structure

```
autonomous-dev/
├── .claude/                      ← Project config (git-tracked)
│   ├── commands/                 ← Commands (sync to plugin)
│   ├── PROJECT.md                ← Architecture
│   └── hooks/                    ← Git hooks
├── plugins/
│   └── autonomous-dev/           ← Plugin (git-tracked)
│       ├── commands/             ← Commands (synced from .claude)
│       ├── agents/               ← AI agents
│       ├── skills/               ← Skills
│       ├── hooks/                ← Automation hooks
│       └── marketplace.json      ← Plugin metadata
├── docs/                         ← Documentation (git-tracked)
└── scripts/                      ← Helper scripts (git-tracked)

~/.claude/                        ← Personal config (NOT in git)
├── commands/                     ← Auto-populated by plugin install
└── CLAUDE.md                     ← Your personal instructions
```

---

## Key Principle

**This repository is the SOURCE OF TRUTH for the autonomous-dev plugin.**

All changes must be:
1. Made in git-tracked locations
2. Committed to git
3. Pushed to GitHub
4. Distributed via marketplace

Personal `~/.claude/` folder is just where the plugin gets INSTALLED, not where you develop.
