#!/usr/bin/env python3
"""CI-visible guarantee that GenAI hooks degrade cleanly with no credential.

Issue #1593.

Why this file exists rather than a reference to the existing test
--------------------------------------------------------------------
``plugins/autonomous-dev/tests/test_genai_prompts.py:197-203`` nominally covers
this ground::

    result = analyzer.analyze("test", var="value")
    assert result is None or isinstance(result, str)

That assertion is a **tautology** -- it holds for every possible outcome,
including the broken one where a credential-less client is built and the
resulting ``TypeError`` is swallowed. And it has never run in CI:
``pytest.ini`` sets ``testpaths = tests`` and
``.github/workflows/ci.yml`` runs ``tests/regression/smoke/``, ``tests/genai/``,
``tests/unit/``, ``tests/integration/`` and ``tests/regression/`` --
``plugins/autonomous-dev/tests/`` appears in no workflow.

So the guarantee is re-homed here, under ``tests/unit/`` where CI runs it, with
the assertion tightened from "None or a string" to three specific properties:
the result is ``None``, no SDK client is constructed, and no subprocess is
spawned.

The subprocess assertion is forward-looking on purpose. Part 2 of #1593 adds a
``claude -p`` transport. This file pins that the transport stays opt-in: the
default-constructed analyzer must never spawn a process behind a consumer's
back. Nine files carrying eleven ``GenAIAnalyzer`` call sites depend on that.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"))
sys.path.insert(0, str(_REPO_ROOT / "plugins" / "autonomous-dev" / "lib"))

import genai_utils  # noqa: E402

try:  # pragma: no cover - anthropic is an optional dependency
    import anthropic as _real_anthropic
except ImportError:  # pragma: no cover
    _real_anthropic = None  # type: ignore[assignment]


@pytest.fixture(autouse=True)
def _no_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guarantee the no-credential condition regardless of the dev machine."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)


def _sdk_ctor_spy() -> tuple:
    """Return ``(patcher, spy)`` for ``anthropic.Anthropic`` construction."""
    spy = MagicMock()
    if _real_anthropic is not None:
        return patch.object(_real_anthropic, "Anthropic", spy), spy
    import types

    stub = types.ModuleType("anthropic")
    stub.Anthropic = spy  # type: ignore[attr-defined]
    return patch.dict(sys.modules, {"anthropic": stub}), spy


class TestGenAIAnalyzerDegradation:
    """``GenAIAnalyzer`` must be inert, not merely quiet, without credentials."""

    def test_analyze_returns_none_constructs_nothing_spawns_nothing(self) -> None:
        """The three-part replacement for the tautology.

        Tightened from ``result is None or isinstance(result, str)``, which
        passed for the broken behaviour too.
        """
        patcher, sdk_spy = _sdk_ctor_spy()
        analyzer = genai_utils.GenAIAnalyzer(use_genai=True)

        with patcher:
            with patch.object(subprocess, "run") as run_spy, patch.object(
                subprocess, "Popen"
            ) as popen_spy:
                result = analyzer.analyze("classify {text}", text="hello world")

        assert result is None, (
            f"analyze() returned {result!r} with no credential configured. It "
            f"must return None so callers can distinguish 'GenAI unavailable' "
            f"from a model answer."
        )
        assert sdk_spy.call_count == 0, (
            f"anthropic.Anthropic was constructed {sdk_spy.call_count} time(s) "
            f"with no credential. Issue #1593: that client is truthy, so the "
            f"'if not self.client' guard in analyze() cannot fire and the "
            f"request-time TypeError gets swallowed as an analysis failure."
        )
        assert run_spy.call_count == 0, (
            "analyze() spawned a subprocess. The claude -p transport is Part 2 "
            "and must be opt-in per consumer -- a security hook firing on "
            "every Write/Edit cannot silently gain a multi-second subprocess."
        )
        assert popen_spy.call_count == 0, "analyze() spawned a subprocess via Popen"

    def test_client_is_none_after_lazy_initialization(self) -> None:
        """``self.client`` must actually be ``None``, not a hollow client.

        This is the property the tautological assertion could not see: before
        #1593 ``analyze()`` returned ``None`` *and* ``self.client`` was a live
        credential-less object.
        """
        patcher, _ = _sdk_ctor_spy()
        analyzer = genai_utils.GenAIAnalyzer(use_genai=True)
        with patcher:
            analyzer.analyze("say {word}", word="hi")
        assert analyzer.client is None, (
            f"self.client is {analyzer.client!r} after a no-credential "
            f"analyze(). A truthy client here means the guard at "
            f"genai_utils.py analyze() is unreachable again."
        )

    def test_disabled_analyzer_is_inert(self) -> None:
        """``use_genai=False`` short-circuits before any initialization.

        Permit-side control for the flag itself: the two paths to ``None`` must
        both stay clean, so a green result above cannot be credited to the
        wrong mechanism.
        """
        patcher, sdk_spy = _sdk_ctor_spy()
        analyzer = genai_utils.GenAIAnalyzer(use_genai=False)
        with patcher:
            assert analyzer.analyze("say {word}", word="hi") is None
        assert sdk_spy.call_count == 0
        assert analyzer.client is None

    def test_credentialed_analyzer_still_calls_the_api(self) -> None:
        """WATCHED PERMITTING: with a credential the normal path is unchanged.

        Without this, every assertion above would be satisfied by a
        ``GenAIAnalyzer`` that had simply been broken into always returning
        ``None``.
        """
        fake_message = MagicMock()
        fake_message.content = [MagicMock(text="  IMPLEMENT  ")]
        fake_client = MagicMock()
        fake_client.auth_headers = {"X-Api-Key": "sk-test"}
        fake_client.messages.create.return_value = fake_message

        patcher, sdk_spy = _sdk_ctor_spy()
        sdk_spy.return_value = fake_client

        analyzer = genai_utils.GenAIAnalyzer(use_genai=True)
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
            with patcher:
                result = analyzer.analyze("classify {text}", text="add a feature")

        assert result == "IMPLEMENT", (
            f"Credentialed analyze() returned {result!r}. The happy path "
            f"regressed -- the no-credential assertions above are then "
            f"passing for the wrong reason."
        )
        assert sdk_spy.call_count == 1
        assert fake_client.messages.create.call_count == 1

    def test_public_constructor_signature_is_part1_stable(self) -> None:
        """Part 1 changes no public signature; 12 call sites depend on it."""
        import inspect

        params = list(inspect.signature(genai_utils.GenAIAnalyzer.__init__).parameters)
        assert params == ["self", "model", "max_tokens", "timeout", "use_genai"], (
            f"GenAIAnalyzer.__init__ is now {params}. allow_cli_fallback and "
            f"cli_timeout belong to Part 2 of #1593, not this pass."
        )
