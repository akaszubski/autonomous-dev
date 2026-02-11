#!/usr/bin/env python3
"""
Session Telemetry Reader Library - Read and classify pipeline logs for postmortem analysis.

Reads error registry and violation logs to identify plugin bugs vs user code issues.
Provides fingerprinting for deduplication and secret redaction for safe GitHub issue filing.

Key Features:
1. Read from .claude/logs/errors/YYYY-MM-DD.jsonl (error registry)
2. Read from .claude/logs/workflow_violations.log (violation log)
3. Classify findings: PLUGIN_BUG, USER_CODE_BUG, UNKNOWN
4. Create fingerprints for deduplication
5. Redact secrets before filing issues
6. Enforce resource limits (max 500 errors per session)

Security:
- CWE-532: Secret redaction for API keys, tokens, passwords
- CWE-400: Resource limits (max errors per session)
- CWE-22: Path validation via path_utils.get_project_root()

Date: 2026-02-11
Issue: #328 (Postmortem analyst for plugin bug detection)
Agent: implementer

See error-handling-patterns skill for exception hierarchy and error handling best practices.

Design Patterns:
    See library-design-patterns skill for standardized design patterns.
"""

import hashlib
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

# Set up logging
logger = logging.getLogger(__name__)

# Import path utilities with fallback pattern
try:
    from .path_utils import get_project_root
except ImportError:
    lib_dir = Path(__file__).parent.resolve()
    sys.path.insert(0, str(lib_dir))
    from path_utils import get_project_root


# =============================================================================
# Constants
# =============================================================================

# Maximum errors to process per session (CWE-400 resource limit)
MAX_ERRORS_PER_SESSION = 500

# Maximum error message length (prevent memory exhaustion)
MAX_ERROR_MESSAGE_LENGTH = 1000

# Secret patterns for redaction (CWE-532)
# Format: (pattern, replacement)
SECRET_PATTERNS = [
    (r"sk-[a-zA-Z0-9]{6,}", "[REDACTED_API_KEY]"),  # OpenAI API key
    (r"anthropic_[a-zA-Z0-9_-]{6,}", "[REDACTED_API_KEY]"),  # Anthropic API key
    (r"ghp_[a-zA-Z0-9]{6,}", "[REDACTED_GITHUB_TOKEN]"),  # GitHub PAT
    (r"gho_[a-zA-Z0-9]{6,}", "[REDACTED_TOKEN]"),  # GitHub OAuth token
    (r"ghr_[a-zA-Z0-9]{6,}", "[REDACTED_TOKEN]"),  # GitHub refresh token
    (r"Bearer\s+[a-zA-Z0-9_\-]+", "[REDACTED_TOKEN]"),  # Bearer token (any format)
    (r"api[_-]?key[\"']?\s*[=:]\s*[\"']?[a-zA-Z0-9_-]{6,}", "[REDACTED_API_KEY]"),  # Generic API key
    (r"password[\"']?\s*[=:]\s*[\"']?[^\s\"']+", "[REDACTED_PASSWORD]"),  # Password
    (r"secret[\"']?\s*[=:]\s*[\"']?[a-zA-Z0-9_-]{6,}", "[REDACTED_SECRET]"),  # Generic secret
    (r"token[\"']?\s*[=:]\s*[\"']?[a-zA-Z0-9_-]{6,}", "[REDACTED_TOKEN]"),  # Generic token
]


# =============================================================================
# Enums and Data Classes
# =============================================================================

class IssueSource(Enum):
    """Classification of finding source."""
    PLUGIN_BUG = "plugin_bug"
    USER_CODE_BUG = "user_code_bug"
    UNKNOWN = "unknown"


@dataclass
class Finding:
    """Represents a single error or violation finding."""
    source: str  # "error_registry" or "violation_log"
    error_type: str  # e.g., "hook_failure", "agent_crash", "test_failure"
    component: str  # e.g., "unified_pre_tool.py", "implementer", "tests/test_user.py"
    message: str  # Error or violation message
    timestamp: Optional[str] = None
    severity: Optional[str] = None
    classification: Optional[IssueSource] = None
    fingerprint: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionTelemetry:
    """Complete telemetry data for a session."""
    date: str
    errors: List[Finding]
    violations: List[Finding]
    plugin_bugs: List[Finding]
    user_issues: List[Finding]
    total_findings: int


class TelemetryError(Exception):
    """Exception raised for telemetry reading errors."""
    pass


# =============================================================================
# Session Telemetry Reader
# =============================================================================

class SessionTelemetryReader:
    """Read and classify session telemetry for postmortem analysis."""

    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize telemetry reader.

        Args:
            project_root: Project root directory (auto-detected if not provided)
        """
        if project_root is None:
            project_root = get_project_root()
        self.project_root = Path(project_root)
        self.logs_dir = self.project_root / ".claude" / "logs"

    def read_errors(self, date: Optional[str] = None) -> List[Finding]:
        """
        Read errors from error registry.

        Args:
            date: Date string (YYYY-MM-DD). If None, uses today.

        Returns:
            List of Finding objects from error registry
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        errors_dir = self.logs_dir / "errors"
        error_file = errors_dir / f"{date}.jsonl"

        if not error_file.exists():
            return []

        findings = []
        try:
            with error_file.open("r") as f:
                for i, line in enumerate(f):
                    # Enforce max limit
                    if i >= MAX_ERRORS_PER_SESSION:
                        logger.warning(f"Error limit exceeded ({MAX_ERRORS_PER_SESSION}), truncating")
                        break

                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)

                        # Skip entries missing required fields
                        if "error" not in data and "error_message" not in data:
                            continue

                        # Extract fields (handle both old and new formats)
                        error_message = data.get("error") or data.get("error_message", "")
                        tool_name = data.get("tool") or data.get("tool_name", "unknown")

                        finding = Finding(
                            source="error_registry",
                            error_type=data.get("classification", "unknown"),
                            component=tool_name,
                            message=error_message,
                            timestamp=data.get("timestamp"),
                            context=data.get("context", {})
                        )
                        findings.append(finding)

                    except json.JSONDecodeError:
                        # Skip malformed JSON lines
                        continue

        except (OSError, IOError, PermissionError):
            # Return empty list on file access errors
            return []

        return findings

    def read_violations(self) -> List[Finding]:
        """
        Read violations from workflow_violations.log.

        Returns:
            List of Finding objects from violation log
        """
        violation_file = self.logs_dir / "workflow_violations.log"

        if not violation_file.exists():
            return []

        findings = []
        try:
            with violation_file.open("r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)

                        # Skip entries missing required fields
                        if "type" not in data:
                            continue

                        finding = Finding(
                            source="violation_log",
                            error_type=data.get("type", "unknown"),
                            component=data.get("agent", "unknown"),
                            message=data.get("details", ""),
                            timestamp=data.get("timestamp"),
                            severity=data.get("severity")
                        )
                        findings.append(finding)

                    except json.JSONDecodeError:
                        # Skip malformed JSON lines
                        continue

        except (OSError, IOError, PermissionError):
            # Return empty list on file access errors
            return []

        return findings

    def classify_finding(self, finding: Finding) -> IssueSource:
        """
        Classify finding as plugin bug, user code bug, or unknown.

        Classification rules:
        - PLUGIN_BUG: hook failures, agent crashes, step skips, missing skills, tool validation errors
        - USER_CODE_BUG: test failures in user code, syntax errors in user code, git bypasses
        - UNKNOWN: everything else

        Args:
            finding: Finding to classify

        Returns:
            IssueSource classification
        """
        error_type = finding.error_type.lower()
        component = finding.component.lower()
        message = finding.message.lower()

        # Plugin bugs
        if error_type in ["hook_failure", "agent_crash", "step_skip", "skill_load_error", "tool_validation_error"]:
            return IssueSource.PLUGIN_BUG

        # Plugin component crashes
        if component in ["unified_pre_tool.py", "implementer", "researcher", "planner", "reviewer"]:
            if "error" in message or "exception" in message or "failed" in message:
                return IssueSource.PLUGIN_BUG

        # User code bugs
        if error_type in ["test_failure", "syntax_error"]:
            # Check if it's in user code (not plugin tests)
            if "tests/" in component or "src/" in component:
                if "plugins/autonomous-dev" not in component:
                    return IssueSource.USER_CODE_BUG

        # Git bypasses (user violations)
        if error_type == "direct_implementation" and "git" in message:
            return IssueSource.USER_CODE_BUG

        # Default
        return IssueSource.UNKNOWN

    def create_fingerprint(self, finding: Finding) -> str:
        """
        Create unique fingerprint for deduplication.

        Fingerprint = sha256(error_type:component:normalized_message)

        Args:
            finding: Finding to fingerprint

        Returns:
            SHA-256 fingerprint (64-character hex string)
        """
        # Normalize message: lowercase, remove line numbers, collapse whitespace
        normalized = finding.message.lower()
        normalized = re.sub(r"\d+", "N", normalized)  # Replace numbers with N
        normalized = re.sub(r"\s+", " ", normalized)  # Collapse whitespace
        normalized = normalized.strip()[:200]  # Cap length

        # Build fingerprint input
        fingerprint_input = f"{finding.error_type}:{finding.component}:{normalized}"

        # Hash
        hash_obj = hashlib.sha256(fingerprint_input.encode("utf-8"))
        return hash_obj.hexdigest()

    def redact_secrets(self, text: str) -> str:
        """
        Redact API keys, tokens, and secrets from text.

        Args:
            text: Text that may contain secrets

        Returns:
            Text with secrets redacted
        """
        redacted = text
        for pattern, replacement in SECRET_PATTERNS:
            redacted = re.sub(pattern, replacement, redacted, flags=re.IGNORECASE)
        return redacted

    def analyze_session(self, date: Optional[str] = None) -> SessionTelemetry:
        """
        Full analysis pipeline: read, classify, fingerprint, redact.

        Args:
            date: Date to analyze (default: today)

        Returns:
            SessionTelemetry with classified findings
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # Read all findings
        errors = self.read_errors(date)
        violations = self.read_violations()

        # Classify and fingerprint all findings
        all_findings = errors + violations
        plugin_bugs = []
        user_issues = []

        for finding in all_findings:
            # Classify
            finding.classification = self.classify_finding(finding)

            # Create fingerprint
            finding.fingerprint = self.create_fingerprint(finding)

            # Redact secrets
            finding.message = self.redact_secrets(finding.message)

            # Categorize
            if finding.classification == IssueSource.PLUGIN_BUG:
                plugin_bugs.append(finding)
            elif finding.classification == IssueSource.USER_CODE_BUG:
                user_issues.append(finding)

        return SessionTelemetry(
            date=date,
            errors=errors,
            violations=violations,
            plugin_bugs=plugin_bugs,
            user_issues=user_issues,
            total_findings=len(all_findings)
        )


# =============================================================================
# Convenience Functions
# =============================================================================

def analyze_session(date: Optional[str] = None, project_root: Optional[Path] = None) -> SessionTelemetry:
    """
    Convenience function to analyze a session.

    Args:
        date: Date to analyze (default: today)
        project_root: Project root (auto-detected if not provided)

    Returns:
        SessionTelemetry with analysis results
    """
    reader = SessionTelemetryReader(project_root)
    return reader.analyze_session(date)
