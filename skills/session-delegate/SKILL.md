---
name: session-delegate
description: "Hands work from this chat to another Claude Code or Codex session: prepares a successor session that has already read the context and returns its resume command, launches bounded background workers, checks whether a running worker is alive or hung, and writes or resumes durable handoff files. Use when the user says hand off, continue in a new chat, prep another session, my context is full, launch a worker, run this in the background, is that agent still running, or asks for a resume command for work that does not exist yet."
---

# Session Delegate

Three ways to move work out of this chat. Pick by what the user needs next.

| They want | Mode | Result |
|---|---|---|
| A fresh chat that already understands the work | **PREPARE** | a resume command; the session is warm |
| One bounded investigation answered while they wait | **WORKER** | a findings file |
| Context preserved for later, or for a human to read | **HANDOFF FILE** | a markdown file |

Ask only if genuinely ambiguous. "My context is full, continue in a new chat"
means PREPARE, not HANDOFF FILE.

---

## MODE: PREPARE a successor session

Do not make the user paste a summary into a fresh chat. Create the successor
now, make it read the context, and hand back one command.

This works because `claude -p --session-id <uuid>` runs a real session that
persists to disk with an id you chose, so `claude --resume <uuid>` later opens a
session whose history already holds everything it read.

```
- [ ] 1. Write the priming prompt to a file
- [ ] 2. Launch it with a chosen session id, in the target cwd
- [ ] 3. Check what the successor understood
- [ ] 4. Give the user the resume command
```

### 1. Write the priming prompt to a file

Never inline the prompt on the command line — see **Quoting** below.

```bash
cat > /tmp/prime-<slug>.txt <<'PROMPT'
You are the continuation of work from another session. Right now your job is to
LOAD CONTEXT, not to act.

Mission: <one line — what we are ultimately trying to achieve>
Repo / cwd: <absolute path>          Branch: <branch>
Status: <e.g. "2 of 4 files done, blocked on X">

Read these before answering:
- <absolute path> — <why it matters>
- <absolute path> — <why it matters>

Prior conversation (read the relevant part, do not dump it):
  csx show <session-id> -G "<regex>" --no-pager

Already done:
- <concrete, with paths / commit SHAs>

Next steps, in order:
1. <explicit action a cold reader could execute>
2. ...

Constraints still in force:
- <e.g. never switch branches; run prettier before commit; JIRA key in commits>

Decisions quoted from the user, do not reinterpret:
- "<verbatim>"

Do this now:
1. Read the files listed above.
2. Run: git status --short && git log --oneline -5
3. Reply with: a 3-line restatement of the mission, the top 3 next steps, and
   anything you found that contradicts this brief.
Do not edit files. Do not commit. Do not start the work yet.
PROMPT
```

Reconstruct that content from the real conversation, not from memory of it. Run
`pwd`, `git rev-parse --abbrev-ref HEAD`, `git status --short`,
`git log --oneline -8` first, and mark anything uncertain `UNVERIFIED`.

### 2. Launch it

```bash
SID=$(python3 -c "import uuid; print(uuid.uuid4())")
cd <target cwd> && timeout 15m claude -p --session-id "$SID" \
  --permission-mode auto --output-format json "$(cat /tmp/prime-<slug>.txt)" \
  < /dev/null > /tmp/prime-<slug>.json 2>&1
echo "$SID"
```

**`< /dev/null` is required.** Without it the launcher waits 3s for stdin and
prepends `Warning: no stdin data received in 3s...` to the file, which is no
longer valid JSON.

`--permission-mode auto` is enough: the brief says read-only. Do not add
`--dangerously-skip-permissions` for a priming run.

### 3. Check what it understood

```bash
python3 -c "
import json; d=json.load(open('/tmp/prime-<slug>.json'))
print(d['session_id']); print(d['result'])"
```

Read the restatement. If it misread the mission or flagged a contradiction, fix
the brief and prime a **new** session — do not hand over a confused one.

### 4. Hand it over

```bash
csx resume "$SID"        # prints: cd <cwd> && claude --resume <id>
```

Give the user that one line and a sentence on what the successor already knows.
It will open with the full priming exchange in its history.

### Codex successor

Same four steps. Codex prints its id as a `thread.started` event under `--json`:

```bash
timeout 15m codex exec -C <target cwd> -s read-only --skip-git-repo-check --json \
  -o /tmp/prime-<slug>.md "$(cat /tmp/prime-<slug>.txt)" \
  < /dev/null > /tmp/prime-<slug>.jsonl 2>&1

SID=$(python3 -c "
import json
for line in open('/tmp/prime-<slug>.jsonl', errors='ignore'):
    try:
        d = json.loads(line)      # first line is a stdin notice, not JSON
    except ValueError:
        continue
    if d.get('type') == 'thread.started':
        print(d['thread_id']); break
")
cat /tmp/prime-<slug>.md          # the successor's restatement
csx resume "$SID"                 # cd <cwd> && codex resume <id>
```

`-s read-only` is the Codex equivalent of a read-only priming run. Never prime
with `--dangerously-bypass-approvals-and-sandbox`.

Do not nest a `<<PY` heredoc inside another heredoc to build these commands —
the inner terminator closes the outer one. Write the script to a file, or use
`python3 -c` as above.

---

## MODE: WORKER — one bounded job, findings back

For "investigate X and tell me", not for continuing a conversation.
Commands per CLI: [reference/launching.md](reference/launching.md)

Non-negotiables, because each has burned a run before:

- **Bounded scope.** Exact task, cwd, whether edits are allowed, expected output.
- **A durable output file** (`-o` for Codex, redirect for Claude) and a
  `timeout` budget. Never launch unattended without both.
- **Split large jobs.** One worker per subsystem beats one worker for a repo.

## MODE: HANDOFF FILE — durable, human-readable

Use when the successor starts later, on another machine, or a person must read
it. Otherwise PREPARE is better: it verifies understanding, this cannot.

Template, storage path and the resume-from-file procedure:
[reference/handoff-file.md](reference/handoff-file.md)

---

## Quoting: write the prompt to a file, always

Background launches get wrapped in `eval '<command>'`. One apostrophe anywhere
in an inline heredoc prompt — `scopes['search.query']`, `don't`, `the tool's
binding` — terminates the wrapper's quoting and the worker starts with **no
prompt at all**.

Failure signature: the log contains only `Reading additional input from
stdin...`, the output file never appears, CPU sits at 0.0, and the process lives
forever blocked on a stdin that never closes. It looks exactly like a hung run.

Verify the launch took, rather than that a process exists:

```bash
wc -c /tmp/<slug>.log      # ~39 bytes == the stdin-wait message == dead on arrival
```

Kill such a worker by PID before relaunching — it holds the same `-o` path and
its exit can overwrite the new run's file.

## Is it still running?

`csx --live --no-pager` lists sessions with a live process. For deciding alive
vs waiting vs hung, and the budget guidance:
[reference/monitoring.md](reference/monitoring.md)

## Safety defaults

- Claude `--permission-mode auto`; Codex `--ask-for-approval on-request
  --sandbox workspace-write`.
- Use no-prompt modes only when the user explicitly asks for this turn, or the
  environment is externally sandboxed. Never for a priming run.
- Never put secrets in a prompt or on a command line.
- Don't launch unsupervised edit workers on a dirty worktree; have the worker
  run `git status --short --branch` first.
- In `abl-platform`, every worker brief that may edit gets: never switch
  branches, never run `git checkout`, preserve unknown edits, honour the
  prettier / TypeScript / JIRA-key rules.
