"""Spec-blind behavioral tests for Issue #991 Validator Diversity Score.

Constructed from acceptance criteria ONLY. No knowledge of implementation choices.

Acceptance criteria covered:
  AC1: Math correctness (jaccard=0.25, diversity=0.75 for |A∩B|=2, |A∪B|=8)
  AC2: Empty-input safety -> classification="blind-spot", alert="[VALIDATOR-BLIND-SPOT]", diversity=0.0
  AC3: Tiny-sample suppression -> count_a + count_b < 6 yields classification="tiny-sample", alert=None
  AC4: Rubber-stamp alert -> count_a + count_b >= 6 AND jaccard > 0.8 yields classification="rubber-stamp", alert="[VALIDATOR-OVERLAP]"
  AC5: CIA report subsection produced when files exist, omitted when missing
  AC6: Stdlib only + malformed inputs MUST NOT raise
"""

from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_PATH = REPO_ROOT / "plugins" / "autonomous-dev" / "lib" / "validator_diversity.py"
CIA_AGENT_PATH = REPO_ROOT / "plugins" / "autonomous-dev" / "agents" / "continuous-improvement-analyst.md"


# ---------------------------------------------------------------------------
# Module loader — load the implementation by file path so the test is robust
# to PYTHONPATH/install state.
# ---------------------------------------------------------------------------

def _load_module():
    spec = importlib.util.spec_from_file_location("validator_diversity_under_test", LIB_PATH)
    assert spec is not None and spec.loader is not None, f"could not load {LIB_PATH}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def vd():
    return _load_module()


# ---------------------------------------------------------------------------
# AC1: Math correctness — jaccard=0.25, diversity=0.75 when |A∩B|=2, |A∪B|=8
# ---------------------------------------------------------------------------

def test_spec_991_ac1_jaccard_math_known_values(vd):
    """Given |A∩B|=2 and |A∪B|=8, jaccard == 0.25 (within 1e-9)."""
    # Build two sets with exactly intersection=2, union=8.
    # A has 5 items, B has 5 items, sharing 2.
    a = {"a", "b", "c", "d", "e"}
    b = {"d", "e", "f", "g", "h"}
    assert len(a & b) == 2
    assert len(a | b) == 8
    j = vd.jaccard(a, b)
    assert abs(j - 0.25) < 1e-9, f"expected 0.25, got {j!r}"


def test_spec_991_ac1_diversity_complement_of_jaccard(vd):
    """diversity == 1 - jaccard == 0.75 for the AC1 case via score()."""
    # Reviewer findings: 5 unique tuples; Security findings: overlap 2 with reviewer + 3 new.
    # We craft text that the parsers will reduce to specific tuples.
    reviewer_text = """
### FINDING-1
- **Severity**: high
- **Category**: security
- **File**: `src/a.py:10`

### FINDING-2
- **Severity**: high
- **Category**: security
- **File**: `src/b.py:20`

### FINDING-3
- **Severity**: medium
- **Category**: performance
- **File**: `src/c.py:30`

### FINDING-4
- **Severity**: medium
- **Category**: performance
- **File**: `src/d.py:40`

### FINDING-5
- **Severity**: low
- **Category**: style
- **File**: `src/e.py:50`
"""

    security_text = """
## A01: Broken Access Control
- **Severity**: high
- **Location**: src/a.py:10

## A02: Cryptographic Failures
- **Severity**: high
- **Location**: src/b.py:20

## A03: Injection
- **Severity**: high
- **Location**: src/x.py:60

## A04: Insecure Design
- **Severity**: high
- **Location**: src/y.py:70

## A05: Security Misconfiguration
- **Severity**: high
- **Location**: src/z.py:80
"""

    result = vd.score(reviewer_text, security_text)
    # Both first reviewer findings normalize to ("blocking", "security", "src/a.py", 10)
    # and ("blocking", "security", "src/b.py", 20). The OWASP a/b ones normalize to the
    # same severity/category/file/line tuple. -> intersection should be 2.
    assert result["n_intersection"] == 2, f"expected 2 overlapping tuples, got {result['n_intersection']} (a={result['count_a']}, b={result['count_b']})"
    assert result["n_union"] == 8, f"expected 8 in union, got {result['n_union']}"
    assert abs(result["jaccard"] - 0.25) < 1e-9, f"jaccard expected 0.25, got {result['jaccard']!r}"
    assert abs(result["diversity"] - 0.75) < 1e-9, f"diversity expected 0.75, got {result['diversity']!r}"


# ---------------------------------------------------------------------------
# AC2: Empty-input safety
# ---------------------------------------------------------------------------

def test_spec_991_ac2_empty_inputs_return_blind_spot(vd):
    """Empty inputs yield classification='blind-spot', alert='[VALIDATOR-BLIND-SPOT]', diversity=0.0, no exception."""
    # Should NOT raise.
    result = vd.score("", "")
    assert result["classification"] == "blind-spot", f"classification={result['classification']!r}"
    assert result["alert"] == "[VALIDATOR-BLIND-SPOT]", f"alert={result['alert']!r}"
    assert result["diversity"] == 0.0, f"diversity={result['diversity']!r}"


# ---------------------------------------------------------------------------
# AC3: Tiny-sample suppression (count_a + count_b < 6)
# ---------------------------------------------------------------------------

def test_spec_991_ac3_tiny_sample_no_alert_even_at_high_jaccard(vd):
    """When count_a + count_b < 6, classification='tiny-sample' and alert is None.

    Use 5 total findings where every reviewer finding overlaps with security
    (jaccard would be 1.0 if sample were large enough). Alert must still be None.
    """
    # Reviewer: 3 findings, all matching first 3 security findings (after normalization).
    reviewer_text = """
### FINDING-1
- **Severity**: high
- **Category**: security
- **File**: `src/a.py:10`

### FINDING-2
- **Severity**: high
- **Category**: security
- **File**: `src/b.py:20`
"""

    security_text = """
## A01: Broken Access Control
- **Severity**: high
- **Location**: src/a.py:10

## A02: Cryptographic Failures
- **Severity**: high
- **Location**: src/b.py:20

## A03: Injection
- **Severity**: high
- **Location**: src/c.py:30
"""

    result = vd.score(reviewer_text, security_text)
    total = result["count_a"] + result["count_b"]
    assert total == 5, f"setup error: count_a+count_b should be 5, got {total} (a={result['count_a']}, b={result['count_b']})"
    assert total < 6
    assert result["classification"] == "tiny-sample", f"classification={result['classification']!r}"
    assert result["alert"] is None, f"alert should be None, got {result['alert']!r}"


# ---------------------------------------------------------------------------
# AC4: Single-run rubber-stamp alert (count_a + count_b >= 6 AND jaccard > 0.8)
# ---------------------------------------------------------------------------

def test_spec_991_ac4_rubber_stamp_alert_at_high_jaccard_with_enough_sample(vd):
    """count_a+count_b >= 6 AND jaccard > 0.8 -> rubber-stamp + [VALIDATOR-OVERLAP]."""
    # Build 4 reviewer findings that EXACTLY match 4 security findings + 0 new -> jaccard = 1.0
    # Total = 8, jaccard = 1.0 > 0.8.
    reviewer_text = """
### FINDING-1
- **Severity**: high
- **Category**: security
- **File**: `src/a.py:10`

### FINDING-2
- **Severity**: high
- **Category**: security
- **File**: `src/b.py:20`

### FINDING-3
- **Severity**: high
- **Category**: security
- **File**: `src/c.py:30`

### FINDING-4
- **Severity**: high
- **Category**: security
- **File**: `src/d.py:40`
"""

    security_text = """
## A01: Broken Access Control
- **Severity**: high
- **Location**: src/a.py:10

## A02: Cryptographic Failures
- **Severity**: high
- **Location**: src/b.py:20

## A03: Injection
- **Severity**: high
- **Location**: src/c.py:30

## A04: Insecure Design
- **Severity**: high
- **Location**: src/d.py:40
"""

    result = vd.score(reviewer_text, security_text)
    total = result["count_a"] + result["count_b"]
    assert total >= 6, f"setup error: need >=6 findings, got {total}"
    assert result["jaccard"] > 0.8, f"setup error: jaccard should be >0.8, got {result['jaccard']!r}"
    assert result["classification"] == "rubber-stamp", f"classification={result['classification']!r}"
    assert result["alert"] == "[VALIDATOR-OVERLAP]", f"alert={result['alert']!r}"


# ---------------------------------------------------------------------------
# AC5: CIA report subsection — must be referenced in the CIA agent prompt with
# the required fields. Omission behavior when files missing must be documented.
# ---------------------------------------------------------------------------

def test_spec_991_ac5_cia_agent_documents_validator_diversity_subsection():
    """CIA agent prompt MUST include a '### Validator Diversity' block with required fields."""
    content = CIA_AGENT_PATH.read_text(encoding="utf-8")
    assert "### Validator Diversity" in content, "CIA agent missing '### Validator Diversity' subsection header"
    # Required fields per AC5
    for field in ("Diversity", "Jaccard", "Reviewer", "Security", "Classification"):
        assert field in content, f"CIA agent missing required field '{field}' in report template"


def test_spec_991_ac5_cia_agent_documents_omission_when_files_missing():
    """When artifact files are missing, the CIA agent MUST OMIT the subsection (not error)."""
    content = CIA_AGENT_PATH.read_text(encoding="utf-8").lower()
    # Look for "omit" semantics tied to files-missing / files_present false.
    assert "omit" in content, "CIA agent must document 'omit' behavior for missing files"
    # The agent should reference the files_present flag or equivalent missing-files semantics.
    assert ("files_present" in content) or ("artifact files are missing" in content), (
        "CIA agent must condition omission on missing files"
    )


def test_spec_991_ac5_score_from_paths_signals_missing_artifacts(vd, tmp_path):
    """When at least one input file is missing, score_from_paths must signal so caller can omit."""
    # Neither file exists.
    missing_a = tmp_path / "reviewer.txt"
    missing_b = tmp_path / "security-auditor.txt"
    result = vd.score_from_paths(str(missing_a), str(missing_b))
    # The score dict must surface a flag indicating files are missing.
    # We accept either files_present=False or an equivalent boolean field.
    assert "files_present" in result, "score_from_paths must expose a 'files_present' field"
    assert result["files_present"] is False, "files_present must be False when files are missing"


def test_spec_991_ac5_score_from_paths_does_not_raise_when_files_missing(vd, tmp_path):
    """Missing artifact files MUST NOT raise — subsection is omitted, not errored."""
    missing_a = tmp_path / "does_not_exist_reviewer.txt"
    missing_b = tmp_path / "does_not_exist_security.txt"
    # Should not raise any exception.
    _ = vd.score_from_paths(str(missing_a), str(missing_b))


# ---------------------------------------------------------------------------
# AC6: Stdlib only + parser robustness
# ---------------------------------------------------------------------------

def test_spec_991_ac6_lib_imports_only_stdlib():
    """AST inspection: validator_diversity.py imports ONLY Python stdlib."""
    source = LIB_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level_imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level_imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                top_level_imports.add(node.module.split(".")[0])
    stdlib = set(sys.stdlib_module_names)
    nonstdlib = top_level_imports - stdlib
    assert not nonstdlib, f"non-stdlib imports detected: {nonstdlib}"


def test_spec_991_ac6_malformed_inputs_do_not_raise(vd):
    """Malformed reviewer/security text MUST NOT raise; yields zero findings parsed."""
    malformed_samples = [
        "this is not a structured finding at all",
        "### FINDING-1\nno fields here",
        "## A01: Broken Access Control\nno severity or location",
        "\x00\x01\x02 garbage bytes",
        "### FINDING-1\n**Severity**\n**Category**\n**File**\n",  # empty values
        "## ##### #### deeply nested malformed",
        "",  # totally empty
    ]
    for sample in malformed_samples:
        # Both as reviewer and as security input.
        # Must not raise.
        _ = vd.score(sample, sample)
        # The parser fns themselves must not raise either.
        _ = vd.parse_reviewer_findings(sample)
        _ = vd.parse_security_auditor_findings(sample)


def test_spec_991_ac6_score_does_not_raise_on_arbitrary_text(vd):
    """score() with completely unrelated text yields a valid result dict (no exception)."""
    result = vd.score("random reviewer junk", "random security junk")
    # We don't assert specific values — only that the contract is honored.
    for key in ("diversity", "jaccard", "count_a", "count_b", "classification"):
        assert key in result, f"missing key '{key}' in score() result"
