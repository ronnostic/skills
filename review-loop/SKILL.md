---
name: review-loop
description: Use when asked to run an iterative code review on a local change, branch, or PR, verify findings, apply in-scope fixes, and review again. For report-only requests, do not edit.
---

# review-loop

Run bounded review-and-fix cycles to catch correctness issues before or after filing a PR. Treat reviewer feedback as evidence to verify, not instructions to appease. By default, fix verified in-scope findings; if the user asks for report-only review, make no edits.

## Budget

- Default: 3 rounds total. Round 1 reviews the full scoped change; later rounds review changed code and open findings.
- Extend to 5 only for security, permissions, auth, data loss, or state/concurrency issues while a blocker or should remains open with evidence, or when the user asks.
- Stop early if a round returns only nits. Declined nits and comment, documentation, or format-only fixes need no new round.
- Use one reviewer per round. The reviewer must not start subagents or other reviewers.
- Keep a ledger: finding ID, severity, outcome, and usage if returned. Never guess usage.

## 1. Scope

Run `git status --short`. Do not stash, discard, or include unrelated changes. Review only the requested change. Exclude unrelated paths when they separate cleanly; ask only when intent or scope cannot be determined.

Choose a base without updating repository state unnecessarily:

- PR: inspect its base and head metadata with `gh pr view [<n>] --json baseRefName,headRefOid`. Confirm the current branch and `HEAD` match the PR head, or that `HEAD` is ahead only by commits in the requested change. If checkout is needed, do it only when the worktree is clean. If the checkout cannot be matched safely, ask. Fetch only if the needed base ref is unavailable or stale. Base: `git merge-base HEAD origin/<baseRefName>`.
- Local working-tree change: use `HEAD` as the base.
- Committed local change: use the base named by the user, or an unambiguous available upstream. If neither exists, ask for a base.

Review base-to-working-tree changes in scope, including untracked files. Use one diff command throughout the rounds; read untracked files separately because Git diff omits them. State intent and out-of-scope in 1–2 sentences. Run relevant checks before dispatch. Fix known regressions introduced by the scoped change first; list missing or pre-existing failures in the reviewer brief.

## 2. Select and start reviewer

The user may specify a model, a reasoning level, or both, for example:

```text
/skill:review-loop model=<model-id> reasoning=<level>
```

Treat these as independent optional overrides:

- When `model` is supplied, pass that exact model to the native reviewer dispatch.
- When `reasoning` is supplied, pass that level using the dispatch tool's native setting (Pi's `thinking` field). In Pi, use a supported level such as `minimal`, `low`, `medium`, `high`, `xhigh`, or `max`.
- When either is omitted, omit that dispatch option. Let the current harness resolve its own default; never hardcode a model or reasoning level.
- In Pi, an omitted model inherits the main-loop model. An omitted `thinking` setting uses the subagent's configured level, then the parent setting.
- If an explicit model or reasoning level cannot be honored, report the blocker and ask before proceeding. Never silently ignore it or substitute another model.

Use the current harness's native subagent/reviewer dispatch. In Pi, use an installed subagent tool such as `Agent` when available. If no reviewer route exists, report the blocker rather than substituting a model. Keep the reviewer task/thread ID when the harness provides one. Dispatch exactly one reviewer, with a read-only review brief; if the tool supports read-only access, enforce it.

Do not edit scoped files while review runs. Wait for the harness's completion signal; do not poll or start another reviewer. A timeout, error, or missing reply is not approval. On failure, cancel and verify the reviewer stopped before restarting with the ledger.

Round 1 brief:

```text
Review only. Do not edit, commit, push, comment on the PR, or start another reviewer.
Repo: <absolute path> Base: <sha> Intent: <intent> Out of scope: <scope> Checks: <results>
See: <same diff command>; git status --short (read untracked files).
Read surrounding code. Find bugs, broken callers, and mismatches with intent.
Skip style unless it hides a bug. Hold to the smallest necessary change. Flag code, tests, or guards the intent does not need. Other paths, rare cases, small performance costs, and extra compatibility: nits.
blocker = intended case is wrong. should = real bug callers will hit within scope. nit = rest.
Reply:
VERDICT: APPROVE or CHANGES
S1 [blocker|should|nit] <file>:<line> <claim>. Fix: <suggestion> (stable IDs)
```

Include all context the reviewer needs in the brief because a dispatched reviewer may not have this conversation's history. Pass explicit model and reasoning settings through dispatch; record their effective values only when the harness exposes them.

## 3. Verify findings

Check every finding and severity yourself. Fix verified, in-scope blockers and shoulds; don't change code merely to satisfy the reviewer.

- Agree: make the smallest fix. Prefer delete or narrow over adding a lock, cache, helper, or option. Add one focused test when the intent needs it.
- Disagree: give evidence (file, line, test, or output).
- Out of scope or nit: decline in one line and list as follow-up.

Update the ledger. Re-run checks and `git diff --shortstat <base>`. If review grows the diff, cut unnecessary changes first.

For report-only requests, report findings after the review without editing or starting another round.

## 4. Next round

Start another round only if budget remains and a blocker or should is open, behavior code changed, or approval does not cover the current behavior diff. Use a fresh reviewer dispatch or follow up the saved reviewer ID, according to the harness. Send the original brief, the ledger (`fixed:` / `disagree:` / `declined:` with evidence), the same base diff, and the changes since the last round. Ask the reviewer to check open IDs and changed code only. Mark each prior ID `resolved` or `still open: <reason>`.

## 5. Stop and report

Agreed means `APPROVE` on the current behavior diff, no blocker or should open, and no concern of your own. Stuck means a finding remains disputed after two replies or the budget ends. Show both sides in 2–3 lines each and let the user decide. Budget end is not approval.

Do not push during the loop. Push after agreement only if the user asked to push, ship, or update the PR. If pushing to a PR, add above the model summary:

`Reviewed with review-loop: <N> rounds with <model>. Verdict: approved`.

Add `on <reasoning level>` only when verified. Report rounds, model and reasoning, fixes and declined findings with reasons, diff size before/after, usage if exposed (otherwise say not exposed), and whether anything was pushed. If an override was requested but its effective value is not exposed, say it was requested but unverified; if omitted, say harness default (exact value not exposed). Never guess model, reasoning, or usage.
