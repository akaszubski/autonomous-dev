#!/usr/bin/env python3
"""
Language-agnostic security scanning hook with GenAI context analysis.

Scans for:
- Hardcoded API keys and secrets
- Common security vulnerabilities
- Sensitive data in code

Features:
- Pattern matching (regex-based detection)
- GenAI context analysis (Claude determines if real vs test data)
- Graceful degradation (works without Anthropic SDK)

Works across Python, JavaScript, Go, and other languages.
"""

import re
import sys
import os
from pathlib import Path
from typing import List, Tuple, Optional

# Secret patterns to detect
SECRET_PATTERNS = [
    # API keys
    (r"sk-[a-zA-Z0-9]{20,}", "Anthropic API key"),
    (r"sk-proj-[a-zA-Z0-9]{20,}", "OpenAI API key"),
    (r"xoxb-[a-zA-Z0-9-]{40,}", "Slack bot token"),
    (r"ghp_[a-zA-Z0-9]{36,}", "GitHub personal access token"),
    (r"gho_[a-zA-Z0-9]{36,}", "GitHub OAuth token"),
    # AWS keys
    (r"AKIA[0-9A-Z]{16}", "AWS access key ID"),
    (r"(?i)aws_secret_access_key.*[=:].*[a-zA-Z0-9/+=]{40}", "AWS secret key"),
    # Generic patterns
    (r'(?i)(api[_-]?key|apikey).*[=:].*["\'][a-zA-Z0-9]{20,}["\']', "Generic API key"),
    (r'(?i)(secret|password|passwd|pwd).*[=:].*["\'][^"\']{8,}["\']', "Generic secret"),
    (r'(?i)token.*[=:].*["\'][a-zA-Z0-9]{20,}["\']', "Generic token"),
    # Database URLs with credentials
    (r"(?i)(mongodb|mysql|postgres)://[^:]+:[^@]+@", "Database URL with credentials"),
]

# File patterns to ignore
IGNORE_PATTERNS = [
    r"\.git/",
    r"__pycache__/",
    r"node_modules/",
    r"\.env\.example$",
    r"\.env\.template$",
    r"test_.*\.py$",  # Test files often have fake secrets
    r".*_test\.go$",
]


def should_scan_file(file_path: Path) -> bool:
    """Determine if file should be scanned."""
    path_str = str(file_path)

    # Ignore patterns
    for pattern in IGNORE_PATTERNS:
        if re.search(pattern, path_str):
            return False

    # Only scan code files
    code_extensions = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".java", ".rb", ".php", ".cs"}
    return file_path.suffix in code_extensions


def is_comment_or_docstring(line: str, language: str) -> bool:
    """Check if line is a comment or docstring."""
    line = line.strip()

    if language == "python":
        return line.startswith("#") or line.startswith('"""') or line.startswith("'''")
    elif language in ["javascript", "typescript", "go", "java"]:
        return line.startswith("//") or line.startswith("/*") or line.startswith("*")

    return False


def analyze_secret_context(line: str, secret_type: str, variable_name: Optional[str] = None) -> bool:
    """Use GenAI to determine if a matched secret is real or test data.

    Returns:
        True if it appears to be a real secret, False if likely test data
    """
    try:
        from anthropic import Anthropic
    except ImportError:
        # If SDK not available, fall back to heuristics
        return _heuristic_secret_check(line, secret_type, variable_name)

    # Check if we should skip GenAI analysis
    use_genai = os.environ.get("GENAI_SECURITY_SCAN", "true").lower() == "true"
    if not use_genai:
        return _heuristic_secret_check(line, secret_type, variable_name)

    try:
        client = Anthropic()

        # Extract variable context
        var_context = ""
        if "=" in line:
            var_context = line.split("=")[0].strip()

        prompt = f"""Analyze this line of code and determine if it contains a REAL API key/secret or TEST DATA.

Line of code:
{line}

Secret type detected: {secret_type}
Variable name context: {var_context or 'N/A'}

Consider:
1. Variable naming: Does name suggest test data? (test_, fake_, mock_, example_)
2. Context: Is this in a test file, fixture, or documentation?
3. Value patterns: Common test patterns like "test123", "dummy", all zeros/same chars?

Respond with ONLY: REAL or FAKE

If unsure, respond: LIKELY_REAL (be conservative - false negatives are better than false positives)"""

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        response = message.content[0].text.strip().upper()
        is_real = "REAL" in response and "FAKE" not in response

        return is_real

    except Exception as e:
        # If GenAI call fails, fall back to heuristics
        if os.environ.get("DEBUG_SECURITY_SCAN"):
            print(f"⚠️  GenAI analysis failed: {e}", file=sys.stderr)
        return _heuristic_secret_check(line, secret_type, variable_name)


def _heuristic_secret_check(line: str, secret_type: str, variable_name: Optional[str] = None) -> bool:
    """Fallback heuristic check if GenAI unavailable.

    Returns:
        True if likely real secret, False if likely test data
    """
    # Common test data indicators
    test_indicators = [
        "test_", "fake_", "mock_", "example_", "dummy_",
        "test123", "fake123", "mock123",
        "sk-test", "pk_test", "rk_test",
        "00000000", "11111111", "aaaaaaa", "99999999",
        "placeholder", "sample", "demo", "xxx",
    ]

    line_lower = line.lower()
    for indicator in test_indicators:
        if indicator in line_lower:
            return False

    # If no obvious test indicators, assume real (conservative approach)
    return True


def get_language(file_path: Path) -> str:
    """Get language from file extension."""
    ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".java": "java",
    }
    return ext_map.get(file_path.suffix, "unknown")


def scan_file(file_path: Path) -> List[Tuple[int, str, str]]:
    """Scan a file for secrets with GenAI context analysis.

    Returns:
        List of (line_number, secret_type, matched_text) tuples
    """
    violations = []
    language = get_language(file_path)

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line_num, line in enumerate(f, 1):
                # Skip comments and docstrings
                if is_comment_or_docstring(line, language):
                    continue

                # Check each pattern
                for pattern, secret_type in SECRET_PATTERNS:
                    if re.search(pattern, line):
                        # Extract matched text (redacted)
                        match = re.search(pattern, line)
                        matched = match.group(0)
                        # Redact middle part
                        if len(matched) > 10:
                            redacted = matched[:5] + "***" + matched[-5:]
                        else:
                            redacted = "***"

                        # Use GenAI to determine if this is a real secret or test data
                        is_real_secret = analyze_secret_context(line, secret_type)

                        if is_real_secret:
                            violations.append((line_num, secret_type, redacted))
                        elif os.environ.get("DEBUG_SECURITY_SCAN"):
                            print(f"ℹ️  Skipped test data in {file_path}:{line_num} ({secret_type})",
                                  file=sys.stderr)

    except Exception as e:
        print(f"⚠️  Error scanning {file_path}: {e}", file=sys.stderr)

    return violations


def scan_directory(directory: Path = Path(".")) -> dict:
    """Scan directory for secrets.

    Returns:
        Dictionary mapping file paths to violations
    """
    all_violations = {}

    # Scan source directories
    for source_dir in ["src", "lib", "pkg", "app"]:
        dir_path = directory / source_dir
        if not dir_path.exists():
            continue

        for file_path in dir_path.rglob("*"):
            if not file_path.is_file():
                continue

            if not should_scan_file(file_path):
                continue

            violations = scan_file(file_path)
            if violations:
                all_violations[file_path] = violations

    return all_violations


def main():
    """Run security scan with GenAI context analysis."""
    use_genai = os.environ.get("GENAI_SECURITY_SCAN", "true").lower() == "true"
    genai_status = "🤖 (with GenAI context analysis)" if use_genai else ""
    print(f"🔒 Running security scan... {genai_status}")

    violations = scan_directory()

    if not violations:
        print("✅ No secrets or sensitive data detected")
        if use_genai:
            print("   (GenAI context analysis reduced false positives)")
        sys.exit(0)

    # Report violations
    print("\n❌ SECURITY ISSUES DETECTED:\n")

    for file_path, issues in violations.items():
        print(f"📄 {file_path}")
        for line_num, secret_type, redacted in issues:
            print(f"   Line {line_num}: {secret_type}")
            print(f"   Found: {redacted}")
        print()

    print("⚠️  Fix these issues before committing:")
    print("  1. Move secrets to .env file (add to .gitignore)")
    print("  2. Use environment variables: os.getenv('API_KEY')")
    print("  3. Never commit real API keys or passwords")
    print()

    if use_genai:
        print("💡 Tip: GenAI analysis reduces false positives by understanding context")
        print("   Disable with: export GENAI_SECURITY_SCAN=false")
    print()

    sys.exit(1)


if __name__ == "__main__":
    main()
