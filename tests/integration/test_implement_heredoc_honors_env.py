"""
Integration tests verifying that all migrated heredoc sites in
commands/implement.md, commands/implement-batch.md, and
commands/implement-fix.md honor the PIPELINE_STATE_FILE env var
instead of using a hardcoded literal path.

These tests inspect the source files directly (content regex checks) —
no subprocess execution required, making them fast and deterministic.

Issues: #1041 #1048
"""

import re
import sys
from pathlib import Path

import pytest

# Repo root is 3 levels up from tests/integration/test_*.py
REPO_ROOT = Path(__file__).resolve().parents[2]

IMPLEMENT_MD = REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"
IMPLEMENT_BATCH_MD = (
    REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement-batch.md"
)
IMPLEMENT_FIX_MD = (
    REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement-fix.md"
)

# The env-var-aware form every migrated site must use.
# Matches both shell-expansion form and os.environ.get() form.
ENV_VAR_SHELL_RE = re.compile(
    r'\$\{PIPELINE_STATE_FILE:-/tmp/implement_pipeline_state\.json\}'
)
ENV_VAR_PYTHON_RE = re.compile(
    r"""os\.environ\.get\(['"]PIPELINE_STATE_FILE['"],\s*['"]/tmp/implement_pipeline_state\.json['"]\)"""
)

# Literal that must NOT appear in functional (non-comment, non-exclusion) code.
BARE_LITERAL = "/tmp/implement_pipeline_state.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _functional_lines(text: str) -> list[tuple[int, str]]:
    """Return (lineno, line) pairs that are functional code, not comment-only lines.

    Lines that start with '#' (after stripping) are treated as pure comments
    and excluded. Doc-comment lines inside triple-quoted strings are NOT
    excluded by this simple heuristic, but those are the security-guard/HMAC
    lines that we verify separately.
    """
    result = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if stripped.startswith("#"):
            continue
        result.append((lineno, raw))
    return result


def _has_env_var_form(line: str) -> bool:
    """Return True if line contains an env-var-aware reference."""
    return bool(ENV_VAR_SHELL_RE.search(line) or ENV_VAR_PYTHON_RE.search(line))


# ---------------------------------------------------------------------------
# Tests: implement.md
# ---------------------------------------------------------------------------


class TestImplementMdHereDocMigration:
    """Verify implement.md migrated heredoc sites use env-var form."""

    def test_file_exists(self) -> None:
        assert IMPLEMENT_MD.exists(), f"Expected {IMPLEMENT_MD} to exist"

    def test_heredoc_uses_pipeline_state_file_when_set(self) -> None:
        """Migrated write sites use os.environ.get('PIPELINE_STATE_FILE', ...)."""
        text = IMPLEMENT_MD.read_text()
        assert ENV_VAR_PYTHON_RE.search(
            text
        ), "implement.md must contain os.environ.get('PIPELINE_STATE_FILE', ...) write form"

    def test_heredoc_shell_rm_uses_env_var(self) -> None:
        """rm -f cleanup commands use ${PIPELINE_STATE_FILE:-...} form."""
        text = IMPLEMENT_MD.read_text()
        assert ENV_VAR_SHELL_RE.search(
            text
        ), "implement.md must contain ${PIPELINE_STATE_FILE:-/tmp/implement_pipeline_state.json} rm-f form"

    def test_sentinel_read_in_resolve_session_id_uses_env_var(self) -> None:
        """All _resolve_session_id() sentinel reads use os.environ.get form."""
        text = IMPLEMENT_MD.read_text()
        # Count env-var-aware Python sentinel reads
        python_matches = len(
            re.findall(
                r"""os\.environ\.get\(['"]PIPELINE_STATE_FILE['"]""",
                text,
            )
        )
        assert python_matches >= 3, (
            f"Expected at least 3 env-var-aware sentinel references in implement.md, "
            f"found {python_matches}"
        )

    def test_gc_call_present_before_run_id_generation(self) -> None:
        """GC call (_gc_stale_states) appears before RUN_ID is generated in STEP 0."""
        text = IMPLEMENT_MD.read_text()
        gc_pos = text.find("_gc_stale_states")
        run_id_pos = text.find("RUN_ID=\"$(python3")
        assert gc_pos != -1, "implement.md must call _gc_stale_states"
        assert run_id_pos != -1, "implement.md must set RUN_ID"
        assert gc_pos < run_id_pos, (
            "GC call must appear BEFORE RUN_ID generation in implement.md"
        )

    def test_no_bare_literal_in_functional_open_calls(self) -> None:
        """No bare (unguarded) /tmp/implement_pipeline_state.json in open() or rm -f calls.

        Lines that use the env-var-aware form (os.environ.get or shell expansion)
        are allowed — they contain the literal as a default fallback, which is
        the correct migrated pattern.
        """
        text = IMPLEMENT_MD.read_text()
        violations = []
        for lineno, line in _functional_lines(text):
            if BARE_LITERAL not in line:
                continue
            # If the line already uses the env-var-aware form, it's correctly migrated
            if _has_env_var_form(line):
                continue
            # Reject if the line contains open(), rm -f, or with open( WITHOUT env-var form
            if re.search(r"""(open\(|rm\s+-f\b)""", line):
                violations.append((lineno, line.strip()))
        assert violations == [], (
            "Found bare (unguarded) literal in open()/rm-f in implement.md:\n"
            + "\n".join(f"  L{ln}: {l}" for ln, l in violations)
        )

    def test_fallback_to_legacy_comment_preserved(self) -> None:
        """The fallback comment referencing the legacy path is preserved (docs)."""
        text = IMPLEMENT_MD.read_text()
        # The comment in the fallback chain doc should still reference the legacy path
        assert BARE_LITERAL in text, (
            "The legacy path should still appear in implement.md (in comments/docs)"
        )


# ---------------------------------------------------------------------------
# Tests: implement-batch.md
# ---------------------------------------------------------------------------


class TestImplementBatchMdMigration:
    """Verify implement-batch.md cleanup site uses env-var form."""

    def test_file_exists(self) -> None:
        assert IMPLEMENT_BATCH_MD.exists(), f"Expected {IMPLEMENT_BATCH_MD} to exist"

    def test_rm_cleanup_uses_env_var(self) -> None:
        """The rm -f cleanup in batch mode uses ${PIPELINE_STATE_FILE:-...} form."""
        text = IMPLEMENT_BATCH_MD.read_text()
        assert ENV_VAR_SHELL_RE.search(
            text
        ), "implement-batch.md must use ${PIPELINE_STATE_FILE:-/tmp/implement_pipeline_state.json}"

    def test_no_bare_literal_in_functional_rm_calls(self) -> None:
        """No bare (unguarded) literal in rm -f calls inside implement-batch.md."""
        text = IMPLEMENT_BATCH_MD.read_text()
        violations = []
        for lineno, line in _functional_lines(text):
            if BARE_LITERAL not in line:
                continue
            if _has_env_var_form(line):
                continue
            if re.search(r"rm\s+-f\b", line):
                violations.append((lineno, line.strip()))
        assert violations == [], (
            "Found bare (unguarded) literal in rm-f in implement-batch.md:\n"
            + "\n".join(f"  L{ln}: {l}" for ln, l in violations)
        )


# ---------------------------------------------------------------------------
# Tests: implement-fix.md
# ---------------------------------------------------------------------------


class TestImplementFixMdMigration:
    """Verify implement-fix.md migrated sites use env-var form."""

    def test_file_exists(self) -> None:
        assert IMPLEMENT_FIX_MD.exists(), f"Expected {IMPLEMENT_FIX_MD} to exist"

    def test_write_site_uses_env_var(self) -> None:
        """Pipeline state initialization write uses os.environ.get form."""
        text = IMPLEMENT_FIX_MD.read_text()
        assert ENV_VAR_PYTHON_RE.search(
            text
        ), "implement-fix.md must use os.environ.get('PIPELINE_STATE_FILE', ...) for write"

    def test_rm_cleanup_uses_env_var(self) -> None:
        """The rm -f cleanup uses ${PIPELINE_STATE_FILE:-...} form."""
        text = IMPLEMENT_FIX_MD.read_text()
        assert ENV_VAR_SHELL_RE.search(
            text
        ), "implement-fix.md must use ${PIPELINE_STATE_FILE:-/tmp/implement_pipeline_state.json}"

    def test_no_bare_literal_in_functional_open_or_rm_calls(self) -> None:
        """No bare (unguarded) literal in open() or rm -f calls in implement-fix.md."""
        text = IMPLEMENT_FIX_MD.read_text()
        violations = []
        for lineno, line in _functional_lines(text):
            if BARE_LITERAL not in line:
                continue
            if _has_env_var_form(line):
                continue
            if re.search(r"""(open\(|rm\s+-f\b)""", line):
                violations.append((lineno, line.strip()))
        assert violations == [], (
            "Found bare (unguarded) literal in open()/rm-f in implement-fix.md:\n"
            + "\n".join(f"  L{ln}: {l}" for ln, l in violations)
        )


# ---------------------------------------------------------------------------
# Tests: Scope-out preservation
# ---------------------------------------------------------------------------


class TestScopeOutPreservation:
    """Verify excluded sites remain unchanged (security guards, HMAC sentinel)."""

    def test_unified_pre_tool_security_guard_unchanged(self) -> None:
        """unified_pre_tool.py _check_bash_state_deletion still has literal path."""
        hook_path = (
            REPO_ROOT
            / "plugins"
            / "autonomous-dev"
            / "hooks"
            / "unified_pre_tool.py"
        )
        if not hook_path.exists():
            pytest.skip(f"Hook not found at {hook_path}")
        text = hook_path.read_text()
        # The guard function must still contain the literal string
        assert '"/tmp/implement_pipeline_state.json"' in text or (
            "'/tmp/implement_pipeline_state.json'" in text
        ), (
            "unified_pre_tool.py _check_bash_state_deletion must still use the "
            "literal path (scope-out per plan)"
        )

    def test_pipeline_state_legacy_sentinel_unchanged(self) -> None:
        """pipeline_state.py LEGACY_SENTINEL_PATH still points to literal path."""
        lib_path = (
            REPO_ROOT / "plugins" / "autonomous-dev" / "lib" / "pipeline_state.py"
        )
        if not lib_path.exists():
            pytest.skip(f"Lib not found at {lib_path}")
        text = lib_path.read_text()
        assert 'LEGACY_SENTINEL_PATH' in text, (
            "pipeline_state.py must still define LEGACY_SENTINEL_PATH"
        )
        assert '/tmp/implement_pipeline_state.json' in text, (
            "pipeline_state.py LEGACY_SENTINEL_PATH must still reference the literal path"
        )
