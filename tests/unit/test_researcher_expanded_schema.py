#!/usr/bin/env python3
"""
TDD Tests for Researcher Agent Expanded Output Schema (FAILING - Red Phase)

This module contains FAILING tests for the expanded researcher agent output schemas
that will provide implementation_guidance and testing_guidance fields to downstream agents.

Feature Requirements (from implementation plan):
1. researcher-local adds implementation_guidance with: reusable_functions, import_patterns, error_handling_patterns
2. researcher-local adds testing_guidance with: test_file_patterns, edge_cases_to_test, mocking_patterns
3. researcher-web adds implementation_guidance with: design_patterns, performance_tips, library_integration_tips
4. researcher-web adds testing_guidance with: testing_frameworks, coverage_recommendations, testing_antipatterns
5. Backward compatibility: existing 4 fields still present (existing_patterns, files_to_update, architecture_notes, similar_implementations)

Test Coverage Target: 100% of schema validation

Following TDD principles:
- Write tests FIRST (red phase)
- Tests describe schema requirements
- Tests should FAIL until agents are updated
- Each test validates ONE schema requirement

Author: test-master agent
Date: 2025-12-13
Phase: TDD Red Phase
"""

import json
import pytest
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock, patch


class TestResearcherLocalExpandedSchema:
    """Test researcher-local agent expanded output schema with implementation and testing guidance."""

    @pytest.fixture
    def sample_researcher_local_output(self) -> Dict[str, Any]:
        """
        Sample JSON output that researcher-local should produce with expanded schema.

        This represents the expected format AFTER implementation.
        Tests should FAIL because agents don't produce this format yet.
        """
        return {
            # Existing fields (backward compatibility)
            "existing_patterns": [
                {
                    "file": "plugins/autonomous-dev/lib/security_utils.py",
                    "pattern": "Path validation with whitelist",
                    "lines": "42-58"
                }
            ],
            "files_to_update": ["plugins/autonomous-dev/lib/security_utils.py"],
            "architecture_notes": [
                "Project uses centralized security validation in lib/ directory"
            ],
            "similar_implementations": [
                {
                    "file": "plugins/autonomous-dev/lib/path_utils.py",
                    "similarity": "Also does path validation",
                    "reusable_code": "get_project_root() function"
                }
            ],
            # NEW: Implementation guidance fields
            "implementation_guidance": {
                "reusable_functions": [
                    {
                        "function": "validate_path_whitelist",
                        "location": "plugins/autonomous-dev/lib/security_utils.py:45",
                        "purpose": "Validates paths are within whitelist",
                        "usage_example": "validate_path_whitelist(path, project_root)"
                    }
                ],
                "import_patterns": [
                    {
                        "pattern": "from pathlib import Path",
                        "frequency": 15,
                        "rationale": "Project prefers Path objects over string paths"
                    }
                ],
                "error_handling_patterns": [
                    {
                        "pattern": "SecurityValidationError for security failures",
                        "location": "plugins/autonomous-dev/lib/security_utils.py:12",
                        "usage": "Raise custom exceptions for domain-specific errors"
                    }
                ]
            },
            # NEW: Testing guidance fields
            "testing_guidance": {
                "test_file_patterns": [
                    {
                        "pattern": "tests/unit/test_*.py for unit tests",
                        "example": "tests/unit/test_security_utils.py",
                        "convention": "Mirror source structure in tests/"
                    }
                ],
                "edge_cases_to_test": [
                    "Path traversal attacks (../../etc/passwd)",
                    "Symlink-based escapes",
                    "Empty/null input validation"
                ],
                "mocking_patterns": [
                    {
                        "pattern": "unittest.mock.patch for external dependencies",
                        "example": "patch('pathlib.Path.exists')",
                        "rationale": "Isolate unit tests from filesystem"
                    }
                ]
            }
        }

    def test_researcher_local_output_has_existing_patterns(self, sample_researcher_local_output):
        """
        Test that researcher-local output includes existing_patterns field.

        BACKWARD COMPATIBILITY: Ensure existing fields still present.
        Expected: Output has 'existing_patterns' array with file/pattern/lines.
        """
        output = sample_researcher_local_output

        assert "existing_patterns" in output, \
            "researcher-local output must include 'existing_patterns' field"

        assert isinstance(output["existing_patterns"], list), \
            "'existing_patterns' must be a list"

        if output["existing_patterns"]:
            pattern = output["existing_patterns"][0]
            assert "file" in pattern, "Pattern must include 'file' field"
            assert "pattern" in pattern, "Pattern must include 'pattern' field"
            assert "lines" in pattern, "Pattern must include 'lines' field"

    def test_researcher_local_output_has_files_to_update(self, sample_researcher_local_output):
        """
        Test that researcher-local output includes files_to_update field.

        BACKWARD COMPATIBILITY: Ensure existing fields still present.
        Expected: Output has 'files_to_update' array of strings.
        """
        output = sample_researcher_local_output

        assert "files_to_update" in output, \
            "researcher-local output must include 'files_to_update' field"

        assert isinstance(output["files_to_update"], list), \
            "'files_to_update' must be a list"

    def test_researcher_local_output_has_architecture_notes(self, sample_researcher_local_output):
        """
        Test that researcher-local output includes architecture_notes field.

        BACKWARD COMPATIBILITY: Ensure existing fields still present.
        Expected: Output has 'architecture_notes' array of strings.
        """
        output = sample_researcher_local_output

        assert "architecture_notes" in output, \
            "researcher-local output must include 'architecture_notes' field"

        assert isinstance(output["architecture_notes"], list), \
            "'architecture_notes' must be a list"

    def test_researcher_local_output_has_similar_implementations(self, sample_researcher_local_output):
        """
        Test that researcher-local output includes similar_implementations field.

        BACKWARD COMPATIBILITY: Ensure existing fields still present.
        Expected: Output has 'similar_implementations' array with file/similarity/reusable_code.
        """
        output = sample_researcher_local_output

        assert "similar_implementations" in output, \
            "researcher-local output must include 'similar_implementations' field"

        assert isinstance(output["similar_implementations"], list), \
            "'similar_implementations' must be a list"

        if output["similar_implementations"]:
            impl = output["similar_implementations"][0]
            assert "file" in impl, "Implementation must include 'file' field"
            assert "similarity" in impl, "Implementation must include 'similarity' field"
            assert "reusable_code" in impl, "Implementation must include 'reusable_code' field"

    def test_researcher_local_output_has_implementation_guidance(self, sample_researcher_local_output):
        """
        Test that researcher-local output includes implementation_guidance field.

        NEW FEATURE: Expanded schema for downstream agents.
        Expected: Output has 'implementation_guidance' object.
        """
        output = sample_researcher_local_output

        assert "implementation_guidance" in output, \
            "researcher-local output must include 'implementation_guidance' field"

        assert isinstance(output["implementation_guidance"], dict), \
            "'implementation_guidance' must be an object/dict"

    def test_researcher_local_implementation_guidance_has_reusable_functions(self, sample_researcher_local_output):
        """
        Test that implementation_guidance includes reusable_functions array.

        NEW FEATURE: Help implementer find and reuse existing functions.
        Expected: reusable_functions with function/location/purpose/usage_example.
        """
        guidance = sample_researcher_local_output["implementation_guidance"]

        assert "reusable_functions" in guidance, \
            "implementation_guidance must include 'reusable_functions' field"

        assert isinstance(guidance["reusable_functions"], list), \
            "'reusable_functions' must be a list"

        if guidance["reusable_functions"]:
            func = guidance["reusable_functions"][0]
            assert "function" in func, "Function must include 'function' name"
            assert "location" in func, "Function must include 'location' (file:line)"
            assert "purpose" in func, "Function must include 'purpose' description"
            assert "usage_example" in func, "Function must include 'usage_example'"

    def test_researcher_local_implementation_guidance_has_import_patterns(self, sample_researcher_local_output):
        """
        Test that implementation_guidance includes import_patterns array.

        NEW FEATURE: Help implementer follow project import conventions.
        Expected: import_patterns with pattern/frequency/rationale.
        """
        guidance = sample_researcher_local_output["implementation_guidance"]

        assert "import_patterns" in guidance, \
            "implementation_guidance must include 'import_patterns' field"

        assert isinstance(guidance["import_patterns"], list), \
            "'import_patterns' must be a list"

        if guidance["import_patterns"]:
            pattern = guidance["import_patterns"][0]
            assert "pattern" in pattern, "Import pattern must include 'pattern' string"
            assert "frequency" in pattern, "Import pattern must include 'frequency' count"
            assert "rationale" in pattern, "Import pattern must include 'rationale' explanation"

    def test_researcher_local_implementation_guidance_has_error_handling_patterns(self, sample_researcher_local_output):
        """
        Test that implementation_guidance includes error_handling_patterns array.

        NEW FEATURE: Help implementer follow project error handling conventions.
        Expected: error_handling_patterns with pattern/location/usage.
        """
        guidance = sample_researcher_local_output["implementation_guidance"]

        assert "error_handling_patterns" in guidance, \
            "implementation_guidance must include 'error_handling_patterns' field"

        assert isinstance(guidance["error_handling_patterns"], list), \
            "'error_handling_patterns' must be a list"

        if guidance["error_handling_patterns"]:
            pattern = guidance["error_handling_patterns"][0]
            assert "pattern" in pattern, "Error pattern must include 'pattern' description"
            assert "location" in pattern, "Error pattern must include 'location' reference"
            assert "usage" in pattern, "Error pattern must include 'usage' guidance"

    def test_researcher_local_output_has_testing_guidance(self, sample_researcher_local_output):
        """
        Test that researcher-local output includes testing_guidance field.

        NEW FEATURE: Expanded schema for test-master agent.
        Expected: Output has 'testing_guidance' object.
        """
        output = sample_researcher_local_output

        assert "testing_guidance" in output, \
            "researcher-local output must include 'testing_guidance' field"

        assert isinstance(output["testing_guidance"], dict), \
            "'testing_guidance' must be an object/dict"

    def test_researcher_local_testing_guidance_has_test_file_patterns(self, sample_researcher_local_output):
        """
        Test that testing_guidance includes test_file_patterns array.

        NEW FEATURE: Help test-master follow project test file conventions.
        Expected: test_file_patterns with pattern/example/convention.
        """
        guidance = sample_researcher_local_output["testing_guidance"]

        assert "test_file_patterns" in guidance, \
            "testing_guidance must include 'test_file_patterns' field"

        assert isinstance(guidance["test_file_patterns"], list), \
            "'test_file_patterns' must be a list"

        if guidance["test_file_patterns"]:
            pattern = guidance["test_file_patterns"][0]
            assert "pattern" in pattern, "Test file pattern must include 'pattern' description"
            assert "example" in pattern, "Test file pattern must include 'example' path"
            assert "convention" in pattern, "Test file pattern must include 'convention' explanation"

    def test_researcher_local_testing_guidance_has_edge_cases_to_test(self, sample_researcher_local_output):
        """
        Test that testing_guidance includes edge_cases_to_test array.

        NEW FEATURE: Help test-master identify important edge cases.
        Expected: edge_cases_to_test with array of strings.
        """
        guidance = sample_researcher_local_output["testing_guidance"]

        assert "edge_cases_to_test" in guidance, \
            "testing_guidance must include 'edge_cases_to_test' field"

        assert isinstance(guidance["edge_cases_to_test"], list), \
            "'edge_cases_to_test' must be a list"

    def test_researcher_local_testing_guidance_has_mocking_patterns(self, sample_researcher_local_output):
        """
        Test that testing_guidance includes mocking_patterns array.

        NEW FEATURE: Help test-master follow project mocking conventions.
        Expected: mocking_patterns with pattern/example/rationale.
        """
        guidance = sample_researcher_local_output["testing_guidance"]

        assert "mocking_patterns" in guidance, \
            "testing_guidance must include 'mocking_patterns' field"

        assert isinstance(guidance["mocking_patterns"], list), \
            "'mocking_patterns' must be a list"

        if guidance["mocking_patterns"]:
            pattern = guidance["mocking_patterns"][0]
            assert "pattern" in pattern, "Mocking pattern must include 'pattern' description"
            assert "example" in pattern, "Mocking pattern must include 'example' code"
            assert "rationale" in pattern, "Mocking pattern must include 'rationale' explanation"


class TestResearcherWebExpandedSchema:
    """Test researcher-web agent expanded output schema with implementation and testing guidance."""

    @pytest.fixture
    def sample_researcher_web_output(self) -> Dict[str, Any]:
        """
        Sample JSON output that researcher-web should produce with expanded schema.

        This represents the expected format AFTER implementation.
        Tests should FAIL because agents don't produce this format yet.
        """
        return {
            # Existing fields (backward compatibility)
            "best_practices": [
                "Use pathlib.Path for cross-platform path handling",
                "Validate all user inputs before processing"
            ],
            "recommended_libraries": [
                {
                    "name": "pathlib",
                    "purpose": "Object-oriented filesystem paths",
                    "rationale": "Standard library, cross-platform"
                }
            ],
            "security_considerations": [
                {
                    "risk": "Path traversal (CWE-22)",
                    "mitigation": "Validate paths against whitelist",
                    "severity": "High"
                }
            ],
            "common_pitfalls": [
                "Not resolving symlinks before validation",
                "Relying on string checks instead of Path methods"
            ],
            # NEW: Implementation guidance fields
            "implementation_guidance": {
                "design_patterns": [
                    {
                        "pattern": "Whitelist validation",
                        "use_case": "Path security",
                        "implementation": "Check resolved path starts with allowed root"
                    }
                ],
                "performance_tips": [
                    {
                        "tip": "Cache Path.resolve() results",
                        "impact": "Reduces filesystem calls",
                        "when_to_use": "When validating multiple paths against same root"
                    }
                ],
                "library_integration_tips": [
                    {
                        "library": "pathlib",
                        "tip": "Use Path.resolve(strict=True) to catch missing files early",
                        "caveat": "Raises FileNotFoundError if path doesn't exist"
                    }
                ]
            },
            # NEW: Testing guidance fields
            "testing_guidance": {
                "testing_frameworks": [
                    {
                        "framework": "pytest",
                        "rationale": "Industry standard for Python testing",
                        "key_features": ["Fixtures", "Parametrize", "Markers"]
                    }
                ],
                "coverage_recommendations": [
                    {
                        "metric": "Branch coverage",
                        "target": "80%+",
                        "focus": "Error handling paths"
                    }
                ],
                "testing_antipatterns": [
                    {
                        "antipattern": "Testing implementation details instead of behavior",
                        "why_bad": "Brittle tests that break on refactoring",
                        "alternative": "Test public API and observable behavior"
                    }
                ]
            }
        }

    def test_researcher_web_output_has_best_practices(self, sample_researcher_web_output):
        """
        Test that researcher-web output includes best_practices field.

        BACKWARD COMPATIBILITY: Ensure existing fields still present.
        Expected: Output has 'best_practices' array of strings.
        """
        output = sample_researcher_web_output

        assert "best_practices" in output, \
            "researcher-web output must include 'best_practices' field"

        assert isinstance(output["best_practices"], list), \
            "'best_practices' must be a list"

    def test_researcher_web_output_has_recommended_libraries(self, sample_researcher_web_output):
        """
        Test that researcher-web output includes recommended_libraries field.

        BACKWARD COMPATIBILITY: Ensure existing fields still present.
        Expected: Output has 'recommended_libraries' array with name/purpose/rationale.
        """
        output = sample_researcher_web_output

        assert "recommended_libraries" in output, \
            "researcher-web output must include 'recommended_libraries' field"

        assert isinstance(output["recommended_libraries"], list), \
            "'recommended_libraries' must be a list"

        if output["recommended_libraries"]:
            lib = output["recommended_libraries"][0]
            assert "name" in lib, "Library must include 'name' field"
            assert "purpose" in lib, "Library must include 'purpose' field"
            assert "rationale" in lib, "Library must include 'rationale' field"

    def test_researcher_web_output_has_security_considerations(self, sample_researcher_web_output):
        """
        Test that researcher-web output includes security_considerations field.

        BACKWARD COMPATIBILITY: Ensure existing fields still present.
        Expected: Output has 'security_considerations' array with risk/mitigation/severity.
        """
        output = sample_researcher_web_output

        assert "security_considerations" in output, \
            "researcher-web output must include 'security_considerations' field"

        assert isinstance(output["security_considerations"], list), \
            "'security_considerations' must be a list"

        if output["security_considerations"]:
            sec = output["security_considerations"][0]
            assert "risk" in sec, "Security consideration must include 'risk' field"
            assert "mitigation" in sec, "Security consideration must include 'mitigation' field"
            assert "severity" in sec, "Security consideration must include 'severity' field"

    def test_researcher_web_output_has_common_pitfalls(self, sample_researcher_web_output):
        """
        Test that researcher-web output includes common_pitfalls field.

        BACKWARD COMPATIBILITY: Ensure existing fields still present.
        Expected: Output has 'common_pitfalls' array of strings.
        """
        output = sample_researcher_web_output

        assert "common_pitfalls" in output, \
            "researcher-web output must include 'common_pitfalls' field"

        assert isinstance(output["common_pitfalls"], list), \
            "'common_pitfalls' must be a list"

    def test_researcher_web_output_has_implementation_guidance(self, sample_researcher_web_output):
        """
        Test that researcher-web output includes implementation_guidance field.

        NEW FEATURE: Expanded schema for downstream agents.
        Expected: Output has 'implementation_guidance' object.
        """
        output = sample_researcher_web_output

        assert "implementation_guidance" in output, \
            "researcher-web output must include 'implementation_guidance' field"

        assert isinstance(output["implementation_guidance"], dict), \
            "'implementation_guidance' must be an object/dict"

    def test_researcher_web_implementation_guidance_has_design_patterns(self, sample_researcher_web_output):
        """
        Test that implementation_guidance includes design_patterns array.

        NEW FEATURE: Help implementer apply industry-standard patterns.
        Expected: design_patterns with pattern/use_case/implementation.
        """
        guidance = sample_researcher_web_output["implementation_guidance"]

        assert "design_patterns" in guidance, \
            "implementation_guidance must include 'design_patterns' field"

        assert isinstance(guidance["design_patterns"], list), \
            "'design_patterns' must be a list"

        if guidance["design_patterns"]:
            pattern = guidance["design_patterns"][0]
            assert "pattern" in pattern, "Design pattern must include 'pattern' name"
            assert "use_case" in pattern, "Design pattern must include 'use_case' description"
            assert "implementation" in pattern, "Design pattern must include 'implementation' guidance"

    def test_researcher_web_implementation_guidance_has_performance_tips(self, sample_researcher_web_output):
        """
        Test that implementation_guidance includes performance_tips array.

        NEW FEATURE: Help implementer optimize performance.
        Expected: performance_tips with tip/impact/when_to_use.
        """
        guidance = sample_researcher_web_output["implementation_guidance"]

        assert "performance_tips" in guidance, \
            "implementation_guidance must include 'performance_tips' field"

        assert isinstance(guidance["performance_tips"], list), \
            "'performance_tips' must be a list"

        if guidance["performance_tips"]:
            tip = guidance["performance_tips"][0]
            assert "tip" in tip, "Performance tip must include 'tip' description"
            assert "impact" in tip, "Performance tip must include 'impact' explanation"
            assert "when_to_use" in tip, "Performance tip must include 'when_to_use' guidance"

    def test_researcher_web_implementation_guidance_has_library_integration_tips(self, sample_researcher_web_output):
        """
        Test that implementation_guidance includes library_integration_tips array.

        NEW FEATURE: Help implementer integrate external libraries correctly.
        Expected: library_integration_tips with library/tip/caveat.
        """
        guidance = sample_researcher_web_output["implementation_guidance"]

        assert "library_integration_tips" in guidance, \
            "implementation_guidance must include 'library_integration_tips' field"

        assert isinstance(guidance["library_integration_tips"], list), \
            "'library_integration_tips' must be a list"

        if guidance["library_integration_tips"]:
            tip = guidance["library_integration_tips"][0]
            assert "library" in tip, "Library tip must include 'library' name"
            assert "tip" in tip, "Library tip must include 'tip' description"
            assert "caveat" in tip, "Library tip must include 'caveat' warning"

    def test_researcher_web_output_has_testing_guidance(self, sample_researcher_web_output):
        """
        Test that researcher-web output includes testing_guidance field.

        NEW FEATURE: Expanded schema for test-master agent.
        Expected: Output has 'testing_guidance' object.
        """
        output = sample_researcher_web_output

        assert "testing_guidance" in output, \
            "researcher-web output must include 'testing_guidance' field"

        assert isinstance(output["testing_guidance"], dict), \
            "'testing_guidance' must be an object/dict"

    def test_researcher_web_testing_guidance_has_testing_frameworks(self, sample_researcher_web_output):
        """
        Test that testing_guidance includes testing_frameworks array.

        NEW FEATURE: Help test-master choose appropriate testing tools.
        Expected: testing_frameworks with framework/rationale/key_features.
        """
        guidance = sample_researcher_web_output["testing_guidance"]

        assert "testing_frameworks" in guidance, \
            "testing_guidance must include 'testing_frameworks' field"

        assert isinstance(guidance["testing_frameworks"], list), \
            "'testing_frameworks' must be a list"

        if guidance["testing_frameworks"]:
            framework = guidance["testing_frameworks"][0]
            assert "framework" in framework, "Framework must include 'framework' name"
            assert "rationale" in framework, "Framework must include 'rationale' explanation"
            assert "key_features" in framework, "Framework must include 'key_features' list"

    def test_researcher_web_testing_guidance_has_coverage_recommendations(self, sample_researcher_web_output):
        """
        Test that testing_guidance includes coverage_recommendations array.

        NEW FEATURE: Help test-master set appropriate coverage targets.
        Expected: coverage_recommendations with metric/target/focus.
        """
        guidance = sample_researcher_web_output["testing_guidance"]

        assert "coverage_recommendations" in guidance, \
            "testing_guidance must include 'coverage_recommendations' field"

        assert isinstance(guidance["coverage_recommendations"], list), \
            "'coverage_recommendations' must be a list"

        if guidance["coverage_recommendations"]:
            rec = guidance["coverage_recommendations"][0]
            assert "metric" in rec, "Coverage recommendation must include 'metric' type"
            assert "target" in rec, "Coverage recommendation must include 'target' percentage"
            assert "focus" in rec, "Coverage recommendation must include 'focus' area"

    def test_researcher_web_testing_guidance_has_testing_antipatterns(self, sample_researcher_web_output):
        """
        Test that testing_guidance includes testing_antipatterns array.

        NEW FEATURE: Help test-master avoid common testing mistakes.
        Expected: testing_antipatterns with antipattern/why_bad/alternative.
        """
        guidance = sample_researcher_web_output["testing_guidance"]

        assert "testing_antipatterns" in guidance, \
            "testing_guidance must include 'testing_antipatterns' field"

        assert isinstance(guidance["testing_antipatterns"], list), \
            "'testing_antipatterns' must be a list"

        if guidance["testing_antipatterns"]:
            antipattern = guidance["testing_antipatterns"][0]
            assert "antipattern" in antipattern, "Antipattern must include 'antipattern' description"
            assert "why_bad" in antipattern, "Antipattern must include 'why_bad' explanation"
            assert "alternative" in antipattern, "Antipattern must include 'alternative' approach"


class TestBackwardCompatibility:
    """Test that expanded schema maintains backward compatibility with existing code."""

    def test_existing_code_can_parse_expanded_schema(self):
        """
        Test that existing code expecting old schema can still parse expanded output.

        BACKWARD COMPATIBILITY: Code expecting 4 fields should still work.
        Expected: Can extract existing_patterns even when new fields present.
        """
        expanded_output = {
            "existing_patterns": [{"file": "test.py", "pattern": "test", "lines": "1-5"}],
            "files_to_update": ["test.py"],
            "architecture_notes": ["Note"],
            "similar_implementations": [],
            # New fields should not break existing parsers
            "implementation_guidance": {"reusable_functions": []},
            "testing_guidance": {"test_file_patterns": []}
        }

        # Simulate existing code that only expects 4 fields
        existing_patterns = expanded_output.get("existing_patterns", [])
        files_to_update = expanded_output.get("files_to_update", [])
        architecture_notes = expanded_output.get("architecture_notes", [])
        similar_implementations = expanded_output.get("similar_implementations", [])

        assert existing_patterns is not None
        assert files_to_update is not None
        assert architecture_notes is not None
        assert similar_implementations is not None

    def test_schema_validation_accepts_both_old_and_new_formats(self):
        """
        Test that schema validation accepts both old (4 fields) and new (6 fields) formats.

        BACKWARD COMPATIBILITY: Old format should still validate.
        Expected: Both formats pass validation.
        """
        old_format = {
            "existing_patterns": [],
            "files_to_update": [],
            "architecture_notes": [],
            "similar_implementations": []
        }

        new_format = {
            "existing_patterns": [],
            "files_to_update": [],
            "architecture_notes": [],
            "similar_implementations": [],
            "implementation_guidance": {
                "reusable_functions": [],
                "import_patterns": [],
                "error_handling_patterns": []
            },
            "testing_guidance": {
                "test_file_patterns": [],
                "edge_cases_to_test": [],
                "mocking_patterns": []
            }
        }

        # Both should have required base fields
        for fmt in [old_format, new_format]:
            assert "existing_patterns" in fmt
            assert "files_to_update" in fmt
            assert "architecture_notes" in fmt
            assert "similar_implementations" in fmt
