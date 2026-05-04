# PLAN_1023 — Non-SWE Intent Classes (Revised pass 2)

**Issue**: #1023
**Status**: Proposed (revised after plan-critic pass 1)
**Date**: 2026-05-04
**Estimated effort**: ~0.5 day implementer + tests

## Revisions from pass 1

- **DROPPED** SCHEMA_VERSION bump (SC-1). Value-domain expansion of intent_class string is forward-safe via existing fail-safe enforcement (unknown strings → enforce). The bump added 2 tests + reader gate for no concrete failure mode.
- **ADDED** explicit edits for stale `_label_to_intent` map and "9 classes" comments inside `intent_classifier.py`.
- **ADDED** HOOK-REGISTRY.md and HOOKS.md to doc-update list.
- **REDUCED** fixture count from 8/class → 4/class to match existing convention.
- **EXPANDED** risk register with token cost, EXPLORATION skip-IMPLEMENT angle, real-LLM untested.

## Problem

The 9-class intent classifier forces enforcement on every prompt that isn't DOC/CONFIG/TYPO/STATUS_QUERY/CONVERSATION. Real non-SWE work (multi-file exploration, GitHub triage, remote SSH ops, scratch experimentation) is mis-classified as IMPLEMENT/REFACTOR/AMBIGUOUS and gets gated. We add 4 new skip-eligible classes while preserving the regex-first security gate, fail-open semantics, and `<user_input>` wrapper.

## Architectural Decisions

| Question | Decision | Rationale |
|---|---|---|
| EXPLORATION vs STATUS_QUERY | EXPLORATION = multi-file (3+ files); STATUS_QUERY = single-turn read. Rule restated in LLM prompt. | Anchors on existing `predicted_file_count` — no new field. Both classes are skip-eligible so misclassification between them is benign. |
| SCRATCH security caveat | This issue: SCRATCH joins `_SKIP_INTENT_CLASSES` (skips all gates). Per-tool Write/Edit exception deferred to follow-up issue, documented as known-limitation. | Out of scope; avoid per-tool refactor. Regex-first still applies. |
| Per-class confidence threshold | Single threshold (0.85) retained; deferred to follow-up. | Not blocking. |
| SCHEMA_VERSION bump | **NOT BUMPED**. The intent_class field is a string; new values are forward-safe via `should_pipeline_enforce` default-True for unknown strings. v1 readers reading new artifacts treat unknown classes as fail-safe enforce — same behavior as a schema mismatch but without the ceremony. | Critic SC-1: bump was speculation. |

## Files to Modify

### 1. `plugins/autonomous-dev/lib/intent_classifier.py` (MODIFY)
- **Lines 120–150** `IntentClass` enum: add 4 members `EXPLORATION = "exploration"`, `TRIAGE = "triage"`, `REMOTE_OPS = "remote_ops"`, `SCRATCH = "scratch"`. Update class docstring "9 task classes" → "13 task classes".
- **Line 153** comment "The 9 'real' intent classes the LLM is allowed to return" → "The 13 'real' intent classes the LLM is allowed to return".
- **Lines 155–165** `_VALID_LLM_INTENTS`: append the 4 new `.value` strings (now 13 entries).
- **Lines 214–243** `_LLM_PROMPT_TEMPLATE`: change "9 fixed intent categories" → "13 fixed intent categories"; update JSON schema comment "one of the 13 strings"; insert 4 bullets after the `conversation:` line:
  - `exploration`: Multi-file read-only investigation across 3+ files (e.g. "look at X across the codebase", "trace how Y works"). Distinct from status_query (single factual read).
  - `triage`: GitHub issue review / prioritization (gh issue list, gh issue view) — no code changes.
  - `remote_ops`: SSH-based work on a remote host (training runs, data pipelines, ssh/scp/rsync to remote IPs).
  - `scratch`: Throwaway work in /tmp/, scripts/scratch/, or .worktrees/scratch-* directories (not the canonical working tree).
- Append a Rule 5: "If the prompt indicates multi-file read-only investigation (look/trace/audit/investigate verbs across 4+ files, NO Write/Edit verbs), prefer exploration over status_query." (Verb-anchored to disambiguate from Rule 3's 2-3 file IMPLEMENT range; threshold raised to 4+ for clean separation.)
- **Lines 367, 373** `_coerce_to_intent` docstring: update "9 valid LLM intent strings" → "13 valid LLM intent strings".
- **Module docstring (lines 1–33)** update "9 classes" references → "13 classes". Keep regex-first/fail-open contract language unchanged. **DO NOT** modify line 32 (`Telemetry... with 9 fields`) — that's telemetry field count, not class count. No blanket find-replace of `9`.
- `_validate_template_integrity` is unaffected — still checks `<user_input>` tag.

### 2. `plugins/autonomous-dev/lib/session_mode.py` (MODIFY — minimal)
- **Lines 270–272** `_SKIP_INTENT_CLASSES`: add `"exploration"`, `"triage"`, `"remote_ops"`, `"scratch"` to the frozenset (now 9 entries).
- **Lines 330–364** `should_pipeline_enforce()` decision table docstring: append 4 rows (`exploration | False`, `triage | False`, `remote_ops | False`, `scratch | False`). Logic unchanged (frozenset lookup).
- **NO** SCHEMA_VERSION change. **NO** `read_session_mode` schema gate change. **NO** module docstring rewrite.

### 3. `plugins/autonomous-dev/config/intent_classifier_config.json` (NO CHANGE)
Confirmed via prior research — does not enumerate intent class names.

### 4. `plugins/autonomous-dev/lib/enforcement_decision.py` (NO CHANGE)
The 8-rule chain consults `should_pipeline_enforce()`; new classes flow through automatically.

### 5. Hook consumers (NO CHANGE)
`unified_prompt_validator.py:276`, `plan_gate.py:185`, `plan_mode_exit_detector.py:134`, `unified_pre_tool.py:4040` all read `intent_class` as a string and route through `should_pipeline_enforce`. Verified by inspection.

## Test Strategy

### 6. `tests/fixtures/intent_classifier_fixtures.json` (MODIFY)
- Update `_comment` to enumerate 13 classes.
- Update `_schema.label` enum string to include the 4 new classes.
- Add **4 fixtures per new class** (16 total): IDs `expl-001..004`, `triag-001..004`, `remote-001..004`, `scrat-001..004`. Mark fixtures `*-004` as `holdout: true` (4 holdouts added). Matches existing-class convention (4 fixtures per skip-eligible class).
- **Adversarial fixtures REQUIRED** (NOT counted in the 4-per-class quota; can be added as e.g. `expl-sec-001`):
  - `expl-sec-001`: Prompt contains a security keyword (e.g. "audit auth flow across handlers, no changes") — must classify as `security_critical` (regex hits before LLM).
  - `scrat-sec-001`: Prompt mentions `/tmp/auth_test.py` — must classify as `security_critical`.
  - `remote-sec-001`: Prompt is `ssh user@host rotate-jwt` — must classify as `security_critical`.
  - `expl-injection-001`: Prompt contains literal `<user_input>` text — wrapper still functions, regex-or-LLM still classifies correctly (NOT as a parse error).

### 7. `tests/unit/lib/test_intent_classifier.py` (MODIFY)
- **Lines 502-513** `_label_to_intent`: add 4 entries (`"exploration": IntentClass.EXPLORATION`, `"triage": IntentClass.TRIAGE`, `"remote_ops": IntentClass.REMOTE_OPS`, `"scratch": IntentClass.SCRATCH`). **REQUIRED** — accuracy test calls this on every fixture; missing keys cause KeyError.
- Add `test_intent_class_enum_has_14_members` regression lock (13 real + AMBIGUOUS).
- Add `test_valid_llm_intents_includes_new_classes` — asserts `_VALID_LLM_INTENTS` contains the 4 new values.
- Add `test_prompt_template_lists_13_categories` — asserts template contains "13 fixed intent categories" and the 4 new bullet labels.
- Add `test_template_integrity_still_passes` — calls `_validate_template_integrity(_LLM_PROMPT_TEMPLATE)` and asserts no raise (regression lock for #960).
- Existing parametrized fixture-driven test auto-covers new fixtures via `_build_label_aware_analyzer` (lines 526–529 use `prompt_to_label` dict — picks up new fixtures automatically).

### 8. `tests/unit/lib/test_session_mode.py` (MODIFY — minimal)
- Add `test_skip_intent_classes_includes_new_classes` — frozenset contains 9 entries including the 4 new ones.
- **NO** schema-version test changes (SCHEMA_VERSION unchanged).
- **NO** edits to `test_schema_version_is_1` (line 178) or line 332 hard-pin (still valid).

### 9. `tests/unit/lib/test_enforcement_decision.py` (MODIFY)
- Add 4 parametrized cases: each new class with `requires_security_audit=False`, `fail_open=False` ⇒ `(True, "mode_skip:<class>")`.
- Add 4 parametrized cases: same classes with `requires_security_audit=True` ⇒ `(False, "security_audit_required")` (proves Priority 6 still wins).

### 10. `tests/integration/test_intent_classifier_observe_mode.py` (NO CHANGE)
Verified line 104 (`assert data["schema_version"] == 1`) still holds — SCHEMA_VERSION not bumped. The test asserts shape, not class enumeration.

### 11. `tests/integration/test_enforcement_mode_cutover.py` (REVIEW)
- Confirm cutover assertions don't pin to a 5-element `_SKIP_INTENT_CLASSES`. If they do, update count to 9.

## Documentation

### 12. `docs/INTENT-CLASSIFICATION.md` (MODIFY)
- §"The 9 intent classes" → rename "13 intent classes"; add 4 table rows with description + example.
- Add subsection "EXPLORATION vs STATUS_QUERY" explaining the file-count anchor.
- Add subsection "SCRATCH known limitation" — Write/Edit gate not relaxed (deferred to follow-up).

### 13. `docs/HOOK-REGISTRY.md` (MODIFY)
- Line 37 enumerates 9 class names — update to enumerate all 13.

### 14. `docs/HOOKS.md` (MODIFY)
- Line 44 enumerates 9 class names — update to enumerate all 13.

### 15. `plugins/autonomous-dev/CHANGELOG.md` (MODIFY)
Entry under next release:
```
### Added
- Intent classifier: 4 non-SWE classes (EXPLORATION, TRIAGE, REMOTE_OPS, SCRATCH) added to skip-eligible set (#1023)

### Known Limitations
- SCRATCH class does not relax Write/Edit gates in this release; only plan/validate steps relaxed (follow-up issue planned)
```

### 16. `.claude/PROJECT.md` (NO CHANGE)
No scope or constraint shifts.

## Implementation Order

1. **Step 1**: Edit `intent_classifier.py` (enum + line 153 comment + `_VALID_LLM_INTENTS` + template + lines 367/373 + module docstring). Run `python3 -c "import sys; sys.path.insert(0, 'plugins/autonomous-dev/lib'); import intent_classifier"` — must not raise (template integrity guard).
2. **Step 2**: Add fixtures (4 per class + 4 adversarial) to `intent_classifier_fixtures.json`.
3. **Step 3**: Edit `tests/unit/lib/test_intent_classifier.py` — add `_label_to_intent` entries FIRST (otherwise existing tests break), then add regression lock tests. Run `pytest tests/unit/lib/test_intent_classifier.py -v`.
4. **Step 4**: Edit `session_mode.py` (`_SKIP_INTENT_CLASSES` + decision table docstring). Add `test_skip_intent_classes_includes_new_classes` to `test_session_mode.py`. Run `pytest tests/unit/lib/test_session_mode.py -v`.
5. **Step 5**: Add cases to `test_enforcement_decision.py`. Run `pytest tests/unit/lib/test_enforcement_decision.py -v`.
6. **Step 6**: Verify `tests/integration/test_intent_classifier_observe_mode.py` and `tests/integration/test_enforcement_mode_cutover.py` still pass — update only if `_SKIP_INTENT_CLASSES` count is hard-pinned.
7. **Step 7**: Update INTENT-CLASSIFICATION.md, HOOK-REGISTRY.md, HOOKS.md, CHANGELOG.md.
8. **Step 8**: Full regression: `pytest tests/unit/lib tests/unit/hooks tests/integration -q`.

## Risk Register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Probability mass redistribution drops confidence on existing classes (LLM less certain across 13 options) — but **untested under mock harness** (deterministic 0.95) | Medium in production | Mitigated by fail-safe: low-confidence → AMBIGUOUS → enforce. First real signal in #1014 shadow mode. |
| EXPLORATION/STATUS_QUERY confusion | Medium | File-count anchor in template Rule 5; both classes are skip-eligible so misclassification between them is benign. |
| EXPLORATION misclassification skips IMPLEMENT/PLAN/VALIDATE gates (not just security gates) for a real SWE prompt | Medium | predicted_file_count is heuristic only. Adversary or accidental phrasing like "look at the auth handler across the codebase" could trigger EXPLORATION skip on a SWE task. Acceptable because: (a) regex-first still catches security keywords, (b) the user can always fall back to /implement explicitly, (c) telemetry (#1014) will surface false-positive patterns. |
| Token cost regression — adding 4 bullets + Rule 5 + "13 strings" expands the LLM prompt template by ~80–120 tokens per classification | Low (Haiku at $0.25/MTok input) | One-time prompt cost; consider caching the static prefix in a follow-up if telemetry shows high call volume. |
| SCRATCH security: payload staged in /tmp/ then sourced | Low | Documented known-limitation; per-tool exception deferred. Regex still hits security keywords pre-LLM. |
| Hook readers crash on unknown intent class | Very low | Verified all readers route through `should_pipeline_enforce` which has fail-safe default-True for unknowns. |
| `<user_input>` wrapper interaction with new fixtures (prompt-injection defense) | Low | Adversarial fixture `expl-injection-001` covers literal `<user_input>` text in user prompts. _validate_template_integrity still passes. |
| _SKIP_INTENT_CLASSES drift surface — hardcoded frozenset, no config path | Very low | Acknowledged. Future #961/#1024 will keep editing it; consider config-file path in a future refactor (out of scope here). |

## Rollback Strategy

1. **Soft rollback** (no redeploy): set `INTENT_CLASSIFIER_ENFORCE=false` env var. Phase E gating disabled, classifier returns to observe-only — new classes recorded in telemetry but ignored by gates.
2. **Full revert**: `git revert <merge-sha>` of the addition. Existing artifacts on disk that recorded a new intent_class string (e.g. `"triage"`) become "unknown" to the reverted reader → fail-safe enforce. No data corruption. Time-to-clean-state ≤ TTL_SECONDS=3600s; live sessions during the bad window hit fail-safe enforce mode after revert (degraded but safe).

## Acceptance Criteria

1. `IntentClass` enum has 14 members total (13 "real" classes + AMBIGUOUS sentinel); `_VALID_LLM_INTENTS` length is 13.
2. `_LLM_PROMPT_TEMPLATE` declares "13 fixed intent categories" and contains the 4 new bullet definitions; `_validate_template_integrity` still passes (`<user_input>` wrapper intact).
3. `_SKIP_INTENT_CLASSES` contains exactly 9 entries: original 5 + `exploration`, `triage`, `remote_ops`, `scratch`.
4. `should_pipeline_enforce()` returns `False` for each of the 4 new strings (case-insensitive); existing behavior for `"ambiguous"`, `"implement"`, `"security_critical"`, unknown strings, non-string inputs is unchanged.
5. Security regex still wins: prompt `"ssh user@host rotate-jwt"` returns `SECURITY_CRITICAL` (regex_hit=True), even though "ssh" pattern would otherwise suggest REMOTE_OPS.
6. Adversarial fixture coverage: 1 fixture per new class containing a security keyword classifies as `security_critical`, not the new class. Plus `expl-injection-001` literal-`<user_input>` fixture passes.
7. Fixture file has 4 fixtures per new class (16 total added) + 4 adversarial fixtures (20 total). 1 holdout per class (4 holdouts added).
8. `_label_to_intent` map in `tests/unit/lib/test_intent_classifier.py:502` contains 13 entries.
9. `pytest tests/unit/lib tests/unit/hooks tests/integration -q` passes; baseline before changes captured (run before Step 1, compare delta).
10. CHANGELOG entry added; INTENT-CLASSIFICATION.md, HOOK-REGISTRY.md, HOOKS.md updated to reflect 13 classes.
11. `INTENT_CLASSIFIER_ENFORCE=false` continues to disable Phase E gating — verified by existing test `test_enforcement_decision.py::test_enforcement_off_returns_no_skip` (asserts `reason == 'enforcement_off'`; no new test required).

## Recommended Implementer Model: opus

Multi-file logic change touching security-sensitive classifier and test glue. Adversarial fixture authoring requires nuanced understanding of regex-first ordering and prompt-injection wrapper. Opus-tier judgment warranted.
