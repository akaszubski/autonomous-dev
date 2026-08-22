"""Canonical resolution of the gh-issue command-context marker path (Issue #1609).

The command-context marker is a **global sanctioning marker**: its presence tells
``unified_pre_tool.py`` (``_is_issue_command_active`` and the sibling detectors
``_detect_gh_issue_create``, ``_detect_gh_issue_marker_creation``,
``_detect_daily_aggregate_direct_filing``) that an issue-creating command is
legitimately in flight, so an otherwise-blocked ``gh issue create`` is permitted.

Because that is a *global* file path, any process that writes it sanctions every
other process that reads it. Issue #1609 measured the consequence inside the test
suite: ``tests/unit/lib`` leaked the real ``/tmp`` path and 49 tests in
``tests/unit/hooks/test_gh_issue_create_block.py`` silently flipped from
"guard refuses" to "guard permits".

This module is the single sanctioned way for library code to name that path.
Every producer and consumer resolves through :func:`gh_issue_context_path`, which
honours the ``GH_ISSUE_CMD_CONTEXT_PATH`` environment variable (introduced in
Issue #1203, mirroring the ``PIPELINE_STATE_FILE`` precedent). Redirecting that
one variable moves the whole mechanism, which is what lets the test suite run
without ever touching the real path.

``hooks/unified_pre_tool.py`` deliberately keeps its own copy of the env-var name
and default (hooks must be importable as standalone scripts with no ``lib`` on
``sys.path``). The two copies are cross-validated by
``tests/regression/test_issue_1609_gh_issue_context_isolation.py``.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = [
    "CONTEXT_PATH_ENV_VAR",
    "DEFAULT_CONTEXT_PATH",
    "gh_issue_context_path",
]

#: Environment variable that overrides the command-context marker location.
CONTEXT_PATH_ENV_VAR = "GH_ISSUE_CMD_CONTEXT_PATH"

#: The real, global marker location used when no override is set.
DEFAULT_CONTEXT_PATH = "/tmp/autonomous_dev_cmd_context.json"


def gh_issue_context_path() -> Path:
    """Resolve the gh-issue command-context marker path.

    Resolution happens on every call (not at import time) so that a redirect
    installed after import — a test fixture, a subprocess env, an operator
    override — takes effect immediately.

    Returns:
        Path to the marker file: ``$GH_ISSUE_CMD_CONTEXT_PATH`` when that
        variable is set to a non-empty value, otherwise
        :data:`DEFAULT_CONTEXT_PATH`.
    """
    return Path(os.environ.get(CONTEXT_PATH_ENV_VAR) or DEFAULT_CONTEXT_PATH)
