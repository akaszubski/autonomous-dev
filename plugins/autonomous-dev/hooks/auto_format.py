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

# Issue #953: Hook safety — wrap main() with safe_main so hook crashes never
# block Claude Code. The wrap is purely an outer safety net; success-path
# return codes are preserved (int return → exit code, sys.exit → propagated).
import sys as _sys_953  # alias to avoid colliding with hook-local sys imports
from pathlib import Path as _Path_953

_hook_dir_953 = _Path_953(__file__).resolve().parent
for _candidate_lib_953 in (
    _hook_dir_953.parent / "lib",                    # plugins/autonomous-dev/lib (dev)
    _hook_dir_953.parent.parent / "lib",             # ~/.claude/lib (installed)
    _Path_953.home() / ".claude" / "plugins" / "autonomous-dev" / "lib",  # marketplace
):
    if _candidate_lib_953.exists() and str(_candidate_lib_953) not in _sys_953.path:
        _sys_953.path.insert(0, str(_candidate_lib_953))

try:
    from hook_safety import safe_main as _safe_main_953
except ImportError:
    # Fallback: no-op wrapper so hooks still load if hook_safety is missing.
    def _safe_main_953(_fn):
        _result = _fn()
        if isinstance(_result, int):
            _sys_953.exit(_result)
        _sys_953.exit(0)


import subprocess
import os
import sys
from pathlib import Path
from typing import List, Tuple

# Add lib to path for error_messages module
def is_running_under_uv() -> bool:
    """Detect if script is running under UV."""
    return "UV_PROJECT_ENVIRONMENT" in os.environ

sys.path.insert(0, str(Path(__file__).parent.parent / 'lib'))
from error_messages import formatter_not_found_error, print_warning


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
    except FileNotFoundError as e:
        # Determine which formatter is missing
        formatter = "black" if "black" in str(e) else "isort"
        error = formatter_not_found_error(formatter, sys.executable)
        error.print()
        sys.exit(1)


def format_javascript(files: List[Path]) -> Tuple[bool, str]:
    """Format JavaScript/TypeScript files with prettier."""
    try:
        result = subprocess.run(
            ["npx", "prettier", "--write", *[str(f) for f in files]], capture_output=True, text=True
        )
        return True, "Formatted with prettier"
    except FileNotFoundError:
        print_warning(
            "prettier not found",
            "Install with: npm install --save-dev prettier\nOR skip formatting: git commit --no-verify"
        )
        sys.exit(1)


def format_go(files: List[Path]) -> Tuple[bool, str]:
    """Format Go files with gofmt."""
    try:
        for file in files:
            subprocess.run(["gofmt", "-w", str(file)], capture_output=True, text=True)
        return True, "Formatted with gofmt"
    except FileNotFoundError:
        print_warning(
            "gofmt not found",
            "gofmt should come with Go installation\nInstall Go from: https://golang.org/dl/\nOR skip formatting: git commit --no-verify"
        )
        sys.exit(1)


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
    # Universal bypass (Issue #969): env var or .claude/.bypass falls through.
    try:
        from hook_bypass import is_bypassed, log_bypass_used
        if is_bypassed():
            log_bypass_used(hook_name=Path(__file__).name, tool_name="auto_format")
            return
    except ImportError:
        pass

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

    # If we get here, formatting succeeded
    print(f"✅ {message} ({len(files)} files)")



# Issue #1012 (W0): Per-hook timing telemetry. Best-effort, never raises.
# Records duration + decision_shape to ~/.claude/logs/hook_timings_YYYY-MM-DD.jsonl.
try:
    from hook_timing import HookTimer  # type: ignore[import-not-found]
except ImportError:
    # Fallback: no-op stub so hooks keep working if hook_timing is missing.
    class HookTimer:  # type: ignore[no-redef]
        def __init__(self, *_, **__): pass
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def set_decision_shape(self, _): pass

_HOOK_TIMER_NAME = _Path_953(__file__).name


def _timed_main():  # type: ignore[no-redef]
    with HookTimer(_HOOK_TIMER_NAME):
        return main()

if __name__ == "__main__":
    _safe_main_953(_timed_main)
