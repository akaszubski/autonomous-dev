"""Canonical native issue extraction never treats incidental counts as issue IDs."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"))
from pipeline_completion_state import extract_native_issue_number


def test_explicit_hash_reference_wins_over_incidental_count():
    assert extract_native_issue_number("fix 2 tests #1807") == 1807


def test_single_bare_issue_and_issue_phrase():
    assert extract_native_issue_number("1807") == 1807
    assert extract_native_issue_number("issue 1807") == 1807


def test_ordinary_numeric_prose_is_not_issue():
    assert extract_native_issue_number("fix 2 tests") is None
    assert extract_native_issue_number("update Python 3.14 docs") is None
