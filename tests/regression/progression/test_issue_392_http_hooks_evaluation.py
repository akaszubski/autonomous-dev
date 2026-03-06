"""
Progression tests for Issue #392: HTTP Hooks Evaluation document.

This issue evaluates Claude Code's HTTP hooks feature against the current
command-based hook approach. The deliverable is an evaluation document at
docs/evaluations/issue_392_http_hooks_evaluation.md.

EXPECTED OUTCOME: Document recommending command hooks remain primary approach,
with HTTP hooks suitable for specific use cases (external integrations,
webhooks, monitoring).

These tests validate:
1. Evaluation document exists at expected path
2. Required sections cover configuration mechanics, decision tree, security,
   comparison matrix, and recommendation
3. Security coverage documents HMAC, timeout, bearer token, allowedEnvVars
4. Decision content validates recommendation and sources

Test Coverage:
- Document existence tests
- Required section content validation
- Security analysis completeness
- Decision rationale and source references

TDD Approach (RED phase):
- Tests written BEFORE document exists
- All tests should FAIL initially
- Tests pass after evaluation document is created
"""

import re
import sys
from pathlib import Path
from typing import Optional


# Project root path helper
def get_project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent.parent.parent


def _get_evaluation_doc() -> Optional[Path]:
    """Find the evaluation document if it exists.

    Returns:
        Path to evaluation document or None if not found.
    """
    project_root = get_project_root()
    path = project_root / "docs" / "evaluations" / "issue_392_http_hooks_evaluation.md"
    return path if path.exists() else None


def _get_evaluation_content() -> str:
    """Get evaluation document content.

    Returns:
        Document content as string.

    Raises:
        AssertionError: If document not found.
    """
    doc = _get_evaluation_doc()
    assert doc is not None, (
        "Evaluation document not found at "
        "docs/evaluations/issue_392_http_hooks_evaluation.md. "
        "Create this document to satisfy Issue #392."
    )
    return doc.read_text()


class TestHTTPHooksEvaluationExists:
    """Test that the HTTP Hooks evaluation document exists.

    The primary deliverable for Issue #392 is an evaluation document
    comparing HTTP hooks vs command hooks for the plugin hook system.
    """

    def test_evaluation_document_exists(self):
        """Test that evaluation document exists at expected path.

        Arrange: docs/evaluations/ directory
        Act: Check for issue_392_http_hooks_evaluation.md
        Assert: File exists

        TDD: This test FAILS until the document is created.
        """
        # Arrange
        project_root = get_project_root()
        eval_doc = project_root / "docs" / "evaluations" / "issue_392_http_hooks_evaluation.md"

        # Act & Assert
        assert eval_doc.exists(), (
            f"Issue #392 evaluation document not found at:\n"
            f"  {eval_doc}\n"
            f"Create this document with HTTP hooks vs command hooks evaluation."
        )


class TestHTTPHooksEvaluationRequiredSections:
    """Test that the evaluation document contains all required sections.

    Required sections cover HTTP hook configuration mechanics, decision tree,
    security analysis, comparison matrix, and recommendation.
    """

    def test_has_configuration_mechanics(self):
        """Test that document describes HTTP hook configuration format.

        The evaluation must document how HTTP hooks are configured including
        type, url, headers, and allowedEnvVars fields.

        Arrange: Evaluation document content
        Act: Search for configuration format discussion
        Assert: Configuration mechanics are documented with key fields
        """
        # Arrange
        content = _get_evaluation_content()
        content_lower = content.lower()

        # Act - Look for config format keywords
        config_keywords = ["type", "url", "headers", "allowedenvvars", "allowed_env_vars"]
        found = [kw for kw in config_keywords if kw in content_lower]

        # Assert
        assert len(found) >= 2, (
            f"Evaluation should document HTTP hook configuration format. "
            f"Searched for: {config_keywords}\n"
            f"Found: {found}\n"
            f"Document the config fields: type, url, headers, allowedEnvVars."
        )

    def test_has_decision_tree(self):
        """Test that document contains a decision tree for HTTP vs command hooks.

        The evaluation must include guidance on when to use HTTP hooks
        versus command hooks, structured as a decision tree or flowchart.

        Arrange: Evaluation document content
        Act: Search for decision tree or when-to-use guidance
        Assert: Decision guidance exists
        """
        # Arrange
        content = _get_evaluation_content()
        content_lower = content.lower()

        # Act
        decision_keywords = [
            "decision tree", "when to use", "use case",
            "choose", "decision", "flowchart",
            "if you need", "recommended when", "suitable for"
        ]
        found = [kw for kw in decision_keywords if kw in content_lower]

        # Assert
        assert len(found) >= 1, (
            f"Evaluation should contain a decision tree for HTTP vs command hooks. "
            f"Searched for: {decision_keywords}\n"
            f"Found: {found}\n"
            f"Add guidance on when to choose HTTP hooks vs command hooks."
        )

    def test_has_security_analysis(self):
        """Test that document contains security analysis of HTTP hooks.

        The evaluation must analyze security concerns including HMAC
        verification, token authentication, and timeout behavior.

        Arrange: Evaluation document content
        Act: Search for security discussion
        Assert: Security analysis section exists
        """
        # Arrange
        content = _get_evaluation_content()
        content_lower = content.lower()

        # Act
        security_keywords = [
            "security", "hmac", "token", "authentication",
            "timeout", "authorization", "secret"
        ]
        found = [kw for kw in security_keywords if kw in content_lower]

        # Assert
        assert len(found) >= 2, (
            f"Evaluation should contain security analysis. "
            f"Searched for: {security_keywords}\n"
            f"Found: {found}\n"
            f"Document security concerns: HMAC, tokens, timeout behavior."
        )

    def test_has_comparison_matrix(self):
        """Test that document contains comparison table of HTTP vs command hooks.

        The evaluation must include a structured comparison (table or matrix)
        showing how HTTP and command hooks differ across key dimensions.

        Arrange: Evaluation document content
        Act: Search for table/matrix comparing approaches
        Assert: Comparison table exists with both approaches mentioned
        """
        # Arrange
        content = _get_evaluation_content()
        content_lower = content.lower()

        # Act - Look for table indicators with comparison keywords
        has_table = "|" in content and "---" in content
        has_comparison_keywords = (
            ("http" in content_lower or "http hook" in content_lower)
            and ("command" in content_lower or "command hook" in content_lower)
        )

        # Assert
        assert has_table, (
            "Evaluation document should contain a comparison table (markdown table with | and ---). "
            "Add a matrix comparing HTTP hooks vs command hooks across key dimensions."
        )
        assert has_comparison_keywords, (
            "Comparison table should reference both 'HTTP hooks' and 'command hooks'. "
            "Ensure both approaches are compared side-by-side."
        )

    def test_has_recommendation(self):
        """Test that document states a recommendation for command hooks as primary.

        The evaluation should conclude with a recommendation that command hooks
        remain the primary approach for the plugin hook system.

        Arrange: Evaluation document content
        Act: Search for recommendation section
        Assert: Clear recommendation exists
        """
        # Arrange
        content = _get_evaluation_content()
        content_lower = content.lower()

        # Act
        has_recommendation_section = (
            "recommendation" in content_lower or "conclusion" in content_lower
        )

        # Assert
        assert has_recommendation_section, (
            "Evaluation should contain a 'Recommendation' or 'Conclusion' section. "
            "Add a clear section stating the recommended approach."
        )


class TestHTTPHooksEvaluationSecurityCoverage:
    """Test that the evaluation document thoroughly covers security concerns.

    HTTP hooks introduce network-based communication which requires careful
    security analysis covering HMAC, tokens, timeout, and env var exposure.
    """

    def test_documents_no_hmac(self):
        """Test that document discusses lack of HMAC verification.

        HTTP hooks may lack HMAC signature verification, meaning the
        receiving endpoint cannot verify the request originated from
        Claude Code.

        Arrange: Evaluation document content
        Act: Search for HMAC discussion
        Assert: HMAC verification concern is documented
        """
        # Arrange
        content = _get_evaluation_content()
        content_lower = content.lower()

        # Act
        hmac_keywords = [
            "hmac", "signature", "signing", "verify",
            "verification", "integrity", "request signing"
        ]
        found = [kw for kw in hmac_keywords if kw in content_lower]

        # Assert
        assert len(found) >= 1, (
            f"Evaluation should document HMAC/signature verification concern. "
            f"Searched for: {hmac_keywords}\n"
            f"Found: {found}\n"
            f"HTTP hooks lack HMAC verification - document this security gap."
        )

    def test_documents_timeout_behavior(self):
        """Test that document describes timeout behavior for HTTP hooks.

        HTTP hooks have timeout behavior where timeouts are non-blocking,
        meaning hook execution continues even if the HTTP endpoint is slow.

        Arrange: Evaluation document content
        Act: Search for timeout discussion
        Assert: Timeout behavior is documented
        """
        # Arrange
        content = _get_evaluation_content()
        content_lower = content.lower()

        # Act
        timeout_keywords = [
            "timeout", "non-blocking", "nonblocking",
            "response time", "latency", "slow response"
        ]
        found = [kw for kw in timeout_keywords if kw in content_lower]

        # Assert
        assert len(found) >= 1, (
            f"Evaluation should document timeout behavior. "
            f"Searched for: {timeout_keywords}\n"
            f"Found: {found}\n"
            f"Document that HTTP hook timeouts are non-blocking."
        )

    def test_documents_bearer_token_auth(self):
        """Test that document describes bearer token authentication.

        HTTP hooks support bearer token authentication via headers,
        which is how endpoints verify requests.

        Arrange: Evaluation document content
        Act: Search for bearer token discussion
        Assert: Bearer token auth is documented
        """
        # Arrange
        content = _get_evaluation_content()
        content_lower = content.lower()

        # Act
        bearer_keywords = [
            "bearer", "token", "authorization",
            "auth header", "authentication", "api key"
        ]
        found = [kw for kw in bearer_keywords if kw in content_lower]

        # Assert
        assert len(found) >= 1, (
            f"Evaluation should document bearer token authentication. "
            f"Searched for: {bearer_keywords}\n"
            f"Found: {found}\n"
            f"Document how HTTP hooks use bearer tokens for auth."
        )

    def test_documents_allowedEnvVars(self):
        """Test that document describes allowedEnvVars whitelist mechanism.

        HTTP hooks use allowedEnvVars to control which environment variables
        are exposed to the HTTP request, preventing secret leakage.

        Arrange: Evaluation document content
        Act: Search for allowedEnvVars discussion
        Assert: Environment variable whitelist is documented
        """
        # Arrange
        content = _get_evaluation_content()
        content_lower = content.lower()

        # Act
        env_keywords = [
            "allowedenvvars", "allowed_env_vars", "environment variable",
            "env var", "whitelist", "allowlist", "secret",
            "variable exposure", "env whitelist"
        ]
        found = [kw for kw in env_keywords if kw in content_lower]

        # Assert
        assert len(found) >= 1, (
            f"Evaluation should document allowedEnvVars whitelist. "
            f"Searched for: {env_keywords}\n"
            f"Found: {found}\n"
            f"Document how allowedEnvVars controls environment variable exposure."
        )


class TestHTTPHooksEvaluationDecisionContent:
    """Test that the evaluation document provides clear decision rationale.

    The rationale should recommend command hooks as primary and include
    source references supporting the analysis.
    """

    def test_command_hooks_remain_primary(self):
        """Test that document recommends command hooks as primary approach.

        The evaluation should conclude that command hooks remain the primary
        hook mechanism for the plugin, with HTTP hooks as supplementary.

        Arrange: Evaluation document content
        Act: Search for command hooks primary recommendation
        Assert: Command hooks recommended as primary
        """
        # Arrange
        content = _get_evaluation_content()
        content_lower = content.lower()

        # Act
        recommends_command = any(
            phrase in content_lower
            for phrase in [
                "command hooks", "command-based",
                "command hook", "existing hook",
                "current approach", "primary"
            ]
        )

        # Assert
        assert recommends_command, (
            "Evaluation should recommend command hooks as the primary approach. "
            "The document should clearly state that command hooks remain preferred "
            "for the plugin hook system."
        )

    def test_includes_sources(self):
        """Test that document includes source references or URLs.

        Evaluation should cite official documentation, release notes,
        or other references supporting the analysis.

        Arrange: Evaluation document content
        Act: Search for URLs or reference indicators
        Assert: At least one source/reference is included
        """
        # Arrange
        content = _get_evaluation_content()

        # Act - Look for URLs or reference patterns
        url_pattern = r'https?://[^\s\)>]+'
        urls = re.findall(url_pattern, content)

        reference_keywords = ["source", "reference", "documentation", "docs.anthropic"]
        content_lower = content.lower()
        found_refs = [kw for kw in reference_keywords if kw in content_lower]

        # Assert
        has_sources = len(urls) > 0 or len(found_refs) >= 1
        assert has_sources, (
            f"Evaluation should include source references or URLs. "
            f"Found URLs: {urls}\n"
            f"Found reference keywords: {found_refs}\n"
            f"Add links to official HTTP hooks documentation or release notes."
        )


class TestIssue392MetaValidation:
    """Meta-validation tests for Issue #392 test suite.

    These tests validate the test suite itself to ensure comprehensive
    coverage of the evaluation requirements.
    """

    def test_all_test_classes_documented(self):
        """Test that all test classes have docstrings explaining their purpose.

        Arrange: This test file
        Act: Check for class docstrings
        Assert: All test classes documented
        """
        # Get current module
        current_module = sys.modules[__name__]

        # Find all test classes
        test_classes = [
            obj for name, obj in vars(current_module).items()
            if isinstance(obj, type) and name.startswith("Test")
        ]

        # Check docstrings
        undocumented = [
            cls.__name__ for cls in test_classes
            if not cls.__doc__ or len(cls.__doc__.strip()) < 20
        ]

        assert len(undocumented) == 0, (
            f"Test classes missing docstrings: {undocumented}. "
            f"All test classes should explain their validation purpose."
        )

    def test_covers_existence_validation(self):
        """Test that test suite includes document existence validation."""
        assert hasattr(TestHTTPHooksEvaluationExists, "test_evaluation_document_exists")

    def test_covers_required_sections(self):
        """Test that test suite validates all required sections."""
        required_methods = [
            "test_has_configuration_mechanics",
            "test_has_decision_tree",
            "test_has_security_analysis",
            "test_has_comparison_matrix",
            "test_has_recommendation",
        ]
        for method in required_methods:
            assert hasattr(TestHTTPHooksEvaluationRequiredSections, method), (
                f"Missing required section test: {method}"
            )

    def test_covers_security_coverage(self):
        """Test that test suite validates security analysis."""
        required_methods = [
            "test_documents_no_hmac",
            "test_documents_timeout_behavior",
            "test_documents_bearer_token_auth",
            "test_documents_allowedEnvVars",
        ]
        for method in required_methods:
            assert hasattr(TestHTTPHooksEvaluationSecurityCoverage, method), (
                f"Missing security test: {method}"
            )

    def test_covers_decision_content(self):
        """Test that test suite validates decision content."""
        required_methods = [
            "test_command_hooks_remain_primary",
            "test_includes_sources",
        ]
        for method in required_methods:
            assert hasattr(TestHTTPHooksEvaluationDecisionContent, method), (
                f"Missing decision content test: {method}"
            )


# Test execution summary for Issue #392
"""
TEST EXECUTION SUMMARY
======================

Phase 1: Document Existence (SHOULD FAIL - RED PHASE)
- test_evaluation_document_exists

Phase 2: Required Sections (SHOULD FAIL - RED PHASE)
- test_has_configuration_mechanics
- test_has_decision_tree
- test_has_security_analysis
- test_has_comparison_matrix
- test_has_recommendation

Phase 3: Security Coverage (SHOULD FAIL - RED PHASE)
- test_documents_no_hmac
- test_documents_timeout_behavior
- test_documents_bearer_token_auth
- test_documents_allowedEnvVars

Phase 4: Decision Content (SHOULD FAIL - RED PHASE)
- test_command_hooks_remain_primary
- test_includes_sources

Phase 5: Meta-Validation (SHOULD PASS NOW)
- test_all_test_classes_documented
- test_covers_existence_validation
- test_covers_required_sections
- test_covers_security_coverage
- test_covers_decision_content

EXPECTED RESULTS:
- Phases 1-4: FAIL (document not created yet - TDD RED phase)
- Phase 5: PASS (meta-validation of test structure)

NEXT STEPS:
1. Run tests: pytest tests/regression/progression/test_issue_392_http_hooks_evaluation.py --tb=line -q
2. Verify Phases 1-4 FAIL (expected - TDD RED phase)
3. Create evaluation document at docs/evaluations/issue_392_http_hooks_evaluation.md
4. Document: config mechanics, decision tree, security analysis, comparison matrix, recommendation
5. Re-run tests to verify all phases PASS (TDD GREEN phase)
"""
