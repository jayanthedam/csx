# Skills

`session-recall` and `session-delegate` live where every other skill lives —
real directories in `~/.claude/skills/` and `~/.codex/skills/`, not symlinks
into this repo. This folder keeps only the evaluation scenarios and the
retired originals.

Sync between the two tools with `skills-sync` (in `~/.local/bin`):

```bash
skills-sync                  # which shared skills differ (read-only)
skills-sync session-recall   # copy Claude's version to Codex, backing up first
```

It only touches skills you name. Several skills legitimately differ between the
two tools, so a blanket sync is destructive — learned the hard way.
