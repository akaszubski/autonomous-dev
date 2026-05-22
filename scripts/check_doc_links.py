#!/usr/bin/env python3
"""Stdlib markdown link checker (Issue #972 AC#7).

Lightweight replacement for ``markdown-link-check`` (which requires Node).
Extracts ``[text](url)`` links from markdown files and verifies them:

- Relative paths resolve to a file that exists (relative to the doc's
  parent directory).
- Anchors (``#section``) and pure mailto/tel links are skipped (we can
  not validate anchors against rendered HTML without a parser).
- HTTP(S) links are HEAD-checked when ``--no-http`` is NOT passed.

Exit code 0 if all links resolve, 1 if any link is broken. Broken links
are printed to stderr.

Usage::

    python scripts/check_doc_links.py docs/HOOK-COMPOSITION.md
    python scripts/check_doc_links.py --no-http docs/*.md
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Tuple

LINK_RE = re.compile(r"\[(?:[^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HTTP_TIMEOUT_SECONDS = 3.0


def _find_project_root(start: Path) -> Path:
    """Walk up from ``start`` to find a project root marker.

    A project root is the first ancestor directory containing either a
    ``.git`` entry (directory or file — git worktrees use a file) or a
    ``pyproject.toml`` file. If no such ancestor is found, ``start`` is
    returned as the fallback.

    Args:
        start: The directory to begin the upward walk from. SHOULD be an
            absolute, resolved path so the comparison is unambiguous.

    Returns:
        The first ancestor directory (inclusive of ``start``) containing
        ``.git`` or ``pyproject.toml``; otherwise ``start``.
    """
    current = start if start.is_dir() else start.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists() or (candidate / "pyproject.toml").exists():
            return candidate
    return current


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Stdlib markdown link checker")
    p.add_argument("paths", nargs="+", help="Markdown files to check")
    p.add_argument(
        "--no-http",
        action="store_true",
        default=True,
        help="Skip HTTP(S) link checks (default; set --check-http to enable)",
    )
    p.add_argument(
        "--check-http",
        dest="no_http",
        action="store_false",
        help="Enable HTTP(S) link checks (off by default for tests)",
    )
    return p.parse_args(argv)


def extract_links(content: str) -> List[str]:
    return LINK_RE.findall(content)


def check_link(link: str, doc_path: Path, *, no_http: bool) -> Tuple[bool, str]:
    """Return (ok, detail). ``detail`` is empty when ok."""
    if not link or link.startswith("#"):
        return True, ""
    if link.startswith(("mailto:", "tel:")):
        return True, ""
    if link.startswith(("http://", "https://")):
        if no_http:
            return True, ""
        try:
            req = urllib.request.Request(link, method="HEAD")
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
                if 200 <= resp.status < 400:
                    return True, ""
                return False, f"HTTP {resp.status}"
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
            return False, f"network error: {exc}"
    # Relative path. Strip anchor fragment for existence check.
    target = link.split("#", 1)[0]
    if not target:
        return True, ""
    candidate = (doc_path.parent / target).resolve()
    # SECURITY (Issue #994): Containment check MUST run BEFORE existence check
    # so a crafted traversal link like "../../../../etc/passwd" cannot leak
    # the existence of files outside the project. Without this guard, a
    # malicious doc could "validate" successfully against arbitrary system
    # files (e.g. /etc/passwd, /etc/hosts), silently turning the link
    # checker into a filesystem oracle.
    project_root = _find_project_root(doc_path.parent.resolve())
    try:
        is_contained = candidate.is_relative_to(project_root)
    except (ValueError, AttributeError):
        # Python < 3.9 fallback: prefix comparison.
        root_str = str(project_root)
        cand_str = str(candidate)
        is_contained = cand_str == root_str or cand_str.startswith(root_str + os.sep)
    if not is_contained:
        return False, f"link escapes project root: {target}"
    if candidate.exists():
        return True, ""
    return False, f"missing file: {candidate}"


def check_doc(doc_path: Path, *, no_http: bool) -> List[Tuple[str, str]]:
    """Return list of (broken_link, detail) for one doc."""
    try:
        content = doc_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [("<unreadable>", str(exc))]
    broken: List[Tuple[str, str]] = []
    for link in extract_links(content):
        ok, detail = check_link(link, doc_path, no_http=no_http)
        if not ok:
            broken.append((link, detail))
    return broken


def main(argv=None) -> int:
    args = parse_args(argv)
    any_broken = False
    for raw in args.paths:
        path = Path(raw)
        if not path.exists():
            print(f"error: not found: {path}", file=sys.stderr)
            any_broken = True
            continue
        broken = check_doc(path, no_http=args.no_http)
        if broken:
            any_broken = True
            print(f"\n{path}: {len(broken)} broken link(s)", file=sys.stderr)
            for link, detail in broken:
                print(f"  {link}  --  {detail}", file=sys.stderr)
    return 1 if any_broken else 0


if __name__ == "__main__":
    sys.exit(main())
