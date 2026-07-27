#!/usr/bin/env python3
"""csx — browse & search Claude Code + Codex sessions.

  csx                      all sessions, newest first, in a pager
  csx auth profile         title search
  csx -g base_row_id       global search: titles + bodies + tool calls + subagents
  csx show <id|prefix>     print a transcript
  csx resume <id|prefix>   print the exact resume command
  csx -h                   full help

Index cached at ~/.claude/.csx-index.json, refreshed by mtime+size.
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys

CLAUDE_ROOT = os.path.expanduser("~/.claude/projects")
CODEX_ROOTS = [os.path.expanduser("~/.codex/sessions"),
               os.path.expanduser("~/.codex/archived_sessions")]
HISTORY = os.path.expanduser("~/.claude/history.jsonl")
CACHE = os.path.expanduser("~/.claude/.csx-index.json")
CACHE_V = 7

C = {"dim": "\033[2m", "b": "\033[1m", "r": "\033[0m",
     "y": "\033[33m", "c": "\033[36m", "g": "\033[32m", "m": "\033[35m"}
PAGER_ON = sys.stdout.isatty()
if not PAGER_ON:
    C = {k: "" for k in C}

OUT = []


def emit(s=""):
    OUT.append(s)


def flush():
    text = "\n".join(OUT)
    if not text:
        return
    if PAGER_ON and text.count("\n") > 40:
        try:
            p = subprocess.Popen(["less", "-RFX"], stdin=subprocess.PIPE)
            p.communicate(text.encode("utf-8", "replace"))
            return
        except (OSError, BrokenPipeError, KeyboardInterrupt):
            pass
    try:
        print(text)
    except BrokenPipeError:
        pass


# ---------- transcript readers ----------

def _claude_msgs(path, meta):
    for line in open(path, encoding="utf-8", errors="ignore"):
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("type") not in ("user", "assistant"):
            continue
        c = d.get("message", {}).get("content")
        if isinstance(c, list):
            parts = []
            for x in c:
                if not isinstance(x, dict):
                    continue
                if x.get("type") == "text":
                    parts.append(x.get("text", ""))
                elif meta and x.get("type") == "tool_use":
                    parts.append(f"[tool:{x.get('name')}] " + json.dumps(x.get("input", ""))[:400])
            c = "\n".join(parts)
        if isinstance(c, str) and c.strip():
            yield d["type"], d.get("timestamp", ""), c


def _codex_msgs(path, meta):
    for line in open(path, encoding="utf-8", errors="ignore"):
        try:
            d = json.loads(line)
        except Exception:
            continue
        ts, p = d.get("timestamp", ""), d.get("payload", {})
        if d.get("type") != "response_item" or not isinstance(p, dict):
            continue
        t = p.get("type")
        if t == "message" and p.get("role") in ("user", "assistant"):
            txt = "\n".join(c.get("text", "") for c in p.get("content", [])
                            if isinstance(c, dict))
            if txt.strip():
                yield p["role"], ts, txt
        elif meta and t in ("function_call", "custom_tool_call"):
            arg = p.get("arguments") or p.get("input") or ""
            yield "assistant", ts, f"[tool:{p.get('name', t)}] {str(arg)[:400]}"


def msgs(entry_or_path, meta=False):
    """entry dict (preferred) or a bare path; yields (role, ts, text)."""
    if isinstance(entry_or_path, dict):
        path, src = entry_or_path["path"], entry_or_path.get("src", "claude")
    else:
        path, src = entry_or_path, ("codex" if "/.codex/" in entry_or_path else "claude")
    try:
        yield from (_codex_msgs(path, meta) if src == "codex" else _claude_msgs(path, meta))
    except OSError:
        return


NOISE = ("<system-reminder>", "<command-name>", "<local-command-stdout>",
         "Caveat: The messages below", "Base directory for this skill:",
         "# AGENTS.md instructions", "<user_instructions>", "<INSTRUCTIONS>",
         "## Memory\n", "# Memory\n", "<environment_context>", "<turn_aborted>")


def is_noise(text):
    return any(n in text[:400] for n in NOISE)


def head(path, src):
    """(cwd, session_id, title) read cheaply from the file.

    Claude Code names sessions itself and stores that as an `ai-title` record —
    the same name its own session list shows. Present for ~2/3 of sessions and
    always better than the first prompt. Codex writes nothing equivalent.
    """
    cwd = sid = named = ""
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if not cwd:
                    m = re.search(r'"cwd":"([^"]+)"', line)
                    if m:
                        cwd = m.group(1)
                if src == "codex":
                    if not sid:
                        m = re.search(r'"session_id":"([^"]+)"', line)
                        if m:
                            sid = m.group(1)
                    if cwd and sid:
                        break
                else:
                    if not named and '"ai-title"' in line:
                        try:
                            d = json.loads(line)
                            if d.get("type") == "ai-title":
                                named = (d.get("aiTitle") or "").strip()
                        except Exception:
                            pass
                    pass
    except OSError:
        pass
    title = named
    if not title:
        for role, _, text in msgs(path):
            if role == "user" and not is_noise(text):
                title = " ".join(text.split())[:160]
                break
    return cwd, sid, title


def profile(path, src):
    """One read per file: message count, first/last timestamp, cwd, id, title."""
    n = 0
    first = last = cwd = sid = named = renamed = first_msg = ""
    try:
        fh = open(path, encoding="utf-8", errors="ignore")
    except OSError:
        return 0, "", "", "", "", ""
    with fh:
        for line in fh:
            try:
                d = json.loads(line)
            except Exception:
                continue
            t = d.get("type")
            if not cwd:
                cwd = d.get("cwd") or (d.get("payload", {}) or {}).get("cwd", "") \
                    if isinstance(d.get("payload"), dict) or d.get("cwd") else ""
            if src == "codex":
                if not sid and isinstance(d.get("payload"), dict):
                    sid = d["payload"].get("session_id", "") or sid
                role, ts, text = None, d.get("timestamp", ""), None
                p = d.get("payload", {})
                if t == "response_item" and isinstance(p, dict) and p.get("type") == "message" \
                        and p.get("role") in ("user", "assistant"):
                    role = p["role"]
                    text = "\n".join(c.get("text", "") for c in p.get("content", [])
                                     if isinstance(c, dict))
            else:
                # both records are rewritten as a session evolves — keep the
                # LAST one, which is the name Claude Code itself displays
                if t == "custom-title" and d.get("customTitle"):
                    renamed = d["customTitle"].strip()       # you ran /rename — always wins
                elif t == "ai-title" and d.get("aiTitle"):
                    named = d["aiTitle"].strip()
                role, ts, text = None, d.get("timestamp", ""), None
                if t in ("user", "assistant"):
                    role = t
                    c = d.get("message", {}).get("content")
                    if isinstance(c, list):
                        c = "\n".join(x.get("text", "") for x in c
                                      if isinstance(x, dict) and x.get("type") == "text")
                    text = c if isinstance(c, str) else ""
            if role and text and text.strip():
                n += 1
                if ts:
                    first = first or ts
                    last = ts
                if role == "user" and not first_msg and not is_noise(text):
                    first_msg = " ".join(text.split())[:160]
    return n, first, last, cwd, sid, (renamed or named or first_msg)


# ---------- parallelism ----------
# Indexing and the search prefilter are CPU-bound (json.loads / bytes.lower over
# ~1 GB). Threads made this SLOWER — the GIL serialises them. Processes don't
# share it, so the work actually spreads across cores.

WORKERS = int(os.environ.get("CSX_WORKERS") or max(1, min(6, (os.cpu_count() or 2) - 2)))
_POOL = [None]


def pool():
    if _POOL[0] is None and WORKERS > 1:
        try:
            import multiprocessing as mp
            _POOL[0] = mp.get_context("fork").Pool(WORKERS)
        except Exception:
            _POOL[0] = False
    return _POOL[0] or None


def _profile_job(args):
    path, src = args
    return path, profile(path, src)


def _probe_job(args):
    path, needles = args
    return path, raw_hit(path, needles)


def _scan_job(args):
    """Prefilter AND extract snippets inside the worker — the parent used to do
    the expensive parsing serially, which left 5 cores idle."""
    path, src, needles, terms, ctx, meta, per = args
    if not raw_hit(path, needles):
        return path, None
    pats = [re.compile(re.escape(t), re.I) for t in terms]
    hits = []
    for role, ts, text in msgs({"path": path, "src": src}, meta):
        if all(p.search(text) for p in pats):
            m = pats[0].search(text)
            hits.append((role, ts, " ".join(
                text[max(0, m.start() - ctx):m.start() + ctx].split())))
            if len(hits) >= per:
                break
    return path, hits


# ---------- index ----------

def _files():
    for dirpath, _, files in os.walk(CLAUDE_ROOT):
        sub = os.sep + "subagents" in dirpath
        for fn in files:
            if fn.endswith(".jsonl"):
                yield "claude", sub, dirpath, fn
    for root in CODEX_ROOTS:
        for dirpath, _, files in os.walk(root):
            for fn in files:
                if fn.endswith(".jsonl"):
                    yield "codex", False, dirpath, fn


def scan(quiet=False):
    old = {}
    if os.path.exists(CACHE):
        try:
            blob = json.load(open(CACHE))
            if blob.get("v") == CACHE_V:
                old = {e["path"]: e for e in blob["sessions"]}
        except Exception:
            old = {}

    out, todo = [], []
    for src, sub, dirpath, fn in _files():
        p = os.path.join(dirpath, fn)
        try:
            st = os.stat(p)
        except OSError:
            continue
        prev = old.get(p)
        if prev and prev.get("mtime") == st.st_mtime and prev.get("size") == st.st_size:
            out.append(prev)
            continue
        todo.append((src, sub, dirpath, fn, p, st))

    fresh = len(todo)
    pl = pool() if fresh > 8 else None
    if pl:
        profiles = dict(pl.map(_profile_job, [(t[4], t[0]) for t in todo], chunksize=4))
    else:
        profiles = {t[4]: profile(t[4], t[0]) for t in todo}

    for src, sub, dirpath, fn, p, st in todo:
        n, first, last, cwd, sid, title = profiles[p]
        if src == "codex":
            m = re.search(r"([0-9a-f]{8}-[0-9a-f-]{27,})", fn)
            ident = sid or (m.group(1) if m else fn[:-6])
            project = os.path.basename(cwd.rstrip("/")) if cwd else "?"
            parent = ""
        else:
            ident = fn[:-6]
            parent = os.path.basename(os.path.dirname(dirpath)) if sub else ""
            project = os.path.basename(
                os.path.dirname(os.path.dirname(dirpath)) if sub else dirpath)
        e = {"path": p, "src": src}
        e.update({"id": ident, "kind": "sub" if sub else "main", "parent": parent,
                  "project": project, "cwd": cwd, "mtime": st.st_mtime,
                  "size": st.st_size, "turns": n, "start": first, "end": last,
                  "title": title})
        out.append(e)

    out.sort(key=lambda e: -e["mtime"])
    try:
        json.dump({"v": CACHE_V, "sessions": out}, open(CACHE, "w"))
    except OSError:
        pass
    if fresh and not quiet:
        print(f"{C['dim']}indexed {fresh} new/changed session(s){C['r']}", file=sys.stderr)
    return out


def load(rescan=False, quiet=False):
    if rescan or not os.path.exists(CACHE):
        return scan(quiet)
    try:
        blob = json.load(open(CACHE))
        if blob.get("v") != CACHE_V:
            return scan(quiet)
        idx = blob["sessions"]
    except Exception:
        return scan(quiet)
    cm = os.path.getmtime(CACHE)
    for _, _, dirpath, fn in _files():
        try:
            if os.path.getmtime(os.path.join(dirpath, fn)) > cm:
                return scan(quiet)
        except OSError:
            pass
    return idx


# ---------- display ----------

def clock(iso):
    """ISO timestamp from a transcript -> local 12-hour time."""
    if not iso:
        return ""
    try:
        d = dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
        return d.strftime("%b %d, %I:%M %p").replace(" 0", " ")
    except Exception:
        return iso[:16]


def ago(mtime):
    s = (dt.datetime.now() - dt.datetime.fromtimestamp(mtime)).total_seconds()
    for lim, div, u in ((60, 1, "s"), (3600, 60, "m"), (86400, 3600, "h"),
                        (86400 * 30, 86400, "d"), (86400 * 365, 86400 * 30, "mo")):
        if s < lim:
            return f"{int(s / div)}{u}"
    return f"{int(s / 86400 / 365)}y"


def proj(e):
    if e.get("cwd"):
        return os.path.basename(e["cwd"].rstrip("/")) or e["cwd"]
    return (e.get("project") or "?").lstrip("-").split("-")[-1]


FULL_IDS = [False]
TRUNC = [""]
SCOPE = [""]


def row(e, w=100):
    when = dt.datetime.fromtimestamp(e["mtime"]).strftime("%m-%d %I:%M%p").lower()
    t = e["title"] or f"{C['dim']}(no text){C['r']}"
    ident = e["id"] if FULL_IDS[0] else e["id"][:8]
    if e.get("kind") == "sub":
        tag = f"{C['dim']}subagent{C['r']}"
    elif e.get("src") == "codex":
        tag = f"{C['y']}codex   {C['r']}"
    else:
        tag = f"{C['c']}claude  {C['r']}"
    return (f"{tag} {C['c']}{ident}{C['r']} {C['dim']}{when} {ago(e['mtime']):>4}"
            f" {e['turns']:>4} msgs{C['r']} {C['m']}{proj(e)[:18]:<18}{C['r']} {t[:w]}")


def show_list(rows):
    if not rows:
        emit(f"{C['dim']}no sessions matched{C['r']}")
        return
    for e in rows:
        emit(row(e))
    emit(f"{C['dim']}{len(rows)} session(s){TRUNC[0]}{SCOPE[0]} · "
         f"`csx show <id>` to read one, `csx resume <id>` to continue it, "
         f"`csx ui` for the browser view{C['r']}")


def hl(text, terms):
    for t in terms:
        if t:
            text = re.sub(f"({re.escape(t)})", C["y"] + r"\1" + C["r"], text, flags=re.I)
    return text


# ---------- commands ----------

def raw_hit(path, needles):
    """Cheap case-insensitive prefilter: bytes.lower() + `in` beats decode+regex ~6x."""
    try:
        blob = open(path, "rb").read().lower()
    except OSError:
        return False
    return all(n in blob for n in needles)


DEBUG = bool(os.environ.get("CSX_DEBUG"))


def tick(label, t0):
    if DEBUG:
        print(f"[csx] {label}: {(dt.datetime.now() - t0).total_seconds():.2f}s "
              f"(workers={WORKERS})", file=sys.stderr)
    return dt.datetime.now()


def prefilter(idx, needles):
    """Yield sessions that could match, newest-first. The expensive part, so it
    runs across cores; lazy so callers can stop early."""
    t0 = dt.datetime.now()
    pl = pool() if len(idx) > 16 else None
    if not pl:
        for e in idx:
            if raw_hit(e["path"], needles):
                yield e
        tick("prefilter (serial)", t0)
        return
    # imap would submit every task up front, so a caller that stops at N results
    # still pays for the whole corpus. Feed it a window at a time instead: enough
    # to keep 6 cores busy, small enough that early exit stays cheap.
    window = WORKERS * 8
    for i in range(0, len(idx), window):
        batch = idx[i:i + window]
        for e, (_, hit) in zip(batch, pl.map(_probe_job,
                                             [(x["path"], needles) for x in batch],
                                             chunksize=2)):
            if hit:
                yield e
    tick("prefilter (parallel)", t0)


def search(idx, terms, ctx=110, meta=False, per=4):
    """Yield (entry, hits) newest-first. Each file is prefiltered and mined in a
    worker; lazy in windows so stopping early stays cheap."""
    t0 = dt.datetime.now()
    pats = [re.compile(re.escape(t), re.I) for t in terms]
    needles = [t.lower().encode("utf-8", "replace") for t in terms]

    def finish(e, hits):
        out = []
        if all(p.search(e["title"]) for p in pats):
            out.append(("ttl", clock(e.get("start") or ""), " ".join(e["title"].split())))
        out += [(r, clock(ts), sn) for r, ts, sn in (hits or [])]
        return out

    pl = pool() if len(idx) > 16 else None
    if not pl:
        for e in idx:
            _, hits = _scan_job((e["path"], e.get("src", "claude"), needles,
                                 terms, ctx, meta, per))
            if hits:
                yield e, finish(e, hits)
        tick("search (serial)", t0)
        return
    window = WORKERS * 8
    for i in range(0, len(idx), window):
        batch = idx[i:i + window]
        jobs = [(e["path"], e.get("src", "claude"), needles, terms, ctx, meta, per)
                for e in batch]
        for e, (_, hits) in zip(batch, pl.map(_scan_job, jobs, chunksize=2)):
            if hits:
                yield e, finish(e, hits)
    tick("search (parallel)", t0)


def cmd_deep(idx, terms, limit, ctx, meta, per=4):
    shown = 0
    for e, hits in search(idx, terms, ctx, meta, per):
        emit(row(e))
        agent = "codex " if e.get("src") == "codex" else "claude"
        for role, ts, s in hits[:per]:
            tg = {"user": f"{C['g']}you   {C['r']}", "ttl": f"{C['m']}title {C['r']}"}.get(
                role, f"{C['b']}{agent}{C['r']}")
            emit(f"    {tg} {C['dim']}{ts}{C['r']} …{hl(s, terms)}…")
        if len(hits) > per:
            emit(f"    {C['dim']}+{len(hits) - per} more hit(s) here{C['r']}")
        emit()
        shown += 1
        if shown >= limit:
            emit(f"{C['dim']}stopped at {limit} sessions (-n N / -a for all){C['r']}")
            break
    if not shown:
        emit(f"{C['dim']}no matches{C['r']}")


def in_tree(cwd, root, subtree=False):
    """Did a session run in root — or, with subtree=True, anywhere below it?

    Exact by default, matching the CLI (-i) and the UI folder picker: the count
    you select is the count you get. The prefix check is separator-anchored, so
    ~/ABL/abl-platform never swallows ~/ABL/abl-platform-deploy, -infra or
    _worktrees.
    """
    if root == NO_CWD:
        return not cwd
    if not cwd:
        return False
    cwd = os.path.normpath(cwd)
    root = os.path.normpath(os.path.expanduser(root))
    return cwd == root or (subtree and cwd.startswith(root + os.sep))


NO_CWD = "(no folder recorded)"


def folders(idx):
    """[(cwd, own, subtree)] by DISTINCT session id — a Codex session split across
    several rollout files must not count more than once."""
    seen = {}
    for e in idx:
        key = (e["id"], e.get("kind"))
        c = os.path.normpath(e["cwd"]) if e.get("cwd") else NO_CWD
        seen.setdefault(key, c)
    own = {}
    for c in seen.values():
        own[c] = own.get(c, 0) + 1
    out = []
    for root, n in own.items():
        if root == NO_CWD:
            out.append((root, n, n))
            continue
        deep = sum(v for c, v in own.items()
                   if c != NO_CWD and (c == root or c.startswith(root + os.sep)))
        out.append((root, n, deep))
    return sorted(out, key=lambda r: (r[0] == NO_CWD, -r[1], r[0]))


TERMINALS = [
    ("ghostty", lambda sh: ["ghostty", "-e", "bash", "-lc", sh]),
    ("kitty", lambda sh: ["kitty", "bash", "-lc", sh]),
    ("wezterm", lambda sh: ["wezterm", "start", "--", "bash", "-lc", sh]),
    ("gnome-terminal", lambda sh: ["gnome-terminal", "--", "bash", "-lc", sh]),
    ("xterm", lambda sh: ["xterm", "-e", "bash", "-lc", sh]),
]


def terminal_argv(shell_cmd):
    """argv that opens shell_cmd in a new terminal window, or None if none found."""
    import shutil
    for name, build in TERMINALS:
        if shutil.which(name):
            return build(shell_cmd), name
    return None, None


def prompt_log(terms, limit=200):
    """Search ~/.claude/history.jsonl — every prompt typed, including ones whose
    session was since deleted or compacted away."""
    pats = [t.lower() for t in terms]
    out, seen = [], set()
    try:
        lines = open(HISTORY, encoding="utf-8", errors="ignore").readlines()
    except OSError:
        return out
    for line in reversed(lines):                      # newest first
        try:
            d = json.loads(line)
        except Exception:
            continue
        text = d.get("display") or ""
        if not text or not all(p in text.lower() for p in pats):
            continue
        key = (d.get("sessionId"), " ".join(text.split())[:120])
        if key in seen:
            continue
        seen.add(key)
        out.append({"text": " ".join(text.split()), "ts": d.get("timestamp", 0),
                    "project": d.get("project", ""), "session": d.get("sessionId", "")})
        if len(out) >= limit:
            break
    return out


def day_of(e):
    """The date a session was last active, as YYYY-MM-DD local."""
    return dt.datetime.fromtimestamp(e["mtime"]).strftime("%Y-%m-%d")


def pick(idx, ident):
    hit = ([e for e in idx if e["id"].startswith(ident)]
           or [e for e in idx if ident in e["id"]]
           or [e for e in idx if ident in os.path.basename(e["path"])])
    if not hit:
        sys.exit(f"no session matching {ident!r}")
    if len({e["id"] for e in hit}) == 1 and len(hit) > 1:
        hit = [max(hit, key=lambda e: e["mtime"])]  # same session, multiple rollout segments
    return hit


def resume_cmd(e):
    if e.get("src") == "codex":
        return f"cd {e.get('cwd') or '~'} && codex resume {e['id']}"
    return f"cd {e.get('cwd') or '~'} && claude --resume {e['id']}"


def cmd_resume(idx, ident):
    hit = pick(idx, ident)
    if len(hit) > 1:
        emit(f"{C['dim']}{len(hit)} matches — be more specific:{C['r']}")
        return show_list(hit)
    e = hit[0]
    if e.get("kind") == "sub":
        par = [x for x in idx if x["id"] == e["parent"]]
        if not par:
            sys.exit(f"{e['id']} is a subagent run; parent {e['parent']} not indexed")
        emit(f"{C['dim']}{e['id'][:8]} is a subagent run — resuming its parent:{C['r']}")
        e = par[0]
    emit(resume_cmd(e))


def cmd_show(idx, ident, meta, grep):
    hit = pick(idx, ident)
    if len(hit) > 1:
        emit(f"{C['dim']}{len(hit)} matches:{C['r']}")
        return show_list(hit)
    e = hit[0]
    kind = "codex" if e.get("src") == "codex" else "claude"
    emit(f"{C['b']}{e['id']}{C['r']} {C['dim']}[{kind}]{C['r']}  {e.get('cwd') or '?'}  "
         f"{clock(e['start'])} → {clock(e['end'])}  {e['turns']} messages")
    emit(f"{C['dim']}resume: {resume_cmd(e)}{C['r']}")
    emit()
    g = re.compile(grep, re.I) if grep else None
    for role, ts, text in msgs(e, meta):
        if role == "user" and is_noise(text):
            continue
        if g and not g.search(text):
            continue
        agent = "CODEX" if e.get("src") == "codex" else "CLAUDE"
        who = f"{C['g']}YOU{C['r']}" if role == "user" else f"{C['b']}{agent}{C['r']}"
        emit(f"{C['dim']}── {clock(ts)} {C['r']}{who}")
        emit(hl(text, [grep]) if g else text)
        emit()


def main():
    ap = argparse.ArgumentParser(
        prog="csx", description="browse & search Claude Code + Codex sessions",
        epilog="examples:\n"
               "  csx                       every session, newest first, scrollable\n"
               "  csx auth profile          title search (AND of terms)\n"
               "  csx -d base_row_id        deep search message bodies\n"
               "  csx -g base_row_id        global: + tool calls + subagent runs\n"
               "  csx --codex               only Codex sessions\n"
               "  csx -p abl-platform       filter by project name / cwd substring\n"
               "  csx -i ~/ABL              sessions run in ~/ABL itself\n"
               "  csx -i ~/ABL --sub        ~/ABL plus everything nested inside it\n"
               "  csx -H                    sessions run in the current directory\n"
               "  csx --folders             every folder that has sessions, with counts\n"
               "  csx -f                    full session ids\n"
               "  csx show cf36f5b1         read a transcript\n"
               "  csx show cf36f5b1 -G OOM  only turns matching a regex\n"
               "  csx resume cf36f5b1       print the exact resume command\n"
               "  csx ui                    local web UI, click-to-copy (port 8787)",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("terms", nargs="*",
                    help="search terms, or `show <id>` / `resume <id>` / `ui [port]`")
    ap.add_argument("-d", "--deep", action="store_true", help="search message bodies")
    ap.add_argument("-g", "--global", dest="glob", action="store_true",
                    help="global search: titles + bodies + tool calls + subagent runs")
    ap.add_argument("-m", "--meta", action="store_true", help="include tool calls")
    ap.add_argument("-s", "--subagents", action="store_true", help="include subagent runs")
    ap.add_argument("--codex", action="store_true", help="only Codex sessions")
    ap.add_argument("--claude", action="store_true", help="only Claude Code sessions")
    ap.add_argument("-p", "--project", help="substring filter on project / cwd")
    ap.add_argument("-i", "--in", dest="inpath", metavar="PATH",
                    help="only sessions run in PATH itself (e.g. -i ~/ABL)")
    ap.add_argument("-H", "--here", action="store_true",
                    help="only sessions run in the current directory")
    ap.add_argument("--sub", action="store_true",
                    help="with -i/-H: include folders nested inside it too")
    ap.add_argument("--folders", action="store_true",
                    help="list every folder that has sessions, with counts")
    ap.add_argument("-n", "--limit", type=int, help="max results (default: all)")
    ap.add_argument("-a", "--all", action="store_true", help="no result limit")
    ap.add_argument("-c", "--context", type=int, default=110, help="snippet radius")
    ap.add_argument("-f", "--full", action="store_true", help="print full session ids")
    ap.add_argument("-G", "--grep", help="with show: only turns matching this regex")
    ap.add_argument("--no-pager", action="store_true", help="never page output")
    ap.add_argument("--no-open", action="store_true", help="with ui: do not open a browser")
    ap.add_argument("-R", "--rescan", action="store_true", help="force reindex")
    a = ap.parse_args()

    global PAGER_ON
    if a.no_pager:
        PAGER_ON = False
    FULL_IDS[0] = a.full

    if a.terms and a.terms[0] in ("ui", "serve"):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import csx_ui
        port = int(a.terms[1]) if len(a.terms) > 1 else 8787
        return csx_ui.serve(sys.modules[__name__], port, not a.no_open)

    if a.terms and a.terms[0] in ("show", "resume"):
        if len(a.terms) < 2:
            sys.exit(f"usage: csx {a.terms[0]} <id-prefix>")
        idx = load(a.rescan, quiet=True)
        if a.terms[0] == "show":
            cmd_show(idx, a.terms[1], a.meta, a.grep)
        else:
            cmd_resume(idx, a.terms[1])
        return flush()

    idx = load(a.rescan)
    if not (a.subagents or a.glob):
        idx = [e for e in idx if e.get("kind") != "sub"]
    if a.codex:
        idx = [e for e in idx if e.get("src") == "codex"]
    if a.claude:
        idx = [e for e in idx if e.get("src") != "codex"]
    if a.project:
        idx = [e for e in idx
               if a.project.lower() in (e.get("project", "") + " " + e.get("cwd", "")).lower()]
    root = os.getcwd() if a.here else a.inpath
    if root:
        idx = [e for e in idx if in_tree(e.get("cwd"), root, a.sub)]
        SCOPE[0] = (f" in {os.path.normpath(os.path.expanduser(root))}"
                    + (" and its subfolders" if a.sub else " only"))

    if a.folders:
        rows = folders(idx)   # honors --codex/--claude/-s/-p already applied
        if root:
            rows = [r for r in rows if in_tree(r[0], root, True)]
        for cwd, own, _ in rows:
            emit(f"{C['c']}{own:>6}{C['r']}  {cwd}")
        total = sum(o for _, o, _ in rows)
        emit(f"{C['dim']}{len(rows)} folder(s), {total} session(s) · "
             f"scope one with `csx -i <path>`{C['r']}")
        return flush()

    limit = 10 ** 6 if (a.all or a.limit is None) else a.limit

    if a.deep or a.glob:
        if not a.terms:
            sys.exit("search needs a term")
        cmd_deep(idx, a.terms, limit, a.context, a.meta or a.glob)
        return flush()

    if a.terms:
        named = [e for e in idx
                 if all(t.lower() in (e["title"] + " " + e.get("project", "") + " "
                                      + e.get("cwd", "")).lower() for t in a.terms)]
        if not named:
            emit(f"{C['dim']}no title match — deep searching instead "
                 f"(csx -g adds tool calls + subagent runs){C['r']}")
            cmd_deep(idx, a.terms, limit, a.context, a.meta)
            return flush()
        idx = named

    if len(idx) > limit:
        TRUNC[0] = f" of {len(idx)} (-a for all)"
    show_list(idx[:limit])
    flush()


if __name__ == "__main__":
    try:
        main()
    except (BrokenPipeError, KeyboardInterrupt):
        pass
