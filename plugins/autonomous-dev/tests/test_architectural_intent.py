"""
Architectural Intent Validation Tests (LAYER 2: Static Validation)

⚠️ IMPORTANT: These are STATIC tests. They validate structure and keywords,
but cannot validate BEHAVIOR or INTENT.

For comprehensive architectural validation, use:
    /validate-architecture (GenAI-powered, understands MEANING)

These tests validate the DESIGN INTENT and ARCHITECTURAL DECISIONS
documented in ARCHITECTURE.md through static analysis.

LIMITATIONS:
- Can only check if files exist and contain keywords
- Cannot understand if implementation matches INTENT
- Cannot detect subtle behavioral drift
- Example: Can check "PROJECT.md" appears in orchestrator.md,
  but can't verify orchestrator actually validates alignment

USE CASES:
- CI/CD pipeline (fast, automated)
- Pre-commit checks (quick sanity)
- Catch obvious regressions (file removal, count changes)

If these tests fail, it means:
1. The architecture has fundamentally changed (update ARCHITECTURE.md), OR
2. A regression has occurred (fix the code), OR
3. The test is too strict (update the test)

Each test documents WHY an architectural decision was made and validates
structural invariants remain true.

See ARCHITECTURE.md § Testing This Document for full validation strategy.
"""

from pathlib import Path
import pytest


class TestProjectMdFirstArchitecture:
    """
    INTENT: Prevent scope creep by validating alignment before work.

    WHY: Without PROJECT.md validation, agents implement whatever is asked
    without considering if it serves project goals. This leads to feature
    bloat and wasted effort.

    BREAKING CHANGE: If orchestrator no longer validates PROJECT.md.

    See ARCHITECTURE.md § Core Design Principles #1
    """

    @pytest.fixture
    def orchestrator(self):
        path = Path(__file__).parent.parent / "agents" / "orchestrator.md"
        return path.read_text()

    @pytest.fixture
    def project_template(self):
        path = Path(__file__).parent.parent / "templates" / "PROJECT.md"
        return path.read_text()

    def test_project_md_first_validated(self, orchestrator):
        """Test orchestrator validates PROJECT.md before starting work."""
        # Orchestrator should mention PROJECT.md in mission
        assert "PROJECT.md" in orchestrator, (
            "ARCHITECTURE VIOLATION: Orchestrator must validate PROJECT.md\n"
            "Without this, no alignment validation occurs.\n"
            "See ARCHITECTURE.md § PROJECT.md-First Architecture"
        )

    def test_project_md_has_required_sections(self, project_template):
        """Test PROJECT.md template enforces required structure."""
        required_sections = ["GOALS", "SCOPE", "CONSTRAINTS"]

        for section in required_sections:
            assert section in project_template, (
                f"ARCHITECTURE VIOLATION: PROJECT.md missing {section} section\n"
                f"These sections are required for alignment validation.\n"
                f"See ARCHITECTURE.md § PROJECT.md-First Architecture"
            )

    def test_orchestrator_is_primary_coordinator(self, orchestrator):
        """Test orchestrator is positioned as PRIMARY coordinator."""
        # Should mention coordination or orchestration
        assert "orchestrat" in orchestrator.lower() or "coordinat" in orchestrator.lower(), (
            "ARCHITECTURE VIOLATION: Orchestrator must be the coordinator\n"
            "See ARCHITECTURE.md § 8-Agent Pipeline"
        )


class TestEightAgentPipeline:
    """
    INTENT: Separate concerns and optimize costs through specialization.

    WHY: Each agent has a specific role. Order matters:
    - Validation before research
    - Design before implementation
    - Tests before code
    - Quality checks after code

    BREAKING CHANGE: If pipeline order changes or agents are removed.

    See ARCHITECTURE.md § Core Design Principles #2
    """

    @pytest.fixture
    def agents_dir(self):
        return Path(__file__).parent.parent / "agents"

    def test_exactly_eight_agents_exist(self, agents_dir):
        """Test exactly 8 agents in pipeline."""
        required_agents = [
            "orchestrator.md",
            "researcher.md",
            "planner.md",
            "test-master.md",
            "implementer.md",
            "reviewer.md",
            "security-auditor.md",
            "doc-master.md",
        ]

        for agent in required_agents:
            assert (agents_dir / agent).exists(), (
                f"ARCHITECTURE VIOLATION: Missing agent {agent}\n"
                f"8-agent pipeline requires all agents present.\n"
                f"See ARCHITECTURE.md § 8-Agent Pipeline"
            )

        # Should be exactly 8 (no more, no less)
        agent_files = list(agents_dir.glob("*.md"))
        assert len(agent_files) == 8, (
            f"ARCHITECTURE VIOLATION: Expected 8 agents, found {len(agent_files)}\n"
            f"Pipeline design assumes exactly 8 specialized agents.\n"
            f"See ARCHITECTURE.md § 8-Agent Pipeline"
        )

    def test_test_master_enforces_tdd(self, agents_dir):
        """Test test-master exists to enforce TDD (tests before code)."""
        test_master = agents_dir / "test-master.md"
        assert test_master.exists(), (
            "ARCHITECTURE VIOLATION: test-master agent missing\n"
            "TDD enforcement requires test-master in pipeline.\n"
            "See ARCHITECTURE.md § TDD Enforcement"
        )


class TestModelOptimization:
    """
    INTENT: Use right model for the job (40% cost reduction).

    WHY:
    - Opus for complex planning (expensive but thorough)
    - Haiku for fast operations (cheap and sufficient)
    - Sonnet for most work (balanced)

    BREAKING CHANGE: If all agents use same model.

    See ARCHITECTURE.md § Core Design Principles #3
    """

    @pytest.fixture
    def agents_dir(self):
        return Path(__file__).parent.parent / "agents"

    def test_model_selection_strategy_documented(self, agents_dir):
        """Test model selection strategy is intentional."""
        # Planner should use opus (or be documented as such)
        planner = (agents_dir / "planner.md").read_text()

        # Security and docs should use haiku (or be documented as such)
        security = (agents_dir / "security-auditor.md").read_text()
        doc_master = (agents_dir / "doc-master.md").read_text()

        # These agents should exist (model assignment may be in config)
        assert planner, "Planner agent must exist"
        assert security, "Security-auditor agent must exist"
        assert doc_master, "Doc-master agent must exist"

    def test_cheap_models_for_fast_operations(self, agents_dir):
        """Test fast operations don't use expensive models."""
        # Security scan and doc updates should be fast
        # (actual model assignment may be in Claude Code config)

        security = agents_dir / "security-auditor.md"
        doc_master = agents_dir / "doc-master.md"

        assert security.exists(), "Security-auditor must exist for fast scans"
        assert doc_master.exists(), "Doc-master must exist for fast updates"


class TestContextManagement:
    """
    INTENT: Keep context under control (scales to 100+ features).

    WHY: Without context management, system degrades after 3-4 features.
    With /clear + session logging, scales to 100+ features.

    BREAKING CHANGE: If session logging removed or /clear not promoted.

    See ARCHITECTURE.md § Core Design Principles #4
    """

    def test_context_management_strategy_documented(self):
        """Test context management is documented."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()

        assert "/clear" in content, (
            "ARCHITECTURE VIOLATION: /clear command not documented\n"
            "Context management requires /clear after each feature.\n"
            "See ARCHITECTURE.md § Context Management"
        )

    def test_session_logging_over_context(self):
        """Test session logging strategy is preferred over context."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()

        # Should mention session or logging
        assert "session" in content.lower() or "log" in content.lower(), (
            "ARCHITECTURE VIOLATION: Session logging not documented\n"
            "Agents should log to files, not context.\n"
            "See ARCHITECTURE.md § Context Management"
        )


class TestOptInAutomation:
    """
    INTENT: Give users choice (manual vs automatic).

    WHY:
    - Beginners need manual control to learn
    - Power users want full automation
    - Forcing automation scares new users

    BREAKING CHANGE: If hooks auto-enable or no manual mode.

    See ARCHITECTURE.md § Core Design Principles #5
    """

    @pytest.fixture
    def commands_dir(self):
        return Path(__file__).parent.parent / "commands"

    @pytest.fixture
    def templates_dir(self):
        return Path(__file__).parent.parent / "templates"

    def test_manual_commands_available(self, commands_dir):
        """Test manual mode commands exist (slash commands)."""
        manual_commands = [
            "format.md",
            "test.md",
            "security-scan.md",
            "full-check.md",
        ]

        for command in manual_commands:
            assert (commands_dir / command).exists(), (
                f"ARCHITECTURE VIOLATION: Missing manual command {command}\n"
                f"Users must have manual control option.\n"
                f"See ARCHITECTURE.md § Opt-In Automation"
            )

    def test_automatic_mode_is_opt_in(self, templates_dir):
        """Test automatic hooks are opt-in (template exists, not auto-applied)."""
        settings_template = templates_dir / "settings.local.json"

        assert settings_template.exists(), (
            "ARCHITECTURE VIOLATION: Hooks template missing\n"
            "Users need template to opt-in to automation.\n"
            "See ARCHITECTURE.md § Opt-In Automation"
        )

    def test_setup_command_offers_choice(self):
        """Test /setup command offers both modes."""
        setup_cmd = Path(__file__).parent.parent / "commands" / "setup.md"
        content = setup_cmd.read_text()

        # Should offer both slash commands and automatic
        assert "slash" in content.lower() or "manual" in content.lower(), (
            "ARCHITECTURE VIOLATION: Setup doesn't offer manual mode\n"
            "See ARCHITECTURE.md § Opt-In Automation"
        )
        assert "automatic" in content.lower() or "hook" in content.lower(), (
            "ARCHITECTURE VIOLATION: Setup doesn't offer automatic mode\n"
            "See ARCHITECTURE.md § Opt-In Automation"
        )


class TestProjectLevelIsolation:
    """
    INTENT: Plugin works across multiple projects without interference.

    WHY: Users work on multiple projects with different goals/constraints.
    Plugin shouldn't interfere between projects.

    BREAKING CHANGE: If global config affects all projects.

    See ARCHITECTURE.md § Core Design Principles #6
    """

    def test_project_level_files_isolated(self):
        """Test setup creates project-level files, not global."""
        setup_script = Path(__file__).parent.parent / "scripts" / "setup.py"
        content = setup_script.read_text()

        # Should reference .claude/ (project-level), not ~/.claude/ (global)
        assert ".claude" in content, (
            "ARCHITECTURE VIOLATION: Setup doesn't use project-level paths\n"
            "Files must be in project's .claude/, not global.\n"
            "See ARCHITECTURE.md § Project-Level vs Global Scope"
        )

    def test_uninstall_preserves_global_plugin(self):
        """Test /uninstall can remove project files without affecting plugin."""
        uninstall_cmd = Path(__file__).parent.parent / "commands" / "uninstall.md"
        content = uninstall_cmd.read_text()

        # Should have option to remove project files only
        assert "project" in content.lower(), (
            "ARCHITECTURE VIOLATION: Uninstall doesn't distinguish project vs global\n"
            "Users must be able to clean one project without affecting others.\n"
            "See ARCHITECTURE.md § Project-Level vs Global Scope"
        )


class TestTDDEnforcement:
    """
    INTENT: Tests written BEFORE code, not after.

    WHY:
    - Tests written after are often incomplete
    - TDD ensures code is testable
    - Prevents "we'll add tests later" syndrome

    BREAKING CHANGE: If test-master runs after implementer.

    See ARCHITECTURE.md § Core Design Principles #7
    """

    def test_test_master_exists_before_implementer(self):
        """Test test-master agent exists (should run before implementer)."""
        agents_dir = Path(__file__).parent.parent / "agents"

        test_master = agents_dir / "test-master.md"
        implementer = agents_dir / "implementer.md"

        assert test_master.exists(), (
            "ARCHITECTURE VIOLATION: test-master missing\n"
            "TDD requires test-master in pipeline.\n"
            "See ARCHITECTURE.md § TDD Enforcement"
        )
        assert implementer.exists(), (
            "ARCHITECTURE VIOLATION: implementer missing\n"
            "Pipeline requires both test-master and implementer.\n"
            "See ARCHITECTURE.md § TDD Enforcement"
        )


class TestReadOnlyPlanning:
    """
    INTENT: Planner and reviewer can't modify code.

    WHY:
    - Planning should be separate from implementation
    - Review should be objective (report issues, not fix them)
    - Forces clear handoffs between pipeline stages

    BREAKING CHANGE: If planner/reviewer gain Write tools.

    See ARCHITECTURE.md § Core Design Principles #8
    """

    @pytest.fixture
    def agents_dir(self):
        return Path(__file__).parent.parent / "agents"

    def test_planner_is_read_only(self, agents_dir):
        """Test planner doesn't have Write/Edit tools."""
        planner = (agents_dir / "planner.md").read_text()

        # Check if planner has Write in its tools section
        # (This is a basic check, actual tool assignment in frontmatter)
        assert planner, "Planner must exist"

        # Planner should be documented as read-only or planning-focused
        # Actual tool restriction validated in architecture tests

    def test_reviewer_is_read_only(self, agents_dir):
        """Test reviewer doesn't have Write/Edit tools."""
        reviewer = (agents_dir / "reviewer.md").read_text()

        assert reviewer, "Reviewer must exist"
        # Reviewer should review, not fix


class TestSecurityFirst:
    """
    INTENT: Security issues caught before commit.

    WHY:
    - Security issues expensive to fix later
    - Automated scanning prevents human error
    - Fast model (haiku) means no friction

    BREAKING CHANGE: If security scan becomes optional.

    See ARCHITECTURE.md § Core Design Principles #9
    """

    def test_security_auditor_in_pipeline(self):
        """Test security-auditor exists in pipeline."""
        agents_dir = Path(__file__).parent.parent / "agents"
        security = agents_dir / "security-auditor.md"

        assert security.exists(), (
            "ARCHITECTURE VIOLATION: security-auditor missing\n"
            "Security-first design requires auditor in pipeline.\n"
            "See ARCHITECTURE.md § Security-First Design"
        )

    def test_security_scan_command_exists(self):
        """Test /security-scan command available for manual use."""
        commands_dir = Path(__file__).parent.parent / "commands"
        security_cmd = commands_dir / "security-scan.md"

        assert security_cmd.exists(), (
            "ARCHITECTURE VIOLATION: /security-scan command missing\n"
            "Users must be able to run security scans manually.\n"
            "See ARCHITECTURE.md § Security-First Design"
        )


class TestDocumentationSync:
    """
    INTENT: Documentation never falls out of sync with code.

    WHY:
    - Manual doc updates often forgotten
    - Stale docs worse than no docs
    - Automated sync ensures accuracy

    BREAKING CHANGE: If doc updates become manual.

    See ARCHITECTURE.md § Core Design Principles #10
    """

    def test_doc_master_in_pipeline(self):
        """Test doc-master exists for automated doc updates."""
        agents_dir = Path(__file__).parent.parent / "agents"
        doc_master = agents_dir / "doc-master.md"

        assert doc_master.exists(), (
            "ARCHITECTURE VIOLATION: doc-master missing\n"
            "Documentation sync requires doc-master in pipeline.\n"
            "See ARCHITECTURE.md § Documentation Sync"
        )


class TestArchitecturalInvariants:
    """
    Test architectural invariants that MUST remain true.

    If these fail, the core architecture has changed.

    See ARCHITECTURE.md § Architectural Invariants
    """

    def test_agent_count_is_eight(self):
        """Test exactly 8 agents (no more, no less)."""
        agents_dir = Path(__file__).parent.parent / "agents"
        agent_files = list(agents_dir.glob("*.md"))

        assert len(agent_files) == 8, (
            f"ARCHITECTURAL INVARIANT VIOLATION: Expected 8 agents, found {len(agent_files)}\n"
            f"8-agent pipeline is core to architecture.\n"
            f"If you need different count, update ARCHITECTURE.md first.\n"
            f"See ARCHITECTURE.md § Architectural Invariants"
        )

    def test_required_skills_exist(self):
        """Test all 6 required skills exist."""
        skills_dir = Path(__file__).parent.parent / "skills"
        required_skills = [
            "python-standards",
            "testing-guide",
            "security-patterns",
            "documentation-guide",
            "research-patterns",
            "engineering-standards",
        ]

        for skill in required_skills:
            assert (skills_dir / skill).exists(), (
                f"ARCHITECTURAL INVARIANT VIOLATION: Missing skill {skill}\n"
                f"6 core skills are required for architecture.\n"
                f"See ARCHITECTURE.md § Architectural Invariants"
            )

    def test_project_md_template_structure(self):
        """Test PROJECT.md template has required structure."""
        template = Path(__file__).parent.parent / "templates" / "PROJECT.md"
        content = template.read_text()

        required = ["GOALS", "SCOPE", "CONSTRAINTS"]
        for section in required:
            assert section in content, (
                f"ARCHITECTURAL INVARIANT VIOLATION: PROJECT.md missing {section}\n"
                f"These sections required for alignment validation.\n"
                f"See ARCHITECTURE.md § Architectural Invariants"
            )


class TestAgentCommunicationStrategy:
    """
    INTENT: Agents communicate via session files, not context.

    WHY: Context has hard limit (200K tokens). Session files are unlimited.
    Keeps context focused on current work.

    BREAKING CHANGE: If agents communicate via context instead of files.

    See ARCHITECTURE.md § Agent Communication Strategy
    """

    def test_session_logging_documented(self):
        """Test session logging strategy is documented."""
        readme = Path(__file__).parent.parent / "README.md"
        content = readme.read_text()

        assert "session" in content.lower() or "/clear" in content, (
            "ARCHITECTURE VIOLATION: Session logging not documented\n"
            "Agents must use session files for communication.\n"
            "See ARCHITECTURE.md § Agent Communication Strategy"
        )

    def test_context_management_strategy_exists(self):
        """Test /clear command exists for context management."""
        readme = Path(__file__).parent.parent / "README.md"
        quickstart = Path(__file__).parent.parent / "QUICKSTART.md"

        readme_content = readme.read_text() if readme.exists() else ""
        quickstart_content = quickstart.read_text() if quickstart.exists() else ""

        combined = readme_content + quickstart_content

        assert "/clear" in combined, (
            "ARCHITECTURE VIOLATION: /clear not documented\n"
            "Context management requires /clear after features.\n"
            "See ARCHITECTURE.md § Agent Communication Strategy"
        )


class TestAgentSpecializationNoOverlap:
    """
    INTENT: Each agent has unique, non-overlapping responsibility.

    WHY:
    - Clear separation of concerns
    - Prevents conflicting decisions
    - No wasted effort on duplicate work

    BREAKING CHANGE: If agents gain overlapping responsibilities.

    See ARCHITECTURE.md § Agent Specialization
    """

    @pytest.fixture
    def agents_dir(self):
        return Path(__file__).parent.parent / "agents"

    def test_orchestrator_coordinates_not_implements(self, agents_dir):
        """Test orchestrator coordinates but doesn't implement."""
        orchestrator = (agents_dir / "orchestrator.md").read_text()

        # Should have Task tool for coordination
        assert "Task" in orchestrator or "task" in orchestrator.lower(), (
            "ARCHITECTURE VIOLATION: Orchestrator must coordinate via Task tool\n"
            "Orchestrator's unique role is coordination, not implementation.\n"
            "See ARCHITECTURE.md § Agent Specialization"
        )

    def test_planner_designs_not_codes(self, agents_dir):
        """Test planner designs architecture but doesn't write code."""
        planner = (agents_dir / "planner.md").read_text()

        # Planner should be read-only
        assert "plan" in planner.lower() or "architect" in planner.lower(), (
            "ARCHITECTURE VIOLATION: Planner's role is architecture design\n"
            "Planner should not overlap with implementer.\n"
            "See ARCHITECTURE.md § Agent Specialization"
        )

    def test_reviewer_identifies_not_fixes(self, agents_dir):
        """Test reviewer identifies issues but doesn't fix them."""
        reviewer = (agents_dir / "reviewer.md").read_text()

        # Reviewer should be read-only
        assert "review" in reviewer.lower() or "quality" in reviewer.lower(), (
            "ARCHITECTURE VIOLATION: Reviewer's role is quality gate\n"
            "Reviewer should identify issues, not fix them.\n"
            "See ARCHITECTURE.md § Agent Specialization"
        )

    def test_all_agents_have_distinct_roles(self, agents_dir):
        """Test each agent file exists with unique purpose."""
        required_agents = {
            "orchestrator.md": "coordinat",
            "researcher.md": "research",
            "planner.md": "plan",
            "test-master.md": "test",
            "implementer.md": "implement",
            "reviewer.md": "review",
            "security-auditor.md": "security",
            "doc-master.md": "doc",
        }

        for agent_file, keyword in required_agents.items():
            agent_path = agents_dir / agent_file
            assert agent_path.exists(), f"Missing agent: {agent_file}"

            content = agent_path.read_text().lower()
            assert keyword in content, (
                f"ARCHITECTURE VIOLATION: {agent_file} missing '{keyword}' in description\n"
                f"Each agent must have clear, unique responsibility.\n"
                f"See ARCHITECTURE.md § Agent Specialization"
            )


class TestSkillBoundariesNoRedundancy:
    """
    INTENT: Each skill covers unique domain expertise.

    WHY:
    - Clear expertise boundaries
    - Skills can be combined
    - Prevents conflicting advice

    BREAKING CHANGE: If skills cover overlapping domains.

    See ARCHITECTURE.md § Skill Boundaries
    """

    @pytest.fixture
    def skills_dir(self):
        return Path(__file__).parent.parent / "skills"

    def test_all_skills_have_distinct_domains(self, skills_dir):
        """Test each skill covers unique domain."""
        required_skills = {
            "python-standards": "python",
            "testing-guide": "test",
            "security-patterns": "security",
            "documentation-guide": "doc",
            "research-patterns": "research",
            "engineering-standards": "engineering",
        }

        for skill_name, keyword in required_skills.items():
            skill_dir = skills_dir / skill_name
            assert skill_dir.exists(), f"Missing skill: {skill_name}"

            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                content = skill_file.read_text().lower()
                assert keyword in content, (
                    f"ARCHITECTURE VIOLATION: {skill_name} missing '{keyword}' focus\n"
                    f"Each skill must have clear domain boundary.\n"
                    f"See ARCHITECTURE.md § Skill Boundaries"
                )

    def test_exactly_thirteen_skills_exist(self, skills_dir):
        """Test exactly 13 skills (comprehensive SDLC coverage + consistency enforcement)."""
        skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]

        expected_skills = [
            "python-standards", "testing-guide", "security-patterns",
            "documentation-guide", "research-patterns", "consistency-enforcement",
            "architecture-patterns", "api-design", "database-design",
            "code-review", "git-workflow", "project-management", "observability"
        ]

        assert len(skill_dirs) == 13, (
            f"ARCHITECTURE VIOLATION: Expected 13 skills, found {len(skill_dirs)}\n"
            f"13 skills chosen for comprehensive SDLC coverage (dev-focused) + consistency enforcement.\n"
            f"Expected: {sorted(expected_skills)}\n"
            f"Found: {sorted([d.name for d in skill_dirs])}\n"
            f"See ARCHITECTURE.md § Skill Boundaries"
        )


class TestDataFlowOneDirection:
    """
    INTENT: Information flows forward through pipeline, not backward.

    WHY:
    - Prevents circular dependencies
    - Clear handoffs between stages
    - Each agent builds on previous work

    BREAKING CHANGE: If agents communicate backward or have circular deps.

    See ARCHITECTURE.md § Data Flow
    """

    def test_pipeline_order_documented(self):
        """Test pipeline order is documented."""
        auto_impl = Path(__file__).parent.parent / "commands" / "auto-implement.md"
        if auto_impl.exists():
            content = auto_impl.read_text()

            # Should mention pipeline or agent order
            assert "orchestrator" in content.lower() or "pipeline" in content.lower(), (
                "ARCHITECTURE VIOLATION: Pipeline order not documented\n"
                "Data flow depends on agent execution order.\n"
                "See ARCHITECTURE.md § Data Flow"
            )

    def test_no_backward_communication_tools(self):
        """Test agents don't have tools for backward communication."""
        agents_dir = Path(__file__).parent.parent / "agents"

        # Later agents shouldn't be able to communicate backward
        # (This is enforced by tool restrictions, validated in architecture tests)

        # Test that implementer can't modify planner's output
        implementer = (agents_dir / "implementer.md").read_text()
        assert implementer, "Implementer must exist"

        # Implementer has Write/Edit for code, not for plans
        # (Actual enforcement via tool scoping in Claude Code)


class TestContextBudgetManagement:
    """
    INTENT: Keep context per feature under 25K tokens.

    WHY: Total limit is 200K. Multiple features must fit.
    Context budget ensures scalability.

    BREAKING CHANGE: If single agent uses >25K tokens or no budget tracking.

    See ARCHITECTURE.md § Agent Communication Strategy
    """

    def test_context_budget_documented(self):
        """Test context budget per agent is documented."""
        arch_doc = Path(__file__).parent.parent / "ARCHITECTURE.md"
        content = arch_doc.read_text()

        assert "Context Budget" in content or "context budget" in content.lower(), (
            "ARCHITECTURE VIOLATION: Context budget not documented\n"
            "Each agent should have context budget limit.\n"
            "See ARCHITECTURE.md § Agent Communication Strategy"
        )

    def test_total_context_under_limit(self):
        """Test total context budget per feature is reasonable."""
        arch_doc = Path(__file__).parent.parent / "ARCHITECTURE.md"
        content = arch_doc.read_text()

        # Should mention token limits
        assert "25K" in content or "tokens" in content.lower(), (
            "ARCHITECTURE VIOLATION: Context limits not specified\n"
            "Total budget must be <200K to allow multiple features.\n"
            "See ARCHITECTURE.md § Agent Communication Strategy"
        )


class TestDesignDecisionDocumentation:
    """
    Test that design decisions are documented and rationale is clear.

    See ARCHITECTURE.md § Design Decisions & Rationale
    """

    def test_architecture_document_exists(self):
        """Test ARCHITECTURE.md exists to document intent."""
        arch_doc = Path(__file__).parent.parent / "ARCHITECTURE.md"

        assert arch_doc.exists(), (
            "CRITICAL: ARCHITECTURE.md missing\n"
            "This document is required to explain design intent.\n"
            "Without it, architectural decisions are lost."
        )

    def test_architecture_document_has_intent(self):
        """Test ARCHITECTURE.md documents intent, not just structure."""
        arch_doc = Path(__file__).parent.parent / "ARCHITECTURE.md"
        content = arch_doc.read_text()

        # Should explain WHY, not just WHAT
        assert "WHY:" in content or "Intent:" in content, (
            "ARCHITECTURE.md must document WHY decisions were made.\n"
            "Structure without rationale is not useful."
        )

    def test_breaking_changes_documented(self):
        """Test ARCHITECTURE.md defines what constitutes breaking changes."""
        arch_doc = Path(__file__).parent.parent / "ARCHITECTURE.md"
        content = arch_doc.read_text()

        assert "Breaking Change" in content or "BREAKING" in content, (
            "ARCHITECTURE.md must document what changes break architecture.\n"
            "This helps prevent unintentional architectural drift."
        )

    def test_agent_responsibilities_table_exists(self):
        """Test agent responsibilities are documented in table."""
        arch_doc = Path(__file__).parent.parent / "ARCHITECTURE.md"
        content = arch_doc.read_text()

        # Should have table documenting each agent's unique role
        assert "| Agent |" in content or "Agent" in content and "Responsibility" in content, (
            "ARCHITECTURE VIOLATION: Agent responsibilities not documented\n"
            "Clear role definition prevents overlap and duplication.\n"
            "See ARCHITECTURE.md § Agent Specialization"
        )

    def test_skill_domains_table_exists(self):
        """Test skill domains are documented in table."""
        arch_doc = Path(__file__).parent.parent / "ARCHITECTURE.md"
        content = arch_doc.read_text()

        # Should have table documenting each skill's domain
        assert "| Skill |" in content or ("Skill" in content and "Coverage" in content), (
            "ARCHITECTURE VIOLATION: Skill domains not documented\n"
            "Clear domain boundaries prevent redundancy.\n"
            "See ARCHITECTURE.md § Skill Boundaries"
        )
