---
title: "Uses"
date: 2026-08-03T21:00:00+10:00
draft: false
description: "The actual kit — the machines, the OS, the editor, and the self-hosted stack behind the projects on this site. Versions are what's installed, not what's recommended."
hideMeta: true
ShowToc: true
TocOpen: false
comments: false
cover:
  image: "/images/pages/uses/cover.png"
  alt: "RAINBOW MATRIX cover — the page title in rainbow monospace over falling matrix rain on black"
  hiddenInSingle: false
---

Every tool here is one I actually run. Versions are whatever is installed on the box as I write
this, not a wish list — if something on this page is wrong, it's because I changed it and forgot to
come back.

## Machines

- **Main rig** — Windows gaming PC, RTX 4090. Games, modding, and the thing I remote into the lab from.
- **Lab VM** — Debian 13 (trixie), kernel 6.12, Xfce 4.20. This is where nearly everything on this
  blog gets built. Runs under VMware, behind pfSense.
- **Laptop** — a second Debian 13 machine, set up to match the lab VM so scripts and configs move
  between them without edits.
- **Network** — Arcadyan HWG2025 on NBN, with pfSense doing the real firewalling and segmentation.

## Desktop

| | |
| --- | --- |
| OS | Debian 13 (trixie) |
| Desktop | Xfce 4.20, red/black theme |
| Terminal | xfce4-terminal 1.1.4 |
| Shell | bash |
| Editor | VS Code 1.131 |
| Browser | Brave 1.93, Firefox ESR for testing |
| Notes | Obsidian 1.8.10 |

## Working with Claude

Claude Code is the main driver for the projects here — I give it the goal, review and correct what
comes back, and test it before it ships. It runs on the Debian VM with a `CLAUDE.md` per project,
custom slash commands, and hooks that enforce things I don't want to rely on remembering.

On top of that there's a self-hosted **multi-LLM gateway** (LiteLLM + Open WebUI + OpenRouter), so
Claude and a range of other models are reachable through one interface — access-controlled and
traced with **Langfuse**.

## The self-hosted stack

Everything runs on the lab VM, in Docker unless noted, reached through a reverse proxy rather than
published ports:

| Job | What runs |
| --- | --- |
| Reverse proxy + TLS | Caddy |
| Identity | Authentik (plus LDAP and RADIUS outposts) |
| Secrets | Vaultwarden |
| DNS filtering | AdGuard Home |
| Metrics | Prometheus + Grafana (native), node_exporter, snmp_exporter |
| Logs | Loki + Promtail |
| Alerting | Alertmanager → ntfy |
| Vulnerability scanning | Greenbone / OpenVAS |
| Automation | n8n |
| LLM observability | Langfuse |
| AI gateway | LiteLLM + Open WebUI |
| Dashboard | Homepage |
| Remote access | Tailscale, with WireGuard on pfSense as a break-glass path |

## Building things

| | |
| --- | --- |
| Node | 24.18 |
| Python | 3.13 |
| Hugo | 0.163.3 extended |
| Docker | 26.1.5 |
| Git | 2.47 |

## This site

Hugo + a heavily customised PaperMod, Markdown content, built and served by Cloudflare Pages on every
push to `main`. Self-hosted Rajdhani, GoatCounter for analytics, giscus for comments, and a
hash-locked Content Security Policy. The longer version of that story is on
[the about page](/about/#how-its-built).

## Notes and study

Obsidian for everything I write down — homelab runbooks, session logs, and the Islamic studies notes
I publish at [/taleb-ilm/](/taleb-ilm/). The vault syncs between the lab VM and the laptop, and I
read it through a small read-only dashboard I had Claude build, described in
[this post](/posts/local-dashboard-obsidian-vault/).
