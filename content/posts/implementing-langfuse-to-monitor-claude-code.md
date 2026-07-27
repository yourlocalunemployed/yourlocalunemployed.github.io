---
title: "Implementing Langfuse to Monitor Claude Code"
date: 2026-07-27T14:55:00+10:00
draft: false
description: "I self-hosted Langfuse so I could see what Claude Code is actually doing in the background instead of just trusting the output — token usage, timing, and a real dashboard."
tags: ["claude-code", "langfuse", "observability", "opentelemetry", "docker", "home-lab", "self-hosting"]
series: ["Home Lab"]
seriesTitle: "Tracing Claude Code with Langfuse"
cover:
  image: "/images/posts/langfuse-claude-code-tracing.png"
  alt: "Langfuse's Tracing view showing a single claude_code.interaction trace with 2 observations and 3.40s latency"
  hiddenInSingle: true
---

We all tend to focus on the output of whatever LLM we're using — did it get the answer right, was it fast, was it useful. What I'd stopped paying attention to was the background: how many tokens a session was actually burning, where they went, and whether I'd have any way of knowing if something had gone quietly wrong. Claude Code runs natively on my homelab now, doing real work against real infrastructure, and I wanted more than "the output looked fine" as my only signal.

So I self-hosted **Langfuse** — an open-source LLM/agent observability platform — as another container on the lab.

---

## What Langfuse actually is

Langfuse's usual job is tracing calls an *application* makes to an LLM: prompts in, completions out, latency, token counts, cost, all captured via its SDK wrapped around your own code. That's not what I needed here — I don't have an app calling an LLM, I have Claude Code itself running on my machine, and I wanted visibility into *its* sessions, not some other program's.

Claude Code has a separate answer for that: a beta OpenTelemetry export that emits its own session activity as traces — prompts, tool calls, API requests, token counts — which can be pointed at any OTLP-compatible collector. Langfuse happens to accept OTLP traces directly, so the two connect without needing Langfuse's usual app-side SDK at all.

## Getting the container up

Docker Compose, same pattern as everything else on the lab. This is where I actually lost the most time — typos and a couple of misconfigured lines in the compose file before anything came up cleanly.

The concrete one: I landed on a host port that was already spoken for. Langfuse's own compose file maps the container's internal port 3000 to a *host* port you choose — the container side has to stay 3000 for the service to work internally, but the host side is yours to pick. On this box, port 3000 was already taken by Grafana, running natively. Pointing Langfuse's web UI at 3000 on the host collided with that. The fix was just remapping the host side — `127.0.0.1:3001:3000` — and leaving the container's internal port alone.

Small thing, but worth writing down: `docker ps` shows you both sides of that mapping. If a service "isn't responding" on the port you expect, check which port is actually bound on the host before assuming the container's broken.

## Wiring Claude Code into it

With Langfuse up on `3001`, the other half was getting Claude Code to actually send it anything. A few environment variables, set globally so every session on this machine picks them up:

```bash
CLAUDE_CODE_ENABLE_TELEMETRY=1
CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1     # tracing is still a beta feature
OTEL_TRACES_EXPORTER=otlp
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf # Langfuse doesn't support gRPC yet
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:3001/api/public/otel/v1/traces
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic <base64 of pk:sk>,x-langfuse-ingestion-version=4
```

The auth header is HTTP Basic, built from Langfuse's own public/secret API keypair (created once in its UI), base64-encoded. Once that's in place, a Claude Code session shows up as a `claude_code.interaction` trace with child observations for the model calls and tool runs underneath it — which is exactly what's in the screenshot above: one trace, two observations, 3.4 seconds, no drama.

I checked the wiring actually worked before trusting it, rather than assuming green means good: POSTing a garbage body to the OTLP endpoint returns `400` (auth accepted, endpoint reachable, body just wasn't valid) — a `401` there would mean the API key was wrong instead.

## What it shows — and what it deliberately doesn't

This is the part that mattered most for what I originally wanted: token counts, latency, and timing per session, without having to eyeball a terminal scrollback. That's the "detailed status of how much tokens I've used" I was after.

What it isn't is a hallucination detector. Langfuse gives me *visibility* — a record of what happened, when, and how much it cost — not an assessment of whether Claude's output was actually correct. It's a better instrument panel, not a lie detector. Worth being precise about that distinction rather than overselling it.

It's also not logging the actual prompt and response text by default. Content fields show as `<REDACTED>` unless I explicitly opt in — which felt like the right default for a brand-new service I'd just stood up, even a self-hosted, loopback-only one.

## What's still loose

- **The traces feature is beta** on Claude Code's side. The span shape could change on an update without warning.
- **One of Langfuse's own containers (minio, its object storage for trace blobs) is bound to all interfaces**, not loopback like the rest of the stack — worth locking down, not yet done.
- Langfuse isn't behind my reverse proxy yet, so it's loopback-only for now — fine while I'm the only one looking at it.

None of that stops it from doing the one job I actually wanted: turning "the output looked fine" into something I can go check.
