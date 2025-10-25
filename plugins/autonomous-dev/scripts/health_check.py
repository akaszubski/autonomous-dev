#!/usr/bin/env python3
"""
Plugin health check utility.

Validates all autonomous-dev plugin components:
- Agents (8 specialist agents)
- Hooks (8 automation hooks)
- Commands (8 core commands)

Note: Skills removed per Issue #5 (PROJECT.md: "No skills/ directory - anti-pattern")

Usage:
    python health_check.py
    python health_check.py --verbose
    python health_check.py --json  # Machine-readable output
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class PluginHealthCheck:
    """Validates autonomous-dev plugin component integrity."""

    # Expected components (from PROJECT.md)
    EXPECTED_AGENTS = [
        "orchestrator",
        "planner",
        "researcher",
        "test-master",
        "implementer",
        "reviewer",
        "security-auditor",
        "doc-master",
    ]

    # Skills removed per Issue #5 - PROJECT.md: "No skills/ directory - anti-pattern"
    EXPECTED_SKILLS = []

    EXPECTED_HOOKS = [
        "auto_format.py",
        "auto_test.py",
        "auto_generate_tests.py",
        "auto_tdd_enforcer.py",
        "auto_add_to_regression.py",
        "auto_enforce_coverage.py",
        "auto_update_docs.py",
        "security_scan.py",
    ]

    EXPECTED_COMMANDS = [
        "align-project.md",
        "auto-implement.md",
        "health-check.md",  # Self-reference
        "setup.md",
        "status.md",
        "test.md",
        "uninstall.md",
    ]

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.plugin_dir = self._find_plugin_dir()
        self.results = {
            "agents": {},
            "skills": {},
            "hooks": {},
            "commands": {},
            "overall": "UNKNOWN",
        }

    def _find_plugin_dir(self) -> Path:
        """Find the plugin directory."""
        # Try ~/.claude/plugins/autonomous-dev
        home_plugin = Path.home() / ".claude" / "plugins" / "autonomous-dev"
        if home_plugin.exists():
            return home_plugin

        # Try current directory structure
        cwd_plugin = Path.cwd() / "plugins" / "autonomous-dev"
        if cwd_plugin.exists():
            return cwd_plugin

        print("❌ Plugin directory not found!", file=sys.stderr)
        print(f"Checked: {home_plugin}", file=sys.stderr)
        print(f"Checked: {cwd_plugin}", file=sys.stderr)
        sys.exit(1)

    def check_component_exists(
        self, component_type: str, component_name: str, file_extension: str = ".md"
    ) -> bool:
        """Check if a component file exists."""
        component_path = (
            self.plugin_dir / component_type / f"{component_name}{file_extension}"
        )
        return component_path.exists()

    def validate_agents(self) -> Tuple[int, int]:
        """Validate all agents exist and are loadable."""
        passed = 0
        for agent in self.EXPECTED_AGENTS:
            exists = self.check_component_exists("agents", agent, ".md")
            self.results["agents"][agent] = "PASS" if exists else "FAIL"
            if exists:
                passed += 1
        return passed, len(self.EXPECTED_AGENTS)

    def validate_skills(self) -> Tuple[int, int]:
        """Validate all skills exist and are loadable.

        Note: Skills removed per Issue #5 - PROJECT.md states
        "No skills/ directory - anti-pattern". Returns (0, 0).
        """
        # Skills intentionally removed - no validation needed
        return 0, 0

    def validate_hooks(self) -> Tuple[int, int]:
        """Validate all hooks exist and are executable."""
        passed = 0
        for hook in self.EXPECTED_HOOKS:
            hook_path = self.plugin_dir / "hooks" / hook
            exists = hook_path.exists()
            executable = hook_path.is_file() and hook_path.stat().st_mode & 0o111
            self.results["hooks"][hook] = "PASS" if exists else "FAIL"
            if exists:
                passed += 1
        return passed, len(self.EXPECTED_HOOKS)

    def validate_commands(self) -> Tuple[int, int]:
        """Validate all commands exist."""
        passed = 0
        for command in self.EXPECTED_COMMANDS:
            exists = self.check_component_exists("commands", command.replace(".md", ""), ".md")
            self.results["commands"][command.replace(".md", "")] = (
                "PASS" if exists else "FAIL"
            )
            if exists:
                passed += 1
        return passed, len(self.EXPECTED_COMMANDS)

    def print_report(self):
        """Print human-readable health check report."""
        print("\nRunning plugin health check...\n")
        print("=" * 60)
        print("PLUGIN HEALTH CHECK REPORT")
        print("=" * 60)
        print()

        # Agents
        agent_pass, agent_total = self.validate_agents()
        print(f"Agents: {agent_pass}/{agent_total} loaded")
        for agent, status in self.results["agents"].items():
            dots = "." * (30 - len(agent))
            print(f"  {agent} {dots} {status}")
        print()

        # Skills - removed per Issue #5
        skill_pass, skill_total = self.validate_skills()
        # Skills section intentionally removed - no output

        # Hooks
        hook_pass, hook_total = self.validate_hooks()
        print(f"Hooks: {hook_pass}/{hook_total} executable")
        for hook, status in self.results["hooks"].items():
            dots = "." * (30 - len(hook))
            print(f"  {hook} {dots} {status}")
        print()

        # Commands
        cmd_pass, cmd_total = self.validate_commands()
        print(f"Commands: {cmd_pass}/{cmd_total} present")
        for cmd, status in list(self.results["commands"].items())[:10]:
            dots = "." * (30 - len(cmd))
            print(f"  /{cmd} {dots} {status}")
        if cmd_total > 10:
            print(f"  ... and {cmd_total - 10} more")
        print()

        # Overall status
        total_issues = (
            (agent_total - agent_pass)
            + (hook_total - hook_pass)
            + (cmd_total - cmd_pass)
        )
        # Note: skills intentionally excluded (removed per Issue #5)

        print("=" * 60)
        if total_issues == 0:
            print("OVERALL STATUS: HEALTHY")
            self.results["overall"] = "HEALTHY"
        else:
            print(f"OVERALL STATUS: DEGRADED ({total_issues} issues found)")
            self.results["overall"] = "DEGRADED"
        print("=" * 60)
        print()

        if total_issues == 0:
            print("✅ All plugin components are functioning correctly!")
        else:
            print("⚠️  Issues detected:")
            issue_num = 1
            for component_type in ["agents", "hooks", "commands"]:  # skills removed
                for name, status in self.results[component_type].items():
                    if status == "FAIL":
                        component_path = f"~/.claude/plugins/autonomous-dev/{component_type}/{name}"
                        if component_type in ["agents", "commands"]:
                            component_path += ".md"
                        elif component_type == "hooks":
                            component_path += ""
                        print(f"  {issue_num}. {component_type[:-1].title()} '{name}' missing: {component_path}")
                        issue_num += 1

            print("\n💡 Action: Reinstall plugin")
            print("   /plugin uninstall autonomous-dev")
            print("   /plugin install autonomous-dev")

        print()

    def print_json(self):
        """Print machine-readable JSON output."""
        # Run all validations first
        agent_pass, agent_total = self.validate_agents()
        skill_pass, skill_total = self.validate_skills()  # Returns (0, 0)
        hook_pass, hook_total = self.validate_hooks()
        cmd_pass, cmd_total = self.validate_commands()

        # Calculate overall status (skills excluded - removed per Issue #5)
        total_issues = (
            (agent_total - agent_pass)
            + (hook_total - hook_pass)
            + (cmd_total - cmd_pass)
        )

        self.results["overall"] = "HEALTHY" if total_issues == 0 else "DEGRADED"

        print(json.dumps(self.results, indent=2))

    def run(self, output_format: str = "text"):
        """Run health check."""
        if output_format == "json":
            self.print_json()
        else:
            self.print_report()

        # Exit code based on overall status
        sys.exit(0 if self.results["overall"] == "HEALTHY" else 1)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Plugin health check utility")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--json", action="store_true", help="JSON output format")
    args = parser.parse_args()

    checker = PluginHealthCheck(verbose=args.verbose)
    checker.run(output_format="json" if args.json else "text")


if __name__ == "__main__":
    main()
