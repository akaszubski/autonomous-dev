---
covers:
  - plugins/autonomous-dev/hooks/conversation_archiver.py
  - ~/.claude/archive/
  - bootstrap/control_trust/cases.json
---

# Session Analytics

Every Claude Code session is a CANDIDATE for archiving; whether it is actually archived depends on the hook's own gating — `conversation_archiver.py`'s `main()` exits normally (code 0) without archiving anything when archiving is disabled via `CONVERSATION_ARCHIVE=false`, when hook input is missing/unreadable/malformed, when no transcript path is given, when the transcript file does not exist, or when it is smaller than `MIN_TRANSCRIPT_BYTES` — so a normally-completed hook invocation is not itself evidence a session was archived. When the hook does reach the copy step, `main()` first copies the transcript directly onto the destination path via `shutil.copy2` (non-atomic — no temp-file-plus-rename); a copy that fails partway through can leave a damaged file where a prior good transcript for that session existed, and any `OSError`/`IOError` makes `_archive_transcript` return `None`, causing `main()` to exit before touching either index. Only after a successful copy does `main()` separately attempt the JSONL index write (tmp+`os.replace`) and the SQLite index write (a transactional `sqlite3.connect(...)` context manager) — each can independently succeed or fail relative to the other, so a run can land the transcript but leave one or both indexes stale. Two layers on disk when all three steps land: a SQLite summary index for fast queries and full raw transcripts on disk.

**Hook**: [conversation_archiver.py](../plugins/autonomous-dev/hooks/conversation_archiver.py) (fires on `Stop` event, per-turn)

## Locations

| What | Path |
|------|------|
| SQLite summary index | `~/.claude/archive/sessions.db` |
| Full raw transcripts | `~/.claude/archive/conversations/{YYYY-MM}/{session_id}.jsonl` |
| JSONL session index (grep/jq friendly) | `~/.claude/archive/index.jsonl` |
| Live transcript (Claude Code's own, near-real-time) | `~/.claude/projects/{project}/{session_id}.jsonl` |

The archive is a CANDIDATE for per-turn population (after each assistant response) — the gating conditions above (disabled, missing/malformed input, missing or too-small transcript) can make a given Stop event add nothing. The live file is updated entry-by-entry as Claude Code produces output, independently of whether the archiver runs on any given turn.

## sessions.db Schema (17 columns)

| Column | Type | Source |
|--------|------|--------|
| `session_id` | TEXT PK | Claude Code session UUID |
| `project` | TEXT | basename of `cwd` (e.g. `realign`, `autonomous-dev`) |
| `cwd` | TEXT | Full working directory at session start |
| `archive_path` | TEXT | Path to the archived JSONL transcript |
| `first_seen` | TEXT | ISO timestamp, preserved across upserts |
| `last_updated` | TEXT | ISO timestamp, intended to update when a Stop event's SQLite write actually commits (see Timing) — `_update_sqlite_index()` wraps its entire connect/create/migrate/upsert body in a blanket `except Exception: pass`, so reaching, or even entering, that call is not evidence the row was written or updated; not every Stop event even reaches this point |
| `message_count` | INTEGER | Total conversation messages (user + assistant only) |
| `user_messages` | INTEGER | User turns |
| `assistant_messages` | INTEGER | Assistant turns |
| `tool_calls` | INTEGER | Count of `tool_use` content blocks in assistant messages |
| `total_input_tokens` | INTEGER | Fresh (non-cached) input tokens |
| `total_output_tokens` | INTEGER | Generated output tokens |
| `total_cache_read_tokens` | INTEGER | Tokens served from cache (0.1x base cost) |
| `total_cache_creation_tokens` | INTEGER | Tokens written to cache (1.25x-2.0x depending on TTL) |
| `transcript_bytes` | INTEGER | Size of the archived transcript file |
| `model` | TEXT | e.g. `claude-opus-4-7`, `claude-sonnet-4-6` |
| `first_user_prompt` | TEXT | First user message, truncated to 200 chars |

## Common Queries

**Per-repo totals**
```bash
sqlite3 -header -column ~/.claude/archive/sessions.db "
  SELECT project, COUNT(*) sessions, SUM(total_output_tokens) out_tok, SUM(tool_calls) tools
  FROM sessions GROUP BY project ORDER BY out_tok DESC;
"
```

**Recent sessions for a specific repo**
```bash
sqlite3 -header -column ~/.claude/archive/sessions.db "
  SELECT substr(session_id,1,8) sid, last_updated, message_count, model,
         substr(first_user_prompt,1,60) prompt
  FROM sessions WHERE project='autonomous-dev'
  ORDER BY last_updated DESC LIMIT 10;
"
```

**Biggest sessions by output tokens**
```bash
sqlite3 -header -column ~/.claude/archive/sessions.db "
  SELECT project, substr(session_id,1,8) sid, total_output_tokens, tool_calls,
         substr(first_user_prompt,1,50) prompt
  FROM sessions ORDER BY total_output_tokens DESC LIMIT 10;
"
```

**Cache hit rate per repo** (higher `cache_pct` = better caching, cheaper)
```bash
sqlite3 -header -column ~/.claude/archive/sessions.db "
  SELECT project,
         SUM(total_input_tokens) fresh_in,
         SUM(total_cache_read_tokens)  cache_read,
         ROUND(100.0 * SUM(total_cache_read_tokens) /
               NULLIF(SUM(total_cache_read_tokens + total_input_tokens), 0), 1) cache_pct
  FROM sessions GROUP BY project ORDER BY cache_read DESC;
"
```

**Find transcript file for a session**
```bash
sqlite3 ~/.claude/archive/sessions.db \
  "SELECT archive_path FROM sessions WHERE session_id LIKE 'abc12345%';"
```

**Search all history for a past prompt or output**
```bash
grep -l "search term" ~/.claude/archive/conversations/**/*.jsonl
```

## Timing

The `Stop` hook fires **after each complete assistant response**, not mid-turn. When the hook actually reaches the copy step and that copy succeeds, the archive is written for that turn — several earlier conditions (disabled, missing/malformed input, missing or too-small transcript) exit normally with no archive attempt at all, and no measurement in this rung establishes a specific lag duration; the transcript copy gates both index writes (a failed copy exits before either runs), and a partial or timed-out hook invocation does not by itself mean the archive was left unaffected, only that it may not have completed. Example:

```
live file:  ~/.claude/projects/.../{session_id}.jsonl   (real-time, every entry)
archive:    ~/.claude/archive/conversations/.../         (per-turn, post-Stop)
```

If Claude Code crashes mid-turn, the live file is written by Claude Code itself, independently of the archiver — its crash-survival behavior is outside `conversation_archiver.py` and is not verified by this document — but the archive may skip that partial turn, may skip it entirely under any of the gating conditions above even after a clean turn, or, if the copy step itself fails partway through, damage a prior good transcript for that session rather than merely skip it (see the copy behaviour above). Letting Claude finish the response normally lets the Stop hook attempt a flush; whether that attempt actually produced or updated an archive artifact is subject to the same gating conditions above and should be checked (archive path, index rows), not assumed from response completion alone.

## Configuration

Controlled by env var `CONVERSATION_ARCHIVE` (default `true`):
- `CONVERSATION_ARCHIVE=true` — attempt archiving on Stop events, subject to the same gating conditions described above (missing/malformed input, a missing or too-small transcript still exit without archiving)
- `CONVERSATION_ARCHIVE=false` — disable archiving

Set in `~/.claude/settings.json`:
```json
{
  "hooks": {
    "Stop": [{
      "command": "CONVERSATION_ARCHIVE=true python3 ~/.claude/hooks/conversation_archiver.py",
      "timeout": 10,
      "type": "command"
    }]
  }
}
```

The hook is non-blocking (always exits 0), uses Python stdlib only, and times out at 10s.

## Per-Repo Quirk: Worktrees and Subdirectories

The `project` column is derived from the `cwd` basename at session start. This means:

- Sessions started in a worktree path like `~/Dev/autonomous-dev/.worktrees/batch-20260413-152323/` get `project = "batch-20260413-152323"` rather than folding into `autonomous-dev`.
- Sessions started in a subdirectory like `~/Dev/spektiv/frontend/` get `project = "frontend"` rather than `spektiv`.

This is by design — it lets you analyze batch-mode sessions separately from main-branch work. If you want unified analytics, group by `cwd` prefix in your query.

## Control-Tool Trust Carrier/Provenance (F0, Issue #1773)

*Added 2026-09-10.* `bootstrap/control_trust/cases.json`'s `carrier_facts`/`carrier_facts_provenance`/`join_status` freeze a private, historical Claude Code CLI 2.1.236 carrier census (artifact `adev-f0-evidence-lHQCBUCy`), captured under an ADDITIVE `--settings` hook overlay over the operator's otherwise-unmodified installed settings, across TWO DIFFERENT native sessions that are never merged into one observation — this is not one stock, joined measurement, and it is distinct from this page's own archiver/index mechanism above. Link there for exact field-level values and counts rather than duplicating a second mutable status table here.

Configured vs. emitted vs. accepted, in one sentence: an enabled OTel flag (`enabled=true`) is not an operating exporter — the same console-exporter configuration produced 1 log exporter under `--output-format text` and 0 under `--output-format stream-json --include-hook-events` (with an explicit event-dropped warning), in the two separate sessions above. Top-level `Read` ingress and the native stream-json tool records join by an EXACT `tool_use_id` match; hook RESULT records (`hook_response`) carry no `tool_use_id` at all (0 of 7 examined), and the dispatcher's own OTel records carry `session.id`/`prompt.id` but no tool- or hook-level identifier — so no single key spans ingress, hook-result, and OTel together. Nearness in time or a shared session is explicitly never accepted as a substitute join. Remote consumers, Serena/other MCP routes, subagent-dispatched tools, descendant processes below a candidate's direct child, and any clean, source-free installed (D0) delivery were none of them observed here and stay UNMEASURED — a zero or an absent key above is a recorded absence, not a repaired one.

A completion timestamp recorded by this rung's own bookkeeping is restored/administrative state — it is evidence of neither a new specialist execution in this rung nor of any resulting target-file effect; the state layer's own ~7200s staleness window (see the State Management entry in [ARCHITECTURE-OVERVIEW.md](ARCHITECTURE-OVERVIEW.md)) governs when a read returns as though empty, and by itself proves neither deletion nor garbage collection of any prior record. F0 freezes these carrier findings for a later rung to act on; it repairs neither this page's own archiving gaps (see Timing above) nor the missing carrier join.

## Related

- [HOOKS.md](HOOKS.md) — full hook catalog
- [HOOK-REGISTRY.md](HOOK-REGISTRY.md) — hook sidecar schema
- [EVALUATION.md](EVALUATION.md) — how sessions feed the effectiveness measurement loop
- [ARCHITECTURE-OVERVIEW.md](ARCHITECTURE-OVERVIEW.md) — where session logging fits in the three-layer system

## Backfill

If you need to populate metadata from existing transcripts (e.g. after a hook bugfix), the extraction logic lives in `_extract_metadata()` in `conversation_archiver.py`. Re-parse transcripts on disk and `UPDATE sessions SET ...` — the schema supports idempotent re-writes via `INSERT OR REPLACE`.

Issue #773 introduced the SQLite index. Later fix added `total_cache_read_tokens` and `total_cache_creation_tokens` columns via idempotent `PRAGMA table_info` + `ALTER TABLE ADD COLUMN` migration. Existing DBs auto-upgrade on the next Stop event.
