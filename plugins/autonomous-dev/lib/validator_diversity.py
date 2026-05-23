"""Validator Diversity Score — measures complementarity between reviewer and security-auditor findings.

Computes 1 - Jaccard similarity over normalized finding tuples (severity, category, file, line).
Low overlap = diverse validators (good). High overlap with enough findings = rubber-stamping (flag).
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional


# Only OWASP category IDs are cross-walked to "security"; reviewer's own "security" category
# is already canonical and also normalizes to "security" for cross-validator dedup.
_OWASP_PREFIX_RE = re.compile(r"^A0?(\d{1,2}):", re.IGNORECASE)

_SEVERITY_MAP = {
    "critical": "blocking",
    "high": "blocking",
    "medium": "warning",
    "warning": "warning",
    "warn": "warning",
    "low": "info",
    "info": "info",
}


def _normalize_severity(raw: str) -> str:
    """Normalize a raw severity string to one of blocking/warning/info."""
    key = raw.strip().lower()
    return _SEVERITY_MAP.get(key, key)


def _normalize_category(raw: str) -> str:
    """Normalize a category string. OWASP A0x/Ax codes → 'security'."""
    stripped = raw.strip()
    if _OWASP_PREFIX_RE.match(stripped):
        return "security"
    return stripped.lower()


def _normalize_file(raw: str) -> Optional[str]:
    """Strip backticks and split off line number; return posix relpath or None."""
    if not raw:
        return None
    cleaned = raw.strip().strip("`").strip()
    if not cleaned:
        return None
    # Split path:line — keep only the path part
    parts = cleaned.split(":")
    path_part = parts[0].strip()
    if not path_part:
        return None
    return path_part


def _extract_line(raw: str) -> Optional[int]:
    """Extract the first integer (line number) from a 'path:line' string."""
    match = re.search(r":(\d+)", raw)
    if match:
        return int(match.group(1))
    return None


def parse_reviewer_findings(text: str) -> list[tuple]:
    """Parse reviewer output into normalized tuples.

    Expects blocks delimited by '### FINDING-N' headers with bullet fields
    **File**, **Severity**, **Category**.
    """
    findings: list[tuple] = []
    blocks = re.split(r"(?m)^###\s+FINDING-\d+", text)
    for block in blocks[1:]:  # skip preamble before first FINDING
        severity_match = re.search(
            r"\*\*Severity\*\*\s*:\s*(.+)", block, re.IGNORECASE
        )
        category_match = re.search(
            r"\*\*Category\*\*\s*:\s*(.+)", block, re.IGNORECASE
        )
        file_match = re.search(
            r"\*\*File\*\*\s*:\s*(.+)", block, re.IGNORECASE
        )

        severity = _normalize_severity(severity_match.group(1).strip()) if severity_match else "info"
        category = _normalize_category(category_match.group(1).strip()) if category_match else "unknown"
        raw_file = file_match.group(1).strip() if file_match else ""
        file_path = _normalize_file(raw_file)
        line = _extract_line(raw_file) if raw_file else None

        findings.append((severity, category, file_path, line))
    return findings


def parse_security_auditor_findings(text: str) -> list[tuple]:
    """Parse security-auditor output into normalized tuples.

    Expects OWASP-style sections '## A01: ...' with **Severity** and **Location** fields.
    """
    findings: list[tuple] = []
    # Split on OWASP section headers like '## A01: Broken Access Control'
    blocks = re.split(r"(?m)^##\s+A0?\d{1,2}:[^\n]*", text)
    headers = re.findall(r"(?m)^##\s+(A0?\d{1,2}:[^\n]*)", text)

    for i, block in enumerate(blocks[1:]):  # skip preamble
        header = headers[i] if i < len(headers) else ""
        severity_match = re.search(r"\*\*Severity\*\*\s*:\s*(.+)", block, re.IGNORECASE)
        location_match = re.search(r"\*\*Location\*\*\s*:\s*(.+)", block, re.IGNORECASE)

        severity = _normalize_severity(severity_match.group(1).strip()) if severity_match else "info"
        # All OWASP categories normalize to "security"
        category = _normalize_category(header.strip())  # already maps via _OWASP_PREFIX_RE
        raw_loc = location_match.group(1).strip() if location_match else ""
        file_path = _normalize_file(raw_loc)
        line = _extract_line(raw_loc) if raw_loc else None

        findings.append((severity, category, file_path, line))
    return findings


def jaccard(set_a: set, set_b: set) -> float:
    """Compute Jaccard similarity between two sets. Returns 0.0 when both are empty."""
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def score(reviewer_text: str, security_text: str) -> dict:
    """Compute validator diversity metrics from raw text outputs.

    Returns a dict with keys: diversity, jaccard, count_a, count_b,
    n_intersection, n_union, classification, alert, files_present.
    files_present is always True when called directly (use score_from_paths for False).
    """
    set_a = set(parse_reviewer_findings(reviewer_text))
    set_b = set(parse_security_auditor_findings(security_text))

    count_a = len(set_a)
    count_b = len(set_b)
    total = count_a + count_b
    intersection = set_a & set_b
    union = set_a | set_b
    n_intersection = len(intersection)
    n_union = len(union)

    j = jaccard(set_a, set_b)
    # When both sets are empty, jaccard=0 and diversity is meaningless; pin to 0.0
    # to signal "no signal" rather than "maximum diversity".
    diversity = 0.0 if (count_a == 0 and count_b == 0) else 1.0 - j

    classification, alert = _classify(count_a, count_b, total, j)

    return {
        "diversity": diversity,
        "jaccard": j,
        "count_a": count_a,
        "count_b": count_b,
        "n_intersection": n_intersection,
        "n_union": n_union,
        "classification": classification,
        "alert": alert,
        "files_present": True,
    }


def _classify(count_a: int, count_b: int, total: int, j: float) -> tuple[str, Optional[str]]:
    """Return (classification, alert) based on counts and Jaccard value."""
    if count_a == 0 and count_b == 0:
        return "blind-spot", "[VALIDATOR-BLIND-SPOT]"
    if total < 6:
        # One empty + other non-empty is a special label, but still tiny-sample if total<6
        if count_a == 0 or count_b == 0:
            return "complementary", None
        return "tiny-sample", None
    # total >= 6
    if j > 0.8:
        return "rubber-stamp", "[VALIDATOR-OVERLAP]"
    if j > 0.5:
        return "overlapping", None
    return "diverse", None


def score_from_paths(reviewer_path: str, security_path: str) -> dict:
    """Read artifact files and compute diversity score.

    Returns the score dict (same shape as score()) plus files_present=False
    when at least one path is missing or empty, so the CIA can decide to omit
    the report subsection.
    """
    r_path = Path(reviewer_path)
    s_path = Path(security_path)

    r_text = ""
    s_text = ""
    files_present = True

    try:
        r_text = r_path.read_text(encoding="utf-8") if r_path.exists() else ""
    except OSError:
        r_text = ""

    try:
        s_text = s_path.read_text(encoding="utf-8") if s_path.exists() else ""
    except OSError:
        s_text = ""

    if not r_text.strip() or not s_text.strip():
        files_present = False

    result = score(r_text, s_text)
    result["files_present"] = files_present
    return result


def _format_markdown(result: dict) -> str:
    """Format the score dict as a Markdown block for human-readable CLI output."""
    lines = [
        "### Validator Diversity",
        f"- **Diversity**: {result['diversity']:.4f}",
        f"- **Jaccard**: {result['jaccard']:.4f}",
        f"- **Reviewer findings**: {result['count_a']}",
        f"- **Security findings**: {result['count_b']}",
        f"- **Classification**: {result['classification']}",
    ]
    if result.get("alert"):
        lines.append(f"- **Alert**: {result['alert']}")
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compute validator diversity score between reviewer and security-auditor outputs."
    )
    parser.add_argument("--reviewer", required=True, help="Path to reviewer output file")
    parser.add_argument("--security", required=True, help="Path to security-auditor output file")
    parser.add_argument(
        "--json", action="store_true", dest="as_json", help="Output as JSON (default: Markdown)"
    )
    args = parser.parse_args()

    result = score_from_paths(args.reviewer, args.security)

    if args.as_json:
        print(json.dumps(result, indent=2))
    else:
        print(_format_markdown(result))

    sys.exit(0)
