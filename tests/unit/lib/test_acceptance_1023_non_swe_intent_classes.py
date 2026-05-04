"""Acceptance tests for issue #1023 — non-SWE intent classes.

Adds 4 new skip-eligible intent classes to the classifier:
EXPLORATION, TRIAGE, REMOTE_OPS, SCRATCH.

Each test maps to one acceptance criterion in
``docs/plans/PLAN_1023_non_swe_intent_classes.md``.

These tests MUST FAIL before implementation and PASS after.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

# ----------------------------------------------------------------------------
# Path bootstrap (project-relative — works from any cwd)
# ----------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LIB_PATH = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"
HOOKS_PATH = PROJECT_ROOT / "plugins" / "autonomous-dev" / "hooks"
sys.path.insert(0, str(LIB_PATH))
sys.path.insert(0, str(HOOKS_PATH))

from intent_classifier import (  # noqa: E402
    IntentClass,
    IntentClassifier,
    _LLM_PROMPT_TEMPLATE,
    _VALID_LLM_INTENTS,
    _validate_template_integrity,
)
from session_mode import (  # noqa: E402
    _SKIP_INTENT_CLASSES,
    should_pipeline_enforce,
)

# ----------------------------------------------------------------------------
# Module-level constants
# ----------------------------------------------------------------------------

NEW_CLASSES: tuple[str, ...] = ("exploration", "triage", "remote_ops", "scratch")
ORIGINAL_SKIP_CLASSES: tuple[str, ...] = (
    "doc",
    "config",
    "typo",
    "status_query",
    "conversation",
)
ORIGINAL_ENUM_REAL_CLASSES = (
    "security_critical",
    "implement",
    "refactor",
    "test",
    "doc",
    "config",
    "typo",
    "status_query",
    "conversation",
)

FIXTURES_PATH = PROJECT_ROOT / "tests" / "fixtures" / "intent_classifier_fixtures.json"
TEST_INTENT_CLASSIFIER_SOURCE = (
    PROJECT_ROOT / "tests" / "unit" / "lib" / "test_intent_classifier.py"
)

DOCS_PATHS = (
    PROJECT_ROOT / "docs" / "INTENT-CLASSIFICATION.md",
    PROJECT_ROOT / "docs" / "HOOK-REGISTRY.md",
    PROJECT_ROOT / "docs" / "HOOKS.md",
)
CHANGELOG_PATH = PROJECT_ROOT / "plugins" / "autonomous-dev" / "CHANGELOG.md"


# ============================================================================
# AC #1 — IntentClass enum has 14 members; _VALID_LLM_INTENTS length is 13
# ============================================================================


def test_ac1_intent_class_enum_has_14_members() -> None:
    """13 real classes + AMBIGUOUS sentinel = 14 total."""
    assert len(list(IntentClass)) == 14, (
        f"Expected 14 IntentClass members, got {len(list(IntentClass))}"
    )


def test_ac1_valid_llm_intents_has_13_entries() -> None:
    """LLM is allowed to return one of 13 real classes (not AMBIGUOUS)."""
    assert len(_VALID_LLM_INTENTS) == 13, (
        f"Expected 13 valid LLM intents, got {len(_VALID_LLM_INTENTS)}"
    )
    assert "ambiguous" not in _VALID_LLM_INTENTS


@pytest.mark.parametrize("class_value", NEW_CLASSES)
def test_ac1_new_class_present_in_enum(class_value: str) -> None:
    """Each new class value is a member of IntentClass."""
    enum_values = {member.value for member in IntentClass}
    assert class_value in enum_values, (
        f"IntentClass missing new value '{class_value}'. Members: {sorted(enum_values)}"
    )


@pytest.mark.parametrize("class_value", NEW_CLASSES)
def test_ac1_new_class_in_valid_llm_intents(class_value: str) -> None:
    """Each new class is allowed as an LLM return value."""
    assert class_value in _VALID_LLM_INTENTS, (
        f"_VALID_LLM_INTENTS missing '{class_value}': {_VALID_LLM_INTENTS}"
    )


# ============================================================================
# AC #2 — Template declares 13 categories and contains 4 new bullets
# ============================================================================


def test_ac2_prompt_template_declares_13_categories() -> None:
    """Template header MUST say '13 fixed intent categories'."""
    assert "13 fixed intent categories" in _LLM_PROMPT_TEMPLATE, (
        "Template still references the old 9-category count"
    )


@pytest.mark.parametrize("class_value", NEW_CLASSES)
def test_ac2_template_contains_new_bullet(class_value: str) -> None:
    """Each new class label MUST appear as a bullet in the template."""
    bullet_marker = f"- {class_value}:"
    assert bullet_marker in _LLM_PROMPT_TEMPLATE, (
        f"Template missing bullet '{bullet_marker}'"
    )


def test_ac2_template_integrity_still_passes() -> None:
    """Template integrity guard (Issue #960 / OWASP LLM01:2025) MUST still pass."""
    # Should NOT raise — this is the regression lock for the user_input wrapper.
    _validate_template_integrity(_LLM_PROMPT_TEMPLATE)


# ============================================================================
# AC #3 — _SKIP_INTENT_CLASSES has exactly 9 entries
# ============================================================================


def test_ac3_skip_intent_classes_has_9_entries() -> None:
    """5 originals + 4 new = 9 skip-eligible classes."""
    assert len(_SKIP_INTENT_CLASSES) == 9, (
        f"Expected 9 skip classes, got {len(_SKIP_INTENT_CLASSES)}: "
        f"{sorted(_SKIP_INTENT_CLASSES)}"
    )


@pytest.mark.parametrize("class_value", NEW_CLASSES)
def test_ac3_new_class_in_skip_set(class_value: str) -> None:
    """Each new class MUST be in the skip frozenset."""
    assert class_value in _SKIP_INTENT_CLASSES, (
        f"'{class_value}' not in _SKIP_INTENT_CLASSES: {sorted(_SKIP_INTENT_CLASSES)}"
    )


@pytest.mark.parametrize("original_class", ORIGINAL_SKIP_CLASSES)
def test_ac3_original_skip_classes_preserved(original_class: str) -> None:
    """The 5 original skip classes MUST remain after expansion."""
    assert original_class in _SKIP_INTENT_CLASSES, (
        f"Original skip class '{original_class}' was removed"
    )


# ============================================================================
# AC #4 — should_pipeline_enforce() behaviour
# ============================================================================


@pytest.mark.parametrize("class_value", NEW_CLASSES)
def test_ac4_should_skip_for_new_classes(class_value: str) -> None:
    """New classes MUST cause should_pipeline_enforce() to return False."""
    assert should_pipeline_enforce(class_value) is False, (
        f"'{class_value}' should be skip-eligible (return False)"
    )


@pytest.mark.parametrize(
    "intent_class",
    ["ambiguous", "implement", "security_critical"],
)
def test_ac4_existing_enforce_classes_unchanged(intent_class: str) -> None:
    """Existing enforce-default classes MUST still return True."""
    assert should_pipeline_enforce(intent_class) is True, (
        f"'{intent_class}' should still trigger enforcement"
    )


@pytest.mark.parametrize("bad_input", [None, 0, 42, [], {}, object()])
def test_ac4_non_string_inputs_fail_safe_enforce(bad_input) -> None:
    """Non-string inputs MUST fail-safe to True (enforce)."""
    assert should_pipeline_enforce(bad_input) is True, (
        f"Non-string {bad_input!r} should fail-safe to True"
    )


def test_ac4_unknown_string_fail_safe_enforces() -> None:
    """Unknown intent strings MUST fail-safe to True (enforce)."""
    assert should_pipeline_enforce("totally_made_up_class") is True


# ============================================================================
# AC #5 — Security regex wins over REMOTE_OPS heuristic
# ============================================================================


def test_ac5_security_regex_wins_over_remote_ops() -> None:
    """`ssh user@host rotate-jwt` MUST classify as SECURITY_CRITICAL via regex."""
    classifier = IntentClassifier(telemetry_enabled=False)
    result = classifier.classify("ssh user@host rotate-jwt")
    assert result.intent is IntentClass.SECURITY_CRITICAL, (
        f"Expected SECURITY_CRITICAL, got {result.intent}"
    )
    assert result.regex_hit is True, "Security regex should have matched first"
    assert result.requires_security_audit is True


# ============================================================================
# AC #6 — Adversarial fixtures exist
# ============================================================================


def _load_fixtures_list() -> list[dict]:
    with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["fixtures"]


@pytest.mark.parametrize(
    "fixture_id",
    ["expl-sec-001", "scrat-sec-001", "remote-sec-001"],
)
def test_ac6_security_adversarial_fixture_present(fixture_id: str) -> None:
    """Each adversarial security fixture MUST exist and be labelled security_critical."""
    fixtures = _load_fixtures_list()
    matching = [f for f in fixtures if f.get("id") == fixture_id]
    assert matching, f"Adversarial fixture '{fixture_id}' missing from fixture file"
    assert matching[0]["label"] == "security_critical", (
        f"'{fixture_id}' must be labelled 'security_critical', "
        f"got {matching[0].get('label')!r}"
    )


def test_ac6_injection_fixture_present() -> None:
    """The literal `<user_input>` injection fixture MUST exist."""
    fixtures = _load_fixtures_list()
    matching = [f for f in fixtures if f.get("id") == "expl-injection-001"]
    assert matching, "Adversarial fixture 'expl-injection-001' missing"


# ============================================================================
# AC #7 — At least 4 fixtures per new-class prefix (excluding adversarial)
# ============================================================================


_PREFIX_BY_CLASS = {
    "exploration": "expl-",
    "triage": "triag-",
    "remote_ops": "remote-",
    "scratch": "scrat-",
}


@pytest.mark.parametrize("class_value", NEW_CLASSES)
def test_ac7_at_least_4_fixtures_per_new_class(class_value: str) -> None:
    """Each new class MUST have >= 4 non-adversarial fixtures.

    Adversarial fixtures (with `-sec-` or `-injection-` infixes) are excluded
    from the 4-per-class quota.
    """
    fixtures = _load_fixtures_list()
    prefix = _PREFIX_BY_CLASS[class_value]
    matching = [
        f
        for f in fixtures
        if isinstance(f.get("id"), str)
        and f["id"].startswith(prefix)
        and "-sec-" not in f["id"]
        and "-injection-" not in f["id"]
    ]
    assert len(matching) >= 4, (
        f"Class '{class_value}' has only {len(matching)} non-adversarial fixtures "
        f"(need >= 4). IDs found: {[f.get('id') for f in matching]}"
    )


# ============================================================================
# AC #8 — _label_to_intent map in test_intent_classifier.py has 13 entries
# ============================================================================


def test_ac8_label_to_intent_map_has_13_entries() -> None:
    """`_label_to_intent` source map MUST list 13 label→IntentClass pairs."""
    source = TEST_INTENT_CLASSIFIER_SOURCE.read_text(encoding="utf-8")

    # Locate the _label_to_intent function body. We slice to the next def to
    # avoid catching mappings elsewhere in the file.
    func_start = source.find("def _label_to_intent")
    assert func_start != -1, "Could not find _label_to_intent in source"
    next_def = source.find("\ndef ", func_start + 1)
    body = source[func_start : next_def if next_def != -1 else len(source)]

    pairs = re.findall(r'"\w+":\s*IntentClass\.\w+', body)
    assert len(pairs) == 13, (
        f"Expected 13 label→IntentClass entries in _label_to_intent, "
        f"got {len(pairs)}: {pairs}"
    )


# ============================================================================
# AC #10 — Documentation mentions the 4 new class names; CHANGELOG cites #1023
# ============================================================================


@pytest.mark.parametrize("doc_path", DOCS_PATHS, ids=lambda p: p.name)
@pytest.mark.parametrize("class_value", NEW_CLASSES)
def test_ac10_doc_mentions_new_class(doc_path: Path, class_value: str) -> None:
    """Each doc file MUST reference each new intent class as a code-formatted token.

    Intent class names are backticked when referenced as identifiers in our
    docs (e.g. ``status_query``, ``security_critical``). Requiring the
    backticked form prevents false positives from prose like "issue triage".
    """
    assert doc_path.exists(), f"Doc file missing: {doc_path}"
    content = doc_path.read_text(encoding="utf-8").lower()
    backticked = f"`{class_value}`"
    assert backticked in content, (
        f"{doc_path.name} does not reference {backticked} as an intent class"
    )


def test_ac10_changelog_mentions_issue_1023() -> None:
    """CHANGELOG MUST cite issue #1023."""
    assert CHANGELOG_PATH.exists(), f"CHANGELOG missing: {CHANGELOG_PATH}"
    content = CHANGELOG_PATH.read_text(encoding="utf-8")
    assert "#1023" in content, "CHANGELOG does not mention #1023"
