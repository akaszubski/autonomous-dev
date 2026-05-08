#!/usr/bin/env python3
"""Extract real user prompts from session archive and label them with two judges.

Pulls first_user_prompt values from ~/.claude/archive/sessions.db (all projects,
last 30 days), applies PII scrubbing, dedup, and length filtering, then uses
two judges (Anthropic + non-Anthropic via OpenRouter) to label each prompt with
one of the 13 intent classes. Only unanimously-agreed entries are written to the
output corpus file.

Usage:
    python scripts/extract_and_label_intent_corpus.py \\
        --output tests/fixtures/intent_classifier_real_corpus.json \\
        --max-prompts 150 \\
        --dry-run

    # With API keys set:
    ANTHROPIC_API_KEY=... OPENROUTER_API_KEY=... \\
        python scripts/extract_and_label_intent_corpus.py \\
        --output tests/fixtures/intent_classifier_real_corpus.json

GitHub Issue: #1043
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import os
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Path setup — import security_utils from lib
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).parent.resolve()
_PROJECT_ROOT = _SCRIPT_DIR.parent
_LIB_DIR = _PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"
if _LIB_DIR.exists():
    sys.path.insert(0, str(_LIB_DIR))

try:
    from security_utils import validate_path  # type: ignore[import-not-found]
except ImportError:
    # Fallback if security_utils is not available
    def validate_path(path: Path) -> Path:  # type: ignore[misc]
        """Stub validate_path when security_utils is unavailable."""
        return path.resolve()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_INTENT_CLASSES = {
    "security_critical",
    "implement",
    "refactor",
    "test",
    "doc",
    "config",
    "typo",
    "status_query",
    "conversation",
    "exploration",
    "triage",
    "remote_ops",
    "scratch",
}

MIN_PROMPT_LEN = 10
MAX_PROMPT_LEN = 2000
COST_CAP_USD = 0.50

# Rough cost estimates per API call (conservative)
_COST_PER_CALL_USD = 0.005  # $0.005 per call (two judges = $0.01 per prompt)

_DEFAULT_DB_PATH = Path.home() / ".claude" / "archive" / "sessions.db"
_DEFAULT_OUTPUT = _PROJECT_ROOT / "tests" / "fixtures" / "intent_classifier_real_corpus.json"

# ---------------------------------------------------------------------------
# PII scrubbing — 10 pattern types (Issue #1043, plan item 3)
# ---------------------------------------------------------------------------

# 1. Email addresses
_RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

# 2. SSH user@host patterns (e.g. andrewkaszubski@10.55.0.2)
_RE_SSH_USER_AT_HOST = re.compile(r"\b[A-Za-z0-9._\-]+@[\d]{1,3}\.[\d]{1,3}\.[\d]{1,3}\.[\d]{1,3}\b")

# 3. Phone numbers
_RE_PHONE = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")

# 4. UUIDs
_RE_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)

# 5. AWS account IDs (exactly 12 digits, not part of a larger number)
_RE_AWS_ACCOUNT = re.compile(r"(?<!\d)\d{12}(?!\d)")

# 6. JWT tokens (header.payload.signature with base64url segments)
_RE_JWT = re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+")

# 7. Base64 blobs >40 chars
_RE_BASE64 = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")

# 8. <local-command-caveat>...</local-command-caveat> blocks (Claude Code internal markup)
_RE_LOCAL_CAVEAT = re.compile(
    r"<local-command-caveat>.*?</local-command-caveat>", re.DOTALL
)

# 9. Mac Studio internal IPs (10.55.x.x)
_RE_INTERNAL_IP = re.compile(r"\b10\.55\.\d{1,3}\.\d{1,3}\b")

# 10. Generic internal IPv4 (RFC-1918 ranges beyond Mac Studio)
_RE_RFC1918_IP = re.compile(
    r"\b(?:192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3})\b"
)

_PII_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
    (_RE_LOCAL_CAVEAT, "local-command-caveat", "[CAVEAT_BLOCK]"),
    (_RE_JWT, "jwt", "[JWT]"),
    (_RE_UUID, "uuid", "[UUID]"),
    (_RE_BASE64, "base64", "[BASE64]"),
    (_RE_SSH_USER_AT_HOST, "ssh_user_at_host", "[USER@HOST]"),
    (_RE_INTERNAL_IP, "internal_ip", "[INTERNAL_IP]"),
    (_RE_RFC1918_IP, "rfc1918_ip", "[INTERNAL_IP]"),
    (_RE_EMAIL, "email", "[EMAIL]"),
    (_RE_PHONE, "phone", "[PHONE]"),
    (_RE_AWS_ACCOUNT, "aws_account", "[AWS_ACCOUNT]"),
]


def scrub_pii(text: str) -> Tuple[str, List[str]]:
    """Remove PII from text, returning the cleaned text and list of redaction types applied.

    Args:
        text: Raw prompt text potentially containing PII

    Returns:
        Tuple of (scrubbed_text, list_of_redaction_type_names)
    """
    redactions: List[str] = []
    for pattern, pattern_name, replacement in _PII_PATTERNS:
        new_text, n = pattern.subn(replacement, text)
        if n > 0:
            redactions.append(pattern_name)
            text = new_text
    return text, redactions


# ---------------------------------------------------------------------------
# Prompt dedup + length filtering
# ---------------------------------------------------------------------------

def _prompt_fingerprint(text: str) -> str:
    """Generate a dedup fingerprint for a prompt.

    Uses lowercase-stripped SHA-256 prefix so near-duplicates with different
    casing or trailing whitespace collapse.

    Args:
        text: Prompt text

    Returns:
        16-char hex fingerprint
    """
    return hashlib.sha256(text.lower().strip().encode()).hexdigest()[:16]


def filter_and_dedup(prompts: List[str]) -> List[str]:
    """Apply length filter and deduplication to a list of prompts.

    Args:
        prompts: Raw list of prompt strings

    Returns:
        Filtered and deduplicated list
    """
    seen: set = set()
    result: List[str] = []
    for p in prompts:
        if not isinstance(p, str):
            continue
        p = p.strip()
        if not (MIN_PROMPT_LEN <= len(p) <= MAX_PROMPT_LEN):
            continue
        fp = _prompt_fingerprint(p)
        if fp in seen:
            continue
        seen.add(fp)
        result.append(p)
    return result


# ---------------------------------------------------------------------------
# SQLite extraction
# ---------------------------------------------------------------------------

def extract_prompts_from_db(
    db_path: Path,
    *,
    days: int = 30,
    max_prompts: int = 200,
) -> List[str]:
    """Pull first_user_prompt values from sessions.db.

    Queries all projects, last N days. Returns raw (un-scrubbed) prompts.

    Args:
        db_path: Path to sessions.db
        days: Look-back window in days
        max_prompts: Maximum number of prompts to return (pre-filter)

    Returns:
        List of raw prompt strings
    """
    if not db_path.exists():
        return []

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT first_user_prompt
            FROM sessions
            WHERE last_updated > datetime('now', ?)
              AND first_user_prompt IS NOT NULL
              AND length(first_user_prompt) > ?
              AND length(first_user_prompt) <= ?
            ORDER BY last_updated DESC
            LIMIT ?
            """,
            (f"-{days} days", MIN_PROMPT_LEN, MAX_PROMPT_LEN * 3, max_prompts * 3),
        )
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows if row[0]]
    except sqlite3.Error as e:
        print(f"WARNING: SQLite error reading {db_path}: {e}", file=sys.stderr)
        return []


# ---------------------------------------------------------------------------
# Synthetic fallback corpus builder
# ---------------------------------------------------------------------------

def _build_synthetic_fallback_corpus() -> List[Dict[str, Any]]:
    """Build synthetic corpus from existing fixtures when no API key is available.

    Returns:
        List of corpus entry dicts
    """
    fixtures_path = _PROJECT_ROOT / "tests" / "fixtures" / "intent_classifier_fixtures.json"
    if not fixtures_path.exists():
        return []

    try:
        data = json.loads(fixtures_path.read_text())
        fixtures = data.get("fixtures", [])
    except (json.JSONDecodeError, OSError):
        return []

    entries: List[Dict[str, Any]] = []
    for i, fx in enumerate(fixtures):
        prompt = fx.get("prompt", "")
        label = fx.get("label", "")
        if not prompt or label not in VALID_INTENT_CLASSES:
            continue
        # Apply PII scrubbing even to synthetic prompts — some contain real IPs/emails
        scrubbed_prompt, redactions = scrub_pii(prompt)
        entry: Dict[str, Any] = {
            "id": f"synthetic-{i:04d}",
            "prompt": scrubbed_prompt,
            "label": label,
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": redactions,
            "holdout": fx.get("holdout", False),
        }
        entries.append(entry)

    # Extend with curated non-SWE prompts to ensure coverage of all 13 classes
    extra_entries: List[Dict[str, Any]] = [
        {
            "id": "synth-extra-doc-001",
            "prompt": "Update the project README with usage examples for the new CLI",
            "label": "doc",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-doc-002",
            "prompt": "Write docstrings for all public functions in utils.py",
            "label": "doc",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-doc-003",
            "prompt": "Add a CHANGELOG entry describing the new features in this release",
            "label": "doc",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-cfg-001",
            "prompt": "Update the pyproject.toml to pin the numpy version to 1.26",
            "label": "config",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-cfg-002",
            "prompt": "Add the REDIS_URL environment variable to the .env.example file",
            "label": "config",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-typo-001",
            "prompt": "Fix the misspelling of 'recieved' in the error message string",
            "label": "typo",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-typo-002",
            "prompt": "Correct 'teh' to 'the' in the help text output",
            "label": "typo",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-status-001",
            "prompt": "What tests are currently failing in CI?",
            "label": "status_query",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-status-002",
            "prompt": "Show me the git log for the last 5 commits",
            "label": "status_query",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-conv-001",
            "prompt": "What are the tradeoffs between using Redis and Memcached for caching?",
            "label": "conversation",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-conv-002",
            "prompt": "Should we adopt GraphQL or stick with REST for the new API?",
            "label": "conversation",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-expl-001",
            "prompt": "Investigate how the session lifecycle is managed across hooks and lib modules",
            "label": "exploration",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-expl-002",
            "prompt": "Trace how environment variables flow from the CI config into hook execution",
            "label": "exploration",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-triage-001",
            "prompt": "List all open issues labeled 'bug' and group them by component",
            "label": "triage",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-triage-002",
            "prompt": "Review the last 10 closed issues and identify patterns in the defects",
            "label": "triage",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-remote-001",
            "prompt": "Check disk usage on the remote training server and report available space",
            "label": "remote_ops",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-remote-002",
            "prompt": "Sync the latest model checkpoints from the remote box to the local storage",
            "label": "remote_ops",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-scratch-001",
            "prompt": "Write a quick throwaway script in /tmp to compare two JSON files",
            "label": "scratch",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-scratch-002",
            "prompt": "Create a one-off notebook in /tmp/ to visualize the training loss curve",
            "label": "scratch",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-impl-001",
            "prompt": "Add a new endpoint to export user data as a CSV file",
            "label": "implement",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-impl-002",
            "prompt": "Build a background job to send weekly digest emails to subscribers",
            "label": "implement",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-ref-001",
            "prompt": "Refactor the large report_generator.py by splitting it into smaller modules",
            "label": "refactor",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-ref-002",
            "prompt": "Clean up dead code in the legacy payment handler",
            "label": "refactor",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-test-001",
            "prompt": "Write integration tests for the new webhook receiver endpoint",
            "label": "test",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-test-002",
            "prompt": "Fix the flaky end-to-end test that fails intermittently in CI",
            "label": "test",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-sec-001",
            "prompt": "Implement rate limiting on the login endpoint to prevent brute force",
            "label": "security_critical",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-sec-002",
            "prompt": "Audit the RBAC permissions for the admin API endpoints",
            "label": "security_critical",
            "source": "synthetic",
            "judge_a": "synthetic-fallback",
            "judge_b": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
    ]

    # Apply PII scrubbing to extra entries as well
    scrubbed_extras: List[Dict[str, Any]] = []
    for entry in extra_entries:
        scrubbed_prompt, redactions = scrub_pii(entry["prompt"])
        scrubbed_extras.append({**entry, "prompt": scrubbed_prompt, "redactions_applied": redactions})

    entries.extend(scrubbed_extras)
    return entries


# ---------------------------------------------------------------------------
# LLM judge: system prompt
# ---------------------------------------------------------------------------

_JUDGE_SYSTEM_PROMPT = """You are an intent classifier for a software development CLI tool.
Your job is to classify user prompts into exactly one of 13 intent classes.

The 13 classes are:
- security_critical: auth, crypto, secrets, migrations, RBAC, vulnerabilities
- implement: building new features, APIs, or capabilities
- refactor: restructuring without behavior change (rename, extract, split, clean up)
- test: writing or fixing tests, improving coverage
- doc: documentation, README, docstrings, CHANGELOG
- config: settings files (.json/.yaml/.toml/.env), feature flags, CI config
- typo: trivial single-word/character fixes in text (not code logic)
- status_query: read-only factual questions (what is the status, show me X)
- conversation: discussion, brainstorming, opinions, architectural questions
- exploration: multi-file read-only investigation across 3+ files
- triage: GitHub issue review or prioritization without code changes
- remote_ops: SSH/rsync/scp work on remote hosts
- scratch: throwaway work in /tmp/, scripts/scratch/, or .worktrees/scratch-*

Respond with ONLY valid JSON in this exact format:
{"intent": "<one of the 13 class names>", "confidence": <float 0.0-1.0>}

Do not include any other text. The intent must be exactly one of the 13 class names listed above.
"""

_JUDGE_USER_TEMPLATE = """Classify this user prompt:
<prompt>{prompt}</prompt>

Respond with only: {{"intent": "...", "confidence": 0.0}}"""


def _call_anthropic_judge(
    prompt: str,
    *,
    model: str,
    api_key: str,
) -> Optional[Dict[str, Any]]:
    """Call Anthropic API for intent classification.

    Args:
        prompt: The user prompt to classify
        model: Anthropic model identifier
        api_key: Anthropic API key

    Returns:
        Dict with 'intent' and 'confidence' or None on failure
    """
    try:
        from anthropic import Anthropic
    except ImportError:
        return None

    client = Anthropic(api_key=api_key)
    try:
        user_content = _JUDGE_USER_TEMPLATE.format(
            prompt=html.escape(prompt, quote=False)
        )
        message = client.messages.create(
            model=model,
            max_tokens=100,
            system=_JUDGE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        raw = message.content[0].text.strip()
        result = json.loads(raw)
        if result.get("intent") not in VALID_INTENT_CLASSES:
            return None
        confidence = float(result.get("confidence", 0.0))
        if not (0.0 <= confidence <= 1.0):
            return None
        return {"intent": result["intent"], "confidence": confidence}
    except Exception:
        return None


def _call_openrouter_judge(
    prompt: str,
    *,
    model: str,
    api_key: str,
) -> Optional[Dict[str, Any]]:
    """Call OpenRouter API for intent classification.

    Args:
        prompt: The user prompt to classify
        model: OpenRouter model identifier (e.g. openai/gpt-4o-mini)
        api_key: OpenRouter API key

    Returns:
        Dict with 'intent' and 'confidence' or None on failure
    """
    try:
        import urllib.request
        import urllib.error
    except ImportError:
        return None

    user_content = _JUDGE_USER_TEMPLATE.format(
        prompt=html.escape(prompt, quote=False)
    )
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": 100,
            "temperature": 0,
        }
    ).encode()

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/autonomous-dev",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        raw = data["choices"][0]["message"]["content"].strip()
        result = json.loads(raw)
        if result.get("intent") not in VALID_INTENT_CLASSES:
            return None
        confidence = float(result.get("confidence", 0.0))
        if not (0.0 <= confidence <= 1.0):
            return None
        return {"intent": result["intent"], "confidence": confidence}
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Cost tracking
# ---------------------------------------------------------------------------

class CostTracker:
    """Track estimated LLM API cost and enforce hard cap.

    Args:
        cap_usd: Maximum spend in USD before hard stop
        cost_per_call_usd: Estimated cost per individual API call
    """

    def __init__(self, cap_usd: float = COST_CAP_USD, cost_per_call_usd: float = _COST_PER_CALL_USD) -> None:
        self._cap = cap_usd
        self._cost_per_call = cost_per_call_usd
        self._total_calls = 0
        self._estimated_cost = 0.0

    def would_exceed_cap(self, additional_calls: int = 2) -> bool:
        """Check if making additional_calls more API calls would exceed the cap.

        Args:
            additional_calls: Number of planned upcoming calls

        Returns:
            True if cap would be exceeded
        """
        projected = self._estimated_cost + additional_calls * self._cost_per_call
        return projected > self._cap

    def record_calls(self, n: int = 1) -> None:
        """Record that n API calls were made.

        Args:
            n: Number of calls completed
        """
        self._total_calls += n
        self._estimated_cost += n * self._cost_per_call

    @property
    def total_calls(self) -> int:
        """Total number of API calls made."""
        return self._total_calls

    @property
    def estimated_cost_usd(self) -> float:
        """Estimated total cost in USD."""
        return self._estimated_cost


# ---------------------------------------------------------------------------
# Two-judge labeling
# ---------------------------------------------------------------------------

def label_prompts_with_two_judges(
    prompts: List[str],
    *,
    judge_a_model: str,
    judge_b_model: str,
    anthropic_api_key: str,
    openrouter_api_key: str,
    cost_tracker: CostTracker,
    confidence_threshold: float = 0.70,
    dry_run: bool = False,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Label prompts using two independent judges.

    Runs judge A (Anthropic) and judge B (OpenRouter/non-Anthropic) on each
    prompt. Only entries where both judges agree on the intent AND both
    report confidence >= threshold are kept.

    Args:
        prompts: List of pre-scrubbed prompts to label
        judge_a_model: Anthropic model ID for judge A
        judge_b_model: OpenRouter model ID for judge B
        anthropic_api_key: Anthropic API key
        openrouter_api_key: OpenRouter API key
        cost_tracker: CostTracker to enforce spend cap
        confidence_threshold: Minimum confidence to accept
        dry_run: If True, skip all API calls

    Returns:
        Tuple of (agreed_entries, disagreement_counts)
        where disagreement_counts maps "label_a->label_b" pairs to count
    """
    agreed: List[Dict[str, Any]] = []
    disagreement_counts: Dict[str, int] = {}
    entry_id = 0

    for prompt in prompts:
        if cost_tracker.would_exceed_cap(additional_calls=2):
            print(
                f"WARNING: Cost cap ${COST_CAP_USD:.2f} would be exceeded. "
                "Stopping early.",
                file=sys.stderr,
            )
            break

        if dry_run:
            # In dry run, simulate agreement with a placeholder label
            agreed.append(
                {
                    "id": f"real-{entry_id:04d}",
                    "prompt": prompt,
                    "label": "conversation",  # dry-run placeholder
                    "source": "sqlite",
                    "judge_a": judge_a_model,
                    "judge_b": judge_b_model,
                    "redactions_applied": [],
                    "holdout": False,
                }
            )
            entry_id += 1
            continue

        result_a = _call_anthropic_judge(prompt, model=judge_a_model, api_key=anthropic_api_key)
        result_b = _call_openrouter_judge(prompt, model=judge_b_model, api_key=openrouter_api_key)
        cost_tracker.record_calls(2)

        # Drop if either judge failed entirely
        if result_a is None or result_b is None:
            disagreement_counts["judge_failure->judge_failure"] = (
                disagreement_counts.get("judge_failure->judge_failure", 0) + 1
            )
            continue

        # Drop if low confidence
        if result_a["confidence"] < confidence_threshold:
            disagreement_counts[f"low_conf_a->{result_a['intent']}"] = (
                disagreement_counts.get(f"low_conf_a->{result_a['intent']}", 0) + 1
            )
            continue
        if result_b["confidence"] < confidence_threshold:
            disagreement_counts[f"low_conf_b->{result_b['intent']}"] = (
                disagreement_counts.get(f"low_conf_b->{result_b['intent']}", 0) + 1
            )
            continue

        # Drop if disagreement
        if result_a["intent"] != result_b["intent"]:
            pair = f"{result_a['intent']}->{result_b['intent']}"
            disagreement_counts[pair] = disagreement_counts.get(pair, 0) + 1
            continue

        # Both agree with sufficient confidence — keep
        agreed.append(
            {
                "id": f"real-{entry_id:04d}",
                "prompt": prompt,
                "label": result_a["intent"],
                "source": "sqlite",
                "judge_a": judge_a_model,
                "judge_b": judge_b_model,
                "redactions_applied": [],
                "holdout": False,
            }
        )
        entry_id += 1

    return agreed, disagreement_counts


# ---------------------------------------------------------------------------
# Corpus builder (combines extraction + labeling + fallback)
# ---------------------------------------------------------------------------

def build_corpus(
    db_path: Path,
    *,
    max_prompts: int = 150,
    judge_a_model: str = "claude-haiku-4-5-20251001",
    judge_b_model: str = "openai/gpt-4o-mini",
    anthropic_api_key: str = "",
    openrouter_api_key: str = "",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Build the full intent classification corpus.

    Extracts from DB, scrubs PII, filters, and labels. Falls back to
    synthetic corpus if API keys are unavailable.

    Args:
        db_path: Path to sessions.db
        max_prompts: Target number of labeled entries
        judge_a_model: Anthropic model for judge A
        judge_b_model: OpenRouter model for judge B
        anthropic_api_key: Anthropic API key (empty = no real calls)
        openrouter_api_key: OpenRouter API key (empty = no real calls)
        dry_run: If True, skip API calls (produces placeholder labels)

    Returns:
        Corpus dict ready for JSON serialization
    """
    has_api_keys = bool(anthropic_api_key and openrouter_api_key)
    methodology = (
        "two-judge unanimous agreement (Anthropic + non-Anthropic)"
        if has_api_keys and not dry_run
        else "synthetic-fallback (no API key)"
    )

    if not has_api_keys and not dry_run:
        print(
            "INFO: No API keys set. Using synthetic-fallback corpus from existing fixtures.",
            file=sys.stderr,
        )
        entries = _build_synthetic_fallback_corpus()
        return {
            "_schema_version": 1,
            "_extracted_at": datetime.now(timezone.utc).isoformat(),
            "_methodology": methodology,
            "entries": entries,
        }

    # Real extraction path
    print(f"INFO: Extracting prompts from {db_path}", file=sys.stderr)
    raw_prompts = extract_prompts_from_db(db_path, days=30, max_prompts=max_prompts * 3)
    print(f"INFO: Got {len(raw_prompts)} raw prompts from DB", file=sys.stderr)

    # Scrub PII
    scrubbed_pairs: List[Tuple[str, List[str]]] = []
    for p in raw_prompts:
        scrubbed, redactions = scrub_pii(p)
        scrubbed_pairs.append((scrubbed, redactions))

    # Filter and dedup
    filtered: List[str] = []
    redaction_map: Dict[str, List[str]] = {}
    for scrubbed, redactions in scrubbed_pairs:
        if MIN_PROMPT_LEN <= len(scrubbed.strip()) <= MAX_PROMPT_LEN:
            filtered.append(scrubbed)
            redaction_map[scrubbed] = redactions

    filtered = filter_and_dedup(filtered)
    filtered = filtered[:max_prompts]
    print(f"INFO: {len(filtered)} prompts after dedup+filter", file=sys.stderr)

    cost_tracker = CostTracker(cap_usd=COST_CAP_USD)

    labeled_entries, disagreement_counts = label_prompts_with_two_judges(
        filtered,
        judge_a_model=judge_a_model,
        judge_b_model=judge_b_model,
        anthropic_api_key=anthropic_api_key,
        openrouter_api_key=openrouter_api_key,
        cost_tracker=cost_tracker,
        dry_run=dry_run,
    )

    # Attach redaction metadata
    for entry in labeled_entries:
        entry["redactions_applied"] = redaction_map.get(entry["prompt"], [])

    # Print disagreement summary to stdout (not committed to file)
    if disagreement_counts:
        print("\n--- Disagreement summary ---")
        total_disagreements = sum(disagreement_counts.values())
        print(f"Total disagreements/drops: {total_disagreements}")
        for pair, count in sorted(disagreement_counts.items(), key=lambda x: -x[1]):
            print(f"  {pair}: {count}")
        print("---")

    print(
        f"INFO: Estimated cost: ${cost_tracker.estimated_cost_usd:.4f} "
        f"({cost_tracker.total_calls} API calls)",
        file=sys.stderr,
    )

    return {
        "_schema_version": 1,
        "_extracted_at": datetime.now(timezone.utc).isoformat(),
        "_methodology": methodology,
        "entries": labeled_entries,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point for corpus extraction and labeling."""
    parser = argparse.ArgumentParser(
        description="Extract and label intent classification corpus from session archive"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=_DEFAULT_DB_PATH,
        help="Path to sessions.db (default: ~/.claude/archive/sessions.db)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help="Output corpus JSON path",
    )
    parser.add_argument(
        "--max-prompts",
        type=int,
        default=150,
        help="Target maximum prompts to label (default: 150)",
    )
    parser.add_argument(
        "--judge-a-model",
        default="claude-haiku-4-5-20251001",
        help="Anthropic model for judge A",
    )
    parser.add_argument(
        "--judge-b-model",
        default="openai/gpt-4o-mini",
        help="OpenRouter model for judge B",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip API calls, write placeholder corpus",
    )
    args = parser.parse_args()

    # Validate paths
    try:
        db_path = validate_path(args.db_path)
    except Exception:
        db_path = args.db_path

    output_path: Path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    openrouter_api_key = os.environ.get("OPENROUTER_API_KEY", "")

    corpus = build_corpus(
        db_path,
        max_prompts=args.max_prompts,
        judge_a_model=args.judge_a_model,
        judge_b_model=args.judge_b_model,
        anthropic_api_key=anthropic_api_key,
        openrouter_api_key=openrouter_api_key,
        dry_run=args.dry_run,
    )

    output_path.write_text(json.dumps(corpus, indent=2))
    entry_count = len(corpus.get("entries", []))
    print(f"INFO: Wrote {entry_count} entries to {output_path}", file=sys.stderr)

    class_counts: Counter = Counter(e["label"] for e in corpus.get("entries", []))
    print("\nClass distribution:")
    for cls in sorted(VALID_INTENT_CLASSES):
        print(f"  {cls}: {class_counts.get(cls, 0)}")

    if entry_count < 100:
        print(
            f"WARNING: Only {entry_count} entries — below ≥100 target. "
            "Consider re-running with API keys or augmenting synthetic corpus.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
