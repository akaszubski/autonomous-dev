"""Known-flaky test allowlist for fix-forward classifier (Issue #983)."""

import json
from pathlib import Path


def load_known_flaky_tests(project_root: Path) -> set[str]:
    """Load known-flaky test IDs from <project_root>/.claude/local/known_flaky_tests.json.

    File is a flat JSON array of test ID strings. Fail-open: returns empty
    set on missing file, malformed JSON, or non-list root.

    Args:
        project_root: Repository root path. Pass explicitly to handle
                      worktree CWD case.
    """
    path = project_root / ".claude" / "local" / "known_flaky_tests.json"
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, list):
            return set()
        return {str(item) for item in data if isinstance(item, str)}
    except (OSError, json.JSONDecodeError, ValueError):
        return set()


def mark_test_flaky(test_id: str, reason: str, project_root: Path) -> None:
    """Append test_id to known-flaky list with a reason. Atomic write.

    Idempotent — does nothing if test_id is already in the list.
    Fail-open: silently no-ops on write errors.

    Args:
        test_id: Fully-qualified test ID (e.g. "tests/unit/test_foo.py::test_bar").
        reason: Free-text reason for marking flaky.
        project_root: Repository root path.
    """
    path = project_root / ".claude" / "local" / "known_flaky_tests.json"
    try:
        existing = load_known_flaky_tests(project_root)
        if test_id in existing:
            return
        existing.add(test_id)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Atomic write via temp file in same dir
        import os
        import tempfile
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp", prefix=f".{path.name}_")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(sorted(existing), f, indent=2)
            os.chmod(tmp, 0o600)
            os.replace(tmp, str(path))
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception:
        pass  # Fail-open
