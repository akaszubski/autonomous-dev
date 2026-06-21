"""Regression: sandbox must allow targeted `rm -rf .worktrees/batch-*` cleanup.

Bug: blanket `rm -rf` blocked_pattern in sandbox_policy.json blocks safe
targeted cleanup of batch worktrees (created by /implement --batch and
--issues), breaking post-run cleanup in consumer repos (e.g., Spektiv).
The pattern matches as a substring, so `rm -rf .worktrees/batch-XYZ` is
blocked even though the target is safe.

These tests run against the PRODUCTION sandbox_policy.json. They fail
until the policy switches from blanket `rm -rf` to a regex that catches
only dangerous targets (mirroring auto_approve_policy.json which already
distinguishes safe vs dangerous targets correctly).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PLUGIN_LIB = (
    Path(__file__).parent.parent.parent.parent
    / "plugins"
    / "autonomous-dev"
    / "lib"
)
sys.path.insert(0, str(_PLUGIN_LIB))

from sandbox_enforcer import CommandClassification, SandboxEnforcer  # noqa: E402

PRODUCTION_POLICY = (
    Path(__file__).parent.parent.parent.parent
    / "plugins"
    / "autonomous-dev"
    / "config"
    / "sandbox_policy.json"
)


def _enforcer() -> SandboxEnforcer:
    return SandboxEnforcer(policy_path=PRODUCTION_POLICY, profile="development")


def test_rm_rf_worktree_batch_path_not_blocked() -> None:
    """rm -rf .worktrees/batch-* must not be blocked (Spektiv cleanup bug)."""
    result = _enforcer().is_command_safe(
        "rm -rf .worktrees/batch-20260621-093618"
    )
    assert result.classification != CommandClassification.BLOCKED, (
        "rm -rf on .worktrees/batch-* must not be blocked. Bug surfaced "
        "from Spektiv: batch worktree cleanup post-/implement is being "
        f"rejected by sandbox. Got: {result.classification}, "
        f"reason: {result.reason}"
    )


def test_rm_rf_root_still_blocked() -> None:
    """rm -rf / must remain blocked (catastrophic target)."""
    result = _enforcer().is_command_safe("rm -rf /")
    assert result.classification == CommandClassification.BLOCKED


def test_rm_rf_home_still_blocked() -> None:
    """rm -rf ~ must remain blocked (catastrophic target)."""
    result = _enforcer().is_command_safe("rm -rf ~")
    assert result.classification == CommandClassification.BLOCKED


def test_rm_rf_git_dir_still_blocked() -> None:
    """rm -rf .git must remain blocked (destroys repo history)."""
    result = _enforcer().is_command_safe("rm -rf .git")
    assert result.classification == CommandClassification.BLOCKED


def test_rm_rf_ssh_dir_still_blocked() -> None:
    """rm -rf .ssh must remain blocked (destroys SSH credentials)."""
    result = _enforcer().is_command_safe("rm -rf .ssh")
    assert result.classification == CommandClassification.BLOCKED


def test_rm_rf_etc_blocked() -> None:
    """rm -rf /etc must be blocked (absolute-path system dir).

    Regression for security-auditor finding: the previous bounded regex
    only matched `rm -rf /` (bare slash); commands targeting absolute
    paths with sub-components (`/etc`, `/var`, `/home`, etc.) silently
    passed. The tightened `/(?:[^\\s]+)?(?=\\s|$)` branch closes this gap.
    """
    result = _enforcer().is_command_safe("rm -rf /etc")
    assert result.classification == CommandClassification.BLOCKED, (
        "rm -rf /etc must be blocked. Security-auditor finding: bounded "
        "regex must catch absolute paths with sub-components, not only "
        f"bare slash. Got: {result.classification}, reason: {result.reason}"
    )


def test_rm_rf_double_slash_blocked() -> None:
    """rm -rf // must be blocked (degenerate absolute-root target)."""
    result = _enforcer().is_command_safe("rm -rf //")
    assert result.classification == CommandClassification.BLOCKED, (
        "rm -rf // must be blocked (degenerate root-ish target). "
        f"Got: {result.classification}, reason: {result.reason}"
    )


def test_rm_rf_aws_dir_blocked() -> None:
    """rm -rf .aws must be blocked (destroys AWS credentials)."""
    result = _enforcer().is_command_safe("rm -rf .aws")
    assert result.classification == CommandClassification.BLOCKED, (
        "rm -rf .aws must be blocked (AWS credentials directory). "
        f"Got: {result.classification}, reason: {result.reason}"
    )


def test_rm_rf_env_file_blocked() -> None:
    """rm -rf .env must be blocked (destroys env-file secrets)."""
    result = _enforcer().is_command_safe("rm -rf .env")
    assert result.classification == CommandClassification.BLOCKED, (
        "rm -rf .env must be blocked (env-file with secrets). "
        f"Got: {result.classification}, reason: {result.reason}"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
