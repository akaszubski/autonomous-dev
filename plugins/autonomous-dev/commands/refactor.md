---
name: refactor
description: "Unified code, docs, and test optimization -- shape analysis, waste detection, dead code, doc redundancy"
argument-hint: "[--tests] [--docs] [--code] [--fix] [--quick] [--deep] [--issues] [--batch]"
user-invocable: true
user_facing: true
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Refactor: Unified Code, Docs, and Test Optimization

Deep analysis and optimization of tests (Quality Diamond shape, waste detection), docs (redundancy), and code (dead code, unused libs). Supersedes `/sweep` with deeper analysis. Use `--quick` for the original sweep-style hygiene check.

## Implementation

ARGUMENTS: {{ARGUMENTS}}

### STEP 0: Parse Arguments

Parse the ARGUMENTS for optional flags:
- `--tests`: Run test optimization analysis only (shape + waste)
- `--docs`: Run narrative-doc drift sweep across whole repo. Identifies count drift (e.g., '216 libraries' vs actual 219 files) and enumeration drift via `covers:` frontmatter dereferencing. Idempotent. Default home for periodic-aggregation per PROJECT.md Layer 4.
- `--docs-redundancy`: Run doc redundancy analysis (semantic similarity between markdown files via SequenceMatcher). This was the prior `--docs` behavior, renamed to free `--docs` for drift detection.
- `--code`: Run code optimization analysis only (dead code + unused libs)
- `--fix`: Apply automated fixes after detection (requires findings)
- `--quick`: Run quick hygiene sweep (delegates to SweepAnalyzer, same as old `/sweep`)
- `--deep`: Enable GenAI semantic analysis (requires ANTHROPIC_API_KEY). Auto-enabled when ANTHROPIC_API_KEY is set, unless --quick.
- `--issues`: Pipe findings through /create-issue (HIGH/CRITICAL get individual issues, LOW/MEDIUM aggregated into one)
- `--batch`: Submit GenAI analysis via Anthropic Batch API (50% cost, async results)

If no mode flags provided (no --tests, --docs, --docs-redundancy, --code, --quick), run **all three deep modes** (tests + docs + code).

**Usage examples:**
```
/refactor --docs               # Drift sweep: count + enumeration drift via covers: frontmatter
/refactor --docs-redundancy    # Prior --docs behavior: SequenceMatcher redundancy analysis
/refactor --docs --issues      # Drift sweep + file GitHub issues for findings
/refactor --docs-redundancy --fix  # Redundancy analysis with auto-fix applied
```

If `--fix` is not provided, this is a dry-run (detect only, no changes).

**Note**: `--fix` is deprecated for creating issues. Use `--issues` instead to generate GitHub issues from findings.

### STEP 1: Run Analysis

Execute the appropriate analyzer to detect optimization opportunities. If `--deep` is set, or ANTHROPIC_API_KEY is set and `--quick` is NOT set, use GenAIRefactorAnalyzer. If `--deep` is set with no API key, display an error and EXIT. Otherwise fall back to RefactorAnalyzer.

```bash
python3 -c "
import sys, json, os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', os.path.expanduser('~/.claude/lib')):
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from pathlib import Path

# Determine whether to use GenAI
use_deep = '--deep' in sys.argv or (os.environ.get('ANTHROPIC_API_KEY') and '--quick' not in sys.argv)

if use_deep:
    from genai_refactor_analyzer import GenAIRefactorAnalyzer
    analyzer = GenAIRefactorAnalyzer(Path('.'), use_batch_api='--batch' in sys.argv)
else:
    from refactor_analyzer import RefactorAnalyzer
    analyzer = RefactorAnalyzer(Path('.'))

# Determine mode based on parsed flags
# For --quick: use quick_sweep() (RefactorAnalyzer only)
# For specific modes: use full_analysis(['tests']), etc.
# For no flags: use full_analysis() (all modes)

# Example for --quick:
# report = analyzer.quick_sweep()

# Example for specific mode:
# report = analyzer.full_analysis(['tests'])

# Example for all modes (with GenAI):
# report = analyzer.full_analysis(deep=True)

print(json.dumps(report.to_dict()))
"
```

Capture the JSON output and parse it.

### STEP 1.5: Findings Self-Critique (--deep mode only)

**Skip if `--quick` mode or if `--deep` was not active.** This step applies only when GenAIRefactorAnalyzer was used.

After obtaining the raw findings from STEP 1, perform one FEEDBACK pass before presenting results to the user. This implements the Self-Refine pattern (GENERATE → FEEDBACK → REFINE).

Audit the findings against these criteria:

1. **False positive audit**: For each DEAD_CODE or UNUSED_LIB finding, verify the symbol is not invoked dynamically (via `subprocess`, `importlib`, `sys.path`, or markdown references). Findings that cannot be confirmed MUST be downgraded to MEDIUM or removed.
2. **Severity calibration**: CRITICAL findings MUST describe a concrete negative outcome (data loss, security exposure, broken tests). Findings without a concrete outcome MUST be downgraded to HIGH or MEDIUM.
3. **Completeness**: If fewer than 3 categories were analyzed in a full-mode run, note the gap as a warning at the top of the findings output.

Revise the findings in memory before passing to STEP 2. Do NOT re-run the analyzer. This step is performed inline by the coordinator.

### STEP 2: Present Findings

Display the categorized report. Group findings by category, sort by severity within each group (CRITICAL first, LOW last). Show total counts per category.

**For --tests mode**, also display the test shape distribution table:

```
## Test Shape Distribution (Quality Diamond)

| Type          | Count | Actual% | Target% | Status |
|---------------|-------|---------|---------|--------|
| Unit          | 120   | 75.0%   | 60%     | Over   |
| Integration   | 20    | 12.5%   | 25%     | Under  |
| Property      | 0     | 0.0%    | 5%      | Under  |
| GenAI         | 20    | 12.5%   | 10%     | OK     |
```

Format findings:

```
## Refactor Results

### TEST_SHAPE (N issues)
- [HIGH] tests/: unit tests over-represented: 75% actual vs 60% target
  Suggestion: Reduce unit tests to align with Quality Diamond

### TEST_WASTE (N issues)
- [MEDIUM] tests/test_old.py:10: Trivial test: test_placeholder
  Suggestion: Add meaningful assertions or remove the test

### DOC_REDUNDANCY (N issues)
- [MEDIUM] docs/guide.md: High similarity (92%) between docs/guide.md and docs/tutorial.md
  Suggestion: Consider merging or deduplicating these documents

### DEAD_CODE (N issues)
- [MEDIUM] lib/old_util.py:42: Potentially dead function: legacy_helper
  Suggestion: Remove function 'legacy_helper' if no longer needed

### UNUSED_LIB (N issues)
- [LOW] lib/deprecated.py: Lib module 'deprecated' not imported outside tests
  Suggestion: Archive or remove 'deprecated.py' if no longer needed

Total: X findings across Y categories
```

Findings with `[genai]` prefix in their description were generated by GenAI semantic analysis (doc-code drift, hollow test detection, dead code verification). These are higher-confidence than structural-only findings.

If **zero findings**: Display "Clean refactor analysis -- no optimization opportunities found." and EXIT.

### STEP 3.5: Create GitHub Issues (only if --issues flag provided)

If `--issues` was passed, pipe findings into GitHub issues:

**HIGH/CRITICAL findings**: Create one GitHub issue per finding using `gh issue create`.
**LOW/MEDIUM findings**: Aggregate into a single "Refactor sweep findings" issue.

**Prior-call ordering contract (Issue #1203)**: the PreToolUse hook
evaluates each Bash invocation BEFORE it runs. **FORBIDDEN: Do NOT bundle
the context write and `gh issue create` into one Bash tool call** — the
hook would not see the context at evaluation time and would block
(see #1203). The context-file WRITE MUST be a separate Bash tool call
PRECEDING any `gh issue create`. The trailing cleanup `rm` MUST be
chained onto the FINAL `gh issue create` call via `;` (Issue #1204) —
standalone `rm` re-introduces a user-visible permission prompt.

Step 1: write the command context file (its OWN Bash tool call, BEFORE
any `gh issue create`):
```bash
# Create command context file to allow gh issue create through the hook (Issue #599)
python3 -c "
import json; from datetime import datetime, timezone
with open('/tmp/autonomous_dev_cmd_context.json', 'w') as f:
    json.dump({'command': 'refactor', 'timestamp': datetime.now(timezone.utc).isoformat()}, f)
"
```

Step 2: create the issues (separate Bash calls, AFTER step 1). Mid-loop
iterations do NOT chain the context-file cleanup; the FINAL `gh issue create`
call chains `; rm -f /tmp/autonomous_dev_cmd_context.json` so the cleanup
runs even if the final create fails AND no separate Bash approval is
required for `rm` (Issue #1204):
```bash
# Example for individual HIGH finding (NON-FINAL — no chained cleanup):
gh issue create --title "Refactor: [genai] Doc-code drift in docs/SECURITY.md" \
  --body "Found by /refactor --deep analysis...

**Plugin Version**: $(python3 -c "import sys,os;next((sys.path.insert(0,p) for p in ('.claude/lib','plugins/autonomous-dev/lib',os.path.expanduser('~/.claude/lib')) if os.path.isdir(p)),None);from version_reader import get_plugin_version;print(get_plugin_version())" 2>/dev/null || echo unknown)" --label "refactor"

# Example for FINAL create (aggregated LOW/MEDIUM — chains context cleanup):
gh issue create --title "Refactor sweep: N optimization opportunities" \
  --body "Aggregated findings from /refactor analysis...

**Plugin Version**: $(python3 -c "import sys,os;next((sys.path.insert(0,p) for p in ('.claude/lib','plugins/autonomous-dev/lib',os.path.expanduser('~/.claude/lib')) if os.path.isdir(p)),None);from version_reader import get_plugin_version;print(get_plugin_version())" 2>/dev/null || echo unknown)" --label "refactor"; rm -f /tmp/autonomous_dev_cmd_context.json
```

If `--issues` was NOT passed, skip this step.

### STEP 3: Apply Fixes (only if --fix flag provided)

If `--fix` was NOT passed, display: "Run with --fix to auto-fix safe categories (trivial tests, duplicate tests) and get a structured review list for everything else." and EXIT.

If `--fix` WAS passed, apply the **safe auto-fix policy** below. The guiding principle: only auto-fix findings where the action is unambiguous and the risk of semantic damage is near zero. Everything else is presented as information for the user to act on.

#### Safe to auto-fix (agent-assisted)

These categories have clear, mechanical fixes that cannot cause semantic damage:

**TEST_WASTE — trivial tests only**: Invoke the implementer agent (use Agent tool with subagent_type="implementer") to remove tests whose body is only `pass`, `assert True`, or `assert None`. These are definitionally useless. Do NOT auto-fix over-mocked tests or duplicate test bodies — those require human judgment about which copy to keep or how to restructure mocking.

**TEST_WASTE — duplicate test bodies**: Invoke the implementer agent to consolidate exact-duplicate test bodies into parameterized tests. Only act on duplicates detected by AST comparison (HIGH confidence). Present the before/after for user review.

#### Inform only — do NOT auto-fix

These categories require human judgment. Display them clearly but do not pass them to agents:

**TEST_SHAPE**: "47% integration vs 25% target" is diagnostic information, not a fix instruction. There is no safe automated action — deleting integration tests to hit a ratio is destructive, and adding empty unit tests is worse. Display the shape table and let the user decide what to write or reclassify.

**DOC_REDUNDANCY**: Documents may be intentionally similar (e.g., a template and its instantiation). Display the pairs and similarity scores. Let the user decide whether to merge, deduplicate, or leave them.

**DEAD_CODE** (MEDIUM confidence): Word-boundary regex is better than substring matching but still not AST-proven. Display findings for manual verification. Do NOT delete code automatically.

**UNUSED_LIB** (MEDIUM confidence): Many libs are invoked dynamically via subprocess or `sys.path.insert` in markdown files. Even with .md/.sh scanning, false positives are possible. Display findings for manual verification. Do NOT archive or delete automatically.

#### Output format for --fix

```
## Auto-Fixed (safe categories)

Removed N trivial tests:
- tests/test_old.py:10: test_placeholder (body was `pass`)
- tests/test_old.py:25: test_todo (body was `assert True`)

Consolidated M duplicate test bodies into parameterized tests.

## Requires Human Review

### Test Shape (informational)
[shape table — no automated action taken]

### Dead Code (MEDIUM confidence — verify before removing)
- lib/old_util.py:42: Potentially dead function: legacy_helper
- lib/checkpoint.py:413: Potentially dead class: WorkflowResumer

### Unused Libs (MEDIUM confidence — verify before removing)
- lib/deprecated.py: Not imported outside tests (may be used dynamically)

### Doc Redundancy (verify intent before merging)
- docs/guide.md ↔ docs/tutorial.md: 92% similarity
```

After auto-fixes are applied, run verification:

```bash
python3 -m pytest --tb=short -q 2>&1 | tail -20
```

Verify no regressions were introduced by the fixes.

### STEP 4: Verify

Re-run analysis for the same modes that were originally scanned. Display a before/after comparison:

```
## Before/After Comparison

| Category       | Before | After | Delta |
|----------------|--------|-------|-------|
| Test Shape     | 2      | 0     | -2    |
| Test Waste     | 5      | 1     | -4    |
| Doc Redundancy | 1      | 0     | -1    |
| Dead Code      | 3      | 0     | -3    |
| Unused Libs    | 2      | 1     | -1    |
| Total          | 13     | 2     | -11   |
```

If all findings resolved: "All optimization opportunities addressed."
If some remain: "N findings remain. Run /refactor again to review."
