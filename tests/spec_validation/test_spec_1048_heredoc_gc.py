"""Spec-blind validation for Issue #1048: heredoc env-var migration + stale GC.

Tests derived ONLY from the acceptance criteria — no knowledge of how the
implementation was structured.

Acceptance criteria:
  AC1. implement.md heredoc sites use ${PIPELINE_STATE_FILE:-/tmp/implement_pipeline_state.json}
  AC2. implement-batch.md and implement-fix.md equivalents migrated
  AC3. rm -f cleanup commands use the env-var form
  AC4. _gc_stale_states() removes state files >2× TTL (default 7200s) and orphaned lockfiles
  AC5. Security guards in unified_pre_tool.py NOT migrated (preserves literal path)
  AC6. pipeline_state.py HMAC fail-open mtime check still uses LEGACY_SENTINEL_PATH unchanged
  AC7. New tests at tests/unit/lib/test_pipeline_state_gc.py and
       tests/integration/test_implement_heredoc_honors_env.py exist
"""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_DIR = REPO_ROOT / "plugins" / "autonomous-dev"
COMMANDS_DIR = PLUGIN_DIR / "commands"
LIB_DIR = PLUGIN_DIR / "lib"
HOOKS_DIR = PLUGIN_DIR / "hooks"


# Pattern that the migrated heredoc form must match.
ENV_VAR_FORM = re.compile(
    r"\$\{PIPELINE_STATE_FILE:-/tmp/implement_pipeline_state\.json\}"
)
LITERAL_PATH = "/tmp/implement_pipeline_state.json"


# ---------------------------------------------------------------------------
# AC1: implement.md heredoc sites migrated
# ---------------------------------------------------------------------------
def test_spec_1048_1_implement_md_uses_env_var_form() -> None:
    """AC1: implement.md must reference ${PIPELINE_STATE_FILE:-...} form."""
    content = (COMMANDS_DIR / "implement.md").read_text()
    assert ENV_VAR_FORM.search(content), (
        "implement.md should contain at least one "
        "${PIPELINE_STATE_FILE:-/tmp/implement_pipeline_state.json} reference"
    )


# ---------------------------------------------------------------------------
# AC2: implement-batch.md and implement-fix.md migrated
# ---------------------------------------------------------------------------
def test_spec_1048_2a_implement_batch_md_uses_env_var_form() -> None:
    """AC2: implement-batch.md must reference the env-var form."""
    content = (COMMANDS_DIR / "implement-batch.md").read_text()
    assert ENV_VAR_FORM.search(content), (
        "implement-batch.md should contain ${PIPELINE_STATE_FILE:-...} form"
    )


def test_spec_1048_2b_implement_fix_md_uses_env_var_form() -> None:
    """AC2: implement-fix.md must reference the env-var form."""
    content = (COMMANDS_DIR / "implement-fix.md").read_text()
    assert ENV_VAR_FORM.search(content), (
        "implement-fix.md should contain ${PIPELINE_STATE_FILE:-...} form"
    )


# ---------------------------------------------------------------------------
# AC3: rm -f cleanup commands migrated
# ---------------------------------------------------------------------------
def test_spec_1048_3_rm_f_cleanup_uses_env_var_form() -> None:
    """AC3: every `rm -f` against the pipeline state file must use env-var form."""
    bare_rm = re.compile(
        r"rm\s+-f\s+\"?/tmp/implement_pipeline_state\.json\"?"
    )
    env_rm = re.compile(
        r"rm\s+-f\s+\"?\$\{PIPELINE_STATE_FILE:-/tmp/implement_pipeline_state\.json\}\"?"
    )
    found_env_rm = False
    for md in ("implement.md", "implement-batch.md", "implement-fix.md"):
        text = (COMMANDS_DIR / md).read_text()
        # No bare literal `rm -f /tmp/implement_pipeline_state.json` allowed.
        bare_matches = bare_rm.findall(text)
        assert not bare_matches, (
            f"{md} contains un-migrated `rm -f /tmp/implement_pipeline_state.json` "
            f"({len(bare_matches)} occurrence(s))"
        )
        if env_rm.search(text):
            found_env_rm = True
    assert found_env_rm, (
        "At least one command file should contain a migrated "
        "`rm -f \"${PIPELINE_STATE_FILE:-/tmp/implement_pipeline_state.json}\"`"
    )


# ---------------------------------------------------------------------------
# AC4: _gc_stale_states() behavior
# ---------------------------------------------------------------------------
def _import_pcs():
    sys.path.insert(0, str(LIB_DIR))
    import pipeline_completion_state  # type: ignore
    return pipeline_completion_state


def test_spec_1048_4a_gc_default_max_age_is_7200() -> None:
    """AC4: default max_age_seconds should be 7200 (2× TTL of 3600s)."""
    import inspect

    pcs = _import_pcs()
    sig = inspect.signature(pcs._gc_stale_states)
    default = sig.parameters["max_age_seconds"].default
    assert default == 7200, f"expected default 7200s, got {default}"


def test_spec_1048_4b_gc_removes_old_state_files_and_lockfiles(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """AC4: GC must remove state files and orphaned lockfiles older than the cutoff."""
    pcs = _import_pcs()

    # Make age comparison deterministic regardless of clock skew.
    old_mtime = time.time() - 10_000  # > 7200 cutoff
    fresh_mtime = time.time() - 60  # well within cutoff

    # Create temp files for each pattern the GC scans.
    old_state = tmp_path / "pipeline_agent_completions_OLD.json"
    fresh_state = tmp_path / "pipeline_agent_completions_FRESH.json"
    old_sentinel = tmp_path / "implement_pipeline_OLD.json"
    fresh_sentinel = tmp_path / "implement_pipeline_FRESH.json"
    old_lock = tmp_path / "pipeline_OLD.lock"
    fresh_lock = tmp_path / "pipeline_FRESH.lock"

    for p in (old_state, fresh_state, old_sentinel, fresh_sentinel, old_lock, fresh_lock):
        p.write_text("{}")
    for p in (old_state, old_sentinel, old_lock):
        os.utime(p, (old_mtime, old_mtime))
    for p in (fresh_state, fresh_sentinel, fresh_lock):
        os.utime(p, (fresh_mtime, fresh_mtime))

    # Redirect /tmp/<pattern> globs to tmp_path/<pattern>.
    real_glob = pcs.glob.glob

    def fake_glob(pattern: str):
        if pattern.startswith("/tmp/"):
            redirected = str(tmp_path / pattern[len("/tmp/"):])
            return real_glob(redirected)
        return real_glob(pattern)

    monkeypatch.setattr(pcs.glob, "glob", fake_glob)

    result = pcs._gc_stale_states(max_age_seconds=7200)

    # Old files removed.
    assert not old_state.exists(), "old state file should have been removed"
    assert not old_sentinel.exists(), "old sentinel should have been removed"
    assert not old_lock.exists(), "old lockfile should have been removed"
    # Fresh files preserved.
    assert fresh_state.exists(), "fresh state file should NOT have been removed"
    assert fresh_sentinel.exists(), "fresh sentinel should NOT have been removed"
    assert fresh_lock.exists(), "fresh lockfile should NOT have been removed"

    # Returned counts match.
    assert result["state_files_removed"] >= 1
    assert result["sentinels_removed"] >= 1
    assert result["lockfiles_removed"] >= 1
    assert result["errors"] == [] or isinstance(result["errors"], list)


def test_spec_1048_4c_gc_returns_required_keys() -> None:
    """AC4: return dict must expose the four documented keys."""
    pcs = _import_pcs()
    # Run with a huge cutoff so nothing is deleted, regardless of /tmp state.
    result = pcs._gc_stale_states(max_age_seconds=10**12)
    for key in ("state_files_removed", "sentinels_removed", "lockfiles_removed", "errors"):
        assert key in result, f"missing key {key!r} in return dict"


# ---------------------------------------------------------------------------
# AC5: Security guards NOT migrated (Issue #1206 update — see below)
# ---------------------------------------------------------------------------
def test_spec_1048_5_security_guard_keeps_literal_path() -> None:
    """AC5 (Issue #1206 update): _check_bash_state_deletion still protects the
    legacy literal path AND the new per-repo path.

    Issue #1206 introduced LEGACY_SENTINEL_LITERALS — a module-level tuple
    containing BOTH ``/tmp/implement_pipeline_state.json`` (orphan protection
    for pre-#1206 sessions) and the new per-repo resolver result. The guard
    function dereferences the tuple via ``*LEGACY_SENTINEL_LITERALS`` so it
    protects both paths.
    """
    text = (HOOKS_DIR / "unified_pre_tool.py").read_text()
    assert "_check_bash_state_deletion" in text, "guard function must still exist"
    # The legacy literal MUST appear at module level (in LEGACY_SENTINEL_LITERALS).
    assert "LEGACY_SENTINEL_LITERALS" in text, (
        "LEGACY_SENTINEL_LITERALS tuple must be defined at module level"
    )
    assert f'"{LITERAL_PATH}"' in text or f"'{LITERAL_PATH}'" in text, (
        f"The legacy literal '{LITERAL_PATH}' must remain in unified_pre_tool.py "
        "(orphan protection per LEGACY_SENTINEL_LITERALS)"
    )
    # Locate the guard function and verify it dereferences the tuple.
    func_start = text.index("def _check_bash_state_deletion")
    next_def_match = re.search(r"\ndef [A-Za-z_]", text[func_start + 4:])
    func_end = func_start + 4 + (next_def_match.start() if next_def_match else len(text))
    body = text[func_start:func_end]
    assert "LEGACY_SENTINEL_LITERALS" in body, (
        "_check_bash_state_deletion must dereference LEGACY_SENTINEL_LITERALS "
        "so both the legacy /tmp path AND the new per-repo path are protected"
    )


# ---------------------------------------------------------------------------
# AC6 (updated by Issue #1206): pipeline_state.py HMAC fail-open uses
# get_legacy_sentinel_path() resolver. The original AC6 referenced a static
# constant LEGACY_SENTINEL_PATH; Issue #1206 replaced that with a per-repo
# resolver to eliminate cross-repo state collisions. Spec semantics preserved:
# the HMAC fail-open path is still consulted at the same logical site.
# ---------------------------------------------------------------------------
def test_spec_1048_6_pipeline_state_legacy_sentinel_unchanged() -> None:
    """AC6 (Issue #1206 update): HMAC fail-open still consults the legacy sentinel.

    The static LEGACY_SENTINEL_PATH constant was replaced by the
    get_legacy_sentinel_path() resolver. The fail-open semantic invariant
    (HMAC verify_state_hmac consults the legacy sentinel mtime) is preserved.
    """
    text = (LIB_DIR / "pipeline_state.py").read_text()

    # New: the resolver function is defined and used.
    assert "def get_legacy_sentinel_path" in text, (
        "get_legacy_sentinel_path() resolver must be defined in pipeline_state.py"
    )
    assert "LEGACY_SENTINEL_FILENAME" in text, (
        "LEGACY_SENTINEL_FILENAME constant must be defined in pipeline_state.py"
    )
    # The HMAC fail-open block must call the resolver to get the sentinel path.
    # (verify_state_hmac contains the call; this guards against the resolver
    # being defined but never used in the fail-open block.)
    assert text.count("get_legacy_sentinel_path") >= 2, (
        "get_legacy_sentinel_path must be defined AND called from at least "
        "one site (HMAC fail-open block or set_pipeline_base_commit)."
    )


# ---------------------------------------------------------------------------
# AC7: New tests exist
# ---------------------------------------------------------------------------
def test_spec_1048_7a_unit_gc_test_file_exists_and_has_tests() -> None:
    """AC7: tests/unit/lib/test_pipeline_state_gc.py must exist with at least one test."""
    p = REPO_ROOT / "tests" / "unit" / "lib" / "test_pipeline_state_gc.py"
    assert p.exists(), f"missing required test file: {p}"
    content = p.read_text()
    test_count = len(re.findall(r"^\s*def test_", content, re.MULTILINE))
    assert test_count >= 1, f"expected >=1 test in {p}, found {test_count}"


def test_spec_1048_7b_integration_heredoc_test_file_exists_and_has_tests() -> None:
    """AC7: tests/integration/test_implement_heredoc_honors_env.py must exist with tests."""
    p = REPO_ROOT / "tests" / "integration" / "test_implement_heredoc_honors_env.py"
    assert p.exists(), f"missing required test file: {p}"
    content = p.read_text()
    test_count = len(re.findall(r"^\s*def test_", content, re.MULTILINE))
    assert test_count >= 1, f"expected >=1 test in {p}, found {test_count}"
