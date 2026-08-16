"""Spec-validation tests for Issue #842: Prompt quality gate.

Tests behavioral compliance with the spec:
1. lib/prompt_quality_rules.py has check_persona, check_casual_register,
   check_constraint_density, check_all functions.
2. tests/unit/test_prompt_quality.py exists with agent file inspection tests.
3. test_routing_config.json maps agent_prompt -> unit: true.
4. Layer 6 in unified_pre_tool.py blocks Write/Edit to agents/*.md or
   commands/*.md when content contains prompt anti-patterns.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

# Repo-relative anchor (Issue #1518): this file lives at tests/spec_validation/,
# so parents[2] is the repo root. Derived from __file__ so it resolves correctly in
# a git worktree AND in the canonical checkout, and survives fresh clones. The
# previous value was a hardcoded developer-specific absolute path to an ephemeral
# build worktree; when that worktree was deleted every assertion in this file raised
# FileNotFoundError, leaving all 35 tests unconditionally red for four months.
# The name WORKTREE is kept because it is referenced throughout this file.
WORKTREE = Path(__file__).resolve().parents[2]
LIB_DIR = WORKTREE / "plugins" / "autonomous-dev" / "lib"
HOOKS_DIR = WORKTREE / "plugins" / "autonomous-dev" / "hooks"
CONFIG_PLUGIN = WORKTREE / "plugins" / "autonomous-dev" / "config" / "test_routing_config.json"
CONFIG_CLAUDE = WORKTREE / ".claude" / "config" / "test_routing_config.json"
UNIT_TEST_FILE = WORKTREE / "tests" / "unit" / "test_prompt_quality.py"
AGENTS_DIR = WORKTREE / "plugins" / "autonomous-dev" / "agents"


def _load_prompt_quality_rules():
    """Import prompt_quality_rules module from lib."""
    mod_path = LIB_DIR / "prompt_quality_rules.py"
    spec = importlib.util.spec_from_file_location("prompt_quality_rules", str(mod_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ============================================================================
# Criterion 1: lib/prompt_quality_rules.py exists with required functions
# ============================================================================


class TestSpec842LibExists:
    """Verify prompt_quality_rules.py exists and exposes the required API."""

    def test_spec_842_1a_module_exists(self) -> None:
        """prompt_quality_rules.py MUST exist in lib/."""
        assert (LIB_DIR / "prompt_quality_rules.py").is_file()

    def test_spec_842_1b_check_persona_callable(self) -> None:
        """check_persona MUST be a callable function."""
        mod = _load_prompt_quality_rules()
        assert callable(getattr(mod, "check_persona", None))

    def test_spec_842_1c_check_casual_register_callable(self) -> None:
        """check_casual_register MUST be a callable function."""
        mod = _load_prompt_quality_rules()
        assert callable(getattr(mod, "check_casual_register", None))

    def test_spec_842_1d_check_constraint_density_callable(self) -> None:
        """check_constraint_density MUST be a callable function."""
        mod = _load_prompt_quality_rules()
        assert callable(getattr(mod, "check_constraint_density", None))

    def test_spec_842_1e_check_all_callable(self) -> None:
        """check_all MUST be a callable function."""
        mod = _load_prompt_quality_rules()
        assert callable(getattr(mod, "check_all", None))


# ============================================================================
# Criterion 2: check_persona detects banned openers, allows role assignments
# ============================================================================


class TestSpec842CheckPersona:
    """Behavioral tests for check_persona."""

    def test_spec_842_2a_catches_expert(self) -> None:
        """'You are an expert' MUST be flagged."""
        mod = _load_prompt_quality_rules()
        violations = mod.check_persona("You are an expert Python developer.")
        assert len(violations) >= 1

    def test_spec_842_2b_catches_senior(self) -> None:
        """'You are a senior' MUST be flagged."""
        mod = _load_prompt_quality_rules()
        violations = mod.check_persona("You are a senior engineer.")
        assert len(violations) >= 1

    def test_spec_842_2c_catches_world_class(self) -> None:
        """'You are a world-class' MUST be flagged."""
        mod = _load_prompt_quality_rules()
        violations = mod.check_persona("You are a world-class architect.")
        assert len(violations) >= 1

    def test_spec_842_2d_allows_role_assignment(self) -> None:
        """'You are the **implementer** agent' MUST NOT be flagged."""
        mod = _load_prompt_quality_rules()
        violations = mod.check_persona("You are the **implementer** agent.")
        assert len(violations) == 0

    def test_spec_842_2e_allows_normal_content(self) -> None:
        """Normal markdown content MUST NOT be flagged."""
        mod = _load_prompt_quality_rules()
        violations = mod.check_persona("## Mission\n\nImplement high-quality code.")
        assert len(violations) == 0


# ============================================================================
# Criterion 3: check_casual_register detects weak phrases
# ============================================================================


class TestSpec842CheckCasualRegister:
    """Behavioral tests for check_casual_register."""

    @pytest.mark.parametrize(
        "phrase",
        ["Make sure the tests pass.", "Try to keep it clean.", "Feel free to refactor.",
         "You should test.", "Check for imports.", "Look for patterns."],
        ids=["make_sure", "try_to", "feel_free", "you_should", "check_for", "look_for"],
    )
    def test_spec_842_3a_catches_casual_phrases(self, phrase: str) -> None:
        """Each casual register phrase MUST be flagged."""
        mod = _load_prompt_quality_rules()
        violations = mod.check_casual_register(phrase)
        assert len(violations) >= 1

    def test_spec_842_3b_allows_formal_directives(self) -> None:
        """Formal directives (MUST, REQUIRED, FORBIDDEN) MUST NOT be flagged."""
        mod = _load_prompt_quality_rules()
        content = "You MUST write tests.\nREQUIRED: type hints.\nFORBIDDEN: bare except."
        violations = mod.check_casual_register(content)
        assert len(violations) == 0

    def test_spec_842_3c_reports_line_numbers(self) -> None:
        """Violations MUST include line numbers."""
        mod = _load_prompt_quality_rules()
        content = "Line one.\nLine two.\nMake sure it works."
        violations = mod.check_casual_register(content)
        assert len(violations) >= 1
        assert "3" in violations[0]  # Line 3


# ============================================================================
# Criterion 4: check_constraint_density flags oversized sections
# ============================================================================


class TestSpec842CheckConstraintDensity:
    """Behavioral tests for check_constraint_density."""

    def test_spec_842_4a_flags_oversized_section(self) -> None:
        """A section with 9 bullet items MUST be flagged (threshold=8)."""
        mod = _load_prompt_quality_rules()
        lines = ["## Rules"] + [f"- Rule {i}" for i in range(9)]
        violations = mod.check_constraint_density("\n".join(lines))
        assert len(violations) >= 1

    def test_spec_842_4b_allows_at_threshold(self) -> None:
        """A section with exactly 8 bullet items MUST NOT be flagged."""
        mod = _load_prompt_quality_rules()
        lines = ["## Rules"] + [f"- Rule {i}" for i in range(8)]
        violations = mod.check_constraint_density("\n".join(lines))
        assert len(violations) == 0

    def test_spec_842_4c_under_threshold_passes(self) -> None:
        """A section with 5 bullet items MUST NOT be flagged."""
        mod = _load_prompt_quality_rules()
        lines = ["## Rules"] + [f"- Rule {i}" for i in range(5)]
        violations = mod.check_constraint_density("\n".join(lines))
        assert len(violations) == 0


# ============================================================================
# Criterion 5: check_all aggregates all checks
# ============================================================================


class TestSpec842CheckAll:
    """Behavioral tests for check_all."""

    def test_spec_842_5a_combines_all_violations(self) -> None:
        """check_all MUST return violations from persona + casual + density."""
        mod = _load_prompt_quality_rules()
        content = "You are an expert coder.\nMake sure you test.\n## Rules\n"
        content += "\n".join(f"- Rule {i}" for i in range(10))
        violations = mod.check_all(content)
        # At least one from each: persona, casual register, constraint density
        assert len(violations) >= 3

    def test_spec_842_5b_clean_content_returns_empty(self) -> None:
        """Clean content MUST return empty violations list."""
        mod = _load_prompt_quality_rules()
        content = "You are the **reviewer** agent.\n\n## Mission\n\n- MUST check quality\n"
        violations = mod.check_all(content)
        assert violations == []


# ============================================================================
# Criterion 6: tests/unit/test_prompt_quality.py exists with agent inspection
# ============================================================================


class TestSpec842UnitTestFile:
    """Verify the unit test file exists and covers agent files."""

    def test_spec_842_6a_unit_test_file_exists(self) -> None:
        """tests/unit/test_prompt_quality.py MUST exist."""
        assert UNIT_TEST_FILE.is_file()

    def test_spec_842_6b_has_agent_file_parametrization(self) -> None:
        """Unit test file MUST contain parametrized tests over agent .md files."""
        content = UNIT_TEST_FILE.read_text(encoding="utf-8")
        assert "AGENT_FILES" in content
        assert "parametrize" in content
        assert "agent_file" in content

    def test_spec_842_6c_tests_all_three_checks(self) -> None:
        """Unit test file MUST test persona, casual register, and constraint density."""
        content = UNIT_TEST_FILE.read_text(encoding="utf-8")
        assert "check_persona" in content
        assert "check_casual_register" in content
        assert "check_constraint_density" in content


# ============================================================================
# Criterion 7: test_routing_config.json has agent_prompt -> unit: true
# ============================================================================


class TestSpec842TestRouting:
    """Verify test routing config maps agent_prompt to unit tests."""

    def test_spec_842_7a_plugin_config_agent_prompt_unit(self) -> None:
        """Plugin test_routing_config.json agent_prompt MUST have unit: true."""
        config = json.loads(CONFIG_PLUGIN.read_text())
        assert config["routing_rules"]["agent_prompt"]["unit"] is True

    def test_spec_842_7b_claude_config_agent_prompt_unit(self) -> None:
        """.claude test_routing_config.json agent_prompt MUST have unit: true."""
        config = json.loads(CONFIG_CLAUDE.read_text())
        assert config["routing_rules"]["agent_prompt"]["unit"] is True

    def test_spec_842_7c_configs_are_consistent(self) -> None:
        """Both test_routing_config.json files MUST have identical content."""
        plugin = json.loads(CONFIG_PLUGIN.read_text())
        claude = json.loads(CONFIG_CLAUDE.read_text())
        assert plugin == claude


# ============================================================================
# Criterion 8: Layer 6 in unified_pre_tool.py blocks anti-patterns
# ============================================================================


class TestSpec842Layer6Hook:
    """Verify Layer 6 prompt quality gate exists in unified_pre_tool.py."""

    def test_spec_842_8a_layer6_present(self) -> None:
        """unified_pre_tool.py MUST contain Layer 6 prompt quality gate."""
        hook_path = HOOKS_DIR / "unified_pre_tool.py"
        content = hook_path.read_text(encoding="utf-8")
        assert "Layer 6" in content
        assert "Prompt quality" in content or "prompt quality" in content

    def test_spec_842_8b_handles_write_tool(self) -> None:
        """Layer 6 MUST handle Write tool for agents/ and commands/ .md files."""
        hook_path = HOOKS_DIR / "unified_pre_tool.py"
        content = hook_path.read_text(encoding="utf-8")
        assert "/agents/" in content
        assert "/commands/" in content
        assert '"Write"' in content or "'Write'" in content

    def test_spec_842_8c_handles_edit_tool(self) -> None:
        """Layer 6 MUST handle Edit tool for agents/ and commands/ .md files."""
        hook_path = HOOKS_DIR / "unified_pre_tool.py"
        content = hook_path.read_text(encoding="utf-8")
        assert '"Edit"' in content or "'Edit'" in content

    def test_spec_842_8d_invokes_prompt_quality_rules(self) -> None:
        """Layer 6 MUST invoke the prompt_quality_rules checks.

        Originally this asserted the hook called the aggregate ``check_all``.
        Issue #1038 made the Edit path diff-aware: it compares violations in the
        new content against violations already present in the existing file, so a
        pre-existing oversized section or persona phrase does not block an edit
        that never touches it. ``check_all`` cannot express that diff (it returns
        violations for the whole document), so the hook now calls the individual
        rule functions instead. What matters for the spec is that the hook wires
        in prompt_quality_rules and actually runs at least one rule, not which
        specific function name it uses.
        """
        hook_path = HOOKS_DIR / "unified_pre_tool.py"
        content = hook_path.read_text(encoding="utf-8")
        assert "prompt_quality_rules" in content, (
            "unified_pre_tool.py must reference prompt_quality_rules — "
            "the prompt quality gate appears unwired."
        )
        rule_functions = ("check_persona", "check_casual_register")
        called = [fn for fn in rule_functions if fn in content]
        assert called, (
            "unified_pre_tool.py must call at least one prompt_quality_rules "
            f"rule function (one of {list(rule_functions)}) — the prompt quality "
            "gate imports the module but never runs a check."
        )

    def test_spec_842_8e_outputs_deny_on_violations(self) -> None:
        """Layer 6 MUST output deny decision when violations found."""
        hook_path = HOOKS_DIR / "unified_pre_tool.py"
        content = hook_path.read_text(encoding="utf-8")
        # After Layer 6 section, must have deny output
        assert "BLOCKED: Prompt quality violation" in content or "deny" in content


# ============================================================================
# Criterion 9: Existing agent files pass quality checks
# ============================================================================


class TestSpec842AgentFilesPass:
    """Existing agent .md files MUST pass the quality checks (no banned personas)."""

    def test_spec_842_9a_no_banned_personas_in_agents(self) -> None:
        """No existing agent .md file should have banned persona openers."""
        mod = _load_prompt_quality_rules()
        agent_files = sorted(
            p for p in AGENTS_DIR.glob("*.md")
            if "archived" not in str(p)
        )
        assert len(agent_files) > 0, "No agent files found"
        failures = []
        for agent_file in agent_files:
            content = agent_file.read_text(encoding="utf-8")
            violations = mod.check_persona(content)
            if violations:
                failures.append(f"{agent_file.name}: {violations}")
        assert failures == [], f"Agent files with banned personas:\n" + "\n".join(failures)
