"""Baseline-missing guardrail for the coordinator (Issue #1139).

If the sentinel does not have a baseline_cmd recorded but pipeline_state is
active (sentinel file exists), emit a WARNING. This guards against the model
resorting to git-stash workarounds when baseline capture is silently absent.
"""

import json
import sys
from pathlib import Path
from typing import Optional

# Add lib dir to path for get_baseline_scope import when used as a script.
_LIB_DIR = Path(__file__).parent
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from pipeline_state import get_baseline_scope  # noqa: E402


_WARNING_MSG = (
    "[BASELINE-MISSING-WARNING] {state_path} exists but no baseline_cmd recorded. "
    "The coordinator MUST NOT use git stash as a baseline-comparison workaround "
    "— re-run STEP 1 baseline capture."
)


def warn_if_baseline_missing(state_path: str) -> bool:
    """Return True iff we emitted a warning (baseline missing).

    Checks the sentinel for a ``baseline_cmd`` field. If absent and the
    sentinel exists (pipeline active), writes a structured WARNING line to
    stderr and returns ``True``.

    Returns ``False`` if the sentinel does not exist (pipeline not active) or
    if ``baseline_cmd`` is already recorded (no action needed).

    NEVER raises — the guardrail is advisory only.

    Args:
        state_path: Absolute path to the pipeline sentinel JSON file.

    Returns:
        ``True`` if a warning was emitted; ``False`` otherwise.
    """
    try:
        sentinel = Path(state_path)
        if not sentinel.exists():
            return False

        scope = get_baseline_scope(state_path)
        if scope is not None:
            # baseline_cmd is present and well-formed — all good.
            return False

        # Sentinel exists but baseline is missing: emit warning.
        print(_WARNING_MSG.format(state_path=state_path), file=sys.stderr)
        return True
    except (OSError, json.JSONDecodeError, ValueError, ImportError):
        # NEVER raises — swallow expected I/O and parse errors silently.
        return False
