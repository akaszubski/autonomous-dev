"""Spec-validation tests for Issue #761.

Feature: verify_state_hmac stale fail-open checks undocumented proxy file path.

The fix:
- Adds a module-level LEGACY_SENTINEL_PATH constant in pipeline_state.py
- Adds inline comments documenting why the sentinel file (not the HMAC state
  file) is used for stale detection
- Adds regression tests pinning the sentinel path so future changes are caught

These tests validate the OBSERVABLE BEHAVIOR described in the spec without
relying on implementation details beyond public API and the new constant.
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Path setup — portable, works from any cwd
# ---------------------------------------------------------------------------
_WORKTREE = Path(__file__).resolve().parents[2]
_LIB = _WORKTREE / "plugins" / "autonomous-dev" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import pipeline_state as _ps
from pipeline_state import (
    LEGACY_SENTINEL_FILENAME,
    _compute_state_hmac,
    get_legacy_sentinel_path,
    get_state_path,
    sign_state,
    verify_state_hmac,
)

# Issue #1206: LEGACY_SENTINEL_PATH constant was replaced by the per-repo
# resolver get_legacy_sentinel_path(). The historical name is kept here as a
# *value snapshot* for tests that still pin the resolved path.
LEGACY_SENTINEL_PATH = get_legacy_sentinel_path()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bogus_state(run_id: str = "run-761") -> dict:
    """Minimal state dict with an HMAC that will never verify."""
    return {
        "session_start": "",
        "run_id": run_id,
        "nonce": "nonce-abc",
        "mode": "full",
        "explicitly_invoked": True,
        "alignment_passed": True,
        "hmac": "totally_invalid_hmac_value",
    }


def _signed_state(run_id: str = "run-761", secret: str = "test-secret") -> dict:
    """Minimal state dict with a valid HMAC signed with `secret`."""
    state = {
        "session_start": "",
        "run_id": run_id,
        "nonce": "nonce-valid",
        "mode": "full",
        "explicitly_invoked": False,
        "alignment_passed": False,
    }
    state["hmac"] = _compute_state_hmac(state, secret)
    return state


# ---------------------------------------------------------------------------
# Criterion 1: LEGACY_SENTINEL_PATH constant exists with exact value
# ---------------------------------------------------------------------------

def test_spec_issue761_1_legacy_sentinel_path_constant_value():
    """Sentinel path must be per-repo (Issue #1206 update of the #761 spec).

    Spec: 'adds a module-level resolver to clarify which file is used as the
    activity proxy'. Issue #1206 replaced the static constant with a per-repo
    resolver to eliminate cross-repo collision on the machine-global path.
    """
    sentinel = get_legacy_sentinel_path()
    assert sentinel.name == LEGACY_SENTINEL_FILENAME, (
        f"sentinel filename changed: {sentinel.name}"
    )
    assert sentinel.parent.name == "local"
    assert sentinel.parent.parent.name == ".claude"
    assert sentinel != Path("/tmp/implement_pipeline_state.json"), (
        "Issue #1206 regression: sentinel still resolves to machine-global /tmp."
    )


# ---------------------------------------------------------------------------
# Criterion 2: LEGACY_SENTINEL_PATH is distinct from HMAC state file paths
# ---------------------------------------------------------------------------

def test_spec_issue761_2_sentinel_path_distinct_from_hmac_state_paths():
    """LEGACY_SENTINEL_PATH must not collide with any per-run HMAC state path.

    Spec: 'the legacy sentinel file path … not the HMAC-signed state file'.
    """
    representative_run_ids = [
        "run-761",
        "batch-20260412-015602",
        "issue-761-fix",
        "abc123",
        "test-run",
    ]
    for run_id in representative_run_ids:
        hmac_path = get_state_path(run_id)
        assert LEGACY_SENTINEL_PATH != hmac_path, (
            f"LEGACY_SENTINEL_PATH collides with HMAC state path for run_id={run_id!r}"
        )


# ---------------------------------------------------------------------------
# Criterion 3: verify_state_hmac checks LEGACY_SENTINEL_PATH for stale detection
# ---------------------------------------------------------------------------

def test_spec_issue761_3_verify_state_hmac_checks_legacy_sentinel_path():
    """verify_state_hmac() must consult the legacy sentinel for stale detection.

    Spec (updated by Issue #1206): 'adds documentation … to clarify that the
    stale fail-open logic … uses the legacy sentinel file path as an activity
    proxy'. Issue #1206 replaced the static LEGACY_SENTINEL_PATH constant with
    a per-repo resolver; the sentinel path is now resolved at call time. To
    make the assertion robust against test ordering side-effects on the
    project-root cache, we resolve the expected path immediately before the
    call and reset the cache to ensure both the test and the function see the
    same CWD-derived path.
    """
    # Reset cache so the resolver sees the current cwd, not a stale cached root.
    import path_utils as _pu
    _pu.reset_project_root_cache()

    # Re-resolve the sentinel path at call time (matches verify_state_hmac()).
    expected_sentinel = str(get_legacy_sentinel_path())

    state = _bogus_state()
    checked_paths: list = []

    def tracking_exists(self):
        checked_paths.append(str(self))
        if str(self) == expected_sentinel:
            return True
        return False

    old_mtime = time.time() - 7200  # 2 hours ago — ensures fail-open fires
    mock_stat = MagicMock()
    mock_stat.st_mtime = old_mtime

    with patch("pipeline_state._read_pipeline_secret", return_value=None), \
         patch.object(Path, "exists", tracking_exists), \
         patch.object(Path, "stat", return_value=mock_stat):
        result = verify_state_hmac(state, "irrelevant-session")

    assert expected_sentinel in checked_paths, (
        f"verify_state_hmac() never checked the legacy sentinel "
        f"({expected_sentinel}). Paths checked: {checked_paths}"
    )
    # If the sentinel was actually used, the stale check should have fired
    # (sentinel mtime is 2hr old) and returned True.
    assert result is True, (
        "Stale legacy sentinel should trigger fail-open"
    )


# ---------------------------------------------------------------------------
# Criterion 4: Stale sentinel (>1hr mtime) + invalid HMAC → fail-open (True)
# ---------------------------------------------------------------------------

@patch("pipeline_state._read_pipeline_secret", return_value=None)
def test_spec_issue761_4_stale_sentinel_with_invalid_hmac_fails_open(mock_secret):
    """Sentinel mtime > 1 hour and HMAC unverifiable must return True.

    Spec: 'if >1 hour old, the pipeline is considered stale and HMAC
    verification fails open to avoid blocking subsequent sessions'.
    """
    state = _bogus_state()
    old_mtime = time.time() - 7200  # 2 hours ago
    mock_stat = MagicMock()
    mock_stat.st_mtime = old_mtime

    with patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "stat", return_value=mock_stat):
        result = verify_state_hmac(state, "other-session")

    assert result is True, (
        "Stale sentinel (>1hr) with unverifiable HMAC should fail-open (True)"
    )


# ---------------------------------------------------------------------------
# Criterion 5: Fresh sentinel (<1hr mtime) + invalid HMAC → no fail-open (False)
# ---------------------------------------------------------------------------

@patch("pipeline_state._read_pipeline_secret", return_value=None)
def test_spec_issue761_5_fresh_sentinel_with_invalid_hmac_does_not_fail_open(mock_secret):
    """Sentinel mtime < 1 hour and HMAC invalid must return False.

    Spec: the fail-open is only for stale states, not for active pipelines.
    """
    state = _bogus_state()
    recent_mtime = time.time() - 300  # 5 minutes ago
    mock_stat = MagicMock()
    mock_stat.st_mtime = recent_mtime

    with patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "stat", return_value=mock_stat):
        result = verify_state_hmac(state, "other-session")

    assert result is False, (
        "Fresh sentinel (<1hr) with invalid HMAC must NOT fail-open (return False)"
    )


# ---------------------------------------------------------------------------
# Criterion 6: Valid HMAC passes regardless of sentinel age
# ---------------------------------------------------------------------------

@patch("pipeline_state._read_pipeline_secret")
def test_spec_issue761_6_valid_hmac_passes_regardless_of_sentinel_age(mock_secret):
    """A properly signed state should pass HMAC verification regardless of age.

    Spec: the fix is documentation-only; existing HMAC verification behavior
    is unchanged.
    """
    secret = "valid-secret-abc"
    mock_secret.return_value = secret
    state = _signed_state(secret=secret)

    # Result should be True without even reaching the stale-check branch
    result = verify_state_hmac(state, "any-session")

    assert result is True, (
        "A validly signed state must pass HMAC verification"
    )


# ---------------------------------------------------------------------------
# Criterion 7: Missing sentinel file does not trigger fail-open
# ---------------------------------------------------------------------------

@patch("pipeline_state._read_pipeline_secret", return_value=None)
def test_spec_issue761_7_missing_sentinel_file_does_not_fail_open(mock_secret):
    """When LEGACY_SENTINEL_PATH does not exist, fail-open must NOT trigger.

    Spec: the sentinel's mtime is checked only if the file exists.
    """
    state = _bogus_state()

    with patch.object(Path, "exists", return_value=False):
        result = verify_state_hmac(state, "other-session")

    assert result is False, (
        "Missing sentinel file must not trigger fail-open"
    )


# ---------------------------------------------------------------------------
# Criterion 8: Forged session_start cannot bypass fail-open guard
# ---------------------------------------------------------------------------

@patch("pipeline_state._read_pipeline_secret", return_value=None)
def test_spec_issue761_8_forged_session_start_blocked_by_fresh_sentinel_mtime(mock_secret):
    """Forged session_start (old timestamp) + fresh sentinel mtime must return False.

    Spec: 'the stale detection uses file mtime (not session_start from the
    state dict) to prevent an attacker from forging session_start to trigger
    fail-open'.
    """
    from datetime import datetime, timezone, timedelta

    two_hours_ago = (
        datetime.now(timezone.utc) - timedelta(hours=2)
    ).isoformat()

    state = _bogus_state()
    state["session_start"] = two_hours_ago  # forged old timestamp

    fresh_mtime = time.time() - 60  # 1 minute ago (file is current)
    mock_stat = MagicMock()
    mock_stat.st_mtime = fresh_mtime

    with patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "stat", return_value=mock_stat):
        result = verify_state_hmac(state, "other-session")

    assert result is False, (
        "Forged session_start with a fresh sentinel mtime must NOT trigger fail-open. "
        "mtime-based check prevents this attack vector."
    )


# ---------------------------------------------------------------------------
# Criterion 9: No behavioral change — public API signatures are preserved
# ---------------------------------------------------------------------------

def test_spec_issue761_9_verify_state_hmac_accepts_two_positional_args():
    """verify_state_hmac(state, session_id) signature must be preserved.

    Spec: 'documentation-only plus test additions' — no behavioral changes.
    """
    import inspect
    sig = inspect.signature(verify_state_hmac)
    params = list(sig.parameters.keys())
    assert "state" in params, "verify_state_hmac must have 'state' parameter"
    assert "session_id" in params, "verify_state_hmac must have 'session_id' parameter"


def test_spec_issue761_9b_sign_state_accepts_two_positional_args():
    """sign_state(state, session_id) signature must be preserved."""
    import inspect
    sig = inspect.signature(sign_state)
    params = list(sig.parameters.keys())
    assert "state" in params, "sign_state must have 'state' parameter"
    assert "session_id" in params, "sign_state must have 'session_id' parameter"


def test_spec_issue761_9c_get_state_path_accepts_run_id():
    """get_state_path(run_id) signature must be preserved."""
    import inspect
    sig = inspect.signature(get_state_path)
    params = list(sig.parameters.keys())
    assert "run_id" in params, "get_state_path must have 'run_id' parameter"


# ---------------------------------------------------------------------------
# Criterion 10: Regression test file for issue 761 covers sentinel pinning
# ---------------------------------------------------------------------------

def test_spec_issue761_10_regression_test_file_exists_for_issue_761():
    """The regression test file for issue 753 must exist (sentinel pinning added).

    Spec: 'adds targeted regression tests that pin the sentinel path so future
    changes are caught'.
    """
    regression_test_file = (
        _WORKTREE / "tests" / "regression" / "test_issue_753_hmac_stale_failopen.py"
    )
    assert regression_test_file.exists(), (
        f"Regression test file not found: {regression_test_file}"
    )


def test_spec_issue761_10b_regression_test_file_contains_sentinel_pinning_class():
    """The regression test file must contain TestIssue761SentinelPathPinning class.

    Spec: 'adds targeted regression tests that pin the sentinel path'.
    """
    regression_test_file = (
        _WORKTREE / "tests" / "regression" / "test_issue_753_hmac_stale_failopen.py"
    )
    content = regression_test_file.read_text()
    assert "TestIssue761SentinelPathPinning" in content, (
        "Regression test file must contain TestIssue761SentinelPathPinning class "
        "to pin the sentinel path per spec"
    )


def test_spec_issue761_10c_legacy_sentinel_path_is_exported_from_module():
    """Sentinel resolver must be importable from pipeline_state (Issue #1206 update).

    Spec: 'adds documentation … module-level resolver'. Issue #1206 replaced
    the static LEGACY_SENTINEL_PATH constant with the get_legacy_sentinel_path
    resolver function. The filename constant LEGACY_SENTINEL_FILENAME is
    also exported.
    """
    assert hasattr(_ps, "get_legacy_sentinel_path"), (
        "get_legacy_sentinel_path must be a module-level attribute of pipeline_state"
    )
    assert hasattr(_ps, "LEGACY_SENTINEL_FILENAME"), (
        "LEGACY_SENTINEL_FILENAME must be a module-level attribute of pipeline_state"
    )
    sentinel = _ps.get_legacy_sentinel_path()
    assert isinstance(sentinel, Path), (
        f"get_legacy_sentinel_path() must return a Path instance, got {type(sentinel)}"
    )
    assert isinstance(_ps.LEGACY_SENTINEL_FILENAME, str)
