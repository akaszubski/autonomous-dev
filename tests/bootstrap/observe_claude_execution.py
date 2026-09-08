"""Frozen, test-only, stdlib-only observer of a controlled Claude execution.

P0-A owns this file (``amendment:178-188``). C0 later binds its exact digest
unchanged (``ladder:398``), which is why it is Python-standard-library-only at
runtime (``ladder:155``) and imports no product module (``amendment:190``).

Three planes, kept disjoint (``ladder:303``):

* ``observation``      raw facts only — argv, environment allowlist, executable
                       identities, settings provenance, pre/post Git state,
                       bounded stream/debug/transcript metadata, hook lifecycle
                       joins, and a recursive pre/post path/digest/mode
                       inventory (``amendment:196-200``).
* ``candidate_claim``  recorded by digest and byte length ONLY. ``reconcile()``
                       never parses it, so a candidate can never supply its own
                       answer (``ladder:282``).
* ``comparison``       one record per member of :data:`DECISION_IDS`, each
                       recomputed from the raw observation.

What this module deliberately cannot do:

* It cannot emit a release state (``amendment:191``). The complete status
  vocabulary is ``OBSERVED`` / ``UNMEASURED`` / ``ERROR``; there is no
  pass, candidate, promotion, or release member anywhere in this file.
* It never changes a hook decision, writes no production journal, and writes
  nothing at all outside a caller-supplied root.
* It runs no Claude binary. The controlled child's argv is built and recorded;
  the live canary run happens after acceptance from a second clean worktree
  (``amendment:205-206``), and an unavailable Claude binary never becomes a
  pass merely because CI cannot execute that node (``amendment:245``).

Missing or ambiguous evidence is ``UNMEASURED``/``ERROR`` (``amendment:208``).
An empty denominator is ``UNMEASURED``, never ``OBSERVED``: a decision that
examined nothing has not observed anything.

Public surface: :data:`DECISION_IDS`, :func:`capture`, :func:`reconcile`,
:func:`inventory`. Everything else is private.

Issue: #1760 (P0-A).
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable, NamedTuple

# --------------------------------------------------------------------------
# Frozen constants
# --------------------------------------------------------------------------

SCHEMA_VERSION = "p0a.1"

#: The twelve deciding observations this observer evaluates. The mutant
#: registry (``tests/fixtures/plugin_carrier/mutants.json``) is a bijection
#: onto this tuple, so a new decision with no killing mutant fails the build.
DECISION_IDS: tuple[str, ...] = (
    "D01_SCHEMA_ROOT_CLOSED",
    "D02_SCHEMA_COMPOSED_CLOSED",
    "D03_NO_STATIC_PRODUCT_IMPORT",
    "D04_NO_DYNAMIC_PRODUCT_IMPORT",
    "D05_NO_CANDIDATE_VERDICT_IN_OBSERVATION",
    "D06_SETTINGS_DIGEST_MATCH",
    "D07_SETTINGS_SOURCE_SET_EXACT",
    "D08_HOOK_TOOL_USE_ID_JOIN",
    "D09_HIDDEN_HOOK_NONZERO",
    "D10_NO_WRITE_OUTSIDE_DECLARED_ROOTS",
    "D11_NO_SILENT_CONTENT_CHANGE",
    "D12_MODE_OWNER_RECORDED_FAITHFULLY",
)

OBSERVED = "OBSERVED"
UNMEASURED = "UNMEASURED"
ERROR = "ERROR"

#: Flags that are forbidden for carrier proof (``amendment:195-196``). Building
#: an argv that contains either is refused, not silently corrected.
FORBIDDEN_CHILD_FLAGS: tuple[str, ...] = ("--safe-mode", "--no-session-persistence")

#: The COMPLETE set of option tokens this module is permitted to emit. The
#: primary refusal is this allowlist, not the blacklist above: an argv whose
#: option tokens are exactly this set cannot contain a forbidden flag under ANY
#: spelling, including spellings nobody enumerated. The blacklist is the second
#: arm, kept because two independent refusals are cheaper than one that has to
#: be right. Removing the category beats enumerating its members (#1503).
ALLOWED_CHILD_FLAGS: tuple[str, ...] = (
    "--print",
    "--output-format",
    "--include-hook-events",
    "--verbose",
    "--debug-file",
    "--setting-sources",
    "--settings",
    "--session-id",
)

#: Options whose emitted VALUE the child's parser splits on ",". This is the
#: registry that makes "validate what reaches the child" mechanical: a value
#: listed here is not one token to the parser, it is the tokens it decomposes
#: into, and those are what must be checked. MEASURED against claude 2.1.236:
#: ``--setting-sources=bogus`` -> rc=1 RECOGNIZED (probe table above), and the
#: option's documented form is a comma list (``user,project,local``).
COMMA_DELIMITED_CHILD_FLAGS: frozenset[str] = frozenset({"--setting-sources"})

#: Option -> the operator-facing name of the thing it carries, so a refusal
#: names the SURFACE the operator supplied rather than the argv slot it landed
#: in. Every value-taking member of :data:`ALLOWED_CHILD_FLAGS` appears here,
#: asserted BOTH ways -- no ``unlabelled``, no ``phantom`` -- by
#: ``test_joined_setting_sources_are_validated_as_the_units_the_child_receives``.
CHILD_FLAG_VALUE_LABELS: dict[str, str] = {
    "--output-format": "output format",
    "--debug-file": "debug file path",
    "--setting-sources": "setting source",
    "--settings": "settings overlay path",
    "--session-id": "session id",
}

# What the REAL Claude CLI parser does, MEASURED against claude 2.1.236 on
# 2026-09-07 by `claude <PROBE> --help` with stdin closed: it is CASE-SENSITIVE,
# accepts NO abbreviations, and DOES accept the `=`-joined form, so `--Safe-Mode`
# and `--safe` are not understood as `--safe-mode`. Two further measured facts
# are why the allowlist above is the primary arm rather than the blacklist: an
# unknown option is NOT rejected (it is absorbed as the positional `prompt`), and
# a value-taking option consumes the next token even when it begins with `-`.
#
# UNMEASURED, and hardened conservatively rather than assumed: BOOLEAN option
# recognition. The probe discriminates only value-taking options — a boolean
# prints usage and exits 0 exactly like an unknown flag — and every probe that
# would decide one requires letting the CLI proceed to session start, which is
# not safely decidable. Every spelling is refused whether or not the parser
# would honour it.
_CLI_PARSER_PROBE = "claude 2.1.236: case-sensitive, no abbreviations, '=' form accepted"

#: Environment names copied into the packet by digest. ``CLAUDE_PLUGIN_ROOT``
#: and ``CLAUDE_PLUGIN_DATA`` are members because hook stdin carries no
#: plugin-identifying field: "this receipt came from a plugin-registered hook"
#: is provable only from the hook process's own environment. Absent at P0-A
#: means ``UNMEASURED``; the join becomes decidable at P1.
ENVIRONMENT_ALLOWLIST: tuple[str, ...] = (
    "CLAUDE_PLUGIN_ROOT",
    "CLAUDE_PLUGIN_DATA",
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDECODE",
    "CLAUDE_PROJECT_DIR",
    "P0A_PROOF_ROOT",
    "HOME",
    "PATH",
)

#: Executables whose identity is recorded. ``claude`` is resolved but never
#: executed at P0-A, so its version stays ``UNMEASURED`` by construction.
EXECUTABLE_NAMES: tuple[str, ...] = ("claude", "python3", "git")

# Output bounds — the caps that CLIP published output. Every one has a matching
# flag and ``reconcile()`` reads every one of them, so a clipped observation
# reports ``UNMEASURED`` rather than a clean ``OBSERVED`` — see
# :data:`DECISION_EVIDENCE_PLANES` and :func:`_evidence_bounds`. Each is
# enforced in the unit its name declares; ``MAX_EVIDENCE_BYTES`` is a RAW-BYTE
# bound and :func:`_read_text` is where that is argued.
MAX_EVIDENCE_BYTES = 4 * 1024 * 1024
MAX_STREAM_RECORDS = 10_000
MAX_INVENTORY_ENTRIES = 5_000
MAX_DISCREPANCIES = 50

# A READER LIMIT, not an output bound: it clips nothing and carries no
# truncation flag. A document nested deeper than this defeats the recursive
# readers below, so :func:`_exceeds_walk_depth` classifies it MALFORMED at the
# parse boundary — the channel that already carries an undecodable document.
MAX_DOCUMENT_DEPTH = 100

#: The largest value ``stat.S_IMODE`` can return, and the ceiling the schema's
#: ``$defs/posix_mode`` already declares (``integer``, 0..4095).
#:
#: A VALUE-DOMAIN test that must run BEFORE the ``S_IMODE`` round-trip in D12,
#: never after it: ``S_IMODE`` is a C call over ``unsigned int``, so a recorded
#: ``-1``, ``2**32`` or ``2**64`` raises ``OverflowError`` — an
#: ``ArithmeticError``, outside every ``except ValueError`` on the route — and
#: aborts the observation with zero packet bytes rather than being NAMED.
#:
#: Deliberately NOT spelled ``MAX_``: this is not an output bound. It clips
#: nothing, carries no truncation flag, and appears in no
#: ``output_bounds`` declaration, so joining the ``MAX_*`` family that
#: ``test_manifest_output_bounds_match_the_observer_constants`` enumerates
#: would make it claim a bound it does not enforce.
_POSIX_MODE_CEILING = 0o7777

#: The seven fields ``$defs/path_entry`` declares, and the ONLY seven it admits
#: — the node carries ``additionalProperties: false`` and requires all seven.
#:
#: WHY THIS EXISTS AT ALL. ``_filesystem_planes`` forwards a recorded ``entries``
#: map VERBATIM, so every value under it is subject-authored and lands in the
#: emitted packet unchanged. The schema declares a domain for each; nothing read
#: three of them. Measured on the un-read bytes, one hostile value at a time in
#: an otherwise valid inventory::
#:
#:     post.entries[<path>].bytes   = -1         -> rc=0 all decisions clean
#:     post.entries[<path>].kind    = 'wormhole' -> rc=0 all decisions clean
#:     post.entries[<path>].sha256  = 12345      -> rc=0 all decisions clean
#:
#: — and each emitted a packet the module's OWN frozen schema rejects. The
#: external ``jsonschema`` oracle refused all three, so the PAIR was total; the
#: observer's half was not, and the packet is what later rungs consume.
#:
#: THE CHOICE MADE HERE, following ``recorded_settings_entry`` and
#: ``recorded_source_list``: the seven VALUE schemas are unconstrained and the
#: constraint lives in this reader. The KEY SET stays closed — mutant M02 adds an
#: unknown key to exactly this ``$def`` and D02_SCHEMA_COMPOSED_CLOSED is bound to
#: its refusal — so widening the values costs that mutant nothing. Nothing is
#: clamped, coerced or dropped: the raw value is forwarded, the deviation is NAMED.
_PATH_ENTRY_FIELDS: tuple[str, ...] = (
    "kind", "sha256", "bytes", "content_truncated", "mode", "uid", "acl_state",
)

#: The three fields D12 already reads, WITHIN ITS OWN SCOPE — entries beneath a
#: declared writable root. They are excluded from the plane-level domain reader
#: for those entries so one bad value is named once, by the decision whose
#: subject it is; outside that scope D12 never looks, so the domain reader is
#: the only reader and covers them.
_D12_PATH_ENTRY_FIELDS: frozenset[str] = frozenset({"mode", "uid", "acl_state"})

#: ``$defs/path_entry.kind`` — the enum, verbatim.
_PATH_ENTRY_KINDS: frozenset[str] = frozenset({"file", "dir", "symlink", "other"})

SUBPROCESS_TIMEOUT_S = 10

#: The names of the output bounds, as they appear in this module.
BOUND_CONSTANT_NAMES: tuple[str, ...] = (
    "MAX_EVIDENCE_BYTES",
    "MAX_STREAM_RECORDS",
    "MAX_INVENTORY_ENTRIES",
    "MAX_DISCREPANCIES",
)

#: The bookkeeping keys this module adds to its own planes and removes before
#: emitting. NAMED rather than matched on an ``_`` prefix: that prefix rule also
#: deleted SUBJECT-SUPPLIED keys — an inventory key is a path — so a cited
#: discrepancy could name a path the emitted packet no longer contained.
PRIVATE_BOOKKEEPING_KEYS: frozenset[str] = frozenset(
    {"_examined", "_static_examined", "_dynamic_examined", "_stream_id_count"}
)

# ==========================================================================
# THE TRUNCATION-FLAG REGISTRY — the declaration the CODE must satisfy
# ==========================================================================
#
# A field named for one bound must never carry another. This registry is that
# statement and
# ``test_every_truncation_flag_is_single_bound_or_a_declared_rollup`` is the
# check: it walks THIS FILE'S AST, finds every binding of a truncation-flag name
# — local, dict key, subscript, annotation, keyword — and refuses
#
#   * any flag name not declared below (so ``truncated`` and ``clipped`` are
#     unspellable);
#   * any BOUND flag whose right-hand side MENTIONS a flag or a cap belonging to
#     a different bound, syntactically, widened by a per-function alias map;
#   * any BOUND flag set to a bare ``True`` outside an ``if`` testing its own
#     cap;
#   * any ROLLUP flag reading an operand it did not declare, or whose name lacks
#     the ``any`` segment that announces it as a rollup.
#
# WHAT THIS IS: a RATCHET over the conflation shapes it is PROVEN to refuse, each
# carrying a named test as its receipt. It is SYNTACTIC, not a dataflow
# analysis; ITS REACH IS NOT CHARACTERISED — any conflation may escape it, and
# the self-test asserts a shape that does.

#: Truncation flags that name EXACTLY ONE bound. The value is the bound this
#: flag reports and the ONLY bound it may ever carry.
TRUNCATION_BOUND_FLAGS: dict[str, str] = {
    # MAX_EVIDENCE_BYTES — the raw-byte cap.
    "byte_truncated": "MAX_EVIDENCE_BYTES",
    "sha_truncated": "MAX_EVIDENCE_BYTES",
    "file_truncated": "MAX_EVIDENCE_BYTES",
    # A SECOND FILE ON THE SETTINGS PLANE, and therefore a second flag. The
    # plane's `byte_truncated` names `settings-sources.json`; the overlay is a
    # different file read by a different call, and its truncation member was
    # bound to a throwaway `_byte_truncated` — so `overlay_sha256` could be a
    # PREFIX digest published beside a flag that names another file and reads
    # False. One field per bound means one field per (bound, published output),
    # not one per cap.
    "overlay_byte_truncated": "MAX_EVIDENCE_BYTES",
    "content_truncated": "MAX_EVIDENCE_BYTES",
    "member_bytes_truncated": "MAX_EVIDENCE_BYTES",
    # MAX_STREAM_RECORDS — the record cap.
    "record_truncated": "MAX_STREAM_RECORDS",
    # MAX_INVENTORY_ENTRIES — the inventory entry cap.
    "entry_truncated": "MAX_INVENTORY_ENTRIES",
    # MAX_DISCREPANCIES — the cap on the two published lists of a decision
    # record. Both are the same cap over the same record, so one flag reports
    # it; the pre-clip count is published beside it as ``discrepancy_count``.
    "discrepancy_truncated": "MAX_DISCREPANCIES",
}

#: Truncation flags that are DECLARED ROLLUPS: they answer "did any bound clip
#: this", never "which one". Every name carries the ``any`` segment so the name
#: itself says it is a rollup, and the value enumerates the operands the flag
#: is permitted to read. Reading an operand outside this list is refused.
TRUNCATION_ROLLUP_FLAGS: dict[str, tuple[str, ...]] = {
    "any_bound_truncated": (
        "byte_truncated",
        "record_truncated",
        "entry_truncated",
        "member_bytes_truncated",
        # DECLARED BECAUSE THE WALK READS THEM. `_plane_bounds` folds every
        # published flag it finds at any depth into this rollup, so these two
        # were operands in fact while the declaration denied it. A declaration
        # that disagrees with the walk is how a flag ends up published, read,
        # and undeclared at the same time.
        "content_truncated",
        "discrepancy_truncated",
        "any_bound_truncated",
        "nested_any_truncated",
        "plane_any_truncated",
        # Same reason as the two above: `_plane_bounds` folds every PUBLISHED
        # flag it finds at any depth, so publishing this one on the settings
        # plane makes it an operand in fact the moment it is published.
        "overlay_byte_truncated",
    ),
    "nested_any_truncated": ("any_bound_truncated",),
    "plane_any_truncated": ("any_bound_truncated",),
}

#: The truncation flags that appear in the emitted packet (and therefore in
#: ``plugin_carrier_bootstrap.schema.json``). ``_TRUNCATION_KEYS`` is derived
#: from this tuple rather than restated, so a plane-level bound cannot be added
#: to the packet and then forgotten by the reader that degrades decisions.
PUBLISHED_TRUNCATION_FLAGS: tuple[str, ...] = (
    "byte_truncated",
    "record_truncated",
    "entry_truncated",
    "member_bytes_truncated",
    "content_truncated",
    "discrepancy_truncated",
    "any_bound_truncated",
    "overlay_byte_truncated",
)

# Fixed evidence file names read from the run root. The debug log is NOT here:
# its path is supplied per run as ``--debug-file``, so it has no fixed name.
EVIDENCE_PACKET = "packet.json"
EVIDENCE_STREAM = "stream.jsonl"
EVIDENCE_TRANSCRIPT = "transcript.jsonl"
EVIDENCE_SETTINGS = "settings-sources.json"
EVIDENCE_FS_INVENTORY = "fs-inventory.json"
EVIDENCE_CANDIDATE_CLAIM = "candidate-claim.json"

SCHEMA_FILENAME = "plugin_carrier_bootstrap.schema.json"

#: Stream record types that CLAIM a hook lifecycle identity.
#:
#: BOTH the identity and the DISCRIMINATOR are rendered by
#: :func:`_recorded_as_text`, and the second half of that is a correction: the
#: claim used to read "a record cannot leave the join by changing the TYPE of
#: the value it recorded", and it was false for the one value the sentence was
#: about. The rendering had been applied to ``tool_use_id`` and ``outcome`` —
#: the two fields the reported bug used — and not to ``type``, the
#: discriminator on the same record in the same loop, so a ghost ``hook_event``
#: recording ``"type": ["hook_event"]`` still left the join in silence.
#:
#: What holds now, stated as what REFUSES rather than as an absolute: a record
#: whose ``type`` the rendering had to change is NAMED on D08 and D09 and
#: degrades the hooks plane to ``UNMEASURED``; a record whose ``type`` is a
#: string outside this vocabulary is declined, and every decline is counted in
#: the plane's ``non_lifecycle_record_count`` so it moves the packet.
#:
#: A TUPLE, not a set, and that is a measurement rather than a style choice:
#: ``unhashable in frozenset`` raises ``TypeError``, so a stream record
#: recording ``"type": ["tool_use"]`` crashed ``reconcile`` outright. The
#: operand is subject-authored, so the membership test must be an equality scan.
_LIFECYCLE_RECORD_TYPES: tuple[str, ...] = ("tool_use", "hook_event")

# Verdict vocabulary is removed as a CATEGORY, not enumerated as members: any
# key whose underscore-separated tokens intersect this set is a leak, however
# the key got there. Enumerating known field names is the #1503 failure shape.
_VERDICT_KEY_TOKENS = frozenset(
    {
        "verdict", "verdicts", "pass", "passed", "passes", "fail", "failed",
        "failure", "promotion", "promote", "promoted", "release", "released",
        "eligible", "eligibility", "approved", "approval", "blessed",
        "certified", "certification",
    }
)

_VERDICT_VALUE_TOKENS = frozenset(
    {
        "pass", "fail", "candidate_pass", "bootstrap_pass", "proven",
        "approved", "released", "standalone_released",
        "private_carrier_released",
    }
)

# ``[DEBUG] hook <Event> tool_use_id=<id> command=<name> exit=<n> stdout_bytes=<n>``
_DEBUG_HOOK_RE = re.compile(
    r"hook\s+(?P<event>[A-Za-z]+)\s+"
    r"tool_use_id=(?P<tool_use_id>\S+)\s+"
    r"command=(?P<command>\S+)\s+"
    r"exit=(?P<exit>-?\d+)\s+"
    r"stdout_bytes=(?P<stdout_bytes>\d+)"
)

#: A line that CLAIMS to be a hook receipt, independent of field ORDER. Every
#: pattern must match for the line to be claimed.
#:
#: WIDER than :data:`_DEBUG_HOOK_RE`, which fixes the order of five fields: a
#: receipt whose fields are permuted, or one missing a field, still reads as a
#: receipt here and is COUNTED as unparsable instead of being dropped. Before
#: this existed, ``hook PreToolUse command=x tool_use_id=T exit=2
#: stdout_bytes=0`` -- the same facts as a matching line, reordered -- fell
#: through the ``continue`` in :func:`_parse_debug_hooks`, no bound fired, and
#: the debug plane still read OBSERVED with a non-zero hook exit invisible.
#:
#: NARROWER than "mentions a hook", deliberately: claiming every such line
#: would drive every real log to a malformed status. What is left is an
#: ASSUMPTION about a corpus nobody has measured -- that an ordinary line
#: carries both ``hook`` and ``tool_use_id=`` only rarely. It does not always
#: hold (``hook registry ready; tagging tool_use_id=<pending>``): such a line
#: over-fires to ERROR, which is fail-closed and pinned as intended below.
_DEBUG_RECEIPT_SHAPE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bhook\b"),
    re.compile(r"\btool_use_id="),
)

#: HOW MANY receipts a claimed line carries BY IDENTITY, where
#: :data:`_DEBUG_RECEIPT_SHAPE_RES` decides only WHETHER it carries any.
#:
#: The distinction is the whole of the residue arithmetic in
#: :func:`_debug_line_receipts`. A yes/no shape gate cannot express "this line
#: carried two receipts and the reader read one", which is exactly what merging
#: a non-zero receipt onto a benign one produced: one record, no malformed
#: count, and the non-zero exit invisible to D09.
#:
#: THIS COUNTS IDENTITIES, NOT DECISIONS, and on its own it is the wrong
#: denominator — see :data:`_DEBUG_RECEIPT_EXIT_RE`. It is kept because a
#: receipt can be lost by carrying an id this reader cannot pair with an exit
#: (a permuted or truncated receipt), which the exit channel alone cannot
#: express. Two channels, and the residue takes the LARGER: either channel
#: coming up short is evidence lost, and a denominator that is the minimum of
#: two claims is a denominator an attacker picks.
_DEBUG_RECEIPT_LEXEME_RE = re.compile(r"\btool_use_id=")

#: HOW MANY DECISIONS a claimed line carries — the unit D09 actually decides
#: on, and the correction to a residue that was sound arithmetic over the wrong
#: denominator.
#:
#: D09 asks "did any hook exit non-zero". The answer is read off ``exit=``,
#: never off ``tool_use_id=``, so a denominator counting identities cannot see
#: a SECOND ``exit=`` appended to a receipt that already carries one.
#: :data:`_DEBUG_HOOK_RE` is greedy-left and stops at the first
#: ``exit=``/``stdout_bytes=`` pair, so
#: ``hook Pre tool_use_id=T command=c exit=0 stdout_bytes=0 exit=2
#: stdout_bytes=0`` read one record (``exit=0``), claimed one receipt by
#: identity, left residue zero, and produced a packet byte-identical to the
#: clean line — while ``grep -o 'exit=[0-9]*'`` on the same bytes reported
#: ``exit=0`` AND ``exit=2``. The mirror image (``exit=2`` first, ``exit=0``
#: appended) was equally undetectable in the other direction: the packet named
#: a non-zero exit and could not say that a second, contradicting decision sat
#: unread on the same line. ``command=`` is written by the candidate into its
#: own settings, so both shapes are subject-authored — ``ladder:282``.
#:
#: The extra pairs are ACCOUNTED, never FABRICATED into records: a bare
#: ``exit=`` pair carries no ``tool_use_id`` and no event name, so inventing a
#: join identity for it would put a value in the packet no byte of the log
#: supports. Counting it in the residue degrades the debug plane to ``ERROR``
#: through ``unparsable_records``, which is the fail-closed half of "unparsed
#: or residual evidence must degrade, never disappear".
_DEBUG_RECEIPT_EXIT_RE = re.compile(r"\bexit=-?\d+")


# --------------------------------------------------------------------------
# Small stdlib helpers
# --------------------------------------------------------------------------


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _recorded_as_text(field: str, value: Any) -> str:
    """Render a subject-authored scalar as text WITHOUT ever declining it.

    THE CATEGORY THIS CLOSES: a reader that answers "is this the type I
    expected?" and drops the value when the answer is no. Every evidence
    document here already has a malformed channel and a named-discrepancy
    channel, and a record excluded by a type test reaches NEITHER — so strictly
    less evidence read strictly cleaner than the violation it concealed. A
    ghost ``hook_event`` escaped D09 by recording ``tool_use_id`` as an integer:
    with a string id the decision named it, with an integer id the discrepancy
    disappeared and the packet was byte-identical to a clean run.

    The rendering is INJECTIVE over ``repr``: two distinct non-string values
    render to two distinct identities, so a mismatch they carry survives into
    the comparison instead of collapsing. That is the property a coercion to
    ``None`` destroys, and destroying it is what let two different digests
    compare equal.

    It also cannot be forged from the debug log: the rendering contains spaces
    and :data:`_DEBUG_HOOK_RE` captures ``tool_use_id`` as ``\\S+``, so no
    receipt can name a rendered identity and pair itself with one.
    """
    if isinstance(value, str):
        return value
    return f"<non-string {field} {value!r}>"


def _recorded_as_json(value: Any) -> str:
    """Render a subject-authored value as the JSON IDENTITY it was recorded with.

    THE CATEGORY THIS CLOSES: comparing two subject-authored values with
    Python ``==``. ``1 == True``, ``0 == False`` and ``1 == 1.0`` are all
    True, so two recordings whose BYTES differ compared EQUAL and the
    difference they carried vanished with no flag, count or status able to see
    it — the same erasure a coercion to ``None`` performs, reached without any
    coercion and so invisible to every guard aimed at coercions.

    The rendering is what ``json`` would WRITE, so it separates exactly the
    recordings a third party recomputing from the raw bytes can separate:
    ``1``, ``true`` and ``1.0`` are three different documents. NO TYPE IS
    ENUMERATED, here or at any call site — listing ``bool``/``int``/``float``
    is the enumerate-the-members shape this module keeps being caught by, and
    it would miss the fourth type nobody thought of. A value ``json`` cannot
    encode is rendered with its type NAMED rather than dropped, because a
    reader defeated by a value must not answer as if the value agreed.
    """
    try:
        return json.dumps(value, sort_keys=True)
    except (TypeError, ValueError):
        return f"<unencodable {type(value).__name__} {value!r}>"


def _recorded_values_differ(left: Any, right: Any) -> bool:
    """True when two subject-authored values are not the SAME RECORDING.

    The single comparison rule for subject-authored operands. It exists as a
    named predicate rather than an inline ``!=`` so a NEW comparison cannot be
    written the unsafe way by default; ``_settings_by_path`` reaches the same
    answer for the settings twin by naming a non-string digest before any
    comparison happens, and both routes are driven by the same node.
    """
    return _recorded_as_json(left) != _recorded_as_json(right)


def _sha256_file(path: Path) -> tuple[str | None, int | None, bool]:
    """Digest ``path``, capped at :data:`MAX_EVIDENCE_BYTES`.

    Returns ``(sha256, byte_count, byte_truncated)``. The third member is named
    ``byte_truncated`` at every call site because it is
    :data:`MAX_EVIDENCE_BYTES` and nothing else; the bare name ``truncated``
    is not spellable in this module (see the truncation-flag registry).

    ``byte_count`` is the number of bytes DIGESTED, which equals the file's
    real size unless ``byte_truncated`` is true, in which case it is exactly
    :data:`MAX_EVIDENCE_BYTES` and the digest covers only that prefix.

    Any OS error yields ``(None, None, False)`` rather than raising: an
    unreadable subject is ``UNMEASURED`` evidence, not a crash.
    """
    digest = hashlib.sha256()
    total = 0
    byte_truncated = False
    try:
        with open(path, "rb") as handle:
            while True:
                chunk = handle.read(65536)
                if not chunk:
                    break
                if total + len(chunk) > MAX_EVIDENCE_BYTES:
                    digest.update(chunk[: MAX_EVIDENCE_BYTES - total])
                    total = MAX_EVIDENCE_BYTES
                    byte_truncated = True
                    break
                digest.update(chunk)
                total += len(chunk)
    except OSError:
        return None, None, False
    return digest.hexdigest(), total, byte_truncated


class _TextRead(NamedTuple):
    """``text`` plus whether :data:`MAX_EVIDENCE_BYTES` clipped it.

    Named ``byte_truncated``, not ``truncated``: this module carries three
    independent bounds, and a field named for none of them can be forwarded
    into the wrong slot.
    """

    text: str | None
    byte_truncated: bool


class _JsonRead(NamedTuple):
    """A parsed JSON object plus the two ways reading it can go wrong.

    ``byte_truncated`` is :data:`MAX_EVIDENCE_BYTES` and nothing else.
    """

    document: dict[str, Any]
    byte_truncated: bool
    malformed: bool


class _JsonlRead(NamedTuple):
    """Parsed JSONL records plus every way reading them can go short.

    ONE FIELD PER BOUND, and no field stands for more than one bound:

    * ``byte_truncated`` -- and only -- :data:`MAX_EVIDENCE_BYTES`.
    * ``record_truncated`` -- and only -- :data:`MAX_STREAM_RECORDS`.
    * ``unparsable`` -- lines the reader got no record out of, whether it
      could not decode them or decoded them to something that is not a record
      object. One channel, because the outcome is one outcome.

    A flag saying a bound fired that did not is the same class of defect as one
    firing silently: either way it stops being evidence about WHICH bound
    clipped the subject. The two bounds degrade differently and are reported
    separately.
    """

    records: list[dict[str, Any]]
    byte_truncated: bool
    record_truncated: bool
    unparsable: int


class _EvidenceCount(NamedTuple):
    """A record count that carries its own bounds, so a count cannot lie.

    ``byte_truncated`` and ``record_truncated`` are separate slots because the
    caller (:func:`_bounded_evidence`) publishes them as separate packet
    fields. A counter that has no record cap to enforce returns
    ``record_truncated=False`` -- the honest answer, since the cap it does not
    apply cannot have clipped anything -- rather than reusing the slot for the
    byte flag it does have.
    """

    count: int | None
    byte_truncated: bool
    record_truncated: bool
    unparsable: int


def _read_text(path: Path) -> _TextRead:
    """Read ``path`` under the RAW-BYTE cap :data:`MAX_EVIDENCE_BYTES`.

    The handle is BINARY on purpose. ``MAX_EVIDENCE_BYTES`` is declared in
    bytes and :func:`_sha256_file` enforces it in bytes, so this reader must
    too. In text mode ``handle.read(n)`` returns *n characters* and ``len()``
    counts *characters*: a stream of 4-byte code points would be clipped at
    four times the declared cap while reporting ``truncated=False``, and the
    two readers over the same file would disagree about whether it was clipped
    at all. That is the same evidence-suppression the record cap closes, and
    a bound enforced in the wrong unit is a bound that does not hold.

    One byte beyond the cap is requested so the clip is DETECTED rather than
    silently applied.

    Decoding is deterministic at the boundary. The byte slice is decoded with
    ``errors="replace"`` — the module's convention — so a multi-byte sequence
    the cap cuts in half becomes U+FFFD rather than raising ``UnicodeDecodeError``
    or varying with buffer size. The same bytes always yield the same text.
    """
    try:
        with open(path, "rb") as handle:
            raw = handle.read(MAX_EVIDENCE_BYTES + 1)
    except OSError:
        return _TextRead(None, False)
    byte_truncated = len(raw) > MAX_EVIDENCE_BYTES
    if byte_truncated:
        raw = raw[:MAX_EVIDENCE_BYTES]
    return _TextRead(raw.decode("utf-8", errors="replace"), byte_truncated)


def _exceeds_walk_depth(node: Any) -> bool:
    """True when ``node`` nests deeper than :data:`MAX_DOCUMENT_DEPTH`.

    Iterative on an explicit stack, so measuring the depth cannot itself hit
    the limit it measures.

    Catching ``RecursionError`` at the parser protects the PARSER only. A
    document a little under the interpreter's limit parses cleanly and then
    defeats the recursive readers that CONSUME it — :func:`_verdict_leaks` and
    :func:`_strip_private` — turning a bounded failure into an uncaught crash
    in ``reconcile()`` (CWE-674). The consumers are guarded here, at the same
    boundary and through the same malformed channel, because a depth no reader
    in this module can walk is a document this module could not decode.
    """
    stack: list[tuple[Any, int]] = [(node, 1)]
    while stack:
        current, depth = stack.pop()
        if depth > MAX_DOCUMENT_DEPTH:
            return True
        if isinstance(current, dict):
            stack.extend((value, depth + 1) for value in current.values())
        elif isinstance(current, list):
            stack.extend((item, depth + 1) for item in current)
    return False


class _RepeatedJsonKey(ValueError):
    """A JSON object recorded the same key twice.

    ``json.loads`` keeps the LAST value for a repeated key and reports nothing.
    One extra ``"<path>": {...}`` pair appended inside ``post.entries`` therefore
    reinstated a superseded record and D11/D12 recomputed ZERO discrepancies
    over bytes that still carried the drift: the collapse happened in the
    READER, upstream of every decision, so no cap fired, no ``evidence_count``
    moved and no plane status degraded. The packet read fully clean.

    ``ValueError`` is the base class deliberately. Both readers already route
    ``ValueError`` through their malformed channel — ``_JsonRead.malformed`` to
    ``ERROR``, ``_JsonlRead.unparsable`` to the same — so the refusal reuses a
    channel that already degrades every decision reading the plane, and needs
    no new packet field.
    """


def _pairs_without_repeats(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """``object_pairs_hook`` refusing any object that records a key twice.

    Installed on EVERY json read in this module rather than on the two readers
    whose collapse was reproduced, because the defect is the parser's
    last-wins rule and not the fields it happened to hide.
    """
    seen: set[str] = set()
    for key, _value in pairs:
        if key in seen:
            raise _RepeatedJsonKey(f"repeated JSON object key {key!r}")
        seen.add(key)
    return dict(pairs)


#: ``float("inf")``, bound once so :func:`_finite_float` can compare against
#: it without importing ``math`` into a module whose import surface is audited.
_POSITIVE_INFINITY: float = float("inf")


class _NonFiniteJsonConstant(ValueError):
    """A JSON document recorded ``Infinity``, ``-Infinity`` or ``NaN``.

    None of the three is JSON (RFC 8259 admits no non-finite number), yet
    Python's ``json`` accepts all three on the way IN and writes them back out
    as bare tokens on the way OUT. A subject writing one into a document this
    module forwards verbatim therefore produced a packet that this module
    considered well formed and that node's ``JSON.parse`` REJECTED -- measured
    at 16,265 bytes and ``rc=0`` on an otherwise clean run.

    That falsifies the manifest's claim that the evidence is recomputable from
    raw bytes by a third party with ordinary tools, which is a claim about
    RECOMPUTABILITY and not about any decision: the naming channel still fired
    and every observer/jq disagreement still ran fail-closed, so no decision
    read clean over it. The claim was wrong anyway, so the token is refused at
    the PARSE boundary rather than tolerated to the emit boundary.

    ``ValueError`` is the base class for the same reason
    :class:`_RepeatedJsonKey` uses it: both readers already route ``ValueError``
    through their malformed channel, so the refusal degrades every decision
    that reads the plane and needs no new packet field.
    """


def _refuse_non_finite(constant: str) -> Any:
    """``parse_constant`` hook: every non-finite JSON token is a parse failure.

    Installed on EVERY ``json.loads`` in this module, beside
    :func:`_pairs_without_repeats`, because the defect is the parser's
    extension to JSON and not the fields it happened to reach through.
    """
    raise _NonFiniteJsonConstant(f"non-finite JSON constant {constant!r}")


def _finite_float(literal: str) -> float:
    """``parse_float`` hook: a numeric literal that OVERFLOWS is refused too.

    THE SECOND ROUTE, and ``parse_constant`` cannot see it. ``1e400`` is a
    NUMBER token, not one of the three constant tokens, so ``json`` hands it to
    ``parse_float`` and ``float("1e400")`` returns ``inf`` with no error at all.
    Found by ATTACKING the ``Infinity`` fix rather than by reading it: with only
    the constant hook installed, a subject writing ``1e400`` into its own
    ``fs-inventory.json`` moved the failure from an unparseable packet to a
    packet of ZERO BYTES at ``rc=3``, because the emit-boundary
    ``allow_nan=False`` then refused the whole document.

    That is a worse outcome, not a fixed one. A subject must not be able to
    DENY an observation; it may only degrade the plane it authored. Refusing
    here puts the literal on the same malformed channel as the constant token,
    so the plane reports ``ERROR`` and the packet is still emitted.

    ``value != value`` is the NaN test written without importing ``math``,
    and it is reachable: ``parse_float`` receives ``nan`` spelled as a literal
    on some producers even though ``json`` routes the bare token elsewhere.
    """
    value = float(literal)
    if value != value or value in (_POSITIVE_INFINITY, -_POSITIVE_INFINITY):
        raise _NonFiniteJsonConstant(f"non-finite JSON number {literal!r}")
    return value


def _read_json(path: Path) -> _JsonRead:
    """Parse ``path`` as a JSON object; report failure instead of hiding it.

    ``RecursionError`` is caught alongside ``ValueError`` because it is a
    ``RuntimeError`` subclass — ``except ValueError`` does not catch it, and a
    deeply nested document would otherwise crash the process (CWE-674). A
    document that parses but is too deep for this module's own readers is
    refused by :func:`_exceeds_walk_depth` on the same channel, and one that
    records a key twice by :class:`_RepeatedJsonKey` on the same channel again.
    """
    read = _read_text(path)
    if read.text is None:
        return _JsonRead({}, False, False)
    try:
        parsed = json.loads(
            read.text,
            object_pairs_hook=_pairs_without_repeats,
            parse_constant=_refuse_non_finite,
            parse_float=_finite_float,
        )
    except (ValueError, RecursionError):
        return _JsonRead({}, read.byte_truncated, True)
    if not isinstance(parsed, dict) or _exceeds_walk_depth(parsed):
        return _JsonRead({}, read.byte_truncated, True)
    return _JsonRead(parsed, read.byte_truncated, False)


def _read_jsonl(path: Path) -> _JsonlRead:
    """Parse ``path`` as JSONL, reporting EACH bound that clipped it, separately.

    Three ways this read can come up short, three fields, no overlap:

    * **Byte cap.** :data:`MAX_EVIDENCE_BYTES` clipped the bytes before any
      line was seen; reported by :func:`_read_text` and passed straight
      through as ``byte_truncated``.
    * **Record cap.** Hitting :data:`MAX_STREAM_RECORDS` sets
      ``record_truncated``. A bare ``break`` here made a hook-bypass event
      lying beyond the cap structurally invisible to D08 — the orphan set is a
      symmetric difference, which cannot express "present in neither".
    * **A line yielding no record.** A line recording the same object key twice is
      counted here too, through :class:`_RepeatedJsonKey`: last-wins is a
      silent edit, not a parse. ``RecursionError`` is a ``RuntimeError`` subclass,
      so ``except ValueError`` alone let a depth-bombed line crash the whole
      process (CWE-674). It is caught here, matching :func:`_read_json`, and
      counted rather than dropped: a line the reader was defeated by is
      evidence about the reader, and a caller must be able to see it. A line
      that decodes to a JSON ARRAY is counted here too — it parsed, and it
      still yielded no record.

    The two flags are never OR-ed together here: a caller wanting "clipped at
    all" composes the rollup from named operands at its own site.
    """
    read = _read_text(path)
    if read.text is None:
        return _JsonlRead([], False, False, 0)
    records: list[dict[str, Any]] = []
    unparsable = 0
    record_truncated = False
    for line in read.text.splitlines():
        line = line.strip()
        if not line:
            continue
        if len(records) >= MAX_STREAM_RECORDS:
            record_truncated = True
            break
        try:
            parsed = json.loads(
                line,
                object_pairs_hook=_pairs_without_repeats,
                parse_constant=_refuse_non_finite,
                parse_float=_finite_float,
            )
        except (ValueError, RecursionError):
            unparsable += 1
            continue
        if _exceeds_walk_depth(parsed):
            unparsable += 1
            continue
        if not isinstance(parsed, dict):
            # A line that DECODED but yielded no record. Counted on the SAME
            # channel as a line that would not decode at all, because the
            # outcome is the same one: the reader got no record out of it. The
            # previous `if isinstance(parsed, dict): records.append(...)`
            # dropped it instead, so a file of SEVEN lines whose seventh was a
            # JSON array reported `record_count=6, unparsable_records=0,
            # observation_status=OBSERVED` — indistinguishable from a file that
            # only ever had six. A record lost upstream of every decision fires
            # no bound and degrades no plane.
            unparsable += 1
            continue
        records.append(parsed)
    return _JsonlRead(records, read.byte_truncated, record_truncated, unparsable)


def _worst(statuses: Iterable[str]) -> str:
    """ERROR dominates UNMEASURED dominates OBSERVED."""
    seen = set(statuses)
    if ERROR in seen:
        return ERROR
    if UNMEASURED in seen or not seen:
        return UNMEASURED
    return OBSERVED


def _is_declarable_root(root: Any) -> bool:
    """True when ``root`` can bind a containment test at all.

    ``declared_writable_roots`` is read verbatim from a document the SUBJECT
    wrote, so the operand of :func:`_is_within` is subject-supplied. A root that
    normalizes to the filesystem root makes the prefix test ``startswith("/")``,
    which is true of every absolute path — the subject would then supply the
    answer to the two decisions about itself (``ladder:282``). Empty, relative
    and ``.``/``..`` roots are refused on the same ground: none of them names a
    containable region, and each would decide by accident rather than by
    declaration. A refused root is not silently narrowed to "nothing is
    declared" — :func:`_filesystem_planes` degrades the plane to ``UNMEASURED``,
    because a candidate that can suppress a decision has steered it just as
    surely as one that can satisfy it.
    """
    if not isinstance(root, str) or not root.strip():
        return False
    norm = os.path.normpath(root)
    if not os.path.isabs(norm):
        return False
    return norm.rstrip(os.sep) != ""


def _is_within(child: str, parent: str) -> bool:
    """True when ``child`` is ``parent`` or lives beneath it.

    Purely lexical on normalized absolute strings — no filesystem access, so a
    recorded path that no longer exists is still classifiable. A parent that is
    not a declarable root contains nothing (:func:`_is_declarable_root`).
    """
    if not _is_declarable_root(parent):
        return False
    child_norm = os.path.normpath(child)
    parent_norm = os.path.normpath(parent)
    if child_norm == parent_norm:
        return True
    return child_norm.startswith(parent_norm.rstrip(os.sep) + os.sep)


def _run_command(argv: list[str], cwd: Path | None = None) -> tuple[int | None, str]:
    """Run ``argv`` with a hard timeout; never raise.

    DECODING IS SPECIFIED, NOT INHERITED, and until it was the "never raise"
    above was false. ``text=True`` with no ``encoding=`` decodes with the
    LOCALE codec and ``errors="strict"``; a child writing bytes that codec
    cannot decode raises ``UnicodeDecodeError``, which is a ``ValueError`` and
    so escapes the ``except (OSError, subprocess.SubprocessError)`` below. A
    git ref name is bytes and need not be valid UTF-8, so a single such branch
    aborted the WHOLE observation with zero packet bytes -- and ``_cli`` then
    reported it on the arm reserved for refused argv, attributing a
    subject-induced reader defeat to the operator.

    The quieter half is that the locale is AMBIENT: two operators with
    different ``LANG`` decoded identical child bytes differently and emitted
    different ``git_snapshot`` bytes from identical repositories, in a module
    that is byte-explicit everywhere else. :func:`_read_text` names UTF-8 and
    ``errors="replace"`` for exactly this reason; this is the same choice,
    applied to the other input channel. ``errors="replace"`` keeps the
    undecodable byte VISIBLE in the recorded output as U+FFFD rather than
    dropping the whole command's result.
    """
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            argv,
            cwd=str(cwd) if cwd is not None else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=SUBPROCESS_TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError):
        return None, ""
    return completed.returncode, (completed.stdout or "").strip()


# --------------------------------------------------------------------------
# Public: recursive inventory
# --------------------------------------------------------------------------


def _identity_moved(path_str: str, before: os.stat_result) -> bool:
    """True when ``path_str`` no longer names the file ``before`` described.

    THE IDENTITY A CONTENT READ IS BOUND TO is ``(st_dev, st_ino, st_mtime_ns,
    st_size)``: the device and inode say it is the same file, the nanosecond
    mtime and the size say the bytes under it did not move. Mode and owner are
    deliberately absent -- a ``chmod`` between the two reads does not
    invalidate a digest, and folding it in here would degrade a measurement
    that is still true.

    A PATH THAT CANNOT BE STAT-ED AT ALL COUNTS AS MOVED. It answered a moment
    ago and does not now, which is the same loss of correspondence between the
    metadata and the bytes, and it is answered the same way rather than being
    re-raised at a caller that has already published half an entry.

    RESIDUAL, stated rather than implied: a rewrite that preserves device,
    inode, size AND the nanosecond mtime is invisible to this. On a filesystem
    whose timestamps are coarse that window is real. What this removes is the
    UNBOUNDED window between two syscalls, not the resolution of the clock.
    """
    try:
        after = os.lstat(path_str)
    except OSError:
        return True
    return (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_size) != (
        after.st_dev,
        after.st_ino,
        after.st_mtime_ns,
        after.st_size,
    )


def inventory(root: Path) -> dict[str, Any]:
    """Recursive path/digest/mode inventory of ``root``.

    Uses ``os.walk(followlinks=False)`` and ``os.lstat`` so a symlink is
    recorded as a symlink rather than followed into whatever it points at.
    Permission bits come from ``stat.S_IMODE(st.st_mode)``; a raw ``st_mode``
    would also encode the file type and is exactly what mutant M12 injects.
    ``st_uid`` is recorded only where ``os.geteuid`` exists, because owner ids
    are meaningless on carriers without POSIX identities.

    TWO bounds reach this plane, and they get two fields — never one:

    * ``entry_truncated`` is :data:`MAX_INVENTORY_ENTRIES` and nothing else.
      True means paths exist under ``root`` that are absent from ``entries``.
    * ``member_bytes_truncated`` is :data:`MAX_EVIDENCE_BYTES` and nothing
      else. True means at least one inventoried FILE was larger than the byte
      cap, so its ``sha256`` covers only the first ``MAX_EVIDENCE_BYTES``
      bytes. The entry itself carries ``content_truncated`` so the clipped
      member can be identified rather than merely counted.

    Both flags are in :data:`PUBLISHED_TRUNCATION_FLAGS`, so
    :func:`_plane_bounds` reads both and either cap firing degrades every
    decision that reads this plane to ``UNMEASURED``.

    IDENTITY AND CONTENT ARE READ BY TWO SEPARATE SYSCALLS, so the pair is
    re-checked with :func:`_identity_moved` before an entry is published. An
    entry whose file moved under the digest keeps its metadata and drops its
    content -- ``sha256`` and ``bytes`` null -- and folds ``UNMEASURED`` into
    ``observation_status``. A hybrid of pre-change metadata and post-change
    bytes is never emitted. Measured by
    ``test_a_file_swapped_between_the_identity_read_and_the_digest_is_not_published_as_one``.

    RESIDUAL, stated rather than implied: two files that exceed the byte cap
    and differ only past it still produce the same ``sha256`` and the same
    ``bytes``. ``content_truncated`` says the digest is a prefix digest; it
    does not restore the discrimination the cap removed. Measured by
    ``test_two_files_differing_past_the_byte_cap_record_identical_digests``.
    """
    root = Path(root)
    entries: dict[str, dict[str, Any]] = {}
    entry_truncated = False
    member_bytes_truncated = False
    status = OBSERVED
    has_uid = hasattr(os, "geteuid")

    if not root.exists():
        return {
            "root": str(root),
            "root_exists": False,
            "entries": {},
            "entry_count": 0,
            "entry_truncated": False,
            "member_bytes_truncated": False,
            "observation_status": UNMEASURED,
        }

    def record(path_str: str) -> None:
        nonlocal entry_truncated, member_bytes_truncated, status
        if len(entries) >= MAX_INVENTORY_ENTRIES:
            entry_truncated = True
            return
        try:
            st = os.lstat(path_str)
        except OSError:
            status = _worst([status, UNMEASURED])
            return
        if stat.S_ISLNK(st.st_mode):
            kind = "symlink"
        elif stat.S_ISDIR(st.st_mode):
            kind = "dir"
        elif stat.S_ISREG(st.st_mode):
            kind = "file"
        else:
            kind = "other"
        digest: str | None = None
        size: int | None = None
        content_truncated = False
        if kind == "file":
            digest, size, file_truncated = _sha256_file(Path(path_str))
            content_truncated = file_truncated
            member_bytes_truncated = member_bytes_truncated or file_truncated
            if digest is None:
                status = _worst([status, UNMEASURED])
            elif _identity_moved(path_str, st):
                # THE OTHER HALF OF THE TOCTOU. Identity comes from `os.lstat`
                # and content from a SEPARATE `open`, so a file swapped between
                # the two syscalls yields ONE entry carrying pre-change mode
                # and owner beside post-change bytes -- a hybrid that describes
                # no state the filesystem was ever in, published as OBSERVED
                # with nothing flagged. The `_bounded_evidence` note covers only
                # the case where the SECOND read FAILS; this is the case where
                # it SUCCEEDS on different bytes, which no channel could see.
                #
                # THE CONTENT IS DROPPED, NOT THE ENTRY. `sha256: null` with
                # `bytes: null` is the shape this module already publishes for
                # a file it could not read, it stays inside the domain
                # `$defs/path_entry` declares, and the path keeps its place in
                # the walk instead of vanishing from a denominator. What is
                # published is then the FIRST `os.lstat` alone: one consistent
                # read, with no content attributed to it.
                #
                # `member_bytes_truncated` IS LEFT AS IT STANDS. It is a walk-
                # wide accumulator; a member really was clipped at
                # MAX_EVIDENCE_BYTES during this walk, and clearing it here
                # would erase another entry's answer to make this one tidy.
                digest = None
                size = None
                content_truncated = False
                status = _worst([status, UNMEASURED])
        entries[os.path.normpath(path_str)] = {
            "kind": kind,
            "sha256": digest,
            "bytes": size,
            "content_truncated": content_truncated,
            "mode": stat.S_IMODE(st.st_mode),
            "uid": st.st_uid if has_uid else None,
            "acl_state": UNMEASURED,
        }

    def unlistable(_error: OSError) -> None:
        """Fold a directory ``os.walk`` could not list toward ``UNMEASURED``.

        ``os.walk`` discards ``scandir`` errors when ``onerror`` is None, so an
        unreadable subtree is dropped BEFORE ``record`` runs: its paths are
        absent from ``entries`` while no cap fired, which no truncation flag can
        report and which ``any_bound_truncated`` therefore cannot see. This is
        the same degradation ``record`` performs on an ``os.lstat`` failure,
        applied at the only other place the walk can lose paths.
        """
        nonlocal status
        status = _worst([status, UNMEASURED])

    record(str(root))
    for dirpath, dirnames, filenames in os.walk(
        str(root), onerror=unlistable, followlinks=False
    ):
        # IN PLACE, so `os.walk` descends in this order too. `sorted(dirnames)`
        # sorts a COPY: the recording order within one directory was sorted
        # while the order the subtrees were VISITED stayed `scandir` order,
        # which is filesystem-dependent. `entries` is an insertion-ordered dict
        # that later rungs digest as `fs-inventory.json`, so identical trees
        # produced different bytes on different filesystems.
        dirnames[:] = sorted(dirnames)
        for name in dirnames + sorted(filenames):
            record(os.path.join(dirpath, name))

    return {
        "root": str(root),
        "root_exists": True,
        "entries": entries,
        "entry_count": len(entries),
        "entry_truncated": entry_truncated,
        "member_bytes_truncated": member_bytes_truncated,
        "observation_status": status,
    }


# --------------------------------------------------------------------------
# Private: source audit (import boundary)
# --------------------------------------------------------------------------


def _stdlib_names() -> frozenset[str]:
    allowed = set(sys.stdlib_module_names) | set(sys.builtin_module_names)
    allowed.add("__future__")
    return frozenset(allowed)


def _static_import_findings(tree: ast.AST) -> tuple[list[dict[str, Any]], int]:
    """Every ``import``/``from ... import`` in the tree, at any nesting depth.

    The rule removes a category: a top-level module name outside the standard
    library is a finding. Scanning only module-level nodes is the defect shape
    that let #1503 fail open, so the walk is unconditional.
    """
    allowed = _stdlib_names()
    findings: list[dict[str, Any]] = []
    examined = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            examined += 1
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in allowed:
                    findings.append(
                        {
                            "kind": "static",
                            "module": alias.name,
                            "lineno": node.lineno,
                            "evidence": f"import {alias.name}",
                        }
                    )
        elif isinstance(node, ast.ImportFrom):
            examined += 1
            if node.level:
                findings.append(
                    {
                        "kind": "static",
                        "module": None,
                        "lineno": node.lineno,
                        "evidence": f"relative import level {node.level}",
                    }
                )
                continue
            top = (node.module or "").split(".")[0]
            if top not in allowed:
                findings.append(
                    {
                        "kind": "static",
                        "module": node.module,
                        "lineno": node.lineno,
                        "evidence": f"from {node.module} import ...",
                    }
                )
    return findings, examined


def _dynamic_import_findings(tree: ast.AST) -> tuple[list[dict[str, Any]], int]:
    """Dynamic import call sites: ``importlib.import_module`` and ``__import__``.

    An unresolvable target is itself a finding. A file that must import only
    the standard library cannot contain an import whose target no reader can
    determine — "I could not tell" is not permission.
    """
    allowed = _stdlib_names()
    findings: list[dict[str, Any]] = []
    examined = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        examined += 1
        func = node.func
        if isinstance(func, ast.Attribute):
            name = func.attr
        elif isinstance(func, ast.Name):
            name = func.id
        else:
            continue
        if name not in ("import_module", "__import__", "find_module", "load_module"):
            continue
        target: str | None = None
        if node.args and isinstance(node.args[0], ast.Constant):
            value = node.args[0].value
            if isinstance(value, str):
                target = value
        if target is None:
            findings.append(
                {
                    "kind": "dynamic",
                    "module": None,
                    "lineno": node.lineno,
                    "evidence": f"{name}(...) target not statically resolvable",
                }
            )
        elif target.split(".")[0] not in allowed:
            findings.append(
                {
                    "kind": "dynamic",
                    "module": target,
                    "lineno": node.lineno,
                    "evidence": f"{name}({target!r})",
                }
            )
    return findings, examined


def _runtime_import_audit(subject: Path) -> tuple[list[dict[str, Any]], int, bool]:
    """Import the subject in ``python3 -S`` and read the child's ``sys.modules``.

    ``-S`` removes ``site``, so ``site-packages`` is off the path; ``cwd`` is
    the subject's own directory, so ``sys.path[0]`` for ``-c`` is that
    directory alone. Product paths that ``tests/conftest.py`` injects into the
    pytest process are therefore absent here — which is the whole point, since
    an ``ImportError`` in-process would never fire.
    """
    program = (
        "import json,sys\n"
        "before=set(sys.modules)\n"
        "import %s\n"
        "after=set(sys.modules)\n"
        "allowed=set(sys.stdlib_module_names)|set(sys.builtin_module_names)|{%r}\n"
        "new={n.split('.')[0] for n in after-before}\n"
        "bad=sorted(n for n in new if n not in allowed and not n.startswith('_frozen_'))\n"
        "print(json.dumps({'examined':len(new),'foreign':bad}))\n"
    ) % (subject.stem, subject.stem)

    # DONTWRITEBYTECODE because the child IMPORTS the subject: a cached .pyc
    # lands in the subject's OWN directory, outside every declared root,
    # perturbing the tree this module digests. The audit returns the identical
    # triple either way, so purity costs no fidelity here.
    #
    # AN ALLOWLIST, NOT A STOPLIST. This was `os.environ` MINUS two names, and
    # a stoplist is an enumeration of today's members: LD_PRELOAD,
    # DYLD_INSERT_LIBRARIES, PYTHONSTARTUP and PYTHONBREAKPOINT were all
    # measured surviving into the child, and `-S` reaches none of them --
    # `site` is an interpreter concern, while the dynamic linker acts BEFORE
    # the interpreter starts. Naming what the child NEEDS removes the whole
    # category instead, so a variable nobody has thought of is absent by
    # construction rather than by omission.
    #
    # WHAT THE CHILD NEEDS, MEASURED rather than assumed: nothing at all. The
    # interpreter is invoked by absolute path, so PATH is not consulted for the
    # exec, and the audit returns the identical triple under an empty
    # environment. The four names kept below are LOCATIONS -- where a home
    # directory, a scratch directory or a system root is -- not injection
    # channels, and they are kept so an ordinary stdlib import on a platform
    # that consults one of them still behaves as it does in-process.
    #
    # NOT REACHABLE THROUGH ANY INPUT THIS RUNG ACCEPTS. This is
    # defence-in-depth, and it is written here because the paragraph above
    # frames this construction as hardening; a reader is entitled to find an
    # allowlist behind that word.
    env = {
        name: os.environ[name]
        for name in ("PATH", "HOME", "TMPDIR", "SYSTEMROOT")
        if name in os.environ
    }
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [sys.executable, "-S", "-c", program],
            cwd=str(subject.parent),
            capture_output=True,
            text=True,
            # THE SAME EXPLICIT CODEC as `_run_command`, for the same reason
            # and against the same escape: `UnicodeDecodeError` is a
            # `ValueError` and would pass straight through the
            # `(OSError, subprocess.SubprocessError)` clause below, aborting
            # the observation instead of degrading the source audit. The child
            # prints JSON built from module names, which are the subject's to
            # choose.
            encoding="utf-8",
            errors="replace",
            timeout=SUBPROCESS_TIMEOUT_S,
            env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return [], 0, False

    if completed.returncode != 0:
        return (
            [
                {
                    "kind": "runtime",
                    "module": None,
                    "lineno": None,
                    "evidence": f"pruned-path import failed rc={completed.returncode}",
                }
            ],
            0,
            True,
        )
    try:
        # FAIL CLOSED OVER THE WHOLE READ, not over the parse alone. The two
        # lines below were outside this handler and each carried a defeat the
        # narrow one could not see: a bare scalar payload has no `.get`
        # (`AttributeError`), a non-list `foreign` is not iterable
        # (`TypeError`), and `int()` over a recorded `Infinity` raises
        # `OverflowError` -- an `ArithmeticError`, so neither `ValueError` nor
        # `RecursionError` catches it. The same enumerate-the-exception-types
        # shape that _plane_bounds was already caught by. Every one of them is
        # ONE finding: this probe produced no reading, so it reports NOT
        # AUDITED rather than a number it invented.
        payload = json.loads(
            completed.stdout.strip() or "{}",
            object_pairs_hook=_pairs_without_repeats,
            parse_constant=_refuse_non_finite,
            parse_float=_finite_float,
        )
        findings = [
            {
                "kind": "runtime",
                "module": name,
                "lineno": None,
                "evidence": f"sys.modules[{name!r}]",
            }
            for name in payload.get("foreign", [])
        ]
        examined = payload.get("examined", 0)
    except Exception:  # noqa: BLE001 - a defeated read IS the finding
        return [], 0, False
    # THE SAME DOMAIN AS EVERY OTHER COUNT IN THIS PACKET, checked rather than
    # coerced. `int(...)` accepted `-1` and `"-1"` alike and made each of them
    # this probe's DENOMINATOR; a negative denominator here would have reported
    # D04 as having examined evidence it did not. This value crosses a JSON
    # boundary out of a subprocess, so it is read as a recorded count and not
    # as a number this module computed. Out of domain is NOT AUDITED — the
    # third member is the channel that says so — never a number invented to
    # stand in its place.
    #
    # WHAT THIS FOLD COSTS, DISCLOSED RATHER THAN FIXED. `findings` was built
    # successfully on the lines above and is DISCARDED here, so the packet
    # cannot tell "the probe could not run" (the two returns above, which
    # genuinely have no findings) from "the probe found a foreign import AND
    # recorded a nonsense denominator". Every sibling correction this cycle
    # NAMES its loss on a discrepancy channel instead — `_recorded_count`,
    # `_finding_text`, `_decision` — and this one names it on none.
    #
    # WHY IT IS LEFT AS IT IS, and this is a reasoned acceptance, not an
    # oversight. (1) It is not a fail-open: the third member is False, so
    # `_source_audit` publishes `runtime_audited=False` and D04 degrades. The
    # direction of the error is toward UNMEASURED, never toward OBSERVED.
    # (2) The branch is effectively unreachable. `examined` is not
    # subject-authored the way `filesystem.*.entries` values are: it is
    # produced by the FIXED child program a few lines above as
    # `len(new)` over a set of module names, which is a non-negative `int` by
    # construction, and `_is_recorded_count` accepts every such value. Reaching
    # this line requires the subject to rebind `len` or `json.dumps` inside the
    # child during import — a reach nothing else in this probe is hardened for.
    # (3) Giving it a channel is a BEHAVIOURAL change to a frozen subject and
    # needs an arm that drives it, which the point above says cannot be driven
    # through the public surface. It is therefore recorded here as a known,
    # bounded loss on an unreachable path rather than papered over, and the
    # honest form of the claim is: this return is the ONLY one of the three
    # that throws away a reading it already had.
    if not _is_recorded_count(examined):
        return [], 0, False
    return findings, examined, True


def _source_audit(subject: Path) -> dict[str, Any]:
    digest, _size, _byte_truncated = _sha256_file(subject)
    read = _read_text(subject)
    source = read.text
    failed = {
        "subject_path": str(subject),
        "subject_sha256": digest,
        "static_findings": [],
        "dynamic_findings": [],
        "runtime_findings": [],
        "runtime_audited": False,
        # One reader, one bound: this plane reads one file under
        # MAX_EVIDENCE_BYTES. It carries no record cap and no entry cap, so
        # there is nothing here for a rollup to roll up.
        "byte_truncated": read.byte_truncated,
        "evidence_malformed": True,
        "observation_status": ERROR,
        "_static_examined": 0,
        "_dynamic_examined": 0,
    }
    if source is None:
        return failed
    try:
        tree = ast.parse(source, filename=str(subject))
    except (SyntaxError, ValueError, RecursionError):
        # A source file the parser cannot walk is ERROR, never a clean import
        # boundary. RecursionError is caught for the same reason it is caught
        # in the JSON readers: it is a RuntimeError subclass (CWE-674).
        return failed
    static_findings, static_examined = _static_import_findings(tree)
    dynamic_findings, dynamic_examined = _dynamic_import_findings(tree)
    runtime_findings, runtime_examined, runtime_audited = _runtime_import_audit(subject)
    # A clipped source means the AST covers only part of the file, so an import
    # in the unread tail is invisible: that is UNMEASURED, not a clean boundary.
    if read.byte_truncated or not runtime_audited:
        status = UNMEASURED
    else:
        status = OBSERVED
    return {
        "subject_path": str(subject),
        "subject_sha256": digest,
        "static_findings": static_findings,
        "dynamic_findings": dynamic_findings,
        "runtime_findings": runtime_findings,
        "runtime_audited": runtime_audited,
        "byte_truncated": read.byte_truncated,
        "evidence_malformed": False,
        "observation_status": status,
        "_static_examined": static_examined,
        "_dynamic_examined": dynamic_examined + runtime_examined,
    }


# --------------------------------------------------------------------------
# Private: stdlib closed-schema walk
# --------------------------------------------------------------------------


def _resolve_ref(schema: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    """Resolve a local ``#/$defs/name`` reference; merge sibling keywords."""
    ref = schema.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return schema
    node: Any = root
    for part in ref[2:].split("/"):
        if not isinstance(node, dict) or part not in node:
            return schema
        node = node[part]
    if not isinstance(node, dict):
        return schema
    merged = dict(node)
    for key, value in schema.items():
        if key != "$ref":
            merged[key] = value
    return merged


def _declared_properties(schema: dict[str, Any], root: dict[str, Any]) -> set[str]:
    """Property names this node declares, following ``$ref`` and ``allOf``."""
    resolved = _resolve_ref(schema, root)
    names: set[str] = set(resolved.get("properties", {}) or {})
    for branch in resolved.get("allOf", []) or []:
        if isinstance(branch, dict):
            names |= _declared_properties(branch, root)
    return names


def _walk_document(
    document: Any,
    schema: dict[str, Any],
    root: dict[str, Any],
    pointer: str,
    unknown: list[str],
) -> int:
    """Collect unknown-property pointers; return the number of nodes examined."""
    resolved = _resolve_ref(schema, root)
    examined = 1

    if isinstance(document, dict):
        declared = _declared_properties(resolved, root)
        patterns = resolved.get("patternProperties", {}) or {}
        closed = resolved.get("additionalProperties") is False or (
            resolved.get("unevaluatedProperties") is False
        )
        properties = resolved.get("properties", {}) or {}
        for key in sorted(document):
            child_pointer = f"{pointer}/{key}"
            child_schema: dict[str, Any] | None = None
            if key in properties and isinstance(properties[key], dict):
                child_schema = properties[key]
            else:
                for pattern, sub in patterns.items():
                    if isinstance(sub, dict) and _safe_search(pattern, key):
                        child_schema = sub
                        break
            if child_schema is None:
                # Declared via allOf but with no local subschema to descend
                # into, or genuinely undeclared at a closed node.
                if key not in declared and closed:
                    unknown.append(child_pointer)
                continue
            examined += _walk_document(
                document[key], child_schema, root, child_pointer, unknown
            )
    elif isinstance(document, list):
        item_schema = resolved.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(document):
                examined += _walk_document(
                    item, item_schema, root, f"{pointer}/{index}", unknown
                )
        elif not _admits_array(resolved):
            # AN ARRAY AT A NODE THE SCHEMA SAYS CANNOT BE ONE. `items` is
            # absent, so the old branch descended nowhere and an undeclared
            # field wrapped in a one-element array at an object-typed node was
            # invisible to D01/D02 — while `jsonschema` reported it, so the two
            # planes disagreed and only the external one was right.
            #
            # Each element is closed against THIS node's own schema, which is
            # the only schema in play: the node declares no `items` because it
            # never expected an array. Where the node's type union DOES admit
            # `array` with no `items` — the verbatim-forwarded settings entry —
            # arbitrary content is legal and descending would invent findings
            # the oracle does not share; that residual is disclosed on the
            # `$def` rather than closed here.
            for index, item in enumerate(document):
                examined += _walk_document(
                    item, resolved, root, f"{pointer}/{index}", unknown
                )
    return examined


def _admits_array(schema: dict[str, Any]) -> bool:
    """Whether ``schema`` permits an array instance at its node.

    An absent ``type`` constrains nothing and therefore admits one. Read from
    the schema's own declaration, never from a list of node names.
    """
    declared = schema.get("type")
    if declared is None:
        return True
    if isinstance(declared, list):
        return "array" in declared
    return declared == "array"


def _safe_search(pattern: str, key: str) -> bool:
    try:
        return bool(re.search(pattern, key))
    except re.error:
        return False


def _schema_audit(schema_path: Path, document_path: Path) -> dict[str, Any]:
    """Audit ``document_path`` against ``schema_path`` with stdlib only.

    This is Plane 1. The self-test recomputes the same answer with the real
    ``jsonschema`` library (Plane 2) and the two must agree; neither is
    permitted to be the other's evidence.
    """
    digest, _size, _byte_truncated = _sha256_file(schema_path)
    schema_read = _read_json(schema_path)
    schema = schema_read.document
    document_present = document_path.is_file()
    audit: dict[str, Any] = {
        "schema_path": str(schema_path),
        "schema_sha256": digest,
        "document_path": str(document_path),
        "document_present": document_present,
        "root_unknown_fields": [],
        "composed_unknown_fields": [],
        # Single bound, two readers: this plane reads two files and both are
        # capped by MAX_EVIDENCE_BYTES. Composing two measurements of the SAME
        # cap still names exactly one cap, which is why this is not a rollup.
        "byte_truncated": schema_read.byte_truncated,
        "evidence_malformed": schema_read.malformed,
        "observation_status": UNMEASURED,
        "_examined": 0,
    }
    if not schema or not document_present:
        return audit
    document_read = _read_json(document_path)
    document = document_read.document
    audit["byte_truncated"] = schema_read.byte_truncated or document_read.byte_truncated
    audit["evidence_malformed"] = schema_read.malformed or document_read.malformed
    if not document:
        audit["observation_status"] = ERROR
        return audit

    unknown: list[str] = []
    examined = _walk_document(document, schema, schema, "", unknown)
    # A pointer with exactly one segment is a sibling of the packet root; a
    # deeper pointer was reached only by resolving a $ref out of $defs.
    audit["root_unknown_fields"] = [p for p in unknown if p.count("/") == 1]
    audit["composed_unknown_fields"] = [p for p in unknown if p.count("/") > 1]
    # A clipped schema or a clipped document means the closure walk covered
    # only part of its subject; an unknown field may sit in the unread tail.
    if audit["evidence_malformed"]:
        audit["observation_status"] = ERROR
    elif audit["byte_truncated"]:
        audit["observation_status"] = UNMEASURED
    else:
        audit["observation_status"] = OBSERVED
    audit["_examined"] = examined
    return audit


# --------------------------------------------------------------------------
# Private: evidence readers
# --------------------------------------------------------------------------


def _bounded_evidence(
    path: Path, record_counter: Callable[[Path], _EvidenceCount] | None
) -> dict[str, Any]:
    """Bounded metadata for one evidence file, with every bound flagged.

    ``byte_truncated`` is the BYTE bound (:data:`MAX_EVIDENCE_BYTES`) and
    NOTHING else; ``record_truncated`` is the RECORD bound
    (:data:`MAX_STREAM_RECORDS`) and NOTHING else; ``unparsable_records``
    counts lines the reader could not decode. The three are separate because
    they degrade differently, and because one flag standing for three bounds
    is how a bound gets lost.

    The byte flag is taken from :func:`_sha256_file` and from the record
    counter and OR-ed. Both operands are :data:`MAX_EVIDENCE_BYTES` -- the same
    cap measured by two independent readers over the same file -- so the result
    still names exactly one bound. They must always agree; OR-ing is the
    conservative resolution if they ever do not, and
    ``test_byte_bounds_are_enforced_in_bytes_and_every_reader_agrees`` fails
    loudly on the disagreement rather than letting it pass silently.

    ``observation_status`` can never be ``OBSERVED`` for clipped, undecodable
    or unreadable evidence: incomplete-but-well-formed is ``UNMEASURED`` (we
    did not measure the whole subject); undecodable is ``ERROR`` (the reader
    was defeated, which is a failure and not a partial measurement); and a file
    that is PRESENT but that no reader could open is the defeated-reader case
    too, so it is ``ERROR`` and therefore strictly worse than the same file
    being ABSENT. ``amendment:208``.
    """
    present = path.is_file()
    digest, size, sha_truncated = _sha256_file(path) if present else (None, None, False)
    # PRESENT BUT UNREADABLE IS A DEFEATED READER, not a partial measurement,
    # and it is measured HERE because no other channel records it.
    # `_sha256_file` returns `(None, None, False)` on ANY OSError and
    # `_read_text` returns `None` with no flag at all, so branching on
    # `path.is_file()` alone made an UNREADABLE file report `present: true`,
    # `sha256: null` and OBSERVED while the SAME file merely ABSENT reported
    # UNMEASURED. Strictly less evidence read strictly cleaner, contradicting
    # `amendment:208`. Not chmod-specific: a TOCTOU unlink between `is_file()`
    # and `open`, EIO, or fd exhaustion all reach it.
    unreadable = present and digest is None
    counted = (
        record_counter(path)
        if (present and record_counter)
        else _EvidenceCount(None, False, False, 0)
    )
    byte_truncated = sha_truncated or counted.byte_truncated
    # A DECLARED ROLLUP, used only to pick this plane's status: "did any bound
    # clip this file". Its operands each name exactly one bound and it is not
    # published, so no reader can mistake it for a per-bound answer.
    any_bound_truncated = byte_truncated or counted.record_truncated
    if not present:
        status = UNMEASURED
    elif unreadable or counted.unparsable > 0:
        status = ERROR
    elif any_bound_truncated:
        status = UNMEASURED
    else:
        status = OBSERVED
    return {
        "path": str(path),
        "present": present,
        "bytes": size,
        "sha256": digest,
        "record_count": counted.count,
        "byte_truncated": byte_truncated,
        "record_truncated": counted.record_truncated,
        "unparsable_records": counted.unparsable,
        "observation_status": status,
    }


def _count_jsonl(path: Path) -> _EvidenceCount:
    """Record count for a JSONL evidence file, one slot per bound.

    Both of :func:`_read_jsonl`'s truncation flags are forwarded to the slot
    that names them. Collapsing them here is what made a byte-clipped file
    report ``record_truncated=True``.
    """
    read = _read_jsonl(path)
    return _EvidenceCount(
        len(read.records), read.byte_truncated, read.record_truncated, read.unparsable
    )


def _decision_from_exit(exit_code: Any, stdout_bytes: Any) -> str | None:
    """The receipt decision DERIVED from its two numbers, or ``None`` when unreadable.

    THE ONLY PLACE A RECEIPT DECISION IS DECIDED, on both sides of the packet
    boundary: :func:`_debug_line_receipts` derives it from bytes it just read,
    and :func:`reconcile` re-derives it from the packet a caller hands back.
    A second copy of this arithmetic in ``reconcile`` would be a second thing
    to keep in step; NO copy there was worse — D09 read ``join["decision"]``,
    a sibling field of the ``exit_code`` it is about, and believed it.
    A packet recording ``{"exit_code": 2, "decision": "SILENT"}`` was clean, and
    the reverse manufactured a non-zero finding out of ``exit_code`` 0.

    ``exit 0`` with empty stdout means the hook made NO decision (``SILENT``),
    not that it approved the call; conflating those is the defect M09 injects.

    ``bool`` is excluded FIRST on both numbers. ``isinstance(True, int)`` is
    True and ``True != 0`` is False, so ``"exit_code": true`` would otherwise
    rank as a clean zero exit — the same subclass trap D12 names for ``mode``.
    ``None`` here is not "clean": it is "this reader cannot rank the exit
    evidence", and every caller degrades on it.

    THE TWO NUMBERS HAVE DIFFERENT DOMAINS, and reading them through one guard
    is what let a NEGATIVE byte count derive an outcome. ``stdout_bytes`` is a
    ``$defs/byte_count`` — ``integer, minimum: 0`` — so it goes through
    :func:`_is_recorded_count`. Before this cycle it carried the TYPE half of
    that guard and not the VALUE half, and ``_decision_from_exit(0, -1)``
    returned ``"RESPONDED"``: a hook that wrote a negative number of bytes was
    ranked as having answered. ``-1`` was caught only INCIDENTALLY, on the runs
    where the derived value happened to contradict the recorded ``decision``;
    isolated so the two agreed, D09 reported ``OBSERVED`` with zero
    discrepancies for ``stdout_bytes`` of ``-1`` and ``-99`` alike.

    ``exit_code`` KEEPS THE TYPE GUARD ALONE, deliberately. A negative exit
    code is in domain: it is how a terminating signal is encoded, and ``-9``
    (SIGKILL) and ``-15`` (SIGTERM) must keep ranking ``NONZERO`` — a hook the
    kernel killed is the loudest hidden-non-zero D09 exists to find. Widening
    the byte-count guard onto its sibling field by analogy would have converted
    that finding into an unrankable read. Verified after the change:
    ``_decision_from_exit(-9, 0)`` and ``_decision_from_exit(-15, 0)`` are both
    ``"NONZERO"``.
    """
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        return None
    if exit_code != 0:
        return "NONZERO"
    if not _is_recorded_count(stdout_bytes):
        return None
    return "SILENT" if stdout_bytes == 0 else "RESPONDED"


def _debug_receipts_claimed(line: str) -> int:
    """How many hook receipts ``line`` CLAIMS to carry, over EVERY claim channel.

    THE DENOMINATOR OF THE RESIDUE, and it is deliberately a COUNT rather than
    a yes/no. Asking only "is this a receipt line" is what let a SECOND receipt
    merged onto an already-parsing line vanish: the line was a receipt line,
    one record came off it, and no channel could express that a second had been
    carried.

    THREE CHANNELS, AND THE CLAIM IS THE LARGEST. Each answers "how many
    receipts are on this line" from a different direction, and each is blind
    somewhere the others are not:

    * :data:`_DEBUG_RECEIPT_LEXEME_RE` counts IDENTITIES (``tool_use_id=``). A
      receipt whose fields are permuted carries an id and no readable exit
      pair, so this channel counts it where the exit channel reads zero.
    * :data:`_DEBUG_RECEIPT_EXIT_RE` counts DECISIONS (``exit=``) — the unit
      D09 decides on. A second ``exit=`` pair appended to a receipt that
      already carries one brings no second id, so this channel counts it where
      the identity channel reads one.
    * :data:`_DEBUG_HOOK_RE` itself counts what THIS READER matched. It is what
      keeps the claim from ever being smaller than the reading, whatever the
      other two gates decide.

    Taking the MINIMUM of two claims — which reading only the identity channel
    silently did — is a denominator the subject chooses. Taking the maximum
    means a receipt is lost only when EVERY channel agrees it was never there.

    THE SHAPE GATE CANNOT ZERO A LINE THIS READER ALREADY READ, and that
    closes an asymmetry that would otherwise have defeated the exit channel
    above. :data:`_DEBUG_HOOK_RE` matches ``hook`` with no word boundary, so it
    reads receipts out of ``prehook``; :data:`_DEBUG_RECEIPT_SHAPE_RES`
    requires ``\bhook\b`` and does not claim them. On the old identity-only
    denominator that asymmetry was fail-CLOSED — the record was still produced
    and D09 still named its exit — but with a residue the gate can zero, a
    ``prehook`` line carrying two exit pairs would have read one and claimed
    none. The gate is therefore an OR with the reader's own match, not an
    unconditional veto: a line no channel claims is still declined, so
    ordinary log lines do not start over-firing.
    """
    read_here = len(_DEBUG_HOOK_RE.findall(line))
    claimed_by_shape = all(
        pattern.search(line) for pattern in _DEBUG_RECEIPT_SHAPE_RES
    )
    if not claimed_by_shape and read_here == 0:
        return 0
    return max(
        len(_DEBUG_RECEIPT_LEXEME_RE.findall(line)),
        len(_DEBUG_RECEIPT_EXIT_RE.findall(line)),
        read_here,
    )


def _debug_line_receipts(line: str) -> tuple[list[dict[str, Any]], int]:
    """Every hook receipt record on ``line``, and how many this reader lost.

    THE ONE PREDICATE BOTH DEBUG READERS RUN, so :func:`_count_lines` and
    :func:`_parse_debug_hooks` can never disagree about what a line carried.
    :func:`_debug_unparsable` is this function's second member; the records are
    its first.

    RESIDUE, NOT FIRST-MATCH. The loss count is
    ``claimed - len(records)``: however many receipts the line claims across
    every channel :func:`_debug_receipts_claimed` reads, minus however many
    this reader actually read off it.

    THE DEMONSTRATED INVARIANT, stated as what is DRIVEN rather than as what
    the implementation does: for every arrangement in the driven corpus —
    N whole receipts merged onto one line for N in 1..4, a second bare
    ``exit=``/``stdout_bytes=`` pair appended to a receipt in EITHER order, a
    receipt whose fields are permuted, and a receipt whose numbers defeat
    ``int()`` — the number of ``exit=`` decisions an ordinary
    ``grep -o 'exit=[0-9]*'`` reports off the line is accounted for, either as
    a record or in the residue. An earlier revision of this docstring claimed
    the ``finditer`` change alone "closes N-receipts-per-line for EVERY N".
    That claim named a MECHANISM and was false of the behaviour: the
    denominator counted identities while D09 decides on exits, so appending a
    second ``exit=`` pair to a receipt that already carried one read one
    record, claimed one receipt, left residue zero, and hid the second
    decision. It is withdrawn.

    Before any of this, ``re.search`` returned at most one match per line and
    the shape gate answered yes/no, so ``hook Pre ... exit=0 ... hook Pre ...
    exit=2 ...`` on ONE line produced one record, no residue, and a non-zero
    hook exit that ``grep -o 'exit=[0-9]*'`` could see was invisible to D09.
    The sibling JSONL reader was already fail-closed on the identical attack
    (two records on one line raise "Extra data"); the debug reader was the
    outlier.

    Ordinary log lines are not claimed: see :data:`_DEBUG_RECEIPT_SHAPE_RES`
    for why the claim needs ``tool_use_id`` and not merely the word ``hook``.
    """
    records: list[dict[str, Any]] = []
    for match in _DEBUG_HOOK_RE.finditer(line):
        numbers = _debug_receipt_numbers(match)
        if numbers is None:
            # A RECEIPT WHOSE NUMBERS DEFEAT THE READER. Dropped from the
            # records and left in the residue below, so it reaches the plane's
            # `unparsable_records` and forces ERROR rather than vanishing.
            continue
        exit_code, stdout_bytes = numbers
        # ONE DECIDER, shared with the recomputation `reconcile` runs over the
        # emitted packet. A second copy of this arithmetic there is what would
        # let a hand-built packet's `decision` field be believed against its
        # own exit evidence.
        decision = _decision_from_exit(exit_code, stdout_bytes)
        if decision is None:  # pragma: no cover - `numbers` is two ints here
            continue
        records.append(
            {
                "tool_use_id": match.group("tool_use_id"),
                "hook_event_name": match.group("event"),
                "exit_code": exit_code,
                "stdout_bytes": stdout_bytes,
                "decision": decision,
            }
        )
    # Clamped at zero: a line may read MORE records than it claims by lexeme
    # (`_DEBUG_HOOK_RE` needs `tool_use_id=` too, so it cannot, but the clamp
    # is what keeps that a measured coincidence rather than an assumption a
    # widened regex would inherit as a NEGATIVE unparsable count).
    return records, max(_debug_receipts_claimed(line) - len(records), 0)


def _debug_text_receipts(text: str) -> tuple[list[dict[str, Any]], int]:
    """Every hook receipt in ``text``, and every DECISION it fails to account for.

    THE UNIT OF THE RESIDUE IS THE FILE, because the LINE is not a unit the
    subject is unable to choose. :func:`_debug_line_receipts` moved the
    residue's KIND from identities to decisions and left its UNIT untouched,
    and the value then reached D09 through the sibling carrier: the line
    boundary itself.

    ``str.splitlines()`` honours TEN separators — ``\\n \\r \\r\\n \\v \\f
    \\x1c \\x1d \\x1e \\x85 \\u2028 \\u2029`` — while ``grep`` and ``wc -l``
    honour one. ``'a\\rb'.splitlines()`` is two lines and carries zero newline
    bytes. ``command=`` is written by the candidate into its own settings
    overlay (``ladder:282``), so a candidate spelling it
    ``c exit=0 stdout_bytes=0<SEP>pad`` splits the harness-written receipt in
    two: fragment one is a syntactically perfect receipt (one record, one
    claim, residue zero) and the real ``exit=2`` lands on fragment two, which
    carries no ``hook``, no ``tool_use_id=`` and no reader match — so it is
    claimed by NOTHING and every per-line channel agrees it was never there.
    Measured on all five of ``\\n``, ``\\r``, ``\\v``, ``\\x85`` and
    ``\\u2028``: D09 reported the same discrepancy count as the clean control
    while ``grep -o 'exit=[-0-9]*'`` over the same bytes reported one more.

    ENUMERATING THE SEPARATORS WOULD BE THE INSTANCE, NOT THE CLASS: a
    separator set is a list of members, and ``splitlines()`` is free to grow
    one. The whole FILE is asked instead, over the same ``exit=`` channel D09
    decides on, and whatever no record and no per-line residue accounts for is
    counted here. That number is folded into the ONE ``unparsable_records``
    channel :func:`_count_lines` already publishes, so an unaccounted decision
    degrades the debug plane to ``ERROR`` through the door that already exists
    rather than through a second one nobody reads.

    CLAMPED AT ZERO for the reason :func:`_debug_line_receipts` states: a
    negative here would be a per-line channel over-claiming, which is already
    reported through the residue it produced, and a negative unaccounted count
    would let one line's over-claim CREDIT another line's loss.

    OVER-FIRING IS THE DIRECTION THIS FAILS IN, and it is the same one
    :data:`_DEBUG_RECEIPT_SHAPE_RES` already accepts: an ordinary log line
    carrying ``exit=0`` for something that is not a hook is counted as
    unaccounted and drives the plane to ``ERROR``. Fail-closed, and pinned as
    intended.
    """
    records: list[dict[str, Any]] = []
    line_residue = 0
    for line in text.splitlines():
        line_records, line_lost = _debug_line_receipts(line)
        records.extend(line_records)
        line_residue += line_lost
    unaccounted = max(
        len(_DEBUG_RECEIPT_EXIT_RE.findall(text)) - len(records) - line_residue, 0
    )
    return records, line_residue + unaccounted


def _debug_unparsable(text: str) -> int:
    """Hook receipts in ``text`` that :data:`_DEBUG_HOOK_RE` could not read.

    THE MALFORMED CHANNEL FOR THE DEBUG LOG, symmetric with the ``unparsable``
    field :func:`_read_jsonl` reports for the stream. A record lost upstream of
    the decision fires no bound, so the plane still reads clean while a
    non-zero hook exit is invisible. A line the reader was defeated by is
    evidence about the reader, and a caller must be able to see it.

    The arithmetic — per-line residue and the file-level unaccounted count, and
    why the second unit is needed at all — lives in
    :func:`_debug_text_receipts`, which this function and
    :func:`_parse_debug_hooks` both call so the two debug readers cannot
    disagree about what was lost.
    """
    return _debug_text_receipts(text)[1]


def _debug_receipt_numbers(match: re.Match[str]) -> tuple[int, int] | None:
    """The two integers a matched receipt records, or ``None`` when defeated.

    MATCHING IS NOT READING, and that gap is the whole reason this exists.
    ``_DEBUG_HOOK_RE`` captures ``exit`` as ``-?\\d+``, so a receipt writing
    5,000 digits MATCHES and then defeats ``int()``: CPython refuses a decimal
    string past ``sys.get_int_max_str_digits()`` (4300 digits). The symbol
    named here used to be ``sys.int_info.str_digits_check_threshold``, which is
    640 and is the LOWER BOUND the limit may be configured to, not the limit:
    ``int('9' * 641)`` succeeds. The parenthesised number and the behaviour
    were right; only the symbol was wrong. The
    ``ValueError`` propagated out of ``capture()`` and aborted the whole
    observation with ZERO packet bytes, which ``_cli`` then reported on the arm
    reserved for ARGV refusals — a subject-induced reader defeat attributed to
    the operator.

    It lives HERE, beside :func:`_debug_unparsable`, so the two debug readers
    cannot disagree about which lines were lost: counting the defeat in
    :func:`_parse_debug_hooks` alone would have left ``_count_lines`` — the
    reader that fills the debug plane's ``unparsable_records`` — still calling
    the line readable, and the plane would have reported OBSERVED over a
    receipt nobody could read.
    """
    try:
        return int(match.group("exit")), int(match.group("stdout_bytes"))
    except ValueError:
        return None


def _count_lines(path: Path) -> _EvidenceCount:
    """Non-blank line count for the debug log, one slot per bound.

    ``record_truncated`` is a hard ``False`` here, and that is a measurement
    rather than a default: this counter applies no record cap at all, so
    :data:`MAX_STREAM_RECORDS` cannot have clipped its result. It reads every
    line inside the byte cap. Passing the byte flag into the record slot --
    which this function previously did -- made the debug plane claim the
    record cap had fired on a log that has no record cap.

    The fourth slot is NOT a hard zero: it carries :func:`_debug_unparsable`,
    so a receipt this module could not decode degrades the debug plane to
    ``ERROR`` through the same ``unparsable_records`` key the stream plane
    already publishes. Leaving it at zero -- which this function previously did
    -- gave the debug plane no malformed channel at all.
    """
    read = _read_text(path)
    if read.text is None:
        return _EvidenceCount(None, False, False, 0)
    return _EvidenceCount(
        len([ln for ln in read.text.splitlines() if ln.strip()]),
        read.byte_truncated,
        False,
        _debug_unparsable(read.text),
    )


class _DebugRead(NamedTuple):
    """Debug-log hook records, the BYTE bound, and the lines it could not read.

    There is no record bound on this reader, so there is no record field to
    carry. A field that would always be ``False`` at this layer is left out
    rather than invented; :func:`_count_lines` reports the record slot the
    packet schema requires for the same file.

    ``unparsable`` is NOT a bound and is not a truncation flag: it counts
    receipts this module was DEFEATED by, matching :class:`_JsonlRead`'s field
    of the same name. Without it this reader could come up short in a way no
    field expressed, which is how a bound goes dark.
    """

    records: list[dict[str, Any]]
    byte_truncated: bool
    unparsable: int


def _parse_debug_hooks(path: Path) -> _DebugRead:
    """Hook lifecycle records from the ``--debug-file`` log.

    ``decision`` is derived, never taken from the hook: exit 0 with empty
    stdout means the hook made NO decision (``SILENT``), not that it approved
    the call. Conflating those two is the defect mutant M09 injects.

    The byte bound is reported, because a hook that exited non-zero past the
    cap is exactly the record D09 exists to find.

    A receipt this reader is defeated by is a DROP, and a drop is only safe for
    a line that is not a receipt. Both the records and the count of what was
    lost come from :func:`_debug_line_receipts`, the ONE predicate
    :func:`_debug_unparsable` also calls, so a receipt lost here degrades the
    plane instead of vanishing from it.

    THE LINE IS NOT THE RECORD. Every receipt on a line is read, not the first
    one, because ``re.search`` returns at most one match per line: merging a
    non-zero receipt onto a line that already carried a benign one left D09
    with zero discrepancies while ``grep -o 'exit=[0-9]*'`` on the same bytes
    reported the ``exit=2``.

    AND THE LINE IS NOT THE UNIT EITHER: :func:`_debug_text_receipts` asks the
    whole FILE what it accounts for, because the line boundary is a value the
    candidate authors through ``command=``.
    """
    read = _read_text(path)
    if read.text is None:
        return _DebugRead([], False, 0)
    records, unparsable = _debug_text_receipts(read.text)
    return _DebugRead(records, read.byte_truncated, unparsable)


def _hook_lifecycle(run_root: Path, debug_file: Path) -> dict[str, Any]:
    stream_read = _read_jsonl(run_root / EVIDENCE_STREAM)
    debug_read = _parse_debug_hooks(debug_file)
    stream_records = stream_read.records
    debug_records = debug_read.records

    # TWO IDENTITY SETS, RECORDED SEPARATELY. They are different observations
    # of different things: `receipt_ids` are the ids the DEBUG LOG issued a
    # hook receipt for (and so the only ids whose exit code was observed at
    # all), while `stream_hook_event_ids` are the ids the STREAM says a hook
    # fired for. Collapsing them into one set before anything is compared lets
    # one mask the other, so they are kept apart here and compared in
    # `hook_events_without_receipt`. Driven both ways by
    # `test_a_deleted_hook_receipt_cannot_be_masked_by_a_surviving_one`.
    #
    # ONE PASS OVER THE STREAM, AND IT DECLINES NOTHING. Two sites here used to
    # filter on `isinstance(tool_use_id, str)` — a `continue` in this loop and
    # again in the `hook_event` set comprehension — so a ghost hook event
    # evaded D09 by changing the TYPE of its id: with `"toolu_GHOST"` D09 named
    # a receiptless hook event, with `9999` the discrepancy vanished and the
    # packet read clean. The membership test below is on the RECORD TYPE, and
    # the identity is RENDERED by `_recorded_as_text` rather than filtered on,
    # so an id of any type still joins, still misses its receipt, and is still
    # named. The `outcome` field is rendered for the same reason: coercing a
    # non-string outcome to `None` made it indistinguishable from a record that
    # published no outcome at all.
    #
    # THE DISCRIMINATOR IS RENDERED TOO, and that was the door left open when
    # the identity was closed: the fix went to the two fields the reported bug
    # used and not to `type`, the discriminator on the same record in the same
    # loop. A ghost `hook_event` recording `"type": ["hook_event"]` or
    # `"type": 7` left this loop through the `continue` below, reached neither
    # the malformed channel nor the named-discrepancy channel, and the packet
    # read clean — the identical shape, one field over.
    #
    # Two separate answers, because the two exclusions are different:
    #
    # * A discriminator the RENDERING CHANGED is a value this reader cannot
    #   rank against a vocabulary written in strings. It is NAMED and degrades
    #   the plane: the record's lifecycle claim is UNMEASURED, not absent. The
    #   test is `rendered != raw`, which is a comparison of the rendering
    #   against the recording rather than a type test — no type is enumerated.
    # * A discriminator that IS a string and simply names another record type
    #   (`system`, `result`, or an unknown one) is correctly declined. Every
    #   such decline is COUNTED and published, so declining can never be
    #   invisible in the packet even when it is right.
    stream_outcomes: dict[str, str | None] = {}
    stream_ids: set[str] = set()
    stream_hook_event_ids: set[str] = set()
    # THE RECEIPT JOIN IS A MULTISET, KEYED ON THE PAIR. Both halves of that
    # sentence are corrections, and the second one is the one three successive
    # fixes moved past: the key went bare id -> `(id, event)` pair -> and the
    # comparison stayed A SET DIFFERENCE the whole way. A set difference
    # structurally cannot express "two events, one receipt", so the ordinary
    # settings shape — TWO hooks both registered on `PreToolUse`, which is one
    # `(id, "PreToolUse")` pair twice — absorbed the deletion of one receipt
    # exactly as the bare-id set had absorbed a `PostToolUse`: `{(T,Pre)} -
    # {(T,Pre)}` is empty however many times each side wrote it. Deleting the
    # ONE non-zero receipt of the pair produced a packet with zero
    # discrepancies, byte-identical to a run carrying one event and one
    # receipt. `Counter` subtraction is by COUNT, so the same deletion is named
    # for every multiplicity, not merely for two.
    #
    # `stream_hook_event_ids` stays a bare-id set because D08 asks a DIFFERENT
    # question — does every `tool_use` have a lifecycle record from EITHER
    # source — and for that question a `PostToolUse` on a known id is a
    # partner, not a second obligation. Keying D08 on the pair would report
    # every hook event as an orphan.
    stream_hook_events: Counter[tuple[str, str]] = Counter()
    unrankable_record_types: list[str] = []
    non_lifecycle_records = 0
    for position, record in enumerate(stream_records):
        raw_type = record.get("type")
        record_type = _recorded_as_text("type", raw_type)
        if record_type != raw_type:
            unrankable_record_types.append(
                f"stream record at index {position} records a lifecycle "
                f"discriminator this reader cannot rank: {raw_type!r}"
            )
        if record_type not in _LIFECYCLE_RECORD_TYPES:
            non_lifecycle_records += 1
            continue
        identity = _recorded_as_text("tool_use_id", record.get("tool_use_id"))
        if record_type == "tool_use":
            stream_ids.add(identity)
            outcome = record.get("outcome")
            stream_outcomes[identity] = (
                None if outcome is None else _recorded_as_text("outcome", outcome)
            )
        else:
            stream_hook_event_ids.add(identity)
            # RENDERED, not filtered: the event name is subject-authored, and
            # a record whose `hook_event_name` is `7` or `["PreToolUse"]` must
            # still carry a receipt obligation rather than pairing itself with
            # a receipt by defeating the comparison. `_recorded_as_text` is
            # injective over `repr`, and no debug receipt can name a rendered
            # identity — `_DEBUG_HOOK_RE` captures `event` as `[A-Za-z]+`.
            stream_hook_events[
                (
                    identity,
                    _recorded_as_text("hook_event_name", record.get("hook_event_name")),
                )
            ] += 1

    receipt_ids = {rec["tool_use_id"] for rec in debug_records}
    # The debug side of the SAME key, and the same MULTISET. Both members come
    # from `_DEBUG_HOOK_RE`, so both are strings and neither needs rendering.
    receipt_events: Counter[tuple[str, str]] = Counter(
        (rec["tool_use_id"], rec["hook_event_name"]) for rec in debug_records
    )

    joins: list[dict[str, Any]] = []
    for record in debug_records:
        joins.append(
            {
                "tool_use_id": record["tool_use_id"],
                "hook_event_name": record["hook_event_name"],
                "exit_code": record["exit_code"],
                "stdout_bytes": record["stdout_bytes"],
                "decision": record["decision"],
                "stream_outcome": stream_outcomes.get(record["tool_use_id"]),
                "observation_status": (
                    OBSERVED if record["tool_use_id"] in stream_ids else UNMEASURED
                ),
            }
        )

    # The orphan set is a SYMMETRIC DIFFERENCE over a DIFFERENT question:
    # does every `tool_use` in the stream have a lifecycle record from EITHER
    # source, and vice versa. For that question the union of the two identity
    # sets is the right operand -- a tool call witnessed by a stream
    # `hook_event` does have a lifecycle partner. It can say "in the stream but
    # not the hook log" and "in the hook log but not the stream"; it cannot say
    # "in neither, because the reader stopped at the cap". So when the evidence
    # was clipped, the plane itself degrades — the decision does not get to
    # read a clean orphan set off an incomplete input.
    lifecycle_ids = receipt_ids | stream_hook_event_ids
    orphans = sorted((stream_ids - lifecycle_ids) | (lifecycle_ids - stream_ids))
    # And this is the question the union CANNOT answer, which is why it is
    # computed and published separately: a hook the stream says fired, for
    # which no receipt exists, has NO OBSERVED EXIT CODE. Its absence is not
    # silence -- it is an unmeasured hook outcome, and D09 is what refuses to
    # call that clean. One surviving benign receipt keeps `joins` populated,
    # so a count of receipts can never stand in for this comparison.
    #
    # THE DIFFERENCE IS A MULTISET SUBTRACTION over (id, event) PAIRS, taken in
    # BOTH DIRECTIONS, and then projected back onto ids for publication.
    #
    # THE KEY WAS NEVER THE PROBLEM. This comparison has been "fixed" three
    # times -- bare id, then (id, event) pair, then the pair again -- and every
    # one of those fixes moved the KEY while leaving the KIND of comparison a
    # SET DIFFERENCE. A set difference structurally cannot express "two events,
    # one receipt": `{(T,Pre)} - {(T,Pre)}` is empty however many times each
    # side wrote it. Two hooks registered on `PreToolUse` for one tool call is
    # the ORDINARY settings shape, so deleting one of their two receipts
    # produced a packet with zero discrepancies and an empty receiptless list
    # -- byte-identical to a run carrying one event and one receipt.
    #
    # `Counter.__sub__` keeps only positive counts, so `missing_events` is what
    # the stream claims and the receipts do not cover, ONE ENTRY PER UNCOVERED
    # EVENT, for every multiplicity rather than for two.
    #
    # SURPLUS IS PUBLISHED TOO, and it is not the same fact reached from the
    # other side. A receipt with no stream event is a hook the stream failed to
    # record; a one-directional difference calls that clean, so a subject can
    # delete stream events instead of receipts and reach the same silence
    # through the opposite door. Both lists carry MULTIPLICITY -- an id repeats
    # once per uncovered unit -- so the extent of the disagreement survives
    # into the packet, while the published shape stays a list of ids so the id
    # a reader must chase is not buried in a composite string.
    missing_events = stream_hook_events - receipt_events
    surplus_receipts = receipt_events - stream_hook_events
    hook_events_without_receipt = sorted(
        identity
        for (identity, _event), count in missing_events.items()
        for _ in range(count)
    )
    receipts_without_hook_event = sorted(
        identity
        for (identity, _event), count in surplus_receipts.items()
        for _ in range(count)
    )
    # ``any_bound_truncated`` is a DECLARED ROLLUP, not a bound: the ``any``
    # segment in the name says so, and it answers "was any input to this plane
    # clipped by any bound". It is composed HERE, at the site that wants the
    # rollup, out of three operands that each name exactly one bound. No
    # per-bound detail is destroyed by composing it -- the ``stream`` and
    # ``debug`` bounded_evidence planes publish ``byte_truncated`` and
    # ``record_truncated`` separately for these same two files.
    any_bound_truncated = (
        stream_read.byte_truncated
        or stream_read.record_truncated
        or debug_read.byte_truncated
    )
    # BOTH readers' malformed channels, OR-ed. The debug side was missing
    # until cycle 20: a receipt `_DEBUG_HOOK_RE` could not read was dropped by
    # `_parse_debug_hooks`, no bound fired, and this plane reported OBSERVED
    # with a non-zero hook exit invisible to D09 -- the same fail-open shape as
    # a record lost past a cap, reached through a different door.
    malformed = stream_read.unparsable > 0 or debug_read.unparsable > 0
    if malformed:
        status = ERROR
    elif any_bound_truncated:
        status = UNMEASURED
    else:
        status = OBSERVED if (stream_records or debug_records) else UNMEASURED
    # THE SAME NESTED-STATUS FOLD the filesystem plane performs, and for the
    # same reason. Each join publishes its own `observation_status`, which is
    # UNMEASURED when the debug receipt's `tool_use_id` has no `tool_use`
    # record in the stream -- that join's stream side was never measured. The
    # id also reaches D08 as an orphan discrepancy, but D08 and D09 read
    # `hooks["observation_status"]`, never `joins[i]["observation_status"]`,
    # so without this fold a plane holding a self-declared-unmeasured member
    # would report OBSERVED.
    status = _worst([status] + [join["observation_status"] for join in joins])
    # A record whose discriminator this reader could not rank never entered
    # `stream_ids` or `stream_hook_event_ids`, so both the orphan set and the
    # receiptless set were computed over strictly less evidence than the
    # subject recorded. The plane says so rather than reporting OBSERVED.
    if unrankable_record_types:
        status = _worst([status, UNMEASURED])
    return {
        "joins": joins,
        "orphan_tool_use_ids": orphans,
        "hook_events_without_receipt": hook_events_without_receipt,
        # THE OTHER DIRECTION OF THE SAME SUBTRACTION, published rather than
        # folded into the list above: which side is short is the whole content
        # of the disagreement, and a reader who cannot tell them apart cannot
        # tell "the stream under-recorded" from "a receipt was deleted".
        "receipts_without_hook_event": receipts_without_hook_event,
        "unrankable_record_types": sorted(unrankable_record_types),
        # PUBLISHED, not merely used: every record this join declined is
        # counted here, so appending a record that the vocabulary declines for
        # ANY reason — including a string type nobody has heard of — moves a
        # number in the packet. A decline that moves nothing is a decline a
        # third party recomputing from the raw bytes cannot see.
        "non_lifecycle_record_count": non_lifecycle_records,
        "any_bound_truncated": any_bound_truncated,
        "evidence_malformed": malformed,
        "observation_status": status,
        "_stream_id_count": len(stream_ids),
    }


def _settings_provenance(
    run_root: Path, settings_overlay: Path, setting_sources: Iterable[str]
) -> dict[str, Any]:
    read = _read_json(run_root / EVIDENCE_SETTINGS)
    document = read.document
    # THE THIRD MEMBER IS PUBLISHED, not discarded. Bound to a throwaway, an
    # overlay of MAX_EVIDENCE_BYTES + 50,000 yielded a PREFIX digest in
    # `overlay_sha256` with this plane's `byte_truncated` — which names
    # `settings-sources.json`, a DIFFERENT file — reading False and the plane
    # reading OBSERVED. Every bound that clips published output carries its own
    # flag; the overlay is a separate output and gets a separate flag.
    overlay_digest, _size, overlay_byte_truncated = _sha256_file(settings_overlay)

    # FORWARDED VERBATIM. There is no normaliser here any more, and its absence
    # IS the fix. The previous one dropped every entry that was not a dict with
    # a string `path`, and coerced a non-string `sha256` to `None`. Both losses
    # happened on the `capture()` route, UPSTREAM of `_settings_by_path` — the
    # guard added specifically to NAME these entries — so that guard was
    # unreachable from the route the smoke command runs and only ever fired for
    # a caller who built the plane in memory. The coercion was worse than the
    # drop: two DISTINCT non-string digests both became `None`, `None != None`
    # is False, the mismatch disappeared, and the emitted packet recorded
    # `"sha256": null` where the subject had written `["AAA"]` while staying
    # schema-valid — so the external `jsonschema` oracle could not see the
    # laundering either.
    #
    # With nothing typed here, `_settings_by_path` is the SINGLE decider and it
    # is reached identically through both doors: the same malformed entry gives
    # the same answer whether it arrives as bytes through `capture()` or as an
    # object through `reconcile()`. The schema pays for this — `declared` and
    # `observed` are `$defs/recorded_settings_list`, deliberately unconstrained
    # — and the compensating control is stronger than the closure it replaces:
    # a schema rejection says only that the packet is invalid, while
    # `_settings_by_path` names WHICH entry and WHY, in a channel that degrades
    # D06 and D07.
    # An ABSENT key records nothing and declines nothing, so it defaults to the
    # empty list. A key that is PRESENT is forwarded exactly as written, list
    # or not — that is the difference between "the subject recorded no sources"
    # and "the subject recorded something this module cannot use".
    declared = document.get("declared", [])
    observed = document.get("observed", [])
    # FORWARDED VERBATIM, FOR THE REASON THE ENTRY LISTS ABOVE ARE. The
    # previous reader substituted the observer's OWN `setting_sources`
    # argument whenever the document's value was not a list, and coerced every
    # member with `str()`. Both were the observer answering a question about
    # the subject, and the substitution was worse than the coercion: it
    # PRESENTED the caller's list as the subject's record.
    #
    # THE MEASURED CONSEQUENCE, and it ran the other way too. With
    # `--setting-sources user,project,local` on the argv and a
    # `settings-sources.json` recording `["user","bogus"]`, the emitted plane
    # published `["user","bogus"]` — the subject writing its own answer into
    # the field a decision is NAMED for — while every deviation of the argv
    # from the canonical list (missing, extra, replaced, reordered) emitted the
    # canonical list and D06/D07 both reported OBSERVED with zero
    # discrepancies. There was no comparison anywhere, in either direction.
    #
    # There is no normaliser here now. :func:`_recorded_source_list` is the
    # SINGLE decider and it is reached identically through both doors — the
    # `capture()` route that reads these bytes and the `reconcile()` route a
    # caller drives with an object — exactly as `_settings_by_path` is for
    # `declared`/`observed`. The schema pays for this: `setting_sources` is
    # `$defs/recorded_source_list`, deliberately unconstrained, so the raw
    # recorded value reaches the packet and a third party recomputing from it
    # arrives at the same discrepancy.
    recorded_sources = document.get("setting_sources")
    if read.malformed:
        status = ERROR
    elif read.byte_truncated or overlay_byte_truncated:
        status = UNMEASURED
    else:
        status = OBSERVED if (declared or observed) else UNMEASURED
    return {
        "overlay_path": str(settings_overlay),
        "overlay_sha256": overlay_digest,
        # WHAT THE SUBJECT RECORDED. Never the caller's list, never coerced.
        "setting_sources": recorded_sources,
        # WHAT THE CONTRACT REQUIRES — the operand D07 compares against, and
        # the reason the comparison is not the subject checking itself. It is
        # caller-supplied and its ONE HOME is the frozen manifest's
        # `expected_settings.setting_sources`; the observer restates it
        # nowhere, which is why `--setting-sources` has no default. It is
        # PUBLISHED so a third party can recompute D07 from the packet alone
        # and can check this field back against the manifest.
        "expected_setting_sources": [str(item) for item in setting_sources],
        "declared": declared,
        "observed": observed,
        # One reader, one bound: MAX_EVIDENCE_BYTES over one JSON file —
        # `settings-sources.json`, and that file ALONE.
        "byte_truncated": read.byte_truncated,
        # The SAME cap over a DIFFERENT file, so a different field. `True` says
        # `overlay_sha256` above covers only the first MAX_EVIDENCE_BYTES of
        # the overlay and is not the whole-file digest a third party would
        # recompute.
        "overlay_byte_truncated": overlay_byte_truncated,
        "evidence_malformed": read.malformed,
        "observation_status": status,
    }


def _filesystem_planes(run_root: Path) -> dict[str, Any]:
    read = _read_json(run_root / EVIDENCE_FS_INVENTORY)
    document = read.document
    empty = {
        "root": str(run_root),
        "root_exists": False,
        "entries": {},
        "entry_count": 0,
        "entry_truncated": False,
        "member_bytes_truncated": False,
        "observation_status": UNMEASURED,
    }

    def normalize(raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            return dict(empty)
        entries = raw.get("entries")
        # A PRESENT-BUT-UNREADABLE `entries` is DECLARED, not silently swapped
        # for `{}`. The substitution made an inventory that recorded no path
        # map read exactly like one that recorded no paths, and every decision
        # over it reported a clean OBSERVED. The schema types this field as an
        # object, so the non-map cannot be forwarded into the packet; the
        # refusal is taken through the status channel this plane already folds
        # instead.
        #
        # THE OTHER DOOR — a caller handing `reconcile()` a plane directly —
        # NOW refuses, and did not when this comment first claimed it did. The
        # claim named `_private_root_entries` as the reader that would name the
        # same input; for `entries = 7` execution never reached it, because
        # `set(post_entries)` raised `TypeError` several decisions earlier. A
        # door downstream of a crash is not a door. `_recorded_path_map` is now
        # the reader on that route and it names the input before any comparison
        # runs, so both doors refuse — measured on both, not inferred from one.
        unreadable_entries = False
        if not isinstance(entries, dict):
            unreadable_entries = "entries" in raw
            entries = {}
        # THE SAME RULE APPLIED TO THE SCALARS, which the behavioural sweep in
        # the self-test found and the six reported sites did not include.
        # `bool(x)` maps many distinct recorded values onto the same two, so
        # `"root_exists": "True"` produced a packet BYTE-IDENTICAL to one
        # recording `true`; `str(x)` collapses `5` and `"5"` the same way. The
        # schema types these four fields, so the recorded value cannot be
        # forwarded into the packet — the coercion is DECLARED instead, on the
        # status channel this plane already folds, so a value this module had
        # to reshape can never leave the plane reading clean.
        coerced = [
            key
            for key, kind in (
                ("root", str),
                ("root_exists", bool),
                ("entry_truncated", bool),
                ("member_bytes_truncated", bool),
            )
            if key in raw and not isinstance(raw[key], kind)
        ]
        declared_status = _plane_declared_status(raw)
        if unreadable_entries:
            declared_status = ERROR
        elif coerced:
            declared_status = _worst([declared_status, UNMEASURED])
        return {
            "root": str(raw.get("root", "")),
            "root_exists": bool(raw.get("root_exists", False)),
            "entries": entries,
            # Recomputed, never accepted: a recorded count that disagrees with
            # the recorded entries would let a stale number stand in for a
            # missing path.
            "entry_count": len(entries),
            # One field per cap, forwarded to the slot that names it.
            "entry_truncated": bool(raw.get("entry_truncated", False)),
            "member_bytes_truncated": bool(raw.get("member_bytes_truncated", False)),
            # Normalised fail-closed rather than forwarded verbatim. A recorded
            # status outside the three-member vocabulary is unrankable by
            # ``_worst``, which would return ``OBSERVED`` for it and make the
            # fold below fail-OPEN on exactly the input it exists to catch.
            "observation_status": declared_status,
        }

    # A LIST THE SUBJECT RECORDED AS SOMETHING ELSE is DECLARED, never narrowed
    # to `[]` inline. A ternary to an empty value cannot account for what it
    # discards — there is nowhere in the expression to put the fact — and
    # narrowing `declared_writable_roots` to "nothing is declared" hands a
    # candidate the same suppression of D10/D11 that an undeclarable root would
    # have given it, with no flag, no count and no status able to see it.
    #
    # AND THE ELEMENTS ARE DECLARED TOO. `[str(p) for p in raw]` is the same
    # coercion `normalize` declares through `coerced` for its four scalars, and
    # these two sites were skipped: `[5]` and `["5"]` both emitted `["5"]` with
    # a BYTE-IDENTICAL packet, as did `[true]` and `["True"]`. No decision
    # reads either list, so nothing was masked — but the packet then
    # misrepresents the subject's bytes, which is exactly what
    # `non_self_certification.achieved[1]` says it does not do. The schema
    # types both lists as arrays of strings, so the recorded value cannot be
    # forwarded; the reshaping is declared on the status channel this plane
    # already folds instead.
    unreadable_lists: list[str] = []
    coerced_elements: list[str] = []

    def read_path_list(field: str) -> list[str]:
        raw = document.get(field)
        if not isinstance(raw, list):
            if field in document:
                unreadable_lists.append(field)
            return []
        for index, member in enumerate(raw):
            if not isinstance(member, str):
                coerced_elements.append(f"{field}[{index}]")
        return [str(member) for member in raw]

    roots = read_path_list("declared_writable_roots")
    # A root the subject supplied that cannot bind a containment test. It is
    # PUBLISHED unchanged below so the packet stays recomputable, and it
    # degrades this plane rather than being dropped: silently narrowing to
    # "nothing is declared" would let a candidate SUPPRESS D10 and D11 with the
    # same operand it could otherwise use to satisfy them.
    undeclarable_roots = [root for root in roots if not _is_declarable_root(root)]
    legacy = read_path_list("legacy_absolute_paths")
    pre = normalize(document.get("pre"))
    post = normalize(document.get("post"))
    # A DECLARED ROLLUP over three distinct caps, which is exactly why it is
    # named for none of them.
    #
    # A clipped inventory cannot support D10's set difference: the write that
    # escaped the declared roots may simply lie past the entry cap, and a
    # member file clipped at the byte cap has a prefix digest that D11 cannot
    # tell from an unchanged file. Either side being clipped by either cap
    # degrades the whole plane.
    #
    # THE LAST OPERAND IS THE SAME WALK THE DECISIONS USE, called here rather
    # than restated. `member_bytes_truncated` is the PRODUCER's rollup of the
    # per-entry `content_truncated`, and a SUBJECT-authored inventory can raise
    # the entry flag with the rollup false — this plane then declared OBSERVED
    # over its own bytes saying a member digest was a prefix. Two readers
    # answering the same question are two readers that can disagree; there is
    # one, and it descends by structure.
    nested_any_truncated, _nested_malformed = _plane_bounds({"pre": pre, "post": post})
    any_bound_truncated = (
        read.byte_truncated
        or bool(pre["entry_truncated"])
        or bool(pre["member_bytes_truncated"])
        or bool(post["entry_truncated"])
        or bool(post["member_bytes_truncated"])
        or nested_any_truncated
    )
    if read.malformed:
        status = ERROR
    elif any_bound_truncated:
        status = UNMEASURED
    else:
        status = OBSERVED if document else UNMEASURED
    # THE STATUS CHANNEL, folded exactly as the bound flags are folded above.
    # `inventory()` sets a NESTED `observation_status` of `UNMEASURED` on an
    # `os.lstat` OSError, on a failed digest, and on an identity that moved
    # between those two reads, and in NO case does it raise `entry_truncated`
    # or `member_bytes_truncated` -- a TOCTOU race or a permission failure
    # during the walk produces exactly that state, so
    # `any_bound_truncated` cannot see it. D10, D11 and D12 read
    # `pre["entries"]`/`post["entries"]` directly, so without this fold they
    # would decide over an inventory that had already said it was incomplete.
    # The producer-side fold contract is stated once, at `_EvidenceBounds`.
    status = _worst([status, pre["observation_status"], post["observation_status"]])
    if undeclarable_roots or unreadable_lists or coerced_elements:
        status = _worst([status, UNMEASURED])
    return {
        "declared_writable_roots": sorted(set(roots + [str(run_root)])),
        "legacy_absolute_paths": legacy,
        "pre": pre,
        "post": post,
        "any_bound_truncated": any_bound_truncated,
        "evidence_malformed": read.malformed,
        "observation_status": status,
    }


def _environment_plane() -> dict[str, Any]:
    """Digest and length for each allowlisted variable, over its REAL bytes.

    ``errors="surrogateescape"`` is not decoration. POSIX permits any byte
    string but NUL in an environment value; CPython decodes such a value with
    ``surrogateescape``, and a plain ``.encode("utf-8")`` of the result raises
    ``UnicodeEncodeError`` -- a ``ValueError``, which :func:`_cli` reported on
    the arm reserved for a REFUSED ARGV, so ``HOME`` holding one stray byte
    produced ``rc=2``, zero packet bytes and a message blaming the caller's
    arguments. The identical misattribution was already corrected twice in this
    module (``_run_command``, ``_debug_receipt_numbers``); this is the third
    site of the same class. Encoding with ``surrogateescape`` round-trips the
    original bytes exactly, so the digest and the length are of what the
    process actually holds and the variable stays ``OBSERVED`` -- it WAS
    observed, and degrading it would be a second wrong answer.
    """
    variables = []
    for name in ENVIRONMENT_ALLOWLIST:
        raw = os.environ.get(name)
        present = raw is not None
        encoded = raw.encode("utf-8", errors="surrogateescape") if present else None
        variables.append(
            {
                "name": name,
                "present": present,
                "sha256": _sha256_bytes(encoded) if present else None,
                "bytes": len(encoded) if present else None,
                "observation_status": OBSERVED if present else UNMEASURED,
            }
        )
    return {
        "allowlist": list(ENVIRONMENT_ALLOWLIST),
        "variables": variables,
        "observation_status": _worst(v["observation_status"] for v in variables),
    }


def _executables_plane() -> dict[str, Any]:
    entries = []
    for name in EXECUTABLE_NAMES:
        resolved = _which(name)
        if name == "claude":
            # Resolved, never executed: P0-A runs no Claude binary, and an
            # unavailable binary must not become a pass (amendment:245).
            entries.append(
                {
                    "name": name,
                    "present": resolved is not None,
                    "path": resolved,
                    "version": None,
                    "observation_status": UNMEASURED,
                }
            )
            continue
        version = None
        status = UNMEASURED
        if resolved is not None:
            code, output = _run_command([resolved, "--version"])
            if code == 0 and output:
                version = output.splitlines()[0][:200]
                status = OBSERVED
        entries.append(
            {
                "name": name,
                "present": resolved is not None,
                "path": resolved,
                "version": version,
                "observation_status": status,
            }
        )
    return {"entries": entries, "observation_status": _worst(e["observation_status"] for e in entries)}


def _which(name: str) -> str | None:
    """Locate ``name`` on PATH without importing ``shutil``-level helpers.

    Kept explicit so the executable-identity observation is an OS fact this
    module can point at, line by line.
    """
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        candidate = os.path.join(directory, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _git_snapshot(cwd: Path) -> dict[str, Any]:
    head_code, head = _run_command(["git", "rev-parse", "HEAD"], cwd=cwd)
    status_code, status_out = _run_command(["git", "status", "--porcelain"], cwd=cwd)
    if head_code != 0:
        return {"head": None, "dirty_path_count": None, "observation_status": UNMEASURED}
    dirty = len([ln for ln in status_out.splitlines() if ln.strip()]) if status_code == 0 else None
    return {
        "head": head or None,
        "dirty_path_count": dirty,
        "observation_status": OBSERVED if dirty is not None else UNMEASURED,
    }


def _candidate_claim_plane(run_root: Path) -> dict[str, Any]:
    path = run_root / EVIDENCE_CANDIDATE_CLAIM
    present = path.is_file()
    # THE THIRD MEMBER IS PUBLISHED, not discarded. This plane published a
    # digest and a byte count with NO truncation flag at all, so a candidate
    # claim past MAX_EVIDENCE_BYTES was recorded by a PREFIX digest that no
    # field distinguished from a whole-file one — and `bytes` reads exactly
    # MAX_EVIDENCE_BYTES rather than the real size, so the pair is
    # self-consistent and silently wrong.
    #
    # `reconcile()` does not read this plane (`read_by_reconcile` is `False` by
    # construction), so no decision degrades on this flag and none is meant to.
    # The flag exists for the THIRD PARTY who recomputes the digest from the
    # raw bytes: without it, that recomputation disagrees with the packet and
    # the packet gives no reason why.
    digest, size, byte_truncated = (
        _sha256_file(path) if present else (None, None, False)
    )
    return {
        "present": present,
        "source_path": str(path) if present else None,
        "sha256": digest,
        "bytes": size,
        "byte_truncated": byte_truncated,
        "read_by_reconcile": False,
    }


# --------------------------------------------------------------------------
# Public: capture
# --------------------------------------------------------------------------


def _flag_key(token: str) -> str:
    """Fold an option token onto a deliberately OVER-BROAD comparison key.

    Case, separators and the ``=``-joined value are all discarded, so
    ``--Safe-Mode``, ``--SAFE_MODE`` and ``--safe-mode=1`` all fold onto
    ``safemode``. The real parser is case-sensitive and rejects abbreviations
    (measured; see the probe table above), so this folds together spellings the
    parser would treat as distinct. That asymmetry is deliberate: refusing more
    than the parser honours is safe, refusing less is the bypass.
    """
    head = token.split("=", 1)[0]
    return re.sub(r"[^a-z0-9]", "", head.lower())


_FORBIDDEN_FLAG_KEYS: tuple[str, ...] = tuple(
    _flag_key(flag) for flag in FORBIDDEN_CHILD_FLAGS
)


def _forbidden_flag_matches(token: str) -> list[str]:
    """Forbidden flags this token could be, under any spelling.

    Applies only to OPTION-SHAPED tokens (those beginning with ``-``), where
    prefix matching runs BOTH ways: ``token_key`` being a prefix of a forbidden
    key catches abbreviations (``--safe`` -> ``safemode``), and a forbidden key
    being a prefix of ``token_key`` catches suffixed variants
    (``--safe-mode-now``). Enumerating the known bad spellings is the #1503
    failure shape — this removes the category instead.

    Non-option tokens are matched on EXACT folded equality instead, because a
    both-ways prefix rule over ordinary values would refuse a legitimate path
    such as ``/s`` for being a prefix of ``safemode``. A guard that refuses
    real inputs gets switched off, and a guard that is off refuses nothing.
    """
    key = _flag_key(token)
    if not key:
        return []
    option_shaped = token.startswith("-")
    matches = set()
    for flag, forbidden_key in zip(FORBIDDEN_CHILD_FLAGS, _FORBIDDEN_FLAG_KEYS):
        if option_shaped:
            hit = key.startswith(forbidden_key) or forbidden_key.startswith(key)
        else:
            hit = key == forbidden_key
        if hit:
            matches.add(flag)
    return sorted(matches)


def _refuse_option_shaped(label: str, value: str) -> None:
    """Refuse a caller-supplied value that could be parsed as, or collide with, an option.

    Two independent rules, because one of them being wrong must not be enough:

    1. **Leading ``-``.** Refused outright. The real parser was measured
       swallowing such a token as the preceding option's VALUE rather than
       re-parsing it as a flag, so this is not currently exploitable — but that
       is a parser detail we do not control, and argument injection is the
       exact class this removes.
    2. **Folds onto a forbidden flag.** Refused however it is spelled.
    """
    if not value:
        raise ValueError(f"refused empty {label}: an empty argv token is not a supplied value")
    if value.startswith("-"):
        raise ValueError(
            f"refused option-shaped {label} {value!r}: a supplied value must not begin "
            f"with '-' ({_CLI_PARSER_PROBE})"
        )
    offenders = _forbidden_flag_matches(value)
    if offenders:
        raise ValueError(
            f"refused {label} {value!r}: it collides with forbidden carrier-proof "
            "flags " + ", ".join(offenders)
        )


def _emitted_units(flag: str, value: str) -> list[str]:
    """Every token the child's parser actually sees for one emitted value.

    Validating the caller's pre-join ELEMENT can never be enough. An element is
    not what the child receives: ``--setting-sources`` takes a comma list, so a
    single element that carries its own comma — ``"user,--safe-mode"`` — is not
    option-shaped as an element, survives an element-level refusal untouched,
    and decomposes at the parser into the two sources ``user`` and
    ``--safe-mode``. That was a real bypass in this file.

    The decomposition here is derived from the EMITTED string rather than from
    the caller's list, so the objects that get checked and the objects that get
    transmitted are the same bytes. That is what closes the category: any
    arrangement of commas across any number of elements produces the same
    joined string and therefore the same units, so there is no fourth variant
    to enumerate.

    The whole value is returned alongside its units, because a value can also
    be option-shaped before any splitting happens.
    """
    if flag in COMMA_DELIMITED_CHILD_FLAGS:
        return [value, *value.split(",")]
    return [value]


def _build_child_argv(
    *,
    session_uuid: str,
    settings_overlay: Path,
    setting_sources: Iterable[str],
    debug_file: Path,
) -> list[str]:
    """Build the controlled child's argv, refusing anything outside the allowlist.

    ``--safe-mode`` and ``--no-session-persistence`` are forbidden for carrier
    proof (``amendment:195-196``): a run that cannot persist a session cannot
    be joined to the transcript that proves what the carrier did.

    Three arms, in order of strength. All three run against the EMITTED
    strings — the argv tokens and the units they decompose into per
    :func:`_emitted_units` — never against the caller's pre-transformation
    inputs, so the checked object and the transmitted object are the same
    bytes.

    * **Allowlist.** Every option-shaped emitted token must be a member of
      :data:`ALLOWED_CHILD_FLAGS`. This removes the category — a forbidden flag
      cannot appear under a spelling nobody thought of, because no token
      outside the frozen set can appear at all.
    * **Value validation.** Every emitted unit is refused if it is
      option-shaped or folds onto a forbidden flag. The session id is required
      to be a real UUID, which is what the CLI itself demands (measured:
      ``--session-id --help`` -> "Invalid session ID. Must be a valid UUID.");
      it is then the CANONICALISED id that is checked, because that is the one
      the child gets.
    * **Blacklist.** The normalized, both-ways-prefix forbidden-flag scan.
      Redundant given the allowlist, and kept for exactly that reason.

    Raises:
        ValueError: on any of the three.
    """
    try:
        canonical_session = str(uuid.UUID(str(session_uuid)))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError(
            f"refused session id {session_uuid!r}: the CLI requires a UUID, and a "
            "non-UUID session value is how an option-shaped token reaches the argv"
        ) from exc

    sources = [str(item) for item in setting_sources]
    if not sources:
        raise ValueError("refused empty setting sources: an unsourced run proves nothing")

    # The (flag, value) pairs ARE the emission structure, so the walk that
    # validates and the walk that emits are one walk over one set of strings.
    # Nothing re-parses a flattened argv to guess which token is a value, and
    # no value is validated in a form the child never receives. `None` marks a
    # flag that takes no value.
    options: tuple[tuple[str, str | None], ...] = (
        ("--print", None),
        ("--output-format", "stream-json"),
        ("--include-hook-events", None),
        ("--verbose", None),
        ("--debug-file", str(debug_file)),
        ("--setting-sources", ",".join(sources)),
        ("--settings", str(settings_overlay)),
        ("--session-id", canonical_session),
    )

    argv = ["claude"]
    emitted: list[str] = []
    for flag, value in options:
        argv.append(flag)
        if value is None:
            continue
        argv.append(value)
        for unit in _emitted_units(flag, value):
            emitted.append(unit)
            _refuse_option_shaped(CHILD_FLAG_VALUE_LABELS[flag], unit)

    # Both remaining arms scan the argv tokens AND the units those tokens
    # decompose into at the parser, so a forbidden flag riding inside a joined
    # value is visible to all three arms rather than to none of them.
    scanned = argv + emitted
    outside = sorted(
        {token for token in scanned if token.startswith("-") and token not in ALLOWED_CHILD_FLAGS}
    )
    if outside:
        raise ValueError(
            "refused option tokens outside the frozen allowlist: " + ", ".join(outside)
        )
    offenders = sorted({flag for token in scanned for flag in _forbidden_flag_matches(token)})
    if offenders:
        raise ValueError(
            "refused forbidden carrier-proof flags: " + ", ".join(offenders)
        )
    return argv


def capture(
    *,
    cwd: Path,
    run_root: Path,
    session_uuid: str,
    settings_overlay: Path,
    setting_sources: Iterable[str],
    debug_file: Path,
) -> dict[str, Any]:
    """Build the raw observation frame for one controlled Claude execution.

    Every argument is caller-supplied (``amendment:192-195``); this function
    invents no path and writes nothing. The controlled child is NOT executed at
    P0-A, so ``run_frame`` records ``child_executed: false`` and the child's
    own outcome fields stay ``UNMEASURED``. Evidence produced by a real run is
    read from ``run_root``; whatever is absent is ``UNMEASURED``.

    Raises:
        ValueError: if the argv it is asked to build would contain
            ``--safe-mode`` or ``--no-session-persistence``.
    """
    cwd = Path(cwd)
    run_root = Path(run_root)
    settings_overlay = Path(settings_overlay)
    debug_file = Path(debug_file)
    # Materialised ONCE, before either consumer. `Iterable[str]` admits a
    # generator, and a generator is exhausted by the first traversal: without
    # this, _build_child_argv would validate and emit `user,project,local`
    # while _settings_provenance recorded `[]` for the same run. The packet
    # would then describe a provenance the argv contradicts — the same
    # checked-object-is-not-the-emitted-object shape as the comma bypass.
    setting_sources = tuple(str(item) for item in setting_sources)

    argv = _build_child_argv(
        session_uuid=session_uuid,
        settings_overlay=settings_overlay,
        setting_sources=setting_sources,
        debug_file=debug_file,
    )

    module_dir = Path(__file__).resolve().parent
    observation: dict[str, Any] = {
        "run": {
            "cwd": str(cwd),
            "run_root": str(run_root),
            "session_uuid": session_uuid,
            "argv": argv,
            "refused_flags": list(FORBIDDEN_CHILD_FLAGS),
            "child_executed": False,
            "observation_status": UNMEASURED,
        },
        "environment": _environment_plane(),
        "executables": _executables_plane(),
        "settings": _settings_provenance(run_root, settings_overlay, setting_sources),
        "git": {},
        "stream": _bounded_evidence(run_root / EVIDENCE_STREAM, _count_jsonl),
        "debug": _bounded_evidence(debug_file, _count_lines),
        "transcript": _bounded_evidence(run_root / EVIDENCE_TRANSCRIPT, _count_jsonl),
        "hooks": _hook_lifecycle(run_root, debug_file),
        "filesystem": _filesystem_planes(run_root),
        "source_audit": _source_audit(module_dir / Path(__file__).name),
        "schema_audit": _schema_audit(
            module_dir / SCHEMA_FILENAME, run_root / EVIDENCE_PACKET
        ),
    }
    pre = _git_snapshot(cwd)
    post = dict(pre)
    observation["git"] = {
        "pre": pre,
        # SINGLE-SAMPLED AT A-TIME, said here so this pair cannot be read as
        # the differential one it resembles. `_git_snapshot` is called ONCE
        # per capture -- one definition, this one call site -- so `post` is a
        # COPY of `pre`, not a second read, and the pair cannot show drift.
        # NO CONTROLLED CHILD ACTION SEPARATES POSSIBLE GIT SAMPLES AT P0-A:
        # no child executes here (`run.child_executed` is `const: false`), so
        # there is no later moment for a second snapshot to observe. The
        # DIFFERENTIAL pair is the filesystem plane's `pre`/`post` -- two
        # separately recorded snapshots WITHIN ONE inventory document, not two
        # reads of it. A differential Git sample belongs to the rung that
        # executes a child (`amendment:278`); no entry in
        # DECISION_EVIDENCE_PLANES names "git", so no decision reads this one.
        "post": post,
        # Folded with `_worst` rather than assigned from `pre`, so this plane
        # obeys the same nested-status contract as `filesystem` and `hooks`:
        # every object nested inside a plane has its `observation_status`
        # folded into the plane's own. `post` is a copy here, so the fold is
        # currently an identity -- writing it as a fold is what keeps that a
        # measured coincidence rather than an assumption the next revision
        # inherits.
        "observation_status": _worst(
            [pre["observation_status"], post["observation_status"]]
        ),
    }
    return observation


# --------------------------------------------------------------------------
# Public: reconcile
# --------------------------------------------------------------------------


class _EvidenceBounds(NamedTuple):
    """Whether a decision's own evidence was clipped, undecodable, or unmeasured.

    ``any_bound_truncated`` is a DECISION-LEVEL ROLLUP across every plane the
    decision reads and every bound those planes carry, because a decision does
    not care WHICH bound cut its evidence short, only that something did. The
    ``any`` segment in the name is what says so. It is composed in
    :func:`_evidence_bounds` from per-bound flags that each name exactly one
    bound, and ``notes`` records which plane contributed; the per-bound detail
    survives in the planes themselves.

    ``plane_status`` is a THIRD, SEPARATE channel and NOT a bound: the worst
    ``observation_status`` any plane in this decision's
    :data:`DECISION_EVIDENCE_PLANES` entry declares ABOUT ITSELF, for ANY
    reason. Two flags answering "did a cap clip us" cannot carry that, because
    an ABSENT evidence file sets no truncation flag at all, and
    ``amendment:208`` requires the degradation anyway. It is kept apart from
    the bound flags rather than folded in, since an absence is not a cap.

    ITS READ IS SINGLE-LEVEL, and that is a contract with the PRODUCERS:
    :func:`_plane_declared_status` reads one key, the plane's own
    ``observation_status``, and reaches a nested object's status only because
    every plane containing one folds it in. The self-test walks the emitted
    packet, discovers every nested status-bearing object, and refuses any site
    without a driven proof of its fold, so the contract is maintained
    mechanically rather than by this paragraph.

    This field is INTERNAL: composed here, applied in :func:`_decision`, never
    emitted. A reader sees the decision's degraded ``observation_status`` plus
    a ``notes`` entry naming the plane and the status it declared.
    """

    any_bound_truncated: bool
    malformed: bool
    notes: list[str]
    #: Defaults to ``OBSERVED`` so that the two call sites which build an empty
    #: bounds record stay neutral under :func:`_worst`.
    plane_status: str = OBSERVED


#: Which observation planes each decision actually reads. ``reconcile()`` looks
#: up every plane a decision consumes and degrades the decision when any of them
#: reports a clipped or undecodable read; the self-test asserts the union covers
#: every plane that carries a bound, so a bound nobody reads cannot ship.
#:
#: MEMBERSHIP IS LOAD-BEARING TWICE: the same lookup also carries each declared
#: plane's own ``observation_status`` into the decision (see
#: :func:`_evidence_bounds` and :attr:`_EvidenceBounds.plane_status`), so adding
#: a plane subscribes the decision to that plane's bounds AND to its status.
#: D09's omission of ``transcript`` is what keeps an absent transcript out of
#: D09 — at A-time the transcript participates by STATUS LEVEL ONLY.
DECISION_EVIDENCE_PLANES: dict[str, tuple[str, ...]] = {
    "D01_SCHEMA_ROOT_CLOSED": ("schema_audit",),
    "D02_SCHEMA_COMPOSED_CLOSED": ("schema_audit",),
    "D03_NO_STATIC_PRODUCT_IMPORT": ("source_audit",),
    "D04_NO_DYNAMIC_PRODUCT_IMPORT": ("source_audit",),
    "D05_NO_CANDIDATE_VERDICT_IN_OBSERVATION": (),
    "D06_SETTINGS_DIGEST_MATCH": ("settings",),
    "D07_SETTINGS_SOURCE_SET_EXACT": ("settings",),
    "D08_HOOK_TOOL_USE_ID_JOIN": ("hooks", "stream", "debug", "transcript"),
    "D09_HIDDEN_HOOK_NONZERO": ("hooks", "stream", "debug"),
    "D10_NO_WRITE_OUTSIDE_DECLARED_ROOTS": ("filesystem",),
    "D11_NO_SILENT_CONTENT_CHANGE": ("filesystem",),
    "D12_MODE_OWNER_RECORDED_FAITHFULLY": ("filesystem",),
}

#: Keys by which a plane declares that one of its bounds clipped the evidence.
#: DERIVED from :data:`PUBLISHED_TRUNCATION_FLAGS` rather than restated, so a
#: plane that starts publishing a new bound is read here without anyone
#: remembering to edit a second list — that omission is how a bound goes dark.
#: Read as a SET, not by plane type. Which bound each key names is declared once,
#: in :data:`TRUNCATION_BOUND_FLAGS` and :data:`TRUNCATION_ROLLUP_FLAGS`.
_TRUNCATION_KEYS: tuple[str, ...] = PUBLISHED_TRUNCATION_FLAGS
_MALFORMED_KEYS: tuple[str, ...] = ("evidence_malformed",)
_MALFORMED_COUNT_KEYS: tuple[str, ...] = ("unparsable_records",)


def _plane_bounds(plane: Any) -> tuple[bool, bool]:
    """``(any_bound_truncated, malformed)`` for one plane, AT EVERY DEPTH.

    THE DESCENT IS BY STRUCTURE, NOT BY A LIST OF PLACES. It used to descend
    into exactly ``("pre", "post")``, which meant a flag published one level
    lower was read by nobody: ``content_truncated`` occurs in the packet ONLY
    at ``/observation/filesystem/{pre,post}/entries/*/content_truncated``, so a
    member file clipped at the byte cap left D11 comparing PREFIX digests as if
    they were whole, with ``any_bound_truncated`` false and the decision
    OBSERVED. The flag was in the published registry and in the schema, and the
    reader still never reached it — the registry could not save a walk that did
    not go there.

    Enumerating two more keys would have closed that one location and left the
    next one open, which is the shape this module keeps being caught by. Every
    dict value and every list item is descended instead, so a bound published
    anywhere under a plane is read wherever it is put.

    Recursion is bounded: ``reconcile`` refuses an observation deeper than
    :data:`MAX_DOCUMENT_DEPTH` before any reader runs, so this walk cannot
    exceed that depth and cannot raise ``RecursionError`` (CWE-674).
    """
    if isinstance(plane, list):
        children: Any = plane
        any_bound_truncated = False
        malformed = False
    elif isinstance(plane, dict):
        children = plane.values()
        any_bound_truncated = any(bool(plane.get(key)) for key in _TRUNCATION_KEYS)
        malformed = any(bool(plane.get(key)) for key in _MALFORMED_KEYS)
        for key in _MALFORMED_COUNT_KEYS:
            # FAIL CLOSED, DO NOT ENUMERATE THE EXCEPTION TYPES. Every arm of
            # this handler already sets `malformed = True`, so a narrow tuple
            # buys nothing and costs the crash: `(TypeError, ValueError)`
            # missed `OverflowError` from `int(float("inf"))`, which is an
            # `ArithmeticError`. `json.loads('{"x": Infinity}')` yields `inf`
            # by default, this walk descends EVERY dict at EVERY depth by
            # design, and `filesystem.pre/post.entries` values are
            # subject-authored (``ladder:282``) — so a recorded
            # `"unparsable_records": Infinity` raised out of `reconcile` and
            # produced zero packet bytes instead of the ERROR that reaching
            # this handler at all is supposed to mean.
            #
            # THE VALUE DOMAIN, TOO. `int(...) > 0` asked only "is it
            # positive", so a recorded `"unparsable_records": -1` — outside the
            # `integer, minimum: 0` its own schema declares — answered False
            # and this plane reported NOT malformed. A count of undecodable
            # records that is itself undecodable is the strongest possible
            # reason to report ERROR, and it was the one input that read clean.
            # A PRESENT value now has to be a count before it can be compared
            # to one; only an ABSENT or `None` key means "nothing to report".
            #
            # AND THE HANDLER BELOW IS NOW BELT-AND-BRACES WITH NO REACHABLE
            # PATH — said plainly, because everything above it is written in
            # the past tense about an `int(...)` call this cycle DELETED, and
            # past-tense-but-true still reads as a live defence. It is not one.
            # `_is_recorded_count` is TOTAL: it decides on `isinstance` alone
            # and returns False for every value, including one whose `__eq__`
            # and `__gt__` raise. `or` then SHORT-CIRCUITS, so `raw_count > 0`
            # is never evaluated for anything the predicate rejected, and the
            # only comparison that survives is `int > 0`. Driven over the whole
            # interesting domain — `inf`, `nan`, `-1`, `"x"`, `True`, `[]`,
            # `{}`, `5.0` — `_plane_bounds` returns `(False, True)` for each
            # and enters this handler for none; the negative controls `None`
            # and `0` return `(False, False)`. The handler is CODE-reachable
            # but not VALUE-drivable: forcing `_is_recorded_count` to raise
            # does enter it and does yield `(False, True)` without a crash,
            # which is the only way to exercise it and is not a path any input
            # can take. It is kept because it costs nothing and because the
            # class it guards — a fail-closed default over a walk that descends
            # subject-authored dicts at every depth — is the one this module
            # keeps being caught by; it is NOT kept because it currently fires.
            try:
                raw_count = plane.get(key)
                if raw_count is None:
                    continue
                malformed = malformed or not _is_recorded_count(raw_count) or raw_count > 0
            except Exception:  # noqa: BLE001 - a defeated read IS the finding
                malformed = True
    else:
        return False, False
    for nested in children:
        nested_any_truncated, nested_malformed = _plane_bounds(nested)
        any_bound_truncated = any_bound_truncated or nested_any_truncated
        malformed = malformed or nested_malformed
    return any_bound_truncated, malformed


def _plane_declared_status(plane: Any) -> str:
    """The ``observation_status`` a plane declares ABOUT ITSELF, read fail-closed.

    Three inputs, three answers, and each way round is deliberate:

    * **Not a dict, or no ``observation_status`` key** -> ``UNMEASURED``. A
      plane a decision declares but the observation does not carry was not
      measured. Returning ``OBSERVED`` here would let a decision whose plane
      is entirely missing report a clean answer.
    * **A member of the status vocabulary** -> itself.
    * **Any other string** -> ``ERROR``. :func:`_worst` ranks only the three
      members; handed ``"FINE"`` it finds neither ``ERROR`` nor ``UNMEASURED``
      in the set and returns ``OBSERVED``, which is the fail-OPEN direction.
      Normalising an unrankable value to ``ERROR`` here is what keeps that
      from happening, and ``ERROR`` rather than ``UNMEASURED`` because a
      status this module cannot rank is a defeated reader, not a partial one.
    """
    if not isinstance(plane, dict):
        return UNMEASURED
    raw = plane.get("observation_status")
    if raw is None:
        return UNMEASURED
    text = str(raw)
    if text not in (OBSERVED, UNMEASURED, ERROR):
        return ERROR
    return text


def _plane_mapping(container: Any, name: str) -> tuple[dict[str, Any], str]:
    """``container[name]`` as a mapping this module's readers can walk, and the
    status that read declares.

    EVERY PLANE READ IN :func:`reconcile` GOES THROUGH HERE, and the reason is
    that ``reconcile`` is PUBLIC while the only in-repo call site feeds it from
    ``capture``. ``reconcile({"filesystem": ["a"]})`` raised
    ``AttributeError: 'list' object has no attribute 'get'`` — the same for
    ``str`` and ``int``, while ``None`` was already safe through the ``or {}``
    idiom this replaces. A caller who skips schema validation crashed instead
    of receiving a degraded packet.

    Three inputs, three answers:

    * **Absent, or ``None``** -> ``({}, UNMEASURED)``. Exactly what
      ``str(plane.get("observation_status", UNMEASURED))`` returned over the
      ``{}`` the old ``or {}`` produced, so no behaviour moves for the case
      that already worked.
    * **A mapping** -> itself, with :func:`_plane_declared_status` deciding the
      status. ONE status decider, reused rather than duplicated.
    * **Present and not a mapping** -> ``({}, ERROR)``. The substitution has to
      happen — no reader here can walk a list — so the fact that one happened
      is DECLARED. ``ERROR`` rather than ``UNMEASURED`` for the reason
      :func:`_plane_declared_status` gives for an unrankable status: a plane
      shaped so this module's readers are defeated is a defeated reader, not a
      partial measurement.

    THE STATUS IS RETURNED TO THE CALL SITE, not left to
    :data:`DECISION_EVIDENCE_PLANES`. ``_evidence_bounds`` would also degrade a
    decision whose declared plane is unreadable, but that route depends on the
    decision's plane tuple being non-empty: emptying a tuple launders an
    unrankable status back to ``OBSERVED``. The status computed here is passed
    straight into :func:`_decision` by every call site, so the refusal survives
    an empty plane declaration.
    """
    if not isinstance(container, dict):
        return {}, ERROR
    raw = container.get(name)
    if raw is None:
        return {}, UNMEASURED
    if not isinstance(raw, dict):
        return {}, ERROR
    return raw, _plane_declared_status(raw)


def _recorded_sequence(
    container: dict[str, Any], name: str, label: str
) -> tuple[list[Any], list[str]]:
    """``container[name]`` as a list this module can walk, and what that read lost.

    THE SIBLING OF :func:`_plane_mapping`, ONE LEVEL DOWN, and its absence was
    the same defect one level down. Every PLANE read in :func:`reconcile` went
    through ``_plane_mapping`` and could not crash; the sub-plane reads on the
    very next lines went through a bare ``.get(..., [])`` and could. A fuzz of
    the thirteen sub-reads with ``["a"], "a", 7, 1.5, True`` raised uncaught out
    of twelve of them — ``TypeError`` from iterating an ``int``, from
    ``set(7)``, and ``AttributeError`` from ``7.get``. ``reconcile`` is PUBLIC,
    so a malformed packet is an INPUT, not a bug: it must degrade, never raise
    and never silently read clean.

    ``str`` is refused with the scalars, deliberately. It IS iterable, so a
    recorded ``"toolu_01"`` would have iterated into nine one-character
    "entries" and produced nine plausible-looking discrepancies over a value
    that recorded one thing — the loudest possible way to be wrong.

    Absent or ``None`` records nothing and is not a defect: the empty list, no
    problem. Present-and-unwalkable is NAMED, and the name carries the raw
    value so a third party recomputing from the packet reaches the same place.
    """
    raw = container.get(name)
    if raw is None:
        return [], []
    if isinstance(raw, list):
        return raw, []
    return [], [
        f"{label} records {raw!r}, not a list this reader can walk; every "
        "member it may have carried is unmeasured"
    ]


def _recorded_path_map(
    container: dict[str, Any], name: str, label: str
) -> tuple[dict[str, Any], list[str]]:
    """``container[name]`` as a path map this module can walk, and what it lost.

    The mapping half of :func:`_recorded_sequence`. ``set(pre_entries)`` over a
    recorded ``7`` raised ``TypeError`` before any decision ran, and over a
    recorded ``"abc"`` would have produced the three single-character "paths"
    ``a``, ``b``, ``c`` — one crash and one silent fabrication out of the same
    unguarded read.
    """
    raw = container.get(name)
    if raw is None:
        return {}, []
    if isinstance(raw, dict):
        return raw, []
    return {}, [
        f"{label} records {raw!r}, not a path map this reader can walk; every "
        "entry it may have carried is unmeasured"
    ]


def _is_recorded_count(value: Any) -> bool:
    """True when ``value`` is inside the domain the schema declares for counts.

    THE VALUE HALF OF A GUARD THAT SHIPPED WITH ONLY ITS TYPE HALF, and the
    same correction :data:`_POSIX_MODE_CEILING` already made for ``mode``.

    WHAT THE SENTENCE BELOW IS ABOUT, said first because an earlier revision
    left it ambiguous and the ambiguity flattered this predicate. It is a claim
    about what the SCHEMA DECLARES, not about what this predicate READS. The
    schema types every count and byte length as ``integer, minimum: 0`` —
    ``$defs/byte_count``, ``evidence_count``, ``discrepancy_count``,
    ``unparsable_records`` — so a NEGATIVE one is outside the domain its own
    schema declares, exactly as ``"mode": -1`` was. THIS PREDICATE IS CALLED ON
    A SUBSET of those sites, and naming ``$defs/byte_count`` in a list headed
    "every count in this packet" read as coverage it did not have: ``$defs/
    byte_count`` is also the type of ``path_entry.bytes``, which had NO reader
    at all until :func:`_path_entry_domain_problems` (which is now one of this
    predicate's callers). A reader looking for what is CHECKED should follow the
    call sites, not this list.

    Three clauses, and the ORDER is load-bearing:

    * ``bool`` FIRST. ``isinstance(True, int)`` is True and ``True >= 0``, so a
      recorded ``true`` would otherwise rank as the count ``1``.
    * ``int`` — a ``float`` is refused with the strings, including ``5.0``: a
      count is not a measurement with a fractional part, and admitting floats
      re-admits ``inf`` and ``nan`` through a door
      :func:`_refuse_non_finite` closes at the parse boundary only.
    * ``>= 0`` — the clause that did not exist. See :func:`_recorded_count`
      for what its absence cost.

    THIS PREDICATE IS FOR COUNTS AND BYTE LENGTHS ONLY. It is deliberately NOT
    applied to ``exit_code``: a negative exit code is not out of domain, it is
    the POSIX encoding of a terminating signal (``-9`` is SIGKILL, ``-15`` is
    SIGTERM), and :func:`_decision_from_exit` must keep ranking it ``NONZERO``.
    A guard generalised from ``stdout_bytes`` to its sibling field by analogy
    would have turned a killed hook into an unrankable one.
    """
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _recorded_count(container: dict[str, Any], name: str, label: str) -> tuple[int, list[str]]:
    """``container[name]`` as a denominator, and what that read lost.

    ``int(source_audit.get("_static_examined", 0) or 0)`` raised ``ValueError``
    on a recorded ``"a"`` and ``TypeError`` on ``["a"]``: the DENOMINATOR was
    as unguarded as the numerator. Refusing to zero is fail-closed —
    :func:`_decision` cannot report ``OBSERVED`` over an empty denominator —
    and the refusal is named as well as counted, so a zero here is never
    mistaken for "nothing was examined".

    ``bool`` is excluded before ``int``: ``isinstance(True, int)`` is True, so
    a recorded ``true`` would otherwise become the denominator ``1``.

    THE VALUE DOMAIN NOW GOES THROUGH THE SAME DOOR AS THE TYPE DOMAIN, and
    that is this cycle's correction. ``max(0, raw)`` was not a guard, it was a
    LAUNDERER: a recorded ``-1`` and a recorded ``-99`` each became the
    denominator ``0`` with an EMPTY problem list, so the packet was
    byte-identical to one whose subject recorded nothing at all — the reader
    could not tell "no evidence was examined" from "the record of how much was
    examined is nonsense". Measured before the fix: ``raw=-1 -> (0, [])``,
    ``raw=-99 -> (0, [])``, beside ``raw=True -> (0, [named])``, so the TYPE
    attack was named and the VALUE attack was silent. A count outside the
    domain :func:`_is_recorded_count` states is now NAMED and degrades, on the
    same channel and by the same words as an unrankable type. Nothing is
    clamped, because clamping is how the finding disappears.
    """
    raw = container.get(name)
    if raw is None:
        return 0, []
    if not _is_recorded_count(raw):
        return 0, [f"{label} records {raw!r}, not a count this reader can rank"]
    return raw, []


def _finding_text(finding: Any, position: int, label: str) -> str:
    """One import finding rendered for a discrepancy list, whatever it records.

    ``f['evidence']`` raised ``TypeError`` on a member recorded as a scalar and
    ``KeyError`` on a dict missing the key. Both are now NAMED rather than
    fatal, and named in a form that carries the raw member: an unreadable
    finding is still a finding, and dropping it would have shrunk D03's
    numerator to zero over a packet that recorded a violation.
    """
    if isinstance(finding, dict) and "evidence" in finding:
        return f"{finding.get('evidence')} (line {finding.get('lineno')})"
    return (
        f"{label} at index {position} records {finding!r}, not an evidence "
        "record this reader can read"
    )


def _degraded(status: str, problems: list[str]) -> str:
    """``ERROR`` when a read was defeated, otherwise the status unchanged.

    ``ERROR`` and not ``UNMEASURED``, for the reason :func:`_plane_mapping`
    gives: a value shaped so this module's readers are defeated is a defeated
    reader, not a partial measurement, and a caller must not be able to read it
    as "we saw less than everything".
    """
    return _worst([status, ERROR]) if problems else status


def _evidence_bounds(observation: dict[str, Any], decision_id: str) -> _EvidenceBounds:
    """Collect the bounds AND the declared statuses of every plane ``decision_id`` reads.

    Status mapping, and why each way round (``amendment:208`` — "Missing or
    ambiguous evidence is ``UNMEASURED``/``ERROR``"):

    * **Clipped but well-formed -> ``UNMEASURED``.** The reader measured part
      of the subject. The unread tail may hold the very event the decision
      looks for, so the decision is *unmeasured*, not clean. This is the D08
      case exactly: the orphan set is a symmetric difference and cannot express
      "present in neither because the reader stopped".
    * **Undecodable -> ``ERROR``.** The reader was defeated by the input. That
      is a failure of the observation, not a partial measurement, and it is the
      stronger of the two statuses because a caller must not be able to read it
      as "we saw less than everything".
    * **A declared plane that is itself ``UNMEASURED`` or ``ERROR``, for any
      reason -> the decision inherits it.** The two flags above answer only
      "did a cap clip us", and an ABSENT evidence file sets neither.
      ``amendment:208`` requires the degradation, so it is taken from the
      plane's own status through :func:`_plane_declared_status`, never
      inferred from a bound. Both arms are driven by
      ``test_an_absent_declared_plane_degrades_exactly_the_decisions_that_declare_it``.

    The ``plane_status`` accumulator is SEEDED with ``OBSERVED`` rather than
    left empty, because ``_worst([])`` is ``UNMEASURED``: a decision that
    declares no plane at all (D05 reads the whole packet, not a plane) must
    stay neutral, not degrade for having nothing to inherit.
    """
    any_bound_truncated = False
    malformed = False
    notes: list[str] = []
    plane_statuses: list[str] = [OBSERVED]
    for name in DECISION_EVIDENCE_PLANES.get(decision_id, ()):
        plane = observation.get(name)
        plane_any_truncated, plane_malformed = _plane_bounds(plane)
        if plane_any_truncated:
            notes.append(
                f"{name}: evidence clipped at an output bound; the unread tail "
                "cannot be ruled out"
            )
        if plane_malformed:
            notes.append(f"{name}: evidence contains records this reader could not decode")
        declared_status = _plane_declared_status(plane)
        if declared_status != OBSERVED:
            notes.append(
                f"{name}: this decision declares the plane and the plane declares "
                f"observation_status {declared_status}"
            )
        plane_statuses.append(declared_status)
        any_bound_truncated = any_bound_truncated or plane_any_truncated
        malformed = malformed or plane_malformed
    return _EvidenceBounds(
        any_bound_truncated, malformed, sorted(notes), _worst(plane_statuses)
    )


def _decision(
    decision_id: str,
    discrepancies: list[str],
    evidence_count: int,
    status: str = OBSERVED,
    bounds: _EvidenceBounds | None = None,
    discrepancy_total: int | None = None,
) -> dict[str, Any]:
    """One decision record. An empty denominator cannot be ``OBSERVED``.

    Neither can clipped or undecodable evidence: ``bounds`` is applied AFTER
    the caller's status, so no caller can hand back a clean ``OBSERVED`` over
    evidence a bound cut short.

    Nor can a plane the decision DECLARES but that was not itself observed.
    ``bounds.plane_status`` is folded in last through :func:`_worst`, so a
    decision reports at worst what the weakest plane it declares reported —
    absence included, which no truncation flag records (``amendment:208``).
    Folding it with :func:`_worst` rather than assigning it preserves the
    existing ranking: ``ERROR`` dominates ``UNMEASURED`` dominates
    ``OBSERVED``, so a malformed read still resolves to ``ERROR`` and a
    clipped one still resolves to ``UNMEASURED``.

    Nor can a record whose own published lists were clipped.
    :data:`MAX_DISCREPANCIES` caps ``discrepancies`` and ``notes`` — one cap
    over one record, so one flag reports it — and ``discrepancy_count`` carries
    the PRE-CLIP total, which ``discrepancy_total`` supplies when this function
    rebuilds a record whose list has already been clipped once.

    NOR CAN A RECORD BUILT OVER A COUNT OUTSIDE ITS OWN DECLARED DOMAIN. Both
    published numbers are ``integer, minimum: 0`` in the schema, and both
    reached it through a ``max(0, ...)`` that turned an out-of-domain value
    into a clean zero with nothing named — the same laundering
    :func:`_recorded_count` carried, at the LAST reader rather than the first.
    Fixing only the first would have left this one covering for it: these two
    are the same category, so they are corrected together and by the same
    predicate. An out-of-domain count is NAMED into this record's own
    discrepancy list and forces ``UNMEASURED``; it is never clamped.
    """
    resolved = status
    domain_lost: list[str] = []
    if not _is_recorded_count(evidence_count):
        domain_lost.append(
            f"{decision_id} was built over evidence_count {evidence_count!r}, which is "
            "outside the non-negative integer domain this packet declares for a count"
        )
        evidence_count = 0
    if evidence_count <= 0:
        resolved = _worst([status, UNMEASURED])
    bounds = bounds if bounds is not None else _EvidenceBounds(False, False, [])
    total = len(discrepancies) if discrepancy_total is None else discrepancy_total
    if not _is_recorded_count(total):
        domain_lost.append(
            f"{decision_id} was built over discrepancy_count {discrepancy_total!r}, which "
            "is outside the non-negative integer domain this packet declares for a count"
        )
        total = len(discrepancies)
    if domain_lost:
        discrepancies = discrepancies + domain_lost
        total = max(total, len(discrepancies))
        resolved = _worst([resolved, UNMEASURED])
    discrepancy_truncated = total > MAX_DISCREPANCIES or len(bounds.notes) > MAX_DISCREPANCIES
    if bounds.malformed:
        resolved = ERROR
    elif bounds.any_bound_truncated or discrepancy_truncated:
        resolved = _worst([resolved, UNMEASURED])
    resolved = _worst([resolved, bounds.plane_status])
    return {
        "decision_id": decision_id,
        "observation_status": resolved,
        # NO `max(0, int(...))` HERE ANY MORE. Both numbers were checked
        # against :func:`_is_recorded_count` above and an out-of-domain one was
        # NAMED, so a clamp at the emission point can only hide a value the
        # named channel already reported — which is the shape being removed,
        # not a second belt.
        "evidence_count": evidence_count,
        "discrepancies": sorted(discrepancies)[:MAX_DISCREPANCIES],
        "discrepancy_count": total,
        "discrepancy_truncated": discrepancy_truncated,
        "evidence_bounds": {
            "any_bound_truncated": bool(bounds.any_bound_truncated),
            "malformed": bool(bounds.malformed),
            "notes": bounds.notes[:MAX_DISCREPANCIES],
        },
    }


def _is_recorded_location(key: Any) -> bool:
    """True when ``key`` is a RECORDED PATH rather than an authored field name.

    :data:`_VERDICT_KEY_TOKENS` is a FIELD-NAME rule: it splits on ``_`` and
    matches the vocabulary a field name would use. An inventory keys its
    entries BY PATH, and those paths are the SUBJECT's to choose, so an
    ordinary recorded file named ``build_pass_marker`` produced a D05
    discrepancy — and the manifest's positive arm requires zero, so a filename
    could DENY the observation. By the rule :func:`_is_declarable_root` states
    -- a candidate that can SUPPRESS a decision has steered it just as surely
    as one that can satisfy it -- that is steering, in the suppressing
    direction.

    Applying a field-name rule to a path is a category error in the PROBE, not
    a narrowing of D05's question: no observer-authored field name is an
    absolute path, the value under the key is still walked, and every authored
    key beneath it is still tested. A key wrongly exempted here yields noise,
    never silence.

    NOT FIXED, and disclosed in the manifest's ``scope_limits``: the VALUE side.
    A subject-written ``"sha256": "pass"`` is still a D05 discrepancy, because
    narrowing values WOULD narrow the question — an observer-authored verdict
    value is indistinguishable from a forwarded one without a corpus argument
    nobody here has.
    """
    return isinstance(key, str) and os.path.isabs(key)


def _verdict_leaks(node: Any, pointer: str, found: list[str]) -> int:
    """Walk the observation plane removing the verdict-vocabulary category."""
    examined = 1
    if isinstance(node, dict):
        for key in sorted(node):
            child = f"{pointer}/{key}"
            if not _is_recorded_location(key):
                tokens = {token for token in str(key).lower().split("_") if token}
                if tokens & _VERDICT_KEY_TOKENS:
                    found.append(f"verdict-vocabulary key at {child}")
            examined += _verdict_leaks(node[key], child, found)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            examined += _verdict_leaks(item, f"{pointer}/{index}", found)
    elif isinstance(node, str):
        if node.strip().lower().replace("-", "_") in _VERDICT_VALUE_TOKENS:
            found.append(f"verdict-vocabulary value at {pointer}")
    return examined


def _recorded_source_list(value: Any, label: str) -> tuple[list[str], list[str]]:
    """A recorded ``--setting-sources`` list this module can compare, and what it lost.

    The settings-source sibling of :func:`_settings_by_path`, and it exists for
    the same reason: the value is SUBJECT-RECORDED (``ladder:282``), so it is
    an INPUT to be read fail-closed rather than a value to be reshaped until it
    compares clean. Absent or ``None`` records nothing and names nothing — the
    comparison in :func:`_source_set_discrepancies` then reports the whole
    contract as unrecorded, which is the fail-CLOSED direction. Present and
    unwalkable is NAMED, and so is every member that is not a string: ``str(5)``
    and ``str("5")`` are the same two characters, so a coerced member is one
    this reader can no longer tell from a different member.
    """
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], [
            f"{label} records {value!r}, not a list of setting sources this reader "
            "can compare; the recorded source set is unmeasured"
        ]
    out: list[str] = []
    problems: list[str] = []
    for position, item in enumerate(value):
        if not isinstance(item, str):
            problems.append(
                f"{label} at index {position} records {item!r}, not a setting source "
                "name this reader can compare"
            )
            continue
        out.append(item)
    return out, problems


def _source_set_discrepancies(expected: list[str], recorded: list[str]) -> list[str]:
    """Every way ``recorded`` departs from the canonical ``expected`` source set.

    THE COMPARISON D07 IS NAMED FOR, and until this cycle it did not exist.
    ``D07_SETTINGS_SOURCE_SET_EXACT`` compared only declared-vs-observed
    settings FILE PATHS while three artifacts — ``amendment:190-198``, the
    manifest's ``expected_settings.setting_sources``, and the decision's own
    name — asserted that the source set was checked. A disclosure that a field
    is unread is honest only when nothing claims it is read; here three things
    claimed it, so the disclosure was a false contract rather than a scope
    limit, and it is removed by supplying the check rather than by softening
    the claim.

    ``expected`` IS THE CANONICAL CONTRACT and never another field of the
    subject's own document: its one home is the frozen manifest, the caller
    passes it in, and :func:`_settings_provenance` publishes it beside the
    recorded list so a third party can recompute this function and check the
    operand back against the manifest.

    THE ORDERING CONTRACT IS A MULTISET, and the grounding for that is the
    DOCUMENTED PRECEDENCE, not an experiment. ``--setting-sources`` is defined
    at https://code.claude.com/docs/en/cli-usage as a "Comma-separated list of
    setting sources to load (user, project, local)" — it SELECTS WHICH SOURCES
    LOAD, and that page says nothing about the list's order meaning anything.
    Precedence is fixed elsewhere and by LEVEL:
    https://code.claude.com/docs/en/settings orders settings highest-first as
    managed settings, command line (``claude --settings``), project-local
    (``.claude/settings.local.json``), shared project
    (``.claude/settings.json``), user (``~/.claude/settings.json``), with "A
    key set at a higher level overrides the same key set lower down." For the
    three SELECTABLE sources that is ``local > project > user``, fixed by
    level and INDEPENDENT of argv order. Argv order therefore carries no
    semantics, so a REORDER is not a violation and must be watched PERMITTING,
    while a missing, extra, replaced or duplicated member each changes the
    multiset and is REFUSED. Counting rather than set-differencing is what
    keeps the duplicate arm alive: ``set()`` on both sides reports
    ``["user","user","local"]`` as equal to ``["user","local"]``.

    WHAT THE BINARY WAS ASKED, AND THE ONLY THING IT ESTABLISHED: acceptance
    and refusal of the argv VALUE. Against claude 2.1.236, ``user,project,local``,
    ``local,project,user``, ``user,user,local`` and a bare ``project`` are each
    ACCEPTED, while ``USER,project,local`` and ``user,bogus,local`` are each
    REFUSED with ``Invalid setting source: <x>. Valid options are: user,
    project, local``. That is membership validation, and it is case-sensitive.
    It is NOT evidence that two orders behave identically: the probe ran
    ``doctor``, which reports on an installation, so an equal exit across two
    orders says the parser ACCEPTED both and nothing about how a session would
    resolve a key.

    UNVERIFIED HERE, and deliberately kept visible: the precedence above is
    DOCUMENTED, not MEASURED by this module. ``capture()`` executes no child
    (``run.child_executed`` is ``const: false``), so nothing here observes a
    real session resolving settings, and a real resolution that contradicted
    the documentation would be invisible to every arm of this function.
    """
    expected_counts = Counter(expected)
    recorded_counts = Counter(recorded)
    problems: list[str] = []
    for source in sorted(set(expected_counts) | set(recorded_counts)):
        want = expected_counts[source]
        got = recorded_counts[source]
        if want == got:
            continue
        problems.append(
            f"setting source {source!r} is recorded {got} time(s) where the canonical "
            f"source contract requires {want}"
        )
    return problems


def _settings_by_path(items: Any, side: str) -> tuple[dict[str, Any], list[str]]:
    """Index settings entries by ``path``, NAMING every entry the index drops.

    A dict comprehension over these lists keeps the LAST entry for a repeated
    path. ONE appended array element whose digest agreed with the other side
    therefore made D06 recompute zero discrepancies over an evidence file that
    still carried the mismatch, with ``evidence_count`` unchanged and no bound,
    flag or status able to see it. The collapse sat in the comprehension,
    upstream of the comparison — the same shape as the parser's last-wins rule
    :class:`_RepeatedJsonKey` closes one door earlier, reached through a
    different door: a list cannot carry a repeated JSON key, so no parse-time
    guard can reach it.

    Both losses are returned as NAMED discrepancies rather than dropped:

    * A repeated path, WHATEVER its value. A duplicate that agrees with the
      original is still evidence the recorder wrote the same source twice, and
      "harmless" is a judgement no reader here is positioned to make.
    * An entry carrying no usable path, over which the previous
      ``item["path"]`` raised ``KeyError`` and crashed :func:`reconcile`.
    * A recorded ``sha256`` that is not a string. It is NAMED and forwarded,
      never coerced: folding two distinct non-string digests to ``None`` made
      ``None != None`` False and erased the mismatch between them.
    * A ``declared``/``observed`` value that is not a list of entries at all.

    ``side`` names which list the entry came from, so a discrepancy points at
    the document that carries it.

    THIS FUNCTION IS NOW REACHED THROUGH BOTH DOORS. Until this cycle
    :func:`_settings_provenance` typed and dropped these entries first, so on
    the ``capture()`` route — the one the smoke command runs — nothing here
    could fire. It fired only for a caller who assembled the plane in memory
    and handed it to :func:`reconcile`. The normaliser is gone; the same
    malformed entry now reaches the same answer through either door.
    """
    index: dict[str, Any] = {}
    problems: list[str] = []
    if items is None:
        # Nothing recorded is not a declined record. An absent list degrades
        # through the plane's own `observation_status`, which every decision
        # that declares the plane already inherits.
        return index, problems
    if not isinstance(items, list):
        # NAMED, never replaced with `[]`. An empty index compares clean, and
        # comparing over evidence that was never there is the fail-OPEN
        # direction — the same shape as the entry drops below, one level up.
        problems.append(
            f"settings {side} is not a list of entries; it records {items!r}"
        )
        return index, problems
    for position, item in enumerate(items):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            problems.append(
                f"settings {side} entry at index {position} records no usable "
                f"path: {item!r}"
            )
            continue
        path = item["path"]
        if path in index:
            problems.append(
                f"settings {side} records {path} more than once; a repeated path "
                "collapses to its last value before any comparison"
            )
        digest = item.get("sha256")
        if digest is not None and not isinstance(digest, str):
            # NAMED, NEVER COERCED. `_settings_provenance` used to fold every
            # non-string digest to `None` before this function ran, so two
            # DISTINCT non-string digests compared equal and the mismatch they
            # carried disappeared. The raw value is carried into the packet by
            # this string, so a third party recomputing from the same bytes
            # reaches the same discrepancy — which is the property the coercion
            # destroyed and the `non_self_certification` claim depends on.
            problems.append(
                f"settings {side} records a non-string sha256 for {path}: {digest!r}"
            )
        index[path] = digest
    return index, problems


def _private_root_entries(
    plane: dict[str, Any],
) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
    """Private-root entries D12 can read, and a NAME for every one it cannot.

    An entry recorded as a scalar used to leave this list silently. D12's
    denominator shrank from two to one, no bound fired, no flag moved, and the
    packet was byte-identical to a run in which the entry never existed — so
    the shape D12 exists to catch escaped it by not being a dict. Every
    excluded entry is now named on the discrepancy channel and counted in the
    denominator, which is the same treatment :func:`_settings_by_path` already
    gave the settings lists.
    """
    # `or []` here, not a `.get` default: a default only fires on an ABSENT
    # key, so a plane recording `"declared_writable_roots": null` reached the
    # iteration on None. The `pre`/`post` sides went the same way through
    # `(plane.get(side) or {})`, which handled `null` and then crashed on
    # `["a"]`, `"a"` and `7` — the SAME AttributeError the top-level plane
    # reads in `reconcile` carried, one level down and through a different
    # door. Both doors now go through `_plane_mapping`.
    if not isinstance(plane, dict):
        return [], [
            "filesystem plane is not a mapping, so no entry beneath a declared "
            "root is readable from it"
        ]
    # THE SAME READER `reconcile` USES, for the same reason: `for root in
    # roots` over a recorded `7` raised `TypeError`, and over a recorded
    # `"/proof"` would have iterated seven single-character "roots" -- one
    # crash and one silent fabrication out of the same unguarded read.
    roots, problems = _recorded_sequence(
        plane, "declared_writable_roots", "filesystem.declared_writable_roots"
    )
    out: list[tuple[str, dict[str, Any]]] = []
    for side in ("pre", "post"):
        raw_side = plane.get(side)
        side_plane, _side_status = _plane_mapping(plane, side)
        if raw_side is not None and not isinstance(raw_side, dict):
            problems.append(
                f"filesystem {side} is recorded as {type(raw_side).__name__}, "
                "not a snapshot object; no entry beneath a declared root is "
                "readable from it"
            )
            continue
        entries = side_plane.get("entries") or {}
        if not isinstance(entries, dict):
            problems.append(
                f"filesystem {side} records `entries` as {type(entries).__name__}, "
                "not a path map; no entry beneath a declared root is readable from it"
            )
            continue
        for path, entry in entries.items():
            if not any(_is_within(path, root) for root in roots):
                continue
            if not isinstance(entry, dict):
                problems.append(
                    f"{side}:{path} records its entry as {entry!r}, not a "
                    "mode/owner record D12 can read"
                )
                continue
            out.append((f"{side}:{path}", entry))
    return out, problems


#: ``$defs/sha256``'s pattern, verbatim. ``fullmatch`` rather than ``match`` so
#: the anchors are not left to the caller.
_SHA256_HEX_RE = re.compile(r"[0-9a-f]{64}")


def _is_sha256_hex(value: Any) -> bool:
    """True for the exact ``$defs/sha256`` domain: 64 lowercase hex characters.

    A non-string is False rather than coerced. ``str(12345)`` would have made a
    recorded integer into a short "digest" and moved the question from "is this
    in domain" to "does this look like one after we rewrote it".
    """
    return isinstance(value, str) and _SHA256_HEX_RE.fullmatch(value) is not None


def _path_entry_domain_problems(
    label: str, entry: Any, *, skip_fields: frozenset[str] = frozenset()
) -> list[str]:
    """Every way ``entry`` leaves the domain ``$defs/path_entry`` declares.

    THE QUESTION IS PACKET WELL-FORMEDNESS, NOT A DECISION'S SUBJECT. D11 asks
    whether content changed and D12 asks whether mode and owner were recorded
    faithfully; this asks whether a value the observer FORWARDS VERBATIM is
    inside the domain the observer's own schema states for it. The three
    questions are distinct, which is why the answers do not collapse into one
    another and why ``skip_fields`` exists: within D12's scope the mode/uid/acl
    triple already has a reader, and naming one bad value twice would be noise.

    NOTHING IS CLAMPED, COERCED OR DROPPED. The caller keeps forwarding the raw
    value; this only produces the name. Clamping is how a finding disappears —
    the correction ``_recorded_count`` already had to make once, where
    ``max(0, raw)`` turned a recorded ``-1`` and a recorded ``-99`` into the same
    silent ``0``.

    ``bool`` is excluded before ``int`` in both numeric clauses for the reason
    :func:`_is_recorded_count` states: ``isinstance(True, int)`` is True, so a
    recorded ``true`` would otherwise rank as the length ``1``.
    """
    if not isinstance(entry, dict):
        return [
            f"inventory entry at {label} records {entry!r}, not the object "
            "$defs/path_entry declares"
        ]
    problems: list[str] = []
    unknown = sorted(set(entry) - set(_PATH_ENTRY_FIELDS))
    if unknown:
        problems.append(
            f"inventory entry at {label} carries {unknown!r}, which "
            "$defs/path_entry does not declare and closes out"
        )
    missing = [name for name in _PATH_ENTRY_FIELDS if name not in entry]
    if missing:
        problems.append(
            f"inventory entry at {label} omits {missing!r}, which "
            "$defs/path_entry requires"
        )
    for name in _PATH_ENTRY_FIELDS:
        if name in skip_fields or name not in entry:
            continue
        value = entry[name]
        if name == "kind":
            # `isinstance` FIRST: `value in <frozenset>` hashes its operand, and
            # a recorded list or dict raises TypeError there — an uncaught
            # exception out of a PUBLIC reconcile() on exactly the malformed
            # input this guard exists to name.
            bad = not isinstance(value, str) or value not in _PATH_ENTRY_KINDS
            domain = f"one of {sorted(_PATH_ENTRY_KINDS)}"
        elif name == "sha256":
            bad = value is not None and not _is_sha256_hex(value)
            domain = "a 64-character lowercase hex digest or null"
        elif name == "bytes":
            bad = value is not None and not _is_recorded_count(value)
            domain = "$defs/byte_count (integer, minimum 0) or null"
        elif name == "content_truncated":
            bad = not isinstance(value, bool)
            domain = "a boolean"
        elif name == "mode":
            bad = (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not (0 <= value <= _POSIX_MODE_CEILING)
            )
            domain = f"$defs/posix_mode (integer, 0..{_POSIX_MODE_CEILING})"
        elif name == "uid":
            bad = value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            )
            domain = "an integer owner id (minimum 0) or null"
        else:  # acl_state
            bad = value != UNMEASURED
            domain = f"the constant {UNMEASURED!r}"
        if bad:
            problems.append(
                f"inventory entry at {label} records {name}={value!r}, outside "
                f"the domain $defs/path_entry declares for it ({domain}); the "
                "value is forwarded unchanged and named here, degrading the "
                "decision that consumes it"
            )
    return problems


def _forwarded_entry_domain_problems(
    plane: dict[str, Any], private_labels: frozenset[str]
) -> list[str]:
    """:func:`_path_entry_domain_problems` over every entry both sides forward.

    ``private_labels`` are the ``side:path`` labels D12 reads, and only there is
    the mode/uid/acl triple skipped — outside D12's declared scope nothing else
    reads them, which is the leak this closes. D12's scope is stated in the
    manifest's ``decision_scopes``; this function is the reason stating it does
    not also mean leaving the gap open.
    """
    problems: list[str] = []
    for side in ("pre", "post"):
        side_plane, _status = _plane_mapping(plane, side)
        entries, _lost = _recorded_path_map(side_plane, "entries", f"filesystem.{side}.entries")
        for path, entry in sorted(entries.items(), key=lambda item: str(item[0])):
            label = f"{side}:{path}"
            problems += _path_entry_domain_problems(
                label,
                entry,
                skip_fields=_D12_PATH_ENTRY_FIELDS if label in private_labels else frozenset(),
            )
    return problems


def reconcile(observation: dict[str, Any]) -> dict[str, Any]:
    """Recompute every deciding observation and return the proof packet.

    Reads the ``observation`` plane only. The candidate claim is recorded by
    digest elsewhere and is never parsed here, so no candidate-authored summary
    can become this function's answer (``ladder:282``).

    The packet carries no pass, candidate, promotion, or release state
    (``amendment:191``). It reports what was observed, what was unmeasured, and
    where recomputation disagreed with what was recorded.
    """
    if not isinstance(observation, dict):
        raise TypeError("observation must be a dict")
    # The parse-boundary guard covers documents this module READS. It does not
    # reach an observation a caller built in memory, and this function's own
    # readers are recursive, so the depth is refused BY NAME here rather than
    # surfacing as an uncaught RecursionError (CWE-674).
    if _exceeds_walk_depth(observation):
        raise ValueError(
            f"observation nests deeper than MAX_DOCUMENT_DEPTH ({MAX_DOCUMENT_DEPTH}); "
            "no reader in this module can walk it"
        )

    decisions: list[dict[str, Any]] = []

    # EVERY SUB-PLANE READ BELOW GOES THROUGH `_recorded_sequence`,
    # `_recorded_path_map` OR `_recorded_count`, for the reason `_plane_mapping`
    # gives one level up: `reconcile` is PUBLIC, a malformed packet is an
    # INPUT, and the eight PLANE reads were hardened while the thirteen
    # SUB-PLANE reads on the next lines were not. Twelve of the thirteen raised
    # uncaught on `["a"]`, `"a"`, `7`, `1.5` or `True`. Every such read now
    # yields the empty container AND a named problem, and the problem is BOTH
    # appended to the discrepancies of the decision that reads it and folded
    # into that decision's status by `_degraded` — so a shape this reader
    # cannot walk can neither crash the caller nor read clean.
    schema_audit, schema_status = _plane_mapping(observation, "schema_audit")
    schema_examined, schema_examined_lost = _recorded_count(
        schema_audit, "_examined", "schema_audit._examined"
    )
    root_unknown, root_lost = _recorded_sequence(
        schema_audit, "root_unknown_fields", "schema_audit.root_unknown_fields"
    )
    composed_unknown, composed_lost = _recorded_sequence(
        schema_audit, "composed_unknown_fields", "schema_audit.composed_unknown_fields"
    )
    decisions.append(
        _decision(
            "D01_SCHEMA_ROOT_CLOSED",
            [f"unknown root field {field}" for field in root_unknown]
            + root_lost
            + schema_examined_lost,
            schema_examined,
            _degraded(schema_status, root_lost + schema_examined_lost),
        )
    )
    decisions.append(
        _decision(
            "D02_SCHEMA_COMPOSED_CLOSED",
            [f"unknown composed field {field}" for field in composed_unknown]
            + composed_lost
            + schema_examined_lost,
            schema_examined,
            _degraded(schema_status, composed_lost + schema_examined_lost),
        )
    )

    source_audit, source_status = _plane_mapping(observation, "source_audit")
    static_findings, static_lost = _recorded_sequence(
        source_audit, "static_findings", "source_audit.static_findings"
    )
    static_examined, static_examined_lost = _recorded_count(
        source_audit, "_static_examined", "source_audit._static_examined"
    )
    decisions.append(
        _decision(
            "D03_NO_STATIC_PRODUCT_IMPORT",
            [
                _finding_text(finding, position, "source_audit.static_findings")
                for position, finding in enumerate(static_findings)
            ]
            + static_lost
            + static_examined_lost,
            static_examined,
            _degraded(source_status, static_lost + static_examined_lost),
        )
    )
    dynamic_findings, dynamic_field_lost = _recorded_sequence(
        source_audit, "dynamic_findings", "source_audit.dynamic_findings"
    )
    runtime_findings, runtime_field_lost = _recorded_sequence(
        source_audit, "runtime_findings", "source_audit.runtime_findings"
    )
    dynamic = list(dynamic_findings) + list(runtime_findings)
    dynamic_examined, dynamic_examined_lost = _recorded_count(
        source_audit, "_dynamic_examined", "source_audit._dynamic_examined"
    )
    dynamic_lost = dynamic_field_lost + runtime_field_lost + dynamic_examined_lost
    decisions.append(
        _decision(
            "D04_NO_DYNAMIC_PRODUCT_IMPORT",
            [
                _finding_text(finding, position, "source_audit.dynamic/runtime_findings")
                for position, finding in enumerate(dynamic)
            ]
            + dynamic_lost,
            dynamic_examined,
            _degraded(source_status, dynamic_lost),
        )
    )

    leaks: list[str] = []
    leak_examined = _verdict_leaks(observation, "", leaks)
    decisions.append(_decision("D05_NO_CANDIDATE_VERDICT_IN_OBSERVATION", leaks, leak_examined))

    settings, settings_status = _plane_mapping(observation, "settings")
    # Both decisions below compare INDEXES BY PATH, so both decide over
    # whatever the indexing lost. `collapsed` is therefore reported on BOTH,
    # not on the one whose masking was reproduced first.
    #
    # AND THROUGH `_degraded`, WHICH HAS NO EXCEPTIONS. D06 and D07 were the
    # only two decisions in this function handing their plane's status through
    # RAW while D01-D04, D08/D09 and D10-D12 all pass it through
    # :func:`_degraded`. A defeated `_settings_by_path` read therefore NAMED
    # its loss on the discrepancy channel without forcing ERROR — the whole
    # value of a chokepoint is that nothing routes around it, so a chokepoint
    # with two exceptions is a convention.
    declared, declared_lost = _settings_by_path(settings.get("declared"), "declared")
    observed, observed_lost = _settings_by_path(settings.get("observed"), "observed")
    # THE SOURCE SET, RE-DERIVED HERE AND NOT READ OFF A CAPTURE-TIME VERDICT,
    # for the reason `_decision_from_exit` is re-run in this function: the
    # comparison has to be recomputable from the packet by a third party who
    # ran none of the capture. Both operands are published in the plane, and
    # they are of DIFFERENT provenance by construction — `expected_...` is the
    # caller-supplied canonical contract whose one home is the frozen
    # manifest, `setting_sources` is what the SUBJECT recorded. Comparing a
    # subject field with another subject field is the self-certification this
    # replaces (``ladder:282``): the observed value used to track the
    # subject's own document with nothing to check it against.
    recorded_sources, recorded_sources_lost = _recorded_source_list(
        settings.get("setting_sources"), "settings.setting_sources"
    )
    expected_sources, expected_sources_lost = _recorded_source_list(
        settings.get("expected_setting_sources"), "settings.expected_setting_sources"
    )
    source_lost = recorded_sources_lost + expected_sources_lost
    # A MISSING CONTRACT CANNOT READ CLEAN. With no canonical operand there is
    # nothing to compare against, and an empty expected list would make EVERY
    # recorded set "exact" — the fail-OPEN direction, and the direction the
    # whole defect ran in.
    #
    # IT IS AN ABSENCE, NOT A DEFEATED READER, and the two get different
    # answers on purpose. `_degraded` reports ERROR, which this module reserves
    # for a value shaped so its readers lose — a contract recorded as `7` or
    # `"a"` earns that through `expected_sources_lost` above. Nothing recorded
    # at all is UNMEASURED, the same answer an ABSENT plane already gets, and
    # collapsing the two would have made an absent `settings` plane report
    # ERROR where every other plane reports UNMEASURED.
    contract_absent = (
        []
        if (expected_sources or expected_sources_lost)
        else [
            "settings.expected_setting_sources records no canonical source contract, so "
            "the recorded setting sources are compared against nothing and are unmeasured"
        ]
    )
    source_exact = (
        []
        if (source_lost or contract_absent)
        else _source_set_discrepancies(expected_sources, recorded_sources)
    )
    collapsed = declared_lost + observed_lost
    settings_status = _degraded(settings_status, collapsed)
    common = sorted(set(declared) & set(observed))
    decisions.append(
        _decision(
            "D06_SETTINGS_DIGEST_MATCH",
            [
                f"settings digest mismatch for {path}: declared {declared[path]} observed {observed[path]}"
                for path in common
                if _recorded_values_differ(declared[path], observed[path])
            ]
            + collapsed,
            len(common),
            settings_status,
        )
    )
    # D07 NOW ASKS BOTH HALVES OF THE QUESTION ITS NAME PROMISES. The
    # settings-FILE half (declared vs observed paths) is the one it always
    # asked; the SOURCE-SET half — the recorded `--setting-sources` list
    # against the canonical contract — is this cycle's addition, and without it
    # the decision was named for a field no code read. The denominator counts
    # both: the union of settings paths PLUS every source name either side of
    # the source comparison mentions, so a run whose only evidence is the
    # source set cannot report a zero denominator, and one whose source
    # contract was unreadable degrades through `_degraded` exactly as a
    # defeated path read does.
    decisions.append(
        _decision(
            "D07_SETTINGS_SOURCE_SET_EXACT",
            [f"undeclared observed source {p}" for p in sorted(set(observed) - set(declared))]
            + [f"declared source not observed {p}" for p in sorted(set(declared) - set(observed))]
            + source_exact
            + collapsed
            + source_lost
            + contract_absent,
            len(set(declared) | set(observed))
            + len(set(expected_sources) | set(recorded_sources)),
            _worst(
                [_degraded(settings_status, source_lost)]
                + ([UNMEASURED] if contract_absent else [])
            ),
        )
    )

    hooks, hooks_status = _plane_mapping(observation, "hooks")
    joins, joins_lost = _recorded_sequence(hooks, "joins", "hooks.joins")
    orphans_recorded, orphans_lost = _recorded_sequence(
        hooks, "orphan_tool_use_ids", "hooks.orphan_tool_use_ids"
    )
    unrankable_recorded, unrankable_lost = _recorded_sequence(
        hooks, "unrankable_record_types", "hooks.unrankable_record_types"
    )
    stream_id_count, stream_count_lost = _recorded_count(
        hooks, "_stream_id_count", "hooks._stream_id_count"
    )
    # NAMED ON BOTH DECISIONS THAT READ THE JOIN. A stream record whose `type`
    # this reader could not rank is missing from the orphan set AND from the
    # receiptless set, so reporting it on only the one whose masking was
    # reproduced first would leave the other reading clean over the same loss.
    unrankable = [str(note) for note in unrankable_recorded]
    d08_lost = orphans_lost + unrankable_lost + joins_lost + stream_count_lost
    decisions.append(
        _decision(
            "D08_HOOK_TOOL_USE_ID_JOIN",
            [f"tool_use_id without a lifecycle partner: {tid}" for tid in orphans_recorded]
            + unrankable
            + d08_lost,
            stream_id_count + len(joins),
            _degraded(hooks_status, d08_lost),
        )
    )
    # Any non-zero exit is an anomaly for this carrier: the P0 manifest holds
    # exactly one dedicated, non-blocking diagnostic canary that always exits
    # zero (amendment:52-53). A stream that reports success over a hook that
    # did not is precisely the evidence a packet must not lose.
    #
    # The receipts are the ONLY place an exit code is observable, so a stream
    # `hook_event` with no receipt is a hook whose outcome was never measured
    # -- not a hook that was quiet. Surviving benign receipts keep `joins`
    # populated, so the two IDENTITY MULTISETS are compared rather than the
    # counts. Each uncovered event is named as its own discrepancy and forces
    # UNMEASURED: this decision cannot answer its question over a receipt set
    # it knows is incomplete (``amendment:208``).
    receiptless_recorded, receiptless_lost = _recorded_sequence(
        hooks, "hook_events_without_receipt", "hooks.hook_events_without_receipt"
    )
    surplus_recorded, surplus_lost = _recorded_sequence(
        hooks, "receipts_without_hook_event", "hooks.receipts_without_hook_event"
    )
    receiptless = [str(tid) for tid in receiptless_recorded]
    surplus = [str(tid) for tid in surplus_recorded]

    # THE DECISION IS RE-DERIVED FROM THE EXIT EVIDENCE, never read off the
    # join's own `decision` field. `decision` and `exit_code` are SIBLINGS on
    # one record, and D09 believed the sibling: a packet recording
    # `{"exit_code": 2, "decision": "SILENT"}` reported zero discrepancies,
    # and the reverse -- `{"exit_code": 0, "decision": "NONZERO"}` --
    # manufactured a non-zero finding out of a clean exit. Either direction is
    # a caller-authored answer standing in for the measurement
    # (``ladder:282``). `_decision_from_exit` is the SAME function that derived
    # the value at capture time, so an honest packet re-derives identically and
    # names nothing.
    #
    # A CONTRADICTION IS NOT SILENTLY OVERRIDDEN. The derived value decides,
    # AND the disagreement is named and degrades the decision: a packet whose
    # two fields disagree is a packet at least one of whose fields is
    # untrustworthy, and this reader cannot tell which.
    nonzero: list[str] = []
    join_problems: list[str] = []
    for position, join in enumerate(joins):
        if not isinstance(join, dict):
            join_problems.append(
                f"hooks.joins at index {position} records {join!r}, not a join "
                "record this reader can walk"
            )
            continue
        exit_code = join.get("exit_code")
        stdout_bytes = join.get("stdout_bytes")
        derived = _decision_from_exit(exit_code, stdout_bytes)
        recorded = join.get("decision")
        if derived is None:
            join_problems.append(
                f"hooks.joins at index {position} for {join.get('tool_use_id')!r} "
                f"records exit_code {exit_code!r} and stdout_bytes "
                f"{stdout_bytes!r}: no exit evidence this reader can rank, so "
                f"its recorded decision {recorded!r} is unmeasured"
            )
            continue
        if recorded != derived:
            join_problems.append(
                f"hooks.joins at index {position} for {join.get('tool_use_id')!r} "
                f"records decision {recorded!r} while its own exit evidence "
                f"(exit_code {exit_code!r}, stdout_bytes {stdout_bytes!r}) "
                f"derives {derived!r}"
            )
        if derived == "NONZERO":
            nonzero.append(
                "hook {0} exited {1} for {2} while the stream reports {3!r}".format(
                    join.get("hook_event_name"),
                    exit_code,
                    join.get("tool_use_id"),
                    join.get("stream_outcome"),
                )
            )
    d09_lost = receiptless_lost + surplus_lost + unrankable_lost + joins_lost
    decisions.append(
        _decision(
            "D09_HIDDEN_HOOK_NONZERO",
            nonzero
            + [
                f"stream reports a hook fired for {tid} but no debug receipt "
                "records its exit code: the hook outcome is unmeasured"
                for tid in receiptless
            ]
            + [
                f"a debug receipt records a hook exit for {tid} that no stream "
                "hook_event reports: the two evidence sides disagree about "
                "which hooks ran"
                for tid in surplus
            ]
            + unrankable
            + join_problems
            + d09_lost,
            len(joins),
            _degraded(
                _worst([hooks_status, UNMEASURED])
                if (receiptless or surplus or unrankable or join_problems)
                else hooks_status,
                d09_lost,
            ),
        )
    )

    filesystem, filesystem_status = _plane_mapping(observation, "filesystem")
    roots, roots_lost = _recorded_sequence(
        filesystem, "declared_writable_roots", "filesystem.declared_writable_roots"
    )
    # THE NESTED PAIR GOES THROUGH THE SAME READER. `(filesystem.get("pre") or
    # {}).get(...)` crashed on a `pre` recorded as a list, a string or an int
    # exactly as the top-level read did, one level down. Their statuses are
    # FOLDED into the plane's own with `_worst` rather than replacing it: the
    # plane declares a status about itself, and a nested object this reader
    # cannot walk can only make that worse, never better. Absent `pre`/`post`
    # yield UNMEASURED here, which is what an fs plane carrying no snapshot
    # pair already reported through its own status.
    #
    # AND THE SUB-PLANE PAIR ONE LEVEL BELOW THAT. `pre_plane.get("entries")`
    # was the read the hardening stopped short of: `set(7)` raised `TypeError`
    # at the `set(post_entries) - set(pre_entries)` line below, BEFORE
    # `_private_root_entries` -- the reader that NAMES a non-map `entries` --
    # was ever reached. A comment
    # beside `_filesystem_planes` claimed "both doors refuse" of exactly this
    # input; the second door was unreachable because execution died at the
    # first. It refuses here now, so the claim is true rather than aspirational.
    pre_plane, pre_status = _plane_mapping(filesystem, "pre")
    post_plane, post_status = _plane_mapping(filesystem, "post")
    pre_entries, pre_entries_lost = _recorded_path_map(
        pre_plane, "entries", "filesystem.pre.entries"
    )
    post_entries, post_entries_lost = _recorded_path_map(
        post_plane, "entries", "filesystem.post.entries"
    )
    # THE DOMAIN OF EVERY FORWARDED ENTRY, on the same channel as the reads that
    # lost something. `_filesystem_planes` forwards `entries` VERBATIM, so a
    # value outside the domain `$defs/path_entry` declares reaches the emitted
    # packet. Three such values — `bytes: -1`, `kind: "wormhole"`,
    # `sha256: 12345` — were measured
    # producing rc=0 with every decision clean. They are NAMED here, not
    # clamped, and the raw value still goes out: a document whose records leave
    # their own declared domain is not one this reader can vouch for, so it
    # degrades the plane exactly as an undeclarable root already does.
    #
    # `_private_root_entries` is called ONCE, here, and reused by D12 below.
    # Calling it twice would let the two readings drift.
    private_entries, private_unreadable = _private_root_entries(filesystem)
    entry_domain_lost = _forwarded_entry_domain_problems(
        filesystem, frozenset(label for label, _entry in private_entries)
    )
    fs_lost = roots_lost + pre_entries_lost + post_entries_lost + entry_domain_lost
    fs_status = _degraded(
        _worst([filesystem_status, pre_status, post_status]), fs_lost
    )

    new_paths = sorted(set(post_entries) - set(pre_entries))
    decisions.append(
        _decision(
            "D10_NO_WRITE_OUTSIDE_DECLARED_ROOTS",
            [
                f"persistent write outside every declared writable root: {path}"
                for path in new_paths
                if not any(_is_within(path, root) for root in roots)
            ]
            + fs_lost,
            len(post_entries),
            fs_status,
        )
    )

    common_paths = sorted(set(pre_entries) & set(post_entries))
    silent: list[str] = []
    for path in common_paths:
        if any(_is_within(path, root) for root in roots):
            continue
        before = pre_entries[path]
        after = post_entries[path]
        if not isinstance(before, dict) or not isinstance(after, dict):
            # NAMED, NOT COERCED TO `{}`. Two non-dict entries both became the
            # empty dict, `{} == {}` compared equal, and a content change on a
            # path outside every declared root read exactly like no change at
            # all. The raw pair is carried into the discrepancy so the
            # difference stays recomputable from the packet.
            silent.append(
                f"inventory entry for {path} is not a digest record on both "
                f"sides, so no content comparison is possible: pre {before!r} "
                f"post {after!r}"
            )
            continue
        # JSON IDENTITY, NOT PYTHON EQUALITY. `1 == True`, `0 == False` and
        # `1 == 1.0` are all True, so a pre/post pair recording two DIFFERENT
        # digests compared equal here and a content change outside every
        # declared root read exactly like no change at all — no coercion
        # involved, so every guard aimed at coercions was blind to it. The
        # settings twin reaches the same answer through `_settings_by_path`,
        # which names a non-string digest before any comparison runs.
        if not _recorded_values_differ(before.get("sha256"), after.get("sha256")):
            continue
        silent.append(
            f"content changed outside every declared writable root: {path} "
            f"{before.get('sha256')} -> {after.get('sha256')}"
        )
    decisions.append(
        _decision(
            "D11_NO_SILENT_CONTENT_CHANGE", silent + fs_lost, len(common_paths), fs_status
        )
    )

    faithless: list[str] = []
    for label, entry in private_entries:
        mode = entry.get("mode")
        # `isinstance(True, int)` is True and `stat.S_IMODE(True) == 1 == True`,
        # so `"mode": true` passed this test as a faithfully recorded permission
        # set. `bool` is excluded FIRST: it is a subclass of `int` that no
        # `S_IMODE` round-trip can separate from the value it equals.
        #
        # THE VALUE DOMAIN IS TESTED BEFORE THE C-LEVEL CONVERSION, and the
        # ORDER is the fix, not the extra clause. Both guards above cover the
        # TYPE domain the reported `"mode": true` bug used; `stat.S_IMODE` is a
        # C call over `unsigned int`, and once the short-circuit clears the two
        # type tests the VALUE reaches it unchecked. `mode` is subject-authored
        # -- `_filesystem_planes` forwards a recorded `entries` verbatim -- so
        # `-1`, `2**32` and `2**64` each raised `OverflowError` out of
        # `reconcile`, which is an `ArithmeticError` and so outside `_cli`'s
        # `except ValueError`: traceback, exit 1, ZERO packet bytes, on the arm
        # reserved for a refused argv. The schema's own `$defs/posix_mode` says
        # integer 0..4095; :data:`_POSIX_MODE_CEILING` is that ceiling, tested
        # here BEFORE the round-trip rather than inferred from surviving it.
        # The sibling `uid` test below already had its value-domain half
        # (`uid < 0`); `mode` was left with the type half only.
        if (
            isinstance(mode, bool)
            or not isinstance(mode, int)
            or not (0 <= mode <= _POSIX_MODE_CEILING)
            or mode != stat.S_IMODE(mode)
        ):
            faithless.append(
                f"recorded mode {mode!r} at {label} is not a stat.S_IMODE value"
            )
        uid = entry.get("uid")
        if uid is not None and (isinstance(uid, bool) or not isinstance(uid, int) or uid < 0):
            faithless.append(f"recorded uid {uid!r} at {label} is not an owner id")
        if entry.get("acl_state") != UNMEASURED:
            faithless.append(
                f"acl_state at {label} is {entry.get('acl_state')!r}; mode bits are "
                "not a complete access description"
            )
    # The DENOMINATOR counts the entries this decision could not read as well
    # as the ones it could. Excluding them shrank `evidence_count` from 2 to 1
    # and made the packet byte-identical to a run that recorded one clean entry
    # — less evidence reading cleaner than the violation it concealed.
    decisions.append(
        _decision(
            "D12_MODE_OWNER_RECORDED_FAITHFULLY",
            faithless + private_unreadable + roots_lost,
            len(private_entries) + len(private_unreadable),
            # A faithless mode/uid/acl inside D12's own scope is skipped by the general
            # domain reader so one bad value is named once — which left the naming without the
            # degradation: D12 reported OBSERVED while carrying the discrepancy.
            _degraded(fs_status, faithless),
        )
    )

    # SINGLE CHOKEPOINT for the output bounds. Every decision above is rebuilt
    # here with the bounds of the planes it actually reads, so no call site can
    # forget one and no decision can leave this function reporting a clean
    # OBSERVED over evidence that a bound cut short (reviewer FINDING-1: the
    # module's stated invariant was previously aspirational).
    decisions = [
        _decision(
            record["decision_id"],
            record["discrepancies"],
            record["evidence_count"],
            record["observation_status"],
            _evidence_bounds(observation, record["decision_id"]),
            record["discrepancy_count"],
        )
        for record in decisions
    ]
    unmapped = sorted(set(DECISION_IDS) - set(DECISION_EVIDENCE_PLANES))
    if unmapped:  # pragma: no cover - the self-test asserts this stays empty
        raise AssertionError(f"decisions with no declared evidence planes: {unmapped}")

    # Summed from the PRE-CLIP per-decision counts, so the cap cannot remove
    # the extent of what it clipped.
    discrepancy_count = sum(int(d["discrepancy_count"]) for d in decisions)
    return {
        "schema_version": SCHEMA_VERSION,
        "observation": _strip_private(observation),
        # Placeholder only. The claim is recorded by digest by the caller; this
        # function never parses candidate bytes, so it cannot consume a
        # candidate-authored summary as its own answer (ladder:282).
        "candidate_claim": {
            "present": False,
            "source_path": None,
            "sha256": None,
            "bytes": None,
            "byte_truncated": False,
            "read_by_reconcile": False,
        },
        "comparison": {
            "decisions": decisions,
            "decision_ids": list(DECISION_IDS),
            "discrepancy_count": discrepancy_count,
            "observation_status": _worst(d["observation_status"] for d in decisions),
        },
    }


def _strip_private(node: Any) -> Any:
    """Drop this module's bookkeeping keys so the packet matches the schema.

    Keys are matched against :data:`PRIVATE_BOOKKEEPING_KEYS` by NAME. An
    ``_``-prefix rule also deleted subject-supplied keys, and an inventory key
    is a path: a discrepancy could cite a path the emitted packet no longer
    contained, so the packet was not self-recomputable.
    """
    if isinstance(node, dict):
        return {
            k: _strip_private(v) for k, v in node.items()
            if k not in PRIVATE_BOOKKEEPING_KEYS
        }
    if isinstance(node, list):
        return [_strip_private(item) for item in node]
    return node


# --------------------------------------------------------------------------
# Private CLI — the verifier-process entry point
# --------------------------------------------------------------------------


def _cli(raw_args: list[str] | None = None) -> int:
    """Emit one packet as JSON on stdout.

    The self-test drives this in a subprocess so the observer runs in a process
    whose ``sys.path`` excludes product modules (``ladder:286``); the pytest
    process cannot supply that, because ``tests/conftest.py`` injects product
    paths into every test.
    """
    parser = argparse.ArgumentParser(prog="observe_claude_execution", add_help=True)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--session-uuid", default=None)
    parser.add_argument("--settings-overlay", required=True)
    # REQUIRED, WITH NO DEFAULT, and the missing default is the point. This
    # argument is the canonical settings-source contract, and a default of
    # "user,project,local" here was that contract RESTATED inside the subject
    # it is used to check — a second home for a value whose one home is the
    # frozen manifest's `expected_settings.setting_sources`. With the default
    # in place the smoke route never passed the flag at all, so the observer
    # supplied its own expected answer and D07's operand came from the thing
    # under observation. The caller reads the manifest and passes it.
    parser.add_argument("--setting-sources", required=True)
    parser.add_argument("--debug-file", required=True)
    args = parser.parse_args(raw_args)

    run_root = Path(args.run_root)
    try:
        observation = capture(
            cwd=Path(args.cwd),
            run_root=run_root,
            session_uuid=args.session_uuid or str(uuid.uuid4()),
            settings_overlay=Path(args.settings_overlay),
            setting_sources=[s for s in args.setting_sources.split(",") if s],
            debug_file=Path(args.debug_file),
        )
        packet = reconcile(observation)
    except ValueError as exc:
        # A refused argv is a deliberate, named outcome, not a crash: report the
        # reason on stderr and exit non-zero rather than emitting a traceback
        # that a caller has to parse. No packet is written, because a refused
        # run produced no observation to write one about.
        sys.stderr.write(f"observe_claude_execution: refused: {exc}\n")
        return 2
    packet["candidate_claim"] = _candidate_claim_plane(run_root)
    try:
        # `allow_nan=False` is the SECOND half of the non-finite fix and it is
        # deliberately not the only half: `_refuse_non_finite` stops the three
        # tokens at every parse, and this stops any that reached the packet by
        # some other route. Rendered to a string FIRST -- `json.dump` streams,
        # so a raise partway through would already have written a truncated
        # document to stdout that a reader could not tell from a whole one.
        rendered = json.dumps(packet, indent=2, sort_keys=True, allow_nan=False)
    except ValueError as exc:
        # ITS OWN EXIT CODE, not the refused-argv 2. An unserialisable packet
        # is neither a bad argument nor a clean run, and reporting it on the
        # argv arm is the misattribution this module has now corrected three
        # times. No bytes are written, because a document a third party cannot
        # reparse is worse than no document.
        sys.stderr.write(f"observe_claude_execution: unserialisable packet: {exc}\n")
        return 3
    sys.stdout.write(rendered + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess
    raise SystemExit(_cli())
