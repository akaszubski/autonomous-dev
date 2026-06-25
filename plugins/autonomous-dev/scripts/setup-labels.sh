#!/usr/bin/env bash
# Idempotent setup of GitHub labels used by autonomous-dev workflows.
# Run once per repo: bash plugins/autonomous-dev/scripts/setup-labels.sh
#
# Labels created:
#   selector-stall  — drain-watchdog files this when the selector returns
#                     no_drainable_cluster for K consecutive fires (Issue #1303).
#   high-priority   — generic operator-triage marker; paired with selector-stall.
set -euo pipefail

echo "Ensuring required labels exist..."

gh label create selector-stall \
  --color "ff6600" \
  --description "Drain selector returned empty for K consecutive fires (Issue #1303)" \
  2>/dev/null || echo "  selector-stall: exists"

gh label create high-priority \
  --color "ff0000" \
  --description "Operator triage needed" \
  2>/dev/null || echo "  high-priority: exists"

echo "Done."
