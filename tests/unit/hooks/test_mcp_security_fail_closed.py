"""Fail-closed enforcement for MCP security validation (Issues #401, #1471).

Background — the bug this file locks out:

``validate_mcp_security`` in ``unified_pre_tool.py`` had two handlers that
looked alike and were treated as one:

1. ``except ImportError`` — the validator module is not installed. Issue #401
   deliberately chose default-allow here, because the previous behaviour fell
   through to an allow-list that produced recurring "Not whitelisted"
   regressions every time Claude Code shipped a new tool. This is *"we chose
   not to check"*, and it is correct.
2. ``except Exception`` — the validator was **present** and its execution
   **crashed**. This is *"we tried to check and do not know the answer"*, and
   it was also returning ``allow``. Issue #401's rationale says nothing about
   this state; encoding it as allow is the same INV-7 breach as #1471 — a gate
   that could not verify reported "verified, pass".

The fix changes only (2) to refuse. (1) is untouched, down to the exact
message string, and this file locks that byte-for-byte.

Path depth: tests/unit/hooks/ -> parents[3] == repo root.
"""

import contextlib
import logging
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(HOOK_DIR))
sys.path.insert(0, str(LIB_DIR))

import unified_pre_tool as hook

MCP_TOOL = "mcp__example__do_thing"

# The exact string the #401 default-allow branch has always returned. Locked
# byte-for-byte: a careless fail-closed change is most likely to break THIS.
ABSENT_MESSAGE = "MCP security validator unavailable — default allow"


class _ImportBlocker:
    """``sys.meta_path`` finder that makes one module name unimportable.

    meta_path runs ahead of every path-based finder, so the hook's own
    ``sys.path`` preamble cannot silently outrank the fault and hand back an
    unfaulted run.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.hits = 0

    def find_spec(self, fullname: str, path=None, target=None):
        if fullname == self.name:
            self.hits += 1
            raise ImportError(f"test fault: {fullname} blocked by meta_path")
        return None


@contextlib.contextmanager
def _validator_absent():
    """Guarantee ``mcp_security_validator`` is unimportable inside the block."""
    blocker = _ImportBlocker("mcp_security_validator")
    saved = sys.modules.pop("mcp_security_validator", None)
    sys.meta_path.insert(0, blocker)
    try:
        yield blocker
    finally:
        sys.meta_path.remove(blocker)
        if saved is not None:
            sys.modules["mcp_security_validator"] = saved


@contextlib.contextmanager
def _validator_present(validate_fn):
    """Install a stub ``mcp_security_validator`` exposing ``validate_mcp_operation``."""
    import types

    module = types.ModuleType("mcp_security_validator")
    module.validate_mcp_operation = validate_fn  # type: ignore[attr-defined]
    saved = sys.modules.pop("mcp_security_validator", None)
    sys.modules["mcp_security_validator"] = module
    try:
        yield module
    finally:
        sys.modules.pop("mcp_security_validator", None)
        if saved is not None:
            sys.modules["mcp_security_validator"] = saved


CRASH_MODES = [
    pytest.param(RuntimeError("validator exploded"), id="RuntimeError"),
    pytest.param(AttributeError("'Request' object has no attribute 'url'"), id="AttributeError"),
    pytest.param(TypeError("validate_mcp_operation() takes 1 positional argument"), id="TypeError"),
    pytest.param(ValueError("unparseable target"), id="ValueError"),
]


class TestFaultInjectorsAreWorkingInstruments:
    """Controls for both injectors — a probe that cannot fail cannot inform."""

    def test_absent_injector_actually_blocks(self) -> None:
        """Positive control: the import really fails inside the block."""
        with _validator_absent() as blocker:
            with pytest.raises(ImportError):
                __import__("mcp_security_validator")
        assert blocker.hits >= 1, "Blocker never fired — no fault was injected"

    def test_present_injector_actually_installs(self) -> None:
        """Positive control: the stub is importable and is the one that runs."""
        sentinel = []

        def _ok(tool_name, tool_input):
            sentinel.append(tool_name)
            return (True, "stub says fine")

        with _validator_present(_ok):
            decision, reason = hook.validate_mcp_security(MCP_TOOL, {})
        assert sentinel == [MCP_TOOL], "Stub validator was never invoked"
        assert decision == "allow"
        assert "stub says fine" in reason

    def test_probe_can_produce_a_deny(self) -> None:
        """Must-deny control: a validator that reports unsafe still denies."""
        with _validator_present(lambda t, i: (False, "path traversal detected")):
            decision, reason = hook.validate_mcp_security(MCP_TOOL, {})
        assert decision == "deny", f"Probe cannot produce a deny at all: {reason!r}"
        assert "path traversal detected" in reason


class TestValidatorCrashFailsClosed:
    """REFUSES arm: validator PRESENT but raising must DENY.

    Covered class: any unexpected exception escaping ``validate_mcp_operation``
    — bad input handling, upstream API drift, arity change, internal bug. All
    of them previously returned ``allow``.
    """

    @pytest.mark.parametrize("exc", CRASH_MODES)
    def test_crash_during_validation_denies(self, exc: Exception, caplog) -> None:
        def _boom(tool_name, tool_input):
            raise exc

        with caplog.at_level(logging.ERROR):
            with _validator_present(_boom):
                decision, reason = hook.validate_mcp_security(
                    MCP_TOOL, {"path": "../../etc/passwd"}
                )

        assert decision == "deny", (
            f"Validator crash failed OPEN on {type(exc).__name__} — "
            f"unverified was encoded as verified. reason={reason!r}"
        )
        assert type(exc).__name__ in reason, f"Refusal must name the failure: {reason!r}"
        assert "REQUIRED NEXT ACTION" in reason, "Refusal must state how to clear it"
        assert "PRE_TOOL_MCP_SECURITY" in reason, "Refusal must name the emergency override"
        assert caplog.records, "A fail-closed refusal must leave a log trace"

    def test_crash_message_does_not_claim_the_validator_was_absent(self) -> None:
        """The two states must stay distinguishable in the reason string."""
        with _validator_present(lambda t, i: (_ for _ in ()).throw(RuntimeError("boom"))):
            _, reason = hook.validate_mcp_security(MCP_TOOL, {})
        assert ABSENT_MESSAGE not in reason, (
            "A crash must not be reported with the 'validator unavailable' message"
        )
        assert "crashed" in reason


class TestAbsentValidatorStillAllows:
    """PERMITTING arm and the Issue #401 control — do not break this.

    Deliberately a different shape from the crash reproducer: nothing raises
    during validation because validation never starts.
    """

    def test_absent_validator_allows(self) -> None:
        with _validator_absent() as blocker:
            decision, reason = hook.validate_mcp_security(MCP_TOOL, {"path": "/tmp/x"})
        assert blocker.hits >= 1, "Fault never fired — result proves nothing"
        assert decision == "allow", f"Issue #401 default-allow regressed: {reason!r}"

    def test_absent_validator_message_is_byte_identical(self) -> None:
        """Lock the #401 message exactly — no decoration, no suffix, no rewording."""
        with _validator_absent():
            _, reason = hook.validate_mcp_security(MCP_TOOL, {"path": "/tmp/x"})
        assert reason == ABSENT_MESSAGE, (
            f"Issue #401 message changed.\n  expected: {ABSENT_MESSAGE!r}\n  actual:   {reason!r}"
        )

    def test_absent_validator_allows_even_a_suspicious_looking_input(self) -> None:
        """#401 is default-allow-when-absent; absence does not become deny."""
        with _validator_absent():
            decision, _ = hook.validate_mcp_security(
                MCP_TOOL, {"path": "../../../etc/shadow", "url": "http://169.254.169.254/"}
            )
        assert decision == "allow", "Absent validator must not start denying"


class TestUnrelatedPathsUnaffected:
    """Ordinary traffic must be untouched by either change."""

    @pytest.mark.parametrize("tool", ["Read", "Write", "Edit", "Bash", "Task"])
    def test_native_tools_short_circuit_before_any_handler(self, tool: str) -> None:
        decision, reason = hook.validate_mcp_security(tool, {"file_path": "/tmp/x"})
        assert decision == "allow"
        assert "MCP security not applicable" in reason

    def test_layer_disabled_short_circuits(self, monkeypatch) -> None:
        """The documented off-switch still bypasses the layer entirely."""
        monkeypatch.setenv("PRE_TOOL_MCP_SECURITY", "false")

        def _boom(tool_name, tool_input):
            raise RuntimeError("must never be reached")

        with _validator_present(_boom):
            decision, reason = hook.validate_mcp_security(MCP_TOOL, {})
        assert decision == "allow"
        assert reason == "MCP security disabled"

    def test_healthy_validator_allow_path_unchanged(self) -> None:
        with _validator_present(lambda t, i: (True, "no risks found")):
            decision, reason = hook.validate_mcp_security(MCP_TOOL, {"path": "/tmp/x"})
        assert decision == "allow"
        assert reason == "MCP Security: no risks found"
