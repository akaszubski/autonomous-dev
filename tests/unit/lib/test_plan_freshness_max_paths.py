"""Test MAX_PATHS truncation in extract_referenced_paths (Issue #1223).

This test module verifies that `extract_referenced_paths()` correctly truncates
its result list to `MAX_PATHS` entries when the input contains more paths than
the limit. The limit prevents unbounded memory consumption on pathological
inputs (e.g., adversarial plan content with thousands of paths).

Test coverage:
1. Normal operation: inputs with fewer than MAX_PATHS paths work unchanged
2. Truncation: inputs with more than MAX_PATHS paths are truncated to exactly MAX_PATHS
3. Debug logging: truncation triggers a debug log message with counts
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import patch

# Add lib to path
repo_root = Path(__file__).resolve().parents[3]
lib_path = repo_root / "plugins/autonomous-dev/lib"
sys.path.insert(0, str(lib_path))

from plan_freshness import extract_referenced_paths, MAX_PATHS  # noqa: E402


def test_extract_paths_under_limit_unchanged() -> None:
    """Verify normal operation when path count is under MAX_PATHS."""
    # Generate plan content with 100 paths (well under the 500 limit)
    paths = [f"path/to/file_{i:04d}.py" for i in range(100)]
    plan_content = "\n".join(paths)
    
    result = extract_referenced_paths(plan_content)
    
    # All paths should be returned, sorted
    assert len(result) == 100
    assert result == sorted(paths)
    # First and last path to verify sorting
    assert result[0] == "path/to/file_0000.py"
    assert result[-1] == "path/to/file_0099.py"


def test_extract_paths_exceeds_limit_truncates() -> None:
    """Verify truncation when path count exceeds MAX_PATHS."""
    # Generate plan content with 1000 paths (double the 500 limit)
    paths = [f"path/to/file_{i:04d}.py" for i in range(1000)]
    plan_content = "\n".join(paths)
    
    result = extract_referenced_paths(plan_content)
    
    # Result should be truncated to exactly MAX_PATHS
    assert len(result) == MAX_PATHS
    assert len(result) == 500  # Explicit check of the constant value
    
    # The truncated result should be the first MAX_PATHS entries from sorted list
    expected = sorted(paths)[:MAX_PATHS]
    assert result == expected
    
    # Verify first and last included paths
    assert result[0] == "path/to/file_0000.py"
    assert result[-1] == "path/to/file_0499.py"
    
    # Verify that file_0500.py and beyond are NOT in the result
    assert "path/to/file_0500.py" not in result
    assert "path/to/file_0999.py" not in result


def test_extract_paths_truncation_logs_debug_message() -> None:
    """Verify debug message is logged when truncation occurs."""
    # Generate plan content with 750 paths (exceeds 500 limit)
    paths = [f"path/to/file_{i:04d}.py" for i in range(750)]
    plan_content = "\n".join(paths)
    
    # Capture log output
    with patch.object(logging.getLogger("plan_freshness"), "debug") as mock_debug:
        result = extract_referenced_paths(plan_content)
    
    # Result should be truncated
    assert len(result) == MAX_PATHS
    
    # Debug message should have been logged with correct counts
    mock_debug.assert_called_once()
    call_args = mock_debug.call_args[0][0]
    assert "Truncating extract_referenced_paths result from 750" in call_args
    assert "to 500 entries" in call_args
    assert "250 paths omitted" in call_args


def test_exact_max_paths_boundary() -> None:
    """Verify behavior at the exact MAX_PATHS boundary (500 paths)."""
    # Generate exactly MAX_PATHS paths
    paths = [f"path/to/file_{i:04d}.py" for i in range(MAX_PATHS)]
    plan_content = "\n".join(paths)
    
    # No truncation should occur
    with patch.object(logging.getLogger("plan_freshness"), "debug") as mock_debug:
        result = extract_referenced_paths(plan_content)
    
    # All paths should be returned
    assert len(result) == MAX_PATHS
    assert result == sorted(paths)
    
    # No debug message should be logged (no truncation happened)
    mock_debug.assert_not_called()


def test_dedupe_before_truncation() -> None:
    """Verify deduplication happens before truncation check."""
    # Generate 600 paths, but with duplicates that reduce to 400 unique
    unique_paths = [f"path/to/file_{i:04d}.py" for i in range(400)]
    # Add each path twice, plus some extras
    duplicated = unique_paths * 2 + [f"extra_{i}.py" for i in range(100)]
    plan_content = "\n".join(duplicated)
    
    with patch.object(logging.getLogger("plan_freshness"), "debug") as mock_debug:
        result = extract_referenced_paths(plan_content)
    
    # After deduplication, we have 500 unique paths, no truncation needed
    assert len(result) == 500
    
    # No debug message (dedupe brought us to exactly MAX_PATHS)
    mock_debug.assert_not_called()


def test_pathological_input_with_thousands_of_paths() -> None:
    """Verify handling of pathological input with many thousands of paths."""
    # Generate 10,000 paths (20x the limit)
    paths = [f"src/module_{i:05d}/component_{i%100:02d}.py" for i in range(10000)]
    plan_content = "\n".join(paths)
    
    # Should complete quickly despite large input
    result = extract_referenced_paths(plan_content)
    
    # Result truncated to MAX_PATHS
    assert len(result) == MAX_PATHS
    
    # Verify it's the lexicographically first MAX_PATHS entries
    expected = sorted(paths)[:MAX_PATHS]
    assert result == expected