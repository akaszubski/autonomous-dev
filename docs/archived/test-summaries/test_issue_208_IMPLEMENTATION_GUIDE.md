# Implementation Guide: Issue #208 - Architecture Documentation Consolidation

**Test File**: `test_issue_208_architecture_doc_consolidation.py`
**Total Tests**: 21 (10 failing, 11 passing)
**Implementation Time**: ~15 minutes

---

## Files to Update

### Files with ARCHITECTURE.md References (15+ files)

Based on grep analysis, the following files reference `ARCHITECTURE.md`:

1. **plugins/autonomous-dev/CHANGELOG.md** (6 references)
   - Historical references in changelog
   - Action: Update to ARCHITECTURE-OVERVIEW.md

2. **plugins/autonomous-dev/tests/README.md** (3 references)
   - Documentation references
   - Action: Update to ARCHITECTURE-OVERVIEW.md

3. **plugins/autonomous-dev/lib/README.md** (1 reference)
   - Architecture link
   - Action: Update to ARCHITECTURE-OVERVIEW.md

4. **plugins/autonomous-dev/skills/semantic-validation/docs/detailed-guide-2.md** (2 references)
   - Example references
   - Action: Update to ARCHITECTURE-OVERVIEW.md

5. **plugins/autonomous-dev/skills/cross-reference-validation/docs/detailed-guide-1.md** (3 references)
   - Cross-reference examples
   - Action: Update to ARCHITECTURE-OVERVIEW.md

6. **docs/ARCHITECTURE.md** (1 reference to ARCHITECTURE-EXPLAINED.md)
   - Broken link reference
   - Action: Will be archived with this reference removed

7. **CLAUDE.md** (likely has references)
   - Action: Update to ARCHITECTURE-OVERVIEW.md

8. **CONTRIBUTING.md** (likely has references)
   - Action: Update to ARCHITECTURE-OVERVIEW.md

9. **docs/AGENTS.md** (likely has references)
   - Action: Update to ARCHITECTURE-OVERVIEW.md

### Files with ARCHITECTURE-EXPLAINED.md References (5 files)

**Broken links** - file never existed:

1. **docs/ARCHITECTURE.md** (1 reference)
   - In "See also" section
   - Action: Remove reference (will be archived)

2. **docs/MAINTAINING-PHILOSOPHY.md** (4 references)
   - Multiple broken references
   - Action: Remove all references

---

## Step-by-Step Implementation

### Step 1: Create Archive Directory

```bash
mkdir -p docs/archived
```

**Validates**: `test_archived_directory_exists`

### Step 2: Archive ARCHITECTURE.md with Deprecation Notice

```bash
# First, prepend deprecation notice
cat > /tmp/deprecation_notice.md << 'EOF'
# Architecture Overview (DEPRECATED)

**DEPRECATED**: This file has been superseded by [ARCHITECTURE-OVERVIEW.md](../ARCHITECTURE-OVERVIEW.md).

**Please use**: [docs/ARCHITECTURE-OVERVIEW.md](../ARCHITECTURE-OVERVIEW.md) for current architecture documentation.

**Archived**: 2026-01-09 (Issue #208 - Documentation consolidation)

---

EOF

# Move original content to archived with deprecation
cat /tmp/deprecation_notice.md docs/ARCHITECTURE.md > docs/archived/ARCHITECTURE.md
rm docs/ARCHITECTURE.md
```

**Validates**:
- `test_archived_architecture_md_exists`
- `test_archived_architecture_has_deprecation_notice`
- `test_original_architecture_md_removed_from_docs`

### Step 3: Update ARCHITECTURE.md References

Use search and replace across all files:

```bash
# Find all references (excluding test files and archived/)
grep -r "ARCHITECTURE\.md" . \
  --include="*.md" \
  --exclude-dir=".git" \
  --exclude-dir="archived" \
  --exclude="test_issue_208*" \
  | grep -v "ARCHITECTURE-OVERVIEW.md"
```

**Manual Updates** (use editor or sed):

```bash
# Example: Update CLAUDE.md
sed -i.bak 's/ARCHITECTURE\.md/ARCHITECTURE-OVERVIEW.md/g' CLAUDE.md

# Example: Update CONTRIBUTING.md
sed -i.bak 's/docs\/ARCHITECTURE\.md/docs\/ARCHITECTURE-OVERVIEW.md/g' CONTRIBUTING.md

# Example: Update docs/AGENTS.md
sed -i.bak 's/ARCHITECTURE\.md/ARCHITECTURE-OVERVIEW.md/g' docs/AGENTS.md
```

**Key Files to Update**:
1. CLAUDE.md
2. CONTRIBUTING.md
3. docs/AGENTS.md
4. plugins/autonomous-dev/CHANGELOG.md
5. plugins/autonomous-dev/tests/README.md
6. plugins/autonomous-dev/lib/README.md
7. plugins/autonomous-dev/skills/semantic-validation/docs/detailed-guide-2.md
8. plugins/autonomous-dev/skills/cross-reference-validation/docs/detailed-guide-1.md

**Validates**:
- `test_no_references_to_architecture_md_except_archived`
- `test_key_files_reference_architecture_overview`

### Step 4: Remove ARCHITECTURE-EXPLAINED.md References

Remove all references to `ARCHITECTURE-EXPLAINED.md` (broken link):

```bash
# Find all references
grep -r "ARCHITECTURE-EXPLAINED\.md" . \
  --include="*.md" \
  --exclude-dir=".git" \
  --exclude="test_issue_208*"
```

**Files to Update**:
1. **docs/MAINTAINING-PHILOSOPHY.md** - Remove 4 references
2. **docs/ARCHITECTURE.md** (archived) - Already moved, reference will be in archived version

**Manual Edits**:
- Open each file
- Remove or replace references to `ARCHITECTURE-EXPLAINED.md`
- If removing a broken link, replace with `ARCHITECTURE-OVERVIEW.md` if appropriate

**Validates**: `test_no_references_to_architecture_explained_md`

### Step 5: Verify Implementation

Run tests to verify all changes:

```bash
# Run full test suite
pytest tests/regression/progression/test_issue_208_architecture_doc_consolidation.py --tb=line -q

# Expected: 21 passed in ~1.5s
```

**Validates**:
- All 21 tests should PASS
- `test_only_one_architecture_file_in_docs_root`
- `test_archived_directory_is_not_empty`
- `test_archived_architecture_preserves_original_content`

---

## Verification Checklist

After implementation, verify:

- [ ] `docs/archived/` directory exists
- [ ] `docs/archived/ARCHITECTURE.md` exists with deprecation notice
- [ ] `docs/ARCHITECTURE.md` does NOT exist (moved to archived/)
- [ ] `docs/ARCHITECTURE-OVERVIEW.md` exists and has all critical sections
- [ ] No files reference `ARCHITECTURE.md` except `docs/archived/ARCHITECTURE.md`
- [ ] No files reference `ARCHITECTURE-EXPLAINED.md` (broken link removed)
- [ ] Key files (CLAUDE.md, CONTRIBUTING.md, docs/AGENTS.md) reference ARCHITECTURE-OVERVIEW.md
- [ ] All 21 tests pass

---

## Test Execution

### Before Implementation (RED Phase)

```bash
pytest tests/regression/progression/test_issue_208_architecture_doc_consolidation.py --tb=line -q

# Expected output:
# 10 failed, 11 passed in ~1.5s
```

### After Implementation (GREEN Phase)

```bash
pytest tests/regression/progression/test_issue_208_architecture_doc_consolidation.py --tb=line -q

# Expected output:
# 21 passed in ~1.5s
```

---

## Common Issues

### Issue 1: Binary Files in Search

**Symptom**: `grep` or search returns binary file matches

**Solution**: Exclude binary directories:
```bash
grep -r "ARCHITECTURE.md" . \
  --exclude-dir=".git" \
  --exclude-dir="__pycache__" \
  --exclude-dir="node_modules" \
  --include="*.md"
```

### Issue 2: Deprecation Notice Not Found

**Symptom**: `test_archived_architecture_has_deprecation_notice` fails

**Solution**: Ensure deprecation notice includes keywords:
- "deprecated" OR "archived" OR "superseded" OR "replaced"
- Reference to "ARCHITECTURE-OVERVIEW.md"

### Issue 3: References Still Found

**Symptom**: `test_no_references_to_architecture_md_except_archived` fails

**Solution**: Check for variations:
- `ARCHITECTURE.md`
- `docs/ARCHITECTURE.md`
- `[ARCHITECTURE.md](...)`
- Update all variations to `ARCHITECTURE-OVERVIEW.md`

---

## Expected Outcomes

1. **Single Source of Truth**: Only `ARCHITECTURE-OVERVIEW.md` exists in `docs/` root
2. **No Broken Links**: All references point to existing files
3. **Preserved History**: Original `ARCHITECTURE.md` archived with deprecation notice
4. **Clean Documentation**: No references to non-existent `ARCHITECTURE-EXPLAINED.md`
5. **Test Coverage**: All 21 tests passing (100% success rate)

---

## Timeline

| Step | Time | Cumulative |
|------|------|------------|
| Create archive directory | 1 min | 1 min |
| Archive ARCHITECTURE.md | 2 min | 3 min |
| Update references (8+ files) | 8 min | 11 min |
| Remove broken links (5 files) | 3 min | 14 min |
| Verify tests | 1 min | 15 min |

**Total Estimated Time**: 15 minutes

---

## Post-Implementation

After all tests pass:

1. Commit changes:
   ```bash
   git add docs/archived/ARCHITECTURE.md
   git add -u  # Stage all updates
   git commit -m "docs: Consolidate ARCHITECTURE.md into ARCHITECTURE-OVERVIEW.md (Issue #208)"
   ```

2. Verify no regressions:
   ```bash
   pytest tests/regression/ -m regression --tb=line -q
   ```

3. Update PROJECT.md if needed (documentation cleanup complete)

---

## Notes

- **No Content Migration Needed**: `ARCHITECTURE-OVERVIEW.md` already has all critical content
- **Reference Updates Only**: This is primarily a documentation hygiene task
- **Broken Link Cleanup**: Discovered `ARCHITECTURE-EXPLAINED.md` never existed (5 broken refs)
- **Test-Driven**: 21 comprehensive tests ensure nothing breaks
