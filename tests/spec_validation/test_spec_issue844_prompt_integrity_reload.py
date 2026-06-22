"""Spec validation tests for Issue #844: Prompt integrity reload validation.

Bug: Prompt integrity gate fires 3x per batch because (1) reloaded prompts
were not validated before re-invocation, and (2) security-auditor received
only 45 words missing all required content (implementer output, changed files,
test results).

Fix adds validate_and_reload() with bounded retry loop and validate_prompt_slots()
that checks required content markers are present before agent invocation.

Tests observable behavior against acceptance criteria ONLY.
"""

import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

_lib_path = str(REPO_ROOT / "plugins" / "autonomous-dev" / "lib")
if _lib_path not in sys.path:
    sys.path.insert(0, _lib_path)

import prompt_integrity  # noqa: E402


class TestSpec844ValidateAndReload:
    """Spec validation: validate_and_reload validates reloaded prompts."""

    def _make_agent_dir(self, tmpdir: Path, agent_type: str, word_count: int) -> Path:
        """Create a temporary agents directory with a template file."""
        agents_dir = tmpdir / "agents"
        agents_dir.mkdir(exist_ok=True)
        template = " ".join(["content"] * word_count)
        (agents_dir / f"{agent_type}.md").write_text(template, encoding="utf-8")
        return agents_dir

    def test_spec_844_1_good_prompt_returns_immediately_no_reload(self):
        """When the original prompt passes validation, no reload occurs."""
        good_prompt = " ".join(["word"] * 300)
        result = prompt_integrity.validate_and_reload(
            good_prompt,
            "reviewer",
            baseline_word_count=300,
        )
        assert result.validation.passed is True
        assert result.reload_count == 0
        assert result.prompt == good_prompt

    def test_spec_844_2_failed_prompt_triggers_reload_from_disk(self):
        """When original prompt fails, validate_and_reload reads template
        from disk and validates the reloaded version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            # Disk template is large enough to pass
            agents_dir = self._make_agent_dir(tmpdir, "reviewer", 280)

            # Original prompt is severely compressed
            compressed_prompt = " ".join(["word"] * 100)

            result = prompt_integrity.validate_and_reload(
                compressed_prompt,
                "reviewer",
                baseline_word_count=300,
                agents_dir=agents_dir,
            )

            assert result.reload_succeeded is True
            assert result.validation.passed is True
            assert result.reload_count >= 1
            # The returned prompt should be the reloaded template, not the original
            assert result.prompt != compressed_prompt

    def test_spec_844_3_reload_also_fails_reports_failure(self):
        """When both original AND reloaded prompt fail validation, the result
        reports failure -- reloaded prompt is validated, not blindly accepted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            # Disk template is also too small (simulates corruption or
            # a template that is itself below threshold)
            agents_dir = self._make_agent_dir(tmpdir, "reviewer", 50)

            compressed_prompt = " ".join(["word"] * 40)

            result = prompt_integrity.validate_and_reload(
                compressed_prompt,
                "reviewer",
                baseline_word_count=300,
                agents_dir=agents_dir,
            )

            assert result.reload_succeeded is False
            assert result.validation.passed is False

    def test_spec_844_4_bounded_retry_loop(self):
        """validate_and_reload retries are bounded by max_reload_attempts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            # Template that always fails validation
            agents_dir = self._make_agent_dir(tmpdir, "reviewer", 30)

            compressed_prompt = " ".join(["word"] * 20)

            # Test with max_reload_attempts=3
            result = prompt_integrity.validate_and_reload(
                compressed_prompt,
                "reviewer",
                baseline_word_count=300,
                max_reload_attempts=3,
                agents_dir=agents_dir,
            )

            assert result.reload_count <= 3
            assert result.reload_succeeded is False

            # Test with max_reload_attempts=1
            result_one = prompt_integrity.validate_and_reload(
                compressed_prompt,
                "reviewer",
                baseline_word_count=300,
                max_reload_attempts=1,
                agents_dir=agents_dir,
            )

            assert result_one.reload_count <= 1

    def test_spec_844_5_keeps_better_prompt_on_failure(self):
        """When all reloads fail, the result contains the prompt with the
        highest word count (best available)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            # Template has more words than original but still fails baseline check
            agents_dir = self._make_agent_dir(tmpdir, "reviewer", 70)

            # Original is even smaller
            compressed_prompt = " ".join(["word"] * 40)

            result = prompt_integrity.validate_and_reload(
                compressed_prompt,
                "reviewer",
                baseline_word_count=500,
                agents_dir=agents_dir,
            )

            # Should keep the template (70 words) over the original (40 words)
            assert result.reload_succeeded is False
            assert len(result.prompt.split()) >= 70


class TestSpec844ValidatePromptSlots:
    """Spec validation: validate_prompt_slots checks required content markers."""

    def test_spec_844_6_security_auditor_missing_all_content(self):
        """A 45-word security-auditor prompt missing implementer output,
        changed files, and test results must fail slot validation."""
        # Simulate the exact failure scenario from the bug
        short_prompt = " ".join(["review"] * 45)

        result = prompt_integrity.validate_prompt_slots("security-auditor", short_prompt)

        assert result.passed is False
        assert "implementer output" in result.missing_slots
        assert "changed files" in result.missing_slots
        assert "test results" in result.missing_slots

    def test_spec_844_7_security_auditor_with_all_content_passes(self):
        """A security-auditor prompt containing all required content markers
        must pass slot validation."""
        prompt = (
            "Review the implementer output for this change. "
            "The changed file list includes prompt_integrity.py. "
            "The test results show all passing."
        )

        result = prompt_integrity.validate_prompt_slots("security-auditor", prompt)

        assert result.passed is True
        assert len(result.missing_slots) == 0

    def test_spec_844_8_reviewer_also_requires_content_slots(self):
        """The reviewer agent also requires implementer output, changed files,
        and test results markers."""
        short_prompt = " ".join(["analyze"] * 50)

        result = prompt_integrity.validate_prompt_slots("reviewer", short_prompt)

        assert result.passed is False
        assert len(result.missing_slots) > 0

    def test_spec_844_9_non_critical_agent_always_passes_slots(self):
        """Agents without required slot definitions always pass slot validation."""
        result = prompt_integrity.validate_prompt_slots("planner", "short prompt")

        assert result.passed is True

    def test_spec_844_10_partial_content_reports_missing(self):
        """A prompt with some but not all required markers reports which
        are missing."""
        # Has implementer mention but missing changed files and test results
        prompt = "The implementer produced working code for this feature."

        result = prompt_integrity.validate_prompt_slots("security-auditor", prompt)

        assert result.passed is False
        assert "implementer output" in result.present_slots
        assert "changed files" in result.missing_slots
        assert "test results" in result.missing_slots

    def test_security_auditor_forbids_credential_quoting(self):
        """Security auditor spec contains FORBIDDEN rule against quoting credentials."""
        # Read the security-auditor.md file
        security_auditor_path = REPO_ROOT / "plugins" / "autonomous-dev" / "agents" / "security-auditor.md"
        assert security_auditor_path.exists(), f"Security auditor spec not found at {security_auditor_path}"
        
        content = security_auditor_path.read_text(encoding="utf-8")
        
        # Check for the FORBIDDEN rule about not quoting credential values
        # Look for key phrases that should be present in the rule
        content_lower = content.lower()
        
        # Check that the rule exists (case-insensitive, robust search)
        has_credential_rule = (
            "credential" in content_lower and 
            "do not quote" in content_lower
        ) or (
            "credential values" in content_lower and
            "verbatim" in content_lower
        ) or (
            "must not quote credential" in content_lower
        )
        
        assert has_credential_rule, (
            "Security auditor spec must contain FORBIDDEN rule about not quoting credential values. "
            "Expected text like: 'You MUST NOT quote credential values verbatim in finding text'"
        )
        
        # More specific check - look for the exact or similar phrasing
        forbidden_lines = [line for line in content.split('\n') if '❌' in line]
        credential_rule_found = any(
            'credential' in line.lower() and ('quote' in line.lower() or 'verbatim' in line.lower())
            for line in forbidden_lines
        )
        
        assert credential_rule_found, (
            "Security auditor spec must have a FORBIDDEN (❌) bullet specifically about not quoting credentials"
        )
