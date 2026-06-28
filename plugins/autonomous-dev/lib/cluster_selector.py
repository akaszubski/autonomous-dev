"""Cluster selection logic for drain-queue command."""

import logging
import re
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


def _is_cluster_closed(cluster) -> "Tuple[bool, str]":
    """Check if any issue in the cluster is CLOSED via gh CLI.
    
    Args:
        cluster: Cluster dict with issue_numbers list
        
    Returns:
        (True, "issue_already_closed") if any issue is CLOSED
        (False, "") otherwise or on error (graceful degradation)
    """
    issue_numbers = cluster.get("issue_numbers", [])
    if not issue_numbers:
        return (False, "")
    
    for issue_num in issue_numbers:
        try:
            result = subprocess.run(
                ["gh", "issue", "view", str(issue_num), "--json", "state", "--jq", ".state"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0 and result.stdout.strip().upper() == "CLOSED":
                return (True, "issue_already_closed")
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception) as e:
            # Graceful: treat errors as not closed (don't block on gh failures)
            logger.debug(f"gh issue view failed for #{issue_num}: {e}")
            continue
    
    return (False, "")


def _is_cluster_in_progress(cluster) -> "Tuple[bool, str]":
    """Check if any issue in the cluster has a fresh in-progress claim (cross-machine mutex).

    Args:
        cluster: Cluster dict with issue_numbers list.

    Returns:
        (True, "issue_claimed_by:<actor>") if any issue is claimed.
        (False, "") otherwise or on any error.
    """
    issue_numbers = cluster.get("issue_numbers", [])
    if not issue_numbers:
        return (False, "")
    try:
        from issue_claim import is_claimed
    except ImportError:
        return (False, "")
    for issue_num in issue_numbers:
        try:
            claimed, info = is_claimed(issue_num)
            if claimed:
                actor = (info or {}).get("actor", "unknown")
                return (True, f"issue_claimed_by:{actor}")
        except Exception as e:
            logger.debug(f"is_claimed failed for #{issue_num}: {e}")
            continue
    return (False, "")


def _gh_rate_limit_ok(min_remaining: int = 100) -> bool:
    """Check if GitHub API rate limit has enough remaining calls.
    
    Args:
        min_remaining: Minimum remaining calls required (default 100)
        
    Returns:
        True if remaining >= min_remaining or on any error (graceful degradation)
    """
    try:
        result = subprocess.run(
            ["gh", "api", "rate_limit", "--jq", ".rate.remaining"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            remaining = int(result.stdout.strip())
            return remaining >= min_remaining
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, ValueError, Exception) as e:
        # Graceful: on any failure assume rate limit is OK (don't block)
        logger.debug(f"gh rate limit check failed: {e}")
    
    return True


def select_next_cluster(clusters, *, apply_auto_drain_gates: bool = False):
    r"""Select the next cluster to drain, skipping tracker-shaped issues.

    Args:
        clusters: List of cluster dicts. Each cluster dict has shape compatible
            with TriageFinding-serialized output PLUS optional hydrated issue
            metadata. Recognized keys per cluster:
              - issue_numbers: List[int]  (REQUIRED for selection)
              - issues: Optional list of issue dicts, each with:
                  - number: int
                  - title: str
                  - body: str
                  - labels: list of label dicts (each {"name": str}) OR list of str
                  - state: str ("open" or "closed")
        apply_auto_drain_gates: If True, apply auto-drain gates (severity, tag,
            size, skip, large-feat, drain-stuck-meta) before tracker/leaf logic.

    Returns:
        A cluster dict for drainage, or None if no drainable cluster exists.
        When the top cluster represents a tracker issue with open leaf children
        among ANY cluster's issues, returns a synthetic single-issue cluster
        for the lowest-numbered open leaf:
            {"root_cause_tag": original_tag, "issue_numbers": [leaf_n], ...}

    Tracker detection (an issue is tracker-shaped if ANY):
        1. Title (stripped of leading whitespace) starts with "[tracker]"
           (case-insensitive).
        2. Labels contain BOTH "root-cause" AND "enhancement" (case-insensitive
           label name match).
        3. Body contains >=2 phase headings matching r"^### Phase [A-Z]" AND
           >=2 leaf issue references matching r"#\d+".

    Leaf preference:
        When the first non-skipped cluster's single (or sole) issue is a tracker
        AND that tracker body contains "#N" references that appear as OPEN
        issues in any cluster in the input, return a synthetic cluster pointing
        at the LOWEST-NUMBERED open leaf.
    """
    # Apply auto-drain gates if requested
    if apply_auto_drain_gates:
        # Import gate functions to avoid circular imports
        from drain_queue_state import (
            severity_gate,
            tag_gate, 
            size_gate,
            skip_gate,
            AUTO_DRAINABLE_SEVERITY,
            MAX_CLUSTER_SIZE_AUTO_DRAINABLE,
            HUMAN_GATE_TAGS,
            SKIP_LABELS,
        )
        
        # Helper functions for large-feat and drain-stuck-meta detection
        def is_large_feat(cluster):
            """Check if cluster is a large feature (>2 issues with feat: prefix)."""
            titles = cluster.get('issue_titles', [])
            prefixes = ('feat:', 'feat(', 'feature:', 'feature(')
            has_feat = any((t or '').lower().lstrip().startswith(prefixes) for t in titles)
            return has_feat and cluster.get('cluster_size', 0) > 2

        def is_drain_stuck_meta(cluster):
            """Check if cluster is drain-stuck meta issue."""
            titles = cluster.get('issue_titles', [])
            return any('[drain-stuck]' in (t or '').lower() for t in titles)
        
        # Filter clusters through gates
        filtered_clusters = []
        for cluster in clusters:
            # Severity gate
            severity = cluster.get('severity', '').lower()
            if severity not in AUTO_DRAINABLE_SEVERITY:
                continue
                
            # Size gate
            cluster_size = cluster.get('cluster_size', len(cluster.get('issue_numbers', [])))
            if cluster_size > MAX_CLUSTER_SIZE_AUTO_DRAINABLE:
                continue
                
            # Large feat gate
            if is_large_feat(cluster):
                continue
                
            # Drain-stuck-meta gate
            if is_drain_stuck_meta(cluster):
                continue
                
            # Tag gate - check if cluster has hydrated labels
            cluster_labels = set()
            for issue in cluster.get('issues', []):
                labels = issue.get('labels', [])
                for label in labels:
                    if isinstance(label, dict):
                        cluster_labels.add(label.get('name', '').lower())
                    else:
                        cluster_labels.add(str(label).lower())
            
            if cluster_labels & HUMAN_GATE_TAGS:
                continue
                
            # Skip gate - soft skip labels
            if cluster_labels & SKIP_LABELS:
                continue
            
            # Cluster passes all gates
            filtered_clusters.append(cluster)
        
        # Use filtered clusters for selection
        clusters = filtered_clusters
        if not clusters:
            return None
    
    # Check rate limit before dedup loop
    rate_limit_ok = _gh_rate_limit_ok()
    if not rate_limit_ok:
        logger.warning("GitHub API rate limit low (<100), skipping closed-issue dedup")
    
    # Collect all open issues from all clusters for leaf checking
    all_open_issues = set()
    for cluster in clusters:
        for issue in cluster.get("issues", []):
            if issue.get("state") == "open":
                all_open_issues.add(issue.get("number"))
    
    # Process clusters in order
    for cluster in clusters:
        # Check if cluster issues are closed (if rate limit allows)
        if rate_limit_ok:
            is_closed, reason = _is_cluster_closed(cluster)
            if is_closed:
                logger.info(f"Skipping cluster {cluster.get('issue_numbers')} - {reason}")
                continue
            in_progress, ip_reason = _is_cluster_in_progress(cluster)
            if in_progress:
                logger.info(f"Skipping cluster {cluster.get('issue_numbers')} - {ip_reason}")
                continue

        issues = cluster.get("issues", [])
        issue_numbers = cluster.get("issue_numbers", [])
        
        # Check if cluster contains any tracker issues
        tracker_found = False
        tracker_leaves = []
        
        for issue in issues:
            title = issue.get("title", "").lstrip()
            body = issue.get("body", "")
            labels = issue.get("labels", [])
            
            # Normalize labels to strings
            label_names = []
            for label in labels:
                if isinstance(label, dict):
                    label_names.append(label.get("name", "").lower())
                else:
                    label_names.append(str(label).lower())
            
            # Check tracker criteria
            is_tracker = False
            
            # Criterion 1: Title starts with [tracker]
            if title.lower().startswith("[tracker]"):
                is_tracker = True
            
            # Criterion 2: Labels contain both "root-cause" AND "enhancement"
            if "root-cause" in label_names and "enhancement" in label_names:
                is_tracker = True
            
            # Criterion 3: Body has >=2 phase headings and >=2 issue refs
            phase_matches = re.findall(r"^### Phase [A-Z]", body, re.MULTILINE)
            issue_refs = re.findall(r"#(\d+)", body)
            if len(phase_matches) >= 2 and len(issue_refs) >= 2:
                is_tracker = True
            
            if is_tracker:
                tracker_found = True
                # Find open leaves referenced in this tracker's body
                for ref in issue_refs:
                    ref_num = int(ref)
                    if ref_num in all_open_issues:
                        tracker_leaves.append(ref_num)
        
        # If tracker with open leaves found, return synthetic cluster for lowest leaf
        if tracker_found and tracker_leaves:
            lowest_leaf = min(tracker_leaves)
            synthetic_cluster = {
                "root_cause_tag": cluster.get("root_cause_tag"),
                "issue_numbers": [lowest_leaf]
            }
            # Copy other fields from original cluster except issues
            for key, value in cluster.items():
                if key not in ["issue_numbers", "issues", "root_cause_tag"]:
                    synthetic_cluster[key] = value
            return synthetic_cluster
        
        # If tracker-only cluster, skip to next
        if tracker_found:
            continue
        
        # Non-tracker cluster found, return it
        return cluster
    
    # No drainable cluster found
    return None