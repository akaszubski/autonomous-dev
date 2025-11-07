# README.md Synchronization Strategy

**Problem**: We have two README files with different audiences but overlapping content:
- `/README.md` - Root (for contributors, developers, architecture)
- `/plugins/autonomous-dev/README.md` - Plugin (for users, installation, usage)

**Goal**: Keep critical sections synchronized automatically.

---

## 🔄 How It Works

### Automated Validation Hook

**Location**: `plugins/autonomous-dev/hooks/validate_readme_sync.py`

**Triggers**: Pre-commit (when either README.md is modified)

**Scope**: This hook **only runs in the autonomous-dev plugin repository**. It automatically detects if it's running in a user project and silently skips validation (no blocking, no warnings). Users who install the plugin will never be affected by this hook.

**What it checks**:
- ✅ **Skill count**: Both READMEs must report same number (e.g., "19 active skills")
- ✅ **Agent count**: Both must report same number (e.g., "18 AI specialists")
- ⚠️ **Command count**: Warning if different (e.g., "18 commands")
- ⚠️ **Version**: Warning if different (e.g., "v3.5.0")

**Exit codes**:
- `0`: READMEs in sync ✅
- `1`: Warning (minor differences, allow commit) ⚠️
- `2`: Block commit (critical sections out of sync) ❌

---

## 📝 What Must Stay in Sync

### Critical (Blocks Commit)

**Skill Count**:
- Root README: `"19 Active Skills"`
- Plugin README: `"19 active skills"`
- Format: `(\d+)\s+[Aa]ctive\s+[Ss]kills`

**Agent Count**:
- Root README: `"18 AI Specialists"`
- Plugin README: `"18 AI specialists"`
- Format: `(\d+)\s+(?:[Aa][Ii]\s+)?[Ss]pecialists?(?:\s+agents)?`

### Warning Only (Allows Commit)

**Command Count**:
- Both should report same count (e.g., "18 commands")

**Version**:
- Both should have same version (e.g., "v3.5.0")

---

## 🛠️ Usage

### Manual Check

```bash
# Run validation manually
python plugins/autonomous-dev/hooks/validate_readme_sync.py

# Exit code 0 = success
echo $?
```

### Automatic Check (Pre-Commit)

**For autonomous-dev contributors only** - Add to `.claude/settings.local.json`:

```json
{
  "hooks": {
    "PreToolUse": {
      "Edit": [
        "plugins/autonomous-dev/hooks/validate_readme_sync.py"
      ],
      "Write": [
        "plugins/autonomous-dev/hooks/validate_readme_sync.py"
      ]
    }
  }
}
```

This runs the validator whenever you edit or write README files.

**Note for plugin users**: This hook automatically detects if you're in a user project (not the plugin repository) and silently succeeds. You will never see validation errors in your own projects, even if this hook is configured.

---

## 🔧 Fixing Sync Issues

If validation fails:

```bash
# 1. See what's different
python plugins/autonomous-dev/hooks/validate_readme_sync.py

# 2. Update the mismatched README
# Example: Root says "19 Active Skills", Plugin says "20 Active Skills"
vim plugins/autonomous-dev/README.md  # Fix to "19 Active Skills"

# 3. Verify sync
python plugins/autonomous-dev/hooks/validate_readme_sync.py
# Should exit 0 (success)

# 4. Commit
git add README.md plugins/autonomous-dev/README.md
git commit -m "docs: sync READMEs"
```

---

## 📋 Checklist for README Updates

When updating either README:

- [ ] Update skill count in BOTH READMEs if skills added/removed
- [ ] Update agent count in BOTH READMEs if agents added/removed
- [ ] Update command count in BOTH READMEs if commands added/removed
- [ ] Update version in BOTH READMEs when releasing
- [ ] Run `python plugins/autonomous-dev/hooks/validate_readme_sync.py` before commit
- [ ] Commit both READMEs together (not separately)

---

## 🎯 What Can Differ

These sections are **intentionally different** between READMEs:

**Root README** (contributor focus):
- Development workflow
- Plugin architecture details
- Contributing guidelines
- Testing infrastructure
- Dogfooding setup

**Plugin README** (user focus):
- Installation instructions
- Quick start guide
- Command reference
- Usage examples
- Troubleshooting

---

## 🚀 Example: Adding a New Skill

**Scenario**: You added a 20th skill called "performance-optimization"

**Steps**:

1. **Add skill directory**:
   ```bash
   mkdir -p plugins/autonomous-dev/skills/performance-optimization
   vim plugins/autonomous-dev/skills/performance-optimization/SKILL.md
   ```

2. **Update root README**:
   ```bash
   vim README.md
   # Change: "19 Active Skills" → "20 Active Skills"
   # Add: "performance-optimization" to skill list
   ```

3. **Update plugin README**:
   ```bash
   vim plugins/autonomous-dev/README.md
   # Change: "19 active skills" → "20 active skills"
   # Add: "performance-optimization" to skill list
   ```

4. **Verify sync**:
   ```bash
   python plugins/autonomous-dev/hooks/validate_readme_sync.py
   # Should exit 0
   ```

5. **Commit**:
   ```bash
   git add README.md plugins/autonomous-dev/README.md
   git add plugins/autonomous-dev/skills/performance-optimization/
   git commit -m "feat: add performance-optimization skill"
   ```

---

## 🔍 Troubleshooting

### Validator reports "NOT FOUND"

**Problem**: Regex didn't match the format

**Solution**: Check that the format matches exactly:
- "19 Active Skills" ✅
- "19 active skills" ✅
- "19 Skills" ❌ (missing "Active")
- "We have 19 skills" ❌ (wrong format)

### Validator reports different counts

**Problem**: READMEs genuinely out of sync

**Solution**: Manually inspect both files and update to match reality:
```bash
# Count skills in filesystem
ls plugins/autonomous-dev/skills/ | wc -l
# Update both READMEs to match this count
```

### Hook not running automatically

**Problem**: Not configured in settings.local.json

**Solution**: Add hook to settings (see "Automatic Check" section above)

---

## 📚 Related Documentation

- `CONTRIBUTING.md` - Contributing guidelines (includes README update process)
- `docs/DEVELOPMENT.md` - Development workflow (includes testing)
- `plugins/autonomous-dev/README.md` - Plugin user guide
- `README.md` - Root contributor guide

---

**Last Updated**: 2025-11-07 (Issue #35 - Agent-Skill Integration)
**Validator**: `plugins/autonomous-dev/hooks/validate_readme_sync.py`
**Status**: Active and enforced on all commits
