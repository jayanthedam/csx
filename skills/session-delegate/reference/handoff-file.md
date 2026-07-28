# Handoff files

## Contents
- When a file beats a primed session
- Writing one
- Resuming from one

## When a file beats a primed session

PREPARE (a primed successor session) is the default: it verifies understanding
before you hand it over. Write a file instead when

- the work resumes days later, or on another machine;
- a person needs to read it;
- you want a durable record independent of any session on disk.

A file can also accompany a primed session — put its path in the priming prompt.

## Writing one

Ground it in reality first, not recollection:

```bash
pwd
git rev-parse --abbrev-ref HEAD 2>/dev/null
git status --short 2>/dev/null
git log --oneline -8 2>/dev/null
csx -H --no-pager -n 5            # what else ran in this folder recently
```

Path:

```bash
SLUG=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
DIR="$HOME/.claude/handoffs/$SLUG"; mkdir -p "$DIR"
echo "$DIR/$(date +%Y-%m-%d-%H%M)-<topic>.md"     # topic: 2-4 word kebab-case
```

The reader has **no memory of the conversation**. Absolute paths, verbatim user
quotes, executable next steps. Mark anything uncertain `UNVERIFIED`; never
invent progress.

```markdown
# Handoff: <one-line mission>

> Written <YYYY-MM-DD HH:MM> for a session with NO memory of the prior chat.
> Source session: `csx show <session-id>`  ·  resume it with `csx resume <session-id>`

## Snapshot
- **Repo / cwd**: <absolute path>
- **Branch**: <branch>
- **Mission**: <what we are ultimately trying to achieve>
- **Status**: <e.g. mid-implementation, 2 of 4 files done, blocked on X>

## Task State
### Done
- <completed step, with paths / commit SHAs>
### In progress
- <what is half-done, and exactly where it stands>
### Next steps (execute in order)
1. <explicit action a cold reader could run>
### Blockers / open questions
- <what is stuck, and what the decision depends on>

## Insights & Gotchas
- <non-obvious discovery, dead end already ruled out, "do NOT touch X because Y">

## Files & Commands Touched
| Path | What / why |
|------|-----------|
| <absolute path> | edited/read — <reason> |

Key commands run:
```
<command that mattered, and what it told us>
```

Git state at handoff:
```
<git status --short + git log --oneline -5>
```

## Verbatim Key Decisions
- > "<exact user instruction>"

## Constraints Still In Force
- <project rules that must be honoured>

---
_Handoff file_: <absolute path to THIS md>
_Repo cwd_: <absolute path>
```

Finish by printing the path and cwd, so the user can paste one line:

```
✅ Handoff written.
  Resume from handoff: <absolute path>
  pwd: <absolute repo cwd>
```

Better still, offer to PREPARE a successor from it immediately — then they get a
resume command instead of a paste.

## Resuming from one

1. Read the file. Given only a slug, list `~/.claude/handoffs/<slug>/` and take
   the most recent, confirming with the user.
2. Verify reality: `pwd`, `git rev-parse --abbrev-ref HEAD`, `git status --short`.
   Flag drift — different branch, new commits, changed files — before acting.
3. If it names a source session, skim the real thing rather than trusting the
   summary: `csx show <session-id> -G "<topic>" --no-pager`.
4. Restate mission, status and the top 3 next steps, then ask to pick up.
5. Honour "Constraints Still In Force" as if given this session.

Storage lives at `~/.claude/handoffs/<repo-slug>/`, deliberately outside any
repo: never committed, survives across repos.
