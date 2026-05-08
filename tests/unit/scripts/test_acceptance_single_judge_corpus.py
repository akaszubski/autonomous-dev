"""Acceptance criteria for the single-judge intent corpus refactor.

These tests are pure static checks — they inspect file contents, run regex
matches, and compare strings. No LLM judgment is required, so no
``@pytest.mark.genai`` decorator is applied.

The tests encode the contract of the upcoming refactor that converts
``scripts/extract_and_label_intent_corpus.py`` from a two-judge pipeline
(Anthropic SDK + OpenRouter API) into a single-judge pipeline that calls
``claude -p`` via ``subprocess.run``. Per-entry schema collapses
``judge_a``/``judge_b`` into a single ``judge`` field. The
``OPENROUTER_API_KEY`` dependency is removed.

These tests are EXPECTED TO FAIL until the refactor lands. They define what
"done" looks like for the implementer agent.

Mapping of tests to acceptance criteria:

* Criterion 1 → ``test_no_api_key_env_reads``
* Criterion 2 → ``test_subprocess_invocation_shape``,
  ``test_subprocess_run_uses_stdin_input``
* Criterion 3 → ``test_uses_shutil_which_for_cli_detection``
* Criterion 4 → ``test_no_legacy_judge_field_references_in_script``,
  ``test_no_legacy_judge_field_references_in_unit_tests``,
  ``test_no_legacy_judge_field_references_in_regression_tests``
* Criterion 5 → ``test_single_judge_labeling_function_exists``,
  ``test_records_one_call_per_prompt``
* Criterion 6 → ``test_unit_tests_cover_claude_p_envelope``,
  ``test_disagreement_test_deleted``
* Criterion 7 → ``test_regression_gates_on_claude_cli``
* Criterion 8 → ``test_docs_mention_single_judge_methodology``,
  ``test_scripts_doc_updated``
* Criterion 9 → ``test_changelog_entry_exists``
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Repo root — this file is at tests/unit/scripts/test_*.py, so:
# parents[0]=scripts, parents[1]=unit, parents[2]=tests, parents[3]=repo_root
REPO_ROOT = Path(__file__).resolve().parents[3]

SCRIPT_PATH = REPO_ROOT / "scripts" / "extract_and_label_intent_corpus.py"
UNIT_TEST_PATH = (
    REPO_ROOT / "tests" / "unit" / "scripts" / "test_extract_and_label_intent_corpus.py"
)
REGRESSION_TEST_PATH = (
    REPO_ROOT / "tests" / "regression" / "test_intent_classifier_corpus.py"
)
INTENT_DOC_PATH = REPO_ROOT / "docs" / "INTENT-CLASSIFICATION.md"
SCRIPTS_DOC_PATH = REPO_ROOT / "docs" / "SCRIPTS.md"
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"


def _read(path: Path) -> str:
    """Read a file as UTF-8 text."""
    return path.read_text(encoding="utf-8")


def _skip_if_missing(path: Path) -> None:
    """Skip the calling test if ``path`` does not yet exist.

    Defense-in-depth for files that may be deleted/moved during the refactor —
    the acceptance contract still applies once the refactor lands.
    """
    if not path.exists():
        pytest.skip(f"{path} does not exist (yet); criterion will apply once it does")


# ---------------------------------------------------------------------------
# Criterion 1: No API key env reads in the script.
# ---------------------------------------------------------------------------


def test_no_api_key_env_reads() -> None:
    """Script must not read ANTHROPIC_API_KEY or OPENROUTER_API_KEY (Crit 1)."""
    src = _read(SCRIPT_PATH)
    assert 'os.environ.get("ANTHROPIC_API_KEY"' not in src, (
        "Criterion 1 violated: script still reads ANTHROPIC_API_KEY via "
        "os.environ.get. Single-judge refactor relies on `claude -p` auth, "
        "not the SDK API key."
    )
    assert 'os.environ.get("OPENROUTER_API_KEY"' not in src, (
        "Criterion 1 violated: script still reads OPENROUTER_API_KEY via "
        "os.environ.get. Single-judge refactor must drop the OpenRouter "
        "dependency entirely."
    )


# ---------------------------------------------------------------------------
# Criterion 2: subprocess invocation shape for `claude -p`.
# ---------------------------------------------------------------------------


def test_subprocess_invocation_shape() -> None:
    """Script must invoke ``claude -p`` with the expected CLI flags (Crit 2)."""
    src = _read(SCRIPT_PATH)
    required_tokens = [
        '"claude"',
        '"-p"',
        '"--output-format"',
        '"json"',
        '"--model"',
        '"--max-turns"',
        '"1"',
        '"--system-prompt"',
    ]
    missing = [tok for tok in required_tokens if tok not in src]
    assert not missing, (
        "Criterion 2 violated: script is missing expected `claude -p` cmd "
        f"tokens: {missing}. The cmd list should begin with "
        '["claude", "-p", "--output-format", "json", ...] and include '
        "--model, --max-turns 1, and --system-prompt."
    )


def test_subprocess_run_uses_stdin_input() -> None:
    """``_call_claude_p_judge`` must use subprocess.run with stdin input (Crit 2)."""
    src = _read(SCRIPT_PATH)
    match = re.search(
        r"def _call_claude_p_judge\b.*?(?=\n(?:def |class )|\Z)",
        src,
        flags=re.DOTALL,
    )
    assert match, (
        "Criterion 2 violated: function `_call_claude_p_judge` is not defined "
        "in the script. The single-judge refactor must introduce this helper "
        "to wrap `subprocess.run(['claude', '-p', ...])`."
    )
    body = match.group(0)
    for token in ("subprocess.run", "input=", "capture_output=True", "timeout="):
        assert token in body, (
            f"Criterion 2 violated: `_call_claude_p_judge` body is missing "
            f"`{token}`. The helper must call subprocess.run with input=<prompt>, "
            "capture_output=True, and a timeout=."
        )


# ---------------------------------------------------------------------------
# Criterion 3: shutil.which for CLI detection.
# ---------------------------------------------------------------------------


def test_uses_shutil_which_for_cli_detection() -> None:
    """CLI presence must be detected via ``shutil.which("claude")`` (Crit 3)."""
    src = _read(SCRIPT_PATH)
    assert "import shutil" in src, (
        "Criterion 3 violated: script does not `import shutil`. CLI detection "
        "must be done via shutil.which, not via subprocess probing."
    )
    assert 'shutil.which("claude")' in src, (
        "Criterion 3 violated: script does not call `shutil.which(\"claude\")` "
        "for CLI detection. The build_corpus path must gate on this."
    )
    assert "_check_claude_p_available" not in src, (
        "Criterion 3 violated: helper `_check_claude_p_available` still exists. "
        "Replace it with a direct shutil.which call inside build_corpus."
    )


# ---------------------------------------------------------------------------
# Criterion 4: legacy judge_a / judge_b fields are gone everywhere.
# ---------------------------------------------------------------------------


def test_no_legacy_judge_field_references_in_script() -> None:
    """Script must not reference judge_a / judge_b fields or models (Crit 4)."""
    src = _read(SCRIPT_PATH)
    forbidden = ['"judge_a"', '"judge_b"', "judge_a_model", "judge_b_model"]
    leaked = [tok for tok in forbidden if tok in src]
    assert not leaked, (
        "Criterion 4 violated: script still references legacy two-judge "
        f"identifiers: {leaked}. The per-entry schema must use a single "
        '"judge" field; judge_a/judge_b must be deleted.'
    )


def test_no_legacy_judge_field_references_in_unit_tests() -> None:
    """Unit tests must not reference judge_a / judge_b kwargs or models (Crit 4)."""
    _skip_if_missing(UNIT_TEST_PATH)
    src = _read(UNIT_TEST_PATH)
    forbidden = ["judge_a_model", "judge_b_model", 'judge_a="', 'judge_b="']
    leaked = [tok for tok in forbidden if tok in src]
    assert not leaked, (
        "Criterion 4 violated: unit tests still reference legacy two-judge "
        f"kwargs/models: {leaked}. Update fixtures and call sites to use "
        "the single `judge` field and `judge_model` parameter."
    )


def test_no_legacy_judge_field_references_in_regression_tests() -> None:
    """Regression test ``required_fields`` must use ``judge``, not judge_a/b (Crit 4)."""
    _skip_if_missing(REGRESSION_TEST_PATH)
    src = _read(REGRESSION_TEST_PATH)
    match = re.search(r"required_fields\s*=\s*\{[^}]*\}", src, flags=re.DOTALL)
    assert match, (
        "Criterion 4 violated: regression test does not declare a "
        "`required_fields = {...}` block. The per-entry schema check must "
        "exist and must require the new `judge` field."
    )
    block = match.group(0)
    assert '"judge"' in block, (
        "Criterion 4 violated: `required_fields` block does not include "
        '`"judge"`. The single-judge refactor renames judge_a/judge_b to a '
        'single "judge" field that the regression test must enforce.'
    )
    assert '"judge_a"' not in block, (
        "Criterion 4 violated: `required_fields` still references "
        '`"judge_a"`. Remove it — the per-entry schema is single-judge now.'
    )
    assert '"judge_b"' not in block, (
        "Criterion 4 violated: `required_fields` still references "
        '`"judge_b"`. Remove it — the per-entry schema is single-judge now.'
    )


# ---------------------------------------------------------------------------
# Criterion 5: single-judge labeling function with correct shape.
# ---------------------------------------------------------------------------


def test_single_judge_labeling_function_exists() -> None:
    """``label_prompts_with_single_judge`` must exist; two-judge variant gone (Crit 5)."""
    src = _read(SCRIPT_PATH)
    assert "def label_prompts_with_single_judge" in src, (
        "Criterion 5 violated: function `label_prompts_with_single_judge` is "
        "not defined. The single-judge refactor must introduce this entry "
        "point in place of `label_prompts_with_two_judges`."
    )
    assert "def label_prompts_with_two_judges" not in src, (
        "Criterion 5 violated: function `label_prompts_with_two_judges` still "
        "exists. Delete it — the script must expose only the single-judge "
        "labeller."
    )

    sig_match = re.search(
        r"def label_prompts_with_single_judge\s*\(([^)]*)\)",
        src,
        flags=re.DOTALL,
    )
    assert sig_match, (
        "Criterion 5 violated: could not parse signature of "
        "`label_prompts_with_single_judge`. Ensure the function definition "
        "is on a single recognisable line with parenthesised parameters."
    )
    params = sig_match.group(1)
    assert "judge_model" in params, (
        "Criterion 5 violated: `label_prompts_with_single_judge` signature "
        f"is missing the `judge_model` parameter. Got params: {params!r}."
    )


def test_records_one_call_per_prompt() -> None:
    """Cost tracker must record 1 call per prompt, not 2 (Crit 5)."""
    src = _read(SCRIPT_PATH)
    match = re.search(
        r"def label_prompts_with_single_judge\b.*?(?=\n(?:def |class )|\Z)",
        src,
        flags=re.DOTALL,
    )
    assert match, (
        "Criterion 5 violated: `label_prompts_with_single_judge` body not "
        "found; cannot verify cost tracking. Define the function first."
    )
    body = match.group(0)
    assert "record_calls(1)" in body, (
        "Criterion 5 violated: `label_prompts_with_single_judge` does not "
        "call `record_calls(1)`. Single-judge mode must record exactly one "
        "API call per prompt."
    )
    assert "record_calls(2)" not in body, (
        "Criterion 5 violated: `label_prompts_with_single_judge` still calls "
        "`record_calls(2)`. That accounting is for the deleted two-judge "
        "path; replace it with `record_calls(1)`."
    )


# ---------------------------------------------------------------------------
# Criterion 6: unit tests target _call_claude_p_judge and drop disagreement test.
# ---------------------------------------------------------------------------


def test_unit_tests_cover_claude_p_envelope() -> None:
    """Unit tests must mock _call_claude_p_judge, not the deleted helpers (Crit 6)."""
    _skip_if_missing(UNIT_TEST_PATH)
    src = _read(UNIT_TEST_PATH)
    assert "_call_claude_p_judge" in src, (
        "Criterion 6 violated: unit tests do not reference "
        "`_call_claude_p_judge`. Update the test suite to mock the new "
        "single-judge subprocess wrapper."
    )
    assert "_call_anthropic_judge" not in src, (
        "Criterion 6 violated: unit tests still reference "
        "`_call_anthropic_judge`. That helper is deleted in the single-judge "
        "refactor; remove its mocks and stubs from the test suite."
    )
    assert "_call_openrouter_judge" not in src, (
        "Criterion 6 violated: unit tests still reference "
        "`_call_openrouter_judge`. That helper is deleted in the single-judge "
        "refactor; remove its mocks and stubs from the test suite."
    )


def test_disagreement_test_deleted() -> None:
    """The two-judge ``test_judges_disagree_drops_entry`` test must be gone (Crit 6)."""
    _skip_if_missing(UNIT_TEST_PATH)
    src = _read(UNIT_TEST_PATH)
    assert "test_judges_disagree_drops_entry" not in src, (
        "Criterion 6 violated: `test_judges_disagree_drops_entry` still "
        "exists in the unit tests. Disagreement is meaningless under "
        "single-judge labeling — delete this test."
    )


# ---------------------------------------------------------------------------
# Criterion 7: regression gating switches to shutil.which("claude").
# ---------------------------------------------------------------------------


def test_regression_gates_on_claude_cli() -> None:
    """Regression test must gate on ``shutil.which("claude")``, not OPENROUTER_API_KEY (Crit 7)."""
    _skip_if_missing(REGRESSION_TEST_PATH)
    src = _read(REGRESSION_TEST_PATH)
    assert 'os.environ.get("OPENROUTER_API_KEY"' not in src, (
        "Criterion 7 violated: regression test still gates on "
        "`os.environ.get(\"OPENROUTER_API_KEY\"`. Switch the skip condition "
        'to `shutil.which("claude") is None`.'
    )
    assert "import shutil" in src, (
        "Criterion 7 violated: regression test does not `import shutil`. "
        "It must use shutil.which to detect the claude CLI."
    )
    assert "shutil.which" in src, (
        "Criterion 7 violated: regression test does not call `shutil.which`. "
        'The skip gate must be `shutil.which("claude") is None`.'
    )


# ---------------------------------------------------------------------------
# Criterion 8: docs describe single-judge methodology via `claude -p`.
# ---------------------------------------------------------------------------


def test_docs_mention_single_judge_methodology() -> None:
    """INTENT-CLASSIFICATION.md must describe the single-judge approach (Crit 8)."""
    src = _read(INTENT_DOC_PATH)
    assert "claude -p" in src, (
        "Criterion 8 violated: docs/INTENT-CLASSIFICATION.md does not "
        "mention `claude -p`. The methodology section must describe the "
        "subprocess-based single-judge approach."
    )

    # Either spelling is acceptable.
    has_single_judge = re.search(r"single[-\s]judge", src, flags=re.IGNORECASE)
    assert has_single_judge, (
        "Criterion 8 violated: docs/INTENT-CLASSIFICATION.md does not "
        "describe the methodology as `single-judge` (or `single judge`). "
        "Update the methodology section."
    )

    # Methodology section must not still call this two-judge.
    method_match = re.search(
        r"###\s+Methodology\b.*?(?=\n###\s|\n##\s|\Z)",
        src,
        flags=re.DOTALL,
    )
    assert method_match, (
        "Criterion 8 violated: docs/INTENT-CLASSIFICATION.md is missing a "
        "`### Methodology` section. The single-judge refactor expects this "
        "section to describe the new approach."
    )
    method_section = method_match.group(0)
    assert not re.search(r"two[-\s]judge", method_section, flags=re.IGNORECASE), (
        "Criterion 8 violated: the `### Methodology` section in "
        "docs/INTENT-CLASSIFICATION.md still uses `two-judge` phrasing. "
        "Rewrite it to describe single-judge labeling via `claude -p`."
    )


def test_scripts_doc_updated() -> None:
    """SCRIPTS.md section for the corpus script must reflect the single-judge flow (Crit 8)."""
    src = _read(SCRIPTS_DOC_PATH)
    section_match = re.search(
        r"extract_and_label_intent_corpus\.py.*?(?=\n##\s|\Z)",
        src,
        flags=re.DOTALL,
    )
    assert section_match, (
        "Criterion 8 violated: docs/SCRIPTS.md has no section for "
        "`extract_and_label_intent_corpus.py`. The single-judge refactor "
        "must update (or add) the documentation entry for this script."
    )
    section = section_match.group(0)

    has_marker = (
        "claude -p" in section
        or re.search(r"single[-\s]judge", section, flags=re.IGNORECASE) is not None
    )
    assert has_marker, (
        "Criterion 8 violated: SCRIPTS.md section for "
        "`extract_and_label_intent_corpus.py` does not mention `claude -p` "
        "or `single-judge`/`single judge`. Update the methodology summary."
    )

    assert not re.search(r"two[-\s]judge", section, flags=re.IGNORECASE), (
        "Criterion 8 violated: SCRIPTS.md section for "
        "`extract_and_label_intent_corpus.py` still uses `two-judge` "
        "phrasing. Rewrite it to reflect the single-judge approach."
    )
    assert "OPENROUTER_API_KEY" not in section, (
        "Criterion 8 violated: SCRIPTS.md section for "
        "`extract_and_label_intent_corpus.py` still mentions "
        "`OPENROUTER_API_KEY`. The single-judge refactor drops this "
        "dependency; remove the reference."
    )


# ---------------------------------------------------------------------------
# Criterion 9: changelog entry exists.
# ---------------------------------------------------------------------------


def test_changelog_entry_exists() -> None:
    """CHANGELOG must mention the single-judge / `claude -p` refactor (Crit 9)."""
    src = _read(CHANGELOG_PATH)
    src_lower = src.lower()

    has_single_judge_phrase = "single-judge" in src_lower or "single judge" in src_lower
    has_claude_p_and_judge = any(
        ("claude -p" in line.lower() and "judge" in line.lower())
        for line in src.splitlines()
    )

    assert has_single_judge_phrase or has_claude_p_and_judge, (
        "Criterion 9 violated: CHANGELOG.md has no entry mentioning the "
        "single-judge refactor. Add a line that contains either "
        "`single-judge` (or `single judge`), or both `claude -p` and "
        "`judge` on the same line."
    )
