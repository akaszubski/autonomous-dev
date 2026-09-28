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
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Tuple

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
#: ``user_approved`` is retained ONLY so historical pre-#1802 signed states
#: still read as passing; no code path can produce a new one (see #1802).
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
    #: Evidentiary trail for an APPLIED approval. Since Issue #1802 closed the
    #: upgrade path this is ALWAYS None on verdicts this library produces; the
    #: field survives so historical artifacts still deserialize.
    approval: Optional[Dict[str, Any]] = None
    #: Why an attempted ``user_approved`` upgrade was REFUSED —
    #: ``"autonomous_context"`` (nobody was there to ask) or
    #: ``"no_verifiable_approval_channel"`` (Issue #1802: nobody can prove who
    #: answered). The attempt stays visible in the audit trail.
    user_approved_refused: str = ""
    #: True when a caller tried to approve this escalation by any means.
    #: Recorded so repeated approval attempts are countable in the audit trail
    #: rather than inferable only from the refusal string (Issue #1802).
    attempted_user_approval: bool = False
    #: True when :func:`record_alignment_verdict` removed caller-supplied
    #: approval metadata from this verdict before persisting it (Issue #1802,
    #: comment 5849895757). The strip is recorded rather than silent so a
    #: tampering attempt on a non-approval verdict stays visible to an auditor.
    approval_metadata_stripped: bool = False

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
        if self.attempted_user_approval:
            payload["attempted_user_approval"] = True
        if self.approval_metadata_stripped:
            payload["approval_metadata_stripped"] = True
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

#: Phrases naming a change to a documented architecture invariant. Each maps
#: to an INV-* clause: enforcement strength (INV-1), agent isolation (INV-2),
#: pipeline shape (INV-3), protected infrastructure (INV-4), one-topic-one-home
#: (INV-5), deterministic-first (INV-6), signed state (INV-7), local-and-free
#: (INV-8).
#:
#: A phrase here is NOT sufficient on its own (Issue #1600). Matching is gated
#: on sentence onset: the segment carrying the phrase must OPEN with a proposal
#: verb (see :data:`PROPOSAL_ONSET_VERBS`). Before that gate every one of these
#: 30 phrases admitted a plain descriptive sentence — measured 30/30 — so any
#: brief *describing* an invariant violation escalated, which is exactly the
#: brief needed to *repair* one.
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


#: Openers that mark a segment as PROPOSING a change rather than describing one.
#: English marks proposal positionally, in three shapes, all covered here:
#: bare imperative (``Drop the hmac ...``), first/second-person subject plus a
#: modal or volitional verb (``We should drop ...``, ``I want to drop ...`` —
#: see :data:`PROPOSER_SUBJECT_ONSETS`), and a proposal noun (``Proposal to
#: drop ...``). Descriptions open with a third-person subject or an adverbial.
#: So this is a property of the segment, not of the phrase, and needs no
#: per-phrase classification. Despite the name the set holds a few nouns
#: (``proposal``, ``suggestion``, ``recommendation``); the name is public API
#: and is kept for compatibility.
#:
#: REPAIR VERBS ARE DELIBERATELY EXCLUDED (Issue #1600): ``fix``, ``add``,
#: ``document``, ``test``, ``harden``, ``strengthen``, ``block``, ``enforce``,
#: ``restore``, ``gate`` and ``tighten`` must never appear here. A brief that
#: repairs an invariant violation opens with exactly those verbs; admitting one
#: recreates the defect this constant exists to fix.
#:
#: A MISSING ENTRY COSTS RECALL, SILENTLY. This set is the ONLY route by which
#: a phrase can reach an escalation, so a genuine proposal phrased with an
#: opener that is absent CLEARS leaving no trace — there is no second detector
#: behind it. That is not hypothetical: the first pass of Issue #1600 shipped
#: an imperatives-only set, and four measured proposals ("Proposal to drop the
#: hmac ...", "I want to drop ...", "Suggest we drop ...", "We should drop
#: ...") escalated under the pre-#1600 substring matcher and CLEARED after it.
#: Stage 0's ESCALATE is un-overridable by an LLM (INV-6), so a lost true
#: positive costs strictly more than a spurious escalation. The set therefore
#: MUST cover hedged and modal openers, not only bare imperatives.
#:
#: Errors here are NOT one-directional, and the earlier claim that they were is
#: what hid the hole: a spurious entry over-escalates (cheap, visible), a
#: missing entry under-escalates (expensive, invisible). Every edit is
#: re-measured in BOTH directions — the 30-row descriptive census and the named
#: 12-entry positive population in
#: ``tests/regression/test_alignment_delta_precision.py``.
#:
#: ``must`` is deliberately absent: it reads as policy statement at least as
#: often as proposal ("We must not self-attest a judgment"), and unlike a
#: missing entry a spurious one here is measurable, so it is excluded until a
#: measured proposal needs it.
PROPOSAL_ONSET_VERBS: FrozenSet[str] = frozenset(
    {
        # Imperative openers.
        "replace",
        "reorder",
        "drop",
        "remove",
        "delete",
        "merge",
        "consolidate",
        "duplicate",
        "allow",
        "permit",
        "require",
        "override",
        "switch",
        "move",
        "make",
        "use",
        "skip",
        "disable",
        "relax",
        "loosen",
        "weaken",
        "share",
        "split",
        "swap",
        "downgrade",
        "bypass",
        "let",
        # Modal / volitional openers, reached either bare or after one
        # PROPOSER_SUBJECT_ONSETS token ("we should", "I want to").
        "should",
        "could",
        "want",
        "wish",
        "need",
        "plan",
        # Suggestion openers.
        "suggest",
        "consider",
        "propose",
        "recommend",
        # Proposal nouns, for "<noun> to <verb> ..." with no colon. A colon
        # lead-in ("Proposal: drop the hmac") is already handled by
        # segmentation, which makes "drop" the onset of the next segment.
        "proposal",
        "suggestion",
        "recommendation",
    }
)

#: Tokens a proposal may place BEFORE its opener — first/second-person
#: subjects, opinion verbs and hedging adverbs. The opener is located by
#: skipping a CONTIGUOUS run of these and nothing else, so "I think we should
#: drop the hmac" reaches ``should`` while census row 23, "A reviewer asked
#: whether we should duplicate this content into the runbook; the answer is
#: no", stops dead at ``a``.
#:
#: THE CLOSED SET IS THE PROTECTION, not :data:`_MAX_FRAME_TOKENS`. Reporting
#: verbs (``asked``, ``debated``, ``wondered``), third-person subjects
#: (``they``, ``the``, ``a``) and every other content word terminate the scan
#: immediately, which is what keeps the gate positional. Row 23 is the sentence
#: that made onset matching beat containment in the original design analysis;
#: it is re-measured on every change to this module.
#:
#: First and second person only. A third-person subject ("they should ...",
#: "the reviewer should ...") reports someone else's position rather than
#: making a proposal; those are left to the imperative and noun shapes.
PROPOSAL_FRAME_TOKENS: FrozenSet[str] = frozenset(
    {
        # First/second-person subjects.
        "i",
        "we",
        "you",
        # Opinion verbs — "I think we should ...".
        "think",
        "believe",
        "feel",
        # Hedging adverbs — "Maybe we should ...".
        "maybe",
        "perhaps",
        "ideally",
        "honestly",
        "personally",
    }
)

#: Secondary cap on the frame run. Belt-and-braces only: the closed set above
#: already terminates the scan at the first content word. Four covers the
#: longest natural frame ("personally I think we should ...").
_MAX_FRAME_TOKENS = 4

#: Sentence/clause boundaries. No entry in :data:`ARCHITECTURE_DELTA_PHRASES`
#: contains any of these characters (asserted by the regression suite), so
#: every phrase occurrence lies wholly inside one segment and segmentation
#: cannot lose a match the previous whole-text matcher would have found.
_SEGMENT_DELIMITERS = re.compile(r"[\n.;:!?,]")

#: Characters trimmed from both ends of a candidate onset token — quotes,
#: markdown emphasis, list bullets, blockquote markers and brackets.
_ONSET_TOKEN_TRIM = "\"'`*_-([{<>}])!.,;:?/\\|~#&+="

#: A gerund/participle token: at least three stem characters plus ``ing``. The
#: floor keeps short function words ("being", "using") from being restemmed
#: into noise; nothing in ARCHITECTURE_DELTA_PHRASES depends on them.
_GERUND_TOKEN = re.compile(r"\b([a-z][a-z-]{2,})ing\b")

#: The three spelling changes English ``-ing`` makes, each reversed by one
#: rule. ``bare``: none ("reordering" -> "reorder"). ``undouble``: a final
#: consonant was doubled ("dropping" -> "dropp" -> "drop"). ``silent_e``: a
#: final ``e`` was dropped ("merging" -> "merg" -> "merge").
_DEGERUND_RULES: Tuple[str, ...] = ("bare", "undouble", "silent_e")


def _segments(text: str) -> List[str]:
    """Split text into sentence-like segments on punctuation and newlines.

    Args:
        text: Text to segment.

    Returns:
        Non-empty, stripped segments in source order.
    """
    return [seg.strip() for seg in _SEGMENT_DELIMITERS.split(text) if seg.strip()]


def _leading_tokens(segment: str, limit: int) -> List[str]:
    """Return up to ``limit`` normalized word-bearing tokens from the opening.

    Each token is lowercased, stripped of surrounding non-alphanumerics (quotes,
    markdown emphasis, list bullets, blockquote markers) and truncated at an
    apostrophe, so ``Let's`` normalizes to ``let``.

    Purely punctuational leading tokens (``-``, ``*``, ``>``, ``#``) are skipped
    rather than treated as the onset, so a proposal written as a markdown list
    item or blockquote is not silently exempted.

    Args:
        segment: One segment from :func:`_segments`.
        limit: Maximum number of tokens to return.

    Returns:
        The normalized leading tokens, in source order.
    """
    tokens: List[str] = []
    for token in segment.split():
        normalized = token.lower().strip(_ONSET_TOKEN_TRIM)
        if not normalized:
            continue  # markdown bullet / blockquote marker, not the onset
        tokens.append(normalized.split("'", 1)[0])
        if len(tokens) == limit:
            break
    return tokens


def _has_proposal_onset(segment: str) -> bool:
    """Report whether a segment OPENS with a proposal.

    The opener is the first word-bearing token that is not part of a proposal
    frame. Leading tokens are consumed while they are in
    :data:`PROPOSAL_FRAME_TOKENS`; the scan stops at the first token that is
    not, and that token must be in :data:`PROPOSAL_ONSET_VERBS`. So all of
    ``Drop the hmac ...``, ``We should drop ...``, ``Maybe we should drop ...``
    and ``I think we should drop ...`` qualify, while ``A reviewer asked
    whether we should duplicate ...`` stops at ``a`` and does not.

    Comparison is by EXACT token equality, so ``Let's`` matches ``let`` while
    the third-person ``Replaces`` does not match ``replace``. That distinction
    is load-bearing: it is what lets a brief reporting *"Replaces prompt-level
    advisory text with a hook"* clear the gate.

    Args:
        segment: One segment from :func:`_segments`.

    Returns:
        True if the segment opens with a proposal.
    """
    for index, token in enumerate(_leading_tokens(segment, _MAX_FRAME_TOKENS + 1)):
        if token in PROPOSAL_ONSET_VERBS:
            return True
        if index >= _MAX_FRAME_TOKENS or token not in PROPOSAL_FRAME_TOKENS:
            return False
    return False


def _degerund_stem(stem: str, rule: str) -> str:
    """Reverse one ``-ing`` spelling change on an already ``ing``-stripped stem.

    Args:
        stem: The token with its trailing ``ing`` removed (``dropp``, ``merg``).
        rule: One of :data:`_DEGERUND_RULES`.

    Returns:
        The candidate base form under that rule.
    """
    if rule == "undouble":
        if len(stem) >= 3 and stem[-1] == stem[-2] and stem[-1] not in "aeiou":
            return stem[:-1]
        return stem
    if rule == "silent_e":
        return stem + "e"
    return stem


def _degerund_variants(segment: str) -> Tuple[str, ...]:
    """Return de-inflected rewrites of ``segment``, at most one per rule.

    A gerund hides a phrase from substring matching: ``"dropping the hmac"``
    does not contain ``"drop the hmac"``, so ``Consider dropping the hmac
    signature`` cleared both before and after Issue #1600's first pass. The
    suggestion openers added in its remediation (``consider``, ``propose``,
    ``suggest``, ``recommend``) take a gerund complement in ordinary English,
    which makes the two changes only useful together.

    Purely ADDITIVE: :func:`detect_architecture_delta` matches the original
    segment as well, so a rewrite can only ADD a match, never remove one. A
    rewrite that mangles an unrelated word (``handling`` -> ``handl``) is
    therefore harmless.

    Args:
        segment: One lowercased segment from :func:`_segments`.

    Returns:
        Distinct rewrites, excluding any identical to ``segment``. Empty when
        the segment contains no gerund.
    """
    if "ing" not in segment:
        return ()
    variants: List[str] = []
    for rule in _DEGERUND_RULES:
        rewritten = _GERUND_TOKEN.sub(
            lambda match, _rule=rule: _degerund_stem(match.group(1), _rule), segment
        )
        if rewritten != segment and rewritten not in variants:
            variants.append(rewritten)
    return tuple(variants)


def detect_architecture_delta(feature_text: str, doc: ProjectDoc) -> Optional[str]:
    """Return the architecture-delta phrase a feature PROPOSES, or None.

    A phrase escalates only when the segment containing it begins with a
    proposal onset (Issue #1600). Merely *describing* an invariant violation —
    the shape of every brief that sets out to repair one — no longer escalates.

    "Begins with a proposal onset" covers the imperative (``Drop the hmac
    ...``), the hedged/modal (``We should drop ...``, ``I want to drop ...``)
    and the proposal-noun (``Proposal to drop ...``) shapes; see
    :func:`_has_proposal_onset`. Each segment is matched both as written and
    de-gerunded (:func:`_degerund_variants`), so ``Consider dropping the hmac
    signature`` reaches ``drop the hmac``.

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
    for segment in _segments(feature_text.lower()):
        if not _has_proposal_onset(segment):
            continue
        # The raw segment FIRST, so de-gerunding can only add matches.
        candidates = (segment,) + _degerund_variants(segment)
        # Tuple order, not segment order, decides which phrase is reported —
        # test_zero_width_architecture_delta_still_escalates pins the exact
        # return value for a segment matching two phrases.
        for phrase in ARCHITECTURE_DELTA_PHRASES:
            if any(phrase in candidate for candidate in candidates):
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

    **This function can never return** :attr:`Verdict.USER_APPROVED`. It once
    took a ``user_approved`` keyword that upgraded ``ESCALATE``; Issue #1802
    REMOVED that parameter and the upgrade branch outright rather than leaving
    them unreachable-by-convention. ``map_verdict`` has no leading underscore,
    so it is part of this module's public surface: any external caller that
    imported it, passed the flag and inspected the result would have seen a
    ``USER_APPROVED`` that never passed through
    :func:`record_alignment_verdict`'s refusal. Keeping the parameter safe only
    because the one production call site declined to use it is exactly the
    "guard scoped to the wired path" shape this fix exists to remove.

    Removal was chosen over retention because the blast radius is zero — no
    production caller passed the flag — and because a deleted parameter fails
    LOUDLY (``TypeError``) for any future caller, where an ignored one would
    fail silently and look like it had worked. Approval now has exactly one
    home: :func:`record_alignment_verdict`, which refuses it.

    Args:
        stage0: Deterministic pre-check result.
        classification: Stage 1 classification, or None on classifier failure.
        cited_clause: Clause Stage 1 cited from PROJECT.md.
        doc: Parsed PROJECT.md.

    Returns:
        The final :class:`Verdict` — one of ``BLOCK``, ``AUTO_PASS`` or
        ``ESCALATE``, never ``USER_APPROVED``.
    """
    if stage0.outcome is Stage0Outcome.BLOCK:
        return Verdict.BLOCK

    # INV-6: the deterministic outcome cannot be overridden by Stage 1.
    if stage0.outcome is Stage0Outcome.ESCALATE:
        return Verdict.ESCALATE

    if not classification or classification not in _KNOWN_CLASSIFICATIONS:
        # Classifier failure, timeout, or an invented label: fail closed.
        return Verdict.ESCALATE

    effective = classification
    if effective == "architecture_delta" and not doc.has_invariants:
        # No documented invariants — judge on scope evidence alone.
        effective = _IN_SCOPE_CLASSIFICATION

    if effective != _IN_SCOPE_CLASSIFICATION:
        return Verdict.ESCALATE

    if not verify_citation(cited_clause, doc):
        return Verdict.ESCALATE

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

# ---------------------------------------------------------------------------
# The escalate -> USER_APPROVED upgrade is fail-closed AT THIS API (Issue #1802)
#
# SCOPE OF THE CLAIM: "closed" below means closed at the canonical library
# surface — record_alignment_verdict, evaluate_and_record, map_verdict. It does
# NOT mean the property holds system-wide. A caller that bypasses this choke
# point and writes .claude/alignment_verdict.json or re-signs pipeline state
# itself is outside everything described here, and runs as the same principal,
# so that ceiling stays OPEN (#1807). The genuine human-approval positive arm
# is UNMEASURED. Issue #1802 remains OPEN: this is a partial fix.
#
# ``user_approved`` was a caller-supplied boolean, and the library synthesized
# ``approval = {"source": "ask_user_question", ...}`` from it. The approval
# sub-object was therefore manufactured from the same assertion it was supposed
# to evidence, and any coordinator acting on standing instructions could turn a
# deterministic ESCALATE into a pass. Observed live on 2026-09-25 (run
# 01e99c0efb9202ae) and 2026-09-27 (run 5b7478ef3af7718e).
#
# No receipt object fixes this. Anything the coordinator can hand to this
# library, the coordinator can also manufacture: it runs as the same principal,
# so it can reach any signing key this process can reach. Nor is there a
# response SHAPE that proves a human — AskUserQuestion ``updatedInput.answers``
# may be supplied programmatically. A signed, bound, single-use record would
# only relocate the self-attestation and dress it up as evidence.
#
# So the upgrade is refused outright until an INDEPENDENTLY verifiable receipt
# channel exists (#1807). Refusing an unknown is the fail-closed answer;
# labelling it honestly and then permitting it is not.
# ---------------------------------------------------------------------------

#: Refusal recorded when any caller tries to approve an escalation.
APPROVAL_UNAVAILABLE = "no_verifiable_approval_channel"

#: Model-visible explanation. Names the issue and the routes that remain open,
#: so a refused coordinator has somewhere to go instead of retrying the flag.
APPROVAL_UNAVAILABLE_MESSAGE = (
    "user approval cannot be recorded (Issue #1802): this library has no "
    "independently verifiable approval receipt, and a caller-supplied flag or "
    "receipt object is indistinguishable from a forged one because the caller "
    "runs as the same principal. Remaining options: narrow the change to stay "
    "in scope, update PROJECT.md scope and re-run the gate, or stop."
)


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


def _sanitize_approval_metadata(
    verdict: AlignmentVerdict,
) -> Tuple[AlignmentVerdict, bool]:
    """Remove caller-supplied approval metadata and report what WAS removed.

    This library never CREATES any of these fields, so anything arriving in
    them is caller-supplied and cannot be evidence of anything.

    ``approval_metadata_stripped`` is itself caller-supplied trust state — the
    marker added to record tampering was forgeable by the same route it was
    meant to record (Issue #1802, comment 5850061581). The inbound value is
    therefore NEVER read into the result: the marker is computed exactly once,
    here, from the SUBSTANTIVE fields this call actually cleared, and returned
    alongside so the caller of this helper cannot disagree with it either.

    Semantics chosen, and the trade-off: a lone forged marker on an otherwise
    clean verdict is discarded and reported as ``False``, NOT as tampering.
    Counting it as tampering would also satisfy "derived, never read", but it
    would make a forged ``True`` and a derived ``True`` indistinguishable by
    observation — there would be no test that can tell pass-through from
    derivation. Reporting ``False`` makes the ignore-invariant directly
    provable in both directions. The cost is that faking the marker alone
    leaves no audit record; accepted because a lone marker asserts nothing
    about approval, so nothing is laundered by discarding it quietly.

    Args:
        verdict: The inbound verdict, trusted for nothing but its ``verdict``
            enum and its Stage 0 / Stage 1 evidence fields.

    Returns:
        ``(clean_verdict, was_stripped)`` where ``was_stripped`` is True only
        when substantive approval metadata was present and removed.
    """
    stripped = bool(
        verdict.approval is not None
        or verdict.user_approved_refused
        or verdict.attempted_user_approval
    )
    if not (stripped or verdict.approval_metadata_stripped):
        return verdict, False
    return (
        dataclasses.replace(
            verdict,
            approval=None,
            user_approved_refused="",
            attempted_user_approval=False,
            approval_metadata_stripped=stripped,
        ),
        stripped,
    )


def record_alignment_verdict(
    verdict: AlignmentVerdict,
    *,
    state_path: Optional[Path] = None,
    session_id: str = "unknown",
    repo_root: Optional[Path] = None,
    user_approved: bool = False,
    autonomous_context: Optional[bool] = None,
    approval_record: Optional[Mapping[str, Any]] = None,
) -> AlignmentVerdict:
    """Persist a verdict and write ``alignment_passed`` into pipeline state.

    This is the SOLE writer of ``alignment_passed`` — every other component
    reads it. The order matters: the artifact is written first, and if that
    write fails the verdict is downgraded to ``ESCALATE`` before state is
    touched, so ``alignment_passed`` is never True without a durable record.

    It is also the SOLE place an approval could ever take effect, which is why
    Issue #1802 closes the upgrade HERE: no caller input can turn an
    ``ESCALATE`` into a ``USER_APPROVED``. A bare ``user_approved=True``, an
    ``approval_record`` receipt object, and a verdict that arrives already
    carrying ``USER_APPROVED`` are all refused identically, because all three
    originate with the same principal and none is distinguishable from a
    forgery. The attempt is recorded in ``user_approved_refused`` so it stays
    visible in the audit trail rather than disappearing.

    This library therefore never writes an ``approval`` sub-object, and never
    emits ``source = "ask_user_question"``. Re-opening the upgrade requires an
    independently verifiable receipt channel, which does not exist (#1807).

    Because the library never CREATES that sub-object, any approval metadata
    arriving on an inbound verdict is caller-supplied. It is stripped from
    EVERY verdict before persistence — not only the approval-relevant ones.
    Scoping the strip to approval-relevant verdicts was the defect in issue
    comment 5849895757: an ``AUTO_PASS`` or ``BLOCK`` skipped the branch, so a
    forged ``approval.source = "ask_user_question"`` reached the artifact, the
    audit row and signed state. Forged ``user_approved_refused`` and
    ``attempted_user_approval`` laundered the same way.

    The correction STRIPS rather than downgrades. The verdict was computed
    deterministically by :func:`map_verdict` from Stage 0 plus citation
    verification, so forged metadata does not invalidate it, and refusing
    would over-refuse honest work whose caller reused a stale object. The
    metadata is what lies, so the metadata is what is removed —
    ``approval_metadata_stripped`` records that it happened so the attempt is
    auditable rather than silently dropped. That marker is derived SOLELY from
    what :func:`_sanitize_approval_metadata` actually cleared in this call; a
    caller-set value is discarded and never read, because the marker is
    caller-supplied trust state exactly like the fields it reports on.

    Never pass this function's own return value back into itself — the
    sanitization step cannot distinguish its own prior output from caller
    forgery, so a round-tripped refusal would be re-reported as tampering.
    Not currently reachable (:func:`evaluate_and_record` always builds a fresh
    verdict), but the assumption is load-bearing and unenforced.

    Args:
        verdict: The verdict produced by :func:`map_verdict` and its evidence.
        state_path: Signed pipeline-state file to update (skipped if absent).
        session_id: Session id used to re-sign the state.
        repo_root: Repository root for the artifact and audit log.
        user_approved: Legacy approval flag. Accepted so old callers get a
            recorded REFUSAL rather than a TypeError; it can no longer upgrade
            anything.
        autonomous_context: Pre-computed autonomy flag. ``None`` (the default)
            means detect it here via :func:`is_autonomous_context`; callers that
            already computed it pass it in to avoid a second filesystem probe.
        approval_record: Any caller-supplied approval receipt. Accepted for the
            same reason and refused for the same reason — see the module note
            above on why no such object can be trusted here.

    Returns:
        The final :class:`AlignmentVerdict`, never upgraded.
    """
    # Issue #1802 (comment 5849895757): sanitize caller-supplied approval
    # metadata on EVERY verdict, BEFORE any branch and before persistence.
    # This block used to live inside the approval-relevant branch below, so an
    # AUTO_PASS or BLOCK skipped it entirely and whatever the caller attached
    # was written straight through to the artifact, the audit row and signed
    # state. This library never CREATES these fields, so anything arriving in
    # them is by definition caller-supplied and cannot be evidence.
    #
    # STRIP, do not downgrade: the verdict itself was computed deterministically
    # by map_verdict() from Stage 0 plus citation verification, so forged
    # metadata does not invalidate it, and refusing would over-refuse honest
    # work whose caller merely reused a stale object. The metadata is the thing
    # that lies, so the metadata is what is removed — and the removal is
    # recorded in approval_metadata_stripped so it is auditable, not silent.
    final, _stripped = _sanitize_approval_metadata(verdict)

    approval_relevant = (
        ((user_approved or approval_record is not None) and final.verdict is Verdict.ESCALATE)
        or (final.verdict is Verdict.USER_APPROVED)
    )
    if approval_relevant:
        autonomous = (
            is_autonomous_context(repo_root=repo_root)
            if autonomous_context is None
            else bool(autonomous_context)
        )
        # Autonomy keeps its own reason: "nobody was there to ask" and "we
        # cannot verify who answered" are different facts, and an auditor
        # reading the trail needs to tell them apart.
        refusal = "autonomous_context" if autonomous else APPROVAL_UNAVAILABLE
        detail = (
            "autonomous context"
            if autonomous
            else APPROVAL_UNAVAILABLE_MESSAGE
        )
        final = dataclasses.replace(
            final,
            verdict=Verdict.ESCALATE,
            approval=None,
            attempted_user_approval=True,
            user_approved_refused=refusal,
            reasoning=(f"{final.reasoning} [user approval refused: {detail}]").strip(),
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
    """Record the alignment fields into an ALREADY-SIGNED pipeline state, fail closed otherwise.

    This is a SIGNING ORACLE and is guarded exactly like
    ``pipeline_state.set_pipeline_base_commit`` (Issue #1807, the SECOND re-sign
    path — this one runs on EVERY F1 alignment). Recording an alignment pass
    means MINTING a signature, so it is permitted ONLY on a state that ALREADY
    holds a valid one. Every not-validly-signed shape it CAN CLASSIFY returns
    ``False`` with NO write and NO mint (see the MALFORMED-INPUT CAVEAT below for
    the one shape that currently RAISES instead of returning). Order (any
    classified failure returns False, no mutation, no write):

        not a dict -> reject
        no ``hmac`` -> reject (see FAIL CLOSED ON UNSIGNED below)
        indeterminate owner -> reject
        unrecognized declared MAC version -> reject
        strict verify fails at that version -> reject
        per-run secret unreadable -> reject
        else: set alignment fields, re-sign AT THE DECLARED VERSION, write.

    MALFORMED-INPUT CAVEAT (return-contract honesty): the "returns False" contract
    holds for every not-validly-signed shape this function can CLASSIFY. It does
    NOT yet hold for a MALFORMED signed state — a non-str signed field (e.g.
    ``mode=123``) or a non-str ``hmac`` — WITH a live per-run secret: the strict
    verify then reaches the shared ``verify_state_hmac`` / ``_compute_state_hmac``
    primitive, whose v1/v2 ``"|".join`` / ``compare_digest`` are not type-guarded,
    and RAISES ``TypeError`` out of this function. That raise is FAIL-CLOSED on
    authority/effects — it is NOT a permit: the hook consumer
    ``_load_pipeline_state_verified`` catches ``Exception`` and denies. It does,
    however, abort a DIRECT ``record_alignment_verdict`` caller. The durable narrow
    malformed-input guard belongs in ``verify_state_hmac`` itself (so it also fixes
    ``classify_current_run_authority``'s "never raises" contract) and is tracked
    separately (#1807/#1757); it is deliberately NOT bolted on here.

    FAIL CLOSED ON UNSIGNED (Issue #1807, second-order laundering oracle). An
    arbitrary unsigned JSON file and a signed state whose ``hmac`` was DELETED are
    OBSERVATIONALLY IDENTICAL at this call site — there is no trustworthy
    in-process criterion to tell "genuine legacy" from "attacker stripped the
    hmac". The former ``else: sign_state(...)`` unsigned-legacy branch was itself
    a laundering oracle: stripping ``hmac`` from a tampered signed state routed to
    it and was handed a FRESH VALID signature carrying ``alignment_passed=True``
    (returned True, verified True, the tampered field survived). It has been
    REMOVED. Any state that is not validly signed — no ``hmac``, unrecognized
    version, indeterminate owner, failed strict-verify — is refused.

    BACKWARD-COMPAT CONSEQUENCE (named, justified reduction — NOT weakening): a
    genuinely-unsigned historical pipeline state is no longer auto-signed by the
    alignment path. Migrating one is NOT this function's job; it requires a
    SEPARATE explicitly-authenticated / reinitialized path (a fresh run that
    signs its state BEFORE alignment, which is what the normal F1 flow already
    does). No heuristic legacy-positive is attempted, by design: any such shape
    check would be exactly the criterion an attacker forges.

    Re-signing is done at the DECLARED version, NOT upgraded to the current one:
    ``sign_state`` always targets ``_STATE_MAC_CURRENT`` (v3), which binds
    ``issue_number``/``subject``/``base_commit`` — fields ABSENT from the v1/v2
    signed message — so upgrading would launder those still-unauthenticated
    values into an authenticated v3. ``alignment_passed``/``alignment_verdict``
    are in the signed message at ALL versions, so re-signing at the declared
    version still covers the two fields written here. The MAC is recomputed
    directly (mirroring ``verify_state_hmac``'s version dispatch) because
    ``sign_state`` cannot target a specific version; ``hmac_version`` and
    ``nonce`` are left untouched so the state stays at its declared version.

    FAIL-CLOSED downstream: on refuse the on-disk state is left unchanged (no new
    alignment pass is minted), so ``record_alignment_verdict``'s consumers refuse
    it — but the refusal MECHANISM differs by shape. A TAMPERED signed state fails
    strict verify here (MAC_INVALID). An UNSIGNED / no-hmac state is refused as
    UNSIGNED_LEGACY by ``classify_current_run_authority`` (authorized=False),
    reached via ``unified_pre_tool._has_alignment_passed`` ->
    ``_load_pipeline_state_verified`` -> ``_state_authorizes_current_run`` — NOT by
    ``verify_state_hmac``, which still returns True on an ABSENT hmac (legacy
    recognition, not authority). Either way ``alignment_passed=True`` is never
    persisted into a valid signature over a state that failed strict verify.

    Args:
        state_path: Path to the pipeline state JSON.
        session_id: Retained for API compatibility. The re-sign binds the state's
            OWN declared owner (mirroring ``set_pipeline_base_commit``), never
            this argument, so it can no longer mint an owner onto a state.
        alignment_passed: Value for the ``alignment_passed`` gate field.
        verdict_value: Value for the ``alignment_verdict`` audit field.

    Returns:
        True when the state file was updated and re-signed; False (with NO write)
        when the file is absent/unreadable, not a dict, unsigned, lacks a
        determinate owner, declares an unrecognized version, fails strict verify,
        or has no readable per-run secret. Does NOT return on a MALFORMED signed
        state with a live secret — it RAISES ``TypeError`` from the shared verify
        primitive (fail-closed at the hook, but aborts a direct caller); see the
        MALFORMED-INPUT CAVEAT above (durable guard tracked in #1807/#1757).
    """
    if not state_path.exists():
        return False
    try:
        from pipeline_state import (
            _compute_state_hmac,
            _declared_mac_version,
            _is_determinate_session_id,
            _read_pipeline_secret,
            verify_state_hmac,
        )
    except ImportError:
        try:
            if str(_THIS_DIR) not in sys.path:
                sys.path.insert(0, str(_THIS_DIR))
            from pipeline_state import (
                _compute_state_hmac,
                _declared_mac_version,
                _is_determinate_session_id,
                _read_pipeline_secret,
                verify_state_hmac,
            )
        except ImportError:
            return False
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False

    # Hole B: a non-dict payload ([1,2,3], a scalar, null) has no ``.get`` and is
    # not a pipeline state — refuse rather than raise AttributeError below.
    if not isinstance(state, dict):
        return False

    # Hole A: FAIL CLOSED on anything not validly signed. Minting a signature
    # (recording an alignment pass) is permitted ONLY over a state that already
    # holds a valid one, verified BEFORE any mutation.
    if state.get("hmac") is None:
        return False
    owner = state.get("session_id")
    if not _is_determinate_session_id(owner):
        return False
    version = _declared_mac_version(state)
    if version is None:
        return False
    if not verify_state_hmac(state, owner, strict=True):
        return False
    run_id = state.get("run_id", "")
    secret = _read_pipeline_secret(run_id) if run_id else None
    if secret is None:
        return False

    try:
        state["alignment_passed"] = alignment_passed
        state["alignment_verdict"] = verdict_value
        # RE-SIGN AT THE DECLARED VERSION (no v2->v3 upgrade).
        state["hmac"] = _compute_state_hmac(state, secret, version=version)
    except (ValueError, TypeError):
        return False

    try:
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError:
        return False
    return True


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
    approval_record: Optional[Mapping[str, Any]] = None,
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
        user_approved: Legacy approval flag. Always REFUSED since Issue #1802
            — see :func:`record_alignment_verdict`.
        issue_number: Issue number recorded in the audit artifact.
        approval_record: Any caller-supplied approval receipt. Also always
            refused, for the same reason.

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
    except OSError as exc:
        # Issue #1802: an UNREADABLE PROJECT.md used to escape as an uncaught
        # PermissionError, so the gate crashed instead of blocking — a caller
        # that swallowed the exception would proceed ungated. Any OSError is
        # now the same fail-closed BLOCK as a missing file (INV-7).
        doc = ProjectDoc(path=md_path)
        project_md_found = False
        unreadable = "" if isinstance(exc, FileNotFoundError) else f" ({type(exc).__name__})"

    feature_text = feature_text or ""
    if project_md_found:
        stage0 = run_stage0(feature_text, doc)
    else:
        stage0 = Stage0Result(
            outcome=Stage0Outcome.BLOCK,
            reason=f"PROJECT.md not found: {md_path}{unreadable}",
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
        approval_record=approval_record,
    )

    result = final.to_dict()
    result["alignment_passed"] = final.verdict.value in ALLOWED_VERDICTS
    result["has_invariants"] = doc.has_invariants
    result["project_md_found"] = project_md_found
    return result
