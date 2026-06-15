"""Tier 0g — ephemeral / scratch paths skip the write-pipeline gate.

The original tiers 0a-0f covered pipeline-active, operator bypass, no-path,
non-code extensions, and test files. Tier 0g (this test class) covers
ephemeral / scratch paths that are never committed and never user-facing,
so the /implement pipeline review adds no value.

Why this matters: without this exemption every agent that writes a
helper script to ``/tmp/foo.sh`` triggers the pipeline gate, which forces
either the bypass-file dance (touch ``.claude/.bypass`` + cleanup) or a
full /implement detour for a one-off scratch file. Both burn agent
attention and operator approvals on noise.

Coverage:
- ``/tmp/`` and ``/private/tmp/`` (the macOS canonical form)
- ``/var/folders/`` (macOS ``tempfile.mkdtemp()`` + ``pytest.tmp_path``)
- ``~/tmp/`` and ``~/.cache/`` (user-level scratch)
- Negative cases: directories that NAME contains 'tmp' or '.cache' but
  are not at the absolute prefix (e.g. ``/repo/tmp/foo.py``,
  ``./.cache/foo.py``)

Filed alongside the realign session that discovered the pain point
(2026-06-15).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Match the import pattern used by sibling test files.
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "hooks"
    ),
)

import unified_pre_tool as upt  # noqa: E402


def _gate(file_path: str):
    """Invoke ``_check_write_pipeline_required`` with neutral args + mocked
    pipeline-state so we exercise the Tier 0g branch deterministically.

    Returns the ``(blocked, tier_label, directive)`` tuple.
    """
    with patch.object(upt, "_is_pipeline_active", return_value=False):
        return upt._check_write_pipeline_required(
            file_path=file_path,
            tool_name="Write",
            old_string="",
            new_string="x = 1\n",
            session_id="unit-test",
        )


# ---------------------------------------------------------------------------
# Exempt paths — Tier 0g matches → not blocked
# ---------------------------------------------------------------------------


class TestEphemeralPathExemption:
    """Files at ephemeral absolute prefixes skip the pipeline gate."""

    @pytest.mark.parametrize(
        "path",
        [
            "/tmp/foo.py",
            "/tmp/scratch/helper.sh",
            "/private/tmp/foo.py",                      # macOS canonical form
            "/var/folders/zz/abc123/T/pytest-of-x/foo.py",  # pytest tmp_path
        ],
    )
    def test_absolute_ephemeral_prefixes_skip_gate(self, path):
        blocked, tier, directive = _gate(path)
        assert not blocked, f"{path} should bypass the pipeline gate"
        assert tier == "tier0_ephemeral_path"
        assert directive == ""

    def test_home_tmp_subtree_is_exempt(self, tmp_path, monkeypatch):
        # Anchor Path.home() to a known location so the prefix check is
        # deterministic across operator machines.
        monkeypatch.setattr(upt.Path, "home", lambda: tmp_path)
        path = str(tmp_path / "tmp" / "helper.sh")
        blocked, tier, _ = _gate(path)
        assert not blocked
        assert tier == "tier0_ephemeral_path"

    def test_home_cache_subtree_is_exempt(self, tmp_path, monkeypatch):
        monkeypatch.setattr(upt.Path, "home", lambda: tmp_path)
        path = str(tmp_path / ".cache" / "foo.py")
        blocked, tier, _ = _gate(path)
        assert not blocked
        assert tier == "tier0_ephemeral_path"


# ---------------------------------------------------------------------------
# Non-exempt paths — Tier 0g must NOT match (gate proceeds to classifier)
# ---------------------------------------------------------------------------


class TestEphemeralPathBoundaries:
    """Look-alike paths that happen to contain ``tmp`` / ``.cache`` MUST
    fall through to the tier classifier — Tier 0g is restricted to
    ABSOLUTE prefixes so a project subdirectory named ``tmp`` is gated
    normally."""

    @pytest.mark.parametrize(
        "path",
        [
            # Project subdir literally named tmp/
            "/Users/operator/Dev/myrepo/tmp/foo.py",
            # Relative path
            "tmp/foo.py",
            "./tmp/foo.py",
            # .cache somewhere other than $HOME/.cache
            "/Users/operator/Dev/myrepo/.cache/foo.py",
            # tmp embedded but not at prefix
            "/Users/operator/notmpdir/foo.py",
        ],
    )
    def test_non_prefix_tmp_paths_do_not_bypass(self, path):
        blocked, tier, _ = _gate(path)
        assert tier != "tier0_ephemeral_path", (
            f"{path} must NOT match Tier 0g (project subdir named tmp/"
            " or relative path)"
        )


# ---------------------------------------------------------------------------
# Tier ordering — Tier 0g fires AFTER Tier 0c (operator bypass), Tier 0f
# (test file), Tier 0e (non-code), etc., so its absence on a non-ephemeral
# code path doesn't change classifier behaviour. Sanity-check ordering.
# ---------------------------------------------------------------------------


class TestTierOrdering:
    def test_test_file_still_takes_precedence_over_ephemeral(self):
        # A pytest test file at /tmp/test_thing.py should be recognised
        # as a test file (Tier 0f) first, not Tier 0g. Both bypass the
        # gate, but the tier label should reflect the more specific
        # reason for telemetry. Tier 0f is currently checked BEFORE
        # Tier 0g; the ordering test pins that contract.
        blocked, tier, _ = _gate("/tmp/test_foo.py")
        assert not blocked
        assert tier == "tier0_test_file", (
            "test files should remain labelled tier0_test_file even when"
            " they live under /tmp/"
        )

    def test_non_code_extension_still_takes_precedence_over_ephemeral(self):
        # A .md file in /tmp/ should be Tier 0e, not Tier 0g — both
        # bypass, but the more specific tier wins.
        blocked, tier, _ = _gate("/tmp/notes.md")
        assert not blocked
        assert tier == "tier0_non_code"
