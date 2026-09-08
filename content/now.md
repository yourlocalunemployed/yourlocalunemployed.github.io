---
title: "Now"
date: 2026-07-01T00:00:00+10:00
updated: "2026-09-08"
layout: now
draft: false
description: "What I'm up to right now — studies, projects, games, and learning."
hideMeta: true
ShowPostNavLinks: false
ShowToc: false
status:
  - label: "Semester"
    value: "Semester 2 · in progress"
  - label: "Diploma"
    value: "Cyber Security · ~Q4 2026"
  - label: "Focus"
    value: "Detection engineering · multi-agent AI infrastructure"
sections:
  - title: "Studies"
    icon: "🎓"
    items:
      - "Back at TAFE — semester 2 started a month ago and is well under way"
      - "Current unit work: setting up and configuring a network from a given scenario"
      - "Ethics and policies projects still ahead this semester"
  - title: "Projects & Labs"
    icon: "🧪"
    items:
      - "Built Homelab Council — one request reviewed independently by Claude, Codex and Kimi, behind a human approval gate"
      - "Ran the first full three-agent panel: all three corrected each other, and the plan that came out was one none of them proposed alone"
      - "Turned down a fourth agent after the panel reviewed the proposal and rejected it, including a safety property I had claimed and it disproved"
      - "Wired the agents into tracing: every run is one session, scored on five measures, with failures recorded and not just successes"
      - "Gave the council a web dashboard behind SSO, then found six bugs in it within an hour of actually using it"
      - "Rebuilt that dashboard to read like a log console — colour means severity now, and the overview shows where runs stop, how each agent replied, and every approval on record"
      - "Let the council dashboard execute an approved plan, after arguing myself out of the idea that typing a flag at a terminal was a security control — the gate is the approval record, not the input device"
      - "Split the lab's front page into tabs and pinned a health strip to all of them — alerts, swap, clock drift and container count, each from one query that returns a number even when the answer is zero"
      - "Ran a full container-image remediation pass: 2042 actionable findings down to 1497, every image pinned"
      - "Put the AI gateway behind single sign-on, with per-project keys carrying their own spend caps"
      - "Built the lab a SOC: seven log sources centralised, 36 detection rules, and one dashboard over all of it — collection first, dashboard last"
      - "Put Kimi on top of the SOC as a read-only analyst — it triages an alert, separates what the evidence shows from what it is guessing, and recommends; it has no tools so it cannot act on any of it"
      - "Had Kimi audit the thing Claude built, and it correctly refused to sign off the network controls it had not tested itself"
      - "Proved a brute-force rule that had matched nothing in 30 days actually fires, by generating the failed logins myself"
      - "Found my own access-log redaction had a hole on the response side, after it had already written session tokens to disk"
      - "Planning a Raspberry Pi as a filter proxy + ad blocker on the home network"
  - title: "Learning"
    icon: "📚"
    items:
      - "Deepening Linux skills and pfSense configuration"
      - "Upskilling in Windows PowerShell"
      - "Strengthening core networking concepts"
      - "Working out where AI agents genuinely belong in an ops workflow — and where a deterministic check has to sit in front of one"
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
