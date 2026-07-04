#!/usr/bin/env python3
"""Edit tier classifier — Phase 1 default-on Write/Edit gate (Issue #1142+).

Classifies a Write/Edit operation into one of three tiers:
- "fix":   small, low-risk edit (<20 lines AND no AST significance)
- "light": new function OR control-flow change OR 20-99 lines added
- "full":  new class OR >=100 lines added

The tier determines which /implement variant the gate directs the model
toward — `/implement --fix`, `/implement --light`, or `/implement` (full).

Pure module: only stdlib `ast`, `re`, and `os`. No fs / network / subprocess.

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
import os
import re
from pathlib import Path
from typing import Tuple

# Phase 2 (Issue #1153): shared heredoc-strip utility. Defensive import so
# this module remains usable from contexts where the lib/ directory is not on
# sys.path (e.g., when loaded by importlib.util from the hook). When the
# import fails we fall back to a no-op strip — preserving existing behavior
# rather than crashing the classifier.
try:
    from heredoc_utils import strip_heredoc_content as _strip_heredoc_content
except Exception:  # pragma: no cover — defensive
    try:
        import importlib.util as _hu_ilu
        _hu_path = Path(__file__).resolve().parent / "heredoc_utils.py"
        if _hu_path.exists():
            _hu_spec = _hu_ilu.spec_from_file_location("heredoc_utils", str(_hu_path))
            if _hu_spec and _hu_spec.loader:
                _hu_mod = _hu_ilu.module_from_spec(_hu_spec)
                _hu_spec.loader.exec_module(_hu_mod)
                _strip_heredoc_content = _hu_mod.strip_heredoc_content
            else:
                def _strip_heredoc_content(command: str) -> str:  # type: ignore[misc]
                    return command
        else:
            def _strip_heredoc_content(command: str) -> str:  # type: ignore[misc]
                return command
    except Exception:
        def _strip_heredoc_content(command: str) -> str:  # type: ignore[misc]
            return command


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


# Phase 2 item (3) (Issue #1154): chained-statement variable resolution.
#
# Resolves `VAR=value; cat > "$VAR"` style commands so the downstream
# regex matchers see the literal target path. Scope is intentionally
# narrow:
#   - In-scope separators: ';' and '\n'.
#   - In-scope RHS form: single literal token (`OUT=foo.py`, `OUT='foo.py'`).
#   - Out-of-scope RHS (residual evasion paths — documented):
#       * Command substitution: `$(cmd)`, backticks.
#       * Default-value/conditional assignment: `${VAR:-default}`, `: ${VAR:=foo}`.
#       * Array expansion / concatenation.
#   - In-scope LHS dereference forms: `"$NAME"`, `${NAME}`, `$NAME`.
#
# This pre-pass runs BEFORE pattern matching so the existing Pattern 3,
# Pattern 4, etc., see the resolved literal — no per-pattern changes.

# Variable assignment: VAR=value at start of segment or after ; / newline.
# RHS may be a bareword, single-quoted, or double-quoted literal — NO
# command substitution, NO default-value forms.
_CHAINED_ASSIGN_RE = re.compile(
    r"""
    (?:^|[;\n])             # segment boundary
    \s*
    ([A-Za-z_][A-Za-z0-9_]*) # variable name
    =
    (                       # value (one of three literal forms)
        '[^'\n]*'           #   single-quoted
        | "[^"$`\\\n]*"       #   double-quoted, NO $, backtick, backslash, or newline (rejects $(...) , `...`, expansions)
        | [^\s;'\"<>|&`$]+   #   bareword: NO whitespace, separators, redirects, $, or `
    )
    """,
    re.VERBOSE,
)


def _resolve_chained_assignments(command: str) -> str:
    """Substitute simple chained variable assignments into their dereferences.

    See module-level comment for the in-scope grammar. Out-of-scope forms
    are left unresolved on purpose — the result is the input with the
    in-scope substitutions applied. Out-of-scope RHS values (anything
    containing ``$``, backtick, etc., in either the bareword or double-
    quoted form) are NOT collected, so the dereference sites for those
    variables stay literal ``"$OUT"`` and downstream patterns will not
    spuriously match.

    Args:
        command: The raw Bash command string.

    Returns:
        A new command string with ``"$VAR"`` / ``${VAR}`` / ``$VAR``
        replaced by the literal RHS for each in-scope assignment. The
        substitution is positional — only dereferences AFTER the
        assignment in the original string are replaced.
    """
    if not command:
        return command
    if "=" not in command:
        return command

    out_chars = list(command)

    for m in _CHAINED_ASSIGN_RE.finditer(command):
        name = m.group(1)
        raw_value = m.group(2)

        # Strip quotes from the value (single or double). After this point
        # the value is a plain literal token. Note the regex already
        # rejects $ / backtick inside the double-quoted form, so we cannot
        # arrive here with command substitution.
        if raw_value.startswith("'") and raw_value.endswith("'"):
            value = raw_value[1:-1]
        elif raw_value.startswith('"') and raw_value.endswith('"'):
            value = raw_value[1:-1]
        else:
            value = raw_value

        # Reject empty values — substitution is pointless.
        if not value:
            continue

        # Build a regex that matches the three in-scope LHS dereference
        # forms. ``\b`` after $NAME prevents matching $FOOBAR when name is
        # FOO.
        deref_pat = re.compile(
            r'(?:"\$' + re.escape(name) + r'"|\$\{' + re.escape(name) +
            r'\}|\$' + re.escape(name) + r'(?![A-Za-z0-9_]))'
        )

        # Substitute only at positions AFTER the assignment site to avoid
        # spurious replacement when the same variable name appears earlier
        # for an unrelated purpose. Operate on the current out_chars buffer
        # so chained renames see prior substitutions.
        current = "".join(out_chars)
        # Locate the assignment in the CURRENT buffer (positions may have
        # shifted after a prior substitution). Fall back to the original
        # match end if not found.
        cur_assign_re = re.compile(
            r'(?:^|[;\n])\s*' + re.escape(name) + r'='
        )
        am = cur_assign_re.search(current)
        if am is None:
            search_from = m.end()
        else:
            # Skip past the assignment + RHS by finding the end-of-token.
            # Conservative: start search at am.end() — substitutions of
            # the RHS itself are harmless (RHS contains no dereferences in
            # the in-scope grammar).
            search_from = am.end()

        prefix = current[:search_from]
        suffix = current[search_from:]
        substituted_suffix = deref_pat.sub(value, suffix)
        out_chars = list(prefix + substituted_suffix)

    return "".join(out_chars)



def _is_temp_path(path: str) -> bool:
    """Check if a path is in a temporary directory (Issue #1355).
    
    Returns True if the path starts with /tmp/, /var/tmp/, or $TMPDIR.
    """
    if not path:
        return False
    # Strip quotes if present
    p = path.strip().strip('\'"')
    if not p:
        return False
    
    # Check for absolute temp paths
    if p.startswith('/tmp/') or p.startswith('/var/tmp/'):
        return True
    
    # Check for TMPDIR environment variable
    tmpdir = os.environ.get('TMPDIR', '/tmp')
    if tmpdir and p.startswith(tmpdir + '/'):
        return True
    
    return False


def detect_bash_code_file_write(command: str) -> Tuple[str, str]:
    """Return (target_path, pattern_name) if the bash command writes a code file.

    Scans for: redirect (`>`/`>>`/`>|`), `tee`/`tee -a`, `sed -i`, `cat > X`
    heredocs, `python -c "open(X, 'w')"`, `awk ... > X.py`, and best-effort
    base64-decoded heredocs.

    Returns ("", "") when no match or when the command is excluded patch
    tooling (`git apply`, `patch < diff`), or when targeting /tmp or similar
    temporary directories (Issue #1355).

    Pure function: only regex, no fs/subprocess.
    """
    if not command:
        return ("", "")
    if _bash_excluded(command):
        return ("", "")

    # Phase 2 (Issue #1153): strip heredoc bodies before scanning so a
    # literal `cat > X.py` example sitting inside a heredoc body (e.g. inside
    # a `gh issue create --body <<HD ... HD` payload) does NOT produce a
    # false-positive code-file write detection. Same precedent as
    # unified_pre_tool.py:_check_state_file_deletion (#866). The plan
    # specifies prepending before Pattern 3 (cat redirect) and Pattern 4
    # (heredoc redirect); in practice the user-supplied content inside a
    # heredoc body can also fall through to the generic Pattern 8 redirect
    # catch-all, so we apply the strip to the buffer used by ALL pattern
    # matchers. Patterns 1/2 (tee / sed -i) are also driven by user-content
    # so they likewise scan the stripped buffer.
    #
    # Phase 2 (Issue #1154): resolve in-scope chained-statement variable
    # assignments so `OUT=foo.py; cat > "$OUT"` is detected. The pre-pass is
    # intentionally narrow — see _resolve_chained_assignments docstring for
    # the residual evasion paths.
    stripped = _strip_heredoc_content(command)
    stripped = _resolve_chained_assignments(stripped)

    # Pattern 1: tee / tee -a TARGET
    m = re.search(r"\btee\s+(?:-a\s+)?([^\s;&|<>]+)", stripped)
    if m:
        target = m.group(1)
        # Issue #1355: Skip temp paths
        if _is_temp_path(target):
            return ("", "")
        if _path_is_code_file(target):
            return (target, "tee")

    # Pattern 2: sed -i ... TARGET (in-place edit). The sed regex below
    # captures the last positional arg that looks like a path.
    m = re.search(
        r"\bsed\s+(?:-[A-Za-z]*i[A-Za-z]*)(?:\s+'[^']*'|\s+\"[^\"]*\"|\s+\S+)+\s+([^\s;&|<>]+)",
        stripped,
    )
    if m:
        target = m.group(1)
        # Issue #1355: Skip temp paths
        if _is_temp_path(target):
            return ("", "")
        if _path_is_code_file(target):
            return (target, "sed -i")

    # Pattern 3: cat > / cat >> / cat -- > TARGET (with optional heredoc later)
    # Scans the heredoc-stripped + variable-resolved buffer (#1153, #1154).
    m = re.search(r"\bcat\s+(?:--\s+)?[>]{1,2}\s*([^\s;&|<>]+)", stripped)
    if m:
        target = m.group(1)
        # Issue #1355: Skip temp paths
        if _is_temp_path(target):
            return ("", "")
        if _path_is_code_file(target):
            return (target, "cat redirect")

    # Pattern 4: heredoc into code file: << 'EOF' > X.py (or <<EOF > X.py).
    #
    # IMPORTANT: this pattern matches the redirect on the heredoc OPENER
    # line itself, NOT inside the heredoc body. The opener line is shell
    # syntax that the shell executes — the body is user-supplied text. So
    # this pattern scans the ORIGINAL ``command`` (not ``stripped``) because
    # ``_strip_heredoc_content`` removes the opener line along with the body
    # (the regex is greedy from ``<<DELIM`` through ``\nDELIM\n``).
    #
    # The chained-assignment resolver still helps here when the form is
    # ``OUT=foo.py; cat <<EOF > "$OUT"`` — we apply variable resolution to
    # the original command (without the body strip) for this pattern.
    pattern4_buf = _resolve_chained_assignments(command)
    m = re.search(
        r"<<\s*[\'\"]?\w+[\'\"]?\s*[>]{1,2}\s*([^\s;&|<>]+)", pattern4_buf
    )
    if m:
        target = m.group(1)
        # Issue #1355: Skip temp paths
        if _is_temp_path(target):
            return ("", "")
        if _path_is_code_file(target):
            return (target, "heredoc redirect")

    # Pattern 5: python -c "..." or python3 -c "..." containing open(..., 'w').
    # Note: we deliberately scan the ORIGINAL ``command`` for the python -c
    # wrapper because the python snippet body is a quoted string the shell
    # passes verbatim — NOT a heredoc body the user might paste example code
    # into. The example we are protecting against in #1153 is a heredoc body
    # mentioning shell redirects, not a python -c invocation.
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
            # Issue #1355: Skip temp paths
            if _is_temp_path(target):
                return ("", "")
            if _path_is_code_file(target):
                return (target, "python -c open()")
        # Path('X.py').write_text(...) / Path("X.py").write_bytes(...)
        path_match = re.search(
            r"Path\s*\(\s*[\'\"]([^\'\"]+)[\'\"]\s*\)\s*\.\s*write_(?:text|bytes)\b",
            body,
        )
        if path_match:
            target = path_match.group(1)
            # Issue #1355: Skip temp paths
            if _is_temp_path(target):
                return ("", "")
            if _path_is_code_file(target):
                return (target, "python -c Path.write_*")

    # Pattern 6: base64-decoded heredoc to code file
    #   echo "<b64>" | base64 -d > X.py
    m = re.search(
        r"\bbase64\s+(?:-d|--decode)\b[^|;]*[>]{1,2}\s*([^\s;&|<>]+)",
        stripped,
    )
    if m:
        target = m.group(1)
        # Issue #1355: Skip temp paths
        if _is_temp_path(target):
            return ("", "")
        if _path_is_code_file(target):
            return (target, "base64 decode redirect")

    # Pattern 7: awk '...' > X.py
    m = re.search(r"\bawk\s+[\'\"][^\'\"]+[\'\"][^|;]*[>]{1,2}\s*([^\s;&|<>]+)", stripped)
    if m:
        target = m.group(1)
        # Issue #1355: Skip temp paths
        if _is_temp_path(target):
            return ("", "")
        if _path_is_code_file(target):
            return (target, "awk redirect")

    # Pattern 8: generic redirect to code file (catch-all). Skip stderr
    # redirects (2>, 2>>). Scans the heredoc-stripped + variable-resolved
    # buffer to avoid false positives on heredoc-body content (#1153).
    for m in re.finditer(r"(?<![0-9])[>]{1,2}\s*([^\s;&|<>]+)", stripped):
        target = m.group(1)
        if target in {"/dev/null", "/dev/stderr", "/dev/stdout", "&1", "&2"}:
            continue
        # Issue #1355: Skip temp paths
        if _is_temp_path(target):
            continue
        if _path_is_code_file(target):
            return (target, "redirect")

    return ("", "")



# Heredoc opener — captures the delimiter word so we can pair it with the
# closing line. Mirrors the strip regex in ``heredoc_utils`` but extracts
# the body instead of removing it. Used by ``extract_heredoc_body_for_redirect``
# (Issue #1154 remediation) to feed the body into the AST classifier so a
# `cat > X.py << EOF\nclass X: pass\nEOF` style fresh-file write classifies
# as ``tier=full`` (new class), not the line-count default of ``light``/``fix``.
_HEREDOC_BODY_RE = re.compile(
    r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n(.*?\n)[ \t]*\1\b",
    re.DOTALL,
)


def extract_heredoc_body_for_redirect(command: str) -> str:
    """Return the first heredoc body in a Bash command, or "" if none.

    Used by the hook's Bash code-file gate (Issue #1154 remediation) to
    classify ``cat > X.py << EOF\\n<body>\\nEOF`` style fresh-file writes
    using the AST analysis on the body content. The body is the new file's
    full content, so feeding it through ``classify_edit_tier(path, "", body)``
    correctly returns ``tier=full`` for new-class / new-function content.

    Conservative: returns the first heredoc body found. If multiple heredocs
    are nested (the AC2 ``gh issue create --body-file - <<HD ... HD`` shape),
    the OUTER body is returned; the inner heredoc is part of the outer body
    text. The detector itself (``detect_bash_code_file_write``) is responsible
    for not matching nested-heredoc-body content (Pattern 3 scans the
    heredoc-stripped buffer), so this helper is only invoked AFTER a code-file
    target has been detected — meaning the outer body genuinely IS the
    file's new content.

    Args:
        command: The raw Bash command string.

    Returns:
        The heredoc body text, or empty string when no heredoc is found
        or the regex engine raises.
    """
    if not command or "<<" not in command:
        return ""
    try:
        m = _HEREDOC_BODY_RE.search(command)
    except re.error:
        return ""
    if m is None:
        return ""
    # Group 2 is the body (everything between the opener line and the
    # closing delimiter line). Trailing newline is preserved so line counts
    # match what the AST parser sees.
    return m.group(2) or ""


# Patterns that represent fresh-file creation (write the entire file in one
# shot, not an incremental edit). For these patterns, when we can extract a
# heredoc body, we feed the body through the classifier so a new-class /
# new-function signal upgrades the tier from the line-count default.
#
# NOT included (intentionally): ``sed -i`` (in-place edit, not a fresh file),
# ``tee -a`` (append, not truncate). Pattern 1 ``tee`` without ``-a`` IS a
# fresh-file form but we don't currently distinguish; the line-count fallback
# (`light`) is the safe default for tee.
_FRESH_FILE_WRITE_PATTERNS = frozenset(
    {
        "cat redirect",
        "heredoc redirect",
        "base64 decode redirect",
        "awk redirect",
        "redirect",
    }
)


def is_fresh_file_write_pattern(pattern: str) -> bool:
    """Return True if ``pattern`` represents a fresh-file (whole-file) write.

    Used by the hook (Issue #1154 remediation) to decide whether to try
    upgrading the tier from the line-count default by re-classifying with
    the heredoc body as ``new_string``. Membership-check only — pure
    function.

    Args:
        pattern: The pattern name returned by ``detect_bash_code_file_write``.

    Returns:
        True when the pattern truncates/creates the target file
        (semantic ``>`` write); False for append-only or in-place forms.
    """
    return pattern in _FRESH_FILE_WRITE_PATTERNS


__all__ = [
    "classify_edit_tier",
    "detect_bash_code_file_write",
    "extract_heredoc_body_for_redirect",
    "is_fresh_file_write_pattern",
    "TIER_FULL_LINE_THRESHOLD",
    "TIER_LIGHT_LINE_THRESHOLD",
]
