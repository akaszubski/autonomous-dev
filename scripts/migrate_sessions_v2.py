#!/usr/bin/env python3
"""migrate_sessions_v2.py — replay JSONL transcripts into v2 schema.

Status: SKELETON for review. Extraction logic is real for core tables;
autonomous-dev-specific extraction (pipeline_runs, enforcement_events,
agent_invocations) is stubbed with TODOs and is best-effort for backfilled
sessions — full fidelity only kicks in once the live archiver is patched
to write these tables directly.

Usage:
    python scripts/migrate_sessions_v2.py replay [--limit N] [--dry-run]
    python scripts/migrate_sessions_v2.py status
    python scripts/migrate_sessions_v2.py validate          # cross-check counts vs v1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator

_SLASH_NAME_RE = re.compile(r"<command-name>\s*(/?[^<]+?)\s*</command-name>")
_SLASH_ARGS_RE = re.compile(r"<command-args>\s*(.*?)\s*</command-args>", re.DOTALL)

ARCHIVE_ROOT = Path.home() / ".claude" / "archive"
TRANSCRIPTS_DIR = ARCHIVE_ROOT / "conversations"
V1_DB = ARCHIVE_ROOT / "sessions.db"
V2_DB = ARCHIVE_ROOT / "sessions_v2.db"

# Categorisation of native Claude Code tool names. Extend as new tools land.
TOOL_CATEGORIES = {
    "Bash": "bash",
    "Read": "read",
    "Write": "write",
    "Edit": "edit",
    "NotebookEdit": "edit",
    "Glob": "search",
    "Grep": "search",
    "WebSearch": "search",
    "WebFetch": "search",
    "Agent": "agent",
    "Task": "agent",
    "TaskCreate": "agent",
    "TaskUpdate": "agent",
    "ScheduleWakeup": "system",
    "Skill": "system",
    "ToolSearch": "system",
}

ENFORCEMENT_GATES = {  # rough heuristics for backfill scan
    "test_gate": ("STEP 5", "test gate", "tests must pass"),
    "anti_stub": ("anti-stub", "raise NotImplementedError", "stub detected"),
    "plan_gate": ("plan_gate", "plan required"),
    "pipeline_complete": ("pipeline incomplete", "STEP 8"),
    "orchestrator_route": ("orchestrator", "must route"),
}

# ---------------------------------------------------------------------------
# Schema (kept inline so the file is self-contained — single source of truth
# for the migration script. Mirrors docs/research/SESSIONS_DB_SCHEMA_V2.md.)
# ---------------------------------------------------------------------------
SCHEMA_SQL = r"""
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY, project TEXT NOT NULL, machine TEXT NOT NULL DEFAULT 'local',
    agent TEXT NOT NULL DEFAULT 'claude-code', cwd TEXT NOT NULL DEFAULT '',
    git_branch TEXT NOT NULL DEFAULT '', model TEXT NOT NULL DEFAULT '',
    started_at TEXT, ended_at TEXT, duration_ms INTEGER,
    message_count INTEGER NOT NULL DEFAULT 0, user_message_count INTEGER NOT NULL DEFAULT 0,
    assistant_message_count INTEGER NOT NULL DEFAULT 0, tool_call_count INTEGER NOT NULL DEFAULT 0,
    total_input_tokens INTEGER NOT NULL DEFAULT 0, total_output_tokens INTEGER NOT NULL DEFAULT 0,
    total_cache_read_tokens INTEGER NOT NULL DEFAULT 0, total_cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
    peak_context_tokens INTEGER NOT NULL DEFAULT 0, total_cost_usd REAL NOT NULL DEFAULT 0,
    transcript_path TEXT, transcript_bytes INTEGER, transcript_hash TEXT,
    is_truncated INTEGER NOT NULL DEFAULT 0, parser_malformed_lines INTEGER NOT NULL DEFAULT 0,
    first_user_prompt TEXT, end_reason TEXT, parent_session_id TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_sessions_project_ended ON sessions(project, ended_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL, role TEXT NOT NULL, timestamp TEXT,
    model TEXT NOT NULL DEFAULT '', content TEXT NOT NULL, thinking_text TEXT NOT NULL DEFAULT '',
    content_length INTEGER NOT NULL DEFAULT 0,
    has_tool_use INTEGER NOT NULL DEFAULT 0, has_thinking INTEGER NOT NULL DEFAULT 0,
    is_sidechain INTEGER NOT NULL DEFAULT 0, is_compact_boundary INTEGER NOT NULL DEFAULT 0,
    input_tokens INTEGER, output_tokens INTEGER,
    cache_read_tokens INTEGER, cache_creation_tokens INTEGER,
    UNIQUE(session_id, ordinal)
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, ordinal);

CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY,
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    tool_use_id TEXT, tool_name TEXT NOT NULL, category TEXT NOT NULL,
    input_json TEXT, skill_name TEXT, subagent_session_id TEXT,
    started_at TEXT, completed_at TEXT, execution_time_ms INTEGER,
    success INTEGER, error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_tool_calls_session ON tool_calls(session_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_category ON tool_calls(category);

CREATE TABLE IF NOT EXISTS tool_result_events (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    tool_call_id INTEGER REFERENCES tool_calls(id) ON DELETE CASCADE,
    tool_use_id TEXT, source TEXT NOT NULL, status TEXT NOT NULL,
    content TEXT NOT NULL, content_length INTEGER NOT NULL DEFAULT 0, timestamp TEXT
);
CREATE INDEX IF NOT EXISTS idx_tool_results_session ON tool_result_events(session_id);

CREATE TABLE IF NOT EXISTS hook_events (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    hook_name TEXT NOT NULL, event_type TEXT NOT NULL, matcher TEXT,
    tool_name TEXT, decision TEXT, reason TEXT, execution_time_ms INTEGER,
    timestamp TEXT, event_data TEXT
);
CREATE INDEX IF NOT EXISTS idx_hook_events_session ON hook_events(session_id, timestamp);

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY, project TEXT NOT NULL, file_path TEXT NOT NULL,
    first_accessed_at TEXT, last_accessed_at TEXT,
    total_reads INTEGER NOT NULL DEFAULT 0, total_writes INTEGER NOT NULL DEFAULT 0,
    total_edits INTEGER NOT NULL DEFAULT 0,
    total_lines_added INTEGER NOT NULL DEFAULT 0, total_lines_removed INTEGER NOT NULL DEFAULT 0,
    UNIQUE(project, file_path)
);

CREATE TABLE IF NOT EXISTS file_operations (
    id INTEGER PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    tool_call_id INTEGER REFERENCES tool_calls(id) ON DELETE SET NULL,
    operation_type TEXT NOT NULL, lines_added INTEGER NOT NULL DEFAULT 0,
    lines_removed INTEGER NOT NULL DEFAULT 0, timestamp TEXT
);

CREATE TABLE IF NOT EXISTS processing_state (
    transcript_path TEXT PRIMARY KEY,
    last_processed_position INTEGER NOT NULL DEFAULT 0,
    last_processed_at TEXT, file_mtime INTEGER, file_hash TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS slash_commands (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL,
    command TEXT NOT NULL, args TEXT, timestamp TEXT
);
CREATE INDEX IF NOT EXISTS idx_slash_commands_command ON slash_commands(command, timestamp DESC);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    command TEXT NOT NULL, args TEXT, started_at TEXT NOT NULL, ended_at TEXT,
    final_step INTEGER, status TEXT NOT NULL DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS pipeline_steps (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    step_no INTEGER NOT NULL, name TEXT NOT NULL,
    started_at TEXT, ended_at TEXT, duration_ms INTEGER,
    blocked INTEGER NOT NULL DEFAULT 0, block_reason TEXT,
    tokens_in INTEGER NOT NULL DEFAULT 0, tokens_out INTEGER NOT NULL DEFAULT 0,
    UNIQUE(run_id, step_no)
);

CREATE TABLE IF NOT EXISTS agent_invocations (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    pipeline_step_id INTEGER REFERENCES pipeline_steps(id) ON DELETE SET NULL,
    agent_name TEXT NOT NULL, model TEXT,
    started_at TEXT, ended_at TEXT, duration_ms INTEGER,
    input_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0,
    success INTEGER, output_summary TEXT
);

CREATE TABLE IF NOT EXISTS enforcement_events (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    hook_event_id INTEGER REFERENCES hook_events(id) ON DELETE SET NULL,
    gate TEXT NOT NULL, decision TEXT NOT NULL, reason TEXT,
    bypassed INTEGER NOT NULL DEFAULT 0, timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_enforcement_gate ON enforcement_events(gate, decision, timestamp DESC);

CREATE TABLE IF NOT EXISTS session_signals (
    session_id TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    outcome TEXT NOT NULL DEFAULT 'unknown', outcome_confidence TEXT NOT NULL DEFAULT 'low',
    health_score INTEGER, health_grade TEXT,
    tool_failure_signal_count INTEGER NOT NULL DEFAULT 0,
    tool_retry_count INTEGER NOT NULL DEFAULT 0,
    edit_churn_count INTEGER NOT NULL DEFAULT 0,
    consecutive_failure_max INTEGER NOT NULL DEFAULT 0,
    compaction_count INTEGER NOT NULL DEFAULT 0,
    mid_task_compaction_count INTEGER NOT NULL DEFAULT 0,
    context_pressure_max REAL,
    pipeline_compliance_score INTEGER,
    enforcement_block_count INTEGER NOT NULL DEFAULT 0,
    enforcement_bypass_count INTEGER NOT NULL DEFAULT 0,
    pipeline_steps_completed INTEGER NOT NULL DEFAULT 0,
    test_gate_blocks INTEGER NOT NULL DEFAULT 0,
    anti_stub_blocks INTEGER NOT NULL DEFAULT 0,
    plan_critic_rounds INTEGER NOT NULL DEFAULT 0,
    last_computed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    description TEXT
);
INSERT OR IGNORE INTO schema_version(version, description)
VALUES (2, 'agentsview core + claude-code-analytics hooks + autonomous-dev pipeline telemetry');
"""


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA_SQL)
    return conn


# ---------------------------------------------------------------------------
# Per-event extraction
# ---------------------------------------------------------------------------

class SessionAccumulator:
    """Builds up the per-session row + child rows as we walk the JSONL."""

    def __init__(self, session_id: str, transcript_path: Path) -> None:
        self.session_id = session_id
        self.transcript_path = transcript_path
        self.cwd = ""
        self.git_branch = ""
        self.model = ""
        self.started_at: str | None = None
        self.ended_at: str | None = None
        self.first_user_prompt: str | None = None
        self.user_messages = 0
        self.assistant_messages = 0
        self.tool_calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cache_read_tokens = 0
        self.cache_creation_tokens = 0
        self.peak_context = 0
        self.malformed_lines = 0

        # Child rows queued for batch insert
        self.messages: list[dict] = []
        self.tool_call_rows: list[dict] = []
        self.tool_results: list[dict] = []
        self.slash_cmds: list[dict] = []
        self.file_ops: list[dict] = []        # (project, path, op_type, ts)
        self.hook_events: list[dict] = []     # best-effort backfill

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def handle_user(self, ev: dict, ordinal: int) -> None:
        self.user_messages += 1
        self.cwd = self.cwd or ev.get("cwd") or ""
        self.git_branch = self.git_branch or ev.get("gitBranch") or ""
        ts = ev.get("timestamp")
        if ts:
            self.started_at = self.started_at or ts
            self.ended_at = ts

        msg = ev.get("message") or {}
        content = msg.get("content")
        text = _coerce_text(content)
        is_sidechain = 1 if ev.get("isSidechain") else 0

        if self.first_user_prompt is None and text and not text.startswith("[tool_result"):
            self.first_user_prompt = text[:500]

        # Slash command extraction. Three sources:
        #   1. <command-name>/foo</command-name> + <command-args>...</command-args>
        #      (the canonical Claude Code slash invocation format)
        #   2. user text starting with '/' (rare — only when typed literally
        #      outside the slash menu)
        #   3. lone '/cmd' on first line of text
        cmd_match = _SLASH_NAME_RE.search(text)
        if cmd_match:
            raw_cmd = cmd_match.group(1).strip()
            cmd = raw_cmd if raw_cmd.startswith("/") else f"/{raw_cmd}"
            args_match = _SLASH_ARGS_RE.search(text)
            args = args_match.group(1).strip() if args_match else ""
            self.slash_cmds.append({
                "command": cmd,
                "args": args[:1024],
                "timestamp": ts,
                "ordinal": ordinal,
            })
        elif text.lstrip().startswith("/"):
            first_line = text.lstrip().split("\n", 1)[0]
            cmd, _, args = first_line.partition(" ")
            self.slash_cmds.append({
                "command": cmd,
                "args": args.strip()[:1024],
                "timestamp": ts,
                "ordinal": ordinal,
            })

        # tool_result blocks live inside user messages
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    self.tool_results.append({
                        "tool_use_id": block.get("tool_use_id"),
                        "status": "errored" if block.get("is_error") else "ok",
                        "content": _coerce_text(block.get("content"))[:65536],
                        "timestamp": ts,
                    })
                    # best-effort backfill of hook decision events
                    self._scan_for_hook_decisions(_coerce_text(block.get("content")), ts)

        self.messages.append({
            "ordinal": ordinal,
            "role": "user",
            "timestamp": ts,
            "model": "",
            "content": text,
            "thinking_text": "",
            "has_tool_use": 0,
            "has_thinking": 0,
            "is_sidechain": is_sidechain,
            "is_compact_boundary": 0,
            "input_tokens": None,
            "output_tokens": None,
            "cache_read_tokens": None,
            "cache_creation_tokens": None,
        })

    def handle_assistant(self, ev: dict, ordinal: int) -> None:
        self.assistant_messages += 1
        ts = ev.get("timestamp")
        if ts:
            self.started_at = self.started_at or ts
            self.ended_at = ts

        msg = ev.get("message") or {}
        self.model = msg.get("model") or self.model
        usage = msg.get("usage") or {}
        in_tok = int(usage.get("input_tokens") or 0)
        out_tok = int(usage.get("output_tokens") or 0)
        cr_tok = int(usage.get("cache_read_input_tokens") or 0)
        cc_tok = int(usage.get("cache_creation_input_tokens") or 0)
        self.input_tokens += in_tok
        self.output_tokens += out_tok
        self.cache_read_tokens += cr_tok
        self.cache_creation_tokens += cc_tok
        self.peak_context = max(self.peak_context, in_tok + cr_tok + cc_tok)

        text_parts: list[str] = []
        thinking_parts: list[str] = []
        has_tool_use = 0
        content = msg.get("content") or []
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "text":
                    text_parts.append(str(block.get("text", "")))
                elif btype == "thinking":
                    thinking_parts.append(str(block.get("thinking", "")))
                elif btype == "tool_use":
                    has_tool_use = 1
                    self.tool_calls += 1
                    name = block.get("name") or ""
                    self.tool_call_rows.append({
                        "ordinal": ordinal,
                        "tool_use_id": block.get("id"),
                        "tool_name": name,
                        "category": _categorise_tool(name, block.get("input")),
                        "input_json": json.dumps(block.get("input") or {})[:65536],
                        "skill_name": _extract_skill_name(name, block.get("input")),
                        "subagent_session_id": _extract_subagent_id(name, block.get("input")),
                        "started_at": ts,
                    })
                    # File-op fanout for Read/Write/Edit
                    self._fanout_file_op(name, block.get("input"), ts)

        self.messages.append({
            "ordinal": ordinal,
            "role": "assistant",
            "timestamp": ts,
            "model": self.model,
            "content": "\n".join(text_parts),
            "thinking_text": "\n".join(thinking_parts),
            "has_tool_use": has_tool_use,
            "has_thinking": 1 if thinking_parts else 0,
            "is_sidechain": 1 if ev.get("isSidechain") else 0,
            "is_compact_boundary": 0,  # detect from system events; TODO
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "cache_read_tokens": cr_tok,
            "cache_creation_tokens": cc_tok,
        })

    def handle_system(self, ev: dict, ordinal: int) -> None:
        # local_command + compact_boundary live here — attach to messages stream
        # so cross-references stay aligned by ordinal.
        ts = ev.get("timestamp")
        subtype = ev.get("subtype") or ""
        text = _coerce_text(ev.get("content"))
        is_compact = 1 if subtype == "compact_boundary" else 0
        self.messages.append({
            "ordinal": ordinal,
            "role": "system",
            "timestamp": ts,
            "model": "",
            "content": text[:8192],
            "thinking_text": "",
            "has_tool_use": 0,
            "has_thinking": 0,
            "is_sidechain": 1 if ev.get("isSidechain") else 0,
            "is_compact_boundary": is_compact,
            "input_tokens": None,
            "output_tokens": None,
            "cache_read_tokens": None,
            "cache_creation_tokens": None,
        })

    # ------------------------------------------------------------------
    # Best-effort extraction helpers
    # ------------------------------------------------------------------
    def _fanout_file_op(self, tool_name: str, tinput: Any, ts: str | None) -> None:
        if not isinstance(tinput, dict):
            return
        path = tinput.get("file_path") or tinput.get("path") or tinput.get("notebook_path")
        if not path:
            return
        op_map = {"Read": "read", "Write": "write", "Edit": "edit", "NotebookEdit": "edit"}
        op = op_map.get(tool_name)
        if not op:
            return
        self.file_ops.append({"path": str(path), "op_type": op, "timestamp": ts})

    def _scan_for_hook_decisions(self, text: str, ts: str | None) -> None:
        """Best-effort scan of tool_result content for hook block decisions.

        Older transcripts only have hook decisions visible if they were echoed
        into tool_result. New live archiver should write hook_events directly.
        """
        if not text:
            return
        lower = text.lower()
        if "permissiondecisionreason" in lower or '"decision":"block"' in lower:
            for gate, needles in ENFORCEMENT_GATES.items():
                if any(n.lower() in lower for n in needles):
                    self.hook_events.append({
                        "hook_name": "unknown_backfilled",
                        "event_type": "PreToolUse",
                        "matcher": None,
                        "tool_name": None,
                        "decision": "block",
                        "reason": text[:1024],
                        "execution_time_ms": None,
                        "timestamp": ts,
                        "event_data": json.dumps({"backfilled": True, "gate": gate}),
                    })
                    return


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _categorise_tool(name: str, _input: Any) -> str:
    if not name:
        return "other"
    if name.startswith("mcp__"):
        return "mcp"
    return TOOL_CATEGORIES.get(name, "other")


def _extract_skill_name(name: str, tinput: Any) -> str | None:
    if name == "Skill" and isinstance(tinput, dict):
        return tinput.get("skill")
    return None


def _extract_subagent_id(name: str, tinput: Any) -> str | None:
    # No reliable subagent session id at invocation time; live archiver
    # should correlate via SubagentStop hook. For backfill, leave NULL.
    return None


def _coerce_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for b in content:
            if isinstance(b, str):
                out.append(b)
            elif isinstance(b, dict):
                if b.get("type") == "text":
                    out.append(str(b.get("text", "")))
                elif b.get("type") == "tool_result":
                    out.append("[tool_result " + str(b.get("tool_use_id", ""))[:16] + "]")
        return "\n".join(out)
    return str(content)


def _project_from_cwd(cwd: str) -> str:
    if not cwd:
        return "unknown"
    return os.path.basename(cwd.rstrip("/")) or "unknown"


def _file_hash(path: Path, blocksize: int = 65536) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while chunk := f.read(blocksize):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Per-file replay
# ---------------------------------------------------------------------------

def replay_file(conn: sqlite3.Connection, path: Path) -> tuple[bool, str]:
    """Replay one JSONL transcript into v2 DB. Returns (changed, status)."""
    stat = path.stat()
    cur = conn.execute(
        "SELECT file_mtime, status FROM processing_state WHERE transcript_path = ?",
        (str(path),),
    ).fetchone()
    if cur and cur[0] == int(stat.st_mtime) and cur[1] == "done":
        return False, "skip"

    session_id = path.stem
    acc = SessionAccumulator(session_id, path)
    ordinal = 0

    with open(path, encoding="utf-8") as fp:
        for raw in fp:
            raw = raw.strip()
            if not raw:
                continue
            try:
                ev = json.loads(raw)
            except json.JSONDecodeError:
                acc.malformed_lines += 1
                continue

            t = ev.get("type")
            if t == "user":
                acc.handle_user(ev, ordinal); ordinal += 1
            elif t == "assistant":
                acc.handle_assistant(ev, ordinal); ordinal += 1
            elif t == "system":
                acc.handle_system(ev, ordinal); ordinal += 1
            # attachment / custom-title / file-history-snapshot / queue-operation
            # / last-prompt are intentionally ignored for now — add handlers as
            # specific telemetry questions arise.

    _flush_session(conn, acc, stat)
    return True, "replayed"


def _flush_session(conn: sqlite3.Connection, acc: SessionAccumulator, stat: os.stat_result) -> None:
    project = _project_from_cwd(acc.cwd)
    duration_ms = None
    if acc.started_at and acc.ended_at:
        from datetime import datetime
        try:
            duration_ms = int(
                (datetime.fromisoformat(acc.ended_at.replace("Z", "+00:00"))
                 - datetime.fromisoformat(acc.started_at.replace("Z", "+00:00"))).total_seconds() * 1000
            )
        except Exception:
            pass

    conn.execute(
        """INSERT OR REPLACE INTO sessions (
            id, project, machine, agent, cwd, git_branch, model,
            started_at, ended_at, duration_ms,
            message_count, user_message_count, assistant_message_count, tool_call_count,
            total_input_tokens, total_output_tokens, total_cache_read_tokens, total_cache_creation_tokens,
            peak_context_tokens, transcript_path, transcript_bytes, transcript_hash,
            parser_malformed_lines, first_user_prompt
        ) VALUES (?, ?, 'local', 'claude-code', ?, ?, ?,
                  ?, ?, ?,
                  ?, ?, ?, ?,
                  ?, ?, ?, ?,
                  ?, ?, ?, ?,
                  ?, ?)""",
        (
            acc.session_id, project, acc.cwd, acc.git_branch, acc.model,
            acc.started_at, acc.ended_at, duration_ms,
            len(acc.messages), acc.user_messages, acc.assistant_messages, acc.tool_calls,
            acc.input_tokens, acc.output_tokens, acc.cache_read_tokens, acc.cache_creation_tokens,
            acc.peak_context, str(acc.transcript_path), stat.st_size, _file_hash(acc.transcript_path),
            acc.malformed_lines, acc.first_user_prompt,
        ),
    )

    # Refresh child rows: simpler to delete-and-reinsert per session for backfill.
    for tbl in ("messages", "tool_calls", "tool_result_events",
                "slash_commands", "file_operations", "hook_events"):
        conn.execute(f"DELETE FROM {tbl} WHERE session_id = ?", (acc.session_id,))

    msg_id_by_ordinal: dict[int, int] = {}
    for m in acc.messages:
        cursor = conn.execute(
            """INSERT INTO messages (
                session_id, ordinal, role, timestamp, model, content, thinking_text,
                content_length, has_tool_use, has_thinking, is_sidechain, is_compact_boundary,
                input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                acc.session_id, m["ordinal"], m["role"], m["timestamp"], m["model"],
                m["content"], m["thinking_text"], len(m["content"]),
                m["has_tool_use"], m["has_thinking"], m["is_sidechain"], m["is_compact_boundary"],
                m["input_tokens"], m["output_tokens"], m["cache_read_tokens"], m["cache_creation_tokens"],
            ),
        )
        msg_id_by_ordinal[m["ordinal"]] = cursor.lastrowid

    tool_call_id_by_use_id: dict[str, int] = {}
    for tc in acc.tool_call_rows:
        msg_id = msg_id_by_ordinal.get(tc["ordinal"])
        if msg_id is None:
            continue
        cursor = conn.execute(
            """INSERT INTO tool_calls (
                message_id, session_id, tool_use_id, tool_name, category,
                input_json, skill_name, subagent_session_id, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (msg_id, acc.session_id, tc["tool_use_id"], tc["tool_name"], tc["category"],
             tc["input_json"], tc["skill_name"], tc["subagent_session_id"], tc["started_at"]),
        )
        if tc["tool_use_id"]:
            tool_call_id_by_use_id[tc["tool_use_id"]] = cursor.lastrowid

    for tr in acc.tool_results:
        conn.execute(
            """INSERT INTO tool_result_events (
                session_id, tool_call_id, tool_use_id, source, status, content, content_length, timestamp
            ) VALUES (?, ?, ?, 'tool', ?, ?, ?, ?)""",
            (acc.session_id,
             tool_call_id_by_use_id.get(tr["tool_use_id"]),
             tr["tool_use_id"], tr["status"], tr["content"], len(tr["content"]), tr["timestamp"]),
        )

    for sc in acc.slash_cmds:
        conn.execute(
            "INSERT INTO slash_commands (session_id, message_id, command, args, timestamp) VALUES (?, ?, ?, ?, ?)",
            (acc.session_id, msg_id_by_ordinal.get(sc["ordinal"]), sc["command"], sc["args"], sc["timestamp"]),
        )

    # Files & file_operations: upsert files row first, then op
    for fop in acc.file_ops:
        cur = conn.execute(
            "SELECT id FROM files WHERE project = ? AND file_path = ?",
            (project, fop["path"]),
        ).fetchone()
        if cur:
            file_id = cur[0]
            conn.execute(
                f"UPDATE files SET total_{fop['op_type']}s = total_{fop['op_type']}s + 1, "
                "last_accessed_at = ? WHERE id = ?",
                (fop["timestamp"], file_id),
            )
        else:
            cur2 = conn.execute(
                f"INSERT INTO files (project, file_path, first_accessed_at, last_accessed_at, total_{fop['op_type']}s) "
                "VALUES (?, ?, ?, ?, 1)",
                (project, fop["path"], fop["timestamp"], fop["timestamp"]),
            )
            file_id = cur2.lastrowid
        conn.execute(
            "INSERT INTO file_operations (file_id, session_id, operation_type, timestamp) VALUES (?, ?, ?, ?)",
            (file_id, acc.session_id, fop["op_type"], fop["timestamp"]),
        )

    for he in acc.hook_events:
        conn.execute(
            """INSERT INTO hook_events (
                session_id, hook_name, event_type, matcher, tool_name,
                decision, reason, execution_time_ms, timestamp, event_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (acc.session_id, he["hook_name"], he["event_type"], he["matcher"], he["tool_name"],
             he["decision"], he["reason"], he["execution_time_ms"], he["timestamp"], he["event_data"]),
        )

    conn.execute(
        """INSERT OR REPLACE INTO processing_state
           (transcript_path, last_processed_position, last_processed_at, file_mtime, file_hash, status)
           VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%fZ','now'), ?, ?, 'done')""",
        (str(acc.transcript_path), stat.st_size, int(stat.st_mtime), _file_hash(acc.transcript_path)),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_replay(args: argparse.Namespace) -> int:
    if args.dry_run:
        print(f"[dry-run] would replay JSONLs under {TRANSCRIPTS_DIR} into {V2_DB}")
        files = sorted(TRANSCRIPTS_DIR.rglob("*.jsonl"))
        if args.limit:
            files = files[: args.limit]
        for p in files:
            print(f"  {p}")
        return 0

    conn = open_db(V2_DB)
    files = sorted(TRANSCRIPTS_DIR.rglob("*.jsonl"))
    if args.limit:
        files = files[: args.limit]
    counts: dict[str, int] = defaultdict(int)
    for i, path in enumerate(files, 1):
        try:
            _, status = replay_file(conn, path)
            counts[status] += 1
            if i % 25 == 0:
                print(f"  {i}/{len(files)} replayed (replayed={counts['replayed']} skipped={counts['skip']})")
        except Exception as e:
            counts["error"] += 1
            print(f"  ERROR {path}: {e}", file=sys.stderr)
    conn.close()
    print(f"Done. {dict(counts)}")
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    if not V2_DB.exists():
        print(f"v2 DB not yet created at {V2_DB}")
        return 0
    conn = open_db(V2_DB)
    print(f"v2 DB: {V2_DB} ({V2_DB.stat().st_size:,} bytes)")
    for table in ("sessions", "messages", "tool_calls", "tool_result_events",
                  "slash_commands", "files", "file_operations", "hook_events",
                  "pipeline_runs", "pipeline_steps", "agent_invocations",
                  "enforcement_events", "session_signals"):
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:<22} {n:>8}")
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    """Cross-check v1 vs v2 session count and per-session token totals."""
    if not V1_DB.exists() or not V2_DB.exists():
        print("Need both v1 and v2 DBs to validate.")
        return 1
    v1 = sqlite3.connect(V1_DB); v2 = sqlite3.connect(V2_DB)
    v1_count = v1.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    v2_count = v2.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    print(f"sessions: v1={v1_count} v2={v2_count}")

    rows = v1.execute(
        "SELECT session_id, total_output_tokens FROM sessions ORDER BY total_output_tokens DESC LIMIT 10"
    ).fetchall()
    print("Top-10 by output tokens (v1 → v2 delta):")
    for sid, v1_out in rows:
        r = v2.execute("SELECT total_output_tokens FROM sessions WHERE id = ?", (sid,)).fetchone()
        v2_out = r[0] if r else None
        delta = (v2_out - v1_out) if v2_out is not None else None
        print(f"  {sid[:8]} v1={v1_out:>9} v2={v2_out!s:>9} Δ={delta}")
    return 0


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("replay")
    pr.add_argument("--limit", type=int, default=None)
    pr.add_argument("--dry-run", action="store_true")
    pr.set_defaults(func=cmd_replay)
    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("validate").set_defaults(func=cmd_validate)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
