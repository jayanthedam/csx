# Retired skills

Superseded by `session-recall` and `session-delegate`. Kept only so the
originals are recoverable — nothing loads them from here.

- `ai-session-orchestrator/` — launching, monitoring and resuming workers. Its
  content lives on in `session-delegate/` (reference/launching.md,
  reference/monitoring.md), minus the `rg` session hunting and `ps`+`find`
  health checks, which `csx --live` does better.
- `session-handoff/` — handoff file write/resume. Now
  `session-delegate/reference/handoff-file.md`, demoted from default to
  fallback: priming a successor session verifies understanding, a file cannot.

`ai-session-orchestrator/agents/openai.yaml` was a Codex interface stub
(display name, one-line description, default prompt). The new skills rely on
frontmatter alone, which both tools read.

To resurrect one: `cp -r <dir> ~/.claude/skills/` (and/or `~/.codex/skills/`).
