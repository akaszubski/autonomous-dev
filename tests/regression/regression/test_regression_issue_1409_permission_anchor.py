"""Regression test for Issue #1409: Write(path) deny no-ops + single-slash anchor.

Two coupled, primary-source-verified bugs in permission rules:

1. **Tool-name**: ``Write(path)`` / ``NotebookEdit(path)`` / ``Glob(path)`` file
   rules are never matched by Claude Code — only ``Edit(path)`` and ``Read(path)``
   match. Every ``Write(...)`` deny rule was a startup-warning no-op.
2. **Anchor**: a single leading slash ``/etc/**`` anchors to the settings *source*
   directory (``~/.claude/etc/**``), not the filesystem root. Real absolute-path
   protection requires a double leading slash: ``//etc/**``.

This is a static class-guard: it parses the canonical ``DEFAULT_DENY_LIST`` plus
the six shipped templates and the global settings template, and asserts the
migration held across every source. No LLM, no runtime — durable structural
assertions.

Fixes #1409.
"""

import json
import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEMPLATES_DIR = PROJECT_ROOT / "plugins/autonomous-dev/templates"
CONFIG_DIR = PROJECT_ROOT / "plugins/autonomous-dev/config"
LIB_DIR = PROJECT_ROOT / "plugins/autonomous-dev/lib"
GLOBAL_TEMPLATE = CONFIG_DIR / "global_settings_template.json"

# Tool-name prefixes that Claude Code silently ignores for file-path rules.
FORBIDDEN_TOOL_PREFIXES = ("Write(", "NotebookEdit(", "Glob(")

# The exact four corrected deny rules expected in DEFAULT_DENY_LIST.
EXPECTED_DEFAULT_DENY_EDIT_RULES = {
    "Edit(//etc/**)",
    "Edit(//System/**)",
    "Edit(//usr/**)",
    "Edit(~/.ssh/**)",
}

# System-root paths that MUST use a double leading slash after migration.
SYSROOT_PAIRS = [
    ("Edit(//etc/**)", "Edit(/etc/**)"),
    ("Edit(//System/**)", "Edit(/System/**)"),
    ("Edit(//usr/**)", "Edit(/usr/**)"),
]

# An absolute Edit rule with exactly ONE leading slash before a non-slash char.
SINGLE_SLASH_ABS_EDIT_RE = re.compile(r"^Edit\(/[^/]")


def _load_default_deny_list() -> list:
    """Import DEFAULT_DENY_LIST from the canonical settings_generator module.

    Returns:
        The canonical deny list as a list of rule strings.
    """
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    from settings_generator import DEFAULT_DENY_LIST

    return list(DEFAULT_DENY_LIST)


def _iter_permission_rules(source_paths: list) -> list:
    """Collect (source_name, list_name, rule) triples from allow + deny lists.

    Args:
        source_paths: JSON settings files to inspect.

    Returns:
        List of (source_name, list_name, rule) tuples.
    """
    rules = []
    for path in source_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        perms = data.get("permissions", {})
        for list_name in ("allow", "deny"):
            for rule in perms.get(list_name, []):
                rules.append((path.name, list_name, rule))
    return rules


def _all_json_sources() -> list:
    """Return the six templates plus the global settings template."""
    return sorted(TEMPLATES_DIR.glob("settings.*.json")) + [GLOBAL_TEMPLATE]


class TestIssue1409PermissionAnchor:
    """Static guard: no ignored tool-name rules, no single-slash absolute paths."""

    def test_no_ignored_tool_name_rules_in_json_sources(self):
        """No allow/deny rule in any template or global template starts with an
        ignored tool prefix (Write(, NotebookEdit(, Glob()."""
        violations = []
        for source_name, list_name, rule in _iter_permission_rules(_all_json_sources()):
            if rule.startswith(FORBIDDEN_TOOL_PREFIXES):
                violations.append(f"{source_name} [{list_name}]: {rule}")
        assert not violations, (
            "Ignored tool-name file rules found (Claude Code silently drops these):\n"
            + "\n".join(violations)
        )

    def test_default_deny_list_has_no_ignored_tool_name_rules(self):
        """DEFAULT_DENY_LIST contains zero Write(/NotebookEdit(/Glob( rules."""
        deny = _load_default_deny_list()
        violations = [r for r in deny if r.startswith(FORBIDDEN_TOOL_PREFIXES)]
        assert not violations, (
            "DEFAULT_DENY_LIST still has ignored tool-name rules: " + repr(violations)
        )

    def test_default_deny_list_contains_corrected_edit_rules(self):
        """DEFAULT_DENY_LIST contains exactly the four migrated Edit rules."""
        deny = set(_load_default_deny_list())
        missing = EXPECTED_DEFAULT_DENY_EDIT_RULES - deny
        assert not missing, f"DEFAULT_DENY_LIST missing corrected rules: {missing}"

    def test_sysroot_rules_use_double_slash_in_default_deny_list(self):
        """Migrated system-root deny rules use // (double slash), never single /."""
        deny = set(_load_default_deny_list())
        for double_slash, single_slash in SYSROOT_PAIRS:
            assert double_slash in deny, f"Expected {double_slash} in DEFAULT_DENY_LIST"
            assert single_slash not in deny, (
                f"Single-slash {single_slash} still present — anchors to settings "
                f"source, not filesystem root"
            )

    def test_no_single_slash_absolute_edit_rule_across_sources(self):
        """No Edit(/...) rule with exactly one leading slash survives anywhere.

        A single leading slash anchors to the settings source directory; absolute
        system paths must use two leading slashes.
        """
        violations = []
        all_rules = _iter_permission_rules(_all_json_sources())
        all_rules += [("DEFAULT_DENY_LIST", "deny", r) for r in _load_default_deny_list()]
        for source_name, list_name, rule in all_rules:
            if SINGLE_SLASH_ABS_EDIT_RE.match(rule):
                violations.append(f"{source_name} [{list_name}]: {rule}")
        assert not violations, (
            "Single-slash absolute Edit rules found (must use // for real root):\n"
            + "\n".join(violations)
        )

    def test_sysroot_double_slash_present_in_global_template(self):
        """Global settings template deny list carries the // system-root rules."""
        data = json.loads(GLOBAL_TEMPLATE.read_text(encoding="utf-8"))
        deny = set(data.get("permissions", {}).get("deny", []))
        for double_slash, single_slash in SYSROOT_PAIRS:
            assert double_slash in deny, f"global template missing {double_slash}"
            assert single_slash not in deny, f"global template still has {single_slash}"
