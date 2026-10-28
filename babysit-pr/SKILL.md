---
name: babysit-pr
description: Monitor a pull request through review and CI. Use when the user asks to monitor, watch, or babysit a PR.
---

# Babysit PR

Use a read-only code-review sub-agent from the current harness for each PR
head.

## Waiting

Never write your own watcher, polling loop, or `sleep` loop. Use one watcher
per PR: the current harness's native watcher when available, otherwise
`pr-wait`. Never run both on the same PR. Watchers on a GitHub account share
one rate limit.

### Native harness watcher

Handle existing checks and comments, and ensure the latest head has a
read-only sub-agent review. Start the harness's event-driven PR watcher and
yield control; resume when it reports check failures or success, new comments or
reviews, or branch conflicts.

- **Only the thread that owns the PR watches it.** If you are a delegated
  child task (a reviewer or other delegate), never own the watcher. The parent
  owns the PR. Do not watch PRs you are not working on.
- **A wake is news, not a merge decision.** Check the merge gate yourself.
- **Unwatch when you hand off.** A watched thread stays in Working and out of
  the user's inbox. When you stop (ready, blocked, or asking the user a question),
stop the watcher through its owning harness or process first. A merge or close
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

If the current harness supports monitored command execution, give it enough
time for events to surface. Otherwise run `pr-wait` as one long command; it
exits on its own.

Start it again after you push, after you handle an exit 1, and after a resume.
It remembers what it already reported, so nothing that arrived in between is
lost. If it says another pid already watches the PR, do not start a second one.
Kill the old one only if its events do not reach you.

With either watcher: when an event needs no action, end your turn without a
message. Never post or say "still waiting".

## GitHub rate limits

`gh pr create`, `gh pr view`, and `gh pr checks` use GraphQL. When GraphQL is
used up, the REST limit is separate and usually still has room. Use
`gh api repos/<owner>/<repo>/pulls/<n>` to read a PR, and
`gh api repos/<owner>/<repo>/commits/<sha>/check-runs` for checks.

## Reviews

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

## Base branch and merging

Keep an eye on changes to `main` and rebase when needed. `pr-wait` reports when
new base commits touch this PR's files, and when the PR becomes BEHIND or DIRTY.
Some native watchers report conflicts only, so check for BEHIND yourself
before you call the PR ready.
If an overlapping PR makes this one obsolete, stop monitoring, report it to the
user, and ask before closing the PR unless closure was explicitly authorized.

If nothing has changed, stay quiet rather than posting filler comments. Stop
when `pr-wait` exits 0, or when the native watcher reports the merge gate
passes on the latest head. Merge only when the user explicitly requested it;
otherwise report that the PR is ready. Right before a merge, run `git fetch` and
check the PR again. Never merge when it is BEHIND or DIRTY, or when base commits
that landed after the last green run touch this PR's files. Rebase, push, and
wait for green again.
