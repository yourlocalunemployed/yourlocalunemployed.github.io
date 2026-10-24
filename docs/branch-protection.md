# Branch protection for `main`

**Status: proposed, not enabled.** `main` has no ruleset and no classic branch
protection as of 2026-10-21 (`gh api .../branches/main` reports `protected:
false`; `.../rulesets` returns an empty list).

## Why

"No agent merges to `main`" is written in `docs/blog-agent-handoff.md` and on
`/ai/`, and today it is an instruction, not a lock. Every token that can push
to this repository can push to `main`, and the leak gate that runs on every
branch is advisory on `main`: a red run there blocks nothing.

A ruleset turns the rule into a lock. It is the one outstanding item from both
the 2026-10-04 and 2026-10-21 audits.

## The fact that shapes the design

The homelab agent pushes with a fine-grained PAT on Bill's own account, so to
GitHub its pushes **are Bill's**. The repo agent pushes through the Claude
GitHub App, which is a separate identity. A bypass for "repository admin" would
therefore exempt the homelab agent along with Bill. There is no setting that
blocks the homelab agent while leaving Bill's direct pushes alone, short of a
separate machine account for the agent.

So the lock has to apply to everyone: **every change to `main` arrives by
pull request, and Bill merges it in the UI.** That is already how the last
fortnight's work landed, but it is a change of habit. Of the last 30 commits on
`main`'s first-parent line, 12 were direct pushes.

## The ruleset

One branch ruleset, targeting the default branch, enforcement active, with an
empty bypass list.

| Rule | Setting | Why |
| :-- | :-- | :-- |
| Restrict deletions | on | `main` cannot be deleted |
| Block force pushes | on | history on `main` stays append-only; the audit trail of who merged what survives |
| Require a pull request before merging | on, **0 required approvals** | the PR is the gate. Approvals are set to 0 because this is a one-person repository and GitHub does not let a PR's author approve it; requiring 1 would block every merge |
| Require status checks to pass | on, required check: **`scan for leaks`** (posted by GitHub Actions) | the leak gate must be green on the PR's head before the merge button works. "Require branches to be up to date" off: it would demand a base merge before every merge for no safety gain here |

Not required on purpose:

- **Cloudflare Pages** (`cloudflare-workers-and-pages`). It is a preview build,
  it runs after the push, and a transient Cloudflare failure should not freeze
  publishing. The production build happens after the merge anyway.
- **CodeQL** (`Analyze (...)`). Useful, slow, and not this repository's threat
  model. Add it later if wanted; it will show up in the same check list.

The check name is the job's `name:` in `.github/workflows/leak-gate.yml`
(`scan for leaks`), confirmed against the check runs on `main`'s head. If the
job is renamed the ruleset must be updated or every merge blocks.

## How to enable it

Either path produces the same ruleset. The API path is deterministic and
reviewable; the UI path is what most people reach for.

### API

```bash
gh api -X POST repos/yourlocalunemployed/yourlocalunemployed.github.io/rulesets \
  --input - <<'JSON'
{
  "name": "main: pull request + leak gate",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false
      } },
    { "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": false,
        "required_status_checks": [
          { "context": "scan for leaks", "integration_id": 15368 }
        ]
      } }
  ]
}
JSON
```

`integration_id` 15368 is GitHub Actions, read off this repository's check runs.
A wrong field name fails with a 422 and creates nothing; it cannot silently
create a weaker rule.

### UI

Settings → Rules → Rulesets → New ruleset → New branch ruleset. Target the
default branch, set enforcement to Active, leave the bypass list empty, and
switch on the four rules in the table above. The GitHub docs host was not
reachable from the session that wrote this, so the exact labels were not checked
against the documentation; the table describes the settings, not their wording.

## What changes for Bill

- `git push origin main` is refused. The publish flow in `CLAUDE.md` ("after a
  post is approved, publishing is just a push") becomes: push a branch, open a
  PR, merge it. **Update that section of `CLAUDE.md` when this is enabled**, or
  the next session will follow a flow that no longer works.
- A PR whose leak gate is red cannot be merged, by anyone, until it is green.
- Nothing else changes. Branches, drafts, the handoff flow and the Claude App's
  PRs all work as before.

## What it does not do

- It does not make a leak un-public. A leak on any pushed branch is still
  public the moment it lands; the ruleset only keeps it off `main`.
- It does not see pixels or history. The gate's known gaps are unchanged.
- It does not stop Bill merging a red PR by first disabling the ruleset. An
  admin can always do that; the point is that it becomes a deliberate act that
  leaves an audit-log entry, rather than a `git push`.

## Verifying it took

After enabling, both of these must fail:

```bash
# 1. a direct push to main is refused
git checkout main && git commit --allow-empty -m "protection check" && git push origin main
# expected: remote rejects the push, citing the ruleset. Then drop the commit:
git reset --hard origin/main
```

```text
2. a PR with a red leak gate shows "Merging is blocked" and the merge button
   is disabled. tests/leak-gate/ has planted-leak fixtures to make a branch
   red on purpose; do not push a real address to prove it.
```

If either succeeds, the ruleset is not active or has a bypass.
