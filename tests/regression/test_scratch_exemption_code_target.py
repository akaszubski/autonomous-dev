"""Scratch exemption in ``_is_code_file_target`` + the ``SCRATCHPAD=/`` bypass.

Two mechanisms are under test, and the order they were built in matters:

1. **The degenerate-root rejection** (security). ``_is_scratch_path`` computed
   ``expanded.startswith(scratchpad.rstrip("/") + "/")``. With ``SCRATCHPAD=/``
   that reduces to ``startswith("/")`` — true for EVERY absolute path,
   including ``unified_pre_tool.py`` itself and ``/etc/passwd``. The bypass
   already existed at the three pre-existing call sites (``_is_gated_repo_source``
   and the two #803 cross-tool checks), so the guard had to land BEFORE the new
   call site was wired in, or wiring would have widened it.
2. **The exemption itself**. ``_is_code_file_target`` gated every ``.py`` under
   ``/tmp`` and ``$SCRATCHPAD`` as though it were repo source, on both the
   Write/Edit branch and the Bash-redirect branch.

Both arms are exercised on both branches. The different-shape negative control
is ``/tmpfoo/bar.py`` — a prefix LOOKALIKE, not the bug that prompted the fix
(which was a genuine ``/tmp/`` child) — so a fix that merely special-cased the
reproducer would fail here.

Issues: #1408, #1435
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(HOOK_DIR))
sys.path.insert(0, str(LIB_DIR))

import unified_pre_tool as upt  # noqa: E402

# In-repo source used as the refuse arm. Also protected infrastructure, so it
# exercises the ordering: scratch is consulted BEFORE _is_protected_infrastructure
# but must not shadow it for a non-scratch path.
REPO_SOURCE = str(HOOK_DIR / "unified_pre_tool.py")
# A root only reachable through the $SCRATCHPAD branch — deliberately NOT under
# /tmp, so it discriminates that branch instead of EPHEMERAL_PREFIXES.
LEGIT_SCRATCH_ROOT = str(REPO_ROOT / ".scratchroot")


# ---------------------------------------------------------------------------
# 1. Degenerate SCRATCHPAD values (the security fix)
# ---------------------------------------------------------------------------


class TestDegenerateScratchpadRejected:
    """``SCRATCHPAD=/`` must exempt nothing, at every caller."""

    @pytest.mark.parametrize("degenerate", ["/", "//", "///", ""])
    @pytest.mark.parametrize(
        "victim",
        [
            REPO_SOURCE,
            "/etc/passwd",
            str(LIB_DIR / "pipeline_state.py"),
        ],
    )
    def test_degenerate_root_exempts_nothing(
        self, monkeypatch: pytest.MonkeyPatch, degenerate: str, victim: str
    ) -> None:
        monkeypatch.setenv("SCRATCHPAD", degenerate)
        assert upt._is_scratch_path(victim) is False, (
            f"SCRATCHPAD={degenerate!r} exempted {victim} — the degenerate-root "
            f"prefix test matched every absolute path"
        )

    def test_degenerate_root_does_not_ungate_code_target(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The wired call site must not inherit the degenerate bypass."""
        monkeypatch.setenv("SCRATCHPAD", "/")
        assert (
            upt._is_code_file_target("Write", {"file_path": REPO_SOURCE}) is True
        )
        assert (
            upt._is_code_file_target(
                "Bash", {"command": f"echo x > {REPO_SOURCE}"}
            )
            is True
        )

    def test_legitimate_scratchpad_still_exempts_positive_control(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Positive control: a real scratchpad root still works.

        Without this, a fix that simply deleted the $SCRATCHPAD branch would
        pass every assertion above while removing the feature.
        """
        monkeypatch.setenv("SCRATCHPAD", LEGIT_SCRATCH_ROOT)
        beneath = f"{LEGIT_SCRATCH_ROOT}/helper.py"
        assert upt._is_scratch_path(beneath) is True
        assert upt._is_code_file_target("Write", {"file_path": beneath}) is False
        # And it must NOT leak upward to its own parent or siblings.
        assert upt._is_scratch_path(f"{LEGIT_SCRATCH_ROOT}-sibling/x.py") is False

    def test_scratchpad_is_protected_from_inline_spoofing(self) -> None:
        """Injection route: the env var itself cannot be set inline in Bash."""
        assert "SCRATCHPAD" in upt.PROTECTED_ENV_VARS
        reason = upt._detect_env_spoofing("SCRATCHPAD=/ python3 -c 'print(1)'")
        assert reason is not None, "inline SCRATCHPAD=/ was not blocked"
        assert "SCRATCHPAD" in reason
        assert upt._detect_env_spoofing("export SCRATCHPAD=/") is not None

    def test_unrelated_env_var_still_allowed(self) -> None:
        """Negative control for the spoofing check: it does not block everything."""
        assert upt._detect_env_spoofing("SCRATCH_NOTES=/tmp/x python3 -c 'print(1)'") is None


# ---------------------------------------------------------------------------
# 2. The exemption — Write/Edit branch
# ---------------------------------------------------------------------------


class TestCodeTargetWriteBranch:
    """``_is_code_file_target`` on transport-independent write tools."""

    @pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit", "NotebookEdit"])
    @pytest.mark.parametrize(
        "scratch",
        [
            "/tmp/helper.py",
            "/private/tmp/claude-501/sess/scratchpad/probe.py",
            "/var/folders/zz/abc/T/gen.sh",
            "/Users/x/repo/.claude/tmp/scratch.py",
        ],
    )
    def test_scratch_is_not_a_code_target(self, tool: str, scratch: str) -> None:
        assert upt._is_code_file_target(tool, {"file_path": scratch}) is False

    def test_scratchpad_env_subtree_is_not_a_code_target(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SCRATCHPAD", LEGIT_SCRATCH_ROOT)
        assert (
            upt._is_code_file_target(
                "Write", {"file_path": f"{LEGIT_SCRATCH_ROOT}/mod.py"}
            )
            is False
        )

    def test_repo_source_stays_a_code_target(self) -> None:
        """Refuse arm: the exemption must not swallow real source."""
        assert upt._is_code_file_target("Write", {"file_path": REPO_SOURCE}) is True

    @pytest.mark.parametrize(
        "lookalike",
        ["/tmpfoo/bar.py", "/var/foldersX/x.py", "/private/tmpish/y.py"],
    )
    def test_prefix_lookalike_stays_gated(self, lookalike: str) -> None:
        """Different-shape control: a prefix lookalike is NOT scratch."""
        assert upt._is_scratch_path(lookalike) is False
        assert upt._is_code_file_target("Write", {"file_path": lookalike}) is True


# ---------------------------------------------------------------------------
# 3. The exemption — Bash-redirect branch (transport parity)
# ---------------------------------------------------------------------------


class TestCodeTargetBashBranch:
    """Bash redirect targets must classify identically to Write/Edit."""

    def test_scratch_redirect_is_not_a_code_target(self) -> None:
        assert (
            upt._is_code_file_target("Bash", {"command": "echo x > /tmp/gen.py"})
            is False
        )

    def test_mixed_redirect_still_reports_the_repo_target(self) -> None:
        """``continue`` (not ``return False``) — a scratch target must not mask
        a repo-source target later in the same command."""
        cmd = f"echo a > /tmp/gen.py; echo b > {REPO_SOURCE}"
        assert upt._is_code_file_target("Bash", {"command": cmd}) is True

    def test_lookalike_redirect_stays_gated(self) -> None:
        assert (
            upt._is_code_file_target("Bash", {"command": "echo x > /tmpfoo/bar.py"})
            is True
        )
