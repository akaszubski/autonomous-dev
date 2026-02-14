# Consistency Enforcement - Templates

Checklists and verification commands.

---

## Quick Consistency Checklist

**Before committing documentation changes, verify:**

- [ ] Counted actual skills/agents/commands in directories
- [ ] Updated README.md with correct counts
- [ ] Updated docs/SYNC-STATUS.md with same counts
- [ ] Updated docs/UPDATES.md with same counts
- [ ] Updated INSTALL_TEMPLATE.md with same counts
- [ ] Updated .claude-plugin/marketplace.json metrics
- [ ] Updated templates/knowledge/best-practices/claude-code-2.0.md
- [ ] Searched for and removed broken skill references
- [ ] Ran `pytest tests/test_documentation_consistency.py -v`
- [ ] All tests passed

---

## Commands for Verification

### Count Everything

```bash
# Count skills
ls -d plugins/autonomous-dev/skills/*/ | wc -l

# Count agents
ls plugins/autonomous-dev/agents/*.md | wc -l

# Count commands
ls plugins/autonomous-dev/commands/*.md | wc -l
```

### Check README.md

```bash
# Find skill count mentions
grep -E "[0-9]+ Skills" plugins/autonomous-dev/README.md

# Find agent count mentions
grep -E "[0-9]+ (Specialized )?Agents" plugins/autonomous-dev/README.md

# Find command count mentions
grep -E "[0-9]+ (Slash )?Commands" plugins/autonomous-dev/README.md
```

### Check Cross-References

```bash
# Find all skill count mentions across docs
grep -r "skills" plugins/autonomous-dev/*.md plugins/autonomous-dev/docs/*.md | grep -E "[0-9]+"

# Check marketplace.json
cat .claude-plugin/marketplace.json | grep -A 5 '"metrics"'
```

### Run Automated Tests

```bash
# Run consistency tests
pytest tests/test_documentation_consistency.py -v

# Run only README checks
pytest tests/test_documentation_consistency.py::TestREADMEConsistency -v

# Run only cross-document checks
pytest tests/test_documentation_consistency.py::TestCrossDocumentConsistency -v

# Run only marketplace.json checks
pytest tests/test_documentation_consistency.py::TestMarketplaceConsistency -v
```

### Validate Before Commit

```bash
# Run pre-commit validation script
python plugins/autonomous-dev/hooks/validate_docs_consistency.py

# If validation passes (exit code 0), safe to commit
echo $?
```

---

## Files That Must Stay Synchronized

| File | Contains |
|------|----------|
| `README.md` | Primary counts (source of truth) |
| `docs/SYNC-STATUS.md` | Current sync status with counts |
| `docs/UPDATES.md` | Update log with counts |
| `INSTALL_TEMPLATE.md` | Installation docs with counts |
| `.claude-plugin/marketplace.json` | Metrics section |
| `templates/.../claude-code-2.0.md` | Best practices with counts |

---

## marketplace.json Metrics Template

```json
{
  "metrics": {
    "agents": 8,
    "skills": 12,
    "commands": 21,
    "hooks": 9
  }
}
```

**Keep this synchronized with actual counts.**
