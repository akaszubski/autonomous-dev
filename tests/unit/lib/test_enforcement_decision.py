"""Unit tests for enforcement_decision (Issue #999, Phase E).

Covers the priority chain in should_skip_enforcement:
    1. hard_floor wins over enforcement_off and skip mode.
    2. enforcement off → no skip.
    3. missing session id → no skip.
    4. missing artifact → ambiguous_safety.
    5. classifier fail_open → enforce.
    6. requires_security_audit → enforce.
    7. enforce class → enforce.
    8. skip class → skip.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LIB_PATH = _REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(_LIB_PATH) not in sys.path:
    sys.path.insert(0, str(_LIB_PATH))

from enforcement_decision import should_skip_enforcement  # noqa: E402


# ---------------------------------------------------------------------------
# Helper: simulate the dependencies enforcement_decision lazily imports.
# ---------------------------------------------------------------------------


@pytest.fixture
def patched_deps():
    """Patch is_hard_floor + read_session_mode + should_pipeline_enforce.

    Returns a context-manager-style object exposing setters so each test can
    pin the deps to the relevant configuration.
    """

    class Deps:
        def __init__(self):
            self.hard_floor_return = False
            self.read_session_mode_return = None
            self.should_pipeline_enforce_return = True

        def hard_floor(self, hook_name, function_name=None):
            return self.hard_floor_return

        def read_session_mode(self, session_id):
            return self.read_session_mode_return

        def should_pipeline_enforce(self, intent_class):
            return self.should_pipeline_enforce_return

    deps = Deps()

    with patch("enforcement_decision.__name__", "enforcement_decision"):
        # Patch the lazy-imported functions in their source modules so that
        # enforcement_decision picks up the mocked versions.
        with patch("hard_floor.is_hard_floor", side_effect=deps.hard_floor):
            with patch(
                "session_mode.read_session_mode",
                side_effect=deps.read_session_mode,
            ):
                with patch(
                    "session_mode.should_pipeline_enforce",
                    side_effect=deps.should_pipeline_enforce,
                ):
                    yield deps


class TestPriority1HardFloor:
    def test_hard_floor_wins_over_enforcement_off(self, patched_deps, monkeypatch):
        """Even when enforcement_off would otherwise skip, hard_floor enforces."""
        patched_deps.hard_floor_return = True
        monkeypatch.delenv("INTENT_CLASSIFIER_ENFORCE", raising=False)
        skip, reason = should_skip_enforcement(
            hook_name="unified_pre_tool.py",
            function_name="_detect_git_bypass",
            session_id="abc",
        )
        assert skip is False
        assert reason == "hard_floor"

    def test_hard_floor_wins_over_skip_mode(self, patched_deps, monkeypatch):
        """Hard floor overrides a session-mode that would otherwise skip."""
        patched_deps.hard_floor_return = True
        patched_deps.read_session_mode_return = {
            "intent_class": "conversation",
            "fail_open": False,
            "requires_security_audit": False,
        }
        patched_deps.should_pipeline_enforce_return = False
        monkeypatch.setenv("INTENT_CLASSIFIER_ENFORCE", "true")
        skip, reason = should_skip_enforcement(
            hook_name="unified_pre_tool.py",
            function_name="_detect_git_bypass",
            session_id="abc",
        )
        assert skip is False
        assert reason == "hard_floor"


class TestPriority2EnforcementOff:
    def test_enforcement_off_returns_no_skip(self, patched_deps, monkeypatch):
        """Default (env unset) → no skip with reason enforcement_off."""
        monkeypatch.delenv("INTENT_CLASSIFIER_ENFORCE", raising=False)
        skip, reason = should_skip_enforcement(
            hook_name="plan_gate.py", session_id="abc"
        )
        assert skip is False
        assert reason == "enforcement_off"

    def test_enforcement_off_case_insensitive(self, patched_deps, monkeypatch):
        """'TRUE' is normalized; only literal 'true' (case-i) means on."""
        monkeypatch.setenv("INTENT_CLASSIFIER_ENFORCE", "TRUE")
        # Should reach beyond rule 2 — fall to rule 3 with no session id.
        skip, reason = should_skip_enforcement(
            hook_name="plan_gate.py", session_id=None
        )
        assert skip is False
        assert reason == "no_session_id_safety"

    def test_enforcement_zero_means_off(self, patched_deps, monkeypatch):
        monkeypatch.setenv("INTENT_CLASSIFIER_ENFORCE", "0")
        skip, reason = should_skip_enforcement(
            hook_name="plan_gate.py", session_id="abc"
        )
        assert skip is False
        assert reason == "enforcement_off"


class TestPriority3NoSessionId:
    @pytest.mark.parametrize("sid", [None, "", "unknown"])
    def test_no_session_id_safety(self, patched_deps, monkeypatch, sid):
        """None/empty/unknown session_id → enforce."""
        monkeypatch.setenv("INTENT_CLASSIFIER_ENFORCE", "true")
        skip, reason = should_skip_enforcement(
            hook_name="plan_gate.py", session_id=sid
        )
        assert skip is False
        assert reason == "no_session_id_safety"


class TestPriority4MissingArtifact:
    def test_ambiguous_safety(self, patched_deps, monkeypatch):
        """Artifact missing → ambiguous_safety."""
        monkeypatch.setenv("INTENT_CLASSIFIER_ENFORCE", "true")
        patched_deps.read_session_mode_return = None
        skip, reason = should_skip_enforcement(
            hook_name="plan_gate.py", session_id="real-sid"
        )
        assert skip is False
        assert reason == "ambiguous_safety"


class TestPriority5ClassifierFailOpen:
    def test_classifier_fail_open_enforces(self, patched_deps, monkeypatch):
        """Classifier fell back → enforce."""
        monkeypatch.setenv("INTENT_CLASSIFIER_ENFORCE", "true")
        patched_deps.read_session_mode_return = {
            "intent_class": "conversation",
            "fail_open": True,  # classifier degraded
            "requires_security_audit": False,
        }
        skip, reason = should_skip_enforcement(
            hook_name="plan_gate.py", session_id="real-sid"
        )
        assert skip is False
        assert reason == "classifier_fail_open"


class TestPriority6SecurityAudit:
    def test_security_audit_required_enforces(self, patched_deps, monkeypatch):
        """requires_security_audit → enforce, even for skip class."""
        monkeypatch.setenv("INTENT_CLASSIFIER_ENFORCE", "true")
        patched_deps.read_session_mode_return = {
            "intent_class": "conversation",
            "fail_open": False,
            "requires_security_audit": True,
        }
        # Even though should_pipeline_enforce would say False:
        patched_deps.should_pipeline_enforce_return = False
        skip, reason = should_skip_enforcement(
            hook_name="plan_gate.py", session_id="real-sid"
        )
        assert skip is False
        assert reason == "security_audit_required"


class TestPriority7And8IntentClass:
    def test_implement_mode_enforces(self, patched_deps, monkeypatch):
        """intent_class=implement → enforce."""
        monkeypatch.setenv("INTENT_CLASSIFIER_ENFORCE", "true")
        patched_deps.read_session_mode_return = {
            "intent_class": "implement",
            "fail_open": False,
            "requires_security_audit": False,
        }
        patched_deps.should_pipeline_enforce_return = True
        skip, reason = should_skip_enforcement(
            hook_name="plan_gate.py", session_id="real-sid"
        )
        assert skip is False
        assert reason == "mode_enforce:implement"

    def test_conversation_mode_skips(self, patched_deps, monkeypatch):
        """intent_class=conversation → skip (the only True branch)."""
        monkeypatch.setenv("INTENT_CLASSIFIER_ENFORCE", "true")
        patched_deps.read_session_mode_return = {
            "intent_class": "conversation",
            "fail_open": False,
            "requires_security_audit": False,
        }
        patched_deps.should_pipeline_enforce_return = False
        skip, reason = should_skip_enforcement(
            hook_name="plan_gate.py", session_id="real-sid"
        )
        assert skip is True
        assert reason == "mode_skip:conversation"

    def test_unknown_intent_class_enforces_fail_safe(
        self, patched_deps, monkeypatch
    ):
        """Unknown class → enforce (fail-safe; never skip on uncertainty)."""
        monkeypatch.setenv("INTENT_CLASSIFIER_ENFORCE", "true")
        patched_deps.read_session_mode_return = {
            "intent_class": "totally_made_up_class",
            "fail_open": False,
            "requires_security_audit": False,
        }
        patched_deps.should_pipeline_enforce_return = True  # default-safe
        skip, reason = should_skip_enforcement(
            hook_name="plan_gate.py", session_id="real-sid"
        )
        assert skip is False
        assert reason == "mode_enforce:totally_made_up_class"


class TestNeverRaises:
    def test_internal_exception_returns_safety(self, monkeypatch):
        """If is_hard_floor itself raises, we still return safe (False)."""
        monkeypatch.setenv("INTENT_CLASSIFIER_ENFORCE", "true")

        def boom(*a, **kw):
            raise RuntimeError("fake boom")

        with patch("hard_floor.is_hard_floor", side_effect=boom):
            skip, reason = should_skip_enforcement(
                hook_name="plan_gate.py", session_id="real-sid"
            )
            # is_hard_floor is wrapped in a try/ImportError block; its
            # RuntimeError is caught by the outer try → exception_safety.
            assert skip is False
            assert reason == "exception_safety"


# ---------------------------------------------------------------------------
# Issue #1023 — Non-SWE classes flow through Priority 7/8
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Issue #1024 (M2) — clarified_intent overrides classifier uncertainty
# ---------------------------------------------------------------------------


class TestIssue1024ClarifiedIntent:
    """Priority 4.5 — user-clarified intent bypasses fail_open + audit gates.

    The AskUserQuestion round-trip on AMBIGUOUS classifications sets
    ``clarified_intent`` on the session-mode artifact. When that field is
    present, ``should_skip_enforcement`` MUST honor it ahead of the
    pessimism short-circuits in priorities 5 and 6, because the user has
    explicitly resolved the classifier's uncertainty.

    Security note: SECURITY_CRITICAL only comes from the regex pre-gate
    (intent_classifier.py:649), never AMBIGUOUS, so a clarified intent
    is never offered when a security keyword was matched. The hook layer
    enforces this — the policy layer trusts what's written on the
    artifact.
    """

    def test_clarified_intent_overrides_fail_open(
        self, patched_deps, monkeypatch
    ):
        """Clarified intent + fail_open=True ⇒ trust user's selection."""
        monkeypatch.setenv("INTENT_CLASSIFIER_ENFORCE", "true")
        patched_deps.read_session_mode_return = {
            "intent_class": "ambiguous",
            "fail_open": True,  # would normally short-circuit Priority 5
            "requires_security_audit": True,  # AMBIGUOUS sets this defensively
            "clarified_intent": "implement",
        }
        # implement → enforce per should_pipeline_enforce
        patched_deps.should_pipeline_enforce_return = True
        skip, reason = should_skip_enforcement(
            hook_name="plan_gate.py", session_id="real-sid"
        )
        assert skip is False
        assert reason == "clarified_enforce:implement", (
            f"Priority 4.5 should fire BEFORE fail_open's Priority 5, "
            f"got reason={reason!r}"
        )

    def test_clarified_intent_overrides_security_audit(
        self, patched_deps, monkeypatch
    ):
        """Clarified DOC + requires_security_audit=True ⇒ skip.

        AMBIGUOUS sets requires_security_audit=True defensively. The user
        has now disambiguated to DOC (a skip class). We trust the user.
        Security rationale: AMBIGUOUS never overlaps with SECURITY_CRITICAL
        (which comes from the regex pre-gate), so this branch is safe.
        """
        monkeypatch.setenv("INTENT_CLASSIFIER_ENFORCE", "true")
        patched_deps.read_session_mode_return = {
            "intent_class": "ambiguous",
            "fail_open": False,
            "requires_security_audit": True,  # would normally Priority 6
            "clarified_intent": "doc",
        }
        # doc → skip per should_pipeline_enforce
        patched_deps.should_pipeline_enforce_return = False
        skip, reason = should_skip_enforcement(
            hook_name="plan_gate.py", session_id="real-sid"
        )
        assert skip is True
        assert reason == "clarified_skip:doc", (
            f"Priority 4.5 should fire BEFORE security_audit's Priority 6, "
            f"got reason={reason!r}"
        )

    def test_clarified_intent_skips_when_class_is_skippable(
        self, patched_deps, monkeypatch
    ):
        """Clarified status_query → skip (clarified_skip:status_query)."""
        monkeypatch.setenv("INTENT_CLASSIFIER_ENFORCE", "true")
        patched_deps.read_session_mode_return = {
            "intent_class": "ambiguous",
            "fail_open": False,
            "requires_security_audit": False,
            "clarified_intent": "status_query",
        }
        patched_deps.should_pipeline_enforce_return = False
        skip, reason = should_skip_enforcement(
            hook_name="plan_gate.py", session_id="real-sid"
        )
        assert skip is True
        assert reason == "clarified_skip:status_query"

    def test_clarified_intent_empty_string_falls_through(
        self, patched_deps, monkeypatch
    ):
        """Empty string MUST NOT trigger Priority 4.5 — only non-empty."""
        monkeypatch.setenv("INTENT_CLASSIFIER_ENFORCE", "true")
        patched_deps.read_session_mode_return = {
            "intent_class": "ambiguous",
            "fail_open": True,
            "requires_security_audit": True,
            "clarified_intent": "",  # falsy — must NOT bypass priorities 5/6
        }
        skip, reason = should_skip_enforcement(
            hook_name="plan_gate.py", session_id="real-sid"
        )
        assert skip is False
        # Should fall through to Priority 5 (fail_open).
        assert reason == "classifier_fail_open"

    def test_clarified_intent_none_falls_through(
        self, patched_deps, monkeypatch
    ):
        """None MUST NOT trigger Priority 4.5."""
        monkeypatch.setenv("INTENT_CLASSIFIER_ENFORCE", "true")
        patched_deps.read_session_mode_return = {
            "intent_class": "ambiguous",
            "fail_open": True,
            "requires_security_audit": True,
            "clarified_intent": None,
        }
        skip, reason = should_skip_enforcement(
            hook_name="plan_gate.py", session_id="real-sid"
        )
        assert skip is False
        assert reason == "classifier_fail_open"

    def test_priority_4_5_does_not_bypass_security_critical(
        self, patched_deps, monkeypatch
    ):
        """Priority 4.5 with clarified_intent='security_critical' ⇒ enforce.

        Defense-in-depth: the security claim ``SECURITY_CRITICAL cannot
        bypass enforcement via clarified_intent`` rests on
        ``should_pipeline_enforce`` returning ``True`` for
        ``security_critical``. Even if an attacker writes
        ``clarified_intent='security_critical'`` directly to the artifact
        (bypassing ``persist_intent_answer.py`` validation),
        ``should_pipeline_enforce`` returns ``True`` for security_critical
        so Priority 4.5 still enforces. Defense-in-depth.

        This test pins the policy contract directly — independent of the
        CLI gate in ``persist_intent_answer.py`` — so a future refactor
        cannot accidentally make Priority 4.5 skip for a class that
        ``should_pipeline_enforce`` would mark as enforce.

        Cross-references audit Finding 2 (HIGH, OWASP A08).
        """
        monkeypatch.setenv("INTENT_CLASSIFIER_ENFORCE", "true")
        patched_deps.read_session_mode_return = {
            "intent_class": "ambiguous",
            "fail_open": True,
            "requires_security_audit": True,
            "clarified_intent": "security_critical",
        }
        # The real should_pipeline_enforce returns True for security_critical
        # (it's NOT in _SKIP_INTENT_CLASSES). Mirror that here.
        patched_deps.should_pipeline_enforce_return = True
        skip, reason = should_skip_enforcement(
            hook_name="plan_gate.py", session_id="real-sid"
        )
        assert skip is False, (
            "clarified_intent='security_critical' must NEVER cause skip — "
            "should_pipeline_enforce returns True for security_critical, "
            "so Priority 4.5 falls into the clarified_enforce branch."
        )
        assert reason == "clarified_enforce:security_critical", (
            f"reason should be clarified_enforce:security_critical to make "
            f"the audit trail explicit; got {reason!r}"
        )


class TestIssue1023NonSWEClasses:
    """The 4 new skip-eligible classes (#1023) MUST:

      1. Cause Priority 8 to skip when no security audit is required.
      2. Defer to Priority 6 (security_audit_required) when set — proves the
         skip-eligibility never overrides security gating.
    """

    NEW_CLASSES = ("exploration", "triage", "remote_ops", "scratch")

    @pytest.mark.parametrize("class_value", NEW_CLASSES)
    def test_new_class_skips_when_no_security_audit(
        self, patched_deps, monkeypatch, class_value
    ):
        """Each new class with requires_security_audit=False ⇒ skip."""
        monkeypatch.setenv("INTENT_CLASSIFIER_ENFORCE", "true")
        patched_deps.read_session_mode_return = {
            "intent_class": class_value,
            "fail_open": False,
            "requires_security_audit": False,
        }
        patched_deps.should_pipeline_enforce_return = False
        skip, reason = should_skip_enforcement(
            hook_name="plan_gate.py", session_id="real-sid"
        )
        assert skip is True, f"{class_value!r} should skip when no security audit"
        assert reason == f"mode_skip:{class_value}"

    @pytest.mark.parametrize("class_value", NEW_CLASSES)
    def test_new_class_yields_to_security_audit(
        self, patched_deps, monkeypatch, class_value
    ):
        """Priority 6 wins: requires_security_audit=True ⇒ enforce regardless."""
        monkeypatch.setenv("INTENT_CLASSIFIER_ENFORCE", "true")
        patched_deps.read_session_mode_return = {
            "intent_class": class_value,
            "fail_open": False,
            "requires_security_audit": True,
        }
        patched_deps.should_pipeline_enforce_return = False
        skip, reason = should_skip_enforcement(
            hook_name="plan_gate.py", session_id="real-sid"
        )
        assert skip is False, (
            f"{class_value!r} must NOT skip when security audit is required"
        )
        assert reason == "security_audit_required"
