# Archived Validators - 2025-10-25

## Purpose

This directory contains old validator files that have been consolidated into the unified tool: `lib/genai_validate.py`

These files are kept for historical reference but should not be used. All functionality is now available through the single unified validator.

## Archived Files

### Regex-Based Validators (Replaced)

1. **version_sync.py** (479 lines)
   - Regex-based version consistency checking
   - Replaced by: `genai_validate.py version-sync`
   - Why removed: GenAI version is 99%+ accurate vs 80% for regex, and it's free on Max Plan

### GenAI Validators (Consolidated)

2. **validate_alignment_genai.py** (367 lines)
   - PROJECT.md alignment validation
   - Now: `genai_validate.py alignment`

3. **validate_docs_genai.py** (471 lines)
   - Documentation consistency validation
   - Now: `genai_validate.py docs`

4. **genai_quality_gates.py** (262 lines)
   - Code review, test quality, security, issues, commits
   - Now: `genai_validate.py code-review|test-quality|security|classify-issue|commit-msg`

5. **version_sync_genai.py** (439 lines)
   - GenAI version consistency validation
   - Now: `genai_validate.py version-sync`

## Consolidation Results

**Before**: 5 separate validator files (2,018 lines total)
**After**: 1 unified validator (genai_validate.py, ~800 lines)
**Reduction**: 60% code reduction (1,218 lines saved)

## Benefits of Consolidation

1. **Single Tool**: One entry point for all validation
2. **Shared Infrastructure**: LLM client code shared (not duplicated)
3. **Easier Maintenance**: Update one file instead of 5
4. **Better UX**: Consistent CLI across all validators
5. **Simpler Dependencies**: One import instead of multiple

## Migration

All functionality preserved. Update your scripts:

```bash
# Old (multiple files)
python lib/validate_alignment_genai.py --feature "Add OAuth"
python lib/validate_docs_genai.py --full
python lib/genai_quality_gates.py review
python lib/version_sync_genai.py --check

# New (unified tool)
python lib/genai_validate.py alignment --feature "Add OAuth"
python lib/genai_validate.py docs --full
python lib/genai_validate.py code-review --diff
python lib/genai_validate.py version-sync --check
```

## Documentation

For complete usage documentation, see:
- **Main Guide**: `docs/GENAI-VALIDATION-GUIDE.md`
- **Unified Tool**: `lib/genai_validate.py --help`

## Archived Date

2025-10-25
