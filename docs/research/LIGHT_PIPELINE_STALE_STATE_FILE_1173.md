---
topic: light-pipeline-stale-state-file-1173
created: 2026-06-09
updated: 2026-06-09
sources:
  - plugins/autonomous-dev/hooks/unified_pre_tool.py
  - plugins/autonomous-dev/lib/agent_ordering_gate.py
  - plugins/autonomous-dev/commands/implement.md
  - tests/unit/hooks/test_stale_session_state_readers.py
  - https://nesin.io/blog/temp-directory-path-github-actions
  - https://docs.pytest.org/en/stable/how-to/tmp_path.html
  - https://csrc.nist.gov/glossary/term/fail_safe
  - https://www.authgear.com/post/owasp-2025-mishandling-of-exceptional-conditions/
  - https://github.com/tox-dev/filelock/security/advisories/GHSA-qmgc-5h2g-mvrw
  - https://github.com/tox-dev/filelock/security/advisories/GHSA-w853-jp5j-5j7f
---

# light-pipeline-stale-state-file-1173

## Local Research (Codebase)

1. `_get_pipeline_mode_from_state()` at hooks/unified_pre_tool.py:1492-1519
2. Call sites: line 1108 (ordering gate — no env-var check), 2961 (completeness — uses PIPELINE_MODE fallback chain), 5618 (batch — same fallback chain)
3. `_is_stale_session()` returns False when either session_id is 'unknown'/empty (indeterminate gap); does NOT remove stale file. `_get_pipeline_mode_from_state()` does NOT call `_is_pipeline_active()` mtime TTL guard, so the gap is unprotected.
4. `LIGHT_PIPELINE_AGENTS` constant at lib/agent_ordering_gate.py:76-82 — deliberately excludes reviewer & security-auditor.
5. Existing tests: tests/unit/hooks/test_stale_session_state_readers.py (covers function directly), tests/regression/test_issue_849_pipeline_mode_from_state.py.
6. STEP 0 of commands/implement.md writes `mode` to /tmp/implement_pipeline_state.json (line ~308-315). LIGHT PIPELINE section (line 1487+) does NOT add a pre-write or `export PIPELINE_MODE=light`.

## Web Research (External Sources)

1. PRIORITY 1 — Add `PIPELINE_MODE` env-var check as the first line of `_get_pipeline_mode_from_state()`; export it in STEP 0 immediately after mode parsing. Mirrors PIPELINE_ISSUE_NUMBER / PIPELINE_STATE_FILE / CLAUDE_SESSION_ID patterns already in the codebase. CI convention (RUNNER_TEMP/GITHUB_RUN_ID).
2. PRIORITY 2 — Add mtime TTL guard (>30 min stale → return 'full') before falling back to `state.get('mode', 'full')`. Closes the indeterminate-session gap where `_is_stale_session()` returns False but the file is from a prior run.
3. PRIORITY 3 — Replace exists()+open() with a single atomic open()/except — closes the TOCTOU window on the predictable /tmp path (filelock CVE class).
4. Fail-closed-to-'full' is correct for security gates but fail-open for the user's explicit --light intent. The fix makes explicit intent authoritative via the env-var; the file-read fallback is only for hooks firing pre-STEP-0, where 'full' is the correct safe default.
5. OPTIONAL — RUN_ID-keyed sentinel path via PIPELINE_STATE_FILE export. High blast radius (6+ readers + pre_compact_batch_saver.sh + Issue #753 mtime-as-activity-proxy). Defer.

## Sources

- [plugins](plugins/autonomous-dev/hooks/unified_pre_tool.py)
- [plugins](plugins/autonomous-dev/lib/agent_ordering_gate.py)
- [plugins](plugins/autonomous-dev/commands/implement.md)
- [tests](tests/unit/hooks/test_stale_session_state_readers.py)
- [nesin.io](https://nesin.io/blog/temp-directory-path-github-actions)
- [docs.pytest.org](https://docs.pytest.org/en/stable/how-to/tmp_path.html)
- [csrc.nist.gov](https://csrc.nist.gov/glossary/term/fail_safe)
- [www.authgear.com](https://www.authgear.com/post/owasp-2025-mishandling-of-exceptional-conditions/)
- [github.com](https://github.com/tox-dev/filelock/security/advisories/GHSA-qmgc-5h2g-mvrw)
- [github.com](https://github.com/tox-dev/filelock/security/advisories/GHSA-w853-jp5j-5j7f)
