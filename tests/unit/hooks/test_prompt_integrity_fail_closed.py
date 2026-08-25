"""Fail-closed enforcement for the prompt-integrity shrinkage HARD GATE (Issue #1471).

Background — the bug this file locks out:

``validate_prompt_integrity`` in ``unified_pre_tool.py`` wrapped its entire
baseline-shrinkage block in a bare ``except Exception: pass``. When the
``PromptIntegrityResult`` field was renamed (``shrinkage_percent`` ->
``shrinkage_pct``) the hook's deny-message f-string kept reading
``result.shrinkage_pct``, which raised ``AttributeError``. The broad handler
swallowed it and execution fell through to ``return ("allow", ...)`` — so the
HARD GATE was silently fail-OPEN for every compression-critical agent.

The fix splits the handler:

* ``ImportError`` -> depends on *why* the import failed (see below).
* ``IOError`` / ``OSError`` / ``json.JSONDecodeError`` (baseline file I/O)
  -> fail OPEN, by design; disk problems must not block agents.
* Any *other* ``Exception`` -> fail CLOSED (``deny``) plus an ERROR log, because
  it means the gate itself is broken and cannot vouch for the prompt.

Second pass — the top-level import at the head of ``validate_prompt_integrity``
was left fail-OPEN and carried the same defect in a different place: an
``ImportError`` there returned ``allow`` unconditionally, so a broken or partial
``prompt_integrity`` module read as "module not installed" and every
compression-critical dispatch was waved through. That handler now separates:

* the module is genuinely **not on disk** (no resolved ``lib/``, or a ``lib/``
  without ``prompt_integrity.py``) -> fail OPEN; there is nothing to enforce.
* the module **is on disk** but did not import -> fail CLOSED; the gate cannot
  evaluate, and "I could not verify" must not be encoded as "verified, pass".

Every test below asserts on the decision AND on the presence of a log record,
because a silent failure was the whole defect.

Path depth: tests/unit/hooks/ -> parents[3] == repo root.
"""

import contextlib
import json
import logging
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
sys.path.insert(0, str(HOOK_DIR))
sys.path.insert(0, str(LIB_DIR))

import unified_pre_tool as hook
from prompt_integrity import PromptIntegrityResult


def _make_prompt(word_count: int) -> str:
    """Build a prompt with exactly ``word_count`` whitespace-separated words."""
    return " ".join(f"word{i}" for i in range(word_count))


# 150 words clears MIN_CRITICAL_AGENT_PROMPT_WORDS so execution reaches the
# baseline-shrinkage block (the code under test) rather than the floor check.
ADEQUATE_PROMPT = _make_prompt(150)

class _ImportBlocker:
    """``sys.meta_path`` finder that makes one module name unimportable.

    A ``sys.path`` shadow is not enough: the hook inserts its own ``lib/``
    directory at ``sys.path[0]`` at load time and would silently outrank the
    shadow, producing an *unfaulted* run that looks like a pass. A meta_path
    finder runs before any path-based finder, so the fault is guaranteed to land.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.hits = 0

    def find_spec(self, fullname: str, path=None, target=None):
        if fullname == self.name:
            self.hits += 1
            raise ImportError(f"test fault: {fullname} blocked by meta_path")
        return None


@contextlib.contextmanager
def _unimportable(name: str):
    """Make ``name`` raise ImportError for the duration of the block.

    Yields the blocker so a test can assert the fault actually fired — a probe
    that never fires measures nothing.
    """
    blocker = _ImportBlocker(name)
    saved = {m: sys.modules[m] for m in list(sys.modules) if m == name or m.startswith(name + ".")}
    for m in saved:
        del sys.modules[m]
    sys.meta_path.insert(0, blocker)
    try:
        yield blocker
    finally:
        sys.meta_path.remove(blocker)
        sys.modules.update(saved)


class TestImportBlockerIsAWorkingInstrument:
    """Positive and negative controls for the fault injector used below."""

    def test_blocker_actually_blocks(self) -> None:
        """Positive control: inside the block, the import really fails."""
        with _unimportable("prompt_integrity") as blocker:
            with pytest.raises(ImportError):
                __import__("prompt_integrity")
        assert blocker.hits >= 1, "Blocker never fired — the fault was not injected"

    def test_import_works_outside_the_blocker(self) -> None:
        """Negative control: without the blocker the module imports fine."""
        module = __import__("prompt_integrity")
        assert hasattr(module, "COMPRESSION_CRITICAL_AGENTS")


class TestTopLevelImportFailureFailsClosed:
    """A ``prompt_integrity`` that is ON DISK but unimportable must DENY.

    Covered class: any import-time breakage of the module the gate depends on
    — syntax error, partial module, renamed/removed symbol, broken transitive
    import. All of them previously read as "module not available" and allowed.
    """

    def test_broken_module_denies_critical_agent(self, caplog) -> None:
        with caplog.at_level(logging.ERROR):
            with _unimportable("prompt_integrity") as blocker:
                decision, reason = hook.validate_prompt_integrity(
                    "Agent",
                    {"subagent_type": "implementer", "prompt": ADEQUATE_PROMPT},
                )

        assert blocker.hits >= 1, "Fault never fired — result proves nothing"
        assert decision == "deny", (
            f"Gate failed OPEN when prompt_integrity was present-but-broken. reason={reason!r}"
        )
        assert "REQUIRED NEXT ACTION" in reason, "Refusal must state how to clear it"
        assert "ImportError" in reason, f"Refusal must name the failure: {reason!r}"
        assert ".claude/.bypass" in reason, "Refusal must name the emergency override"
        assert caplog.records, "A fail-closed refusal must leave a log trace"

    def test_broken_module_denies_even_for_non_critical_agent(self) -> None:
        """Criticality is unknowable without the module, so nothing is waved through.

        Different shape from the reproducer above: the agent is NOT on the
        compression-critical list. Without ``COMPRESSION_CRITICAL_AGENTS`` the
        gate cannot know that, and guessing "probably fine" is the defect.
        """
        with _unimportable("prompt_integrity"):
            decision, reason = hook.validate_prompt_integrity(
                "Agent",
                {"subagent_type": "test-master", "prompt": ADEQUATE_PROMPT},
            )
        assert decision == "deny", f"Unverifiable dispatch allowed. reason={reason!r}"

    def test_healthy_module_is_unaffected(self) -> None:
        """Regression control: the import branch is not taken when the module works."""
        with (
            patch("prompt_integrity.get_prompt_baseline", return_value=None),
            patch("prompt_integrity.record_prompt_baseline"),
            patch("prompt_integrity.record_batch_observation"),
            patch("prompt_integrity.get_cumulative_shrinkage", return_value=None),
        ):
            decision, reason = hook.validate_prompt_integrity(
                "Agent",
                {"subagent_type": "reviewer", "prompt": ADEQUATE_PROMPT},
            )
        assert decision == "allow", f"Healthy path regressed: {reason!r}"
        assert "failed to import" not in reason
        assert "not available" not in reason


class TestGenuinelyAbsentModuleStillAllows:
    """The permitting arm: no ``prompt_integrity.py`` on disk -> allow.

    This is the "absent by design" case the original handler was written for,
    and it must survive the fix. It is discriminated by a filesystem fact, which
    a broken import cannot fake.
    """

    def test_no_lib_dir_at_all_allows(self) -> None:
        with patch.object(hook, "LIB_DIR", None):
            with _unimportable("prompt_integrity"):
                decision, reason = hook.validate_prompt_integrity(
                    "Agent",
                    {"subagent_type": "implementer", "prompt": ADEQUATE_PROMPT},
                )
        assert decision == "allow", f"Genuinely absent module must allow. reason={reason!r}"
        assert "not available" in reason

    def test_lib_dir_without_the_module_allows(self, tmp_path: Path) -> None:
        with patch.object(hook, "LIB_DIR", tmp_path):
            with _unimportable("prompt_integrity"):
                decision, reason = hook.validate_prompt_integrity(
                    "Agent",
                    {"subagent_type": "implementer", "prompt": ADEQUATE_PROMPT},
                )
        assert decision == "allow", f"Genuinely absent module must allow. reason={reason!r}"

    def test_absence_predicate_both_arms(self, tmp_path: Path) -> None:
        """``_prompt_integrity_is_absent`` must answer differently for the two states."""
        with patch.object(hook, "LIB_DIR", None):
            assert hook._prompt_integrity_is_absent() is True
        with patch.object(hook, "LIB_DIR", tmp_path):
            assert hook._prompt_integrity_is_absent() is True
            (tmp_path / "prompt_integrity.py").write_text("# present\n")
            assert hook._prompt_integrity_is_absent() is False
        # The real install has the module on disk -> present, so an import
        # failure there means "broken", not "absent".
        assert hook._prompt_integrity_is_absent() is False


INTERNAL_ERRORS = [
    pytest.param(AttributeError("'PromptIntegrityResult' object has no attribute 'shrinkage_pct'"), id="AttributeError"),
    pytest.param(TypeError("unsupported format string passed to NoneType.__format__"), id="TypeError"),
    pytest.param(KeyError("shrinkage_pct"), id="KeyError"),
]


class TestGateInternalErrorsFailClosed:
    """Programming errors inside the gate must DENY, never silently allow."""

    @pytest.mark.parametrize("exc", INTERNAL_ERRORS)
    def test_validate_word_count_internal_error_denies(self, exc: Exception, caplog) -> None:
        """AttributeError/TypeError/KeyError from the validator must not fail open."""
        with caplog.at_level(logging.ERROR):
            with (
                patch("prompt_integrity.get_prompt_baseline", return_value=169),
                patch("prompt_integrity.validate_prompt_word_count", side_effect=exc),
            ):
                decision, reason = hook.validate_prompt_integrity(
                    "Agent",
                    {"subagent_type": "reviewer", "prompt": ADEQUATE_PROMPT},
                )

        assert decision != "allow", (
            f"Gate failed OPEN on {type(exc).__name__} — this is the Issue #1471 defect. "
            f"reason={reason!r}"
        )
        assert type(exc).__name__ in reason, (
            f"Deny message must name the failing exception type. reason={reason!r}"
        )
        assert caplog.records, "A gate-internal failure must emit a log record, not fail silently"

    def test_cumulative_shrinkage_internal_error_denies(self, caplog) -> None:
        """An AttributeError in the cumulative-drift block must also fail closed."""
        passing_result = PromptIntegrityResult(
            agent_type="reviewer",
            word_count=150,
            baseline_word_count=169,
            passed=True,
            reason="OK",
            shrinkage_pct=11.2,
            should_reload=False,
        )
        with caplog.at_level(logging.ERROR):
            with (
                patch("prompt_integrity.get_prompt_baseline", return_value=169),
                patch("prompt_integrity.validate_prompt_word_count", return_value=passing_result),
                patch("prompt_integrity.record_batch_observation"),
                patch(
                    "prompt_integrity.get_cumulative_shrinkage",
                    side_effect=AttributeError("boom"),
                ),
            ):
                decision, reason = hook.validate_prompt_integrity(
                    "Agent",
                    {"subagent_type": "reviewer", "prompt": ADEQUATE_PROMPT},
                )

        assert decision != "allow", (
            f"Cumulative-drift block failed OPEN on AttributeError. reason={reason!r}"
        )
        assert caplog.records, "Cumulative-drift failure must emit a log record"


class TestDocumentedFailOpenPreserved:
    """I/O problems are an intentional fail-open — disks must not block agents."""

    def test_baseline_io_error_still_allows(self, caplog) -> None:
        """get_prompt_baseline raising IOError keeps the documented fail-open."""
        with caplog.at_level(logging.WARNING):
            with (
                patch(
                    "prompt_integrity.get_prompt_baseline",
                    side_effect=IOError("baselines file unreadable"),
                ),
                patch("prompt_integrity.record_batch_observation"),
                patch("prompt_integrity.get_cumulative_shrinkage", return_value=None),
            ):
                decision, reason = hook.validate_prompt_integrity(
                    "Agent",
                    {"subagent_type": "reviewer", "prompt": ADEQUATE_PROMPT},
                )

        assert decision == "allow", (
            f"Baseline I/O errors must fail OPEN by design. reason={reason!r}"
        )
        assert caplog.records, "Even a fail-open path must leave a warning trace"

    def test_baseline_json_decode_error_still_allows(self, caplog) -> None:
        """A corrupt baselines JSON file is an I/O-class fault -> fail open."""
        with caplog.at_level(logging.WARNING):
            with (
                patch(
                    "prompt_integrity.get_prompt_baseline",
                    side_effect=json.JSONDecodeError("bad", "{", 0),
                ),
                patch("prompt_integrity.record_batch_observation"),
                patch("prompt_integrity.get_cumulative_shrinkage", return_value=None),
            ):
                decision, reason = hook.validate_prompt_integrity(
                    "Agent",
                    {"subagent_type": "reviewer", "prompt": ADEQUATE_PROMPT},
                )

        assert decision == "allow", (
            f"Corrupt baseline JSON must fail OPEN by design. reason={reason!r}"
        )
        assert caplog.records, "Even a fail-open path must leave a warning trace"


class TestIssue1471AttributeErrorCannotRecur:
    """Anti-regression: exercise the deny path with a REAL result object.

    The other tests use mocks, which would happily satisfy any attribute name.
    This one constructs an actual ``PromptIntegrityResult`` and drives the
    failing branch, so the deny-message f-string must read a field that really
    exists on the dataclass. If someone renames the field again without updating
    the hook, this test fails instead of the gate silently opening.
    """

    def test_real_result_renders_shrinkage_in_deny_message(self) -> None:
        failing_result = PromptIntegrityResult(
            agent_type="reviewer",
            word_count=84,
            baseline_word_count=169,
            passed=False,
            reason="Prompt for reviewer shrank 50.3% from baseline.",
            shrinkage_pct=50.3,
            should_reload=True,
        )

        # sanity: the field the hook's deny message formats must exist on the
        # real dataclass — the Issue #1471 root cause was exactly this drift.
        assert hasattr(failing_result, "shrinkage_pct"), (
            "PromptIntegrityResult must expose shrinkage_pct — the hook formats it"
        )

        with (
            patch("prompt_integrity.get_prompt_baseline", return_value=169),
            patch("prompt_integrity.validate_prompt_word_count", return_value=failing_result),
        ):
            decision, reason = hook.validate_prompt_integrity(
                "Agent",
                {"subagent_type": "reviewer", "prompt": _make_prompt(84)},
            )

        assert decision == "deny", (
            f"A real failing result must produce a deny, not a swallowed error. reason={reason!r}"
        )
        # The rendered percentage proves the f-string evaluated the real field.
        assert "50.3%" in reason, f"Deny message lost the shrinkage figure: {reason!r}"
        assert "REQUIRED NEXT ACTION" in reason
        assert "get_agent_prompt_template" in reason
