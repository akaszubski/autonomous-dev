---
topic: sessions.db v2 schema (merged) + JSONL replay migration plan
created: 2026-05-02
updated: 2026-06-09
sources:
  - https://github.com/wesm/agentsview/blob/main/internal/db/schema.sql
  - https://github.com/wesm/agentsview/tree/main/internal/signals
  - https://github.com/spences10/claude-code-analytics/blob/main/src/database/schema.sql
  - ~/.claude/hooks/conversation_archiver.py
  - docs/research/CONVERSATION_ARCHIVER_METADATA_EXTRACTION.md
status: in-progress — decision pending (finish or abandon; see #1157)
---

> **Status (2026-06-09)**: This schema design and the accompanying `scripts/migrate_sessions_v2.py` are committed as **in-progress** to make the work visible. A `~/.claude/archive/sessions_v2.db` (123 MB) already exists on disk from May 2026 work. The migration has NOT been switched in — canonical readers still use `sessions.db` v1. A decision is owed: finish the migration and switch in, or abandon and clean up. Tracked by Issue #1157.

# sessions.db v2 — merged schema + migration plan

## Composition

- **Core (sessions / messages / tool_calls / tool_result_events)** — wesm/agentsview
- **hook_events / files / file_operations / processing_state** — spences10/claude-code-analytics
- **pipeline_runs / pipeline_steps / agent_invocations / slash_commands / enforcement_events** — autonomous-dev specific
- **session_signals (derived)** — agentsview signals/ pattern + autonomous-dev compliance metrics

Source of truth remains `~/.claude/archive/conversations/{YYYY-MM}/{sid}.jsonl`. The DB is a derived index — drop and rebuild from JSONL is always safe.

## Schema (SQLite)

```sql
-- =========================================================================
-- Core: session, message, tool tables (from agentsview)
-- =========================================================================

CREATE TABLE sessions (
    id                          TEXT PRIMARY KEY,
    project                     TEXT NOT NULL,
    machine                     TEXT NOT NULL DEFAULT 'local',
    agent                       TEXT NOT NULL DEFAULT 'claude-code',
    cwd                         TEXT NOT NULL DEFAULT '',
    git_branch                  TEXT NOT NULL DEFAULT '',
    model                       TEXT NOT NULL DEFAULT '',

    started_at                  TEXT,
    ended_at                    TEXT,
    duration_ms                 INTEGER,

    message_count               INTEGER NOT NULL DEFAULT 0,
    user_message_count          INTEGER NOT NULL DEFAULT 0,
    assistant_message_count     INTEGER NOT NULL DEFAULT 0,
    tool_call_count             INTEGER NOT NULL DEFAULT 0,

    total_input_tokens          INTEGER NOT NULL DEFAULT 0,
    total_output_tokens         INTEGER NOT NULL DEFAULT 0,
    total_cache_read_tokens     INTEGER NOT NULL DEFAULT 0,
    total_cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
    peak_context_tokens         INTEGER NOT NULL DEFAULT 0,
    total_cost_usd              REAL NOT NULL DEFAULT 0,

    transcript_path             TEXT,
    transcript_bytes            INTEGER,
    transcript_hash             TEXT,
    is_truncated                INTEGER NOT NULL DEFAULT 0,
    parser_malformed_lines      INTEGER NOT NULL DEFAULT 0,

    first_user_prompt           TEXT,
    end_reason                  TEXT,
    parent_session_id           TEXT,

    created_at                  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX idx_sessions_project_ended ON sessions(project, ended_at DESC);
CREATE INDEX idx_sessions_started        ON sessions(started_at);
CREATE INDEX idx_sessions_parent         ON sessions(parent_session_id) WHERE parent_session_id IS NOT NULL;

CREATE TABLE messages (
    id                          INTEGER PRIMARY KEY,
    session_id                  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    ordinal                     INTEGER NOT NULL,
    role                        TEXT NOT NULL,
    timestamp                   TEXT,
    model                       TEXT NOT NULL DEFAULT '',
    content                     TEXT NOT NULL,
    thinking_text               TEXT NOT NULL DEFAULT '',
    content_length              INTEGER NOT NULL DEFAULT 0,
    has_tool_use                INTEGER NOT NULL DEFAULT 0,
    has_thinking                INTEGER NOT NULL DEFAULT 0,
    is_sidechain                INTEGER NOT NULL DEFAULT 0,
    is_compact_boundary         INTEGER NOT NULL DEFAULT 0,
    input_tokens                INTEGER,
    output_tokens               INTEGER,
    cache_read_tokens           INTEGER,
    cache_creation_tokens       INTEGER,
    UNIQUE(session_id, ordinal)
);

CREATE INDEX idx_messages_session       ON messages(session_id, ordinal);
CREATE INDEX idx_messages_session_role  ON messages(session_id, role);

CREATE TABLE tool_calls (
    id                          INTEGER PRIMARY KEY,
    message_id                  INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    session_id                  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    tool_use_id                 TEXT,
    tool_name                   TEXT NOT NULL,
    category                    TEXT NOT NULL,
    input_json                  TEXT,
    skill_name                  TEXT,
    subagent_session_id         TEXT,
    started_at                  TEXT,
    completed_at                TEXT,
    execution_time_ms           INTEGER,
    success                     INTEGER,
    error_message               TEXT
);

CREATE INDEX idx_tool_calls_session  ON tool_calls(session_id);
CREATE INDEX idx_tool_calls_category ON tool_calls(category);
CREATE INDEX idx_tool_calls_skill    ON tool_calls(skill_name) WHERE skill_name IS NOT NULL;
CREATE INDEX idx_tool_calls_subagent ON tool_calls(subagent_session_id) WHERE subagent_session_id IS NOT NULL;

CREATE TABLE tool_result_events (
    id                          INTEGER PRIMARY KEY,
    session_id                  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    tool_call_id                INTEGER REFERENCES tool_calls(id) ON DELETE CASCADE,
    tool_use_id                 TEXT,
    source                      TEXT NOT NULL,
    status                      TEXT NOT NULL,
    content                     TEXT NOT NULL,
    content_length              INTEGER NOT NULL DEFAULT 0,
    timestamp                   TEXT
);

CREATE INDEX idx_tool_results_session ON tool_result_events(session_id);
CREATE INDEX idx_tool_results_call    ON tool_result_events(tool_call_id);

-- =========================================================================
-- Hook & file ops (from claude-code-analytics)
-- =========================================================================

CREATE TABLE hook_events (
    id                          INTEGER PRIMARY KEY,
    session_id                  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    hook_name                   TEXT NOT NULL,
    event_type                  TEXT NOT NULL,
    matcher                     TEXT,
    tool_name                   TEXT,
    decision                    TEXT,
    reason                      TEXT,
    execution_time_ms           INTEGER,
    timestamp                   TEXT,
    event_data                  TEXT
);

CREATE INDEX idx_hook_events_session   ON hook_events(session_id, timestamp);
CREATE INDEX idx_hook_events_decision  ON hook_events(decision) WHERE decision IS NOT NULL;
CREATE INDEX idx_hook_events_hook_name ON hook_events(hook_name);

CREATE TABLE files (
    id                          INTEGER PRIMARY KEY,
    project                     TEXT NOT NULL,
    file_path                   TEXT NOT NULL,
    first_accessed_at           TEXT,
    last_accessed_at            TEXT,
    total_reads                 INTEGER NOT NULL DEFAULT 0,
    total_writes                INTEGER NOT NULL DEFAULT 0,
    total_edits                 INTEGER NOT NULL DEFAULT 0,
    total_lines_added           INTEGER NOT NULL DEFAULT 0,
    total_lines_removed         INTEGER NOT NULL DEFAULT 0,
    UNIQUE(project, file_path)
);

CREATE INDEX idx_files_project_active ON files(project, last_accessed_at DESC);

CREATE TABLE file_operations (
    id                          INTEGER PRIMARY KEY,
    file_id                     INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    session_id                  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    tool_call_id                INTEGER REFERENCES tool_calls(id) ON DELETE SET NULL,
    operation_type              TEXT NOT NULL,
    lines_added                 INTEGER NOT NULL DEFAULT 0,
    lines_removed               INTEGER NOT NULL DEFAULT 0,
    timestamp                   TEXT
);

CREATE INDEX idx_file_ops_session ON file_operations(session_id);
CREATE INDEX idx_file_ops_file    ON file_operations(file_id);

CREATE TABLE processing_state (
    transcript_path             TEXT PRIMARY KEY,
    last_processed_position     INTEGER NOT NULL DEFAULT 0,
    last_processed_at           TEXT,
    file_mtime                  INTEGER,
    file_hash                   TEXT,
    status                      TEXT NOT NULL DEFAULT 'pending'
);

-- =========================================================================
-- Autonomous-dev specific telemetry
-- =========================================================================

CREATE TABLE pipeline_runs (
    id                          INTEGER PRIMARY KEY,
    session_id                  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    command                     TEXT NOT NULL,
    args                        TEXT,
    started_at                  TEXT NOT NULL,
    ended_at                    TEXT,
    final_step                  INTEGER,
    status                      TEXT NOT NULL DEFAULT 'running'
);

CREATE INDEX idx_pipeline_runs_session ON pipeline_runs(session_id);
CREATE INDEX idx_pipeline_runs_command ON pipeline_runs(command, started_at DESC);

CREATE TABLE pipeline_steps (
    id                          INTEGER PRIMARY KEY,
    run_id                      INTEGER NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    step_no                     INTEGER NOT NULL,
    name                        TEXT NOT NULL,
    started_at                  TEXT,
    ended_at                    TEXT,
    duration_ms                 INTEGER,
    blocked                     INTEGER NOT NULL DEFAULT 0,
    block_reason                TEXT,
    tokens_in                   INTEGER NOT NULL DEFAULT 0,
    tokens_out                  INTEGER NOT NULL DEFAULT 0,
    UNIQUE(run_id, step_no)
);

CREATE INDEX idx_pipeline_steps_run     ON pipeline_steps(run_id);
CREATE INDEX idx_pipeline_steps_blocked ON pipeline_steps(blocked, name) WHERE blocked = 1;

CREATE TABLE agent_invocations (
    id                          INTEGER PRIMARY KEY,
    session_id                  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    pipeline_step_id            INTEGER REFERENCES pipeline_steps(id) ON DELETE SET NULL,
    agent_name                  TEXT NOT NULL,
    model                       TEXT,
    started_at                  TEXT,
    ended_at                    TEXT,
    duration_ms                 INTEGER,
    input_tokens                INTEGER NOT NULL DEFAULT 0,
    output_tokens               INTEGER NOT NULL DEFAULT 0,
    success                     INTEGER,
    output_summary              TEXT
);

CREATE INDEX idx_agent_invocations_session ON agent_invocations(session_id);
CREATE INDEX idx_agent_invocations_agent   ON agent_invocations(agent_name, started_at DESC);

CREATE TABLE slash_commands (
    id                          INTEGER PRIMARY KEY,
    session_id                  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    message_id                  INTEGER REFERENCES messages(id) ON DELETE SET NULL,
    command                     TEXT NOT NULL,
    args                        TEXT,
    timestamp                   TEXT
);

CREATE INDEX idx_slash_commands_session ON slash_commands(session_id);
CREATE INDEX idx_slash_commands_command ON slash_commands(command, timestamp DESC);

CREATE TABLE enforcement_events (
    id                          INTEGER PRIMARY KEY,
    session_id                  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    hook_event_id               INTEGER REFERENCES hook_events(id) ON DELETE SET NULL,
    gate                        TEXT NOT NULL,
    decision                    TEXT NOT NULL,
    reason                      TEXT,
    bypassed                    INTEGER NOT NULL DEFAULT 0,
    timestamp                   TEXT NOT NULL
);

CREATE INDEX idx_enforcement_session ON enforcement_events(session_id, timestamp);
CREATE INDEX idx_enforcement_gate    ON enforcement_events(gate, decision, timestamp DESC);
CREATE INDEX idx_enforcement_bypass  ON enforcement_events(bypassed) WHERE bypassed = 1;

-- =========================================================================
-- Derived signals (computed by batch job, mirrors agentsview signals/)
-- =========================================================================

CREATE TABLE session_signals (
    session_id                  TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    outcome                     TEXT NOT NULL DEFAULT 'unknown',
    outcome_confidence          TEXT NOT NULL DEFAULT 'low',
    health_score                INTEGER,
    health_grade                TEXT,
    tool_failure_signal_count   INTEGER NOT NULL DEFAULT 0,
    tool_retry_count            INTEGER NOT NULL DEFAULT 0,
    edit_churn_count            INTEGER NOT NULL DEFAULT 0,
    consecutive_failure_max     INTEGER NOT NULL DEFAULT 0,
    compaction_count            INTEGER NOT NULL DEFAULT 0,
    mid_task_compaction_count   INTEGER NOT NULL DEFAULT 0,
    context_pressure_max        REAL,

    pipeline_compliance_score   INTEGER,
    enforcement_block_count     INTEGER NOT NULL DEFAULT 0,
    enforcement_bypass_count    INTEGER NOT NULL DEFAULT 0,
    pipeline_steps_completed    INTEGER NOT NULL DEFAULT 0,
    test_gate_blocks            INTEGER NOT NULL DEFAULT 0,
    anti_stub_blocks            INTEGER NOT NULL DEFAULT 0,
    plan_critic_rounds          INTEGER NOT NULL DEFAULT 0,

    last_computed_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX idx_signals_outcome ON session_signals(outcome);
CREATE INDEX idx_signals_health  ON session_signals(health_score);

-- =========================================================================
-- Reference
-- =========================================================================

CREATE TABLE model_pricing (
    model_pattern               TEXT PRIMARY KEY,
    input_per_mtok              REAL NOT NULL DEFAULT 0,
    output_per_mtok             REAL NOT NULL DEFAULT 0,
    cache_creation_per_mtok     REAL NOT NULL DEFAULT 0,
    cache_read_per_mtok         REAL NOT NULL DEFAULT 0,
    updated_at                  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE schema_version (
    version                     INTEGER PRIMARY KEY,
    applied_at                  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    description                 TEXT
);

INSERT INTO schema_version(version, description)
VALUES (2, 'agentsview core + claude-code-analytics hooks + autonomous-dev pipeline telemetry');
```

## Migration: replay JSONL, do not re-run sessions

The 235 JSONL transcripts in `~/.claude/archive/conversations/{YYYY-MM}/*.jsonl` already contain every prompt, response, tool call, and tool result. The DB is a derived index — re-running sessions through Claude would (a) cost real money, (b) produce different non-deterministic results, (c) lose original timestamps. **Replay the JSONLs.**

### Phases

1. **Schema bring-up** — create `sessions_v2.db` next to `sessions.db`. Keep the old DB as `sessions_v1.db.bak`. Don't delete until v2 is validated.
2. **JSONL replay** — walk `~/.claude/archive/conversations/**/*.jsonl`. For each file:
   - parse turn-by-turn (line is one event: `user_message`, `assistant_message`, `tool_use`, `tool_result`, `system`)
   - upsert `sessions` row (one per file)
   - insert `messages`, `tool_calls`, `tool_result_events` for every turn
   - extract file paths from Read/Write/Edit `input_json` → `files` + `file_operations`
   - extract slash commands from user messages starting with `/` → `slash_commands`
   - record processing watermark in `processing_state` (idempotent re-runs)
3. **Best-effort hook & enforcement extraction** — many old transcripts include hook decision strings inside `tool_result` content (e.g. `permissionDecisionReason`, `decision: block`). Parse what's there into `hook_events` / `enforcement_events`. Older sessions will be sparse — that's expected; pipeline telemetry only becomes complete from when the live archiver starts writing it directly.
4. **Pipeline reconstruction** (heuristic) — for sessions where the user invoked `/implement` etc, walk subsequent turns and infer pipeline_steps from agent invocations and step-tagged messages. Imperfect for old data; perfect for new.
5. **Signal derivation** — run the batch job (port of agentsview's `signals/` package, ~300 lines Python) over all sessions to compute `session_signals`.
6. **Cutover** — patch `~/.claude/hooks/conversation_archiver.py` to write directly to v2 schema. Keep v1 write disabled. Live sessions write the rich tables natively from this point on.

### What you can answer immediately after replay

For all 228 sessions:
- per-tool counts and timing (where transcripts have it)
- file-touch heatmap (which files I edit most across all sessions)
- subagent attribution (which agents got invoked, how often, total tokens spent in each)
- compaction events, mid-task compactions, peak context tokens
- outcome classification (completed / abandoned / errored)
- health score 0–100 with letter grade

### What only fills in for new sessions (post-cutover)

- `pipeline_runs` / `pipeline_steps` with accurate step boundaries and durations
- `enforcement_events` with full block/bypass attribution
- `agent_invocations` with reliable tokens-per-agent (older sessions only get an approximation from message counts)

### Effort estimate

- Schema migration script: ~50 lines Python
- JSONL replay: ~300 lines (parsers per event type, upsert logic)
- Best-effort hook extraction: ~150 lines (regex over tool_result content)
- Signal derivation: ~250 lines (port of agentsview signals/)
- Live archiver patch: rewrite of `_extract_metadata` and `_update_database` in `conversation_archiver.py` (~200 lines)

Total: ~1k lines, one focused day of work, fully tested.

### Why not extend the existing `sessions.db`?

You could `ALTER TABLE` it — the existing archiver already does additive migration for cache token columns. But adding 6 child tables and rewriting all the extraction logic is enough work that it's cleaner to write v2 alongside, validate it produces correct counts against v1 (sanity check), then swap the live writer over. Keeps a fallback.

## Open design questions

1. **Should `messages.content` store full text or a 4KB preview?** agentsview stores full; claude-code-analytics stores `content_preview`. Full text is 10× larger but enables substring search. Recommend: full text, plus optional FTS5 virtual table for search (kuroko1t/claude-vault pattern).
2. **Per-prompt cost calc**: do it at write time (denormalized into `messages.cost_usd`) or compute on read via `JOIN model_pricing`? agentsview joins on read; claude-code-analytics denormalizes. Recommend: denormalize — model pricing rarely changes and denormalizing makes dashboards trivially fast.
3. **`pipeline_compliance_score` formula**: needs definition. Strawman: 100 − 20 per skipped step − 10 per gate bypass − 5 per anti-pattern (e.g. raise NotImplementedError committed). Calibrate against known-good sessions.
4. **Cleanup policy**: still no retention. Recommended cap before this lands: gzip JSONLs older than 30 days, delete (not gzip) full JSONLs older than 12 months — but keep the v2 DB rows forever (cheap).
