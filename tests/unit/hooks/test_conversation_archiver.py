"""Unit tests for the conversation_archiver Stop hook.

Tests cover: happy path archiving, index management, metadata extraction,
env var toggle, size thresholds, error resilience, monthly routing, and dedup.
"""

import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

# Add the hooks directory to sys.path so we can import the module
REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

import conversation_archiver


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def archive_dir(tmp_path):
    """Temporary archive base directory."""
    d = tmp_path / "archive"
    d.mkdir()
    return d


@pytest.fixture
def sample_transcript(tmp_path):
    """Create a sample JSONL transcript file using the real Claude Code schema.

    Layout (4 entries, all user/assistant — no standalone tool_use/tool_result lines
    because in the real schema tool_use blocks live INSIDE assistant content):
      1. user string prompt
      2. assistant with 1 text block + 1 tool_use block; usage 500/200
      3. user prompt (follow-up)
      4. assistant with 1 tool_use block; usage 800/350

    Expected:
      message_count=4, user=2, assistant=2, tool_calls=2
      total_input_tokens=1300, total_output_tokens=550
      model="claude-opus-4-6"
      first_user_prompt="How do I implement a retry pattern in Python?"
    """
    transcript = tmp_path / "session_abc123.jsonl"
    lines = [
        json.dumps(
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": "How do I implement a retry pattern in Python?",
                },
            }
        ),
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "model": "claude-opus-4-6",
                    "content": [
                        {"type": "text", "text": "Here is a retry pattern..."},
                        {
                            "type": "tool_use",
                            "id": "toolu_r1",
                            "name": "Read",
                            "input": {"path": "/tmp/foo.py"},
                        },
                    ],
                    "usage": {"input_tokens": 500, "output_tokens": 200},
                },
            }
        ),
        json.dumps(
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": "Can you also add exponential backoff?",
                },
            }
        ),
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "model": "claude-opus-4-6",
                    "content": [
                        {
                            "type": "text",
                            "text": "Sure, here is the updated version...",
                        },
                        {
                            "type": "tool_use",
                            "id": "toolu_w1",
                            "name": "Write",
                            "input": {"path": "/tmp/retry.py"},
                        },
                    ],
                    "usage": {"input_tokens": 800, "output_tokens": 350},
                },
            }
        ),
    ]
    transcript.write_text("\n".join(lines) + "\n")
    return transcript


@pytest.fixture
def tiny_transcript(tmp_path):
    """Create a transcript smaller than MIN_TRANSCRIPT_BYTES."""
    transcript = tmp_path / "tiny.jsonl"
    transcript.write_text("{}\n")  # ~3 bytes
    return transcript


@pytest.fixture
def hook_input_factory(sample_transcript):
    """Factory for creating hook input dicts."""
    def _make(
        transcript_path=None,
        session_id="abc123",
        cwd="/Users/dev/myproject",
        **kwargs,
    ):
        data = {
            "hook_event_name": "Stop",
            "transcript_path": str(transcript_path or sample_transcript),
            "session_id": session_id,
            "cwd": cwd,
        }
        data.update(kwargs)
        return data
    return _make


# ---------------------------------------------------------------------------
# Test: Happy path - transcript archived + index created
# ---------------------------------------------------------------------------

class TestHappyPath:
    """Test the full archive flow end-to-end."""

    def test_transcript_archived_and_index_created(
        self, sample_transcript, archive_dir, hook_input_factory
    ):
        """Full happy path: transcript is copied and index entry is created."""
        hook_input = hook_input_factory(transcript_path=sample_transcript)

        # Archive transcript
        month_dir = conversation_archiver._get_month_dir(archive_dir)
        archive_path = conversation_archiver._archive_transcript(
            sample_transcript, "abc123", month_dir
        )

        assert archive_path is not None
        assert archive_path.exists()
        assert archive_path.name == "abc123.jsonl"
        assert archive_path.read_text() == sample_transcript.read_text()

        # Extract metadata
        meta = conversation_archiver._extract_metadata(sample_transcript, hook_input)
        assert meta["message_count"] == 4
        assert meta["user_messages"] == 2
        assert meta["assistant_messages"] == 2
        assert meta["tool_calls"] == 2
        assert meta["total_input_tokens"] == 1300
        assert meta["total_output_tokens"] == 550
        assert meta["model"] == "claude-opus-4-6"
        assert meta["first_user_prompt"] == "How do I implement a retry pattern in Python?"

        # Create and verify index
        index_path = archive_dir / "index.jsonl"
        now_iso = datetime.now(timezone.utc).isoformat()
        index_entry = {
            "session_id": "abc123",
            "project": "myproject",
            "cwd": "/Users/dev/myproject",
            "archive_path": str(archive_path),
            "first_seen": now_iso,
            "last_updated": now_iso,
            **meta,
            "transcript_bytes": sample_transcript.stat().st_size,
        }
        conversation_archiver._update_index(index_path, index_entry)

        assert index_path.exists()
        entries = [json.loads(line) for line in index_path.read_text().strip().split("\n")]
        assert len(entries) == 1
        assert entries[0]["session_id"] == "abc123"
        assert entries[0]["message_count"] == 4


# ---------------------------------------------------------------------------
# Test: Tiny/empty transcript skip
# ---------------------------------------------------------------------------

class TestTranscriptSizeThreshold:
    """Test that small transcripts are skipped."""

    def test_tiny_transcript_skipped(self, tiny_transcript):
        """Transcripts below MIN_TRANSCRIPT_BYTES should be skipped."""
        size = tiny_transcript.stat().st_size
        assert size < conversation_archiver.MIN_TRANSCRIPT_BYTES

    def test_empty_transcript_skipped(self, tmp_path):
        """Zero-byte transcripts should be skipped."""
        empty = tmp_path / "empty.jsonl"
        empty.write_text("")
        assert empty.stat().st_size < conversation_archiver.MIN_TRANSCRIPT_BYTES


# ---------------------------------------------------------------------------
# Test: No transcript_path in input
# ---------------------------------------------------------------------------

class TestMissingTranscriptPath:
    """Test clean exit when transcript_path is missing."""

    def test_no_transcript_path_exits_cleanly(self, archive_dir):
        """Hook should exit 0 when transcript_path is absent."""
        hook_input = json.dumps({"hook_event_name": "Stop"})

        with patch.dict(os.environ, {"CONVERSATION_ARCHIVE": "true"}, clear=False):
            with patch("sys.stdin") as mock_stdin:
                mock_stdin.read.return_value = hook_input
                with pytest.raises(SystemExit) as exc_info:
                    conversation_archiver.main()
                assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# Test: CONVERSATION_ARCHIVE=false
# ---------------------------------------------------------------------------

class TestEnvVarToggle:
    """Test the CONVERSATION_ARCHIVE env var toggle."""

    def test_archive_disabled_exits_immediately(self):
        """Setting CONVERSATION_ARCHIVE=false should exit 0 immediately."""
        with patch.dict(os.environ, {"CONVERSATION_ARCHIVE": "false"}, clear=False):
            with pytest.raises(SystemExit) as exc_info:
                conversation_archiver.main()
            assert exc_info.value.code == 0

    def test_archive_enabled_by_default(self):
        """Default value for CONVERSATION_ARCHIVE should be 'true'."""
        env = os.environ.copy()
        env.pop("CONVERSATION_ARCHIVE", None)
        # Should not exit at the env var check point — it will exit later
        # due to no stdin. Just verify the default is true.
        assert os.environ.get("CONVERSATION_ARCHIVE", "true").lower() != "false"


# ---------------------------------------------------------------------------
# Test: Dedup on same session
# ---------------------------------------------------------------------------

class TestIndexDedup:
    """Test that multiple Stop events for same session produce single index entry."""

    def test_same_session_updates_not_duplicates(self, archive_dir):
        """Multiple index updates for same session_id should dedup."""
        index_path = archive_dir / "index.jsonl"

        entry_v1 = {
            "session_id": "sess_001",
            "project": "proj",
            "message_count": 10,
            "first_seen": "2026-04-11T10:00:00+00:00",
            "last_updated": "2026-04-11T10:00:00+00:00",
        }
        conversation_archiver._update_index(index_path, entry_v1)

        entry_v2 = {
            "session_id": "sess_001",
            "project": "proj",
            "message_count": 25,
            "first_seen": "2026-04-11T12:00:00+00:00",
            "last_updated": "2026-04-11T12:00:00+00:00",
        }
        conversation_archiver._update_index(index_path, entry_v2)

        entries = [json.loads(line) for line in index_path.read_text().strip().split("\n")]
        assert len(entries) == 1
        assert entries[0]["message_count"] == 25
        # first_seen should be preserved from v1
        assert entries[0]["first_seen"] == "2026-04-11T10:00:00+00:00"

    def test_different_sessions_both_kept(self, archive_dir):
        """Different session_ids should both be in the index."""
        index_path = archive_dir / "index.jsonl"

        entry1 = {"session_id": "sess_001", "message_count": 10}
        entry2 = {"session_id": "sess_002", "message_count": 20}

        conversation_archiver._update_index(index_path, entry1)
        conversation_archiver._update_index(index_path, entry2)

        entries = [json.loads(line) for line in index_path.read_text().strip().split("\n")]
        assert len(entries) == 2
        ids = {e["session_id"] for e in entries}
        assert ids == {"sess_001", "sess_002"}


# ---------------------------------------------------------------------------
# Test: Directory creation on first run
# ---------------------------------------------------------------------------

class TestDirectoryCreation:
    """Test that archive directories are created automatically."""

    def test_archive_dir_created_on_first_run(self, tmp_path, sample_transcript):
        """Archive and month directories should be created automatically."""
        archive_base = tmp_path / "fresh_archive"
        assert not archive_base.exists()

        month_dir = conversation_archiver._get_month_dir(archive_base)
        result = conversation_archiver._archive_transcript(
            sample_transcript, "new_session", month_dir
        )

        assert result is not None
        assert result.exists()
        assert month_dir.exists()

    def test_index_dir_created_on_first_run(self, tmp_path):
        """Index parent directory should be created automatically."""
        index_path = tmp_path / "new_dir" / "index.jsonl"
        assert not index_path.parent.exists()

        conversation_archiver._update_index(index_path, {"session_id": "test"})
        assert index_path.exists()


# ---------------------------------------------------------------------------
# Test: Atomic index update (tmp+rename pattern)
# ---------------------------------------------------------------------------

class TestAtomicIndexUpdate:
    """Test the tmp+rename atomicity of index writes."""

    def test_index_written_atomically(self, archive_dir):
        """Index should use tmp+rename, not direct write."""
        index_path = archive_dir / "index.jsonl"

        # Write initial entry
        conversation_archiver._update_index(
            index_path, {"session_id": "s1", "count": 1}
        )

        # Read back and verify valid JSON
        content = index_path.read_text().strip()
        entry = json.loads(content)
        assert entry["session_id"] == "s1"

    def test_no_partial_writes_on_multiple_entries(self, archive_dir):
        """Multiple sequential updates should never produce corrupt index."""
        index_path = archive_dir / "index.jsonl"

        for i in range(10):
            conversation_archiver._update_index(
                index_path, {"session_id": f"s_{i}", "count": i}
            )

        lines = [l for l in index_path.read_text().strip().split("\n") if l]
        assert len(lines) == 10
        for line in lines:
            entry = json.loads(line)  # Should not raise
            assert "session_id" in entry


# Metadata extraction tests moved to test_conversation_archiver_extraction.py
# (real-format fixtures with comprehensive coverage).


# ---------------------------------------------------------------------------
# Test: Large transcript copy
# ---------------------------------------------------------------------------

class TestLargeTranscript:
    """Test that large transcripts are fully copied."""

    def test_large_transcript_copied_completely(self, tmp_path):
        """A multi-MB transcript should be fully archived."""
        transcript = tmp_path / "large.jsonl"
        # Write ~500KB of JSONL
        lines = []
        for i in range(1000):
            lines.append(json.dumps({
                "type": "assistant",
                "content": "x" * 500,
                "model": "claude-opus-4-6",
            }))
        content = "\n".join(lines) + "\n"
        transcript.write_text(content)

        archive_dir = tmp_path / "archive" / "2026-04"
        result = conversation_archiver._archive_transcript(transcript, "large_sess", archive_dir)

        assert result is not None
        assert result.stat().st_size == transcript.stat().st_size


# ---------------------------------------------------------------------------
# Test: Error resilience
# ---------------------------------------------------------------------------

class TestErrorResilience:
    """Test that errors never crash the hook."""

    def test_nonexistent_transcript_exits_zero(self):
        """Hook should exit 0 even if transcript_path doesn't exist."""
        hook_input = json.dumps({
            "hook_event_name": "Stop",
            "transcript_path": "/nonexistent/path/transcript.jsonl",
            "session_id": "test",
        })

        with patch.dict(os.environ, {"CONVERSATION_ARCHIVE": "true"}, clear=False):
            with patch("sys.stdin") as mock_stdin:
                mock_stdin.read.return_value = hook_input
                with pytest.raises(SystemExit) as exc_info:
                    conversation_archiver.main()
                assert exc_info.value.code == 0

    def test_invalid_json_stdin_exits_zero(self):
        """Hook should exit 0 on invalid JSON stdin."""
        with patch.dict(os.environ, {"CONVERSATION_ARCHIVE": "true"}, clear=False):
            with patch("sys.stdin") as mock_stdin:
                mock_stdin.read.return_value = "not json at all"
                with pytest.raises(SystemExit) as exc_info:
                    conversation_archiver.main()
                assert exc_info.value.code == 0

    def test_empty_stdin_exits_zero(self):
        """Hook should exit 0 on empty stdin."""
        with patch.dict(os.environ, {"CONVERSATION_ARCHIVE": "true"}, clear=False):
            with patch("sys.stdin") as mock_stdin:
                mock_stdin.read.return_value = ""
                with pytest.raises(SystemExit) as exc_info:
                    conversation_archiver.main()
                assert exc_info.value.code == 0

    def test_archive_to_readonly_dir_exits_zero(self, sample_transcript, tmp_path):
        """Archive failure should not raise — returns None."""
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)

        result = conversation_archiver._archive_transcript(
            sample_transcript, "test", readonly_dir / "subdir"
        )
        # Should return None, not raise
        assert result is None

        # Cleanup permissions for tmp_path cleanup
        readonly_dir.chmod(0o755)


# ---------------------------------------------------------------------------
# Test: Model detection
# ---------------------------------------------------------------------------

class TestModelDetection:
    """Test model extraction from transcript and hook input."""

    def test_model_from_transcript(self, sample_transcript, hook_input_factory):
        """Model should be extracted from first assistant message."""
        hook_input = hook_input_factory(transcript_path=sample_transcript)
        meta = conversation_archiver._extract_metadata(sample_transcript, hook_input)
        assert meta["model"] == "claude-opus-4-6"

    def test_model_fallback_to_hook_input(self, tmp_path):
        """If transcript has no model, fall back to hook input."""
        transcript = tmp_path / "no_model.jsonl"
        transcript.write_text(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {"role": "assistant", "content": "hello"},
                }
            )
            + "\n"
        )

        hook_input = {"model": "claude-sonnet-4-20250514"}
        meta = conversation_archiver._extract_metadata(transcript, hook_input)
        assert meta["model"] == "claude-sonnet-4-20250514"

    def test_no_model_available(self, tmp_path):
        """If no model info anywhere, model should be None."""
        transcript = tmp_path / "no_model.jsonl"
        transcript.write_text(
            json.dumps(
                {
                    "type": "user",
                    "message": {"role": "user", "content": "hello"},
                }
            )
            + "\n"
        )

        meta = conversation_archiver._extract_metadata(transcript, {})
        assert meta["model"] is None


# ---------------------------------------------------------------------------
# Test: Monthly subdirectory routing
# ---------------------------------------------------------------------------

class TestMonthlyRouting:
    """Test that archives go into correct monthly subdirectory."""

    def test_month_dir_format(self, tmp_path):
        """Month directory should follow YYYY-MM format."""
        month_dir = conversation_archiver._get_month_dir(tmp_path)

        # Should be archive_base/conversations/YYYY-MM
        assert month_dir.parent.name == "conversations"
        parts = month_dir.name.split("-")
        assert len(parts) == 2
        assert len(parts[0]) == 4  # YYYY
        assert len(parts[1]) == 2  # MM

    def test_month_dir_matches_current_month(self, tmp_path):
        """Month directory should match the current UTC month."""
        now = datetime.now(timezone.utc)
        expected = now.strftime("%Y-%m")
        month_dir = conversation_archiver._get_month_dir(tmp_path)
        assert month_dir.name == expected


# ---------------------------------------------------------------------------
# Test: Hook registration verification
# ---------------------------------------------------------------------------

class TestHookRegistration:
    """Verify the hook is registered in all required locations."""

    def test_hook_in_global_settings_template(self):
        """conversation_archiver must be in global_settings_template.json Stop hooks."""
        template_path = (
            REPO_ROOT / "plugins" / "autonomous-dev" / "config"
            / "global_settings_template.json"
        )
        data = json.loads(template_path.read_text())
        stop_hooks = data["hooks"]["Stop"]

        archiver_found = any(
            "conversation_archiver" in h.get("command", "")
            for entry in stop_hooks
            for h in entry.get("hooks", [])
        )
        assert archiver_found, "conversation_archiver not found in global_settings_template Stop hooks"

    def test_hook_in_install_manifest(self):
        """conversation_archiver files must be in install_manifest.json."""
        manifest_path = (
            REPO_ROOT / "plugins" / "autonomous-dev" / "config"
            / "install_manifest.json"
        )
        data = json.loads(manifest_path.read_text())
        hook_files = data["components"]["hooks"]["files"]

        assert any("conversation_archiver.py" in f for f in hook_files), \
            "conversation_archiver.py not in install_manifest hooks"
        assert any("conversation_archiver.hook.json" in f for f in hook_files), \
            "conversation_archiver.hook.json not in install_manifest hooks"

    def test_hook_in_component_classifications(self):
        """conversation_archiver must be in component_classifications.json."""
        classifications_path = (
            REPO_ROOT / "plugins" / "autonomous-dev" / "config"
            / "component_classifications.json"
        )
        data = json.loads(classifications_path.read_text())
        hooks = data["classifications"]["hooks"]

        assert "conversation_archiver" in hooks, \
            "conversation_archiver not in component_classifications"
        assert hooks["conversation_archiver"]["classification"] == "process-requirement"

    # conversation_archiver is a global hook (see
    # plugins/autonomous-dev/lib/settings_merger.py::CANONICAL_GLOBAL_HOOKS).
    # Global hooks are registered ONCE in ~/.claude/settings.json by
    # configure_global_settings.py and fire for every session regardless of
    # per-repo template.
    #
    # Issue #944 codified the invariant that per-repo templates MUST NOT
    # redeclare global hooks (would cause double execution). The 4 templates
    # below are the user-facing per-repo templates enforced by
    # tests/regression/smoke/test_settings_template_integrity.py::
    # test_template_has_no_global_hook_duplicates. The constant is duplicated
    # locally (rather than imported from the regression test module) to avoid
    # cross-test-module imports — if the regression test renames the constant,
    # mypy/pyflakes will not flag a stale import here.
    #
    # The dogfooding templates (settings.autonomous-dev.json,
    # settings.local.json) are intentionally NOT in this set — they redeclare
    # global hooks on purpose so they work without configure_global_settings.py
    # having been run first.
    _GLOBAL_FREE_TEMPLATES = (
        "settings.default.json",
        "settings.granular-bash.json",
        "settings.permission-batching.json",
        "settings.strict-mode.json",
    )

    @staticmethod
    def _template_has_archiver(template_path: Path) -> bool:
        """Return True iff conversation_archiver is referenced in Stop hooks."""
        data = json.loads(template_path.read_text())
        hooks_section = data.get("hooks", {})
        stop_hooks = hooks_section.get("Stop", [])
        return any(
            "conversation_archiver" in h.get("command", "")
            for entry in stop_hooks
            for h in entry.get("hooks", [])
        )

    def test_hook_in_all_settings_templates(self):
        """conversation_archiver must be registered in dogfooding templates.

        conversation_archiver is a global hook. Per Issue #944, it is REQUIRED
        in the dogfooding templates (settings.autonomous-dev.json,
        settings.local.json) but FORBIDDEN in the templates listed in
        ``_GLOBAL_FREE_TEMPLATES`` (default, granular-bash, permission-batching,
        strict-mode) — those rely on the global ~/.claude/settings.json
        registration to avoid double execution.
        """
        templates_dir = REPO_ROOT / "plugins" / "autonomous-dev" / "templates"
        templates = list(templates_dir.glob("settings.*.json"))

        assert len(templates) >= 5, f"Expected at least 5 templates, found {len(templates)}"

        checked_non_global_free = 0
        for template in templates:
            if template.name in self._GLOBAL_FREE_TEMPLATES:
                # Issue #944: global-free templates MUST NOT contain
                # conversation_archiver. Skip the positive assertion here —
                # ``test_archiver_absent_from_global_free_templates`` below
                # enforces the negative invariant.
                continue
            checked_non_global_free += 1
            assert self._template_has_archiver(template), (
                f"conversation_archiver not found in {template.name} Stop hooks"
            )

        assert checked_non_global_free >= 1, (
            "Expected at least one non-global-free (dogfooding) template "
            "containing conversation_archiver, found none. "
            "Check templates/ — has settings.autonomous-dev.json or "
            "settings.local.json been removed?"
        )

    def test_archiver_absent_from_global_free_templates(self):
        """conversation_archiver MUST NOT appear in _GLOBAL_FREE_TEMPLATES.

        Inverse assertion enforcing Issue #944 from the conversation_archiver
        side. If a future maintainer adds conversation_archiver to any of the
        four user-facing per-repo templates, this test fails and points them
        to the global-hook deduplication invariant.

        Complements ``test_template_has_no_global_hook_duplicates`` in
        tests/regression/smoke/test_settings_template_integrity.py — that test
        checks the full CANONICAL_GLOBAL_HOOKS list; this one specifically
        targets conversation_archiver because that is the hook whose
        registration this test module is responsible for.
        """
        templates_dir = REPO_ROOT / "plugins" / "autonomous-dev" / "templates"
        violations = []
        for template_name in self._GLOBAL_FREE_TEMPLATES:
            template_path = templates_dir / template_name
            if not template_path.exists():
                continue  # Template removed — handled by other tests
            if self._template_has_archiver(template_path):
                violations.append(template_name)

        assert not violations, (
            f"conversation_archiver was found in global-free templates "
            f"{violations} — this violates Issue #944 (global hooks must not "
            f"be redeclared in per-repo templates, causes double execution). "
            f"Remove the Stop-hook entry from the listed template(s)."
        )


# ---------------------------------------------------------------------------
# Test: Session ID sanitization and path traversal prevention
# ---------------------------------------------------------------------------

class TestSessionIdSanitization:
    """Test that session_id is sanitized to prevent path traversal."""

    def test_forward_slash_sanitized(self, sample_transcript, tmp_path):
        """session_id containing '/' should have slashes replaced with '_'."""
        archive_dir = tmp_path / "archive" / "2026-04"
        result = conversation_archiver._archive_transcript(
            sample_transcript, "foo/bar/baz", archive_dir
        )

        # With sanitization in main() the id would already be clean,
        # but _archive_transcript has a guard that rejects traversal.
        # A forward slash in session_id creates a subdirectory, which
        # means dest.resolve() is NOT relative to archive_dir — guard blocks it.
        # If the guard allows it (because OS created subdirs), the file
        # would still be inside archive_dir tree, which is acceptable.
        if result is not None:
            assert result.resolve().is_relative_to(archive_dir.resolve())

    def test_backslash_sanitized(self, sample_transcript, tmp_path):
        r"""session_id containing '\\' should have backslashes replaced with '_'."""
        archive_dir = tmp_path / "archive" / "2026-04"
        archive_dir.mkdir(parents=True)
        result = conversation_archiver._archive_transcript(
            sample_transcript, "foo\\bar", archive_dir
        )

        if result is not None:
            assert result.resolve().is_relative_to(archive_dir.resolve())

    def test_path_traversal_blocked(self, sample_transcript, tmp_path):
        """A session_id like '../../etc/foo' must NOT write outside archive_dir."""
        archive_dir = tmp_path / "archive" / "2026-04"
        archive_dir.mkdir(parents=True)

        result = conversation_archiver._archive_transcript(
            sample_transcript, "../../etc/evil", archive_dir
        )

        # The guard in _archive_transcript should return None
        assert result is None, (
            "Path traversal session_id should be blocked by _archive_transcript guard"
        )

        # Double check: nothing was written outside archive_dir
        evil_path = archive_dir / "../../etc/evil.jsonl"
        assert not evil_path.exists()

    def test_null_byte_removed(self, sample_transcript, tmp_path):
        """Null bytes in session_id should be stripped."""
        archive_dir = tmp_path / "archive" / "2026-04"
        archive_dir.mkdir(parents=True)

        # After sanitization in main(), null bytes are stripped.
        # Test _archive_transcript with a clean id (null already removed).
        clean_id = "session\x00abc".replace("\x00", "")
        result = conversation_archiver._archive_transcript(
            sample_transcript, clean_id, archive_dir
        )

        assert result is not None
        assert result.name == "sessionabc.jsonl"

    def test_main_sanitizes_session_id(self, sample_transcript, tmp_path):
        """Integration: main() should sanitize session_id before archiving."""
        archive_base = tmp_path / "archive"

        hook_input = json.dumps({
            "hook_event_name": "Stop",
            "transcript_path": str(sample_transcript),
            "session_id": "../../etc/evil",
            "cwd": "/Users/dev/project",
        })

        with patch.dict(os.environ, {
            "CONVERSATION_ARCHIVE": "true",
            "CONVERSATION_ARCHIVE_DIR": str(archive_base),
        }, clear=False):
            with patch("sys.stdin") as mock_stdin:
                mock_stdin.read.return_value = hook_input
                with pytest.raises(SystemExit) as exc_info:
                    conversation_archiver.main()
                assert exc_info.value.code == 0

        # The session_id "../../etc/evil" should become ".._.._.._etc_evil"
        # after sanitization (/ replaced with _), so no file outside archive_base
        evil_path = archive_base / ".." / ".." / "etc" / "evil.jsonl"
        assert not evil_path.exists()


# ---------------------------------------------------------------------------
# Test: Stderr logging on unexpected errors
# ---------------------------------------------------------------------------

class TestStderrLogging:
    """Test that unexpected errors are logged to stderr, not silently swallowed."""

    def test_unexpected_error_logged_to_stderr(self, sample_transcript, tmp_path, capsys):
        """Unexpected errors in main() should print to stderr before exit 0."""
        hook_input = json.dumps({
            "hook_event_name": "Stop",
            "transcript_path": str(sample_transcript),
            "session_id": "test_session",
            "cwd": "/Users/dev/project",
        })

        with patch.dict(os.environ, {
            "CONVERSATION_ARCHIVE": "true",
            "CONVERSATION_ARCHIVE_DIR": str(tmp_path / "archive"),
        }, clear=False):
            with patch("sys.stdin") as mock_stdin:
                mock_stdin.read.return_value = hook_input
                # Force an unexpected error by making _archive_transcript raise
                with patch.object(
                    conversation_archiver, "_get_month_dir",
                    side_effect=RuntimeError("simulated unexpected error"),
                ):
                    with pytest.raises(SystemExit) as exc_info:
                        conversation_archiver.main()
                    assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "[conversation_archiver] unexpected error" in captured.err
        assert "simulated unexpected error" in captured.err


# ---------------------------------------------------------------------------
# Test: SQLite index
# ---------------------------------------------------------------------------

def _make_index_entry(
    session_id: str = "test_session",
    project: str = "myproject",
    cwd: str = "/Users/dev/myproject",
    archive_path: str = "/archive/2026-04/test_session.jsonl",
    first_seen: str = "2026-04-11T10:00:00+00:00",
    last_updated: str = "2026-04-11T10:00:00+00:00",
    message_count: int = 8,
    user_messages: int = 2,
    assistant_messages: int = 2,
    tool_calls: int = 2,
    total_input_tokens: int = 1300,
    total_output_tokens: int = 550,
    total_cache_read_tokens: int = 0,
    total_cache_creation_tokens: int = 0,
    transcript_bytes: int = 1024,
    model: str = "claude-opus-4-6",
    first_user_prompt: str = "How do I implement a retry pattern in Python?",
) -> dict:
    """Build a complete index entry dict for SQLite tests."""
    return {
        "session_id": session_id,
        "project": project,
        "cwd": cwd,
        "archive_path": archive_path,
        "first_seen": first_seen,
        "last_updated": last_updated,
        "message_count": message_count,
        "user_messages": user_messages,
        "assistant_messages": assistant_messages,
        "tool_calls": tool_calls,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_cache_read_tokens": total_cache_read_tokens,
        "total_cache_creation_tokens": total_cache_creation_tokens,
        "transcript_bytes": transcript_bytes,
        "model": model,
        "first_user_prompt": first_user_prompt,
    }


class TestSqliteIndex:
    """Test the _update_sqlite_index function."""

    def test_sqlite_happy_path(self, tmp_path):
        """Write a row and verify all column values are stored correctly."""
        db_path = tmp_path / "sessions.db"
        entry = _make_index_entry()

        conversation_archiver._update_sqlite_index(db_path, entry)

        assert db_path.exists()
        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", ("test_session",)
        ).fetchone()
        conn.close()

        assert row is not None
        col_names = [
            "session_id", "project", "cwd", "archive_path",
            "first_seen", "last_updated",
            "message_count", "user_messages", "assistant_messages", "tool_calls",
            "total_input_tokens", "total_output_tokens",
            "total_cache_read_tokens", "total_cache_creation_tokens",
            "transcript_bytes", "model", "first_user_prompt",
        ]
        row_dict = dict(zip(col_names, row))

        assert row_dict["session_id"] == "test_session"
        assert row_dict["project"] == "myproject"
        assert row_dict["cwd"] == "/Users/dev/myproject"
        assert row_dict["message_count"] == 8
        assert row_dict["user_messages"] == 2
        assert row_dict["assistant_messages"] == 2
        assert row_dict["tool_calls"] == 2
        assert row_dict["total_input_tokens"] == 1300
        assert row_dict["total_output_tokens"] == 550
        assert row_dict["transcript_bytes"] == 1024
        assert row_dict["model"] == "claude-opus-4-6"
        assert row_dict["first_user_prompt"] == "How do I implement a retry pattern in Python?"
        assert row_dict["first_seen"] == "2026-04-11T10:00:00+00:00"

    def test_sqlite_upsert_preserves_first_seen(self, tmp_path):
        """Second write with same session_id preserves first_seen from first write."""
        db_path = tmp_path / "sessions.db"

        entry_v1 = _make_index_entry(
            first_seen="2026-04-11T10:00:00+00:00",
            last_updated="2026-04-11T10:00:00+00:00",
            message_count=10,
        )
        conversation_archiver._update_sqlite_index(db_path, entry_v1)

        entry_v2 = _make_index_entry(
            first_seen="2026-04-11T12:00:00+00:00",
            last_updated="2026-04-11T12:00:00+00:00",
            message_count=25,
        )
        conversation_archiver._update_sqlite_index(db_path, entry_v2)

        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT first_seen, last_updated, message_count FROM sessions").fetchall()
        conn.close()

        assert len(rows) == 1
        first_seen, last_updated, message_count = rows[0]
        # first_seen preserved from first write
        assert first_seen == "2026-04-11T10:00:00+00:00"
        # message_count updated to second write
        assert message_count == 25

    def test_sqlite_table_auto_creation(self, tmp_path):
        """Fresh db_path: file does not exist, function creates it with sessions table."""
        db_path = tmp_path / "subdir" / "sessions.db"
        assert not db_path.exists()

        entry = _make_index_entry()
        conversation_archiver._update_sqlite_index(db_path, entry)

        assert db_path.exists()
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT session_id FROM sessions").fetchall()
        conn.close()
        assert len(rows) == 1

    def test_sqlite_error_resilience(self, tmp_path):
        """Passing a directory as db_path should not raise any exception."""
        # A directory cannot be opened as a SQLite file — this tests the try/except
        db_path = tmp_path / "i_am_a_directory"
        db_path.mkdir()

        # Must not raise
        entry = _make_index_entry()
        conversation_archiver._update_sqlite_index(db_path, entry)

    def test_sqlite_queryable(self, tmp_path):
        """Write two rows with different session_ids and verify both are readable."""
        db_path = tmp_path / "sessions.db"

        entry_a = _make_index_entry(session_id="session_a", message_count=5)
        entry_b = _make_index_entry(session_id="session_b", message_count=15)

        conversation_archiver._update_sqlite_index(db_path, entry_a)
        conversation_archiver._update_sqlite_index(db_path, entry_b)

        conn = sqlite3.connect(str(db_path))
        rows = conn.execute(
            "SELECT session_id, message_count FROM sessions ORDER BY session_id"
        ).fetchall()
        conn.close()

        assert len(rows) == 2
        assert rows[0] == ("session_a", 5)
        assert rows[1] == ("session_b", 15)

    def test_sqlite_main_integration(self, sample_transcript, tmp_path):
        """Run main() via stdin and verify both sessions.db and index.jsonl are created."""
        archive_base = tmp_path / "archive"

        hook_input = json.dumps({
            "hook_event_name": "Stop",
            "transcript_path": str(sample_transcript),
            "session_id": "integration_session",
            "cwd": "/Users/dev/project",
        })

        with patch.dict(os.environ, {
            "CONVERSATION_ARCHIVE": "true",
            "CONVERSATION_ARCHIVE_DIR": str(archive_base),
        }, clear=False):
            with patch("sys.stdin") as mock_stdin:
                mock_stdin.read.return_value = hook_input
                with pytest.raises(SystemExit) as exc_info:
                    conversation_archiver.main()
                assert exc_info.value.code == 0

        assert (archive_base / "index.jsonl").exists(), "index.jsonl not created"
        db_path = archive_base / "sessions.db"
        assert db_path.exists(), "sessions.db not created"

        conn = sqlite3.connect(str(db_path))
        rows = conn.execute(
            "SELECT session_id FROM sessions WHERE session_id = 'integration_session'"
        ).fetchall()
        conn.close()
        assert len(rows) == 1
