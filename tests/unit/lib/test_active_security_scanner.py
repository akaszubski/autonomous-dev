"""
Unit tests for active_security_scanner.py — Issue #710.

Tests cover:
- TestDependencyAudit: requirements parsing, vulnerable version detection, graceful degradation
- TestCredentialHistoryScan: git history scanning, pattern matching, graceful degradation
- TestOwaspPatternScan: dangerous pattern detection, comment/docstring/test file skipping
- TestFullScan: orchestration, aggregation, severity ordering
- TestFormatReport: markdown output, remediation included
"""

import importlib
import sys
import textwrap
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module import
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"

if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from active_security_scanner import (
    ActiveScanReport,
    Finding,
    Severity,
    credential_history_scan,
    dependency_audit,
    format_report,
    full_scan,
    owasp_pattern_scan,
)


# ---------------------------------------------------------------------------
# TestDependencyAudit
# ---------------------------------------------------------------------------


class TestDependencyAudit:
    """Tests for dependency_audit() function."""

    def test_parses_requirements_txt(self, tmp_path: Path):
        """Should parse requirements.txt and detect vulnerable packages."""
        req = tmp_path / "requirements.txt"
        req.write_text("django==3.2.0\nrequests==2.28.0\n")
        findings = dependency_audit(tmp_path)
        # django 3.2.0 < 3.2.25 should be flagged
        django_findings = [f for f in findings if "django" in f.description.lower()]
        assert len(django_findings) >= 1
        assert django_findings[0].severity in (Severity.HIGH, Severity.CRITICAL)
        assert django_findings[0].remediation

    def test_parses_pyproject_toml(self, tmp_path: Path):
        """Should parse pyproject.toml dependencies."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(textwrap.dedent("""\
            [project]
            dependencies = [
                "flask==2.3.0",
            ]
        """))
        findings = dependency_audit(tmp_path)
        flask_findings = [f for f in findings if "flask" in f.description.lower()]
        assert len(flask_findings) >= 1

    def test_detects_vulnerable_version(self, tmp_path: Path):
        """Should detect a known vulnerable version from DEPENDENCY_ADVISORIES."""
        req = tmp_path / "requirements.txt"
        req.write_text("cryptography==41.0.0\n")
        findings = dependency_audit(tmp_path)
        assert any("CVE-2023-49083" in f.description for f in findings)

    def test_safe_version_not_flagged(self, tmp_path: Path):
        """Should not flag a safe version."""
        req = tmp_path / "requirements.txt"
        req.write_text("django==5.0.4\n")
        findings = dependency_audit(tmp_path)
        django_findings = [f for f in findings if "django" in f.description.lower()]
        assert len(django_findings) == 0

    def test_handles_missing_requirements_file(self, tmp_path: Path):
        """Should return empty list when no requirements file exists."""
        findings = dependency_audit(tmp_path)
        # Should not crash, should return list (possibly from pip-audit)
        assert isinstance(findings, list)

    def test_handles_malformed_requirements(self, tmp_path: Path):
        """Should handle malformed requirements.txt without crashing."""
        req = tmp_path / "requirements.txt"
        req.write_text("this is not valid\n\n# comment\n==broken==\n")
        findings = dependency_audit(tmp_path)
        assert isinstance(findings, list)

    @patch("active_security_scanner.subprocess.run")
    def test_pip_audit_available(self, mock_run: MagicMock, tmp_path: Path):
        """Should use pip-audit output when available."""
        mock_run.return_value = MagicMock(
            stdout='[{"name": "urllib3", "version": "1.26.0", "vulns": [{"id": "CVE-TEST", "description": "test vuln", "fix_versions": ["2.0.7"]}]}]',
            returncode=0,
        )
        findings = dependency_audit(tmp_path)
        pip_audit_findings = [f for f in findings if "pip-audit" in f.file_path]
        assert len(pip_audit_findings) >= 1

    @patch("active_security_scanner.subprocess.run", side_effect=FileNotFoundError)
    def test_pip_audit_unavailable(self, mock_run: MagicMock, tmp_path: Path):
        """Should gracefully handle pip-audit not being installed."""
        findings = dependency_audit(tmp_path)
        assert isinstance(findings, list)  # No crash


# ---------------------------------------------------------------------------
# TestCredentialHistoryScan
# ---------------------------------------------------------------------------


class TestCredentialHistoryScan:
    """Tests for credential_history_scan() function."""

    def test_detects_secrets_in_git_output(self, tmp_path: Path):
        """Should detect an Anthropic API key in mocked git output."""
        fake_git_output = (
            "commit abc123def456\n"
            "diff --git a/config.py b/config.py\n"
            "+++ b/config.py\n"
            '+API_KEY = "sk-abcdefghijklmnopqrstuvwxyz12345678"\n'
        )
        with patch("active_security_scanner.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=fake_git_output)
            # Create .git dir to pass the git check
            (tmp_path / ".git").mkdir()
            findings = credential_history_scan(tmp_path)
            assert len(findings) >= 1
            assert findings[0].severity == Severity.CRITICAL
            assert "remediation" in findings[0].__dataclass_fields__

    def test_handles_no_git_repo(self, tmp_path: Path):
        """Should return empty list when not in a git repo."""
        findings = credential_history_scan(tmp_path)
        assert findings == []

    @patch("active_security_scanner.subprocess.run", side_effect=FileNotFoundError)
    def test_handles_git_not_installed(self, mock_run: MagicMock, tmp_path: Path):
        """Should handle git not being installed."""
        (tmp_path / ".git").mkdir()
        findings = credential_history_scan(tmp_path)
        assert isinstance(findings, list)

    def test_accepts_custom_patterns(self, tmp_path: Path):
        """Should accept custom patterns parameter."""
        import re
        custom_patterns = [(re.compile(r"CUSTOM_SECRET_\w+"), "Custom secret")]
        (tmp_path / ".git").mkdir()

        fake_output = "commit abc\ndiff --git a/f b/f\n+CUSTOM_SECRET_XYZ\n"
        with patch("active_security_scanner.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=fake_output)
            findings = credential_history_scan(tmp_path, patterns=custom_patterns)
            assert len(findings) >= 1

    def test_max_commits_parameter(self, tmp_path: Path):
        """Should pass max_commits to git command."""
        (tmp_path / ".git").mkdir()
        with patch("active_security_scanner.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="")
            credential_history_scan(tmp_path, max_commits=50)
            call_args = mock_run.call_args[0][0]
            assert "--max-count=50" in call_args


# ---------------------------------------------------------------------------
# TestOwaspPatternScan
# ---------------------------------------------------------------------------


class TestOwaspPatternScan:
    """Tests for owasp_pattern_scan() function."""

    def test_detects_shell_true(self, tmp_path: Path):
        """Should detect subprocess.run(..., shell=True)."""
        f = tmp_path / "app.py"
        f.write_text('import subprocess\nsubprocess.run("ls", shell=True)\n')
        findings = owasp_pattern_scan([f])
        assert any("shell" in finding.category.lower() or "injection" in finding.category.lower() for finding in findings)

    def test_detects_eval(self, tmp_path: Path):
        """Should detect eval() usage."""
        f = tmp_path / "app.py"
        f.write_text('result = eval(user_input)\n')
        findings = owasp_pattern_scan([f])
        assert any("eval" in finding.category.lower() for finding in findings)

    def test_detects_exec(self, tmp_path: Path):
        """Should detect exec() usage."""
        f = tmp_path / "app.py"
        f.write_text('exec(code_string)\n')
        findings = owasp_pattern_scan([f])
        assert any("exec" in finding.category.lower() for finding in findings)

    def test_detects_debug_true(self, tmp_path: Path):
        """Should detect debug=True."""
        f = tmp_path / "app.py"
        f.write_text('app = Flask(__name__)\napp.run(debug=True)\n')
        findings = owasp_pattern_scan([f])
        assert any("debug" in finding.category.lower() for finding in findings)

    def test_skips_comments(self, tmp_path: Path):
        """Should not flag patterns inside comments."""
        f = tmp_path / "app.py"
        f.write_text('# eval(user_input)  # This is just a comment\nprint("safe")\n')
        findings = owasp_pattern_scan([f])
        eval_findings = [f for f in findings if "eval" in f.category.lower()]
        assert len(eval_findings) == 0

    def test_skips_docstrings(self, tmp_path: Path):
        """Should not flag patterns inside docstrings."""
        f = tmp_path / "app.py"
        f.write_text('"""\neval(user_input) is dangerous\n"""\nprint("safe")\n')
        findings = owasp_pattern_scan([f])
        eval_findings = [f for f in findings if "eval" in f.category.lower()]
        assert len(eval_findings) == 0

    def test_skips_test_files(self, tmp_path: Path):
        """Should skip test files."""
        f = tmp_path / "test_app.py"
        f.write_text('result = eval("1+1")\n')
        findings = owasp_pattern_scan([f])
        assert len(findings) == 0

    def test_skips_non_python_files(self, tmp_path: Path):
        """Should skip non-Python files."""
        f = tmp_path / "app.js"
        f.write_text('eval(userInput);\n')
        findings = owasp_pattern_scan([f])
        assert len(findings) == 0

    def test_remediation_included(self, tmp_path: Path):
        """Every finding should have non-empty remediation text."""
        f = tmp_path / "app.py"
        f.write_text('result = eval(user_input)\n')
        findings = owasp_pattern_scan([f])
        for finding in findings:
            assert finding.remediation, "Finding must have remediation text"
            assert len(finding.remediation) > 10, "Remediation should be specific, not generic"


# ---------------------------------------------------------------------------
# TestFullScan
# ---------------------------------------------------------------------------


class TestFullScan:
    """Tests for full_scan() orchestrator."""

    def test_aggregates_findings(self, tmp_path: Path):
        """Should aggregate findings from all scans."""
        (tmp_path / ".git").mkdir()
        req = tmp_path / "requirements.txt"
        req.write_text("django==3.2.0\n")
        app = tmp_path / "app.py"
        app.write_text('result = eval(user_input)\n')

        with patch("active_security_scanner.subprocess.run") as mock_run:
            # Mock git log (no secrets)
            mock_run.return_value = MagicMock(stdout="")
            report = full_scan(tmp_path, changed_files=[app])

        assert isinstance(report, ActiveScanReport)
        assert len(report.findings) >= 1
        assert len(report.scans_completed) >= 1

    def test_severity_ordering(self, tmp_path: Path):
        """Findings should be sorted by severity (CRITICAL first)."""
        (tmp_path / ".git").mkdir()
        req = tmp_path / "requirements.txt"
        req.write_text("django==3.2.0\n")

        with patch("active_security_scanner.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="")
            report = full_scan(tmp_path)

        if len(report.findings) >= 2:
            for i in range(len(report.findings) - 1):
                assert report.findings[i].severity <= report.findings[i + 1].severity

    def test_scan_duration_tracked(self, tmp_path: Path):
        """Should track scan duration."""
        with patch("active_security_scanner.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="")
            report = full_scan(tmp_path)
        assert report.scan_duration >= 0

    def test_returns_report_type(self, tmp_path: Path):
        """full_scan must return ActiveScanReport."""
        with patch("active_security_scanner.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="")
            report = full_scan(tmp_path)
        assert isinstance(report, ActiveScanReport)

    def test_accepts_str_project_root(self, tmp_path: Path):
        """full_scan must not crash when project_root is a str (Issue #1463).

        Regression: security-auditor callers on some platforms pass a plain
        str path. Previously this crashed on ``project_root / ".git"`` with
        ``unsupported operand type(s) for /: 'str' and 'str'`` and on
        ``project_root.rglob("*.py")`` with ``'str' object has no attribute
        'rglob'``. The public entrypoints must coerce to Path defensively.
        """
        (tmp_path / ".git").mkdir()
        with patch("active_security_scanner.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="")
            # Pass a str, not a Path — must not raise
            report = full_scan(str(tmp_path))
        assert isinstance(report, ActiveScanReport)
        # And it must have actually attempted the scans (not silently no-op)
        assert len(report.scans_completed) >= 1

    def test_dependency_audit_accepts_str(self, tmp_path: Path):
        """dependency_audit must accept str project_root (Issue #1463)."""
        (tmp_path / "requirements.txt").write_text("django==3.2.0\n")
        findings = dependency_audit(str(tmp_path))
        assert isinstance(findings, list)

    def test_credential_history_scan_accepts_str(self, tmp_path: Path):
        """credential_history_scan must accept str project_root (Issue #1463)."""
        findings = credential_history_scan(str(tmp_path))
        assert isinstance(findings, list)


# ---------------------------------------------------------------------------
# TestFormatReport
# ---------------------------------------------------------------------------


class TestFormatReport:
    """Tests for format_report() and ActiveScanReport.format_markdown()."""

    def test_markdown_output(self):
        """Should produce valid markdown output."""
        report = ActiveScanReport(
            findings=[
                Finding(
                    severity=Severity.HIGH,
                    category="A06: Vulnerable Components",
                    file_path="requirements.txt",
                    line_number=0,
                    description="django==3.2.0 is vulnerable",
                    remediation="Upgrade Django to >= 3.2.25",
                ),
            ],
            scan_duration=1.5,
            scans_completed=["dependency_audit"],
        )
        md = format_report(report)
        assert "# Active Security Scan Report" in md
        assert "HIGH" in md
        assert "django" in md

    def test_remediation_in_report(self):
        """Remediation actions should appear in the report."""
        report = ActiveScanReport(
            findings=[
                Finding(
                    severity=Severity.MEDIUM,
                    category="A03: Injection",
                    file_path="app.py",
                    line_number=10,
                    description="eval() detected",
                    remediation="Use ast.literal_eval() instead",
                ),
            ],
            scan_duration=0.5,
            scans_completed=["owasp_pattern_scan"],
        )
        md = report.format_markdown()
        assert "ast.literal_eval()" in md
        assert "Remediation" in md

    def test_empty_report(self):
        """Empty report should not crash."""
        report = ActiveScanReport(
            findings=[],
            scan_duration=0.1,
            scans_completed=["dependency_audit"],
        )
        md = format_report(report)
        assert "No security findings detected" in md

    def test_severity_summary(self):
        """Report should include severity summary counts."""
        report = ActiveScanReport(
            findings=[
                Finding(Severity.CRITICAL, "cat1", "f1", 1, "desc1", "rem1"),
                Finding(Severity.HIGH, "cat2", "f2", 2, "desc2", "rem2"),
                Finding(Severity.HIGH, "cat3", "f3", 3, "desc3", "rem3"),
            ],
            scan_duration=0.5,
            scans_completed=["full"],
        )
        md = format_report(report)
        assert "CRITICAL" in md
        assert "HIGH" in md
