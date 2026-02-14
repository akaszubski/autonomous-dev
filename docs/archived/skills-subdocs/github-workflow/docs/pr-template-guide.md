# Pull Request Description Guide

Best practices for writing effective PR descriptions that accelerate code review and improve collaboration.

## Overview

A well-written PR description helps reviewers understand:
- **What** changed (the implementation)
- **Why** it changed (the motivation)
- **How** to test it (the validation)
- **What** impact it has (the scope)

## Standard PR Structure

### Minimum Required Sections

Every PR should include these sections:

```markdown
## Summary
Brief overview of changes (1-3 sentences)

## Changes
- Bullet list of specific changes
- Each item should be concise
- Focus on user-facing or behavior changes

## Test Plan
How to verify this works correctly

## Breaking Changes
Any changes that break backwards compatibility
```

### Expanded Template (Recommended)

For more complex PRs:

```markdown
## Summary
[1-3 sentence overview]

## Motivation
Why this change is needed

## Changes
- Change 1
- Change 2
- Change 3

## Test Plan
[How to test these changes]

## Breaking Changes
[Any breaking changes, or "None"]

## Screenshots / Videos
[Visual proof for UI changes]

## Checklist
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] CI/CD passes
```

## Writing an Effective Summary

### Purpose
The summary is the first thing reviewers read. Make it count.

### Best Practices

✅ **Do's:**
- Write 1-3 sentences maximum
- Lead with the primary change
- Use active voice
- Be specific about impact

❌ **Don'ts:**
- Write paragraphs of background
- Use vague terms like "updates", "improvements"
- Repeat the PR title verbatim
- Include implementation details (save for Changes section)

### Examples

**Bad Summary:**
```markdown
## Summary
This PR makes some changes to the authentication system.
```

**Good Summary:**
```markdown
## Summary
Migrates authentication from session-based to JWT tokens, enabling stateless API architecture and improved scalability.
```

**Bad Summary:**
```markdown
## Summary
I added some features and fixed a few bugs that were causing issues.
```

**Good Summary:**
```markdown
## Summary
Adds PDF export for reports and resolves memory leak in data processing pipeline.
```

## Documenting Changes

### Structure

Use bullet points for scannability:

```markdown
## Changes

### Added
- JWT authentication with refresh token support
- Rate limiting middleware (100 requests/minute)
- API documentation with OpenAPI/Swagger

### Changed
- Database queries now use connection pooling
- Error messages include request IDs for debugging
- Configuration moved from environment variables to config file

### Fixed
- Memory leak in data processing worker
- Race condition in concurrent uploads
- Incorrect timezone handling in timestamps

### Removed
- Deprecated v1 API endpoints
- Legacy session management code
```

### Focus on "What", Not "How"

✅ **Good (user/behavior-focused):**
```markdown
- Add support for PDF export with custom page sizes
- Fix incorrect calculation of shipping costs
- Update error messages to include recovery suggestions
```

❌ **Bad (implementation-focused):**
```markdown
- Added PdfExporter class with generate() method
- Changed shipping_cost variable from int to Decimal
- Refactored error handling to use new ErrorMessage class
```

### Group Related Changes

```markdown
## Changes

### Authentication Improvements
- Add JWT token support
- Implement token refresh endpoint
- Add middleware for token validation

### Performance Optimizations
- Enable database connection pooling
- Add Redis caching for frequently accessed data
- Optimize N+1 queries in user list endpoint
```

## Writing a Test Plan

### Purpose
The test plan tells reviewers (and future you) how to verify the changes work correctly.

### Components

1. **Setup instructions** (if needed)
2. **Steps to test manually**
3. **Expected results**
4. **Automated test coverage**

### Template

```markdown
## Test Plan

### Manual Testing
1. Log in as a standard user
2. Navigate to /reports
3. Click "Export PDF" button
4. Verify PDF downloads with correct formatting

### Automated Tests
- Unit tests: `test_pdf_export.py::TestPDFExport`
- Integration tests: `test_report_api.py::TestReportExport`
- Coverage: 94% of new code

### Edge Cases Tested
- Large reports (>1000 rows)
- Special characters in report data
- Concurrent export requests
```

### Examples

**Bad Test Plan:**
```markdown
## Test Plan
I tested it and it works.
```

**Good Test Plan:**
```markdown
## Test Plan

### Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Set `JWT_SECRET` environment variable
3. Start Redis server

### Manual Testing
1. Obtain JWT token: `curl -X POST /auth/login -d '{"username":"test","password":"test"}'`
2. Make authenticated request: `curl -H "Authorization: Bearer <token>" /api/users`
3. Verify response includes user list (200 OK)
4. Verify invalid token returns 401 Unauthorized

### Automated Tests
- `pytest tests/test_jwt_auth.py` (12 tests, all passing)
- Coverage: 96% of auth module
```

## Documenting Breaking Changes

### Why This Matters
Breaking changes require special attention because they force users to update their code.

### Structure

```markdown
## Breaking Changes

### Change 1: API Response Format
**Before:**
```json
{
  "user_id": 1,
  "user_name": "John"
}
```

**After:**
```json
{
  "data": {
    "type": "user",
    "id": "1",
    "attributes": {
      "name": "John"
    }
  }
}
```

**Migration:** Update client code to parse nested `data.attributes` structure.

### Change 2: Removed Deprecated Endpoint
**Removed:** `/api/v1/users` endpoint
**Migration:** Use `/api/v2/users` instead
**Documentation:** https://docs.example.com/migration-guide
```

### Template

For each breaking change, document:
1. What changed
2. Before/after comparison
3. Migration instructions
4. Links to documentation

## Best Practices

### Keep It Concise

**Goal:** Reviewers should understand the PR in 2-3 minutes of reading.

- Use bullet points, not paragraphs
- Lead with most important information
- Link to external docs for background
- Use screenshots/videos for UI changes

### Explain the "Why"

**Bad:**
```markdown
## Summary
Refactored the authentication code.
```

**Good:**
```markdown
## Summary
Refactored authentication to use JWT tokens instead of sessions, enabling
horizontal scaling and stateless API architecture.

## Motivation
Current session-based auth requires sticky sessions in load balancer,
limiting our ability to scale horizontally. JWT tokens eliminate this
constraint and improve API performance.
```

### Use Visuals for UI Changes

For any UI/UX change:
- Include before/after screenshots
- Use videos for interactions (clicks, hover states, animations)
- Annotate images to highlight specific changes

```markdown
## Screenshots

### Before
![Old UI](./screenshots/before.png)

### After
![New UI](./screenshots/after.png)

**Key changes:**
- Improved button placement (top-right corner)
- Added loading spinner during form submission
- Better error message visibility
```

### Link Related Context

```markdown
## Related
- Closes #123
- Relates to #124, #125
- Follow-up to PR #100
- Blocks #126
- Design doc: [Design Doc Title](link)
- RFC: [RFC Title](link)
```

### Include a Checklist

Helps you remember important steps:

```markdown
## Checklist
- [x] Tests added for new functionality
- [x] Tests pass locally (`pytest tests/`)
- [x] Documentation updated (README, API docs)
- [x] CHANGELOG.md updated
- [x] No new warnings or errors
- [x] Breaking changes documented
- [ ] Product team notified (for user-facing changes)
```

## PR Size Guidelines

### Optimal Size
- **Target:** < 300 lines changed
- **Acceptable:** 300-500 lines
- **Too large:** > 500 lines

### Why Size Matters
- **Small PRs:** Faster reviews, fewer bugs, easier to revert
- **Large PRs:** Review fatigue, higher bug risk, harder to understand

### When to Split a PR

If your PR is >500 lines, consider splitting into:
1. **Refactoring PR** (prepare codebase)
2. **Feature PR** (add new functionality)
3. **Tests PR** (comprehensive testing)
4. **Docs PR** (documentation updates)

**Example:**

Instead of one 1200-line PR:
```markdown
PR #1: refactor: extract authentication logic to separate module (200 lines)
PR #2: feat: add JWT token support (300 lines)
PR #3: test: add comprehensive auth tests (250 lines)
PR #4: docs: update authentication guide (150 lines)
```

## Examples

### Example 1: Feature Addition

```markdown
## Summary
Add PDF export functionality for reports, enabling users to download formatted reports for offline viewing.

## Motivation
Users frequently request the ability to save reports for offline review and sharing with stakeholders who don't have system access.

## Changes
- Add PDF export button to report view page
- Implement PDF generation using ReportLab library
- Add configuration options for page size and orientation
- Include company branding (logo, footer) in exported PDFs

## Test Plan
### Manual Testing
1. Navigate to any report (e.g., /reports/monthly-sales)
2. Click "Export PDF" button in top-right corner
3. Verify PDF downloads with:
   - Correct report data
   - Company logo in header
   - Page numbers in footer
   - Proper table formatting

### Automated Tests
- Unit tests: `tests/test_pdf_export.py` (8 tests)
- Integration tests: `tests/integration/test_report_export.py` (3 tests)
- Coverage: 92% of new PDF export code

### Edge Cases
- Tested with reports containing 1000+ rows (pagination works)
- Tested with special characters (unicode, emojis)
- Tested concurrent exports (no race conditions)

## Breaking Changes
None

## Screenshots
![Export Button](./screenshots/export-button.png)
![Sample PDF Output](./screenshots/sample-pdf.png)

## Checklist
- [x] Tests added and passing
- [x] Documentation updated (docs/features/pdf-export.md)
- [x] CHANGELOG.md updated
- [x] No performance degradation
- [x] Works on Chrome, Firefox, Safari

Closes #234
```

### Example 2: Bug Fix

```markdown
## Summary
Fix memory leak in data processing worker that caused OOM errors after processing ~1000 files.

## Root Cause
Worker held references to processed files in a results cache that was never cleared, causing memory usage to grow unbounded.

## Changes
- Add automatic cache eviction after 100 entries
- Implement LRU eviction policy for cache
- Add memory usage monitoring to worker logs
- Reduce file handle retention time

## Test Plan
### Reproduction
Before fix, process 1000 files:
```bash
python scripts/process_batch.py --files 1000
# Memory usage climbs to 8GB+, then OOM crash
```

After fix, process 1000 files:
```bash
python scripts/process_batch.py --files 1000
# Memory usage stable at ~500MB
```

### Automated Tests
- Added `tests/test_worker_memory.py::test_no_memory_leak`
- Processes 1000 files and verifies memory usage < 1GB
- CI runs this test to prevent regression

## Breaking Changes
None

## Performance Impact
- Memory usage reduced by 93% (8GB → 500MB)
- No impact on processing speed
- Slight increase in cache misses (acceptable tradeoff)

Fixes #567, #568, #569
```

### Example 3: Refactoring

```markdown
## Summary
Extract validation logic into reusable validation module, improving code organization and reducing duplication.

## Motivation
Validation code was duplicated across 12 different files, making bug fixes require changes in multiple places. Centralize validation logic for maintainability.

## Changes
- Create `src/validation` module with common validators
- Extract email validation to `validators.validate_email()`
- Extract phone validation to `validators.validate_phone()`
- Extract date validation to `validators.validate_date()`
- Update 12 files to use new validation module
- Add comprehensive unit tests for validators

## Test Plan
### Regression Testing
- All existing tests pass (195 tests, 0 failures)
- No behavior changes - pure refactoring
- Validation logic identical to previous implementation

### New Tests
- `tests/test_validators.py` (32 tests)
- Coverage: 100% of validation module

## Breaking Changes
None - internal refactoring only, no API changes

## Benefits
- Reduced code duplication: ~400 lines → 150 lines
- Easier to maintain: One place to fix validation bugs
- Better test coverage: 32 tests vs previous 8 tests
- Improved reusability: Other modules can import validators

Closes #123
```

## Common Mistakes to Avoid

### 1. Vague Descriptions
❌ **Bad:** "Updated some things"
✅ **Good:** "Add JWT authentication and rate limiting"

### 2. Missing Test Plan
❌ **Bad:** "Tested it, works fine"
✅ **Good:** Detailed manual + automated test steps

### 3. No Context
❌ **Bad:** Only list of changes, no explanation
✅ **Good:** Explain why changes are needed

### 4. Burying the Lede
❌ **Bad:** Long background story before getting to changes
✅ **Good:** Lead with summary, provide background later

### 5. Implementation Details
❌ **Bad:** "Changed variable x to y, refactored function z"
✅ **Good:** "Improved error messages to include recovery suggestions"

## Summary

Great PR descriptions:
- **Are concise** - Reviewers understand in 2-3 minutes
- **Explain why** - Motivation is clear
- **Include test plan** - Easy to verify changes
- **Document breaking changes** - Migration path is clear
- **Use visuals** - Screenshots/videos for UI changes
- **Are scannable** - Bullet points, not paragraphs

**Remember:** Time spent writing a clear PR description is time saved in code review. Make it easy for reviewers to understand and approve your changes.
