---
name: session-handoff
description: Capture the full working context of a chat session into one portable markdown file so a fresh session can continue with zero re-discovery — and resume from such a file. Use when the user asks to hand off, transfer memory/context, dump the session, write a handoff, continue in a new chat, or when this session's context is degrading. Also use when a new session is handed a handoff file to pick up prior work.
---

# Session Handoff

## Overview

A chat accumulates insights, dead ends, decisions, and touched files that live only in this
context window. When context fills or the user starts a new chat, all of that is lost and the new
session re-discovers everything. This skill turns that live context into one **portable markdown
file** written for a *cold reader with no memory*, then knows how to consume such a file on the
other end.

Two modes, auto-detected:

- **WRITE** — user asks to hand off / transfer context / dump the session, or context is degrading.
- **RESUME** — user hands you a handoff file (a path, or "continue from this handoff") at the start
  of a new session.

If it's ambiguous which mode applies, ask one question: "Write a new handoff, or resume from one?"

## Core Principle

The reader has **no memory of this conversation**. Every line must stand alone.

- Use concrete absolute file paths, never "the file we edited" or "as discussed above."
- Quote the user's actual instructions verbatim — do not paraphrase intent away.
- Write next steps as explicit actions someone could execute cold, not vague summaries.
- Prefer specifics (function names, line numbers, commands, error strings) over prose.

---

## MODE: WRITE

### 1. Gather real state (don't rely on memory alone)

Run these to ground the handoff in reality rather than recollection:

```bash
pwd
git rev-parse --abbrev-ref HEAD 2>/dev/null
git status --short 2>/dev/null
git log --oneline -8 2>/dev/null
```

Reconstruct from the actual conversation: files you read/edited, commands you ran, errors hit,
decisions the user made, things you tried that failed, and what's left undone. Do not invent
progress — if something is uncertain, mark it `UNVERIFIED`.

### 2. Compute the output path

```bash
SLUG=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
DIR="$HOME/.claude/handoffs/$SLUG"
mkdir -p "$DIR"
# filename: <YYYY-MM-DD-HHMM>-<short-topic>.md  — ask the date via `date` since Date.now is fine in bash
STAMP=$(date +%Y-%m-%d-%H%M)
echo "$DIR/$STAMP-<topic>.md"
```

Replace `<topic>` with a 2-4 word kebab-case slug of the mission (e.g. `action-tools-tool-test`).

### 3. Write the file using this template

Fill every section. Delete a section only if it is genuinely `N/A`, and say so.

```markdown
# Handoff: <one-line mission>

> Written <YYYY-MM-DD HH:MM> for a fresh session with NO memory of the prior chat.
> To continue: invoke the `session-handoff` skill in RESUME mode and point it at this file.

## Snapshot
- **Repo / cwd**: <absolute path>
- **Branch**: <branch>
- **Mission**: <what we're ultimately trying to achieve, 1-2 sentences>
- **Status**: <e.g. "mid-implementation, 2 of 4 files done, blocked on X">

## Task State
### Done
- <completed step — concrete, with file paths / commit SHAs>
### In progress
- <what's half-done right now, and exactly where it stands>
### Next steps (execute in order)
1. <explicit next action — a cold reader could run it>
2. ...
### Blockers / open questions
- <anything stuck, and what a decision depends on>

## Insights & Gotchas
- <non-obvious discovery, dead end already ruled out, "do NOT touch X because Y">
- <nuance about the codebase/tooling learned this session>

## Files & Commands Touched
| Path | What / why |
|------|-----------|
| <absolute path> | edited/read — <reason> |

Key commands run:
```
<command that mattered, with what it told us>
```

Git state at handoff:
```
<paste of git status --short + git log --oneline -5>
```

## Verbatim Key Decisions
Quote the user directly — do not paraphrase.
- > "<exact user instruction / decision>"
- > "<exact open question the user posed>"

## Constraints Still In Force
- <project rules that must be honored: e.g. never switch branches, run prettier before commit,
  strict tsc gate, JIRA key format — pull the ones actually relevant to this work>

---
_Handoff file_: <absolute path to THIS md>
_Repo cwd_: <absolute path>
```

### 4. Echo the path to the user

After writing, print to the user, clearly, so they can copy it straight into the next chat:

```
✅ Handoff written.

Give the next session this line:
  Resume from handoff: <absolute path to the md>

pwd: <absolute repo cwd>
```

The final thing you say MUST include the absolute path of the md and the `pwd`. This is the whole
point — the user pastes that one line into a fresh chat.

---

## MODE: RESUME

Triggered when a new session is given a handoff path or told to continue from one.

1. **Read the file** at the given path (Read tool). If only a directory or slug was given, list
   `~/.claude/handoffs/<slug>/` and pick the most recent, confirming with the user.
2. **Verify reality matches** — run `pwd`, `git rev-parse --abbrev-ref HEAD`, `git status --short`.
   Compare against the handoff's Snapshot / Git state. **Flag any drift** (different branch, files
   changed since, commits added) before doing anything — the world may have moved on.
3. **Restate to the user**: mission, current status, and the top 3 next steps, then ask: "Pick up
   here?" Do not silently start editing.
4. **Honor the Constraints Still In Force** section as if they were given this session.
5. On confirmation, continue at the first unchecked next step.

---

## Notes

- Storage `~/.claude/handoffs/<repo-slug>/` is intentionally outside any repo — never committed,
  survives across repos, easy to point a new session at.
- This skill captures context; the sibling `ai-session-orchestrator` skill *launches/resumes* the
  actual worker sessions. Use them together: write a handoff here, then hand its path to a session
  started via that skill.
- Proactively suggest a WRITE handoff when you notice this session's context degrading (repeated
  re-reading, lost thread, user says you're deviating) — don't wait to be asked.
