"""
Documentation Consistency Tests - Layer 1 Defense Against Documentation Drift

This test suite ensures that documentation (especially README.md) stays in sync
with the actual codebase. If these tests fail, it means documentation is out of date.

Purpose:
- Catch documentation drift automatically in CI/CD
- Prevent README.md from showing incorrect counts (agents, skills, commands)
- Ensure all referenced files actually exist
- Validate cross-references between documents

Part of 4-layer consistency enforcement strategy.
"""

import sys
from pathlib import Path
import re

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestREADMEConsistency:
    """Test README.md matches actual codebase state."""

    @pytest.fixture
    def readme_path(self):
        """Path to main README.md."""
        return Path(__file__).parent.parent / "README.md"

    @pytest.fixture
    def readme_content(self, readme_path):
        """README.md content."""
        return readme_path.read_text()

    @pytest.fixture
    def skills_dir(self):
        """Path to skills directory."""
        return Path(__file__).parent.parent / "skills"

    @pytest.fixture
    def agents_dir(self):
        """Path to agents directory."""
        return Path(__file__).parent.parent / "agents"

    @pytest.fixture
    def commands_dir(self):
        """Path to commands directory."""
        return Path(__file__).parent.parent / "commands"

    def test_readme_skill_count_matches_actual(self, readme_content, skills_dir):
        """Test README.md skill count matches actual skills directory.

        This catches drift like:
        - README.md says "9 Core Skills" but we have 12
        - README.md says "6 skills" but we have 12
        """
        # Count actual skills
        actual_skills = [
            d for d in skills_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]
        actual_count = len(actual_skills)

        # Check README mentions correct count
        # Should find "12 Skills" or "12 skills"
        skill_count_pattern = rf"\b{actual_count}\s+[Ss]kills"

        assert re.search(skill_count_pattern, readme_content), (
            f"README.md INCONSISTENCY: Expected to find '{actual_count} Skills' or '{actual_count} skills'\n"
            f"Actual skills in {skills_dir}: {actual_count}\n"
            f"Found skills: {sorted([d.name for d in actual_skills])}\n"
            f"Fix: Update README.md to show '{actual_count} Skills (Comprehensive SDLC Coverage)'"
        )

    def test_readme_skill_names_match_actual(self, readme_content, skills_dir):
        """Test all skills mentioned in README.md actually exist.

        This catches:
        - README.md references non-existent skill (e.g., "engineering-standards")
        - README.md missing newly added skills
        """
        # Get actual skills
        actual_skills = set(
            d.name for d in skills_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )

        # Extract skill names from README.md (look for **skill-name** pattern)
        mentioned_skills = set(re.findall(r'\*\*([a-z-]+)\*\*', readme_content))

        # Filter to only skill-like names (contain hyphens, lowercase)
        mentioned_skills = {
            s for s in mentioned_skills
            if '-' in s and s.islower() and s in actual_skills
        }

        # Check: All actual skills should be mentioned
        missing_in_readme = actual_skills - mentioned_skills

        assert not missing_in_readme, (
            f"README.md MISSING SKILLS: {sorted(missing_in_readme)}\n"
            f"These skills exist in {skills_dir} but are not mentioned in README.md\n"
            f"Fix: Add these skills to the README.md skills table"
        )

        # Check: All mentioned skills should exist
        extra_in_readme = mentioned_skills - actual_skills

        # Exclude known non-skill entries (like agent names, commands)
        known_non_skills = {
            'claude-code', 'autonomous-dev', 'project-md',
            'user-prompt', 'api-key', 'rest-api'
        }
        extra_in_readme = extra_in_readme - known_non_skills

        # If we find skills in README that don't exist, that's a problem
        if extra_in_readme:
            # But only fail if they look like skill names
            skill_like = {
                s for s in extra_in_readme
                if any(keyword in s for keyword in ['standard', 'pattern', 'guide', 'workflow', 'design', 'review'])
            }

            assert not skill_like, (
                f"README.md REFERENCES NON-EXISTENT SKILLS: {sorted(skill_like)}\n"
                f"These skills are mentioned in README.md but don't exist in {skills_dir}\n"
                f"Fix: Remove references to these skills or create the skill files"
            )

    def test_readme_agent_count_matches_actual(self, readme_content, agents_dir):
        """Test README.md agent count matches actual agents directory.

        This catches:
        - README.md says "7 agents" but we have 8
        - README.md outdated after adding new agent
        """
        # Count actual agents
        actual_agents = [
            f for f in agents_dir.iterdir()
            if f.is_file() and f.suffix == ".md" and not f.name.startswith(".")
        ]
        actual_count = len(actual_agents)

        # Check README mentions correct count
        agent_count_pattern = rf"\b{actual_count}\s+[Ss]pecialized\s+[Aa]gents|\b{actual_count}\s+[Aa]gents"

        assert re.search(agent_count_pattern, readme_content), (
            f"README.md INCONSISTENCY: Expected to find '{actual_count} Specialized Agents' or '{actual_count} agents'\n"
            f"Actual agents in {agents_dir}: {actual_count}\n"
            f"Found agents: {sorted([f.stem for f in actual_agents])}\n"
            f"Fix: Update README.md to show correct agent count"
        )

    def test_readme_command_count_matches_actual(self, readme_content, commands_dir):
        """Test README.md command count matches actual commands directory.

        This catches:
        - README.md says "33 commands" but we have 21
        - README.md outdated after adding/removing commands
        """
        # Count actual commands
        actual_commands = [
            f for f in commands_dir.iterdir()
            if f.is_file() and f.suffix == ".md" and not f.name.startswith(".")
        ]
        actual_count = len(actual_commands)

        # Check README mentions correct count (more flexible pattern)
        # Should find "21 Slash Commands" or "21 commands" somewhere
        command_count_pattern = rf"\b{actual_count}\s+[Ss]lash\s+[Cc]ommands|\b{actual_count}\s+[Cc]ommands"

        assert re.search(command_count_pattern, readme_content), (
            f"README.md INCONSISTENCY: Expected to find '{actual_count} Slash Commands' or '{actual_count} commands'\n"
            f"Actual commands in {commands_dir}: {actual_count}\n"
            f"Found commands: {sorted([f.stem for f in actual_commands])}\n"
            f"Fix: Update README.md to show correct command count"
        )

    def test_readme_has_no_broken_skill_references(self, readme_content, skills_dir):
        """Test README.md doesn't reference non-existent skills in prose.

        This catches:
        - "engineering-standards" mentioned but doesn't exist
        - Old skill names after renaming
        """
        # Get actual skills
        actual_skills = set(
            d.name for d in skills_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )

        # Known problematic references we've seen before
        problematic_skills = ['engineering-standards']

        for skill in problematic_skills:
            if skill not in actual_skills:
                # Check if README mentions this non-existent skill
                assert skill not in readme_content, (
                    f"README.md BROKEN REFERENCE: Mentions '{skill}' but this skill doesn't exist\n"
                    f"Fix: Remove references to '{skill}' or create the skill directory"
                )


class TestCrossDocumentConsistency:
    """Test consistency across multiple documentation files."""

    @pytest.fixture
    def docs_dir(self):
        """Path to docs directory."""
        return Path(__file__).parent.parent / "docs"

    @pytest.fixture
    def skills_dir(self):
        """Path to skills directory."""
        return Path(__file__).parent.parent / "skills"

    def test_sync_status_matches_readme(self):
        """Test SYNC-STATUS.md shows same counts as README.md."""
        readme_path = Path(__file__).parent.parent / "README.md"
        sync_status_path = Path(__file__).parent.parent / "docs" / "SYNC-STATUS.md"

        if not sync_status_path.exists():
            pytest.skip("SYNC-STATUS.md not found")

        readme_content = readme_path.read_text()
        sync_status_content = sync_status_path.read_text()

        # Extract skill count from README
        readme_skill_match = re.search(r'(\d+)\s+Skills', readme_content)
        assert readme_skill_match, "Could not find skill count in README.md"
        readme_skill_count = readme_skill_match.group(1)

        # Check SYNC-STATUS mentions same count
        assert readme_skill_count in sync_status_content, (
            f"SYNC-STATUS.md INCONSISTENCY: Should mention '{readme_skill_count} skills'\n"
            f"README.md shows: {readme_skill_count} skills\n"
            f"Fix: Update SYNC-STATUS.md to match README.md"
        )

    def test_updates_doc_matches_readme(self):
        """Test UPDATES.md shows same counts as README.md."""
        readme_path = Path(__file__).parent.parent / "README.md"
        updates_path = Path(__file__).parent.parent / "docs" / "UPDATES.md"

        if not updates_path.exists():
            pytest.skip("UPDATES.md not found")

        readme_content = readme_path.read_text()
        updates_content = updates_path.read_text()

        # Extract skill count from README
        readme_skill_match = re.search(r'(\d+)\s+Skills', readme_content)
        assert readme_skill_match, "Could not find skill count in README.md"
        readme_skill_count = readme_skill_match.group(1)

        # Check UPDATES mentions same count (in "All X skills" or "X skills" context)
        skill_pattern = rf"All {readme_skill_count} skills|{readme_skill_count} skills"

        assert re.search(skill_pattern, updates_content), (
            f"UPDATES.md INCONSISTENCY: Should mention 'All {readme_skill_count} skills' or '{readme_skill_count} skills'\n"
            f"README.md shows: {readme_skill_count} skills\n"
            f"Fix: Update UPDATES.md to match README.md"
        )

    def test_install_template_matches_readme(self):
        """Test INSTALL_TEMPLATE.md shows same counts as README.md."""
        readme_path = Path(__file__).parent.parent / "README.md"
        install_template_path = Path(__file__).parent.parent / "INSTALL_TEMPLATE.md"

        if not install_template_path.exists():
            pytest.skip("INSTALL_TEMPLATE.md not found")

        readme_content = readme_path.read_text()
        install_content = install_template_path.read_text()

        # Extract skill count from README
        readme_skill_match = re.search(r'(\d+)\s+Skills', readme_content)
        assert readme_skill_match, "Could not find skill count in README.md"
        readme_skill_count = readme_skill_match.group(1)

        # Check INSTALL_TEMPLATE mentions same count
        assert readme_skill_count in install_content, (
            f"INSTALL_TEMPLATE.md INCONSISTENCY: Should mention '{readme_skill_count} skills'\n"
            f"README.md shows: {readme_skill_count} skills\n"
            f"Fix: Update INSTALL_TEMPLATE.md to match README.md"
        )


class TestMarketplaceConsistency:
    """Test marketplace.json matches actual codebase state."""

    @pytest.fixture
    def marketplace_path(self):
        """Path to marketplace.json."""
        return Path(__file__).parent.parent / ".claude-plugin" / "marketplace.json"

    @pytest.fixture
    def marketplace_data(self, marketplace_path):
        """marketplace.json content."""
        import json
        return json.loads(marketplace_path.read_text())

    @pytest.fixture
    def skills_dir(self):
        """Path to skills directory."""
        return Path(__file__).parent.parent / "skills"

    @pytest.fixture
    def agents_dir(self):
        """Path to agents directory."""
        return Path(__file__).parent.parent / "agents"

    @pytest.fixture
    def commands_dir(self):
        """Path to commands directory."""
        return Path(__file__).parent.parent / "commands"

    def test_marketplace_skill_count_matches_actual(self, marketplace_data, skills_dir):
        """Test marketplace.json skill count matches actual skills."""
        actual_count = len([
            d for d in skills_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ])

        marketplace_count = marketplace_data.get("metrics", {}).get("skills", 0)

        assert marketplace_count == actual_count, (
            f"marketplace.json INCONSISTENCY: Shows {marketplace_count} skills but actual is {actual_count}\n"
            f"Fix: Update .claude-plugin/marketplace.json metrics.skills to {actual_count}"
        )

    def test_marketplace_agent_count_matches_actual(self, marketplace_data, agents_dir):
        """Test marketplace.json agent count matches actual agents."""
        actual_count = len([
            f for f in agents_dir.iterdir()
            if f.is_file() and f.suffix == ".md" and not f.name.startswith(".")
        ])

        marketplace_count = marketplace_data.get("metrics", {}).get("agents", 0)

        assert marketplace_count == actual_count, (
            f"marketplace.json INCONSISTENCY: Shows {marketplace_count} agents but actual is {actual_count}\n"
            f"Fix: Update .claude-plugin/marketplace.json metrics.agents to {actual_count}"
        )

    def test_marketplace_command_count_matches_actual(self, marketplace_data, commands_dir):
        """Test marketplace.json command count matches actual commands."""
        actual_count = len([
            f for f in commands_dir.iterdir()
            if f.is_file() and f.suffix == ".md" and not f.name.startswith(".")
        ])

        marketplace_count = marketplace_data.get("metrics", {}).get("commands", 0)

        assert marketplace_count == actual_count, (
            f"marketplace.json INCONSISTENCY: Shows {marketplace_count} commands but actual is {actual_count}\n"
            f"Fix: Update .claude-plugin/marketplace.json metrics.commands to {actual_count}"
        )




class TestDeprecatedPatterns:
    """Test that README.md doesn't contain deprecated procedural instructions."""

    @pytest.fixture
    def readme_content(self):
        """README.md content."""
        return (Path(__file__).parent.parent / "README.md").read_text()

    def test_no_deprecated_setup_py_references(self, readme_content):
        """Test README.md doesn't reference deprecated 'python setup.py' workflow."""
        deprecated_patterns = [
            r"python\s+.*setup\.py",
            r"scripts/setup\.py",
            r"python\s+plugins/.*setup\.py",
            r"\.claude/scripts/setup\.py",
        ]

        violations = []
        for pattern in deprecated_patterns:
            matches = re.findall(pattern, readme_content, re.IGNORECASE)
            if matches:
                violations.append(f"Found deprecated pattern: {matches[0]}")

        assert not violations, (
            f"README.md contains deprecated setup instructions:
" +
            "
".join(f"  - {v}" for v in violations) +
            f"

Fix: Replace 'python setup.py' references with '/setup' command.
"
            f"We now use slash commands, not Python scripts for setup."
        )

    def test_no_deprecated_script_references(self, readme_content):
        """Test README.md doesn't reference scripts that should be commands."""
        # This test can be extended for other deprecated patterns in the future
        assert "python scripts/setup.py" not in readme_content.lower(), (
            "README.md references 'python scripts/setup.py' but should use '/setup' command"
        )




class TestVersionConsistency:
    """Test version numbers are consistent across configuration files."""

    @pytest.fixture
    def plugin_json_path(self):
        return Path(__file__).parent.parent / ".claude-plugin" / "plugin.json"

    @pytest.fixture
    def marketplace_json_path(self):
        return Path(__file__).parent.parent / ".claude-plugin" / "marketplace.json"

    def test_versions_match(self, plugin_json_path, marketplace_json_path):
        """Test plugin.json and marketplace.json have matching versions."""
        import json
        
        plugin_data = json.loads(plugin_json_path.read_text())
        marketplace_data = json.loads(marketplace_json_path.read_text())
        
        plugin_version = plugin_data.get("version")
        marketplace_version = marketplace_data.get("version")
        
        assert plugin_version == marketplace_version, (
            f"VERSION MISMATCH:\n"
            f"  plugin.json: {plugin_version}\n"
            f"  marketplace.json: {marketplace_version}\n"
            f"Fix: Update both files to use the same version"
        )


class TestReadOnlyAgentRestrictions:
    """Test that read-only agents don't have Write/Edit tools."""

    @pytest.fixture
    def agents_dir(self):
        return Path(__file__).parent.parent / "agents"

    def test_planner_is_readonly(self, agents_dir):
        """Test planner agent has no Write/Edit tools."""
        planner_path = agents_dir / "planner.md"
        content = planner_path.read_text()
        
        # Check frontmatter
        frontmatter_match = re.search(r'---\n(.*?)\n---', content, re.DOTALL)
        assert frontmatter_match, "planner.md missing frontmatter"
        
        frontmatter = frontmatter_match.group(1)
        assert 'Write' not in frontmatter and 'Edit' not in frontmatter, (
            "planner.md has Write/Edit tools but should be read-only"
        )

    def test_reviewer_is_readonly(self, agents_dir):
        """Test reviewer agent has no Write/Edit tools."""
        reviewer_path = agents_dir / "reviewer.md"
        content = reviewer_path.read_text()
        
        frontmatter_match = re.search(r'---\n(.*?)\n---', content, re.DOTALL)
        assert frontmatter_match, "reviewer.md missing frontmatter"
        
        frontmatter = frontmatter_match.group(1)
        assert 'Write' not in frontmatter and 'Edit' not in frontmatter, (
            "reviewer.md has Write/Edit tools but should be read-only"
        )

    def test_security_auditor_is_readonly(self, agents_dir):
        """Test security-auditor agent has no Write/Edit tools."""
        auditor_path = agents_dir / "security-auditor.md"
        content = auditor_path.read_text()
        
        frontmatter_match = re.search(r'---\n(.*?)\n---', content, re.DOTALL)
        assert frontmatter_match, "security-auditor.md missing frontmatter"
        
        frontmatter = frontmatter_match.group(1)
        assert 'Write' not in frontmatter and 'Edit' not in frontmatter, (
            "security-auditor.md has Write/Edit tools but should be read-only"
        )


class TestSkillTableCompleteness:
    """Test that all skills are documented in README."""

    @pytest.fixture
    def readme_content(self):
        return (Path(__file__).parent.parent / "README.md").read_text()

    @pytest.fixture
    def skills_dir(self):
        return Path(__file__).parent.parent / "skills"

    def test_all_skills_documented_in_readme(self, readme_content, skills_dir):
        """Test that every skill in skills/ is mentioned in README.md."""
        actual_skills = [
            d.name for d in skills_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]
        
        missing_skills = [
            skill for skill in actual_skills
            if skill not in readme_content
        ]
        
        assert not missing_skills, (
            f"Skills exist but not documented in README.md:\n"
            + "\n".join(f"  - {s}" for s in missing_skills) +
            f"\nFix: Add these skills to README.md skill table"
        )


class TestAgentFrontmatterSchema:
    """Test that all agents have required frontmatter fields."""

    @pytest.fixture
    def agents_dir(self):
        return Path(__file__).parent.parent / "agents"

    def test_all_agents_have_name_field(self, agents_dir):
        """Test that all agents have 'name' field in frontmatter."""
        for agent_file in agents_dir.glob("*.md"):
            if agent_file.name.startswith("."):
                continue
            
            content = agent_file.read_text()
            assert content.startswith("---"), f"{agent_file.name} missing frontmatter"
            
            frontmatter_match = re.search(r'---\n(.*?)\n---', content, re.DOTALL)
            assert frontmatter_match, f"{agent_file.name} invalid frontmatter format"
            
            frontmatter = frontmatter_match.group(1)
            assert "name:" in frontmatter, f"{agent_file.name} missing 'name' field"

    def test_all_agents_have_tools_field(self, agents_dir):
        """Test that all agents have 'tools' field in frontmatter."""
        for agent_file in agents_dir.glob("*.md"):
            if agent_file.name.startswith("."):
                continue
            
            content = agent_file.read_text()
            frontmatter_match = re.search(r'---\n(.*?)\n---', content, re.DOTALL)
            assert frontmatter_match, f"{agent_file.name} missing frontmatter"
            
            frontmatter = frontmatter_match.group(1)
            assert "tools:" in frontmatter, f"{agent_file.name} missing 'tools' field"


class TestCommandDocumentation:
    """Test that all commands are documented."""

    @pytest.fixture
    def readme_content(self):
        return (Path(__file__).parent.parent / "README.md").read_text()

    @pytest.fixture
    def commands_dir(self):
        return Path(__file__).parent.parent / "commands"

    def test_all_commands_documented_in_readme(self, readme_content, commands_dir):
        """Test that every command in commands/ is mentioned in README.md."""
        actual_commands = [
            f.stem for f in commands_dir.glob("*.md")
            if not f.name.startswith(".")
        ]
        
        undocumented_commands = [
            cmd for cmd in actual_commands
            if f"/{cmd}" not in readme_content
        ]
        
        assert not undocumented_commands, (
            f"Commands exist but not documented in README.md:\n"
            + "\n".join(f"  - /{cmd}" for cmd in sorted(undocumented_commands)) +
            f"\nFix: Add these commands to README.md"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
