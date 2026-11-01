---
name: babysit-pr
description: Monitor a pull request through review and CI. Use when the user asks to monitor, watch, or babysit a PR.
---

# Babysit PR

Use a read-only code-review sub-agent from the current harness for each PR
head.

## Waiting

Never write your own watcher, polling loop, or `sleep` loop. Use one watcher
per PR: the current harness's native watcher when available; otherwise use
`pr-wait` only when the compatibility checks below pass. Never run both on the
same PR. If neither watcher is compatible, report a monitoring blocker and do
not claim readiness. Watchers on a GitHub account share one rate limit.

### Native harness watcher

Handle existing checks and comments, and ensure the latest head has a
read-only sub-agent review. Start the harness's event-driven PR watcher and
resume when it reports check failures or success, new comments or reviews, or
branch conflicts. In full-send, keep it active after review approval through all
required checks and subsequent review/head events; green or ready alone is not
a stopping point. Re-review any new head and continue watching until merge or a
genuine blocker.

- **Only the thread that owns the PR watches it.** If you are a delegated
  child task (a reviewer or other delegate), never own the watcher. The parent
  owns the PR. Do not watch PRs you are not working on.
- **A wake is news, not a merge decision.** Check the merge gate yourself.
- **Unwatch before handoff.** A watched thread stays in Working and out of the
  user's inbox. In full-send, stop only after merge or a genuine blocker; stop
  through its owning harness or process before handing off. A merge or close
  ends the watch on its own.
- **"Stopped watching, could not read it"** usually means GitHub's rate limit
  is used up. Run `gh api rate_limit --jq .resources.graphql` before you
  watch again. If `remaining` is near 0, wait for `reset` with one background
  command, then watch again. Never watch again in a tight loop.

### Fallback: `pr-wait`

Wait with `scripts/pr-wait` from this skill's directory (use its absolute
path).

```bash
pr-wait <pr> [--repo owner/name] [--until ready|green|any-change]
```

It prints one line per real event. It exits 0 when the `--until` condition is
met or the PR merges, 1 when it needs you (a required check failed, conflicts,
unresolved threads, PR closed), and 2 on bad input.

- `ready` (default): checks green, no unresolved threads, and branch not
  BEHIND. The calling skill must also ensure the latest head has a current-harness
  sub-agent review.
- `green`: checks only. Use it when you need check status without review or
  thread readiness.
- `any-change`: exit on the first event.

For full-send, run `pr-wait <pr> --until any-change` and re-arm it after each
event; `ready` and `green` only cover checks/thread readiness and are not merge
completion. If the current harness supports monitored command execution, keep
it active long enough for events to surface. Otherwise run `pr-wait` as one long
command; it exits on its own.

Re-arm after each handled event, push, exit 1, or resume. It remembers what it
already reported, so events between runs are not lost. If it says another pid
already watches the PR, do not start a second one. Kill the old one only if its
events do not reach you.

When an event needs no action, keep the watcher active and await its next event;
do not end the task or send a final/status message while a required gate or
review event remains pending. Never post or say "still waiting".

## Check status and GitHub CLI compatibility

Check `gh pr checks --help` before choosing flags. Use supported text output
from `gh pr checks <pr> --required` (or `--required --watch` for checks only);
do not assume `--json` exists. The bundled `pr-wait` currently requests
`gh pr checks --json` and reads branch-protection/ruleset endpoints. If `--json`
is unsupported or those endpoints return 403, its required-check result is
unverified: 403 means unknown, not “no required checks.” Use the supported CLI
command to inspect required check statuses, but if that command fails, returns
no required checks while requirements remain unknown, or required-check
configuration cannot be verified, report checks as unverified and do not merge
or call the PR ready. `gh pr checks --watch` monitors checks only; keep a
compatible event-driven PR watcher for new reviews/comments and head changes.
If no compatible PR event watcher is available, report a blocker and leave the PR
open.

## Reviews

Keep a separate result for each reviewer run: run ID, role, exact PR head SHA,
status, and output. Persist completed reviewer results independently so one
failed reviewer cannot discard successful findings. Killed, missing, or unusable
reviewers are UNKNOWN, never approval. Retry only failed reviewers once, with
the same role and scope, after verifying the worktree is unchanged; if retry
fails, report successful findings and failed run IDs/errors as blocked.

Declare review complete only when every reviewer result and required-check
configuration is known for the exact current PR head, required checks pass, and
there are no conflicts, BEHIND state, or unresolved threads. A head change
invalidates prior review and check results; review the new head before readiness.
This workflow never merges or enables auto-merge.

Only act on checks, comments, and sub-agent findings for the latest head. Verify
every finding against the source before changing code. Fix real findings and CI
failures, distinguish repository failures from infrastructure flakes, and reply
with a written reason when dismissing false positives.

Before waiting, ensure the latest PR head has a read-only code review from a
sub-agent in the current harness; run one if it has not already been reviewed.
Repeat after each new head and verify findings against the source before changing
code. The watcher does not run or wait for this review.

If a PR review thread raises a finding you decide not to address, reply with a
written reason and resolve the comment. Use the `leaving-pr-comments` skill for
every comment posted on the user's behalf.

Screenshots and videos help as well, when you have a way to upload them.

Keep the PR at the size the user's goal needs. Review loops tend to grow a
PR one cheap-looking fix at a time. Fix real bugs in the intended case.
Decline the rest with a written reason, and list them as follow-ups:
unneeded tests, guards for edge cases that do not matter, extra integration
or compatibility, and small performance costs. Prefer the fix that deletes or
narrows code.

## Base branch

Keep an eye on changes to `main` and rebase when needed. `pr-wait` reports when
new base commits touch this PR's files, and when the PR becomes BEHIND or DIRTY.
Some native watchers report conflicts only, so check for BEHIND yourself
before you call the PR ready.
If an overlapping PR makes this one obsolete, stop monitoring, report it to the
user, and ask before closing the PR unless closure was explicitly authorized.

If nothing has changed, stay quiet rather than posting filler comments. In
full-send, a green/ready result is not terminal: keep watching through review
events and stop only after a merge performed outside this workflow or a genuine
blocker. After every requested gate is verified, report readiness; never merge
or enable auto-merge from this workflow.
