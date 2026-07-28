# Is the worker alive, waiting, or hung?

## Contents
- Fast check
- Evidence to gather
- Verdict rules
- Stuck-launch signature

Do not judge by elapsed time. Gather evidence, then state which evidence you
checked.

## Fast check

```bash
csx --live --no-pager        # sessions with a live process, newest write first
```

`csx` resolves live sessions from Claude Code's pid registry plus `/proc`
command lines, which is more reliable than grepping `ps`. The `msgs` count and
the age column tell you whether the transcript is still growing.

## Evidence to gather

```bash
# process state
ps -o pid,ppid,stat,etime,pcpu,pmem,wchan:30,cmd -u "$USER" | rg 'codex|claude|PID'

# output file growth
ls -l /tmp/<slug>.md /tmp/<slug>.log 2>/dev/null

# transcript movement, if csx is unavailable
find ~/.codex/sessions ~/.claude/projects -name '*.jsonl' -mmin -35 -printf '%TH:%TM %p\n' | sort
```

Process state codes: `R` running · `S`/`I` sleeping (normal for a chat UI
waiting on network or input) · `T` stopped · `Z` zombie · `D` uninterruptible IO.

## Verdict rules

- **Alive and working** — process exists, transcript or output file growing, CPU
  or a live child command.
- **Alive but waiting** — process exists, no recent writes, low CPU, and the
  TTY is sitting at a prompt or approval.
- **Hung** — long ETIME, no transcript change, no output growth, no child
  progress, and no visible movement.
- **Not running** — no matching process and no recent transcript writes.

Report the evidence, not just the verdict: "process exists, but no transcript
write in 30 minutes and CPU is 0.0, so it is alive and not doing useful work."

Never kill a worker that has recent output, transcript movement, CPU, or a live
child command.

## Stuck-launch signature

A worker blocked in `ep_poll`, `futex_do_wait` or `unix_stream_data_wait` with
`0.0` CPU and a ~39-byte log saying `Reading additional input from stdin...`
never received its prompt. That is the quoting failure, not a hang — kill by
PID and relaunch from a prompt file.
