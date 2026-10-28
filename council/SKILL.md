---
name: council
description: Trigger this if the user says 'council'.
---

# Council

Bring in three delegates to help with the user's request, usually for review
or feedback. Use one strong model from each of three different providers, at
high reasoning effort. If the user's instructions name council members, use
those. Otherwise choose each provider's latest available flagship model. Avoid
model-name examples here because availability changes.

Use the current harness's native model-selection and sub-agent tools to start
one delegate per provider in parallel. If distinct-provider selection is
unavailable, or a named member cannot be reached, report that limitation rather
than substituting.

Give each delegate the request and relevant context. For review or feedback,
keep their work read-only. Collect their responses and summarize the useful
findings, disagreements, and recommended next steps.

For a code review, ask each delegate for a score out of 10.
Count each full review pass as one round.
A fresh review after fixes starts a new round.

If the work ends in a pull request, put the results in the PR description.
Put this section before the model and harness line at the end:

```markdown
## Council review

Rounds: <N>

| Delegate | Round 1 | Round 2 |
| --- | --- | --- |
| Delegate 1 | [score]/10 | [score]/10 |
| Delegate 2 | [score]/10 | [score]/10 |
| Delegate 3 | [score]/10 | [score]/10 |
```

If a delegate gives no score, write `no score`. Do not invent one.
If the PR is open, edit the description. Do not post a comment for this.
If there is no PR, put the same results in the final reply only.

If you agree with their recommendations, make the changes and request a fresh
review after. Continue this process until all delegates are satisfied with the
outcome.

Do not let repeated reviews result in scope creep. It is your job to fight to
keep scope limited.
