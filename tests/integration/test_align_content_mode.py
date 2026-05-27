"""Integration tests for /align --content mode (Issue #1123).

Validates that the new `--content` sub-flag is wired into:
- the align command (Mode 4 section, modes table, mode detection, when-to-use table)
- the content-allocation skill (frontmatter, trigger language, size budget)
- the templates (CONTENT_ALLOCATION.md, CLAUDE.md.template)
- the install manifest (skills + templates entries)

These tests are spec-blind: they check shipped artifacts against the plan, not
the implementer's behaviour.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Repo root: tests/integration/test_X.py -> parents[2]
REPO_ROOT = Path(__file__).resolve().parents[2]

ALIGN_COMMAND_PATH = REPO_ROOT / "plugins/autonomous-dev/commands/align.md"
SKILL_PATH = REPO_ROOT / "plugins/autonomous-dev/skills/content-allocation/SKILL.md"
TEMPLATE_CONTENT_ALLOCATION = (
    REPO_ROOT / "plugins/autonomous-dev/templates/CONTENT_ALLOCATION.md"
)
TEMPLATE_CLAUDE_MD = REPO_ROOT / "plugins/autonomous-dev/templates/CLAUDE.md.template"
MANIFEST_PATH = REPO_ROOT / "plugins/autonomous-dev/config/install_manifest.json"


# ---------------------------------------------------------------------------
# TestAlignContentCommandRouting (4 tests)
# ---------------------------------------------------------------------------


class TestAlignContentCommandRouting:
    """The /align command file MUST route --content to Mode 4."""

    @pytest.fixture
    def align_content(self) -> str:
        assert ALIGN_COMMAND_PATH.exists(), f"Missing: {ALIGN_COMMAND_PATH}"
        return ALIGN_COMMAND_PATH.read_text()

    def test_align_md_has_mode4_section(self, align_content: str) -> None:
        """align.md MUST contain a Mode 4 section for content allocation."""
        assert "## Mode 4: Content Allocation" in align_content, (
            "align.md is missing the 'Mode 4: Content Allocation' section."
        )

    def test_modes_table_includes_content(self, align_content: str) -> None:
        """The modes bullet block MUST list /align --content."""
        assert "/align --content" in align_content, (
            "align.md does not advertise /align --content in the modes list."
        )

    def test_mode_detection_has_elif_content(self, align_content: str) -> None:
        """Mode Detection pseudocode MUST branch on the --content flag."""
        assert "ELIF --content flag:" in align_content, (
            "align.md Mode Detection block is missing the ELIF --content branch."
        )

    def test_when_to_use_table_has_content_row(self, align_content: str) -> None:
        """The 'When to Use Each Mode' table MUST include a --content row."""
        # Match the table row syntax used elsewhere in the file
        assert "| `/align --content` |" in align_content, (
            "align.md 'When to Use Each Mode' table has no row for /align --content."
        )


# ---------------------------------------------------------------------------
# TestContentAllocationSkillLoad (4 tests)
# ---------------------------------------------------------------------------


class TestContentAllocationSkillLoad:
    """The content-allocation skill MUST be installable and well-formed."""

    @pytest.fixture
    def skill_text(self) -> str:
        assert SKILL_PATH.exists(), f"Missing skill file: {SKILL_PATH}"
        return SKILL_PATH.read_text()

    def test_skill_file_exists(self) -> None:
        assert SKILL_PATH.is_file(), (
            f"content-allocation/SKILL.md must exist at {SKILL_PATH}"
        )

    def test_frontmatter_has_required_keys(self, skill_text: str) -> None:
        """Frontmatter MUST have name=content-allocation + description + allowed-tools."""
        # Crude but reliable frontmatter extraction
        assert skill_text.startswith("---\n"), "SKILL.md must start with --- fence"
        end = skill_text.find("\n---\n", 4)
        assert end != -1, "SKILL.md frontmatter not closed"
        frontmatter = skill_text[4:end]

        assert "name: content-allocation" in frontmatter, (
            "Frontmatter missing 'name: content-allocation'"
        )
        assert "description:" in frontmatter, "Frontmatter missing description"
        assert "allowed-tools:" in frontmatter, "Frontmatter missing allowed-tools"

    def test_description_has_trigger_phrases(self, skill_text: str) -> None:
        """The description field MUST contain both TRIGGER and DO NOT TRIGGER guidance."""
        end = skill_text.find("\n---\n", 4)
        frontmatter = skill_text[4:end]
        assert "TRIGGER when:" in frontmatter, (
            "Description missing 'TRIGGER when:' clause"
        )
        assert "DO NOT TRIGGER when:" in frontmatter, (
            "Description missing 'DO NOT TRIGGER when:' clause"
        )

    def test_skill_body_within_hard_ceiling(self, skill_text: str) -> None:
        """Skill body (after frontmatter) MUST be <= 500 lines (HARD CEILING)."""
        end = skill_text.find("\n---\n", 4)
        body = skill_text[end + len("\n---\n") :]
        line_count = body.count("\n") + (0 if body.endswith("\n") else 1)
        assert line_count <= 500, (
            f"SKILL.md body is {line_count} lines, exceeds HARD CEILING of 500."
        )


# ---------------------------------------------------------------------------
# TestTemplateDropIdempotency (4 tests)
# ---------------------------------------------------------------------------


class TestTemplateDropIdempotency:
    """Templates ship in the plugin and follow install.py's skip-when-exists policy."""

    def test_content_allocation_template_exists(self) -> None:
        assert TEMPLATE_CONTENT_ALLOCATION.is_file(), (
            f"Missing template: {TEMPLATE_CONTENT_ALLOCATION}"
        )

    def test_claude_md_template_exists(self) -> None:
        assert TEMPLATE_CLAUDE_MD.is_file(), f"Missing template: {TEMPLATE_CLAUDE_MD}"

    def test_install_skip_when_target_exists(self, tmp_path: Path) -> None:
        """Simulates install.py default mode: skip when target already exists.

        Mirrors the `if target_path.exists(): self.stats['skipped'] += 1; continue`
        branch in plugins/autonomous-dev/scripts/install.py around lines 540-543.
        """
        target = tmp_path / "CONTENT_ALLOCATION.md"
        target.write_text("USER CUSTOMIZATION — must not be overwritten\n")
        original = target.read_text()

        # Default install mode: skip when target exists
        skipped = 0
        if target.exists():
            skipped += 1
        else:
            target.write_bytes(TEMPLATE_CONTENT_ALLOCATION.read_bytes())

        assert skipped == 1, "Expected install.py-style skip when target exists"
        assert target.read_text() == original, (
            "User customization must be preserved on install"
        )

    def test_install_drop_when_target_missing(self, tmp_path: Path) -> None:
        """Simulates install.py default mode: drop the template when missing."""
        target = tmp_path / "CONTENT_ALLOCATION.md"
        assert not target.exists()

        # Default install mode: write when missing
        downloaded = 0
        if target.exists():
            pass
        else:
            target.write_bytes(TEMPLATE_CONTENT_ALLOCATION.read_bytes())
            downloaded += 1

        assert downloaded == 1, "Expected install.py-style write when target missing"
        assert target.exists() and target.stat().st_size > 0, (
            "Template content must land at target"
        )
        assert "# Content allocation" in target.read_text(), (
            "Dropped file must contain the expected template content"
        )


# ---------------------------------------------------------------------------
# TestInstallManifestEntries (2 tests)
# ---------------------------------------------------------------------------


class TestInstallManifestEntries:
    """install_manifest.json MUST list the new templates and skill."""

    @pytest.fixture
    def manifest(self) -> dict:
        return json.loads(MANIFEST_PATH.read_text())

    def test_manifest_templates_lists_new_files(self, manifest: dict) -> None:
        templates = manifest["components"]["templates"]["files"]
        assert (
            "plugins/autonomous-dev/templates/CLAUDE.md.template" in templates
        ), "manifest templates.files missing CLAUDE.md.template"
        assert (
            "plugins/autonomous-dev/templates/CONTENT_ALLOCATION.md" in templates
        ), "manifest templates.files missing CONTENT_ALLOCATION.md"

    def test_manifest_skills_lists_content_allocation(self, manifest: dict) -> None:
        skills = manifest["components"]["skills"]["files"]
        assert (
            "plugins/autonomous-dev/skills/content-allocation/SKILL.md" in skills
        ), "manifest skills.files missing content-allocation/SKILL.md"
