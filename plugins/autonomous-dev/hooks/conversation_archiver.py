#!/usr/bin/env python3
"""
Conversation Archiver - Archive full conversation transcripts for long-term analytics.

Stop hook that copies conversation transcripts to ~/.claude/archive/ with
queryable JSONL and SQLite indexes for session analytics, DuckDB queries, and
long-term pattern analysis.

Hook: Stop (after every assistant response)

Captures:
    - Full transcript copy in monthly subdirectories
    - Session metadata index (message counts, token stats, model, first prompt)

Archive location: ~/.claude/archive/conversations/{YYYY-MM}/{session_id}.jsonl
Index location: ~/.claude/archive/index.jsonl
SQLite index: ~/.claude/archive/sessions.db

Environment Variables:
    CONVERSATION_ARCHIVE=true/false (default: true)
        true  = archive transcripts and update index
        false = disabled
    CLAUDE_SESSION_ID - Session identifier (provided by Claude Code)

Exit codes:
    0: Always (non-blocking hook)
"""

# Issue #953: Hook safety — wrap main() with safe_main so hook crashes never
# block Claude Code. The wrap is purely an outer safety net; success-path
# return codes are preserved (int return → exit code, sys.exit → propagated).
import sys as _sys_953  # alias to avoid colliding with hook-local sys imports
from pathlib import Path as _Path_953

_hook_dir_953 = _Path_953(__file__).resolve().parent
for _candidate_lib_953 in (
    _hook_dir_953.parent / "lib",                    # plugins/autonomous-dev/lib (dev)
    _hook_dir_953.parent.parent / "lib",             # ~/.claude/lib (installed)
    _Path_953.home() / ".claude" / "plugins" / "autonomous-dev" / "lib",  # marketplace
):
    if _candidate_lib_953.exists() and str(_candidate_lib_953) not in _sys_953.path:
        _sys_953.path.insert(0, str(_candidate_lib_953))

try:
    from hook_safety import safe_main as _safe_main_953
except ImportError:
    # Fallback: no-op wrapper so hooks still load if hook_safety is missing.
    def _safe_main_953(_fn):
        _result = _fn()
        if isinstance(_result, int):
            _sys_953.exit(_result)
        _sys_953.exit(0)


import fcntl
import json
import os
import sqlite3
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# Minimum transcript size to archive (skip empty/trivial transcripts)
MIN_TRANSCRIPT_BYTES = 50

# Maximum length for first_user_prompt in index
MAX_PROMPT_LENGTH = 200

# Archive base directory
ARCHIVE_BASE = Path.home() / ".claude" / "archive"


def _get_month_dir(archive_base: Path) -> Path:
    """Return monthly subdirectory path for current month.

    Args:
        archive_base: Base archive directory.

    Returns:
        Path to the monthly conversations subdirectory (e.g., archive/conversations/2026-04/).
    """
    now = datetime.now(timezone.utc)
    month_str = now.strftime("%Y-%m")
    return archive_base / "conversations" / month_str


def _extract_metadata(
    transcript_path: Path,
    hook_input: dict[str, Any],
) -> dict[str, Any]:
    """Parse transcript JSONL to extract session metadata.

    Reads the canonical Claude Code transcript schema where each line is a JSON
    object whose top-level ``type`` field acts as the message discriminator
    (``user``/``assistant`` vs noise like ``attachment``/``permission-mode``).
    The actual message payload (role, model, content, usage) is nested under
    ``entry["message"]``.

    Args:
        transcript_path: Path to the transcript JSONL file.
        hook_input: The hook input JSON from stdin.

    Returns:
        Dict with message counts, token stats (including cache tokens), model,
        and first user prompt.
    """
    message_count = 0
    user_messages = 0
    assistant_messages = 0
    tool_calls = 0
    total_input_tokens = 0
    total_output_tokens = 0
    total_cache_read_tokens = 0
    total_cache_creation_tokens = 0
    model: Optional[str] = None
    first_user_prompt: Optional[str] = None

    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    # Malformed JSONL lines skipped (defense in depth against partial writes)
                    continue

                entry_type = entry.get("type")

                # Only user/assistant entries are conversation messages. Skip noise
                # (attachment, permission-mode, file-history-snapshot, last-prompt,
                # summary, system) without incrementing message_count.
                if entry_type not in ("user", "assistant"):
                    continue

                message_count += 1

                raw_msg = entry.get("message")
                msg = raw_msg if isinstance(raw_msg, dict) else {}

                if entry_type == "user":
                    user_messages += 1
                    if first_user_prompt is None:
                        content = msg.get("content")
                        if isinstance(content, str):
                            first_user_prompt = content[:MAX_PROMPT_LENGTH]
                        elif isinstance(content, list):
                            for block in content:
                                if (
                                    isinstance(block, dict)
                                    and block.get("type") == "text"
                                ):
                                    first_user_prompt = block.get("text", "")[
                                        :MAX_PROMPT_LENGTH
                                    ]
                                    break

                else:  # entry_type == "assistant"
                    assistant_messages += 1

                    if model is None and msg.get("model"):
                        model = msg.get("model")

                    raw_usage = msg.get("usage")
                    usage = raw_usage if isinstance(raw_usage, dict) else {}
                    total_input_tokens += int(usage.get("input_tokens") or 0)
                    total_output_tokens += int(usage.get("output_tokens") or 0)
                    total_cache_read_tokens += int(
                        usage.get("cache_read_input_tokens") or 0
                    )
                    total_cache_creation_tokens += int(
                        usage.get("cache_creation_input_tokens") or 0
                    )

                    # tool_use blocks live inside assistant message content
                    content = msg.get("content")
                    if isinstance(content, list):
                        for block in content:
                            if (
                                isinstance(block, dict)
                                and block.get("type") == "tool_use"
                            ):
                                tool_calls += 1

    except (OSError, IOError):
        pass

    # Fallback: try to get model from hook input
    if model is None:
        model = hook_input.get("model", None)

    return {
        "message_count": message_count,
        "user_messages": user_messages,
        "assistant_messages": assistant_messages,
        "tool_calls": tool_calls,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_cache_read_tokens": total_cache_read_tokens,
        "total_cache_creation_tokens": total_cache_creation_tokens,
        "model": model,
        "first_user_prompt": first_user_prompt,
    }


def _archive_transcript(
    transcript_path: Path,
    session_id: str,
    archive_dir: Path,
) -> Optional[Path]:
    """Copy transcript to monthly archive subdirectory.

    Args:
        transcript_path: Source transcript file path.
        session_id: Session identifier for the filename.
        archive_dir: Monthly subdirectory to archive into.

    Returns:
        Path to the archived file, or None on failure.
    """
    try:
        archive_dir.mkdir(parents=True, exist_ok=True)
        dest = archive_dir / f"{session_id}.jsonl"
        # Guard: refuse to write outside archive_dir (defense in depth)
        if not dest.resolve().is_relative_to(archive_dir.resolve()):
            return None
        shutil.copy2(str(transcript_path), str(dest))
        return dest
    except (OSError, IOError):
        return None


def _update_index(
    index_path: Path,
    metadata: dict[str, Any],
) -> None:
    """Atomic read-modify-write of index.jsonl with dedup by session_id.

    Uses fcntl.flock() for concurrent session safety. Reads existing entries,
    replaces any entry with the same session_id, then writes via tmp+rename.

    Args:
        index_path: Path to the index.jsonl file.
        metadata: Session metadata dict to upsert.
    """
    index_path.parent.mkdir(parents=True, exist_ok=True)

    # Use a lock file for concurrent access
    lock_path = index_path.with_suffix(".lock")

    try:
        lock_fd = open(lock_path, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        try:
            # Read existing entries
            entries: list[dict[str, Any]] = []
            if index_path.exists():
                with open(index_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            entries.append(entry)
                        except json.JSONDecodeError:
                            continue

            # Dedup: replace existing entry for this session_id
            session_id = metadata.get("session_id")
            new_entries = []
            replaced = False
            for entry in entries:
                if entry.get("session_id") == session_id:
                    # Preserve first_seen from existing entry
                    if "first_seen" in entry:
                        metadata["first_seen"] = entry["first_seen"]
                    new_entries.append(metadata)
                    replaced = True
                else:
                    new_entries.append(entry)

            if not replaced:
                new_entries.append(metadata)

            # Atomic write: tmp file + rename
            fd, tmp_path = tempfile.mkstemp(
                dir=str(index_path.parent),
                suffix=".tmp",
                prefix="index_",
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as tmp_f:
                    for entry in new_entries:
                        tmp_f.write(json.dumps(entry, separators=(",", ":")) + "\n")
                os.replace(tmp_path, str(index_path))
            except Exception:
                # Clean up temp file on failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
            # Clean up lock file (best effort)
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass

    except (OSError, IOError):
        pass


def _update_sqlite_index(db_path: Path, metadata: dict[str, Any]) -> None:
    """Write session metadata to SQLite index for fast queryable access.

    Creates the sessions table on first use and idempotently migrates legacy
    databases to include the cache-token columns. Upserts the row identified
    by session_id, preserving the original first_seen value from a previous
    write so repeated Stop events do not reset the session start time.

    Args:
        db_path: Path to the SQLite database file (e.g. archive/sessions.db).
        metadata: Session metadata dict containing all 17 column values
            (15 legacy + total_cache_read_tokens + total_cache_creation_tokens).
    """
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    project TEXT,
                    cwd TEXT,
                    archive_path TEXT,
                    first_seen TEXT,
                    last_updated TEXT,
                    message_count INTEGER,
                    user_messages INTEGER,
                    assistant_messages INTEGER,
                    tool_calls INTEGER,
                    total_input_tokens INTEGER,
                    total_output_tokens INTEGER,
                    total_cache_read_tokens INTEGER,
                    total_cache_creation_tokens INTEGER,
                    transcript_bytes INTEGER,
                    model TEXT,
                    first_user_prompt TEXT
                )
                """
            )

            # Idempotent migration for databases created before the cache-token
            # columns were added. Running this block repeatedly is safe.
            existing_cols = {
                row[1]
                for row in conn.execute("PRAGMA table_info(sessions)").fetchall()
            }
            for col in ("total_cache_read_tokens", "total_cache_creation_tokens"):
                if col not in existing_cols:
                    conn.execute(f"ALTER TABLE sessions ADD COLUMN {col} INTEGER")

            # Preserve first_seen from an existing row
            session_id = metadata.get("session_id")
            row = conn.execute(
                "SELECT first_seen FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            first_seen = row[0] if row else metadata.get("first_seen")

            conn.execute(
                """
                INSERT OR REPLACE INTO sessions (
                    session_id, project, cwd, archive_path,
                    first_seen, last_updated,
                    message_count, user_messages, assistant_messages, tool_calls,
                    total_input_tokens, total_output_tokens,
                    total_cache_read_tokens, total_cache_creation_tokens,
                    transcript_bytes, model, first_user_prompt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    metadata.get("project"),
                    metadata.get("cwd"),
                    metadata.get("archive_path"),
                    first_seen,
                    metadata.get("last_updated"),
                    metadata.get("message_count"),
                    metadata.get("user_messages"),
                    metadata.get("assistant_messages"),
                    metadata.get("tool_calls"),
                    metadata.get("total_input_tokens"),
                    metadata.get("total_output_tokens"),
                    metadata.get("total_cache_read_tokens"),
                    metadata.get("total_cache_creation_tokens"),
                    metadata.get("transcript_bytes"),
                    metadata.get("model"),
                    metadata.get("first_user_prompt"),
                ),
            )
    except Exception:
        pass


def main() -> None:
    """Entry point: read stdin, check env, orchestrate archive and index."""
    # Env var toggle (default: true)
    archive_enabled = os.environ.get("CONVERSATION_ARCHIVE", "true").lower()
    if archive_enabled == "false":
        sys.exit(0)

    try:
        # Read hook input from stdin
        raw = sys.stdin.read().strip()
        if not raw:
            sys.exit(0)

        try:
            hook_input = json.loads(raw)
        except json.JSONDecodeError:
            sys.exit(0)

        # Get transcript path from hook input
        transcript_path_str = hook_input.get("transcript_path")
        if not transcript_path_str:
            sys.exit(0)

        transcript_path = Path(transcript_path_str)
        if not transcript_path.exists():
            sys.exit(0)

        # Skip tiny/empty transcripts
        try:
            transcript_size = transcript_path.stat().st_size
        except OSError:
            sys.exit(0)

        if transcript_size < MIN_TRANSCRIPT_BYTES:
            sys.exit(0)

        # Derive session_id (from hook input or transcript filename)
        session_id = hook_input.get("session_id") or os.environ.get("CLAUDE_SESSION_ID")
        if not session_id:
            # Fallback: use transcript filename stem
            session_id = transcript_path.stem

        # Sanitize session_id to prevent path traversal
        session_id = session_id.replace("/", "_").replace("\\", "_").replace("\x00", "")

        # Determine archive directory
        archive_base = Path(os.environ.get("CONVERSATION_ARCHIVE_DIR", str(ARCHIVE_BASE)))
        month_dir = _get_month_dir(archive_base)

        # Archive the transcript
        archive_path = _archive_transcript(transcript_path, session_id, month_dir)
        if archive_path is None:
            sys.exit(0)

        # Extract metadata from transcript
        meta = _extract_metadata(transcript_path, hook_input)

        # Build index entry
        now_iso = datetime.now(timezone.utc).isoformat()
        cwd = hook_input.get("cwd", os.getcwd())
        project = Path(cwd).name if cwd else "unknown"

        index_entry = {
            "session_id": session_id,
            "project": project,
            "cwd": cwd,
            "archive_path": str(archive_path),
            "first_seen": now_iso,
            "last_updated": now_iso,
            "message_count": meta["message_count"],
            "user_messages": meta["user_messages"],
            "assistant_messages": meta["assistant_messages"],
            "tool_calls": meta["tool_calls"],
            "total_input_tokens": meta["total_input_tokens"],
            "total_output_tokens": meta["total_output_tokens"],
            "total_cache_read_tokens": meta["total_cache_read_tokens"],
            "total_cache_creation_tokens": meta["total_cache_creation_tokens"],
            "transcript_bytes": transcript_size,
            "model": meta["model"],
            "first_user_prompt": meta["first_user_prompt"],
        }

        # Update index
        index_path = archive_base / "index.jsonl"
        _update_index(index_path, index_entry)
        _update_sqlite_index(archive_base / "sessions.db", index_entry)

    except Exception as e:
        # Non-blocking: never crash Claude Code
        # Log to stderr so operators can detect unexpected failures
        import traceback

        print(f"[conversation_archiver] unexpected error: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

    sys.exit(0)



# Issue #1012 (W0): Per-hook timing telemetry. Best-effort, never raises.
# Records duration + decision_shape to ~/.claude/logs/hook_timings_YYYY-MM-DD.jsonl.
try:
    from hook_timing import HookTimer  # type: ignore[import-not-found]
except ImportError:
    # Fallback: no-op stub so hooks keep working if hook_timing is missing.
    class HookTimer:  # type: ignore[no-redef]
        def __init__(self, *_, **__): pass
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def set_decision_shape(self, _): pass

_HOOK_TIMER_NAME = _Path_953(__file__).name


def _timed_main():  # type: ignore[no-redef]
    with HookTimer(_HOOK_TIMER_NAME):
        return main()

if __name__ == "__main__":
    _safe_main_953(_timed_main)
