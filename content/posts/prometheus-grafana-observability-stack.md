---
title: "Building a Prometheus and Grafana Observability Stack for My Home Lab"
date: 2026-07-06T21:26:00+10:00
draft: false
description: "The dashboard layer under the LaMetric glance: Prometheus scraping my Debian VM and pfSense firewall, Grafana turning it into real graphs with history — all on one isolated VM, bound to localhost, reusing the SNMP work from the last project."
tags: ["prometheus", "grafana", "monitoring", "pfsense", "snmp", "home-lab"]
series: ["Home Lab"]
seriesTitle: "Prometheus + Grafana stack"
cover:
  image: "/images/posts/grafana-node-dashboard.png"
  alt: "Grafana Node Exporter dashboard for the Debian VM"
  hiddenInSingle: true
---

My [LaMetric display](/posts/implementing-lametric-time-to-network/) gives an at-a-glance read on the lab, but it's a spot reading with no history — good for "is something on fire right now," useless for "what happened overnight." This project adds the layer underneath: a **Prometheus + Grafana** stack that scrapes my hosts continuously, stores the history, and draws real dashboards.

Two targets: **CLAUDDEB** (my Debian automation VM) and my **pfSense firewall**, reusing the exact SNMP setup from the [pfSense post](/posts/implementing-lametric-time-to-network-part-2/) — just pointed at something far more capable than a 37-pixel display.

## Where it runs, and why

The whole stack lives on CLAUDDEB, and that falls out of how Prometheus works. Prometheus is **pull-based**: it reaches out to each target and scrapes its metrics, rather than targets pushing to it. So placement is decided by reachability. My targets are node_exporter on CLAUDDEB itself (localhost) and pfSense (the gateway CLAUDDEB is already allowed to reach). Anywhere else, Prometheus would have to scrape *across* my network isolation into the lab segment — which the containment blocks. Running it inside the segment, next to the data, keeps everything self-contained with no new firewall holes.

The consequence: Grafana lives on `localhost:3000`, viewed from CLAUDDEB's own desktop. Reaching it from another machine would be a separate, scoped decision (a firewall rule or a VPN), left for later.

## The tools

- **Prometheus** (port 9090) — the core: a time-series database that scrapes targets on a schedule, stores the numbers over time, and answers queries in its own language, PromQL.
- **node_exporter** (port 9100) — exposes a host's own metrics (CPU, memory, disk, network, filesystem) as a page of numbers for Prometheus to scrape. This is how CLAUDDEB's health gets in.
- **snmp_exporter** (port 9116) — a translator. Prometheus speaks HTTP; pfSense speaks SNMP. The exporter sits between: Prometheus asks it over HTTP, it queries pfSense over SNMP (the same interface counters as last time), and hands back Prometheus-style metrics.
- **Grafana** (port 3000) — the dashboards. It stores nothing itself; it queries Prometheus on demand and draws the graphs.
- **systemd** — runs each of the above as a service that starts on boot, the same pattern as my LaMetric pusher.

## The build, in order

Each piece got a locked-down service user (no home, no login), a systemd unit, and — importantly — was bound to **localhost only**. I verified each layer before adding the next.

1. **node_exporter** — installed, confirmed it served metrics at `127.0.0.1:9100/metrics`.
2. **Prometheus** — installed with a config listing what to scrape (itself + node_exporter to start), then checked its `/targets` page showed both **UP**.

![Prometheus /targets — node and prometheus both UP](/images/posts/prometheus-targets-node.png)

Prometheus's own query UI confirmed the data was flowing before I built anything on top of it:

![Querying node_memory_MemAvailable_bytes in the Prometheus expression browser](/images/posts/prometheus-query-memory.png)

3. **snmp_exporter** — installed with its bundled config (which already includes an `if_mib` module for interface counters). One edit: the default config only knows the community `public`, so I added an auth block for my real read-only community. Tested directly with `curl` and got the pfSense interface counters back.
4. **Wired pfSense into Prometheus** — the one genuinely odd bit. Scraping SNMP needs a `relabel_configs` block that reads as a redirect: Prometheus connects to the *exporter* (`127.0.0.1:9116`) but tells it to go query *pfSense*, and labels the results as pfSense's. That indirection is the whole trick of SNMP-via-exporter. A third target, `snmp-pfsense`, then showed **UP**.

![All three targets UP — node, prometheus, and snmp-pfsense](/images/posts/prometheus-targets-all.png)

5. **Grafana** — installed from its APT repo (so `apt upgrade` keeps it patched — worth it for anything with a login), bound to localhost, logged in, forced a new password.

![Grafana up and running on localhost:3000](/images/posts/grafana-welcome.png)

6. **Connected and visualized** — added Prometheus as a Grafana data source, then imported two prebuilt community dashboards by ID rather than building panels by hand:
   - **1860** — *Node Exporter Full*, a comprehensive host dashboard.
   - **11169** — an *SNMP interface* dashboard for the pfSense data.

Both lit up with live data almost immediately. Importing by ID is a genuinely useful trick — grafana.com hosts thousands of these, and they "just work" when the metric names match your exporter.

## Security posture

Nothing here is exposed, which was the point:

- **Everything binds to `127.0.0.1`.** The exporters have *no authentication* — they hand their metrics to anyone who asks — so localhost binding is essential, not optional. Grafana does have a login, but I bound it to localhost anyway: a login page that isn't reachable can't be attacked.
- **SNMP stays read-only** with a non-default community, bound to pfSense's LAN side only.
- **Service users** can't log in or own files elsewhere — standard hardening for daemons that only need to run.

## The gotchas

The parts that cost time:

- **Prometheus 3.x dropped the old console templates.** The install step to copy `consoles/` and `console_libraries/` failed because 3.x no longer ships them (deprecated in favour of Grafana). Harmless — nothing uses them, so skip it.
- **A systemd unit choked on inline comments.** I'd added comments *after* a line-continuation (`\`) in `ExecStart`, and systemd threw `Invalid unit name`. In a systemd unit, comments must be on their **own line** — never trailing a value or a continuation.
- **`software-properties-common` doesn't exist under that name on Debian 13.** It provides `add-apt-repository`, which I wasn't using — I added Grafana's repo by writing the source file directly.
- **Prometheus briefly showed itself as down** right after a restart — just the self-scrape not having run yet. It went green within 30 seconds. "Down" immediately after a restart usually means "not scraped yet," not "broken."
- **The SNMP dashboard's Uptime tile reads N/A.** The `if_mib` module only exposes interface data, not system uptime — cosmetic, and throughput (the thing I care about) works perfectly.

## The result

A proper monitoring backbone: node_exporter and snmp_exporter feeding Prometheus, visualized in two live Grafana dashboards — one for CLAUDDEB's health, one for the firewall's interface throughput, both building history every fifteen seconds.

![Node Exporter Full — CLAUDDEB's CPU, memory, disk, and network with history](/images/posts/grafana-node-dashboard.png)

![The SNMP interface dashboard — pfSense throughput per interface](/images/posts/grafana-snmp-dashboard.png)

The disk-usage panels alone would have flagged the near-full root filesystem that bit me earlier, long before it caused trouble. The layering now makes sense end to end: the **LaMetric** is the glance, **Grafana** is the deep-dive, and **Prometheus** is the memory underneath both.

## What's next

The capstone is closing the loop. Grafana has an alerting engine, so a threshold breach — WAN throughput spiking, disk creeping past 85% — could fire a warning frame back to the LaMetric over the same MQTT broker from the first project. That would turn four separate builds into one connected system: metrics → alerting → a physical light on my desk.

The broader lesson is simple: **a glance is not monitoring.** A display tells you the current value; observability tells you the trend, the history, and when something started. Both are useful, but only one lets you answer the question that actually matters at 2am — *what changed?*
