#!/usr/bin/env python3
"""Extract real user prompts from session archive and label them with a single judge.

Pulls first_user_prompt values from ~/.claude/archive/sessions.db (all projects,
last 30 days), applies PII scrubbing, dedup, and length filtering, then uses a
single LLM-as-judge invoked via ``claude -p`` (subprocess) to label each prompt
with one of the 13 intent classes. Authentication uses the user's existing
Claude Code subscription session — no API keys are required.

ANTHROPIC_API_KEY/OPENROUTER_API_KEY are NOT used. Auth comes from
your existing ``claude`` CLI session (run ``claude /login`` once).

Usage::

    # Synthetic-fallback (no claude CLI required)
    python scripts/extract_and_label_intent_corpus.py \\
        --output tests/fixtures/intent_classifier_real_corpus.json \\
        --dry-run

    # Real labeling (requires `claude` on PATH and a logged-in session)
    python scripts/extract_and_label_intent_corpus.py \\
        --output tests/fixtures/intent_classifier_real_corpus.json \\
        --max-prompts 150

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
import shutil
import sqlite3
import subprocess
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
_COST_PER_CALL_USD = 0.005  # $0.005 per call (single judge ~ $0.005 per prompt)

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
            "judge": "synthetic-fallback",
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
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-doc-002",
            "prompt": "Write docstrings for all public functions in utils.py",
            "label": "doc",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-doc-003",
            "prompt": "Add a CHANGELOG entry describing the new features in this release",
            "label": "doc",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-cfg-001",
            "prompt": "Update the pyproject.toml to pin the numpy version to 1.26",
            "label": "config",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-cfg-002",
            "prompt": "Add the REDIS_URL environment variable to the .env.example file",
            "label": "config",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-typo-001",
            "prompt": "Fix the misspelling of 'recieved' in the error message string",
            "label": "typo",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-typo-002",
            "prompt": "Correct 'teh' to 'the' in the help text output",
            "label": "typo",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-status-001",
            "prompt": "What tests are currently failing in CI?",
            "label": "status_query",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-status-002",
            "prompt": "Show me the git log for the last 5 commits",
            "label": "status_query",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-conv-001",
            "prompt": "What are the tradeoffs between using Redis and Memcached for caching?",
            "label": "conversation",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-conv-002",
            "prompt": "Should we adopt GraphQL or stick with REST for the new API?",
            "label": "conversation",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-expl-001",
            "prompt": "Investigate how the session lifecycle is managed across hooks and lib modules",
            "label": "exploration",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-expl-002",
            "prompt": "Trace how environment variables flow from the CI config into hook execution",
            "label": "exploration",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-triage-001",
            "prompt": "List all open issues labeled 'bug' and group them by component",
            "label": "triage",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-triage-002",
            "prompt": "Review the last 10 closed issues and identify patterns in the defects",
            "label": "triage",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-remote-001",
            "prompt": "Check disk usage on the remote training server and report available space",
            "label": "remote_ops",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-remote-002",
            "prompt": "Sync the latest model checkpoints from the remote box to the local storage",
            "label": "remote_ops",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-scratch-001",
            "prompt": "Write a quick throwaway script in /tmp to compare two JSON files",
            "label": "scratch",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-scratch-002",
            "prompt": "Create a one-off notebook in /tmp/ to visualize the training loss curve",
            "label": "scratch",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-impl-001",
            "prompt": "Add a new endpoint to export user data as a CSV file",
            "label": "implement",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-impl-002",
            "prompt": "Build a background job to send weekly digest emails to subscribers",
            "label": "implement",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-ref-001",
            "prompt": "Refactor the large report_generator.py by splitting it into smaller modules",
            "label": "refactor",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-ref-002",
            "prompt": "Clean up dead code in the legacy payment handler",
            "label": "refactor",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-test-001",
            "prompt": "Write integration tests for the new webhook receiver endpoint",
            "label": "test",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-test-002",
            "prompt": "Fix the flaky end-to-end test that fails intermittently in CI",
            "label": "test",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-sec-001",
            "prompt": "Implement rate limiting on the login endpoint to prevent brute force",
            "label": "security_critical",
            "source": "synthetic",
            "judge": "synthetic-fallback",
            "redactions_applied": [],
            "holdout": False,
        },
        {
            "id": "synth-extra-sec-002",
            "prompt": "Audit the RBAC permissions for the admin API endpoints",
            "label": "security_critical",
            "source": "synthetic",
            "judge": "synthetic-fallback",
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


def _call_claude_p_judge(
    prompt: str,
    *,
    model: str,
    timeout_sec: int = 60,
) -> Optional[Dict[str, Any]]:
    """Call ``claude -p`` for intent classification.

    Uses the user's existing Claude Code subscription auth (no API key
    needed). Returns None on any failure (timeout, parse error, invalid
    intent class, missing CLI).

    Args:
        prompt: The user prompt to classify (already PII-scrubbed).
        model: Anthropic model identifier passed to ``--model``.
        timeout_sec: Subprocess timeout in seconds.

    Returns:
        Dict with 'intent' and 'confidence' or None on failure.
    """
    user_message = _JUDGE_USER_TEMPLATE.format(
        prompt=html.escape(prompt, quote=False)
    )
    cmd = [
        "claude",
        "-p",
        "--output-format", "json",
        "--model", model,
        "--max-turns", "1",
        "--system-prompt", _JUDGE_SYSTEM_PROMPT,
    ]
    try:
        result = subprocess.run(
            cmd,
            input=user_message,
            text=True,
            capture_output=True,
            timeout=timeout_sec,
            check=False,
            cwd=str(Path.home()),  # avoid loading project CLAUDE.md/hooks in nested session (#1064)
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    try:
        envelope = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if envelope.get("is_error") or envelope.get("subtype") != "success":
        return None
    raw = envelope.get("result")
    if not isinstance(raw, str):
        return None
    try:
        parsed = json.loads(raw.strip())
    except json.JSONDecodeError:
        return None
    intent = parsed.get("intent")
    if intent not in VALID_INTENT_CLASSES:
        return None
    try:
        confidence = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        return None
    if not (0.0 <= confidence <= 1.0):
        return None
    return {"intent": intent, "confidence": confidence}


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
# Single-judge labeling
# ---------------------------------------------------------------------------

def label_prompts_with_single_judge(
    prompts: List[str],
    *,
    judge_model: str,
    cost_tracker: CostTracker,
    confidence_threshold: float = 0.70,
    dry_run: bool = False,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Label prompts using a single LLM judge invoked via ``claude -p``.

    Runs the judge on each prompt. Entries are kept when the judge returns a
    valid intent class with confidence >= ``confidence_threshold``.

    Args:
        prompts: List of pre-scrubbed prompts to label
        judge_model: Anthropic model ID passed to ``claude -p --model``
        cost_tracker: CostTracker to enforce spend cap
        confidence_threshold: Minimum confidence to accept
        dry_run: If True, skip all subprocess calls

    Returns:
        Tuple of (agreed_entries, drop_counts) where drop_counts maps a drop
        reason ("judge_failure", "low_confidence", "invalid_intent") to count.
    """
    agreed: List[Dict[str, Any]] = []
    drop_counts: Dict[str, int] = {}
    entry_id = 0

    for prompt in prompts:
        if cost_tracker.would_exceed_cap(additional_calls=1):
            print(
                f"WARNING: Cost cap ${COST_CAP_USD:.2f} would be exceeded. "
                "Stopping early.",
                file=sys.stderr,
            )
            break

        if dry_run:
            # In dry run, simulate a judge response with a placeholder label
            agreed.append(
                {
                    "id": f"real-{entry_id:04d}",
                    "prompt": prompt,
                    "label": "conversation",  # dry-run placeholder
                    "source": "sqlite",
                    "judge": judge_model,
                    "redactions_applied": [],
                    "holdout": False,
                }
            )
            entry_id += 1
            continue

        result = _call_claude_p_judge(prompt, model=judge_model)
        cost_tracker.record_calls(1)

        # Drop if judge failed entirely (subprocess error, parse error, invalid intent)
        if result is None:
            drop_counts["judge_failure"] = drop_counts.get("judge_failure", 0) + 1
            continue

        # Drop if low confidence
        if result["confidence"] < confidence_threshold:
            drop_counts["low_confidence"] = drop_counts.get("low_confidence", 0) + 1
            continue

        # Defense-in-depth — should already be filtered by _call_claude_p_judge
        if result["intent"] not in VALID_INTENT_CLASSES:
            drop_counts["invalid_intent"] = drop_counts.get("invalid_intent", 0) + 1
            continue

        # Accept entry
        agreed.append(
            {
                "id": f"real-{entry_id:04d}",
                "prompt": prompt,
                "label": result["intent"],
                "source": "sqlite",
                "judge": judge_model,
                "redactions_applied": [],
                "holdout": False,
            }
        )
        entry_id += 1

    return agreed, drop_counts


# ---------------------------------------------------------------------------
# Corpus builder (combines extraction + labeling + fallback)
# ---------------------------------------------------------------------------

def build_corpus(
    db_path: Path,
    *,
    max_prompts: int = 150,
    judge_model: str = "claude-haiku-4-5-20251001",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Build the full intent classification corpus.

    Extracts from DB, scrubs PII, filters, and labels using ``claude -p``.
    Falls back to synthetic corpus when the ``claude`` CLI is not on PATH.

    Args:
        db_path: Path to sessions.db
        max_prompts: Target number of labeled entries
        judge_model: Anthropic model ID passed to ``claude -p --model``
        dry_run: If True, skip subprocess calls (produces placeholder labels)

    Returns:
        Corpus dict ready for JSON serialization
    """
    has_claude_cli = shutil.which("claude") is not None
    use_real_judge = has_claude_cli and not dry_run
    if use_real_judge:
        methodology = "single-judge via claude -p (Anthropic subscription auth)"
    elif dry_run:
        methodology = "dry-run placeholder (no real labeling)"
    else:
        methodology = "synthetic-fallback (claude CLI unavailable)"

    if not use_real_judge and not dry_run:
        print(
            "INFO: claude CLI not on PATH. Using synthetic-fallback corpus from existing fixtures.",
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

    labeled_entries, drop_counts = label_prompts_with_single_judge(
        filtered,
        judge_model=judge_model,
        cost_tracker=cost_tracker,
        dry_run=dry_run,
    )

    # Attach redaction metadata
    for entry in labeled_entries:
        entry["redactions_applied"] = redaction_map.get(entry["prompt"], [])

    # Print drop summary to stdout (not committed to file)
    if drop_counts:
        print("\n--- Drop summary ---")
        total_drops = sum(drop_counts.values())
        print(f"Total drops: {total_drops}")
        for reason, count in sorted(drop_counts.items(), key=lambda x: -x[1]):
            print(f"  {reason}: {count}")
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
        "--judge-model",
        default="claude-haiku-4-5-20251001",
        help="Anthropic model ID passed to `claude -p --model`",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip subprocess calls, write placeholder corpus",
    )
    args = parser.parse_args()

    # Validate paths
    try:
        db_path = validate_path(args.db_path)
    except Exception:
        db_path = args.db_path

    output_path: Path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    corpus = build_corpus(
        db_path,
        max_prompts=args.max_prompts,
        judge_model=args.judge_model,
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
            "Consider re-running with the claude CLI on PATH or augmenting the synthetic corpus.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
