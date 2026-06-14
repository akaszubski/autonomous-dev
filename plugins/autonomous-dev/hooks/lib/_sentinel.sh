#!/usr/bin/env bash
# shellcheck disable=SC2120
# _sentinel.sh — bash helpers for resolving the per-repo legacy sentinel path.
#
# Issue #1206: the legacy sentinel was previously hardcoded to the machine-
# global ``/tmp/implement_pipeline_state.json``, which caused concurrent
# /implement sessions in different repos to overwrite each other's state.
# This helper resolves the sentinel to ``<repo>/.claude/local/implement_pipeline_state.json``
# instead, mirroring the Python ``pipeline_state.get_legacy_sentinel_path()``
# resolver (same marker priority: ``.git`` first, then ``.claude``).
#
# Usage:
#   source "$(dirname "$0")/lib/_sentinel.sh"
#   PIPELINE_STATE_FILE="${PIPELINE_STATE_FILE:-$(_default_sentinel)}"
#
# Returns (echoes to stdout) the fully-qualified sentinel path. The parent
# directory ``.claude/local/`` is created with mode 0700 if missing.

# _find_repo_root: walk upward from CWD looking for a ``.git`` or ``.claude``
# marker (max 30 levels). Echoes the discovered repo root on stdout, or echoes
# CWD if no marker is found. Mirrors Python find_project_root() priority: .git
# wins even if .claude is closer.
_find_repo_root() {
    local start_dir current parent marker
    start_dir="$(pwd -P)"

    # Priority 1: .git anywhere above
    current="$start_dir"
    for _ in $(seq 1 30); do
        if [ -e "$current/.git" ]; then
            printf '%s\n' "$current"
            return 0
        fi
        parent="$(dirname "$current")"
        # Hit filesystem root
        if [ "$parent" = "$current" ]; then
            break
        fi
        current="$parent"
    done

    # Priority 2: .claude anywhere above (only if .git not found)
    current="$start_dir"
    for _ in $(seq 1 30); do
        if [ -e "$current/.claude" ]; then
            printf '%s\n' "$current"
            return 0
        fi
        parent="$(dirname "$current")"
        if [ "$parent" = "$current" ]; then
            break
        fi
        current="$parent"
    done

    # Fallback: current working directory
    printf '%s\n' "$start_dir"
}

# _default_sentinel: echoes the per-repo legacy sentinel path. Creates the
# parent directory at mode 0700 if missing. Idempotent.
_default_sentinel() {
    local root sentinel_dir sentinel_path
    root="$(_find_repo_root)"
    sentinel_dir="$root/.claude/local"
    if [ ! -d "$sentinel_dir" ]; then
        # Best effort; if mkdir fails (read-only FS, permissions), we still
        # echo the path so the caller can decide how to handle errors.
        mkdir -p "$sentinel_dir" 2>/dev/null || true
        chmod 0700 "$sentinel_dir" 2>/dev/null || true
    else
        chmod 0700 "$sentinel_dir" 2>/dev/null || true
    fi
    sentinel_path="$sentinel_dir/implement_pipeline_state.json"
    printf '%s\n' "$sentinel_path"
}
