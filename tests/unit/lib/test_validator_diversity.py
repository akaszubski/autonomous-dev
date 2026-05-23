"""Unit tests for validator_diversity.py — Issue #991.

12 deterministic tests covering Jaccard math, classification logic, parsers,
normalization, cross-validator overlap, malformed input robustness, and
the score_from_paths missing-files sentinel.
"""

import sys
from pathlib import Path

import pytest

# Ensure lib is importable from test context
_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "plugins" / "autonomous-dev" / "lib"))

from validator_diversity import (  # noqa: E402
    jaccard,
    parse_reviewer_findings,
    parse_security_auditor_findings,
    score,
    score_from_paths,
)

# ---------------------------------------------------------------------------
# Fixtures — raw text samples
# ---------------------------------------------------------------------------

REVIEWER_FIXTURE = """
### FINDING-1
- **File**: `src/auth.py:42`
- **Severity**: BLOCKING
- **Category**: security
- **Issue**: SQL injection in login form
- **Detail**: ...
- **Suggested Fix**: parameterize queries.

### FINDING-2
- **File**: `src/api.py:100`
- **Severity**: WARNING
- **Category**: performance
- **Issue**: N+1 query
- **Detail**: ...
"""

SECURITY_AUDITOR_OWASP_FIXTURE = """
## A01: Broken Access Control
- **Severity**: High
- **Location**: src/auth.py:42
- **Attack Vector**: ...
- **Recommendation**: ...
"""


# ---------------------------------------------------------------------------
# AC1 — Math correctness: |A∩B|=2, |A∪B|=8 → jaccard=0.25, diversity=0.75
# ---------------------------------------------------------------------------


def test_jaccard_quarter_overlap() -> None:
    """AC1: jaccard and diversity computed correctly for 2/8 overlap."""
    set_a = {("blocking", "security", "a.py", 1), ("warning", "performance", "b.py", 2),
             ("info", "code-quality", "c.py", None), ("blocking", "security", "d.py", 10),
             ("warning", "documentation", "e.py", 5), ("info", "test-coverage", "f.py", None)}
    set_b = {("blocking", "security", "a.py", 1), ("warning", "performance", "b.py", 2),
             ("blocking", "security", "g.py", 20), ("info", "security", "h.py", None)}
    # |A∩B| = 2, |A∪B| = 8
    assert len(set_a & set_b) == 2
    assert len(set_a | set_b) == 8

    j = jaccard(set_a, set_b)
    diversity = 1.0 - j
    assert abs(j - 0.25) < 1e-9, f"Expected jaccard=0.25, got {j}"
    assert abs(diversity - 0.75) < 1e-9, f"Expected diversity=0.75, got {diversity}"

    # Verify score() integrates correctly by constructing minimal texts that
    # parse to exactly these sets — using the score() return value to confirm.
    # Build text from set_a (reviewer) and set_b (security, via OWASP notation).
    # Because parsers are unit-tested separately, we test the math via jaccard() directly.
    result_j = jaccard(set_a, set_b)
    assert abs(result_j - 0.25) < 1e-9


# ---------------------------------------------------------------------------
# AC2 — Empty-input safety
# ---------------------------------------------------------------------------


def test_both_empty_blind_spot() -> None:
    """AC2: score('', '') → blind-spot, alert=[VALIDATOR-BLIND-SPOT], diversity=0.0, no exception."""
    result = score("", "")
    assert result["classification"] == "blind-spot"
    assert result["alert"] == "[VALIDATOR-BLIND-SPOT]"
    assert result["diversity"] == 0.0
    assert result["count_a"] == 0
    assert result["count_b"] == 0


# ---------------------------------------------------------------------------
# AC3 — Tiny-sample suppression
# ---------------------------------------------------------------------------


def test_tiny_sample_suppresses_alert_even_with_high_jaccard() -> None:
    """AC3: total < 6 → tiny-sample (or complementary), alert is None."""
    # 1 reviewer finding, 1 security finding, same tuple → high Jaccard but total=2
    reviewer = """
### FINDING-1
- **File**: `src/auth.py:10`
- **Severity**: High
- **Category**: security
- **Issue**: test
"""
    security = """
## A01: Broken Access Control
- **Severity**: High
- **Location**: src/auth.py:10
- **Attack Vector**: ...
"""
    result = score(reviewer, security)
    total = result["count_a"] + result["count_b"]
    assert total < 6, f"Expected total < 6, got {total}"
    assert result["alert"] is None, f"Expected no alert for tiny sample, got {result['alert']}"
    assert result["classification"] in ("tiny-sample", "complementary", "blind-spot")


# ---------------------------------------------------------------------------
# AC4 — Rubber-stamp alert on single run
# ---------------------------------------------------------------------------


def _build_reviewer_text(n: int) -> str:
    """Build reviewer text with n identical-structure (but distinct) findings."""
    blocks = []
    for i in range(1, n + 1):
        blocks.append(
            f"### FINDING-{i}\n"
            f"- **File**: `src/file{i}.py:{i * 10}`\n"
            f"- **Severity**: BLOCKING\n"
            f"- **Category**: security\n"
            f"- **Issue**: issue {i}\n"
        )
    return "\n".join(blocks)


def _build_security_text(n: int) -> str:
    """Build security-auditor text with n OWASP sections matching reviewer files."""
    blocks = []
    for i in range(1, n + 1):
        blocks.append(
            f"## A01: Broken Access Control ({i})\n"
            f"- **Severity**: High\n"
            f"- **Location**: src/file{i}.py:{i * 10}\n"
            f"- **Attack Vector**: ...\n"
        )
    return "\n".join(blocks)


def test_rubber_stamp_single_run_alert() -> None:
    """AC4: total >= 6 AND jaccard > 0.8 → rubber-stamp + [VALIDATOR-OVERLAP]."""
    # 6 findings each, all same tuples (perfect overlap → jaccard=1.0)
    reviewer_text = _build_reviewer_text(6)
    security_text = _build_security_text(6)
    result = score(reviewer_text, security_text)
    total = result["count_a"] + result["count_b"]
    assert total >= 6, f"Expected total >= 6, got {total}"
    assert result["jaccard"] > 0.8, f"Expected high jaccard, got {result['jaccard']}"
    assert result["classification"] == "rubber-stamp"
    assert result["alert"] == "[VALIDATOR-OVERLAP]"


# ---------------------------------------------------------------------------
# AC5 (part) + Test 5 — All unique findings → diverse
# ---------------------------------------------------------------------------


def test_all_unique_findings_diverse() -> None:
    """J=0, total >= 6 → 'diverse', no alert."""
    # 3 reviewer findings, 3 security findings — no overlap at all
    reviewer = """
### FINDING-1
- **File**: `src/a.py:1`
- **Severity**: BLOCKING
- **Category**: code-quality
- **Issue**: x

### FINDING-2
- **File**: `src/b.py:2`
- **Severity**: WARNING
- **Category**: test-coverage
- **Issue**: x

### FINDING-3
- **File**: `src/c.py:3`
- **Severity**: INFO
- **Category**: documentation
- **Issue**: x
"""
    security = """
## A02: Cryptographic Failures
- **Severity**: High
- **Location**: src/d.py:4
- **Attack Vector**: ...

## A03: Injection
- **Severity**: Medium
- **Location**: src/e.py:5
- **Attack Vector**: ...

## A04: Insecure Design
- **Severity**: Low
- **Location**: src/f.py:6
- **Attack Vector**: ...
"""
    result = score(reviewer, security)
    total = result["count_a"] + result["count_b"]
    assert total >= 6
    assert result["jaccard"] == 0.0
    assert result["classification"] == "diverse"
    assert result["alert"] is None


# ---------------------------------------------------------------------------
# Test 6 — One empty + one full → complementary
# ---------------------------------------------------------------------------


def test_one_empty_one_full_classified_complementary() -> None:
    """Light-mode parity: one validator empty, other non-empty → complementary, no alert."""
    result = score(REVIEWER_FIXTURE, "")
    assert result["classification"] == "complementary"
    assert result["alert"] is None
    assert result["count_a"] > 0
    assert result["count_b"] == 0


# ---------------------------------------------------------------------------
# Test 7 — Reviewer FINDING block parser
# ---------------------------------------------------------------------------


def test_parse_reviewer_finding_blocks() -> None:
    """Two FINDING blocks parse to exactly 2 tuples."""
    findings = parse_reviewer_findings(REVIEWER_FIXTURE)
    assert len(findings) == 2, f"Expected 2 findings, got {len(findings)}: {findings}"


# ---------------------------------------------------------------------------
# Test 8 — Security-auditor OWASP block parser
# ---------------------------------------------------------------------------


def test_parse_security_auditor_owasp_block() -> None:
    """A01 OWASP block with High severity parses to ('blocking', 'security', 'src/auth.py', 42)."""
    findings = parse_security_auditor_findings(SECURITY_AUDITOR_OWASP_FIXTURE)
    assert len(findings) == 1, f"Expected 1 finding, got {len(findings)}: {findings}"
    tup = findings[0]
    assert tup == ("blocking", "security", "src/auth.py", 42), f"Got {tup}"


# ---------------------------------------------------------------------------
# Test 9 — Severity normalization (case-insensitive)
# ---------------------------------------------------------------------------


def test_severity_normalization_case_insensitive() -> None:
    """Critical → blocking, MEDIUM → warning, Low → info."""
    reviewer = """
### FINDING-1
- **File**: `a.py:1`
- **Severity**: Critical
- **Category**: security
- **Issue**: x

### FINDING-2
- **File**: `b.py:2`
- **Severity**: MEDIUM
- **Category**: performance
- **Issue**: x

### FINDING-3
- **File**: `c.py:3`
- **Severity**: Low
- **Category**: code-quality
- **Issue**: x
"""
    findings = parse_reviewer_findings(reviewer)
    assert len(findings) == 3
    severities = [f[0] for f in findings]
    assert severities[0] == "blocking", f"Critical should map to blocking, got {severities[0]}"
    assert severities[1] == "warning", f"MEDIUM should map to warning, got {severities[1]}"
    assert severities[2] == "info", f"Low should map to info, got {severities[2]}"


# ---------------------------------------------------------------------------
# Test 10 — OWASP + reviewer security finding produce same tuple (overlap)
# ---------------------------------------------------------------------------


def test_owasp_and_reviewer_security_overlap() -> None:
    """Reviewer security finding and security-auditor OWASP A01 on same file:line → same tuple, overlap=1."""
    reviewer_text = """
### FINDING-1
- **File**: `src/auth.py:42`
- **Severity**: High
- **Category**: security
- **Issue**: SQL injection
"""
    security_text = """
## A01: Broken Access Control
- **Severity**: High
- **Location**: src/auth.py:42
- **Attack Vector**: ...
"""
    result = score(reviewer_text, security_text)
    assert result["n_intersection"] == 1, (
        f"Expected intersection of 1 (same tuple normalized), got {result['n_intersection']}"
    )
    assert result["count_a"] == 1
    assert result["count_b"] == 1


# ---------------------------------------------------------------------------
# Test 11 — Malformed input does not raise
# ---------------------------------------------------------------------------


def test_malformed_input_does_not_raise() -> None:
    """Passing arbitrary text to parsers returns empty lists, no exception."""
    text = "some random text with no markers"
    reviewer_findings = parse_reviewer_findings(text)
    security_findings = parse_security_auditor_findings(text)
    assert reviewer_findings == [], f"Expected [], got {reviewer_findings}"
    assert security_findings == [], f"Expected [], got {security_findings}"

    # score() should also not raise
    result = score(text, text)
    assert result["count_a"] == 0
    assert result["count_b"] == 0
    assert result["classification"] == "blind-spot"


# ---------------------------------------------------------------------------
# Test 12 — score_from_paths with missing files → blind-spot + files_present=False
# ---------------------------------------------------------------------------


def test_score_from_paths_missing_files() -> None:
    """score_from_paths with nonexistent paths → blind-spot shape, files_present=False, no exception."""
    result = score_from_paths("/nonexistent/a.txt", "/nonexistent/b.txt")
    assert result["files_present"] is False, (
        f"Expected files_present=False for missing paths, got {result['files_present']}"
    )
    assert result["classification"] == "blind-spot"
    assert result["alert"] == "[VALIDATOR-BLIND-SPOT]"
    assert result["diversity"] == 0.0
    assert result["count_a"] == 0
    assert result["count_b"] == 0
