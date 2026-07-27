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
| `-p NAME` | filter by project or cwd |
| `-n N` / `-a` | cap results / no cap |
| `-f` | print full session ids instead of the 8-char prefix |
| `-G REGEX` | with `show`: only print turns matching a regex |
| `--no-pager` | never page (for piping into grep) |
| `-R` | force a reindex |

A bare `csx some words` searches titles; if nothing matches it falls back to a
body search automatically, so you rarely have to pick a flag.

## UI

`csx ui` serves `http://127.0.0.1:8787` and opens it (`csx ui 9000` for another
port, `--no-open` to skip the browser).

- **Click a row** → copies `cd <cwd> && claude --resume <id>` (or `codex resume <id>`)
- **Click the id** → copies the raw session id
- **Double-click** → full transcript, with the resume command as a copy chip
- Search in **Titles / Messages / Everything**, filter by tool, toggle subagent runs
- Theme: Auto / Light / Dark, remembered in `localStorage`
- `/` focuses search, `Esc` closes the transcript

Clipboard writes are verified by reading back — but only when permission is already
granted, so it never triggers a browser permission prompt. If a write fails, a
pre-selected text box appears instead of a toast that lies about having copied.

## Design notes

**The index.** One pass over every JSONL builds `~/.claude/.csx-index.json`
(path, id, tool, cwd, project, first/last timestamp, message count, title).
Entries are invalidated by `mtime` + `size`, so a rebuild only re-reads what
changed. Full build ≈ 6s for ~800 files; warm start is instant.

**Titles.** Claude Code writes a `summary` record for some sessions — that wins.
Otherwise it's the first real user message, with system reminders, skill preambles,
`AGENTS.md` blocks and Codex's `<environment_context>` filtered out, or you get a
wall of boilerplate instead of a title.

**Why search is fast.** The obvious prefilter — decode each file to `str`, then
`re.search(..., re.I)` — costs 8.15s over 892 MB. Reading bytes and doing
`needle in blob.lower()` costs 1.28s for the same result, so that's the gate;
only the ~60 files that pass get parsed as JSON. A worst-case search (term matches
nothing, so nothing short-circuits) is ~2.2s.

A thread pool made this **slower** (10.6s), not faster: it's CPU-bound regex under
the GIL, not I/O. Left single-threaded on purpose.

**Codex quirk.** A resumed Codex session writes several `rollout-*.jsonl` files
under one session id. `show` and `resume` collapse them to the newest segment;
the listing still shows each segment on its own date.

## Ideas / not done yet

- Date-range filter (`--since 2026-07-01`)
- Export a session to Markdown
- Search `~/.claude/history.jsonl` (every prompt typed, including sessions since deleted)
- Stats view: sessions per day, tokens, which projects eat the time
