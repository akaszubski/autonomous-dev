"""Per-hook timing telemetry (Issue #1012, W0).

Single canonical surface for recording how long each hook invocation takes.
The library is independent of :mod:`hook_telemetry` — they are sibling
modules writing to different files (``hook-blocks.jsonl`` vs
``hook_timings_YYYY-MM-DD.jsonl``) so the deny-decision telemetry surface
and the per-invocation timing surface can evolve independently.

Each ``HookTimer`` context manager invocation emits one JSONL row to
``~/.claude/logs/hook_timings_YYYY-MM-DD.jsonl``. The schema is stable:
``{ts, hook, dur_ns, decision_shape, schema_version}``.

``decision_shape`` semantics (schema_version 2)
-----------------------------------------------

Schema 1 classified *any* exception reaching ``HookTimer.__exit__`` as
``"exception"`` — including ``SystemExit``. But ``sys.exit(0)`` inside the
timer scope is the normal, correct **success** termination for most hooks,
so successful invocations and genuine crashes were recorded identically and
the column could not answer the one question it exists to answer. Schema 2
separates them:

===========================================  ====================
Termination                                  ``decision_shape``
===========================================  ====================
Normal return from ``main()``                the hook's shape (default ``"allow"``)
``sys.exit(0)`` / ``sys.exit(None)``         the hook's shape (default ``"allow"``)
``sys.exit(N)`` for truthy ``N``             ``"exit_nonzero"`` (unless the hook set a shape)
Unhandled non-``SystemExit`` exception       ``"exception"``
``SystemExit`` marked as a crash conversion  ``"exception"``
===========================================  ====================

The last row is the subtle one. :func:`hook_safety.safe_main` converts an
unhandled crash into ``SystemExit(0)`` so a broken hook never blocks Claude
Code. Exempting ``SystemExit`` naively would therefore relabel real crashes
as successes — strictly worse than the original defect, because it hides
failures rather than merely over-reporting them. ``safe_main`` marks the
``SystemExit`` it synthesises (see :func:`mark_crash_exit`) so a timer that
observes it still records ``"exception"``.

**Ordering note (established empirically, not by inspection).** In the
production topology every hook uses ``safe_main(_timed_main)`` — the timer
lives *inside* the wrap — so ``HookTimer.__exit__`` runs BEFORE
``safe_main``'s handler and observes the raw exception (e.g.
``RuntimeError``), never the converted ``SystemExit``. The crash marker is
therefore belt-and-braces for that topology: it is load-bearing only if a
hook ever nests ``safe_main`` *inside* the timer, where ``__exit__`` sees a
bare ``SystemExit(0)`` that is indistinguishable from success without it.
Both topologies are covered so the classification does not silently invert
if the wrapping order is ever changed.

Historical log files written under schema 1 are deliberately NOT rewritten;
:data:`SCHEMA_VERSION` is how a reader tells the two eras apart and avoids
averaging across the correction.

Design constraints (mirrored from :mod:`hook_telemetry`):

- Telemetry must NEVER raise. A logging or filesystem failure must NEVER
  block the underlying hook decision — the hook decision is the
  load-bearing path, telemetry is best-effort.
- Read-only filesystem fallback writes the JSON line to stderr instead.
- ``HOOK_TIMING_DISABLED=<truthy>`` env var is the rollback switch.
- ``HOOK_TIMING_DIR`` env var redirects the daily log directory (used by
  tests and the baseline capture script).
- The timer uses :func:`time.perf_counter_ns` so durations are recorded
  with monotonic, sub-millisecond precision (PEP 564).

Why home-dir path: hooks fire across many cwds within a single Claude
Code session. Using ``Path.home() / ".claude" / "logs"`` produces a
single user-global stream the report consumer can read without
reconciling per-project log files.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

LOG_DIR_RELATIVE_HOME: Path = Path(".claude") / "logs"
LOG_FILE_PREFIX: str = "hook_timings_"
LOG_FILE_SUFFIX: str = ".jsonl"

DISABLE_ENV_VAR: str = "HOOK_TIMING_DISABLED"
LOG_DIR_OVERRIDE_ENV_VAR: str = "HOOK_TIMING_DIR"

MAX_DECISION_SHAPE_LENGTH: int = 64
MAX_HOOK_NAME_LENGTH: int = 128

# Schema 2 corrects ``decision_shape`` classification: ``sys.exit(0)`` inside
# the timer scope is the SUCCESS path and no longer records ``"exception"``.
# Rows with ``schema_version == 1`` predate the correction and over-report
# ``"exception"`` for every hook that terminates via ``sys.exit()``; readers
# MUST NOT aggregate shape counts across the two versions.
SCHEMA_VERSION: int = 2

# ``decision_shape`` values this module produces on its own (hooks may set
# any other value via :meth:`HookTimer.set_decision_shape`).
SHAPE_EXCEPTION: str = "exception"
SHAPE_EXIT_NONZERO: str = "exit_nonzero"
SHAPE_DEFAULT: str = "allow"

# Issue #1704: rollback switch for the budget-overrun record ONLY. Setting it
# leaves timing rows intact and silences the ``hook-blocks.jsonl`` side effect.
BUDGET_OVERRUN_DISABLE_ENV_VAR: str = "HOOK_BUDGET_OVERRUN_DISABLED"

# Issue #1704 remediation (W7). The smallest budget any hook declares. No
# invocation shorter than this can possibly be an overrun, so the check
# short-circuits here BEFORE importing ``hook_budgets`` and reading a ~9KB
# JSON file. MEASURED: that import+read costs 3.28ms median in a fresh process
# (n=15) -- +51% on ``unified_pre_tool``'s 6.4ms p50, paid on ~89k invocations
# per week to detect 23 events.
#
# The value is a LITERAL here on purpose: importing ``hook_budgets`` to learn it
# would pay exactly the cost being avoided. ``hook_budgets.OVERRUN_FLOOR_SECONDS``
# is the AUTHORITY; this is its mirror. Two tests lock the relationship:
# ``test_min_budget_ns_matches_the_canonical_minimum`` (mirror == authority) and
# ``check_ceiling``'s refusal of any budget below the floor, so a budget that
# would overrun undetectably is refused at the config rather than only noticed
# by a repo-local test a consumer never runs.
MIN_BUDGET_SECONDS: int = 3
MIN_BUDGET_NS: int = MIN_BUDGET_SECONDS * 1_000_000_000

# Attribute name stamped onto a ``SystemExit`` that :func:`hook_safety.safe_main`
# synthesised from an unhandled crash. Kept as a module constant because
# ``hook_safety`` must agree on the spelling; a cross-validation test locks
# the two together.
CRASH_EXIT_ATTR: str = "_hook_safety_crash"

# Owner-only permissions for the timing log file (Issue #1056, Finding 2).
# Multi-user systems must not expose internal hook timing data to other users.
LOG_FILE_MODE: int = 0o600

_FALSY_ENV_VALUES = frozenset({"", "0", "false", "no", "off"})

# Path-detection regex used by :func:`_sanitize_os_error` (Issue #1056,
# Finding 3). Matches POSIX absolute paths (``/...``) AND optionally
# quoted variants such as ``'/foo/bar'`` or ``"/foo/bar"``. The match is
# intentionally greedy on non-whitespace, non-quote characters so paths
# containing spaces (which OSError strings typically wrap in quotes) are
# still captured by the quoted-path branch.
_ABS_PATH_PATTERN = re.compile(
    r"""(?P<quoted>['"])(?P<qpath>/[^'"\n]+)(?P=quoted)|(?P<path>/[^\s'"]+)""",
    re.VERBOSE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_timing_disabled() -> bool:
    """Return True iff timing telemetry is disabled via env var.

    Truthy: any non-empty string NOT in ``{"0", "false", "no", "off"}``.
    """
    raw = os.environ.get(DISABLE_ENV_VAR)
    if raw is None:
        return False
    return raw.strip().lower() not in _FALSY_ENV_VALUES


def _resolve_log_dir(override: Optional[Path] = None) -> Path:
    """Resolve the directory where timing JSONL files are written.

    Resolution order:

    1. The ``override`` argument (used by tests / baseline capture).
    2. ``HOOK_TIMING_DIR`` environment variable.
    3. ``Path.home() / ".claude" / "logs"`` (the production default).
    """
    if override is not None:
        return override

    env_override = os.environ.get(LOG_DIR_OVERRIDE_ENV_VAR)
    if env_override:
        return Path(env_override)

    return Path.home() / LOG_DIR_RELATIVE_HOME


def _resolve_log_path(override: Optional[Path] = None) -> Path:
    """Resolve the daily-rotated JSONL path for today's UTC date."""
    log_dir = _resolve_log_dir(override)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return log_dir / f"{LOG_FILE_PREFIX}{today}{LOG_FILE_SUFFIX}"


def _sanitize_os_error(exc: BaseException) -> str:
    """Return a stringified OSError with full paths replaced by basenames.

    OSError messages from the standard library frequently embed absolute
    paths (``[Errno 13] Permission denied: '/Users/alice/.claude/logs/x'``).
    Surfacing those raw to stderr leaks internal directory structure to
    anyone reading stderr — including subordinate processes, log
    aggregators, and CI artifacts. This helper rewrites every absolute
    path in the message to just its basename via :class:`pathlib.PurePosixPath`,
    so the failing filename is still visible without revealing the
    surrounding directory tree.

    Handles paths with spaces (when quoted in the message), paths under
    ``/Users/``, ``/tmp/``, ``/home/``, and arbitrary depths. The
    ``filename`` and ``filename2`` attributes (which OSError carries
    separately from the message) are also substituted out of the rendered
    string when they appear, so a custom ``__str__`` that includes them
    is still sanitized.

    Args:
        exc: An OSError (or any BaseException — non-OSError input is
            rendered with ``str()`` and run through the same substitution).

    Returns:
        A safe-to-log string with only basename references.
    """
    try:
        raw = str(exc)
    except Exception:
        return "<unrepresentable error>"

    def _replace(match: "re.Match[str]") -> str:
        qpath = match.group("qpath")
        path = match.group("path")
        full = qpath if qpath is not None else path
        try:
            base = Path(full).name or full
        except Exception:
            base = full
        if qpath is not None:
            quote = match.group("quoted")
            return f"{quote}{base}{quote}"
        return base

    sanitized = _ABS_PATH_PATTERN.sub(_replace, raw)

    # OSError carries filename/filename2 attributes; some Python builds
    # render them outside the main message in subclasses. Substitute any
    # surviving full-path mentions of those attributes too.
    for attr in ("filename", "filename2"):
        try:
            value = getattr(exc, attr, None)
        except Exception:
            value = None
        if isinstance(value, (str, bytes, os.PathLike)):
            try:
                full = os.fspath(value)
            except (TypeError, ValueError):
                continue
            if isinstance(full, bytes):
                try:
                    full = full.decode("utf-8", errors="replace")
                except Exception:
                    continue
            if full and full.startswith("/") and full in sanitized:
                try:
                    base = Path(full).name or full
                except Exception:
                    base = full
                sanitized = sanitized.replace(full, base)

    return sanitized


# ---------------------------------------------------------------------------
# Crash marking (Issue: sys.exit(0) misclassified as "exception")
# ---------------------------------------------------------------------------

# Process-global "a crash was converted to SystemExit" flag. Hooks are
# single-shot, single-threaded processes, so a plain module global is
# sufficient and avoids the ordering subtleties of context vars. The flag is
# cleared by ``HookTimer.__enter__`` so a timer never inherits a crash that
# happened before its own scope opened.
_crash_noted: bool = False


def note_crash() -> None:
    """Record that an unhandled crash was converted into a ``SystemExit``.

    Called by :func:`hook_safety.safe_main` on its crash path. A subsequent
    :meth:`HookTimer.__exit__` that observes a ``SystemExit`` will record
    ``"exception"`` rather than treating it as the success path.

    NEVER raises.
    """
    global _crash_noted
    _crash_noted = True


def clear_crash() -> None:
    """Reset the process-global crash flag. NEVER raises."""
    global _crash_noted
    _crash_noted = False


def crash_noted() -> bool:
    """Return True iff a crash-to-``SystemExit`` conversion was recorded."""
    return _crash_noted


def mark_crash_exit(exc: BaseException) -> BaseException:
    """Stamp ``exc`` as a crash-converted exit and set the process flag.

    Two redundant channels are used because they fail in different ways:
    the attribute survives even if the exception is caught and re-raised
    through code that does not know about this module, while the module
    flag survives if the exception object itself is replaced en route.

    Args:
        exc: The ``SystemExit`` synthesised from an unhandled exception.

    Returns:
        The same ``exc``, for call-site chaining.
    """
    try:
        setattr(exc, CRASH_EXIT_ATTR, True)
    except Exception:
        # Some exception types forbid attribute assignment; the module-level
        # flag below is the fallback channel.
        pass
    note_crash()
    return exc


def _is_crash_exit(exc: Optional[BaseException]) -> bool:
    """Return True iff this ``SystemExit`` represents a converted crash."""
    try:
        if getattr(exc, CRASH_EXIT_ATTR, False):
            return True
    except Exception:
        pass
    return crash_noted()


def _classify_exit(
    exc_type: Optional[type],
    exc: Optional[BaseException],
    *,
    decision_shape: str,
    explicitly_set: bool,
) -> str:
    """Map how a timed block terminated onto a ``decision_shape`` value.

    See the module docstring for the full truth table and rationale.

    Args:
        exc_type: The exception type propagating out of the ``with`` block,
            or ``None`` for a normal return.
        exc: The exception instance (may be ``None`` even when ``exc_type``
            is not, for hand-constructed ``__exit__`` calls).
        decision_shape: The shape the hook reported for itself.
        explicitly_set: Whether the hook actually called
            :meth:`HookTimer.set_decision_shape` (as opposed to inheriting
            the ``"allow"`` default).

    Returns:
        The ``decision_shape`` string to record.
    """
    # Normal return: the hook's own report stands.
    if exc_type is None:
        return decision_shape

    # A genuine unhandled exception. This is the branch that catches real
    # crashes in the production (outer-wrap) topology, where the timer sees
    # the raw exception before ``safe_main`` ever converts it.
    if not (isinstance(exc_type, type) and issubclass(exc_type, SystemExit)):
        return SHAPE_EXCEPTION

    # ``SystemExit`` is deliberate — UNLESS hook_safety manufactured it from
    # a crash. Checking the marker first is what stops the fix from
    # inverting the defect and relabelling crashes as successes.
    if _is_crash_exit(exc):
        return SHAPE_EXCEPTION

    code = getattr(exc, "code", None)
    if code is None or code == 0:
        # ``sys.exit(0)`` is the normal success termination for hooks.
        return decision_shape

    # Deliberate non-zero exit: neither success nor crash. Recording it as
    # "allow" would hide blocking behaviour; recording it as "exception"
    # would repeat the original defect in miniature. A hook that reported a
    # shape for itself is more specific than the exit code, so that wins.
    return decision_shape if explicitly_set else SHAPE_EXIT_NONZERO


def _normalize_decision_shape(shape: str) -> str:
    """Coerce ``shape`` to a short, well-formed ASCII string.

    - Non-strings are coerced via ``str(...)``.
    - Strings longer than :data:`MAX_DECISION_SHAPE_LENGTH` are truncated.
    - On any failure, ``"unknown"`` is returned.
    """
    try:
        s = str(shape)
    except Exception:
        return "unknown"
    if len(s) > MAX_DECISION_SHAPE_LENGTH:
        s = s[:MAX_DECISION_SHAPE_LENGTH]
    return s


def emit_timing_event(
    *,
    hook_name: str,
    dur_ns: int,
    decision_shape: str = "unknown",
    log_dir: Optional[Path] = None,
) -> None:
    """Append one JSONL row for a single hook invocation.

    Writes to ``<log_dir>/hook_timings_YYYY-MM-DD.jsonl`` with the schema
    ``{ts, hook, dur_ns, decision_shape, schema_version}``. Auto-creates
    the directory if missing. On any OSError (read-only FS, permission
    denied, JSON-serialization error), falls back to writing the JSON
    line to stderr prefixed with ``[hook-timing]``.

    This function NEVER raises. Telemetry must never block hooks.

    Args:
        hook_name: Filename of the hook (e.g. ``"unified_pre_tool.py"``).
        dur_ns: Duration of the hook invocation in nanoseconds.
        decision_shape: One of ``"allow"``, ``"tuple"``, ``"dict"``,
            ``"exit2"``, ``"legacy_recovery"``, ``"mode_skip"``,
            ``"exit_nonzero"``, or ``"exception"``. Unknown values are
            logged as-is.
        log_dir: Optional directory override. Falls back to the
            ``HOOK_TIMING_DIR`` env var, then to
            ``~/.claude/logs``.
    """
    if is_timing_disabled():
        return

    try:
        safe_hook = str(hook_name) if hook_name is not None else "unknown"
    except Exception:
        safe_hook = "unknown"

    # Issue #1056, Finding 1: cap hook_name length BEFORE it reaches the
    # log file. Adversarial or malformed hook names could otherwise
    # produce oversized JSONL lines or break downstream parsers that
    # assume bounded fields. The cap is applied here (write-path) rather
    # than at the call site so every code path that emits a row is
    # protected by a single guard.
    if len(safe_hook) > MAX_HOOK_NAME_LENGTH:
        safe_hook = safe_hook[:MAX_HOOK_NAME_LENGTH]

    try:
        safe_dur = int(dur_ns)
    except Exception:
        safe_dur = 0

    safe_shape = _normalize_decision_shape(decision_shape)

    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "hook": safe_hook,
        "dur_ns": safe_dur,
        "decision_shape": safe_shape,
        "schema_version": SCHEMA_VERSION,
    }

    try:
        line = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError):
        # Last-resort serialization with stringified values.
        try:
            line = json.dumps(
                {
                    "ts": event["ts"],
                    "hook": safe_hook,
                    "dur_ns": safe_dur,
                    "decision_shape": safe_shape,
                    "schema_version": SCHEMA_VERSION,
                }
            )
        except Exception:
            return

    try:
        log_path = _resolve_log_path(log_dir)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Issue #1056, Finding 2: enforce owner-only (0o600) permissions
        # on the timing log. The opener sets the mode at file-creation
        # time so newly created files are tight from the first byte.
        # ``os.chmod`` is then re-applied as a backstop for files that
        # already existed (legacy logs created before this guard landed
        # would otherwise retain their old, possibly looser, perms).
        def _secure_opener(path: str, flags: int) -> int:
            return os.open(path, flags, LOG_FILE_MODE)

        with open(log_path, "a", encoding="utf-8", opener=_secure_opener) as fh:
            fh.write(line + "\n")

        # Backstop: tighten perms in case the file pre-existed with
        # looser permissions. Swallow chmod failures — telemetry must
        # never block the host hook over a perm-tightening attempt.
        try:
            os.chmod(log_path, LOG_FILE_MODE)
        except OSError:
            pass

        return
    except OSError as exc:
        # Issue #1056, Finding 3: sanitize the error message so absolute
        # paths (which OSError typically embeds verbatim) do not leak
        # internal directory structure to stderr.
        safe_exc = _sanitize_os_error(exc)
        try:
            sys.stderr.write(f"[hook-timing] {line} (log_write_failed: {safe_exc})\n")
        except Exception:
            pass
    except Exception as exc:  # pragma: no cover - last-resort guard
        try:
            safe_exc = _sanitize_os_error(exc)
        except Exception:
            safe_exc = "<unrepresentable error>"
        try:
            sys.stderr.write(f"[hook-timing] {line} (unexpected_error: {safe_exc})\n")
        except Exception:
            pass


def is_budget_overrun_disabled() -> bool:
    """Return True iff the budget-overrun record is disabled via env var.

    Narrower than :func:`is_timing_disabled`: this silences only the
    ``hook-blocks.jsonl`` side effect, leaving the timing row in place.
    """
    raw = os.environ.get(BUDGET_OVERRUN_DISABLE_ENV_VAR)
    if raw is None:
        return False
    return raw.strip().lower() not in _FALSY_ENV_VALUES


def maybe_record_budget_overrun(hook_name: str, dur_ns: int) -> bool:
    """Record a countable skip when ``hook_name`` blew its configured budget.

    Issue #1704. When a hook exceeds its registered timeout the Claude Code
    runtime stops waiting and DISCARDS its decision -- for
    ``unified_pre_tool.py`` that silently drops all ~51 checks. Before this
    function existed the event was invisible in both directions: no row in
    ``hook-blocks.jsonl``, and an ordinary ``"allow"`` in the timing log.

    The record is possible at all because the runtime abandons the *wait*, not
    the *process*: the timing log contains COMPLETED rows at 13,139.7ms for a
    hook budgeted at 5s, so the hook is still alive here and can report.

    Only hooks with an explicit entry in ``hook_time_budgets.json`` are
    considered. Non-hook processes that borrow :class:`HookTimer` (notably
    ``scripts/mutation_witness_gate.py``, which is registered nowhere and
    contributed 56 spurious over-5s rows to the production sink) have no entry
    and are silently skipped.

    NEVER raises.

    Args:
        hook_name: Filename of the hook, e.g. ``"unified_pre_tool.py"``.
        dur_ns: Measured duration of the invocation in nanoseconds.

    Returns:
        True when an overrun row was written; False otherwise.
    """
    # W7 fast path, BEFORE any import or file read. Ordered cheapest-first: an
    # integer comparison rejects >99.9% of invocations (p50 is 6.4ms against a
    # 3s floor) for the cost of one comparison.
    if dur_ns < MIN_BUDGET_NS:
        return False
    if is_budget_overrun_disabled():
        return False
    try:
        lib_dir = str(Path(__file__).resolve().parent)
        if lib_dir not in sys.path:
            sys.path.insert(0, lib_dir)
        import hook_budgets  # type: ignore[import-not-found]

        if not hook_budgets.has_hook_budget(hook_name):
            return False
        budget_seconds = hook_budgets.get_hook_budget(hook_name)
        duration_ms = float(dur_ns) / 1_000_000.0
        if duration_ms <= budget_seconds * 1000.0:
            return False
        return hook_budgets.record_budget_overrun(
            hook_name=hook_name,
            duration_ms=duration_ms,
            budget_seconds=budget_seconds,
        )
    except Exception:
        # Telemetry must never break the host hook.
        return False


class HookTimer:
    """Context manager that emits one timing event on ``__exit__``.

    Default ``decision_shape`` is ``"allow"``. Hooks that produce a
    non-allow outcome should call :meth:`set_decision_shape` before
    leaving the ``with`` block.

    Termination is classified by :func:`_classify_exit` (full truth table in
    the module docstring). In short: a normal return and ``sys.exit(0)`` are
    both the SUCCESS path and keep the hook's own shape; a genuine unhandled
    exception — including a ``SystemExit`` that :func:`hook_safety.safe_main`
    manufactured from a crash — records ``"exception"``; a deliberate
    non-zero ``sys.exit(N)`` records ``"exit_nonzero"``. Whatever the shape,
    the exception propagates normally — the timer NEVER swallows errors.

    Example:

    >>> with HookTimer("auto_format.py") as timer:
    ...     timer.set_decision_shape("allow")
    ...     # hook body

    Honors the :envvar:`HOOK_TIMING_DISABLED` rollback switch and the
    :envvar:`HOOK_TIMING_DIR` directory override.
    """

    def __init__(
        self,
        hook_name: str,
        *,
        log_dir: Optional[Path] = None,
    ) -> None:
        self.hook_name = hook_name
        self._log_dir = log_dir
        self._decision_shape: str = SHAPE_DEFAULT
        self._explicitly_set: bool = False
        self._start_ns: int = 0
        self._disabled: bool = False

    def __enter__(self) -> "HookTimer":
        # Fast-path: short-circuit when disabled. ``__exit__`` becomes a no-op.
        if is_timing_disabled():
            self._disabled = True
            return self
        # A crash noted BEFORE this scope opened is not this invocation's
        # crash. Clearing here keeps the marker scoped to the ``with`` body.
        clear_crash()
        self._start_ns = time.perf_counter_ns()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # ``return None`` → propagate any exception unchanged.
        if self._disabled:
            return None

        try:
            dur_ns = time.perf_counter_ns() - self._start_ns
            shape = _classify_exit(
                exc_type,
                exc,
                decision_shape=self._decision_shape,
                explicitly_set=self._explicitly_set,
            )
            emit_timing_event(
                hook_name=self.hook_name,
                dur_ns=dur_ns,
                decision_shape=shape,
                log_dir=self._log_dir,
            )
            # Issue #1704: a discarded decision must be COUNTABLE. Emitted
            # after the timing row so a failure here cannot cost us the row.
            maybe_record_budget_overrun(self.hook_name, dur_ns)
        except Exception:
            # Last-resort guard: a bug in emit_timing_event must not block
            # the host hook. ``emit_timing_event`` already swallows errors
            # internally; this is defense in depth.
            pass
        # Returning None / falsy → exception (if any) propagates.
        return None

    def set_decision_shape(self, shape: str) -> None:
        """Record the outcome shape for this invocation.

        Acceptable values mirror :data:`hook_telemetry.VALID_DECISION_SHAPES`
        plus ``"allow"``. Unknown strings are logged as-is — readers MUST
        treat the field as opaque.
        """
        self._decision_shape = _normalize_decision_shape(shape)
        self._explicitly_set = True
