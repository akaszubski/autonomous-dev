# Strict Mode - Professional SDLC Enforcement

**Status**: ⚠️ Beta - Auto-orchestration system active

Strict Mode enforces software engineering best practices automatically through "vibe coding" (natural language feature requests). All work must align with PROJECT.md strategic direction.

---

## 🎯 What is Strict Mode?

**The Vision**: Describe features in natural language → System automatically follows all SDLC best practices → Professional, consistent output without manual steps.

**How it works**:
1. You say: "implement user authentication"
2. System detects feature request (auto-orchestration)
3. Orchestrator checks PROJECT.md alignment
4. If aligned → Full agent pipeline activates
5. All SDLC steps enforced automatically

---

## 🚀 Quick Start

### Enable Strict Mode

```bash
# Copy strict mode settings
cp .claude/templates/settings.strict-mode.json .claude/settings.local.json

# Ensure PROJECT.md exists
cp .claude/templates/PROJECT.md PROJECT.md

# Edit PROJECT.md to define your strategic direction
vim PROJECT.md
```

### Use Vibe Coding

```bash
# Just describe what you want to implement
"implement user authentication with JWT tokens"

# Auto-orchestration activates:
→ Detects feature request
→ Invokes orchestrator agent
→ Checks PROJECT.md alignment
→ Runs full SDLC pipeline if aligned
```

---

## 🔒 What Strict Mode Enforces

### 1. PROJECT.md Alignment (Gatekeeper)

**BEFORE any feature work**:
- ✅ PROJECT.md must exist
- ✅ Must have GOALS, SCOPE, CONSTRAINTS sections
- ✅ Feature request must align with SCOPE
- ❌ Work BLOCKED if not aligned

**Two options when misaligned**:
1. Update PROJECT.md to include new scope
2. Don't implement the feature (out of scope)

### 2. Auto-Orchestration

**Feature request keywords trigger agents**:
- "implement X"
- "add X"
- "create X"
- "build X"
- "develop X"
- "write X"

**Agent pipeline** (automatic):
```
researcher → planner → test-master → implementer → 
reviewer → security-auditor → doc-master
```

### 3. SDLC Steps (Cannot Skip)

**Each step required**:
1. ✅ Research - Find existing patterns
2. ✅ Plan - Create implementation plan
3. ✅ Tests FIRST - Write failing tests (TDD)
4. ✅ Implement - Make tests pass
5. ✅ Review - Code quality check
6. ✅ Security - Vulnerability scan
7. ✅ Documentation - Update docs
8. ✅ Validate - Run all checks

**If you try to skip**:
- Implement without tests → BLOCKED
- Commit without docs → BLOCKED
- Push without security scan → BLOCKED

### 4. File Organization

**Standard structure enforced**:
```
project/
├── src/              # ALL source code
├── tests/            # ALL tests
│   ├── unit/        # Unit tests
│   ├── integration/ # Integration tests
│   └── uat/         # User acceptance tests
├── docs/             # ALL documentation
├── scripts/          # Utility scripts
└── .claude/          # Claude Code config
    └── PROJECT.md    # Strategic direction
```

**Root directory kept clean**:
- ❌ No loose .py files
- ❌ No temp files
- ❌ No test files
- ✅ Only README.md, LICENSE, .gitignore, config files

**Auto-fix available**:
```bash
python hooks/enforce_file_organization.py --fix
```

### 5. Pre-Commit Validation (Blocking)

**Before EVERY commit, these run**:
1. PROJECT.md alignment check
2. All tests must pass
3. Security scan must pass
4. Documentation must be synced

**Commit blocked if any fail**.

---

## 📋 Complete Workflow Example

### Greenfield (New Project)

```bash
# 1. Install plugin
/plugin install autonomous-dev

# 2. Enable strict mode
/setup --strict-mode

# 3. Define strategic direction
vim PROJECT.md  # Define GOALS, SCOPE, CONSTRAINTS

# 4. Start building
"implement user authentication with JWT"

# Auto-orchestration activates:
[Feature Request Detected]
→ Orchestrator: Checking PROJECT.md...
→ Orchestrator: "Authentication is IN SCOPE. Proceeding."
→ Researcher: Finding JWT best practices...
→ Planner: Creating implementation plan...
   [Shows plan, asks approval]
→ Test-Master: Writing failing tests...
→ Implementer: Making tests pass...
→ Reviewer: Checking code quality...
→ Security-Auditor: Scanning for vulnerabilities...
→ Doc-Master: Updating documentation...
→ Validator: Running all checks...

✅ Implementation complete
✅ All tests passing
✅ Documentation synced
✅ Security scan passed
✅ Ready to commit

# 5. Commit (validation automatic)
git commit -m "feat: add JWT authentication"

# Pre-commit hooks run:
→ PROJECT.md alignment ✅
→ Tests ✅
→ Security ✅
→ Docs sync ✅

✅ Commit successful
```

### Brownfield (Existing Project)

```bash
# 1. Retrofit existing project
cd my-existing-project/
/plugin install autonomous-dev

# 2. Align structure
/align-project-retrofit

[Analysis]
❌ Files in wrong locations
❌ Missing PROJECT.md
❌ Tests not organized
❌ Docs out of sync

[Plan]
1. Create standard directories (src/, tests/, docs/)
2. Move 47 files to correct locations
3. Create PROJECT.md from existing README
4. Organize tests into unit/integration/uat
5. Sync documentation

Approve? [Yes/No]

# 3. Enable strict mode going forward
/setup --strict-mode

# 4. All future work follows strict mode
"add API rate limiting"
→ Auto-orchestration ensures best practices
```

---

## 🛠️ Commands

### Setup
```bash
/setup --strict-mode              # Enable strict mode
/setup --create-project-md        # Create PROJECT.md only
```

### Validation
```bash
/align-project                    # Check PROJECT.md alignment
python hooks/validate_project_alignment.py   # Manual validation
python hooks/enforce_file_organization.py    # Check structure
python hooks/enforce_file_organization.py --fix  # Auto-fix structure
```

### Brownfield
```bash
/align-project-retrofit           # Retrofit existing project (COMING SOON)
```

---

## 📊 Validation Hooks

### UserPromptSubmit Hook
```python
# Runs BEFORE processing your message
→ Detects feature requests
→ Invokes orchestrator if detected
→ Orchestrator checks PROJECT.md alignment
→ Proceeds with agent pipeline if aligned
```

### PreCommit Hook (Blocking)
```python
# Runs BEFORE every commit
→ PROJECT.md alignment validation
→ All tests must pass
→ Security scan must pass
→ Documentation sync validation
# Blocks commit if any fail
```

### PostFileEdit Hook
```python
# Runs AFTER file edits
→ Auto-format code (black, prettier)
→ Maintains consistent style automatically
```

### SubagentStop Hook
```python
# Runs AFTER subagent completes task
→ Logs agent actions to docs/sessions/ (prevents context bloat)
→ Tracks progress without filling conversation history
→ New in Issue #84: Moved to plugins/autonomous-dev/hooks/session_tracker.py
```

---

## ⚙️ Configuration

### Strict Mode Settings

Location: `.claude/settings.local.json`

**Fix for Issue #84**: Hook paths now correctly reference plugin location.

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python plugins/autonomous-dev/hooks/detect_feature_request.py && echo '[Auto-Orchestration] Invoking orchestrator for PROJECT.md validation...'"
          }
        ]
      }
    ],
    "PreFileEdit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python plugins/autonomous-dev/hooks/auto_format.py"
          }
        ]
      }
    ],
    "PostFileEdit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python plugins/autonomous-dev/hooks/auto_format.py"
          }
        ]
      }
    ],
    "PreCommit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python plugins/autonomous-dev/hooks/validate_project_alignment.py || exit 1"
          },
          {
            "type": "command",
            "command": "python plugins/autonomous-dev/hooks/enforce_orchestrator.py || exit 1"
          },
          {
            "type": "command",
            "command": "python plugins/autonomous-dev/hooks/enforce_tdd.py || exit 1"
          },
          {
            "type": "command",
            "command": "python plugins/autonomous-dev/hooks/auto_fix_docs.py || exit 1"
          },
          {
            "type": "command",
            "command": "python plugins/autonomous-dev/hooks/validate_session_quality.py || exit 1"
          },
          {
            "type": "command",
            "command": "python plugins/autonomous-dev/hooks/auto_test.py || exit 1"
          },
          {
            "type": "command",
            "command": "python plugins/autonomous-dev/hooks/security_scan.py || exit 1"
          }
        ]
      }
    ],
    "SubagentStop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python plugins/autonomous-dev/hooks/session_tracker.py subagent 'Subagent completed task'"
          }
        ]
      }
    ]
  }
}
```

**Key Path Changes (Issue #84)**:
- `.claude/hooks/` → `plugins/autonomous-dev/hooks/` (plugin location)
- `scripts/session_tracker.py` → `plugins/autonomous-dev/hooks/session_tracker.py` (new hook location)
- Ensures hooks resolve correctly in both plugin-installed and development environments

---

## 🚨 Troubleshooting

### "PROJECT.md not found"
```bash
# Create from template
cp .claude/templates/PROJECT.md PROJECT.md

# Or use setup
/setup --create-project-md
```

### "Feature not in SCOPE"
```bash
# Option 1: Update PROJECT.md to include it
vim PROJECT.md  # Add to SCOPE section

# Option 2: Don't implement (respect boundaries)
```

### "Commit blocked by validation"
```bash
# Check what failed
git commit

# Fix the issues
# - If tests failing: Fix tests
# - If docs out of sync: Update docs
# - If security issues: Fix vulnerabilities

# Retry commit
git commit
```

### "Auto-orchestration not triggering"
```bash
# Check hook is installed
cat .claude/settings.local.json | grep detect_feature_request

# Verify hook script exists
ls .claude/hooks/detect_feature_request.py

# Use explicit keywords
"implement user authentication"  # ✅ Triggers
"how does auth work?"            # ❌ Doesn't trigger (question)
```

---

## 📖 Philosophy

**Automation > Reminders > Hope**

Strict mode makes quality automatic, not optional:
- ✅ PROJECT.md alignment enforced (not hoped for)
- ✅ Tests required (not reminded to write)
- ✅ Docs synced automatically (not manual)
- ✅ Security scanned (not forgotten)

**Result**: Professional consistency without cognitive load.

---

## 🎯 Future Enhancements

Planned features:
- [ ] `/align-project-retrofit` - Brownfield alignment command
- [ ] AI-powered SCOPE validation - Semantic alignment checking
- [ ] Cross-project templates - Reuse patterns across projects
- [ ] Team presets - Standardize across team members
- [ ] CI/CD integration - GitHub Actions validation

---

## 📚 See Also

- [PROJECT.md Template](../templates/PROJECT.md)
- [Standard Project Structure](../templates/project-structure.json)
- [Agent Pipeline](../README.md#agents)
- [Hooks System](../README.md#hooks)
