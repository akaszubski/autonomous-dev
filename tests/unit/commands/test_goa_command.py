"""Tests for /goa command file — Issue #1320."""

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_goa_command_frontmatter_valid() -> None:
    """Issue #1320 — /goa command file exists with valid frontmatter."""
    goa_path = PROJECT_ROOT / "plugins/autonomous-dev/commands/goa.md"
    assert goa_path.exists(), f"Missing: {goa_path}"
    text = goa_path.read_text(encoding="utf-8")
    # Extract frontmatter between --- markers
    assert text.startswith("---"), "Missing frontmatter"
    end_idx = text.find("---", 3)
    assert end_idx > 0, "Frontmatter closing --- not found"
    frontmatter = yaml.safe_load(text[3:end_idx])
    assert frontmatter["name"] == "goa"
    assert frontmatter["user-invocable"] is True
    assert frontmatter["user_facing"] is True
    assert "Bash" in frontmatter["allowed-tools"]
