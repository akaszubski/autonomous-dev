#!/usr/bin/env python3
"""
Language-agnostic security scanning hook.

Scans for:
- Hardcoded API keys and secrets
- Common security vulnerabilities
- Sensitive data in code

Works across Python, JavaScript, Go, and other languages.
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple

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
    """Scan a file for secrets.

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

                        violations.append((line_num, secret_type, redacted))

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
    """Run security scan."""
    print("🔒 Running security scan...")

    violations = scan_directory()

    if not violations:
        print("✅ No secrets or sensitive data detected")
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

    sys.exit(1)


if __name__ == "__main__":
    main()
