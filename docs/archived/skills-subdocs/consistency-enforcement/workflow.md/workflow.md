# Consistency Enforcement - Workflow

Step-by-step workflows for common documentation scenarios.

---

## Scenario 1: Adding New Skill

**Problem**: Creating new skill but forgetting to update documentation counts.

**Correct workflow**:

```bash
# 1. Create skill
mkdir skills/new-skill-name

# 2. Update README.md
# Change "X Skills" to "Y Skills" (where Y = X + 1)
# Add skill to categorized table

# 3. Update cross-references
# - docs/SYNC-STATUS.md
# - docs/UPDATES.md
# - INSTALL_TEMPLATE.md
# - .claude-plugin/marketplace.json (metrics.skills)
# - templates/knowledge/best-practices/claude-code-2.0.md

# 4. Run tests to verify
pytest tests/test_documentation_consistency.py -v

# ✅ Now all counts match!
```

---

## Scenario 2: Updating README.md

**Problem**: Updating README.md counts but forgetting other docs.

**Correct workflow**:

```bash
# 1. Update README.md
# "9 Skills" → "12 Skills (Comprehensive SDLC Coverage)"

# 2. Find all cross-references
grep -r "9 skills\|9 Skills" plugins/autonomous-dev/*.md plugins/autonomous-dev/docs/*.md

# 3. Update each file found
# - SYNC-STATUS.md: "9 skills" → "12 skills"
# - UPDATES.md: "All 9 skills" → "All 12 skills"
# - INSTALL_TEMPLATE.md: "9 Skills" → "12 Skills"

# 4. Update marketplace.json
# "skills": 9 → "skills": 12

# 5. Run tests to verify
pytest tests/test_documentation_consistency.py -v

# ✅ All documents now consistent!
```

---

## Scenario 3: Removing Skill

**Problem**: Removing skill but leaving stale references.

**Correct workflow**:

```bash
# 1. Remove skill
rm -rf skills/deprecated-skill

# 2. Update README.md count
# "12 Skills" → "11 Skills"
# Remove skill from table

# 3. Update all cross-references
# (Same as Scenario 2)

# 4. Search for skill references
grep -r "deprecated-skill" plugins/autonomous-dev/

# 5. Remove all references found

# 6. Run tests to verify
pytest tests/test_documentation_consistency.py -v

# ✅ Skill removed, all docs updated!
```

---

## Scenario 4: Before Committing

**Problem**: Committing documentation changes without verifying consistency.

**Correct workflow**:

```bash
# 1. Run consistency validation
python plugins/autonomous-dev/hooks/validate_docs_consistency.py

# 2. If checks fail, fix issues

# 3. Re-run validation
python plugins/autonomous-dev/hooks/validate_docs_consistency.py

# 4. When all checks pass, commit
git commit -m "docs: update skill count to 12"

# ✅ Consistent documentation committed!
```

---

## Troubleshooting

### "Tests are failing but I don't know why"

```bash
# Run tests with verbose output
pytest tests/test_documentation_consistency.py -v

# Read the assertion error - it tells you exactly what's wrong
# Example: "README.md shows 9 skills but actual is 12"
```

### "I updated README.md but tests still fail"

**Check**: Did you update ALL cross-references?

```bash
# Find all skill count mentions
grep -r "[0-9]+ skills" plugins/autonomous-dev/*.md plugins/autonomous-dev/docs/*.md

# Each file should show the SAME count
```

### "marketplace.json metrics don't match"

```bash
# Check current metrics
cat .claude-plugin/marketplace.json | grep -A 5 '"metrics"'

# Count actual resources
ls -d plugins/autonomous-dev/skills/*/ | wc -l
ls plugins/autonomous-dev/agents/*.md | wc -l
ls plugins/autonomous-dev/commands/*.md | wc -l

# Update marketplace.json to match
```

### "Pre-commit hook is blocking my commit"

**Option 1**: Fix the inconsistency (recommended)
```bash
python plugins/autonomous-dev/hooks/validate_docs_consistency.py
# Read output, fix issues
```

**Option 2**: Skip hook (NOT RECOMMENDED)
```bash
git commit --no-verify
# Only use in emergency!
```
