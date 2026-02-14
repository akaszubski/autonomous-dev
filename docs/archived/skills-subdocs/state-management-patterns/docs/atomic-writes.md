# Atomic Write Patterns

Prevent file corruption by using atomic filesystem operations.

## Why Atomic Writes Matter

Crashes mid-write leave files partially written. Atomic writes guarantee all-or-nothing.

## Implementation

Write to temp file, then rename (atomic on POSIX systems).

See: `docs/json-persistence.md`
