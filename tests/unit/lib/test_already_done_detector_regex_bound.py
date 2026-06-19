"""Regression tests for Issue #1221 — ReDoS bound on ``_PATH_RE``.

``already_done_detector._PATH_RE`` previously used an unbounded ``+`` quantifier
on the character class ``[\\w/.-]`` (i.e. ``[\\w/.-]+\\.(py|md|...)``). With
adversarial input — e.g. a 100 KB run of class-matching characters that does
NOT end in one of the listed extensions — the regex engine can exhibit
superlinear scanning time as it repeatedly tries to extend the match. The fix
bounds the run with ``{1,512}``: each match attempt is now capped at 512
chars, defusing the scanning-time amplification on long padded inputs.

These tests pin the new behaviour and prevent regression:

1. A long (100 KB) run of ``[\\w/.-]`` chars with NO matching extension
   completes extraction quickly (<1 s) AND produces no path-like matches —
   the AC verbatim from Issue #1221. Note: ``_extract_symbols`` may still
   pick up non-path tokens from ``_SYMBOL_RE``/``_IDENT_RE`` on the pad
   (e.g. the identifier ``aaaa...``), so we filter on the path-extension
   suffixes specifically.
2. A 512-char run followed by ``.py`` IS matched — the upper bound is
   inclusive, not exclusive (boundary regression guard).
3. A typical short path still matches — sanity guard so the cap doesn't
   over-block in the common case.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"

if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from already_done_detector import _extract_symbols  # noqa: E402

# Path-extension suffixes that ``_PATH_RE`` matches. Used to filter the
# returned symbol list down to path-like tokens specifically — non-path
# tokens (raw identifiers, backtick-quoted symbols) are allowed through
# by ``_SYMBOL_RE``/``_IDENT_RE`` and are not the subject of these tests.
_PATH_EXTENSIONS = (".py", ".md", ".json", ".yaml", ".yml", ".sh", ".ts", ".js")


def test_overlong_path_does_not_match() -> None:
    """AC (verbatim from Issue #1221): 100 KB ``[\\w/.-]`` run with no matching
    extension extracts in <1 s AND produces no path-like matches.

    The pre-fix regex (``[\\w/.-]+\\.(py|md|...)``) on a long adversarial
    pad would scan superlinearly. After the Issue #1221 fix, the ``{1,512}``
    upper bound caps each match attempt at 512 chars — the engine completes
    the scan in well under 1 s and ``_PATH_RE`` returns no match because no
    listed extension follows the padded run.

    Note: ``_extract_symbols`` also runs ``_SYMBOL_RE`` and ``_IDENT_RE``,
    which may pick up the long ``aaaa...`` identifier from the pad. We
    filter to path-extension tokens only — that is the regex affected by
    the ReDoS fix.
    """
    # 100 KB run of \w-class chars with NO matching extension suffix.
    # This is the precise adversarial input pattern from Issue #1221 AC.
    payload = "a" * (100 * 1024)
    start = time.perf_counter()
    syms = _extract_symbols(title="", body=payload, max_count=10)
    elapsed = time.perf_counter() - start
    # Filter to path-like tokens (the ones produced by _PATH_RE).
    path_matches = [s for s in syms if s.endswith(_PATH_EXTENSIONS)]
    assert path_matches == [], (
        f"100 KB [\\w/.-] pad (no extension) must produce no path-like matches. "
        f"Got path_matches={path_matches!r} (full syms={syms!r})"
    )
    # Timing budget: <1 s as a defensive ceiling. The Issue #1221 AC cited
    # "<100 ms" as an illustrative figure; we use a more generous 1 s ceiling
    # so the test is robust on slower CI hardware while still catching the
    # superlinear-blowup regression class — pre-cap adversarial input could
    # extend match time arbitrarily (seconds → hangs). With the {1,512} cap
    # the worst case is bounded at O(N × 512) per scan position.
    assert elapsed < 1.0, (
        f"Extraction on 100 KB pad must complete in <1 s (ReDoS cap). "
        f"Got {elapsed * 1000:.1f} ms — possible regression of the {{1,512}} bound."
    )


def test_path_at_512_boundary_matches() -> None:
    """AC: a 512-char run of ``[\\w/.-]`` + ``.py`` IS matched (inclusive upper bound).

    ``{1,512}`` is inclusive at the upper end. A run of exactly 512
    character-class chars followed by ``.py`` MUST still match — anything
    less would be over-blocking. The expected token is ``<512 chars>.py``
    (total length 515).
    """
    body = "a" * 512
    payload = body + ".py"
    syms = _extract_symbols(title="", body=payload, max_count=10)
    assert payload in syms, (
        f"512-char [\\w/.-] run + .py must match (boundary is inclusive). "
        f"Got {syms!r}"
    )


def test_legitimate_typical_path_still_matches() -> None:
    """AC: a typical short well-formed path still matches under the new bound.

    Regression guard: the {1,512} cap must not over-block in the common
    case. ``plugins/autonomous-dev/lib/already_done_detector.py`` is a
    realistic repo-relative path; it MUST appear in the returned list.
    """
    payload = (
        "Plan references plugins/autonomous-dev/lib/already_done_detector.py "
        "for the helper."
    )
    syms = _extract_symbols(title="", body=payload, max_count=10)
    assert "plugins/autonomous-dev/lib/already_done_detector.py" in syms, (
        f"Typical short path must still match under the new bound. "
        f"Got {syms!r}"
    )
