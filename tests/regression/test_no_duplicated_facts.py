"""The archived-code rule and the no-counts-in-prose rule, enforced.

PROJECT.md states: "active code must never import or reference archived
components. Archived code lives in */archived/ directories and is dead code."
That rule exists so the archive can be deleted without breaking anything.
Nothing enforced it, so it has been false for months and the archive cannot
safely be deleted.

WHY A GATE RATHER THAN CARE
---------------------------
These were being found by accident, one red test at a time. A systematic scan
found 13 archived references where careful manual work had found 4 -- including
one in skill_loader.py, a file edited an hour earlier while fixing the
identical drift on the skills side. Correctness that depends on remembering to
check is not correctness.

THE UNDERLYING DEFECT
---------------------
One fact stored in two places, with nothing forcing the copy to change when the
original does. Instances found: skill_loader -> skills (#1526), AGENT_CONFIGS ->
agents (#1528), the test_skills roster, three code copies (#1521), four
registration surfaces (#1522), and component counts in prose.

For counts specifically the fix is DELETION, not generation: a number in prose
is a copy of something that changes, and generating it only adds a generator
that can also rot. If a count is needed, measure it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PLUG = REPO / "plugins" / "autonomous-dev"


# --------------------------------------------------------------------------
# ground truth, measured -- never hardcoded
# --------------------------------------------------------------------------

def _active_agents() -> set:
    return {p.stem for p in (PLUG / "agents").glob("*.md")}


def _archived_agents() -> set:
    d = PLUG / "agents" / "archived"
    return {p.stem for p in d.glob("*.md")} if d.is_dir() else set()


def _active_skills() -> set:
    return {p.name for p in (PLUG / "skills").iterdir()
            if p.is_dir() and (p / "SKILL.md").exists()}


def _archived_skills() -> set:
    d = PLUG / "skills" / "archived"
    return {p.name for p in d.iterdir() if p.is_dir()} if d.is_dir() else set()


def _active_python() -> list:
    """Active library and hook sources. Excludes archived/ by construction."""
    out = []
    for sub in ("lib", "hooks"):
        for p in (PLUG / sub).rglob("*.py"):
            if "archived" in p.parts or "__pycache__" in p.parts:
                continue
            out.append(p)
    return sorted(out)


# Not a name-SHAPE regex. An earlier version matched quoted kebab-case tokens
# and was therefore blind to single-word components -- `advisor` and
# `orchestrator` are archived agents, and `orchestrator` is referenced by a
# registered hook and three command files. That version reported 13 references
# as though it were a total; it was a floor.
#
# Searching for each KNOWN archived name is exact and has no shape blind spot.
# Caught by this module's own negative control failing, not by review.
_NON_COMPONENTS = {"README", "readme", "__init__"}


def _quoted(name: str) -> re.Pattern:
    return re.compile(r'["\']' + re.escape(name) + r'["\']')


def _archived_references() -> list:
    """[(file, name, kind)] for every archived component named in active code."""
    active = _active_agents() | _active_skills()
    arch_a = {n for n in _archived_agents() if n not in _NON_COMPONENTS}
    arch_s = {n for n in _archived_skills() if n not in _NON_COMPONENTS}

    # A name that is ALSO an active component is not a dangling reference.
    targets = [(n, "agent") for n in sorted(arch_a - active)]
    targets += [(n, "skill") for n in sorted(arch_s - active)]

    hits = []
    for py in _active_python():
        try:
            txt = py.read_text(errors="replace")
        except OSError:
            continue
        for name, kind in targets:
            if _quoted(name).search(txt):
                hits.append((py.relative_to(REPO), name, kind))
    return hits


class TestArchivedCodeRule:
    """PROJECT.md's archived-code rule, made enforceable."""

    def test_no_active_code_references_archived_components(self):
        hits = _archived_references()
        detail = "\n".join(f"  {kind:<6} {name:<30} {f}" for f, name, kind in hits)
        assert not hits, (
            f"{len(hits)} reference(s) to archived components in active code.\n"
            f"{detail}\n\n"
            "PROJECT.md: 'active code must never import or reference archived "
            "components.' That rule exists so the archive can be deleted "
            "safely; while these remain, it cannot.\n"
            "Fix: repoint to the live successor, or remove the entry."
        )

    @pytest.mark.parametrize("planted", ["advisor", "quality-validator"])
    def test_scanner_detects_a_planted_reference(self, planted):
        """Negative control on the SCANNER, not the tree.

        A gate that cannot fire is worth nothing. Both a SINGLE-WORD and a
        hyphenated archived name are planted, because the first version of this
        scanner used a kebab-case shape regex and was silently blind to
        single-word components -- it reported 13 references as a total when it
        was a floor. This control is what caught that.
        """
        arch = _archived_agents() | _archived_skills()
        if planted not in arch:
            pytest.skip(f"{planted} is not archived in this tree")
        assert _quoted(planted).search(f'AGENT = "{planted}"'), (
            f"scanner failed to detect a planted archived name {planted!r} — "
            "it cannot catch what it exists to catch"
        )

    def test_clean_source_does_not_false_positive(self):
        """A file naming only LIVE components must not be flagged."""
        arch = _archived_agents() | _archived_skills()
        active = _active_agents() | _active_skills()
        sample = "\n".join(f'X = "{n}"' for n in sorted(active)[:5])
        found = [n for n in sorted(arch - active) if _quoted(n).search(sample)]
        assert not found, f"false positive on live component names: {found}"


# --------------------------------------------------------------------------
# counts in prose
# --------------------------------------------------------------------------

# Documents that describe intent, where a changing number does not belong.
_PROSE_DOCS = [
    REPO / "CLAUDE.md",
    REPO / ".claude" / "PROJECT.md",
    PLUG / ".claude-plugin" / "marketplace.json",
]

# "#348 hook registration" is an ISSUE NUMBER, not a count. An earlier version
# of this scan reported PROJECT.md as claiming "348 hooks" -- a false positive
# that would have been filed as fact. Hence the lookbehind, and the control below.
_COUNT = re.compile(
    r"(?<!#)(?<!#\d)(?<!#\d\d)(?<!#\d\d\d)\b(\d+)\s+"
    r"(agents?|skills?|hooks?)\b", re.I)


def _count_claims(text: str) -> list:
    return [(int(m.group(1)), m.group(2).lower().rstrip("s"))
            for m in _COUNT.finditer(text)]


class TestNoComponentCountsInProse:
    """A count in prose is a copy of a fact that changes.

    Deliberately DELETION rather than generation: generating the number adds a
    generator that can also rot, and the number still tells a reader nothing
    they could not measure. Describe what a thing is for; measure how many
    there are.
    """

    @pytest.mark.parametrize("doc", [d for d in _PROSE_DOCS if d.exists()],
                             ids=lambda p: p.name)
    def test_doc_states_no_component_counts(self, doc):
        claims = _count_claims(doc.read_text(errors="replace"))
        detail = ", ".join(f"{n} {noun}s" for n, noun in sorted(set(claims)))
        assert not claims, (
            f"{doc.relative_to(REPO)} states component counts: {detail}\n"
            "These drift silently — measured today: 33 hook files (11 reachable), "
            "17 agents, 20 skills.\n"
            "Fix: remove the number. Describe purpose, not inventory; anyone "
            "needing a count can measure one."
        )

    def test_issue_numbers_are_not_mistaken_for_counts(self):
        """Negative control. Without this the pattern flags '#348 hook'."""
        assert _count_claims("proven through #348 hook registration") == []
        assert _count_claims("see #206 test gate and #310 anti-stubbing") == []

    def test_pattern_still_detects_a_real_count(self):
        """...and the control must not have disabled the detector."""
        assert _count_claims("Enforcement: 27 hooks with hard gates") == [(27, "hook")]
