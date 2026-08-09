#!/usr/bin/env python3
"""Two-stage alignment gate for /implement STEP 0 (Issue #1467).

The gate has two stages:

- **Stage 0** (deterministic, this module): scans untrusted feature text for
  prompt-injection markers, PROJECT.md OUT-of-scope overlap, and architecture
  invariant deltas. Per INV-6 (deterministic before probabilistic) its outcome
  is FINAL — an LLM classification can never override a Stage 0 ESCALATE or
  BLOCK.
- **Stage 1** (the Haiku classifier agent, external): returns a classification
  plus a cited PROJECT.md clause. :func:`map_verdict` folds that into the final
  :class:`Verdict`, and only a clause that verifies verbatim against PROJECT.md
  can produce ``AUTO_PASS``.

Verdict semantics: ``AUTO_PASS`` and ``USER_APPROVED`` BOTH mean the gate
passed. Downstream consumers MUST test membership in :data:`ALLOWED_VERDICTS`
rather than comparing against a single literal — otherwise a human-approved
escalation is silently treated as a failure.

Everything fails closed (INV-7): a missing classification, an unverifiable
citation, an unavailable injection detector, and a failed artifact write all
resolve to ``ESCALATE`` rather than to a pass.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import sys
import tempfile
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

# ---------------------------------------------------------------------------
# Canonical injection-marker surface (Issue #960, reused per Issue #1467).
#
# This module deliberately defines NO parallel marker list: the phrase markers
# live in ``hooks/genai_utils.py`` beside ``_wrap_user_input`` so the
# injection-defense surface has exactly one home (INV-5). If that import fails
# we fail CLOSED — every text is treated as suspicious rather than clean.
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent

#: Candidate hook directories, HIGHEST priority first. A sibling ``hooks/``
#: (dev checkout or an installed ``~/.claude/lib`` next to ``~/.claude/hooks``)
#: always wins over the global install, so a repo-local copy is never shadowed
#: by a stale deployed one.
_HOOK_DIRS = (
    _THIS_DIR.parent / "hooks",
    Path.cwd() / "plugins" / "autonomous-dev" / "hooks",
    Path.cwd() / ".claude" / "hooks",
    Path.home() / ".claude" / "hooks",
)


def _load_canonical_injection_markers():
    """Resolve ``genai_utils.detect_injection`` from the highest-priority copy.

    ``sys.modules`` may already hold a stale ``genai_utils`` loaded by a hook
    from the global install, so a plain import is not sufficient. Each
    candidate directory is therefore also tried by explicit file load. Returns
    a fail-closed stub if no copy exposes the symbol.

    Returns:
        Callable taking text and returning a list of matched markers.
    """
    import importlib.util

    module = sys.modules.get("genai_utils")
    if module is not None and hasattr(module, "detect_injection"):
        return module.detect_injection

    for hook_dir in _HOOK_DIRS:
        source = hook_dir / "genai_utils.py"
        if not source.exists():
            continue
        if str(hook_dir) not in sys.path:
            sys.path.append(str(hook_dir))
        try:
            spec = importlib.util.spec_from_file_location("_alignment_genai_utils", source)
            if spec is None or spec.loader is None:
                continue
            loaded = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(loaded)
        except Exception:
            continue
        detector = getattr(loaded, "detect_injection", None)
        if detector is not None:
            return detector

    def _unavailable(_text: str) -> list:
        """Fail-closed stub: an unavailable detector means "assume injection"."""
        return ["injection_detection_unavailable"]

    return _unavailable


_canonical_injection_markers = _load_canonical_injection_markers()


# ---------------------------------------------------------------------------
# Enums and constants
# ---------------------------------------------------------------------------


class Verdict(str, Enum):
    """Final alignment verdict for a requested feature."""

    AUTO_PASS = "auto_pass"
    ESCALATE = "escalate"
    USER_APPROVED = "user_approved"
    BLOCK = "block"


class Stage0Outcome(str, Enum):
    """Outcome of the deterministic Stage 0 pre-check."""

    CLEAR = "clear"
    ESCALATE = "escalate"
    BLOCK = "block"


#: Verdicts that mean the gate PASSED. Consumers MUST test membership here
#: rather than comparing against a single verdict literal (Amendment 2).
ALLOWED_VERDICTS = frozenset({Verdict.AUTO_PASS.value, Verdict.USER_APPROVED.value})

#: Classifications Stage 1 is allowed to return.
_IN_SCOPE_CLASSIFICATION = "in_scope"
_KNOWN_CLASSIFICATIONS = frozenset({"in_scope", "out_of_scope", "architecture_delta", "ambiguous"})

#: Minimum normalized length for a cited clause to count as evidence. Shorter
#: strings ("SCOPE", "tests") appear in almost any document and prove nothing.
_MIN_CITATION_CHARS = 12


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectDoc:
    """Parsed view of a repository's ``.claude/PROJECT.md``."""

    raw: str = ""
    goals: str = ""
    in_scope: Tuple[str, ...] = ()
    out_scope: Tuple[str, ...] = ()
    constraints: str = ""
    architecture: str = ""
    invariants: Tuple[str, ...] = ()
    path: Optional[Path] = None

    @property
    def has_invariants(self) -> bool:
        """True when the project documents an INVARIANTS section.

        Consumer repos usually have none. Architecture-delta escalation is
        gated on this so those repos are never blocked on an axis their
        PROJECT.md does not define.
        """
        return bool(self.invariants)


@dataclass(frozen=True)
class Stage0Result:
    """Result of the deterministic Stage 0 pre-check."""

    outcome: Stage0Outcome
    reason: str = ""
    injection_detected: bool = False
    matched_out_scope_clause: Optional[str] = None
    is_standard_change: bool = False
    architecture_delta_phrase: Optional[str] = None


@dataclass(frozen=True)
class AlignmentVerdict:
    """Full record of one alignment decision, persisted as the audit artifact."""

    verdict: Verdict
    feature_text: str = ""
    classification: Optional[str] = None
    cited_clause: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""
    stage0_outcome: Stage0Outcome = Stage0Outcome.CLEAR
    stage0_reason: str = ""
    citation_verified: bool = False
    autonomous_context: bool = False
    issue_number: str = ""
    timestamp: str = ""
    #: Evidentiary trail for an APPLIED human approval. Present only when an
    #: ``ESCALATE`` was upgraded to ``USER_APPROVED``, so a real approval is
    #: distinguishable from a bare ``user_approved=True`` flag flip.
    approval: Optional[Dict[str, Any]] = None
    #: Why an attempted ``user_approved`` upgrade was REFUSED (currently only
    #: ``"autonomous_context"``). Non-empty means somebody tried to approve
    #: with no human present; the attempt stays visible in the audit trail.
    user_approved_refused: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to the schema-versioned artifact payload.

        ``approval`` and ``user_approved_refused`` are emitted only when set, so
        the payload of an ordinary verdict is byte-identical to the pre-hardening
        schema (zero blast radius for existing readers).
        """
        payload = {
            "schema_version": 1,
            "verdict": self.verdict.value,
            "feature_text": self.feature_text,
            "classification": self.classification,
            "cited_clause": self.cited_clause,
            "citation_verified": self.citation_verified,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "stage0_outcome": self.stage0_outcome.value,
            "stage0_reason": self.stage0_reason,
            "autonomous_context": self.autonomous_context,
            "issue_number": self.issue_number,
            "timestamp": self.timestamp,
        }
        if self.approval is not None:
            payload["approval"] = dict(self.approval)
        if self.user_approved_refused:
            payload["user_approved_refused"] = self.user_approved_refused
        return payload


# ---------------------------------------------------------------------------
# PROJECT.md parsing
# ---------------------------------------------------------------------------

_SECTION_RE = re.compile(
    r"^#{1,3}[ \t]*(GOALS|SCOPE|CONSTRAINTS|ARCHITECTURE)\b.*$",
    re.IGNORECASE | re.MULTILINE,
)
_IN_SCOPE_RE = re.compile(r"\*\*[ \t]*IN[ \t]+Scope[ \t]*:?[ \t]*\*\*", re.IGNORECASE)
_OUT_SCOPE_RE = re.compile(r"\*\*[ \t]*OUT[ \t]+of[ \t]+Scope[ \t]*:?[ \t]*\*\*", re.IGNORECASE)
_INVARIANTS_RE = re.compile(r"^#{1,4}[ \t]*INVARIANTS\b.*$", re.IGNORECASE | re.MULTILINE)
_ANY_HEADING_RE = re.compile(r"^#{1,6}[ \t]", re.MULTILINE)


def _clean_bullet(line: str) -> str:
    """Strip the list marker and inline Markdown emphasis from a bullet."""
    text = line.strip()
    if text.startswith("- "):
        text = text[2:]
    return text.replace("**", "").replace("`", "").replace("*", "").strip()


def _bullets(block: str) -> Tuple[str, ...]:
    """Extract ``- `` bullets from a Markdown block."""
    return tuple(
        cleaned
        for line in block.splitlines()
        if line.strip().startswith("- ")
        for cleaned in (_clean_bullet(line),)
        if cleaned
    )


def parse_project_md_text(text: str) -> ProjectDoc:
    """Parse PROJECT.md content into a :class:`ProjectDoc`.

    Tolerant by design: headings at depth 1-3 are all recognized, and any
    missing section yields an empty value rather than an exception. A malformed
    PROJECT.md therefore degrades into "no scope evidence" — which citation
    verification turns into an ESCALATE — instead of crashing the gate.

    Args:
        text: Full PROJECT.md contents.

    Returns:
        Parsed :class:`ProjectDoc`; ``raw`` always holds the original text.
    """
    text = text or ""
    sections: Dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(text))
    for idx, match in enumerate(matches):
        name = match.group(1).upper()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        sections[name] = sections.get(name, "") + "\n" + text[start:end]

    scope_body = sections.get("SCOPE", "")
    in_match = _IN_SCOPE_RE.search(scope_body)
    out_match = _OUT_SCOPE_RE.search(scope_body)
    in_scope: Tuple[str, ...] = ()
    out_scope: Tuple[str, ...] = ()
    if in_match:
        end = (
            out_match.start()
            if out_match and out_match.start() > in_match.end()
            else len(scope_body)
        )
        in_scope = _bullets(scope_body[in_match.end() : end])
    if out_match:
        end = (
            in_match.start() if in_match and in_match.start() > out_match.end() else len(scope_body)
        )
        out_scope = _bullets(scope_body[out_match.end() : end])
    if not in_match and not out_match:
        # No IN/OUT markers: treat every SCOPE bullet as in scope.
        in_scope = _bullets(scope_body)

    architecture = sections.get("ARCHITECTURE", "")
    invariants: Tuple[str, ...] = ()
    inv_match = _INVARIANTS_RE.search(architecture)
    if inv_match:
        rest = architecture[inv_match.end() :]
        next_heading = _ANY_HEADING_RE.search(rest)
        invariants = _bullets(rest[: next_heading.start()] if next_heading else rest)

    return ProjectDoc(
        raw=text,
        goals=sections.get("GOALS", "").strip(),
        in_scope=in_scope,
        out_scope=out_scope,
        constraints=sections.get("CONSTRAINTS", "").strip(),
        architecture=architecture.strip(),
        invariants=invariants,
    )


def parse_project_md(path: Path) -> ProjectDoc:
    """Read and parse a PROJECT.md file.

    Args:
        path: Path to PROJECT.md.

    Returns:
        Parsed :class:`ProjectDoc` with ``path`` populated.

    Raises:
        FileNotFoundError: If the file does not exist. The coordinator turns
            this into a BLOCK — a project with no alignment source of truth
            cannot be auto-passed.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"PROJECT.md not found: {path}\n"
            f"Expected: the alignment source of truth at .claude/PROJECT.md\n"
            f"See: docs/development/CONTENT_ALLOCATION.md"
        )
    doc = parse_project_md_text(path.read_text(encoding="utf-8"))
    return dataclasses.replace(doc, path=path)


# ---------------------------------------------------------------------------
# Text normalization (Stage 0 hardening)
# ---------------------------------------------------------------------------

#: Zero-width and byte-order characters an attacker can splice into a phrase
#: ("ign​ore previous instructions") to defeat literal matching. They are
#: all Unicode category ``Cf`` (format), which is what the filter below keys on;
#: the tuple documents the concrete code points the corpus exercises.
ZERO_WIDTH_CHARS: Tuple[str, ...] = ("​", "‌", "‍", "﻿")


def _normalize_text(text: str) -> str:
    """Fold text into the canonical form every Stage 0 detector matches against.

    Two transforms, both purely lexical:

    1. NFKC normalization — collapses compatibility forms (fullwidth
       ``ｉｇｎｏｒｅ``, ligatures) onto their ASCII equivalents.
    2. Category ``Cf`` removal — strips zero-width joiners/spaces, the BOM, and
       other invisible format characters that carry no meaning to a reader but
       break substring and token matching.

    Applying this once at the Stage 0 boundary means ``detect_injection``,
    ``_tokens``, OUT-of-scope matching, and architecture-delta matching all see
    the same de-obfuscated text without any detector needing its own copy of the
    logic (INV-5).

    Args:
        text: Untrusted text (may be None-ish or empty).

    Returns:
        The normalized text; ``""`` for empty input.
    """
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", str(text))
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Cf")


# ---------------------------------------------------------------------------
# Stage 0 detector: injection
# ---------------------------------------------------------------------------

#: Delimiter-escape attempts — closing an untrusted-text tag or opening a
#: privileged one. Complements the phrase markers in genai_utils, which cannot
#: express structural patterns.
_STRUCTURAL_INJECTION_RE = re.compile(
    r"</\s*[a-z_][\w-]*\s*>|<\s*(?:system|assistant|admin|instructions?)\b",
    re.IGNORECASE,
)

#: Claims that some authority already approved the work, used to skip the gate.
_AUTHORITY_CLAIM_RE = re.compile(
    r"\b(?:user|maintainer|owner|human|reviewer)\b[^.!?]{0,60}\b"
    r"(?:approved|authorized|authorised|signed off)\b",
    re.IGNORECASE,
)

#: Direct requests to bypass a gate or check.
_GATE_BYPASS_RE = re.compile(
    r"\b(?:skip|bypass|disable|ignore|forget|override)\b[^.!?]{0,40}\b"
    r"(?:alignment|gate|guard|check|validation|review|instructions?|everything)\b",
    re.IGNORECASE,
)

#: Attempts to re-open the system prompt from inside untrusted text.
_PROMPT_OVERRIDE_RE = re.compile(
    r"\b(?:system|new)\s+(?:prompt|instructions?)\b|\balways\s+return\b",
    re.IGNORECASE,
)

_INJECTION_PATTERNS = (
    ("structural_delimiter_escape", _STRUCTURAL_INJECTION_RE),
    ("authority_claim", _AUTHORITY_CLAIM_RE),
    ("gate_bypass_request", _GATE_BYPASS_RE),
    ("prompt_override", _PROMPT_OVERRIDE_RE),
)


def injection_signals(text: str) -> List[str]:
    """Return every injection signal present in ``text``.

    Combines the canonical phrase markers from ``genai_utils`` (Issue #960)
    with structural/semantic patterns that a flat marker list cannot express.
    The text is passed through :func:`_normalize_text` first, so zero-width
    obfuscation ("ign<ZWSP>ore previous instructions") cannot hide a marker.

    Args:
        text: Untrusted feature text.

    Returns:
        List of signal descriptions; empty means the text looks clean.
    """
    text = _normalize_text(text)
    if not text:
        return []
    try:
        signals = [f"marker:{m}" for m in (_canonical_injection_markers(text) or [])]
    except Exception:
        # Fail closed — a broken detector must never read as "clean".
        signals = ["marker:injection_detection_unavailable"]
    for name, pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            signals.append(name)
    return signals


def detect_injection(text: str) -> bool:
    """Report whether untrusted feature text contains injection signals.

    Args:
        text: Untrusted feature text.

    Returns:
        True when at least one injection signal is present.
    """
    return bool(injection_signals(text))


# ---------------------------------------------------------------------------
# Stage 0 detector: out-of-scope overlap
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset(
    {
        "with",
        "that",
        "this",
        "from",
        "into",
        "should",
        "would",
        "could",
        "have",
        "must",
        "them",
        "they",
        "when",
        "where",
        "what",
        "also",
        "only",
        "your",
        "their",
        "there",
        "then",
        "than",
        "such",
        "each",
        "some",
        "more",
        "make",
        "made",
        "does",
        "done",
        "will",
        "were",
        "been",
        "being",
        "about",
        "which",
        "while",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")

#: Minimum significant-word overlap for an OUT bullet to count as a match.
_OUT_SCOPE_MIN_OVERLAP = 2


def _tokens(text: str) -> Tuple[str, ...]:
    """Significant lowercase tokens: alphanumeric, >=4 chars, non-stopword."""
    return tuple(
        t for t in _TOKEN_RE.findall((text or "").lower()) if len(t) >= 4 and t not in _STOPWORDS
    )


def _shares_prefix(a: str, b: str) -> bool:
    """True when two tokens share a >=4-character prefix (cheap stemming).

    Lets "replaces" match "Replacing" and "hosting" match "hosted" without a
    stemming dependency.
    """
    if len(a) < 4 or len(b) < 4:
        return False
    return a[:4] == b[:4] and os.path.commonprefix([a, b]).__len__() >= 4


def _overlap_score(feature_tokens: Tuple[str, ...], clause: str) -> int:
    """Count distinct clause tokens that prefix-match some feature token."""
    return sum(
        1 for ct in set(_tokens(clause)) if any(_shares_prefix(ct, ft) for ft in feature_tokens)
    )


def _best_clause(feature_tokens: Tuple[str, ...], clauses) -> Tuple[Optional[str], int]:
    """Return the highest-scoring clause and its score."""
    best: Optional[str] = None
    best_score = 0
    for clause in clauses or ():
        score = _overlap_score(feature_tokens, clause)
        if score > best_score:
            best, best_score = clause, score
    return best, best_score


def detect_out_of_scope(feature_text: str, doc: ProjectDoc) -> Optional[str]:
    """Return the OUT-of-scope clause a feature matches, or None.

    A clause matches only when it shares at least
    :data:`_OUT_SCOPE_MIN_OVERLAP` significant words with the feature text AND
    outscores every IN-scope clause. The IN-scope comparison is the precision
    guard: features that merely reuse project vocabulary ("PROJECT.md alignment
    validation") describe in-scope work and must not escalate deterministically
    — Stage 1 still classifies them.

    Args:
        feature_text: Untrusted feature text.
        doc: Parsed PROJECT.md.

    Returns:
        The matched OUT-of-scope clause, or None when nothing matches.
    """
    if not feature_text or not doc.out_scope:
        return None
    feature_tokens = _tokens(feature_text)
    if not feature_tokens:
        return None

    out_clause, out_score = _best_clause(feature_tokens, doc.out_scope)
    if out_score < _OUT_SCOPE_MIN_OVERLAP:
        return None
    _, in_score = _best_clause(feature_tokens, doc.in_scope)
    if out_score <= in_score:
        return None
    return out_clause


# ---------------------------------------------------------------------------
# Stage 0 detector: standard change
# ---------------------------------------------------------------------------

#: Light-mode vocabulary, reused verbatim from implement.md auto-mode detection.
STANDARD_CHANGE_KEYWORDS: Tuple[str, ...] = (
    "update docs",
    "update readme",
    "update the readme",
    "update comment",
    "changelog",
    "typo",
    "rename",
    "config change",
    "docstring",
)

#: A documentation file reached through a path (``docs/RUNBOOK.md``). Bare
#: governance filenames such as ``PROJECT.md`` are deliberately excluded — a
#: request that merely names PROJECT.md is usually about the gate itself.
_DOC_PATH_RE = re.compile(r"[\w.-]+/[\w./-]*\.(?:md|txt|rst)\b", re.IGNORECASE)

#: Protected infrastructure (INV-4). Source changes here are never "standard",
#: no matter how much documentation vocabulary the request carries.
_SENSITIVE_PATH_RE = re.compile(
    r"\b(?:lib|hooks|agents|commands|skills|src)/[\w./-]*\.(?:py|sh|json|yaml|yml)\b",
    re.IGNORECASE,
)


def detect_standard_change(feature_text: str) -> bool:
    """Report whether a request is a routine documentation/rename change.

    Standard changes suppress only the OUT-of-scope keyword heuristic — never
    injection or architecture-delta detection — so a genuinely out-of-scope
    docs change is still caught by Stage 1.

    Args:
        feature_text: Untrusted feature text.

    Returns:
        True for routine doc/config/rename edits, False otherwise.
    """
    if not feature_text:
        return False
    lowered = feature_text.lower()
    if _SENSITIVE_PATH_RE.search(lowered):
        return False
    if any(keyword in lowered for keyword in STANDARD_CHANGE_KEYWORDS):
        return True
    return bool(_DOC_PATH_RE.search(lowered))


# ---------------------------------------------------------------------------
# Stage 0 detector: architecture delta
# ---------------------------------------------------------------------------

#: Phrases proposing a change to a documented architecture invariant. Each maps
#: to an INV-* clause: enforcement strength (INV-1), agent isolation (INV-2),
#: pipeline shape (INV-3), protected infrastructure (INV-4), one-topic-one-home
#: (INV-5), deterministic-first (INV-6), signed state (INV-7), local-and-free
#: (INV-8). Scope words (SaaS, paid features) live in the OUT-of-scope detector
#: instead, so a doc edit that merely mentions them does not escalate here.
ARCHITECTURE_DELTA_PHRASES: Tuple[str, ...] = (
    # INV-1 — enforcement is hooks, not nudges
    "prompt-level advisory",
    "advisory instead of blocking",
    "advisory rather than blocking",
    "hooks into nudges",
    "replace the hooks with",
    "replace the blocking hooks",
    "warning instead of blocking",
    # INV-2 — specialists run in fresh context
    "self-attest",
    "self attest",
    "single agent sharing",
    "sharing one context",
    "merge the reviewer",
    "merge the agents",
    "consolidate the agents",
    # INV-3 — the pipeline shape is fixed
    "reorder the pipeline",
    "drop the alignment step",
    "remove a pipeline step",
    "drop the acceptance",
    # INV-4 — protected infrastructure is implementer-only
    "outside /implement",
    "direct editing of hooks",
    "direct edits to hooks",
    # INV-5 — one topic, one home
    "duplicate the content",
    "duplicate this content",
    # INV-6 — deterministic before probabilistic
    "override the deterministic",
    "judgment override the",
    # INV-7 — gating state is signed and fails closed
    "drop the hmac",
    "unsigned state",
    "fail open",
    # INV-8 — local-first and free
    "paid api",
    "hosted model",
)


def detect_architecture_delta(feature_text: str, doc: ProjectDoc) -> Optional[str]:
    """Return the architecture-delta phrase a feature matches, or None.

    Always returns None for repositories with no INVARIANTS section: without a
    documented invariant there is nothing for a change to violate, and consumer
    repos must never be blocked on an axis their PROJECT.md does not define.

    Args:
        feature_text: Untrusted feature text.
        doc: Parsed PROJECT.md.

    Returns:
        The matched phrase, or None.
    """
    if not feature_text or not doc.has_invariants:
        return None
    lowered = feature_text.lower()
    for phrase in ARCHITECTURE_DELTA_PHRASES:
        if phrase in lowered:
            return phrase
    return None


# ---------------------------------------------------------------------------
# Stage 0 orchestration
# ---------------------------------------------------------------------------


def run_stage0(feature_text: str, doc: ProjectDoc) -> Stage0Result:
    """Run the deterministic pre-check over untrusted feature text.

    Precedence, highest first:

    1. **Injection** — never suppressed by anything.
    2. **Architecture delta** — an invariant change is structural, so a
       documentation framing does not excuse it.
    3. **Out-of-scope overlap** — suppressed when the request is a standard
       documentation change (Stage 1 still classifies it).

    Args:
        feature_text: Untrusted feature text.
        doc: Parsed PROJECT.md.

    Returns:
        A :class:`Stage0Result`. ``BLOCK`` means the project has no usable
        alignment source of truth.
    """
    # Normalize ONCE at the boundary: every detector below (injection, tokens,
    # OUT-of-scope, architecture delta) then matches de-obfuscated text, so a
    # zero-width splice cannot slip past any of them.
    feature_text = _normalize_text(feature_text)

    if not doc.raw.strip():
        return Stage0Result(
            outcome=Stage0Outcome.BLOCK,
            reason="PROJECT.md is empty — no alignment source of truth",
        )

    is_standard = detect_standard_change(feature_text)

    signals = injection_signals(feature_text)
    if signals:
        return Stage0Result(
            outcome=Stage0Outcome.ESCALATE,
            reason=f"injection signals detected: {', '.join(signals)}",
            injection_detected=True,
            is_standard_change=is_standard,
        )

    phrase = detect_architecture_delta(feature_text, doc)
    if phrase:
        return Stage0Result(
            outcome=Stage0Outcome.ESCALATE,
            reason=f"architecture invariant delta: {phrase!r}",
            is_standard_change=is_standard,
            architecture_delta_phrase=phrase,
        )

    clause = detect_out_of_scope(feature_text, doc)
    if clause and not is_standard:
        return Stage0Result(
            outcome=Stage0Outcome.ESCALATE,
            reason=f"overlaps OUT-of-scope clause: {clause!r}",
            matched_out_scope_clause=clause,
            is_standard_change=False,
        )

    return Stage0Result(
        outcome=Stage0Outcome.CLEAR,
        reason=(
            "standard change; no deterministic signal" if is_standard else "no deterministic signal"
        ),
        matched_out_scope_clause=clause,
        is_standard_change=is_standard,
    )


# ---------------------------------------------------------------------------
# Citation verification and verdict mapping
# ---------------------------------------------------------------------------


def verify_citation(clause: Optional[str], doc: ProjectDoc) -> bool:
    """Verify a cited clause appears verbatim in PROJECT.md.

    Whitespace is collapsed and case is folded, so a classifier that re-wraps
    or re-cases a quoted line still verifies. Clauses under
    :data:`_MIN_CITATION_CHARS` normalized characters are rejected — they are
    too generic to be evidence.

    Args:
        clause: The clause Stage 1 claims to have cited (may be None).
        doc: Parsed PROJECT.md.

    Returns:
        True only when the normalized clause is a substring of the normalized
        document.
    """
    if not clause:
        return False
    normalized = " ".join(str(clause).split()).casefold()
    if len(normalized) < _MIN_CITATION_CHARS:
        return False
    haystack = " ".join((doc.raw or "").split()).casefold()
    return bool(haystack) and normalized in haystack


def map_verdict(
    stage0: Stage0Result,
    classification: Optional[str],
    cited_clause: Optional[str],
    doc: ProjectDoc,
    *,
    user_approved: bool = False,
) -> Verdict:
    """Fold Stage 0 and Stage 1 into the final verdict.

    Truth table (first match wins):

    ===========================  ==========================  ==============
    Stage 0                      Stage 1                     Verdict
    ===========================  ==========================  ==============
    ``BLOCK``                    anything                    ``BLOCK``
    ``ESCALATE``                 anything                    ``ESCALATE``
    ``CLEAR``                    ``None`` / unknown          ``ESCALATE``
    ``CLEAR``                    ``in_scope`` + citation     ``AUTO_PASS``
    ``CLEAR``                    ``in_scope``, bad citation  ``ESCALATE``
    ``CLEAR``                    ``out_of_scope``            ``ESCALATE``
    ``CLEAR``                    ``architecture_delta``      ``ESCALATE``*
    ===========================  ==========================  ==============

    \\* Downgraded to the ``in_scope`` path when the repo documents no
    invariants.

    ``user_approved`` upgrades ``ESCALATE`` to ``USER_APPROVED`` and nothing
    else — a ``BLOCK`` is never upgradable (INV-7). This function is pure and
    reads no environment: the autonomy gate that decides whether an approval may
    take effect at all lives at the recording choke point
    (:func:`record_alignment_verdict`), which refuses the upgrade — and
    downgrades an already-``USER_APPROVED`` verdict — when no human is present.

    Args:
        stage0: Deterministic pre-check result.
        classification: Stage 1 classification, or None on classifier failure.
        cited_clause: Clause Stage 1 cited from PROJECT.md.
        doc: Parsed PROJECT.md.
        user_approved: True when a human explicitly approved the escalation.

    Returns:
        The final :class:`Verdict`.
    """
    if stage0.outcome is Stage0Outcome.BLOCK:
        return Verdict.BLOCK

    def _escalate() -> Verdict:
        return Verdict.USER_APPROVED if user_approved else Verdict.ESCALATE

    # INV-6: the deterministic outcome cannot be overridden by Stage 1.
    if stage0.outcome is Stage0Outcome.ESCALATE:
        return _escalate()

    if not classification or classification not in _KNOWN_CLASSIFICATIONS:
        # Classifier failure, timeout, or an invented label: fail closed.
        return _escalate()

    effective = classification
    if effective == "architecture_delta" and not doc.has_invariants:
        # No documented invariants — judge on scope evidence alone.
        effective = _IN_SCOPE_CLASSIFICATION

    if effective != _IN_SCOPE_CLASSIFICATION:
        return _escalate()

    if not verify_citation(cited_clause, doc):
        return _escalate()

    return Verdict.AUTO_PASS


# ---------------------------------------------------------------------------
# Execution context
# ---------------------------------------------------------------------------

_TRUTHY = frozenset({"1", "true", "yes", "on"})
_DRAIN_MARKER_REL = Path(".claude") / "local" / "drain_pending.json"


def is_autonomous_context(
    *,
    env: Optional[Mapping[str, str]] = None,
    repo_root: Optional[Path] = None,
) -> bool:
    """Report whether no human is available to answer an escalation prompt.

    True when ``AUTONOMOUS_DEV_NONINTERACTIVE`` is truthy OR a drain-pending
    marker exists. Deliberately NOT keyed on ``BATCH_NO_WORKTREE``: that flag
    is an in-place modifier also set for interactive runs
    (``batch_orchestrator.py:1002``), so treating it as an autonomy signal
    would suppress the prompt for a maintainer sitting at the keyboard.

    Args:
        env: Environment mapping (defaults to ``os.environ``).
        repo_root: Repository root used to locate the drain marker.

    Returns:
        True when the run is autonomous.
    """
    environ = os.environ if env is None else env
    if str(environ.get("AUTONOMOUS_DEV_NONINTERACTIVE", "")).strip().lower() in _TRUTHY:
        return True

    if repo_root is not None:
        return (Path(repo_root) / _DRAIN_MARKER_REL).exists()

    try:
        from drain_pending import _marker_path

        return Path(_marker_path()).exists()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

_ARTIFACT_REL = Path(".claude") / "alignment_verdict.json"
_AUDIT_LOG_REL = Path(".claude") / "logs" / "alignment_verdicts.jsonl"


def write_alignment_verdict(
    verdict: AlignmentVerdict,
    *,
    repo_root: Optional[Path] = None,
) -> bool:
    """Persist the verdict artifact atomically and append an audit line.

    The artifact is written via a temp file plus ``os.replace`` so a reader
    never observes a partial JSON document. The JSONL log is append-only.

    Args:
        verdict: The verdict to persist.
        repo_root: Repository root (defaults to cwd).

    Returns:
        True on success, False on any I/O failure. Callers MUST treat False as
        "not persisted" and downgrade the verdict — an unrecorded pass is
        indistinguishable from a skipped gate (INV-7).
    """
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    payload = verdict.to_dict()
    tmp_name: Optional[str] = None
    try:
        artifact = root / _ARTIFACT_REL
        artifact.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", dir=str(artifact.parent), delete=False, encoding="utf-8"
        ) as handle:
            tmp_name = handle.name
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, artifact)
        tmp_name = None

        log_path = root / _AUDIT_LOG_REL
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
        return True
    except (OSError, TypeError, ValueError):
        return False
    finally:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def record_alignment_verdict(
    verdict: AlignmentVerdict,
    *,
    state_path: Optional[Path] = None,
    session_id: str = "unknown",
    repo_root: Optional[Path] = None,
    user_approved: bool = False,
    autonomous_context: Optional[bool] = None,
) -> AlignmentVerdict:
    """Persist a verdict and write ``alignment_passed`` into pipeline state.

    This is the SOLE writer of ``alignment_passed`` — every other component
    reads it. The order matters: the artifact is written first, and if that
    write fails the verdict is downgraded to ``ESCALATE`` before state is
    touched, so ``alignment_passed`` is never True without a durable record.

    It is also the SOLE place where a human approval takes effect, which is what
    makes the autonomy gate enforceable: ``USER_APPROVED`` requires a human, so
    in an autonomous context the upgrade is REFUSED (the verdict stays
    ``ESCALATE``) and the attempt is recorded in ``user_approved_refused``. A
    verdict that arrives already carrying ``USER_APPROVED`` is downgraded the
    same way — otherwise the gate could be bypassed by pre-upgrading upstream.
    An applied upgrade records an ``approval`` sub-object so a real
    AskUserQuestion round-trip is auditable, and distinguishable from a bare
    flag flip.

    Args:
        verdict: The verdict produced by :func:`map_verdict` and its evidence.
        state_path: Signed pipeline-state file to update (skipped if absent).
        session_id: Session id used to re-sign the state.
        repo_root: Repository root for the artifact and audit log.
        user_approved: True when a human approved the escalation. Upgrades
            ``ESCALATE`` to ``USER_APPROVED`` and nothing else — never a
            ``BLOCK``, and never in an autonomous context.
        autonomous_context: Pre-computed autonomy flag. ``None`` (the default)
            means detect it here via :func:`is_autonomous_context`; callers that
            already computed it pass it in to avoid a second filesystem probe.

    Returns:
        The final :class:`AlignmentVerdict` after any upgrade or downgrade.
    """
    final = verdict
    approval_relevant = (user_approved and final.verdict is Verdict.ESCALATE) or (
        final.verdict is Verdict.USER_APPROVED
    )
    if approval_relevant:
        autonomous = (
            is_autonomous_context(repo_root=repo_root)
            if autonomous_context is None
            else bool(autonomous_context)
        )
        if autonomous:
            # No human is present to have approved anything (INV-7 fail closed).
            final = dataclasses.replace(
                final,
                verdict=Verdict.ESCALATE,
                user_approved_refused="autonomous_context",
                reasoning=(
                    f"{final.reasoning} [user approval refused: autonomous context]"
                ).strip(),
            )
        elif final.verdict is Verdict.ESCALATE:
            final = dataclasses.replace(
                final,
                verdict=Verdict.USER_APPROVED,
                approval={
                    "source": "ask_user_question",
                    "approved_at": datetime.now(timezone.utc).isoformat(),
                    "stage0_reason": final.stage0_reason,
                    "citation_verified": bool(final.citation_verified),
                },
            )

    if not write_alignment_verdict(final, repo_root=repo_root):
        if final.verdict.value in ALLOWED_VERDICTS:
            final = dataclasses.replace(
                final,
                verdict=Verdict.ESCALATE,
                reasoning=(
                    f"{final.reasoning} [downgraded: verdict artifact write failed]"
                ).strip(),
            )

    alignment_passed = final.verdict.value in ALLOWED_VERDICTS
    if state_path is not None:
        _update_pipeline_state(
            Path(state_path),
            session_id=session_id,
            alignment_passed=alignment_passed,
            verdict_value=final.verdict.value,
        )
    return final


def _update_pipeline_state(
    state_path: Path,
    *,
    session_id: str,
    alignment_passed: bool,
    verdict_value: str,
) -> bool:
    """Write the alignment fields into signed pipeline state and re-sign it.

    Args:
        state_path: Path to the pipeline state JSON.
        session_id: Session id passed to ``sign_state``.
        alignment_passed: Value for the ``alignment_passed`` gate field.
        verdict_value: Value for the ``alignment_verdict`` audit field.

    Returns:
        True when the state file was updated and re-signed.
    """
    if not state_path.exists():
        return False
    try:
        from pipeline_state import sign_state
    except ImportError:
        try:
            if str(_THIS_DIR) not in sys.path:
                sys.path.insert(0, str(_THIS_DIR))
            from pipeline_state import sign_state
        except ImportError:
            return False
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["alignment_passed"] = alignment_passed
        state["alignment_verdict"] = verdict_value
        state = sign_state(state, session_id)
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        return True
    except (OSError, ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Orchestration entry point
# ---------------------------------------------------------------------------

_PROJECT_MD_REL = Path(".claude") / "PROJECT.md"

#: Stage 1 reports confidence as a word; the artifact stores a float.
_CONFIDENCE_WORDS = {"high": 0.9, "medium": 0.6, "low": 0.3}


def _coerce_confidence(value: Any) -> float:
    """Map a classifier confidence (word or number) onto ``0.0``-``1.0``.

    Args:
        value: ``"high"``/``"medium"``/``"low"``, a number, or anything else.

    Returns:
        The mapped float; ``0.0`` for an unrecognized value (fail closed —
        confidence is audit metadata and never gates the verdict).
    """
    if isinstance(value, str):
        return _CONFIDENCE_WORDS.get(value.strip().lower(), 0.0)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return max(0.0, min(1.0, float(value)))
    return 0.0


def evaluate_and_record(
    feature_text: str,
    classifier_json: Optional[Mapping[str, Any]] = None,
    *,
    project_md_path: Optional[Path] = None,
    state_path: Optional[Path] = None,
    session_id: str = "unknown",
    repo_root: Optional[Path] = None,
    user_approved: bool = False,
    issue_number: str = "",
) -> Dict[str, Any]:
    """Run the whole gate end to end and persist the result.

    This is the single entry point the ``/implement`` STEP 2 snippets call. It
    parses PROJECT.md, runs :func:`run_stage0`, folds Stage 0 and the Stage 1
    classifier output through :func:`map_verdict`, builds the
    :class:`AlignmentVerdict`, and hands it to :func:`record_alignment_verdict`.
    No decision logic lives here — it only wires the existing pieces together
    so the command file cannot drift from the library surface.

    A missing PROJECT.md becomes a Stage 0 ``BLOCK`` rather than an exception:
    a project with no alignment source of truth fails closed (INV-7).

    Args:
        feature_text: Untrusted feature text being classified.
        classifier_json: The Stage 1 agent's parsed JSON block, or None when the
            classifier failed, timed out, or emitted unparseable output.
        project_md_path: PROJECT.md location (defaults to
            ``<repo_root>/.claude/PROJECT.md``).
        state_path: Signed pipeline-state file to update (skipped if absent).
        session_id: Session id used to re-sign the pipeline state.
        repo_root: Repository root for the artifact and audit log.
        user_approved: True when a human approved an escalation. Honoured only
            in an interactive context — see :func:`record_alignment_verdict`.
        issue_number: Issue number recorded in the audit artifact.

    Returns:
        A JSON-safe dict: the artifact payload from
        :meth:`AlignmentVerdict.to_dict` plus ``alignment_passed``,
        ``has_invariants``, and ``project_md_found``.
    """
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    md_path = Path(project_md_path) if project_md_path is not None else root / _PROJECT_MD_REL

    try:
        doc = parse_project_md(md_path)
        project_md_found = True
    except FileNotFoundError:
        doc = ProjectDoc(path=md_path)
        project_md_found = False

    feature_text = feature_text or ""
    if project_md_found:
        stage0 = run_stage0(feature_text, doc)
    else:
        stage0 = Stage0Result(
            outcome=Stage0Outcome.BLOCK,
            reason=f"PROJECT.md not found: {md_path}",
        )

    payload: Mapping[str, Any] = classifier_json if isinstance(classifier_json, Mapping) else {}
    classification = payload.get("classification")
    classification = str(classification) if isinstance(classification, str) else None
    cited_clause = payload.get("cited_clause")
    cited_clause = str(cited_clause) if isinstance(cited_clause, str) else None

    # The approval upgrade is applied at exactly ONE choke point
    # (record_alignment_verdict), which is where the autonomy gate lives. Passing
    # user_approved to map_verdict here as well would upgrade the verdict before
    # that gate ever sees it.
    autonomous = is_autonomous_context(repo_root=root)
    verdict = map_verdict(stage0, classification, cited_clause, doc)
    record = AlignmentVerdict(
        verdict=verdict,
        feature_text=feature_text,
        classification=classification,
        cited_clause=cited_clause,
        confidence=_coerce_confidence(payload.get("confidence")),
        reasoning=str(payload.get("reasoning") or ""),
        stage0_outcome=stage0.outcome,
        stage0_reason=stage0.reason,
        citation_verified=verify_citation(cited_clause, doc),
        autonomous_context=autonomous,
        issue_number=str(issue_number or ""),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    final = record_alignment_verdict(
        record,
        state_path=Path(state_path) if state_path is not None else None,
        session_id=session_id,
        repo_root=root,
        user_approved=user_approved,
        autonomous_context=autonomous,
    )

    result = final.to_dict()
    result["alignment_passed"] = final.verdict.value in ALLOWED_VERDICTS
    result["has_invariants"] = doc.has_invariants
    result["project_md_found"] = project_md_found
    return result
