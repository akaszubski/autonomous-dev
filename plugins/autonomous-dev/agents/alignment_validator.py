#!/usr/bin/env python3
"""
Python wrapper for alignment-validator agent.

This module provides a Python interface to the alignment-validator agent
for testing and programmatic access.

Issue: #46 Phase 9 (Model Downgrade)
Date: 2025-11-13
"""

import re
from pathlib import Path
from typing import Dict, Any, Optional, Tuple


class AlignmentValidator:
    """
    Wrapper class for alignment-validator agent.

    Provides programmatic access to agent metadata and configuration.
    """

    def __init__(self, model: Optional[str] = None, project_md: Optional[Path] = None):
        """
        Initialize alignment-validator agent.

        Args:
            model: Override model (defaults to value in agent.md frontmatter)
            project_md: Path to PROJECT.md file
        """
        self.agent_file = Path(__file__).parent / "alignment-validator.md"
        self.metadata = self._parse_frontmatter()
        self.project_md = project_md

        # Override model if provided
        if model:
            self.metadata["model"] = model

        # Load project goals if project_md provided
        self.project_goals = ""
        if project_md and project_md.exists():
            self.project_goals = project_md.read_text()

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
        return self.metadata.get("name", "alignment-validator")

    def validate(self, changes: Dict[str, Any]) -> bool:
        """
        Validate if changes align with project goals.

        Two-stage validation:
        1. Check if feature aligns with GOALS/IN SCOPE (positive validation)
        2. Check if feature is NOT in OUT OF SCOPE (negative validation)

        Args:
            changes: Dict with 'description', 'files', and 'type' keys

        Returns:
            True if aligned (in GOALS and NOT in OUT OF SCOPE), False otherwise

        Note: This is a mock implementation for testing.
        Real validation happens through Claude Code agent invocation.
        """
        description = changes.get("description", "").lower()
        files = changes.get("files", [])
        change_type = changes.get("type", "")

        goals_lower = self.project_goals.lower()

        # Stage 1: Positive validation - check if aligned with GOALS
        aligned_with_goals = self._check_goals_alignment(description, goals_lower)

        # Stage 2: Negative validation - check if NOT in OUT OF SCOPE
        not_out_of_scope = not self._check_out_of_scope(description, goals_lower)

        # Return True only if both conditions met
        return aligned_with_goals and not_out_of_scope

    def _check_goals_alignment(self, description: str, goals_lower: str) -> bool:
        """
        Check if feature aligns with GOALS or IN SCOPE sections.

        Args:
            description: Feature description (lowercase)
            goals_lower: PROJECT.md content (lowercase)

        Returns:
            True if feature aligns with any goal
        """
        # Check for auth/security alignment (expanded keywords)
        auth_keywords = ['auth', 'security', 'user', 'password', 'token', 'jwt', 'login', 'session']
        security_keywords = ['security', 'harden', 'cwe-', 'vulnerability', 'traversal', 'injection', 'xss']

        if any(keyword in description for keyword in auth_keywords):
            if 'authentication' in goals_lower or 'auth' in goals_lower:
                return True

        if any(keyword in description for keyword in security_keywords):
            if 'security' in goals_lower or 'hardening' in goals_lower:
                return True

        # Check for test/quality alignment (be careful with "integration" - it could mean API integration)
        test_keywords = ['test', 'coverage', 'quality', 'unit']
        # Only match "integration" if it's followed by "test" or "testing"
        if 'integration test' in description or 'integration testing' in description:
            test_keywords.append('integration')

        if any(keyword in description for keyword in test_keywords):
            if 'test' in goals_lower or 'coverage' in goals_lower or 'quality' in goals_lower:
                return True

        # Check for performance alignment
        if any(keyword in description for keyword in ['performance', 'optimize', 'speed', 'efficiency']):
            if 'performance' in goals_lower or 'optimize' in goals_lower:
                return True

        # Default: not aligned (require explicit match with goals)
        return False

    def _check_out_of_scope(self, description: str, goals_lower: str) -> bool:
        """
        Check if feature is explicitly OUT OF SCOPE.

        Args:
            description: Feature description (lowercase)
            goals_lower: PROJECT.md content (lowercase)

        Returns:
            True if feature is out of scope (should be rejected)
        """
        # Extract OUT OF SCOPE section if it exists
        if 'out of scope' not in goals_lower:
            # No OUT OF SCOPE section - nothing is explicitly out of scope
            return False

        # Get content after "## OUT OF SCOPE" header
        out_of_scope_section = goals_lower.split('out of scope')[-1]

        # If there's another "##" header, only use content until that header
        if '\n##' in out_of_scope_section:
            out_of_scope_section = out_of_scope_section.split('\n##')[0]

        # Check if description contains out-of-scope keywords
        out_of_scope_keywords = {
            'admin dashboard': ['admin', 'dashboard'],
            'email notifications': ['email', 'notification'],
            'slack': ['slack'],
            'payment': ['payment'],
            'video streaming': ['video', 'streaming'],
            'mobile app': ['mobile', 'app'],
            'monitoring dashboard': ['monitoring', 'dashboard'],
            'analytics': ['analytics'],
            'marketing': ['marketing']
        }

        for feature_name, keywords in out_of_scope_keywords.items():
            # Check if feature_name is in OUT OF SCOPE section
            if feature_name in out_of_scope_section or any(kw in out_of_scope_section for kw in keywords):
                # Check if description matches this out-of-scope feature
                if all(kw in description for kw in keywords):
                    return True

        return False

    def validate_alignment(self, feature: str, project_goals: str) -> Tuple[bool, str]:
        """
        Validate if feature aligns with project goals.

        Args:
            feature: Feature description
            project_goals: Project goals from PROJECT.md

        Returns:
            Tuple of (is_aligned, reason)

        Note: This is a mock implementation for testing.
        Real validation happens through Claude Code agent invocation.
        """
        # Mock alignment validation for testing
        # Real implementation would invoke the agent through Claude Code

        # Simple keyword matching for testing
        feature_lower = feature.lower()
        goals_lower = project_goals.lower()

        # Check for alignment keywords
        if any(keyword in feature_lower for keyword in ['auth', 'security', 'user']):
            if any(keyword in goals_lower for keyword in ['auth', 'security', 'user']):
                return True, "Feature aligns with security and authentication goals."

        if any(keyword in feature_lower for keyword in ['performance', 'optimize', 'speed']):
            if any(keyword in goals_lower for keyword in ['performance', 'optimize', 'speed']):
                return True, "Feature aligns with performance optimization goals."

        if any(keyword in feature_lower for keyword in ['test', 'quality', 'coverage']):
            if any(keyword in goals_lower for keyword in ['test', 'quality', 'coverage']):
                return True, "Feature aligns with testing and quality goals."

        # Default alignment for common cases
        if 'improve' in feature_lower or 'add' in feature_lower or 'implement' in feature_lower:
            return True, "Feature contributes to project goals."

        return False, "Feature does not clearly align with stated project goals."
