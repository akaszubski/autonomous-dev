"""Smart test routing for /implement pipeline.

Classifies changed files into categories and computes the minimal pytest
marker expression needed, skipping irrelevant test tiers.

Usage:
    from test_routing import route_tests

    result = route_tests()
    print(result["marker_expression"])  # e.g. "smoke or hooks or regression"
    print(result["skipped_tiers"])      # e.g. ["genai", "property"]

Date: 2026-03-20
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Classification patterns: (regex, category)
# Order matters -- first match wins per file
_CLASSIFICATION_PATTERNS: List[Tuple[str, str]] = [
    (r"(?:^|/)hooks/[^/]+\.py$", "hook"),
    (r"(?:^|/)agents/[^/]+\.md$", "agent_prompt"),
    (r"(?:^|/)commands/[^/]+\.md$", "command"),
    (r"(?:^|/)lib/[^/]+\.py$", "lib"),
    (r"(?:^|/)skills/[^/]+/SKILL\.md$", "skill"),
    (r"(?:^|/)install\.sh$", "install_sync"),
    (r"(?:^|/)sync[^/]*\.md$", "install_sync"),
    (r"(?:^|/)setup[^/]*\.md$", "install_sync"),
    (r"\.json$", "config"),
    (r"\.ya?ml$", "config"),
    (r"(?:^|/)docs/[^/]+\.md$", "docs_only"),
    (r"(?:^|/)README\.md$", "docs_only"),
    (r"(?:^|/)CHANGELOG\.md$", "docs_only"),
]


def classify_changes(file_paths: List[str]) -> Set[str]:
    """Classify changed files into routing categories.

    Each file is matched against known path patterns. Files that don't
    match any pattern are marked as 'unclassified', which triggers a
    full test suite run for safety.

    Args:
        file_paths: List of relative file paths (from git diff).

    Returns:
        Set of category strings (e.g. {"hook", "lib"}).
    """
    categories: Set[str] = set()

    for fpath in file_paths:
        matched = False
        for pattern, category in _CLASSIFICATION_PATTERNS:
            if re.search(pattern, fpath):
                categories.add(category)
                matched = True
                break
        if not matched:
            categories.add("unclassified")

    return categories


def get_changed_files(cwd: Optional[Path] = None) -> List[str]:
    """Get list of changed files from git diff (staged + unstaged + untracked).

    Args:
        cwd: Working directory for git commands. Defaults to current directory.

    Returns:
        List of relative file paths that have changed.
    """
    try:
        # Staged + unstaged changes
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd else None,
            timeout=30,
        )
        files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]

        # Also include untracked files
        result_untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd else None,
            timeout=30,
        )
        untracked = [
            f.strip()
            for f in result_untracked.stdout.strip().split("\n")
            if f.strip()
        ]

        all_files = list(set(files + untracked))
        if all_files:
            return sorted(all_files)

        # Fallback: when HEAD diff and untracked are both empty (e.g., all
        # changes are already committed and the coordinator cwd differs from
        # the worktree), try git diff HEAD~1 to surface the most-recent commit.
        try:
            result_fallback = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1"],
                capture_output=True,
                text=True,
                cwd=str(cwd) if cwd else None,
                timeout=30,
            )
            if result_fallback.returncode == 0:
                fallback_files = [
                    f.strip()
                    for f in result_fallback.stdout.strip().split("\n")
                    if f.strip()
                ]
                if fallback_files:
                    return sorted(set(fallback_files))
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

        return []
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


def load_routing_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load the test routing configuration.

    Args:
        config_path: Path to routing config JSON. If None, uses default
            location relative to this file.

    Returns:
        Parsed routing configuration dict.

    Raises:
        FileNotFoundError: If config file doesn't exist at the given path.
    """
    if config_path is None:
        # Default: relative to this library file
        config_path = Path(__file__).parent.parent / "config" / "test_routing_config.json"

    if not config_path.exists():
        raise FileNotFoundError(
            f"Test routing config not found: {config_path}\n"
            f"Expected JSON file with 'routing_rules' and 'tier_to_marker' keys.\n"
            f"See: plugins/autonomous-dev/config/test_routing_config.json"
        )

    return json.loads(config_path.read_text())


def compute_marker_expression(
    categories: Set[str],
    routing_config: Dict[str, Any],
) -> str:
    """Compute pytest marker expression from detected categories.

    Combines the routing rules for all detected categories into a
    union of pytest markers. Returns empty string for full suite
    (no filtering) or docs-only skip.

    Args:
        categories: Set of change categories from classify_changes().
        routing_config: Loaded routing configuration.

    Returns:
        Pytest marker expression string (e.g. "smoke or hooks or regression"),
        or empty string meaning "run all" or "run none".
    """
    routing_rules = routing_config.get("routing_rules", {})
    tier_to_marker = routing_config.get("tier_to_marker", {})
    always_smoke = routing_config.get("always_smoke", True)
    docs_only_skip_all = routing_config.get("docs_only_skip_all", True)

    # Safety fallback: unclassified or empty -> full suite
    if not categories or "unclassified" in categories:
        return ""

    # docs_only with skip_all -> no tests
    if categories == {"docs_only"} and docs_only_skip_all:
        return "__skip_all__"

    # Collect enabled tiers across all categories
    enabled_tiers: Set[str] = set()
    for category in categories:
        if category == "docs_only":
            # docs_only doesn't add tiers when mixed with other categories
            continue
        rules = routing_rules.get(category, {})
        for tier, enabled in rules.items():
            if enabled:
                enabled_tiers.add(tier)

    # Always include smoke for non-docs changes
    if always_smoke and categories - {"docs_only"}:
        enabled_tiers.add("smoke")

    # Map tiers to pytest markers
    markers: Set[str] = set()
    for tier in enabled_tiers:
        marker = tier_to_marker.get(tier, tier)
        markers.add(marker)

    if not markers:
        return ""

    return " or ".join(sorted(markers))


def get_skipped_tiers(
    categories: Set[str],
    routing_config: Dict[str, Any],
) -> List[str]:
    """Return the list of test tiers that will be skipped.

    Args:
        categories: Set of change categories from classify_changes().
        routing_config: Loaded routing configuration.

    Returns:
        Sorted list of tier names that are NOT enabled for these categories.
    """
    routing_rules = routing_config.get("routing_rules", {})
    all_tiers: Set[str] = set()
    enabled_tiers: Set[str] = set()

    # Collect all known tiers
    for rules in routing_rules.values():
        all_tiers.update(rules.keys())

    # Safety fallback: unclassified or empty -> full suite (nothing skipped)
    if not categories or "unclassified" in categories:
        return []

    # docs_only skip all
    docs_only_skip_all = routing_config.get("docs_only_skip_all", True)
    if categories == {"docs_only"} and docs_only_skip_all:
        return sorted(all_tiers)

    # Collect enabled tiers
    for category in categories:
        if category == "docs_only":
            continue
        rules = routing_rules.get(category, {})
        for tier, enabled in rules.items():
            if enabled:
                enabled_tiers.add(tier)

    # Always include smoke
    if routing_config.get("always_smoke", True) and categories - {"docs_only"}:
        enabled_tiers.add("smoke")

    skipped = all_tiers - enabled_tiers
    return sorted(skipped)


def route_tests(
    cwd: Optional[Path] = None,
    config_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """High-level API: analyze changes and return full routing decision.

    Args:
        cwd: Working directory for git diff. Defaults to current directory.
        config_path: Path to routing config. Defaults to standard location.

    Returns:
        Dict with keys:
            - changed_files: list of changed file paths
            - categories: list of detected categories
            - marker_expression: pytest -m expression (empty = full suite)
            - skipped_tiers: list of skipped tier names
            - full_suite: True if running full suite (fallback)
            - skip_all: True if docs-only change (no tests needed)
    """
    changed_files = get_changed_files(cwd)

    try:
        config = load_routing_config(config_path)
    except FileNotFoundError:
        # Fallback: run full suite if config missing
        return {
            "changed_files": changed_files,
            "categories": [],
            "marker_expression": "",
            "skipped_tiers": [],
            "full_suite": True,
            "skip_all": False,
        }

    categories = classify_changes(changed_files)
    marker_expr = compute_marker_expression(categories, config)
    skipped = get_skipped_tiers(categories, config)

    skip_all = marker_expr == "__skip_all__"
    full_suite = marker_expr == "" and not skip_all

    return {
        "changed_files": changed_files,
        "categories": sorted(categories),
        "marker_expression": "" if skip_all else marker_expr,
        "skipped_tiers": skipped,
        "full_suite": full_suite,
        "skip_all": skip_all,
        "tier_pass_rates": {},  # Populated by quality gate after test execution
    }
