"""Pure policy layer for Phase E enforcement skip decisions (Issue #999).

This module contains zero filesystem or stdin side effects. Given a hook name,
optional function name, and optional session_id, it consults:

- ``hard_floor.is_hard_floor``      (Phase C catastrophe registry)
- ``session_mode.read_session_mode`` (Phase D artifact reader)
- ``session_mode.should_pipeline_enforce`` (intent-class allowlist)

and returns a ``(skip, reason)`` tuple. The wrapping hook decides what to do
with the result; this layer is pure policy.

Priority (first match wins) — 9 priorities total:
    1. ``is_hard_floor(...)`` true       → ``(False, "hard_floor")``
    2. ``INTENT_CLASSIFIER_ENFORCE`` not "true" → ``(False, "enforcement_off")``
    3. session_id missing/unknown        → ``(False, "no_session_id_safety")``
    4. artifact missing or stale         → ``(False, "ambiguous_safety")``
    4.5. ``mode["clarified_intent"]`` set → trust user's disambiguation
         (``(False, f"clarified_enforce:{cls}")`` or
         ``(True, f"clarified_skip:{cls}")``). This bypasses 5 and 6 because
         the user has explicitly overridden the classifier's uncertainty.
    5. ``mode["fail_open"]`` true        → ``(False, "classifier_fail_open")``
    6. ``mode["requires_security_audit"]`` true → ``(False, "security_audit_required")``
    7. ``should_pipeline_enforce(...)`` true → ``(False, f"mode_enforce:{intent_class}")``
    8. else                              → ``(True, f"mode_skip:{intent_class}")``

The fail-safe direction across the board is "enforce" (return ``False``):
when in doubt, run the existing gate. The only ``True`` returns are rule 4.5
(user-clarified skip class) and rule 8 (a fully-qualified, classifier-
confident, non-security skip class).

Security note for Priority 4.5: SECURITY_CRITICAL only comes from the regex
pre-gate (intent_classifier.py:649) and is never AMBIGUOUS, so a clarified
intent is never offered when a security keyword was matched. The
AskUserQuestion round-trip ONLY fires on AMBIGUOUS — see
unified_prompt_validator.py.

Issue: #999 (Phase E — pipeline-gate hook cutover).
Issue: #1024 (M2 — AskUserQuestion round-trip on AMBIGUOUS classifications).
"""

from __future__ import annotations

import os

__all__ = ["should_skip_enforcement"]


def _enforcement_enabled() -> bool:
    """Return True iff INTENT_CLASSIFIER_ENFORCE env var is the literal ``"true"``.

    Case-insensitive. Any other value (including unset, empty, "0", "false",
    "yes", "1") returns False — the rollout knob is opt-in only.
    """
    raw = os.environ.get("INTENT_CLASSIFIER_ENFORCE", "")
    if not isinstance(raw, str):
        return False
    return raw.strip().lower() == "true"


def should_skip_enforcement(
    *,
    hook_name: str,
    function_name: str | None = None,
    session_id: str | None = None,
) -> tuple[bool, str]:
    """Return (skip, reason) for Phase E hook gating. NEVER raises.

    See module docstring for the priority order. The reason string is the
    canonical machine-readable name of the rule that fired — telemetry
    consumers parse on this prefix (e.g. ``"mode_skip:conversation"``).

    Args:
        hook_name: Filename of the calling hook (e.g.
            ``"unified_pre_tool.py"``).
        function_name: Optional function name within the hook for fine-grained
            hard-floor matching.
        session_id: The session id resolved by the calling hook (may be
            ``None`` if stdin had no usable id).

    Returns:
        Tuple ``(skip: bool, reason: str)``. ``skip == True`` means the
        calling check SHOULD be bypassed. ``skip == False`` means the gate
        runs as it does today — including all hard-floor catastrophe checks.
        On any internal exception, returns ``(False, "exception_safety")``
        so the safe default (enforce) wins.
    """
    try:
        # Priority 1: hard floor wins over everything. We import lazily so
        # this module remains importable in environments where the registry
        # is absent (e.g. partial deploy mid-rollout).
        try:
            from hard_floor import is_hard_floor  # type: ignore[import-not-found]

            if is_hard_floor(hook_name, function_name):
                return (False, "hard_floor")
        except ImportError:
            # Registry missing — be conservative and treat the hook as not
            # hard-floor; the next rules will still default-safe to enforce
            # when nothing else applies.
            pass

        # Priority 2: enforcement opt-in. Default-off until the rollout flag
        # flips repo-wide.
        if not _enforcement_enabled():
            return (False, "enforcement_off")

        # Priority 3: cannot key off a session without a session id. Default
        # to enforce; the harness already runs hooks correctly without
        # session-mode context.
        if session_id is None or session_id == "" or session_id == "unknown":
            return (False, "no_session_id_safety")

        # Priority 4: missing or stale artifact. This is the "ambiguous"
        # branch — we don't know what the session is doing, so we keep the
        # gate hot.
        try:
            from session_mode import (  # type: ignore[import-not-found]
                read_session_mode,
                should_pipeline_enforce,
            )
        except ImportError:
            return (False, "exception_safety")

        mode = read_session_mode(session_id)
        if mode is None:
            return (False, "ambiguous_safety")

        # Priority 4.5 (Issue #1024 M2): user clarification overrides the
        # classifier's uncertainty. When the classifier returned AMBIGUOUS,
        # fail_open=True and requires_security_audit=True (set defensively
        # in intent_classifier _fail_open). The user has now disambiguated
        # via AskUserQuestion, so we trust their selection and skip the
        # pessimism short-circuits in priorities 5 and 6.
        #
        # Security rationale: SECURITY_CRITICAL comes from the regex
        # pre-gate (intent_classifier.py:649), never AMBIGUOUS. A clarified
        # intent is never offered when a security keyword was matched, so
        # this branch cannot be used to bypass the security gate.
        clarified = mode.get("clarified_intent")
        if isinstance(clarified, str) and clarified:
            if should_pipeline_enforce(clarified):
                return (False, f"clarified_enforce:{clarified}")
            return (True, f"clarified_skip:{clarified}")

        # Priority 5: classifier itself fell back. Don't trust the
        # intent_class — keep enforcement hot.
        if mode.get("fail_open") is True:
            return (False, "classifier_fail_open")

        # Priority 6: any session that touched a security keyword keeps the
        # gates hot, even if intent_class would otherwise be a skip class.
        if mode.get("requires_security_audit") is True:
            return (False, "security_audit_required")

        # Priority 7 / 8: the intent class drives the final decision.
        intent_class = mode.get("intent_class", "")
        if should_pipeline_enforce(intent_class):
            return (False, f"mode_enforce:{intent_class}")
        return (True, f"mode_skip:{intent_class}")

    except Exception:
        # Fail-safe: any unexpected failure inside the policy layer →
        # enforce. The hook decision path is load-bearing; we never want
        # to skip a gate because we hit a weird exception here.
        return (False, "exception_safety")
