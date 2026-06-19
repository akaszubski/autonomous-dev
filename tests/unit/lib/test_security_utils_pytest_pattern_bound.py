"""Regression tests for Issue #1220 — ReDoS bound on ``PYTEST_PATH_PATTERN``.

``security_utils.PYTEST_PATH_PATTERN`` previously used an unbounded ``+``
quantifier on the character class ``[\\w/.-]`` (i.e.
``^[\\w/.-]+\\.py(?:::[\\w\\[\\],_-]+)?$``). With adversarial input — e.g. a
100 KB run of class-matching characters that does NOT end in ``.py`` — the
regex engine can exhibit superlinear scanning time as it repeatedly tries to
extend the match. The fix bounds the runs with ``{1,4096}`` (path segment,
mirroring ``MAX_PATH_LENGTH``) and ``{1,512}`` (optional test-ID segment,
mirroring the Issue #1194 precedent), capping match attempts and defusing
the scanning-time amplification.

These tests pin the new behaviour and prevent regression:

1. A 100 KB run of ``a`` chars with NO ``.py`` suffix is rejected with
   ``ValueError`` in <1 s wall-clock — the AC verbatim from Issue #1220.
2. A path that exercises the regex bound INCLUSIVELY without tripping
   the upstream ``MAX_PATH_LENGTH = 4096`` check still validates — the
   boundary is inclusive on both the regex cap and the path-length cap.
3. A typical short pytest path still validates — sanity guard so the
   cap doesn't over-block in the common case.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"

if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from security_utils import validate_pytest_path  # noqa: E402


def test_adversarial_pad_completes_fast() -> None:
    """AC (verbatim from Issue #1220): 100 KB ``[\\w/.-]`` run with no ``.py``
    suffix raises ``ValueError`` in <1 s wall-clock.

    The pre-fix regex (``^[\\w/.-]+\\.py(?:::[\\w\\[\\],_-]+)?$``) on a long
    adversarial pad would scan superlinearly while the engine repeatedly
    tries to extend the run and fails to find a ``.py`` suffix. After the
    Issue #1220 fix, the ``{1,4096}`` upper bound caps each match attempt
    at 4096 chars — the engine fails fast and ``validate_pytest_path``
    raises ``ValueError`` (invalid format) in well under 1 s.
    """
    # 100 KB run of \w-class chars with NO ``.py`` suffix.
    # This is the precise adversarial input pattern from Issue #1220 AC.
    payload = "a" * (100 * 1024)
    start = time.perf_counter()
    with pytest.raises(ValueError):
        validate_pytest_path(payload, purpose="redos_regression_test")
    elapsed = time.perf_counter() - start
    # Timing budget: <1 s as a defensive ceiling. The Issue #1220 AC cited
    # "<1 s" — we hold the line at 1 s so the test is robust on slower CI
    # hardware while still catching the superlinear-blowup regression class
    # (pre-cap adversarial input could extend match time arbitrarily —
    # seconds to hangs). With the {1,4096} cap the worst case is bounded
    # at O(N * 4096) per scan position.
    assert elapsed < 1.0, (
        f"validate_pytest_path on 100 KB pad must complete in <1 s (ReDoS cap). "
        f"Got {elapsed * 1000:.1f} ms — possible regression of the {{1,4096}} bound."
    )


def test_path_segment_at_max_validates() -> None:
    """AC: a path that exercises the regex bound INCLUSIVELY validates.

    The ``{1,4096}`` cap is inclusive at the upper end. We must also clear
    the upstream ``MAX_PATH_LENGTH = 4096`` check in ``validate_path`` —
    that check is ``len(path_str) > MAX_PATH_LENGTH`` (strict ``>``), so
    a path of exactly 4096 chars passes.

    Construction: ``"a" * 4093 + ".py"`` = 4096 chars total. The
    ``[\\w/.-]{1,4096}`` run matches exactly 4093 chars (within bound),
    then ``.py`` closes the regex. ``validate_path`` sees ``len = 4096``,
    which is NOT ``> 4096``, so it proceeds. The path resolves under
    PROJECT_ROOT (relative path → CWD prefix), passing the whitelist.

    Total: 4096 chars. Body run: 4093 chars.
    """
    body = "a" * 4093
    payload = body + ".py"
    assert len(payload) == 4096, (
        f"Test payload sized to hit MAX_PATH_LENGTH inclusive boundary; "
        f"got len={len(payload)} (expected 4096)."
    )
    result = validate_pytest_path(payload, purpose="boundary_regression_test")
    assert result == payload, (
        f"validate_pytest_path must return the input unchanged at the "
        f"inclusive boundary. Got {result!r}"
    )


def test_typical_pytest_path_validates() -> None:
    """AC: a typical short well-formed pytest path still validates.

    Regression guard: the {1,4096} / {1,512} caps must not over-block in
    the common case. ``tests/unit/lib/test_security_utils.py::test_foo``
    is a realistic pytest invocation; ``validate_pytest_path`` MUST
    return it unchanged.
    """
    payload = "tests/unit/lib/test_security_utils.py::test_foo"
    result = validate_pytest_path(payload, purpose="typical_path_sanity")
    assert result == payload, (
        f"Typical pytest path must validate unchanged under the new bound. "
        f"Got {result!r}"
    )
