# Test Project 2: Translation Service - Validation Guide

**Purpose**: Test Enhancement 1 - GenAI-Powered Semantic Validation

## What This Tests

✅ `semantic-validation` skill - outdated documentation detection
✅ `documentation-currency` skill - stale markers detection
✅ Enhanced `alignment-validator` agent - 5-phase validation
✅ Version mismatch detection
✅ "Coming soon" feature status validation

## Planted Issues

This project intentionally has these problems:

### 1. Outdated Issue Status (Semantic Validation)
- **PROJECT.md:28**: "Stream Handling (CRITICAL ISSUE)"
- **Reality**: SOLVED in src/index.ts:9 (comment says "Fixed in v2.0.0")
- **Expected**: Semantic validation detects this divergence

### 2. Version Mismatches (Semantic Validation)
- **package.json**: version "1.0.0"
- **CHANGELOG.md**: version "2.0.0" (latest entry)
- **README.md**: "Latest stable: v1.5.0"
- **PROJECT.md**: version "1.5.0"
- **Expected**: All 3 version inconsistencies detected

### 3. Stale "Coming Soon" Features (Documentation Currency)
- **PROJECT.md:60**: "Advanced caching (planned for Q4 2024)"
- **Reality**: Implemented in src/cache.ts
- **PROJECT.md:61**: "Multi-tenant support (planned for Q1 2025)"
- **Reality**: Implemented in src/tenant.ts
- **Expected**: Both detected as implemented but still marked "coming soon"

### 4. Stale "WIP" Marker (Documentation Currency)
- **PROJECT.md:40**: "Memory Leaks (WIP)"
- **Git blame**: Would show this is 60+ days old
- **Expected**: Detected as stale WIP (threshold: 60 days)

### 5. Outdated "Last Updated" Date (Documentation Currency)
- **PROJECT.md:3**: "Last Updated: 2024-09-01"
- **Git log**: Would show recent changes
- **Expected**: Detected as outdated date

### 6. Version Lag in Documentation (Documentation Currency)
- **PROJECT.md:72**: "Compatible with v1.2.0 and above"
- **Current version**: 2.0.0 (1 major version behind)
- **Expected**: Detected as version lag

## Running Validation

```bash
cd plugins/autonomous-dev/tests/synthetic-projects/test2-translation-service
/align-project
```

## Expected Output - Phase 2 (Semantic Validation)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 2: Semantic Validation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ DIVERGENT: Stream Handling Issue (PROJECT.md:28-38)
   Severity: HIGH
   Documented: "CRITICAL ISSUE - still investigating"
   Actual: SOLVED (comment in src/index.ts:9 says "Fixed in v2.0.0")

   Evidence:
   - src/index.ts:9 has solution comment
   - No TODO or FIXME in related code

   Fix: Update PROJECT.md section to:
   ```markdown
   ### 1. Stream Handling (SOLVED)
   Status: SOLVED (v2.0.0)
   Solution: Proper streaming with backpressure handling
   Implementation: src/index.ts:9-12
   ```

❌ VERSION MISMATCH (CRITICAL)
   package.json: 1.0.0
   CHANGELOG.md: 2.0.0 (most recent)
   README.md: 1.5.0
   PROJECT.md: 1.5.0

   Recommended: Update all to 2.0.0

   Fixes needed:
   1. package.json:3 → "version": "2.0.0"
   2. README.md:5 → "Latest stable: v2.0.0"
   3. PROJECT.md:3 → "Version": 2.0.0

Issues found: 2
  - 1 divergent section
  - 1 version mismatch (3 files affected)
```

## Expected Output - Phase 3 (Documentation Currency)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 3: Documentation Currency
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ STALE WIP: "Memory Leaks" (PROJECT.md:40)
   Age: 67 days (threshold: 60 days)
   Status: WIP marker older than limit

   Action needed: Either:
   1. Update status if resolved
   2. Update progress if still in progress
   3. Escalate to HIGH if blocked

⚠️ IMPLEMENTED: "Advanced caching (coming soon)"
   Location: PROJECT.md:60
   Age: 37 days
   Status: Implementation found in src/cache.ts

   Fix: Mark as complete
   ```markdown
   - ✅ Advanced caching (implemented in v2.0.0)
   ```

⚠️ IMPLEMENTED: "Multi-tenant support (coming soon)"
   Location: PROJECT.md:61
   Age: 37 days
   Status: Implementation found in src/tenant.ts

   Fix: Mark as complete
   ```markdown
   - ✅ Multi-tenant support (implemented in v2.0.0)
   ```

⚠️ OUTDATED VERSION REFERENCE
   Location: PROJECT.md:72
   Referenced: v1.2.0
   Current: v2.0.0
   Age: 1 major version behind

   Fix: Update to current version
   ```markdown
   Compatible with v2.0.0 and above
   ```

Issues found: 4
  - 1 stale WIP
  - 2 implemented "coming soon" features
  - 1 version lag reference
```

## Expected Summary

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ALIGNMENT SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Overall Alignment: 60% (needs improvement)

Phase 1 (Structural): 10/10 checks passed
Phase 2 (Semantic): 2/3 sections outdated
Phase 3 (Currency): 4 stale claims
Phase 4 (Cross-Refs): 0 broken references

Total Issues: 6
  - Critical: 1 (version mismatch)
  - High: 1 (outdated issue status)
  - Medium: 4 (stale markers)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Validation Checklist

**Phase 2 - Semantic Validation:**
- [ ] Detects outdated "CRITICAL ISSUE" for stream handling
- [ ] Provides evidence (file:line reference to solution)
- [ ] Detects version mismatch (3 files)
- [ ] Recommends correct version (2.0.0 from CHANGELOG)

**Phase 3 - Documentation Currency:**
- [ ] Detects stale "WIP" marker (>60 days)
- [ ] Finds implemented "coming soon" features (2 features)
- [ ] Detects version lag (v1.2.0 reference when current is v2.0.0)
- [ ] All 4 issues detected with correct severity

**Overall:**
- [ ] Alignment score: 50-70% (expected range for intentionally broken project)
- [ ] All 6 planted issues detected
- [ ] Auto-fix suggestions provided
- [ ] Evidence includes file:line references

## Success Criteria

✅ All 6 planted issues detected
✅ Correct severity assigned (CRITICAL for version mismatch)
✅ Evidence provided with file:line references
✅ Auto-fix suggestions are accurate
✅ Alignment score reflects actual state (50-70%)
✅ Interactive menu offers fix option

## Common Issues

**Issue**: Only 4-5 issues detected instead of 6
**Possible Cause**: Git history not available (need git init for age detection)
**Fix**: Run `git init && git add . && git commit -m "initial"` in test project

**Issue**: Version mismatch not detected
**Possible Cause**: Semantic validation skill needs access to all files
**Fix**: Verify skill is invoked correctly by alignment-validator agent

**Issue**: "Coming soon" features not detected as implemented
**Possible Cause**: Grep pattern doesn't find class definitions
**Fix**: Skill should search for "class CacheManager" and "class TenantManager"
