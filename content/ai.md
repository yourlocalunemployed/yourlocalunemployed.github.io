---
title: "AI Infrastructure"
layout: ai
description: "AI agents have real access to this lab, and one of them can change it. This is what sits between them and anything that matters — the roles, the gateway, the orchestration, and the controls that are deterministic rather than polite requests."
ShowToc: false
hideMeta: true
comments: false
---

Several agents work on this homelab, in different roles — a builder, reviewers, an auditor, an
analyst over the SOC, a second instance that owns this blog — and exactly one of them can change
the lab. That makes the interesting question not *which models run here* but **what stands between
them and anything that matters**.

The short answer: the agent that proposes a change is never the agent that certifies it, and
nothing reaches the lab without a human approval bound to a hash of the exact plan. The longer
answer is below, including the parts that don't work yet.
