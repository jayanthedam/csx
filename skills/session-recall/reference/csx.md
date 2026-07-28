# csx reference

## Contents
- Search
- Scope
- Read
- Resume
- Row format
- Performance notes

Always pass `--no-pager` in a non-interactive shell.

## Search

| Command | Searches |
|---|---|
| `csx <words>` | titles; falls back to bodies when nothing matches |
| `csx -d <term>` | message bodies |
| `csx -g <term>` | bodies + tool calls + **tool results** + subagent runs |

Quoted phrases stay whole: `csx -d "agent tables"`. Multiple terms are AND.

`-g` reaches command output and error text. An error string can match 20x more
sessions under `-g` than `-d`.

The prompt log (`~/.claude/history.jsonl`) is separate — every prompt ever
typed, including sessions since deleted. csx does not index it; read it directly
(see the parent SKILL.md snippet) or browse it with `csx ui` → Prompts.

## Scope

| Flag | Effect |
|---|---|
| `-i PATH` | sessions run in PATH itself |
| `-i PATH --sub` | ...and everything nested inside it |
| `-H` | the directory you are standing in |
| `-p NAME` | loose substring on project name or cwd |
| `-b BRANCH` | one git branch |
| `--claude` / `--codex` | one tool |
| `-s` | include subagent runs |
| `--live` | only sessions running right now |
| `--empty` | include zero-message sessions (hidden by default) |
| `--folders` | every folder that has sessions, with counts |

`~/ABL` and `~/ABL/abl-platform` are different scopes — 21 sessions versus 271.
`-i` is exact by design; `--sub` opts into nesting.

## Read

```bash
csx show <id-prefix> --no-pager              # whole transcript
csx show <id-prefix> -G "<regex>" --no-pager # only turns matching a regex
csx show <id-prefix> -m --no-pager           # include tool calls
```

Locate with `-G` before reading — transcripts reach thousands of messages.

## Resume

```bash
csx resume <id-prefix>            # cd <cwd> && claude --resume <full-id>
csx resume <id-prefix> --copy     # also onto the clipboard
csx resume <id-prefix> --fork     # branch it (--fork-session)
csx resume <id-prefix> --danger   # skip permission prompts — only if asked
```

Codex sessions get `codex resume <id>` automatically. Subagent rows resolve to
their parent, which is the resumable one.

## Row format

```
·claude   cf36f5b1 07-26 11:43pm  13h  125 msgs ABL   main   Analyze work patterns
│└ tool   └ id     └ last write  └age └messages └folder └branch └ title
└ running right now
```

`-f` prints full ids. Titles come from `/rename`, else Claude Code's generated
`ai-title`, else the first user message; Codex has no title record.

## Performance notes

- First run builds an index (`~/.claude/.csx-index.json`); later runs are ~0.2s.
- Searching everything reads ~1 GB. Scoping with `-i` or `--claude`/`--codex`
  is the cheapest speed-up.
- `CSX_DEBUG=1` prints phase timings; `CSX_WORKERS=N` changes parallelism.
