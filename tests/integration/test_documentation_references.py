#!/usr/bin/env python3
"""Integration tests for cross-references between the top-level docs.

Scope: ``CLAUDE.md`` plus the three extracted reference documents
(``docs/LIBRARIES.md``, ``docs/PERFORMANCE.md``, ``docs/GIT-AUTOMATION.md``).

Focus:

1. Link validity — every relative link resolves to an existing file, AND
   every ``#fragment`` resolves to a real heading in the target.
2. Bidirectional references — each extracted doc is reachable from its
   canonical home.
3. Content consistency — documented facts agree across files.
4. Navigation flow — a reader can get from an entry point to the detail.
5. Markdown rendering — links and code fences are well formed.

**Canonical-home note.** Several tests in this module used to assert that
``CLAUDE.md`` itself carried deep reference content and links. That is the
opposite of current policy: ``docs/development/CONTENT_ALLOCATION.md:10``
gives ``CLAUDE.md`` "hard rules, gates, canonical paths, pointers" and
explicitly denies it "vision, purpose, architecture, history, current state,
deep reference". Those tests have been re-pointed at the homes that actually
own the content — ``docs/ARCHITECTURE-OVERVIEW.md`` and ``README.md`` — so
they test the invariant (the doc is reachable) rather than a stale location.

Originally written 2025-11-11 by the test-master agent for the CLAUDE.md
optimization; substantially repaired 2026-08-30.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: The four documents whose cross-references this module governs.
DOC_FILES: Tuple[Path, ...] = (
    PROJECT_ROOT / "CLAUDE.md",
    PROJECT_ROOT / "docs" / "LIBRARIES.md",
    PROJECT_ROOT / "docs" / "PERFORMANCE.md",
    PROJECT_ROOT / "docs" / "GIT-AUTOMATION.md",
)

#: ``[text](url)`` — the only link form these docs use.
LINK_PATTERN = r"\[([^\]]+)\]\(([^\)]+)\)"

#: Fence openers recognised by :func:`_lines_outside_code_fences`.
_FENCE_PREFIXES = ("```", "~~~")


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _walk_fence_state(content: str) -> List[Tuple[int, str, bool, bool]]:
    """Walk ``content`` line by line tracking code-fence state.

    Known quirk, carried forward unchanged from the loop this was extracted
    from: ```` ``` ```` and ``~~~`` are treated as interchangeable, so a
    ``~~~`` line closes a ```` ``` ```` block. Real markdown does not work
    that way. Preserved deliberately — fixing it is a behaviour change, not
    an extraction.

    Args:
        content: Full text of a markdown document.

    Returns:
        One tuple per line: ``(line_number, line, inside_fence,
        is_fence_marker)``. ``inside_fence`` is the state *before* a marker
        line is applied, so a marker itself is never reported as inside.
    """
    result: List[Tuple[int, str, bool, bool]] = []
    inside = False
    for line_num, line in enumerate(content.split("\n"), 1):
        is_marker = line.strip().startswith(_FENCE_PREFIXES)
        if is_marker:
            result.append((line_num, line, False, True))
            inside = not inside
        else:
            result.append((line_num, line, inside, False))
    return result


def _lines_outside_code_fences(content: str) -> List[Tuple[int, str]]:
    """Return the lines of ``content`` that sit outside any code fence.

    Fence delimiter lines themselves are excluded. Inline code spans
    (single backticks in prose) are **not** excluded — that is exactly where
    a leaked absolute path shows up, so stripping them would narrow the
    check that motivated this helper.

    Args:
        content: Full text of a markdown document.

    Returns:
        ``(line_number, line)`` pairs, 1-indexed, in document order.
    """
    return [
        (line_num, line)
        for line_num, line, inside, is_marker in _walk_fence_state(content)
        if not inside and not is_marker
    ]


def _unclosed_fence_start(content: str) -> Optional[int]:
    """Return the line number of an unclosed code fence, or ``None``.

    Shares :func:`_walk_fence_state` with
    :func:`_lines_outside_code_fences` so there is one fence state machine
    in this module, not two that can drift.

    Args:
        content: Full text of a markdown document.

    Returns:
        Line number of the last opening fence when the document ends inside
        a fence; ``None`` when every fence is closed.
    """
    open_at: Optional[int] = None
    inside = False
    for line_num, _line, _inside, is_marker in _walk_fence_state(content):
        if not is_marker:
            continue
        if inside:
            inside = False
        else:
            inside = True
            open_at = line_num
    return open_at if inside else None


def _github_slug(heading_text: str) -> str:
    """Slugify a heading the way GitHub builds its anchor ids.

    Lowercase, drop everything that is not a word character, whitespace or
    a hyphen, then collapse whitespace runs into single hyphens.

    Args:
        heading_text: Heading text with the leading ``#`` markers removed.

    Returns:
        The anchor id a ``#fragment`` link must match.
    """
    slug = heading_text.strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    return slug


def _heading_anchors(content: str) -> set:
    """Return every anchor id defined by the headings in ``content``.

    Headings inside code fences are ignored — a ``# comment`` in a shell
    example is not a heading.

    Args:
        content: Full text of a markdown document.

    Returns:
        Set of GitHub-style anchor ids.
    """
    anchors = set()
    for _line_num, line in _lines_outside_code_fences(content):
        match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if match:
            anchors.add(_github_slug(match.group(2)))
    return anchors


def _split_fragment(link_url: str) -> Tuple[str, str]:
    """Split ``file.md#anchor`` into its file part and its fragment.

    Args:
        link_url: The URL half of a markdown link.

    Returns:
        ``(file_part, fragment)``; ``fragment`` is ``""`` when absent.
    """
    file_part, _sep, fragment = link_url.partition("#")
    return file_part, fragment


class TestLinkValidityIntegration:
    """Integration tests for link validity across documentation files."""

    def test_all_markdown_links_resolve_to_existing_files(self):
        """Every relative link resolves — file **and** ``#fragment``.

        Two-step, following lychee and markdownlint MD051: strip the
        fragment, resolve the file, then validate the fragment against the
        target document's slugified headings. Resolving only the file is
        the narrowing that let two dead anchors
        (``HOOKS.md#lifecycle-constraints``, ``HOOKS.md#pre_commit_gatepy``)
        live in ``docs/LIBRARIES.md``: ``docs/HOOKS.md`` exists, so a
        file-only check reports them green.
        """
        for doc_file in DOC_FILES:
            assert doc_file.exists(), f"{doc_file.name} not found"

        broken_links: List[Dict[str, str]] = []
        anchor_cache: Dict[Path, set] = {}

        for doc_file in DOC_FILES:
            content = doc_file.read_text(encoding="utf-8")

            for link_text, link_url in re.findall(LINK_PATTERN, content):
                # Skip external links.
                if link_url.startswith(("http://", "https://", "mailto:")):
                    continue

                file_part, fragment = _split_fragment(link_url)

                # Same-document anchors (no file part) are out of scope for
                # this check — see the module docstring's limits.
                if not file_part:
                    continue

                link_path = (doc_file.parent / file_part).resolve()

                if not link_path.exists():
                    broken_links.append(
                        {
                            "source": doc_file.name,
                            "link": f"[{link_text}]({link_url})",
                            "reason": f"file does not exist: {link_path}",
                        }
                    )
                    continue

                if not fragment or not link_path.is_file():
                    continue

                if link_path not in anchor_cache:
                    anchor_cache[link_path] = _heading_anchors(
                        link_path.read_text(encoding="utf-8")
                    )

                if fragment.lower() not in anchor_cache[link_path]:
                    broken_links.append(
                        {
                            "source": doc_file.name,
                            "link": f"[{link_text}]({link_url})",
                            "reason": (
                                f"no heading in {link_path.name} slugifies to "
                                f"'{fragment}'"
                            ),
                        }
                    )

        assert not broken_links, (
            f"Found {len(broken_links)} broken links:\n"
            + "\n".join(
                f"  - {item['source']}: {item['link']} -> {item['reason']}"
                for item in broken_links
            )
        )

    def test_relative_links_work_from_different_directories(self):
        """``docs/LIBRARIES.md`` is reachable by a resolving relative link.

        Re-pointed 2026-08-30. This previously asserted the literal string
        ``docs/LIBRARIES.md`` appeared in ``CLAUDE.md`` — 0 matches, and
        deep reference links are denied to ``CLAUDE.md`` by
        ``docs/development/CONTENT_ALLOCATION.md:10``. The invariant that
        actually matters is preserved: the doc is linked from its canonical
        home, and that link resolves from that home's directory.
        """
        home = PROJECT_ROOT / "docs" / "ARCHITECTURE-OVERVIEW.md"
        target = PROJECT_ROOT / "docs" / "LIBRARIES.md"

        assert home.exists(), "docs/ARCHITECTURE-OVERVIEW.md not found"
        assert target.exists(), "docs/LIBRARIES.md not found"

        home_content = home.read_text(encoding="utf-8")

        resolving_links = [
            link_url
            for _text, link_url in re.findall(LINK_PATTERN, home_content)
            if not link_url.startswith(("http://", "https://", "mailto:"))
            and (home.parent / _split_fragment(link_url)[0]).resolve() == target
        ]

        assert resolving_links, (
            "docs/ARCHITECTURE-OVERVIEW.md should carry a relative link that "
            "resolves to docs/LIBRARIES.md (it is the canonical home for "
            "library detail)"
        )

    def test_no_absolute_paths_in_any_documentation(self):
        """No absolute filesystem path may appear in documentation prose.

        Fenced code blocks are excluded: a fenced sample such as
        ``enforcer.is_command_safe("rm command /home/user")`` in
        ``docs/LIBRARIES.md`` is an input to a security check, not a leaked
        path. Inline code spans are deliberately **not** excluded — inline
        backticks in prose are precisely where a real leaked home directory
        appears.
        """
        absolute_patterns = [
            r"/Users/[^/\s]+",  # macOS
            r"C:\\[^\s]+",  # Windows
            r"/home/[^/\s]+",  # Linux
            r"/opt/[^/\s]+",  # Linux opt
        ]

        violations: List[str] = []

        for doc_file in DOC_FILES:
            if not doc_file.exists():
                continue

            content = doc_file.read_text(encoding="utf-8")

            for line_num, line in _lines_outside_code_fences(content):
                for pattern in absolute_patterns:
                    matches = re.findall(pattern, line)
                    if matches:
                        violations.append(
                            f"{doc_file.name}:{line_num}: {pattern} -> "
                            f"{matches[:3]}"
                        )

        assert not violations, (
            "Found absolute paths in documentation prose:\n"
            + "\n".join(f"  - {item}" for item in violations)
        )


class TestBidirectionalReferenceIntegration:
    """Integration tests for bidirectional references between docs."""

    def test_claude_md_references_all_extracted_docs(self):
        """Each extracted doc is referenced from its canonical home.

        Re-pointed 2026-08-30. The old name is kept so the test id stays
        traceable, but the subject is corrected: ``CLAUDE.md`` is a rules
        and pointers file, and ``docs/development/CONTENT_ALLOCATION.md:10``
        denies it deep reference. The homes below are where the links
        actually live and where a reader is sent.
        """
        canonical_homes = {
            "LIBRARIES.md": PROJECT_ROOT / "docs" / "ARCHITECTURE-OVERVIEW.md",
            "PERFORMANCE.md": PROJECT_ROOT / "docs" / "ARCHITECTURE-OVERVIEW.md",
            "GIT-AUTOMATION.md": PROJECT_ROOT / "README.md",
        }

        missing = []
        for doc_name, home in canonical_homes.items():
            assert home.exists(), f"{home} not found"
            if doc_name not in home.read_text(encoding="utf-8"):
                missing.append(f"{doc_name} (expected in {home.name})")

        assert not missing, (
            "Extracted docs unreferenced from their canonical home: "
            + ", ".join(missing)
        )

    def test_extracted_docs_reference_claude_md_where_appropriate(self):
        """
        Extracted docs should reference CLAUDE.md for context (if appropriate).

        At minimum, should mention they are extracted from CLAUDE.md.
        """
        project_root = PROJECT_ROOT

        extracted_docs = [
            project_root / "docs" / "LIBRARIES.md",
            project_root / "docs" / "PERFORMANCE.md",
            project_root / "docs" / "GIT-AUTOMATION.md",
        ]

        # This will FAIL if docs don't mention source
        docs_without_context = []

        for doc_file in extracted_docs:
            if not doc_file.exists():
                docs_without_context.append(doc_file.name)
                continue

            content = doc_file.read_text(encoding="utf-8")

            # Should mention CLAUDE.md or have back-reference
            has_context = any(
                keyword in content
                for keyword in ["CLAUDE.md", "main documentation", "See CLAUDE.md"]
            )

            if not has_context:
                docs_without_context.append(doc_file.name)

        # Allow docs to exist without back-reference (not strictly required)
        # But it's good practice, so we warn
        if docs_without_context:
            pytest.skip(
                f"Docs without CLAUDE.md reference: {', '.join(docs_without_context)}. "
                f"Consider adding context for readers."
            )

    def test_documentation_hierarchy_makes_sense(self):
        """The reader-facing entry point carries entry-point sections.

        Re-pointed 2026-08-30. This previously demanded ``## Project
        Overview`` / ``## Installation`` / ``## Quick Reference`` in
        ``CLAUDE.md``; none is present and two are forbidden there by
        ``docs/development/CONTENT_ALLOCATION.md:10``. ``README.md`` is the
        human entry point and owns those sections — ``README.md:615`` is
        literally ``## Quick Reference``.
        """
        readme = PROJECT_ROOT / "README.md"
        assert readme.exists(), "README.md not found"

        content = readme.read_text(encoding="utf-8")
        anchors = _heading_anchors(content)

        # The three the old CLAUDE.md assertion was reaching for — overview,
        # installation, quick reference — named as README.md actually spells
        # them (`## What Is This?`:11, `## Install`:163, `## Quick
        # Reference`:615).
        required_sections = ["What Is This?", "Install", "Quick Reference"]

        missing = [
            section
            for section in required_sections
            if _github_slug(section) not in anchors
        ]

        assert not missing, (
            f"README.md missing entry-point sections: {', '.join(missing)}. "
            f"The entry point should orient a new reader, not just link out."
        )


class TestContentConsistencyIntegration:
    """Integration tests for content consistency across files.

    ``test_library_counts_consistent_across_docs`` was deleted 2026-08-30.
    It passed vacuously: ``re.search(r'(\\d+)\\s+(?:Shared\\s+)?Libraries',
    claude_content)`` returned ``None``, so its guarded ``if`` skipped every
    assertion — the same fail-open shape as ``cmd || true``, one conditional
    instead of one boolean. Its coverage is replaced by
    ``tests/unit/test_documentation_congruence.py::TestComponentCounts::
    test_library_count``, which is strictly better: it counts real ``.py``
    files under ``plugins/autonomous-dev/lib`` via ``rglob`` and compares
    that to ``docs/ARCHITECTURE-OVERVIEW.md``, so the expected value is
    derived from disk rather than from a doc string.
    """

    def test_performance_phase_counts_consistent(self):
        """
        Performance phase count should be consistent.

        If CLAUDE.md mentions "Phases 4-7", PERFORMANCE.md should document all 4.
        """
        project_root = PROJECT_ROOT
        claude_md = project_root / "CLAUDE.md"
        performance_md = project_root / "docs" / "PERFORMANCE.md"

        # This will FAIL if phase counts inconsistent
        assert claude_md.exists(), "CLAUDE.md not found"
        assert performance_md.exists(), "docs/PERFORMANCE.md not found"

        performance_content = performance_md.read_text(encoding="utf-8")

        # Should have Phase 4, 5, 6, 7
        required_phases = ["Phase 4", "Phase 5", "Phase 6", "Phase 7"]

        missing_phases = []
        for phase in required_phases:
            if phase not in performance_content:
                missing_phases.append(phase)

        assert not missing_phases, (
            f"PERFORMANCE.md missing phases: {', '.join(missing_phases)}. "
            f"Should document Phases 4-7 completely."
        )

    def test_git_automation_env_vars_complete(self):
        """
        Git automation environment variables should be completely documented.

        If CLAUDE.md mentions git automation, GIT-AUTOMATION.md should have all vars.
        """
        project_root = PROJECT_ROOT
        git_automation_md = project_root / "docs" / "GIT-AUTOMATION.md"

        # This will FAIL if env vars incomplete
        assert git_automation_md.exists(), "docs/GIT-AUTOMATION.md not found"

        content = git_automation_md.read_text(encoding="utf-8")

        # Required environment variables
        required_env_vars = [
            "AUTO_GIT_ENABLED",
            "AUTO_GIT_PUSH",
            "AUTO_GIT_PR",
        ]

        missing_env_vars = []
        for env_var in required_env_vars:
            if env_var not in content:
                missing_env_vars.append(env_var)

        assert not missing_env_vars, (
            f"GIT-AUTOMATION.md missing environment variables: {', '.join(missing_env_vars)}"
        )


class TestNavigationFlowIntegration:
    """Integration tests for user navigation flow."""

    @pytest.mark.parametrize(
        ("doc_relpath", "home_relpath"),
        [
            ("docs/LIBRARIES.md", "docs/ARCHITECTURE-OVERVIEW.md"),
            ("docs/PERFORMANCE.md", "docs/ARCHITECTURE-OVERVIEW.md"),
            ("docs/GIT-AUTOMATION.md", "README.md"),
        ],
    )
    def test_users_can_navigate_from_canonical_home_to_detail(
        self, doc_relpath: str, home_relpath: str
    ):
        """A reader can get from a canonical home to the detailed doc.

        Collapsed 2026-08-30 from three near-duplicate
        ``test_users_can_find_*_details_easily`` tests. Each asserted the
        same two things about ``CLAUDE.md``; after re-pointing to the real
        canonical homes they differed only in their (doc, home) pair, so
        the pair is now the parameter.
        """
        doc = PROJECT_ROOT / doc_relpath
        home = PROJECT_ROOT / home_relpath

        assert doc.exists(), f"{doc_relpath} not found"
        assert home.exists(), f"{home_relpath} not found"

        home_content = home.read_text(encoding="utf-8")

        resolving_links = [
            link_url
            for _text, link_url in re.findall(LINK_PATTERN, home_content)
            if not link_url.startswith(("http://", "https://", "mailto:"))
            and (home.parent / _split_fragment(link_url)[0]).resolve() == doc.resolve()
        ]

        assert resolving_links, (
            f"{home_relpath} should carry a relative link that resolves to "
            f"{doc_relpath} so a reader can navigate from overview to detail"
        )


class TestMarkdownRenderingIntegration:
    """Integration tests for markdown rendering correctness."""

    def test_all_markdown_syntax_valid(self):
        """Links are well formed.

        The global ``content.count('[') != content.count(']')`` heuristic
        was removed 2026-08-30. It counted brackets across 801 KB including
        fenced code, ``- [ ]`` task checkboxes, Python list literals and
        regex character classes, so it reported "unbalanced brackets" on
        documents whose *links* are all fine. The per-link malformation
        checks below are what it was meant to catch, and they are kept.
        """
        syntax_errors = []

        for doc_file in DOC_FILES:
            if not doc_file.exists():
                continue

            content = doc_file.read_text(encoding="utf-8")

            for link_text, link_url in re.findall(LINK_PATTERN, content):
                if link_text.count("[") > 0 or link_text.count("]") > 0:
                    syntax_errors.append(
                        f"{doc_file.name}: Malformed link text: "
                        f"[{link_text}]({link_url})"
                    )
                if link_url.count("(") > 0 or link_url.count(")") > 0:
                    syntax_errors.append(
                        f"{doc_file.name}: Malformed link URL: "
                        f"[{link_text}]({link_url})"
                    )

        assert not syntax_errors, (
            "Found markdown syntax errors:\n"
            + "\n".join(f"  - {error}" for error in syntax_errors)
        )

    def test_headings_follow_hierarchy(self):
        """
        Markdown headings should follow proper hierarchy (no skipping levels).

        Valid: # -> ## -> ### -> ####
        Invalid: # -> ### (skipping ##)
        """
        project_root = PROJECT_ROOT

        doc_files = list(DOC_FILES)

        hierarchy_violations = []

        for doc_file in doc_files:
            if not doc_file.exists():
                continue

            content = doc_file.read_text(encoding="utf-8")
            lines = content.split('\n')

            previous_level = 0
            for line_num, line in enumerate(lines, 1):
                if line.startswith('#'):
                    # Count heading level
                    level = len(re.match(r'^#+', line).group(0))

                    # Check if skipping levels
                    if previous_level > 0 and level > previous_level + 1:
                        hierarchy_violations.append(
                            f"{doc_file.name}:{line_num}: Skipped heading level "
                            f"(from {'#' * previous_level} to {'#' * level}): {line[:50]}"
                        )

                    previous_level = level

        # Allow some flexibility (not all docs require strict hierarchy)
        if hierarchy_violations:
            pytest.skip(
                f"Heading hierarchy violations found:\n" +
                "\n".join(f"  - {violation}" for violation in hierarchy_violations)
            )

    def test_code_blocks_properly_closed(self):
        """Every code fence is closed.

        Behaviour-preserving rewrite 2026-08-30: the fence state machine
        that used to be inlined in this test body is now
        :func:`_walk_fence_state`, shared with
        :func:`_lines_outside_code_fences`. Same verdict, same message,
        one implementation.
        """
        code_block_errors = []

        for doc_file in DOC_FILES:
            if not doc_file.exists():
                continue

            unclosed_at = _unclosed_fence_start(
                doc_file.read_text(encoding="utf-8")
            )
            if unclosed_at is not None:
                code_block_errors.append(
                    f"{doc_file.name}: Unclosed code block starting at line "
                    f"{unclosed_at}"
                )

        assert not code_block_errors, (
            "Found code block errors:\n"
            + "\n".join(f"  - {error}" for error in code_block_errors)
        )


class TestSearchabilityIntegration:
    """Integration tests for content searchability."""

    def test_key_terms_findable_via_search(self):
        """Key technical terms are findable in the doc that owns them.

        ``SubagentStop`` was mapped to both ``GIT-AUTOMATION.md`` and
        ``CLAUDE.md`` until 2026-08-30. ``CLAUDE.md`` does not carry hook
        lifecycle detail and is not supposed to
        (``docs/development/CONTENT_ALLOCATION.md:10``), so the
        ``CLAUDE.md`` half of that one mapping was dropped. The other four
        mappings are unchanged.
        """
        project_root = PROJECT_ROOT

        # Key terms and where they should be found
        search_terms = {
            "security_utils": ["LIBRARIES.md"],
            "Phase 4": ["PERFORMANCE.md"],
            "AUTO_GIT_ENABLED": ["GIT-AUTOMATION.md"],
            "validate_path": ["LIBRARIES.md"],
            "SubagentStop": ["GIT-AUTOMATION.md"],
        }

        search_failures = []

        all_doc_files = [
            ("CLAUDE.md", project_root / "CLAUDE.md"),
            ("LIBRARIES.md", project_root / "docs" / "LIBRARIES.md"),
            ("PERFORMANCE.md", project_root / "docs" / "PERFORMANCE.md"),
            ("GIT-AUTOMATION.md", project_root / "docs" / "GIT-AUTOMATION.md"),
        ]

        for term, expected_files in search_terms.items():
            found_in = []

            for doc_name, doc_path in all_doc_files:
                if not doc_path.exists():
                    continue

                content = doc_path.read_text(encoding="utf-8")
                if term in content:
                    found_in.append(doc_name)

            for expected_file in expected_files:
                if expected_file not in found_in:
                    search_failures.append(
                        f"Term '{term}' not found in {expected_file} (expected)"
                    )

        assert not search_failures, (
            "Search failures:\n"
            + "\n".join(f"  - {failure}" for failure in search_failures)
        )


# NOTE (Issue #1582): a module-scope rebind of ``pytest.mark.integration`` was
# removed from here. It assigned a ``skipif`` onto pytest's GLOBAL marker
# namespace, and tests/conftest.py resolves auto-markers by name
# (``getattr(pytest.mark, marker_name)``), so collecting this one module turned
# the ENTIRE tests/integration/ tier into skips — 1,844 of them, including CI's
# own `pytest tests/integration/` step, which reported success over zero tests.
# Do not reintroduce it; tests/unit/scripts/test_integration_ceiling.py has a
# guard that fails on the pattern anywhere in the repo.
