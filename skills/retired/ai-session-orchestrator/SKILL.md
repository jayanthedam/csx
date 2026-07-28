---
name: ai-session-orchestrator
description: Launch, resume, fork, or hand off work to another Claude Code or Codex session from an AI-controlled terminal. Use when the user asks for agent-to-agent orchestration, continuous worker sessions, background Claude agents, Codex/Claude resume commands, non-interactive handoffs, PTY/tmux worker chats, or dangerous/no-prompt automation modes.
---

# AI Session Orchestrator

## Overview

Use this skill to start a child Claude/Codex worker, resume an existing worker, or hand off a bounded prompt without losing session continuity. Prefer explicit scope, cwd, and permission mode in every command.

## First Checks

Before giving or running commands:

- Verify the installed CLI syntax if the exact flag matters: `claude --help`, `claude agents --help`, `codex --help`, `codex resume --help`, `codex exec --help`, or `codex exec resume --help`.
- Ask before using dangerous/no-prompt modes unless the user already explicitly requested them for this turn.
- Keep child prompts bounded: exact task, cwd, branch/worktree constraint, allowed files, expected output, and whether edits are allowed.
- In `abl-platform`, include: never switch branches, never run `git checkout`, preserve unknown edits, and run prettier/build/typecheck rules when editing.

## Choose Mode

- Use a long-lived interactive child when the worker needs iterative chat, tool use, or manual follow-up.
- Use a non-interactive handoff when the worker should do one bounded investigation and return a summary.
- Use `codex resume <session-id>` or `claude --resume <session-id>` for continuous interactive continuation when the worker already has useful context.
- Use dangerous/no-prompt mode only for trusted, externally sandboxed, or explicitly approved automation.

## Health Check Running Workers

When a user asks whether a long-running Claude/Codex worker is really running, do not trust elapsed time alone. Check process state, child commands, and session transcript movement before saying it is alive or hung.

Process check:

```bash
ps -o pid,ppid,stat,etime,pcpu,pmem,tty,cmd -u "$USER" | rg 'codex|claude|PID'
```

Interpretation:

- `R` with changing CPU or active child process means likely working.
- `S`/`I` with near-zero CPU can be normal for a chat UI waiting on network or user input.
- `T` means stopped/suspended.
- `Z` means zombie/dead.
- `D` means blocked in uninterruptible I/O.
- Long `ETIME` plus no CPU and no transcript changes usually means idle, blocked, or hung rather than doing useful work.

Codex transcript check:

```bash
find ~/.codex/sessions -type f -mmin -35 -printf '%TY-%Tm-%Td %TH:%TM %p\n' | sort
```

Claude transcript check:

```bash
find ~/.claude/projects -type f -name '*.jsonl' -mmin -35 -printf '%TY-%Tm-%Td %TH:%TM %p\n' | sort
```

If a specific session id is known, search the index/transcripts:

```bash
rg '<session-id>' ~/.codex/session_index.jsonl ~/.codex/sessions ~/.claude/projects
```

Verdict rules:

- Alive and working: process exists, recent transcript writes, and CPU/child command activity or new output.
- Alive but waiting: process exists, no recent transcript writes, low CPU, and TTY/session is waiting for user input or approval.
- Hung/stuck: process exists for a long time, no transcript changes, no child process progress, and no visible prompt/output movement.
- Not running: no matching process and no recent transcript writes.

When reporting, say which evidence was checked. Example: "Process exists but no transcript has changed in 30 minutes and CPU is 0.0, so it is alive but not doing useful work."

## Never Build The Prompt In The Same Command That Launches The Worker

Write the prompt to a file in one call, launch the worker in a separate call. Background launches are wrapped in `eval '<command>'`, so a single quote or apostrophe anywhere in an inline heredoc prompt (`scopes['search.query']`, `don't`, `the tool's binding`) terminates the wrapper's quoting and the worker starts with NO prompt argument.

Failure signature: the log contains only `Reading additional input from stdin...`, the output file is never created, CPU sits at 0.0, and the process stays alive indefinitely because it is blocked on a stdin that never closes. It looks identical to a hung review.

```bash
# call 1 — write the prompt
cat > /tmp/worker-<slug>.txt <<'EOF'
<bounded prompt, quotes and apostrophes are safe here>
EOF

# call 2 — launch, nothing quotable on the command line but the file read
timeout --preserve-status --signal=INT --kill-after=2m <budget> \
  codex exec -C <repo> -s read-only --skip-git-repo-check \
  -o /tmp/worker-<slug>.md "$(cat /tmp/worker-<slug>.txt)" > /tmp/worker-<slug>.log 2>&1
```

Verify the launch took, not just that a process exists:

```bash
wc -c /tmp/worker-<slug>.log            # 39 bytes == the stdin-wait message == dead on arrival
ps -u "$USER" -o pid,etime,pcpu,args | rg 'codex exec|claude -p'
```

A worker doing real work shows non-trivial CPU within the first minute. A stdin-blocked worker shows `0.0` forever and must be killed by PID, not waited on. When relaunching after this failure, kill the old PIDs first: they hold the same `-o` output path and their eventual exit can overwrite or race the new run's file.

## Prevent Silent Worker Hangs

Do not launch unattended non-interactive workers without a durable output file and an explicit runtime budget. This especially applies when one AI session launches `codex exec` or `claude -p` from a shell command, because the child process can stay alive while doing no useful work.

Do not use short hard timeouts for valuable long reviews. Pick a budget that matches the task, and only call it stuck when there is no progress evidence: no output file growth, no transcript movement, no CPU/network activity, and no live child command.

Preferred Codex worker pattern:

```bash
timeout --preserve-status --signal=INT --kill-after=2m <budget> codex exec -C <repo> -s read-only --skip-git-repo-check -o /tmp/codex-worker-<slug>.md "<bounded prompt>"
```

Preferred Claude one-shot worker pattern:

```bash
timeout --preserve-status --signal=INT --kill-after=2m <budget> claude -p --permission-mode auto "<bounded prompt>" > /tmp/claude-worker-<slug>.md
```

For dangerous/no-prompt workers, still use `timeout` and `-o`/redirection:

```bash
timeout --preserve-status --signal=INT --kill-after=2m <budget> codex exec -C <repo> --dangerously-bypass-approvals-and-sandbox -o /tmp/codex-worker-<slug>.md "<bounded prompt>"
timeout --preserve-status --signal=INT --kill-after=2m <budget> claude -p --permission-mode bypassPermissions --dangerously-skip-permissions "<bounded prompt>" > /tmp/claude-worker-<slug>.md
```

Budget guidance:

- Small read-only question: `10m` to `20m`.
- Focused repo review: `30m` to `45m`.
- Broad multi-repo audit: split the work; if not possible, use `60m` to `90m` and require output/checkpoints.

After launch, verify within a few minutes:

```bash
ls -l /tmp/codex-worker-<slug>.md /tmp/claude-worker-<slug>.md 2>/dev/null
ps -o pid,ppid,stat,etime,pcpu,pmem,wchan:30,cmd -u "$USER" | rg 'codex exec|claude -p|PID'
```

If the output file is absent or unchanged, CPU is `0.0`, and the process is in `ep_poll`, `futex_do_wait`, or `unix_stream_data_wait` for several minutes, report it as likely stuck and relaunch with a smaller prompt. Do not kill a worker that has recent output, transcript movement, CPU/network activity, or a live child command proving progress.

For complex reviews, split one large prompt into smaller workers. Example: one worker for Terraform, one for Helm, one for secret handoff. Large multi-repo prompts are more likely to hang or produce no useful output.

## Claude Code Commands

Fresh interactive worker:

```bash
claude --permission-mode auto --add-dir /home/Jayanth.Edam/ABL/abl-platform
```

Fresh interactive worker with no permission prompts:

```bash
claude --permission-mode bypassPermissions --dangerously-skip-permissions --add-dir /home/Jayanth.Edam/ABL/abl-platform
```

Continue most recent conversation in current directory:

```bash
claude --continue
```

Resume continuous interactive chat by session id or picker/search:

```bash
claude --resume <session-id-or-search>
claude -r <session-id-or-search>
```

One-shot handoff:

```bash
claude -p --permission-mode auto "Investigate <task>. Return findings with file paths and evidence. Do not edit files."
```

One-shot dangerous handoff:

```bash
claude -p --permission-mode bypassPermissions --dangerously-skip-permissions "Do <bounded task>. Preserve user changes. Report commands run."
```

Background worker:

```bash
claude --bg --permission-mode auto "Work on <task>. Stop before commit and summarize."
claude agents --json
```

Background worker with no permission prompts:

```bash
claude --bg --permission-mode bypassPermissions --dangerously-skip-permissions "Work on <bounded task>. Stop before commit and summarize."
```

## Codex Commands

Fresh interactive worker in a cwd:

```bash
codex -C /home/Jayanth.Edam/ABL/abl-platform --ask-for-approval on-request --sandbox workspace-write
```

Fresh interactive worker with no permission prompts:

```bash
codex -C /home/Jayanth.Edam/ABL/abl-platform --ask-for-approval never --sandbox danger-full-access
```

Most dangerous Codex mode:

```bash
codex -C /home/Jayanth.Edam/ABL/abl-platform --dangerously-bypass-approvals-and-sandbox
```

Resume continuous interactive chat by session id:

```bash
codex resume <session-id>
codex resume --last
```

Resume continuous interactive chat and send an initial prompt:

```bash
codex resume <session-id> "Continue with <task>. Preserve existing worktree changes."
```

One-shot handoff:

```bash
codex exec -C /home/Jayanth.Edam/ABL/abl-platform --ask-for-approval never --sandbox workspace-write "Investigate <task>. Return findings only. Do not edit files."
```

One-shot resume and send prompt, then exit:

```bash
codex exec resume <session-id> "Continue <task>. Return a concise status and next actions."
codex exec resume --last "Continue from the previous turn and report status."
```

One-shot dangerous handoff:

```bash
codex exec -C /home/Jayanth.Edam/ABL/abl-platform --dangerously-bypass-approvals-and-sandbox "Do <bounded task>. Preserve user changes. Report commands run."
```

## Parent Prompt Template

Use this shape when launching a worker:

```text
You are a worker session launched by another AI agent.
CWD: <absolute path>
Scope: <exact task>
Permissions: <read-only | edits allowed | no commit | commit allowed>
Constraints: Do not switch branches. Do not run git checkout. Preserve unknown changes. Do not touch unrelated files.
Verification: <commands/tests expected, or explain if not run>
Return: concise findings, changed files, commands run, blockers, and next step.
```

For `abl-platform`, append the repo agent block if the worker may edit files, especially the prettier, TypeScript, Jira-key, and no-branch-switch rules.

## Safety Defaults

- Prefer `--permission-mode auto` for Claude and `--ask-for-approval on-request --sandbox workspace-write` for Codex.
- Use no-prompt modes only when the user explicitly asks for dangerous mode or the environment is externally sandboxed.
- Avoid passing secrets in prompts or command arguments.
- Avoid long-running unsupervised edit workers on dirty worktrees; ask the worker to inspect `git status --short --branch` first.
- Prefer non-interactive `-p` or `codex exec` for research and summaries; prefer interactive/background sessions for implementation work.
