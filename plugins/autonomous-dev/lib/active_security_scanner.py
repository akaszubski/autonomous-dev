"""
Active security scanner — dependency audit, credential detection, OWASP patterns.

Provides three scanning modes:
1. dependency_audit: Parse requirements.txt/pyproject.toml, check for known vulnerabilities
2. credential_history_scan: Scan git history for leaked secrets
3. owasp_pattern_scan: Detect dangerous code patterns (OWASP Top 10)

Plus an orchestrator (full_scan) and a report formatter.

Issue #710: Active security scanning.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional

# Import shared secret patterns (single source of truth per AC7)
_lib_dir = Path(__file__).resolve().parent
if str(_lib_dir) not in sys.path:
    sys.path.insert(0, str(_lib_dir))

from secret_patterns import (
    COMPILED_OWASP_PATTERNS,
    COMPILED_SECRET_PATTERNS,
    DEPENDENCY_ADVISORIES,
    OWASP_CODE_PATTERNS,
    SECRET_PATTERNS,
)

logger = logging.getLogger(__name__)

# OWASP_CODE_PATTERNS (imported from secret_patterns) covers:
#   - shell=True command injection (subprocess with shell=True)
#   - eval() / exec() code injection
#   - SQL injection via string formatting (SELECT, INSERT, format)
#   - debug=True security misconfiguration
#   - SSRF via dynamic URL construction


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class Severity(Enum):
    """Severity levels for security findings, ordered from most to least critical."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        order = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]
        return order.index(self) < order.index(other)


@dataclass
class Finding:
    """A single security finding with actionable remediation.

    Args:
        severity: Risk level (CRITICAL, HIGH, MEDIUM, LOW).
        category: Category of the finding (e.g., 'A03: Injection').
        file_path: Path to the affected file (or commit SHA for git findings).
        line_number: Line number in the affected file (0 if not applicable).
        description: Human-readable description of the finding.
        remediation: Specific actionable remediation text.
    """

    severity: Severity
    category: str
    file_path: str
    line_number: int
    description: str
    remediation: str


@dataclass
class ActiveScanReport:
    """Aggregated results from all active security scans.

    Args:
        findings: All findings across all scans, sorted by severity.
        scan_duration: Total wall-clock seconds for the scan.
        scans_completed: Names of scans that ran successfully.
    """

    findings: List[Finding] = field(default_factory=list)
    scan_duration: float = 0.0
    scans_completed: List[str] = field(default_factory=list)

    def format_markdown(self) -> str:
        """Format the report as Markdown with findings table and remediation actions."""
        return format_report(self)


# ---------------------------------------------------------------------------
# Dependency audit
# ---------------------------------------------------------------------------


def _parse_version(version_str: str) -> tuple:
    """Parse a version string like '3.2.1' into a comparable tuple of ints."""
    parts = []
    for p in version_str.strip().split("."):
        try:
            parts.append(int(p))
        except ValueError:
            # Handle pre-release markers like '1.0.0a1' — strip non-numeric suffix
            numeric = ""
            for ch in p:
                if ch.isdigit():
                    numeric += ch
                else:
                    break
            parts.append(int(numeric) if numeric else 0)
    return tuple(parts)


def _version_in_range(installed: str, spec: str) -> bool:
    """Check if installed version matches a simple version spec like '<3.2.25'.

    Supports: <X.Y.Z, <=X.Y.Z, >=X.Y.Z, >X.Y.Z, ==X.Y.Z
    """
    spec = spec.strip()
    if spec.startswith("<="):
        return _parse_version(installed) <= _parse_version(spec[2:])
    elif spec.startswith("<"):
        return _parse_version(installed) < _parse_version(spec[1:])
    elif spec.startswith(">="):
        return _parse_version(installed) >= _parse_version(spec[2:])
    elif spec.startswith(">"):
        return _parse_version(installed) > _parse_version(spec[1:])
    elif spec.startswith("=="):
        return _parse_version(installed) == _parse_version(spec[2:])
    return False


def _parse_requirements_txt(path: Path) -> dict[str, str]:
    """Parse requirements.txt into {package_name: version_string}.

    Handles == pins, >= constraints, and skips comments/blank lines.
    """
    packages: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            # Handle ==, >=, <=, ~= operators
            for op in ["==", ">=", "<=", "~=", "!="]:
                if op in line:
                    name, version = line.split(op, 1)
                    name = name.strip().lower()
                    version = version.strip().split(";")[0].strip()  # strip env markers
                    packages[name] = version
                    break
    except Exception as exc:
        logger.info("Could not parse %s: %s", path, exc)
    return packages


def _parse_pyproject_toml(path: Path) -> dict[str, str]:
    """Parse pyproject.toml dependencies section for package versions.

    Simple parser — handles [project] dependencies list format.
    """
    packages: dict[str, str] = {}
    try:
        content = path.read_text(encoding="utf-8")
        # Find dependencies section
        in_deps = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped == "dependencies = [":
                in_deps = True
                continue
            if in_deps:
                if stripped == "]":
                    break
                # Parse lines like '"requests>=2.28.0",'
                dep_match = re.match(r'["\']([a-zA-Z0-9_-]+)([><=~!]+)([^"\';\s]+)', stripped)
                if dep_match:
                    name = dep_match.group(1).lower()
                    version = dep_match.group(3).strip(",").strip("\"'")
                    packages[name] = version
    except Exception as exc:
        logger.info("Could not parse %s: %s", path, exc)
    return packages


def _run_pip_audit(project_root: Path) -> List[Finding]:
    """Run pip-audit if available, return findings from its JSON output."""
    findings: List[Finding] = []
    try:
        result = subprocess.run(
            ["pip-audit", "--format", "json", "--desc"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(project_root),
        )
        if result.stdout:
            data = json.loads(result.stdout)
            deps = data if isinstance(data, list) else data.get("dependencies", [])
            for dep in deps:
                vulns = dep.get("vulns", [])
                for vuln in vulns:
                    findings.append(
                        Finding(
                            severity=Severity.HIGH,
                            category="A06: Vulnerable Components",
                            file_path="pip-audit",
                            line_number=0,
                            description=(
                                f"{dep.get('name', '?')} {dep.get('version', '?')}: "
                                f"{vuln.get('id', 'unknown')} — {vuln.get('description', 'N/A')}"
                            ),
                            remediation=(
                                f"Upgrade {dep.get('name', '?')} to "
                                f"{vuln.get('fix_versions', ['latest'])}. "
                                f"See: https://pypi.org/project/{dep.get('name', '')}"
                            ),
                        )
                    )
    except FileNotFoundError:
        logger.info("pip-audit not installed — skipping automated dependency audit")
    except subprocess.TimeoutExpired:
        logger.warning("pip-audit timed out")
    except (json.JSONDecodeError, subprocess.SubprocessError, OSError) as exc:
        logger.info("pip-audit failed: %s", exc)
    return findings


def dependency_audit(project_root: Path) -> List[Finding]:
    """Audit project dependencies for known vulnerabilities.

    Parses requirements.txt and/or pyproject.toml, checks versions against
    DEPENDENCY_ADVISORIES, and optionally runs pip-audit if available.

    Args:
        project_root: Path to the project root directory. Accepts str for
            defensive interop (Issue #1463) — coerced to Path internally.

    Returns:
        List of Finding objects for vulnerable dependencies.
    """
    project_root = Path(project_root)
    findings: List[Finding] = []

    # Collect installed package versions from requirements files
    packages: dict[str, str] = {}

    req_path = project_root / "requirements.txt"
    if req_path.exists():
        packages.update(_parse_requirements_txt(req_path))

    pyproject_path = project_root / "pyproject.toml"
    if pyproject_path.exists():
        packages.update(_parse_pyproject_toml(pyproject_path))

    # Check against known advisories
    for pkg_name, version in packages.items():
        advisories = DEPENDENCY_ADVISORIES.get(pkg_name, [])
        for advisory in advisories:
            affected = advisory.get("affected_versions", "")
            if _version_in_range(version, affected):
                sev_str = advisory.get("severity", "MEDIUM")
                try:
                    severity = Severity[sev_str]
                except KeyError:
                    severity = Severity.MEDIUM

                findings.append(
                    Finding(
                        severity=severity,
                        category="A06: Vulnerable Components",
                        file_path=str(req_path if req_path.exists() else pyproject_path),
                        line_number=0,
                        description=(
                            f"{pkg_name}=={version} matches {advisory.get('cve', 'N/A')}: "
                            f"{advisory.get('description', 'Known vulnerability')}"
                        ),
                        remediation=advisory.get(
                            "remediation",
                            f"Upgrade {pkg_name} to a patched version.",
                        ),
                    )
                )

    # Try pip-audit for comprehensive coverage
    findings.extend(_run_pip_audit(project_root))

    return findings


# ---------------------------------------------------------------------------
# Credential history scan
# ---------------------------------------------------------------------------


def credential_history_scan(
    project_root: Path,
    patterns: Optional[List] = None,
    *,
    max_commits: int = 1000,
) -> List[Finding]:
    """Scan git history for leaked credentials.

    Runs ``git log --all -p`` and checks each diff line against SECRET_PATTERNS.

    Args:
        project_root: Path to the git repository root. Accepts str for
            defensive interop (Issue #1463) — coerced to Path internally.
        patterns: Optional list of (regex, description) tuples. Defaults to SECRET_PATTERNS.
        max_commits: Maximum number of commits to scan (default 1000).

    Returns:
        List of Finding objects for credentials found in git history.
    """
    project_root = Path(project_root)
    findings: List[Finding] = []
    scan_patterns = patterns if patterns is not None else COMPILED_SECRET_PATTERNS

    # Verify this is a git repo
    git_dir = project_root / ".git"
    if not git_dir.exists() and not (project_root / ".git").is_file():
        logger.info("Not a git repository: %s — skipping credential history scan", project_root)
        return findings

    try:
        result = subprocess.run(
            [
                "git", "log", "--all", "-p",
                f"--max-count={max_commits}",
                "--diff-filter=A",  # Only added lines
                "--no-color",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(project_root),
        )

        current_commit = ""
        current_file = ""

        for line in result.stdout.splitlines():
            if line.startswith("commit "):
                current_commit = line.split()[1][:12] if len(line.split()) > 1 else ""
            elif line.startswith("diff --git"):
                parts = line.split(" b/")
                current_file = parts[-1] if len(parts) > 1 else ""
            elif line.startswith("+") and not line.startswith("+++"):
                # Check added lines against secret patterns
                for compiled_re, description in scan_patterns:
                    if compiled_re.search(line):
                        findings.append(
                            Finding(
                                severity=Severity.CRITICAL,
                                category="A02: Cryptographic Failures (leaked credential)",
                                file_path=f"{current_file} (commit {current_commit})",
                                line_number=0,
                                description=(
                                    f"{description} detected in git history: "
                                    f"commit {current_commit}, file {current_file}"
                                ),
                                remediation=(
                                    "Rotate the exposed credential immediately. "
                                    "Use git-filter-repo or BFG to remove from history. "
                                    "Store secrets in .env (gitignored) or a secret manager."
                                ),
                            )
                        )
                        break  # One finding per line is enough

    except FileNotFoundError:
        logger.info("git not found — skipping credential history scan")
    except subprocess.TimeoutExpired:
        logger.warning("git log timed out after 300s — partial scan only")
    except (subprocess.SubprocessError, OSError) as exc:
        logger.info("git history scan failed: %s", exc)

    return findings


# ---------------------------------------------------------------------------
# OWASP pattern scan
# ---------------------------------------------------------------------------

# Re-export for test visibility
from secret_patterns import OWASP_CODE_PATTERNS as OWASP_CODE_PATTERNS  # noqa: F811


def _is_in_comment_or_docstring(line: str) -> bool:
    """Check if a line is a Python comment or inside a docstring marker."""
    stripped = line.lstrip()
    return stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''")


def _is_test_file(path: Path) -> bool:
    """Check if a file is a test file (by naming convention)."""
    name = path.name
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or "conftest" in name
        or "/tests/" in str(path)
        or "\\tests\\" in str(path)
    )


def owasp_pattern_scan(file_paths: List[Path]) -> List[Finding]:
    """Scan Python files for OWASP Top 10 dangerous code patterns.

    Checks files against OWASP_CODE_PATTERNS. Skips comments, docstrings,
    and test files to reduce false positives.

    Args:
        file_paths: List of file paths to scan.

    Returns:
        List of Finding objects for detected patterns.
    """
    findings: List[Finding] = []

    for file_path in file_paths:
        # Skip non-Python files
        if file_path.suffix != ".py":
            continue

        # Skip test files
        if _is_test_file(file_path):
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, IOError) as exc:
            logger.info("Could not read %s: %s", file_path, exc)
            continue

        in_docstring = False
        docstring_char = None

        for line_num, line in enumerate(content.splitlines(), 1):
            stripped = line.lstrip()

            # Track docstring state (simple heuristic)
            if not in_docstring:
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    docstring_char = stripped[:3]
                    # Single-line docstring
                    if stripped.count(docstring_char) >= 2:
                        continue
                    in_docstring = True
                    continue
            else:
                if docstring_char and docstring_char in stripped:
                    in_docstring = False
                continue

            # Skip comments
            if stripped.startswith("#"):
                continue

            # Check against OWASP patterns
            for compiled_re, category, remediation in COMPILED_OWASP_PATTERNS:
                if compiled_re.search(line):
                    findings.append(
                        Finding(
                            severity=Severity.MEDIUM,
                            category=category,
                            file_path=str(file_path),
                            line_number=line_num,
                            description=f"Detected: {category} at {file_path}:{line_num}",
                            remediation=remediation,
                        )
                    )

    return findings


# ---------------------------------------------------------------------------
# Full scan orchestrator
# ---------------------------------------------------------------------------


def full_scan(
    project_root: Path,
    changed_files: Optional[List[Path]] = None,
) -> ActiveScanReport:
    """Orchestrate all active security scans and aggregate results.

    Runs dependency_audit, credential_history_scan, and owasp_pattern_scan,
    then returns a unified report sorted by severity.

    Args:
        project_root: Path to the project root directory. Accepts str for
            defensive interop (Issue #1463) — coerced to Path internally so
            downstream ``/`` and ``.rglob`` operations don't crash.
        changed_files: Optional list of specific files to scan for OWASP patterns.
            If None, scans all .py files under project_root.

    Returns:
        ActiveScanReport with aggregated findings and scan metadata.
    """
    project_root = Path(project_root)
    start_time = time.monotonic()
    all_findings: List[Finding] = []
    scans_completed: List[str] = []

    # 1. Dependency audit
    try:
        dep_findings = dependency_audit(project_root)
        all_findings.extend(dep_findings)
        scans_completed.append("dependency_audit")
    except Exception as exc:
        logger.warning("dependency_audit failed: %s", exc)

    # 2. Credential history scan
    try:
        cred_findings = credential_history_scan(project_root)
        all_findings.extend(cred_findings)
        scans_completed.append("credential_history_scan")
    except Exception as exc:
        logger.warning("credential_history_scan failed: %s", exc)

    # 3. OWASP pattern scan
    try:
        if changed_files is not None:
            scan_files = changed_files
        else:
            scan_files = list(project_root.rglob("*.py"))
        owasp_findings = owasp_pattern_scan(scan_files)
        all_findings.extend(owasp_findings)
        scans_completed.append("owasp_pattern_scan")
    except Exception as exc:
        logger.warning("owasp_pattern_scan failed: %s", exc)

    # Sort by severity (CRITICAL first)
    all_findings.sort(key=lambda f: f.severity)

    elapsed = time.monotonic() - start_time

    return ActiveScanReport(
        findings=all_findings,
        scan_duration=elapsed,
        scans_completed=scans_completed,
    )


# ---------------------------------------------------------------------------
# Report formatter
# ---------------------------------------------------------------------------


def format_report(report: ActiveScanReport) -> str:
    """Format an ActiveScanReport as Markdown with findings table and remediation.

    Args:
        report: The scan report to format.

    Returns:
        Markdown-formatted string with severity summary, findings table,
        and remediation actions.
    """
    lines: List[str] = []
    lines.append("# Active Security Scan Report")
    lines.append("")
    lines.append(f"**Scans completed**: {', '.join(report.scans_completed) or 'none'}")
    lines.append(f"**Duration**: {report.scan_duration:.2f}s")
    lines.append(f"**Total findings**: {len(report.findings)}")
    lines.append("")

    if not report.findings:
        lines.append("No security findings detected.")
        return "\n".join(lines)

    # Severity summary
    severity_counts: dict[str, int] = {}
    for finding in report.findings:
        key = finding.severity.value
        severity_counts[key] = severity_counts.get(key, 0) + 1

    lines.append("## Severity Summary")
    lines.append("")
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        count = severity_counts.get(sev, 0)
        if count > 0:
            lines.append(f"- **{sev}**: {count}")
    lines.append("")

    # Findings table
    lines.append("## Findings")
    lines.append("")
    lines.append("| # | Severity | Category | File | Line | Description |")
    lines.append("|---|----------|----------|------|------|-------------|")
    for idx, finding in enumerate(report.findings, 1):
        lines.append(
            f"| {idx} | {finding.severity.value} | {finding.category} | "
            f"{finding.file_path} | {finding.line_number} | {finding.description} |"
        )
    lines.append("")

    # Remediation actions
    lines.append("## Remediation Actions")
    lines.append("")
    seen_remediations: set[str] = set()
    for finding in report.findings:
        if finding.remediation not in seen_remediations:
            seen_remediations.add(finding.remediation)
            lines.append(f"- **{finding.category}**: {finding.remediation}")
    lines.append("")

    return "\n".join(lines)
