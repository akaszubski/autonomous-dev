## Summary

The doc-master agent should automatically validate and fix alignment between README.md, PROJECT.md, CLAUDE.md whenever changes are made.

## Problem

Documentation drift occurs silently - Issue #121 simplified commands from 20 to 9 but docs weren't updated.

## Current Drift

- README.md: says 20 commands (should be 9)
- PROJECT.md: says 20 commands (should be 9)
- CLAUDE.md: mixed (9 at top, 20 later)

## Proposed Solution

1. Add alignment check to doc-master agent prompt
2. Auto-extract metrics from codebase (command count, agent count, skill count)
3. Auto-fix misalignments in all 3 files
4. Optional: Pre-commit hook to prevent future drift

## Acceptance Criteria

- Doc-master checks alignment during every /auto-implement
- Misaligned counts auto-fixed
- Pre-commit hook validates alignment

## Related: #121, #123
