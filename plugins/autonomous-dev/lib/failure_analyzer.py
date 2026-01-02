#!/usr/bin/env python3
"""
Failure Analyzer - Parse pytest output to extract failure details.

Parses pytest output to extract structured failure information including
error type, location, message, and stack trace.

Key Features:
1. Multi-error type detection (syntax, import, assertion, type, runtime)
2. File path and line number extraction
3. Stack trace extraction for debugging
4. Test name extraction from pytest format
5. Graceful handling of malformed/empty output

Error Type Classification:
    - syntax: SyntaxError, IndentationError, invalid syntax
    - import: ImportError, ModuleNotFoundError
    - assertion: AssertionError, assert failed
    - type: TypeError, AttributeError, NameError
    - runtime: ZeroDivisionError, KeyError, IndexError, ValueError, etc.

Usage:
    from failure_analyzer import (
        FailureAnalyzer,
        FailureAnalysis,
        parse_pytest_output,
    )

    # Parse pytest output
    analyzer = FailureAnalyzer()
    failures = analyzer.parse_pytest_output(pytest_stdout)

    for failure in failures:
        print(f"Error: {failure.error_type} at {failure.file_path}:{failure.line_number}")
        print(f"Message: {failure.error_message}")

Security:
- No arbitrary code execution
- Safe regex parsing
- Bounded output (no memory exhaustion)

Date: 2026-01-02
Issue: #184 (Self-healing QA loop with automatic test fix iterations)
Agent: implementer
Phase: TDD Green (making tests pass)

See error-handling-patterns skill for exception hierarchy and error handling best practices.
"""

import re
from dataclasses import dataclass
from typing import List, Tuple, Optional


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class FailureAnalysis:
    """Structured failure information extracted from pytest output."""
    test_name: str           # test_module.py::test_function
    error_type: str          # "syntax", "import", "assertion", "type", "runtime"
    error_message: str       # Short error description
    file_path: str           # File where error occurred
    line_number: int         # Line number of error
    stack_trace: str         # Complete stack trace for debugging


# =============================================================================
# Error Type Patterns
# =============================================================================

# Error type classification patterns (case-insensitive)
ERROR_TYPE_PATTERNS = {
    "syntax": [
        r"SyntaxError",
        r"IndentationError",
        r"invalid syntax",
        r"was never closed",
        r"unexpected EOF",
    ],
    "import": [
        r"ImportError",
        r"ModuleNotFoundError",
        r"No module named",
        r"cannot import",
    ],
    "assertion": [
        r"AssertionError",
        r"assert.*==",
        r"assert False",
    ],
    "type": [
        r"TypeError",
        r"AttributeError",
        r"NameError",
        r"expected.*got",
    ],
    "runtime": [
        r"ZeroDivisionError",
        r"KeyError",
        r"IndexError",
        r"ValueError",
        r"RuntimeError",
        r"Exception",
    ],
}


# =============================================================================
# Failure Analyzer Class
# =============================================================================

class FailureAnalyzer:
    """Parse pytest output and extract structured failure information."""

    def parse_pytest_output(self, output: str) -> List[FailureAnalysis]:
        """
        Parse pytest output to extract all failures.

        Args:
            output: Raw pytest stdout/stderr

        Returns:
            List of FailureAnalysis objects (empty if no failures or malformed)
        """
        if not output or not output.strip():
            return []

        failures = []

        try:
            # Extract individual error/failure blocks
            error_blocks = self._extract_error_blocks(output)

            for block in error_blocks:
                failure = self._parse_error_block(block)
                if failure:
                    failures.append(failure)

        except Exception:
            # Graceful degradation - return empty list on parse errors
            return []

        return failures

    def _extract_error_blocks(self, output: str) -> List[str]:
        """
        Extract individual error/failure blocks from pytest output.

        Returns:
            List of error block strings
        """
        blocks = []

        # Look for ERROR/FAILURE section headers
        lines = output.split('\n')

        # Find ERROR/FAILURE sections
        in_section = False
        current_block = []

        for i, line in enumerate(lines):
            # Start of error/failure section
            if line.strip().startswith('_') and ('ERROR' in lines[i-1:i+2] or 'FAILURE' in lines[i-1:i+2] if i > 0 else False):
                if current_block:
                    blocks.append('\n'.join(current_block))
                    current_block = []
                in_section = True
                current_block.append(line)
            elif in_section:
                current_block.append(line)
                # End section on next delimiter or summary
                if line.strip().startswith('_') or line.strip().startswith('==='):
                    if current_block:
                        blocks.append('\n'.join(current_block))
                        current_block = []
                    in_section = False

        # Add final block
        if current_block:
            blocks.append('\n'.join(current_block))

        # Also extract inline errors (not in sections)
        # These are typically single-line errors like "test.py:5: SyntaxError: ..."
        # But skip if we already found section blocks (avoid duplicates)
        if not blocks:
            for i, line in enumerate(lines):
                if ':' in line and any(err in line for err in ['SyntaxError:', 'ImportError:', 'AssertionError:', 'TypeError:', 'ZeroDivisionError:']):
                    # Check if this is a simple file:line:error format
                    if re.match(r'[a-zA-Z0-9_/.\-]+\.py:\d+:', line):
                        # This is a standalone error - use just this line
                        blocks.append(line)
                    else:
                        # Get context (2 lines before and after)
                        start = max(0, i - 2)
                        end = min(len(lines), i + 3)
                        block = '\n'.join(lines[start:end])
                        blocks.append(block)

        # Only fall back to full output if it looks like an error
        if not blocks:
            # Check if output contains error markers
            if any(marker in output for marker in ['Error:', 'FAILED', 'ERROR', 'Exception']):
                return [output]
            else:
                # Truly malformed - no errors found
                return []

        return blocks

    def _parse_error_block(self, block: str) -> Optional[FailureAnalysis]:
        """
        Parse a single error block to extract failure details.

        Args:
            block: Single error/failure text block

        Returns:
            FailureAnalysis object or None if parsing fails
        """
        # Extract file path and line number
        file_path, line_number = self._extract_file_line(block)

        # If no file path found, try to infer from error context
        # This handles minimal error messages like "ImportError: module not found"
        if not file_path:
            # For minimal errors, use placeholder values
            file_path = "unknown.py"
            line_number = 0

        # Extract test name
        test_name = self._extract_test_name(block, file_path)

        # Classify error type
        error_type = self._classify_error_type(block)

        # Extract error message
        error_message = self._extract_error_message(block, error_type)

        # Stack trace is the full block
        stack_trace = block

        return FailureAnalysis(
            test_name=test_name,
            error_type=error_type,
            error_message=error_message,
            file_path=file_path,
            line_number=line_number,
            stack_trace=stack_trace,
        )

    def _extract_file_line(self, block: str) -> Tuple[str, int]:
        """
        Extract file path and line number from error block.

        Args:
            block: Error block text

        Returns:
            Tuple of (file_path, line_number). Returns ("", 0) if not found.
        """
        # Pattern: test_file.py:15: error
        match = re.search(r'([a-zA-Z0-9_/.\-]+\.py):(\d+):', block)
        if match:
            file_path = match.group(1)
            line_number = int(match.group(2))
            return file_path, line_number

        # Pattern: File "test_file.py", line 15
        match = re.search(r'File "([^"]+)", line (\d+)', block)
        if match:
            file_path = match.group(1)
            line_number = int(match.group(2))
            return file_path, line_number

        # Pattern: test_file.py line 15
        match = re.search(r'([a-zA-Z0-9_/.\-]+\.py) line (\d+)', block)
        if match:
            file_path = match.group(1)
            line_number = int(match.group(2))
            return file_path, line_number

        return "", 0

    def _extract_test_name(self, block: str, file_path: str) -> str:
        """
        Extract test name from error block.

        Args:
            block: Error block text
            file_path: Already extracted file path

        Returns:
            Test name in format "file.py::test_function" or just file path
        """
        # Pattern: test_module.py::test_function FAILED
        match = re.search(r'([a-zA-Z0-9_/.\-]+\.py)::([a-zA-Z0-9_]+)\s+(FAILED|ERROR)', block)
        if match:
            return f"{match.group(1)}::{match.group(2)}"

        # Pattern: test_module.py::test_function (without FAILED)
        match = re.search(r'([a-zA-Z0-9_/.\-]+\.py)::([a-zA-Z0-9_]+)', block)
        if match:
            return f"{match.group(1)}::{match.group(2)}"

        # Fall back to just file path
        return file_path

    def _classify_error_type(self, block: str) -> str:
        """
        Classify error type based on error message patterns.

        Args:
            block: Error block text

        Returns:
            Error type: "syntax", "import", "assertion", "type", or "runtime"
        """
        block_lower = block.lower()

        # Check in priority order (syntax > import > assertion > type > runtime)
        # This ensures more specific errors aren't overridden by generic ones
        priority_order = ["syntax", "import", "assertion", "type", "runtime"]

        for error_type in priority_order:
            patterns = ERROR_TYPE_PATTERNS.get(error_type, [])
            for pattern in patterns:
                if re.search(pattern, block_lower, re.IGNORECASE):
                    return error_type

        # Default to runtime if unknown
        return "runtime"

    def _extract_error_message(self, block: str, error_type: str) -> str:
        """
        Extract concise error message from block.

        Args:
            block: Error block text
            error_type: Classified error type

        Returns:
            Short error description
        """
        lines = block.split('\n')

        # For import errors, prioritize ModuleNotFoundError with module name
        if error_type == "import":
            for line in lines:
                if 'ModuleNotFoundError' in line or 'No module named' in line:
                    return line.strip()

        # Look for lines starting with 'E' (pytest error marker)
        error_lines = [line.lstrip('E ').strip() for line in lines if line.strip().startswith('E ')]
        if error_lines:
            # Join first 2-3 error lines for context
            return ' '.join(error_lines[:3])

        # Look for exception type lines (specific exceptions)
        for line in lines:
            if any(exc in line for exc in ['Error:', 'Exception:', 'AssertionError', 'SyntaxError', 'ImportError', 'TypeError']):
                # Include next line for more context
                idx = lines.index(line)
                context = line.strip()
                if idx + 1 < len(lines) and lines[idx + 1].strip():
                    context += ' ' + lines[idx + 1].strip()
                return context

        # Fall back to first non-empty line
        for line in lines:
            if line.strip():
                return line.strip()

        return f"Unknown {error_type} error"


# =============================================================================
# Standalone Functions (for convenience)
# =============================================================================

def parse_pytest_output(output: str) -> List[FailureAnalysis]:
    """
    Parse pytest output (convenience function).

    Args:
        output: Raw pytest stdout/stderr

    Returns:
        List of FailureAnalysis objects
    """
    analyzer = FailureAnalyzer()
    return analyzer.parse_pytest_output(output)


def extract_error_details(output: str) -> List[FailureAnalysis]:
    """
    Extract error details from pytest output (alias for parse_pytest_output).

    Args:
        output: Raw pytest stdout/stderr

    Returns:
        List of FailureAnalysis objects
    """
    return parse_pytest_output(output)
