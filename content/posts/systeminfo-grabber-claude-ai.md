---
title: "Created a SystemInfo Grabber Program with Claude AI"
date: 2026-07-02T22:02:00+10:00
draft: false
description: "One Claude Code session: a native desktop GUI that grabs system info and exports a styled HTML report — Tarkov-themed, security-hardened, and packaged as executables for both Linux and Windows."
tags: ["python", "claude-code", "gui", "pyinstaller", "debian", "windows"]
---

![The finished HTML report — dark red/black theme, one card per category](/images/posts/sysinfo-html-report.png)

I wanted a small desktop tool that grabs a snapshot of a machine — hardware, resource usage, network state — and writes it to a styled HTML report I can open in any browser. Useful for quick system audits and for keeping a record of a machine's specs over time. I built it in one Claude Code session (Opus 4.8) on my Debian 13 laptop, then packaged it for Windows as well.

## The prompt that started it

The entire spec was one sentence:

> can you create me a simple local program for myself with fancy gui with the whole purpose of gathering system information and it generating to a file location of whatever chose in the input, give me any prompt of info if you require

![The opening Claude Code session — system check first, then structured questions about GUI approach and report format](/images/posts/sysinfo-claude-first-prompt.png)

What Claude did first mattered more than the code: it checked the machine before writing anything. It found Python 3.13.5 with `psutil` already installed, no GUI toolkit (`tkinter` missing), and a PEP 668 "externally-managed" environment — then asked me structured questions about the GUI approach and output format instead of guessing. I picked a native desktop window and HTML output.

## First working version

The stack it landed on:

| Choice | Decision |
|---|---|
| GUI framework | `customtkinter` — native dark-mode desktop window |
| System info source | `psutil` |
| Output format | Styled, self-contained HTML report |
| Packaging | PyInstaller — single-file executable |
| Design | Background thread + live progress bar; each probe isolated so one failure won't crash the app |

The missing Tk dependency was installed with `pkexec apt install -y python3-tk`, and the first version came up: a dark window with category checkboxes, an output folder picker, and a generate button.

![First version running on Debian — default dark theme, before the re-skin](/images/posts/sysinfo-first-version-gui.png)

It collects eight categories:

| Category | Details |
|---|---|
| System / OS | Hostname, user, OS, kernel, architecture, boot time, uptime |
| CPU | Physical/logical cores, frequency, per-core usage, load average |
| Memory | RAM and swap — total / used / available / percent |
| Disk | Every mounted partition (size, used, free) + total I/O |
| Network | Interfaces, IP/MAC addresses, bytes sent/received, active connections |
| Logged-in Users | Active user sessions |
| Sensors / Battery | Battery %, power state, temperatures (if available) |
| Top Processes | 15 heaviest processes by RAM |

## Upgrade rounds

The first version worked but went through several more passes.

**Tarkov re-skin.** A darkened Escape from Tarkov BEAR faction emblem became the window background — downloaded, then processed with Pillow (brightness, red duotone, vignette). The whole interface was recoloured to red/black: dark cards, red accents on buttons, checkboxes and the progress bar. Same theme as this blog, which is the point.

**JSON → HTML.** The plain JSON export was replaced with the styled HTML report at the top of this post — the emblem embedded in the header, one table per section. The report is self-contained (image embedded as base64) and can auto-open in the browser when done.

**Optimisation and hardening.** The pass I actually care about for this portfolio:

- Bug fix: per-core CPU usage was returning zeros — now uses one accurate 1-second sample, with the total as the mean.
- Path-traversal guard: the output filename is stripped to a basename so it can't escape the chosen folder.
- HTML-injection safe: every dynamic value is escaped in the report, verified by feeding it an injected `<script>` payload.
- Safe file URI: browser auto-open uses `Path.as_uri()`, which handles spaces.
- The embedded emblem is computed once and cached, and asset paths resolve correctly when running frozen as an executable.

![Claude's session summary after the theme, HTML and hardening rounds](/images/posts/sysinfo-claude-upgrade-summary.png)

## Packaging — Linux executable and a Windows build kit

PyInstaller bundled the app into a standalone Linux executable (~18 MB) at `~/SystemInfoCollector/dist/SystemInfoCollector` — no Python needed to run it. The desktop launcher points at it, with a Troll Face icon, because it's my machine.

A Windows `.exe` can't be cross-built from Linux, so Claude produced a `Windows_Build_Kit/` instead: `build.bat`, the app source, `requirements.txt`, the theme assets and a README. Copy it to a Windows PC, double-click `build.bat`, and it builds `SystemInfoCollector.exe` locally.

![Building the kit on the Windows side — pip pulling dependencies while the kit README explains the one-time Python requirement](/images/posts/sysinfo-windows-build-kit.png)

That's exactly how it went on my Windows PC — one run of `build.bat`, and the resulting exe (~19 MB) launches the same red/black GUI:

![SystemInfoCollector.exe built and running on Windows 11 — same theme, same categories](/images/posts/sysinfo-windows-exe-gui.png)

## Verification

- Data-gathering logic tested headless — correctly read 16 logical cores, 15 GB RAM and 8 disks; all 8 collector categories passed.
- HTML report confirmed valid and self-contained.
- The `<script>` injection test confirmed escaping works.
- Linux executable smoke-tested: launched cleanly, GUI loop ran, assets and theme loaded, no errors.
- The Windows build command was validated on the Linux machine before shipping the kit.

## How I use it

1. Double-click the launcher, or run `~/SystemInfoCollector/dist/SystemInfoCollector`.
2. Tick the categories to collect.
3. Choose the output folder and optionally edit the filename (defaults to `sysinfo_<hostname>_<timestamp>.html`).
4. Click **GENERATE REPORT** — the styled report saves to the chosen location and opens in the browser.

Small tool, but the workflow is the takeaway: one plain-English prompt, a model that inspects the environment and asks before building, and an afternoon later there's a hardened, packaged program running on two operating systems.
