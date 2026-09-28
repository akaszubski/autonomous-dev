"""Backward-compatibility and wiring regression tests for Issue #1467.

The two-stage alignment gate must be additive. Everything that worked before
it landed must keep working:

- Pipeline states written before #1467 (no ``alignment_verdict`` key) still
  sign, verify, and pass the hook gate.
- Consumer repos whose PROJECT.md has no INVARIANTS section are never blocked
  on the architecture-delta axis.
- A repo with no PROJECT.md at all still produces a clean BLOCK, not a crash.

It also locks the operational wiring rule from PROJECT.md CONSTRAINTS: a new
agent must be registered in ``AGENT_CONFIGS`` AND the install manifest, the
new label must exist in the label-setup script, and the drain runner must mark
its subprocesses non-interactive.

GitHub Issue: #1467
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tests.helpers.state_isolation import redirect_pipeline_state  # noqa: E402
from tests.helpers.sanctioned_run import (  # noqa: E402
    clear_run_artifacts,
    write_sanctioned_sentinel,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PLUGIN_ROOT = _REPO_ROOT / "plugins" / "autonomous-dev"
_LIB_DIR = _PLUGIN_ROOT / "lib"
_HOOK_DIR = _PLUGIN_ROOT / "hooks"

for _p in (str(_LIB_DIR), str(_HOOK_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

AGENT_NAME = "alignment-classifier"
AGENT_FILE = _PLUGIN_ROOT / "agents" / f"{AGENT_NAME}.md"
MANIFEST = _PLUGIN_ROOT / "config" / "install_manifest.json"
LABEL = "needs-scope-decision"


# ---------------------------------------------------------------------------
# 1. Legacy pipeline state compatibility
# ---------------------------------------------------------------------------


class TestLegacyStateCompatibility:
    """Pre-#1467 states must be indistinguishable from before."""

    def test_legacy_state_signs_and_verifies(self):
        from pipeline_state import cleanup_pipeline_secret, sign_state, verify_state_hmac

        state = {
            "session_start": "2026-03-28T10:00:00",
            "mode": "full",
            "run_id": "legacy-1467",
            "explicitly_invoked": True,
            "alignment_passed": True,
        }
        signed = sign_state(state, "legacy-session")
        assert verify_state_hmac(signed, "legacy-session") is True
        assert "alignment_verdict" not in state
        cleanup_pipeline_secret("legacy-1467")

    def test_legacy_state_without_verdict_passes_hook_gate(self, tmp_path, monkeypatch):
        """A pre-#1467 state (no ``alignment_verdict``) still passes the gate.

        Issue #1807 AMENDMENT — the SUBJECT of this arm is #1467 verdict
        back-compat, and that is unchanged: the boolean is still the whole
        contract when the verdict field is absent. What changed is the SETUP.
        The pre-#1807 version signed a state with NO ``session_id`` and no
        run-start receipt, and asserted the gate honoured it; that shape is the
        #1807 forgery (an owner nobody can verify, a MAC the caller minted), so
        asserting it "passes" would now be asserting the defect. The state is
        built as a sanctioned run instead, which keeps this arm measuring verdict
        back-compat rather than authority.
        """
        import unified_pre_tool as hook

        import pipeline_completion_state as _pcs
        import pipeline_state as _ps
        import unified_pre_tool as _hook

        redirect_pipeline_state(monkeypatch, tmp_path, _ps, _pcs, _hook)
        owner = "sess-legacy-gate-1467"
        path = tmp_path / "state.json"
        state = write_sanctioned_sentinel(
            path, owner, "legacy-gate-1467", alignment_passed=True
        )
        assert "alignment_verdict" not in state, (
            "this arm is about the pre-#1467 shape; a verdict field would make "
            "it test the #1467 path instead"
        )
        monkeypatch.setenv("PIPELINE_STATE_FILE", str(path))
        monkeypatch.setenv("CLAUDE_SESSION_ID", owner)
        # Issue #1807 (defect 1): authority binds to the NATIVE stdin identity.
        monkeypatch.setattr(hook, "_session_id", owner, raising=False)
        try:
            assert hook._has_alignment_passed() is True
        finally:
            clear_run_artifacts(owner)

    def test_unsigned_legacy_state_does_not_pass_hook_gate(self, tmp_path, monkeypatch):
        """REFUSE arm (Issue #1807): an UNSIGNED legacy state is recognized, not authorized.

        The counterfactual for the amendment above, and the reason it is not a
        silent coverage loss. A state carrying every field the gate reads but no
        MAC skipped the integrity branch entirely before #1807 — the route
        ``--fix`` mode actually used.
        """
        import unified_pre_tool as hook

        path = tmp_path / "unsigned.json"
        path.write_text(json.dumps({
            "session_start": __import__("datetime").datetime.now().isoformat(),
            "mode": "full",
            "run_id": "legacy-gate-1467",
            "explicitly_invoked": True,
            "alignment_passed": True,
            "session_id": "sess-legacy-unsigned",
        }))
        monkeypatch.setenv("PIPELINE_STATE_FILE", str(path))
        monkeypatch.setenv("CLAUDE_SESSION_ID", "sess-legacy-unsigned")
        assert hook._has_alignment_passed() is False


# ---------------------------------------------------------------------------
# 2. Consumer repos without INVARIANTS
# ---------------------------------------------------------------------------


class TestConsumerRepoCompatibility:
    """Repos that never adopted INVARIANTS must never be blocked by them."""

    _CONSUMER_PROJECT_MD = (
        "# My App\n\n"
        "## GOALS\nShip the product.\n\n"
        "## SCOPE\n\n**IN Scope:**\n- Building the web application\n\n"
        "**OUT of Scope:**\n- Mobile native applications\n\n"
        "## CONSTRAINTS\nPython 3.11+.\n"
    )

    def test_parses_without_invariants(self):
        from alignment_classifier import parse_project_md_text

        doc = parse_project_md_text(self._CONSUMER_PROJECT_MD)
        assert doc.has_invariants is False
        assert doc.invariants == ()

    def test_architecture_delta_does_not_block_without_invariants(self):
        from alignment_classifier import (
            Stage0Outcome,
            Stage0Result,
            Verdict,
            map_verdict,
            parse_project_md_text,
        )

        doc = parse_project_md_text(self._CONSUMER_PROJECT_MD)
        stage0 = Stage0Result(
            outcome=Stage0Outcome.CLEAR,
            reason="no deterministic signal",
            injection_detected=False,
            matched_out_scope_clause=None,
            is_standard_change=False,
            architecture_delta_phrase=None,
        )
        verdict = map_verdict(
            stage0, "architecture_delta", "Building the web application", doc
        )
        assert verdict is Verdict.AUTO_PASS

    def test_out_of_scope_still_escalates_without_invariants(self):
        """Scope enforcement is independent of the INVARIANTS section."""
        from alignment_classifier import (
            Stage0Outcome,
            Verdict,
            map_verdict,
            parse_project_md_text,
            run_stage0,
        )

        doc = parse_project_md_text(self._CONSUMER_PROJECT_MD)
        stage0 = run_stage0("Add mobile native applications support", doc)
        assert stage0.outcome is Stage0Outcome.ESCALATE
        assert map_verdict(stage0, "out_of_scope", None, doc) is Verdict.ESCALATE

    def test_missing_project_md_raises_for_block(self, tmp_path):
        from alignment_classifier import parse_project_md

        with pytest.raises(FileNotFoundError):
            parse_project_md(tmp_path / ".claude" / "PROJECT.md")


# ---------------------------------------------------------------------------
# 3. Operational wiring rule (PROJECT.md CONSTRAINTS)
# ---------------------------------------------------------------------------


class TestOperationalWiring:
    """A new agent must be registered everywhere, not just created on disk."""

    def test_agent_file_exists(self):
        assert AGENT_FILE.exists(), f"Missing agent definition: {AGENT_FILE}"

    def test_agent_frontmatter_declares_haiku_and_read_only_tools(self):
        content = AGENT_FILE.read_text()
        assert content.startswith("---"), "Agent file must open with YAML frontmatter"
        frontmatter = content.split("---", 2)[1]
        assert f"name: {AGENT_NAME}" in frontmatter
        assert "model: haiku" in frontmatter
        for forbidden in ("Write", "Edit", "Bash"):
            assert forbidden not in frontmatter, (
                f"Classifier must be read-only; frontmatter grants {forbidden}"
            )

    def test_agent_registered_in_agent_configs(self):
        sys.path.insert(0, str(_REPO_ROOT))
        from plugins.autonomous_dev.lib.agent_invoker import AgentInvoker

        assert AGENT_NAME in AgentInvoker.AGENT_CONFIGS, (
            f"{AGENT_NAME} missing from AGENT_CONFIGS — the registry consistency "
            "test will also fail."
        )

    def test_agent_registered_in_install_manifest(self):
        manifest = json.loads(MANIFEST.read_text())
        files = manifest["components"]["agents"]["files"]
        expected = f"plugins/autonomous-dev/agents/{AGENT_NAME}.md"
        assert expected in files, f"{expected} missing from install manifest"

    def test_manifest_agent_list_stays_sorted(self):
        files = json.loads(MANIFEST.read_text())["components"]["agents"]["files"]
        assert files == sorted(files), "Manifest agents list must stay sorted"

    def test_library_registered_in_install_manifest(self):
        files = json.loads(MANIFEST.read_text())["components"]["lib"]["files"]
        expected = "plugins/autonomous-dev/lib/alignment_classifier.py"
        assert expected in files, f"{expected} missing from install manifest"

    def test_needs_scope_decision_label_in_setup_script(self):
        script = (_PLUGIN_ROOT / "scripts" / "setup-labels.sh").read_text()
        assert f"gh label create {LABEL}" in script, (
            f"setup-labels.sh must create the {LABEL} label idempotently"
        )
        assert "|| echo" in script, "Label creation must be idempotent"

    def test_drain_runner_marks_subprocess_noninteractive(self):
        source = (_LIB_DIR / "drain_runner.py").read_text()
        assert "AUTONOMOUS_DEV_NONINTERACTIVE" in source, (
            "drain_runner._build_env must export AUTONOMOUS_DEV_NONINTERACTIVE so "
            "the alignment gate never blocks an autonomous drain on a user prompt."
        )


# ---------------------------------------------------------------------------
# 4. PROJECT.md INVARIANTS section
# ---------------------------------------------------------------------------


class TestProjectMdInvariants:
    """The INVARIANTS section is the source of truth for architecture deltas."""

    def _project_md(self) -> str:
        return (_REPO_ROOT / ".claude" / "PROJECT.md").read_text()

    def test_architecture_header_renamed(self):
        content = self._project_md()
        assert "## ARCHITECTURE (Solution-on-a-Page)" in content
        assert "## ARCHITECTURE (high level)" not in content

    def test_invariants_subsection_present(self):
        assert "### INVARIANTS" in self._project_md()

    @pytest.mark.parametrize("inv", [f"INV-{n}" for n in range(1, 9)])
    def test_all_eight_invariants_present(self, inv: str):
        assert f"**{inv} —" in self._project_md(), f"{inv} missing from PROJECT.md"

    def test_invariants_parse_into_project_doc(self):
        from alignment_classifier import parse_project_md

        doc = parse_project_md(_REPO_ROOT / ".claude" / "PROJECT.md")
        assert doc.has_invariants is True
        assert len(doc.invariants) >= 8

    def test_volatile_detail_is_declared_non_invariant(self):
        """Component counts must be explicitly excluded from the invariant set."""
        content = self._project_md()
        assert "explicitly NOT invariant" in content

    def test_project_md_still_passes_structural_validators(self, tmp_path):
        """INVARIANTS must not trip the forbidden-section or required-section checks."""
        from validate_project_alignment import (
            check_forbidden_sections,
            check_required_sections,
            check_scope_alignment,
        )

        content = self._project_md()
        ok_forbidden, msg_forbidden = check_forbidden_sections(content)
        assert ok_forbidden, msg_forbidden

        # Isolate our file: check_required_sections prefers <root>/PROJECT.md,
        # so stage only .claude/PROJECT.md in a scratch root.
        staged = tmp_path / ".claude"
        staged.mkdir()
        (staged / "PROJECT.md").write_text(content)

        ok_required, msg_required = check_required_sections(tmp_path)
        assert ok_required, msg_required

        ok_scope, msg_scope = check_scope_alignment(tmp_path)
        assert ok_scope, msg_scope


# ---------------------------------------------------------------------------
# 5. Shipped greenfield templates must be architecture-safe by default (#1489)
# ---------------------------------------------------------------------------


class TestGreenfieldTemplateInvariants:
    """A fresh, uncustomized repo must never architecture-block on placeholders.

    The templates ship generic placeholder invariants written as a NUMBERED list
    (not ``- `` bullets), so ``parse_project_md`` reports ``has_invariants=False``
    until a maintainer converts them to real ``- **INV-N — Property.** ...``
    bullets. This preserves the safe default: no INVARIANTS => never blocked on
    the architecture-delta axis (Issue #1489, Decision 4).
    """

    _TEMPLATES = (
        _PLUGIN_ROOT / "templates" / "PROJECT.md",
        _PLUGIN_ROOT / "templates" / "PROJECT.md.template",
    )

    @pytest.mark.parametrize("template_path", _TEMPLATES, ids=lambda p: p.name)
    def test_shipped_template_yields_no_invariants(self, template_path: Path):
        from alignment_classifier import parse_project_md

        doc = parse_project_md(template_path)
        assert doc.has_invariants is False, (
            f"{template_path} parses has_invariants=True — a fresh repo would "
            "architecture-block on placeholder invariants. Placeholders MUST be a "
            "numbered list, never '- ' bullets (Issue #1489, Decision 4)."
        )

    def test_derived_bullet_format_parses(self):
        """Real derived invariants (bullets under ## ARCHITECTURE) activate the gate."""
        from alignment_classifier import parse_project_md_text

        text = (
            "## ARCHITECTURE (Solution-on-a-Page)\n\n"
            "### INVARIANTS\n\n"
            "- **INV-1 — X.** y\n"
        )
        doc = parse_project_md_text(text)
        assert doc.has_invariants is True
        assert doc.invariants, "Derived bullet-format invariants must be non-empty"

    def test_invariants_outside_architecture_not_detected(self):
        """INVARIANTS must live UNDER ## ARCHITECTURE, not at top level, to count."""
        from alignment_classifier import parse_project_md_text

        text = "## INVARIANTS\n- **INV-1 — X.** y"
        doc = parse_project_md_text(text)
        assert doc.has_invariants is False, (
            "A top-level ## INVARIANTS section (outside the ARCHITECTURE block) "
            "must not activate architecture-delta checking."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
