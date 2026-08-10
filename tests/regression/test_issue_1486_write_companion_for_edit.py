"""Regression test for Issue #1486: settings generator must emit Write(<path>)
companion for every non-protected Edit(<path>) permission rule.

Edit and Write are distinct permission grants in Claude Code:
- Edit covers modifying an existing file
- Write covers creating a new one

Without the Write companion, creating a brand-new file at an otherwise-safe
content path (e.g. a new plan file, a new doc) triggers a live permission
prompt every time even though the path is trusted for Edit.

Protected-infrastructure paths (agents/, commands/, hooks/, lib/, skills/)
are EXCLUDED from the companion — those must be modified only via
/implement (enforced by unified_pre_tool.py) and a Write companion would
defeat the block.

The converse (Write without Edit) is intentionally NOT required — some
paths may be write-once/append-only.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from settings_generator import (  # noqa: E402
    DEFAULT_DENY_LIST,
    PROTECTED_INFRASTRUCTURE_PATTERNS,
    SettingsGenerator,
    _extract_path,
    _is_protected_infrastructure_path,
    add_write_companions,
)

_EDIT_PATH_RE = re.compile(r"^Edit\((.+)\)$")
_WRITE_PATH_RE = re.compile(r"^Write\((.+)\)$")

TEMPLATE_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "templates"
GLOBAL_TEMPLATE = (
    REPO_ROOT / "plugins" / "autonomous-dev" / "config" / "global_settings_template.json"
)


def _edit_paths(patterns: list[str]) -> set[str]:
    out: set[str] = set()
    for p in patterns:
        m = _EDIT_PATH_RE.match(p)
        if m:
            out.add(m.group(1))
    return out


def _write_paths(patterns: list[str]) -> set[str]:
    out: set[str] = set()
    for p in patterns:
        m = _WRITE_PATH_RE.match(p)
        if m:
            out.add(m.group(1))
    return out


class TestExtractPath:
    def test_extracts_edit_path(self) -> None:
        assert _extract_path("Edit(.claude/plans/*.md)") == ".claude/plans/*.md"

    def test_extracts_write_path(self) -> None:
        assert _extract_path("Write(~/.ssh/**)") == "~/.ssh/**"

    def test_bare_tool_returns_none(self) -> None:
        assert _extract_path("Edit") is None
        assert _extract_path("Write") is None

    def test_non_edit_or_write_returns_none(self) -> None:
        assert _extract_path("Read(./.env)") is None
        assert _extract_path("Bash(git:*)") is None


class TestProtectedInfrastructure:
    @pytest.mark.parametrize(
        "path",
        [
            "agents/*.md",
            "commands/*.md",
            "hooks/*.py",
            "lib/*.py",
            "skills/*/SKILL.md",
            "plugins/autonomous-dev/agents/*.md",
            "plugins/autonomous-dev/hooks/unified_pre_tool.py",
        ],
    )
    def test_protected_paths_detected(self, path: str) -> None:
        assert _is_protected_infrastructure_path(path)

    @pytest.mark.parametrize(
        "path",
        [
            ".claude/plans/*.md",
            "docs/*.md",
            "tests/**/*.py",
            "README.md",
            "CHANGELOG.md",
        ],
    )
    def test_content_paths_not_protected(self, path: str) -> None:
        assert not _is_protected_infrastructure_path(path)


class TestAddWriteCompanions:
    def test_edit_gets_write_companion(self) -> None:
        patterns = ["Edit(.claude/plans/*.md)"]
        out = add_write_companions(patterns)
        assert "Edit(.claude/plans/*.md)" in out
        assert "Write(.claude/plans/*.md)" in out

    def test_protected_infrastructure_gets_no_write(self) -> None:
        patterns = ["Edit(agents/*.md)", "Edit(hooks/*.py)", "Edit(lib/*.py)"]
        out = add_write_companions(patterns)
        # Edit rules preserved as-is
        for p in patterns:
            assert p in out
        # No Write companion added for protected paths
        assert "Write(agents/*.md)" not in out
        assert "Write(hooks/*.py)" not in out
        assert "Write(lib/*.py)" not in out

    def test_bare_edit_untouched(self) -> None:
        patterns = ["Edit", "Write", "Read"]
        out = add_write_companions(patterns)
        assert out.count("Write") == 1  # not duplicated
        assert "Edit" in out
        assert "Read" in out

    def test_existing_write_not_duplicated(self) -> None:
        patterns = ["Edit(docs/*.md)", "Write(docs/*.md)"]
        out = add_write_companions(patterns)
        assert out.count("Write(docs/*.md)") == 1

    def test_write_without_edit_preserved(self) -> None:
        # The converse invariant is not required — Write without Edit is valid
        patterns = ["Write(logs/*.log)"]
        out = add_write_companions(patterns)
        assert out == ["Write(logs/*.log)"]

    def test_empty_list_returns_empty(self) -> None:
        assert add_write_companions([]) == []


class TestGeneratedSettingsInvariant:
    """Every non-protected Edit(<path>) in generated settings must have a
    matching Write(<path>). Also verify the deny list carries Write
    companions for every path-scoped Edit deny."""

    def test_default_deny_list_has_write_companion_for_every_edit(self) -> None:
        edits = _edit_paths(DEFAULT_DENY_LIST)
        writes = _write_paths(DEFAULT_DENY_LIST)
        # Every Edit(<path>) in deny must have a matching Write(<path>).
        # These are sensitive paths — bypassing Edit-deny by creating a new
        # file is a security gap the companion closes.
        missing = edits - writes
        assert not missing, (
            f"DEFAULT_DENY_LIST has Edit(<path>) entries without matching "
            f"Write(<path>): {sorted(missing)}"
        )

    def test_generate_settings_output_has_write_companion(self, tmp_path: Path) -> None:
        # Use the real plugin directory (canonical autonomous-dev source)
        plugin_dir = REPO_ROOT / "plugins" / "autonomous-dev"
        generator = SettingsGenerator(plugin_dir)
        settings = generator.generate_settings()

        allow = settings["permissions"]["allow"]
        edits = _edit_paths(allow)
        writes = _write_paths(allow)

        # Every non-protected Edit(<path>) in allow must have a matching
        # Write(<path>).
        for path in edits:
            if _is_protected_infrastructure_path(path):
                # Protected paths intentionally get no Write companion
                assert f"Write({path})" not in allow, (
                    f"protected path {path!r} must NOT have a Write companion"
                )
            else:
                assert path in writes, (
                    f"Edit({path}) missing Write({path}) companion in "
                    f"generated allow list"
                )

    def test_merge_preserves_write_companion_invariant(self) -> None:
        plugin_dir = REPO_ROOT / "plugins" / "autonomous-dev"
        generator = SettingsGenerator(plugin_dir)

        # Simulate a user config that adds an Edit(<content-path>) rule
        user_settings = {
            "permissions": {
                "allow": ["Edit(.claude/plans/*.md)"],
                "deny": [],
            },
        }
        merged = generator.generate_settings(merge_with=user_settings)
        allow = merged["permissions"]["allow"]

        assert "Edit(.claude/plans/*.md)" in allow
        assert "Write(.claude/plans/*.md)" in allow, (
            "user-supplied Edit(<content-path>) must gain a Write companion "
            "during merge"
        )


class TestTemplateFilesHaveWriteCompanion:
    """Every template JSON file's deny list must carry Write(<path>)
    companions for its path-scoped Edit(<path>) entries."""

    TEMPLATE_FILES = [
        "settings.default.json",
        "settings.autonomous-dev.json",
        "settings.local.json",
        "settings.granular-bash.json",
        "settings.strict-mode.json",
        "settings.permission-batching.json",
    ]

    @pytest.mark.parametrize("template_name", TEMPLATE_FILES)
    def test_template_deny_edit_has_write_companion(self, template_name: str) -> None:
        template_path = TEMPLATE_DIR / template_name
        data = json.loads(template_path.read_text())
        deny = data.get("permissions", {}).get("deny", [])
        edits = _edit_paths(deny)
        writes = _write_paths(deny)
        missing = edits - writes
        assert not missing, (
            f"{template_name} deny list has Edit(<path>) entries without "
            f"matching Write(<path>) companion: {sorted(missing)}"
        )

    def test_global_settings_template_deny_edit_has_write_companion(self) -> None:
        data = json.loads(GLOBAL_TEMPLATE.read_text())
        deny = data.get("permissions", {}).get("deny", [])
        edits = _edit_paths(deny)
        writes = _write_paths(deny)
        missing = edits - writes
        assert not missing, (
            f"global_settings_template.json deny list has Edit(<path>) "
            f"entries without matching Write(<path>): {sorted(missing)}"
        )


def test_protected_infrastructure_patterns_are_stable() -> None:
    # Lock the exact set of protected prefixes so future refactors don't
    # silently narrow or widen the protection.
    assert PROTECTED_INFRASTRUCTURE_PATTERNS == (
        "agents/",
        "commands/",
        "hooks/",
        "lib/",
        "skills/",
    )
