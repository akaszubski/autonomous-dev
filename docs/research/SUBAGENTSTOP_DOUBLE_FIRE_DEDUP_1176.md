---
topic: subagentstop-double-fire-dedup-1176
created: 2026-06-09
updated: 2026-06-09
sources:
  - plugins/autonomous-dev/hooks/unified_session_tracker.py
  - plugins/autonomous-dev/lib/subagent_invocation_cache.py
  - plugins/autonomous-dev/lib/error_analyzer.py
  - plugins/autonomous-dev/lib/pipeline_completion_state.py
  - tests/unit/hooks/test_unified_session_tracker.py
  - https://code.claude.com/docs/en/hooks
  - https://github.com/anthropics/claude-code/issues/7881
  - https://www.svix.com/resources/webhook-university/reliability/idempotency-and-deduplication/
  - https://hookdeck.com/webhooks/guides/implement-webhook-idempotency
  - https://pubs.opengroup.org/onlinepubs/009695399/functions/open.html
---

# subagentstop-double-fire-dedup-1176

## Local Research (Codebase)

1. SubagentStop handler at hooks/unified_session_tracker.py main() lines 878-1018; _write_jsonl_entry called at 979-986; record_agent_completion at 991
2. agent_transcript_path is unique per agent invocation (validated line 936); safe as dedup key
3. Reusable file-backed cache pattern: lib/subagent_invocation_cache.py uses sha256(session_id)[:8] + fcntl.flock + 1h TTL on /tmp
4. Reusable in-memory dedup pattern: lib/error_analyzer.py _seen_fingerprints set
5. record_agent_completion is already idempotent (tri-scope + last-write-wins per #1046) — duplicate calls harmless
6. Test target: tests/unit/hooks/test_unified_session_tracker.py (class-based pytest, patch/MagicMock fixtures)

## Web Research (External Sources)

1. ROOT CAUSE confirmed: dual registration in ~/.claude/settings.json AND .claude/settings.json. Both register same unified_session_tracker.py with matcher=*. Claude Code merges → every hook (not just SubagentStop) fires twice. Affects all hook types.
2. Claude Code official docs (code.claude.com/docs/en/hooks) confirm SubagentStop fires ONCE per completion. Not a Claude Code bug — config duplication.
3. Webhook industry standard for at-least-once delivery: idempotency key + dedup store. For shell subprocesses with no shared state, file-backed marker is the correct tier.
4. POSIX O_CREAT|O_EXCL atomic exclusive-create is the canonical 'first writer wins' primitive — race-condition-free without lock files.
5. Recommendation: in-handler dedup + follow-up issue to remove duplicate registration. Handler dedup protects regardless of future re-introduction.

## Sources

- [plugins](plugins/autonomous-dev/hooks/unified_session_tracker.py)
- [plugins](plugins/autonomous-dev/lib/subagent_invocation_cache.py)
- [plugins](plugins/autonomous-dev/lib/error_analyzer.py)
- [plugins](plugins/autonomous-dev/lib/pipeline_completion_state.py)
- [tests](tests/unit/hooks/test_unified_session_tracker.py)
- [code.claude.com](https://code.claude.com/docs/en/hooks)
- [github.com](https://github.com/anthropics/claude-code/issues/7881)
- [www.svix.com](https://www.svix.com/resources/webhook-university/reliability/idempotency-and-deduplication/)
- [hookdeck.com](https://hookdeck.com/webhooks/guides/implement-webhook-idempotency)
- [pubs.opengroup.org](https://pubs.opengroup.org/onlinepubs/009695399/functions/open.html)
