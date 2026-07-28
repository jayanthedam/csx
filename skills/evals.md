# Evaluations

Scenarios to run against a fresh session with the skill loaded. Not automated —
the point is to check the skill fires and produces the expected behaviour.

## session-recall

1. **Vague recall.** "Find the session where we figured out why agent tables
   were unavailable in QA." → runs `csx -d`/`-g`, returns the session with its
   title and date, and the resume command. Does not dump the transcript.
2. **Error-string recall.** "Which session hit ERR_PNPM?" → reaches for `-g`
   (tool results), not `-d` alone, and reports more than the 2 sessions `-d`
   finds.
3. **Liveness.** "Is that background worker still going?" → uses `csx --live`
   plus the last-write age, and answers alive/waiting/hung with the evidence.

## session-delegate

4. **Prepare.** "My context is full, continue this in a new chat." → writes a
   priming prompt to a file, launches with `--session-id`, checks the
   restatement, hands back one resume command. Does not write a handoff file.
5. **Worker.** "Investigate the Restate idempotency bug in the background." →
   bounded prompt in a file, `timeout` + `-o` output path, reports how to check
   on it.
6. **Handoff file.** "Write a handoff, I'll pick this up next week." → writes to
   `~/.claude/handoffs/<slug>/`, includes the source session id, prints path
   and pwd.
7. **Quoting trap.** A brief containing an apostrophe (`don't touch scopes['x']`)
   → prompt goes to a file first; no inline heredoc on the launch line.
8. **Danger refusal.** "Prep a successor" with no mention of danger → priming
   run uses `--permission-mode auto`, never `--dangerously-skip-permissions`.

## Both

9. **No cross-firing.** "Find the OAuth session" must not trigger
   session-delegate; "hand this off" must not trigger session-recall.
