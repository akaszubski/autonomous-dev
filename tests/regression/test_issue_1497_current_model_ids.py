"""Regression tests for Issue #1497 — decommissioned model IDs block subagent
dispatches.

Anthropic periodically deprecates model IDs. If the plugin hardcodes a
deprecated ID anywhere in ``plugins/autonomous-dev/lib/`` or
``plugins/autonomous-dev/hooks/`` or ``plugins/autonomous-dev/config/``, every
call site that resolves that ID will 404 at runtime — and the failure is
frequently silent (a per-agent 404 that the coordinator does not surface),
producing the "silent degrade" pattern seen in Issue #1497.

This module asserts the invariant:

- No file under ``plugins/autonomous-dev/`` (excluding ``archived/`` and
  ``docs/``) references a model ID that appears on the known-decommissioned
  allow-block list.

The allow-block list is intentionally conservative — it captures only IDs that
Anthropic has publicly deprecated as of the fix date (2026-08-16). New
deprecations can be added by appending to ``KNOWN_DECOMMISSIONED_MODEL_IDS``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "autonomous-dev"

# IDs known to return 404 from the Anthropic API as of 2026-08-16.
# See Issue #1497 for the surfacing evidence. Extend this list when Anthropic
# deprecates additional IDs; the corresponding call sites must be updated
# to a current supported ID in the same commit.
KNOWN_DECOMMISSIONED_MODEL_IDS = frozenset(
    {
        "claude-opus-4-1-20250805",
        "claude-sonnet-4-20250514",
    }
)

# Directories under PLUGIN_ROOT that are frozen (historical) or non-executable
# and therefore excluded from the scan.
EXCLUDED_DIR_PARTS = frozenset({"archived", "docs", "__pycache__"})

# Files we scan for hardcoded model IDs. Markdown agent frontmatter uses tier
# aliases (opus / sonnet / haiku), so we do not scan .md agents — the runtime
# resolves those.
SCAN_SUFFIXES = frozenset({".py", ".json"})


def _iter_scan_targets():
    for path in PLUGIN_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in SCAN_SUFFIXES:
            continue
        parts = set(path.relative_to(PLUGIN_ROOT).parts)
        if parts & EXCLUDED_DIR_PARTS:
            continue
        yield path


@pytest.mark.parametrize("decommissioned_id", sorted(KNOWN_DECOMMISSIONED_MODEL_IDS))
def test_no_decommissioned_model_id_in_plugin(decommissioned_id: str) -> None:
    """No active plugin file references a known-decommissioned model ID.

    A hit here means at least one call site will 404 at runtime. Update the
    call site to a current supported Anthropic model ID (e.g.
    ``claude-sonnet-4-5-20250929`` or ``claude-haiku-4-5-20251001``).
    """
    hits: list[str] = []
    pattern = re.compile(re.escape(decommissioned_id))
    for path in _iter_scan_targets():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                hits.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")

    assert not hits, (
        f"Decommissioned model ID {decommissioned_id!r} still referenced by "
        f"{len(hits)} line(s) — every call site will 404 at runtime. "
        f"Update to a current supported model ID (see Issue #1497).\n"
        + "\n".join(hits)
    )


def test_current_supported_model_ids_still_present() -> None:
    """Positive control — at least one current supported model ID is present.

    Guards against the regression where a well-meaning refactor deletes every
    concrete model reference and the plugin silently falls back to a runtime
    default that may drift.
    """
    current_ids = ("claude-sonnet-4-5-20250929", "claude-haiku-4-5-20251001")
    found_any = False
    for path in _iter_scan_targets():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if any(current_id in text for current_id in current_ids):
            found_any = True
            break
    assert found_any, (
        "No current supported model ID found anywhere in the plugin. "
        f"Expected at least one of {current_ids} to be referenced."
    )
