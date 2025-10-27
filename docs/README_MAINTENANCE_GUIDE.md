# README.md Maintenance Guide

**Version**: v3.1.0
**Last Updated**: 2025-10-27
**Objective**: Keep README.md in sync with actual codebase state through automated validation

---

## Quick Start

### One-Time Setup

```bash
# Make hooks executable
chmod +x plugins/autonomous-dev/hooks/validate_readme_*.py

# Install as pre-commit hook (optional)
# This will automatically validate on every commit
pip install pre-commit
pre-commit install -c .hooks/pre-commit-config.yaml
```

### Manual Validation (Anytime)

```bash
# Quick validation (filesystem checks only)
python plugins/autonomous-dev/hooks/validate_readme_accuracy.py

# Detailed audit with report generation
python plugins/autonomous-dev/hooks/validate_readme_accuracy.py --audit

# GenAI semantic validation (requires ANTHROPIC_API_KEY)
python plugins/autonomous-dev/hooks/validate_readme_with_genai.py --genai

# Full audit with GenAI
python plugins/autonomous-dev/hooks/validate_readme_with_genai.py --audit --genai
```

---

## What Gets Validated

### Automatic Filesystem Checks ✅

The hook validates these aspects automatically:

1. **Agent Count** (should be 19)
   - Counts: `plugins/autonomous-dev/agents/*.md`
   - Verifies README claims 19 agents

2. **Skill Count** (should be 19)
   - Counts: `plugins/autonomous-dev/skills/*/SKILL.md`
   - Verifies README lists 19 skills

3. **Command Count** (should be 9)
   - Counts: `plugins/autonomous-dev/commands/*.md`
   - Verifies all commands documented in README

4. **Hook Count** (should be 24)
   - Counts: `plugins/autonomous-dev/hooks/*.py`
   - Verifies README claims correct count

5. **Descriptions**
   - Verifies core agent descriptions present
   - Checks skill categories explained
   - Validates workflow descriptions

### Optional GenAI Validation 🤖

When enabled with `--genai` flag:

1. **Semantic Accuracy** - Uses Claude to verify:
   - Agent descriptions are accurate
   - Skill categories are correct
   - Workflow explanation matches implementation
   - Command purposes are correctly stated

2. **Consistency** - Checks:
   - Version numbers align
   - Project status is current
   - Installation instructions accurate

3. **Completeness** - Detects:
   - Missing command documentation
   - Incomplete skill descriptions
   - Outdated claim

---

## When README Changes Require Updates

### Scenario 1: You Add a New Agent

**What happens**:
- New file added: `plugins/autonomous-dev/agents/new-agent.md`
- Hook detects count mismatch (19 vs expected count)

**What to do**:
```bash
# 1. Validate - hook will flag the issue
python plugins/autonomous-dev/hooks/validate_readme_accuracy.py

# 2. Update README.md manually
# - Add agent to appropriate section (Core/Analysis/Automation)
# - Include description and model size
# - Update count in section header

# 3. Re-validate
python plugins/autonomous-dev/hooks/validate_readme_accuracy.py

# 4. Commit
git add plugins/autonomous-dev/agents/new-agent.md README.md
git commit -m "feat: Add new-agent specialist"
```

### Scenario 2: You Add a New Skill

**What happens**:
- New directory: `plugins/autonomous-dev/skills/new-skill/`
- Hook detects count mismatch (19 vs expected count)

**What to do**:
```bash
# 1. Validate - hook will flag the issue
python plugins/autonomous-dev/hooks/validate_readme_accuracy.py

# 2. Update README.md manually
# - Add skill to appropriate category
# - Include brief description
# - Update skill count if needed

# 3. Re-validate
python plugins/autonomous-dev/hooks/validate_readme_accuracy.py --genai

# 4. Commit
git add plugins/autonomous-dev/skills/new-skill/ README.md
git commit -m "feat: Add new-skill specialist"
```

### Scenario 3: You Add a New Command

**What happens**:
- New file: `plugins/autonomous-dev/commands/new-command.md`
- Hook detects command count mismatch

**What to do**:
```bash
# 1. Validate
python plugins/autonomous-dev/hooks/validate_readme_accuracy.py

# 2. Update README.md
# - Add to appropriate command section
# - Include usage example and description
# - Update command count if it's now 9+

# 3. Validate
python plugins/autonomous-dev/hooks/validate_readme_accuracy.py

# 4. Commit
git add plugins/autonomous-dev/commands/new-command.md README.md
git commit -m "feat: Add /new-command for X"
```

### Scenario 4: You Modify Agent/Skill Descriptions

**What happens**:
- Description changes in agent/skill file
- README may now have outdated description

**What to do**:
```bash
# 1. Run GenAI validation to catch semantic drift
python plugins/autonomous-dev/hooks/validate_readme_with_genai.py --genai

# 2. GenAI will flag if README is now inaccurate

# 3. Update README.md descriptions to match

# 4. Re-validate
python plugins/autonomous-dev/hooks/validate_readme_with_genai.py --genai

# 5. Commit both changes
git add plugins/autonomous-dev/agents/agent.md README.md
git commit -m "docs: Update agent description in README"
```

---

## Pre-Commit Hook Configuration

### Option 1: Automatic on Every Commit

Create `.hooks/pre-commit-config.yaml`:

```yaml
# Pre-commit hook configuration
# Runs automatically before every commit

repos:
  - repo: local
    hooks:
      - id: validate-readme-accuracy
        name: Validate README.md accuracy
        entry: python plugins/autonomous-dev/hooks/validate_readme_accuracy.py
        language: python
        stages: [commit]
        pass_filenames: false
        always_run: true
        verbose: true

      # Optional: Run GenAI validation on relevant changes
      - id: validate-readme-genai
        name: GenAI semantic validation (README)
        entry: python plugins/autonomous-dev/hooks/validate_readme_with_genai.py --genai
        language: python
        stages: [commit]
        pass_filenames: false
        files: (plugins/autonomous-dev/(agents|skills|commands)/)|(README\.md)
        verbose: true
```

Then install:
```bash
pre-commit install -c .hooks/pre-commit-config.yaml
```

### Option 2: Manual Validation Before Commit

Run manually before committing:
```bash
# Quick check
python plugins/autonomous-dev/hooks/validate_readme_accuracy.py

# Detailed check with GenAI (if you modified agents/skills/commands)
if git diff --cached | grep -q "agents\|skills\|commands\|README"; then
    python plugins/autonomous-dev/hooks/validate_readme_with_genai.py --genai
fi
```

### Option 3: Git Alias for Easy Access

Add to your `.gitconfig`:

```ini
[alias]
    validate-readme = !python plugins/autonomous-dev/hooks/validate_readme_accuracy.py
    audit-readme = !python plugins/autonomous-dev/hooks/validate_readme_accuracy.py --audit
    validate-all = !python plugins/autonomous-dev/hooks/validate_readme_with_genai.py --genai --audit
```

Then use:
```bash
git validate-readme              # Quick check
git audit-readme                 # Full audit with report
git validate-all                 # GenAI + report
```

---

## Troubleshooting

### Hook Says Agent Count Mismatch

**Problem**: "Agent count mismatch: README claims 19, but found 20"

**Solution**:
```bash
# 1. Check what agents actually exist
ls plugins/autonomous-dev/agents/ | wc -l

# 2. Update README to match actual count
# Find "19 Specialized Agents" and update the number

# 3. Re-validate
python plugins/autonomous-dev/hooks/validate_readme_accuracy.py
```

### GenAI Validation Fails

**Problem**: "ANTHROPIC_API_KEY not set" or GenAI reports issues

**Solution**:
```bash
# Make sure API key is set
export ANTHROPIC_API_KEY="sk-..."

# Run validation with GenAI
python plugins/autonomous-dev/hooks/validate_readme_with_genai.py --genai

# If issues found, read GenAI assessment and fix README accordingly
```

### Pre-commit Hook Blocks Commit

**Problem**: "Hook failed: validate-readme-accuracy.py"

**Solution**:
```bash
# 1. Run hook manually to see detailed error
python plugins/autonomous-dev/hooks/validate_readme_accuracy.py

# 2. Fix the issue (usually update README)

# 3. Re-run hook
python plugins/autonomous-dev/hooks/validate_readme_accuracy.py

# 4. Commit again
git add README.md
git commit -m "docs: Fix README accuracy"
```

### Skip Validation for a Commit

If you absolutely must skip validation:

```bash
# Only for emergency situations!
git commit --no-verify -m "Emergency fix"
```

⚠️ **Warning**: Skipping validation can introduce documentation drift. Only use if necessary.

---

## Audit Report

### Running Audits

```bash
# Generate detailed audit report
python plugins/autonomous-dev/hooks/validate_readme_accuracy.py --audit

# This creates: docs/README_AUDIT.md
```

### What's in the Report

The audit report includes:
- ✅ Validation results for each component
- ✅ Counts: actual vs claimed
- ✅ Warnings about potential issues
- ✅ Timestamp of audit
- ✅ Recommendations for fixes

Example report location: `docs/README_AUDIT.md`

---

## Validation Workflow

### When Adding/Changing Components

```
1. Make code change
   (add/modify agent, skill, command, hook)
   ↓
2. Run validation
   python plugins/autonomous-dev/hooks/validate_readme_accuracy.py
   ↓
3. Does it pass?
   YES → Continue to step 5
   NO → Fix README and goto step 2
   ↓
5. Commit both code and README changes
   git add .
   git commit -m "feat/docs: ..."
```

### When You're Unsure if README is Accurate

```
1. Run quick check
   python plugins/autonomous-dev/hooks/validate_readme_accuracy.py
   ↓
2. Any warnings or errors?
   YES → Run full audit
   NO → All good!
   ↓
3. Run full audit with GenAI
   python plugins/autonomous-dev/hooks/validate_readme_with_genai.py --audit --genai
   ↓
4. Read report (docs/README_AUDIT.md)
   ↓
5. Fix any issues found
```

---

## Best Practices

### ✅ DO

- ✅ Run validation before committing changes to agents/skills/commands
- ✅ Use GenAI validation when modifying descriptions
- ✅ Generate audit reports quarterly
- ✅ Fix README immediately when validation fails
- ✅ Keep README_AUDIT.md reports in git history

### ❌ DON'T

- ❌ Commit without validating if you changed agents/skills/commands
- ❌ Skip validation hooks without good reason
- ❌ Update counts without updating actual files
- ❌ Leave README with warnings for more than a few commits
- ❌ Ignore GenAI semantic validation warnings

---

## Integration with CI/CD

### GitHub Actions Example

Create `.github/workflows/validate-readme.yml`:

```yaml
name: Validate README.md

on:
  pull_request:
    paths:
      - 'plugins/autonomous-dev/**'
      - 'README.md'
  push:
    branches: [main, master]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install anthropic

      - name: Validate README accuracy
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          python plugins/autonomous-dev/hooks/validate_readme_with_genai.py --genai

      - name: Generate audit report
        if: always()
        run: |
          python plugins/autonomous-dev/hooks/validate_readme_accuracy.py --audit

      - name: Upload audit report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: readme-audit-report
          path: docs/README_AUDIT.md
```

---

## Summary

| Task | Command | Frequency |
|------|---------|-----------|
| Quick check | `validate_readme_accuracy.py` | Before commits |
| Full audit | `validate_readme_accuracy.py --audit` | Monthly |
| GenAI validation | `validate_readme_with_genai.py --genai` | When descriptions change |
| CI/CD validation | GitHub Actions | Every PR/push |

---

**Questions?** Check `docs/README_AUDIT.md` for latest validation report.
