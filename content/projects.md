---
title: "Projects"
description: "The projects behind the posts — networking, security, game modding, and tooling."
ShowToc: false
hidemeta: true
comments: false
---

Real work on my own gear, written up honestly — including what broke. Each project links to its full post.

## pfSense containment lab

A pfSense VM firewalling the Debian VM where my Claude Code agents run — egress rules allow internet-out and block every private range. Includes diagnosing a full outage caused by a Windows update silently re-enabling the hypervisor.

[Read: Debugging a Dead VMware NAT and Hardening My pfSense Containment Lab →](/posts/pfsense-lab-recovery-and-hardening/)

## Home network hardening

Baseline hardening and guest segmentation on an ISP-issued Arcadyan HWG2025: WPA3, WPS off, remote management off, two isolated zones, and the ISP-locked DNS workaround.

[Read: Hardening and Segmenting My Home Network on an Arcadyan HWG2025 →](/posts/home-network-hardening-hwg2025/)

## BiggerBang — SPT mod port (TypeScript → C#)

An abandoned Single Player Tarkov trader mod, ported from the SPT 3.x TypeScript API to a compiled C#/.NET DLL for SPT 4.0 — five bugs fixed, released to the community.

[Read: Porting a TypeScript Game Mod to C# and Hardening It for Community Release →](/posts/spt-aki-typescript-to-csharp-port/)

## FoxWeaponSound — SPT mod port via Claude Fable 5

A 2022 JavaScript weapon-sound mod rebuilt as a .NET 9 DLL for SPT 4.0.13, driven end-to-end through Claude Fable 5 — which surfaced five bugs the original had shipped with for four years.

[Read: Porting a Mod Through Claude Fable 5 →](/posts/porting-mod-claude-fable-5/)

## Spec Grabber — system info desktop tool

A native desktop GUI (Python, customtkinter, psutil) that collects system and hardware info into a styled, self-contained HTML report. Security-hardened; packaged for Linux and Windows with PyInstaller.

[Read: Created a SystemInfo Grabber Program with Claude AI →](/posts/systeminfo-grabber-claude-ai/)

## LaMetric TIME on an isolated network

Live home-lab stats on a LaMetric Time display, bridged over MQTT through a cloud broker — the publisher VM and the display can't reach each other on the LAN by design, so both connect outbound and the isolation stays intact.

[Read: Implementing LaMetric TIME to Network →](/posts/implementing-lametric-time-to-network/)

## This blog

Hugo + PaperMod on GitHub Pages with a Claude Code publishing pipeline: raw notes in, finished post out — filed, committed, and deployed by one command.

[Read: Self-Hosting a Hugo Blog with a Claude Code Publishing Pipeline →](/posts/self-hosted-hugo-claude-code-pipeline/)
