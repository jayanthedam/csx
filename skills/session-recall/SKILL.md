---
name: session-recall
description: "Finds and reads past Claude Code and Codex sessions stored on this machine, and reports which ones are running now. Use when the user refers to earlier work that is not in this context — 'the session where we debugged X', 'what did I do yesterday', 'find that chat about the OAuth bug', 'which session had the RCA', 'is that worker still running', 'resume the one from last week' — or when prior decisions, commands, or error output live in another session's transcript. Produces an answer plus the exact resume command, not a tool tour."
---

# Session Recall

Every Claude Code and Codex conversation on this machine is on disk as JSONL.
`csx` indexes them. Use it to answer the question, then hand over the session id
and its resume command.

## Tool

`csx` is on PATH (source: `~/personal/project/csx`). It is read-only over
`~/.claude/projects/**` and `~/.codex/sessions/**`.

**Always pass `--no-pager`.** Without it `csx` opens `less` and hangs a
non-interactive shell.

Full flag reference: [reference/csx.md](reference/csx.md)

## Workflow

```
- [ ] 1. Search wide (titles → bodies → everything → prompt log)
- [ ] 2. Narrow by folder / tool / branch if there is too much
- [ ] 3. Read only the relevant part of the transcript
- [ ] 4. Answer the question, then give the resume command
```

### 1. Search wide

The user rarely remembers a title, so search what was *said*, not what it was
called. Each step reaches further than the last — stop at the first that answers.

```bash
csx "<words>" --no-pager                  # titles; silently falls back to bodies
csx -d "<term>" --no-pager -n 10          # message bodies
csx -g "<term>" --no-pager -n 10          # + tool calls, tool results, subagents
```

`-g` matters more than it looks: it indexes command output and error text, so
`ERR_PNPM` matches 42 sessions under `-g` versus 2 under `-d`.

Still nothing? The prompt log is a separate corpus — every prompt ever typed,
including sessions since deleted or compacted away:

```bash
python3 - "<term>" <<'PY'
import json, os, sys
term = sys.argv[1].lower()
for line in open(os.path.expanduser("~/.claude/history.jsonl"), errors="ignore"):
    d = json.loads(line)
    if term in d.get("display", "").lower():
        print(d["timestamp"], d["project"], d["display"][:160])
PY
```

### 2. Narrow

These compose with any search:

```bash
csx -d "<term>" -i ~/ABL --no-pager        # ran in that folder (--sub adds nested)
csx -d "<term>" --codex --no-pager         # one tool only (--claude for the other)
csx -d "<term>" -b <branch> --no-pager     # one git branch
csx --folders --no-pager                   # what folders exist, with counts
```

Scoping is also the cheapest speed-up: searching everything reads ~1 GB.

### 3. Read

Transcripts run to thousands of messages. Locate first, then read around it:

```bash
csx show <id-prefix> -G "<regex>" --no-pager   # only turns matching a regex
csx show <id-prefix> --no-pager                # whole thing
csx show <id-prefix> -m --no-pager             # include tool calls
```

### 4. Answer

Report what the user asked for. Then, and only then, the session:

```bash
csx resume <id-prefix>                # cd <cwd> && claude --resume <full-id>
csx resume <id-prefix> --copy         # ...and onto the clipboard
csx resume <id-prefix> --fork         # branch it instead of continuing it
```

Do **not** add `--danger` unless the user asked. It bypasses every permission
prompt (`--dangerously-skip-permissions` /
`--dangerously-bypass-approvals-and-sandbox`).

## Is a session running right now?

```bash
csx --live --no-pager          # sessions with a live process
```

`csx` resolves this from Claude Code's pid registry plus `/proc` command lines,
so it beats grepping `ps`. A `·` before any row means that row is live.

Live is not the same as *working*. The list is newest-first by last write, so
combine both facts:

- live + written to in the last minute → working
- live + nothing written for 30+ minutes → waiting on input, or hung
- not live → finished or killed

For judging a worker you launched yourself, see the `session-delegate` skill.

## Reading the output

```
claude   cf36f5b1 07-26 11:43pm  13h  125 msgs ABL   main   Analyze work patterns
└ tool   └ id     └ last write  └age └messages └folder └branch └ title
```

- `claude` / `codex` / `subagent` — subagent rows are Task runs inside a
  session. They are not separately resumable; `csx resume` returns the parent.
- Titles come from `/rename`, else Claude Code's own generated name, else the
  first user message. Codex writes no title, so Codex rows show a first prompt.
- `-f` prints full session ids when one must be quoted exactly.

## Rules

- Never guess a session id. If several match, list them with titles and dates
  and let the user choose.
- Report the finding, not the search. The user wants the answer and the resume
  command, not a transcript of which flags were tried.
- `csx tui` and `csx ui` exist for browsing. Mention them only if the user asks
  to browse — being asked to find something is not a request for a tool tip.
