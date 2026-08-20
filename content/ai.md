---
title: "AI Infrastructure"
layout: ai
description: "Three coding agents have real access to this lab. This is what sits between them and anything that matters — the roles, the gateway, the orchestration, and the controls that are deterministic rather than polite requests."
ShowToc: false
hideMeta: true
comments: false
---

Three coding agents work on this homelab, and one of them can change it. That makes the
interesting question not *which models run here* but **what stands between them and anything that
matters**.

The short answer: the agent that proposes a change is never the agent that certifies it, and
nothing reaches the lab without a human approval bound to a hash of the exact plan. The longer
answer is below, including the parts that don't work yet.
