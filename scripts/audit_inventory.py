#!/usr/bin/env python3
"""Mechanical inventory of every hook and lib module in autonomous-dev.

Produces one row per module with reachability measured FOUR independent ways,
because static import analysis alone is known to be wrong here (this repo loads
lib/ via importlib and via `python3 -c` blocks embedded in markdown).

No judgement. Only measurement. Judgement happens downstream.
"""
import json, os, re, subprocess, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path("/Users/akaszubski/Dev/autonomous-dev")
PLUG = ROOT / "plugins" / "autonomous-dev"
HOOKS_D, LIB_D = PLUG / "hooks", PLUG / "lib"

def read(p):
    try: return p.read_text(encoding="utf-8", errors="replace")
    except Exception: return ""

# ---------- corpora we search for references ----------
def gather(globs):
    out = {}
    for g in globs:
        for p in ROOT.glob(g):
            if p.is_file(): out[str(p)] = read(p)
    return out

md_corpus     = gather(["plugins/autonomous-dev/commands/**/*.md",
                        "plugins/autonomous-dev/agents/**/*.md",
                        "plugins/autonomous-dev/skills/**/*.md"])
script_corpus = gather(["scripts/**/*.sh", "scripts/**/*.py", "*.sh"])
test_corpus   = gather(["tests/**/*.py"])
py_corpus     = gather(["plugins/autonomous-dev/hooks/**/*.py",
                        "plugins/autonomous-dev/lib/**/*.py"])

# ---------- settings / manifest binding ----------
BOUND_FILES = {}
_cands = [ROOT/'.claude/settings.json', ROOT/'.claude/settings.local.json']
_cands += sorted(ROOT.glob('plugins/autonomous-dev/templates/settings*.json'))
_cands += sorted(ROOT.glob('plugins/autonomous-dev/config/global_settings_template.json'))
for _c in _cands:
    if not _c.exists(): continue
    try: _d = json.loads(read(_c))
    except Exception: continue
    for _ev, _entries in (_d.get('hooks') or {}).items():
        for _m in re.findall(r'([A-Za-z0-9_\-]+\.(?:py|sh))', json.dumps(_entries)):
            BOUND_FILES.setdefault(_m, set()).add(_ev)

manifest_blob = read(PLUG / "config" / "install_manifest.json")

# ---------- refusal counts from the live block log ----------
refusals = defaultdict(int)
blog = ROOT / ".claude" / "logs" / "hook-blocks.jsonl"
TESTY = re.compile(r"foo\.md|bar\.py|because reasons|^blocked$|/tmp/pytest|dummy", re.I)
if blog.exists():
    for line in read(blog).splitlines():
        line = line.strip()
        if not line: continue
        try: r = json.loads(line)
        except Exception: continue
        if r.get("refused") is not True: continue
        if TESTY.search(r.get("reason") or ""): continue
        refusals[r.get("hook_name", "?")] += 1

def except_profile(src):
    """Count exception handlers by what they do: deny / allow / unknown."""
    lines = src.split("\n"); closed = openn = unk = 0
    for i, l in enumerate(lines):
        if not re.match(r"\s*except\b", l): continue
        body = "\n".join(lines[i+1:i+7])
        if re.search(r'return\s*\(?\s*["\']deny|output_decision\(\s*["\']deny', body): closed += 1
        elif re.search(r"^\s*pass\s*$", body, re.M) or \
             re.search(r"return\s*(None|False|\(\s*False|\[\]|\{\}|\"\"|'')|return\s*$", body): openn += 1
        else: unk += 1
    return closed, openn, unk

def count_refs(corpus, needle_re, skip_self=None):
    n = 0
    for path, txt in corpus.items():
        if skip_self and os.path.samefile(path, skip_self) if os.path.exists(path) else False: continue
        if needle_re.search(txt): n += 1
    return n

rows = []
for kind, d in (("hook", HOOKS_D), ("lib", LIB_D)):
    for p in sorted(d.rglob("*.py")):
        rel = p.relative_to(ROOT)
        if "archived" in p.parts or p.name == "__init__.py": continue
        mod = p.stem
        src = read(p)
        static_re = re.compile(rf"(?:^|\n)\s*(?:from\s+{re.escape(mod)}\s+import|import\s+{re.escape(mod)}\b)")
        word_re   = re.compile(rf"\b{re.escape(mod)}\b")

        static = sum(1 for q, t in py_corpus.items()
                     if q != str(p) and static_re.search(t))
        dyn_re = re.compile(rf"[\"']{re.escape(mod)}(?:\.py)?[\"']|\b{re.escape(p.name)}\b")
        dynamic = sum(1 for q, t in py_corpus.items()
                      if q != str(p) and dyn_re.search(t))
        md_refs = count_refs(md_corpus, word_re)
        sc_refs = count_refs(script_corpus, word_re)
        tst     = count_refs(test_corpus, word_re)
        closed, openn, unk = except_profile(src)

        rows.append({
            "kind": kind, "path": str(rel), "module": mod,
            "lines": src.count("\n") + 1,
            "static_importers": static, "dynamic_str_refs": dynamic,
            "md_refs": md_refs, "script_refs": sc_refs, "test_refs": tst,
            "in_settings": p.name in BOUND_FILES,
            "events": sorted(BOUND_FILES.get(p.name, [])),
            "in_manifest": bool(re.search(rf"\b{re.escape(p.name)}\b", manifest_blob)),
            "refusals": refusals.get(p.name, 0),
            "except_closed": closed, "except_open": openn, "except_unknown": unk,
        })

for r in rows:
    prod = r["static_importers"] + r["dynamic_str_refs"] + r["md_refs"] + r["script_refs"]
    if r["kind"] == "hook":
        r["reach"] = ("BOUND" if r["in_settings"] else
                      "PROD-REF" if prod else
                      "TESTS-ONLY" if r["test_refs"] else "NO-REF")
    else:
        r["reach"] = ("PROD-REF" if prod else
                      "TESTS-ONLY" if r["test_refs"] else "NO-REF")

out = ROOT / "docs" / "audits" / "inventory-2026-09-01.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(rows, indent=1))

h = [r for r in rows if r["kind"] == "hook"]; l = [r for r in rows if r["kind"] == "lib"]
print(f"hooks: {len(h)}  lib: {len(l)}  total lines: {sum(r['lines'] for r in rows):,}")
print(f"\nwritten -> {out.relative_to(ROOT)}\n")
for label, group in (("HOOKS", h), ("LIB", l)):
    c = defaultdict(lambda: [0, 0])
    for r in group:
        c[r["reach"]][0] += 1; c[r["reach"]][1] += r["lines"]
    print(f"{label} reachability:")
    for k in ("BOUND", "PROD-REF", "TESTS-ONLY", "NO-REF"):
        if k in c: print(f"   {k:12s} {c[k][0]:4d} modules  {c[k][1]:7,d} lines")
print(f"\nhooks that have EVER refused: {sum(1 for r in h if r['refusals'])}")
print(f"except handlers across all:   closed={sum(r['except_closed'] for r in rows)}"
      f"  open={sum(r['except_open'] for r in rows)}"
      f"  unknown={sum(r['except_unknown'] for r in rows)}")
