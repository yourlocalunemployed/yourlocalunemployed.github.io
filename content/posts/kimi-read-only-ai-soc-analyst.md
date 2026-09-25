---
title: "Integrating Kimi as a read-only AI security analyst for my homelab SOC"
date: 2026-09-08T21:45:00+10:00
draft: false
description: "My SOC caught things but couldn't think. Kimi sits above it read-only — two services split by what each may reach, and a guardrail that was completely inert."
tags: ["home-lab", "security", "ai", "siem", "kimi", "systemd", "detection-engineering", "claude-code"]
series: ["Detection Engineering"]
seriesTitle: "An AI analyst on the SOC"
---

With the new SOC structure and dashboard built, I decided to take on a bigger project: integrating Kimi as a security AI analyst. Its role covers reporting on alerts, examining logs, judging whether something is a false positive, and auditing continuously. It is built in phases, and each phase needs extensive validation before the next one starts.

## The problem

The SOC we built catches things. Seven log sources into Loki, 36 detection
rules, alerts routed to my phone by severity, one Grafana dashboard over all of
it.

What it does not do is *think*. Every alert still meant me opening Grafana,
picking a time window, writing a LogQL query, and deciding whether it mattered.
The detection was automated. The investigation was not.

So: put Kimi above the SOC as a first-line analyst. It reads the evidence,
correlates it, assigns a severity and a confidence, and recommends what to look
at next. It never fixes anything. Deciding what happens is still my job.

## How this was built, and by whom

The working model matters to the story, so it goes up front rather than in a
footnote.

I run this lab as an AI-assisted workflow. My job is designing the workflow,
deciding what gets built and what does not, approving each phase, typing every
root command myself, and doing the analysis of whether a result is actually
believable. **Claude Code** did the implementation — the collector, the
sanitiser, the systemd units, the tests, the documentation — and most of the
diagnosis. **Kimi** is both the subject and, separately, the independent
auditor: the analyst that reads alerts, and the read-only reviewer that audited
Claude's work afterwards. **Codex** holds the integrity manifests that stop any
agent re-blessing its own policy files.

I did not write the code in this post and I am not going to imply otherwise.
What I did was set the constraints, refuse the shortcuts, insist on evidence
for each claim, and catch things on screen that the agent had convinced itself
were fine — including two of the defects below.

That division is also the security model, not just a disclosure. No agent
reviews its own change: the one that builds cannot audit, the one that audits
cannot remediate, and neither can approve. That stays with me.

## The rule that shaped everything

Not this:

    logs -> LLM -> decision

But this:

    telemetry -> deterministic detection -> alert
              -> bounded evidence collection -> sanitisation
              -> Kimi analysis -> human decision

Detection stays deterministic. The model interprets; it does not detect, and it
does not act. Everything below follows from that one ordering.

## The phases

**Phase 0 — look before touching.** No changes at all. Read the existing SOC,
Kimi's controls, the audit plane, and find out what is actually true rather
than what the docs claim.

Three findings changed the design before a line was written:

- Loki and Alertmanager listen on `127.0.0.1` only. The n8n container I had
  planned to orchestrate with **cannot reach either of them**. So the analyst
  became a host-native service instead.
- The Kimi CLI wrapper hard-refuses `-p`, `--prompt`, `--auto` and `--yolo`,
  and always forces plan mode. There is no headless mode, by design. So
  automation through the wrapper was impossible without weakening a control —
  and weakening it was not on the table.
- LiteLLM, the lab's AI gateway, serves twelve models and none of them is Kimi.

**Phase 1 — build the deterministic half first.** Collect evidence, sanitise
it, and stop. No model involved. This meant I could inspect exactly what would
be sent before anything was ever sent.

**Phase 2 — the model call.** Text in, text out, no tools.

**Phase 3 — commission it.** Install, prove the guardrails hold, run it against
a real alert.

## The design decision I would defend hardest

The analyst is two systemd units, not one, split by what each is allowed to
reach:

| Unit | Can reach | Cannot reach |
| --- | --- | --- |
| collect | loopback only | internet, LAN, firewall, containers |
| analyse | the model API | Loki, Alertmanager, Prometheus, LAN |

The component that reads all the telemetry has no route off the machine. The
component that talks to a third party cannot read a single log line. A file on
disk between them is the only channel. Neither half can do the whole job, so
exfiltration means defeating two kernel-enforced controls rather than one
policy written in a comment.

The second control is that **the model gets no tools at all**. Not "tools it is
told not to use" — no tool interface exists. Every forbidden action becomes
structurally impossible rather than policy-enforced. There is nothing to
bypass, because there is nothing there.

## The guardrails that failed their own tests

This is the part worth reading.

Claude wrote the egress rules and documented them as kernel-enforced. I asked
for them to be tested with both a negative control (must fail) and a positive
control (must succeed) before I would accept the claim. The positive controls are the important half: a test that fails for
the wrong reason looks exactly like a test that passed.

The analyser reached Loki and Alertmanager anyway. `HTTP 200`, twice.

**`IPAddressAllow=any` silently neutralises every `IPAddressDeny` in the same
unit.** The entire deny list was inert. It had been inert since it was written, it
looked correct in the file, and the one test that appeared to pass — "the model
API is reachable" — passed *because* the rules were doing nothing.

Fixing it surfaced a second defect. The deny list included the tailnet CGNAT
range. DNS on this host resolves through Tailscale's MagicDNS, whose resolver sits
inside that very range. Had the rules ever actually worked, the analyst would never have
resolved the API at all. One bug was hiding the other.

The corrected policy blocks loopback at the *interface* level and denies RFC1918
directly. Re-tested: Loki `000`, Alertmanager `000`, Prometheus `000`, firewall
`000`, model API `401` — reachable, unauthenticated. Six assertions, both
directions.

## Two more found by running it

The first live call failed with `HTTP 400`. The error handler returned exactly
that and threw the API's explanation away, which cost a diagnostic round trip.
Probing with a minimal request isolated it: `kimi-k2.7-code` accepts no
temperature except `1`, and the request was sending `0.2`.

Fixed, and it failed again — this time a timeout. It is a reasoning model, and
the call took 77 seconds against a 120-second ceiling. Both defects were real,
neither was visible from reading the code, and the minimal probe that found the
first could not have found the second because it was too small to be slow.

The retry logic earned its place here. Both failures preserved the evidence for
another attempt rather than discarding it, which is a behaviour corrected
mid-build once we realised a transient outage would otherwise lose an
incident permanently.

![The SOC Analyst (Kimi) dashboard. Top row: reports produced 4, analyses failed 2, gave up 0, integrity warnings 0. Below it an Assurance row reading automatic actions performed 0, distinct incidents analysed 4, and one model in use](/images/posts/kimi-read-only-ai-soc-analyst/dashboard-overview.png)

Both of those failures are still on the board. `Analyses failed (24h): 2` is
the rejected temperature and the timeout, and I would rather it stayed visible
than be quietly cropped out — `Gave up: 0` next to it is the retry logic
reporting that neither one lost an incident.

The panel I actually care about is on the second row. `Automatic actions
performed` is not a count of things that went well. It is a constant, rendered
from a field the model cannot write to, and if it is ever not zero the design
has failed rather than the run.

## What it actually said

First real report, on a `critical` alert about a container fatal error:

**LOW severity. 95% confidence.**

It read the traceback, saw it came from an authentication handler, saw the HTTP
401 that followed, and concluded the exception had been *caught*. It checked
the container metrics: zero unhealthy, twenty-eight running, unchanged across
the whole window. Then it said the quiet part:

> The rule-labeled 'critical' severity reflects a broad regex match on a handled
> Python traceback, not a genuine service-impacting event. The main risk is
> alert fatigue.

It was right. That rule matches any traceback, including handled ones.

The reports need no new delivery mechanism. They are JSONL on disk, picked up
by the Promtail job that already ships eight other sources, and they surface as
a third dashboard beside the two that were already there.

![The Grafana Homelab folder listing three dashboards: Homelab Security Overview, pfSense Security, and SOC Analyst (Kimi), the last tagged ai, security, siem and soc-analyst](/images/posts/kimi-read-only-ai-soc-analyst/grafana-folder.png)

![The lower half of the analyst dashboard. A panel holding the full report text including its Data Unavailable, Historical Context, Risk Assessment and Recommended Investigation sections, above an audit trail of records showing actions performed NONE, hashed incident and run references, and idle heartbeats](/images/posts/kimi-read-only-ai-soc-analyst/dashboard-reports.png)

The audit trail underneath is deliberately dull: no evidence, no prompts, no
report prose, no addresses. Timestamps, stage, status, hashed references, and
`"actions_performed": "NONE"`. The `idle` records are there because a system
that only writes on findings cannot be told apart from one that has died.

It also flagged something under *suspicious content*: one of our own alert
annotations contained an embedded shell command. Not an attack — it is our
annotation —
but the instinct was correct, and it made me notice we had been shipping
executable text into an LLM prompt out of habit.

Severity and confidence are deliberately separate. A serious event with thin
evidence should be high severity and low confidence. The conflicting-evidence
test was meant to prove that, and it is the one result in this project that
came out worse the second time.

The first run returned MEDIUM at 50% and reported the contradiction instead of
resolving it, which is exactly what I wanted. Then I read the fixture properly.
It contained a note saying the evidence was *deliberately contradictory*, and
the model had quoted it back under suspicious content. I had handed it the
answer and then graded it for knowing it.

So I rebuilt the fixture without the tell and ran it blind. Logs showing a
container panic and fatal exit, metrics showing zero unhealthy containers
across the same window, and nothing anywhere saying the two disagreed on
purpose.

It came back **LOW at 90%**. It *noticed* the discrepancy — the report lists
the flat unhealthy metric and reasons that it is "consistent with either the
container not being marked unhealthy by the Docker health check or the restart
happening faster than the scrape/health-check interval". But it filed that
under correlated evidence as a reconciliation, not under conflict, and its
confidence never moved.

That is the honest result. Told the sources conflicted, it reported a conflict.
Left to find one, it explained it away and stayed confident. The earlier
version of this post said it "reports conflicts rather than resolving them",
and blind evidence does not support that claim, so it is gone.

It is also the clearest argument for why this thing does not get to act on its
own conclusions. A 90% confidence that survived contact with contradicting
telemetry is precisely the output you would not want wired to a firewall.

## What it cannot do

It has no shell, no filesystem, no tools, no ability to restart, block, disable
or change anything. The line "Automatic Actions Performed: NONE" at the bottom
of every report is written by the reporting code, not by the model — which has no field
it can use to claim otherwise, and any it invents is discarded.

It can still be *wrong*, and nothing here prevents that. The controls guarantee
it cannot act and cannot leak. They do not guarantee it is right. One good
report on a benign alert is not evidence it reasons well about a real intrusion.

## Rollback, actually executed

We disabled the timers and restored the one changed config file from backup —
I ran the privileged half of that myself — then checked: `promtail-config.yml` byte-identical to its pre-project state,
detection rules never touched, twenty-eight containers, zero alerts, all eight
original log sources still ingesting. Then I put it back.

A documented rollback that has never been run is the same category of thing as
a detection rule that has never fired. It looks like safety, and you find out
whether it is when you can least afford to.
