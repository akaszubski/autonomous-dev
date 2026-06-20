"""Issue #1263: SWE router hook integration tests (Phase A, log-only).

Validates the dispatcher ``unified_pre_tool._maybe_invoke_swe_router``:

    AC#12: invokes ``semantic_gate.route`` (not ``judge``) when the
           ``swe_router`` feature flag is explicitly enabled.
    AC#13: fires at most once per session per user-prompt token
           (fire-once-per-turn).
    AC#14: fires again when the user-message token changes.
    AC#15: skips when ``is_write_to_code_file`` returns False.
    AC#16: skips when ``get_user_msg_token`` returns None.
    AC#17: router exception NEVER affects the hook (the helper swallows).

The dispatcher was extracted from ``main()`` so it can be unit tested
in-process without subprocess overhead. This mirrors the pattern used by
``test_unified_pre_tool_prompt_integrity_telemetry.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Bridge sys.path: hooks + lib.
_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"))
sys.path.insert(0, str(_REPO_ROOT / "plugins" / "autonomous-dev" / "lib"))

import unified_pre_tool as hook  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_router_cache():
    """Clear the in-process fire-once-per-turn cache between tests."""
    hook._LAST_ROUTE_TOKEN_BY_SESSION.clear()
    yield
    hook._LAST_ROUTE_TOKEN_BY_SESSION.clear()


@pytest.fixture
def flag_enabled(monkeypatch):
    """Force ``is_feature_explicitly_enabled('swe_router')`` to True."""
    import feature_flags
    monkeypatch.setattr(
        feature_flags,
        "is_feature_explicitly_enabled",
        lambda name: name == "swe_router",
    )


@pytest.fixture
def flag_disabled(monkeypatch):
    """Force ``is_feature_explicitly_enabled`` to always return False."""
    import feature_flags
    monkeypatch.setattr(
        feature_flags, "is_feature_explicitly_enabled", lambda _name: False
    )


@pytest.fixture
def stub_token(monkeypatch):
    """Stub ``session_mode.get_user_msg_token`` to return a configurable token."""
    state = {"token": "tokendeadbeef00"}

    def _set(t):
        state["token"] = t

    def _get(_sid):
        return state["token"]

    import session_mode
    monkeypatch.setattr(session_mode, "get_user_msg_token", _get)
    return _set


@pytest.fixture
def spy_route(monkeypatch):
    """Replace ``semantic_gate.route`` with a recording spy."""
    calls = []

    def _spy(**kwargs):
        calls.append(kwargs)
        from semantic_gate import RouterResult
        return RouterResult(
            verdict="agree", route_target="/implement", reasoning="ok",
            latency_ms=1.0, cache_hit=False, fail_open=False,
        )

    import semantic_gate
    monkeypatch.setattr(semantic_gate, "route", _spy)
    return calls


@pytest.fixture
def spy_judge(monkeypatch):
    """Replace ``semantic_gate.judge`` with a recording spy."""
    calls = []

    def _spy(**kwargs):
        calls.append(kwargs)
        from semantic_gate import JudgeResult
        return JudgeResult(
            verdict="agree", confidence=0.9, reasoning="ok",
            fail_open=False, latency_ms=1.0, cache_hit=False,
        )

    import semantic_gate
    monkeypatch.setattr(semantic_gate, "judge", _spy)
    return calls


# ---------------------------------------------------------------------------
# AC#13 — fire-once-per-turn within same token
# ---------------------------------------------------------------------------


class TestRouterFiresOncePerTurn:
    """AC#13: router fires at most once per session per user-prompt token."""

    def test_two_writes_same_token_one_call(
        self, flag_enabled, stub_token, spy_route
    ):
        stub_token("token-A")
        tool_input = {"file_path": "/repo/foo.py", "content": "x = 1\n"}
        hook._maybe_invoke_swe_router("Write", tool_input, "session-x")
        hook._maybe_invoke_swe_router("Write", tool_input, "session-x")
        assert len(spy_route) == 1, (
            f"router MUST fire only once per turn; got {len(spy_route)} calls"
        )

    def test_three_writes_same_token_still_one_call(
        self, flag_enabled, stub_token, spy_route
    ):
        stub_token("same-token")
        for i in range(3):
            hook._maybe_invoke_swe_router(
                "Write",
                {"file_path": f"/repo/f{i}.py", "content": "x\n"},
                "session-y",
            )
        assert len(spy_route) == 1


# ---------------------------------------------------------------------------
# AC#14 — re-fires on token change
# ---------------------------------------------------------------------------


class TestRouterFiresOnNewTurn:
    """AC#14: router fires again when the user-message token changes."""

    def test_token_change_re_fires(self, flag_enabled, stub_token, spy_route):
        tool_input = {"file_path": "/repo/foo.py", "content": "x\n"}
        stub_token("token-A")
        hook._maybe_invoke_swe_router("Write", tool_input, "session-z")
        stub_token("token-B")
        hook._maybe_invoke_swe_router("Write", tool_input, "session-z")
        assert len(spy_route) == 2

    def test_three_turns_three_calls(self, flag_enabled, stub_token, spy_route):
        tool_input = {"file_path": "/repo/foo.py", "content": "x\n"}
        for t in ("t1", "t2", "t3"):
            stub_token(t)
            hook._maybe_invoke_swe_router("Write", tool_input, "session-multi")
        assert len(spy_route) == 3


# ---------------------------------------------------------------------------
# AC#15 — non-code file skip
# ---------------------------------------------------------------------------


class TestRouterSkipsNonCodeFile:
    """AC#15: router does NOT fire when is_write_to_code_file is False."""

    def test_skipped_for_txt_file(self, flag_enabled, stub_token, spy_route):
        stub_token("token-A")
        hook._maybe_invoke_swe_router(
            "Write",
            {"file_path": "/repo/readme.txt", "content": "hi"},
            "session-skip-txt",
        )
        assert len(spy_route) == 0

    def test_skipped_for_no_extension(self, flag_enabled, stub_token, spy_route):
        stub_token("token-A")
        hook._maybe_invoke_swe_router(
            "Write",
            {"file_path": "/repo/Makefile", "content": "hi"},
            "session-skip-makefile",
        )
        assert len(spy_route) == 0

    def test_skipped_for_non_write_tool(
        self, flag_enabled, stub_token, spy_route
    ):
        stub_token("token-A")
        hook._maybe_invoke_swe_router(
            "Bash",
            {"command": "ls"},
            "session-skip-bash",
        )
        assert len(spy_route) == 0


# ---------------------------------------------------------------------------
# AC#16 — missing token skip
# ---------------------------------------------------------------------------


class TestRouterSkipsWhenNoToken:
    """AC#16: router does NOT fire when get_user_msg_token returns None."""

    def test_skipped_when_no_session_mode(
        self, flag_enabled, stub_token, spy_route
    ):
        stub_token(None)  # simulates missing/stale artifact
        hook._maybe_invoke_swe_router(
            "Write",
            {"file_path": "/repo/foo.py", "content": "x\n"},
            "session-no-token",
        )
        assert len(spy_route) == 0


# ---------------------------------------------------------------------------
# AC#17 — router exception never blocks
# ---------------------------------------------------------------------------


class TestRouterFailureNeverBlocks:
    """AC#17: router exception does NOT affect hook decision (helper swallows)."""

    def test_route_raises_helper_still_returns_none(
        self, flag_enabled, stub_token, monkeypatch
    ):
        stub_token("token-boom")

        def _explode(**kwargs):
            raise RuntimeError("simulated router failure")

        import semantic_gate
        monkeypatch.setattr(semantic_gate, "route", _explode)
        # MUST NOT raise.
        result = hook._maybe_invoke_swe_router(
            "Write",
            {"file_path": "/repo/foo.py", "content": "x\n"},
            "session-explode",
        )
        # Helper returns None; what matters is no propagated exception.
        assert result is None

    def test_get_token_raises_helper_still_returns_none(
        self, flag_enabled, monkeypatch
    ):
        import session_mode

        def _explode(_sid):
            raise RuntimeError("token lookup failure")

        monkeypatch.setattr(session_mode, "get_user_msg_token", _explode)
        # MUST NOT raise (the outer try/except in the helper catches).
        assert hook._maybe_invoke_swe_router(
            "Write",
            {"file_path": "/repo/foo.py", "content": "x\n"},
            "session-token-boom",
        ) is None


# ---------------------------------------------------------------------------
# AC#12 — callsite uses route() not judge() when swe_router is enabled
# ---------------------------------------------------------------------------


class TestCallsite:
    """AC#12: when swe_router is enabled the helper calls route(), not judge()."""

    def test_swe_router_flag_calls_route_not_judge(
        self, flag_enabled, stub_token, spy_route, spy_judge
    ):
        stub_token("tok-ac12")
        hook._maybe_invoke_swe_router(
            "Write",
            {"file_path": "/repo/foo.py", "content": "x\n"},
            "session-ac12",
        )
        assert len(spy_route) == 1
        assert len(spy_judge) == 0

    def test_no_flag_calls_neither(
        self, flag_disabled, stub_token, spy_route, spy_judge
    ):
        stub_token("tok-noflag")
        hook._maybe_invoke_swe_router(
            "Write",
            {"file_path": "/repo/foo.py", "content": "x\n"},
            "session-noflag",
        )
        assert len(spy_route) == 0
        assert len(spy_judge) == 0

    def test_semantic_gate_only_calls_judge_not_route(
        self, monkeypatch, stub_token, spy_route, spy_judge
    ):
        """When only ``semantic_gate`` is enabled (Phase 1 fallback), the
        legacy judge path runs and route is NOT invoked."""
        import feature_flags
        monkeypatch.setattr(
            feature_flags,
            "is_feature_explicitly_enabled",
            lambda name: name == "semantic_gate",  # only semantic_gate
        )
        stub_token("tok-fallback")
        hook._maybe_invoke_swe_router(
            "Edit",
            {"file_path": "/repo/foo.py", "old_string": "x", "new_string": "y"},
            "session-fallback",
        )
        assert len(spy_route) == 0
        assert len(spy_judge) == 1


# ---------------------------------------------------------------------------
# Default-OFF invariant
# ---------------------------------------------------------------------------


class TestDefaultOff:
    """Without any flag, neither router nor judge runs."""

    def test_default_off_no_calls(
        self, flag_disabled, stub_token, spy_route, spy_judge
    ):
        stub_token("tok-default")
        hook._maybe_invoke_swe_router(
            "Write",
            {"file_path": "/repo/foo.py", "content": "x\n"},
            "session-default",
        )
        assert len(spy_route) == 0
        assert len(spy_judge) == 0
