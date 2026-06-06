#!/usr/bin/env python3
"""Edit tier classifier — Phase 1 default-on Write/Edit gate (Issue #1142+).

Classifies a Write/Edit operation into one of three tiers:
- "fix":   small, low-risk edit (<20 lines AND no AST significance)
- "light": new function OR control-flow change OR 20-99 lines added
- "full":  new class OR >=100 lines added

The tier determines which /implement variant the gate directs the model
toward — `/implement --fix`, `/implement --light`, or `/implement` (full).

Pure module: only stdlib `ast` and `re`. No fs / network / subprocess.

Design Decisions:
- Python files: AST-based diff. We parse old and new and compare the sets of
  classes / functions / control-flow nodes / signatures. Edge cases that
  reduce to identical structures (comment-only, format-only, import reorder,
  type-hint-only, docstring-only) classify as `fix`.
- Non-Python code files: line-count fallback returning `light` as the safe
  default. We cannot AST-analyze them, but we still preserve enforcement
  without falsely upgrading to `full`.
- AST parse failure: degrade gracefully to the line-count rules.
- New-file Write (empty old_string): use new_string as added content;
  for Python, AST-parse new_string with an empty "old" tree.

Issue: #1142 (Phase 1 — default-on tier-aware Write Gate, Polarity Flip).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Tuple


# Tier thresholds (verbatim from plan).
TIER_FULL_LINE_THRESHOLD = 100
TIER_LIGHT_LINE_THRESHOLD = 20

# Python file extensions that trigger AST analysis. Everything else uses
# the line-count fallback.
_PYTHON_EXTENSIONS = {".py"}

# AST node types that count as "control flow" for tier classification.
_CONTROL_FLOW_NODES: tuple = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.With,
    ast.AsyncWith,
)

# Add Match (Python 3.10+) when available. ast.Match exists from 3.10.
if hasattr(ast, "Match"):
    _CONTROL_FLOW_NODES = _CONTROL_FLOW_NODES + (ast.Match,)


def _count_added_lines(old_string: str, new_string: str) -> int:
    """Count lines added by the edit.

    Conservative: returns the difference between new line count and old
    line count, clamped at 0. For new-file Write (empty old_string), this
    returns the full line count of new_string.
    """
    old_lines = len(old_string.splitlines()) if old_string else 0
    new_lines = len(new_string.splitlines()) if new_string else 0
    return max(0, new_lines - old_lines)


def _safe_parse(source: str) -> ast.Module | None:
    """Best-effort `ast.parse`. Returns None on SyntaxError or any AST error.

    We catch broadly because partial-edit content (Edit's `new_string` is
    a substring, not a full module) is expected to fail parsing often.
    Callers fall back to the line-count rule on None.
    """
    if not source.strip():
        # Empty source parses successfully but produces no info; treat as ok.
        return ast.parse("")
    try:
        return ast.parse(source)
    except (SyntaxError, ValueError, TypeError):
        return None


def _collect_function_names(tree: ast.Module) -> set[str]:
    """Return the set of top-level + nested function/method names in the tree.

    We include FunctionDef and AsyncFunctionDef at any depth, because new
    methods on classes also count as new functions for tier purposes.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
    return names


def _collect_class_names(tree: ast.Module) -> set[str]:
    """Return the set of class names defined anywhere in the tree."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            names.add(node.name)
    return names


def _count_control_flow(tree: ast.Module) -> int:
    """Count control-flow statements in the tree."""
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, _CONTROL_FLOW_NODES):
            count += 1
    return count


def _collect_signatures(tree: ast.Module) -> dict:
    """Return a map of function-name -> signature-fingerprint.

    Signature fingerprint is a tuple of (arg_names, return_annotation_repr).
    A signature change for an existing function is a `light`-tier signal.
    """
    sigs: dict = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            # Collect positional, vararg, kwonly, kwarg names.
            arg_names: list[str] = []
            arg_names.extend(a.arg for a in args.args)
            if args.vararg is not None:
                arg_names.append(f"*{args.vararg.arg}")
            arg_names.extend(a.arg for a in args.kwonlyargs)
            if args.kwarg is not None:
                arg_names.append(f"**{args.kwarg.arg}")
            # Return annotation as text (None if no annotation).
            ret = ast.unparse(node.returns) if node.returns is not None else ""
            sigs[node.name] = (tuple(arg_names), ret)
    return sigs


def _signatures_changed(old_sigs: dict, new_sigs: dict) -> bool:
    """Return True if any same-name function has a different signature."""
    for name, new_sig in new_sigs.items():
        if name in old_sigs and old_sigs[name] != new_sig:
            return True
    return False


def _strip_docstrings(tree: ast.Module) -> ast.Module:
    """Return a copy of the tree with leading docstring statements removed.

    Docstring-only edits should classify as `fix`. We strip docstrings so
    that two trees differing only in docstrings produce identical dumps.
    """
    new_tree = ast.parse(ast.unparse(tree)) if hasattr(ast, "unparse") else tree
    for node in ast.walk(new_tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                node.body = body[1:] or [ast.Pass()]
    return new_tree


def _strip_annotations(tree: ast.Module) -> ast.Module:
    """Return a copy of the tree with type annotations removed.

    Type-hint-only edits should classify as `fix`. We zero out function
    arg annotations and return annotations so that adding/removing type
    hints does not produce a structural diff.
    """
    new_tree = ast.parse(ast.unparse(tree)) if hasattr(ast, "unparse") else tree
    for node in ast.walk(new_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node.returns = None
            for a in node.args.args:
                a.annotation = None
            for a in node.args.kwonlyargs:
                a.annotation = None
            if node.args.vararg is not None:
                node.args.vararg.annotation = None
            if node.args.kwarg is not None:
                node.args.kwarg.annotation = None
        elif isinstance(node, ast.AnnAssign):
            # Replace `x: int = 1` with `x = 1` (or `x = None`).
            node.annotation = ast.Constant(value=None)
    return new_tree


def _normalize_imports(tree: ast.Module) -> ast.Module:
    """Sort top-level Import / ImportFrom statements by their source code.

    Import reordering is a `fix`. By sorting we make reordered imports
    produce identical dumps.
    """
    if not hasattr(ast, "unparse"):
        return tree
    new_tree = ast.parse(ast.unparse(tree))
    # Partition module body into imports and non-imports while preserving
    # the relative order of non-imports.
    imports = []
    others = []
    for stmt in new_tree.body:
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            imports.append(stmt)
        else:
            others.append(stmt)
    try:
        imports.sort(key=lambda s: ast.unparse(s))
    except Exception:
        # If sort fails for any reason, keep original order — still safe.
        pass
    new_tree.body = imports + others
    return new_tree


def _canonical_dump(tree: ast.Module) -> str:
    """Produce a canonical structural dump of the tree.

    Strips docstrings, annotations, and sorts imports so that edits that
    only touch those produce the same dump as the pre-edit tree.
    """
    try:
        t = _strip_docstrings(tree)
        t = _strip_annotations(t)
        t = _normalize_imports(t)
        return ast.dump(t, annotate_fields=False)
    except Exception:
        # On any failure, fall back to a raw dump — still deterministic.
        return ast.dump(tree, annotate_fields=False)


def _line_count_tier(added_lines: int) -> Tuple[str, str]:
    """Pure line-count classification used as fallback.

    <TIER_LIGHT_LINE_THRESHOLD          -> fix
    TIER_LIGHT_LINE_THRESHOLD..99       -> light
    >=TIER_FULL_LINE_THRESHOLD          -> full
    """
    if added_lines >= TIER_FULL_LINE_THRESHOLD:
        return ("full", f"+{added_lines} lines (>=100)")
    if added_lines >= TIER_LIGHT_LINE_THRESHOLD:
        return ("light", f"+{added_lines} lines (20-99)")
    return ("fix", f"+{added_lines} lines (<20)")


def _classify_python(old_string: str, new_string: str) -> Tuple[str, str]:
    """AST-based classification for Python edits.

    Returns (tier, reason). Falls back to line-count rules if either side
    fails to parse.
    """
    added = _count_added_lines(old_string, new_string)

    old_tree = _safe_parse(old_string)
    new_tree = _safe_parse(new_string)

    if old_tree is None or new_tree is None:
        # Partial-edit content commonly fails parsing — fall back to lines.
        return _line_count_tier(added)

    # Edge-case short-circuit: if the canonical (docstring/annotation-
    # stripped, imports-sorted) dumps match AND added lines are small,
    # this is a comment/format/import/type-hint/docstring-only edit -> fix.
    old_canon = _canonical_dump(old_tree)
    new_canon = _canonical_dump(new_tree)
    if old_canon == new_canon:
        return ("fix", "no structural change (comment/format/import/type-hint/docstring-only)")

    # Class additions -> full
    old_classes = _collect_class_names(old_tree)
    new_classes = _collect_class_names(new_tree)
    if new_classes - old_classes:
        return ("full", f"new class(es): {sorted(new_classes - old_classes)}")

    # Line-count full-tier upgrade
    if added >= TIER_FULL_LINE_THRESHOLD:
        return ("full", f"+{added} lines (>=100)")

    # New function -> light
    old_funcs = _collect_function_names(old_tree)
    new_funcs = _collect_function_names(new_tree)
    if new_funcs - old_funcs:
        return ("light", f"new function(s): {sorted(new_funcs - old_funcs)}")

    # Control-flow added -> light
    old_cf = _count_control_flow(old_tree)
    new_cf = _count_control_flow(new_tree)
    if new_cf > old_cf:
        return ("light", f"control-flow added (+{new_cf - old_cf})")

    # Signature change -> light
    old_sigs = _collect_signatures(old_tree)
    new_sigs = _collect_signatures(new_tree)
    if _signatures_changed(old_sigs, new_sigs):
        return ("light", "function signature change")

    # Line-count light-tier
    if added >= TIER_LIGHT_LINE_THRESHOLD:
        return ("light", f"+{added} lines (20-99)")

    return ("fix", f"+{added} lines (<20), no AST signal")


def classify_edit_tier(
    file_path: str,
    old_string: str,
    new_string: str,
) -> Tuple[str, str]:
    """Classify an edit into fix / light / full tier with a brief reason.

    Args:
        file_path: Target file path (string). Suffix determines whether
            AST analysis runs. Empty string is tolerated.
        old_string: Pre-edit content of the changed region. Empty for
            new-file Write.
        new_string: Post-edit content of the changed region. For new-file
            Write, this is the full file content.

    Returns:
        A tuple ``(tier, reason)`` where:
            - tier is one of ``"fix"``, ``"light"``, ``"full"``.
            - reason is a short human-readable explanation that callers
              can splat into block-message text.
    """
    old_string = old_string or ""
    new_string = new_string or ""

    suffix = Path(file_path).suffix.lower() if file_path else ""

    # Non-Python code file: line-count fallback, returning `light` as the
    # safe default per AC10. Even a 1-line .ts edit returns `light` —
    # preserves enforcement without false-positive `full` upgrades.
    if suffix not in _PYTHON_EXTENSIONS:
        added = _count_added_lines(old_string, new_string)
        if added >= TIER_FULL_LINE_THRESHOLD:
            return ("full", f"non-python +{added} lines (>=100)")
        return ("light", f"non-python file ({suffix or 'no-ext'}); safe default")

    # Python file: AST-based.
    return _classify_python(old_string, new_string)


# --------------------------------------------------------------------------
# Bash-to-code-file detection helpers (used by unified_pre_tool.py)
# --------------------------------------------------------------------------

# Code-file extensions for Bash detection. Mirrors CODE_EXTENSIONS in
# unified_pre_tool.py; kept local so this module remains self-contained.
_BASH_CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
    ".kt", ".scala", ".sh", ".bash", ".zsh", ".vue", ".svelte",
    ".dart",
}

# Patterns that are USER-DRIVEN PATCH TOOLING — always pass even when the
# command targets a code file.
_BASH_EXCLUDED_PREFIXES = ("git apply", "patch ")


def _bash_excluded(command: str) -> bool:
    """Return True if the command is patch tooling (git apply, patch < diff)."""
    stripped = command.strip()
    if not stripped:
        return False
    if stripped.startswith("git apply"):
        return True
    # `patch <file>` or `patch -p1 < diff` — the bare command starts with patch
    head = stripped.split(None, 1)[0]
    if head == "patch":
        return True
    return False


def _path_is_code_file(path: str) -> bool:
    """Return True if `path` has a known code-file extension."""
    if not path:
        return False
    # Strip surrounding quotes if present.
    p = path.strip().strip("'\"")
    if not p:
        return False
    suffix = Path(p).suffix.lower()
    return suffix in _BASH_CODE_EXTENSIONS


def detect_bash_code_file_write(command: str) -> Tuple[str, str]:
    """Return (target_path, pattern_name) if the bash command writes a code file.

    Scans for: redirect (`>`/`>>`/`>|`), `tee`/`tee -a`, `sed -i`, `cat > X`
    heredocs, `python -c "open(X, 'w')"`, `awk ... > X.py`, and best-effort
    base64-decoded heredocs.

    Returns ("", "") when no match or when the command is excluded patch
    tooling (`git apply`, `patch < diff`).

    Pure function: only regex, no fs/subprocess.
    """
    if not command:
        return ("", "")
    if _bash_excluded(command):
        return ("", "")

    # Pattern 1: tee / tee -a TARGET
    m = re.search(r"\btee\s+(?:-a\s+)?([^\s;&|<>]+)", command)
    if m:
        target = m.group(1)
        if _path_is_code_file(target):
            return (target, "tee")

    # Pattern 2: sed -i ... TARGET (in-place edit). The sed regex below
    # captures the last positional arg that looks like a path.
    m = re.search(
        r"\bsed\s+(?:-[A-Za-z]*i[A-Za-z]*)(?:\s+'[^']*'|\s+\"[^\"]*\"|\s+\S+)+\s+([^\s;&|<>]+)",
        command,
    )
    if m:
        target = m.group(1)
        if _path_is_code_file(target):
            return (target, "sed -i")

    # Pattern 3: cat > / cat >> / cat -- > TARGET (with optional heredoc later)
    m = re.search(r"\bcat\s+(?:--\s+)?[>]{1,2}\s*([^\s;&|<>]+)", command)
    if m:
        target = m.group(1)
        if _path_is_code_file(target):
            return (target, "cat redirect")

    # Pattern 4: heredoc into code file: << 'EOF' > X.py (or <<EOF > X.py)
    m = re.search(r"<<\s*[\'\"]?\w+[\'\"]?\s*[>]{1,2}\s*([^\s;&|<>]+)", command)
    if m:
        target = m.group(1)
        if _path_is_code_file(target):
            return (target, "heredoc redirect")

    # Pattern 5: python -c "..." or python3 -c "..." containing open(..., 'w')
    py_c_match = re.search(
        r"python3?\s+-c\s+(?:\"([^\"]+)\"|'([^']+)')",
        command,
    )
    if py_c_match:
        body = py_c_match.group(1) or py_c_match.group(2) or ""
        # Look for open('X.py', 'w') / open("X.py", "w") inside the snippet.
        open_match = re.search(
            r"open\s*\(\s*[\'\"]([^\'\"]+)[\'\"]\s*,\s*[\'\"][wa][\'\"+b]*[\'\"]",
            body,
        )
        if open_match:
            target = open_match.group(1)
            if _path_is_code_file(target):
                return (target, "python -c open()")
        # Path('X.py').write_text(...) / Path("X.py").write_bytes(...)
        path_match = re.search(
            r"Path\s*\(\s*[\'\"]([^\'\"]+)[\'\"]\s*\)\s*\.\s*write_(?:text|bytes)\b",
            body,
        )
        if path_match:
            target = path_match.group(1)
            if _path_is_code_file(target):
                return (target, "python -c Path.write_*")

    # Pattern 6: base64-decoded heredoc to code file
    #   echo "<b64>" | base64 -d > X.py
    m = re.search(
        r"\bbase64\s+(?:-d|--decode)\b[^|;]*[>]{1,2}\s*([^\s;&|<>]+)",
        command,
    )
    if m:
        target = m.group(1)
        if _path_is_code_file(target):
            return (target, "base64 decode redirect")

    # Pattern 7: awk '...' > X.py
    m = re.search(r"\bawk\s+[\'\"][^\'\"]+[\'\"][^|;]*[>]{1,2}\s*([^\s;&|<>]+)", command)
    if m:
        target = m.group(1)
        if _path_is_code_file(target):
            return (target, "awk redirect")

    # Pattern 8: generic redirect to code file (catch-all). Skip stderr
    # redirects (2>, 2>>).
    for m in re.finditer(r"(?<![0-9])[>]{1,2}\s*([^\s;&|<>]+)", command):
        target = m.group(1)
        if target in {"/dev/null", "/dev/stderr", "/dev/stdout", "&1", "&2"}:
            continue
        if _path_is_code_file(target):
            return (target, "redirect")

    return ("", "")


__all__ = [
    "classify_edit_tier",
    "detect_bash_code_file_write",
    "TIER_FULL_LINE_THRESHOLD",
    "TIER_LIGHT_LINE_THRESHOLD",
]
