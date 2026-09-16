"""Tests for Issue #725: doc-master minimum prompt violation in implement.md.

Bug (#725): In implement.md, doc-master was invoked with only 58-63 words
(STEP 10 parallel, STEP 10c sequential, STEP L4 light mode). The 80-word
minimum enforced by implement-batch.md for security-critical agents was not
being met because implement.md had no structured prompt templates for
doc-master — just a one-line inline comment.

Fix:
1. Added >= 80 word prompt templates at each doc-master invocation point in
   implement.md (STEP 10 parallel, STEP 10c sequential, STEP L4 light).
2. Expanded implement-batch.md 80-word requirement to include doc-master,
   implementer, and planner (all agents in COMPRESSION_CRITICAL_AGENTS).

Validates:
1. implement.md STEP 10 doc-master template contains DOC-DRIFT-VERDICT
2. implement.md STEP 10c doc-master template contains DOC-DRIFT-VERDICT
3. implement.md STEP L4 doc-master template contains DOC-DRIFT-VERDICT
4. implement.md doc-master templates each have >= 80 words of template text
5. implement-batch.md lists doc-master in the 80-word requirement
"""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
IMPLEMENT_CMD_PATH = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"
BATCH_CMD_PATH = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement-batch.md"

MIN_CRITICAL_AGENT_PROMPT_WORDS = 80

# Issue #1773: verdict tokens the dispatch templates used to request. The parser at
# lib/doc_verdict_validator.py rejects all three (measured: found=False), so a
# doc-master run that obeyed the old templates emitted a label outside the canonical
# contract declared in agents/doc-master.md section 'Step 5: Output Verdict'.
RETIRED_VERDICT_TOKENS = ("DOCS-UPDATED", "NO-UPDATE-NEEDED", "DOCS-DRIFT-FOUND")

# A verdict DECLARATION is the field name immediately followed by a token value.
# See test_no_template_declares_verdict_values for why this differs from a bare
# mention of the word PASS in explanatory prose.
VERDICT_DECLARATION_RE = re.compile(r"DOC-DRIFT-VERDICT:\s*(PASS|FAIL)", re.IGNORECASE)

# Path to the canonical role definition the templates must point at.
DOC_MASTER_AGENT_REL = "agents/doc-master.md"


def _extract_doc_master_prompt_blocks(content: str) -> list[str]:
    """Extract all doc-master prompt template blocks from a file.

    Finds all prompt blocks for doc-master agents and returns the template
    text excluding placeholder markers (content inside square brackets).

    Args:
        content: Full file content of implement.md.

    Returns:
        List of template texts (one per doc-master prompt block found).
    """
    prompt_blocks = re.findall(
        r'subagent_type:\s*"doc-master".*?prompt:\s*"(.*?)"',
        content,
        re.DOTALL,
    )
    results = []
    for block in prompt_blocks:
        # Remove placeholder markers: [any text inside brackets]
        template_text = re.sub(r"\[.*?\]", "", block)
        results.append(template_text)
    return results


def _count_words(text: str) -> int:
    """Count non-empty words in text.

    Args:
        text: Input text.

    Returns:
        Number of words.
    """
    return len([w for w in text.split() if w.strip()])


class TestImplementDocMasterPromptMinimum:
    """Regression test: Issue #725 — doc-master prompts in implement.md must have >= 80 words.

    Bug: doc-master invocations in STEP 10, STEP 10c, and STEP L4 had only
    58-63 words, violating the minimum set in implement-batch.md.
    Fix: Structured prompt templates added at each invocation point.
    """

    @pytest.fixture
    def implement_content(self) -> str:
        """Read implement.md content."""
        assert IMPLEMENT_CMD_PATH.exists(), f"implement.md not found at {IMPLEMENT_CMD_PATH}"
        return IMPLEMENT_CMD_PATH.read_text(encoding="utf-8")

    def test_doc_master_prompt_blocks_exist(self, implement_content: str) -> None:
        """implement.md must have at least 3 doc-master prompt template blocks.

        There are three invocation points: STEP 10 parallel, STEP 10c sequential,
        STEP L4 light mode. All three must have structured templates.
        """
        blocks = _extract_doc_master_prompt_blocks(implement_content)
        assert len(blocks) >= 3, (
            f"implement.md has only {len(blocks)} doc-master prompt template block(s). "
            f"Expected at least 3 (STEP 10 parallel, STEP 10c sequential, STEP L4 light). "
            f"Issue #725: each invocation point needs a structured prompt template."
        )

    def test_all_doc_master_prompts_meet_minimum(self, implement_content: str) -> None:
        """All doc-master prompt templates must contain >= 80 words excluding placeholders.

        This is the regression test for Issue #725. Without the fix, each
        invocation had only 58-63 words. With the fix, each has >= 80.
        """
        blocks = _extract_doc_master_prompt_blocks(implement_content)
        assert blocks, "No doc-master prompt template blocks found in implement.md."

        for i, block in enumerate(blocks):
            word_count = _count_words(block)
            assert word_count >= MIN_CRITICAL_AGENT_PROMPT_WORDS, (
                f"Doc-master prompt template #{i + 1} has only {word_count} words "
                f"(minimum: {MIN_CRITICAL_AGENT_PROMPT_WORDS}). "
                f"Issue #725: the template must be self-sufficient (>= 80 words)."
            )

    def test_all_doc_master_prompts_contain_doc_drift_verdict(self, implement_content: str) -> None:
        """All doc-master prompt templates must name the canonical DOC-DRIFT-VERDICT field.

        Issue #1773: this assertion previously read
        ``"DOC-DRIFT-VERDICT" in block_upper or "DOCS-DRIFT" in block_upper``,
        which passed under BOTH the canonical vocabulary and the retired
        ``DOCS-*`` vocabulary. That ``or`` is why the contract mismatch survived.
        The alternative is removed: only the canonical field name satisfies this.
        """
        blocks = _extract_doc_master_prompt_blocks(implement_content)
        assert blocks, "No doc-master prompt template blocks found in implement.md."

        for i, block in enumerate(blocks):
            block_upper = block.upper()
            assert "DOC-DRIFT-VERDICT" in block_upper, (
                f"Doc-master prompt template #{i + 1} does not name DOC-DRIFT-VERDICT. "
                f"Issue #1773: the canonical field name is the only accepted form; "
                f"the retired DOCS-* tokens are not a substitute."
            )

    def test_no_template_requests_retired_verdict_tokens(self, implement_content: str) -> None:
        """No doc-master template may request a verdict token the parser rejects.

        Issue #1773 root cause: the templates instructed doc-master to emit
        DOCS-UPDATED / NO-UPDATE-NEEDED / DOCS-DRIFT-FOUND, none of which the
        regex in lib/doc_verdict_validator.py matches. An agent that obeyed the
        dispatched contract would emit a label outside the canonical contract
        declared in agents/doc-master.md section 'Step 5: Output Verdict' — the
        dispatched contract and the canonical contract disagreed. This test
        asserts the source contract, not any runtime outcome.
        """
        blocks = _extract_doc_master_prompt_blocks(implement_content)
        assert blocks, "No doc-master prompt template blocks found in implement.md."

        for i, block in enumerate(blocks):
            block_upper = block.upper()
            present = [tok for tok in RETIRED_VERDICT_TOKENS if tok in block_upper]
            assert not present, (
                f"Doc-master prompt template #{i + 1} requests retired verdict "
                f"token(s) {present}. Issue #1773: those labels are rejected by "
                f"lib/doc_verdict_validator.py and are not part of the canonical "
                f"verdict contract declared in agents/doc-master.md section "
                f"'Step 5: Output Verdict', so a template requesting them "
                f"conflicts with the canonical role. Use DOC-DRIFT-VERDICT as "
                f"declared there."
            )

    def test_templates_reference_canonical_role(self, implement_content: str) -> None:
        """Every doc-master template must point at the canonical role definition.

        The templates carry no token values of their own (Decision 3). That is
        only safe if each one names the file where the vocabulary IS defined, so
        a reader of the dispatch prompt can resolve the contract.
        """
        blocks = _extract_doc_master_prompt_blocks(implement_content)
        assert blocks, "No doc-master prompt template blocks found in implement.md."

        for i, block in enumerate(blocks):
            assert DOC_MASTER_AGENT_REL in block, (
                f"Doc-master prompt template #{i + 1} does not reference "
                f"{DOC_MASTER_AGENT_REL}. Issue #1773: templates declare no token "
                f"values, so each MUST name the canonical role definition."
            )

    def test_no_template_declares_verdict_values(self, implement_content: str) -> None:
        """No template may DECLARE verdict values; only the role definition may.

        Disambiguation rule (documented deliberately — Issue #1773):

        * A verdict DECLARATION is the field name immediately followed by a token
          value, e.g. ``DOC-DRIFT-VERDICT: PASS`` or ``DOC-DRIFT-VERDICT: FAIL(2)``.
          This is FORBIDDEN in a dispatch template because it would create a third
          source of truth alongside agents/doc-master.md Step 5 and the parser in
          lib/doc_verdict_validator.py — the exact divergence that caused #1773.
        * An explanatory MENTION of the bare word ``PASS`` or ``FAIL`` in running
          prose (for example, "this run is not a pass") is PERMITTED. It states no
          token value and cannot drift from the parser, so forbidding it would only
          push authors toward vaguer wording.

        The rule is therefore positional, not lexical: what matters is whether a
        token follows the field name, not whether the word appears anywhere.
        """
        blocks = _extract_doc_master_prompt_blocks(implement_content)
        assert blocks, "No doc-master prompt template blocks found in implement.md."

        for i, block in enumerate(blocks):
            declaration = VERDICT_DECLARATION_RE.search(block)
            assert declaration is None, (
                f"Doc-master prompt template #{i + 1} DECLARES a verdict value: "
                f"{declaration.group(0)!r}. Issue #1773: templates MUST point at "
                f"agents/doc-master.md Step 5 rather than restating token values."
            )
            assert "FAIL(" not in block.upper(), (
                f"Doc-master prompt template #{i + 1} declares the FAIL(N) literal. "
                f"Issue #1773: the FAIL(N) form is declared only in "
                f"agents/doc-master.md Step 5 and lib/doc_verdict_validator.py."
            )

    def test_all_doc_master_prompts_contain_scan_step(self, implement_content: str) -> None:
        """All doc-master prompt templates must include a SCAN step."""
        blocks = _extract_doc_master_prompt_blocks(implement_content)
        assert blocks, "No doc-master prompt template blocks found in implement.md."

        for i, block in enumerate(blocks):
            assert "scan" in block.lower() or "SCAN" in block, (
                f"Doc-master prompt template #{i + 1} does not include a SCAN step. "
                f"Issue #725: all doc-master prompts must require scanning for affected docs."
            )

    def test_all_doc_master_prompts_contain_semantic_comparison(self, implement_content: str) -> None:
        """All doc-master prompt templates must include a semantic comparison step."""
        blocks = _extract_doc_master_prompt_blocks(implement_content)
        assert blocks, "No doc-master prompt template blocks found in implement.md."

        for i, block in enumerate(blocks):
            assert "semantic" in block.lower(), (
                f"Doc-master prompt template #{i + 1} does not include a SEMANTIC COMPARISON step. "
                f"Issue #725: all doc-master prompts must require semantic comparison."
            )

    def test_step10_parallel_has_doc_master_template(self, implement_content: str) -> None:
        """STEP 10 parallel mode must have a doc-master prompt template block.

        Verifies the template is present near the STEP 10 parallel mode section.
        """
        # Find the parallel mode section and check doc-master template follows it
        parallel_idx = implement_content.find("DEFAULT: Parallel mode")
        sequential_idx = implement_content.find("SEQUENTIAL mode")
        assert parallel_idx != -1, "STEP 10 parallel mode section not found."
        assert sequential_idx != -1, "STEP 10 sequential mode section not found."

        parallel_section = implement_content[parallel_idx:sequential_idx]
        assert 'subagent_type: "doc-master"' in parallel_section, (
            "STEP 10 parallel mode section does not contain a doc-master prompt template. "
            "Issue #725: STEP 10 parallel doc-master invocation must use structured template."
        )
        assert "DOC-DRIFT-VERDICT" in parallel_section.upper(), (
            "STEP 10 parallel doc-master template must contain DOC-DRIFT-VERDICT."
        )
        retired_present = [
            tok for tok in RETIRED_VERDICT_TOKENS if tok in parallel_section.upper()
        ]
        assert not retired_present, (
            f"STEP 10 parallel section still carries retired verdict token(s) "
            f"{retired_present}. Issue #1773: the parser rejects all of them."
        )

    def test_step10c_sequential_has_doc_master_template(self, implement_content: str) -> None:
        """STEP 10c sequential mode must have a doc-master prompt template block."""
        step10c_idx = implement_content.find("STEP 10c")
        assert step10c_idx != -1, "STEP 10c section not found in implement.md."

        step11_idx = implement_content.find("STEP 11", step10c_idx)
        assert step11_idx != -1, "STEP 11 not found after STEP 10c."

        step10c_section = implement_content[step10c_idx:step11_idx]
        assert 'subagent_type: "doc-master"' in step10c_section, (
            "STEP 10c does not contain a doc-master prompt template. "
            "Issue #725: STEP 10c sequential doc-master invocation must use structured template."
        )

    def test_step_l4_light_mode_has_doc_master_template(self, implement_content: str) -> None:
        """STEP L4 light mode must have a doc-master prompt template block."""
        stepl4_idx = implement_content.find("STEP L4")
        assert stepl4_idx != -1, "STEP L4 section not found in implement.md."

        # Find the next section after STEP L4
        next_section_idx = implement_content.find("###", stepl4_idx + len("STEP L4"))
        if next_section_idx == -1:
            stepl4_section = implement_content[stepl4_idx:]
        else:
            stepl4_section = implement_content[stepl4_idx:next_section_idx]

        assert 'subagent_type: "doc-master"' in stepl4_section, (
            "STEP L4 does not contain a doc-master prompt template. "
            "Issue #725: STEP L4 light mode doc-master invocation must use structured template."
        )


class TestBatchDocMasterInCriticalAgents:
    """Regression test: Issue #725 — implement-batch.md must list doc-master in 80-word requirement.

    Bug: implement-batch.md only listed security-auditor and reviewer as agents
    requiring >= 80 words. Doc-master was excluded, allowing prompt compression
    across batch issues.
    """

    @pytest.fixture
    def batch_content(self) -> str:
        """Read implement-batch.md content."""
        assert BATCH_CMD_PATH.exists(), f"implement-batch.md not found at {BATCH_CMD_PATH}"
        return BATCH_CMD_PATH.read_text(encoding="utf-8")

    def test_doc_master_listed_in_80_word_requirement(self, batch_content: str) -> None:
        """implement-batch.md must list doc-master in the 80-word minimum requirement.

        This is the regression test for Issue #725. Without the fix, only
        security-auditor and reviewer were required to receive >= 80 words.
        """
        # Find the line containing the 80-word requirement
        lines_with_80_words = [
            line for line in batch_content.splitlines()
            if "80 words" in line.lower() and "must receive" in line.lower()
        ]
        assert lines_with_80_words, (
            "implement-batch.md does not contain a line requiring agents to receive 80 words. "
            "Issue #725: The 80-word minimum requirement line must exist."
        )

        # The line must include doc-master
        requirement_line = " ".join(lines_with_80_words)
        assert "doc-master" in requirement_line, (
            f"The 80-word minimum requirement line does not include 'doc-master'. "
            f"Found: {lines_with_80_words[0]!r}. "
            f"Issue #725: doc-master must be listed in the 80-word minimum requirement."
        )

    def test_implementer_listed_in_80_word_requirement(self, batch_content: str) -> None:
        """implement-batch.md must list implementer in the 80-word minimum requirement.

        All COMPRESSION_CRITICAL_AGENTS should be covered by the requirement.
        """
        lines_with_80_words = [
            line for line in batch_content.splitlines()
            if "80 words" in line.lower() and "must receive" in line.lower()
        ]
        requirement_line = " ".join(lines_with_80_words)
        assert "implementer" in requirement_line, (
            f"The 80-word minimum requirement line does not include 'implementer'. "
            f"Found: {requirement_line!r}. "
            f"Issue #725: implementer must be listed in the 80-word minimum requirement."
        )

    def test_planner_listed_in_80_word_requirement(self, batch_content: str) -> None:
        """implement-batch.md must list planner in the 80-word minimum requirement."""
        lines_with_80_words = [
            line for line in batch_content.splitlines()
            if "80 words" in line.lower() and "must receive" in line.lower()
        ]
        requirement_line = " ".join(lines_with_80_words)
        assert "planner" in requirement_line, (
            f"The 80-word minimum requirement line does not include 'planner'. "
            f"Found: {requirement_line!r}. "
            f"Issue #725: planner must be listed in the 80-word minimum requirement."
        )
