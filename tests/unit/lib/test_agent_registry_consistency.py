#!/usr/bin/env python3
"""
Registry consistency tests for agent infrastructure.

These tests read real files to catch drift between:
- AGENT_CONFIGS in agent_invoker.py
- Agent .md files in agents/ and agents/archived/
- AGENT_SKILL_MAP in skill_loader.py
- MCP tool tokens cited in agent prose vs. tools:/optional_mcp: frontmatter
- Hosted web tools (WebSearch/WebFetch) declared anywhere in the declaration
  corpus. This module therefore also walks ``commands/*.md`` and
  ``skills/*/SKILL.md``, not agents/ alone — see ``TestNoHostedWebTools``.

Issue: #411 (Agent registry naming collisions)
Issue: #1546 (Agent MCP tool declarations must match cited prose and the
    read/write tool registries in tool_intent.py)
"""

import inspect
import re
import sys
from pathlib import Path

import pytest
import yaml

# Add project root to path for proper imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from plugins.autonomous_dev.lib.agent_invoker import AgentInvoker
from plugins.autonomous_dev.lib.skill_loader import AGENT_SKILL_MAP
from plugins.autonomous_dev.lib.tool_intent import (
    MCP_OPTIONAL_DECLARABLE_TOOLS,
    MCP_READ_TOOLS,
    MCP_WRITE_TOOLS,
    may_be_declared_optional,
)

AGENTS_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "agents"
ARCHIVED_DIR = AGENTS_DIR / "archived"

# Any ``mcp__<server>__<tool>`` token, including the wildcard ``__*`` form.
# The trailing class includes ``-`` because real MCP servers ship hyphenated
# tool names (e.g. ``mcp__ms365__send-mail``); without it the token would
# truncate at the hyphen and INV-1 would report a spurious violation on the
# truncated prefix.
MCP_TOKEN_RE = re.compile(r"mcp__[A-Za-z0-9_]+__[A-Za-z0-9_*-]+")

# Native tools that mutate the filesystem. Agents that are read-only by
# design (INV-4) must declare none of these.
NATIVE_WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})

# Agents that MUST stay read-only (Issue #1546, INV-4).
READ_ONLY_AGENTS = (
    "alignment-classifier",
    "planner",
    "researcher-local",
    "test-coverage-auditor",
)

# NOTE: there is deliberately no ``WRITE_CAPABLE_SERVERS`` allowance here.
# Deriving the wildcard rule from ``MCP_WRITE_TOOLS`` would only reject
# wildcards for servers we have *already* classified, which is "no wildcards
# for servers we already caught", not "no wildcards for unproven-safe
# servers". INV-3 rejects every wildcard in ``optional_mcp:`` instead — see
# ``check_agent_mcp_declarations``.


def _split_frontmatter(path: Path) -> "tuple[dict, str]":
    """Split an agent .md file into its YAML frontmatter and its body.

    Args:
        path: Path to the agent markdown file.

    Returns:
        Tuple of (frontmatter mapping, body text after the closing ``---``).

    Raises:
        ValueError: If the file has no frontmatter block, or the frontmatter
            is not parseable YAML, or does not parse to a mapping. Never
            silently skips a file — a malformed agent is a hard failure.
    """
    content = path.read_text(encoding="utf-8")
    if not content.lstrip().startswith("---"):
        raise ValueError(
            f"Agent file has no YAML frontmatter block: {path}\n"
            f"Expected the file to start with '---'\n"
            f"See: plugins/autonomous-dev/agents/planner.md for the canonical shape"
        )

    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError(
            f"Agent file frontmatter is not terminated: {path}\n"
            f"Expected an opening '---' and a closing '---'\n"
            f"See: plugins/autonomous-dev/agents/planner.md for the canonical shape"
        )

    try:
        frontmatter = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        raise ValueError(
            f"Agent file frontmatter is not parseable YAML: {path}\n"
            f"Expected: a YAML mapping with keys name, tools, ...\n"
            f"Parser said: {exc}"
        ) from exc

    if not isinstance(frontmatter, dict):
        raise ValueError(
            f"Agent file frontmatter did not parse to a mapping: {path}\n"
            f"Expected: a YAML mapping, got {type(frontmatter).__name__}\n"
            f"See: plugins/autonomous-dev/agents/planner.md for the canonical shape"
        )

    return frontmatter, parts[2]


def _parse_frontmatter(path: Path) -> dict:
    """Return the YAML frontmatter mapping of an agent .md file.

    Args:
        path: Path to the agent markdown file.

    Returns:
        The frontmatter as a dict.

    Raises:
        ValueError: If the frontmatter is missing or unparseable.
    """
    return _split_frontmatter(path)[0]


def _as_tool_list(value: object) -> "list[str]":
    """Normalize a frontmatter tool declaration to a list of tool names.

    Tolerates both the bracketed flow-sequence form (``tools: [Read, Grep]``)
    and the bare comma-separated form (``tools: Read, Grep, Glob``) used by
    alignment-classifier.md.

    Args:
        value: The raw YAML value of a ``tools:``/``optional_mcp:`` key.

    Returns:
        List of stripped tool-name strings. Empty list when the key is absent.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    raise ValueError(
        f"Unsupported tool declaration type: {type(value).__name__}\n"
        f"Expected: a YAML list or a comma-separated string\n"
        f"Got: {value!r}"
    )


def _declared_and_prose(path: Path) -> "tuple[set, set, set]":
    """Extract granted tools, optional MCP tools, and prose MCP tokens.

    Args:
        path: Path to the agent markdown file.

    Returns:
        Tuple of ``(granted, optional, prose)`` sets. ``granted`` is every
        entry of the frontmatter ``tools:`` key, ``optional`` every entry of
        ``optional_mcp:``, and ``prose`` every unique ``mcp__*`` token cited
        in the body (frontmatter excluded).

    Raises:
        ValueError: If the frontmatter is missing or unparseable.
    """
    frontmatter, body = _split_frontmatter(path)
    granted = set(_as_tool_list(frontmatter.get("tools")))
    optional = set(_as_tool_list(frontmatter.get("optional_mcp")))
    prose = set(MCP_TOKEN_RE.findall(body))
    return granted, optional, prose


def check_agent_mcp_declarations(path: Path) -> "list[str]":
    """Check INV-1..INV-3 and INV-5 for a single agent file.

    INV-1: every ``mcp__*`` token cited in the body is declared in ``tools:``
        or ``optional_mcp:`` (one violation per uncovered token).
    INV-2: every ``mcp__*`` entry in ``tools:`` is a member of
        ``MCP_READ_TOOLS``. This is an ALLOWLIST, not a denylist against
        ``MCP_WRITE_TOOLS`` — a denylist would permit tools that are in
        neither registry (e.g. ``mcp__serena__execute_shell_command``).
    INV-3: no declared tool (granted or optional) is a member of
        ``MCP_WRITE_TOOLS``, and ``optional_mcp:`` contains no wildcard at
        all, for any server. The blanket wildcard ban is deliberate: a
        wildcard asserts coverage over tools that do not exist yet and
        therefore cannot have been classified into either registry, so a
        rule derived from ``MCP_WRITE_TOOLS`` would rot the moment a new
        server or a new tool appears (the ``mcp__playwright__*`` case —
        ``browser_evaluate`` executes arbitrary JS and is in neither
        registry).
    INV-5: every CONCRETE (non-wildcard) ``optional_mcp:`` entry is
        declarable per ``tool_intent.may_be_declared_optional`` — i.e. a
        member of ``MCP_READ_TOOLS`` or of
        ``MCP_OPTIONAL_DECLARABLE_TOOLS``. This is the concrete-token
        analogue of the wildcard ban, and it is what INV-2 does NOT cover:
        INV-2 iterates ``granted`` only, so before INV-5 any concrete token
        from a server with zero ``MCP_WRITE_TOOLS`` entries passed all four
        invariants with zero violations no matter what the tool did.

    Args:
        path: Path to the agent markdown file.

    Returns:
        List of human-readable violation strings. Empty list means the agent
        satisfies INV-1, INV-2, INV-3 and INV-5.

    Raises:
        ValueError: If the frontmatter is missing or unparseable.
    """
    granted, optional, prose = _declared_and_prose(path)
    declared = granted | optional
    violations: "list[str]" = []

    # INV-1 — prose tokens must be declared.
    for token in sorted(prose - declared):
        violations.append(
            f"INV-1 {path.name}: body cites {token!r} but it is declared in "
            f"neither tools: nor optional_mcp:"
        )

    # INV-2 — granted MCP tools must be in the read allowlist.
    for tool in sorted(t for t in granted if t.startswith("mcp__")):
        if tool not in MCP_READ_TOOLS:
            violations.append(
                f"INV-2 {path.name}: tools: grants {tool!r} which is not in "
                f"MCP_READ_TOOLS (tool_intent.py). Only read-classified MCP "
                f"tools may be granted."
            )

    # INV-3 — nothing declared may be a known writer.
    for tool in sorted(t for t in declared if t in MCP_WRITE_TOOLS):
        violations.append(
            f"INV-3 {path.name}: declares {tool!r} which is in MCP_WRITE_TOOLS "
            f"(tool_intent.py). Agents must not declare mutating MCP tools."
        )

    # INV-3 (wildcard clause) — no wildcard in optional_mcp:, for any server.
    # A wildcard covers tools that do not exist yet and so cannot have been
    # classified as read or write; scoping the ban to already-classified
    # write servers would let an unclassified exec-capable tool (e.g.
    # mcp__playwright__browser_evaluate) ride in on the wildcard.
    for tool in sorted(t for t in optional if "*" in t):
        violations.append(
            f"INV-3 {path.name}: optional_mcp: declares wildcard {tool!r}. "
            f"Wildcards are forbidden outright — they assert coverage over "
            f"tools that may not exist yet and therefore cannot have been "
            f"classified. List the individual read tools instead."
        )

    # INV-5 — concrete optional_mcp entries must be on a positive allowlist.
    #
    # Wildcards are excluded here because they are not tool names and INV-3
    # already owns them; every other entry is checked, INCLUDING known
    # writers. The overlap with INV-3 on writers is deliberate
    # defence-in-depth: if the INV-3 write clause were ever weakened, INV-5
    # still refuses, because a writer is on neither allowlist.
    #
    # Note this rule is deliberately STRONGER than "must be classified".
    # mcp__playwright__browser_evaluate IS classified today — it is listed in
    # MCP_KNOWN_EXEC_TOOLS in scripts/audit_tool_intent_coverage.py — and a
    # classification-only rule would admit it. Executing caller-supplied
    # JavaScript is not something an availability check can bound, so
    # declarability is a separate allowlist rather than a corollary of
    # classification.
    for tool in sorted(t for t in optional if "*" not in t):
        if not may_be_declared_optional(tool):
            violations.append(
                f"INV-5 {path.name}: optional_mcp: declares {tool!r}, which is "
                f"on neither positive allowlist (MCP_READ_TOOLS or "
                f"MCP_OPTIONAL_DECLARABLE_TOOLS in tool_intent.py). Classify "
                f"the tool there with a rationale, or remove the declaration. "
                f"Being classified elsewhere as EXEC is NOT sufficient — "
                f"arbitrary-execution tools are refused by design."
            )

    return violations


def check_agent_no_write_tools(path: Path) -> "list[str]":
    """Check INV-4 — a read-only agent declares no native write tool.

    Args:
        path: Path to the agent markdown file.

    Returns:
        List of violation strings; empty when the agent declares no member of
        ``NATIVE_WRITE_TOOLS``.

    Raises:
        ValueError: If the frontmatter is missing or unparseable.
    """
    granted, optional, _ = _declared_and_prose(path)
    return [
        f"INV-4 {path.name}: declares native write tool {tool!r}; this agent "
        f"is read-only by design."
        for tool in sorted((granted | optional) & NATIVE_WRITE_TOOLS)
    ]


def _get_active_agent_names() -> set:
    """Get names of all active agent .md files (excluding archived/)."""
    return {
        f.stem
        for f in AGENTS_DIR.glob("*.md")
        if f.is_file()
    }


def _get_archived_agent_names() -> set:
    """Get names of all archived agent .md files."""
    if not ARCHIVED_DIR.exists():
        return set()
    return {
        f.stem
        for f in ARCHIVED_DIR.glob("*.md")
        if f.is_file() and f.stem != "README"
    }


class TestRegistryConsistency:
    """Verify consistency between AGENT_CONFIGS, agent files, and skill map."""

    def test_every_config_entry_has_agent_file(self):
        """Every AGENT_CONFIGS key must have a .md file in agents/ (not archived/)."""
        active_agents = _get_active_agent_names()
        config_agents = set(AgentInvoker.AGENT_CONFIGS.keys())

        missing_files = config_agents - active_agents
        assert not missing_files, (
            f"AGENT_CONFIGS entries without active agent files: {missing_files}\n"
            f"Either create the agent file or remove the config entry."
        )

    def test_every_agent_file_has_config_entry(self):
        """Every .md in agents/ (not archived/) must have an AGENT_CONFIGS entry."""
        active_agents = _get_active_agent_names()
        config_agents = set(AgentInvoker.AGENT_CONFIGS.keys())

        missing_configs = active_agents - config_agents
        assert not missing_configs, (
            f"Active agent files without AGENT_CONFIGS entries: {missing_configs}\n"
            f"Either add a config entry or archive the agent file."
        )

    def test_skill_map_agents_in_config(self):
        """Every AGENT_SKILL_MAP key must exist in AGENT_CONFIGS."""
        config_agents = set(AgentInvoker.AGENT_CONFIGS.keys())
        skill_map_agents = set(AGENT_SKILL_MAP.keys())

        missing = skill_map_agents - config_agents
        assert not missing, (
            f"AGENT_SKILL_MAP entries without AGENT_CONFIGS: {missing}\n"
            f"Either add to AGENT_CONFIGS or remove from AGENT_SKILL_MAP."
        )

    def test_no_agent_in_both_active_and_archived(self):
        """No .md filename should exist in both agents/ and agents/archived/."""
        active_agents = _get_active_agent_names()
        archived_agents = _get_archived_agent_names()

        duplicates = active_agents & archived_agents
        assert not duplicates, (
            f"Agent files in both active and archived: {duplicates}\n"
            f"Remove one copy to avoid confusion."
        )

    def test_config_entries_have_required_fields(self):
        """All AGENT_CONFIGS entries must have progress_pct, artifacts_required, description_template, mission."""
        required_fields = {"progress_pct", "artifacts_required", "description_template", "mission"}

        for agent_name, config in AgentInvoker.AGENT_CONFIGS.items():
            missing = required_fields - set(config.keys())
            assert not missing, (
                f"Agent '{agent_name}' missing required fields: {missing}"
            )

    def test_no_ghost_registrations(self):
        """All AGENT_CONFIGS entries must have active (not archived) agent files.

        Ghost registrations are config entries whose agent files only exist
        in agents/archived/ (or don't exist at all).
        """
        active_agents = _get_active_agent_names()
        config_agents = set(AgentInvoker.AGENT_CONFIGS.keys())

        ghosts = config_agents - active_agents
        assert not ghosts, (
            f"Ghost registrations (config entries without active agent files): {ghosts}\n"
            f"These agents are registered in AGENT_CONFIGS but their .md files "
            f"are missing or only in agents/archived/."
        )


def _active_agent_paths() -> "list[Path]":
    """Return every active agent .md path (non-recursive, archived/ excluded)."""
    return sorted(f for f in AGENTS_DIR.glob("*.md") if f.is_file())


class TestAgentMcpToolDeclarations:
    """Agent MCP declarations must match cited prose and the tool registries.

    Implements Issue #1546 invariants INV-1 through INV-5 over every active
    agent, plus negative controls that prove the checker refuses the cases it
    is meant to refuse and positive controls that prove it still permits the
    shipped declarations. A guard is unproven until watched doing both.
    """

    # ---- Positive: the live agent roster ---------------------------------

    def test_active_agents_discovered(self):
        """Sanity: the invariants below must actually be running on files."""
        paths = _active_agent_paths()
        assert len(paths) >= 15, (
            f"Expected the full active agent roster, found {len(paths)} in "
            f"{AGENTS_DIR}. An empty glob would make every invariant below "
            f"vacuously true."
        )

    def test_inv1_prose_mcp_tokens_are_declared(self):
        """INV-1: every mcp__ token cited in a body is declared."""
        violations = [
            v
            for path in _active_agent_paths()
            for v in check_agent_mcp_declarations(path)
            if v.startswith("INV-1")
        ]
        assert not violations, "Undeclared MCP tools in agent prose:\n" + "\n".join(
            violations
        )

    def test_inv2_granted_mcp_tools_are_read_only(self):
        """INV-2: granted mcp__ tools must be members of MCP_READ_TOOLS."""
        violations = [
            v
            for path in _active_agent_paths()
            for v in check_agent_mcp_declarations(path)
            if v.startswith("INV-2")
        ]
        assert not violations, "Non-read MCP tools granted:\n" + "\n".join(violations)

    def test_inv3_no_agent_declares_a_write_mcp_tool(self):
        """INV-3: no agent declares any MCP_WRITE_TOOLS member or write wildcard."""
        violations = [
            v
            for path in _active_agent_paths()
            for v in check_agent_mcp_declarations(path)
            if v.startswith("INV-3")
        ]
        assert not violations, "Mutating MCP tools declared:\n" + "\n".join(violations)

    @pytest.mark.parametrize("agent_name", READ_ONLY_AGENTS)
    def test_inv4_read_only_agents_declare_no_write_tool(self, agent_name):
        """INV-4: read-only agents declare no Write/Edit/MultiEdit/NotebookEdit."""
        path = AGENTS_DIR / f"{agent_name}.md"
        assert path.exists(), f"Read-only agent file missing: {path}"
        violations = check_agent_no_write_tools(path)
        assert not violations, "\n".join(violations)

    def test_inv5_optional_mcp_entries_are_declarable(self):
        """INV-5: every optional_mcp entry is on a positive allowlist."""
        violations = [
            v
            for path in _active_agent_paths()
            for v in check_agent_mcp_declarations(path)
            if v.startswith("INV-5")
        ]
        assert not violations, "Non-declarable optional MCP tools:\n" + "\n".join(
            violations
        )

    @pytest.mark.parametrize("agent_name", ["mobile-tester", "ui-tester", "reviewer"])
    def test_inv5_watched_permitting_the_three_shipped_agents(self, agent_name):
        """Positive control: the shipped optional_mcp declarations are allowed.

        A guard is only proven by watching it BOTH refuse and permit. The
        negative controls below watch INV-5 refuse; this watches it permit,
        so a rule that simply rejected everything could not pass.
        """
        path = AGENTS_DIR / f"{agent_name}.md"
        _granted, optional, _prose = _declared_and_prose(path)
        assert optional, f"{agent_name}.md must declare optional_mcp entries"
        for tool in sorted(optional):
            assert may_be_declared_optional(tool), (
                f"{agent_name}.md declares {tool!r}, which is on neither "
                f"MCP_READ_TOOLS nor MCP_OPTIONAL_DECLARABLE_TOOLS"
            )
        assert not [
            v for v in check_agent_mcp_declarations(path) if v.startswith("INV-5")
        ]

    def test_declarable_registry_is_disjoint_from_read_and_write(self):
        """A tool classified into two registries is a contradiction."""
        assert not (MCP_OPTIONAL_DECLARABLE_TOOLS & MCP_READ_TOOLS), (
            "A tool in both MCP_READ_TOOLS and MCP_OPTIONAL_DECLARABLE_TOOLS "
            "is classified twice: "
            f"{sorted(MCP_OPTIONAL_DECLARABLE_TOOLS & MCP_READ_TOOLS)}"
        )
        assert not (MCP_OPTIONAL_DECLARABLE_TOOLS & MCP_WRITE_TOOLS), (
            "A filesystem writer must never be declarable: "
            f"{sorted(MCP_OPTIONAL_DECLARABLE_TOOLS & MCP_WRITE_TOOLS)}"
        )

    def test_all_invariants_green_across_active_agents(self):
        """Aggregate gate: zero INV-1..INV-5 violations repo-wide."""
        violations = []
        for path in _active_agent_paths():
            violations.extend(check_agent_mcp_declarations(path))
        for agent_name in READ_ONLY_AGENTS:
            violations.extend(check_agent_no_write_tools(AGENTS_DIR / f"{agent_name}.md"))
        assert not violations, "Agent MCP declaration violations:\n" + "\n".join(
            violations
        )

    def test_granted_serena_tools_cover_the_navigation_prose(self):
        """The 4 granted agents actually reference serena and a grep fallback."""
        expected = {
            "researcher-local": {
                "mcp__serena__find_symbol",
                "mcp__serena__find_referencing_symbols",
                "mcp__serena__find_implementations",
                "mcp__serena__get_symbols_overview",
            },
            "planner": {
                "mcp__serena__find_symbol",
                "mcp__serena__find_referencing_symbols",
                "mcp__serena__get_symbols_overview",
            },
            "reviewer": {
                "mcp__serena__find_symbol",
                "mcp__serena__find_referencing_symbols",
                "mcp__serena__get_symbols_overview",
                "mcp__serena__get_diagnostics_for_file",
            },
            "test-coverage-auditor": {
                "mcp__serena__get_symbols_overview",
                "mcp__serena__find_referencing_symbols",
            },
        }
        for agent_name, serena_tools in expected.items():
            path = AGENTS_DIR / f"{agent_name}.md"
            granted, _optional, _prose = _declared_and_prose(path)
            missing = serena_tools - granted
            assert not missing, f"{agent_name}.md missing serena grants: {missing}"

            body = _split_frontmatter(path)[1]
            assert "Navigation: serena" in body, (
                f"{agent_name}.md must instruct emitting 'Navigation: serena'"
            )
            assert "Navigation: grep (serena unavailable)" in body, (
                f"{agent_name}.md must instruct the grep-fallback marker "
                f"'Navigation: grep (serena unavailable)'"
            )

    def test_planner_call_boundary_audit_names_serena_first(self):
        """AC-4: planner uses find_referencing_symbols; findReferences is gone."""
        body = _split_frontmatter(AGENTS_DIR / "planner.md")[1]
        assert "findReferences" not in body, (
            "planner.md still names the non-existent tool 'findReferences'"
        )
        assert "mcp__serena__find_referencing_symbols" in body, (
            "planner.md Call-Boundary Audit must name "
            "mcp__serena__find_referencing_symbols as the primary caller search"
        )

    def test_optional_mcp_covers_exactly_the_prose_tokens(self):
        """AC-6: optional_mcp declarations match cited prose token counts."""
        expected_counts = {"mobile-tester": 5, "ui-tester": 1, "reviewer": 2}
        for agent_name, count in expected_counts.items():
            path = AGENTS_DIR / f"{agent_name}.md"
            _granted, optional, prose = _declared_and_prose(path)
            non_serena_prose = {t for t in prose if not t.startswith("mcp__serena__")}
            assert len(optional) == count, (
                f"{agent_name}.md optional_mcp has {len(optional)} entries, "
                f"expected {count}: {sorted(optional)}"
            )
            assert non_serena_prose == optional, (
                f"{agent_name}.md optional_mcp {sorted(optional)} does not match "
                f"its cited prose tokens {sorted(non_serena_prose)}"
            )

    # ---- Negative controls: the guard must be watched refusing ----------

    @staticmethod
    def _write_agent(tmp_path: Path, name: str, frontmatter: str, body: str) -> Path:
        path = tmp_path / f"{name}.md"
        path.write_text(f"---\n{frontmatter}\n---\n\n{body}\n", encoding="utf-8")
        return path

    def test_negative_control_1_undeclared_write_tool_in_prose_fails_inv1(self, tmp_path):
        """Control 1: body cites a writer, tools: [Read] → INV-1 violation."""
        path = self._write_agent(
            tmp_path,
            "control-one",
            "name: control-one\ntools: [Read]",
            "Use `mcp__serena__replace_symbol_body` to patch the function.",
        )
        violations = check_agent_mcp_declarations(path)
        inv1 = [v for v in violations if v.startswith("INV-1")]
        assert len(inv1) == 1, f"expected 1 INV-1 violation, got {violations}"
        assert "mcp__serena__replace_symbol_body" in inv1[0]

    def test_negative_control_2_granted_writer_fails_inv2_and_inv3(self, tmp_path):
        """Control 2: tools: grants write_memory → INV-2 AND INV-3 violations."""
        path = self._write_agent(
            tmp_path,
            "control-two",
            "name: control-two\ntools: [Read, mcp__serena__write_memory]",
            "No MCP tokens in this body.",
        )
        violations = check_agent_mcp_declarations(path)
        assert any(v.startswith("INV-2") for v in violations), violations
        assert any(v.startswith("INV-3") for v in violations), violations

    def test_negative_control_3_unregistered_tool_fails_inv2(self, tmp_path):
        """Control 3: execute_shell_command is in NEITHER registry.

        This is the case a denylist against MCP_WRITE_TOOLS would silently
        permit. INV-2 is an allowlist against MCP_READ_TOOLS, so it refuses.
        """
        assert "mcp__serena__execute_shell_command" not in MCP_READ_TOOLS
        assert "mcp__serena__execute_shell_command" not in MCP_WRITE_TOOLS

        path = self._write_agent(
            tmp_path,
            "control-three",
            "name: control-three\ntools: [Read, mcp__serena__execute_shell_command]",
            "No MCP tokens in this body.",
        )
        violations = check_agent_mcp_declarations(path)
        inv2 = [v for v in violations if v.startswith("INV-2")]
        assert len(inv2) == 1, f"expected 1 INV-2 violation, got {violations}"
        assert "execute_shell_command" in inv2[0]

    def test_negative_control_4_serena_wildcard_fails_inv3(self, tmp_path):
        """Control 4: optional_mcp wildcard for a known write-capable server."""
        path = self._write_agent(
            tmp_path,
            "control-four",
            'name: control-four\ntools: [Read]\noptional_mcp: ["mcp__serena__*"]',
            "No MCP tokens in this body.",
        )
        violations = check_agent_mcp_declarations(path)
        inv3 = [v for v in violations if v.startswith("INV-3")]
        assert len(inv3) == 1, f"expected 1 INV-3 wildcard violation, got {violations}"
        assert "mcp__serena__*" in inv3[0]

    def test_negative_control_5_historical_mobile_tester_fails_with_5_violations(
        self, tmp_path
    ):
        """Control 5: today's mobile-tester body minus optional_mcp → 5 INV-1 fails.

        Pins the guard to the real content that falsified the v1 design: the
        agent cites 5 unique appium tools it was never granted.
        """
        frontmatter, body = _split_frontmatter(AGENTS_DIR / "mobile-tester.md")
        assert frontmatter.get("optional_mcp"), (
            "mobile-tester.md must declare optional_mcp for this control to be "
            "meaningful"
        )
        path = self._write_agent(
            tmp_path,
            "control-five",
            "name: mobile-tester\ntools: [Read, Write, Edit, Bash, Grep, Glob]",
            body,
        )
        violations = check_agent_mcp_declarations(path)
        inv1 = [v for v in violations if v.startswith("INV-1")]
        assert len(inv1) == 5, (
            f"expected exactly 5 INV-1 violations from the historical "
            f"mobile-tester body, got {len(inv1)}:\n" + "\n".join(violations)
        )
        assert all("mcp__appium__" in v for v in inv1), inv1

    def test_negative_control_6_unparseable_frontmatter_fails_loudly(self, tmp_path):
        """Malformed frontmatter must raise naming the file, never skip silently."""
        path = tmp_path / "control-six.md"
        path.write_text("---\ntools: [Read\n  bad: : yaml\n---\n\nbody\n", encoding="utf-8")
        with pytest.raises(ValueError, match="control-six.md"):
            check_agent_mcp_declarations(path)

    def test_negative_control_7_missing_frontmatter_fails_loudly(self, tmp_path):
        """A file with no frontmatter block must raise naming the file."""
        path = tmp_path / "control-seven.md"
        path.write_text("# Just a heading\n\nNo frontmatter here.\n", encoding="utf-8")
        with pytest.raises(ValueError, match="control-seven.md"):
            check_agent_mcp_declarations(path)

    def test_negative_control_8_non_write_capable_wildcard_fails_inv3(self, tmp_path):
        """Control 8: a wildcard for a server with ZERO write entries → INV-3.

        This is the gap control 4 does not cover. ``somefakeserver`` has no
        member in either MCP registry, so a rule derived from
        ``MCP_WRITE_TOOLS`` would permit this wildcard — laundering every
        unclassified tool on that server, exactly the pattern INV-3 exists
        to close. The blanket wildcard ban must refuse it.
        """
        server_prefix = "mcp__somefakeserver__"
        assert not any(t.startswith(server_prefix) for t in MCP_WRITE_TOOLS), (
            "somefakeserver must have no MCP_WRITE_TOOLS entries for this "
            "control to exercise the unclassified-server case"
        )
        assert not any(t.startswith(server_prefix) for t in MCP_READ_TOOLS), (
            "somefakeserver must have no MCP_READ_TOOLS entries either"
        )

        path = self._write_agent(
            tmp_path,
            "control-eight",
            'name: control-eight\ntools: [Read]\n'
            'optional_mcp: ["mcp__somefakeserver__*"]',
            "No MCP tokens in this body.",
        )
        violations = check_agent_mcp_declarations(path)
        inv3 = [v for v in violations if v.startswith("INV-3")]
        assert len(inv3) == 1, f"expected 1 INV-3 wildcard violation, got {violations}"
        assert "mcp__somefakeserver__*" in inv3[0]

    def test_negative_control_9_concrete_unclassified_optional_token_fails_inv5(
        self, tmp_path
    ):
        """Control 9: a CONCRETE unclassified optional_mcp token → INV-5.

        This is the exact gap that survived remediation cycle 1. INV-2
        iterates ``granted`` only, and INV-3's wildcard clause requires a
        ``*``, so a concrete token from a server with zero MCP_WRITE_TOOLS
        entries produced ZERO violations no matter what the tool did. The
        premise is asserted below so this control cannot pass for an
        incidental reason.
        """
        token = "mcp__somefakeserver__wipe_database"
        assert token not in MCP_READ_TOOLS
        assert token not in MCP_WRITE_TOOLS
        assert token not in MCP_OPTIONAL_DECLARABLE_TOOLS

        path = self._write_agent(
            tmp_path,
            "control-nine",
            f'name: control-nine\ntools: [Read]\noptional_mcp: ["{token}"]',
            "No MCP tokens in this body.",
        )
        violations = check_agent_mcp_declarations(path)
        inv5 = [v for v in violations if v.startswith("INV-5")]
        assert len(inv5) == 1, f"expected 1 INV-5 violation, got {violations}"
        assert token in inv5[0]

    def test_negative_control_10_concrete_browser_evaluate_optional_fails_inv5(
        self, tmp_path
    ):
        """Control 10: browser_evaluate as a CONCRETE optional token → INV-5.

        The specific case proven to pass before this change. It also proves
        the rule is stronger than "every declared tool must be classified":
        browser_evaluate IS classified today, as a non-read browser action in
        MCP_KNOWN_EXEC_TOOLS (scripts/audit_tool_intent_coverage.py), so a
        classification-only rule would admit it. It executes caller-supplied
        JavaScript, which no availability check can bound, so it must be
        refused on the declarable allowlist regardless.
        """
        token = "mcp__playwright__browser_evaluate"
        assert token not in MCP_READ_TOOLS, "AC #19: never read-only"
        assert token not in MCP_WRITE_TOOLS, (
            "browser_evaluate is not a FILESYSTEM writer — that is precisely "
            "why the MCP_WRITE_TOOLS check alone never caught it"
        )
        assert token not in MCP_OPTIONAL_DECLARABLE_TOOLS, (
            "browser_evaluate must never become declarable"
        )

        path = self._write_agent(
            tmp_path,
            "control-ten",
            f'name: control-ten\ntools: [Read]\noptional_mcp: ["{token}"]',
            "No MCP tokens in this body.",
        )
        violations = check_agent_mcp_declarations(path)
        inv5 = [v for v in violations if v.startswith("INV-5")]
        assert len(inv5) == 1, f"expected 1 INV-5 violation, got {violations}"
        assert token in inv5[0]

    def test_negative_control_11_optional_writer_fails_inv3_and_inv5(self, tmp_path):
        """Control 11: a known writer in optional_mcp trips BOTH clauses.

        The overlap is deliberate defence-in-depth — if the INV-3 write
        clause were weakened, INV-5 still refuses because a writer is on
        neither positive allowlist.
        """
        path = self._write_agent(
            tmp_path,
            "control-eleven",
            'name: control-eleven\ntools: [Read]\n'
            'optional_mcp: ["mcp__serena__write_memory"]',
            "No MCP tokens in this body.",
        )
        violations = check_agent_mcp_declarations(path)
        assert any(v.startswith("INV-3") for v in violations), violations
        assert any(v.startswith("INV-5") for v in violations), violations

    def test_negative_control_12_asymmetry_is_intentional_not_accidental(
        self, tmp_path
    ):
        """Declarable is strictly WIDER than grantable, and that is by design.

        ``mcp__appium__tap`` mutates device state. It may be DECLARED
        (mobile-tester attempts it behind an availability check) but must
        never be GRANTED, because ``tools:`` is the only real control —
        unified_pre_tool.py default-allows every ``mcp__*`` call. Cycle 1's
        asymmetry was accidental and unguarded; this pins it as intended.
        """
        token = "mcp__appium__tap"
        assert may_be_declared_optional(token), "tap must be declarable"
        assert token not in MCP_READ_TOOLS, (
            "tap mutates device state and must never be laundered into the "
            "read allowlist, which grants plan-exit passage"
        )

        granted = self._write_agent(
            tmp_path,
            "control-twelve-granted",
            f'name: control-twelve-granted\ntools: [Read, "{token}"]',
            "No MCP tokens in this body.",
        )
        assert [
            v for v in check_agent_mcp_declarations(granted) if v.startswith("INV-2")
        ], "granting tap in tools: must be an INV-2 violation"

        declared = self._write_agent(
            tmp_path,
            "control-twelve-declared",
            f'name: control-twelve-declared\ntools: [Read]\noptional_mcp: ["{token}"]',
            "No MCP tokens in this body.",
        )
        assert not check_agent_mcp_declarations(declared), (
            "declaring tap in optional_mcp: must be clean"
        )

    def test_mcp_token_regex_matches_hyphenated_tool_names(self):
        """A hyphenated MCP tool name must be matched whole, not truncated.

        Without ``-`` in the trailing character class the token truncates at
        the hyphen and INV-1 reports a spurious violation on the prefix.
        """
        body = "Call `mcp__ms365__send-mail` to notify the on-call engineer."
        assert MCP_TOKEN_RE.findall(body) == ["mcp__ms365__send-mail"]

    def test_hyphenated_prose_token_is_covered_by_its_declaration(self, tmp_path):
        """INV-1 must not fire when the hyphenated token IS declared."""
        path = self._write_agent(
            tmp_path,
            "control-hyphen",
            'name: control-hyphen\ntools: [Read]\n'
            'optional_mcp: ["mcp__ms365__send-mail"]',
            "Call `mcp__ms365__send-mail` to notify the on-call engineer.",
        )
        violations = [
            v for v in check_agent_mcp_declarations(path) if v.startswith("INV-1")
        ]
        assert not violations, (
            "hyphenated token truncated by MCP_TOKEN_RE: " + "\n".join(violations)
        )


PLUGIN_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev"
COMMANDS_DIR = PLUGIN_DIR / "commands"
SKILLS_DIR = PLUGIN_DIR / "skills"

# Native web tools that require Anthropic's hosted search/fetch service. They
# work on the hosted backend and silently no-op on any other, so a declaration
# naming one ALONE grants a capability that is not portable. PROJECT.md permits
# them only alongside a local route (INV-8 never-alone).
HOSTED_WEB_TOOLS = frozenset({"WebSearch", "WebFetch"})

# The self-hosted replacement pair.
SEARXNG_TOOLS = frozenset({"mcp__searxng__search", "mcp__searxng__fetch"})

# The researcher's availability-disclosure markers. Copied in shape from the
# shipped serena precedent ("Navigation: serena" / "Navigation: grep (serena
# unavailable)") asserted by
# ``test_granted_serena_tools_cover_the_navigation_prose`` above.
RESEARCH_MARKERS = (
    "Research: searxng",
    "Research: unavailable (no searxng server)",
    "Research: web",
)


def _command_and_skill_paths(
    commands_dir: Path = COMMANDS_DIR, skills_dir: Path = SKILLS_DIR
) -> "list[Path]":
    """Return every command and skill declaration file.

    Args:
        commands_dir: Directory holding ``*.md`` command definitions.
        skills_dir: Directory holding ``*/SKILL.md`` skill packages.

    Returns:
        Sorted list of paths. Both globs are non-recursive by shape, so an
        ``archived/`` subdirectory of commands_dir is excluded automatically.
    """
    commands = sorted(f for f in commands_dir.glob("*.md") if f.is_file())
    skills = sorted(f for f in skills_dir.glob("*/SKILL.md") if f.is_file())
    return commands + skills


def check_no_hosted_web_tools(path: Path, *, key: str) -> "list[str]":
    """Check that a hosted web tool is never granted ALONE (INV-8 never-alone).

    A hosted tool (``WebSearch``/``WebFetch``) MAY be declared — including as
    the primary route — but ONLY alongside a local ``mcp__searxng__*`` tool.
    The binding constraint is never-alone, not prohibition: a hosted-only
    declaration silently no-ops on any backend without Anthropic's hosted
    service, which is exactly the portability defect the rule exists to catch.
    Declaring neither is also clean; the rule inspects hosted grants only.

    This is the single implementation behind R1 (agents, ``tools:``) and R2
    (commands/skills, ``allowed-tools:``). The live corpus and every negative
    control below call THIS function — a control that re-implemented the rule
    would prove nothing about the rule.

    Args:
        path: Path to an agent/command/skill markdown file.
        key: Frontmatter key holding the tool list — ``"tools"`` for agents,
            ``"allowed-tools"`` for commands and skills.

    Returns:
        List of human-readable violation strings, one per hosted web tool
        declared without any local searxng tool. Empty list means the file
        satisfies never-alone.

    Raises:
        ValueError: If the frontmatter is missing or unparseable.
    """
    frontmatter, _body = _split_frontmatter(path)
    declared = set(_as_tool_list(frontmatter.get(key)))
    hosted = declared & HOSTED_WEB_TOOLS
    if not hosted or (declared & SEARXNG_TOOLS):
        return []
    return [
        f"{path.name}: {key}: declares hosted web tool {tool!r} with no "
        f"local searxng tool also declared. PROJECT.md permits a hosted "
        f"tool only ALONGSIDE a local one (INV-8 never-alone) — hosted-only "
        f"silently no-ops on any backend without Anthropic's hosted service."
        for tool in sorted(hosted)
    ]


def check_researcher_web_disclosure(path: Path) -> "list[str]":
    """Check R3: the researcher grants searxng AND discloses availability.

    Frontmatter grants alone are not enough. Without the two markers the
    coordinator cannot distinguish a searched answer from an unsearched one,
    which is precisely the failure the deleted (and never-implemented)
    "coordinator will check your tool usage count" gate pretended to cover.

    Args:
        path: Path to the researcher agent markdown file.

    Returns:
        List of violation strings. Empty list means R3 is satisfied.

    Raises:
        ValueError: If the frontmatter is missing or unparseable.
    """
    frontmatter, body = _split_frontmatter(path)
    granted = set(_as_tool_list(frontmatter.get("tools")))
    violations: "list[str]" = []

    for tool in sorted(SEARXNG_TOOLS - granted):
        violations.append(
            f"{path.name}: tools: must grant {tool!r} — it is the researcher's "
            f"only route to the web that survives on a backend without "
            f"Anthropic's hosted service (INV-8 never-alone)."
        )

    for marker in RESEARCH_MARKERS:
        if marker not in body:
            violations.append(
                f"{path.name}: body must instruct emitting the verbatim marker "
                f"{marker!r}. Without both markers an unsearched answer is "
                f"indistinguishable from a searched one."
            )

    return violations


# The two prose sites that together describe the researcher's web-research
# contract: the agent that EMITS the disclosure marker, and the coordinator
# step that CONSUMES it. They must agree, and neither may assert a check that
# no code performs.
RESEARCH_CONTRACT_SITES = (
    AGENTS_DIR / "researcher.md",
    COMMANDS_DIR / "implement.md",
)

# Claims of a tool-use count that the pipeline never performs. ``tools_used``
# is stored by ``agent_tracker/state.py`` and rendered by
# ``agent_tracker/display.py``; nothing in ``lib/`` or ``hooks/`` branches on
# it. Prose promising a count-driven retry therefore describes a gate that
# cannot fire, which is exactly what INV-1 forbids.
#
# WHAT FOLLOWS IS A LINT, NOT A DECISION PROCEDURE. Whether a sentence asserts
# a check that nothing performs is a question about natural language, and no
# regex answers it: these alternations recognise the phrasings observed in the
# wild plus close paraphrases of them, and a determined rewording gets past
# them. That limit is accepted deliberately rather than papered over, because
# the positive rule below (``check_consumes_research_markers``, R5) is what
# carries the weight — it asserts the contract slot DOES contain the
# marker-based text, and text that says the right thing there cannot
# simultaneously say the wrong thing. This lint is the cheap second line that
# catches the known shapes; R5 is the guarantee.
_ZERO = r"(?:0|zero|none|no|empty)"
_COUNT_NOUN = (
    r"(?:uses?|usages?|calls?|queries|invocations?|dispatches|searches|counts?)"
)
_RETRY = (
    r"(?:retr(?:y|ies|ied|ying)|re-?dispatch(?:es|ed|ing)?"
    r"|re-?invoke[sd]?|re-?invoking|re-?run(?:s|ning)?|try\s+again)"
)
# A period must NOT defeat the lint: a claim routinely spans two sentences
# ("...performed 0 queries. Then retry the whole step."). Bounded at 160 chars
# so the window stays local rather than pairing unrelated paragraphs.
_GAP = r"[\s\S]{0,160}?"
_ZERO_COUNT = rf"\b{_ZERO}\s+(?:\w+\s+){{0,2}}?{_COUNT_NOUN}\b"

UNPERFORMED_COUNT_CLAIMS = (
    (
        re.compile(r"tool[\s\-]*(?:usage[\s\-]*)?count", re.IGNORECASE),
        "asserts a 'tool usage count' check",
    ),
    (
        re.compile(rf"{_ZERO_COUNT}{_GAP}\b{_RETRY}\b", re.IGNORECASE),
        "asserts a retry triggered by a zero tool-use count",
    ),
    (
        re.compile(rf"\b{_RETRY}\b{_GAP}{_ZERO_COUNT}", re.IGNORECASE),
        "asserts a retry triggered by a zero tool-use count (reversed order)",
    ),
    (
        re.compile(rf"\btools_used\b{_GAP}\b{_RETRY}\b", re.IGNORECASE),
        "branches a retry on the unconsumed 'tools_used' field",
    ),
    (
        re.compile(rf"\b{_RETRY}\b{_GAP}\btools_used\b", re.IGNORECASE),
        "branches a retry on the unconsumed 'tools_used' field (reversed order)",
    ),
)


def check_no_unperformed_tool_count_claim(path: Path) -> "list[str]":
    """Check R4 — a BEST-EFFORT LINT over KNOWN SHAPES, not a complete rule.

    This function is deliberately incomplete and must not be described as
    covering every way the false promise could be worded. It recognises the
    phrasings seen in the wild plus close paraphrases; a rewording outside
    that family gets past it. The complete, load-bearing rule is
    ``check_consumes_research_markers`` (R5): that one is decidable and total
    over the slot it inspects, so it is what the contract rests on. This lint
    exists to catch the known shapes cheaply, behind R5.

    The live corpus and every control below call THIS function, so a control
    proves something about the lint rather than about a paraphrase of it.

    Args:
        path: Path to a markdown file in the research contract (agent or
            command). Read whole — the claim is prose and may sit anywhere.

    Returns:
        List of violation strings, one per matched phrasing. An empty list
        means no KNOWN shape matched — it is NOT proof that the file carries
        no such promise.
    """
    text = path.read_text(encoding="utf-8")
    violations: "list[str]" = []
    for pattern, description in UNPERFORMED_COUNT_CLAIMS:
        for match in pattern.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            violations.append(
                f"{path.name}:{line_no}: {description} — {match.group(0)!r}. "
                f"No consumer of tools_used makes any decision, so this "
                f"promises enforcement that cannot fire (INV-1). Read the "
                f"{RESEARCH_MARKERS[0]!r} / {RESEARCH_MARKERS[1]!r} marker in "
                f"the agent's returned text instead — that is observable."
            )
    return violations


def check_consumes_research_markers(path: Path) -> "list[str]":
    """Check R5 — the LOAD-BEARING rule, and COMPLETE over the slot it reads.

    Unlike the R4 lint, this rule is decidable and total. It asks whether the
    coordinator names the verbatim strings ``researcher.md`` is required to
    emit. A file either contains those literals or it does not; there is no
    paraphrase that satisfies the contract while evading the check, because
    here the contract IS the literal marker. That is why the guarantee lives
    on this side: R4 subtracts an unobservable signal by recognising known
    phrasings, while R5 requires the observable one positively, and positive
    text that says the right thing cannot at the same time say the wrong
    thing in that same slot.

    Args:
        path: Path to the coordinator command file.

    Returns:
        List of violation strings, one per absent marker. Empty means clean.
    """
    text = path.read_text(encoding="utf-8")
    return [
        f"{path.name}: must name the verbatim marker {marker!r} that "
        f"researcher.md is required to emit. The Agent tool's return value is "
        f"the only web-research signal the coordinator actually receives."
        for marker in RESEARCH_MARKERS
        if marker not in text
    ]


class TestNoHostedWebTools:
    """No declaration may grant a hosted web tool ALONE (INV-8 never-alone).

    ``WebSearch``/``WebFetch`` MAY be declared, including as the primary route,
    but only alongside a local ``mcp__searxng__*`` tool — a hosted-only grant
    silently no-ops on any backend without Anthropic's hosted service.

    R1 agents, R2 commands+skills, R3 the researcher's disclosure contract.
    Each rule is factored into a helper taking a path so the synthetic corpora
    in the negative controls execute the IDENTICAL code path as the live one.
    """

    # ---- NC3 (vacuity): a rule over an empty corpus inspects nothing ------

    def test_nc3_agent_corpus_is_non_empty(self):
        """NC3: R1's glob must find files, or R1 passes without looking."""
        paths = _active_agent_paths()
        assert len(paths) >= 15, (
            f"Expected the full active agent roster, found {len(paths)} in "
            f"{AGENTS_DIR}. R1 over an empty glob is vacuously true."
        )

    def test_nc3_command_and_skill_corpus_is_non_empty(self):
        """NC3: R2's globs must find files, or R2 passes without looking."""
        paths = _command_and_skill_paths()
        commands = [p for p in paths if p.parent == COMMANDS_DIR]
        skills = [p for p in paths if p.name == "SKILL.md"]
        assert len(commands) >= 20, (
            f"Expected the full command roster, found {len(commands)} in "
            f"{COMMANDS_DIR}. R2 over an empty glob is vacuously true."
        )
        assert len(skills) >= 15, (
            f"Expected the full skill roster, found {len(skills)} under "
            f"{SKILLS_DIR}. R2 over an empty glob is vacuously true."
        )

    # ---- The three rules, over the shipped corpus ------------------------

    def test_r1_no_active_agent_grants_a_hosted_web_tool(self):
        """R1: no agents/*.md grants a hosted tool without a local one."""
        violations = [
            v
            for path in _active_agent_paths()
            for v in check_no_hosted_web_tools(path, key="tools")
        ]
        assert not violations, "Hosted web tools granted to agents:\n" + "\n".join(
            violations
        )

    def test_r2_no_command_or_skill_allows_a_hosted_web_tool(self):
        """R2: no command/skill grants a hosted tool without a local one."""
        violations = [
            v
            for path in _command_and_skill_paths()
            for v in check_no_hosted_web_tools(path, key="allowed-tools")
        ]
        assert not violations, (
            "Hosted web tools in command/skill allowed-tools:\n" + "\n".join(violations)
        )

    def test_r3_researcher_grants_searxng_and_discloses_availability(self):
        """R3: researcher.md grants both searxng tools and ships both markers."""
        violations = check_researcher_web_disclosure(AGENTS_DIR / "researcher.md")
        assert not violations, "researcher.md web-research contract:\n" + "\n".join(
            violations
        )

    @pytest.mark.parametrize(
        "site", RESEARCH_CONTRACT_SITES, ids=lambda p: p.name
    )
    def test_r4_no_contract_site_claims_an_unperformed_tool_count(self, site):
        """R4 lint: neither prose site may carry a KNOWN count-claim shape.

        Both sites shipped the same false claim — researcher.md said "the
        coordinator will check your tool usage count", implement.md STEP 4
        said "if web researcher shows 0 tool uses, retry". Nothing in
        ``lib/`` or ``hooks/`` branches on ``tools_used``; it is stored by
        ``agent_tracker/state.py`` and rendered by ``display.py`` only. One
        lint now runs over both sites so fixing one cannot leave the other.

        This is a lint over known phrasings, so a green result here is not
        proof the sites are free of such a promise — R5 below is the rule
        that carries the contract.
        """
        violations = check_no_unperformed_tool_count_claim(site)
        assert not violations, "Unperformed tool-count claim:\n" + "\n".join(
            violations
        )

    def test_r5_coordinator_consumes_the_researcher_markers(self):
        """R5: implement.md must read the markers researcher.md emits.

        R4 removes the unobservable signal; without R5 the coordinator would
        be left with no research signal at all.
        """
        violations = check_consumes_research_markers(COMMANDS_DIR / "implement.md")
        assert not violations, "Coordinator/researcher marker drift:\n" + "\n".join(
            violations
        )

    # ---- NC5/NC6 for R4: same shape, then a DIFFERENT shape --------------

    def test_nc5_synthetic_reproducer_claim_is_refused(self, tmp_path):
        """NC5: the verbatim implement.md:839 shape MUST be refused."""
        path = TestAgentMcpToolDeclarations._write_agent(
            tmp_path,
            "control-count-claim",
            "description: synthetic coordinator step",
            "Validation: If web researcher shows 0 tool uses, retry. "
            "Merge both outputs.",
        )
        violations = check_no_unperformed_tool_count_claim(path)
        assert len(violations) == 1, f"expected 1 violation, got {violations}"
        assert "zero tool-use count" in violations[0]

    def test_nc6_differently_shaped_count_claim_is_refused(self, tmp_path):
        """NC6: a DIFFERENT shape from the reproducer MUST also be refused.

        Reversed clause order, a different noun ("searxng uses" rather than
        "tool uses"), and no "Validation:" prefix. A lint scoped to the one
        sentence that prompted it would pass this file. This wording sits
        inside the known-shape family the lint recognises, so it refuses —
        which bounds the lint's reach without implying it is complete.
        """
        path = TestAgentMcpToolDeclarations._write_agent(
            tmp_path,
            "control-count-claim-variant",
            "description: synthetic coordinator step",
            "Re-dispatch and retry the agent whenever it reports 0 searxng "
            "uses, and note its tool-usage count in the run log.",
        )
        violations = check_no_unperformed_tool_count_claim(path)
        assert len(violations) == 2, f"expected 2 violations, got {violations}"
        assert any("reversed order" in v for v in violations), violations
        assert any("'tool usage count' check" in v for v in violations), violations

    # ---- The guard on the guard's own self-description -------------------

    # Wordings that would assert the R4 lint reaches further than it does.
    # None of these can appear innocently in a description of a lint that is
    # openly partial, so each is a reliable signal of an overclaim.
    _OVERCLAIM_WORDINGS = (
        r"\bclass\b",
        r"\bany\s+phrasing\b",
        r"\ball\s+phrasings?\b",
        r"\bevery\s+phrasing\b",
        r"\bevery\s+wording\b",
        r"\bexhaustive\b",
    )

    def test_r4_lint_docstring_does_not_overclaim_its_own_coverage(self):
        """R4's self-description must not outrun R4's behaviour.

        A lint that advertises itself as complete commits the very defect it
        exists to catch — a check whose subject is the description rather
        than the behaviour. This is measured, not argued: after broadening,
        the lint catches the five paraphrases the reviewer supplied, and
        five FURTHER rewordings of the same false promise ("come back
        empty-handed... run the step a second time", "never touched the
        web", "if that figure is nil") still walk past it. Any wording here
        promising coverage of the whole family would therefore be false.
        Completeness legitimately lives on R5, which is asserted separately
        by ``test_r5_docstring_states_it_is_the_load_bearing_rule``.
        """
        doc = inspect.getdoc(check_no_unperformed_tool_count_claim) or ""
        assert doc, "R4 lint has no docstring, so it describes itself nowhere."

        for pattern in self._OVERCLAIM_WORDINGS:
            match = re.search(pattern, doc, re.IGNORECASE)
            assert match is None, (
                f"R4's docstring overclaims via {match.group(0)!r}. The lint "
                f"recognises known phrasings only — rewordings outside that "
                f"family are known to evade it. Describe it as partial."
            )

        lowered = doc.lower()
        for required in ("best-effort", "known shapes"):
            assert required in lowered, (
                f"R4's docstring must contain {required!r} so a reader "
                f"cannot mistake a green result for proof of absence."
            )

    def test_no_test_docstring_overclaims_the_r4_lint(self):
        """Every docstring describing the lint must be honest, not just one.

        Fixing only the helper's own docstring would repeat the defect this
        remediation exists to correct: a guard scoped to the single instance
        that prompted it. The removed overclaim — a sentence asserting the
        lint covered the whole family of count-driven-retry prose — lived on
        NC6, not on the helper, so a check inspecting only the helper would
        have missed the original. This discovers its subjects by reading which
        methods CALL the lint, so a future test added to the family is
        covered without anyone remembering to enrol it.
        """
        target = "check_no_unperformed_tool_count_claim"
        callers = {
            name: method
            for name, method in inspect.getmembers(
                TestNoHostedWebTools, inspect.isfunction
            )
            if name.startswith("test_") and target in inspect.getsource(method)
        }
        assert len(callers) >= 4, (
            f"Expected the family of tests exercising the R4 lint, found "
            f"{sorted(callers)}. A docstring sweep over an empty or tiny set "
            f"is vacuously true."
        )

        offenders: "list[str]" = []
        for name, method in sorted(callers.items()):
            doc = inspect.getdoc(method) or ""
            for pattern in self._OVERCLAIM_WORDINGS:
                match = re.search(pattern, doc, re.IGNORECASE)
                if match is not None:
                    offenders.append(f"{name}: {match.group(0)!r}")

        assert not offenders, (
            "Test docstrings describe the R4 lint as reaching further than "
            "it does:\n" + "\n".join(offenders) + "\nThe lint recognises "
            "known phrasings; rewordings outside that family evade it."
        )

    def test_r5_docstring_states_it_is_the_load_bearing_rule(self):
        """R5 must name itself as the half that carries the contract.

        The honest architecture is only useful if it is written down where
        the next reader meets it: R4 subtracts known bad phrasings, R5
        positively requires the observable marker and is total over that
        slot. If R5 stops saying so, the pair silently becomes two lints.
        """
        doc = (inspect.getdoc(check_consumes_research_markers) or "").lower()
        assert doc, "R5 has no docstring, so it describes itself nowhere."
        assert "load-bearing" in doc, (
            "R5's docstring must identify it as the load-bearing rule — it "
            "is what remains if the R4 lint is evaded."
        )
        assert "complete" in doc or "total" in doc, (
            "R5's docstring must state that it is complete/total over the "
            "slot it inspects; that property is why it carries the weight."
        )

    def test_control_overclaiming_docstring_would_be_refused(self):
        """Negative control: the honesty check must be able to REFUSE.

        Aimed at the ORIGINAL overclaiming sentence this remediation
        removed, so the control is a real prior artifact rather than a
        strawman. Without this arm, a typo in the pattern list would leave
        both honesty tests passing over prose they no longer inspect.
        """
        overclaiming = (
            "Check R4: a file must not claim a tool-use count that never "
            "happens. The rule covers the class 'prose asserting a "
            "count-driven retry', so it refuses any phrasing of it."
        )
        hits = [
            p
            for p in self._OVERCLAIM_WORDINGS
            if re.search(p, overclaiming, re.IGNORECASE)
        ]
        assert len(hits) >= 2, (
            f"The honesty check failed to flag the known overclaiming "
            f"wording it was built from; it matched only {hits}. A pattern "
            f"list that cannot refuse cannot inform."
        )

        honest = inspect.getdoc(check_no_unperformed_tool_count_claim) or ""
        assert not [
            p for p in self._OVERCLAIM_WORDINGS if re.search(p, honest, re.IGNORECASE)
        ], "The shipped docstring must be permitted by the same pattern list."

    def test_positive_control_marker_based_prose_is_permitted(self, tmp_path):
        """R4/R5 must be watched PERMITTING the honest replacement.

        This file talks about the researcher, about retrying, and about
        research being unavailable — everything except a count-driven gate. A
        rule that refused it would refuse the very prose it demands.
        """
        path = TestAgentMcpToolDeclarations._write_agent(
            tmp_path,
            "control-honest-prose",
            "description: synthetic coordinator step",
            "Validation: the researcher ends its output with "
            "`Research: searxng`, `Research: web`, or `Research: unavailable "
            "(no searxng server)`. Read that marker; if it is absent, "
            "dispatch the researcher once more.",
        )
        assert not check_no_unperformed_tool_count_claim(path)
        assert not check_consumes_research_markers(path)

    def test_nc7_prose_missing_the_markers_fails_r5(self, tmp_path):
        """NC7 for R5: honest-but-silent prose names no marker → refused."""
        path = TestAgentMcpToolDeclarations._write_agent(
            tmp_path,
            "control-no-markers",
            "description: synthetic coordinator step",
            "Validation: merge both research outputs and persist them.",
        )
        violations = check_consumes_research_markers(path)
        assert len(violations) == len(RESEARCH_MARKERS), (
            f"expected one violation per absent marker, got {violations}"
        )
        for marker in RESEARCH_MARKERS:
            assert any(marker in v for v in violations), f"{marker!r} not reported"

    # ---- Positive control: the rules must be watched PERMITTING ----------

    def test_positive_control_serena_grant_still_passes_r1(self, tmp_path):
        """R1 targets hosted web tools specifically, not every tool.

        A rule that refused everything would pass every negative control. This
        agent declares an MCP tool and native readers and must be PERMITTED.
        """
        path = TestAgentMcpToolDeclarations._write_agent(
            tmp_path,
            "control-serena",
            "name: control-serena\ntools: [mcp__serena__find_symbol, Read, Grep, Glob]",
            "Use `mcp__serena__find_symbol` to locate the definition.",
        )
        assert not check_no_hosted_web_tools(path, key="tools")

    def test_positive_control_searxng_grant_passes_r1(self, tmp_path):
        """R1 must permit the replacement pair it is migrating everyone to."""
        path = TestAgentMcpToolDeclarations._write_agent(
            tmp_path,
            "control-searxng",
            "name: control-searxng\n"
            "tools: [mcp__searxng__search, mcp__searxng__fetch, Read]",
            "Use `mcp__searxng__search` for prior art.",
        )
        assert not check_no_hosted_web_tools(path, key="tools")

    def test_positive_control_hosted_alongside_local_passes_r1(self, tmp_path):
        """R1 must PERMIT a hosted tool declared alongside a local one.

        This is the arm that proves the rule inverted rather than being
        renamed: under the previous prohibition rule this same fixture was
        REFUSED. PROJECT.md (commit 951fdf1e) permits a hosted search tool as
        primary "ONLY alongside a local one" — never-alone, not prohibition.
        """
        path = TestAgentMcpToolDeclarations._write_agent(
            tmp_path,
            "control-hosted-plus-local",
            "name: control-hosted-plus-local\n"
            "tools: [WebSearch, mcp__searxng__search, Read]",
            "Search with `WebSearch`, and always issue at least one "
            "`mcp__searxng__search` query.",
        )
        assert not check_no_hosted_web_tools(path, key="tools")

    # ---- NC1 (same shape, baseline) --------------------------------------

    @pytest.mark.parametrize("hosted_tool", sorted(HOSTED_WEB_TOOLS))
    def test_nc1_synthetic_agent_granting_a_hosted_tool_is_refused(
        self, tmp_path, hosted_tool
    ):
        """NC1: tools: [WebSearch, Read] → R1's helper MUST refuse."""
        path = TestAgentMcpToolDeclarations._write_agent(
            tmp_path,
            "control-hosted",
            f"name: control-hosted\ntools: [{hosted_tool}, Read]",
            "Search the web for prior art.",
        )
        violations = check_no_hosted_web_tools(path, key="tools")
        assert len(violations) == 1, f"expected 1 violation, got {violations}"
        assert hosted_tool in violations[0]

    def test_nc1_synthetic_command_allowing_a_hosted_tool_is_refused(self, tmp_path):
        """NC1 for R2: allowed-tools: [Read, WebFetch] MUST be refused.

        Also proves the ``key`` argument is load-bearing: the same file is
        CLEAN when inspected under the agent key, because ``tools:`` is absent.
        """
        path = TestAgentMcpToolDeclarations._write_agent(
            tmp_path,
            "control-command",
            "description: synthetic command\nallowed-tools: [Read, WebFetch]",
            "Fetch the upstream docs.",
        )
        violations = check_no_hosted_web_tools(path, key="allowed-tools")
        assert len(violations) == 1, f"expected 1 violation, got {violations}"
        assert "WebFetch" in violations[0]
        assert not check_no_hosted_web_tools(path, key="tools")

    # ---- NC4 (different shape: partial compliance) -----------------------

    def test_nc4_correct_grants_but_stripped_markers_fail_r3(self, tmp_path):
        """NC4: right frontmatter, missing markers → R3 MUST refuse.

        Different shape from the bug (nothing hosted is declared; the grants
        are exactly right). Proves R3 is not satisfiable by frontmatter alone.
        """
        path = TestAgentMcpToolDeclarations._write_agent(
            tmp_path,
            "researcher",
            "name: researcher\n"
            "tools: [mcp__searxng__search, mcp__searxng__fetch, Read, Grep, Glob]",
            "Research best practices with `mcp__searxng__search`.",
        )
        violations = check_researcher_web_disclosure(path)
        assert len(violations) == len(RESEARCH_MARKERS), (
            f"expected one violation per missing marker, got {violations}"
        )
        for marker in RESEARCH_MARKERS:
            assert any(marker in v for v in violations), f"{marker!r} not reported"

    def test_nc4_markers_present_but_grants_missing_fail_r3(self, tmp_path):
        """NC4 mirror: right markers, no searxng grants → R3 MUST refuse.

        The complementary half. Together these prove R3 requires BOTH arms,
        so neither half alone can satisfy it.
        """
        path = TestAgentMcpToolDeclarations._write_agent(
            tmp_path,
            "researcher",
            "name: researcher\ntools: [Read, Grep, Glob]",
            "End with `Research: searxng`, `Research: web`, or "
            "`Research: unavailable (no searxng server)`.",
        )
        violations = check_researcher_web_disclosure(path)
        assert len(violations) == len(SEARXNG_TOOLS), (
            f"expected one violation per missing grant, got {violations}"
        )
        for tool in sorted(SEARXNG_TOOLS):
            assert any(tool in v for v in violations), f"{tool!r} not reported"

    def test_nc4_the_shipped_researcher_is_permitted(self):
        """Positive control paired with NC4: the real file must PASS R3."""
        assert not check_researcher_web_disclosure(AGENTS_DIR / "researcher.md")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
