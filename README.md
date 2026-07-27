# csx — browse and search your Claude Code + Codex sessions

Every Claude Code and Codex conversation is already on disk as JSONL. `csx` makes
that pile searchable: list every session, find the one where you discussed a thing,
read it back, and get the exact command to resume it.

Two files, no dependencies, no build step, no network calls.

```
csx                        every session, newest first, in a pager
csx auth profile           search titles
csx -d base_row_id         search message bodies
csx -g base_row_id         search everything (+ tool calls + subagent runs)
csx show cf36f5b1          read a transcript
csx resume cf36f5b1        print the exact resume command
csx ui                     browser view, click a row to copy its resume command
```

## Install

```bash
ln -sf ~/personal/project/csx/csx      ~/.local/bin/csx
ln -sf ~/personal/project/csx/csx_ui.py ~/.local/bin/csx_ui.py
```

Requires Python 3.8+ and `less` (already on any Linux box). Nothing else.

## What it reads

| Source | Location | Format |
|---|---|---|
| Claude Code | `~/.claude/projects/**/*.jsonl` | `{"type":"user"/"assistant","message":{...}}` |
| Claude subagents | `~/.claude/projects/**/subagents/*.jsonl` | same, one file per Task run |
| Codex | `~/.codex/sessions/**/rollout-*.jsonl` | `{"type":"response_item","payload":{...}}` |
| Codex archived | `~/.codex/archived_sessions/*.jsonl` | same |

Read-only. It never writes to either tool's directory — its own index lives at
`~/.claude/.csx-index.json`.

## CLI

| Flag | Meaning |
|---|---|
| `-d` / `-g` | search message bodies / everything incl. tool calls + subagent runs |
| `-s` | include subagent runs in the listing |
| `-b BRANCH` | only sessions on that git branch |
| `--empty` | include sessions with no messages (hidden by default) |
| `--live` | only sessions running right now |
| `resume --danger` | add the permission-bypass flag for that tool |
| `resume --fork` | branch the session instead of continuing it |
| `resume --copy` | put the command on the clipboard |
| `--claude` / `--codex` | restrict to one tool |
| `-p NAME` | substring match on project name or cwd |
| `-i PATH` | only sessions run in PATH **itself** (`-i ~/ABL`) |
| `-H` | same, for the directory you're standing in |
| `--sub` | with `-i`/`-H`: include folders nested inside it too |
| `--folders` | list every folder that has sessions, with counts |
| `-n N` / `-a` | cap results / no cap |
| `-f` | print full session ids instead of the 8-char prefix |
| `-G REGEX` | with `show`: only print turns matching a regex |
| `--no-pager` | never page (for piping into grep) |
| `-R` | force a reindex |

### Scoping to one folder

`~/ABL` and `~/ABL/abl-platform` are different working folders, and most sessions
live in the latter. To see only the ones you ran from `~/ABL` itself:

```bash
csx --folders             # what folders exist, and how many sessions each holds
csx -i ~/ABL              # ~/ABL itself                    → 21 sessions
csx -i ~/ABL --sub        # ~/ABL + everything nested in it  → 331 sessions
csx -H                    # whatever directory you're in right now
csx -i ~/ABL -d OOM       # scoping also makes search faster — less to read
```

A bare `csx some words` searches titles; if nothing matches it falls back to a
body search automatically, so you rarely have to pick a flag.

## TUI — `csx tui`

The same thing without leaving the terminal, and the reason to prefer it:
**Enter doesn't copy a command or spawn a window — the process `exec`s into the
session.** You are just in it.

```
 title> agent tables
 ~/ABL (21) · claude+codex · 12 shown
   TOOL    WHEN            MSGS FOLDER           TITLE
 ▸ claude  jul 27 12:27pm    50 ABL              AGENT TABLES
   claude  jul 27 12:25pm  1439 ABL              Map agent tables setup across dev and QA
 enter resume · ^r read · ^d deep · ^g global · ^p prompts · ^y today · ^f folder …
```

`/` starts a filter (enter applies, esc clears). Everything else is a plain
letter — no Ctrl combos, because terminals and layouts swallow some of them
(`^x` never arrived under Ghostty) and `^C`/`^Z`/`^S` are already spoken for:

| | |
|---|---|
| `j` `k` `g` `G` `space` | move, top, bottom, page |
| `enter` | resume — this process becomes the session |
| `b` | branch it instead (`--fork-session`) |
| `y` / `Y` | copy the resume command / the session id |
| `x` | danger: resume and copy skip permission prompts |
| `r` | read the transcript (markdown; `m` for raw source) |
| `d` / `a` / `p` | search bodies / everything / your prompt log |
| `t` / `s` / `f` | today · claude-codex-both · folder picker |
| `?` / `q` | keys · quit |

`f` opens a folder picker — every folder with a session count, type to filter,
enter to scope. `r` opens a built-in reader that renders the markdown —
headings, bullets, blockquotes, fenced code as `┌─ bash │ …`, inline styles —
word-wrapped to your terminal. Stdlib `curses`, no dependencies.

## Browser UI

`csx ui` serves `http://127.0.0.1:8787` and opens it (`csx ui 9000` for another
port, `--no-open` to skip the browser).

- **Click a row** → copies `cd <cwd> && claude --resume <id>` (or `codex resume <id>`)
- **Click the id** → copies the raw session id
- **Double-click** → full transcript, rendered as Markdown. **← Back to list**
  or `Esc` returns. **Raw text** shows the unrendered source; **Tool calls**
  folds the agent's tool invocations back in (hidden by default — they drown
  out the conversation)
- Search in **Titles / Messages / Everything**, filter by tool, toggle subagent runs
- **Folder dropdown** — each folder and how many sessions ran in it
  (`~/ABL — 21 sessions`). Picking one shows exactly that count; nested folders
  are opt-in via **+ subfolders**
- **▶ Resume** on any row opens a new terminal already inside that session
  (`claude --resume` / `codex resume`, in the right cwd). ⧉ Copy still copies
  the command instead, if you'd rather paste it yourself
- **⚠ danger** checkbox — Resume, Fork and the copied command all switch to the
  permission-bypass flag (`--dangerously-skip-permissions` for Claude,
  `--dangerously-bypass-approvals-and-sandbox` for Codex)
- **Today** filters to sessions you touched today and shows a summary strip:
  count, messages, first→last span, and which folders they were in
- **Prompts** is a fourth search mode over `~/.claude/history.jsonl` — every
  prompt you have typed (12k here), including ones whose session is gone
- Keyboard: `↑↓`/`j`/`k` move, `Enter` reads, `o` opens a terminal, `y` copies,
  `/` focuses search, `g`/`G` jump to top/bottom, `Esc` closes
- Theme (Auto / Light / Dark) and your mode, folder and tool filters are
  remembered between visits; the list refreshes when you return to the tab

Clipboard writes are verified by reading back — but only when permission is already
granted, so it never triggers a browser permission prompt. If a write fails, a
pre-selected text box appears instead of a toast that lies about having copied.

### Launching terminals

`▶ Resume` posts to `/api/launch`, which spawns `ghostty -e bash -lc "cd <cwd> &&
exec claude --resume <id>"` (falling back to kitty, wezterm, gnome-terminal,
xterm). The command is assembled from indexed values and shell-quoted — the page
sends only a session id, never a command string. The server binds to
`127.0.0.1`, so nothing off-machine can reach it. `?dry=1` returns the argv
without running it.

## Borrowed from the neighbours

Other tools exist for this — [claude-history](https://github.com/raine/claude-history),
[claude-session-manager-tui](https://github.com/borball/claude-session-manager-tui),
[claude-code-log](https://github.com/daaain/claude-code-log). Reading them was
worth it; four things came back:

- **Git branch** per session (as Claude Code's own picker shows). A column in
  both UIs, `-b` to filter. 196 of 403 sessions have one; Codex records none.
- **Tool *results*, not just tool calls.** `-g` used to index what the agent
  ran, not what came back. Searching `ERR_PNPM` found 2 sessions before and
  **42** after — error text and command output live in results.
- **Fork.** `⑂ Fork` / `^o` resumes with `--fork-session`, branching the
  conversation and leaving the original untouched.
- **Skip empty sessions.** 13 sessions have no messages at all; they were pure
  noise in the list. Hidden unless `--empty`.

Not taken: AI-generated summaries (Claude Code's own `ai-title` already fills
that role, free) and semantic search (needs a local embedding model and an
embedding store — a real dependency, and lexical + the prompt log has found
everything so far).

**Live sessions.** A quiet `·` marks sessions running right now (muted green in
the browser, plain in the terminal) — deliberately a dot, not a badge, since on
a normal day five of ~400 rows are live and the list should stay calm.
`csx --live` lists only those.

Detection is two-sided: Claude Code registers each live session as
`~/.claude/sessions/<pid>.json` (a stale file just means the pid is gone, so the
pid is checked against `/proc`), and any resumed session — Claude or Codex —
carries its id on the process command line, so `/proc/*/cmdline` is scanned too.
Cached for 3s so redraws stay cheap.

## Design notes

**The index.** One read per file builds `~/.claude/.csx-index.json` (path, id,
tool, cwd, project, first/last timestamp, message count, title). Entries are
invalidated by `mtime` + `size`, so a rebuild only re-reads what changed — the
day-to-day cost is ~0.2s. A full cold rebuild of ~800 files / 1.3 GB is ~14s.

`json.loads` is ~60% of that, and 78 of every 98 MB sits in `user`/`assistant`
records that genuinely have to be parsed — so the fix is spreading the work, not
avoiding it. Indexing and search run on a `fork` process pool
(`min(6, cores-2)`, override with `CSX_WORKERS`):

| | serial | 6 workers |
|---|---|---|
| full rebuild (warm cache) | 15.8s | **6.2s** |
| full rebuild (cold cache) | 30.6s | **8.4s** |
| search, rare term, whole corpus | 5.7s | **3.5s** |
| search, common term (stops at 80) | 1.4s | **0.7s** |
| incremental start (nothing changed) | 0.15s | 0.15s |

Threads were tried first and made it *slower* (10.6s vs 8.2s) — this is CPU-bound
work under the GIL. Processes don't share it.

Two things that mattered more than the pool itself:

- **Mine in the worker, not the parent.** The first version only prefiltered in
  parallel and parsed matches in the parent, leaving 5 cores idle during the
  expensive half. Moving snippet extraction into the worker halved rare-term
  search again (7.2s → 3.6s).
- **Feed the pool in windows.** `imap` submits every task up front, so a search
  that stops at 80 results still paid for the whole corpus — a common-term query
  went from 1.85s to 3.52s. Batching `WORKERS * 8` at a time keeps cores busy
  while early exit stays cheap.

Gating `json.loads` behind a raw-substring check also made things *worse*: too
few lines are skippable, and every large line gets scanned three extra times.

**Titles.** Three sources, in order:

1. `custom-title` — what you set with `/rename`. Your name always wins.
2. `ai-title` — the name Claude Code picks itself, and what its own `/resume`
   picker shows ("Analyze work patterns and improve productivity"). ~63% of
   sessions have one.
3. the first real user message.

Both title records are **rewritten as the session evolves** — one session here
carries 46 copies of an old name followed by 87 of the current one. Take the
last, not the first, or the list disagrees with Claude Code's own picker.

The fallback filters noise first: system reminders,
skill preambles, `AGENTS.md` blocks and Codex's `<environment_context>` are
filtered out first, or the title is a wall of boilerplate. Codex writes no title
record of its own, so Codex rows are always first-message titles.

**Why search is fast.** The obvious prefilter — decode each file to `str`, then
`re.search(..., re.I)` — costs 8.15s over 892 MB. Reading bytes and doing
`needle in blob.lower()` costs 1.28s for the same result, so that's the gate;
only the ~60 files that pass get parsed as JSON. A worst-case search (term matches
nothing, so nothing short-circuits) is ~2.2s.

A thread pool made this **slower** (10.6s), not faster: it's CPU-bound regex under
the GIL, not I/O. Left single-threaded on purpose.

**Folder counts.** One number per folder: sessions that ran in it, counted once,
ranked by that number. A parent does not absorb its children's sessions unless
you ask (`--sub`). Three things that quietly go wrong here and are covered by `tests.py`:

- **Sibling prefixes.** `~/ABL/abl-platform` must not swallow `-deploy`, `-infra`,
  `-2268` or `_worktrees`, all of which exist in this tree. The prefix check is
  anchored on a path separator, not a bare `startswith`.
- **One session, several files.** A resumed Codex session writes multiple rollout
  files; counts key on distinct session id so it isn't tallied twice.
- **Sessions with no recorded cwd.** 9 of mine have none. They'd silently vanish
  from every folder filter, so they get their own `(no folder recorded)` bucket
  that you can scope to like any other folder.

**Exact by default.** Both `-i` and the UI dropdown scope to the folder itself.
Subfolders are opt-in (`--sub`, or the checkbox) so the number you pick is the
number you get. `~/ABL` is 21 sessions; `~/ABL --sub` is 331.

`-p` is different and deliberately loose: `-p abl-platform` is a substring match,
so it *does* also hit `abl-platform-deploy`. Use `-i` when you mean one folder.

**Markdown.** Transcripts are Markdown, so the reader renders them — fenced code,
headings, lists, tables, blockquotes, inline code, links, bold/italic — with a
~60-line renderer rather than a library, since the page must stay self-contained.
Input is HTML-escaped before any transform, and fenced blocks are lifted out
first so their contents are never treated as markup.

**Z-index.** The panel is `position:fixed; inset:0`, which is *not* enough to sit
above a `position:sticky` header — the header wins on paint order regardless of
coverage, so its own Back button was unclickable underneath. The panel needs an
explicit `z-index` above the header's.

**Clocks.** Everything renders in local 12-hour time. Transcript timestamps are
stored UTC with a `Z`, so they're converted, not truncated — reading `13:47Z` as
a wall-clock time would be off by your UTC offset.

**Codex quirk.** A resumed Codex session writes several `rollout-*.jsonl` files
under one session id. `show` and `resume` collapse them to the newest segment;
the listing still shows each segment on its own date.

## Tests

```bash
python3 tests.py     # 19 assertions, no deps; also cross-checks the live index
```

The live-index check asserts that, for every folder, the counts shown by
`--folders` equal what `-i` and `-i --only` actually return.

## Ideas / not done yet

- Date-range filter (`--since 2026-07-01`), and a Today-like view for any past day
- Export a session to Markdown
- `csx go <query>` — same one-step resume from the CLI
- Trend view: sessions/day over weeks, not just today
