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

## UI

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

## Design notes

**The index.** One read per file builds `~/.claude/.csx-index.json` (path, id,
tool, cwd, project, first/last timestamp, message count, title). Entries are
invalidated by `mtime` + `size`, so a rebuild only re-reads what changed — the
day-to-day cost is ~0.2s. A full cold rebuild of ~800 files / 1.3 GB is ~14s.

`json.loads` is ~60% of that. Gating it behind a raw-substring check made things
*worse*: most Claude lines are genuinely `user`/`assistant` records, so the gate
skips little while scanning every (sometimes 100 KB) line three more times.

**Titles.** Three sources, in order:

1. `custom-title` — what you set with `/rename`. Your name always wins.
2. `ai-title` — the name Claude Code picks itself, and what its own `/resume`
   picker shows ("Analyze work patterns and improve productivity"). ~63% of
   sessions have one.
3. the first real user message.

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
