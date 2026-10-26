---
title: "Now"
date: 2026-07-01T00:00:00+10:00
updated: "2026-10-24"
layout: now
draft: false
description: "What I'm up to right now — studies, projects, games, and learning."
hideMeta: true
ShowPostNavLinks: false
ShowToc: false
status:
  - label: "Term"
    value: "Final term · capstone in progress"
  - label: "Diploma"
    value: "Cyber Security · ~Q4 2026"
  - label: "At TAFE"
    value: "A group SOC build and test project"
  - label: "In the lab"
    value: "Multi-agent AI infrastructure"
sections:
  - title: "Studies"
    icon: "🎓"
    items:
      - "**Build & Battle** — the final-term group project at TAFE: a prototype SOC network on Proxmox. pfSense splitting seven VMs into four zones, a Wazuh SIEM in the SOC zone, a DMZ, then attack-and-defend rounds against it. Coursework, built by hand; none of the AI work on this blog is involved"
      - "**Team lead** — a group of five, so the job is as much sequencing the build and keeping evidence as it is building"
      - "**The build guide** — written first and ordered to follow the topology diagram, so each part depends only on the one before it"
  - title: "Projects & Labs"
    icon: "🧪"
    items:
      - "**A two-agent blog pipeline** — the agent on the lab drafts and redacts, a second one finishes the post in the repo, and a fail-closed leak gate sits on every push in between. Only I merge"
      - "**Homelab Council** — one request reviewed independently by Claude, Codex and Kimi, behind a human approval gate"
      - "**Claude Assurance** — an independent reviewer over the agents themselves, checking what they claim against the evidence they produced"
      - "**Homelab SOC** — eight log sources centralised, 53 detection rules, one dashboard over all of it"
      - "**Kimi as a read-only SOC analyst** — triages an alert and separates evidence from guesswork; no tools, so it cannot act on any of it"
      - "**Network digital twin** — NetBox holds what should be listening, a bounded nmap scan holds what actually answers"
      - "**AI gateway** — a self-hosted multi-LLM gateway behind single sign-on, with per-project keys and spend caps"
      - "**LABDECK** — an iPhone app mirroring the lab dashboard over the tailnet"
      - "**This blog** — self-hosted Hugo, moved off GitHub Pages to Cloudflare Pages for real security headers, on my own domain"
      - "**Identity provider** — Authentik across the lab: one login with MFA, including the firewall itself"
      - "**Observability stack** — Prometheus, Grafana and Loki, built before anything needed watching"
      - "**Segmented home network** — VLANs on pfSense with three isolated zones and no managed switch, behind a hardened consumer router"
      - "**Self-hosted password manager** — Vaultwarden behind Caddy and three firewalls"
      - "**Game modding with agents** — Witcher 3 mods built through an agent pipeline (three on Nexus, an armour set in progress), two SPT ports hardened for community release, and a GLSL shader pack for Minecraft — all on [/mods/](/mods/)"

  - title: "Learning"
    icon: "📚"
    items:
      - "Proxmox VE — VLAN-aware bridges and thin-provisioned VMs under a hard disk quota"
      - "Deepening Linux skills and pfSense configuration"
      - "Upskilling in Windows PowerShell"
      - "Strengthening core networking concepts"
      - "Working out where AI agents genuinely belong in an ops workflow — and where a deterministic check has to sit in front of one"
      - "Reading a system by its measurements rather than its comments: several numbers written down in my own configs turned out not to reproduce"
gaming:
  - name: "Single Player Tarkov"
    note: "modding + playing heavily"
  - name: "Minecraft"
    note: "heavily modded"
  - name: "Warframe"
    note: ""
  - name: "LEGO Batman Legacy"
    note: ""
  - name: "Batman: Arkham Knight"
    note: "modding + playing"
  - name: "Call of Duty: Black Ops III"
    note: ""
  - name: "Gray Zone Warfare"
    note: ""
  - name: "S.T.A.L.K.E.R. 2: Heart of Chornobyl"
    note: ""
  - name: "Terraria"
    note: ""
  - name: "Forza Horizon 5"
    note: ""
  - name: "Just Cause 4"
    note: ""
  - name: "Just Cause 3"
    note: ""
  - name: "Red Dead Redemption 2"
    note: ""
  - name: "Black Myth: Wukong"
    note: ""
  - name: "and many more"
    note: ""
---

What I'm up to right now — a living snapshot of studies, projects, games, and what I'm learning.
