#!/usr/bin/env python3
"""Ratchet: ``anthropic.Anthropic`` may only be constructed in one place.

Issue #1593. ``lib/genai_credentials.get_anthropic_client`` is the sanctioned
construction site. Every other direct ``Anthropic(...)`` call is a bypass of
the credential pre-flight check, and each one re-creates the #1593 defect:
a truthy, credential-less client whose failure is deferred to request time and
swallowed there.

The sites that remain are named in :data:`PINNED_OUT_OF_SINK` with a per-entry
justification. **That set may only SHRINK.** Adding an entry is NOT an
acceptable resolution for a failure of this guard -- route the construction
through ``get_anthropic_client()`` instead.

The ceiling
-----------
:data:`PINNED_CEILING` exists because an escape hatch without its own ceiling is
decorative: the next module that fails simply gets appended to the list instead
of being migrated. Unlike ``test_refusal_sink_ratchet.py`` (which uses ``<=``),
this ratchet asserts **equality**. Equality is the stronger form -- it forces
both growth *and* shrink to be a deliberate two-line diff, so the exemption list
can never move without appearing in review.

Instrument choice
-----------------
Detection is **AST**, not regex. Two files in this repo mention "Anthropic" as
text without constructing anything (``lib/semantic_gate.py`` in a docstring,
``lib/secret_patterns.py`` in regex pattern data). A filename-level
``grep -l Anthropic`` reports both; the AST detector reports neither. Both are
pinned below as negative controls, each asserting its own premise so it cannot
pass vacuously if the file is reworded.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pytest

# tests/unit/lib/test_x.py -> lib -> unit -> tests -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]

PLUGIN_ROOT = _REPO_ROOT / "plugins" / "autonomous-dev"
HOOKS_DIR = PLUGIN_ROOT / "hooks"
LIB_DIR = PLUGIN_ROOT / "lib"
SCRIPTS_DIR = _REPO_ROOT / "scripts"

SCAN_ROOTS = (HOOKS_DIR, LIB_DIR, SCRIPTS_DIR)

# Path components that take a file out of scope. ``archived/`` is excluded by
# the PROJECT.md archived-code rule; ``.codex/`` and ``.worktrees/`` are mirrors
# of the source tree and would double-count every finding.
EXCLUDED_PATH_PARTS = frozenset({"archived", ".codex", ".worktrees"})

# The sanctioned sink: the single module allowed to construct the SDK client.
SANCTIONED_CONSTRUCTION_SITES = frozenset({"genai_credentials.py"})

# Modules known to construct ``Anthropic`` outside the sanctioned sink.
#
# This set may only SHRINK. Adding an entry is NOT an acceptable resolution for
# a guard failure: call ``genai_credentials.get_anthropic_client()`` instead,
# which performs the credential pre-flight check that #1593 is about.
#
#  * alignment_gate.py (:152) -- has its own pre-flight check at :138-154, but
#    returns a ``(client, model, provider)`` triple and raises ``AlignmentError``
#    on failure. Migrating means reshaping its error contract; deferred.
#  * conflict_resolver.py (:256, :429, :479) -- all three take ``api_key`` as a
#    parameter rather than reading the environment. Credential-injected, so
#    structurally different from the helper's env-resolution contract. Its
#    ``__main__`` pre-flight lives at :1094-1098.
#  * genai_manifest_validator.py (:183) -- construction is inlined in
#    ``__init__`` behind a ``has_api_key`` flag that other methods branch on.
#    Migrating means untangling that flag; deferred.
#  * genai_validate.py (:95) -- returns a ``(client, model, provider)`` triple
#    with an OpenRouter branch and calls ``sys.exit(1)`` on failure; 4 callers.
#    Migrating means reshaping the return contract; deferred.
#  * improve_reviewer.py (:454) -- top-level ``scripts/``, which
#    ``config/install_manifest.json`` does NOT deploy (its "scripts" block ships
#    only ``plugins/autonomous-dev/scripts/*``). A deployed consumer could not
#    import the helper from here, so this is pinned rather than migrated.
#  * run_reviewer_benchmark.py (:69) -- same undeployed-``scripts/`` reason.
PINNED_OUT_OF_SINK: "frozenset[str]" = frozenset(
    {
        "alignment_gate.py",
        "conflict_resolver.py",
        "genai_manifest_validator.py",
        "genai_validate.py",
        "improve_reviewer.py",
        "run_reviewer_benchmark.py",
    }
)

# Ceiling on the escape hatch, asserted by EQUALITY (see module docstring).
#
# History -- the ratchet may only count DOWN:
#   7 -> 6  Issue #1593: genai_refactor_analyzer.py (:886, :919) migrated to
#           genai_credentials.get_anthropic_client(). The guard landed at 7,
#           green against the live state, and shrank in the same change.
PINNED_CEILING = 6


def _is_anthropic_construction(node: ast.AST) -> bool:
    """Return True for a call that constructs the Anthropic SDK client.

    Matches both import shapes used in this repo::

        from anthropic import Anthropic;  Anthropic(...)     -> ast.Name
        import anthropic;  anthropic.Anthropic(...)          -> ast.Attribute
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "Anthropic"
    if isinstance(func, ast.Attribute):
        return func.attr == "Anthropic"
    return False


def anthropic_construction_sites(
    roots: Optional[Iterable[Path]] = None,
) -> Dict[str, List[int]]:
    """Scan ``roots`` for direct Anthropic client constructions.

    Args:
        roots: Directories to scan. Defaults to :data:`SCAN_ROOTS`. Overridable
            so the guard can be watched refusing on a synthetic tree.

    Returns:
        Mapping of file *basename* to the line numbers where a construction
        occurs. Basenames are used because the pinned set is a set of module
        names, and because ``scripts/`` sits outside the plugin tree.
    """
    sites: Dict[str, List[int]] = {}
    for root in roots if roots is not None else SCAN_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if EXCLUDED_PATH_PARTS.intersection(path.parts):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if _is_anthropic_construction(node):
                    sites.setdefault(path.name, []).append(node.lineno)
    return sites


def out_of_sink_sites(roots: Optional[Iterable[Path]] = None) -> Dict[str, List[int]]:
    """Construction sites outside :data:`SANCTIONED_CONSTRUCTION_SITES`."""
    return {
        name: lines
        for name, lines in anthropic_construction_sites(roots).items()
        if name not in SANCTIONED_CONSTRUCTION_SITES
    }


class TestDetectorIntegrity:
    """The instrument must be verified before any of its output is trusted."""

    def test_detector_is_non_empty(self) -> None:
        """A detector that finds nothing is not evidence of nothing."""
        sites = anthropic_construction_sites()
        assert sites, (
            "Zero Anthropic construction sites found across hooks/, lib/ and "
            "scripts/. That is an instrument failure, not a clean repo -- the "
            "sanctioned helper alone must always be found."
        )

    def test_scan_roots_all_exist(self) -> None:
        """A vanished scan root would silently shrink the population to zero."""
        for root in SCAN_ROOTS:
            assert root.is_dir(), (
                f"Scan root {root} does not exist. The detector would silently "
                f"report fewer sites than are really present."
            )

    def test_positive_control_conflict_resolver_is_detected(self) -> None:
        """``conflict_resolver.py`` carries three constructions and must be seen.

        It is the densest out-of-sink file in the repo. If the detector stops
        reporting it, the instrument has regressed.
        """
        path = LIB_DIR / "conflict_resolver.py"
        assert path.exists(), "premise: the positive-control file still exists"
        assert "Anthropic(" in path.read_text(encoding="utf-8"), (
            "premise: conflict_resolver.py still constructs Anthropic. If it "
            "was migrated, this control no longer exercises detection -- pick "
            "another dense file and drop it from PINNED_OUT_OF_SINK."
        )
        sites = anthropic_construction_sites()
        assert "conflict_resolver.py" in sites, (
            "conflict_resolver.py was not detected. The AST detector has "
            "regressed and the ratchet is under-counting."
        )
        assert len(sites["conflict_resolver.py"]) == 3, (
            f"Expected 3 constructions in conflict_resolver.py, detected "
            f"{sites['conflict_resolver.py']}. Either the file changed or the "
            f"detector is collapsing multiple call sites."
        )

    def test_sanctioned_helper_is_itself_detected(self) -> None:
        """The sink must be found, or the exclusion below is meaningless.

        If ``genai_credentials.py`` stopped being detected, filtering it out of
        the out-of-sink population would be a no-op and the ratchet would be
        measuring something other than what it claims.
        """
        assert "genai_credentials.py" in anthropic_construction_sites(), (
            "The sanctioned helper is not detected as a construction site. "
            "Either it stopped constructing the SDK client (in which case the "
            "credential path is broken) or the detector is broken."
        )

    def test_negative_control_docstring_mention_is_not_detected(self) -> None:
        """``semantic_gate.py`` names Anthropic in prose and constructs nothing.

        Its docstring at line 357 reads "...so we do not re-import the /
        Anthropic SDK on every call." A filename-level ``grep -l Anthropic``
        flags this file. The AST detector must not. The premise is asserted so
        this control cannot pass vacuously if the docstring is reworded.
        """
        path = LIB_DIR / "semantic_gate.py"
        assert path.exists(), "premise: the negative-control file still exists"
        content = path.read_text(encoding="utf-8")
        assert "Anthropic" in content, (
            "premise: semantic_gate.py still mentions 'Anthropic' as text, so "
            "a text-matching instrument would still flag it. If the mention "
            "was removed, this control no longer exercises text-blindness -- "
            "pick another file that mentions it in prose."
        )
        assert "semantic_gate.py" not in anthropic_construction_sites(), (
            "semantic_gate.py is reported as an Anthropic construction site. "
            "It only mentions the name in a docstring. The detector has lost "
            "AST-awareness and is matching text again."
        )

    def test_negative_control_pattern_data_is_not_detected(self) -> None:
        """``secret_patterns.py`` carries "Anthropic API key" as string data.

        A second text-mention shape: a string literal in a data table rather
        than a docstring. Premise asserted for the same reason as above.
        """
        path = LIB_DIR / "secret_patterns.py"
        assert path.exists(), "premise: the negative-control file still exists"
        content = path.read_text(encoding="utf-8")
        assert "Anthropic API key" in content, (
            "premise: secret_patterns.py still carries the 'Anthropic API key' "
            "string literal, so a text-matching instrument would still flag "
            "it. If the label changed, pick another string-literal instance."
        )
        assert "secret_patterns.py" not in anthropic_construction_sites(), (
            "secret_patterns.py is reported as an Anthropic construction site. "
            "It only names Anthropic in regex pattern data."
        )

    def test_attribute_form_is_detected(self) -> None:
        """``anthropic.Anthropic(...)`` must be caught, not just the bare name.

        Three of the seven pinned files use the attribute form. A ``Name``-only
        detector would report 4 out-of-sink files and the ratchet would look
        green while under-counting by three.
        """
        source = "import anthropic\nc = anthropic.Anthropic(api_key='x')\n"
        tree = ast.parse(source)
        calls = [n for n in ast.walk(tree) if _is_anthropic_construction(n)]
        assert len(calls) == 1, "attribute-form construction was not recognised"

    def test_name_form_is_detected(self) -> None:
        """``Anthropic(...)`` after a ``from`` import must be caught."""
        source = "from anthropic import Anthropic\nc = Anthropic()\n"
        tree = ast.parse(source)
        calls = [n for n in ast.walk(tree) if _is_anthropic_construction(n)]
        assert len(calls) == 1, "name-form construction was not recognised"

    def test_unrelated_call_is_not_detected(self) -> None:
        """Negative control on the matcher itself, not on a repo file."""
        tree = ast.parse("x = SomethingElse()\ny = mod.Other()\nz = 'Anthropic('\n")
        assert not [n for n in ast.walk(tree) if _is_anthropic_construction(n)]


class TestGuardRefusesAndPermits:
    """The ratchet watched BOTH ways: refusing a new site, permitting the real one."""

    def test_guard_refuses_a_synthetic_new_construction_site(self, tmp_path: Path) -> None:
        """WATCHED REFUSING: a brand-new out-of-sink construction must be caught.

        Deliberately a DIFFERENT shape from the sites that prompted the guard:
        the synthetic file uses the attribute form inside a nested class method
        with a keyword argument, none of which the seven pinned files combine.
        A guard scoped to the instances that prompted it is not a guard.
        """
        offender = tmp_path / "brand_new_consumer.py"
        offender.write_text(
            "import anthropic\n"
            "\n"
            "class Consumer:\n"
            "    def build(self):\n"
            "        return anthropic.Anthropic(api_key='sk-nope')\n",
            encoding="utf-8",
        )
        detected = out_of_sink_sites(roots=[tmp_path])
        assert "brand_new_consumer.py" in detected, (
            "A newly added out-of-sink Anthropic construction was NOT detected. "
            "The ratchet cannot fail, so it is not enforcement."
        )
        # And the ratchet's own assertion must be the thing that trips.
        assert set(detected) - PINNED_OUT_OF_SINK == {"brand_new_consumer.py"}, (
            "The offender must surface as an unpinned site -- that difference "
            "is what makes test_live_state_matches_pinned_set fail."
        )

    def test_guard_permits_the_sanctioned_helper(self, tmp_path: Path) -> None:
        """WATCHED PERMITTING: the sink's own construction must NOT be flagged.

        A guard that refuses everything is equally useless. This proves the
        legitimate case passes through.
        """
        sanctioned = tmp_path / "genai_credentials.py"
        sanctioned.write_text(
            "from anthropic import Anthropic\n\n"
            "def get_anthropic_client():\n"
            "    return Anthropic(api_key='sk-ok')\n",
            encoding="utf-8",
        )
        assert "genai_credentials.py" in anthropic_construction_sites(roots=[tmp_path])
        assert out_of_sink_sites(roots=[tmp_path]) == {}, (
            "The sanctioned construction site was reported as out-of-sink. The "
            "guard now refuses the legitimate path."
        )

    def test_exclusions_are_honoured_and_cannot_silently_widen(self) -> None:
        """``archived/`` and ``.codex/`` mirrors must stay out of the population.

        Both directories really do contain Anthropic constructions, so the
        premise is live: if the exclusion broke, the count would jump and the
        ratchet would fail for a bogus reason.
        """
        archived = HOOKS_DIR / "archived" / "validate_readme_with_genai.py"
        assert archived.exists(), "premise: an archived construction site exists"
        assert "Anthropic(" in archived.read_text(encoding="utf-8"), (
            "premise: the archived file still constructs Anthropic, so the "
            "exclusion is doing real work."
        )
        assert "validate_readme_with_genai.py" not in anthropic_construction_sites(), (
            "An archived file leaked into the scan. The exclusion has widened "
            "or broken; the PROJECT.md archived-code rule is not being applied."
        )
        assert EXCLUDED_PATH_PARTS == {"archived", ".codex", ".worktrees"}, (
            f"EXCLUDED_PATH_PARTS changed to {sorted(EXCLUDED_PATH_PARTS)}. "
            f"Widening this set is how a real construction site disappears "
            f"from the ratchet without anyone noticing."
        )


class TestRatchetState:
    """The pinned set and its ceiling, pinned by exact membership."""

    def test_sanctioned_set_is_exactly_the_helper(self) -> None:
        """One canonical way. A second sanctioned site defeats the purpose."""
        assert SANCTIONED_CONSTRUCTION_SITES == {"genai_credentials.py"}, (
            f"SANCTIONED_CONSTRUCTION_SITES changed to "
            f"{sorted(SANCTIONED_CONSTRUCTION_SITES)}. There is exactly one "
            f"sanctioned construction site by design (Issue #1593): "
            f"lib/genai_credentials.get_anthropic_client. Adding a second "
            f"re-opens the credential-less-client defect this guard exists to "
            f"prevent."
        )

    def test_pinned_ceiling_equals_pinned_size(self) -> None:
        """Equality, not ``<=``: growth AND shrink must be a two-line diff.

        ``test_refusal_sink_ratchet.py:778`` uses ``<=``. Equality is stronger:
        under ``<=`` a shrink can happen without the ceiling following it down,
        leaving headroom for a future silent re-addition.
        """
        assert len(PINNED_OUT_OF_SINK) == PINNED_CEILING, (
            f"PINNED_OUT_OF_SINK has {len(PINNED_OUT_OF_SINK)} entries "
            f"{sorted(PINNED_OUT_OF_SINK)} but PINNED_CEILING is "
            f"{PINNED_CEILING}. These must move together. If you migrated a "
            f"file, lower the ceiling in the same commit. If you are trying to "
            f"ADD a file, stop: adding an entry is NOT an acceptable "
            f"resolution -- route the construction through "
            f"genai_credentials.get_anthropic_client() instead."
        )

    def test_pinned_set_is_exactly(self) -> None:
        """Exact membership. A swap must be as loud as an addition."""
        assert PINNED_OUT_OF_SINK == {
            "alignment_gate.py",
            "conflict_resolver.py",
            "genai_manifest_validator.py",
            "genai_validate.py",
            "improve_reviewer.py",
            "run_reviewer_benchmark.py",
        }, (
            f"PINNED_OUT_OF_SINK changed to {sorted(PINNED_OUT_OF_SINK)}. Only "
            f"REMOVALS are legitimate, and each must lower PINNED_CEILING by "
            f"the same amount in the same commit."
        )

    def test_live_state_matches_pinned_set(self) -> None:
        """The ratchet proper: reality must equal the pin, in both directions."""
        live = set(out_of_sink_sites())
        unpinned = live - PINNED_OUT_OF_SINK
        stale = PINNED_OUT_OF_SINK - live

        assert not unpinned, (
            f"NEW out-of-sink Anthropic construction(s): {sorted(unpinned)}. "
            f"Every direct Anthropic(...) call bypasses the credential "
            f"pre-flight check and re-creates Issue #1593: a truthy, "
            f"credential-less client whose failure is deferred to request time "
            f"and swallowed there. Call "
            f"genai_credentials.get_anthropic_client() instead. Adding an "
            f"entry to PINNED_OUT_OF_SINK is NOT an acceptable resolution."
        )
        assert not stale, (
            f"PINNED_OUT_OF_SINK names {sorted(stale)}, which no longer "
            f"construct Anthropic directly. Delete them from the set and lower "
            f"PINNED_CEILING by the same amount -- that deletion IS the "
            f"ratchet advancing."
        )

    def test_genai_utils_is_no_longer_a_construction_site(self) -> None:
        """The #1593 subject specifically. Regression pin.

        ``hooks/genai_utils.py:256`` used to call ``Anthropic()`` directly. It
        now delegates to the helper. If it ever constructs again, the guard in
        ``analyze()`` goes back to being unreachable.
        """
        assert "genai_utils.py" not in anthropic_construction_sites(), (
            "hooks/genai_utils.py constructs Anthropic directly again. That is "
            "the exact Issue #1593 defect: Anthropic() does not raise without "
            "credentials, so self.client becomes truthy and the "
            "'if not self.client' guard in analyze() can never fire."
        )
        assert "genai_utils.py" not in PINNED_OUT_OF_SINK, (
            "genai_utils.py must never be pinned -- it is the module #1593 "
            "migrated. Pinning it would grandfather the defect back in."
        )

    def test_genai_refactor_analyzer_is_no_longer_a_construction_site(self) -> None:
        """The Batch API paths, migrated by the ratchet's first shrink (7 -> 6).

        ``_submit_batch`` (:886) and ``_poll_batch`` (:919) used to call a bare
        ``Anthropic()`` inside a ``try/except Exception -> None``, so a missing
        credential surfaced as "Batch submission failed" rather than as a skip.
        """
        assert "genai_refactor_analyzer.py" not in anthropic_construction_sites(), (
            "genai_refactor_analyzer.py constructs Anthropic directly again. "
            "Its Batch API paths must call "
            "genai_credentials.get_anthropic_client() so a missing credential "
            "is a clean skip, not a swallowed request-time TypeError."
        )


@pytest.mark.parametrize("module_name", sorted(PINNED_OUT_OF_SINK))
def test_every_pinned_file_is_still_present_and_still_offending(
    module_name: str,
) -> None:
    """No pinned entry may become vacuous.

    If a pinned file is deleted or migrated, the entry stops protecting
    anything while still consuming ceiling headroom. This forces the removal.
    """
    live = out_of_sink_sites()
    assert module_name in live, (
        f"{module_name} is pinned in PINNED_OUT_OF_SINK but no longer "
        f"constructs Anthropic outside the sink. Remove it from the set and "
        f"lower PINNED_CEILING from {PINNED_CEILING} to {PINNED_CEILING - 1}."
    )
