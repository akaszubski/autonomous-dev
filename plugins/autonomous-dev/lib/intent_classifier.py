#!/usr/bin/env python3
"""Semantic intent classifier for user prompts.

Phase 1 of the autonomous-dev semantic intent classifier. The hook layer reads
the result and may relax false-positive routing blocks WHILE preserving the
security gate. This module produces the IntentResult; it never enforces.

Architecture (override-only, do NOT change without re-reading the plan):

1. Regex runs BEFORE the LLM. Any security keyword match short-circuits to
   IntentClass.SECURITY_CRITICAL and the LLM is never called. This prevents
   prompt-injection bypassing the security gate (OWASP LLM01:2025) and
   replicates the Issue #141 lesson where the LLM rephrased the prompt and
   lost the security signal.
2. Fail-open semantics. Any failure path — timeout, exception, malformed
   JSON, intent outside the enum, low confidence, ambiguous result — returns
   IntentResult(intent=AMBIGUOUS, fail_open=True, requires_security_audit=True).
   Never default to "skip security".
3. Defense-in-depth on the enum: the prompt instructs Haiku to return one of
   the 9 classes, AND the parser rejects anything outside the enum.
4. Coexists with the existing INTENT_CLASSIFICATION_PROMPT in genai_prompts.py
   (5-class scheme used by auto_generate_tests.py). This module defines its
   own private prompt template; it does not import or mutate genai_prompts.

Public API:
    IntentClass — 10-value enum (9 intents + AMBIGUOUS sentinel)
    IntentResult — frozen dataclass with classification + telemetry fields
    IntentClassifier — main class with classify() and from_config()

Telemetry:
    Every call emits one JSONL line to .claude/logs/activity/{YYYY-MM-DD}.jsonl
    with 9 fields. Telemetry failures NEVER raise.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# GenAI bridge (mirrors lib/issue_scope_detector.py:62-79)
# ============================================================================
#
# genai_utils lives in plugins/autonomous-dev/hooks/. We bridge sys.path so
# this lib module can import it. If the SDK is unavailable, the classifier
# degrades to regex-only mode (fail-open for non-security prompts).

_HOOKS_PATH = Path(__file__).parent.parent / "hooks"
if _HOOKS_PATH.exists() and str(_HOOKS_PATH) not in sys.path:
    sys.path.insert(0, str(_HOOKS_PATH))

try:
    from genai_utils import GenAIAnalyzer  # type: ignore[import-not-found]
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False
    GenAIAnalyzer = None  # type: ignore[assignment,misc]


# ============================================================================
# Constants
# ============================================================================

# Pinned model — do NOT use the genai_prompts default; this classifier needs
# stability across model upgrades since it gates security-critical routing.
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_MAX_TOKENS = 300
DEFAULT_TIMEOUT_SECONDS = 5
DEFAULT_CONFIDENCE_THRESHOLD = 0.85
DEFAULT_MAX_PROMPT_CHARS = 10000

# Default security keywords if config file is missing/malformed. Mirrors
# config/intent_classifier_config.json. Keep this list in sync OR rely on
# config file as source of truth (the config file wins when loadable).
_DEFAULT_SECURITY_KEYWORDS: List[str] = [
    "auth", "authn", "authz", "authentication", "authorization",
    "token", "secret", "password", "passwd",
    "encrypt", "decrypt", "crypto", "cryptography",
    "sso", "saml", "oauth", "oauth2", "jwt",
    "rbac", "permission", "permissions", "session",
    "credential", "credentials",
    "cve", "vulnerability", "exploit",
    "migrate", "migration", "schema",
    "key", "api_key", "api-key", "apikey",
    "sql injection", "xss", "csrf", "ssrf",
]

# Path to the default config file (relative to this module's parent).
_DEFAULT_CONFIG_PATH = (
    Path(__file__).parent.parent / "config" / "intent_classifier_config.json"
)


# ============================================================================
# Enums and Dataclasses
# ============================================================================


class IntentClass(Enum):
    """Semantic intent classes for user prompts.

    The 9 task classes describe what the user is trying to do. The 10th
    (AMBIGUOUS) is the fail-open sentinel: any failure or low-confidence
    result becomes AMBIGUOUS so callers fall back to the safer routing path.

    Values:
        SECURITY_CRITICAL: Auth, crypto, secrets, migrations, schema, RBAC, etc.
            ALWAYS triggered if any security keyword regex hits, BEFORE the LLM.
        IMPLEMENT: Building new features, adding functionality, new code.
        REFACTOR: Restructuring without behavior change, renaming, cleanup.
        TEST: Writing or fixing tests.
        DOC: Documentation, README, docstrings, changelogs.
        CONFIG: Settings, .json/.yaml/.toml tweaks, env vars, hook configs.
        TYPO: Single-character or word-level fixes; trivial edits.
        STATUS_QUERY: "what is...", "show me...", "how do I..." — read-only.
        CONVERSATION: Chat, brainstorming, advice, opinions — no concrete task.
        AMBIGUOUS: Sentinel for fail-open. Caller MUST treat as security-relevant.
    """

    SECURITY_CRITICAL = "security_critical"
    IMPLEMENT = "implement"
    REFACTOR = "refactor"
    TEST = "test"
    DOC = "doc"
    CONFIG = "config"
    TYPO = "typo"
    STATUS_QUERY = "status_query"
    CONVERSATION = "conversation"
    AMBIGUOUS = "ambiguous"


# The 9 "real" intent classes the LLM is allowed to return. AMBIGUOUS is
# reserved for the fail-open path and MUST NOT come from the LLM.
_VALID_LLM_INTENTS: List[str] = [
    IntentClass.SECURITY_CRITICAL.value,
    IntentClass.IMPLEMENT.value,
    IntentClass.REFACTOR.value,
    IntentClass.TEST.value,
    IntentClass.DOC.value,
    IntentClass.CONFIG.value,
    IntentClass.TYPO.value,
    IntentClass.STATUS_QUERY.value,
    IntentClass.CONVERSATION.value,
]


@dataclass(frozen=True)
class IntentResult:
    """Result of classifying a user prompt.

    Attributes:
        intent: One of the 10 IntentClass values.
        confidence: Float in [0.0, 1.0]. Regex hits get 1.0. LLM results clamped.
        regex_hit: True if a security keyword regex matched (LLM was NOT called).
        llm_used: True if the LLM was called (regex_hit is False AND SDK available).
        fail_open: True if any failure path was hit. Implies intent == AMBIGUOUS.
        requires_security_audit: True if the caller should NOT relax security checks.
            Always True for SECURITY_CRITICAL and AMBIGUOUS.
        prompt_length: Length of the original prompt in characters (post-strip, pre-truncate).
        predicted_file_count: Estimated number of files the task touches (1 = focused, >5 = broad).
            Heuristic only; not a hard guarantee.
        reasoning: Optional one-line explanation (LLM may return; otherwise empty).
    """

    intent: IntentClass
    confidence: float
    regex_hit: bool
    llm_used: bool
    fail_open: bool
    requires_security_audit: bool
    prompt_length: int
    predicted_file_count: int
    reasoning: str = ""


# ============================================================================
# Private LLM prompt template
# ============================================================================
#
# Defined HERE (private to this module) so we don't conflict with the existing
# INTENT_CLASSIFICATION_PROMPT in genai_prompts.py (5-class scheme). DO NOT
# move this to genai_prompts.py — that's a separate intent contract used by
# auto_generate_tests.py.

_LLM_PROMPT_TEMPLATE = """You classify user prompts into one of 9 fixed intent categories. Return STRICT JSON ONLY — no prose, no markdown fences.

User prompt:
{prompt}

Categories (you MUST return one of these exact strings):
- security_critical: Authentication, authorization, encryption, secrets, tokens, sessions, RBAC, OAuth/SAML/JWT/SSO, schema migrations, credentials, vulnerabilities (CVE, XSS, CSRF, SSRF, SQL injection)
- implement: Building new features, adding functionality, creating new code or APIs
- refactor: Restructuring existing code without behavior change, renaming, code cleanup
- test: Writing or fixing tests
- doc: Documentation, README, docstrings, comments, changelogs
- config: Settings, .json/.yaml/.toml/.env edits, hook configs, environment variables
- typo: Trivial fixes — single character or word-level edits, comments, formatting
- status_query: Read-only questions ("what is...", "show me...", "how do I...")
- conversation: Chat, brainstorming, opinions, advice — no concrete code task

Return JSON with this exact schema (NO trailing comma, NO comments, NO extra fields):
{{
  "intent": "<one of the 9 strings above>",
  "confidence": <float between 0.0 and 1.0>,
  "predicted_file_count": <integer 1-50>,
  "reasoning": "<one short sentence>"
}}

Rules:
1. Be conservative. If the prompt is ambiguous, return confidence < 0.7.
2. If ANY security keyword is plausibly relevant, prefer security_critical.
3. predicted_file_count: 1 for trivial edits, 2-3 for focused changes, 5+ for broad changes.
4. Respond with JSON ONLY. No preamble, no explanation outside the reasoning field."""


# ============================================================================
# Helpers
# ============================================================================


def _truncate(text: str, max_chars: int) -> str:
    """Truncate text to max_chars characters."""
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def _build_security_regex(keywords: List[str]) -> "re.Pattern[str]":
    """Build a single compiled regex matching any keyword as a STEM.

    Design choices (safety-biased):
        - Multi-word keywords (e.g. "sql injection") match as exact phrases.
        - Single-word keywords match as STEMS: \\b<keyword> with NO trailing
          boundary. This catches morphological variants AND identifier forms:
              "auth"     matches: auth, authn, authz, authenticate, auth_handler
              "encrypt"  matches: encrypt, encryption, encrypted, encrypts
              "secret"   matches: secret, secrets
              "token"    matches: token, tokens, tokenize, token_store
              "key"      matches: key, keys, keystore, key_id
        - This intentionally OVER-matches (Issue #141 lesson + OWASP LLM01:2025).
          Over-matching SECURITY_CRITICAL means more security audits, never fewer.
        - Keywords with internal dashes/underscores (api_key, api-key) work as
          phrase-like patterns because re.escape preserves them.

    Args:
        keywords: List of security keywords from config or defaults.

    Returns:
        Compiled case-insensitive regex pattern. Returns a never-matching
        pattern if keywords is empty (NOT an empty regex which would match all).
    """
    if not keywords:
        # Use a regex that never matches (negative lookahead) rather than ""
        # which would match every prompt.
        return re.compile(r"(?!)")

    parts: List[str] = []
    for kw in keywords:
        kw = kw.strip()
        if not kw:
            continue
        if " " in kw:
            # Multi-word: match as phrase. Use word boundaries on outer edges.
            parts.append(rf"\b{re.escape(kw)}\b")
        elif "_" in kw or "-" in kw:
            # Compound identifier (api_key, api-key): require word boundaries
            # on outer edges only. \b before underscore/dash works because Python
            # regex \b is between \w and non-\w; underscore is \w but dash is not,
            # so we use lookarounds for safety.
            parts.append(rf"(?:^|[^A-Za-z0-9_-]){re.escape(kw)}(?:$|[^A-Za-z0-9_-])")
        else:
            # Single-word: STEM match — leading \b, NO trailing boundary.
            # Catches plurals, conjugations, AND _-suffixed identifiers.
            parts.append(rf"\b{re.escape(kw)}")

    if not parts:
        return re.compile(r"(?!)")

    pattern = "(?:" + "|".join(parts) + ")"
    return re.compile(pattern, re.IGNORECASE)


def _clamp_confidence(value: Any) -> float:
    """Clamp a value to a valid float in [0.0, 1.0]. NaN/None/non-numeric -> 0.0.

    Args:
        value: Anything the LLM might return. Strings are coerced.

    Returns:
        Float in [0.0, 1.0].
    """
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(f) or math.isinf(f):
        return 0.0
    if f < 0.0:
        return 0.0
    if f > 1.0:
        return 1.0
    return f


def _coerce_intent(value: Any) -> Optional[str]:
    """Coerce a value to one of the 9 valid LLM intent strings, or None.

    Args:
        value: Anything the LLM might return.

    Returns:
        One of the 9 valid intent strings, or None if unrecognized.
    """
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in _VALID_LLM_INTENTS:
        return normalized
    return None


def _parse_llm_json(response: Optional[str]) -> Optional[Dict[str, Any]]:
    """Parse LLM JSON response, tolerating markdown fences and extra whitespace.

    Args:
        response: Raw LLM response text, or None.

    Returns:
        Parsed dict, or None if unparseable.
    """
    if response is None:
        return None
    text = response.strip()
    if not text:
        return None

    # Strip markdown code fences if present (defensive — prompt asks for none).
    if text.startswith("```"):
        # Remove opening fence (```json, ```JSON, ```)
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
        # Remove trailing fence
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()

    # Extract first {...} block in case there's prose around it.
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace == -1 or last_brace == -1 or last_brace < first_brace:
        return None
    candidate = text[first_brace : last_brace + 1]

    try:
        parsed = json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        return None

    if not isinstance(parsed, dict):
        return None
    return parsed


def _append_telemetry(
    log_dir: Path,
    *,
    timestamp: str,
    intent: str,
    confidence: float,
    regex_hit: bool,
    llm_used: bool,
    fail_open: bool,
    decision: str,
    prompt_length: int,
    predicted_file_count: int,
) -> None:
    """Append one JSONL telemetry line. NEVER raises.

    Args:
        log_dir: Directory to write the log file (created if missing).
        timestamp: ISO 8601 UTC timestamp.
        intent: Intent class value string.
        confidence: Confidence in [0.0, 1.0].
        regex_hit: True if security regex matched.
        llm_used: True if the LLM was called.
        fail_open: True if a failure path was hit.
        decision: "regex"|"llm"|"fail_open"|"unavailable".
        prompt_length: Original prompt length.
        predicted_file_count: Predicted file count.
    """
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_path = log_dir / f"{date_str}.jsonl"
        entry = {
            "timestamp": timestamp,
            "hook": "intent_classifier",
            "intent": intent,
            "confidence": confidence,
            "regex_hit": regex_hit,
            "llm_used": llm_used,
            "fail_open": fail_open,
            "decision": decision,
            "prompt_length": prompt_length,
            "predicted_file_count": predicted_file_count,
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except Exception:  # noqa: BLE001 — telemetry MUST never raise
        # Silent: telemetry failures must not block the classifier.
        pass


# ============================================================================
# Main classifier
# ============================================================================


@dataclass
class IntentClassifier:
    """Semantic intent classifier with regex-first security detection.

    Phase 1 contract:
        - classify() returns IntentResult; never raises.
        - SECURITY_CRITICAL is decided by regex BEFORE the LLM (defense in depth).
        - All other intents go through the LLM (if available).
        - Any failure -> AMBIGUOUS + fail_open=True + requires_security_audit=True.

    Construct via from_config() or directly. Direct construction is mostly for
    testing — production callers should use from_config(_DEFAULT_CONFIG_PATH).
    """

    model: str = DEFAULT_MODEL
    max_tokens: int = DEFAULT_MAX_TOKENS
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    max_prompt_chars: int = DEFAULT_MAX_PROMPT_CHARS
    security_keywords: List[str] = field(
        default_factory=lambda: list(_DEFAULT_SECURITY_KEYWORDS)
    )
    telemetry_log_dir: Path = field(
        default_factory=lambda: Path(os.getcwd()) / ".claude" / "logs" / "activity"
    )
    telemetry_enabled: bool = True

    # Internal: built lazily on first classify() call.
    _security_regex: Optional["re.Pattern[str]"] = field(default=None, init=False, repr=False)
    _analyzer: Optional[Any] = field(default=None, init=False, repr=False)

    @classmethod
    def from_config(cls, config_path: Optional[Path] = None) -> "IntentClassifier":
        """Load config from JSON file. Missing or malformed -> defaults.

        Args:
            config_path: Path to config JSON. Defaults to bundled config.

        Returns:
            IntentClassifier instance.
        """
        path = config_path if config_path is not None else _DEFAULT_CONFIG_PATH
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, dict):
                raise ValueError("Config root must be an object")
        except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError) as exc:
            logger.debug("intent_classifier: using defaults (%s)", exc)
            return cls()

        telemetry_cfg = raw.get("telemetry", {})
        if not isinstance(telemetry_cfg, dict):
            telemetry_cfg = {}

        log_dir_str = telemetry_cfg.get("log_dir", ".claude/logs/activity")
        if not isinstance(log_dir_str, str) or not log_dir_str:
            log_dir_str = ".claude/logs/activity"
        log_dir = Path(os.getcwd()) / log_dir_str

        keywords = raw.get("security_keywords", _DEFAULT_SECURITY_KEYWORDS)
        if not isinstance(keywords, list) or not keywords:
            keywords = list(_DEFAULT_SECURITY_KEYWORDS)
        keywords = [str(k) for k in keywords if isinstance(k, str)]
        if not keywords:
            keywords = list(_DEFAULT_SECURITY_KEYWORDS)

        return cls(
            model=str(raw.get("model", DEFAULT_MODEL)),
            max_tokens=int(raw.get("max_tokens", DEFAULT_MAX_TOKENS)),
            timeout_seconds=int(raw.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)),
            confidence_threshold=float(
                raw.get("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD)
            ),
            max_prompt_chars=int(raw.get("max_prompt_chars", DEFAULT_MAX_PROMPT_CHARS)),
            security_keywords=keywords,
            telemetry_log_dir=log_dir,
            telemetry_enabled=bool(telemetry_cfg.get("enabled", True)),
        )

    def _get_regex(self) -> "re.Pattern[str]":
        """Lazily build and cache the security keyword regex."""
        if self._security_regex is None:
            self._security_regex = _build_security_regex(self.security_keywords)
        return self._security_regex

    def _get_analyzer(self) -> Optional[Any]:
        """Lazily build the GenAIAnalyzer. Returns None if SDK unavailable."""
        if not _GENAI_AVAILABLE or GenAIAnalyzer is None:
            return None
        if self._analyzer is None:
            try:
                self._analyzer = GenAIAnalyzer(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    timeout=self.timeout_seconds,
                )
            except Exception:  # noqa: BLE001
                self._analyzer = None
        return self._analyzer

    def classify(self, prompt: Optional[str]) -> IntentResult:
        """Classify a user prompt. NEVER raises.

        Order of operations:
            1. Sanitize input (None/whitespace -> AMBIGUOUS fail-open).
            2. Run security regex. Match -> SECURITY_CRITICAL (LLM not called).
            3. If LLM unavailable -> AMBIGUOUS fail-open.
            4. Call LLM, parse JSON.
            5. Validate intent in enum + confidence >= threshold.
            6. Any failure in 4-5 -> AMBIGUOUS fail-open.

        Args:
            prompt: User prompt text (may be None or empty).

        Returns:
            IntentResult. requires_security_audit is True for SECURITY_CRITICAL
            and AMBIGUOUS results.
        """
        # Single top-level try/except so this method never raises.
        try:
            return self._classify_inner(prompt)
        except Exception as exc:  # noqa: BLE001
            logger.debug("intent_classifier: top-level exception, fail-open: %s", exc)
            return self._fail_open(
                prompt_length=len(prompt) if isinstance(prompt, str) else 0,
                decision="fail_open",
            )

    def _classify_inner(self, prompt: Optional[str]) -> IntentResult:
        """Inner classification logic. May raise; classify() catches all."""
        # ---- 1. Sanitize input ----
        if prompt is None:
            return self._fail_open(prompt_length=0, decision="fail_open")
        if not isinstance(prompt, str):
            return self._fail_open(prompt_length=0, decision="fail_open")

        stripped = prompt.strip()
        if not stripped:
            return self._fail_open(prompt_length=0, decision="fail_open")

        prompt_length = len(stripped)
        truncated = _truncate(stripped, self.max_prompt_chars)

        # ---- 2. Regex BEFORE LLM (security gate) ----
        regex = self._get_regex()
        if regex.search(truncated):
            result = IntentResult(
                intent=IntentClass.SECURITY_CRITICAL,
                confidence=1.0,
                regex_hit=True,
                llm_used=False,
                fail_open=False,
                requires_security_audit=True,
                prompt_length=prompt_length,
                predicted_file_count=1,
                reasoning="security keyword regex hit",
            )
            self._emit_telemetry(result, decision="regex")
            return result

        # ---- 3. LLM availability ----
        analyzer = self._get_analyzer()
        if analyzer is None:
            return self._fail_open(
                prompt_length=prompt_length, decision="unavailable"
            )

        # ---- 4. Call LLM ----
        try:
            response = analyzer.analyze(_LLM_PROMPT_TEMPLATE, prompt=truncated)
        except Exception as exc:  # noqa: BLE001
            logger.debug("intent_classifier: analyzer raised, fail-open: %s", exc)
            return self._fail_open(
                prompt_length=prompt_length, decision="fail_open"
            )

        if response is None:
            # SDK signaled timeout/error.
            return self._fail_open(
                prompt_length=prompt_length, decision="fail_open"
            )

        parsed = _parse_llm_json(response)
        if parsed is None:
            return self._fail_open(
                prompt_length=prompt_length, decision="fail_open"
            )

        # ---- 5. Validate ----
        intent_str = _coerce_intent(parsed.get("intent"))
        if intent_str is None:
            return self._fail_open(
                prompt_length=prompt_length, decision="fail_open"
            )

        confidence = _clamp_confidence(parsed.get("confidence"))
        if confidence < self.confidence_threshold:
            # Low confidence -> fail-open (preserves security audit requirement).
            return self._fail_open(
                prompt_length=prompt_length, decision="fail_open"
            )

        try:
            file_count_raw = parsed.get("predicted_file_count", 1)
            file_count = int(file_count_raw)
            if file_count < 1:
                file_count = 1
            if file_count > 50:
                file_count = 50
        except (TypeError, ValueError):
            file_count = 1

        reasoning_raw = parsed.get("reasoning", "")
        reasoning = str(reasoning_raw)[:200] if reasoning_raw is not None else ""

        intent = IntentClass(intent_str)
        # Even when LLM returns SECURITY_CRITICAL via prompt-following, mark
        # requires_security_audit=True (defense in depth).
        requires_audit = intent == IntentClass.SECURITY_CRITICAL

        result = IntentResult(
            intent=intent,
            confidence=confidence,
            regex_hit=False,
            llm_used=True,
            fail_open=False,
            requires_security_audit=requires_audit,
            prompt_length=prompt_length,
            predicted_file_count=file_count,
            reasoning=reasoning,
        )
        self._emit_telemetry(result, decision="llm")
        return result

    def _fail_open(self, *, prompt_length: int, decision: str) -> IntentResult:
        """Build the canonical fail-open IntentResult and emit telemetry."""
        result = IntentResult(
            intent=IntentClass.AMBIGUOUS,
            confidence=0.0,
            regex_hit=False,
            llm_used=False,
            fail_open=True,
            requires_security_audit=True,
            prompt_length=prompt_length,
            predicted_file_count=1,
            reasoning="fail-open: classification unavailable or low-confidence",
        )
        self._emit_telemetry(result, decision=decision)
        return result

    def _emit_telemetry(self, result: IntentResult, *, decision: str) -> None:
        """Emit one telemetry line if enabled. NEVER raises."""
        if not self.telemetry_enabled:
            return
        timestamp = datetime.now(timezone.utc).isoformat()
        _append_telemetry(
            self.telemetry_log_dir,
            timestamp=timestamp,
            intent=result.intent.value,
            confidence=result.confidence,
            regex_hit=result.regex_hit,
            llm_used=result.llm_used,
            fail_open=result.fail_open,
            decision=decision,
            prompt_length=result.prompt_length,
            predicted_file_count=result.predicted_file_count,
        )


# ============================================================================
# Module-level convenience
# ============================================================================


def classify_prompt(prompt: Optional[str]) -> IntentResult:
    """One-shot classification using the bundled config. NEVER raises.

    For most callers; production hooks should cache the classifier instance.

    Args:
        prompt: User prompt to classify.

    Returns:
        IntentResult.
    """
    try:
        classifier = IntentClassifier.from_config()
    except Exception:  # noqa: BLE001
        classifier = IntentClassifier()
    return classifier.classify(prompt)
