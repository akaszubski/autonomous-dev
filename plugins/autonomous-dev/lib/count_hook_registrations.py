"""Count the UNION of hook lifecycle events across all settings files.

Issue #1672 background: ``scripts/deploy-all.sh`` had a hook-registration
count check that inspected only the per-repo project ``settings.json``
and compared its count to ``EXPECTED_HOOK_EVENTS=8``. Registration is
split by design across three files (project ``settings.json``, project
``settings.local.json``, and global ``~/.claude/settings.json``), so
the count could never reach 8 no matter how correct the install. The
check was permanently red in every repo it touched. Every deploy ended
with ``5 VALIDATION ERRORS``, training operators to ignore the deploy
validator entirely — cry-wolf.

This helper computes the correct count: the size of the union of hook
event keys across all three files. Missing files degrade to an empty
set (they are not an error — a repo may not have a local settings
file, or the deploy may be pre-``~/.claude`` bootstrap).

Callable as CLI:
    python3 count_hook_registrations.py <project> <local> <global>

Prints the integer count to stdout and exits 0. Any exception is caught
and prints ``0`` — the validator's fail-open behaviour is preserved.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _load_events(path: str | Path) -> set[str]:
    """Return the set of hook event names declared in one settings file."""

    p = Path(path)
    if not p.exists() or not p.is_file():
        return set()
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return set()
    try:
        data = json.loads(text)
    except (ValueError, json.JSONDecodeError):
        return set()
    hooks = data.get("hooks") if isinstance(data, dict) else None
    if not isinstance(hooks, dict):
        return set()
    return {k for k in hooks.keys() if isinstance(k, str)}


def count_union(
    project_path: str | Path,
    local_path: str | Path,
    global_path: str | Path,
) -> int:
    """Return the union count of distinct hook event names across three files."""

    return len(
        _load_events(project_path)
        | _load_events(local_path)
        | _load_events(global_path)
    )


def _main(argv: list[str]) -> int:
    if len(argv) != 3:
        # Callers expect one integer on stdout; emit 0 and exit 0 so we
        # never break a deploy that mis-invokes us.
        print(0)
        return 0
    try:
        print(count_union(argv[0], argv[1], argv[2]))
    except Exception:
        print(0)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
