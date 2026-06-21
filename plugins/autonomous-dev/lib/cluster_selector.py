"""Cluster selection logic for drain-queue command."""

import re


def select_next_cluster(clusters):
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
    # Collect all open issues from all clusters for leaf checking
    all_open_issues = set()
    for cluster in clusters:
        for issue in cluster.get("issues", []):
            if issue.get("state") == "open":
                all_open_issues.add(issue.get("number"))
    
    # Process clusters in order
    for cluster in clusters:
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