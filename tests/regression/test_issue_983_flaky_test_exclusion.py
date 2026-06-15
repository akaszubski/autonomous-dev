"""Regression test for Issue #983: classify_failures flaky test exclusion."""

import sys
from pathlib import Path

LIB_DIR = Path(__file__).resolve().parents[2] / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(LIB_DIR))

from fix_forward import classify_failures


def test_classify_failures_without_flaky_set_preserves_existing_behavior():
    baseline = {"tests/a.py::test_1"}
    current = {"tests/a.py::test_1", "tests/b.py::test_2"}
    result = classify_failures(baseline, current)
    assert result["fixed"] == set()
    assert result["pre_existing_remaining"] == {"tests/a.py::test_1"}
    assert result["new_failures"] == {"tests/b.py::test_2"}


def test_classify_failures_with_flaky_set_excludes_known_flakes_from_new_failures():
    baseline = {"tests/a.py::test_1"}
    current = {"tests/a.py::test_1", "tests/b.py::test_flaky", "tests/c.py::test_real_regression"}
    flaky = {"tests/b.py::test_flaky"}
    result = classify_failures(baseline, current, known_flaky_tests=flaky)
    assert result["new_failures"] == {"tests/c.py::test_real_regression"}
    assert "tests/b.py::test_flaky" not in result["new_failures"]
