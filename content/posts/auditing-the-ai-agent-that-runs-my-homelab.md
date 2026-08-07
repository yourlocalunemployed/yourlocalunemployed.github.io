---
title: "Auditing the AI Agent That Runs My Homelab"
date: 2026-08-07T18:50:00+10:00
draft: false
description: "I gave Claude Code real access to my homelab, then built an independent assurance plane around it — hash-chained evidence, a sanitised SIEM feed, and AI reviewers that can escalate but never approve."
tags: ["claude-code", "ai-agents", "observability", "security", "langfuse", "loki", "home-lab", "opentelemetry"]
series: ["Home Lab"]
seriesTitle: "An assurance plane for an infrastructure agent"
cover:
  image: "/images/posts/agent-auditor-dashboard.png"
  alt: "The agent auditor's local operator dashboard, showing observe-only mode and a list of recent Claude sessions with their recorded timelines"
  hiddenInSingle: true
---

My homelab has picked up a lot of moving parts this year, and several of them are now LLMs.
Claude Code runs natively on the box and does real work against real infrastructure —
containers, reverse proxy config, monitoring, the lot. That's genuinely useful. It also
creates a trust problem I hadn't had before.

The problem is simple to state: **the same agent that makes a change also writes the summary
explaining why the change was safe.** That's convenient. It is not independent verification.
If the agent quietly skips a validator and then reports "config validated", I have no signal
at all. The report *is* the evidence, and the thing that wrote the report is the thing being
checked.

So I built an assurance plane around it. Not to replace Claude, and not to promote a second
model to administrator — just to make the agent's actions observable, keep the evidence
somewhere the agent can't reach, and let something independent challenge claims it can't
support.

I had **Codex** build it, deliberately. The agent being audited didn't write its own auditor.

---

## What it actually is

Four independent layers of evidence, none of which the main agent controls:

1. **Managed lifecycle hooks.** Claude Code lets you run a script before and after tool use.
   These ones are installed as *managed settings* under `/etc/claude-code/managed-settings.d/`,
   which is root-owned and sits above user and project settings in the precedence order. In
   plain terms: my own `CLAUDE.md` or a project's `.claude/settings.json` cannot turn them off.
2. **Claude's native OpenTelemetry stream**, scrubbed by a pinned collector before anything
   is written to disk.
3. **An append-only, hash-chained ledger** — the durable record.
4. **Tiered model review** after a session ends, with the verdicts scored in Langfuse.

The auditor itself runs as a separate systemd service under its own `agent-audit` user, with
no Docker socket, no D-Bus, no broad home-directory writes, and no privilege escalation. It
listens on loopback only.

![Architecture diagram: Claude Code's tool calls and session lifecycle flow through root-managed hooks and a pinned OTel collector into the agent-auditor service, which writes a 0640 hash-chained JSONL ledger and a rebuildable SQLite index; a reduced 0644 projection goes to Promtail and Loki, alerts to ntfy, and a read-only dashboard on loopback. A dashed review tier — LiteLLM triage, Codex escalation, Langfuse scores — is built but switched off, and authority stays with the human operator.](/images/posts/agent-auditor-architecture.svg)

The shape of it matters more than the parts. Evidence flows *left to right, away from the
agent* — each hop puts the record somewhere the agent has less ability to touch, ending in
files it can't write and a log platform it has no credentials for. And the whole bottom row
is dashed, because it isn't switched on yet.

## The hash chain, in plain language

The ledger is a daily JSONL file — one JSON object per line, appended, never rewritten. Every
record carries the SHA-256 hash of the record before it.

That chaining is the whole point. If someone edits record 12 after the fact, its hash changes,
so record 13's stored "previous hash" no longer matches, and every record after it is now
inconsistent too. **You can't quietly change one line — you'd have to rewrite the entire rest
of the file.** A daily checkpoint anchors the chain head so a whole-file rewrite is visible as
well.

There's a SQLite index next to it that makes queries fast, but the JSONL is canonical. If the
index gets corrupted or a write is interrupted, the index gets rebuilt from the JSONL, never
the other way round.

Verifying it is one call:

```bash
curl --fail --silent http://127.0.0.1:8765/healthz
```

```json
{"mode":"observe","review_enabled":false,"langfuse_enabled":false,
 "ledger":{"records":58,"valid":true,
           "head":"9f30ccf0433e4a7a79e6d4d06d4848439fa5b9d501a10a65b5ffffaea132f4e5",
           "anchor":"0000000000000000000000000000000000000000000000000000000000000000"},
 "review_queue_depth":0,"status":"ok"}
```

`"valid":true` means the chain recomputed cleanly end to end.

## What gets recorded — and what deliberately doesn't

This is the part I spent the most thought on, because an audit log that hoovers up prompts and
command text is its own security problem. You've just built a second place for your secrets to
leak from.

So the hook client sanitises before anything leaves the session. It **hashes** command text
rather than storing it, keeps only the binary name (`docker`, not the full command line),
normalises paths, strips message content entirely, and redacts anything credential-shaped on
the way past:

```python
r"\b[A-Za-z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Za-z0-9_]*\s*=\s*\S+"
```

Then there are two files, with different permissions and different audiences:

| File | Mode | Contents |
| --- | --- | --- |
| Canonical ledger | `0640` | Full sanitised evidence, hash-chained |
| SIEM projection | `0644` | Severity, stage, outcome, policy category, hashed session refs |

Only the reduced `0644` projection goes to Promtail and into Loki, because Promtail runs
non-root inside its container and can only read what's world-readable. That constraint turned
out to be useful rather than annoying: it forces the log platform to receive the *smaller*
dataset. No prompts, no command text, no paths, no tool output, no raw session IDs.

Queries look like this:

```logql
{job="agent-auditor"}
{job="agent-auditor", risk="critical"}
{job="agent-auditor", verdict=~"POLICY_VIOLATION|UNVERIFIABLE"}
```

Session references in there are one-way hashes. I can correlate everything one session did
without the log itself telling anyone which session that was.

## Two reviewers, different jobs

Once a session ends, its events become a metadata-only review packet. Deterministic
completeness checks run **first** — before any model sees it — because "did the end-of-session
record actually arrive" is a question code can answer, and code doesn't hallucinate.

Then a cheap, capped model on my local LiteLLM gateway does first-pass triage on every
completed infrastructure session. A deeper Codex review only runs when one of these is true:

- the task was medium risk or above;
- the first reviewer failed, or returned "can't verify";
- evidence is missing;
- a deterministic policy rule fired;
- a reproducible 10% sample picks it.

That last one matters. If you only escalate the scary-looking results, you never find out what
your cheap reviewer is missing on the results that *look* fine. The sample is derived from the
session ID rather than randomised, so the same session always makes the same decision and I
can reproduce it later.

The reviewers get a deliberately tiny vocabulary:

```text
PASS  NEEDS_REVIEW  POLICY_VIOLATION  INCOMPLETE  UNVERIFIABLE
```

Note what's absent: there is no `APPROVE`. **A reviewer can only increase scrutiny.** It cannot
emit an authorisation, it cannot clear a blocked action, and it cannot override policy. Whether
a restart, a firewall change or a database migration goes ahead is decided by deterministic
rules and by me. Models are advisory, permanently — that isn't a temporary restriction while I
build confidence.

## Observe before enforcing

The first release records everything and changes nothing about how Claude's tools behave.

That's on purpose, and it's the design decision I'd defend hardest. An uncalibrated guard is
worse than no guard in both directions. False positives train you to click through warnings —
and once you're doing that reflexively, the real one goes through too. False negatives are
worse: now you have a dashboard telling you everything's fine, and you believe it.

So enforcement stays off behind explicit gates:

- at least **30 infrastructure sessions or two weeks** in observe mode, whichever is longer;
- at least **50 human-labelled packets**, balanced between "safe" and "escalate";
- a **20% test split** I don't get to look at while tuning;
- both true-positive and true-negative rate above **0.90** on that held-out split.

Fail the gate and the system stays advisory. Pass it and models are *still* advisory — only
deterministic rules ever change tool flow, returning `ask` for operations that need my approval
and `deny` only for secret material or dangerously broad destruction.

Right now it reports exactly that, and I'd rather it be honest than impressive:

```json
"notices": [
  {"level":"info","title":"Independent AI review is not active yet",
   "detail":"The observe-only pilot is collecting evidence before reviewer calibration."},
  {"level":"info","title":"Observe-only mode",
   "detail":"The auditor records policy decisions but does not change Claude's tool flow."}
]
```

## A dashboard, because LogQL is not an interface

Loki and Grafana are the forensic backend, but I didn't want "was anything weird today" to
require writing a query. So the auditor serves a small read-only console on loopback that
answers four questions in plain English: is the evidence chain healthy, is Claude active or
finished or missing an end record, which sessions need a closer look, and what happened in a
given session.

![The agent auditor's local dashboard, showing observe-only mode and recent Claude sessions with their recorded timelines](/images/posts/agent-auditor-dashboard.png)

Honest note about that screenshot: every session in it reads **0 tool actions**. Those sessions
predate the tool hooks going live, so all the auditor had was session start and end. It looked
underwhelming and it was correct — which is the behaviour I want. It reports what it recorded,
not what it assumes happened.

It fills in properly once tools are actually running. Here's the live feed while I was writing
this post:

```json
{"type":"PreToolUse","risk":"low","outcome":"decision:observe",
 "title":"Claude prepared to use Bash",
 "detail":"Command tools: cd, python3, python3, head"}
```

Binary names, no arguments, no paths. That's the session that wrote this post, being audited
while it wrote it.

I also surfaced posture on my existing Homepage dashboard, so I see it without going looking:

![A Homepage widget titled Agent Assurance showing posture "Review recommended", 3 sessions in 24 hours, and 1 needing attention](/images/posts/agent-auditor-homepage-card.png)

## Reusing what's already there

I built almost no new infrastructure for this, which was a goal rather than an accident:

- **Langfuse** groups traces and holds five session-level scores — policy compliance, evidence
  completeness, change risk, review status, reviewer agreement;
- **LiteLLM** supplies the capped first-stage reviewer through a dedicated key;
- **Loki and Grafana** handle investigation and alert rules;
- **Alertmanager and ntfy** push urgent findings to my phone;
- the existing **claim/handoff protocol** ties every session to a declared scope.

Each system answers a different question, and keeping them separate is what keeps them honest.
Langfuse tells me how the reasoning pipeline behaved. Loki tells me what event happened and
when. The hash chain tells me whether the stored sequence still matches what was originally
written. None of those three can quietly cover for another.

## What this does not solve

Worth being blunt, because a security control you've oversold is a liability:

**Shared identity is the real hole.** The main Claude process and the hook process run as the
same login user. The hardened service stops ordinary agent behaviour from editing stored
history, but a fully compromised login could fabricate additional loopback events. Genuinely
fixing that means running the agent under its own OS identity, or collecting below the user
boundary. This is protection against mistakes, missing evidence, ordinary policy bypass and
overconfident reporting — not against a compromised account.

**A checkpoint is not a timestamp.** Daily checkpoints are tamper-*evidence* anchored on my own
machine. They are not third-party attestation. Someone with root and patience can rewrite the
lot.

**The judge is not automatically right.** A second model being *different* doesn't make it
correct. Its judgements need human labels, held-out evaluation, disagreement review, cost
monitoring and periodic recalibration. That's why the review pipeline is built but switched
off — `"review_enabled": false` in the health output above is the current, accurate state, not
an oversight.

## The bit that changed how I work

The most useful shift wasn't technical. It was starting to treat agent output as a **claim**
rather than as **evidence**.

A completion report saying "I validated the configuration" is a claim. The assurance plane asks
the follow-up questions: did a validator actually run, was the result recorded, did the work
stay inside the scope it declared, and can an independent reviewer trace that conclusion back
to recorded facts?

That's a modest goal. It also changes the relationship. The agent can still move fast — I
haven't slowed it down at all, since observe mode doesn't touch its tool flow. But I can now
see what happened, challenge what can't be proven, and keep the authority for consequential
changes where it belongs, which is with me.

Next step is the boring one: two weeks of observe mode, then sitting down and hand-labelling
fifty sessions so the reviewer has something real to be measured against.
