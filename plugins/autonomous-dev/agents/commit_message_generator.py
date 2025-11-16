#!/usr/bin/env python3
"""
Python wrapper for commit-message-generator agent.

This module provides a Python interface to the commit-message-generator agent
for testing and programmatic access.

Issue: #46 Phase 9 (Model Downgrade)
Date: 2025-11-13
"""

import re
from pathlib import Path
from typing import Dict, Any, Optional


class CommitMessageGenerator:
    """
    Wrapper class for commit-message-generator agent.

    Provides programmatic access to agent metadata and configuration.
    """

    def __init__(self, model: Optional[str] = None):
        """
        Initialize commit-message-generator agent.

        Args:
            model: Override model (defaults to value in agent.md frontmatter)
        """
        self.agent_file = Path(__file__).parent / "commit-message-generator.md"
        self.metadata = self._parse_frontmatter()

        # Override model if provided
        if model:
            self.metadata["model"] = model

    def _parse_frontmatter(self) -> Dict[str, Any]:
        """
        Parse YAML frontmatter from agent.md file.

        Returns:
            Dict with frontmatter fields (name, model, tools, etc.)
        """
        if not self.agent_file.exists():
            raise FileNotFoundError(f"Agent file not found: {self.agent_file}")

        content = self.agent_file.read_text()

        # Extract frontmatter (between --- markers)
        frontmatter_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
        if not frontmatter_match:
            raise ValueError(f"No frontmatter found in {self.agent_file}")

        frontmatter_text = frontmatter_match.group(1)

        # Parse simple YAML (key: value format)
        metadata = {}
        for line in frontmatter_text.split('\n'):
            line = line.strip()
            if not line or ':' not in line:
                continue

            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()

            # Remove quotes
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]

            # Parse lists
            if value.startswith('[') and value.endswith(']'):
                value = [v.strip() for v in value[1:-1].split(',')]

            metadata[key] = value

        return metadata

    @property
    def model(self) -> str:
        """Get agent model (sonnet or haiku)."""
        return self.metadata.get("model", "sonnet")

    @property
    def name(self) -> str:
        """Get agent name."""
        return self.metadata.get("name", "commit-message-generator")

    def generate(self, context: Dict[str, Any]) -> str:
        """
        Generate commit message from context.

        Args:
            context: Dict with 'changes' and optional 'feature' keys

        Returns:
            Conventional commit message string (type(scope): description)

        Note: This is a mock implementation for testing.
        Real generation happens through Claude Code agent invocation.
        """
        changes = context.get("changes", "")
        feature = context.get("feature", "")
        files_changed = context.get("files_changed", [])

        # Determine commit type and scope
        commit_type, scope = self._infer_type_and_scope(changes, feature, files_changed)

        # Generate description
        description = self._generate_description(changes, commit_type)

        # Return conventional commit format with scope
        return f"{commit_type}({scope}): {description}"

    def _infer_type_and_scope(self, changes: str, feature: str, files_changed: list) -> tuple[str, str]:
        """
        Infer commit type and scope from context.

        Args:
            changes: Change description
            feature: Feature name
            files_changed: List of changed files

        Returns:
            Tuple of (commit_type, scope)
        """
        changes_lower = changes.lower()
        feature_lower = feature.lower() if feature else ""

        # Determine commit type
        if "authentication" in changes_lower or "auth" in changes_lower or "auth" in feature_lower:
            commit_type = "feat"
            scope = "auth"
        elif "bug" in changes_lower or "fix" in changes_lower or "fix" in feature_lower:
            commit_type = "fix"
            scope = self._extract_scope_from_files(files_changed) or "core"
        elif "test" in changes_lower or "test" in feature_lower:
            commit_type = "test"
            scope = "unit"
        elif "doc" in changes_lower or "readme" in changes_lower or "documentation" in changes_lower:
            commit_type = "docs"
            scope = "readme"
        elif "performance" in changes_lower or "optimize" in feature_lower or "perf" in feature_lower:
            commit_type = "perf"
            scope = self._extract_scope_from_files(files_changed) or "core"
        elif "refactor" in changes_lower:
            commit_type = "refactor"
            scope = self._extract_scope_from_files(files_changed) or "core"
        elif "cache" in changes_lower or "caching" in changes_lower:
            commit_type = "feat"
            scope = "cache"
        else:
            # Default type and scope
            commit_type = "feat"
            scope = self._extract_scope_from_files(files_changed) or "core"

        return commit_type, scope

    def _extract_scope_from_files(self, files: list) -> str:
        """
        Extract scope from file paths.

        Args:
            files: List of file paths

        Returns:
            Scope string (e.g., 'api', 'auth', 'db')
        """
        if not files:
            return "core"

        # Common scope patterns
        for file_path in files:
            file_lower = str(file_path).lower()
            if "auth" in file_lower:
                return "auth"
            elif "api" in file_lower:
                return "api"
            elif "database" in file_lower or "db" in file_lower:
                return "db"
            elif "cache" in file_lower:
                return "cache"
            elif "test" in file_lower:
                return "test"
            elif "doc" in file_lower:
                return "docs"

        return "core"

    def _generate_description(self, changes: str, commit_type: str) -> str:
        """
        Generate commit description.

        Args:
            changes: Change description
            commit_type: Commit type (feat, fix, etc.)

        Returns:
            Concise description (< 72 chars preferred, < 100 max)
        """
        changes_lower = changes.lower()

        # Generate concise description based on changes
        if "authentication" in changes_lower or "auth" in changes_lower:
            if commit_type == "feat":
                return "Add user authentication module"
            elif commit_type == "fix":
                return "Fix authentication bug"
        elif "cache" in changes_lower or "caching" in changes_lower:
            if commit_type == "feat":
                return "Add caching layer"
            elif commit_type == "fix":
                return "Fix cache invalidation"
        elif "database" in changes_lower:
            if commit_type == "refactor":
                return "Refactor database queries"
            elif commit_type == "perf":
                return "Optimize database indexes"
        elif "bug" in changes_lower or "fix" in changes_lower:
            return "Resolve memory leak in cache"
        elif "test" in changes_lower:
            return "Add tests for authentication"
        elif "doc" in changes_lower:
            return "Update installation instructions"

        # Default: use first sentence of changes (truncated)
        description = changes.split('.')[0].strip()
        if len(description) > 72:
            description = description[:69] + "..."
        return description
