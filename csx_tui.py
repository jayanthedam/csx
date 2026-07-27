"""csx tui — the browser UI, in the terminal.

Same index, same search, same features. The difference that matters: Enter
*becomes* the session (os.execvp), so there is no window to spawn and nothing
to paste.

Launched by `csx tui`. Stdlib curses only.
"""
import curses
import os
import sys

KEYS = [
    ("enter", "resume"), ("^r", "read"), ("^d", "deep"), ("^g", "global"),
    ("^p", "prompts"), ("^y", "today"), ("^f", "folder"), ("tab", "tool"),
    ("^u", "clear"), ("^n/^k", "move"), ("esc", "quit"),
]
HELP = " · ".join(f"{k} {v}" for k, v in KEYS)


class Tui:
    def __init__(self, csx, idx):
        self.csx = csx
        self.all = [e for e in idx if e.get("kind") != "sub"]
        self.q = ""
        self.mode = "title"          # title | deep | global | prompts
        self.src = ""                # "" | claude | codex
        self.today = False
        self.folders = [("", "all folders")] + [
            (p, self.short(p) + f" ({n})") for p, n, _ in csx.folders(self.all)[:14]]
        self.fi = 0
        self.rows, self.sel, self.top, self.note = [], 0, 0, ""
        self.reader = None           # (entry, lines, offset) when reading
        self.refilter()

    @staticmethod
    def short(p):
        home = os.path.expanduser("~")
        return ("~" + p[len(home):]) if p.startswith(home) else p

    # ---------- data ----------

    def scope(self):
        out = self.all
        root = self.folders[self.fi][0]
        if root:
            out = [e for e in out if self.csx.in_tree(e.get("cwd"), root)]
        if self.src:
            out = [e for e in out if (e.get("src") == "codex") == (self.src == "codex")]
        if self.today:
            today = self.csx.dt.datetime.now().strftime("%Y-%m-%d")
            out = [e for e in out if self.csx.day_of(e) == today]
        return out

    def refilter(self):
        """Title filtering is instant, so it runs on every keystroke."""
        idx = self.scope()
        terms = self.q.lower().split()
        if terms and self.mode == "title":
            idx = [e for e in idx
                   if all(t in (e["title"] + " " + e.get("cwd", "")).lower() for t in terms)]
        self.rows = [(e, None) for e in idx]
        self.sel = self.top = 0

    def run_search(self, mode, scr):
        """deep/global/prompts take seconds, so say so before blocking."""
        if not self.q.strip():
            self.note = "type something first, then ^d / ^g / ^p"
            return
        self.mode = mode
        self.draw(scr, banner=f"searching {mode} for “{self.q}”…")
        scr.refresh()
        t0 = self.csx.dt.datetime.now()
        if mode == "prompts":
            by_id = {e["id"]: e for e in self.all}
            rows = []
            for h in self.csx.prompt_log(self.q.split(), 200):
                e = by_id.get(h["session"])
                # the prompt IS the result — show it, keep the session for resume
                rows.append((dict(e, title=h["text"]), None) if e else
                            ({"id": h["session"] or "-", "title": h["text"], "src": "claude",
                              "kind": "gone", "turns": 0, "cwd": h["project"],
                              "mtime": (h["ts"] or 0) / 1000, "start": "", "end": "",
                              "project": ""}, None))
            self.rows = rows
        else:
            found = []
            for e, hits in self.csx.search(self.scope(), self.q.split(),
                                           ctx=90, meta=(mode == "global"), per=2):
                found.append((e, hits))
                if len(found) >= 200:
                    break
            self.rows = found
        took = (self.csx.dt.datetime.now() - t0).total_seconds()
        self.sel = self.top = 0
        self.note = f"{len(self.rows)} result(s) in {took:.1f}s"

    def day_line(self):
        today = self.csx.dt.datetime.now().strftime("%Y-%m-%d")
        mine = [e for e in self.all if self.csx.day_of(e) == today]
        if not mine:
            return "today — nothing yet"
        stamps = []
        for e in mine:
            for k in ("start", "end"):
                try:
                    d = self.csx.dt.datetime.fromisoformat(
                        e[k].replace("Z", "+00:00")).astimezone()
                    if d.strftime("%Y-%m-%d") == today:
                        stamps.append(d)
                except Exception:
                    pass
        span = ""
        if stamps:
            lo, hi = min(stamps), max(stamps)
            span = (f" · {lo.strftime('%I:%M%p').lstrip('0').lower()}"
                    f"→{hi.strftime('%I:%M%p').lstrip('0').lower()}"
                    f" ({(hi - lo).total_seconds() / 3600:.1f}h)")
        folders = {}
        for e in mine:
            folders[self.csx.proj(e)] = folders.get(self.csx.proj(e), 0) + 1
        tops = " · ".join(f"{k} {v}" for k, v in
                          sorted(folders.items(), key=lambda kv: -kv[1])[:4])
        return (f"today — {len(mine)} sessions, {sum(e['turns'] for e in mine)} msgs"
                f"{span} · {tops}")

    # ---------- actions ----------

    def current(self):
        return self.rows[self.sel][0] if self.rows else None

    def resume(self):
        e = self.current()
        if not e or e.get("kind") == "gone":
            self.note = "that prompt's session is gone — nothing to resume"
            return
        cwd = e.get("cwd") or os.path.expanduser("~")
        if os.path.isdir(cwd):
            os.chdir(cwd)
        argv = (["codex", "resume", e["id"]] if e.get("src") == "codex"
                else ["claude", "--resume", e["id"]])
        curses.endwin()
        print(f"\n→ {' '.join(argv)}   ({cwd})\n", flush=True)
        os.execvp(argv[0], argv)          # this process becomes the session

    def open_reader(self):
        e = self.current()
        if not e or e.get("kind") == "gone":
            return
        agent = "CODEX" if e.get("src") == "codex" else "CLAUDE"
        lines = []
        for role, ts, body in self.csx.msgs(e):
            if role == "user" and self.csx.is_noise(body):
                continue
            lines.append(("head", f"{'YOU' if role == 'user' else agent} · "
                                  f"{self.csx.clock(ts)}"))
            for ln in body.splitlines() or [""]:
                lines.append(("body", ln))
            lines.append(("body", ""))
        self.reader = [e, lines, 0]

    # ---------- drawing ----------

    def draw(self, scr, banner=None):
        if self.reader:
            return self.draw_reader(scr)
        scr.erase()
        h, w = scr.getmaxyx()
        dim, sel_c = curses.color_pair(1), curses.color_pair(2)
        tool_c = {"claude": curses.color_pair(3), "codex": curses.color_pair(4),
                  "gone": curses.color_pair(1)}

        head = f" {self.mode}> {self.q}"
        scr.addnstr(0, 0, head.ljust(w - 1), w - 1, curses.A_BOLD)
        state = (f" {self.folders[self.fi][1]} · {self.src or 'claude+codex'}"
                 f"{' · today' if self.today else ''} · {len(self.rows)} shown"
                 + (f" · {banner or self.note}" if (banner or self.note) else ""))
        scr.addnstr(1, 0, state.ljust(w - 1), w - 1, dim)
        y = 2
        if self.today:
            scr.addnstr(y, 0, (" " + self.day_line()).ljust(w - 1), w - 1,
                        curses.A_BOLD | dim)
            y += 1
        scr.addnstr(y, 0, "  TOOL    WHEN            MSGS FOLDER           TITLE"
                    .ljust(w - 1), w - 1, curses.A_UNDERLINE | dim)
        y += 1

        body_h = h - y - 1
        if self.sel < self.top:
            self.top = self.sel
        if self.sel >= self.top + body_h:
            self.top = self.sel - body_h + 1

        for i in range(self.top, min(len(self.rows), self.top + body_h)):
            if y >= h - 1:
                break
            e, hits = self.rows[i]
            on = i == self.sel
            tag = ("gone" if e.get("kind") == "gone"
                   else ("codex" if e.get("src") == "codex" else "claude"))
            when = (self.csx.dt.datetime.fromtimestamp(e["mtime"])
                    .strftime("%b %d %I:%M%p").replace(" 0", " ").lower()
                    if e.get("mtime") else "")
            left = (f"{'▸' if on else ' '} {tag:<7} {when:<15} {e['turns']:>4} "
                    f"{self.csx.proj(e)[:16]:<16} ")
            row = (left + e["title"])[:w - 1]
            scr.addnstr(y, 0, row.ljust(w - 1), w - 1,
                        (sel_c | curses.A_BOLD) if on else tool_c.get(tag, 0))
            y += 1
            if on and hits:
                for role, ts, snip in hits[:2]:
                    if y >= h - 1:
                        break
                    scr.addnstr(y, 4, f"{role} {ts} …{snip}"[:w - 6], w - 6, dim)
                    y += 1

        scr.addnstr(h - 1, 0, HELP[:w - 1].ljust(w - 1), w - 1, dim)
        scr.move(0, min(len(head), w - 1))

    def draw_reader(self, scr):
        e, lines, off = self.reader
        scr.erase()
        h, w = scr.getmaxyx()
        dim = curses.color_pair(1)
        title = (f" {e['title']}  ·  {self.csx.proj(e)}  ·  {e['turns']} messages"
                 f"  ·  {self.csx.clock(e['start'])} → {self.csx.clock(e['end'])}")
        scr.addnstr(0, 0, title.ljust(w - 1), w - 1, curses.A_BOLD)
        body_h = h - 2
        for i in range(body_h):
            if off + i >= len(lines):
                break
            kind, text = lines[off + i]
            scr.addnstr(i + 1, 0, text[:w - 1],
                        w - 1, curses.A_BOLD if kind == "head" else 0)
        pct = int(100 * min(1.0, (off + body_h) / max(len(lines), 1)))
        scr.addnstr(h - 1, 0,
                    f" {pct:>3}% · ↑↓/pgup/pgdn scroll · g/G top/end · "
                    f"enter resume · q back".ljust(w - 1), w - 1, dim)

    # ---------- loop ----------

    def key_reader(self, ch):
        e, lines, off = self.reader
        h = self.h
        page = max(1, h - 4)
        if ch in ("q", "\x1b"):
            self.reader = None
        elif ch in (curses.KEY_DOWN, "\x0e", "j"):
            self.reader[2] = min(max(0, len(lines) - 2), off + 1)
        elif ch in (curses.KEY_UP, "\x0b", "k"):
            self.reader[2] = max(0, off - 1)
        elif ch in (curses.KEY_NPAGE, " ", "\x04"):
            self.reader[2] = min(max(0, len(lines) - 2), off + page)
        elif ch in (curses.KEY_PPAGE, "\x15"):
            self.reader[2] = max(0, off - page)
        elif ch == "g":
            self.reader[2] = 0
        elif ch == "G":
            self.reader[2] = max(0, len(lines) - page)
        elif ch in ("\n", "\r", curses.KEY_ENTER):
            self.resume()

    def loop(self, scr):
        curses.curs_set(1)
        try:
            curses.use_default_colors()
            for i, c in ((1, curses.COLOR_WHITE), (2, curses.COLOR_CYAN),
                         (3, -1), (4, curses.COLOR_YELLOW)):
                curses.init_pair(i, c, -1)
        except curses.error:
            pass

        while True:
            self.h, _ = scr.getmaxyx()
            self.draw(scr)
            try:
                ch = scr.get_wch()
            except (curses.error, KeyboardInterrupt):
                return
            except Exception:
                continue

            if self.reader:
                self.key_reader(ch)
                continue

            if ch == "\x1b":
                return
            elif ch in (curses.KEY_DOWN, "\x0e"):
                self.sel = min(len(self.rows) - 1, self.sel + 1)
            elif ch in (curses.KEY_UP, "\x0b"):
                self.sel = max(0, self.sel - 1)
            elif ch == curses.KEY_NPAGE:
                self.sel = min(len(self.rows) - 1, self.sel + 10)
            elif ch == curses.KEY_PPAGE:
                self.sel = max(0, self.sel - 10)
            elif ch in ("\n", "\r", curses.KEY_ENTER):
                self.resume()
            elif ch == "\x12":                       # ^r
                self.open_reader()
            elif ch == "\x04":                       # ^d
                self.run_search("deep", scr)
            elif ch == "\x07":                       # ^g
                self.run_search("global", scr)
            elif ch == "\x10":                       # ^p prompt log
                self.run_search("prompts", scr)
            elif ch == "\x19":                       # ^y today
                self.today = not self.today
                self.mode = "title"
                self.refilter()
            elif ch == "\x06":                       # ^f folder
                self.fi = (self.fi + 1) % len(self.folders)
                self.mode = "title"
                self.refilter()
            elif ch == "\t":                         # tab tool
                self.src = {"": "claude", "claude": "codex", "codex": ""}[self.src]
                self.mode = "title"
                self.refilter()
            elif ch == "\x15":                       # ^u
                self.q, self.mode, self.note = "", "title", ""
                self.refilter()
            elif ch in ("\x7f", "\b", curses.KEY_BACKSPACE):
                self.q = self.q[:-1]
                self.mode = "title"
                self.refilter()
            elif isinstance(ch, str) and ch.isprintable():
                self.q += ch
                self.mode = "title"
                self.refilter()


def run(csx):
    if not sys.stdout.isatty():
        sys.exit("csx tui needs a terminal")
    tui = Tui(csx, csx.load(quiet=True))
    curses.wrapper(tui.loop)
