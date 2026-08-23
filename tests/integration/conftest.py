"""Integration-tier safety guard: no git mutation may reach the real repository.

Issue #1638. This tier isolates git operations with a process-global ``os.chdir()``
and then calls ``subprocess.run(['git', 'commit', ...])`` with no explicit working
directory. When the chdir does not hold, git commits the real autonomous-dev
checkout -- which happened four times, each sweeping ~485 files and ~205,000
insertions, each titled from a test fixture.

The guard is installed session-wide and autouse so that it is active during
collection-adjacent fixture setup, during module-, class- and function-scoped
fixtures, and during teardown -- not merely inside test bodies. Under
``pytest-xdist`` each worker is a separate process and installs its own copy, so
coverage does not depend on how work is distributed.

Classification lives in :mod:`tests.helpers.git_safety_guard` so it can be
unit-tested without a running pytest session.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

_HELPERS = Path(__file__).resolve().parents[1] / "helpers"
if str(_HELPERS.parent.parent) not in sys.path:
    sys.path.insert(0, str(_HELPERS.parent.parent))

from tests.helpers.git_safety_guard import (  # noqa: E402
    REAL_REPO_ROOT,
    UnsafeGitInvocation,
    enforce_git_safety,
)

__all__ = ["REAL_REPO_ROOT", "UnsafeGitInvocation"]


@pytest.fixture(scope="session", autouse=True)
def _refuse_git_writes_to_real_repo() -> Any:
    """Intercept ``subprocess.run``/``Popen`` and refuse unsafe git invocations.

    Yields:
        None. The patch is active for the whole session and undone on teardown.
    """
    monkeypatch = pytest.MonkeyPatch()

    real_run = subprocess.run
    real_popen = subprocess.Popen

    def guarded_run(args: Any = None, *positional: Any, **kwargs: Any) -> Any:
        enforce_git_safety(args, kwargs, caller="subprocess.run")
        return real_run(args, *positional, **kwargs)

    def guarded_popen(args: Any = None, *positional: Any, **kwargs: Any) -> Any:
        enforce_git_safety(args, kwargs, caller="subprocess.Popen")
        return real_popen(args, *positional, **kwargs)

    # ``check_output``/``check_call``/``call`` resolve ``run``/``Popen`` through the
    # module globals, so patching these two intercepts every stdlib entry point.
    monkeypatch.setattr(subprocess, "run", guarded_run)
    monkeypatch.setattr(subprocess, "Popen", guarded_popen)

    try:
        yield
    finally:
        monkeypatch.undo()
