"""Three guards over hook time budgets (Issue #1704).

One unmeasured constant -- ``5`` -- was declared independently in the 7 hook
registration surfaces, in ``genai_prompts.DEFAULT_TIMEOUT``, in
``intent_classifier_config.json`` and in ``semantic_gate.TIMEOUT_S``. It
silently discarded enforcement: 23 ``unified_pre_tool.py`` invocations
exceeded 5s in one week and each one dropped all ~51 checks, with no row in the
block log and an ordinary ``allow`` in the timing log.

G1  surface parity  -- every settings surface carries the canonical budget.
G2  nesting         -- a library timeout is strictly inside every host's budget.
G3  measured headroom -- a budget clears its own measured tail.

Every guard is exercised REFUSING and PERMITTING. G2 and G3 take their refusing
arm from the REAL PRE-FIX VALUES this issue found in the tree, not from a
synthetic mutation; G1's refusing arm is authored against a surface that was
not hand-edited during the fix, plus an injected entry shape that did not exist
when the guard was written.

A fourth guard -- a ratchet over raw ``*TIMEOUT*`` literals -- was designed and
DROPPED: 9 of the 13 module-level timeout constants are ``gh``/``git`` CLI
timeouts with no hook host, so the ratchet would have been mostly noise. Three
guards that refuse beat four where one is decorative.

Date: 2026-08-28
"""

import ast
import copy
import json
import sys
import time
from pathlib import Path

import pytest

# tests/regression/regression/<this file> -> regression -> regression -> tests -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "autonomous-dev"
LIB_DIR = PLUGIN_ROOT / "lib"
HOOKS_DIR = PLUGIN_ROOT / "hooks"
SCRIPTS_DIR = REPO_ROOT / "scripts"

for _p in (str(LIB_DIR), str(HOOKS_DIR), str(SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hook_budgets  # noqa: E402
import generate_hook_config as ghc  # noqa: E402

#: The value this issue exists to remove. Named so every arm derives from it.
THE_UNMEASURED_FIVE = 5


#: The three modules that bind a library timeout at import time behind a
#: ``try: ... except ImportError:`` guard. Discovered, not hardcoded, would be
#: better -- but the SHAPE is what is being verified, and the extractor below
#: refuses a file that does not have it, so a fourth site added without this
#: shape fails ``test_every_library_key_has_a_verified_call_site``.
_FALLBACK_MODULES = {
    "genai_prompts": "plugins/autonomous-dev/hooks/genai_prompts.py",
    "intent_classifier": "plugins/autonomous-dev/lib/intent_classifier.py",
    "semantic_gate": "plugins/autonomous-dev/lib/semantic_gate.py",
}


def extract_fallback_literals(
    source: str,
) -> "list[tuple[str, str, int, int | None]]":
    """Return ``(attr, key, call_literal, except_literal)`` per binding site.

    Reads the LITERALS OUT OF THE SOURCE. This is the whole point: at runtime
    the attribute holds ``library_timeout_or(key, literal)``, which DISCARDS
    the literal whenever the config is readable -- so any assertion comparing
    the runtime attribute to the canonical value compares X to X and passes for
    every literal, including the pre-#1704 5. Measured:

        library_timeout_or('genai_prompts.DEFAULT_TIMEOUT', 99) -> 15

    Args:
        source: Python source text.

    Returns:
        One tuple per ``try/except ImportError`` binding site.
        ``except_literal`` is None when the handler assigns no bare int.
    """
    found: "list[tuple[str, str, int, int | None]]" = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Try):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
                continue
            target = stmt.targets[0]
            if not isinstance(target, ast.Name):
                continue
            call = stmt.value
            if not isinstance(call, ast.Call):
                continue
            func = call.func
            func_name = (
                func.id
                if isinstance(func, ast.Name)
                else func.attr if isinstance(func, ast.Attribute) else ""
            )
            if "library_timeout_or" not in func_name:
                continue
            if len(call.args) != 2:
                continue
            key_node, default_node = call.args
            if not (
                isinstance(key_node, ast.Constant)
                and isinstance(key_node.value, str)
                and isinstance(default_node, ast.Constant)
                and isinstance(default_node.value, int)
            ):
                continue

            except_literal: "int | None" = None
            for handler in node.handlers:
                exc = handler.type
                if not (isinstance(exc, ast.Name) and exc.id == "ImportError"):
                    continue
                for hstmt in handler.body:
                    if (
                        isinstance(hstmt, ast.Assign)
                        and len(hstmt.targets) == 1
                        and isinstance(hstmt.targets[0], ast.Name)
                        and hstmt.targets[0].id == target.id
                        and isinstance(hstmt.value, ast.Constant)
                        and isinstance(hstmt.value.value, int)
                    ):
                        except_literal = hstmt.value.value
            found.append(
                (target.id, key_node.value, default_node.value, except_literal)
            )
    return found


def check_fallback_literals(source: str, canonical: "dict[str, int]") -> "list[str]":
    """Return one message per fail-safe literal that disagrees with canonical.

    Args:
        source: Python source text of a binding module.
        canonical: ``{library_key: timeout_seconds}`` from the budget config.

    Returns:
        Violation messages; empty when every literal matches.
    """
    violations: "list[str]" = []
    for attr, key, call_literal, except_literal in extract_fallback_literals(source):
        expected = canonical.get(key)
        if expected is None:
            violations.append(f"{attr}: key {key!r} is not declared in the config")
            continue
        if call_literal != expected:
            violations.append(
                f"{attr}: library_timeout_or fail-safe is {call_literal}, "
                f"canonical is {expected}"
            )
        if except_literal is None:
            violations.append(
                f"{attr}: the `except ImportError` branch assigns no int literal, "
                f"so its value cannot be checked"
            )
        elif except_literal != expected:
            violations.append(
                f"{attr}: the `except ImportError` literal is {except_literal}, "
                f"canonical is {expected}"
            )
    return violations


def _get_timeout_defaults(source: str) -> "list[int]":
    """Return every literal default passed to ``.get("timeout", N)`` in ``source``.

    Args:
        source: Python source text.

    Returns:
        The literal integer defaults found, in AST order.
    """
    found: "list[int]" = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "get"):
            continue
        if len(node.args) != 2:
            continue
        key, default = node.args
        if not (isinstance(key, ast.Constant) and key.value == "timeout"):
            continue
        if isinstance(default, ast.Constant) and isinstance(default.value, int):
            found.append(default.value)
    return found


@pytest.fixture()
def canonical_config() -> dict:
    """The real, on-disk budget config."""
    hook_budgets.clear_cache()
    return hook_budgets.load_budget_config()


# ---------------------------------------------------------------------------
# Instrument controls -- verify the probe before trusting one cell of output
# ---------------------------------------------------------------------------


class TestInstrumentPremises:
    """A probe that cannot fail cannot inform."""

    def test_surface_discovery_is_not_empty(self) -> None:
        """POSITIVE CONTROL: a sweep returning zero is a broken sweep."""
        surfaces = ghc.discover_settings_surfaces(PLUGIN_ROOT)
        assert surfaces, (
            "discover_settings_surfaces found ZERO registration surfaces. "
            "Expected at least config/global_settings_template.json. The "
            "sweep is broken, not the repo."
        )

    def test_surface_discovery_finds_the_file_no_glob_sees(self) -> None:
        """``settings*.json`` misses this file; it carries the most bindings."""
        names = {p.name for p in ghc.discover_settings_surfaces(PLUGIN_ROOT)}
        assert "global_settings_template.json" in names, (
            "global_settings_template.json is not discovered. It matches no "
            "settings*.json glob, which is exactly why discovery is by content."
        )

    def test_surface_discovery_discriminates(self) -> None:
        """NEGATIVE CONTROL: it must not accept everything with a hooks key.

        ``plugin.json`` carries ``"hooks": {"active": N, "archived": M}`` -- a
        component COUNT. ``templates/settings.local.json`` carries ``{}``.
        Neither is a registration surface. A sweep that counts them reports 9
        surfaces where there are 7.
        """
        paths = {p for p in ghc.discover_settings_surfaces(PLUGIN_ROOT)}
        assert PLUGIN_ROOT / "plugin.json" not in paths, (
            "plugin.json was counted as a settings surface, but its 'hooks' "
            "key is a component count, not registrations."
        )
        assert PLUGIN_ROOT / "templates" / "settings.local.json" not in paths, (
            "settings.local.json has an EMPTY hooks object and is not a "
            "registration surface."
        )
        # And the discriminator itself, driven over both shapes directly.
        assert not ghc._is_registration_block({"active": 27, "archived": 61})
        assert not ghc._is_registration_block({})
        assert ghc._is_registration_block(
            {"PreToolUse": [{"matcher": "*", "hooks": [{"command": "x.py"}]}]}
        )

    def test_measurements_are_present(self, canonical_config: dict) -> None:
        """POSITIVE CONTROL for G3: it must examine something."""
        assert hook_budgets.measured_hook_count(canonical_config) > 0, (
            "Zero hooks carry a measurement, so check_measured_headroom "
            "examines nothing and its empty result means nothing."
        )

    def test_unmeasured_hooks_are_null_not_zero(self, canonical_config: dict) -> None:
        """An absence of measurement must not read as a measurement of zero."""
        unmeasured = [
            name
            for name, entry in canonical_config["hooks"].items()
            if entry.get("measured_p99_ms") is None
        ]
        assert unmeasured, (
            "Expected at least the bash hooks to be UNMEASURED -- they do not "
            "use HookTimer and emit no timing rows. If every hook now has a "
            "measurement, re-verify rather than assume."
        )
        for name in unmeasured:
            entry = canonical_config["hooks"][name]
            assert entry["measured_p99_ms"] is None
            assert entry.get("measured_n") == 0, (
                f"{name} is unmeasured but claims measured_n="
                f"{entry.get('measured_n')}"
            )


# ---------------------------------------------------------------------------
# G1 -- surface parity
# ---------------------------------------------------------------------------


class TestG1SurfaceParity:
    """The budget is set in ONE place and takes effect on every surface."""

    def test_permitting_no_timeout_drift_in_the_live_tree(self) -> None:
        """PERMITTING ARM: the real tree agrees with the canonical source."""
        surfaces = ghc.discover_settings_surfaces(PLUGIN_ROOT)
        drift = ghc.collect_timeout_drift(surfaces)
        assert not drift, "Timeout drift across settings surfaces:\n" + "\n".join(
            f"  {p.relative_to(REPO_ROOT)}: {ev}/{hk} has {cur}, canonical {can}"
            for p, ev, hk, cur, can in drift
        )

    def test_refusing_a_mutated_surface_is_caught(self, tmp_path: Path) -> None:
        """REFUSING ARM, shape 1: a surface reverted to the unmeasured 5.

        Deliberately mutates ``settings.granular-bash.json`` -- a template NOT
        hand-edited while writing this guard -- so the guard is not scoped to
        the files its author happened to touch.
        """
        source = PLUGIN_ROOT / "templates" / "settings.granular-bash.json"
        mutant = tmp_path / source.name
        data = json.loads(source.read_text())
        target = data["hooks"]["PreToolUse"][0]["hooks"][0]
        assert "unified_pre_tool" in target["command"], (
            "Anchor moved: expected unified_pre_tool as the first PreToolUse "
            "entry. Re-derive the anchor rather than mutating nothing."
        )
        assert target["timeout"] != THE_UNMEASURED_FIVE, (
            "Pre-mutation value is already 5; the mutation would be a no-op "
            "and the arm would be vacuous."
        )
        target["timeout"] = THE_UNMEASURED_FIVE
        mutant.write_text(json.dumps(data, indent=2))

        drift = ghc.collect_timeout_drift([mutant])
        assert drift, (
            "The guard did NOT refuse a surface reverted to the unmeasured 5. "
            "It cannot fail, so it proves nothing."
        )
        assert any(hk == "unified_pre_tool" for _, _, hk, _, _ in drift)

    def test_refusing_an_injected_entry_is_caught(self, tmp_path: Path) -> None:
        """REFUSING ARM, shape 2: a NEW registration with a stray timeout.

        This shape did not exist in the tree when the guard was written -- a
        newly added hook entry, on an event the file did not previously carry.
        The guard must reach it because it walks entries, not a fixed list.
        """
        mutant = tmp_path / "injected.json"
        mutant.write_text(
            json.dumps(
                {
                    "hooks": {
                        "SubagentStop": [
                            {
                                "matcher": "*",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "python3 ~/.claude/hooks/unified_pre_tool.py",
                                        "timeout": THE_UNMEASURED_FIVE,
                                    }
                                ],
                            }
                        ]
                    }
                },
                indent=2,
            )
        )
        drift = ghc.collect_timeout_drift([mutant])
        assert drift, (
            "A newly injected registration carrying a stray 5 was NOT refused. "
            "The guard is enumerating known entries instead of walking them."
        )

    def test_no_sidecar_declares_a_timeout(self) -> None:
        """A sidecar timeout would be a second declaration of a canonical number."""
        offenders = []
        for path in sorted(HOOKS_DIR.glob("*.hook.json")):
            data = json.loads(path.read_text())
            for reg in data.get("registrations", []):
                if "timeout" in reg:
                    offenders.append(f"{path.name}:{reg.get('event')}={reg['timeout']}")
        assert not offenders, (
            "Sidecars declaring a timeout re-introduce the sprawl:\n  "
            + "\n  ".join(offenders)
            + "\nDeclare it in config/hook_time_budgets.json instead."
        )

    def test_generator_default_no_longer_hardcodes_five(self) -> None:
        """The ORIGIN of the sprawl: ``reg.get("timeout", 5)``.

        Asked of the AST, not of the text. A text grep answers a different
        question and goes red on the module docstring that EXPLAINS the removed
        default -- punishing the documentation of the fix. ``_get_timeout_defaults``
        is verified against a known-positive fixture below so a zero here is
        evidence of zero.
        """
        found = _get_timeout_defaults((SCRIPTS_DIR / "generate_hook_config.py").read_text())
        assert not found, (
            f"generate_hook_config.py still calls .get('timeout', N) with a "
            f"literal default {found}; that is the constant which propagated "
            f"to every settings surface. Use resolve_timeout()."
        )

    def test_the_hardcoded_default_detector_can_actually_fire(self) -> None:
        """POSITIVE CONTROL: a probe that returns zero must be able to return one."""
        assert _get_timeout_defaults('x = reg.get("timeout", 5)') == [5]
        assert _get_timeout_defaults('x = reg.get("timeout")') == []
        assert _get_timeout_defaults('x = reg.get("matcher", 5)') == []


# ---------------------------------------------------------------------------
# G2 -- the nesting constraint
# ---------------------------------------------------------------------------


class TestG2Nesting:
    """A library timeout must be STRICTLY inside its host hook's budget."""

    def test_permitting_the_live_tree_nests_correctly(
        self, canonical_config: dict
    ) -> None:
        """PERMITTING ARM: every declared pair nests."""
        violations = hook_budgets.check_nesting(canonical_config)
        assert not violations, "Nesting violations:\n  " + "\n  ".join(violations)

    def test_permitting_arm_is_not_vacuous(self, canonical_config: dict) -> None:
        """The permitting arm must have had pairs to permit."""
        assert canonical_config["libraries"], "No libraries declared to check."
        for key, entry in canonical_config["libraries"].items():
            assert entry.get("host_hooks"), f"{key} declares no host_hooks"

    def test_refusing_the_real_pre_fix_values(self, canonical_config: dict) -> None:
        """REFUSING ARM: the values actually in the tree before this change.

        Not a synthetic mutation -- ``intent_classifier_config.json`` carried
        ``timeout_seconds: 5`` under a host registered at ``"timeout": 5``.
        ``5 >= 5``: the runtime discards the hook at the same instant the
        library gives up, so the library can never report its own timeout.
        """
        pre_fix = copy.deepcopy(canonical_config)
        pre_fix["hooks"]["unified_prompt_validator"]["budget_seconds"] = (
            THE_UNMEASURED_FIVE
        )
        pre_fix["libraries"]["intent_classifier.timeout_seconds"][
            "timeout_seconds"
        ] = THE_UNMEASURED_FIVE

        violations = hook_budgets.check_nesting(pre_fix)
        assert any("intent_classifier" in v for v in violations), (
            "The guard did NOT refuse equality between a library timeout and "
            "its host budget. Equality is the violation the constraint exists "
            f"for; got: {violations}"
        )

    def test_semantic_gate_is_permitted_within_the_refusing_config(
        self, canonical_config: dict
    ) -> None:
        """PERMITTING ARM inside the refusing case -- discrimination, not blanket deny.

        ``semantic_gate.TIMEOUT_S = 3`` already satisfied the constraint against
        the old 5s host budget. It predates the guard and was not authored for
        it, so it is the honest permitting shape.
        """
        pre_fix = copy.deepcopy(canonical_config)
        pre_fix["hooks"]["unified_pre_tool"]["budget_seconds"] = THE_UNMEASURED_FIVE
        pre_fix["hooks"]["unified_prompt_validator"]["budget_seconds"] = (
            THE_UNMEASURED_FIVE
        )
        pre_fix["libraries"]["intent_classifier.timeout_seconds"][
            "timeout_seconds"
        ] = THE_UNMEASURED_FIVE

        violations = hook_budgets.check_nesting(pre_fix)
        assert violations, "Expected the pre-fix config to produce refusals."
        assert not any("semantic_gate" in v for v in violations), (
            "semantic_gate (3s under a 5s host) was refused. The guard denies "
            f"blanket rather than discriminating; got: {violations}"
        )

    def test_refusing_an_undeclared_host(self, canonical_config: dict) -> None:
        """A nesting claim against a hook with no budget is unverifiable."""
        broken = copy.deepcopy(canonical_config)
        broken["libraries"]["semantic_gate.TIMEOUT_S"]["host_hooks"] = [
            "a_hook_that_does_not_exist"
        ]
        violations = hook_budgets.check_nesting(broken)
        assert any("a_hook_that_does_not_exist" in v for v in violations)

    def test_library_source_constants_match_the_canonical_source(self) -> None:
        """The config must not be a lie: the live constants must agree.

        Cross-validation, not a third copy: both sides are read dynamically.
        """
        import genai_prompts
        import intent_classifier
        import semantic_gate

        pairs = [
            ("genai_prompts.DEFAULT_TIMEOUT", genai_prompts.DEFAULT_TIMEOUT),
            (
                "intent_classifier.timeout_seconds",
                intent_classifier.DEFAULT_TIMEOUT_SECONDS,
            ),
            ("semantic_gate.TIMEOUT_S", semantic_gate.TIMEOUT_S),
        ]
        for key, live_value in pairs:
            canonical = hook_budgets.get_library_timeout(key)
            assert live_value == canonical, (
                f"{key}: the live constant is {live_value} but "
                f"hook_time_budgets.json declares {canonical}. The canonical "
                f"file is describing a system that does not exist."
            )

    def test_intent_classifier_config_mirrors_the_canonical_source(self) -> None:
        """The JSON config is a mirror; drift between it and canonical is a defect."""
        cfg = json.loads(
            (PLUGIN_ROOT / "config" / "intent_classifier_config.json").read_text()
        )
        canonical = hook_budgets.get_library_timeout(
            "intent_classifier.timeout_seconds"
        )
        assert cfg["timeout_seconds"] == canonical, (
            f"intent_classifier_config.json declares "
            f"{cfg['timeout_seconds']}, canonical is {canonical}."
        )


# ---------------------------------------------------------------------------
# G3 -- measured headroom
# ---------------------------------------------------------------------------


class TestG3MeasuredHeadroom:
    """A budget below its own measured tail discards enforcement by construction."""

    def test_permitting_the_live_budgets_have_headroom(
        self, canonical_config: dict
    ) -> None:
        """PERMITTING ARM: every measured hook clears its own tail."""
        violations = hook_budgets.check_measured_headroom(canonical_config)
        assert not violations, "Headroom violations:\n  " + "\n  ".join(violations)

    def test_refusing_the_real_pre_fix_budget(self, canonical_config: dict) -> None:
        """REFUSING ARM: the 5s that ``unified_pre_tool`` actually carried.

        Measured p99 2,223.4ms and max 13,139.7ms over 34,973 invocations.
        ``max(p99 x 3, max) = 13.14s`` against a 5s budget -- which is exactly
        why 23 invocations discarded all ~51 checks in one week.
        """
        pre_fix = copy.deepcopy(canonical_config)
        pre_fix["hooks"]["unified_pre_tool"]["budget_seconds"] = THE_UNMEASURED_FIVE

        violations = hook_budgets.check_measured_headroom(pre_fix)
        assert any("unified_pre_tool" in v for v in violations), (
            "The guard did NOT refuse a 5s budget on a hook with a measured "
            f"13,139.7ms tail. Got: {violations}"
        )

    def test_permitting_arm_survives_the_refusing_mutation(
        self, canonical_config: dict
    ) -> None:
        """Discrimination: the other measured hooks stay permitted."""
        pre_fix = copy.deepcopy(canonical_config)
        pre_fix["hooks"]["unified_pre_tool"]["budget_seconds"] = THE_UNMEASURED_FIVE
        violations = hook_budgets.check_measured_headroom(pre_fix)
        assert len(violations) == 1, (
            f"Expected exactly one refusal (unified_pre_tool); the guard is "
            f"refusing broadly: {violations}"
        )

    def test_ceiling_is_read_from_the_schema_not_redeclared(self) -> None:
        """60 must have ONE home: the file that actually refuses a larger value."""
        schema = json.loads(
            (PLUGIN_ROOT / "config" / "hook-metadata.schema.json").read_text()
        )
        declared = schema["properties"]["registrations"]["items"]["properties"][
            "timeout"
        ]["maximum"]
        assert hook_budgets.schema_max_seconds() == declared
        assert hook_budgets.FALLBACK_SCHEMA_MAX_SECONDS == declared, (
            "The fail-safe fallback drifted from the schema; a missing schema "
            "would silently widen the ceiling."
        )

    def test_no_budget_exceeds_the_ceiling_or_removes_the_bound(
        self, canonical_config: dict
    ) -> None:
        """Raising a ceiling must not remove it."""
        assert not hook_budgets.check_ceiling(canonical_config)
        for name, entry in canonical_config["hooks"].items():
            assert entry["budget_seconds"] >= 1, f"{name} is unbounded"

    def test_refusing_a_budget_above_the_ceiling(self, canonical_config: dict) -> None:
        """REFUSING ARM for the ceiling."""
        over = copy.deepcopy(canonical_config)
        over["hooks"]["unified_pre_tool"]["budget_seconds"] = (
            hook_budgets.schema_max_seconds() + 1
        )
        assert any("unified_pre_tool" in v for v in hook_budgets.check_ceiling(over))

    def test_refusing_a_budget_of_zero(self, canonical_config: dict) -> None:
        """REFUSING ARM: a zero budget removes the bound entirely."""
        zeroed = copy.deepcopy(canonical_config)
        zeroed["hooks"]["plan_gate"]["budget_seconds"] = 0
        assert any("plan_gate" in v for v in hook_budgets.check_ceiling(zeroed))


# ---------------------------------------------------------------------------
# The countable skip -- watched being written, and watched NOT being written
# ---------------------------------------------------------------------------


class TestRemediationBlocking1SyncRefusesUndeclared:
    """`--sync-timeouts` must not rewrite a declared bound to an undeclared default.

    The pre-remediation write path called ``resolve_timeout`` for every entry.
    A missing or mistyped hook key resolved to the silent default and rewrote
    that hook to 5 across all 7 surfaces, exiting 0 -- ``reg.get("timeout", 5)``,
    the line this issue names as the origin of the sprawl, reintroduced in the
    WRITE path inside the fix for it.
    """

    @staticmethod
    def _surface_with_hook(tmp_path: Path, hook_name: str, timeout: int) -> Path:
        """Build a scratch copy of a REAL surface renamed to ``hook_name``."""
        source = PLUGIN_ROOT / "templates" / "settings.granular-bash.json"
        data = json.loads(source.read_text())
        entry = data["hooks"]["PreToolUse"][0]["hooks"][0]
        assert "unified_pre_tool" in entry["command"], (
            "Anchor moved: expected unified_pre_tool as the first PreToolUse "
            "entry. Re-derive the anchor rather than mutating nothing."
        )
        entry["command"] = entry["command"].replace("unified_pre_tool", hook_name)
        entry["timeout"] = timeout
        dst = tmp_path / "surface.json"
        dst.write_text(json.dumps(data, indent=2))
        return dst

    def test_refusing_a_typod_hook_key_raises_and_writes_nothing(
        self, tmp_path: Path
    ) -> None:
        """REFUSING ARM: the real CLI function, on a scratch copy of a real surface."""
        surface = self._surface_with_hook(tmp_path, "unified_pre_tool_TYPO", 20)
        before = surface.read_text()

        with pytest.raises(RuntimeError) as exc:
            ghc.sync_timeouts([surface])

        assert "undeclared default" in str(exc.value)
        assert surface.read_text() == before, (
            "sync_timeouts raised but had already written. The refusal must "
            "happen BEFORE any surface is touched."
        )
        still = json.loads(surface.read_text())["hooks"]["PreToolUse"][0]["hooks"][0]
        assert still["timeout"] == 20, (
            f"The declared bound was overwritten to {still['timeout']}."
        )

    def test_permitting_the_correct_key_writes_normally(self, tmp_path: Path) -> None:
        """PERMITTING ARM: same shape, correct name -> no raise."""
        surface = self._surface_with_hook(tmp_path, "unified_pre_tool", 999)
        updated = ghc.sync_timeouts([surface])
        assert updated == 1
        written = json.loads(surface.read_text())["hooks"]["PreToolUse"][0]["hooks"][0]
        assert written["timeout"] == hook_budgets.get_hook_budget("unified_pre_tool")

    def test_the_silent_default_is_still_reachable_via_get_hook_budget(self) -> None:
        """The defaulting behaviour still exists -- the WRITE path just refuses it.

        NEGATIVE CONTROL: without this, the refusal above could be passing
        because ``get_hook_budget`` started raising, which would be a different
        (and worse) change.
        """
        assert hook_budgets.get_hook_budget("unified_pre_tool_TYPO") == (
            THE_UNMEASURED_FIVE
        )
        assert hook_budgets.has_hook_budget("unified_pre_tool_TYPO") is False

    def test_sync_validates_the_config_before_touching_any_surface(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A config that violates nesting must not be propagated to 7 files."""
        surface = self._surface_with_hook(tmp_path, "unified_pre_tool", 999)
        before = surface.read_text()

        broken = copy.deepcopy(hook_budgets.load_budget_config())
        broken["libraries"]["semantic_gate.TIMEOUT_S"]["timeout_seconds"] = 999

        with pytest.raises(RuntimeError) as exc:
            ghc.sync_timeouts([surface], broken)

        assert "does not validate" in str(exc.value)
        assert surface.read_text() == before


class TestRemediationBlocking3InstalledSkew:
    """The declared budget is not the enforced one. Detect the gap."""

    @staticmethod
    def _installed(tmp_path: Path, hook_name: str, timeout) -> Path:
        entry = {"type": "command", "command": f"python3 ~/.claude/hooks/{hook_name}.py"}
        if timeout is not None:
            entry["timeout"] = timeout
        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps({"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [entry]}]}})
        )
        return path

    def test_refusing_skew_between_declared_and_enforced(
        self, tmp_path: Path, canonical_config: dict
    ) -> None:
        """REFUSING ARM: the exact state a bare `deploy-all.sh` produces.

        Libraries land at 20s while the installed settings stay at 5s. A 6s run
        is discarded by the runtime and records NO overrun row, because
        ``maybe_record_budget_overrun`` compares against 20.
        """
        installed = self._installed(tmp_path, "unified_pre_tool", THE_UNMEASURED_FIVE)
        skew = hook_budgets.check_installed_settings_skew([installed], canonical_config)
        assert any("unified_pre_tool" in s for s in skew), (
            f"Skew between a 20s declaration and a 5s enforced bound was NOT "
            f"detected. Got: {skew}"
        )
        assert any("deploy-all.sh --global-settings" in s for s in skew), (
            "The message must name the remedy; a skew report with no next "
            "action trains dismissal."
        )

    def test_permitting_an_installed_copy_that_agrees(
        self, tmp_path: Path, canonical_config: dict
    ) -> None:
        """PERMITTING ARM: a correctly deployed copy produces no skew."""
        declared = hook_budgets.get_hook_budget("unified_pre_tool", canonical_config)
        installed = self._installed(tmp_path, "unified_pre_tool", declared)
        assert hook_budgets.check_installed_settings_skew(
            [installed], canonical_config
        ) == []

    def test_refusing_an_installed_hook_with_no_bound(
        self, tmp_path: Path, canonical_config: dict
    ) -> None:
        """A DIFFERENT shape: registered and executing with no timeout at all."""
        installed = self._installed(tmp_path, "unified_pre_tool", None)
        skew = hook_budgets.check_installed_settings_skew([installed], canonical_config)
        assert any("NO timeout" in s for s in skew)

    def test_refusing_an_installed_hook_with_no_budget_entry(
        self, tmp_path: Path, canonical_config: dict
    ) -> None:
        """A THIRD shape: executing under a bound that no budget governs."""
        installed = self._installed(tmp_path, "some_unbudgeted_hook", 5)
        skew = hook_budgets.check_installed_settings_skew([installed], canonical_config)
        assert any("governed by nothing" in s for s in skew)

    def test_the_reader_reads_installed_paths_not_repo_templates(self) -> None:
        """The whole point: it must not be validating the declaration."""
        for path in hook_budgets.installed_settings_paths():
            assert "plugins/autonomous-dev/templates" not in str(path)
            assert path.name.startswith("settings")

    def test_overrun_row_carries_its_budget_provenance(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Under skew the threshold is not the enforced one -- say where it came from."""
        monkeypatch.chdir(tmp_path)
        assert hook_budgets.record_budget_overrun(
            hook_name="unified_pre_tool.py", duration_ms=21000.0, budget_seconds=20
        )
        sink = tmp_path / ".claude" / "logs" / "hook-blocks.jsonl"
        row = json.loads(sink.read_text().splitlines()[0])
        assert row["metadata"]["budget_source"] == str(
            hook_budgets.BUDGET_CONFIG_PATH
        )


class TestRemediationW4NoPassOverZero:
    """A checker with nothing to check has not passed."""

    def test_check_nesting_on_a_missing_config_reports_a_violation(
        self, tmp_path: Path
    ) -> None:
        empty = hook_budgets.load_budget_config(tmp_path / "absent.json")
        assert hook_budgets.budgeted_hook_count(empty) == 0
        violations = hook_budgets.check_nesting(empty)
        assert violations, "check_nesting returned [] over ZERO hooks."
        assert "ZERO hooks" in violations[0]

    def test_check_ceiling_on_a_missing_config_reports_a_violation(
        self, tmp_path: Path
    ) -> None:
        empty = hook_budgets.load_budget_config(tmp_path / "absent.json")
        violations = hook_budgets.check_ceiling(empty)
        assert violations, "check_ceiling returned [] over ZERO hooks."
        assert "ZERO hooks" in violations[0]

    def test_check_nesting_reports_when_hooks_exist_but_libraries_do_not(
        self, tmp_path: Path
    ) -> None:
        """A DIFFERENT vacuity shape: hooks present, nothing to nest."""
        path = tmp_path / "b.json"
        path.write_text(
            json.dumps(
                {
                    "default": {"budget_seconds": 5, "warning_pct": 0.8},
                    "hooks": {"h": {"budget_seconds": 5}},
                    "libraries": {},
                }
            )
        )
        violations = hook_budgets.check_nesting(
            hook_budgets.load_budget_config(path)
        )
        assert violations and "ZERO libraries" in violations[0]

    def test_permitting_the_real_config_still_passes(
        self, canonical_config: dict
    ) -> None:
        """PERMITTING ARM: the anti-vacuity guard must not deny everything."""
        assert hook_budgets.budgeted_hook_count(canonical_config) > 0
        assert hook_budgets.check_nesting(canonical_config) == []
        assert hook_budgets.check_ceiling(canonical_config) == []


class TestRemediationW5HostHooksAreDerived:
    """A hand-written host list is a comment; a derived one is a guard."""

    def test_the_derivation_instrument_has_a_positive_control(self) -> None:
        """POSITIVE CONTROL: auto_fix_docs IS registered and DOES reach genai_prompts.

        This control caught a real defect in the instrument itself: the name
        extractor used ``match.group(0)``, which keeps the trailing delimiter
        the pattern consumes, so every discovered name was ``foo.py"`` and
        matched no budget. The checker returned [] for the wrong reason.
        """
        registered = hook_budgets.registered_hook_names()
        assert "auto_fix_docs" in registered, (
            "auto_fix_docs is registered in .claude-plugin/default-settings.json "
            "(PreCommit). If discovery cannot see it, the instrument is broken."
        )
        assert not any("." in name for name in registered), (
            f"Discovered names still carry extensions/delimiters: "
            f"{sorted(n for n in registered if '.' in n)}"
        )
        assert hook_budgets.reaches_module("auto_fix_docs", "genai_prompts")

    def test_the_derivation_instrument_has_a_negative_control(self) -> None:
        """NEGATIVE CONTROL: it must not claim every hook reaches everything."""
        assert not hook_budgets.reaches_module("plan_gate", "genai_prompts")
        assert not hook_budgets.reaches_module("nonexistent_module", "genai_prompts")

    def test_security_scan_reaches_genai_but_is_not_registered(self) -> None:
        """Discrimination: reaching the module is not enough to be a host."""
        assert hook_budgets.reaches_module("security_scan", "genai_prompts")
        assert "security_scan" not in hook_budgets.registered_hook_names()

    def test_permitting_the_declared_hosts_cover_the_derived_ones(self) -> None:
        """PERMITTING ARM: the live config declares every real host."""
        violations = hook_budgets.check_declared_hosts_match_derived()
        assert not violations, "Undeclared hosts:\n  " + "\n  ".join(violations)

    def test_refusing_a_host_list_that_omits_auto_fix_docs(
        self, canonical_config: dict
    ) -> None:
        """REFUSING ARM: the exact omission that shipped in the first pass."""
        broken = copy.deepcopy(canonical_config)
        hosts = broken["libraries"]["genai_prompts.DEFAULT_TIMEOUT"]["host_hooks"]
        broken["libraries"]["genai_prompts.DEFAULT_TIMEOUT"]["host_hooks"] = [
            h for h in hosts if h != "auto_fix_docs"
        ]
        violations = hook_budgets.check_declared_hosts_match_derived(broken)
        assert any("auto_fix_docs" in v for v in violations), (
            f"Omitting a real host was NOT refused. Got: {violations}"
        )

    def test_auto_fix_docs_now_nests_correctly(self, canonical_config: dict) -> None:
        """The omission was load-bearing: a 15s library under an unbounded host."""
        host_budget = hook_budgets.get_hook_budget("auto_fix_docs", canonical_config)
        lib_timeout = hook_budgets.get_library_timeout(
            "genai_prompts.DEFAULT_TIMEOUT", canonical_config
        )
        assert lib_timeout < host_budget


class TestRemediationW6UnboundButBudgeted:
    """A hook WITH a budget carrying NO bound on a surface is drift, not a warning."""

    @staticmethod
    def _surface(tmp_path: Path, hook_name: str, timeout) -> Path:
        entry = {"type": "command", "command": f"python3 ~/.claude/hooks/{hook_name}.py"}
        if timeout is not None:
            entry["timeout"] = timeout
        path = tmp_path / f"{hook_name}_surface.json"
        path.write_text(
            json.dumps({"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [entry]}]}})
        )
        return path

    def test_refusing_a_budgeted_hook_with_no_bound(self, tmp_path: Path) -> None:
        """REFUSING ARM: a shape neither original refusing arm covered.

        Both earlier G1 arms mutated an entry that already HAD a timeout, so
        the missing-bound shape passed as a stdout warning.
        """
        surface = self._surface(tmp_path, "unified_pre_tool", None)
        drift = ghc.collect_timeout_drift([surface])
        assert any(hk == "unified_pre_tool" and cur is None for _, _, hk, cur, _ in drift), (
            f"A budgeted hook with NO bound was not treated as drift: {drift}"
        )
        assert ghc.collect_unbounded_entries([surface]) == [], (
            "It was ALSO reported as a mere warning; the two classes must be "
            "disjoint or the warning re-hides the drift."
        )

    def test_permitting_an_unbudgeted_hook_with_no_bound(self, tmp_path: Path) -> None:
        """PERMITTING ARM: neither declared nor bound stays a warning."""
        surface = self._surface(tmp_path, "totally_unbudgeted_hook", None)
        assert ghc.collect_timeout_drift([surface]) == []
        assert len(ghc.collect_unbounded_entries([surface])) == 1

    def test_live_tree_has_no_budgeted_but_unbound_entries(self) -> None:
        """The live tree was fixed, not exempted."""
        surfaces = ghc.discover_settings_surfaces(PLUGIN_ROOT)
        assert ghc.collect_timeout_drift(surfaces) == []
        assert ghc.collect_unbudgeted_entries(surfaces) == []


class TestRemediationW7OverrunCheckIsCheap:
    """3.28ms median import+read on every hook exit, to detect 23 events a week."""

    def test_min_budget_ns_matches_the_canonical_minimum(self) -> None:
        """Locks the literal to the config it cannot afford to import."""
        import hook_timing

        assert hook_timing.MIN_BUDGET_SECONDS == (
            hook_budgets.min_declared_budget_seconds()
        ), (
            "MIN_BUDGET_SECONDS drifted from the smallest declared budget. A "
            "budget below it would have overrun detection silently disabled."
        )
        assert hook_timing.MIN_BUDGET_NS == hook_timing.MIN_BUDGET_SECONDS * 10**9

    def test_short_invocations_short_circuit_before_importing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """REFUSING ARM for the cost: the module must not even be imported.

        Poisons ``hook_budgets`` in ``sys.modules`` so any attempt to use it
        raises. A sub-floor duration must return without touching it.
        """
        import hook_timing

        class _Poisoned:
            def __getattr__(self, name):
                raise AssertionError(
                    f"hook_budgets.{name} was accessed for a sub-floor "
                    f"duration; the W7 fast path did not short-circuit."
                )

        monkeypatch.setitem(sys.modules, "hook_budgets", _Poisoned())
        assert (
            hook_timing.maybe_record_budget_overrun("unified_pre_tool.py", 6_400_000)
            is False
        )

    def test_long_invocations_still_reach_the_check(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PERMITTING ARM: the fast path must not swallow real overruns."""
        import hook_timing

        monkeypatch.chdir(tmp_path)
        hook_budgets.clear_cache()
        over_ns = (hook_budgets.get_hook_budget("plan_gate") + 1) * 1_000_000_000
        assert hook_timing.maybe_record_budget_overrun("plan_gate.py", over_ns) is True

    def test_the_floor_sits_below_every_declared_budget(
        self, canonical_config: dict
    ) -> None:
        """Boundary: no budgeted hook may be under the short-circuit floor."""
        import hook_timing

        for name, entry in canonical_config["hooks"].items():
            assert entry["budget_seconds"] >= hook_timing.MIN_BUDGET_SECONDS, (
                f"{name} is budgeted below the fast-path floor; its overruns "
                f"would never be recorded."
            )


class TestRemediationW8DegradeIsNoisy:
    """A silent fallback returns a number that LOOKS configured."""

    def test_degrade_path_writes_to_stderr(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        assert hook_budgets.library_timeout_or("no-such-key", 7) == 7
        assert "DEGRADED" in capsys.readouterr().err

    def test_success_path_is_silent(self, capsys: pytest.CaptureFixture) -> None:
        """NEGATIVE CONTROL: a working lookup must not cry wolf."""
        hook_budgets.library_timeout_or("semantic_gate.TIMEOUT_S", 999)
        assert capsys.readouterr().err == ""

    def test_programming_errors_still_propagate(self) -> None:
        """It must not be a bare `except Exception`."""
        with pytest.raises(TypeError):
            hook_budgets.library_timeout_or(["not", "a", "key"], 7)

    def test_runtime_attributes_match_canonical(self) -> None:
        """The HAPPY path: with a readable config the attributes are canonical.

        NOT a check on the fail-safe literals. At runtime the attribute holds
        ``library_timeout_or(key, literal)``, which discards the literal
        whenever the config is readable -- so this assertion is X == X with
        respect to the literal and would pass with a 5, a 99 or a -1 in every
        fail-safe slot. It is kept because it does verify the SUCCESS path
        (config -> attribute), and it is named for what it actually covers.
        The literals are checked statically by
        ``TestRemediation3FallbackLiteralsAreReallyLocked``.
        """
        import genai_prompts
        import intent_classifier
        import semantic_gate

        for module, attr, key in (
            (genai_prompts, "DEFAULT_TIMEOUT", "genai_prompts.DEFAULT_TIMEOUT"),
            (
                intent_classifier,
                "DEFAULT_TIMEOUT_SECONDS",
                "intent_classifier.timeout_seconds",
            ),
            (semantic_gate, "TIMEOUT_S", "semantic_gate.TIMEOUT_S"),
        ):
            assert getattr(module, attr) == hook_budgets.get_library_timeout(key)

    def test_measurement_window_is_recorded(self) -> None:
        """A count without its window is not re-derivable."""
        raw = json.loads(
            (PLUGIN_ROOT / "config" / "hook_time_budgets.json").read_text()
        )
        window = raw["_measurement_window"]
        assert window["start_date_inclusive"] == "2026-08-21"
        assert window["schema_version"] == 2
        assert window["total_rows_at_capture"] > 0


class TestRemediation2BlockingASkewIsAGate:
    """Printing a skew and exiting 0 is a print statement, not a gate.

    The skew block had no ``return 1``; control fell through to an empty
    ``drift`` and returned 0. It was asymmetric with both adjacent paths --
    ``unbudgeted`` and ``drift`` each returned 1 -- which is why it read as an
    omission rather than a decision.

    The refusing arm uses a SYNTHETIC skew, not the live one, so it keeps
    working after deploy removes the live skew.
    """

    @staticmethod
    def _synthetic_skew(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Force exactly one skew, independent of what is deployed."""
        installed = tmp_path / "settings.json"
        installed.write_text(
            json.dumps(
                {
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": "*",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "python3 ~/.claude/hooks/unified_pre_tool.py",
                                        "timeout": THE_UNMEASURED_FIVE,
                                    }
                                ],
                            }
                        ]
                    }
                }
            )
        )
        monkeypatch.setattr(
            hook_budgets, "installed_settings_paths", lambda *a, **k: [installed]
        )

    def test_refusing_skew_exits_nonzero_without_the_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """REFUSING ARM: synthetic skew, no flag -> exit 1."""
        self._synthetic_skew(monkeypatch, tmp_path)
        rc = ghc.main(["--check-timeouts"])
        out = capsys.readouterr().out
        assert "SKEW" in out, "The skew was not even reported."
        assert rc == 1, (
            f"--check-timeouts printed a skew and returned {rc}. A gate that "
            f"cannot fail is a print statement; nothing can gate on it."
        )
        assert "deploy-all.sh --global-settings" in out

    def test_permitting_skew_exits_zero_with_the_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """PERMITTING ARM: the acknowledged pre-deploy window.

        Skew is currently EXPECTED because deploy has deliberately not run. A
        bare `return 1` would make the command permanently red and train
        everyone to ignore it -- the cry-wolf failure this repo treats as
        first-class. The acknowledgement is explicit and narrow.
        """
        self._synthetic_skew(monkeypatch, tmp_path)
        rc = ghc.main(["--check-timeouts", "--allow-skew"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "ACKNOWLEDGED via --allow-skew" in out, (
            "A silent acknowledgement is indistinguishable from a checker that "
            "did not run."
        )

    def test_no_skew_exits_zero_without_the_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """NEGATIVE CONTROL: the flag is not what produces exit 0."""
        declared = hook_budgets.get_hook_budget("unified_pre_tool")
        installed = tmp_path / "settings.json"
        installed.write_text(
            json.dumps(
                {
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": "*",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "python3 ~/.claude/hooks/unified_pre_tool.py",
                                        "timeout": declared,
                                    }
                                ],
                            }
                        ]
                    }
                }
            )
        )
        monkeypatch.setattr(
            hook_budgets, "installed_settings_paths", lambda *a, **k: [installed]
        )
        rc = ghc.main(["--check-timeouts"])
        assert rc == 0
        assert "SKEW" not in capsys.readouterr().out

    def test_the_flag_does_not_mask_drift_or_unbudgeted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--allow-skew is NARROW: it must not become a blanket pass.

        Scoped to the pre-deploy window only. Drift and unbudgeted entries are
        different classes and keep failing.
        """
        self._synthetic_skew(monkeypatch, tmp_path)
        surface = tmp_path / "drifted.json"
        surface.write_text(
            json.dumps(
                {
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": "*",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "python3 ~/.claude/hooks/unified_pre_tool.py",
                                        "timeout": THE_UNMEASURED_FIVE,
                                    }
                                ],
                            }
                        ]
                    }
                }
            )
        )
        monkeypatch.setattr(
            ghc, "discover_settings_surfaces", lambda *a, **k: [surface]
        )
        assert ghc.main(["--check-timeouts", "--allow-skew"]) == 1


class TestRemediation2WarningBSkewVacuity:
    """The W4 pattern, now in the skew mechanism itself."""

    def test_refusing_zero_installed_settings_files(
        self, canonical_config: dict
    ) -> None:
        """SHAPE A: the consumer-repo case -- nothing deployed at all."""
        violations = hook_budgets.check_installed_settings_skew([], canonical_config)
        assert violations, (
            "A checker whose purpose is catching undeployed state gave a clean "
            "bill to a machine with nothing deployed."
        )
        assert "ZERO installed settings" in violations[0]
        assert hook_budgets.inspected_settings_count([]) == 0

    def test_refusing_a_settings_file_with_no_hooks(
        self, tmp_path: Path, canonical_config: dict
    ) -> None:
        """SHAPE B: parses cleanly, registers nothing."""
        path = tmp_path / "s.json"
        path.write_text(json.dumps({"permissions": {}}))
        violations = hook_budgets.check_installed_settings_skew(
            [path], canonical_config
        )
        assert violations and "ZERO hooks" in violations[0]

    def test_refusing_a_malformed_settings_file(
        self, tmp_path: Path, canonical_config: dict
    ) -> None:
        """SHAPE C, the worst: a corrupt file that still governs execution."""
        path = tmp_path / "s.json"
        path.write_text("{ this is not json")
        violations = hook_budgets.check_installed_settings_skew(
            [path], canonical_config
        )
        assert violations, "A corrupt settings file read as CLEAN."
        assert "MALFORMED JSON" in violations[0]
        assert "UNKNOWN, not absent" in violations[0]

    def test_the_reader_distinguishes_no_hooks_from_unparseable(
        self, tmp_path: Path
    ) -> None:
        """The root cause: `{}` meant both, so the caller could not tell."""
        empty = tmp_path / "a.json"
        empty.write_text(json.dumps({"permissions": {}}))
        broken = tmp_path / "b.json"
        broken.write_text("{ nope")

        assert hook_budgets.read_installed_timeouts(empty) == ({}, None)
        timeouts, error = hook_budgets.read_installed_timeouts(broken)
        assert timeouts == {} and error is not None

    def test_permitting_a_correctly_deployed_file(
        self, tmp_path: Path, canonical_config: dict
    ) -> None:
        """PERMITTING ARM: the anti-vacuity guards must not deny everything."""
        declared = hook_budgets.get_hook_budget("plan_gate", canonical_config)
        path = tmp_path / "s.json"
        path.write_text(
            json.dumps(
                {
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": "*",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "python3 ~/.claude/hooks/plan_gate.py",
                                        "timeout": declared,
                                    }
                                ],
                            }
                        ]
                    }
                }
            )
        )
        assert (
            hook_budgets.check_installed_settings_skew([path], canonical_config) == []
        )
        assert hook_budgets.inspected_settings_count([path]) == 1

    def test_project_root_is_found_from_a_subdirectory(self) -> None:
        """WARNING-B / #1697: anchoring on cwd drops the project tier."""
        for start in (
            REPO_ROOT,
            REPO_ROOT / "plugins" / "autonomous-dev" / "lib",
            REPO_ROOT / "tests" / "unit" / "lib",
        ):
            assert hook_budgets.find_project_root(start) == REPO_ROOT, (
                f"find_project_root({start}) drifted off the repo root."
            )

    def test_git_marker_wins_over_a_stray_dot_claude(self, tmp_path: Path) -> None:
        """NEGATIVE CONTROL, measured not hypothesised.

        `plugins/autonomous-dev/.claude/` exists in this repo as a log
        artifact. A combined "first ancestor with either marker" walk anchors
        THERE and silently drops the real project tier -- my own probe caught
        exactly that before this ordering was introduced.

        Built hermetically in tmp_path rather than depending on the repo's
        artifact directory: a conditional skip would make this control vanish
        on a clean clone, which is precisely when it matters.
        """
        root = tmp_path / "repo"
        (root / ".git").mkdir(parents=True)
        nested = root / "plugins" / "thing"
        (nested / ".claude").mkdir(parents=True)

        assert hook_budgets.find_project_root(nested) == root, (
            "A stray .claude/ shadowed the real repo root; the two marker "
            "passes are not ordered."
        )
        # And .claude still anchors when there is no .git anywhere.
        standalone = tmp_path / "consumer"
        (standalone / ".claude").mkdir(parents=True)
        assert hook_budgets.find_project_root(standalone) == standalone


class TestRemediation2WarningCImportWalkSeesDynamicLoads:
    """importlib is this repo's primary hook->lib loader."""

    def test_importlib_edges_are_visible(self) -> None:
        """`spec_from_file_location` loads must be seen, or W5 relocates."""
        edges = hook_budgets._module_imports(
            HOOKS_DIR / "unified_pre_tool.py"
        )
        index = hook_budgets._local_module_index()
        local = {e for e in edges if e in index}
        assert len(local) >= 8, (
            f"unified_pre_tool.py loads at least eight local modules via "
            f"importlib; the walk sees {len(local)}."
        )
        assert "hook_telemetry" in local
        assert "semantic_gate" in local

    def test_relative_imports_are_visible(self, tmp_path: Path) -> None:
        """`from . import x` was filtered out by node.level == 0."""
        src = tmp_path / "m.py"
        src.write_text("from . import sibling_module\nfrom .pkg import other\n")
        edges = hook_budgets._module_imports(src)
        assert "sibling_module" in edges
        assert "other" in edges

    def test_dynamic_edges_from_string_literals(self, tmp_path: Path) -> None:
        src = tmp_path / "m.py"
        src.write_text(
            "import importlib.util\n"
            "s = importlib.util.spec_from_file_location('alpha', '/x/alpha.py')\n"
            "m = importlib.import_module('beta')\n"
        )
        edges = hook_budgets._module_imports(src)
        assert {"alpha", "beta"} <= edges

    def test_it_does_not_over_credit(self, tmp_path: Path) -> None:
        """NEGATIVE CONTROL (#1698 shape): prose is not an edge.

        Over-crediting is the dangerous direction -- it would let a real host
        be declared covered by a mention in a comment.
        """
        src = tmp_path / "m.py"
        src.write_text(
            '"""Docstring mentioning genai_prompts."""\n'
            "# comment mentioning genai_prompts\n"
            "TEXT = 'genai_prompts'\n"
            "def f():\n    return 'genai_prompts'\n"
        )
        assert "genai_prompts" not in hook_budgets._module_imports(src)

    def test_the_remaining_blind_spot_is_declared(self) -> None:
        """A gap named in the docstring is declared; an unnamed one is silent."""
        doc = hook_budgets._module_imports.__doc__ or ""
        assert "BLIND SPOT" in doc.upper()
        assert "COMPUTED" in doc.upper()

    def test_widening_the_walk_did_not_change_the_derived_hosts(self) -> None:
        """The property held before and after; the walk is now honest about why."""
        assert hook_budgets.derive_host_hooks("intent_classifier") == {
            "unified_prompt_validator"
        }
        assert hook_budgets.check_declared_hosts_match_derived() == []


class TestRemediation2WarningDBudgetBelowOverrunFloor:
    """A budget below the floor passes every check and can never record."""

    def test_refusing_a_budget_below_the_overrun_floor(
        self, canonical_config: dict
    ) -> None:
        """REFUSING ARM: 2s, above the old `< 1` bar, below the 3s floor."""
        below = copy.deepcopy(canonical_config)
        below["hooks"]["plan_gate"]["budget_seconds"] = (
            hook_budgets.OVERRUN_FLOOR_SECONDS - 1
        )
        violations = hook_budgets.check_ceiling(below)
        assert any("plan_gate" in v for v in violations), (
            "A budget below the overrun floor passed check_ceiling. It would "
            "overrun forever without producing a countable record."
        )
        assert any("overrun floor" in v for v in violations)

    def test_permitting_a_budget_exactly_at_the_floor(
        self, canonical_config: dict
    ) -> None:
        """BOUNDARY, permitting side: equal to the floor is fine."""
        at = copy.deepcopy(canonical_config)
        at["hooks"]["plan_gate"]["budget_seconds"] = (
            hook_budgets.OVERRUN_FLOOR_SECONDS
        )
        assert hook_budgets.check_ceiling(at) == []

    def test_the_floor_authority_and_its_mirror_agree(self) -> None:
        """One authority, one performance mirror, locked together."""
        import hook_timing

        assert (
            hook_timing.MIN_BUDGET_SECONDS == hook_budgets.OVERRUN_FLOOR_SECONDS
        ), (
            "hook_timing's literal drifted from hook_budgets.OVERRUN_FLOOR_SECONDS."
        )
        assert (
            hook_budgets.OVERRUN_FLOOR_SECONDS
            <= hook_budgets.min_declared_budget_seconds()
        ), "The floor sits ABOVE a declared budget; that hook cannot record."

    def test_the_live_config_has_no_budget_below_the_floor(
        self, canonical_config: dict
    ) -> None:
        for name, entry in canonical_config["hooks"].items():
            assert entry["budget_seconds"] >= hook_budgets.OVERRUN_FLOOR_SECONDS, (
                f"{name} is budgeted below the overrun floor."
            )


class TestRemediation3FallbackLiteralsAreReallyLocked:
    """Six fail-safe literals were claimed locked by a test that could not fail.

    ``test_fallback_literals_match_canonical_not_the_pre_fix_value`` asserted
    ``module.ATTR == get_library_timeout(key)``. At import ``ATTR`` is assigned
    ``library_timeout_or(key, literal)``, which returns ``get_library_timeout(key)``
    whenever the config is readable -- so the assertion compared X to X and the
    pre-#1704 ``5`` could sit in every slot and still pass. MEASURED:

        library_timeout_or('genai_prompts.DEFAULT_TIMEOUT', 5)  -> 15
        library_timeout_or('genai_prompts.DEFAULT_TIMEOUT', 99) -> 15

    A tautological assertion inside the change that made enforcement real, under
    a comment claiming coverage. A false coverage claim is worse than an
    uncovered line: it stops anyone looking.

    Two independent mechanisms replace it:

    1. STATIC -- read the literals out of the source and compare to canonical.
       Cannot be tautological: the literal never passes through the runtime
       value. Covers all six (three call args + three ``except ImportError``
       duplicates), including the branch that is unreachable in test.
    2. RUNTIME -- a synthetic module built in tmp_path exercises the actual
       degrade path with an unreadable config, proving the literal IS what the
       fallback yields.
    """

    @pytest.fixture()
    def canonical(self) -> "dict[str, int]":
        cfg = hook_budgets.load_budget_config()
        return {
            key: hook_budgets.get_library_timeout(key, cfg)
            for key in cfg["libraries"]
        }

    # -- instrument controls -------------------------------------------------

    def test_the_extractor_finds_every_site(self) -> None:
        """POSITIVE CONTROL: a zero result would make every arm below vacuous."""
        for module_name, rel in _FALLBACK_MODULES.items():
            sites = extract_fallback_literals((REPO_ROOT / rel).read_text())
            assert len(sites) == 1, (
                f"{module_name}: expected exactly one library_timeout_or "
                f"binding site, found {len(sites)}. The extractor anchor moved "
                f"or the shape changed; a zero here would silently pass."
            )
            attr, key, call_lit, except_lit = sites[0]
            assert isinstance(call_lit, int)
            assert except_lit is not None, (
                f"{module_name}: no int literal in the `except ImportError` "
                f"branch, so that duplicate is unverifiable."
            )

    def test_the_extractor_ignores_unrelated_try_blocks(self) -> None:
        """NEGATIVE CONTROL: it must not match every try/except."""
        assert extract_fallback_literals(
            "try:\n    import os\nexcept ImportError:\n    X = 5\n"
        ) == []
        assert extract_fallback_literals(
            "try:\n    X = other_call('k', 5)\nexcept ImportError:\n    X = 5\n"
        ) == []

    def test_the_checker_can_fail(self, canonical: "dict[str, int]") -> None:
        """POSITIVE CONTROL on the checker itself, not just the extractor."""
        wrong = (
            "try:\n"
            "    from hook_budgets import library_timeout_or\n"
            "    T = library_timeout_or('semantic_gate.TIMEOUT_S', 999)\n"
            "except ImportError:\n"
            "    T = 999\n"
        )
        assert check_fallback_literals(wrong, canonical)

    # -- the static lock, both arms -----------------------------------------

    def test_permitting_the_live_literals_match_canonical(
        self, canonical: "dict[str, int]"
    ) -> None:
        """PERMITTING ARM: every one of the six literals is correct today."""
        for module_name, rel in _FALLBACK_MODULES.items():
            violations = check_fallback_literals(
                (REPO_ROOT / rel).read_text(), canonical
            )
            assert not violations, f"{module_name}:\n  " + "\n  ".join(violations)

    @pytest.mark.parametrize("module_name", sorted(_FALLBACK_MODULES))
    def test_refusing_a_call_literal_reverted_to_the_pre_fix_five(
        self, module_name: str, canonical: "dict[str, int]"
    ) -> None:
        """REFUSING ARM: the pre-#1704 5 in the fail-safe slot must FAIL.

        This is the exact mutation the old test could not detect.
        """
        rel = _FALLBACK_MODULES[module_name]
        source = (REPO_ROOT / rel).read_text()
        attr, key, call_lit, _ = extract_fallback_literals(source)[0]
        if call_lit == THE_UNMEASURED_FIVE:
            pytest_fail = (
                f"{module_name} already carries {THE_UNMEASURED_FIVE}; the "
                f"mutation would be a no-op and the arm vacuous."
            )
            raise AssertionError(pytest_fail)

        mutated = source.replace(
            f'library_timeout_or_1704("{key}", {call_lit})',
            f'library_timeout_or_1704("{key}", {THE_UNMEASURED_FIVE})',
        ).replace(
            f'library_timeout_or_1704(\n        "{key}", {call_lit}\n    )',
            f'library_timeout_or_1704(\n        "{key}", {THE_UNMEASURED_FIVE}\n    )',
        )
        assert mutated != source, (
            f"The mutation changed nothing in {module_name}; the anchor is "
            f"wrong and this arm proves nothing."
        )
        violations = check_fallback_literals(mutated, canonical)
        assert any("fail-safe is" in v for v in violations), (
            f"A fail-safe literal of {THE_UNMEASURED_FIVE} was NOT refused in "
            f"{module_name}. The replacement check is tautological too. "
            f"Got: {violations}"
        )

    @pytest.mark.parametrize("module_name", sorted(_FALLBACK_MODULES))
    def test_refusing_an_except_importerror_literal_that_drifts(
        self, module_name: str, canonical: "dict[str, int]"
    ) -> None:
        """REFUSING ARM for the three `# pragma: no cover` duplicates.

        These lines never execute in test, so line coverage can never reach
        them. Their VALUE is still checkable statically -- which is what makes
        the pragma honest rather than a hiding place.
        """
        rel = _FALLBACK_MODULES[module_name]
        source = (REPO_ROOT / rel).read_text()
        attr, key, _, except_lit = extract_fallback_literals(source)[0]
        assert except_lit is not None

        lines = source.splitlines(keepends=True)
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(f"{attr} = ") and stripped.split("=")[1].strip().split(
                "#"
            )[0].strip() == str(except_lit):
                lines[i] = line.replace(
                    f"= {except_lit}", f"= {THE_UNMEASURED_FIVE}", 1
                )
                break
        else:
            raise AssertionError(
                f"Could not locate the except-branch assignment in "
                f"{module_name}; the mutation would be a no-op."
            )
        mutated = "".join(lines)
        assert mutated != source
        violations = check_fallback_literals(mutated, canonical)
        assert any("except ImportError" in v for v in violations), (
            f"A drifted `except ImportError` literal was NOT refused in "
            f"{module_name}. Got: {violations}"
        )

    def test_every_library_key_has_a_verified_call_site(
        self, canonical: "dict[str, int]"
    ) -> None:
        """A fourth library added without this shape must not slip through."""
        covered = set()
        for rel in _FALLBACK_MODULES.values():
            for _, key, _, _ in extract_fallback_literals(
                (REPO_ROOT / rel).read_text()
            ):
                covered.add(key)
        assert covered == set(canonical), (
            f"Library keys with no statically-verified binding site: "
            f"{sorted(set(canonical) - covered)}. Add the module to "
            f"_FALLBACK_MODULES or the literal is unchecked."
        )

    # -- the runtime degrade path, both arms --------------------------------

    @staticmethod
    def _degrade(tmp_path: Path, literal: int, name: str) -> int:
        """Import a synthetic binder with an UNREADABLE config; return the value.

        Exercises the real ``library_timeout_or`` error branch, so the literal
        is genuinely what the attribute ends up holding.
        """
        import importlib.util

        module_path = tmp_path / f"{name}.py"
        module_path.write_text(
            "from hook_budgets import library_timeout_or\n"
            f"VALUE = library_timeout_or('semantic_gate.TIMEOUT_S', {literal})\n"
        )
        original = hook_budgets.BUDGET_CONFIG_PATH
        try:
            hook_budgets.BUDGET_CONFIG_PATH = tmp_path / "absent.json"
            hook_budgets.clear_cache()
            spec = importlib.util.spec_from_file_location(name, module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.VALUE
        finally:
            hook_budgets.BUDGET_CONFIG_PATH = original
            hook_budgets.clear_cache()

    def test_permitting_the_degrade_path_yields_the_canonical_value(
        self, tmp_path: Path, canonical: "dict[str, int]"
    ) -> None:
        """PERMITTING ARM: correct literal, config unreadable -> canonical."""
        expected = canonical["semantic_gate.TIMEOUT_S"]
        assert self._degrade(tmp_path, expected, "binder_ok") == expected

    def test_refusing_the_degrade_path_with_a_wrong_literal(
        self, tmp_path: Path, canonical: "dict[str, int]"
    ) -> None:
        """REFUSING ARM: a wrong literal is what the degrade path actually returns.

        This is the property the old test could not see, because on the happy
        path the literal is discarded.
        """
        expected = canonical["semantic_gate.TIMEOUT_S"]
        got = self._degrade(tmp_path, THE_UNMEASURED_FIVE, "binder_bad")
        assert got == THE_UNMEASURED_FIVE
        assert got != expected, (
            "The wrong literal did not survive to the attribute, so the "
            "degrade path is not exercising the fallback at all."
        )


class TestOverrunIsCountable:
    """A timeout-skip must be findable by one query afterwards."""

    @staticmethod
    def _tiny_budget_config(tmp_path: Path) -> Path:
        """Write a budget config at the SMALLEST budget the fast path permits.

        Derived from ``hook_timing.MIN_BUDGET_SECONDS``, never hardcoded. The
        first version of this fixture used 1s and went red when the W7 fast
        path landed -- correctly: a hook budgeted below the floor can never
        record an overrun, so a 1s fixture was asserting behaviour the system
        does not have. Deriving it means the fixture can never again sit in
        that dead zone silently.
        """
        import hook_timing

        config = {
            "default": {"budget_seconds": 5, "warning_pct": 0.8},
            "hooks": {
                "fake_slow_hook": {
                    "budget_seconds": hook_timing.MIN_BUDGET_SECONDS,
                    "warning_pct": 0.8,
                    "measured_p99_ms": None,
                    "measured_max_ms": None,
                }
            },
            "libraries": {},
        }
        path = tmp_path / "tiny_budgets.json"
        path.write_text(json.dumps(config))
        return path

    def test_overrun_writes_a_findable_row_and_fast_run_does_not(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BOTH ARMS with a real wall-clock overrun, plus the scope control.

        Arm A  REFUSING  : registered hook exceeds its budget -> one row.
        Arm B  PERMITTING: same hook returns fast             -> no row.
        Arm C  SCOPE     : UNREGISTERED name exceeds it       -> no row.

        Arm C is the mutation_witness_gate class: it borrows HookTimer, is
        registered nowhere, and contributed 56 spurious over-5s rows to the
        production timing sink (tracked separately as #1645). Counting it here
        would re-import that pollution into the refusal sink.
        """
        import hook_timing
        from hook_telemetry import is_refusal_row

        monkeypatch.setattr(
            hook_budgets, "BUDGET_CONFIG_PATH", self._tiny_budget_config(tmp_path)
        )
        hook_budgets.clear_cache()
        monkeypatch.setenv("HOOK_TIMING_DIR", str(tmp_path / "timings"))
        monkeypatch.chdir(tmp_path)

        budget = hook_budgets.get_hook_budget("fake_slow_hook")
        assert budget == hook_timing.MIN_BUDGET_SECONDS, (
            "Fixture budget did not load; the arm would be vacuous."
        )
        assert budget * 1_000_000_000 >= hook_timing.MIN_BUDGET_NS, (
            "Fixture sits below the W7 fast-path floor, so no row could be "
            "written for a reason unrelated to what this test asserts."
        )

        started = time.monotonic()
        with hook_timing.HookTimer("fake_slow_hook.py"):
            time.sleep(budget + 0.05)
        elapsed = time.monotonic() - started
        assert elapsed > budget, (
            f"The overrun did not actually happen ({elapsed:.2f}s <= {budget}s); "
            f"a faked duration would prove nothing."
        )

        with hook_timing.HookTimer("fake_slow_hook.py"):
            pass

        with hook_timing.HookTimer("mutation_witness_gate.py"):
            time.sleep(budget + 0.05)

        sink = tmp_path / ".claude" / "logs" / "hook-blocks.jsonl"
        assert sink.exists(), "No row reached the canonical sink at all."
        rows = [json.loads(x) for x in sink.read_text().splitlines() if x.strip()]

        names = [r["hook_name"] for r in rows]
        assert names == ["fake_slow_hook.py"], (
            f"Expected exactly one row, from the registered hook that "
            f"overran. Got: {names}"
        )

        row = rows[0]
        assert row["decision_shape"] == hook_budgets.SHAPE_BUDGET_OVERRUN
        assert (
            row["metadata"]["event_type"] == hook_budgets.EVENT_TYPE_BUDGET_OVERRUN
        ), "The one-query handle is missing; an auditor cannot find these rows."
        assert row["metadata"]["budget_seconds"] == budget
        assert row["metadata"]["duration_ms"] > budget * 1000
        assert row["metadata"]["overrun_ms"] > 0

        assert not is_refusal_row(row), (
            "An overrun was counted as a REFUSAL. Enforcement skipped is the "
            "opposite of a refusal and must never inflate the refusal count."
        )

    def test_overrun_shape_is_not_a_block_shape(self) -> None:
        """Structural: the shape must sit outside the refusal vocabulary."""
        from hook_telemetry import BLOCK_SHAPES

        assert hook_budgets.SHAPE_BUDGET_OVERRUN not in BLOCK_SHAPES

    def test_overrun_record_has_a_rollback_switch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The record can be disabled without losing the timing row.

        The sleep must clear the W7 fast-path floor, or the absent row would
        prove the floor works rather than the switch -- a vacuous pass.
        """
        import hook_timing

        monkeypatch.setattr(
            hook_budgets, "BUDGET_CONFIG_PATH", self._tiny_budget_config(tmp_path)
        )
        hook_budgets.clear_cache()
        monkeypatch.setenv(hook_timing.BUDGET_OVERRUN_DISABLE_ENV_VAR, "1")
        monkeypatch.setenv("HOOK_TIMING_DIR", str(tmp_path / "timings"))
        monkeypatch.chdir(tmp_path)

        budget = hook_budgets.get_hook_budget("fake_slow_hook")
        with hook_timing.HookTimer("fake_slow_hook.py"):
            time.sleep(budget + 0.05)

        assert not (tmp_path / ".claude" / "logs" / "hook-blocks.jsonl").exists()
        timing_rows = list((tmp_path / "timings").glob("hook_timings_*.jsonl"))
        assert timing_rows, "The rollback switch also silenced the timing row."

    def test_the_disable_switch_is_not_what_suppresses_the_row(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """NEGATIVE CONTROL for the test above: without the switch, a row appears.

        Same fixture, same duration, switch OFF. If this produced no row either,
        the test above would be passing on the fast-path floor rather than on
        the rollback switch.
        """
        import hook_timing

        monkeypatch.setattr(
            hook_budgets, "BUDGET_CONFIG_PATH", self._tiny_budget_config(tmp_path)
        )
        hook_budgets.clear_cache()
        monkeypatch.delenv(hook_timing.BUDGET_OVERRUN_DISABLE_ENV_VAR, raising=False)
        monkeypatch.setenv("HOOK_TIMING_DIR", str(tmp_path / "timings"))
        monkeypatch.chdir(tmp_path)

        budget = hook_budgets.get_hook_budget("fake_slow_hook")
        with hook_timing.HookTimer("fake_slow_hook.py"):
            time.sleep(budget + 0.05)

        assert (tmp_path / ".claude" / "logs" / "hook-blocks.jsonl").exists()
