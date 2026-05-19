"""Doc Drift Detector — periodic-aggregation pass for narrative-doc drift.

Sweeps every doc with ``covers:`` YAML frontmatter against actual code/component
state to detect count drift and enumeration drift across the whole repo.

Usage::

    from doc_drift_detector import detect_doc_drift
    from pathlib import Path

    findings = detect_doc_drift(Path("."))
    for f in findings:
        print(f.doc_path, f.drift_type, f.description)

Issue: #1098 (sub-issue #1 of umbrella #1075)
Date: 2026-05-18
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Import covers_index with fallback pattern
try:
    from plugins.autonomous_dev.lib.covers_index import build_covers_index
except ImportError:
    from covers_index import build_covers_index  # type: ignore[no-redef]


# =============================================================================
# Data Classes
# =============================================================================


@dataclass(frozen=True)
class DocDriftFinding:
    """A single doc-drift finding.

    Attributes:
        doc_path: Repo-relative POSIX path to the affected doc (e.g. "docs/LIBRARIES.md").
            NEVER absolute — computed via path.relative_to(project_root).as_posix().
        drift_type: One of "count_mismatch" or "enumeration_drift".
        description: Human-readable description (e.g. "Library count: docs say 216, actual 219").
        severity: "low" | "medium" | "high".
        auto_fixable: True when the fix can be applied automatically.
        line_number: 1-indexed line number of the finding, or None if not localizable.
    """

    doc_path: str
    drift_type: str
    description: str
    severity: str
    auto_fixable: bool
    line_number: Optional[int]


# =============================================================================
# Count-keyword → file-extension mapping
# =============================================================================

# Maps keyword (lower-case) to counting strategy.
# Strategy is one of: "py", "md", "dirs"
_KEYWORD_STRATEGY: dict[str, str] = {
    "libraries": "py",
    "hooks": "py",
    "agents": "md",
    "commands": "md",
    "skills": "dirs",
}

# Regex to find count claims like "216 libraries" or "30 hooks"
_COUNT_PATTERN = re.compile(
    r"(\d+)\s+(libraries|hooks|agents|skills|commands)\b",
    re.IGNORECASE,
)

# Regex for Markdown list items (unordered or ordered)
_LIST_ITEM_PATTERN = re.compile(r"^[-*]\s+(.+)|^\d+\.\s+(.+)", re.MULTILINE)

# Regex for Markdown headings
_HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+)", re.MULTILINE)


# =============================================================================
# Public API
# =============================================================================


def detect_doc_drift(project_root: Path) -> list[DocDriftFinding]:
    """Sweep all docs with ``covers:`` frontmatter for count and enumeration drift.

    Entry point for the periodic-aggregation pass. Deterministic: same input
    → byte-identical output (no timestamps, sorted enumerations, sorted file
    listings).

    Args:
        project_root: Absolute path to the repository root.

    Returns:
        Sorted list of DocDriftFinding instances, keyed by
        (doc_path, line_number or 0, drift_type).
    """
    docs_dir = project_root / "docs"
    if not docs_dir.is_dir():
        return []

    # Build covers index: source_path -> [doc_rel_path, ...]
    try:
        covers_idx = build_covers_index(docs_dir)
    except Exception:
        return []

    # Invert: doc_rel_path -> [source_paths]
    doc_to_sources: dict[str, list[str]] = {}
    for src, doc_list in sorted(covers_idx.items()):
        for doc in sorted(doc_list):
            doc_to_sources.setdefault(doc, []).append(src)

    findings: list[DocDriftFinding] = []
    for doc_rel, sources in sorted(doc_to_sources.items()):
        doc_abs = project_root / doc_rel
        if not doc_abs.exists():
            continue
        doc_rel_str = Path(doc_rel).as_posix()
        findings.extend(
            _detect_count_mismatch(doc_abs, sources, project_root, doc_rel_str)
        )
        findings.extend(
            _detect_enumeration_drift(doc_abs, sources, project_root, doc_rel_str)
        )

    return sorted(findings, key=lambda f: (f.doc_path, f.line_number or 0, f.drift_type))


# =============================================================================
# Private helpers
# =============================================================================


def _count_artifacts(covers_paths: list[str], strategy: str, project_root: Path) -> int:
    """Count actual artifacts under the covered paths using the given strategy.

    Args:
        covers_paths: List of source paths/dirs from covers frontmatter.
        strategy: One of "py" (count .py files), "md" (count .md files),
            "dirs" (count immediate subdirectories).
        project_root: Repo root for resolving relative paths.

    Returns:
        Total count of matching artifacts.
    """
    total = 0
    for cp in sorted(covers_paths):
        abs_path = project_root / cp
        if abs_path.is_dir():
            if strategy == "py":
                total += sum(1 for _ in abs_path.rglob("*.py")
                             if not _is_excluded(_, project_root))
            elif strategy == "md":
                total += sum(1 for _ in abs_path.rglob("*.md")
                             if not _is_excluded(_, project_root))
            elif strategy == "dirs":
                total += sum(1 for _ in abs_path.iterdir() if _.is_dir()
                             and not _is_excluded(_, project_root))
        elif abs_path.is_file():
            if strategy == "py" and abs_path.suffix == ".py":
                total += 1
            elif strategy == "md" and abs_path.suffix == ".md":
                total += 1
            # single file doesn't contribute to "dirs" strategy
    return total


def _is_excluded(path: Path, project_root: Path) -> bool:
    """Return True if path contains an excluded directory segment."""
    _EXCLUDED = {
        "__pycache__", ".pytest_cache", ".git", "node_modules",
        "venv", ".venv", "env", ".tox", ".nox", "archived",
        ".worktrees", "sessions", "site-packages",
    }
    try:
        rel = path.relative_to(project_root)
        return any(part in _EXCLUDED for part in rel.parts)
    except ValueError:
        return False


def _classify_severity(diff: int) -> str:
    """Map count difference to severity string.

    Args:
        diff: Absolute difference between documented and actual count.

    Returns:
        "low" for diff <= 1, "medium" for diff <= 5, "high" otherwise.
    """
    if diff <= 1:
        return "low"
    elif diff <= 5:
        return "medium"
    return "high"


def _detect_count_mismatch(
    doc_path: Path,
    covers_paths: list[str],
    project_root: Path,
    doc_rel_str: str,
) -> list[DocDriftFinding]:
    """Detect count claims in doc that disagree with actual artifact counts.

    Finds patterns like "216 libraries" and counts actual .py files under
    the covered source dirs to compare.

    Args:
        doc_path: Absolute path to the doc file.
        covers_paths: Source paths from the doc's covers frontmatter.
        project_root: Repo root for resolving relative paths.
        doc_rel_str: Repo-relative POSIX string for doc_path.

    Returns:
        List of DocDriftFinding for each count mismatch found.
    """
    try:
        content = doc_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    findings: list[DocDriftFinding] = []
    lines = content.splitlines()

    for line_idx, line in enumerate(lines, start=1):
        for match in _COUNT_PATTERN.finditer(line):
            claimed_count = int(match.group(1))
            keyword = match.group(2).lower()
            strategy = _KEYWORD_STRATEGY.get(keyword)
            if strategy is None:
                continue
            actual_count = _count_artifacts(covers_paths, strategy, project_root)
            diff = abs(claimed_count - actual_count)
            if diff == 0:
                continue
            severity = _classify_severity(diff)
            findings.append(
                DocDriftFinding(
                    doc_path=doc_rel_str,
                    drift_type="count_mismatch",
                    description=(
                        f"{keyword.capitalize()} count: docs say {claimed_count},"
                        f" actual {actual_count}"
                    ),
                    severity=severity,
                    auto_fixable=True,
                    line_number=line_idx,
                )
            )

    return findings


def _detect_enumeration_drift(
    doc_path: Path,
    covers_paths: list[str],
    project_root: Path,
    doc_rel_str: str,
) -> list[DocDriftFinding]:
    """Detect list items in doc that reference non-existent source artifacts.

    Finds Markdown lists within sections whose heading mentions a covered
    source dir name. For each listed item, checks whether a file with a
    matching stem exists under the covered dirs.

    Args:
        doc_path: Absolute path to the doc file.
        covers_paths: Source paths from the doc's covers frontmatter.
        project_root: Repo root for resolving relative paths.
        doc_rel_str: Repo-relative POSIX string for doc_path.

    Returns:
        List of DocDriftFinding for each enumeration item that has no
        corresponding source artifact.
    """
    try:
        content = doc_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    lines = content.splitlines()

    # Build set of all file stems under covered paths
    all_stems: set[str] = set()
    for cp in covers_paths:
        abs_cp = project_root / cp
        if abs_cp.is_dir():
            for f in sorted(abs_cp.rglob("*")):
                if f.is_file() and not _is_excluded(f, project_root):
                    all_stems.add(f.stem.lower())
        elif abs_cp.is_file():
            all_stems.add(abs_cp.stem.lower())

    if not all_stems:
        return []

    # Build set of dir names from covers paths to match against headings
    covered_dir_names: set[str] = set()
    for cp in covers_paths:
        abs_cp = project_root / cp
        if abs_cp.is_dir():
            covered_dir_names.add(abs_cp.name.lower())
        elif abs_cp.is_file():
            covered_dir_names.add(abs_cp.parent.name.lower())

    findings: list[DocDriftFinding] = []
    in_relevant_section = False

    for line_idx, line in enumerate(lines, start=1):
        heading_match = _HEADING_PATTERN.match(line)
        if heading_match:
            heading_text = heading_match.group(1).lower()
            in_relevant_section = any(
                dir_name in heading_text for dir_name in covered_dir_names
            )
            continue

        if not in_relevant_section:
            continue

        list_match = _LIST_ITEM_PATTERN.match(line)
        if not list_match:
            continue

        item_text = (list_match.group(1) or list_match.group(2) or "").strip()
        if not item_text:
            continue

        # Extract the item name: take first word, strip punctuation
        item_name = re.split(r"[\s:,\(\)\[\]`]", item_text)[0].strip("`").lower()
        # Strip common file extensions that might appear in the doc
        for ext in (".py", ".md", ".sh", ".json", ".yaml", ".yml"):
            if item_name.endswith(ext):
                item_name = item_name[: -len(ext)]
                break

        if not item_name:
            continue

        # Check if this name matches any known stem
        if item_name not in all_stems:
            findings.append(
                DocDriftFinding(
                    doc_path=doc_rel_str,
                    drift_type="enumeration_drift",
                    description=(
                        f"Listed item '{item_name}' has no matching source artifact"
                        f" in covered paths"
                    ),
                    severity="medium",
                    auto_fixable=False,
                    line_number=line_idx,
                )
            )

    return findings
