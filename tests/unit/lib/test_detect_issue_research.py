"""Tests for detect_issue_research() -- Issue #628."""

import sys

sys.path.insert(0, "plugins/autonomous-dev/lib")

from research_persistence import detect_issue_research


THOROUGH_ISSUE_BODY = """\
## Summary

This feature adds JWT authentication to the API gateway.

## Implementation Approach

Use PyJWT library with RS256 signing. Integrate at the middleware layer
so all routes are protected by default.

## What Does NOT Work

- HS256 is insecure for multi-service architectures
- Cookie-based sessions don't scale across microservices

## Security Considerations

- Rotate signing keys every 90 days
- Store refresh tokens in HttpOnly cookies
- Validate audience and issuer claims

## Test Scenarios

1. Valid token passes authentication
2. Expired token returns 401
3. Malformed token returns 400

## Scenarios

- High traffic: 10k req/s token validation
- Key rotation during active sessions

## Acceptance Criteria

- [ ] All API routes require valid JWT
- [ ] Token refresh endpoint works
"""

QUICK_ISSUE_BODY = """\
## Summary

Add rate limiting to the API.

## Implementation Approach

Use a sliding window counter with Redis.

## Test Scenarios

1. Requests under limit pass
2. Requests over limit get 429

## Acceptance Criteria

- [ ] Rate limiting works
- [ ] Returns 429 when exceeded
"""


class TestDetectIssueResearch:
    """Tests for detect_issue_research function."""

    def test_thorough_issue_body_detected(self) -> None:
        """Full thorough issue body with 6+ sections is detected as research-rich."""
        result = detect_issue_research(THOROUGH_ISSUE_BODY)
        assert result["is_research_rich"] is True
        assert result["section_count"] >= 3

    def test_quick_issue_body_not_detected(self) -> None:
        """Quick issue body with only 2 research sections is not research-rich."""
        result = detect_issue_research(QUICK_ISSUE_BODY)
        assert result["is_research_rich"] is False
        # "Implementation Approach" and "Test Scenarios" are research sections
        # "Summary" and "Acceptance Criteria" are NOT
        assert result["section_count"] == 2

    def test_empty_body(self) -> None:
        """Empty string returns not research-rich with zero sections."""
        result = detect_issue_research("")
        assert result["is_research_rich"] is False
        assert result["section_count"] == 0
        assert result["matched_sections"] == []
        assert result["issue_body_as_research"] == ""

    def test_none_body(self) -> None:
        """None input is handled gracefully."""
        result = detect_issue_research(None)  # type: ignore[arg-type]
        assert result["is_research_rich"] is False
        assert result["section_count"] == 0

    def test_code_blocks_stripped(self) -> None:
        """H2 headings inside code blocks are NOT counted."""
        body = """\
## Summary

Some text.

```markdown
## Implementation Approach

This is inside a code block and should not match.

## Security Considerations

Also inside code block.

## Edge Cases

Also inside code block.
```

## Acceptance Criteria

- [ ] Something
"""
        result = detect_issue_research(body)
        # Only non-code-block headings: Summary (excluded), Acceptance Criteria (excluded)
        assert result["is_research_rich"] is False
        assert result["section_count"] == 0

    def test_boundary_exactly_three_sections(self) -> None:
        """Body with exactly 3 research sections is research-rich."""
        body = """\
## Implementation Approach

Use pattern X.

## Security Considerations

Validate all inputs.

## Edge Cases

Handle empty input.
"""
        result = detect_issue_research(body)
        assert result["is_research_rich"] is True
        assert result["section_count"] == 3

    def test_boundary_two_sections(self) -> None:
        """Body with exactly 2 research sections is NOT research-rich."""
        body = """\
## Implementation Approach

Use pattern X.

## Security Considerations

Validate all inputs.
"""
        result = detect_issue_research(body)
        assert result["is_research_rich"] is False
        assert result["section_count"] == 2

    def test_case_insensitive_matching(self) -> None:
        """Headings are matched case-insensitively."""
        body = """\
## implementation approach

Use pattern X.

## security considerations

Validate inputs.

## edge cases

Handle empty input.
"""
        result = detect_issue_research(body)
        assert result["is_research_rich"] is True
        assert result["section_count"] == 3

    def test_matched_sections_list(self) -> None:
        """matched_sections contains the correct section names."""
        body = """\
## Implementation Approach

Details here.

## Dependencies

Library X, Library Y.

## Background

Historical context.
"""
        result = detect_issue_research(body)
        assert "Implementation Approach" in result["matched_sections"]
        assert "Dependencies" in result["matched_sections"]
        assert "Background" in result["matched_sections"]
        assert result["section_count"] == 3

    def test_issue_body_as_research_contains_content(self) -> None:
        """issue_body_as_research contains actual section content, not just headers."""
        body = """\
## Implementation Approach

Use the decorator pattern for middleware.

## Dependencies

- PyJWT >= 2.0
- cryptography >= 41.0

## Background

The current system uses session cookies.
"""
        result = detect_issue_research(body)
        research = result["issue_body_as_research"]
        assert "## Implementation Approach" in research
        assert "decorator pattern" in research
        assert "## Dependencies" in research
        assert "PyJWT" in research
        assert "## Background" in research
        assert "session cookies" in research

    def test_empty_sections_not_counted(self) -> None:
        """H2 headers with no content under them are NOT counted."""
        body = """\
## Implementation Approach

## Security Considerations

## Edge Cases

## Background

Actual content here.
"""
        result = detect_issue_research(body)
        # Only "Background" has content
        assert result["section_count"] == 1
        assert result["matched_sections"] == ["Background"]
        assert result["is_research_rich"] is False

    def test_non_research_sections_ignored(self) -> None:
        """Summary and Acceptance Criteria are not research-indicating."""
        body = """\
## Summary

This is a summary of the feature.

## Acceptance Criteria

- [ ] Feature works
- [ ] Tests pass
"""
        result = detect_issue_research(body)
        assert result["section_count"] == 0
        assert result["matched_sections"] == []
        assert result["is_research_rich"] is False


class TestEmpiricalSections:
    """Regression tests for Issue #1009 — empirical/scientific vocabulary allowlist."""

    def test_data_source_section_recognised(self) -> None:
        """'data source' is a recognised research section."""
        body = """\
## Background

Historical context about the system.

## Context

Relevant operational context.

## Data Source

The dataset was collected from production logs spanning 2024-2025.
"""
        result = detect_issue_research(body)
        assert result["is_research_rich"] is True
        assert result["section_count"] >= 3

    def test_empirical_analysis_section_recognised(self) -> None:
        """'empirical analysis' is a recognised research section."""
        body = """\
## Background

Historical context about the system.

## Context

Relevant operational context.

## Empirical Analysis

Quantitative analysis of 10,000 samples shows p < 0.01.
"""
        result = detect_issue_research(body)
        assert result["is_research_rich"] is True
        assert result["section_count"] >= 3

    def test_empirical_evidence_section_recognised(self) -> None:
        """'empirical evidence' is a recognised research section."""
        body = """\
## Background

Historical context about the system.

## Context

Relevant operational context.

## Empirical Evidence

Observed 42% latency reduction across 500 production deploys.
"""
        result = detect_issue_research(body)
        assert result["is_research_rich"] is True
        assert result["section_count"] >= 3

    def test_experimental_results_section_recognised(self) -> None:
        """'experimental results' is a recognised research section."""
        body = """\
## Background

Historical context about the system.

## Context

Relevant operational context.

## Experimental Results

A/B test with 10k users shows 15% improvement in retention.
"""
        result = detect_issue_research(body)
        assert result["is_research_rich"] is True
        assert result["section_count"] >= 3

    def test_findings_source_section_recognised(self) -> None:
        """'findings source' is a recognised research section."""
        body = """\
## Background

Historical context about the system.

## Context

Relevant operational context.

## Findings Source

Data sourced from internal monitoring dashboards.
"""
        result = detect_issue_research(body)
        assert result["is_research_rich"] is True
        assert result["section_count"] >= 3

    def test_measurements_section_recognised(self) -> None:
        """'measurements' is a recognised research section."""
        body = """\
## Background

Historical context about the system.

## Context

Relevant operational context.

## Measurements

p99 latency: 240ms baseline, 180ms after fix (25% reduction).
"""
        result = detect_issue_research(body)
        assert result["is_research_rich"] is True
        assert result["section_count"] >= 3

    def test_observed_behavior_section_recognised(self) -> None:
        """'observed behavior' is a recognised research section."""
        body = """\
## Background

Historical context about the system.

## Context

Relevant operational context.

## Observed Behavior

Hook fires 3x per Bash invocation in current implementation.
"""
        result = detect_issue_research(body)
        assert result["is_research_rich"] is True
        assert result["section_count"] >= 3

    def test_proposed_configuration_section_recognised(self) -> None:
        """'proposed configuration' is a recognised research section."""
        body = """\
## Background

Historical context about the system.

## Context

Relevant operational context.

## Proposed Configuration

max_connections: 100, timeout: 30s, retry_backoff: exponential.
"""
        result = detect_issue_research(body)
        assert result["is_research_rich"] is True
        assert result["section_count"] >= 3

    def test_proposed_values_section_recognised(self) -> None:
        """'proposed values' is a recognised research section."""
        body = """\
## Background

Historical context about the system.

## Context

Relevant operational context.

## Proposed Values

threshold=0.85, window=60s, burst_limit=200.
"""
        result = detect_issue_research(body)
        assert result["is_research_rich"] is True
        assert result["section_count"] >= 3

    def test_references_section_recognised(self) -> None:
        """'references' is a recognised research section."""
        body = """\
## Background

Historical context about the system.

## Context

Relevant operational context.

## References

- RFC 7519 (JWT)
- NIST SP 800-107 (SHA-based HMACs)
"""
        result = detect_issue_research(body)
        assert result["is_research_rich"] is True
        assert result["section_count"] >= 3

    def test_results_section_recognised(self) -> None:
        """'results' is a recognised research section."""
        body = """\
## Background

Historical context about the system.

## Context

Relevant operational context.

## Results

Error rate dropped from 2.3% to 0.1% after deploying the fix.
"""
        result = detect_issue_research(body)
        assert result["is_research_rich"] is True
        assert result["section_count"] >= 3

    def test_realistic_empirical_issue_body_is_rich(self) -> None:
        """End-to-end: a realistic empirical research issue body is classified as rich."""
        body = """\
## Background

The current rate-limiting implementation uses a fixed window counter
which causes thundering herd at window boundaries.

## Empirical Evidence

Observed 3.2x spike in 429 responses at each 60-second window boundary
across 5 days of production traffic logs (sample: 1.2M requests).

## Proposed Values

sliding_window_size: 60s, token_bucket_capacity: 1000,
refill_rate: 16.7 tokens/s (matches current avg throughput).

## Results

Sliding window simulation on the 1.2M request replay shows boundary
spike eliminated; p99 response time unchanged at 180ms.

## References

- Token bucket algorithm: RFC 6585 section 4
- Sliding window counter: Cloudflare blog "How we built rate limiting"
"""
        result = detect_issue_research(body)
        assert result["is_research_rich"] is True
        assert result["section_count"] == 5

    def test_two_new_sections_below_threshold(self) -> None:
        """Boundary guard: only 2 new-vocabulary sections does NOT reach the threshold."""
        body = """\
## Empirical Evidence

Latency increased by 40ms on average across sampled requests.

## Results

The fix reduced error rate from 5% to 0.5%.
"""
        result = detect_issue_research(body)
        assert result["is_research_rich"] is False
        assert result["section_count"] == 2
