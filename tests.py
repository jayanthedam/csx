#!/usr/bin/env python3
"""Assertions for the fiddly parts: folder scoping, counting, id matching.

Run: python3 tests.py   (uses the live index; skips gracefully if absent)
"""
import importlib.machinery, importlib.util, os, sys

spec = importlib.util.spec_from_loader("csx", importlib.machinery.SourceFileLoader(
    "csx", os.path.join(os.path.dirname(os.path.abspath(__file__)), "csx")))
csx = importlib.util.module_from_spec(spec)
sys.argv = ["csx"]
spec.loader.exec_module(csx)

ok = fail = 0


def check(label, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print(f"  pass  {label}")
    else:
        fail += 1
        print(f"  FAIL  {label}\n        got {got!r}\n        want {want!r}")


print("in_tree — separator-anchored, so sibling names never leak in")
A = "/home/j/ABL/abl-platform"
check("exact match", csx.in_tree(A, A), True)
check("child is in subtree", csx.in_tree(A + "/apps/studio", A), True)
check("child excluded when subtree=False", csx.in_tree(A + "/apps/studio", A, False), False)
check("sibling -deploy NOT a child", csx.in_tree(A + "-deploy", A), False)
check("sibling -infra NOT a child", csx.in_tree(A + "-infra", A), False)
check("sibling _worktrees NOT a child", csx.in_tree(A + "_worktrees/x", A), False)
check("parent is not inside child", csx.in_tree("/home/j/ABL", A), False)
check("trailing slash on root", csx.in_tree(A, A + "/"), True)
check("empty cwd matches nothing", csx.in_tree("", A), False)
check("empty cwd matches the no-folder bucket", csx.in_tree("", csx.NO_CWD), True)
check("real cwd not in no-folder bucket", csx.in_tree(A, csx.NO_CWD), False)

print("\nfolders() — one row per session, counted where it ran")
idx = [
    {"id": "a", "kind": "main", "cwd": "/r"},
    {"id": "b", "kind": "main", "cwd": "/r/child"},
    {"id": "c", "kind": "main", "cwd": "/r-sibling"},
    {"id": "d", "kind": "main", "cwd": "/r/child"},
    {"id": "d", "kind": "main", "cwd": "/r/child"},   # same session, 2nd rollout file
    {"id": "e", "kind": "main", "cwd": ""},
]
f = {row[0]: row[1:] for row in csx.folders(idx)}
check("/r own=1 subtree=3", f["/r"], (1, 3))
check("/r/child own=2 (dupe id counted once)", f["/r/child"], (2, 2))
check("/r-sibling excluded from /r subtree", f["/r-sibling"], (1, 1))
check("no-cwd bucket present", f[csx.NO_CWD], (1, 1))
check("owns sum to distinct sessions", sum(v[0] for v in f.values()), 5)
check("no-cwd bucket sorts last", csx.folders(idx)[-1][0], csx.NO_CWD)

print("\nlive index (skipped if you have no sessions yet)")
if os.path.exists(csx.CACHE):
    live = [e for e in csx.load(quiet=True) if e.get("kind") != "sub"]
    rows = csx.folders(live)
    distinct = len({e["id"] for e in live})
    check("folder owns == distinct session ids", sum(r[1] for r in rows), distinct)
    home = os.path.expanduser("~")
    for root, own, deep in rows:
        if root == csx.NO_CWD:
            continue
        scoped = [e for e in live if csx.in_tree(e.get("cwd"), root)]
        exact = [e for e in live if csx.in_tree(e.get("cwd"), root, False)]
        if len({e["id"] for e in scoped}) != deep or len({e["id"] for e in exact}) != own:
            check(f"{root} counts match filtering", (len(scoped), len(exact)), (deep, own))
            break
    else:
        ok += 1
        print("  pass  every folder's counts match what -i / -i --only actually return")
else:
    print("  skip  no index at", csx.CACHE)

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
