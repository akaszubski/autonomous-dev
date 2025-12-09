"""
Test suite for Issue #108: Optimize model tier assignments (Haiku/Sonnet/Opus).

Tests verify that:
1. Agent frontmatter has correct model field values
2. Auto-implement.md removes/aligns model overrides
3. Documentation contains accurate tier strategy

TDD RED PHASE - These tests should FAIL before implementation.
"""

import pytest
import re
from pathlib import Path


# Test Fixtures
@pytest.fixture
def project_root():
    """Get project root directory (where .git is located)."""
    current = Path(__file__).resolve()
    while current != current.parent:
        # Only check for .git to find actual repo root
        # (plugins/autonomous-dev/.claude is a symlink, not the root)
        if (current / ".git").exists():
            return current
        current = current.parent
    return Path.cwd()


@pytest.fixture
def agents_dir(project_root):
    """Get agents directory."""
    return project_root / "plugins/autonomous-dev/agents"


@pytest.fixture
def auto_implement_path(project_root):
    """Get auto-implement.md path."""
    return project_root / "plugins/autonomous-dev/commands/auto-implement.md"


@pytest.fixture
def claude_md_path(project_root):
    """Get CLAUDE.md path."""
    return project_root / "CLAUDE.md"


def extract_frontmatter_model(agent_path: Path) -> str:
    """Extract model field from agent frontmatter.

    Args:
        agent_path: Path to agent markdown file

    Returns:
        Model value from frontmatter (e.g., 'haiku', 'sonnet', 'opus')

    Raises:
        ValueError: If model field not found or invalid format
    """
    content = agent_path.read_text()

    # Extract frontmatter (between --- markers)
    match = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL | re.MULTILINE)
    if not match:
        raise ValueError(f"No frontmatter found in {agent_path.name}")

    frontmatter = match.group(1)

    # Extract model field (supports hyphens for edge case testing)
    model_match = re.search(r'^model:\s*["\']?([\w-]+)["\']?\s*$', frontmatter, re.MULTILINE)
    if not model_match:
        raise ValueError(f"No model field found in {agent_path.name} frontmatter")

    return model_match.group(1).lower()


def extract_auto_implement_overrides(auto_implement_path: Path) -> dict:
    """Extract model overrides from auto-implement.md.

    Args:
        auto_implement_path: Path to auto-implement.md

    Returns:
        Dict mapping agent names to their model overrides (empty dict if no overrides)
    """
    content = auto_implement_path.read_text()
    overrides = {}

    # Look for Task tool calls with model overrides
    # Pattern: /subagent agent-name --model haiku|sonnet|opus
    task_pattern = r'/subagent\s+([\w-]+)\s+[^}]*?--model\s+(haiku|sonnet|opus)'
    for match in re.finditer(task_pattern, content, re.IGNORECASE):
        agent_name = match.group(1)
        model = match.group(2).lower()
        overrides[agent_name] = model

    return overrides


# =============================================================================
# AGENT FRONTMATTER TESTS
# =============================================================================

class TestAgentFrontmatterHaiku:
    """Test Haiku tier agents (8 agents - fast, simple tasks)."""

    HAIKU_AGENTS = [
        'researcher',
        'reviewer',
        'doc-master',
        'commit-message-generator',
        'alignment-validator',
        'project-progress-tracker',
        'sync-validator',
        'pr-description-generator'
    ]

    @pytest.mark.parametrize("agent_name", HAIKU_AGENTS)
    def test_haiku_agent_model_field(self, agents_dir, agent_name):
        """Test that Haiku tier agents have model: haiku in frontmatter."""
        agent_path = agents_dir / f"{agent_name}.md"
        assert agent_path.exists(), f"Agent file not found: {agent_path}"

        model = extract_frontmatter_model(agent_path)
        assert model == 'haiku', (
            f"Agent {agent_name} should use Haiku model for fast, simple tasks. "
            f"Found: {model}"
        )

    def test_haiku_agent_count(self, agents_dir):
        """Test that exactly 8 agents are assigned to Haiku tier."""
        haiku_count = 0
        for agent_name in self.HAIKU_AGENTS:
            agent_path = agents_dir / f"{agent_name}.md"
            if agent_path.exists():
                try:
                    model = extract_frontmatter_model(agent_path)
                    if model == 'haiku':
                        haiku_count += 1
                except ValueError:
                    pass

        assert haiku_count == 8, f"Expected 8 Haiku agents, found {haiku_count}"


class TestAgentFrontmatterSonnet:
    """Test Sonnet tier agents (10 agents - balanced tasks)."""

    SONNET_AGENTS = [
        'implementer',
        'test-master',
        'planner',
        'issue-creator',
        'setup-wizard',
        'project-bootstrapper',
        'brownfield-analyzer',
        'quality-validator',
        'alignment-analyzer',
        'project-status-analyzer'
    ]

    @pytest.mark.parametrize("agent_name", SONNET_AGENTS)
    def test_sonnet_agent_model_field(self, agents_dir, agent_name):
        """Test that Sonnet tier agents have model: sonnet in frontmatter."""
        agent_path = agents_dir / f"{agent_name}.md"
        assert agent_path.exists(), f"Agent file not found: {agent_path}"

        model = extract_frontmatter_model(agent_path)
        assert model == 'sonnet', (
            f"Agent {agent_name} should use Sonnet model for balanced tasks. "
            f"Found: {model}"
        )

    def test_sonnet_agent_count(self, agents_dir):
        """Test that exactly 10 agents are assigned to Sonnet tier."""
        sonnet_count = 0
        for agent_name in self.SONNET_AGENTS:
            agent_path = agents_dir / f"{agent_name}.md"
            if agent_path.exists():
                try:
                    model = extract_frontmatter_model(agent_path)
                    if model == 'sonnet':
                        sonnet_count += 1
                except ValueError:
                    pass

        assert sonnet_count == 10, f"Expected 10 Sonnet agents, found {sonnet_count}"


class TestAgentFrontmatterOpus:
    """Test Opus tier agents (2 agents - complex reasoning)."""

    OPUS_AGENTS = [
        'security-auditor',
        'advisor'
    ]

    @pytest.mark.parametrize("agent_name", OPUS_AGENTS)
    def test_opus_agent_model_field(self, agents_dir, agent_name):
        """Test that Opus tier agents have model: opus in frontmatter."""
        agent_path = agents_dir / f"{agent_name}.md"
        assert agent_path.exists(), f"Agent file not found: {agent_path}"

        model = extract_frontmatter_model(agent_path)
        assert model == 'opus', (
            f"Agent {agent_name} should use Opus model for complex reasoning. "
            f"Found: {model}"
        )

    def test_opus_agent_count(self, agents_dir):
        """Test that exactly 2 agents are assigned to Opus tier."""
        opus_count = 0
        for agent_name in self.OPUS_AGENTS:
            agent_path = agents_dir / f"{agent_name}.md"
            if agent_path.exists():
                try:
                    model = extract_frontmatter_model(agent_path)
                    if model == 'opus':
                        opus_count += 1
                except ValueError:
                    pass

        assert opus_count == 2, f"Expected 2 Opus agents, found {opus_count}"


class TestAgentFrontmatterComprehensive:
    """Comprehensive tests across all agent tiers."""

    def test_total_agent_count(self, agents_dir):
        """Test that all 20 agents have model assignments."""
        all_agents = (
            TestAgentFrontmatterHaiku.HAIKU_AGENTS +
            TestAgentFrontmatterSonnet.SONNET_AGENTS +
            TestAgentFrontmatterOpus.OPUS_AGENTS
        )

        assert len(all_agents) == 20, "Should have exactly 20 agents defined"

        # Verify no duplicates
        assert len(all_agents) == len(set(all_agents)), "Agent list contains duplicates"

    def test_no_missing_model_fields(self, agents_dir):
        """Test that all agent files have valid model fields."""
        all_agents = (
            TestAgentFrontmatterHaiku.HAIKU_AGENTS +
            TestAgentFrontmatterSonnet.SONNET_AGENTS +
            TestAgentFrontmatterOpus.OPUS_AGENTS
        )

        missing_fields = []
        for agent_name in all_agents:
            agent_path = agents_dir / f"{agent_name}.md"
            if not agent_path.exists():
                missing_fields.append(f"{agent_name} (file not found)")
                continue

            try:
                extract_frontmatter_model(agent_path)
            except ValueError as e:
                missing_fields.append(f"{agent_name} ({str(e)})")

        assert not missing_fields, (
            f"Agents with missing/invalid model fields: {', '.join(missing_fields)}"
        )

    def test_model_distribution_balanced(self, agents_dir):
        """Test that model distribution follows 8-10-2 pattern (Haiku-Sonnet-Opus)."""
        all_agents = (
            TestAgentFrontmatterHaiku.HAIKU_AGENTS +
            TestAgentFrontmatterSonnet.SONNET_AGENTS +
            TestAgentFrontmatterOpus.OPUS_AGENTS
        )

        distribution = {'haiku': 0, 'sonnet': 0, 'opus': 0}

        for agent_name in all_agents:
            agent_path = agents_dir / f"{agent_name}.md"
            if agent_path.exists():
                try:
                    model = extract_frontmatter_model(agent_path)
                    distribution[model] += 1
                except ValueError:
                    pass

        assert distribution['haiku'] == 8, f"Expected 8 Haiku agents, found {distribution['haiku']}"
        assert distribution['sonnet'] == 10, f"Expected 10 Sonnet agents, found {distribution['sonnet']}"
        assert distribution['opus'] == 2, f"Expected 2 Opus agents, found {distribution['opus']}"


# =============================================================================
# AUTO-IMPLEMENT OVERRIDE TESTS
# =============================================================================

class TestAutoImplementOverrides:
    """Test that auto-implement.md aligns with agent frontmatter (no unnecessary overrides)."""

    def test_researcher_no_sonnet_override(self, auto_implement_path):
        """Test that researcher uses Haiku (no Sonnet override in auto-implement)."""
        overrides = extract_auto_implement_overrides(auto_implement_path)

        # Researcher should either not be in overrides, or should be haiku
        if 'researcher' in overrides:
            assert overrides['researcher'] == 'haiku', (
                "Researcher should use Haiku model (fast research tasks). "
                f"Found override: {overrides['researcher']}"
            )

    def test_reviewer_no_sonnet_override(self, auto_implement_path):
        """Test that reviewer uses Haiku (no Sonnet override in auto-implement)."""
        overrides = extract_auto_implement_overrides(auto_implement_path)

        # Reviewer should either not be in overrides, or should be haiku
        if 'reviewer' in overrides:
            assert overrides['reviewer'] == 'haiku', (
                "Reviewer should use Haiku model (fast code review). "
                f"Found override: {overrides['reviewer']}"
            )

    def test_security_auditor_opus_upgrade(self, auto_implement_path):
        """Test that security-auditor uses Opus (upgraded from Haiku)."""
        overrides = extract_auto_implement_overrides(auto_implement_path)

        # Security-auditor should either not be in overrides (uses frontmatter opus),
        # or should be opus if override exists
        if 'security-auditor' in overrides:
            assert overrides['security-auditor'] == 'opus', (
                "Security-auditor should use Opus model (complex security reasoning). "
                f"Found override: {overrides['security-auditor']}"
            )

    def test_planner_sonnet_downgrade(self, auto_implement_path):
        """Test that planner uses Sonnet (downgraded from Opus)."""
        overrides = extract_auto_implement_overrides(auto_implement_path)

        # Planner should either not be in overrides (uses frontmatter sonnet),
        # or should be sonnet if override exists
        if 'planner' in overrides:
            assert overrides['planner'] == 'sonnet', (
                "Planner should use Sonnet model (balanced planning tasks). "
                f"Found override: {overrides['planner']}"
            )

    def test_no_conflicting_overrides(self, auto_implement_path, agents_dir):
        """Test that auto-implement overrides don't conflict with agent frontmatter."""
        overrides = extract_auto_implement_overrides(auto_implement_path)

        conflicts = []
        for agent_name, override_model in overrides.items():
            agent_path = agents_dir / f"{agent_name}.md"
            if not agent_path.exists():
                continue

            try:
                frontmatter_model = extract_frontmatter_model(agent_path)
                if frontmatter_model != override_model:
                    conflicts.append(
                        f"{agent_name}: frontmatter={frontmatter_model}, "
                        f"override={override_model}"
                    )
            except ValueError:
                pass

        assert not conflicts, (
            "Auto-implement overrides conflict with agent frontmatter. "
            "Either remove overrides or update frontmatter. "
            f"Conflicts: {', '.join(conflicts)}"
        )

    def test_minimal_overrides(self, auto_implement_path):
        """Test that auto-implement uses minimal model overrides (prefer frontmatter)."""
        overrides = extract_auto_implement_overrides(auto_implement_path)

        # Should have minimal or no overrides (agents use frontmatter model)
        assert len(overrides) <= 5, (
            f"Auto-implement should use minimal model overrides (found {len(overrides)}). "
            "Prefer setting model in agent frontmatter instead. "
            f"Current overrides: {list(overrides.keys())}"
        )


# =============================================================================
# DOCUMENTATION TESTS
# =============================================================================

class TestDocumentation:
    """Test that documentation accurately reflects model tier strategy."""

    def test_claude_md_has_model_tiers_section(self, claude_md_path):
        """Test that CLAUDE.md contains model tier documentation."""
        content = claude_md_path.read_text()

        # Should have a section about model tiers
        assert re.search(
            r'##\s+Model\s+Tiers?|##\s+Agent\s+Model\s+Assignments?',
            content,
            re.IGNORECASE
        ), "CLAUDE.md should contain a 'Model Tiers' or 'Agent Model Assignments' section"

    def test_claude_md_documents_haiku_agents(self, claude_md_path):
        """Test that CLAUDE.md documents Haiku tier agents."""
        content = claude_md_path.read_text()

        # Should mention Haiku tier with count
        assert re.search(
            r'8\s+haiku|haiku\s+\(8\s+agents?\)',
            content,
            re.IGNORECASE
        ), "CLAUDE.md should document 8 Haiku tier agents"

    def test_claude_md_documents_sonnet_agents(self, claude_md_path):
        """Test that CLAUDE.md documents Sonnet tier agents."""
        content = claude_md_path.read_text()

        # Should mention Sonnet tier with count
        assert re.search(
            r'10\s+sonnet|sonnet\s+\(10\s+agents?\)',
            content,
            re.IGNORECASE
        ), "CLAUDE.md should document 10 Sonnet tier agents"

    def test_claude_md_documents_opus_agents(self, claude_md_path):
        """Test that CLAUDE.md documents Opus tier agents."""
        content = claude_md_path.read_text()

        # Should mention Opus tier with count
        assert re.search(
            r'2\s+opus|opus\s+\(2\s+agents?\)',
            content,
            re.IGNORECASE
        ), "CLAUDE.md should document 2 Opus tier agents"

    def test_claude_md_documents_tier_rationale(self, claude_md_path):
        """Test that CLAUDE.md explains the rationale for each tier."""
        content = claude_md_path.read_text()

        # Should explain why each tier is used
        tier_keywords = {
            'haiku': ['fast', 'simple', 'quick', 'lightweight'],
            'sonnet': ['balanced', 'moderate', 'general', 'standard'],
            'opus': ['complex', 'reasoning', 'critical', 'security']
        }

        missing_rationale = []
        for tier, keywords in tier_keywords.items():
            # Find tier section
            tier_pattern = rf'###?\s+{tier}|{tier}\s+tier'
            tier_match = re.search(tier_pattern, content, re.IGNORECASE)

            if tier_match:
                # Check if any rationale keywords appear near the tier mention
                section_start = tier_match.start()
                section_end = min(section_start + 500, len(content))
                section_text = content[section_start:section_end].lower()

                has_rationale = any(keyword in section_text for keyword in keywords)
                if not has_rationale:
                    missing_rationale.append(tier)

        assert not missing_rationale, (
            f"CLAUDE.md should explain rationale for tiers: {', '.join(missing_rationale)}"
        )

    def test_claude_md_tier_counts_accurate(self, claude_md_path):
        """Test that documented tier counts match reality (8-10-2 distribution)."""
        content = claude_md_path.read_text()

        # Extract all numbers near model tier keywords
        haiku_counts = re.findall(r'(\d+)\s+haiku|haiku\s+\((\d+)', content, re.IGNORECASE)
        sonnet_counts = re.findall(r'(\d+)\s+sonnet|sonnet\s+\((\d+)', content, re.IGNORECASE)
        opus_counts = re.findall(r'(\d+)\s+opus|opus\s+\((\d+)', content, re.IGNORECASE)

        # Flatten tuples and convert to ints
        haiku_nums = [int(n) for match in haiku_counts for n in match if n]
        sonnet_nums = [int(n) for match in sonnet_counts for n in match if n]
        opus_nums = [int(n) for match in opus_counts for n in match if n]

        # Should have correct counts documented
        assert 8 in haiku_nums, "CLAUDE.md should document 8 Haiku agents"
        assert 10 in sonnet_nums, "CLAUDE.md should document 10 Sonnet agents"
        assert 2 in opus_nums, "CLAUDE.md should document 2 Opus agents"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestModelTierIntegration:
    """Integration tests for model tier optimization across system."""

    def test_all_agents_have_consistent_tiers(self, agents_dir, auto_implement_path):
        """Test that all agents have consistent model assignments (frontmatter + overrides)."""
        all_agents = (
            TestAgentFrontmatterHaiku.HAIKU_AGENTS +
            TestAgentFrontmatterSonnet.SONNET_AGENTS +
            TestAgentFrontmatterOpus.OPUS_AGENTS
        )

        overrides = extract_auto_implement_overrides(auto_implement_path)
        inconsistent = []

        for agent_name in all_agents:
            agent_path = agents_dir / f"{agent_name}.md"
            if not agent_path.exists():
                continue

            try:
                frontmatter_model = extract_frontmatter_model(agent_path)
                override_model = overrides.get(agent_name)

                if override_model and override_model != frontmatter_model:
                    inconsistent.append(
                        f"{agent_name}: frontmatter={frontmatter_model}, "
                        f"override={override_model}"
                    )
            except ValueError:
                pass

        assert not inconsistent, (
            "Agents have inconsistent model assignments between frontmatter and overrides. "
            f"Inconsistencies: {', '.join(inconsistent)}"
        )

    def test_critical_agents_use_appropriate_models(self, agents_dir):
        """Test that critical agents (security, advisor) use Opus for complex reasoning."""
        critical_agents = {
            'security-auditor': 'opus',  # Security requires deep reasoning
            'advisor': 'opus'  # Strategic advice requires deep reasoning
        }

        incorrect_assignments = []
        for agent_name, expected_model in critical_agents.items():
            agent_path = agents_dir / f"{agent_name}.md"
            if agent_path.exists():
                try:
                    actual_model = extract_frontmatter_model(agent_path)
                    if actual_model != expected_model:
                        incorrect_assignments.append(
                            f"{agent_name}: expected {expected_model}, got {actual_model}"
                        )
                except ValueError as e:
                    incorrect_assignments.append(f"{agent_name}: {str(e)}")

        assert not incorrect_assignments, (
            "Critical agents should use Opus for complex reasoning. "
            f"Incorrect assignments: {', '.join(incorrect_assignments)}"
        )

    def test_fast_agents_use_haiku(self, agents_dir):
        """Test that fast agents (researcher, reviewer) use Haiku for speed."""
        fast_agents = {
            'researcher': 'haiku',  # Research should be fast
            'reviewer': 'haiku',  # Code review should be fast
            'doc-master': 'haiku',  # Documentation should be fast
            'commit-message-generator': 'haiku'  # Commit messages should be fast
        }

        incorrect_assignments = []
        for agent_name, expected_model in fast_agents.items():
            agent_path = agents_dir / f"{agent_name}.md"
            if agent_path.exists():
                try:
                    actual_model = extract_frontmatter_model(agent_path)
                    if actual_model != expected_model:
                        incorrect_assignments.append(
                            f"{agent_name}: expected {expected_model}, got {actual_model}"
                        )
                except ValueError as e:
                    incorrect_assignments.append(f"{agent_name}: {str(e)}")

        assert not incorrect_assignments, (
            "Fast agents should use Haiku for speed. "
            f"Incorrect assignments: {', '.join(incorrect_assignments)}"
        )


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_agent_file_missing(self, agents_dir):
        """Test behavior when agent file doesn't exist."""
        nonexistent = agents_dir / "nonexistent-agent.md"

        with pytest.raises(FileNotFoundError):
            if not nonexistent.exists():
                raise FileNotFoundError(f"Agent file not found: {nonexistent}")

    def test_invalid_model_value(self, agents_dir, tmp_path):
        """Test behavior when agent has invalid model value."""
        # Create temporary agent file with invalid model
        temp_agent = tmp_path / "test-agent.md"
        temp_agent.write_text("""---
name: test-agent
model: invalid-model
---

Test agent content.
""")

        model = extract_frontmatter_model(temp_agent)
        assert model not in ['haiku', 'sonnet', 'opus'], (
            "Invalid model value should be detected"
        )

    def test_missing_frontmatter(self, tmp_path):
        """Test behavior when agent file has no frontmatter."""
        temp_agent = tmp_path / "test-agent.md"
        temp_agent.write_text("Agent content without frontmatter.")

        with pytest.raises(ValueError, match="No frontmatter found"):
            extract_frontmatter_model(temp_agent)

    def test_missing_model_field(self, tmp_path):
        """Test behavior when frontmatter has no model field."""
        temp_agent = tmp_path / "test-agent.md"
        temp_agent.write_text("""---
name: test-agent
description: Test agent
---

Test agent content.
""")

        with pytest.raises(ValueError, match="No model field found"):
            extract_frontmatter_model(temp_agent)

    def test_auto_implement_no_overrides(self, tmp_path):
        """Test behavior when auto-implement.md has no model overrides."""
        temp_file = tmp_path / "auto-implement.md"
        temp_file.write_text("""
# Auto-Implement Command

This command runs agents without model overrides.

/subagent researcher
/subagent planner
""")

        overrides = extract_auto_implement_overrides(temp_file)
        assert overrides == {}, "Should return empty dict when no overrides found"

    def test_malformed_override_syntax(self, tmp_path):
        """Test behavior with malformed override syntax."""
        temp_file = tmp_path / "auto-implement.md"
        temp_file.write_text("""
/subagent researcher --model
/subagent planner --model haiku sonnet
/subagent implementer model=haiku
""")

        overrides = extract_auto_implement_overrides(temp_file)
        # Should only extract valid overrides
        assert len(overrides) <= 1, "Should skip malformed override syntax"


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================

class TestPerformance:
    """Test that model tier changes improve performance."""

    def test_haiku_agents_prioritize_speed(self, agents_dir):
        """Test that Haiku agents are used for tasks where speed matters."""
        haiku_agents = TestAgentFrontmatterHaiku.HAIKU_AGENTS

        # These agents should complete quickly
        speed_critical = [
            'researcher',  # Fast research
            'reviewer',  # Fast code review
            'commit-message-generator'  # Fast commit messages
        ]

        for agent_name in speed_critical:
            assert agent_name in haiku_agents, (
                f"{agent_name} should use Haiku for speed-critical tasks"
            )

    def test_opus_agents_limited_to_critical_tasks(self, agents_dir):
        """Test that Opus is only used for critical complex reasoning tasks."""
        opus_agents = TestAgentFrontmatterOpus.OPUS_AGENTS

        # Should only have 2 Opus agents (expensive model)
        assert len(opus_agents) == 2, (
            f"Should limit Opus usage to critical tasks (found {len(opus_agents)} agents)"
        )

        # Verify they're truly critical
        critical_tasks = ['security-auditor', 'advisor']
        for agent in opus_agents:
            assert agent in critical_tasks, (
                f"{agent} uses Opus but may not require complex reasoning"
            )

    def test_balanced_distribution(self, agents_dir):
        """Test that model distribution is balanced (cost vs performance)."""
        haiku_count = len(TestAgentFrontmatterHaiku.HAIKU_AGENTS)
        sonnet_count = len(TestAgentFrontmatterSonnet.SONNET_AGENTS)
        opus_count = len(TestAgentFrontmatterOpus.OPUS_AGENTS)

        total = haiku_count + sonnet_count + opus_count

        # Distribution should be reasonable (not all Opus, not all Haiku)
        haiku_pct = (haiku_count / total) * 100
        sonnet_pct = (sonnet_count / total) * 100
        opus_pct = (opus_count / total) * 100

        assert 30 <= haiku_pct <= 50, (
            f"Haiku should be 30-50% of agents (found {haiku_pct:.1f}%)"
        )
        assert 40 <= sonnet_pct <= 60, (
            f"Sonnet should be 40-60% of agents (found {sonnet_pct:.1f}%)"
        )
        assert 5 <= opus_pct <= 15, (
            f"Opus should be 5-15% of agents (found {opus_pct:.1f}%)"
        )
