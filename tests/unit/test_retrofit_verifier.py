"""
Unit tests for retrofit_verifier.py - Phase 5: Verification and compliance checking.

TDD RED PHASE - These tests WILL FAIL until implementation exists.

Tests cover:
- Compliance checks (PROJECT.md, file org, tests, git)
- Test suite execution (mocked pytest)
- Compatibility verification
- Readiness assessment
- Verification report format
- Edge case: Tests failing
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Import correct classes from implementation
from plugins.autonomous_dev.lib.retrofit_verifier import (
    ComplianceCheck,
    # ComplianceStatus does not exist - removed
    RetrofitVerifier,
    VerificationResult,  # Changed from VerificationResult (checking actual name)
)


class TestComplianceChecks:
    """Test compliance checking against autonomous-dev standards."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project directory."""
        project = tmp_path
        project.mkdir(exist_ok=True)
        return project

    @pytest.fixture
    def verifier(self, temp_project):
        """Create RetrofitVerifier instance."""
        return RetrofitVerifier(project_root=temp_project)

    def test_check_project_md_exists(self, verifier, temp_project):
        """Test checking PROJECT.md exists."""
        claude_dir = temp_project / ".claude"
        claude_dir.mkdir()
        (claude_dir / "PROJECT.md").write_text("## GOALS\n\nTest goals\n")

        check = verifier.check_project_md()

        assert check.passed == True
        assert check.check_name == "PROJECT.md exists"

    def test_check_project_md_missing_fails(self, verifier):
        """Test PROJECT.md missing fails compliance."""
        check = verifier.check_project_md()

        assert check.passed == False
        assert "missing" in check.message.lower()

    def test_check_project_md_structure(self, verifier, temp_project):
        """Test checking PROJECT.md has required sections."""
        claude_dir = temp_project / ".claude"
        claude_dir.mkdir()
        (claude_dir / "PROJECT.md").write_text(
            "## GOALS\n\nGoals\n\n## SCOPE\n\nScope\n\n## CONSTRAINTS\n\nConstraints\n\n## ARCHITECTURE\n\nArch\n"
        )

        check = verifier.check_project_md_structure()

        assert check.passed == True
        assert all(
            section in check.details
            for section in ["GOALS", "SCOPE", "CONSTRAINTS", "ARCHITECTURE"]
        )

    def test_check_file_organization(self, verifier, temp_project):
        """Test checking file organization compliance."""
        # Create standard structure
        (temp_project / "src").mkdir()
        (temp_project / "tests").mkdir()
        (temp_project / "docs").mkdir()
        (temp_project / "src" / "main.py").write_text("def main(): pass\n")

        check = verifier.check_file_organization()

        assert check.passed == True
        assert "organized" in check.message.lower()

    def test_check_file_organization_flat_structure_warning(self, verifier, temp_project):
        """Test flat structure gets warning."""
        # Create flat structure
        (temp_project / "main.py").write_text("def main(): pass\n")
        (temp_project / "utils.py").write_text("def util(): pass\n")

        check = verifier.check_file_organization()

        assert check.passed == False
        assert "flat" in check.message.lower()

    def test_check_test_directory_exists(self, verifier, temp_project):
        """Test checking test directory exists."""
        (temp_project / "tests").mkdir()
        (temp_project / "tests" / "test_main.py").write_text("def test_main(): assert True\n")

        check = verifier.check_test_directory()

        assert check.passed == True

    def test_check_test_directory_missing_fails(self, verifier):
        """Test missing test directory fails."""
        check = verifier.check_test_directory()

        assert check.passed == False
        assert "test" in check.message.lower()

    def test_check_git_repository_exists(self, verifier, temp_project):
        """Test checking git repository exists."""
        git_dir = temp_project / ".git"
        git_dir.mkdir()

        check = verifier.check_git_repository()

        assert check.passed == True

    def test_check_git_repository_missing_warning(self, verifier):
        """Test missing git repo gets warning."""
        check = verifier.check_git_repository()

        assert check.passed == False
        assert "git" in check.message.lower()

    def test_check_dependency_management(self, verifier, temp_project):
        """Test checking dependency management files."""
        (temp_project / "requirements.txt").write_text("pytest==7.4.0\n")

        check = verifier.check_dependency_management()

        assert check.passed == True
        assert "requirements.txt" in check.details

    def test_check_ci_cd_configuration(self, verifier, temp_project):
        """Test checking CI/CD configuration."""
        workflows_dir = temp_project / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "ci.yml").write_text("name: CI\n")

        check = verifier.check_ci_cd_configuration()

        assert check.passed == True

    def test_check_ci_cd_missing_warning(self, verifier):
        """Test missing CI/CD gets warning."""
        check = verifier.check_ci_cd_configuration()

        assert check.passed == False

    def test_check_documentation_exists(self, verifier, temp_project):
        """Test checking documentation exists."""
        (temp_project / "README.md").write_text("# Project\n")
        docs_dir = temp_project / "docs"
        docs_dir.mkdir()

        check = verifier.check_documentation()

        assert check.passed == True

    def test_check_env_config_support(self, verifier, temp_project):
        """Test checking environment config support."""
        (temp_project / ".env.example").write_text("API_KEY=your-key\n")

        check = verifier.check_env_config_support()

        assert check.passed == True


class TestTestSuiteExecution:
    """Test test suite execution and validation."""

    @pytest.fixture
    def verifier(self, tmp_path):
        """Create verifier instance."""
        return RetrofitVerifier(project_root=tmp_path)

    @patch("subprocess.run")
    def test_run_test_suite_success(self, mock_run, verifier):
        """Test running test suite successfully."""
        mock_run.return_value = Mock(returncode=0, stdout="5 passed")

        check = verifier.run_test_suite()

        assert check.passed == True
        assert "passed" in check.message.lower()

    @patch("subprocess.run")
    def test_run_test_suite_failures(self, mock_run, verifier):
        """Test handling test suite failures."""
        mock_run.return_value = Mock(returncode=1, stdout="3 passed, 2 failed")

        check = verifier.run_test_suite()

        assert check.passed == False
        assert "failed" in check.message.lower()

    @patch("subprocess.run")
    def test_run_test_suite_timeout(self, mock_run, verifier):
        """Test handling test suite timeout."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("pytest", 300)

        check = verifier.run_test_suite(timeout=300)

        assert check.passed == False
        assert "timeout" in check.message.lower()

    @patch("subprocess.run")
    def test_check_test_coverage(self, mock_run, verifier):
        """Test checking test coverage."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Coverage: 85%",
        )

        check = verifier.check_test_coverage()

        assert check.passed == True
        assert "85" in check.details

    @patch("subprocess.run")
    def test_check_test_coverage_below_threshold(self, mock_run, verifier):
        """Test coverage below 80% threshold fails."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Coverage: 65%",
        )

        check = verifier.check_test_coverage(threshold=80)

        assert check.passed == False
        assert "65" in check.message

    def test_test_suite_not_found_warning(self, verifier):
        """Test warning when no test suite found."""
        check = verifier.run_test_suite()

        assert check.passed == False
        assert "no tests" in check.message.lower()


class TestCompatibilityVerification:
    """Test compatibility verification with autonomous-dev."""

    @pytest.fixture
    def verifier(self, tmp_path):
        """Create verifier instance."""
        return RetrofitVerifier(project_root=tmp_path)

    def test_check_python_version_compatible(self, verifier):
        """Test checking Python version compatibility."""
        check = verifier.check_python_version()

        # Should pass if Python >= 3.8
        assert check.status in [ComplianceStatus.PASS, ComplianceStatus.WARNING]

    def test_check_plugin_installable(self, verifier, tmp_path):
        """Test checking if autonomous-dev plugin can be installed."""
        # Create .claude directory
        (tmp_path / ".claude").mkdir()

        check = verifier.check_plugin_installable()

        assert check.passed == True

    def test_check_hooks_compatible(self, verifier, tmp_path):
        """Test checking hook compatibility."""
        # Create .claude/hooks directory
        hooks_dir = tmp_path / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)

        check = verifier.check_hooks_compatible()

        assert check.passed == True

    def test_check_command_compatibility(self, verifier):
        """Test checking command compatibility."""
        check = verifier.check_command_compatibility()

        # Should check if project can use slash commands
        assert check.status in [ComplianceStatus.PASS, ComplianceStatus.WARNING]

    def test_check_directory_permissions(self, verifier, tmp_path):
        """Test checking directory permissions."""
        check = verifier.check_directory_permissions()

        # Should verify write permissions
        assert check.passed == True

    def test_check_disk_space_available(self, verifier):
        """Test checking available disk space."""
        check = verifier.check_disk_space()

        # Should verify enough space for plugin and backups
        assert check.status in [ComplianceStatus.PASS, ComplianceStatus.WARNING]


class TestReadinessAssessment:
    """Test overall readiness assessment."""

    @pytest.fixture
    def verifier(self, tmp_path):
        """Create verifier instance."""
        return RetrofitVerifier(project_root=tmp_path)

    def test_assess_readiness_all_pass(self, verifier):
        """Test readiness assessment when all checks pass."""
        with patch.object(verifier, "run_all_checks") as mock_checks:
            mock_checks.return_value = [
                ComplianceCheck(
                    check_name="Check 1",
                    passed=True,
                    message="Pass",
                ),
                ComplianceCheck(
                    check_name="Check 2",
                    passed=True,
                    message="Pass",
                ),
            ]

            report = verifier.assess_readiness()

        assert report.is_ready is True
        assert report.readiness_score == 100

    def test_assess_readiness_with_warnings(self, verifier):
        """Test readiness assessment with warnings."""
        with patch.object(verifier, "run_all_checks") as mock_checks:
            mock_checks.return_value = [
                ComplianceCheck(
                    check_name="Check 1",
                    passed=True,
                    message="Pass",
                ),
                ComplianceCheck(
                    check_name="Check 2",
                    passed=False,
                    message="Warning",
                ),
            ]

            report = verifier.assess_readiness()

        assert report.is_ready is True  # Warnings don't block
        assert 50 <= report.readiness_score < 100

    def test_assess_readiness_with_failures(self, verifier):
        """Test readiness assessment with failures."""
        with patch.object(verifier, "run_all_checks") as mock_checks:
            mock_checks.return_value = [
                ComplianceCheck(
                    check_name="Check 1",
                    passed=True,
                    message="Pass",
                ),
                ComplianceCheck(
                    check_name="Check 2",
                    passed=False,
                    message="Fail",
                ),
            ]

            report = verifier.assess_readiness()

        assert report.is_ready is False
        assert report.readiness_score < 100

    def test_calculate_readiness_score(self, verifier):
        """Test readiness score calculation."""
        checks = [
            ComplianceCheck(
                check_name="Check 1",
                passed=True,
                message="Pass",
            ),  # 100 points
            ComplianceCheck(
                check_name="Check 2",
                passed=False,
                message="Warning",
            ),  # 50 points
            ComplianceCheck(
                check_name="Check 3",
                passed=False,
                message="Fail",
            ),  # 0 points
        ]

        score = verifier.calculate_readiness_score(checks)

        # (100 + 50 + 0) / 3 = 50
        assert score == 50

    def test_identify_blockers(self, verifier):
        """Test identifying blocking issues."""
        checks = [
            ComplianceCheck(
                check_name="Non-blocker",
                passed=False,
                message="Warning",
            ),
            ComplianceCheck(
                check_name="Blocker",
                passed=False,
                message="Critical failure",
            ),
        ]

        blockers = verifier.identify_blockers(checks)

        assert len(blockers) == 1
        assert blockers[0].check_name == "Blocker"

    def test_generate_remediation_plan(self, verifier):
        """Test generating remediation plan for failures."""
        checks = [
            ComplianceCheck(
                check_name="Missing tests",
                passed=False,
                message="No test directory",
            ),
        ]

        plan = verifier.generate_remediation_plan(checks)

        assert len(plan) > 0
        assert any("test" in step.lower() for step in plan)


class TestVerificationResult:
    """Test verification report generation."""

    @pytest.fixture
    def sample_checks(self):
        """Create sample compliance checks."""
        return [
            ComplianceCheck(
                check_name="PROJECT.md exists",
                passed=True,
                message="Found",
                details={"path": ".claude/PROJECT.md"},
            ),
            ComplianceCheck(
                check_name="Test suite",
                passed=False,
                message="Low coverage",
                details={"coverage": "65%"},
            ),
            ComplianceCheck(
                check_name="CI/CD",
                passed=False,
                message="Not configured",
                details={},
            ),
        ]

    @pytest.fixture
    def sample_report(self, sample_checks):
        """Create sample verification report."""
        return VerificationResult(
            is_ready=False,
            readiness_score=55,
            checks=sample_checks,
            blockers=[sample_checks[2]],
            recommendations=["Add CI/CD pipeline", "Improve test coverage"],
        )

    def test_report_to_dict(self, sample_report):
        """Test converting report to dictionary."""
        data = sample_report.to_dict()

        assert isinstance(data, dict)
        assert data["is_ready"] is False
        assert data["readiness_score"] == 55
        assert len(data["checks"]) == 3

    def test_report_to_json(self, sample_report):
        """Test converting report to JSON."""
        json_str = sample_report.to_json()

        assert isinstance(json_str, str)
        assert "55" in json_str
        assert "PROJECT.md" in json_str

    def test_generate_summary(self, sample_report):
        """Test generating report summary."""
        summary = sample_report.generate_summary()

        assert "55" in summary
        assert "not ready" in summary.lower()
        assert "1 blocker" in summary.lower()

    def test_report_includes_pass_fail_counts(self, sample_report):
        """Test report includes pass/fail/warning counts."""
        summary = sample_report.generate_summary()

        assert "1 pass" in summary.lower() or "1 passed" in summary.lower()
        assert "1 warning" in summary.lower()
        assert "1 fail" in summary.lower() or "1 failed" in summary.lower()

    def test_report_includes_recommendations(self, sample_report):
        """Test report includes actionable recommendations."""
        summary = sample_report.generate_summary()

        assert any(rec in summary for rec in sample_report.recommendations)

    def test_export_report_to_markdown(self, sample_report):
        """Test exporting report to markdown."""
        markdown = sample_report.to_markdown()

        assert "# Verification Report" in markdown
        assert "Readiness Score: 55" in markdown
        assert "## Blockers" in markdown

    def test_report_ready_state(self):
        """Test report for ready project."""
        report = VerificationResult(
            is_ready=True,
            readiness_score=95,
            checks=[
                ComplianceCheck(
                    check_name="All checks",
                    passed=True,
                    message="Pass",
                )
            ],
            blockers=[],
            recommendations=["Maintain current practices"],
        )

        summary = report.generate_summary()
        assert "ready" in summary.lower()
        assert report.is_ready is True


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_tests_failing_after_migration(self, tmp_path):
        """Test handling tests that fail after migration."""
        verifier = RetrofitVerifier(project_root=tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="All tests failed")

            check = verifier.run_test_suite()

        assert check.passed == False
        assert "failed" in check.message.lower()

    def test_invalid_project_root(self):
        """Test handling invalid project root."""
        with pytest.raises(ValueError, match="Invalid project root"):
            RetrofitVerifier(project_root="/nonexistent/path")

    def test_permission_denied_during_checks(self, tmp_path):
        """Test handling permission denied errors."""
        protected_dir = tmp_path / "protected"
        protected_dir.mkdir()
        protected_dir.chmod(0o000)

        try:
            verifier = RetrofitVerifier(project_root=tmp_path)
            check = verifier.check_directory_permissions()

            # Should detect permission issues
            assert check.status in [ComplianceStatus.FAIL, ComplianceStatus.WARNING]
        finally:
            protected_dir.chmod(0o755)  # Cleanup

    def test_corrupted_project_md(self, tmp_path):
        """Test handling corrupted PROJECT.md."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "PROJECT.md").write_bytes(b"\x00\xff\xfe")

        verifier = RetrofitVerifier(project_root=tmp_path)
        check = verifier.check_project_md_structure()

        assert check.passed == False

    def test_empty_project_verification(self, tmp_path):
        """Test verifying completely empty project."""
        verifier = RetrofitVerifier(project_root=tmp_path)
        report = verifier.assess_readiness()

        # Should have many failures
        assert report.is_ready is False
        assert report.readiness_score < 50
        assert len(report.blockers) > 0

    @patch("subprocess.run")
    def test_test_command_not_found(self, mock_run, tmp_path):
        """Test handling pytest not installed."""
        mock_run.side_effect = FileNotFoundError("pytest not found")

        verifier = RetrofitVerifier(project_root=tmp_path)
        check = verifier.run_test_suite()

        assert check.passed == False
        assert "not found" in check.message.lower()
