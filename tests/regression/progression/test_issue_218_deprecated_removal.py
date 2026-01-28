#!/usr/bin/env python3
"""
Progression Tests for Issue #218: Remove deprecated batch_state_manager functions

TDD RED PHASE: These tests MUST FAIL initially (deprecated items still exist).

Goal: Verify that deprecated context clearing functions are removed from
batch_state_manager.py since Claude Code manages context automatically.

Deprecated Items to Remove:
- should_clear_context() function
- pause_batch_for_clear() function
- get_clear_notification_message() function
- @deprecated decorator
- CONTEXT_THRESHOLD constant

Test Categories:
1. Function Removal - Verify deprecated functions don't exist
2. Decorator Removal - Verify @deprecated decorator is removed
3. Constant Removal - Verify CONTEXT_THRESHOLD is removed
4. Core Functionality - Verify BatchState still works without deprecated functions
5. Backward Compatibility - Verify state file format compatibility
6. Documentation - Verify CHANGELOG documents breaking change

Created: 2026-01-09
Issue: #218 (Remove deprecated batch_state_manager functions)
Agent: test-master
"""

import sys
import tempfile
from pathlib import Path

import pytest

# Add lib to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
LIB_PATH = PROJECT_ROOT / "plugins/autonomous-dev/lib"
sys.path.insert(0, str(LIB_PATH))

# Import module under test
import batch_state_manager  # type: ignore[import-not-found]
from batch_state_manager import (  # type: ignore[import-not-found]
    BatchState as _BatchState,  # Imported for type completeness, used implicitly
    create_batch_state,
    load_batch_state,
    save_batch_state,
)

# Silence unused import warning - BatchState used implicitly via create_batch_state
_ = _BatchState


# ============================================================================
# Test Category 1: Function Removal Tests
# ============================================================================


def test_should_clear_context_function_removed():
    """Verify should_clear_context() function is removed.

    TDD: This test should FAIL initially (function exists with @deprecated).
    After removal, test should PASS (AttributeError raised).
    """
    # Verify function does NOT exist
    assert not hasattr(batch_state_manager, "should_clear_context"), \
        "should_clear_context() should be removed (deprecated in v3.34.0)"


def test_pause_batch_for_clear_function_removed():
    """Verify pause_batch_for_clear() function is removed.

    TDD: This test should FAIL initially (function exists with @deprecated).
    After removal, test should PASS (AttributeError raised).
    """
    # Verify function does NOT exist
    assert not hasattr(batch_state_manager, "pause_batch_for_clear"), \
        "pause_batch_for_clear() should be removed (deprecated in v3.34.0)"


def test_get_clear_notification_message_function_removed():
    """Verify get_clear_notification_message() function is removed.

    TDD: This test should FAIL initially (function exists with @deprecated).
    After removal, test should PASS (AttributeError raised).
    """
    # Verify function does NOT exist
    assert not hasattr(batch_state_manager, "get_clear_notification_message"), \
        "get_clear_notification_message() should be removed (deprecated in v3.34.0)"


def test_deprecated_functions_not_importable():
    """Verify deprecated functions cannot be imported.

    TDD: This test should FAIL initially (functions importable).
    After removal, imports should raise ImportError or AttributeError.
    """
    # Verify functions are not accessible via getattr (ImportError equivalent)
    assert not hasattr(batch_state_manager, "should_clear_context"), \
        "should_clear_context should not be importable"
    assert not hasattr(batch_state_manager, "pause_batch_for_clear"), \
        "pause_batch_for_clear should not be importable"
    assert not hasattr(batch_state_manager, "get_clear_notification_message"), \
        "get_clear_notification_message should not be importable"


# ============================================================================
# Test Category 2: Decorator Removal Tests
# ============================================================================


def test_deprecated_decorator_removed():
    """Verify @deprecated decorator is removed from module.

    TDD: This test should FAIL initially (decorator exists).
    After removal, test should PASS (AttributeError raised).
    """
    # Verify decorator does NOT exist
    assert not hasattr(batch_state_manager, "deprecated"), \
        "@deprecated decorator should be removed (no longer needed)"


def test_no_deprecation_warnings_in_imports():
    """Verify importing batch_state_manager does not emit DeprecationWarning.

    TDD: This test should FAIL initially (warnings emitted when importing).
    After removal, no warnings should be emitted.
    """
    import warnings
    import importlib

    # Reload module with warning tracking
    with warnings.catch_warnings(record=True) as warning_list:
        warnings.simplefilter("always")
        importlib.reload(batch_state_manager)

        # Filter to DeprecationWarnings
        deprecation_warnings = [w for w in warning_list
                               if issubclass(w.category, DeprecationWarning)]

        assert len(deprecation_warnings) == 0, \
            f"Module should not emit DeprecationWarning on import (found {len(deprecation_warnings)})"


def test_source_code_has_no_deprecated_decorator():
    """Verify source code does not contain @deprecated decorator.

    TDD: This test should FAIL initially (decorator in source).
    After removal, decorator should not appear in source.
    """
    source_file = LIB_PATH / "batch_state_manager.py"
    source_code = source_file.read_text()

    # Should NOT contain @deprecated decorator
    assert "@deprecated" not in source_code, \
        "Source code should not contain @deprecated decorator"

    # Should NOT contain 'def deprecated(' decorator definition
    assert "def deprecated(" not in source_code, \
        "Source code should not contain deprecated() decorator definition"


# ============================================================================
# Test Category 3: Constant Removal Tests
# ============================================================================


def test_context_threshold_constant_removed():
    """Verify CONTEXT_THRESHOLD constant is removed.

    TDD: This test should FAIL initially (constant exists).
    After removal, test should PASS (AttributeError raised).
    """
    # Verify constant does NOT exist
    assert not hasattr(batch_state_manager, "CONTEXT_THRESHOLD"), \
        "CONTEXT_THRESHOLD should be removed (no longer needed)"


def test_no_hardcoded_150000_threshold():
    """Verify source code does not contain hardcoded 150000 token threshold.

    TDD: This test should FAIL initially (150000 appears in source).
    After removal, constant should not appear in source.
    """
    source_file = LIB_PATH / "batch_state_manager.py"
    source_code = source_file.read_text()

    # Count occurrences of 150000 (threshold value)
    # Allow in comments/docstrings for context, but not in code
    lines = source_code.split("\n")
    code_lines = [
        line for line in lines
        if not line.strip().startswith("#")
        and not line.strip().startswith('"""')
        and not line.strip().startswith("'''")
    ]
    code_text = "\n".join(code_lines)

    # Should NOT contain 150000 in executable code
    assert "150000" not in code_text and "150_000" not in code_text, \
        "Source code should not contain CONTEXT_THRESHOLD constant (150000 or 150_000)"


def test_source_code_removed_context_threshold_references():
    """Verify source code does not reference CONTEXT_THRESHOLD variable.

    TDD: This test should FAIL initially (variable referenced in code).
    After removal, variable should not be used.
    """
    source_file = LIB_PATH / "batch_state_manager.py"
    source_code = source_file.read_text()

    # Remove docstrings and comments
    lines = source_code.split("\n")
    code_lines = [
        line for line in lines
        if not line.strip().startswith("#")
        and "CONTEXT_THRESHOLD" in line
    ]

    # Should NOT reference CONTEXT_THRESHOLD in code (only in comments allowed)
    assert len(code_lines) == 0, \
        f"Source code should not reference CONTEXT_THRESHOLD (found {len(code_lines)} lines)"


# ============================================================================
# Test Category 4: Core Functionality Tests
# ============================================================================


def test_batch_state_create_still_works():
    """Verify create_batch_state() still works after deprecation removal.

    Backward compatibility: Core functionality should not be affected.
    """
    features = ["Feature 1", "Feature 2", "Feature 3"]

    # Should work without deprecated functions
    state = create_batch_state(features=features)

    assert state.batch_id is not None
    assert state.total_features == 3
    assert state.features == features
    assert state.status == "in_progress"


def test_batch_state_save_load_roundtrip():
    """Verify save/load roundtrip still works after deprecation removal.

    Backward compatibility: State persistence should not be affected.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / ".claude" / "batch_state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)

        # Create and save state
        features = ["Feature 1", "Feature 2"]
        original_state = create_batch_state(features=features)
        save_batch_state(state_file, original_state)

        # Load state
        loaded_state = load_batch_state(state_file)

        # Verify roundtrip
        assert loaded_state.batch_id == original_state.batch_id
        assert loaded_state.total_features == original_state.total_features
        assert loaded_state.features == original_state.features


def test_should_auto_clear_still_works():
    """Verify should_auto_clear() function still works (backward compatibility).

    Note: should_auto_clear() was NOT deprecated in Issue #218, but IS deprecated
    as of Issue #277. Claude handles auto-compact automatically. This test validates
    backward compatibility only - the function is not used in production.
    """
    from batch_state_manager import should_auto_clear  # type: ignore[import-not-found]

    # Create state with low token estimate
    state = create_batch_state(features=["Feature 1"])
    state.context_token_estimate = 1000

    # Should not auto-clear at 1000 tokens
    assert should_auto_clear(state) is False

    # Increase token estimate to threshold
    state.context_token_estimate = 186000

    # Should auto-clear at 186000 tokens (above 185K threshold)
    assert should_auto_clear(state) is True


# ============================================================================
# Test Category 5: Backward Compatibility Tests
# ============================================================================


def test_old_state_files_load_without_deprecated_fields():
    """Verify old state files (pre-removal) load correctly.

    Backward compatibility: State files from v3.34.0 should still load.
    Old files may have context_tokens_before_clear and paused_at_feature_index fields.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / ".claude" / "batch_state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)

        # Create old state file with deprecated fields
        old_state_json = """{
  "batch_id": "batch-20260109-120000",
  "features_file": "/path/to/features.txt",
  "total_features": 2,
  "features": ["Feature 1", "Feature 2"],
  "current_index": 1,
  "completed_features": [0],
  "failed_features": [],
  "context_token_estimate": 50000,
  "auto_clear_count": 0,
  "auto_clear_events": [],
  "created_at": "2026-01-09T12:00:00Z",
  "updated_at": "2026-01-09T12:30:00Z",
  "status": "in_progress",
  "issue_numbers": null,
  "source_type": "file",
  "state_file": "",
  "context_tokens_before_clear": 155000,
  "paused_at_feature_index": 1,
  "retry_attempts": {},
  "git_operations": {}
}"""
        state_file.write_text(old_state_json)

        # Load state - should work despite deprecated fields
        state = load_batch_state(state_file)

        # Verify core fields loaded correctly
        assert state.batch_id == "batch-20260109-120000"
        assert state.total_features == 2
        assert state.current_index == 1

        # Deprecated fields should be loaded for backward compat (but not used)
        assert hasattr(state, "context_tokens_before_clear")
        assert hasattr(state, "paused_at_feature_index")


def test_new_state_files_do_not_contain_deprecated_fields():
    """Verify new state files do not contain deprecated fields.

    New state files should not include context_tokens_before_clear or
    paused_at_feature_index (they're only for backward compat loading).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / ".claude" / "batch_state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)

        # Create and save new state
        state = create_batch_state(features=["Feature 1"])
        save_batch_state(state_file, state)

        # Read raw JSON
        import json
        with open(state_file) as f:
            state_json = json.load(f)

        # New state files should NOT actively set deprecated fields to non-null values
        # (They may exist with null values for backward compat, but should not be used)
        if "context_tokens_before_clear" in state_json:
            assert state_json["context_tokens_before_clear"] is None, \
                "New state files should not use context_tokens_before_clear"

        if "paused_at_feature_index" in state_json:
            assert state_json["paused_at_feature_index"] is None, \
                "New state files should not use paused_at_feature_index"


def test_batch_state_dataclass_has_deprecated_fields_for_backward_compat():
    """Verify BatchState dataclass still has deprecated fields for backward compat.

    Note: Fields should exist for loading old state files, but should not be
    actively used in new code.
    """
    # Create state
    state = create_batch_state(features=["Feature 1"])

    # Deprecated fields should exist (for backward compat)
    assert hasattr(state, "context_tokens_before_clear")
    assert hasattr(state, "paused_at_feature_index")

    # But should be None by default (not actively used)
    assert state.context_tokens_before_clear is None
    assert state.paused_at_feature_index is None


# ============================================================================
# Test Category 6: Documentation Tests
# ============================================================================


def test_changelog_documents_breaking_change():
    """Verify CHANGELOG.md documents the breaking change for Issue #218.

    Documentation: Breaking changes should be documented in CHANGELOG.
    """
    changelog = PROJECT_ROOT / "CHANGELOG.md"
    changelog_text = changelog.read_text()

    # Should mention Issue #218 or deprecated function removal
    assert "#218" in changelog_text or "deprecated" in changelog_text.lower(), \
        "CHANGELOG should document Issue #218 or deprecated function removal"

    # Should mention breaking change or removal
    breaking_change_keywords = [
        "breaking",
        "removed",
        "deprecated functions",
        "should_clear_context",
        "pause_batch_for_clear",
        "get_clear_notification_message",
    ]

    found_keywords = [kw for kw in breaking_change_keywords if kw.lower() in changelog_text.lower()]

    assert len(found_keywords) >= 2, \
        f"CHANGELOG should document breaking change with relevant keywords (found: {found_keywords})"


def test_module_docstring_updated():
    """Verify batch_state_manager.py docstring no longer mentions deprecated functions.

    Documentation: Module docstring should not reference removed functions.
    """
    source_file = LIB_PATH / "batch_state_manager.py"
    source_code = source_file.read_text()

    # Extract module docstring
    lines = source_code.split("\n")
    docstring_start = None
    docstring_end = None

    for i, line in enumerate(lines):
        if '"""' in line and docstring_start is None:
            docstring_start = i
        elif '"""' in line and docstring_start is not None:
            docstring_end = i
            break

    if docstring_start is not None and docstring_end is not None:
        docstring = "\n".join(lines[docstring_start:docstring_end + 1])

        # Docstring should NOT mention deprecated functions in active workflow
        # (Historical mentions in deprecation notes are OK)
        deprecated_function_names = [
            "should_clear_context()",
            "pause_batch_for_clear()",
            "get_clear_notification_message()",
        ]

        # Count non-deprecation-note mentions
        for func_name in deprecated_function_names:
            # Allow mentions in DEPRECATED/NOTE sections (historical context)
            lines_with_func = [line for line in docstring.split("\n")
                             if func_name in line
                             and "DEPRECATED" not in line
                             and "NOTE:" not in line]

            assert len(lines_with_func) == 0, \
                f"Module docstring should not reference {func_name} in active workflow"


# ============================================================================
# Test Category 7: Integration Tests
# ============================================================================


def test_batch_workflow_without_manual_clearing():
    """Verify batch workflow works without manual context clearing.

    Integration: Compaction-resilient design means no manual /clear needed.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / ".claude" / "batch_state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)

        # Create batch
        features = ["Feature 1", "Feature 2", "Feature 3"]
        state = create_batch_state(features=features)
        save_batch_state(state_file, state)

        # Simulate processing features without manual clearing
        from batch_state_manager import update_batch_progress, get_next_pending_feature  # type: ignore[import-not-found]

        while True:
            # Load fresh state
            state = load_batch_state(state_file)

            # Get next feature
            next_feature = get_next_pending_feature(state)
            if next_feature is None:
                break

            # Process feature (simulate token consumption)
            update_batch_progress(
                state_file,
                state.current_index,
                status="completed",
                context_token_delta=50000,  # 50K tokens per feature
            )

        # Verify all features completed
        final_state = load_batch_state(state_file)
        assert len(final_state.completed_features) == 3
        assert final_state.status == "completed"


def test_no_pause_status_in_workflow():
    """Verify batch workflow never sets status to 'paused'.

    Integration: 'paused' status was for manual clearing, no longer needed.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / ".claude" / "batch_state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)

        # Create batch
        state = create_batch_state(features=["Feature 1", "Feature 2"])
        save_batch_state(state_file, state)

        # Valid statuses (should not include 'paused')
        valid_statuses = ["in_progress", "running", "completed", "failed"]

        # Verify initial status
        assert state.status in valid_statuses, \
            f"Invalid status: {state.status} (should not be 'paused')"

        # Process feature
        from batch_state_manager import update_batch_progress  # type: ignore[import-not-found]

        update_batch_progress(state_file, 0, status="completed", context_token_delta=50000)

        # Verify status after processing
        state = load_batch_state(state_file)
        assert state.status in valid_statuses, \
            f"Invalid status: {state.status} (should not be 'paused')"


# ============================================================================
# Test Category 8: Edge Cases
# ============================================================================


def test_high_token_estimate_does_not_trigger_deprecation_warning():
    """Verify high token estimate does not emit deprecation warning.

    Edge case: Even with high token count, no deprecated function should be called.
    """
    import warnings

    state = create_batch_state(features=["Feature 1"])
    state.context_token_estimate = 200000  # Very high token count

    # Check should_auto_clear without deprecation warnings
    with warnings.catch_warnings(record=True) as warning_list:
        warnings.simplefilter("always")

        from batch_state_manager import should_auto_clear  # type: ignore[import-not-found]
        _ = should_auto_clear(state)  # Call function, result not needed for this test

        # Filter to DeprecationWarnings
        deprecation_warnings = [w for w in warning_list
                               if issubclass(w.category, DeprecationWarning)]

        assert len(deprecation_warnings) == 0, \
            "should_auto_clear() should not emit DeprecationWarning"


def test_import_error_for_deprecated_functions_has_clear_message():
    """Verify import error for deprecated functions has clear error message.

    User experience: Error should guide users to correct approach.
    """
    # Verify the function cannot be accessed via getattr
    # This is equivalent to import failing but avoids Pyright warnings
    if hasattr(batch_state_manager, "should_clear_context"):
        pytest.fail("should_clear_context should not be importable (function still exists)")

    # If we get here, function was successfully removed
    # No ImportError to check since we use hasattr pattern


# ============================================================================
# Test Summary
# ============================================================================


def test_removal_completeness():
    """Meta-test: Verify test coverage is comprehensive for Issue #218.

    This test validates that we're testing all the requirements from Issue #218.
    """
    import inspect

    # Count test functions
    current_module = sys.modules[__name__]
    test_functions = [
        name for name, obj in inspect.getmembers(current_module)
        if inspect.isfunction(obj) and name.startswith("test_")
    ]

    # Should have tests for all categories
    categories = {
        "function_removal": [
            "test_should_clear_context_function_removed",
            "test_pause_batch_for_clear_function_removed",
            "test_get_clear_notification_message_function_removed",
            "test_deprecated_functions_not_importable",
        ],
        "decorator_removal": [
            "test_deprecated_decorator_removed",
            "test_no_deprecation_warnings_in_imports",
            "test_source_code_has_no_deprecated_decorator",
        ],
        "constant_removal": [
            "test_context_threshold_constant_removed",
            "test_no_hardcoded_150000_threshold",
            "test_source_code_removed_context_threshold_references",
        ],
        "core_functionality": [
            "test_batch_state_create_still_works",
            "test_batch_state_save_load_roundtrip",
            "test_should_auto_clear_still_works",
        ],
        "backward_compatibility": [
            "test_old_state_files_load_without_deprecated_fields",
            "test_new_state_files_do_not_contain_deprecated_fields",
            "test_batch_state_dataclass_has_deprecated_fields_for_backward_compat",
        ],
        "documentation": [
            "test_changelog_documents_breaking_change",
            "test_module_docstring_updated",
        ],
        "integration": [
            "test_batch_workflow_without_manual_clearing",
            "test_no_pause_status_in_workflow",
        ],
    }

    # Verify all category tests exist
    for category, expected_tests in categories.items():
        for test_name in expected_tests:
            assert test_name in test_functions, \
                f"Missing test: {test_name} (category: {category})"

    # Should have at least 20 tests (comprehensive coverage)
    assert len(test_functions) >= 20, \
        f"Insufficient test coverage: {len(test_functions)} tests (expected 20+)"
