# Project Note — System Info Collector

> **Started:** 2 July 2026
> **Built with:** Claude Code (Opus 4.8) on Linux (Debian 13) laptop
> **Location:** `~/SystemInfoCollector/`
> **Status:** Built, optimised, hardened, and packaged — Linux executable running,
> Windows build kit ready.

---

## Purpose

A simple **local desktop program** to gather system information about the
machine and export it to a **styled HTML report** at a folder of my choosing.
Useful for:

- Quick system audits / snapshots of hardware and resource usage
- Keeping a record of machine specs and state over time
- Producing a clean, readable report I can open in any browser

---

## What It Does

A fancy native desktop GUI (red/black **Escape from Tarkov** theme) that lets me
tick which categories to collect, choose an output folder, and generate an HTML
report with one click.

### Information it gathers

| Category | Details |
|---|---|
| **System / OS** | Hostname, user, OS, kernel, architecture, boot time, uptime |
| **CPU** | Physical/logical cores, frequency, per-core usage, load average |
| **Memory** | RAM and swap — total / used / available / percent |
| **Disk** | Every mounted partition (size, used, free) + total I/O |
| **Network** | Interfaces, IP/MAC addresses, bytes sent/received, active connections |
| **Logged-in Users** | Active user sessions |
| **Sensors / Battery** | Battery %, power state, temperatures (if available) |
| **Top Processes** | 15 heaviest processes by RAM |

---

## How It Was Built

| Choice | Decision |
|---|---|
| **GUI framework** | `customtkinter` — native dark-mode desktop window |
| **Theme** | Red/black, with a darkened EFT **BEAR faction emblem** as the window background |
| **Output format** | Styled, self-contained **HTML** report |
| **System info source** | `psutil` |
| **Packaging** | `PyInstaller` — single-file executable |
| **Design** | Background thread + live progress bar; each probe isolated so one failure won't crash the app |

---

## Changes & Enhancements (log)

The program went through several rounds of upgrades after the first version:

### 1. Look & feel — Tarkov theme + red/black GUI
- Added a darkened, red-tinted **Escape from Tarkov (BEAR faction)** emblem as
  the window background (downloaded, then processed with Pillow — brightness,
  red duotone, vignette).
- Recoloured the whole interface to a **red-and-black** theme: dark cards, red
  accents on buttons/checkboxes/progress bar, red headings.

### 2. Output format — JSON → HTML
- Replaced the plain JSON export with a **styled HTML report** (dark red/black
  theme to match the app, the emblem embedded in the header, tables per section).
- The report is **self-contained** (image embedded as base64) and can auto-open
  in the browser when done.

### 3. Packaging — turned into an executable
- Bundled the app into a **standalone executable** with PyInstaller — no Python
  needed to run it.
- A **Linux executable** is built and kept on this machine at
  `~/SystemInfoCollector/dist/SystemInfoCollector` (~18 MB), and the Desktop
  launcher now points at it (with a **Troll Face** icon).

### 4. Windows build kit
- Because a Windows `.exe` can't be built from Linux, created a
  **`Windows_Build_Kit/`** — copy to a Windows PC, double-click `build.bat`, and
  it produces `SystemInfoCollector.exe` with the Troll Face icon.
- Kit contents: `build.bat`, `sysinfo_gui.py`, `requirements.txt`,
  `assets\tarkov_bg.png`, `assets\trollface.ico`, `README_WINDOWS.txt`.
- Zipped to the Desktop as `SystemInfoCollector_Windows_BuildKit.zip`, with a
  full guide in `Build on Windows - Instructions.md`.

### 5. Optimisation & security hardening
- **Bug fix:** per-core CPU usage was returning zeros — now uses one accurate
  1-second sample, with the total as the mean.
- **Path-traversal guard:** output filename is stripped to a basename so it
  can't escape the chosen folder.
- **HTML-injection (XSS) safe:** every dynamic value is HTML-escaped in the
  report (verified with an injected `<script>` payload).
- **Safe file URI:** browser auto-open uses `Path.as_uri()` (handles spaces).
- **Efficiency:** embedded emblem is computed once and cached.
- **Frozen-aware assets:** resolves bundled paths correctly when run as the exe.

---

## Files created

| File | Role |
|---|---|
| `~/SystemInfoCollector/sysinfo_gui.py` | The application (optimised/hardened) |
| `~/SystemInfoCollector/dist/SystemInfoCollector` | **Standalone Linux executable** |
| `~/SystemInfoCollector/assets/tarkov_bg.png` | Processed Tarkov background |
| `~/SystemInfoCollector/assets/trollface.ico / .png` | Executable / launcher icon |
| `~/SystemInfoCollector/Windows_Build_Kit/` | **Windows .exe build kit** |
| `~/SystemInfoCollector/README.md` | Documentation |
| `~/SystemInfoCollector/run.sh` | Terminal launcher (dev) |
| `~/Desktop/SystemInfoCollector.desktop` | Desktop launcher (points at the executable) |
| `~/Desktop/SystemInfoCollector_Windows_BuildKit.zip` | Zipped kit for transfer to Windows |
| `~/Desktop/Build on Windows - Instructions.md` | Windows build guide |

### Dependencies

- **psutil**, **customtkinter**, **Pillow** — installed via pip
- **python3-tk** — system Tk package (installed via `pkexec apt install -y python3-tk`)
- **PyInstaller** — used to build the executables

---

## Verification

- Data-gathering logic tested headless — correctly read **16 logical cores,
  15 GB RAM, and 8 disks**; all 8 collector categories passed.
- HTML report generation confirmed valid and self-contained.
- Security: `<script>` injection test confirmed escaping works.
- **Linux executable** smoke-tested — launched cleanly, GUI loop ran, assets
  and theme loaded, no errors.
- **Windows build command** validated on the Linux build machine before shipping
  the kit (theme files + background bundled correctly).

---

## How I Use It

1. Double-click **System Info Collector** on the Desktop, or run
   `~/SystemInfoCollector/dist/SystemInfoCollector`.
2. Tick the categories to collect.
3. Choose the output folder (📁 Browse) and optionally edit the filename
   (defaults to `sysinfo_<hostname>_<timestamp>.html`).
4. Click **GENERATE REPORT** — a styled HTML report is saved to the chosen
   location and opens in the browser.
