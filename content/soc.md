---
title: "Security Operations Centre"
layout: soc
description: "The lab's security operations centre — seven log sources, 35 detection rules, an alert path to my phone, and one dashboard over all of it. Built collection-first, and every claim on this page was verified rather than assumed."
ShowToc: false
hideMeta: true
comments: false
---

My homelab had identity, a reverse proxy and a firewall — and only the firewall produced any security telemetry. Authentik's events stayed in its own database, Caddy wrote no access log at all, and 28 containers logged to disk with nothing reading them. Nothing needed installing; it was a *sources* gap, which is the kind that hides well because every service looks healthy.

This page is the result: what feeds the SOC, what it detects, how an alert reaches me, and what I still haven't got right. The [detection catalogue](/detections/) lists every rule with its live expression; the [write-up](/posts/homelab-soc-logs-detections-dashboard/) covers the bugs found along the way — including two I introduced myself.
