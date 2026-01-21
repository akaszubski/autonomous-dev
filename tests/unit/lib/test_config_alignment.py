#!/usr/bin/env python3
"""
Regression Test for Issue #257: Config Alignment Validation

Validates that project-local config (.claude/config/auto_approve_policy.json)
has the same core file tools as the plugin template.

BUG THAT OCCURRED:
- Project-local config was missing Read, Write, Edit, Glob, Grep from tools.always_allowed
- Plugin template had them correctly
- This caused prompts for basic file operations

This test ensures the two configs stay aligned on core file tools.

Run with: pytest tests/unit/lib/test_config_alignment.py -v

Issue: GitHub #257
Date: 2026-01-21
"""

import json
from pathlib import Path

import pytest


# Paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
PROJECT_LOCAL_CONFIG = PROJECT_ROOT / ".claude/config/auto_approve_policy.json"
PLUGIN_TEMPLATE_CONFIG = (
    PROJECT_ROOT / "plugins/autonomous-dev/config/auto_approve_policy.json"
)


# Core file tools that MUST be in always_allowed to avoid prompts
REQUIRED_CORE_TOOLS = [
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
]


@pytest.fixture
def project_config():
    """Load the project-local auto_approve_policy.json."""
    if not PROJECT_LOCAL_CONFIG.exists():
        pytest.skip(
            f"Project-local config not found: {PROJECT_LOCAL_CONFIG}\n"
            "This is expected in worktree environments."
        )
    with open(PROJECT_LOCAL_CONFIG) as f:
        return json.load(f)


@pytest.fixture
def plugin_config():
    """Load the plugin template auto_approve_policy.json."""
    if not PLUGIN_TEMPLATE_CONFIG.exists():
        pytest.fail(
            f"Plugin template config not found: {PLUGIN_TEMPLATE_CONFIG}\n"
            "This file must exist in the plugin."
        )
    with open(PLUGIN_TEMPLATE_CONFIG) as f:
        return json.load(f)


class TestConfigAlignment:
    """Regression tests for config alignment (Issue #257)."""

    def test_project_config_has_required_core_tools(self, project_config):
        """
        Project-local config must have core file tools in always_allowed.

        Regression test for Issue #257 where Read, Write, Edit, Glob, Grep
        were missing, causing prompts for basic file operations.
        """
        always_allowed = project_config.get("tools", {}).get("always_allowed", [])

        missing_tools = [tool for tool in REQUIRED_CORE_TOOLS if tool not in always_allowed]

        assert not missing_tools, (
            f"Project-local config missing required core tools: {missing_tools}\n"
            f"Config path: {PROJECT_LOCAL_CONFIG}\n"
            f"This will cause prompts for basic file operations!\n"
            f"Required tools: {REQUIRED_CORE_TOOLS}"
        )

    def test_plugin_template_has_required_core_tools(self, plugin_config):
        """
        Plugin template config must have core file tools in always_allowed.

        Ensures the plugin template stays correct and doesn't regress.
        """
        always_allowed = plugin_config.get("tools", {}).get("always_allowed", [])

        missing_tools = [tool for tool in REQUIRED_CORE_TOOLS if tool not in always_allowed]

        assert not missing_tools, (
            f"Plugin template missing required core tools: {missing_tools}\n"
            f"Config path: {PLUGIN_TEMPLATE_CONFIG}\n"
            f"Required tools: {REQUIRED_CORE_TOOLS}"
        )

    def test_configs_have_same_core_tools(self, project_config, plugin_config):
        """
        Project-local and plugin template configs must have same core file tools.

        This ensures they stay aligned on the critical tools that should
        never prompt users.
        """
        project_tools = set(project_config.get("tools", {}).get("always_allowed", []))
        plugin_tools = set(plugin_config.get("tools", {}).get("always_allowed", []))

        # Core tools are the intersection of required tools
        project_core = project_tools & set(REQUIRED_CORE_TOOLS)
        plugin_core = plugin_tools & set(REQUIRED_CORE_TOOLS)

        missing_from_project = plugin_core - project_core
        missing_from_plugin = project_core - plugin_core

        assert not missing_from_project and not missing_from_plugin, (
            f"Core file tools misalignment detected:\n"
            f"  Missing from project config: {missing_from_project}\n"
            f"  Missing from plugin template: {missing_from_plugin}\n"
            f"Both configs must have these core tools: {REQUIRED_CORE_TOOLS}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
