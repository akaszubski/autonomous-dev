#!/usr/bin/env python3
"""One row per mechanism, joining every audit artifact into a single view.

Five separate audits answered five questions about the same 277 objects and none
of them were joined. This joins them, and adds the three columns that decide
re-architecture ORDER rather than content:

  coupling  -- what imports it, and what it imports. Decides what can be
               extracted without breaking something else.
  churn     -- commits in the last 90 days. Churn multiplied by size is where a
               design keeps being wrong, not merely where it is big.
  leverage  -- lines per refusal. A 9,000-line file with 2 refusals and a
               200-line file with 2,000 refusals are opposite problems.

Mechanical columns only. PURPOSE / FIT_FOR_PURPOSE / GAPS are judgement, filled
by review passes that actually read the code, and are never guessed here -- a
column inferred from a filename is how "dead code" gets asserted about a module
that a shell hook invokes by path. Two such false negatives were found on
2026-09-02 (batch_resume_helper, selector_stall_detector) and the reachability
walk was widened to parse .sh and workflow YAML as a result.

Regenerate after any change: the point is a view that cannot rot.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path("/Users/akaszubski/Dev/autonomous-dev")
AUDITS = ROOT / "docs" / "audits"


def sh(*args: str) -> str:
    """Run a git command, returning stdout. Never raises -- a missing history
    must degrade one column, not abort the whole view."""
    try:
        return subprocess.run(
            args, cwd=ROOT, capture_output=True, text=True, timeout=30
        ).stdout
    except Exception:
        return ""


def load(name: str):
    try:
        return json.loads((AUDITS / name).read_text())
    except Exception:
        print(f"  ! missing artifact: {name}", file=sys.stderr)
        return []


# ---------- artifact 1: reachability, measured four ways ----------
rows = {r["path"]: dict(r) for r in load("inventory-2026-09-01.json")}
if not rows:
    sys.exit("no inventory -- run scripts/audit_inventory.py first")

# ---------- artifact 2: fail-open handlers inside DECISION functions ----------
fail_open: dict[str, int] = defaultdict(int)
for r in load("fail-open-decision-paths-2026-09-01.json"):
    fail_open[r["file"]] += 1

# ---------- artifact 3: measured latency, hooks only ----------
bench: dict[str, float] = {}
for r in load("hook-latency-2026-09-02.json"):
    if r.get("hook"):
        bench[r["hook"]] = max(bench.get(r["hook"], 0.0), float(r.get("max_ms", 0)))

# ---------- artifact 4: origin and churn, straight from git ----------
since = (datetime.now(timezone.utc) - timedelta(days=90)).date().isoformat()
ISSUE_RE = re.compile(r"#(\d+)")

for path, row in rows.items():
    add = sh("git", "log", "--diff-filter=A", "--follow",
             "--format=%h\x1f%ad\x1f%s", "--date=short", "-1", "--", path).strip()
    if add and "\x1f" in add:
        commit, date, subject = add.split("\x1f", 2)
        m = ISSUE_RE.search(subject)
        row["origin"] = (commit, date, subject[:110], int(m.group(1)) if m else None)
    else:
        row["origin"] = (None, None, None, None)
    row["churn_90d"] = len([
        l for l in sh("git", "log", "--since", since, "--format=%h", "--", path).splitlines()
        if l.strip()
    ])

# ---------- coupling: who imports whom ----------
sources = {}
for path in rows:
    try:
        sources[path] = (ROOT / path).read_text(errors="replace")
    except Exception:
        sources[path] = ""

mod_to_path = {rows[p]["module"]: p for p in rows}
imports_out: dict[str, set] = defaultdict(set)
for path, src in sources.items():
    own = rows[path]["module"]
    for mod in mod_to_path:
        if mod == own:
            continue
        if re.search(rf"(?:^|\n)\s*(?:from\s+{re.escape(mod)}\s+import"
                     rf"|import\s+{re.escape(mod)}\b)", src):
            imports_out[path].add(mod)

imported_by: dict[str, set] = defaultdict(set)
for path, mods in imports_out.items():
    for m in mods:
        imported_by[mod_to_path[m]].add(rows[path]["module"])

# ---------- assemble ----------
view = []
for path, row in rows.items():
    refusals = row.get("refusals") or 0
    lines = row.get("lines") or 0
    commit, date, subject, issue = row["origin"]
    view.append({
        "module": row["module"],
        "path": path,
        "kind": row["kind"],
        "lines": lines,
        # CONNECTED -- is there a machine-checkable route to it
        "reach": row["reach"],
        "events": row.get("events") or [],
        "in_manifest": row.get("in_manifest"),
        # WORKS -- has it refused; can an error silence it
        "refusals": refusals,
        "fail_open_in_decisions": fail_open.get(path, 0),
        # COSTS -- measured, not budgeted
        "max_latency_ms": bench.get(row["module"] + ".py"),
        # ORDER OF WORK
        "imports_n": len(imports_out.get(path, ())),
        "imported_by_n": len(imported_by.get(path, ())),
        "imported_by": sorted(imported_by.get(path, ()))[:8],
        "churn_90d": row["churn_90d"],
        "lines_per_refusal": round(lines / refusals, 1) if refusals else None,
        # ORIGIN -- a proxy for purpose, never a substitute for reading it
        "origin_commit": commit,
        "origin_date": date,
        "origin_issue": issue,
        "origin_subject": subject,
        # JUDGEMENT -- filled by review passes only
        "purpose": None,
        "fit_for_purpose": None,
        "gaps": None,
    })

view.sort(key=lambda r: (-(r["refusals"] or 0), -r["lines"]))
(AUDITS / "mechanism-view.json").write_text(json.dumps(view, indent=1))


def bucket(r) -> str:
    """Gap buckets are DERIVED, not decided. Each is a different problem with a
    different fix: over-budget needs surgery, never-refused needs a probe,
    not-connected needs a call site, no-route needs a decision."""
    if r["max_latency_ms"] and r["max_latency_ms"] > 1000:
        return "CONNECTED, OVER BUDGET"
    if r["reach"] == "BOUND" and not r["refusals"]:
        return "CONNECTED, NEVER REFUSED"
    if r["reach"] == "TESTS-ONLY":
        return "BUILT, NOT CONNECTED"
    if r["reach"] == "NO-REF":
        return "NO ROUTE AT ALL"
    return "routine"


counts: dict[str, list] = defaultdict(lambda: [0, 0])
for r in view:
    k = bucket(r)
    counts[k][0] += 1
    counts[k][1] += r["lines"]

print(f"mechanism-view.json -- {len(view)} mechanisms, "
      f"{sum(r['lines'] for r in view):,} lines\n")

print("GAP BUCKETS (derived from the join; nobody decided these):")
for k in ("CONNECTED, OVER BUDGET", "CONNECTED, NEVER REFUSED",
          "BUILT, NOT CONNECTED", "NO ROUTE AT ALL", "routine"):
    if k in counts:
        print(f"   {k:26s} {counts[k][0]:4d} modules  {counts[k][1]:8,d} lines")

print("\nHIGHEST LEVERAGE (fewest lines per refusal -- these earn their keep):")
for r in sorted([x for x in view if x["lines_per_refusal"]],
                key=lambda x: x["lines_per_refusal"])[:5]:
    print(f"   {r['refusals']:5d} refusals {r['lines']:6,d} lines  "
          f"1 per {r['lines_per_refusal']:7.1f}  {r['module']}")

print("\nMOST ENTANGLED (extract these LAST -- breaking them breaks many):")
for r in sorted(view, key=lambda x: -x["imported_by_n"])[:5]:
    print(f"   {r['imported_by_n']:3d} importers {r['lines']:6,d} lines  {r['module']}")

print("\nCHURN x SIZE (the design keeps being wrong here):")
for r in sorted(view, key=lambda x: -(x["churn_90d"] * x["lines"]))[:5]:
    print(f"   {r['churn_90d']:3d} commits/90d {r['lines']:6,d} lines  {r['module']}")

missing = sum(1 for r in view if r["purpose"] is None)
print(f"\nJUDGEMENT COLUMNS UNFILLED: {missing}/{len(view)} "
      f"-- purpose/fit/gaps require reading the code, not inferring from names.")
