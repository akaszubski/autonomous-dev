"""Print the comma-separated issue numbers of the next drainable cluster.

Thin wrapper around :func:`drain_queue_state.select_next_cluster` for use in
GitHub Actions shell steps.  Produces output in the form ``"101,102,103"``
(no trailing newline) so callers can consume it directly:

    CLUSTER=$(python3 scripts/select_next_drainable_cluster.py || echo "")

If no drainable cluster exists, or if any error is encountered, an empty string
is printed and the script exits with code 0 to avoid failing the surrounding
shell step.

.. note::
    **CWD dependency**: this script resolves ``plugins/autonomous-dev/lib`` as a
    relative path.  It must be invoked from the repository root, which is the
    default ``$GITHUB_WORKSPACE`` working directory set by ``actions/checkout@v4``.
    ``sys.path.insert(0, 'plugins/autonomous-dev/lib')`` therefore resolves to
    ``$GITHUB_WORKSPACE/plugins/autonomous-dev/lib``.

ADR-002 Phase B Invariant 1: replaces duplicated inline Python heredocs in
drain-driver.yml and drain-watchdog.yml.
"""

from __future__ import annotations

import json
import subprocess
import sys
import traceback

# CWD must be the repository root (set by actions/checkout@v4 default).
# This relative insert resolves to $GITHUB_WORKSPACE/plugins/autonomous-dev/lib.
sys.path.insert(0, "plugins/autonomous-dev/lib")

try:
    from drain_queue_state import select_next_cluster
except Exception as exc:
    # Cannot import — fail gracefully so the workflow step does not error out.
    print(
        f"::warning::select_next_drainable_cluster: import stage failed: {exc}",
        file=sys.stderr,
    )
    traceback.print_exc(file=sys.stderr)
    print("", end="")
    sys.exit(0)

try:
    result = subprocess.run(
        [
            sys.executable,
            "plugins/autonomous-dev/lib/issue_triage_analyzer.py",
            "--auto-improvement",
            "--json",
            "--limit",
            "50",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    clusters = json.loads(result.stdout)
except Exception as exc:
    print(
        f"::warning::select_next_drainable_cluster: triage stage failed: {exc}",
        file=sys.stderr,
    )
    traceback.print_exc(file=sys.stderr)
    print("", end="")
    sys.exit(0)

try:
    cluster = select_next_cluster(clusters)
    if cluster:
        issue_nums = cluster.get("issue_numbers", [])[:3]
        print(",".join(str(n) for n in issue_nums), end="")
    else:
        print("", end="")
except Exception as exc:
    print(
        f"::warning::select_next_drainable_cluster: selection stage failed: {exc}",
        file=sys.stderr,
    )
    traceback.print_exc(file=sys.stderr)
    print("", end="")
    sys.exit(0)
