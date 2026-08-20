#!/usr/bin/env bash
# PreToolUseWrite hook for autonomous-dev v2.0
# Blocks writes to sensitive files (credentials, git internals, etc.)
#
# Issue #1587 — refusing and recording are ONE act.
#
# This hook produced a valid deny payload on two paths and recorded nothing,
# so every refusal it made was invisible in .claude/logs/hook-blocks.jsonl.
# The fix is deliberately NOT "add a logging call next to each heredoc" —
# that reproduces the defect class, where refusing and recording are two acts
# and the second is forgettable. `deny_and_record` below is the ONLY thing in
# this file that emits a deny payload, so no path can refuse without recording.
#
# Recording delegates to lib/hook_telemetry.py's log_block_event() rather than
# appending JSON from shell: the row schema, the JSON escaping, the flock
# line-integrity guard (Issue #992), the reason cap, the HOOK_TELEMETRY_DISABLED
# rollback switch and the read-only-FS stderr fallback then live in exactly one
# place instead of two that drift. python3 is already a hard dependency of every
# hook registration in this repo, so this adds no new dependency — and the
# interpreter is spawned only on the deny path, never on the allow path.
#
# Telemetry is strictly subordinate to enforcement. The deny payload is written
# to stdout BEFORE any recording is attempted, and every recording failure mode
# (python3 absent, hook_telemetry unimportable, unwritable log, recorder raising)
# degrades to "refused but unrecorded" — never to "allowed".

set -euo pipefail

HOOK_NAME="PreToolUseWrite-protect-sensitive.sh"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# Sibling lib/ in both layouts: plugins/autonomous-dev/{hooks,lib} in source,
# .claude/{hooks,lib} when deployed.
LIB_DIR="$SCRIPT_DIR/../lib"

TOOL_USE=$(cat)
FILE_PATH=$(echo "$TOOL_USE" | jq -r '.parameters.file_path // empty')

# Append one hook-blocks.jsonl row for a refusal. Never fatal, never noisy on
# success. Called only from deny_and_record.
#
# $1 reason  — the exact model-visible reason string that was emitted
# $2 rule    — which refusal rule fired, for triage
_record_block() {
  local reason="$1"
  local rule="$2"
  local repo_root tool_name session_id

  if ! command -v python3 >/dev/null 2>&1; then
    printf '[hook-telemetry] %s: refusal unrecorded (python3 unavailable)\n' \
      "$HOOK_NAME" >&2
    return 0
  fi

  # Anchor the log at the repo root, not the invoking process's cwd. Without
  # this a write issued from a subdirectory writes <subdir>/.claude/logs/
  # instead of the repo's. Same resolution order the settings templates use.
  repo_root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || true)}"
  tool_name=$(printf '%s' "$TOOL_USE" | jq -r '.tool_name // ""' 2>/dev/null || true)
  session_id=$(printf '%s' "$TOOL_USE" | jq -r '.session_id // ""' 2>/dev/null || true)

  PYTHONPATH="$LIB_DIR${PYTHONPATH:+:$PYTHONPATH}" python3 - \
    "$HOOK_NAME" "$reason" "$rule" "$FILE_PATH" "$tool_name" "$session_id" \
    "$repo_root" <<'PY' || true
import sys
from pathlib import Path

_, hook_name, reason, rule, file_path, tool_name, session_id, repo_root = sys.argv

try:
    from hook_telemetry import log_block_event
except Exception as exc:  # stale install / missing lib
    sys.stderr.write(
        "[hook-telemetry] %s: refusal unrecorded "
        "(hook_telemetry unimportable: %s)\n" % (hook_name, exc)
    )
    raise SystemExit(0)

try:
    log_block_event(
        hook_name=hook_name,
        # "dict" == a printed JSON envelope, and a member of
        # scripts/hook_perf_report.py BLOCK_SHAPES, so this refusal is
        # counted as a block by the existing report.
        decision_shape="dict",
        reason=reason,
        metadata={
            "tool_name": tool_name,
            "file_path": file_path,
            "rule": rule,
            # This hook emits a TOP-LEVEL permissionDecision, not the
            # documented hookSpecificOutput.permissionDecision envelope.
            # Recording which variant was emitted lets triage see the
            # divergence in the data rather than only in prose (#1588).
            "envelope": "top-level permissionDecision",
        },
        session_id=session_id or None,
        start_dir=Path(repo_root) if repo_root else None,
    )
except Exception as exc:  # log_block_event is documented never to raise
    sys.stderr.write(
        "[hook-telemetry] %s: refusal unrecorded (recorder failed: %s)\n"
        % (hook_name, exc)
    )

raise SystemExit(0)
PY
}

# The ONLY producer of a deny payload in this file. Emits the refusal and
# records it as a single indivisible act, then exits.
#
# $1 reason  — model-visible reason (may contain JSON \n escapes)
# $2 rule    — which refusal rule fired, for triage
deny_and_record() {
  local reason="$1"
  local rule="$2"

  # Refuse FIRST. Nothing in the recording path can suppress this.
  cat <<EOF
{
  "permissionDecision": "deny",
  "reason": "$reason"
}
EOF

  _record_block "$reason" "$rule" || true
  exit 0
}

# Block sensitive files
if echo "$FILE_PATH" | grep -qE "\.env$|\.env\..*|\.git/|credentials|secrets|private.*key|\.pem$|\.key$"; then
  deny_and_record \
    "🔒 Cannot write to sensitive file: $FILE_PATH\n\nProtected patterns: .env, .git/, credentials, secrets, private keys" \
    "sensitive_file_pattern"
fi

# Block PROJECT.md from non-orchestrator agents (prevent drift)
if echo "$FILE_PATH" | grep -qE "PROJECT\.md$"; then
  deny_and_record \
    "🔒 PROJECT.md is protected\n\nTo update project goals/scope/constraints, edit PROJECT.md manually.\nAutomatic modifications would compromise alignment validation." \
    "project_md_protected"
fi

# Allow other files. Deliberately records nothing — a recorder that also fired
# on allows would corrupt every count derived from the block log.
echo '{"permissionDecision": "allow"}'
