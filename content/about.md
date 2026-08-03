---
title: "About"
date: 2026-07-01T00:00:00+10:00
draft: false
description: "IT student, gamer, and hobbyist based in Australia — using Claude to build, learn, and document."
hideMeta: true
ShowPostNavLinks: false
ShowToc: false
timeline:
  - when: "6+ yrs"
    what: "Around IT and tech — the background I build on"
  - when: "In studies"
    what: "A teacher introduced me to Claude; it became part of my daily workflow"
  - when: "2026"
    what: "Documenting real projects publicly on billsblog.dev"
  - when: "~Q4 2026"
    what: "Diploma in Cyber Security (expected)"
skillgroups:
  - name: "Networking"
    icon: "🌐"
    items: ["pfSense", "RFC1918 containment", "Guest segmentation", "WPA3", "DNS", "SNMP", "WireGuard / Tailscale"]
  - name: "Security"
    icon: "🛡"
    items: ["Isolation & containment", "Host / service hardening", "Least-privilege", "Threat modelling", "Defence-in-depth"]
  - name: "Linux & systems"
    icon: "🐧"
    items: ["Debian", "systemd", "Bash", "Service hardening", "Self-hosting"]
  - name: "Virtualisation"
    icon: "🖥"
    items: ["VMware Workstation", "VM networking", "Isolated lab environments"]
  - name: "Observability"
    icon: "📊"
    items: ["Prometheus", "Grafana", "node_exporter", "snmp_exporter", "MQTT"]
  - name: "AI-assisted workflow"
    icon: "🤖"
    items: ["Claude Code", "Custom MCP servers", "Agentic build & debug", "Multi-LLM gateway (LiteLLM + Open WebUI)"]
  - name: "Web & tooling"
    icon: "🌍"
    items: ["Hugo", "Git / GitHub", "Cloudflare Pages"]
---

{{< authorcard >}}

## Who I Am

I'm Billal, an IT student based in Australia with nearly six years in the field. I'm currently completing a Diploma in Cyber Security, with graduation set for late 2026.

My main interests span networking, cybersecurity, virtualisation, Linux, and gaming — and more often than not, several of those overlap in the same project.

{{< timeline >}}

## How I Got Here

One of my teachers introduced me to Claude early in my studies, and it genuinely changed how I think about AI as a tool. I went from treating it as a novelty to using it as a proper part of my workflow — for studying, building, troubleshooting, and writing.

## What I Do

- **Networking & Security** — hands-on practice with Linux CLI, Windows PowerShell, pfSense, and virtual lab environments
- **Virtualisation** — running Debian and pfSense VMs, using Claude Code and Claude Desktop within isolated environments
- **AI infrastructure** — Claude Code is still the main LLM driving my homelab; on top of it I now run a self-hosted multi-LLM gateway, so Claude plus a range of other models are reachable through one interface — access-controlled and traced
- **Game Modding** — as a heavy gamer, I mod and extend games in ways I couldn't do without AI assistance
- **Side Projects** — small builds and experiments I do in my own time, mostly to learn by doing

## Skills & Tools

Grouped by what I actually build and troubleshoot in the projects on this site:

{{< skills >}}

## What This Blog Is

This blog documents what I actually do with Claude — not polished tutorials, just real projects, small wins, and things I figured out along the way. If it ended up working, it probably ended up here.

### How it's built

It's a **static site** — a folder of HTML, CSS and JS with no server-side code and no database. I write Markdown, **Hugo** builds it, **Cloudflare Pages** serves it. That was a deliberate choice: a dynamic CMS runs code for every visitor, which is a live attack surface of plugins, a database and a server that can be compromised. A static site is built once, ahead of time, so there's no per-request code to exploit. For a blog that documents security work, the blog should be as defensible as the work it shows.

There's no manual deploy step — the whole flow is one `git push`:

```text
edit Markdown ─► git commit + push ─► GitHub ─► Cloudflare builds (hugo --gc --minify) ─► served at the edge
```

Since there's no backend, the security story is about protecting the pipeline and telling the browser how to behave:

- **Content Security Policy** — `script-src` is **hash-locked**: it lists the SHA-256 hash of each inline script instead of `'unsafe-inline'`, so an injected `<script>` has the wrong hash and is blocked. That's the real XSS defence.
- **HSTS** (`includeSubDomains; preload`), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy` and `Cross-Origin-Opener-Policy`, all served from a `_headers` file at the edge.
- **The GitHub token** is a fine-grained PAT scoped to this one repo, with an expiry and a rotation habit.

I wrote up the two big moves in detail: [moving off GitHub Pages for real security headers](/posts/cloudflare-pages-migration-security-headers/) and [registering my own domain](/posts/registering-billsblog-dev/).

Under the hood it's also a playground — a WebGL shader background, smooth momentum scrolling, a command palette (**Ctrl/⌘ + K**), scroll-driven reveals and a Konami code. All of it is CSS-first, any JavaScript is external and served from this origin so the hash-locked CSP stays clean, and everything respects `prefers-reduced-motion`. Type is Rajdhani, self-hosted as `woff2`; the accent is `#E81A1A` on near-black. Analytics is GoatCounter (no cookies), comments are giscus on GitHub Discussions (no database of my own).

See the [changelog](/changelog/) for how it got here and the [stats](/stats/) for where it stands.

Want to get in touch? The GitHub and LinkedIn links are on the [home page](/).
