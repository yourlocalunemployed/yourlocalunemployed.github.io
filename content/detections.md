---
title: "Detection Engineering"
layout: detections
description: "Every alert rule the lab actually runs — the live LogQL and PromQL, what each one catches, and how it maps to MITRE ATT&CK. Copied from the config on the host, not a wish list."
ShowToc: false
hideMeta: true
comments: false
---

Monitoring answers "is it up?" Detection answers "is something wrong on purpose?" This is the catalogue of rules the lab actually evaluates — 17 over logs and 18 over metrics — each one shown with its real expression, the threshold that trips it, and the MITRE ATT&CK technique it maps to. Everything below is copied verbatim from the live config on the host ([Prometheus](/posts/metrics-arent-monitoring/) alert rules and the [Loki ruler](/posts/homelab-soc-logs-detections-dashboard/)); a rule that isn't running doesn't get a card. For how the sources, alert path and dashboard fit together, see the [SOC](/soc/).
