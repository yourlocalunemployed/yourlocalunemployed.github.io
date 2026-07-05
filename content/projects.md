---
title: "Projects"
description: "The projects behind the posts — networking, security, game modding, and tooling."
ShowToc: false
hidemeta: true
comments: false
---

Everything here is real work on my own gear, written up honestly — including what broke. Each project links to its full post.

## pfSense containment lab

A pfSense VM firewalling a Debian VM where my Claude Code agents run. Egress rules allow internet-out but block every private range, so a misbehaving agent can't touch my home network. Includes the diagnosis of a total outage caused by a Windows update silently re-enabling the hypervisor.

[Read: Debugging a Dead VMware NAT and Hardening My pfSense Containment Lab →](/posts/pfsense-lab-recovery-and-hardening/)

## Home network hardening

Baseline hardening and guest segmentation on an ISP-issued Arcadyan HWG2025 (Wi-Fi 7) — WPA3, WPS off, remote management off, two isolated zones, and the ISP-locked DNS problem.

[Read: Hardening and Segmenting My Home Network on an Arcadyan HWG2025 →](/posts/home-network-hardening-hwg2025/)

## BiggerBang — SPT mod port (TypeScript → C#)

Ported an abandoned Single Player Tarkov trader mod from the SPT 3.x TypeScript API to a compiled C#/.NET DLL for SPT 4.0, fixed five real bugs on the way, and released it to the community.

[Read: Porting a TypeScript Game Mod to C# and Hardening It for Community Release →](/posts/spt-aki-typescript-to-csharp-port/)

## FoxWeaponSound — SPT mod port, run through Claude Fable 5

A 2022 JavaScript weapon-sound mod rebuilt as a .NET 9 DLL for SPT 4.0.13, with the whole port driven through Claude Fable 5 — which found five bugs the original had shipped with for four years.

[Read: Porting a Mod Through Claude Fable 5 →](/posts/porting-mod-claude-fable-5/)

## Spec Grabber — system info desktop tool

A native desktop GUI (Python, customtkinter, psutil) that collects system and hardware info into a styled self-contained HTML report. Security-hardened, packaged with PyInstaller for both Linux and Windows.

[Read: Created a SystemInfo Grabber Program with Claude AI →](/posts/systeminfo-grabber-claude-ai/)

## LaMetric TIME on an isolated network

Live home-lab stats (CPU, RAM, disk, throughput, latency) on a LaMetric Time smart display — bridged over MQTT through a cloud broker, because the publisher VM and the display sit on two networks that deliberately can't reach each other. Outbound-only connections on both sides; the isolation stays intact.

[Read: Implementing LaMetric TIME to Network →](/posts/implementing-lametric-time-to-network/)

## This blog

Hugo + PaperMod on GitHub Pages, with a Claude Code publishing pipeline: raw notes in, finished post out — filed, committed, and deployed by one command.

[Read: Self-Hosting a Hugo Blog with a Claude Code Publishing Pipeline →](/posts/self-hosted-hugo-claude-code-pipeline/)
