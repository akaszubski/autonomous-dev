"""
TDD RED Phase Tests for Issue #72: Documentation Accuracy Validation

Tests that CLAUDE.md and CHANGELOG.md token counts match actual measurements
after cleanup. All tests should FAIL initially.

Test Coverage:
1. CLAUDE.md documents correct token savings
2. CHANGELOG.md includes Issue #72 entry
3. Documentation matches actual measurements
4. Token count claims are verifiable
5. Documentation follows standard format
"""

import pytest
from pathlib import Path
from typing import Dict, List, Optional
import re


# ============================================================================
# Test 1: CLAUDE.md Documents Correct Token Savings
# ============================================================================


def test_claude_md_mentions_issue_72():
    """
    Test that CLAUDE.md documents Issue #72 cleanup.

    EXPECTED TO FAIL: Documentation not updated yet.
    """
    claude_md = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/CLAUDE.md")
    content = claude_md.read_text()

    # Should mention Issue #72 or agent output cleanup
    assert "#72" in content or "Issue 72" in content or \
           "agent output cleanup" in content.lower(), \
        "CLAUDE.md should document Issue #72 cleanup"


def test_claude_md_documents_token_savings():
    """
    Test that CLAUDE.md documents token savings from cleanup.

    EXPECTED TO FAIL: Token savings not documented yet.
    """
    claude_md = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/CLAUDE.md")
    content = claude_md.read_text()

    # Should mention token savings amount
    # Look for patterns like "1,500 tokens" or "1500 tokens" or "1.5K tokens"
    token_pattern = r'\d{1,3}[,\.]?\d{0,3}\s*(tokens|K tokens)'
    matches = re.findall(token_pattern, content, re.IGNORECASE)

    assert len(matches) > 0, \
        "CLAUDE.md should document token savings with specific numbers"


def test_claude_md_token_savings_matches_actual_measurements():
    """
    Test that documented token savings match actual measurements.

    EXPECTED TO FAIL: Need to implement measurement comparison.
    """
    from scripts.measure_agent_tokens import calculate_token_savings

    # Get actual savings from measurements
    baseline_file = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/docs/metrics/baseline_tokens.json")
    post_cleanup_file = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/docs/metrics/post_cleanup_tokens.json")

    assert baseline_file.exists(), "Baseline token measurements not found"
    assert post_cleanup_file.exists(), "Post-cleanup token measurements not found"

    import json
    with open(baseline_file) as f:
        baseline = json.load(f)
    with open(post_cleanup_file) as f:
        post_cleanup = json.load(f)

    savings = calculate_token_savings(baseline, post_cleanup)
    actual_savings = savings["total_saved"]

    # Extract documented savings from CLAUDE.md
    claude_md = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/CLAUDE.md")
    content = claude_md.read_text()

    # Look for Issue #72 section and extract token number
    issue_72_section_start = content.find("#72")
    if issue_72_section_start != -1:
        section = content[issue_72_section_start:issue_72_section_start + 500]

        # Extract first number that looks like token count
        token_match = re.search(r'(\d{1,3}[,\.]?\d{0,3})\s*tokens', section, re.IGNORECASE)
        if token_match:
            documented_savings = int(token_match.group(1).replace(',', '').replace('.', ''))

            # Allow 10% tolerance for rounding
            tolerance = 0.1
            assert abs(documented_savings - actual_savings) <= actual_savings * tolerance, \
                f"Documented savings ({documented_savings}) should match actual ({actual_savings}) within {tolerance*100}%"


def test_claude_md_explains_cleanup_approach():
    """
    Test that CLAUDE.md explains the cleanup approach (Phase 1 + Phase 2).

    EXPECTED TO FAIL: Cleanup approach not documented yet.
    """
    claude_md = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/CLAUDE.md")
    content = claude_md.read_text()

    # Should explain the phased approach
    assert "phase 1" in content.lower() or "phase 2" in content.lower(), \
        "CLAUDE.md should explain phased cleanup approach"

    # Should mention adding skill references (Phase 1)
    assert "skill reference" in content.lower() or \
           "agent-output-formats" in content.lower(), \
        "CLAUDE.md should mention adding skill references"

    # Should mention streamlining sections (Phase 2)
    assert "streamline" in content.lower() or "cleanup" in content.lower() or \
           "reduce" in content.lower() or "simplify" in content.lower(), \
        "CLAUDE.md should mention streamlining Output Format sections"


def test_claude_md_maintains_correct_skill_count():
    """
    Test that CLAUDE.md still reports correct number of skills (21 active).

    EXPECTED TO FAIL: Skill count may be outdated.
    """
    claude_md = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/CLAUDE.md")
    content = claude_md.read_text()

    # Find skills section
    skills_section_start = content.find("## Skills")
    if skills_section_start != -1:
        skills_section = content[skills_section_start:skills_section_start + 1000]

        # Should mention 21 skills (no change from Issues #63, #64)
        assert "21" in skills_section, \
            "CLAUDE.md should still report 21 active skills (no change in count)"


# ============================================================================
# Test 2: CHANGELOG.md Includes Issue #72 Entry
# ============================================================================


def test_changelog_includes_issue_72_entry():
    """
    Test that CHANGELOG.md includes entry for Issue #72.

    EXPECTED TO FAIL: Changelog not updated yet.
    """
    changelog = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/CHANGELOG.md")
    content = changelog.read_text()

    assert "#72" in content or "Issue 72" in content, \
        "CHANGELOG.md should include Issue #72 entry"


def test_changelog_entry_has_correct_format():
    """
    Test that Issue #72 changelog entry follows standard format.

    EXPECTED TO FAIL: Entry doesn't exist yet or has wrong format.
    """
    changelog = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/CHANGELOG.md")
    content = changelog.read_text()

    # Find Issue #72 entry
    issue_72_start = content.find("#72")
    assert issue_72_start != -1, "Issue #72 entry not found in CHANGELOG.md"

    # Extract the line with #72
    line_start = content.rfind('\n', 0, issue_72_start) + 1
    line_end = content.find('\n', issue_72_start)
    entry_line = content[line_start:line_end]

    # Should follow format: "- feat: description (Issue #72)"
    # or similar with fix/docs/refactor
    assert entry_line.strip().startswith('-'), "Entry should be a list item"
    assert any(type_marker in entry_line for type_marker in [
        "feat:", "fix:", "docs:", "refactor:", "chore:"
    ]), "Entry should have conventional commit type"


def test_changelog_entry_describes_cleanup():
    """
    Test that Issue #72 entry describes agent output cleanup.

    EXPECTED TO FAIL: Entry doesn't exist or lacks description.
    """
    changelog = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/CHANGELOG.md")
    content = changelog.read_text()

    # Find Issue #72 section (could be multiple lines)
    issue_72_start = content.find("#72")
    assert issue_72_start != -1, "Issue #72 not in changelog"

    # Get surrounding context (200 chars before and after)
    context_start = max(0, issue_72_start - 200)
    context_end = min(len(content), issue_72_start + 300)
    context = content[context_start:context_end]

    # Should mention key aspects of cleanup
    keywords = ["agent", "output", "format", "token", "skill", "cleanup", "streamline"]
    found_keywords = [kw for kw in keywords if kw in context.lower()]

    assert len(found_keywords) >= 3, \
        f"Issue #72 entry should describe cleanup (found keywords: {found_keywords})"


def test_changelog_entry_includes_token_savings():
    """
    Test that Issue #72 entry mentions token savings.

    EXPECTED TO FAIL: Entry doesn't mention token savings yet.
    """
    changelog = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/CHANGELOG.md")
    content = changelog.read_text()

    issue_72_start = content.find("#72")
    assert issue_72_start != -1, "Issue #72 not in changelog"

    # Get context around Issue #72
    context_start = max(0, issue_72_start - 100)
    context_end = min(len(content), issue_72_start + 300)
    context = content[context_start:context_end]

    # Should mention tokens
    assert "token" in context.lower(), \
        "Issue #72 entry should mention token savings"


# ============================================================================
# Test 3: Documentation Matches Actual Measurements
# ============================================================================


def test_documentation_token_counts_are_verifiable():
    """
    Test that all token count claims in docs are verifiable.

    EXPECTED TO FAIL: Need to implement verification.
    """
    from scripts.verify_token_claims import verify_all_claims

    # Check CLAUDE.md and CHANGELOG.md
    verification_results = verify_all_claims()

    assert verification_results["all_verified"], \
        f"Some token claims unverified: {verification_results['unverified']}"


def test_token_savings_range_is_accurate():
    """
    Test that documented range (1,500-4,000 tokens) matches estimates.

    EXPECTED TO FAIL: Range may not match actual savings.
    """
    from scripts.measure_agent_tokens import calculate_token_savings

    # Get actual measurements
    baseline_file = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/docs/metrics/baseline_tokens.json")
    post_cleanup_file = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/docs/metrics/post_cleanup_tokens.json")

    if baseline_file.exists() and post_cleanup_file.exists():
        import json
        with open(baseline_file) as f:
            baseline = json.load(f)
        with open(post_cleanup_file) as f:
            post_cleanup = json.load(f)

        savings = calculate_token_savings(baseline, post_cleanup)
        actual_savings = savings["total_saved"]

        # Check if within documented range (1,500-4,000)
        assert 1500 <= actual_savings <= 4000, \
            f"Actual savings ({actual_savings}) outside documented range (1,500-4,000)"


def test_baseline_token_measurements_saved():
    """
    Test that baseline token measurements are saved for verification.

    EXPECTED TO FAIL: Baseline measurements not saved yet.
    """
    baseline_file = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/docs/metrics/baseline_tokens.json")

    assert baseline_file.exists(), \
        "Baseline token measurements should be saved in docs/metrics/"

    # Should be valid JSON
    import json
    with open(baseline_file) as f:
        baseline = json.load(f)

    assert isinstance(baseline, dict), "Baseline should be a dictionary"
    assert len(baseline) == 20, f"Baseline should have 20 agents, got {len(baseline)}"


def test_post_cleanup_token_measurements_saved():
    """
    Test that post-cleanup token measurements are saved.

    EXPECTED TO FAIL: Post-cleanup measurements not saved yet.
    """
    post_cleanup_file = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/docs/metrics/post_cleanup_tokens.json")

    assert post_cleanup_file.exists(), \
        "Post-cleanup token measurements should be saved in docs/metrics/"

    # Should be valid JSON
    import json
    with open(post_cleanup_file) as f:
        post_cleanup = json.load(f)

    assert isinstance(post_cleanup, dict), "Post-cleanup should be a dictionary"
    assert len(post_cleanup) == 20, f"Post-cleanup should have 20 agents, got {len(post_cleanup)}"


# ============================================================================
# Test 4: Token Count Claims Are Verifiable
# ============================================================================


def test_verification_script_exists():
    """
    Test that token claims verification script exists.

    EXPECTED TO FAIL: Script doesn't exist yet.
    """
    script_path = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/scripts/verify_token_claims.py")

    assert script_path.exists(), f"Verification script not found: {script_path}"


def test_verification_script_checks_claude_md():
    """
    Test that verification script validates CLAUDE.md token claims.

    EXPECTED TO FAIL: Script doesn't exist yet.
    """
    import subprocess

    result = subprocess.run(
        ["python", "scripts/verify_token_claims.py", "--check-claude-md"],
        cwd="/Users/akaszubski/Documents/GitHub/autonomous-dev",
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, f"Verification failed: {result.stderr}"
    assert "CLAUDE.md" in result.stdout


def test_verification_script_checks_changelog():
    """
    Test that verification script validates CHANGELOG.md token claims.

    EXPECTED TO FAIL: Script doesn't exist yet.
    """
    import subprocess

    result = subprocess.run(
        ["python", "scripts/verify_token_claims.py", "--check-changelog"],
        cwd="/Users/akaszubski/Documents/GitHub/autonomous-dev",
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, f"Verification failed: {result.stderr}"
    assert "CHANGELOG.md" in result.stdout


def test_verification_script_reports_discrepancies():
    """
    Test that verification script reports any discrepancies.

    EXPECTED TO FAIL: Script doesn't exist yet.
    """
    import subprocess

    result = subprocess.run(
        ["python", "scripts/verify_token_claims.py", "--all"],
        cwd="/Users/akaszubski/Documents/GitHub/autonomous-dev",
        capture_output=True,
        text=True
    )

    # Should either pass (returncode 0) or report discrepancies clearly
    if result.returncode != 0:
        assert "discrepancy" in result.stdout.lower() or \
               "mismatch" in result.stdout.lower(), \
            "Failed verification should clearly report discrepancies"


# ============================================================================
# Test 5: Documentation Follows Standard Format
# ============================================================================


def test_claude_md_issue_72_section_placement():
    """
    Test that Issue #72 is documented in appropriate section of CLAUDE.md.

    EXPECTED TO FAIL: Section placement may be incorrect.
    """
    claude_md = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/CLAUDE.md")
    content = claude_md.read_text()

    # Find Issue #72 mention
    issue_72_pos = content.find("#72")
    assert issue_72_pos != -1, "Issue #72 not found in CLAUDE.md"

    # Should be in Skills or Architecture section
    # Find which section it's in
    section_markers = [
        ("## Architecture", 0),
        ("## Skills", 0),
        ("## Agents", 0),
    ]

    for marker, _ in section_markers:
        marker_pos = content.rfind(marker, 0, issue_72_pos)
        if marker_pos != -1:
            # Found the section
            section_markers[section_markers.index((marker, _))] = (marker, marker_pos)

    # Find closest section before Issue #72
    closest_section = max(section_markers, key=lambda x: x[1])

    assert closest_section[1] > 0, "Issue #72 should be in a major section"
    assert "Skills" in closest_section[0] or "Architecture" in closest_section[0], \
        f"Issue #72 should be in Skills or Architecture section, found in {closest_section[0]}"


def test_changelog_entry_in_unreleased_section():
    """
    Test that Issue #72 entry is in [Unreleased] section if not released.

    EXPECTED TO FAIL: Entry may be in wrong section.
    """
    changelog = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/CHANGELOG.md")
    content = changelog.read_text()

    # Find [Unreleased] section
    unreleased_start = content.find("[Unreleased]")
    if unreleased_start == -1:
        pytest.skip("No [Unreleased] section in CHANGELOG.md")

    # Find next version section
    next_version = content.find("## [", unreleased_start + 1)
    if next_version == -1:
        next_version = len(content)

    unreleased_section = content[unreleased_start:next_version]

    # Issue #72 should be in unreleased section (if not released yet)
    # OR in a recent version section (if already released)
    issue_72_pos = content.find("#72")
    assert issue_72_pos != -1, "Issue #72 not in changelog"

    # Check if in unreleased or recent version
    in_unreleased = unreleased_start < issue_72_pos < next_version

    if not in_unreleased:
        # Should be in a recent version (within first 2000 chars of changelog)
        assert issue_72_pos < 2000, \
            "Issue #72 should be in [Unreleased] or recent version section"


def test_documentation_uses_consistent_terminology():
    """
    Test that docs use consistent terminology for cleanup.

    EXPECTED TO FAIL: Terminology may be inconsistent.
    """
    claude_md = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/CLAUDE.md")
    changelog = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/CHANGELOG.md")

    claude_content = claude_md.read_text()
    changelog_content = changelog.read_text()

    # Extract Issue #72 sections
    claude_72_start = claude_content.find("#72")
    changelog_72_start = changelog_content.find("#72")

    if claude_72_start != -1 and changelog_72_start != -1:
        claude_context = claude_content[claude_72_start:claude_72_start + 500]
        changelog_context = changelog_content[changelog_72_start:changelog_72_start + 300]

        # Should use similar terminology
        # Check for "agent output format" vs "output format" vs "agent format"
        claude_terms = set()
        changelog_terms = set()

        if "agent output format" in claude_context.lower():
            claude_terms.add("agent output format")
        if "output format" in claude_context.lower():
            claude_terms.add("output format")
        if "agent format" in claude_context.lower():
            claude_terms.add("agent format")

        if "agent output format" in changelog_context.lower():
            changelog_terms.add("agent output format")
        if "output format" in changelog_context.lower():
            changelog_terms.add("output format")
        if "agent format" in changelog_context.lower():
            changelog_terms.add("agent format")

        # Should have at least one term in common
        common_terms = claude_terms & changelog_terms
        assert len(common_terms) > 0, \
            "CLAUDE.md and CHANGELOG.md should use consistent terminology"


# ============================================================================
# Test 6: Version Number Updates
# ============================================================================


def test_claude_md_version_updated():
    """
    Test that CLAUDE.md version is updated for Issue #72 release.

    EXPECTED TO FAIL: Version not updated yet.
    """
    claude_md = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/CLAUDE.md")
    content = claude_md.read_text()

    # Extract version from header
    version_match = re.search(r'\*\*Version\*\*:\s*v(\d+\.\d+\.\d+)', content)
    assert version_match, "Version not found in CLAUDE.md header"

    version = version_match.group(1)

    # Should be v3.15.0 or later (Issue #72 target)
    major, minor, patch = map(int, version.split('.'))

    assert (major, minor) >= (3, 15), \
        f"Version should be v3.15.0+ for Issue #72, got v{version}"


def test_claude_md_last_updated_date():
    """
    Test that CLAUDE.md Last Updated date is recent.

    EXPECTED TO FAIL: Date may not be updated.
    """
    claude_md = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/CLAUDE.md")
    content = claude_md.read_text()

    # Extract Last Updated date
    date_match = re.search(r'\*\*Last Updated\*\*:\s*(\d{4}-\d{2}-\d{2})', content)
    assert date_match, "Last Updated date not found in CLAUDE.md"

    date_str = date_match.group(1)

    # Should be recent (within last 7 days if Issue #72 just completed)
    from datetime import datetime, timedelta
    last_updated = datetime.strptime(date_str, "%Y-%m-%d")
    now = datetime.now()

    # Allow 7 days grace period
    assert (now - last_updated).days <= 7, \
        f"Last Updated date should be recent, got {date_str}"


# ============================================================================
# Test 7: Cross-Reference Validation
# ============================================================================


def test_issue_72_mentioned_in_all_relevant_docs():
    """
    Test that Issue #72 is mentioned in all relevant documentation.

    EXPECTED TO FAIL: May not be mentioned everywhere.
    """
    relevant_docs = [
        Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/CLAUDE.md"),
        Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/CHANGELOG.md"),
    ]

    # Optional: README might mention it
    readme = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/README.md")
    if readme.exists():
        relevant_docs.append(readme)

    missing_docs = []
    for doc in relevant_docs:
        if not doc.exists():
            continue

        content = doc.read_text()
        if "#72" not in content and "Issue 72" not in content:
            missing_docs.append(doc.name)

    assert len(missing_docs) == 0, \
        f"Issue #72 should be mentioned in: {missing_docs}"


def test_documentation_links_are_valid():
    """
    Test that any links in Issue #72 documentation are valid.

    EXPECTED TO FAIL: Links may not be validated yet.
    """
    from scripts.validate_doc_links import validate_links_in_section

    # Validate links in CLAUDE.md Issue #72 section
    claude_md = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev/CLAUDE.md")
    content = claude_md.read_text()

    issue_72_start = content.find("#72")
    if issue_72_start != -1:
        # Extract section (500 chars)
        section = content[issue_72_start:issue_72_start + 500]

        # Check for any markdown links
        link_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
        links = re.findall(link_pattern, section)

        if links:
            # Validate each link
            for link_text, link_url in links:
                # If relative path, check if file exists
                if not link_url.startswith('http'):
                    link_path = Path("/Users/akaszubski/Documents/GitHub/autonomous-dev") / link_url
                    assert link_path.exists(), \
                        f"Broken link in Issue #72 docs: {link_url}"
