#!/usr/bin/env python3
"""
Code Path Analyzer Library - Discover all code paths matching a pattern.

This library discovers all code paths matching a pattern for debug-first
enforcement. Uses Python's native glob and regex (not ripgrep) for portability.

Features:
- Find all locations matching a pattern (regex search)
- Return CodePath objects with file_path, line_number, context, match_text
- Handle empty results gracefully
- Handle invalid patterns gracefully
- Search recursively in project directory
- Filter by file types (e.g., ["*.py", "*.md"])
- Exclude common directories (.git, __pycache__, node_modules)
- Support multiline context (N lines before/after match)

Usage:
    from code_path_analyzer import find_all_code_paths, CodePathAnalyzer

    # Find all matches
    results = find_all_code_paths(pattern="calculate", file_types=["*.py"])
    for code_path in results:
        print(f"{code_path.file_path}:{code_path.line_number} - {code_path.match_text}")

    # Use analyzer for repeated searches
    analyzer = CodePathAnalyzer("/path/to/project")
    results = analyzer.find(pattern=r"def \w+\(\):")

Author: implementer agent
Date: 2026-01-03
Related: Issue #200 - Debug-first enforcement and self-test requirements
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


# Default directories to exclude from search
DEFAULT_EXCLUDE_PATTERNS = [
    ".git",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
    "build",
    "dist",
    ".pytest_cache",
    ".mypy_cache",
]


@dataclass
class CodePath:
    """
    A code path matching a search pattern.

    Attributes:
        file_path: Path to file containing match
        line_number: Line number of match (1-indexed)
        context: Surrounding lines for context
        match_text: The matched text
    """

    file_path: str
    line_number: int
    context: str
    match_text: str


def _matches_file_types(file_path: Path, file_types: Optional[List[str]]) -> bool:
    """
    Check if file matches any of the file type patterns.

    Args:
        file_path: Path to check
        file_types: List of patterns like ["*.py", "*.md"] (None = all files)

    Returns:
        True if file matches any pattern
    """
    if file_types is None:
        return True

    for pattern in file_types:
        # Convert glob pattern to simple suffix match
        # "*.py" -> ".py"
        if pattern.startswith("*"):
            suffix = pattern[1:]  # Remove the *
            if file_path.name.endswith(suffix):
                return True
        else:
            # Exact match
            if file_path.name == pattern:
                return True

    return False


def _should_exclude_path(file_path: Path, exclude_patterns: List[str]) -> bool:
    """
    Check if path should be excluded from search.

    Args:
        file_path: Path to check
        exclude_patterns: List of directory names to exclude

    Returns:
        True if path should be excluded
    """
    # Check if any part of the path matches an exclude pattern
    for part in file_path.parts:
        if part in exclude_patterns:
            return True
    return False


def find_all_code_paths(
    pattern: str,
    project_root: Optional[str] = None,
    file_types: Optional[List[str]] = None,
    context_lines: int = 3,
    case_sensitive: bool = True,
    exclude_patterns: Optional[List[str]] = None,
) -> List[CodePath]:
    """
    Find all code paths matching a pattern.

    Args:
        pattern: Regex pattern to search for
        project_root: Root directory to search (default: current directory)
        file_types: List of file type patterns like ["*.py", "*.md"] (None = all)
        context_lines: Number of lines before/after match to include in context
        case_sensitive: Case-sensitive search (default: True)
        exclude_patterns: Additional directories to exclude (beyond defaults)

    Returns:
        List of CodePath objects for each match

    Raises:
        ValueError: If pattern is invalid regex
        FileNotFoundError: If project_root doesn't exist

    Examples:
        >>> results = find_all_code_paths(pattern="calculate", file_types=["*.py"])
        >>> for code_path in results:
        ...     print(f"{code_path.file_path}:{code_path.line_number}")

        >>> results = find_all_code_paths(
        ...     pattern=r"def \w+\(\):",
        ...     project_root="/path/to/project",
        ...     context_lines=5
        ... )
    """
    # Validate project root
    if project_root is None:
        root = Path.cwd()
    else:
        root = Path(project_root)

    if not root.exists():
        raise FileNotFoundError(f"Project root not found: {project_root}")

    # Compile regex pattern
    try:
        flags = 0 if case_sensitive else re.IGNORECASE
        regex = re.compile(pattern, flags)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern: {e}")

    # Merge exclude patterns
    exclude = DEFAULT_EXCLUDE_PATTERNS.copy()
    if exclude_patterns:
        exclude.extend(exclude_patterns)

    # Search all files
    results = []

    for file_path in root.rglob("*"):
        # Skip directories
        if not file_path.is_file():
            continue

        # Skip excluded paths
        if _should_exclude_path(file_path, exclude):
            continue

        # Skip non-matching file types
        if not _matches_file_types(file_path, file_types):
            continue

        # Search file for pattern
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines()

            for i, line in enumerate(lines):
                match = regex.search(line)
                if match:
                    # Extract context
                    start = max(0, i - context_lines)
                    end = min(len(lines), i + context_lines + 1)
                    context = "\n".join(lines[start:end])

                    # Create CodePath
                    results.append(
                        CodePath(
                            file_path=str(file_path),
                            line_number=i + 1,  # 1-indexed
                            context=context,
                            match_text=line.strip(),
                        )
                    )

        except (UnicodeDecodeError, PermissionError):
            # Skip binary files and files without read permission
            continue
        except Exception:
            # Skip files with other read errors
            continue

    return results


class CodePathAnalyzer:
    """
    Stateful code path analyzer for repeated searches.

    Attributes:
        project_root: Root directory to search
        exclude_patterns: Directories to exclude from search

    Examples:
        >>> analyzer = CodePathAnalyzer("/path/to/project")
        >>> results = analyzer.find(pattern="calculate")

        >>> analyzer = CodePathAnalyzer(
        ...     "/path/to/project",
        ...     exclude_patterns=["build", "dist"]
        ... )
        >>> results = analyzer.find(pattern=r"def \w+\(\):", file_types=["*.py"])
    """

    def __init__(
        self,
        project_root: str,
        exclude_patterns: Optional[List[str]] = None,
    ):
        """
        Initialize CodePathAnalyzer.

        Args:
            project_root: Root directory to search
            exclude_patterns: Additional directories to exclude (beyond defaults)
        """
        self.project_root = Path(project_root)

        # Merge exclude patterns with defaults
        self.exclude_patterns = DEFAULT_EXCLUDE_PATTERNS.copy()
        if exclude_patterns:
            self.exclude_patterns.extend(exclude_patterns)

    def find(
        self,
        pattern: str,
        file_types: Optional[List[str]] = None,
        context_lines: int = 3,
        case_sensitive: bool = True,
    ) -> List[CodePath]:
        """
        Find all code paths matching a pattern.

        Args:
            pattern: Regex pattern to search for
            file_types: List of file type patterns like ["*.py", "*.md"]
            context_lines: Number of lines before/after match to include
            case_sensitive: Case-sensitive search (default: True)

        Returns:
            List of CodePath objects for each match
        """
        return find_all_code_paths(
            pattern=pattern,
            project_root=str(self.project_root),
            file_types=file_types,
            context_lines=context_lines,
            case_sensitive=case_sensitive,
            exclude_patterns=self.exclude_patterns,
        )
