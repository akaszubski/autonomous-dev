#!/usr/bin/env python3
"""Sanctioned construction site for the Anthropic SDK client (Issue #1593).

This module is the **one canonical way** to obtain an ``anthropic.Anthropic``
client in this repository. Every other module should call
:func:`get_anthropic_client` rather than constructing the SDK client directly.

Why this module exists
----------------------
``Anthropic()`` does **not** raise when no credential is present. Verified
against the executing SDK (anthropic 0.84.0, ``/opt/homebrew/lib/python3.14``)::

    >>> c = Anthropic()            # no ANTHROPIC_API_KEY, no ANTHROPIC_AUTH_TOKEN
    >>> bool(c)                    # True  -- a truthy, credential-less client
    >>> c.api_key, c.auth_token    # (None, None)

The failure is deferred to request time, where ``_validate_headers``
(``_client.py:185``) raises ``TypeError("Could not resolve authentication
method...")``. In ``hooks/genai_utils.py`` that ``TypeError`` was swallowed by a
blanket ``except Exception`` and reported as "GenAI analysis failed", making a
missing credential indistinguishable from a model refusal. A
"return ``None`` when construction fails" fix is therefore a **no-op** -- the
construction never fails. The fix has to be a *pre-flight* check.

The two-layer check
-------------------
Layer 1 -- **env pre-check** (authoritative). If neither ``ANTHROPIC_API_KEY``
nor ``ANTHROPIC_AUTH_TOKEN`` holds a non-blank value, return ``None`` *without
constructing a client at all*. Not constructing is the property Issue #1593 is
about.

Layer 2 -- **post-construction ``auth_headers`` probe** (defence in depth). The
SDK exposes a public, network-free validity probe at ``_client.py:155-158``::

    @property
    def auth_headers(self) -> dict[str, str]:
        return {**self._api_key_auth, **self._bearer_auth}

``_api_key_auth`` (``:160-165``) is ``{}`` when ``api_key is None``;
``_bearer_auth`` (``:167-172``) is ``{}`` when ``auth_token is None``.

**Layer 2 is an over-approximation of ``_validate_headers``, not the same
predicate.** Measured against 0.84.0::

    no creds      auth_headers={}                  falsy   -> TypeError
    api_key=""    auth_headers={'X-Api-Key': ''}   TRUTHY  -> TypeError   <- diverge
    api_key="x"   auth_headers={'X-Api-Key': 'x'}  truthy  -> AuthenticationError

``auth_headers`` reports credential *presence*; ``_validate_headers``
(``_client.py:186``) tests header *value* truthiness. They agree for ``None``
and disagree for the empty string. **The empty-string case is caught by layer 1,
not by layer 2** -- which is precisely why both layers exist. Layer 2 earns its
place by honouring the SDK's own resolution order (explicit argument, then env),
rather than re-implementing SDK-internal precedence in this module.

Known limitation, recorded rather than hidden: ``_validate_headers`` also
returns early (``_client.py:190-194``) when a caller passes ``Omit()`` for the
auth headers. No caller in this repository does, so layer 2 is not weakened in
practice -- but a future caller that did would slip past it.

Credentials this module deliberately does NOT use
-------------------------------------------------
* The macOS keychain ``accessToken`` -- it expires hourly, so a client built
  from it succeeds in test and fails in production an hour later.
* A Claude Code OAuth token passed as ``auth_token`` -- the API rejects it
  without the unsupported ``anthropic-beta: oauth-2025-04-20`` header
  (anthropics/claude-code#37205, closed "not planned").

Sites deliberately NOT migrated to this helper yet
--------------------------------------------------
Three copy-pasted pre-flight checks remain, each structurally entangled with
its caller. They are tracked by ``tests/unit/lib/test_anthropic_client_ratchet.py``
so the deferral is build-visible rather than forgotten:

* ``lib/genai_validate.py:82-97`` -- returns ``(client, model, provider)`` with
  an OpenRouter branch and a ``sys.exit(1)``; 4 callers.
* ``lib/alignment_gate.py:138-154`` -- same triple, raises ``AlignmentError``.
* ``lib/genai_manifest_validator.py:176-188`` -- inlined in ``__init__`` behind
  a ``has_api_key`` flag that other methods branch on.

The two ``scripts/`` sites are pinned rather than migrated because top-level
``scripts/`` is **not deployed** -- ``config/install_manifest.json``'s
``"scripts"`` block ships only ``plugins/autonomous-dev/scripts/*``, so a
deployed consumer could not import this helper from there.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:  # pragma: no cover - typing only
    from anthropic import Anthropic

__all__ = ["API_KEY_ENV_VAR", "AUTH_TOKEN_ENV_VAR", "get_anthropic_client"]

API_KEY_ENV_VAR = "ANTHROPIC_API_KEY"
AUTH_TOKEN_ENV_VAR = "ANTHROPIC_AUTH_TOKEN"


def _debug_enabled() -> bool:
    """Return True when ``DEBUG_GENAI`` requests diagnostics on stderr."""
    return os.environ.get("DEBUG_GENAI", "").lower() == "true"


def _debug(message: str) -> None:
    """Write a diagnostic to stderr when debugging is enabled.

    Never raises: diagnostics must not be able to break a credential lookup.
    """
    if _debug_enabled():
        try:
            print(message, file=sys.stderr)
        except Exception:  # noqa: BLE001 - diagnostics are best-effort
            pass


def get_anthropic_client(*, purpose: str = "") -> Optional["Anthropic"]:
    """Return a credentialed Anthropic client, or ``None`` if none can be built.

    This is the sole sanctioned construction site for ``anthropic.Anthropic``.
    It **never raises** -- a missing SDK, a missing credential, and a malformed
    credential all resolve to ``None``, so callers need exactly one guard
    (``if client is None: ...``) instead of a blanket ``except Exception``.

    Resolution order matches the SDK's own: ``ANTHROPIC_API_KEY`` first, then
    ``ANTHROPIC_AUTH_TOKEN``. If both are set, the API key wins.

    Args:
        purpose: Short human-readable label for the caller, used only in
            ``DEBUG_GENAI`` diagnostics (for example ``"security_scan"``).
            Never sent to the API and never logged outside debug mode.

    Returns:
        A constructed ``anthropic.Anthropic`` whose ``auth_headers`` are
        non-empty, or ``None`` when the SDK is unavailable, no credential is
        configured, or the constructed client carries no usable credential.
        Returning ``None`` is a first-class, tested outcome -- not an error.

    Raises:
        Nothing. All failure modes are reported as ``None``.
    """
    label = f" ({purpose})" if purpose else ""

    try:
        from anthropic import Anthropic
    except ImportError:
        _debug(f"[genai_credentials] anthropic SDK not installed{label}")
        return None

    # ---- Layer 1: env pre-check -------------------------------------------
    # Authoritative. Decides WHETHER TO CONSTRUCT, so a credential-less client
    # is never created (the Issue #1593 property). ``.strip()`` is used only to
    # decide emptiness -- a whitespace-only value is never a real credential.
    # The RAW value is what gets handed to the SDK, so a credential with
    # surrounding whitespace behaves exactly as it does today.
    raw_api_key = os.environ.get(API_KEY_ENV_VAR, "")
    raw_auth_token = os.environ.get(AUTH_TOKEN_ENV_VAR, "")

    if raw_api_key.strip():
        kwargs: dict[str, Any] = {"api_key": raw_api_key}
        source = API_KEY_ENV_VAR
    elif raw_auth_token.strip():
        kwargs = {"auth_token": raw_auth_token}
        source = AUTH_TOKEN_ENV_VAR
    else:
        _debug(
            f"[genai_credentials] no credential in {API_KEY_ENV_VAR} or "
            f"{AUTH_TOKEN_ENV_VAR}; not constructing a client{label}"
        )
        return None

    try:
        client = Anthropic(**kwargs)
    except Exception as exc:  # noqa: BLE001 - INV-8: never raise from here
        _debug(f"[genai_credentials] client construction failed{label}: {type(exc).__name__}")
        return None

    # ---- Layer 2: post-construction probe ---------------------------------
    # Defence in depth, NOT the authoritative predicate. Catches a credential
    # the SDK silently declined to adopt. It does NOT catch the empty string
    # (auth_headers is truthy there) -- layer 1 already rejected that.
    # ``getattr`` keeps this working on SDK versions predating the property.
    auth_headers = getattr(client, "auth_headers", None)
    if auth_headers is not None and not auth_headers:
        _debug(
            f"[genai_credentials] {source} was set but the client resolved no "
            f"auth headers; discarding client{label}"
        )
        return None

    _debug(f"[genai_credentials] client constructed from {source}{label}")
    return client
