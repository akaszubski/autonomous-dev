"""Regression tests for Issue #994 — doc-link checker path-traversal guard.

``scripts/check_doc_links.py`` previously resolved relative markdown links
via ``(doc_path.parent / target).resolve()`` and only checked
``candidate.exists()``. A crafted link such as ``../../../../etc/passwd``
resolves to ``/private/etc/passwd`` (or ``/etc/passwd``) — a file that
exists on virtually every Unix system — and was silently reported as
"valid". A pre-commit hook or CI step using the checker could be deceived
into validating a malicious doc that exfiltrates information about the
host filesystem layout.

The fix adds:

1. A ``_find_project_root()`` helper that walks up from the doc's
   directory looking for ``.git`` or ``pyproject.toml`` (either marker
   is sufficient).
2. A containment check in ``check_link()`` that fires BEFORE the
   ``candidate.exists()`` call. Any link whose resolved candidate is
   outside the detected project root is reported as
   ``"link escapes project root: <target>"`` — never as "exists" and
   never as "missing file" (the latter would leak the path).

These regression tests reproduce each finding by exercising the failing
behaviour pre-fix (traversal links accepted) and asserting the new guards
hold post-fix.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make scripts/check_doc_links.py importable.
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import check_doc_links  # noqa: E402  (import after path manipulation)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(tmp_path: Path, *, marker: str = ".git") -> Path:
    """Create an isolated, self-contained project directory.

    Args:
        tmp_path: Base directory provided by pytest fixture.
        marker: Project-root marker to place — ``".git"`` (a directory)
            or ``"pyproject.toml"`` (a file).

    Returns:
        The created project root directory (resolved to its real path so
        ``Path.resolve()`` comparisons inside the script behave the same
        way they will at runtime).
    """
    project = (tmp_path / "myproject").resolve()
    project.mkdir(parents=True, exist_ok=True)
    if marker == ".git":
        (project / ".git").mkdir(exist_ok=True)
    elif marker == "pyproject.toml":
        (project / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    else:
        raise ValueError(f"unsupported marker: {marker!r}")
    return project


# ---------------------------------------------------------------------------
# check_link() — the link validator
# ---------------------------------------------------------------------------


def test_traversal_link_to_etc_passwd_is_rejected(tmp_path: Path) -> None:
    """Test 1 — A crafted ``../../../../etc/passwd`` link MUST be rejected
    with the ``"escapes project root"`` reason, even though
    ``/etc/passwd`` exists on Unix systems.
    """
    project = _make_project(tmp_path)
    docs = project / "docs"
    docs.mkdir()
    doc = docs / "README.md"
    doc.write_text("[passwd](../../../../etc/passwd)\n")

    ok, detail = check_doc_links.check_link(
        "../../../../etc/passwd", doc, no_http=True
    )

    assert ok is False, (
        f"traversal link MUST be rejected; got ok=True with detail={detail!r}"
    )
    assert "escapes project root" in detail, (
        f"reason MUST mention 'escapes project root'; got {detail!r}"
    )
    # Crucially: must NOT say "missing file" — that would leak the path.
    assert "missing file" not in detail, (
        f"reason MUST NOT leak the absolute resolved path; got {detail!r}"
    )


def test_legitimate_sibling_link_inside_project_is_allowed(tmp_path: Path) -> None:
    """Test 2 — A legitimate intra-project link such as ``../README.md``
    MUST resolve and return ``ok=True`` when the sibling exists.
    """
    project = _make_project(tmp_path)
    docs = project / "docs"
    docs.mkdir()
    sibling = project / "README.md"
    sibling.write_text("# Hello\n")
    doc = docs / "guide.md"
    doc.write_text("[home](../README.md)\n")

    ok, detail = check_doc_links.check_link("../README.md", doc, no_http=True)

    assert ok is True, (
        f"legitimate intra-project sibling MUST be accepted; "
        f"got ok=False with detail={detail!r}"
    )
    assert detail == "", f"detail MUST be empty on success; got {detail!r}"


def test_nonexistent_intraproject_link_reports_missing(tmp_path: Path) -> None:
    """Test 3 — A link to a non-existent file *inside* the project MUST
    report the missing-file reason (NOT the escape reason). This proves
    the containment check does not over-reject in-tree references.
    """
    project = _make_project(tmp_path)
    docs = project / "docs"
    docs.mkdir()
    doc = docs / "guide.md"
    doc.write_text("[missing](./does-not-exist.md)\n")

    ok, detail = check_doc_links.check_link(
        "./does-not-exist.md", doc, no_http=True
    )

    assert ok is False, "non-existent in-tree link MUST be rejected"
    assert "missing file" in detail, (
        f"in-tree missing link MUST report 'missing file'; got {detail!r}"
    )
    assert "escapes project root" not in detail, (
        f"in-tree missing link MUST NOT be classified as escape; got {detail!r}"
    )


def test_http_link_behavior_unchanged(tmp_path: Path) -> None:
    """Test 4 — HTTP(S) link handling MUST be unchanged by this fix.
    With ``no_http=True`` (the default), HTTP links short-circuit to
    ``(True, "")`` without touching the filesystem-containment logic.
    """
    project = _make_project(tmp_path)
    doc = project / "README.md"
    doc.write_text("[example](https://example.com)\n")

    ok, detail = check_doc_links.check_link(
        "https://example.com", doc, no_http=True
    )

    assert ok is True, (
        f"HTTP link with no_http=True MUST short-circuit to True; "
        f"got ok=False with detail={detail!r}"
    )
    assert detail == "", f"detail MUST be empty for skipped HTTP; got {detail!r}"

    # http:// scheme — same behaviour.
    ok2, detail2 = check_doc_links.check_link(
        "http://example.com", doc, no_http=True
    )
    assert ok2 is True and detail2 == ""


# ---------------------------------------------------------------------------
# _find_project_root() — the root detector
# ---------------------------------------------------------------------------


def test_find_project_root_locates_git_marker(tmp_path: Path) -> None:
    """Test 5 — ``_find_project_root()`` MUST return the directory
    containing ``.git`` when started from a descendant directory.
    """
    project = _make_project(tmp_path, marker=".git")
    deep = project / "docs" / "subsection"
    deep.mkdir(parents=True)

    found = check_doc_links._find_project_root(deep)

    assert found == project, (
        f"expected project root {project}, got {found}"
    )


def test_find_project_root_locates_pyproject_toml(tmp_path: Path) -> None:
    """Test 6 — ``_find_project_root()`` MUST return the directory
    containing ``pyproject.toml`` when no ``.git`` is present.
    """
    project = _make_project(tmp_path, marker="pyproject.toml")
    deep = project / "src" / "pkg"
    deep.mkdir(parents=True)

    found = check_doc_links._find_project_root(deep)

    assert found == project, (
        f"expected project root {project}, got {found}"
    )
    # And no .git should be present (proves it found pyproject.toml).
    assert not (project / ".git").exists()


def test_find_project_root_fallback_when_no_marker(tmp_path: Path) -> None:
    """Test 7 — When neither ``.git`` nor ``pyproject.toml`` is found
    walking upward, ``_find_project_root()`` MUST fall back to a sane
    default (the starting directory itself).
    """
    # tmp_path on macOS/Linux test runners may live under /tmp or
    # /private/var/folders — neither has .git or pyproject.toml, so the
    # walk reaches filesystem root without finding a marker. We resolve
    # to handle the macOS /tmp -> /private/tmp symlink.
    isolated = (tmp_path / "no_markers_here").resolve()
    isolated.mkdir()

    found = check_doc_links._find_project_root(isolated)

    # Fallback contract: returns the starting directory itself when no
    # ancestor markers exist along the path. We assert against the
    # resolved starting dir — anything else (e.g. a real project root
    # higher up) would be wrong since tmp_path is outside any project.
    # If pytest's tmp_path *does* happen to sit under a project (very
    # unusual), the test would still detect a malfunction since
    # _find_project_root walking upward without a marker MUST land on
    # the starting directory.
    #
    # We allow either: (a) the starting directory itself, or
    # (b) None of the ancestors had markers and we landed at a
    # filesystem boundary — in which case the starting dir is correct.
    # The contract documented in the docstring is "fallback = start".
    assert found == isolated, (
        f"with no markers, _find_project_root should fall back to start; "
        f"got {found} (start was {isolated})"
    )
