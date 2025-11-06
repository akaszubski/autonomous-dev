"""Regression test suite for autonomous-dev plugin.

Test tier classification:
- smoke/: < 5s - Critical paths, fast validation
- regression/: < 30s - Bug fixes, feature validation
- extended/: 1-5min - Performance, edge cases
- progression/: Variable - Feature progression tests

Parallel execution:
- pytest -n auto (uses pytest-xdist)
- Each test gets isolated tmp_path
- No shared state between tests

Snapshot testing:
- Uses syrupy for output validation
- Snapshots in __snapshots__/ directory
- Update with: pytest --snapshot-update
"""
