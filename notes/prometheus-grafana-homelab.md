---
title: "A Real Observability Stack for the Home Lab: Prometheus + Grafana"
date: 2026-07-06
draft: false
tags: ["homelab", "prometheus", "grafana", "monitoring", "observability", "pfsense", "snmp", "debian", "systemd", "security"]
categories: ["Home Lab"]
summary: "The LaMetric on my desk is the glance layer. This is the dashboard layer underneath it: Prometheus scraping my Debian box and my pfSense firewall, Grafana turning it into real graphs with history. Built on the same isolated VM, bound to localhost, reusing the SNMP work from the last project."
---

My [LaMetric display](/lametric-mqtt-homelab/) gives me an at-a-glance read on the lab, but it's a spot reading with no history — great for "is something on fire right now," useless for "what happened overnight." So this project adds the proper layer underneath: a **Prometheus + Grafana** stack that scrapes my hosts continuously, stores the history, and draws real dashboards.

The two targets: **CLAUDDEB** (my Debian automation VM) and my **pfSense firewall** — reusing the exact SNMP setup from the [pfSense post](/lametric-pfsense-snmp/), just pointed somewhere far more capable than a 37-pixel display.

## Where it runs, and why

The whole stack lives on **CLAUDDEB**. That's not arbitrary — it falls out of how Prometheus works.

Prometheus is **pull-based**: it reaches *out* to each target and scrapes its metrics, rather than targets pushing to it. So placement is decided by reachability. My targets are node_exporter on CLAUDDEB itself (localhost) and pfSense (the gateway CLAUDDEB is already allowed to reach). Put Prometheus anywhere else and it'd have to scrape *across* my network isolation into the lab segment — which my containment blocks. Running it inside the segment, next to the data, keeps everything self-contained with no new firewall holes. Same "put the collector where it can already reach the data" logic that drove the earlier builds.

Consequence: Grafana lives on `localhost:3000`, viewed from CLAUDDEB's own desktop. Reaching it from another machine would be a separate, scoped decision (a firewall rule or a VPN) — left for later.

## The tools, and what each one does

**Prometheus** — the core. A time-series database that scrapes targets on a schedule, stores the numbers over time, and answers queries in its own language, PromQL. Everything else plugs into it. (Port 9090.)

**node_exporter** — exposes the host's own metrics (CPU, memory, disk, network, filesystem) as a web page of numbers that Prometheus scrapes. This is how CLAUDDEB's health gets into the system. (Port 9100.)

**snmp_exporter** — a **translator**. Prometheus only speaks HTTP; pfSense only speaks SNMP. This exporter sits in the middle: Prometheus asks it over HTTP, it queries pfSense over SNMP (the same interface counters from last project), and hands back Prometheus-style metrics. (Port 9116.)

**Grafana** — the dashboards. It stores nothing itself; it queries Prometheus on demand and draws the graphs. This is where raw counters become something you actually read. (Port 3000.)

**systemd** — runs each of the above as a background service that starts on boot, same pattern as my LaMetric pusher.

## The build, in order

Each piece got a locked-down service user (no home, no login), a systemd unit, and — importantly — was bound to **localhost only**. I verified each layer worked before adding the next.

1. **node_exporter** → installed, confirmed it served metrics at `127.0.0.1:9100/metrics`.
2. **Prometheus** → installed with a config listing what to scrape (itself + node_exporter to start), then checked its `/targets` page showed both **UP**.
3. **snmp_exporter** → installed with its bundled config (which already includes an `if_mib` module for interface counters). One edit was needed: the default config only knows the community `public`, and mine is different, so I added a small auth block for my real read-only community. Tested it directly with `curl` and got my pfSense interface counters back.
4. **Wired pfSense into Prometheus** → this is the one genuinely odd bit. Scraping SNMP needs a `relabel_configs` block that reads as a redirect: Prometheus connects to the *exporter* (`127.0.0.1:9116`) but tells it to go query *pfSense*, and labels the results as pfSense's. That indirection is the whole trick of SNMP-via-exporter. After it, a third target — `snmp-pfsense` — showed **UP**.
5. **Grafana** → installed from its APT repo (so `apt upgrade` keeps it patched — worth it for anything with a login), bound to localhost, logged in, forced a new password.
6. **Connected + visualized** → added Prometheus as a Grafana **data source**, then imported two prebuilt community dashboards by ID rather than building panels by hand:
   - **1860** — *Node Exporter Full*, a comprehensive host dashboard.
   - **11169** — an *SNMP interface* dashboard for the pfSense data.

Both lit up with live data almost immediately. Importing by ID is a genuinely useful trick — grafana.com hosts thousands of these, and they "just work" when the metric names match your exporter.

## Security posture

Nothing here is exposed:

- **Everything binds to `127.0.0.1`.** The exporters have *no authentication* — they'll hand their metrics to anyone who asks — so localhost binding is essential, not optional. Grafana *does* have a login, but I bound it to localhost anyway: defense in depth, since a login page that isn't reachable can't be attacked.
- **SNMP stays read-only** with a non-default community, bound to pfSense's LAN side only.
- **Service users** can't log in or own files elsewhere — standard hardening for daemons that only need to run.

## The gotchas

The parts that cost time, so they don't cost yours:

- **Prometheus 3.x dropped the old console templates.** The install step to copy `consoles/` and `console_libraries/` failed because 3.x no longer ships them (a deprecated feature everyone replaced with Grafana). Harmless — nothing uses them, so skip it.
- **A systemd unit choked on inline comments.** I'd added teaching comments *after* a line-continuation (`\`) in `ExecStart`, and systemd threw `Invalid unit name`. Lesson worth keeping: in a systemd unit, comments must be on their **own line** — never trailing a value or a continuation. (Shell commands are fine with inline `#`; config files often aren't.)
- **`software-properties-common` doesn't exist on Debian 13** under that name. It provides `add-apt-repository`, which I wasn't using anyway — I added Grafana's repo by writing the source file directly. Skipped it, no impact.
- **Prometheus briefly showed itself as down** right after a restart — just the self-scrape not having run yet. It went green within 30 seconds. A good reminder that "down" immediately after a restart usually means "not scraped yet," not "broken."
- **The SNMP dashboard's Uptime tile reads N/A.** The `if_mib` module only exposes interface data, not system uptime. Cosmetic — throughput, the thing I care about, works perfectly. Populating it would mean adding the system MIB to the config, which I didn't bother with.

## The result

I now have a proper monitoring backbone: **node_exporter and snmp_exporter feeding Prometheus, visualized in two live Grafana dashboards** — one for CLAUDDEB's health, one for the firewall's interface throughput, both building history every fifteen seconds. The disk-usage panels alone would have flagged the near-full root filesystem that bit me earlier, long before it caused trouble.

The layering now makes sense end to end: the **LaMetric** is the glance, **Grafana** is the deep-dive, and **Prometheus** is the memory underneath both.

## What's next

The obvious capstone is closing the loop: Grafana has an alerting engine, so a threshold breach — WAN throughput spiking, disk creeping past 85% — could fire a **warning frame to the LaMetric** over the same MQTT broker from the first project. That turns four separate builds into one connected system: metrics → alerting → a physical light on my desk. I've left it as a part two, but it's the piece that ties the whole lab together.

The broader lesson from this one is simple: **a glance is not monitoring.** A display tells you the current value; observability tells you the trend, the history, and the "when did this start." Both are useful, but only one of them lets you answer the question that actually matters at 2am — *what changed?*
