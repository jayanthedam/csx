---
name: find-session
description: "Find a past Claude Code or Codex session on this machine and read what happened in it. Use when the user refers to earlier work not in the current context — 'the session where we debugged X', 'what did I do yesterday', 'find that chat about the OAuth bug', 'which session had the RCA', 'resume the one from last week' — or when you need prior decisions, commands, or findings that live in another session's transcript."
---

# Find Session

Search every Claude Code and Codex transcript on this machine, read the relevant
one, and report what it contains.

## Tool

`csx` (on PATH; source at `~/personal/project/csx`). Read-only over
`~/.claude/projects/**` and `~/.codex/sessions/**`. Always pass `--no-pager` —
without it the CLI opens `less` and will hang a non-interactive shell.

## Procedure

1. **Widen from the user's words.** They rarely remember titles. Start with the
   term most likely to appear *inside* the conversation, not in a title:

   ```bash
   csx -d "<term>" --no-pager -n 10      # message bodies
   csx -g "<term>" --no-pager -n 10      # + tool calls + subagent runs
   ```

   `csx <words>` alone searches titles and silently falls back to bodies when
   nothing matches, so it is a fine first shot for a vague ask.

2. **Narrow when you have too much.** These compose:

   ```bash
   csx -d "<term>" -i ~/ABL --no-pager        # sessions run in that folder
   csx -d "<term>" -i ~/ABL --sub --no-pager  # ...and its subfolders
   csx -d "<term>" --codex --no-pager         # Codex only (--claude for the other)
   csx --folders --no-pager                   # every folder with a session count
   ```

3. **Still nothing? Search the prompt log.** Every prompt the user ever typed is
   in `~/.claude/history.jsonl`, including prompts whose session was deleted or
   compacted away. Nothing else reaches these:

   ```bash
   python3 -c "
   import json,os
   for l in open(os.path.expanduser('~/.claude/history.jsonl'),errors='ignore'):
       d=json.loads(l)
       if '<term>' in d.get('display','').lower(): print(d['timestamp'], d['project'], d['display'][:160])
   "
   ```

4. **Read the transcript.** Do not dump it — it can be thousands of messages.

   ```bash
   csx show <id-prefix> --no-pager                  # whole thing
   csx show <id-prefix> -G "<regex>" --no-pager     # only turns matching a regex
   csx show <id-prefix> -m --no-pager               # include tool calls
   ```

   Prefer `-G` first to locate the part that matters, then read around it.

5. **Report, don't relay.** Give the user the answer they asked for plus the
   session id and its resume command:

   ```bash
   csx resume <id-prefix>      # prints: cd <cwd> && claude --resume <full-id>
   ```

## Reading the output

```
claude   cf36f5b1 07-26 11:43pm  13h  125 msgs ABL   Analyze work patterns and improve productivity
└ tool   └ id     └ last touched └age └messages └folder └ title
```

- `claude` / `codex` / `subagent` — which tool wrote it. Subagent rows are Task
  runs inside a session; they are not separately resumable, and `csx resume`
  points at the parent.
- Titles come from `/rename`, else Claude Code's own generated name, else the
  first user message. Codex has no title record, so Codex rows always show a
  first prompt.
- `-f` prints full session ids when you need to quote one exactly.

## Notes

- Searching everything takes a few seconds (~1 GB of transcripts); scoping with
  `-i` or `--claude`/`--codex` is much faster than filtering after the fact.
- The user also has a browser UI (`csx ui`) — mention it only if they ask to
  browse rather than to have an answer found for them.
- Don't guess a session id. If several match, list them with their titles and
  dates and let the user pick.
