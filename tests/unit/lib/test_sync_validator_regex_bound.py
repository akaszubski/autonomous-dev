"""Regression tests for Issue #1222 — ReDoS bound on sync_validator regex.

`sync_validator._extract_hook_paths_from_object_format` previously used an
unbounded ``+`` quantifier on the character class ``[\\w./~-]`` (i.e.
``[\\w./~-]+\\.(py|sh)``). With adversarial input — e.g. a 100 KB run of
class-matching characters that does NOT end in .py or .sh — the regex engine
can exhibit superlinear scanning time. The fix bounds the run with ``{1,512}``:
each match attempt is now capped at 512 chars, defusing the scanning-time
amplification on long padded inputs.

These tests pin the new behaviour and prevent regression:

1. A long (100 KB) run of ``[\\w./~-]`` chars with NO matching extension
   completes extraction quickly (<1 s) AND produces no false matches.
2. A 512-char run followed by ``.py`` IS matched — the upper bound is
   inclusive, not exclusive (boundary regression guard).
3. A typical short path still matches — sanity guard so the cap doesn't
   over-block in the common case.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"

if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from sync_validator import SyncValidator  # noqa: E402


def test_overlong_path_does_not_match() -> None:
    """AC: 100 KB ``[\\w./~-]`` run with no matching extension extracts
    in <1 s AND produces no false matches.
    
    The pre-fix regex would scan superlinearly on adversarial input.
    After Issue #1222 fix, the ``{1,512}`` upper bound caps each match
    attempt at 512 chars.
    """
    # 100 KB run of valid path chars with NO matching extension
    payload = "a" * (100 * 1024)
    
    # Create a mock hook structure with the adversarial payload
    hooks = {
        "PreToolUse": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": f"python3 {payload}"  # No .py/.sh extension
                    }
                ]
            }
        ]
    }
    
    validator = SyncValidator(REPO_ROOT)
    start = time.perf_counter()
    paths = validator._extract_hook_paths_from_object_format(hooks)
    elapsed = time.perf_counter() - start
    
    # No false matches: the pad never produces a spurious match
    assert paths == [], (
        f"100 KB [\\w./~-] pad (no extension) must produce no matches. "
        f"Got {paths!r}"
    )
    
    # Timing budget: <1 s to catch superlinear-blowup regression
    assert elapsed < 1.0, (
        f"Extraction on 100 KB pad must complete in <1 s (ReDoS cap). "
        f"Got {elapsed * 1000:.1f} ms — possible regression of the {{1,512}} bound."
    )


def test_path_at_512_boundary_matches() -> None:
    """A 512-char run of ``[\\w./~-]`` + ``.py`` IS matched (inclusive upper bound).
    
    ``{1,512}`` is inclusive at the upper end. A run of exactly 512
    character-class chars followed by ``.py`` MUST still match.
    """
    body = "a" * 512
    path = body + ".py"
    
    hooks = {
        "PreToolUse": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": f"python3 {path}"
                    }
                ]
            }
        ]
    }
    
    validator = SyncValidator(REPO_ROOT)
    paths = validator._extract_hook_paths_from_object_format(hooks)
    
    assert path in paths, (
        f"512-char [\\w./~-] run + .py must match (boundary is inclusive). "
        f"Got {paths!r}"
    )


def test_legitimate_typical_path_still_matches() -> None:
    """A typical short well-formed path still matches under the new bound.
    
    Regression guard: the {1,512} cap must not over-block in the common case.
    ``hooks/pre_commit.py`` is a realistic path; it MUST appear in the list.
    """
    hook_path = "hooks/pre_commit.py"
    
    hooks = {
        "PreToolUse": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": f"python3 ~/.claude/{hook_path}"
                    }
                ]
            }
        ]
    }
    
    validator = SyncValidator(REPO_ROOT)
    paths = validator._extract_hook_paths_from_object_format(hooks)
    
    # The regex extracts the full path including ~/.claude/
    expected_path = f"~/.claude/{hook_path}"
    assert expected_path in paths, (
        f"Typical short path must still match under the new bound. "
        f"Got {paths!r}"
    )