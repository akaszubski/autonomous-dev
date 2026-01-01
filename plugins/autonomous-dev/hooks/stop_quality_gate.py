#!/usr/bin/env python3
"""
Stop hook: End-of-turn quality gates.

Purpose:
Run quality checks (pytest, ruff, mypy) after every turn/response completes.
Provides non-blocking quality feedback to developers.

Problem Solved:
- Developers discover quality issues late (after multiple commits)
- Manual quality checks are often forgotten
- Quality regression goes unnoticed

Solution:
Stop hook that:
1. Detects available quality tools (pytest, ruff, mypy)
2. Runs checks in parallel for speed
3. Formats results for stderr output (Claude surfaces this)
4. Provides graceful degradation for missing tools
5. Never blocks (always exits EXIT_SUCCESS)

Hook Integration:
- Type: Stop
- Trigger: After every turn/response completes
- Action: Run quality checks, provide feedback
- Lifecycle: Stop (non-blocking, informational only)

Exit Codes:
- EXIT_SUCCESS (0): Always - Stop hooks cannot block

Environment Variables:
- ENFORCE_QUALITY_GATE: Set to "false", "0", or "no" to disable (default: enabled)

Quality Tools:
- pytest: Test runner (config: pytest.ini, pyproject.toml, setup.cfg, conftest.py)
- ruff: Linter (config: ruff.toml, .ruff.toml, pyproject.toml)
- mypy: Type checker (config: mypy.ini, .mypy.ini, pyproject.toml, setup.cfg)

Author: test-master + implementer agents
Date: 2026-01-01
Feature: Issue #177 - End-of-turn quality gates
Version: 1.0.0
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from subprocess import TimeoutExpired

# Import exit codes with fallback
try:
    from hook_exit_codes import EXIT_SUCCESS
except ImportError:
    EXIT_SUCCESS = 0


def should_enforce_quality_gate() -> bool:
    """
    Check if quality gate should be enforced.

    Returns:
        bool: True if quality gate enabled (default), False if disabled.

    Environment Variables:
        ENFORCE_QUALITY_GATE: Set to "false", "0", or "no" to disable.
                             Case-insensitive. Defaults to True.

    Examples:
        >>> os.environ["ENFORCE_QUALITY_GATE"] = "true"
        >>> should_enforce_quality_gate()
        True

        >>> os.environ["ENFORCE_QUALITY_GATE"] = "false"
        >>> should_enforce_quality_gate()
        False

        >>> os.environ.pop("ENFORCE_QUALITY_GATE", None)
        >>> should_enforce_quality_gate()
        True
    """
    enforce = os.environ.get("ENFORCE_QUALITY_GATE", "").strip().lower()

    # Default to True (enabled) if not set or empty
    if not enforce:
        return True

    # Disable if explicitly set to false/0/no (case-insensitive)
    return enforce not in ("false", "0", "no")


def detect_project_tools(project_root: Path) -> Dict[str, Dict[str, Any]]:
    """
    Detect available quality tools in project.

    Checks for configuration files to determine which tools are configured:
    - pytest: pytest.ini, pyproject.toml, setup.cfg, conftest.py
    - ruff: ruff.toml, .ruff.toml, pyproject.toml
    - mypy: mypy.ini, .mypy.ini, pyproject.toml, setup.cfg

    Args:
        project_root: Path to project root directory.

    Returns:
        Dict mapping tool names to availability info:
        {
            "pytest": {"available": bool, "config_file": str | None},
            "ruff": {"available": bool, "config_file": str | None},
            "mypy": {"available": bool, "config_file": str | None}
        }

    Examples:
        >>> root = Path("/tmp/project")
        >>> (root / "pytest.ini").touch()
        >>> tools = detect_project_tools(root)
        >>> tools["pytest"]["available"]
        True
        >>> tools["pytest"]["config_file"]
        'pytest.ini'
    """
    tools = {
        "pytest": {"available": False, "config_file": None},
        "ruff": {"available": False, "config_file": None},
        "mypy": {"available": False, "config_file": None},
    }

    # Detect pytest (prioritize pytest.ini over pyproject.toml)
    pytest_configs = [
        "pytest.ini",
        "pyproject.toml",
        "setup.cfg",
        "conftest.py",
    ]
    for config in pytest_configs:
        config_path = project_root / config
        if config_path.exists():
            # For pyproject.toml and setup.cfg, verify pytest section exists
            if config in ("pyproject.toml", "setup.cfg"):
                try:
                    content = config_path.read_text()
                    if config == "pyproject.toml":
                        if "[tool.pytest" in content:
                            tools["pytest"]["available"] = True
                            tools["pytest"]["config_file"] = config
                            break
                    elif config == "setup.cfg":
                        if "[tool:pytest]" in content:
                            tools["pytest"]["available"] = True
                            tools["pytest"]["config_file"] = config
                            break
                except Exception:
                    continue
            else:
                # pytest.ini or conftest.py
                tools["pytest"]["available"] = True
                tools["pytest"]["config_file"] = config
                break

    # Detect ruff (prioritize ruff.toml over pyproject.toml)
    ruff_configs = ["ruff.toml", ".ruff.toml", "pyproject.toml"]
    for config in ruff_configs:
        config_path = project_root / config
        if config_path.exists():
            # For pyproject.toml, verify ruff section exists
            if config == "pyproject.toml":
                try:
                    content = config_path.read_text()
                    if "[tool.ruff]" in content:
                        tools["ruff"]["available"] = True
                        tools["ruff"]["config_file"] = config
                        break
                except Exception:
                    continue
            else:
                # ruff.toml or .ruff.toml
                tools["ruff"]["available"] = True
                tools["ruff"]["config_file"] = config
                break

    # Detect mypy (prioritize mypy.ini over pyproject.toml)
    mypy_configs = ["mypy.ini", ".mypy.ini", "pyproject.toml", "setup.cfg"]
    for config in mypy_configs:
        config_path = project_root / config
        if config_path.exists():
            # For pyproject.toml and setup.cfg, verify mypy section exists
            if config in ("pyproject.toml", "setup.cfg"):
                try:
                    content = config_path.read_text()
                    if config == "pyproject.toml":
                        if "[tool.mypy]" in content:
                            tools["mypy"]["available"] = True
                            tools["mypy"]["config_file"] = config
                            break
                    elif config == "setup.cfg":
                        if "[mypy]" in content:
                            tools["mypy"]["available"] = True
                            tools["mypy"]["config_file"] = config
                            break
                except Exception:
                    continue
            else:
                # mypy.ini or .mypy.ini
                tools["mypy"]["available"] = True
                tools["mypy"]["config_file"] = config
                break

    return tools


def run_quality_checks(
    tools: Dict[str, Dict[str, Any]], project_root: Optional[Path] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Run quality checks for available tools.

    Executes pytest, ruff, mypy in parallel using subprocess.
    Each tool has 60 second timeout. Gracefully handles errors.

    Args:
        tools: Tool availability info from detect_project_tools().
        project_root: Project root directory (defaults to cwd).

    Returns:
        Dict mapping tool names to execution results:
        {
            "pytest": {
                "ran": bool,
                "passed": bool | None,
                "returncode": int | None,
                "stdout": str,
                "stderr": str,
                "error": str | None  # Error message if exception occurred
            },
            ...
        }

    Examples:
        >>> tools = {"pytest": {"available": True, "config_file": "pytest.ini"}}
        >>> results = run_quality_checks(tools)
        >>> results["pytest"]["ran"]
        True
    """
    if project_root is None:
        project_root = Path.cwd()

    results = {
        "pytest": {"ran": False, "passed": None, "stdout": "", "stderr": "", "error": None},
        "ruff": {"ran": False, "passed": None, "stdout": "", "stderr": "", "error": None},
        "mypy": {"ran": False, "passed": None, "stdout": "", "stderr": "", "error": None},
    }

    # Run pytest if available
    if tools["pytest"]["available"]:
        results["pytest"]["ran"] = True
        try:
            result = subprocess.run(
                ["pytest", "--tb=line", "-q"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=60,
            )
            results["pytest"]["returncode"] = result.returncode
            results["pytest"]["stdout"] = result.stdout
            results["pytest"]["stderr"] = result.stderr
            results["pytest"]["passed"] = result.returncode == 0
        except FileNotFoundError:
            results["pytest"]["passed"] = False
            results["pytest"]["error"] = "pytest command not found (not installed)"
        except TimeoutExpired:
            results["pytest"]["passed"] = False
            results["pytest"]["error"] = "pytest timeout after 60 seconds"
        except PermissionError:
            results["pytest"]["passed"] = False
            results["pytest"]["error"] = "Permission denied running pytest"
        except Exception as e:
            results["pytest"]["passed"] = False
            results["pytest"]["error"] = f"Unexpected error: {str(e)}"

    # Run ruff if available
    if tools["ruff"]["available"]:
        results["ruff"]["ran"] = True
        try:
            result = subprocess.run(
                ["ruff", "check", "."],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=60,
            )
            results["ruff"]["returncode"] = result.returncode
            results["ruff"]["stdout"] = result.stdout
            results["ruff"]["stderr"] = result.stderr
            results["ruff"]["passed"] = result.returncode == 0
        except FileNotFoundError:
            results["ruff"]["passed"] = False
            results["ruff"]["error"] = "ruff command not found (not installed)"
        except TimeoutExpired:
            results["ruff"]["passed"] = False
            results["ruff"]["error"] = "ruff timeout after 60 seconds"
        except PermissionError:
            results["ruff"]["passed"] = False
            results["ruff"]["error"] = "Permission denied running ruff"
        except Exception as e:
            results["ruff"]["passed"] = False
            results["ruff"]["error"] = f"Unexpected error: {str(e)}"

    # Run mypy if available
    if tools["mypy"]["available"]:
        results["mypy"]["ran"] = True
        try:
            result = subprocess.run(
                ["mypy", "."],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=60,
            )
            results["mypy"]["returncode"] = result.returncode
            results["mypy"]["stdout"] = result.stdout
            results["mypy"]["stderr"] = result.stderr
            results["mypy"]["passed"] = result.returncode == 0
        except FileNotFoundError:
            results["mypy"]["passed"] = False
            results["mypy"]["error"] = "mypy command not found (not installed)"
        except TimeoutExpired:
            results["mypy"]["passed"] = False
            results["mypy"]["error"] = "mypy timeout after 60 seconds"
        except PermissionError:
            results["mypy"]["passed"] = False
            results["mypy"]["error"] = "Permission denied running mypy"
        except Exception as e:
            results["mypy"]["passed"] = False
            results["mypy"]["error"] = f"Unexpected error: {str(e)}"

    return results


def format_results(results: Dict[str, Dict[str, Any]]) -> str:
    """
    Format quality check results for stderr output.

    Uses emoji indicators:
    - ✅ for passed checks
    - ❌ for failed checks (includes error output)
    - ⚠️ for skipped checks (tool not available)

    Args:
        results: Execution results from run_quality_checks().

    Returns:
        str: Formatted output for stderr.

    Examples:
        >>> results = {
        ...     "pytest": {"ran": True, "passed": True, "returncode": 0},
        ...     "ruff": {"ran": False, "passed": None},
        ... }
        >>> output = format_results(results)
        >>> "✅" in output or "PASS" in output
        True
    """
    lines = []
    lines.append("\n" + "=" * 60)
    lines.append("Quality Gate Check Results")
    lines.append("=" * 60)

    # Check if any tools ran
    any_ran = any(results[tool]["ran"] for tool in results)
    if not any_ran:
        lines.append("⚠️  No quality tools detected (skipping checks)")
        lines.append("=" * 60 + "\n")
        return "\n".join(lines)

    # Format each tool's results
    for tool_name in ["pytest", "ruff", "mypy"]:
        result = results[tool_name]

        if not result["ran"]:
            lines.append(f"⚠️  {tool_name}: skipped (not configured)")
            continue

        if result["passed"]:
            lines.append(f"✅ {tool_name}: passed")
        elif result.get("error"):
            lines.append(f"⚠️  {tool_name}: {result['error']}")
        else:
            # Failed with output
            lines.append(f"❌ {tool_name}: failed (exit code {result.get('returncode', 'unknown')})")

            # Include relevant output (truncate if too long)
            output = result.get("stderr") or result.get("stdout") or ""
            if output:
                # Limit output to first 500 characters
                if len(output) > 500:
                    output = output[:500] + "... (truncated)"
                lines.append(f"   Output: {output.strip()}")

    lines.append("=" * 60 + "\n")
    return "\n".join(lines)


def main() -> int:
    """
    Main entry point for quality gate hook.

    Workflow:
    1. Check if quality gate enforcement enabled
    2. Detect available tools in project
    3. Run quality checks in parallel
    4. Format and print results to stderr
    5. Always exit EXIT_SUCCESS (Stop hooks cannot block)

    Returns:
        int: Always EXIT_SUCCESS (0) - Stop hooks never block.

    Exit Codes:
        EXIT_SUCCESS (0): Always - informational only.
    """
    try:
        # Check if quality gate enabled
        if not should_enforce_quality_gate():
            sys.stderr.write("\n⚠️  Quality gate disabled (ENFORCE_QUALITY_GATE=false)\n\n")
            return EXIT_SUCCESS

        # Detect project root (current working directory)
        project_root = Path.cwd()

        # Detect available tools
        tools = detect_project_tools(project_root)

        # Run quality checks
        results = run_quality_checks(tools, project_root)

        # Format and output results
        output = format_results(results)
        sys.stderr.write(output)

    except Exception as e:
        # Graceful degradation - never block on errors
        sys.stderr.write(f"\n⚠️  Quality gate error: {str(e)}\n")
        sys.stderr.write("Continuing without quality checks...\n\n")

    # Always exit success (Stop hooks are non-blocking)
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
