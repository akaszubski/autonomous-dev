---
topic: subagentstop-foreground-unreliability-1174
created: 2026-06-09
updated: 2026-06-09
sources:
  - plugins/autonomous-dev/commands/implement.md
  - plugins/autonomous-dev/commands/implement-batch.md
  - plugins/autonomous-dev/hooks/unified_session_tracker.py
  - plugins/autonomous-dev/lib/pipeline_completion_state.py
  - tests/regression/test_issue_852_doc_verdict_completion.py
  - https://code.claude.com/docs/en/agent-sdk/hooks
  - https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-orchestrations
  - https://github.com/anthropics/claude-code/issues/33049
  - https://github.com/anthropics/claude-code/issues/27755
---

# subagentstop-foreground-unreliability-1174

## Local Research (Codebase)

1. Pre-Dispatch Ordering Protocol at commands/implement.md:116-173 — calls check_ordering_with_session_fallback before each agent dispatch
2. SubagentStop hook at hooks/unified_session_tracker.py:988-998 calls record_agent_completion non-blockingly (Issues #625, #629, #632)
3. Existing doc-master manual record_agent_completion pattern at implement.md:1383-1391 and :1614-1620 — TEMPLATE for the fix
4. implement-batch.md:202-208 has the same doc-master pattern (Issue #852 batch parity)
5. record_agent_completion is already idempotent (tri-scope writes, fcntl locking, last-write-wins per Issue #1046) — no API change needed for double-recording
6. tests/regression/test_issue_852_doc_verdict_completion.py:168-207 has the test pattern: assert both function names present within 10 lines

## Web Research (External Sources)

1. Coordinator-side bookkeeping is the established orchestration pattern (Azure Durable Functions writes checkpoint synchronously at each await; Temporal uses workflow event history as source of truth). Async hooks are supplementary, not authoritative.
2. Claude Code SubagentStop is structurally async (post-event hook). GitHub issues #33049 and #27755 document SubagentStop NOT firing at all in some cases and being unreliable for settings.json-based hooks.
3. Idempotency required when both coordinator and hook fire. Last-write-wins dict assignment (existing record_agent_completion pattern) satisfies this. Double-recording is safe.
4. Fix is mechanical: replicate the existing doc-master template for foreground agents. Coordinator call precedes hook fire (in-process synchronous beats async hook).

## Sources

- [plugins](plugins/autonomous-dev/commands/implement.md)
- [plugins](plugins/autonomous-dev/commands/implement-batch.md)
- [plugins](plugins/autonomous-dev/hooks/unified_session_tracker.py)
- [plugins](plugins/autonomous-dev/lib/pipeline_completion_state.py)
- [tests](tests/regression/test_issue_852_doc_verdict_completion.py)
- [code.claude.com](https://code.claude.com/docs/en/agent-sdk/hooks)
- [learn.microsoft.com](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-orchestrations)
- [github.com](https://github.com/anthropics/claude-code/issues/33049)
- [github.com](https://github.com/anthropics/claude-code/issues/27755)
