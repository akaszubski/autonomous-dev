#!/usr/bin/env python3
"""Serena LSP navigation grants and the anti-silent-fallback sentinel.

Issue #1574: an agent without ``mcp__serena__*`` in its frontmatter cannot
follow the repo convention "Serena for dependencies, grep for strings". It is
structurally forced to answer symbol questions ("who calls this?", "is this
unused?") with a text matcher, and a grep-derived caller set is a LOWER BOUND
presented as a total.

This module guards the three agents brought in scope by #1574 —
``implementer``, ``security-auditor``, ``spec-validator`` — on two axes:

1. They GRANT the three read-only serena navigation tools.
2. Their body carries the ``Navigation:`` sentinel, which turns an invisible
   degradation (serena unavailable -> silent grep fallback) into a greppable
   string, so a grep-derived answer is never mistaken for an authoritative one.

Deliberate non-duplication of prior art
---------------------------------------
``tests/unit/lib/test_agent_registry_consistency.py`` (Issue #1546) already
enforces INV-1..INV-5 repo-wide over every active agent:

* INV-2 is an ALLOWLIST — every granted ``mcp__*`` tool must be a member of
  ``MCP_READ_TOOLS``. That is strictly STRONGER than "declares no member of
  ``MCP_WRITE_TOOLS``", because it also refuses tools in neither registry.
* INV-3 is the ``MCP_WRITE_TOOLS`` denylist over ``tools:`` and
  ``optional_mcp:`` together.

So the repo-wide "no agent grants a serena writer" sweep is ALREADY COVERED and
is NOT re-implemented here. What this module adds is the narrow pin
``test_in_scope_agents_grant_no_write_capable_serena_tool``: it is scoped to
the three #1574 agents and derived from ``MCP_WRITE_TOOLS`` (never a hardcoded
roster — a hardcoded list goes stale exactly when a new writer is added). It
exists as defence-in-depth so that a future weakening of INV-3 cannot silently
let the #1574 grant grow a write tool.

The frontmatter parser is IMPORTED from the #1546 module rather than re-written,
so this repo has one canonical agent-frontmatter parser rather than two that can
drift.
"""

from pathlib import Path

import pytest

from plugins.autonomous_dev.lib.tool_intent import MCP_READ_TOOLS, MCP_WRITE_TOOLS
from tests.unit.lib.test_agent_registry_consistency import (
    _as_tool_list,
    _split_frontmatter,
)

# tests/unit/test_agent_serena_tools.py -> unit -> tests -> repo root = parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# The TRACKED source of truth. NOT ``.claude/agents/``, which is a gitignored
# local deploy artifact (``.gitignore:147`` matches ``.claude/*``; ``git
# ls-files .claude/agents/`` returns 0 files). A guard pointed at an untracked
# deploy artifact would be red in CI and in every fresh clone, and green or red
# locally according to deploy freshness rather than according to the change.
AGENTS_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "agents"

# The read-only navigation triad added by #1574.
SERENA_NAV_TOOLS = frozenset(
    {
        "mcp__serena__find_symbol",
        "mcp__serena__find_referencing_symbols",
        "mcp__serena__get_symbols_overview",
    }
)

# Agents brought in scope by #1574.
#
# This is a LITERAL, deliberately. "Which agents perform symbol reasoning" is an
# editorial judgment with no on-disk registry to derive it from:
# ``AgentInvoker.AGENT_CONFIGS`` carries only progress_pct, artifacts_required,
# description_template and mission — no navigation field. The established
# precedent for exactly this situation is the ``READ_ONLY_AGENTS`` literal at
# ``tests/unit/lib/test_agent_registry_consistency.py:51``.
#
# The literal is NOT the only rule here: ``TestSentinelScalesToEveryGrantee``
# below derives its roster from disk, so a future agent that gains serena grants
# is covered without anyone editing this tuple.
SERENA_NAV_AGENTS = ("implementer", "security-auditor", "spec-validator")

SENTINEL_SERENA = "Navigation: serena"
SENTINEL_GREP = "Navigation: grep (serena unavailable)"

# Agents that grant the navigation triad but do NOT yet carry the sentinel.
#
# ``plan-critic`` received its serena grants in 1e8720d1 (#1574 priority 1)
# without the body rule. Fixing it is out of scope for this change (#1574 scopes
# the body-rule work to exactly three agents), so it is pinned here rather than
# silently excluded — and ``test_exemption_set_only_shrinks`` is the ceiling on
# this exemption mechanism, so the escape hatch cannot grow.
SENTINEL_EXEMPT = frozenset({"plan-critic"})


def _agent_path(agent_name: str) -> Path:
    """Return the path to an active agent's markdown file.

    Args:
        agent_name: Bare agent name, e.g. ``"implementer"``.

    Returns:
        Path to ``plugins/autonomous-dev/agents/<agent_name>.md``.
    """
    return AGENTS_DIR / f"{agent_name}.md"


def _granted_tools(agent_name: str) -> "set[str]":
    """Return the set of tools an agent declares in its ``tools:`` frontmatter.

    Args:
        agent_name: Bare agent name, e.g. ``"implementer"``.

    Returns:
        Set of declared tool-name strings.

    Raises:
        ValueError: If the agent frontmatter is missing or unparseable.
    """
    frontmatter, _body = _split_frontmatter(_agent_path(agent_name))
    return set(_as_tool_list(frontmatter.get("tools")))


def _body(agent_name: str) -> str:
    """Return an agent's markdown body (frontmatter excluded).

    Args:
        agent_name: Bare agent name, e.g. ``"implementer"``.

    Returns:
        The body text following the closing ``---``.

    Raises:
        ValueError: If the agent frontmatter is missing or unparseable.
    """
    return _split_frontmatter(_agent_path(agent_name))[1]


def _agents_granting_serena_navigation() -> "list[str]":
    """Discover every active agent granting AT LEAST ONE navigation tool.

    Derived from disk so the sentinel rule scales to agents that do not exist
    yet, rather than being scoped to the instance that prompted it.

    The membership test is ANY, not ALL, deliberately. Keying on the full triad
    would let a PARTIAL grantee escape the sentinel obligation entirely —
    ``test-coverage-auditor`` grants two of the three tools today, so an
    all-three rule silently skipped it. An agent holding even one symbol tool
    can produce a symbol answer, and therefore owes the reader a statement of
    which instrument produced it.

    Returns:
        Sorted list of agent names whose ``tools:`` intersects
        ``SERENA_NAV_TOOLS``.

    Raises:
        ValueError: If any active agent's frontmatter is missing or unparseable.
    """
    names = []
    for path in sorted(AGENTS_DIR.glob("*.md")):
        if not path.is_file():
            continue
        frontmatter, _body_text = _split_frontmatter(path)
        if SERENA_NAV_TOOLS & set(_as_tool_list(frontmatter.get("tools"))):
            names.append(path.stem)
    return names


class TestInScopeAgentsGrantSerenaNavigation:
    """The three #1574 agents declare the read-only navigation triad."""

    def test_agents_dir_is_populated(self):
        """Sanity: an empty glob would make every rule below vacuously true."""
        paths = [p for p in AGENTS_DIR.glob("*.md") if p.is_file()]
        assert len(paths) >= 15, (
            f"Expected the full active agent roster, found {len(paths)} in "
            f"{AGENTS_DIR}. Verify AGENTS_DIR points at the tracked source."
        )

    @pytest.mark.parametrize("agent_name", SERENA_NAV_AGENTS)
    def test_in_scope_agent_grants_all_three_navigation_tools(self, agent_name):
        """Issue #1574: each in-scope agent declares all three serena nav tools."""
        granted = _granted_tools(agent_name)
        missing = SERENA_NAV_TOOLS - granted
        assert not missing, (
            f"{agent_name}.md is missing serena navigation grants: "
            f"{sorted(missing)}\n"
            f"Expected tools: to be a superset of {sorted(SERENA_NAV_TOOLS)}\n"
            f"Without them the agent cannot answer symbol questions and is "
            f"forced to present a grep lower bound as a total (Issue #1574)."
        )

    @pytest.mark.parametrize("agent_name", SERENA_NAV_AGENTS)
    def test_in_scope_agent_preserves_its_pre_existing_tools(self, agent_name):
        """The nav grant is an APPEND — Read/Grep/Glob must survive it."""
        granted = _granted_tools(agent_name)
        for baseline_tool in ("Read", "Grep", "Glob"):
            assert baseline_tool in granted, (
                f"{agent_name}.md lost its pre-existing {baseline_tool!r} grant. "
                f"Issue #1574 appends serena tools; it never replaces the "
                f"existing list. Declared: {sorted(granted)}"
            )

    @pytest.mark.parametrize("agent_name", SERENA_NAV_AGENTS)
    def test_in_scope_agents_grant_no_write_capable_serena_tool(self, agent_name):
        """Read-only contract: no member of MCP_WRITE_TOOLS may be granted.

        Derived from ``tool_intent.MCP_WRITE_TOOLS`` rather than a hardcoded
        roster, so adding a new serena writer to the registry extends this guard
        automatically. See the module docstring for why this is a narrow pin and
        not a re-implementation of INV-2/INV-3.
        """
        granted = _granted_tools(agent_name)
        writers = granted & MCP_WRITE_TOOLS
        assert not writers, (
            f"{agent_name}.md grants write-capable MCP tool(s) {sorted(writers)}.\n"
            f"Expected: only read-classified tools (Issue #1574 grants the "
            f"read-only navigation triad and nothing else).\n"
            f"See: plugins/autonomous-dev/lib/tool_intent.py MCP_WRITE_TOOLS"
        )

    def test_navigation_triad_is_read_classified(self):
        """Premise check: the triad really is on the read allowlist.

        If a triad member were ever reclassified as a writer, the grant tests
        above and the write-tool pin would contradict each other. This asserts
        the premise instead of letting the contradiction sit silently.
        """
        assert SERENA_NAV_TOOLS <= MCP_READ_TOOLS, (
            f"Navigation triad members missing from MCP_READ_TOOLS: "
            f"{sorted(SERENA_NAV_TOOLS - MCP_READ_TOOLS)}"
        )
        assert not (SERENA_NAV_TOOLS & MCP_WRITE_TOOLS), (
            f"Navigation triad members classified as writers: "
            f"{sorted(SERENA_NAV_TOOLS & MCP_WRITE_TOOLS)}"
        )


class TestNavigationSentinel:
    """The anti-silent-fallback sentinel must be present and complete."""

    @pytest.mark.parametrize("agent_name", SERENA_NAV_AGENTS)
    def test_in_scope_agent_body_declares_the_serena_sentinel(self, agent_name):
        """Issue #1574: the body instructs emitting ``Navigation: serena``."""
        body = _body(agent_name)
        assert SENTINEL_SERENA in body, (
            f"{agent_name}.md body does not contain {SENTINEL_SERENA!r}.\n"
            f"Expected: the Code Navigation (serena LSP) section, which ends "
            f"'End your output with exactly one of: `Navigation: serena` or "
            f"`Navigation: grep (serena unavailable)`.'\n"
            f"See: plugins/autonomous-dev/agents/planner.md for the canonical text"
        )

    @pytest.mark.parametrize("agent_name", SERENA_NAV_AGENTS)
    def test_in_scope_agent_body_declares_the_grep_fallback_sentinel(self, agent_name):
        """Both arms are required — one arm cannot signal a degradation."""
        body = _body(agent_name)
        assert SENTINEL_GREP in body, (
            f"{agent_name}.md body does not contain {SENTINEL_GREP!r}.\n"
            f"Without the fallback arm a grep-derived answer emits the serena "
            f"sentinel and is mistaken for an authoritative one (Issue #1574)."
        )

    @pytest.mark.parametrize("agent_name", SERENA_NAV_AGENTS)
    def test_in_scope_agent_mandates_graceful_degradation(self, agent_name):
        """On serena failure the agent MUST fall back to Grep and continue.

        The sentinel is only half the mechanism. Without the explicit fallback
        instruction an agent could treat serena unavailability as licence to
        skip a required audit entirely.
        """
        body = _body(agent_name)
        assert "fall back to `Grep`" in body, (
            f"{agent_name}.md does not mandate the Grep fallback. The Code "
            f"Navigation section must instruct falling back and CONTINUING, "
            f"never skipping a required audit because serena was missing."
        )

    @pytest.mark.parametrize("agent_name", SERENA_NAV_AGENTS)
    def test_in_scope_agent_forbids_calling_undeclared_serena_tools(self, agent_name):
        """The section must bound the agent to its declared tool surface."""
        body = _body(agent_name)
        assert (
            "MUST NOT call any serena tool that is absent from your `tools:` "
            "frontmatter line" in body
        ), (
            f"{agent_name}.md omits the undeclared-tool prohibition from the "
            f"Code Navigation section. Copy the section from planner.md verbatim."
        )


class TestSentinelScalesToEveryGrantee:
    """Derived-from-disk rule: granting serena obliges carrying the sentinel.

    This complements the ``SERENA_NAV_AGENTS`` literal. The roster here is
    discovered from the filesystem, so an agent that gains serena grants in a
    future change is covered without editing this file — the guard is not
    scoped to the instance that prompted it.
    """

    def test_grantee_roster_is_discovered_and_non_empty(self):
        """Sanity: the derived rule must actually be running on agents."""
        grantees = _agents_granting_serena_navigation()
        assert len(grantees) >= len(SERENA_NAV_AGENTS), (
            f"Discovered only {grantees} agents granting the navigation triad; "
            f"expected at least the {len(SERENA_NAV_AGENTS)} in-scope agents. "
            f"An empty roster would make the rule below vacuous."
        )
        for agent_name in SERENA_NAV_AGENTS:
            assert agent_name in grantees, (
                f"{agent_name} grants the triad per the literal roster but was "
                f"not discovered from disk — the two rosters disagree."
            )

    def test_every_serena_grantee_carries_the_sentinel(self):
        """Any agent granting the triad must emit a Navigation: line."""
        offenders = []
        for agent_name in _agents_granting_serena_navigation():
            if agent_name in SENTINEL_EXEMPT:
                continue
            body = _body(agent_name)
            if SENTINEL_SERENA not in body or SENTINEL_GREP not in body:
                offenders.append(agent_name)
        assert not offenders, (
            f"Agents granting serena navigation without the sentinel: "
            f"{sorted(offenders)}\n"
            f"Expected: every grantee ends its output with exactly one of "
            f"`{SENTINEL_SERENA}` or `{SENTINEL_GREP}`.\n"
            f"Granting the tools without the sentinel reintroduces the silent "
            f"fallback the sentinel exists to make visible (Issue #1574)."
        )

    def test_exemption_set_only_shrinks(self):
        """Ceiling on the exemption mechanism — the escape hatch cannot grow.

        An exemption list without its own ratchet is decorative: the next agent
        that fails the rule gets added to the list instead of fixed. This pins
        the exemption set to exactly the one known gap.
        """
        assert SENTINEL_EXEMPT == frozenset({"plan-critic"}), (
            f"SENTINEL_EXEMPT changed to {sorted(SENTINEL_EXEMPT)}.\n"
            f"Adding an agent here is NOT an acceptable resolution — add the "
            f"Code Navigation section to that agent instead. Removing "
            f"'plan-critic' (after fixing it) requires updating this assertion "
            f"to frozenset()."
        )

    def test_exempt_agents_actually_exist_and_actually_grant_serena(self):
        """An exemption for a non-grantee would be dead weight hiding nothing."""
        grantees = set(_agents_granting_serena_navigation())
        for agent_name in sorted(SENTINEL_EXEMPT):
            assert _agent_path(agent_name).exists(), (
                f"SENTINEL_EXEMPT names {agent_name!r} but "
                f"{_agent_path(agent_name)} does not exist — stale exemption."
            )
            assert agent_name in grantees, (
                f"SENTINEL_EXEMPT names {agent_name!r}, which does not grant the "
                f"navigation triad. The exemption is unnecessary; remove it."
            )


class TestNegativeControls:
    """The rules must be watched REFUSING, not only permitting.

    Each control feeds a synthetic agent through the same helpers the live
    rules use, so a rule that could never fail cannot pass these.
    """

    @staticmethod
    def _write_agent(tmp_path: Path, name: str, frontmatter: str, body: str) -> Path:
        path = tmp_path / f"{name}.md"
        path.write_text(f"---\n{frontmatter}\n---\n\n{body}\n", encoding="utf-8")
        return path

    def test_control_missing_nav_tool_is_detected(self, tmp_path):
        """Two of three granted -> the missing-grant check must report it."""
        path = self._write_agent(
            tmp_path,
            "control-partial-grant",
            "name: control-partial-grant\n"
            "tools: [Read, Grep, Glob, mcp__serena__find_symbol, "
            "mcp__serena__get_symbols_overview]",
            "No navigation section here.",
        )
        frontmatter, _ = _split_frontmatter(path)
        granted = set(_as_tool_list(frontmatter.get("tools")))
        missing = SERENA_NAV_TOOLS - granted
        assert missing == {"mcp__serena__find_referencing_symbols"}, (
            f"expected exactly the caller-search tool to be reported missing, "
            f"got {sorted(missing)}"
        )

    def test_control_write_capable_grant_is_detected(self, tmp_path):
        """A serena writer in tools: must trip the MCP_WRITE_TOOLS pin."""
        path = self._write_agent(
            tmp_path,
            "control-writer",
            "name: control-writer\n"
            "tools: [Read, Grep, Glob, mcp__serena__find_symbol, "
            "mcp__serena__find_referencing_symbols, "
            "mcp__serena__get_symbols_overview, "
            "mcp__serena__replace_symbol_body]",
            "No navigation section here.",
        )
        frontmatter, _ = _split_frontmatter(path)
        granted = set(_as_tool_list(frontmatter.get("tools")))
        assert granted & MCP_WRITE_TOOLS == {"mcp__serena__replace_symbol_body"}, (
            f"the write-tool pin failed to flag replace_symbol_body; "
            f"flagged {sorted(granted & MCP_WRITE_TOOLS)}"
        )

    def test_control_every_forbidden_write_tool_is_in_the_registry(self):
        """The five tools #1574 forbids are all derivable from MCP_WRITE_TOOLS.

        Proves the derived pin genuinely covers the brief's forbidden list — a
        hardcoded roster is unnecessary because the registry already names them.
        """
        forbidden = {
            "mcp__serena__replace_symbol_body",
            "mcp__serena__rename_symbol",
            "mcp__serena__safe_delete_symbol",
            "mcp__serena__insert_after_symbol",
            "mcp__serena__replace_in_files",
        }
        uncovered = forbidden - MCP_WRITE_TOOLS
        assert not uncovered, (
            f"Issue #1574 forbids {sorted(uncovered)} but tool_intent."
            f"MCP_WRITE_TOOLS does not classify them, so the derived pin would "
            f"not catch them. Classify them in tool_intent.py."
        )

    def test_control_partial_grantee_is_still_subject_to_the_sentinel_rule(self):
        """A partial grantee must not escape the sentinel obligation.

        ``test-coverage-auditor`` grants two of the three navigation tools. An
        all-three membership test skipped it silently — a guard scoped to the
        shape of the instance that prompted it. This pins the ANY semantics by
        asserting the real partial grantee IS discovered and DOES carry the
        sentinel.
        """
        granted = _granted_tools("test-coverage-auditor")
        overlap = SERENA_NAV_TOOLS & granted
        assert overlap, "premise: test-coverage-auditor grants some nav tool"
        assert not SERENA_NAV_TOOLS <= granted, (
            f"premise: test-coverage-auditor is a PARTIAL grantee. It now "
            f"grants the full triad, so this control no longer exercises the "
            f"partial case — pick another partial grantee or drop it. "
            f"Granted: {sorted(overlap)}"
        )
        assert "test-coverage-auditor" in _agents_granting_serena_navigation(), (
            "the ANY membership test failed to discover the partial grantee"
        )
        body = _body("test-coverage-auditor")
        assert SENTINEL_SERENA in body and SENTINEL_GREP in body, (
            "test-coverage-auditor is a discovered grantee and must carry the "
            "sentinel like any other"
        )

    def test_control_single_tool_grantee_is_discovered(self, tmp_path):
        """Synthetic: one nav tool is enough to incur the sentinel obligation."""
        path = self._write_agent(
            tmp_path,
            "control-single-tool",
            "name: control-single-tool\n"
            "tools: [Read, mcp__serena__find_referencing_symbols]",
            "No sentinel here.",
        )
        frontmatter, body = _split_frontmatter(path)
        granted = set(_as_tool_list(frontmatter.get("tools")))
        assert SERENA_NAV_TOOLS & granted, "ANY test must match a single tool"
        assert not SERENA_NAV_TOOLS <= granted, "premise: not a full grantee"
        assert SENTINEL_SERENA not in body, (
            "this synthetic agent would be flagged by the sentinel rule"
        )

    def test_control_missing_sentinel_is_detected(self, tmp_path):
        """A grantee body with no Navigation: line must be reported."""
        path = self._write_agent(
            tmp_path,
            "control-no-sentinel",
            "name: control-no-sentinel\n"
            "tools: [Read, mcp__serena__find_symbol, "
            "mcp__serena__find_referencing_symbols, "
            "mcp__serena__get_symbols_overview]",
            "Structural questions MUST use serena. But no sentinel is declared.",
        )
        body = _split_frontmatter(path)[1]
        assert SENTINEL_SERENA not in body
        assert SENTINEL_GREP not in body

    def test_control_half_a_sentinel_is_still_a_failure(self, tmp_path):
        """Only the serena arm present -> the grep-arm rule must still refuse.

        This is the shape the single-arm version of the rule would permit: an
        agent that always claims `Navigation: serena` and has no way to signal
        that it silently fell back to grep.
        """
        path = self._write_agent(
            tmp_path,
            "control-half-sentinel",
            "name: control-half-sentinel\n"
            "tools: [Read, mcp__serena__find_symbol, "
            "mcp__serena__find_referencing_symbols, "
            "mcp__serena__get_symbols_overview]",
            "End your output with: `Navigation: serena`.",
        )
        body = _split_frontmatter(path)[1]
        assert SENTINEL_SERENA in body, "premise: the serena arm IS present"
        assert SENTINEL_GREP not in body, (
            "the grep-fallback arm must be absent for this control to exercise "
            "the half-sentinel case"
        )

    def test_control_non_grantee_is_not_subject_to_the_sentinel_rule(self, tmp_path):
        """Positive control: an agent with no serena grants is out of scope.

        A rule that flagged every agent regardless of grants would pass all the
        negative controls above while being useless. This watches it PERMIT.
        """
        path = self._write_agent(
            tmp_path,
            "control-no-serena",
            "name: control-no-serena\ntools: [Read, Grep, Glob]",
            "No serena, no sentinel, and that is fine.",
        )
        frontmatter, body = _split_frontmatter(path)
        granted = set(_as_tool_list(frontmatter.get("tools")))
        assert not SERENA_NAV_TOOLS <= granted, "premise: not a grantee"
        assert SENTINEL_SERENA not in body
        # A non-grantee carries no sentinel obligation; the derived rule skips it.

    def test_control_malformed_frontmatter_fails_loudly(self, tmp_path):
        """A broken agent file must raise naming the file, never skip silently."""
        path = tmp_path / "control-malformed.md"
        path.write_text("---\ntools: [Read\n bad: : yaml\n---\n\nbody\n", encoding="utf-8")
        with pytest.raises(ValueError, match="control-malformed.md"):
            _split_frontmatter(path)


class TestDeployedCopyIsNotTheSourceOfTruth:
    """Pin the corpus choice so a future edit cannot quietly repoint it."""

    def test_dot_claude_agents_is_untracked_and_therefore_not_the_corpus(self):
        """``.claude/agents/`` is a gitignored deploy artifact, not source.

        Issue #1574's brief asked for the guard to read ``.claude/agents/*.md``.
        That directory matches ``.gitignore:147`` (``.claude/*``) and has zero
        git-tracked files, so a guard reading it would be red in CI and in every
        fresh clone. This test records the evidence for the deviation so the
        next reader does not "fix" AGENTS_DIR back to the artifact.
        """
        import subprocess

        tracked = subprocess.run(
            ["git", "ls-files", ".claude/agents/"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert tracked == "", (
            f".claude/agents/ now has git-tracked files:\n{tracked}\n"
            f"If it became the source of truth, revisit AGENTS_DIR here."
        )

        source_tracked = subprocess.run(
            ["git", "ls-files", "plugins/autonomous-dev/agents/"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert source_tracked, (
            "plugins/autonomous-dev/agents/ has no tracked files — AGENTS_DIR "
            "does not point at a tracked corpus."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
