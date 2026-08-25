---
title: "The Council Gets a Front Door"
date: 2026-08-23T18:34:16+10:00
draft: false
description: "A web dashboard for the multi-agent council — and the six bugs I only found because I finally had to use the thing."
tags: ["homelab", "ai", "claude", "codex", "kimi", "python", "systemd", "security"]
series: ["Home Lab"]
seriesTitle: "Giving the council a dashboard, and finding out what I'd built"
cover:
  image: "/images/posts/council-dashboard-run.png"
  alt: "The council dashboard showing a run's pipeline, all stages passed through the approval gate"
---

The [council](/posts/three-agents-one-approval-gate/) worked. One request went to
Claude, Codex and Kimi, they answered independently, and nothing touched the lab
without a human approval bound to a hash of the exact plan.

It also lived entirely in a terminal, which meant that to approve a run I had to
type a run id like `hc-20260822-6fbfa5` and then re-type the original 350-character
request verbatim, because `resume` rebuilds the context pack from it. Get one
character wrong and you have quietly changed the inputs the agents were judged on.

So I built a dashboard. This is what it is, and — more usefully — the six things
that broke once I had something I actually had to look at every day.

![The dashboard: run list, pipeline, and the approval gate](/images/posts/council-dashboard-run.png)

## The constraint that shaped everything

Codex reviewed the idea before I wrote any of it and set one rule I kept:

> The browser never gains authority the terminal does not have.

Concretely: no credential is ever sent to the page, the browser cannot start a
mutation, and it submits an approval bound to a plan hash that the *server*
computes. The orchestrator still re-checks the record and the claim before
anything runs. The dashboard renders history and collects one decision.

It's standard library only — `ThreadingHTTPServer`, a few JSON endpoints, one
page served from memory. The venv had no web framework and I didn't want to add
one to a box whose blog runs Hugo specifically to avoid a dependency tree.

Agent replies go into the DOM with `textContent`, never as markup. They quote
shell and YAML; interpolating them as HTML would let a model's output execute in
the browser of the person reviewing it. There's a test that greps for
`innerHTML`, `insertAdjacentHTML`, `document.write` and `outerHTML`.

## Then I started using it

### 1. The poll was eating what I typed

Text entered into the approval box vanished as I typed it. The five-second
refresh rebuilt the pane with `replaceChildren()`, taking every half-filled
field with it. There was a pause button, but needing it to fill in a form isn't
a workaround — it's the bug wearing a hat.

Fixed twice over: the pane is never rebuilt while any field in it holds text, and
an unchanged run doesn't rebuild at all. Then I replaced polling with
server-sent events, which removes the conflict at the source rather than
guarding around it.

### 2. A comment ate the end of a statement

```js
setInterval(()=>{...}  // sel is null while the form is open},5000);
```

The `//` comment I'd added in the previous change swallowed the `},5000);` that
closed the arrow function. The script didn't parse, so nothing ran: header stuck
on "loading", no runs, no panel health. One line, three broken features.

Three hundred Python tests passed the whole time. To Python it was a perfectly
valid string. I had a test asserting the page contained no `innerHTML`, and no
test asserting the page *worked*.

The suite now extracts the inline script and runs `node --check` over it. That's
the project's own rule — move validation into code rather than trusting a careful
read — applied to the one file that had no checker at all.

### 3. The columns assumed nothing was above them

I added a band at the top for starting a review. The two columns below still had
`height: calc(100vh - 38px)` — the header, and nothing else. The sidebar ran past
the bottom of the window with its scrollbar below the fold, so older runs weren't
just off-screen, they were unreachable.

The magic number stopped being right the moment something appeared above it,
which is the argument against having written it. It's a flex column now and
nothing needs to know how tall anything else is.

### 4. A correct refusal that arrived as an empty 500

Recording a second approval failed with *"unexpected end of JSON input"*.

The cause was the design working. Approvals carry a `UNIQUE` constraint on run
and stage because they're single-use — no blanket approvals, no quietly widening
one that exists. But `sqlite3.IntegrityError` went unhandled, so the server
returned an empty 500 and the page could only report that it had failed to parse
nothing.

### 5. A run that died yesterday still advertised itself as running

I'd killed a TUI mid-approval a day earlier. Nothing rewrote the row, so the
record claimed `human_approval: running` indefinitely — and the header strip I'd
just built to show live activity displayed it as live.

There's no process table worth consulting: the orchestrator may have been started
from a terminal that's long gone. The event log is what's reliable. Every stage
transition appends to it, so a run genuinely working writes something within its
own stage timeout, and one that hasn't, isn't.

```text
silent for 1296 minutes -> interrupted
```

Forty-five minutes is the threshold, deliberately generous — a review stage
allows fifteen minutes per agent and a panel can sit quiet for most of it. The
display relabels; the stored status is untouched and travels alongside, because
the dashboard doesn't get to edit history.

### 6. My own hardening broke the agents

I resumed a run from the browser. It reached `independent_verification` and then:

```text
codex: error Error: failed to initialize in-process app-server client:
Read-only file system (os error 30)
```

Not a codex fault. The dashboard's unit runs `ProtectHome=read-only` with write
access to the runs directory and nothing else, and agents spawned as its children
inherit that. Codex keeps an app-server socket and a sqlite database under
`~/.codex`; Claude keeps session state under `~/.claude`.

The easy fix is widening `ReadWritePaths` until the agents work. That hands a
service reachable from a browser write access to both agents' credential
directories, to solve an inconvenience. Worse trade than the problem.

So the dashboard no longer starts agents at all:

```text
browser ──▶ dashboard   (sandboxed, reachable, holds no credential)
                 │  writes a validated job file
                 ▼
            runs/_queue/
                 │
            runner      (not sandboxed, not reachable) ──▶ claude / codex / kimi
```

The worker isn't confined, because the agents genuinely need their state. It's
protected by being unreachable rather than by being restricted. Run ids and
workflow names are validated twice — at the endpoint and again in the worker —
because the file between them becomes a command line and was written by something
exposed.

One job at a time. This guest has frozen from concurrent heavy work before.

## What the dashboard is actually for

Two things the terminal genuinely couldn't do.

**Round comparison.** Each agent's round 1 next to its round 2. The panel's value
is the correction between them — *"my position is revised"*, *"the claim that both
logs are 0640 is false"* — and that's invisible in a scrolling transcript.

**The Kimi handoff inline.** Kimi is human-mediated on purpose — I asked Codex
to review a headless launcher for it and took its advice not to build one. So
every run that includes
Kimi parks and waits for a paste. That used to mean Mousepad, a second terminal
and retyping the request. Now it's on the page.

![The Kimi handoff, panel health, and resume](/images/posts/council-dashboard-kimi-handoff.png)

Panel health is the six scores each run emits to Langfuse. Note what it says
under `synthesis format ok`: **"1 pt — too few for a trend"**. Two points make a
line and a line looks like a conclusion, so a series with fewer than three real
points refuses to draw one. Runs that aren't real runs — my own probes while
building the score emitter — are dropped rather than padding the chart with data
about nothing.

## The thread running through all six

Every one of these was the same failure in different clothes: **something absent
rendering as something healthy.**

A form that lost your text looked like a form you hadn't filled in. A dead script
looked like a page still loading. A dead run looked like a live one. An empty 500
looked like a parse error. A score that never sent looked like a score of zero —
that one bit me earlier in the week, when a categorical value sent as a number
got a `400` that my own fail-safe swallowed.

So the page renders *empty* and *unavailable* differently on purpose, and a test
enforces it. When the stream drops, the indicator says `reconnecting…` with
backoff until it genuinely is — it never sits on "live" while blind.

## Where it sits now

It runs as a systemd unit behind Authentik forward_auth, bound to the Docker
bridge rather than the LAN, alongside everything else on the board.

![The homelab dashboard, regrouped by what fails together](/images/posts/homepage-regrouped.png)

The desktop icon opens the dashboard now. A second launcher keeps the Textual
interface, which is still the answer over SSH and when the dashboard is down —
the terminal became the fallback rather than the front door.

332 tests. Six bugs, all found by using it rather than by testing it, which is
its own lesson: I had good coverage of the layer I understood and none of the
layer I'd just written.
