#!/usr/bin/env python3
"""Credential resolution chain for GenAI hooks (Issue #1593).

Covers ``lib/genai_credentials.get_anthropic_client`` and the delegation from
``hooks/genai_utils.GenAIAnalyzer._initialize_client`` to it.

The bug being locked down: ``Anthropic()`` does **not** raise when no credential
is configured. It returns a truthy client with ``api_key=None`` and the
``TypeError`` fires at request time, where ``genai_utils.analyze`` swallowed it.
So ``self.client`` was always truthy, the ``if not self.client`` guard never
fired, and a missing credential was indistinguishable from a model refusal.

No test here performs a real network call. ``anthropic.Anthropic`` is patched
wherever a client would otherwise be constructed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"))
sys.path.insert(0, str(_REPO_ROOT / "plugins" / "autonomous-dev" / "lib"))

import genai_credentials  # noqa: E402
import genai_utils  # noqa: E402
from genai_credentials import (  # noqa: E402
    API_KEY_ENV_VAR,
    AUTH_TOKEN_ENV_VAR,
    get_anthropic_client,
)

# ``anthropic`` is an OPTIONAL runtime dependency (it is not declared in
# pyproject.toml). Tests must not require it, but where it IS present we
# strengthen assertions with the real SDK surface rather than trusting a mock.
try:  # pragma: no cover - availability varies by environment
    import anthropic as _real_anthropic
except ImportError:  # pragma: no cover
    _real_anthropic = None  # type: ignore[assignment]


@pytest.fixture(autouse=True)
def _clear_anthropic_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove inherited credentials so tests never depend on the dev machine.

    Without this an engineer with ``ANTHROPIC_API_KEY`` exported would see the
    no-credential tests pass for the wrong reason.
    """
    monkeypatch.delenv(API_KEY_ENV_VAR, raising=False)
    monkeypatch.delenv(AUTH_TOKEN_ENV_VAR, raising=False)
    monkeypatch.delenv("DEBUG_GENAI", raising=False)


class _StubClient:
    """Minimal stand-in for an SDK client with a controllable auth surface."""

    def __init__(self, auth_headers: Optional[dict] = None) -> None:
        if auth_headers is not None:
            self.auth_headers = auth_headers


class _NoAuthHeadersClient:
    """Stand-in for an SDK version predating the ``auth_headers`` property."""


# ---------------------------------------------------------------------------
# The sanctioned helper: lib/genai_credentials.py
# ---------------------------------------------------------------------------


class TestGetAnthropicClient:
    """Behaviour of the one sanctioned construction site."""

    def test_no_credentials_returns_none(self) -> None:
        """Core regression for #1593: no credential must yield ``None``.

        Before this change the equivalent code path returned a truthy,
        credential-less client that failed only at request time.
        """
        with _patched_anthropic(MagicMock()):
            assert get_anthropic_client() is None

    def test_credentialless_client_is_never_constructed(self) -> None:
        """The client must not merely be discarded -- it must never be built.

        This is the actual #1593 property. A fix that constructs and then
        returns ``None`` would still pay the httpx setup cost and would still
        leave a usable-looking object one refactor away from being returned.
        """
        fake_ctor = MagicMock()
        with _patched_anthropic(fake_ctor):
            result = get_anthropic_client()
        assert result is None
        assert fake_ctor.call_count == 0, (
            f"Anthropic was constructed {fake_ctor.call_count} time(s) despite "
            f"no credential being available. Not constructing is the property "
            f"Issue #1593 is about."
        )

    def test_api_key_env_var_is_passed_as_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``ANTHROPIC_API_KEY`` must reach the SDK as ``api_key=``."""
        monkeypatch.setenv(API_KEY_ENV_VAR, "sk-test-key")
        fake_ctor = MagicMock(return_value=_StubClient({"X-Api-Key": "sk-test-key"}))
        with _patched_anthropic(fake_ctor):
            client = get_anthropic_client()
        assert client is not None
        fake_ctor.assert_called_once_with(api_key="sk-test-key")

    def test_auth_token_only_is_passed_as_auth_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``ANTHROPIC_AUTH_TOKEN`` alone must reach the SDK as ``auth_token=``."""
        monkeypatch.setenv(AUTH_TOKEN_ENV_VAR, "tok-abc")
        fake_ctor = MagicMock(return_value=_StubClient({"Authorization": "Bearer tok-abc"}))
        with _patched_anthropic(fake_ctor):
            client = get_anthropic_client()
        assert client is not None
        fake_ctor.assert_called_once_with(auth_token="tok-abc")

    def test_api_key_wins_over_auth_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With both set, the API key wins -- matching the SDK's own order."""
        monkeypatch.setenv(API_KEY_ENV_VAR, "sk-wins")
        monkeypatch.setenv(AUTH_TOKEN_ENV_VAR, "tok-loses")
        fake_ctor = MagicMock(return_value=_StubClient({"X-Api-Key": "sk-wins"}))
        with _patched_anthropic(fake_ctor):
            get_anthropic_client()
        fake_ctor.assert_called_once_with(api_key="sk-wins")

    def test_empty_string_credential_is_rejected_without_constructing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``ANTHROPIC_API_KEY=""`` must be caught by the ENV pre-check.

        This is the case where the two layers provably diverge. The
        ``auth_headers`` probe is TRUTHY for an empty API key
        (``{'X-Api-Key': ''}``) while ``_validate_headers`` still raises
        ``TypeError``. Layer 2 therefore cannot catch this; layer 1 must.
        """
        monkeypatch.setenv(API_KEY_ENV_VAR, "")
        fake_ctor = MagicMock()
        with _patched_anthropic(fake_ctor):
            assert get_anthropic_client() is None
        assert fake_ctor.call_count == 0

        if _real_anthropic is not None:
            # Premise for the paragraph above, asserted against the executing
            # SDK rather than assumed. If this ever fails, the divergence has
            # closed and the layering rationale must be re-examined.
            real_client = _real_anthropic.Anthropic(api_key="")
            assert bool(real_client.auth_headers) is True, (
                "premise: the real SDK reports TRUTHY auth_headers for an "
                "empty api_key, which is why layer 1 (env pre-check) is the "
                "authoritative check and layer 2 is defence in depth."
            )

    def test_whitespace_only_credential_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A whitespace-only value is never a real credential."""
        monkeypatch.setenv(API_KEY_ENV_VAR, "   \t ")
        fake_ctor = MagicMock()
        with _patched_anthropic(fake_ctor):
            assert get_anthropic_client() is None
        assert fake_ctor.call_count == 0

    def test_client_with_empty_auth_headers_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Layer 2: env looked set but the SDK adopted no credential.

        Pins the ``auth_headers`` post-check as load-bearing rather than
        incidental -- deleting it must turn this test red.
        """
        monkeypatch.setenv(API_KEY_ENV_VAR, "sk-looks-fine")
        fake_ctor = MagicMock(return_value=_StubClient({}))
        with _patched_anthropic(fake_ctor):
            assert get_anthropic_client() is None
        assert fake_ctor.call_count == 1, "the client IS constructed, then discarded"

    def test_client_without_auth_headers_property_is_accepted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An SDK version lacking ``auth_headers`` must not crash the helper.

        The probe degrades to the env pre-check rather than raising
        ``AttributeError``.
        """
        monkeypatch.setenv(API_KEY_ENV_VAR, "sk-old-sdk")
        stub = _NoAuthHeadersClient()
        assert not hasattr(stub, "auth_headers"), "premise: the stub lacks the property"
        with _patched_anthropic(MagicMock(return_value=stub)):
            assert get_anthropic_client() is stub

    def test_import_error_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """INV-8: a missing SDK is a ``None``, never an exception."""
        monkeypatch.setenv(API_KEY_ENV_VAR, "sk-present")
        monkeypatch.setitem(sys.modules, "anthropic", None)
        # ``sys.modules[name] = None`` makes ``import anthropic`` raise ImportError.
        assert get_anthropic_client() is None

    def test_construction_exception_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A raising constructor is reported as ``None``, not propagated."""
        monkeypatch.setenv(API_KEY_ENV_VAR, "sk-present")
        with _patched_anthropic(MagicMock(side_effect=RuntimeError("boom"))):
            assert get_anthropic_client() is None

    def test_purpose_is_keyword_only_and_optional(self) -> None:
        """``purpose`` is diagnostics-only and must never be positional."""
        import inspect

        sig = inspect.signature(get_anthropic_client)
        assert list(sig.parameters) == ["purpose"]
        assert sig.parameters["purpose"].kind is inspect.Parameter.KEYWORD_ONLY
        assert sig.parameters["purpose"].default == ""

    def test_real_sdk_exposes_the_mocked_auth_headers_surface(self) -> None:
        """Mocked-surface canary: ``auth_headers`` must exist on the real class.

        Every test above stubs ``auth_headers``. If the SDK renamed or removed
        it, those stubs would keep passing while production silently lost
        layer 2.

        Enforcement scope, stated rather than assumed: ``anthropic`` is an
        OPTIONAL dependency. ``.github/workflows/ci.yml`` installs it for the
        smoke job but NOT for the unit job, so this canary is live on developer
        machines and in any environment carrying the SDK, and degrades to the
        contract assertion below where it is absent. It is deliberately not a
        hard failure on absence -- a permanently-red check in the unit job
        would train everyone to ignore this file.
        """
        if _real_anthropic is None:
            # No SDK: the guarantee that still has to hold is INV-8.
            assert (
                get_anthropic_client() is None
            ), "with no anthropic SDK installed the helper must return None"
            return
        assert hasattr(_real_anthropic.Anthropic, "auth_headers"), (
            "anthropic.Anthropic no longer exposes 'auth_headers'. "
            "genai_credentials layer 2 is now dead code and every stub in "
            "this file simulates a method that does not exist."
        )


# ---------------------------------------------------------------------------
# The delegation: hooks/genai_utils.py -> lib/genai_credentials.py
# ---------------------------------------------------------------------------


class TestGenAIUtilsDelegation:
    """``_initialize_client`` must go through the sanctioned helper."""

    def test_initialize_client_is_none_without_credentials(self) -> None:
        """RED before #1593, green after: no credential means ``client is None``.

        Previously ``Anthropic()`` returned a truthy credential-less client, so
        ``self.client`` was never ``None`` and the guard in ``analyze()`` at
        ``genai_utils.py:212-213`` could not fire.
        """
        analyzer = genai_utils.GenAIAnalyzer(use_genai=True)
        with _patched_anthropic(MagicMock(return_value=_StubClient({}))):
            analyzer._initialize_client()
        assert analyzer.client is None

    def test_initialize_client_constructs_nothing_without_credentials(self) -> None:
        """RED before #1593: the SDK must not be constructed at all."""
        analyzer = genai_utils.GenAIAnalyzer(use_genai=True)
        fake_ctor = MagicMock()
        with _patched_anthropic(fake_ctor):
            analyzer._initialize_client()
        assert fake_ctor.call_count == 0, (
            f"genai_utils constructed Anthropic {fake_ctor.call_count} time(s) "
            f"with no credential present. It must delegate to "
            f"genai_credentials.get_anthropic_client, which does not construct."
        )

    def test_initialize_client_uses_the_sanctioned_helper(self) -> None:
        """Delegation is behavioural, not incidental: the helper's return wins.

        RED before #1593 -- ``_initialize_client`` built its own client and
        ignored the helper entirely.
        """
        sentinel = _StubClient({"X-Api-Key": "sk-from-helper"})
        analyzer = genai_utils.GenAIAnalyzer(use_genai=True)
        with patch.object(
            genai_credentials, "get_anthropic_client", return_value=sentinel
        ) as helper:
            analyzer._initialize_client()
        assert analyzer.client is sentinel, (
            "genai_utils did not use the client returned by "
            "genai_credentials.get_anthropic_client -- it is still "
            "constructing its own."
        )
        assert helper.call_count == 1

    def test_initialize_client_survives_helper_import_failure(self) -> None:
        """If the lib bridge breaks, degrade to ``None`` rather than raising."""
        analyzer = genai_utils.GenAIAnalyzer(use_genai=True)
        with patch.dict(sys.modules, {"genai_credentials": None}):
            analyzer._initialize_client()
        assert analyzer.client is None

    def test_analyze_returns_none_without_credentials(self) -> None:
        """End of the chain: the public API degrades cleanly."""
        analyzer = genai_utils.GenAIAnalyzer(use_genai=True)
        with _patched_anthropic(MagicMock()):
            assert analyzer.analyze("say {word}", word="hi") is None

    def test_public_init_signature_is_unchanged(self) -> None:
        """12 call sites across 10 files depend on this signature (#1593 Part 1).

        Part 1 must be byte-identical at the call boundary. ``allow_cli_fallback``
        and ``cli_timeout`` belong to Part 2 and must not appear here yet.
        """
        import inspect

        sig = inspect.signature(genai_utils.GenAIAnalyzer.__init__)
        assert list(sig.parameters) == [
            "self",
            "model",
            "max_tokens",
            "timeout",
            "use_genai",
        ], f"GenAIAnalyzer.__init__ signature changed to {list(sig.parameters)}"
        assert sig.parameters["use_genai"].default is True


def _patched_anthropic(ctor: Any):
    """Patch ``anthropic.Anthropic`` so no real client is ever constructed.

    Works whether or not the real package is installed: when it is absent a
    stub module is injected so the ``from anthropic import Anthropic`` inside
    the helper still resolves to the mock.
    """
    if _real_anthropic is not None:
        return patch.object(_real_anthropic, "Anthropic", ctor)

    import types

    stub = types.ModuleType("anthropic")
    stub.Anthropic = ctor  # type: ignore[attr-defined]
    return patch.dict(sys.modules, {"anthropic": stub})
