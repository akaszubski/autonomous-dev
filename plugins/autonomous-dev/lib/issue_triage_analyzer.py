"""Issue Triage Analyzer - Periodic-aggregation root-cause clustering for the auto-improvement queue.

Reads the open auto-improvement GitHub issues, groups them by root cause, surfaces
dependencies between clusters, and emits a ranked work queue.

Two-level clustering:
1. Primary: extract bracket tag (e.g., ``[CI]``, ``[HARDENING]``) from each issue title.
2. Secondary: within each primary bucket, group by Jaccard token similarity (>= 2 shared
   tokens) using union-find. This prevents the ``[CI]`` mega-cluster from being a useless
   77% bucket.

Idempotence guarantees:
* All collections (findings, issue numbers, shared files, dependency notes) are sorted
  deterministically.
* ``_now`` is the ONLY time-varying input. Tests pin it to a fixed datetime.
* Re-running on unchanged data produces byte-identical output.

GitHub Issue: #1099
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# Robust import of runtime_data_aggregator.fetch_open_issues_with_label
try:
    from .runtime_data_aggregator import fetch_open_issues_with_label, SourceHealth  # type: ignore
except ImportError:
    _lib_dir = Path(__file__).parent.resolve()
    if str(_lib_dir) not in sys.path:
        sys.path.insert(0, str(_lib_dir))
    from runtime_data_aggregator import fetch_open_issues_with_label, SourceHealth  # type: ignore


# =============================================================================
# Constants
# =============================================================================

STOPWORDS = frozenset({
    "a", "an", "the", "in", "on", "of", "to", "for", "and", "or", "but",
    "is", "was", "with", "by", "at", "be", "this", "that", "it", "as", "from",
})

SEVERITY_WEIGHTS: Dict[str, float] = {"low": 1.0, "medium": 1.5, "high": 2.0}
RECENCY_HALF_LIFE_DAYS = 30.0
MIN_SHARED_TOKENS = 2

# Match unix-style relative paths with at least one slash and a recognized extension.
PATH_REGEX = re.compile(r"(?:[a-zA-Z0-9_\-./]+/)+[a-zA-Z0-9_\-]+\.(?:py|md|sh|json|ya?ml|txt)")

# Bracket tag at the start of a title. Bracket content must be non-empty.
TAG_REGEX = re.compile(r"^\s*\[([^\]]+)\]")

# Severity classifications by label name substring.
HIGH_LABEL_KEYWORDS = ("critical", "p0")  # security is a topic label, not a severity signal
MEDIUM_LABEL_KEYWORDS = ("bug", "regression", "p1")

DEFAULT_REPO = "akaszubski/autonomous-dev"
DEFAULT_LIMIT = 200

FP_ACK_LABEL = "fp-acknowledged"
AUTO_IMPROVEMENT_LABEL = "auto-improvement"


# =============================================================================
# Public Data Classes
# =============================================================================


@dataclass(frozen=True)
class TriageFinding:
    """A single root-cause cluster of related auto-improvement issues.

    Attributes:
        root_cause_tag: Bracket content from the issue title (e.g., "CI"). "UNTAGGED" if no
            bracket tag could be extracted.
        sub_cluster_id: 1-indexed sub-cluster ID within ``root_cause_tag``. Sub-clusters are
            produced by Jaccard token similarity within a tag.
        issue_numbers: Sorted ASC tuple of GitHub issue numbers in the cluster.
        issue_titles: Tuple of issue titles, parallel to ``issue_numbers``.
        cluster_size: Number of issues in the cluster (``len(issue_numbers)``).
        severity: ``"low"``, ``"medium"``, or ``"high"`` based on the most severe label across
            all issues in the cluster.
        rank_score: ``cluster_size * severity_weight * recency_decay``.
        shared_files: Sorted lexicographic tuple of file paths mentioned in 2+ issue bodies.
        dependency_notes: Sorted lexicographic tuple of free-form notes describing
            cross-cluster dependencies.
        suggested_fix_order: 1-indexed global order after sorting by ``rank_score`` DESC.
    """

    root_cause_tag: str
    sub_cluster_id: int
    issue_numbers: Tuple[int, ...]
    issue_titles: Tuple[str, ...]
    cluster_size: int
    severity: str
    rank_score: float
    shared_files: Tuple[str, ...]
    dependency_notes: Tuple[str, ...]
    suggested_fix_order: int


# =============================================================================
# Pure Functions
# =============================================================================


def extract_root_cause_tag(title: str) -> str:
    """Extract the bracket tag from an issue title.

    Args:
        title: Issue title (may have leading whitespace).

    Returns:
        The verbatim bracket content (e.g., ``"CI"``, ``"CI-warning"``). Returns
        ``"UNTAGGED"`` when no bracket tag is present or the tag content is empty.
    """
    if not title:
        return "UNTAGGED"
    match = TAG_REGEX.match(title)
    if match is None:
        return "UNTAGGED"
    tag = match.group(1).strip()
    if not tag:
        return "UNTAGGED"
    return tag


def _strip_leading_tag(title: str) -> str:
    """Remove the ``[TAG]`` prefix from a title (if present) for token extraction."""
    return TAG_REGEX.sub("", title, count=1)


def extract_title_tokens(
    title: str, stopwords: Iterable[str] = STOPWORDS
) -> frozenset[str]:
    """Tokenize an issue title for Jaccard similarity comparison.

    Steps:
    1. Strip the leading ``[TAG]`` prefix.
    2. Split on any non-alphabetic character.
    3. Lowercase, drop tokens with length < 3, drop tokens in ``stopwords``.

    Args:
        title: Raw issue title.
        stopwords: Token strings to exclude.

    Returns:
        A frozenset of tokens.
    """
    if not title:
        return frozenset()
    stop = set(stopwords)
    body = _strip_leading_tag(title)
    raw_tokens = re.split(r"[^a-zA-Z]+", body)
    tokens: set[str] = set()
    for tok in raw_tokens:
        tok = tok.lower()
        if len(tok) < 3:
            continue
        if tok in stop:
            continue
        tokens.add(tok)
    return frozenset(tokens)


def cluster_within_tag(
    issues: List[Dict[str, Any]],
    min_shared_tokens: int = MIN_SHARED_TOKENS,
) -> List[List[int]]:
    """Group issues sharing >= ``min_shared_tokens`` title tokens into sub-clusters.

    Uses union-find for transitivity: if A and B share 2 tokens, and B and C share 2 tokens,
    then A, B, C are all in the same sub-cluster even if A and C share fewer tokens directly.

    Args:
        issues: List of issue dicts. Each dict MUST contain ``"number"`` (int) and
            ``"title"`` (str).
        min_shared_tokens: Minimum number of shared title tokens needed to merge two issues.

    Returns:
        A list of sub-clusters. Each sub-cluster is a list of issue numbers, sorted ASC.
        The outer list is sorted so that the sub-cluster containing the lowest issue number
        comes first (deterministic ordering).
    """
    if not issues:
        return []

    # Sort input to ensure deterministic union-find ordering.
    indexed = sorted(
        ((int(issue["number"]), str(issue.get("title", ""))) for issue in issues),
        key=lambda pair: pair[0],
    )
    numbers = [pair[0] for pair in indexed]
    token_sets = [extract_title_tokens(pair[1]) for pair in indexed]
    n = len(indexed)

    # Union-find with path compression.
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        # Lower root index wins for determinism.
        if ra < rb:
            parent[rb] = ra
        else:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            shared = len(token_sets[i] & token_sets[j])
            if shared >= min_shared_tokens:
                union(i, j)

    # Group indices by root.
    groups: Dict[int, List[int]] = {}
    for i in range(n):
        root = find(i)
        groups.setdefault(root, []).append(i)

    clusters: List[List[int]] = []
    for indices in groups.values():
        cluster = sorted(numbers[i] for i in indices)
        clusters.append(cluster)

    # Deterministic outer order: sort clusters by their minimum issue number.
    clusters.sort(key=lambda c: c[0])
    return clusters


def merge_compatible_singletons(
    findings: list[TriageFinding],
    max_size: int = 4,
) -> list[TriageFinding]:
    """Merge singleton findings with the same root cause tag into super-clusters.
    
    Singletons with the same non-UNTAGGED root_cause_tag are chunked into
    super-clusters up to max_size. Multi-issue clusters and UNTAGGED singletons
    pass through unchanged.
    
    GitHub Issue: #1250
    
    Args:
        findings: List of TriageFinding instances to potentially merge.
        max_size: Maximum size for merged super-clusters (default 4).
    
    Returns:
        List of TriageFinding instances with compatible singletons merged.
    """
    if not findings:
        return []
    
    # Partition into singletons and multi-issue clusters
    singletons = []
    multi_clusters = []
    
    for finding in findings:
        if finding.cluster_size == 1:
            singletons.append(finding)
        else:
            multi_clusters.append(finding)
    
    # Filter out UNTAGGED singletons (they never merge)
    untagged = []
    tagged = []
    
    for singleton in singletons:
        if singleton.root_cause_tag == "UNTAGGED":
            untagged.append(singleton)
        else:
            tagged.append(singleton)
    
    # Group tagged singletons by root_cause_tag
    by_tag: dict[str, list[TriageFinding]] = {}
    for singleton in tagged:
        tag = singleton.root_cause_tag
        if tag not in by_tag:
            by_tag[tag] = []
        by_tag[tag].append(singleton)
    
    # Process each tag group
    result = []
    super_cluster_counter = 0
    
    for tag in sorted(by_tag.keys()):  # Sort for determinism
        group = by_tag[tag]
        # Sort singletons by issue number for deterministic chunking
        group.sort(key=lambda f: f.issue_numbers[0])
        
        # Chunk into groups of max_size
        for i in range(0, len(group), max_size):
            chunk = group[i:i+max_size]
            
            if len(chunk) == 1:
                # Single leftover remains as singleton
                result.append(chunk[0])
            else:
                # Create super-cluster
                # Collect all issue numbers and titles
                all_numbers = []
                issue_to_title = {}
                severities = []
                
                for finding in chunk:
                    for num, title in zip(finding.issue_numbers, finding.issue_titles):
                        all_numbers.append(num)
                        issue_to_title[num] = title
                    severities.append(finding.severity)
                
                # Sort issue numbers for determinism
                all_numbers.sort()
                all_titles = tuple(issue_to_title[num] for num in all_numbers)
                
                # Aggregate severity
                aggregated_severity = _aggregate_severity(severities)
                
                # Create new super-cluster with unique sub_cluster_id
                super_cluster = TriageFinding(
                    root_cause_tag=tag,
                    sub_cluster_id=1000 + super_cluster_counter,
                    issue_numbers=tuple(all_numbers),
                    issue_titles=all_titles,
                    cluster_size=len(all_numbers),
                    severity=aggregated_severity,
                    rank_score=0.0,
                    shared_files=(),
                    dependency_notes=(),
                    suggested_fix_order=0,
                )
                result.append(super_cluster)
                super_cluster_counter += 1
    
    # Add multi-clusters and untagged singletons
    result.extend(multi_clusters)
    result.extend(untagged)
    
    # Sort output by (root_cause_tag, min(issue_numbers))
    def sort_key(f: TriageFinding) -> tuple[str, int]:
        min_issue = min(f.issue_numbers) if f.issue_numbers else 0
        return (f.root_cause_tag, min_issue)
    
    result.sort(key=sort_key)
    
    return result


def compute_rank_score(
    cluster_size: int, severity_weight: float, recency_decay: float
) -> float:
    """Compute the cluster ranking score.

    Args:
        cluster_size: Number of issues in the cluster.
        severity_weight: Weight from :data:`SEVERITY_WEIGHTS`.
        recency_decay: Recency decay in ``[0, 1]``.

    Returns:
        ``cluster_size * severity_weight * recency_decay`` (never negative).
    """
    return float(cluster_size) * float(severity_weight) * float(recency_decay)


def extract_shared_files(issue_bodies: List[str]) -> Tuple[str, ...]:
    """Find file paths mentioned in 2 or more issue bodies.

    Args:
        issue_bodies: List of issue body strings (one per issue in a cluster).

    Returns:
        Sorted lexicographic tuple of file paths appearing in >= 2 bodies. Each file is
        counted once per body even if it appears multiple times in that body.
    """
    if len(issue_bodies) < 2:
        return tuple()
    counts: Dict[str, int] = {}
    for body in issue_bodies:
        if not body:
            continue
        files_in_body = set(PATH_REGEX.findall(body))
        for path in files_in_body:
            counts[path] = counts.get(path, 0) + 1
    shared = sorted(path for path, count in counts.items() if count >= 2)
    return tuple(shared)


def _infer_severity(labels: List[Dict[str, Any]]) -> str:
    """Infer cluster severity from issue labels.

    Args:
        labels: List of label dicts from the gh CLI (each dict has a ``"name"`` key).

    Returns:
        ``"high"`` if any label contains ``critical`` or ``p0``.
        ``"medium"`` if any label contains ``bug``, ``regression``, or ``p1``.
        Otherwise ``"low"``.
        
    Note: ``security`` is a topic/area label, not a severity signal.
    """
    if not labels:
        return "low"
    names = []
    for entry in labels:
        if isinstance(entry, dict):
            name = entry.get("name")
        else:
            name = entry
        if isinstance(name, str):
            names.append(name.lower())
    joined = " ".join(names)
    for kw in HIGH_LABEL_KEYWORDS:
        if kw in joined:
            return "high"
    for kw in MEDIUM_LABEL_KEYWORDS:
        if kw in joined:
            return "medium"
    return "low"


def _aggregate_severity(severities: Sequence[str]) -> str:
    """Return the most severe of a sequence of severity labels."""
    order = ["high", "medium", "low"]
    for sev in order:
        if sev in severities:
            return sev
    return "low"


def _recency_decay(
    created_at_iso: str,
    now: datetime,
    half_life_days: float = RECENCY_HALF_LIFE_DAYS,
) -> float:
    """Compute exponential recency decay.

    Formula: ``0.5 ** (age_days / half_life_days)``, clamped to ``[0, 1]``.

    Args:
        created_at_iso: ISO-8601 timestamp string (e.g., ``"2026-03-25T10:00:00Z"``).
        now: Reference time. ``tzinfo``-aware.
        half_life_days: Half-life of the decay function.

    Returns:
        Decay value in ``[0, 1]``. Returns ``0.0`` when ``created_at_iso`` cannot be
        parsed (treats undated issues as infinitely old).
    """
    if not created_at_iso:
        return 0.0
    text = created_at_iso.strip()
    # Accept Z suffix.
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        created = datetime.fromisoformat(text)
    except (ValueError, TypeError):
        return 0.0
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    age_seconds = (now - created).total_seconds()
    if age_seconds <= 0:
        return 1.0
    age_days = age_seconds / 86400.0
    decay = 0.5 ** (age_days / float(half_life_days))
    if decay < 0.0:
        return 0.0
    if decay > 1.0:
        return 1.0
    return decay


def _aggregate_cluster_recency(
    created_at_isos: Sequence[str], now: datetime
) -> float:
    """Return the maximum recency decay across a cluster (most-recent issue wins)."""
    if not created_at_isos:
        return 0.0
    return max(_recency_decay(ts, now) for ts in created_at_isos)


def _has_label(labels: List[Dict[str, Any]], target: str) -> bool:
    """Return True iff the labels list contains a label whose name equals ``target``."""
    if not labels:
        return False
    lowered = target.lower()
    for entry in labels:
        if isinstance(entry, dict):
            name = entry.get("name", "")
        else:
            name = entry
        if isinstance(name, str) and name.lower() == lowered:
            return True
    return False


# =============================================================================
# Dependency Detection
# =============================================================================


def detect_cross_cluster_dependencies(
    clusters: List[TriageFinding],
) -> Dict[Tuple[str, int], Tuple[Tuple[str, int], ...]]:
    """Identify clusters that share at least one file path.

    Two clusters with shared files likely require coordinated remediation, even if their
    root-cause tags differ.

    Args:
        clusters: List of :class:`TriageFinding` records. ``shared_files`` MUST already be
            populated.

    Returns:
        A mapping from ``(root_cause_tag, sub_cluster_id)`` to a tuple of dependent
        cluster keys, sorted lexicographically. Clusters with no dependencies are absent
        from the result.
    """
    out: Dict[Tuple[str, int], Tuple[Tuple[str, int], ...]] = {}
    for i, cluster in enumerate(clusters):
        deps: set[Tuple[str, int]] = set()
        if not cluster.shared_files:
            continue
        files_i = set(cluster.shared_files)
        for j, other in enumerate(clusters):
            if i == j:
                continue
            if not other.shared_files:
                continue
            files_j = set(other.shared_files)
            if files_i & files_j:
                deps.add((other.root_cause_tag, other.sub_cluster_id))
        if deps:
            out[(cluster.root_cause_tag, cluster.sub_cluster_id)] = tuple(sorted(deps))
    return out


# =============================================================================
# Main Triage Pipeline
# =============================================================================


def _build_finding(
    *,
    root_cause_tag: str,
    sub_cluster_id: int,
    issues_in_cluster: List[Dict[str, Any]],
    now: datetime,
    cross_cluster_notes: Tuple[str, ...] = (),
) -> TriageFinding:
    """Build a :class:`TriageFinding` from the issues in one cluster.

    Args:
        root_cause_tag: Primary tag for the cluster.
        sub_cluster_id: 1-indexed sub-cluster ID.
        issues_in_cluster: Raw issue dicts belonging to the cluster.
        now: Reference time for recency decay.
        cross_cluster_notes: Optional pre-built dependency notes.

    Returns:
        A frozen :class:`TriageFinding`. ``suggested_fix_order`` is set to 0; it is
        re-assigned after global ranking.
    """
    # Sort issues by number ASC for determinism.
    ordered = sorted(issues_in_cluster, key=lambda issue: int(issue["number"]))
    issue_numbers = tuple(int(issue["number"]) for issue in ordered)
    issue_titles = tuple(str(issue.get("title", "")) for issue in ordered)
    bodies = [str(issue.get("body", "")) for issue in ordered]
    shared_files = extract_shared_files(bodies)

    severities = [_infer_severity(issue.get("labels", [])) for issue in ordered]
    severity = _aggregate_severity(severities)
    severity_weight = SEVERITY_WEIGHTS.get(severity, SEVERITY_WEIGHTS["low"])

    created_ats = [str(issue.get("createdAt", "")) for issue in ordered]
    recency = _aggregate_cluster_recency(created_ats, now)

    rank_score = compute_rank_score(len(ordered), severity_weight, recency)

    return TriageFinding(
        root_cause_tag=root_cause_tag,
        sub_cluster_id=sub_cluster_id,
        issue_numbers=issue_numbers,
        issue_titles=issue_titles,
        cluster_size=len(ordered),
        severity=severity,
        rank_score=rank_score,
        shared_files=shared_files,
        dependency_notes=tuple(sorted(cross_cluster_notes)),
        suggested_fix_order=0,
    )


def _filter_fp_acknowledged(
    issues: List[Dict[str, Any]], *, include_fp_acknowledged: bool
) -> List[Dict[str, Any]]:
    """Drop ``fp-acknowledged`` issues unless ``include_fp_acknowledged`` is True."""
    if include_fp_acknowledged:
        return list(issues)
    return [
        issue for issue in issues
        if not _has_label(issue.get("labels", []), FP_ACK_LABEL)
    ]


def triage_auto_improvement(
    repo: str = DEFAULT_REPO,
    limit: int = DEFAULT_LIMIT,
    include_fp_acknowledged: bool = False,
    _now: Optional[datetime] = None,
) -> List[TriageFinding]:
    """Cluster the open auto-improvement queue by root cause and rank the result.

    This is the primary public entry point. It fetches issues via
    :func:`runtime_data_aggregator.fetch_open_issues_with_label`, then clusters and ranks.

    Args:
        repo: GitHub repository in ``owner/repo`` form.
        limit: Maximum number of issues to fetch.
        include_fp_acknowledged: When True, do NOT filter out issues labelled
            ``fp-acknowledged``.
        _now: Optional fixed datetime for testing. Defaults to ``datetime.now(timezone.utc)``.

    Returns:
        A list of :class:`TriageFinding` records sorted by ``rank_score`` DESC, then by
        ``root_cause_tag`` ASC, then by ``sub_cluster_id`` ASC. ``suggested_fix_order`` is
        assigned 1..N in this final order.
    """
    now = _now if _now is not None else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    raw_issues, _health = fetch_open_issues_with_label(
        repo=repo, label=AUTO_IMPROVEMENT_LABEL, limit=limit
    )
    return _triage_from_issues(
        raw_issues,
        include_fp_acknowledged=include_fp_acknowledged,
        now=now,
    )


def _triage_from_issues(
    raw_issues: List[Dict[str, Any]],
    *,
    include_fp_acknowledged: bool,
    now: datetime,
) -> List[TriageFinding]:
    """Cluster + rank a pre-fetched list of issue dicts (no I/O)."""
    issues = _filter_fp_acknowledged(raw_issues, include_fp_acknowledged=include_fp_acknowledged)
    if not issues:
        return []

    # Primary bucketing by tag.
    by_tag: Dict[str, List[Dict[str, Any]]] = {}
    for issue in issues:
        if "number" not in issue:
            continue
        title = str(issue.get("title", ""))
        tag = extract_root_cause_tag(title)
        by_tag.setdefault(tag, []).append(issue)

    findings: List[TriageFinding] = []
    for tag in sorted(by_tag):
        bucket = by_tag[tag]
        sub_clusters = cluster_within_tag(bucket)
        # Map issue_number -> issue dict for fast lookup.
        index = {int(issue["number"]): issue for issue in bucket}
        for sub_id, numbers in enumerate(sub_clusters, start=1):
            cluster_issues = [index[n] for n in numbers]
            finding = _build_finding(
                root_cause_tag=tag,
                sub_cluster_id=sub_id,
                issues_in_cluster=cluster_issues,
                now=now,
            )
            findings.append(finding)

    # Compute cross-cluster dependency notes.
    dep_map = detect_cross_cluster_dependencies(findings)
    if dep_map:
        annotated: List[TriageFinding] = []
        for f in findings:
            key = (f.root_cause_tag, f.sub_cluster_id)
            deps = dep_map.get(key, ())
            if deps:
                notes = tuple(
                    sorted(
                        f"shares files with {dep_tag}#{dep_id}"
                        for dep_tag, dep_id in deps
                    )
                )
            else:
                notes = ()
            annotated.append(
                TriageFinding(
                    root_cause_tag=f.root_cause_tag,
                    sub_cluster_id=f.sub_cluster_id,
                    issue_numbers=f.issue_numbers,
                    issue_titles=f.issue_titles,
                    cluster_size=f.cluster_size,
                    severity=f.severity,
                    rank_score=f.rank_score,
                    shared_files=f.shared_files,
                    dependency_notes=notes,
                    suggested_fix_order=0,
                )
            )
        findings = annotated

    # Global sort: rank_score DESC, then root_cause_tag ASC, then sub_cluster_id ASC.
    findings.sort(key=lambda f: (-f.rank_score, f.root_cause_tag, f.sub_cluster_id))

    # Re-issue suggested_fix_order 1..N.
    ordered: List[TriageFinding] = []
    for idx, f in enumerate(findings, start=1):
        ordered.append(
            TriageFinding(
                root_cause_tag=f.root_cause_tag,
                sub_cluster_id=f.sub_cluster_id,
                issue_numbers=f.issue_numbers,
                issue_titles=f.issue_titles,
                cluster_size=f.cluster_size,
                severity=f.severity,
                rank_score=f.rank_score,
                shared_files=f.shared_files,
                dependency_notes=f.dependency_notes,
                suggested_fix_order=idx,
            )
        )
    return ordered


# =============================================================================
# Rendering
# =============================================================================


def render_json(findings: List[TriageFinding]) -> str:
    """Serialize findings as a deterministic JSON string."""
    payload = [asdict(f) for f in findings]
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)


def render_human(findings: List[TriageFinding]) -> str:
    """Render findings as a human-readable text block."""
    if not findings:
        return "Auto-improvement queue is empty. Nothing to triage."

    lines: List[str] = []
    lines.append("Auto-Improvement Triage Report")
    lines.append("==============================")
    lines.append(f"Clusters: {len(findings)}")
    lines.append("")
    for f in findings:
        header = (
            f"[{f.suggested_fix_order}] {f.root_cause_tag}#{f.sub_cluster_id} "
            f"({f.severity}) size={f.cluster_size} "
            f"rank={f.rank_score:.4f}"
        )
        lines.append(header)
        for num, title in zip(f.issue_numbers, f.issue_titles):
            lines.append(f"  - #{num} {title}")
        if f.shared_files:
            lines.append(f"  shared_files: {', '.join(f.shared_files)}")
        if f.dependency_notes:
            for note in f.dependency_notes:
                lines.append(f"  dep: {note}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# =============================================================================
# CLI
# =============================================================================


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="triage",
        description=(
            "Periodic-aggregation root-cause triage of the open "
            "auto-improvement issue queue."
        ),
    )
    parser.add_argument(
        "--auto-improvement",
        action="store_true",
        help="Triage the auto-improvement queue (currently the only supported mode).",
    )
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPO,
        help=f"GitHub repository (default: {DEFAULT_REPO}).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Maximum issues to fetch (default: {DEFAULT_LIMIT}).",
    )
    parser.add_argument(
        "--include-fp-acknowledged",
        action="store_true",
        help="Include issues labelled fp-acknowledged (filtered out by default).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human-readable text.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point.

    Returns:
        ``0`` on success (including empty queue). ``2`` if the GitHub fetch failed.
    """
    args = _parse_args(argv)
    # --auto-improvement is currently the only mode; default to it.
    raw_issues, health = fetch_open_issues_with_label(
        repo=args.repo, label=AUTO_IMPROVEMENT_LABEL, limit=args.limit
    )
    if health.status == "error":
        sys.stderr.write(
            f"WARN: failed to fetch auto-improvement issues: {health.error_message}\n"
        )
        return 2
    if args.limit and len(raw_issues) >= args.limit:
        sys.stderr.write(
            f"WARN: fetched {len(raw_issues)} issues (--limit={args.limit}); "
            f"results may be truncated.\n"
        )
    findings = _triage_from_issues(
        raw_issues,
        include_fp_acknowledged=args.include_fp_acknowledged,
        now=datetime.now(timezone.utc),
    )
    if args.json:
        sys.stdout.write(render_json(findings) + "\n")
    else:
        sys.stdout.write(render_human(findings))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
