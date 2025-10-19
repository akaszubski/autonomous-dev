#!/usr/bin/env python3
"""
Multi-language code formatting hook.

Automatically formats code based on detected project language.
Runs after file writes to maintain consistent code style.

Supported languages:
- Python: black + isort
- JavaScript/TypeScript: prettier
- Go: gofmt
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


def detect_language() -> str:
    """Detect project language from project files."""
    if (
        Path("pyproject.toml").exists()
        or Path("setup.py").exists()
        or Path("requirements.txt").exists()
    ):
        return "python"
    elif Path("package.json").exists():
        return "javascript"
    elif Path("go.mod").exists():
        return "go"
    else:
        return "unknown"


def format_python(files: List[Path]) -> Tuple[bool, str]:
    """Format Python files with black and isort."""
    try:
        # Format with black
        result = subprocess.run(
            ["black", "--quiet", *[str(f) for f in files]], capture_output=True, text=True
        )

        # Sort imports with isort
        subprocess.run(
            ["isort", "--quiet", *[str(f) for f in files]], capture_output=True, text=True
        )

        return True, "Formatted with black + isort"
    except FileNotFoundError:
        return False, "black or isort not installed. Run: pip install black isort"


def format_javascript(files: List[Path]) -> Tuple[bool, str]:
    """Format JavaScript/TypeScript files with prettier."""
    try:
        result = subprocess.run(
            ["npx", "prettier", "--write", *[str(f) for f in files]], capture_output=True, text=True
        )
        return True, "Formatted with prettier"
    except FileNotFoundError:
        return False, "prettier not installed. Run: npm install --save-dev prettier"


def format_go(files: List[Path]) -> Tuple[bool, str]:
    """Format Go files with gofmt."""
    try:
        for file in files:
            subprocess.run(["gofmt", "-w", str(file)], capture_output=True, text=True)
        return True, "Formatted with gofmt"
    except FileNotFoundError:
        return False, "gofmt not installed (should come with Go)"


def get_source_files(language: str) -> List[Path]:
    """Get list of source files to format based on language."""
    patterns = {
        "python": ["**/*.py"],
        "javascript": ["**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx"],
        "go": ["**/*.go"],
    }

    files = []
    for pattern in patterns.get(language, []):
        # Format only files in src/, lib/, pkg/ directories
        for dir_name in ["src", "lib", "pkg"]:
            dir_path = Path(dir_name)
            if dir_path.exists():
                files.extend(dir_path.glob(pattern))

    return files


def main():
    """Run auto-formatting."""
    language = detect_language()

    if language == "unknown":
        print("⚠️  Could not detect project language. Skipping auto-format.")
        return

    print(f"📝 Auto-formatting {language} code...")

    # Get files to format
    files = get_source_files(language)

    if not files:
        print(f"ℹ️  No {language} files found to format")
        return

    # Format based on language
    formatters = {"python": format_python, "javascript": format_javascript, "go": format_go}

    success, message = formatters[language](files)

    if success:
        print(f"✅ {message} ({len(files)} files)")
    else:
        print(f"⚠️  {message}")
        sys.exit(0)  # Don't fail, just warn


if __name__ == "__main__":
    main()
