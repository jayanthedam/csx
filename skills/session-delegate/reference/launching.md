# Launching workers

## Contents
- Claude Code commands
- Codex commands
- Worker prompt template
- Budgets

Verify flags against the installed CLI when one matters: `claude --help`,
`codex --help`, `codex exec --help`, `codex resume --help`.

## Claude Code commands

```bash
# fresh interactive worker
claude --permission-mode auto --add-dir /home/Jayanth.Edam/ABL/abl-platform

# continue the most recent conversation in this directory
claude --continue

# resume a specific session
claude --resume <session-id>

# one-shot, findings back
claude -p --permission-mode auto "<bounded prompt>" > /tmp/claude-worker-<slug>.md

# one-shot with a chosen, resumable session id (this is what PREPARE uses)
claude -p --session-id <uuid> --permission-mode auto --output-format json "<prompt>"

# background worker
claude --bg --permission-mode auto "<bounded prompt>. Stop before commit and summarize."
claude agents --json          # list background agents

# no-prompt variants — only on explicit request
claude --permission-mode bypassPermissions --dangerously-skip-permissions
claude -p --permission-mode bypassPermissions --dangerously-skip-permissions "<prompt>"
```

## Codex commands

```bash
# fresh interactive worker
codex -C /home/Jayanth.Edam/ABL/abl-platform --ask-for-approval on-request --sandbox workspace-write

# resume
codex resume <session-id>
codex resume --last
codex resume <session-id> "Continue with <task>. Preserve existing worktree changes."

# one-shot, findings to a file
codex exec -C <repo> -s read-only --skip-git-repo-check -o /tmp/codex-worker-<slug>.md "<prompt>"

# one-shot resume, then exit
codex exec resume <session-id> "Continue <task>. Return status and next actions."
codex exec resume --last "Continue from the previous turn and report status."

# no-prompt variants — only on explicit request
codex -C <repo> --dangerously-bypass-approvals-and-sandbox
codex exec -C <repo> --dangerously-bypass-approvals-and-sandbox -o /tmp/out.md "<prompt>"
```

Codex prints session events with `--json`; if the id is not to hand, the newest
rollout is `csx --codex --no-pager -n 1 -f`.

## Worker prompt template

```text
You are a worker session launched by another AI agent.
CWD: <absolute path>
Scope: <exact task>
Permissions: <read-only | edits allowed | no commit | commit allowed>
Constraints: Do not switch branches. Do not run git checkout. Preserve unknown
changes. Do not touch unrelated files.
Verification: <commands/tests expected, or say why none were run>
Return: findings, changed files, commands run, blockers, next step.
```

For `abl-platform`, append the repo agent block whenever the worker may edit —
prettier, TypeScript, JIRA-key and no-branch-switch rules.

## Budgets

Always pair a budget with a durable output path:

```bash
timeout --preserve-status --signal=INT --kill-after=2m <budget> \
  codex exec -C <repo> -s read-only --skip-git-repo-check \
  -o /tmp/worker-<slug>.md "$(cat /tmp/worker-<slug>.txt)" > /tmp/worker-<slug>.log 2>&1
```

- Small read-only question: 10–20m
- Focused repo review: 30–45m
- Broad multi-repo audit: split it; if truly impossible, 60–90m with checkpoints

Do not use short hard timeouts on valuable long reviews. Only call a run stuck
when there is no progress evidence at all — see monitoring.md.
