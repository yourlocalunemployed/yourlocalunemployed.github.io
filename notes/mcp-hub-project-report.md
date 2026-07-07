# Cross-Device Claude Code Sync: Building a Centralised MCP Hub over Tailscale

## Project Overview

This project connected two independent Claude Code environments — a home lab Debian VM (the "hub") and a portable Debian laptop (the "agent") — so that the laptop can push information into a centralised store on the VM from anywhere, including off-network locations such as a campus Wi-Fi environment.

Rather than using Claude Code's built-in Remote Control feature (which turns a second device into a remote *window* into a single session), this build keeps both machines as fully independent Claude Code agents and links them through a custom **MCP server** hosted on the VM. The laptop's Claude Code treats the hub as just another tool it can call.

## Goals

- Allow the laptop's Claude Code agent to send notes, facts, and updates to a central point on the home lab VM
- Make that link work from any network (home LAN, campus Wi-Fi, mobile hotspot) without opening inbound ports on the home firewall
- Preserve the existing network isolation of the home lab VM (pfSense RFC1918 containment)
- Keep the server's capabilities deliberately narrow for security

## Tools & Technologies Used

| Tool | Role in Project |
|---|---|
| **Claude Code** | AI coding agent running independently on both machines; the laptop's instance calls the hub as an MCP tool |
| **Python 3 + FastMCP (`mcp` SDK)** | Framework used to build the custom MCP server with minimal boilerplate |
| **Python venv** | Isolated Python environment (required on Debian, which blocks system-wide pip installs) |
| **systemd** | Runs the MCP server as a persistent service that survives reboots and auto-restarts on crash |
| **Tailscale** | WireGuard-based mesh VPN giving each device a stable private IP reachable from any network |
| **pfSense** | Existing virtual firewall enforcing outbound-only containment of the lab VM (unchanged by this project) |
| **curl / ping** | Verification tools used at each stage to confirm connectivity before moving on |

## Key Terminology

**MCP (Model Context Protocol)** — An open protocol that lets AI models like Claude connect to external tools and data sources. An *MCP server* exposes capabilities (called "tools") as functions; an *MCP client* (here, Claude Code) discovers those tools and can invoke them mid-conversation. In this project, the hub server exposes two tools: `push_info` (write a note) and `get_recent` (read notes back).

**SSE (Server-Sent Events)** — The network transport used by the MCP server. Unlike the default `stdio` transport (which only works for a process running on the same machine), SSE runs over HTTP, allowing remote machines to connect across a network.

**Tailscale / tailnet** — A mesh VPN built on WireGuard. Every enrolled device gets a permanent private IP in the `100.x.x.x` range that works identically regardless of physical network. Connections are outbound-only from each device to Tailscale's coordination servers, so no inbound firewall ports are ever opened. A "tailnet" is your private collection of enrolled devices.

**systemd service** — Linux's init system mechanism for managing background processes. A `.service` unit file defines what to run, as which user, and when — enabling the MCP server to start automatically on boot and restart if it crashes.

**venv (virtual environment)** — A self-contained Python environment that isolates a project's dependencies from the system Python. Debian enforces this separation and blocks direct system-wide `pip` installs.

**JSONL (JSON Lines)** — A file format where each line is an independent JSON object. Used here as an append-only inbox log, which safely handles multiple writes without risk of overwriting existing entries.

**Hub-and-spoke architecture** — A design where one central, always-on node (the hub) provides services that mobile or intermittently-available nodes (the spokes) connect to. Chosen here because the VM is always on, while the laptop sleeps and roams.

## Build Process

### 1. MCP server on the hub VM

- Created a project directory with a Python venv and installed the `mcp` SDK
- Wrote a FastMCP server (~40 lines) exposing two tools:
  - `push_info(source, content)` — appends a timestamped entry to an append-only JSONL inbox file
  - `get_recent(n)` — returns the last *n* inbox entries
- Bound the server to `0.0.0.0:8420` so it listens on all interfaces (necessary for the Tailscale interface, not just localhost), using the SSE transport

### 2. Persistence via systemd

- Created a service unit pointing at the venv's Python interpreter and the server script
- Configured `Restart=always` and ordered startup after networking and the Tailscale daemon
- Enabled and started with `systemctl enable --now`

### 3. Mesh VPN with Tailscale

- Installed Tailscale on both the VM and the laptop, enrolled both under the same account (same account = same tailnet)
- The VM's containment firewall rules required **no changes** — Tailscale's connections are outbound-only, matching the existing security model
- Recorded each machine's permanent tailnet IP

### 4. Registering the hub with Claude Code

- On the laptop: `claude mcp add --transport sse --scope user desktop-hub http://<hub-tailnet-ip>:8420/sse`
- On the VM itself (so its local Claude Code can also read the inbox): the same command pointed at `localhost`
- `--scope user` registers the server account-wide rather than per-project-directory

### 5. End-to-end verification

- Laptop Claude Code session invoked `push_info` with a test note; the hub confirmed storage
- The note was verified on the VM both via `cat` on the inbox file and via the VM's own Claude Code calling `get_recent`

## Troubleshooting Log

Real issues encountered and resolved — the most instructive part of the build:

| Symptom | Root Cause | Fix |
|---|---|---|
| `systemctl status` → `status=203/EXEC`, died in 34ms | Service file's `ExecStart` and `User=` referenced the wrong username/home path — systemd couldn't find the binary | Corrected paths to the actual account; `daemon-reload` then restart |
| Venv Python "No such file or directory" | The `python3 -m venv` step had silently never completed — only `server.py` existed in the project folder | Re-ran venv creation (installing `python3-venv` if missing) and reinstalled the SDK |
| Service still failing after venv fix | Edited paths hadn't been saved to the unit file — status output still showed old paths | Verified the `Process:` line in `systemctl status` to spot the stale path; re-edited, `daemon-reload`, restart |
| Tailnet ping showed 0.05–0.12ms latency; curl returned nothing | Pinging the laptop's **own** tailnet IP (loopback-level latency was the giveaway) rather than the VM's | `tailscale status` lists every device with its IP — used the VM's entry instead |
| Laptop's Claude Code session couldn't see the hub | Server was added *after* the session started (MCP servers load at session start), and default scope is per-directory | Re-added with `--scope user`; started a fresh session |
| Note "not found" on the VM | Looked for a visible artefact rather than the inbox file; also the VM's own Claude Code had no MCP registration (hosting a server ≠ being its client) | Read the JSONL inbox directly; separately registered the hub with the VM's Claude Code via localhost |

**Diagnostic techniques worth remembering:** `journalctl -u <service>` for service logs; the `Process:` line in `systemctl status` reveals the *actual* command systemd attempted; abnormally low ping latency indicates you're talking to yourself; `claude mcp list` from the shell vs `/mcp` inside a session are different surfaces.

## Security Considerations

- **Minimal tool surface:** the hub exposes only note-write and note-read. No shell execution, no arbitrary filesystem access. Every tool added to an MCP server is invocable by *any* connected client, so capabilities were kept deliberately narrow — a generic "run command" tool would turn a compromised client into a remote shell on the hub.
- **Input sanitisation pattern:** any future tool touching the filesystem should strip path components from inputs (e.g. `os.path.basename()`) to prevent directory traversal.
- **No inbound exposure:** Tailscale's outbound-only model means the home firewall never opens a port; the hub is unreachable from the public internet.
- **Existing containment preserved:** the VM's RFC1918 isolation rules remained untouched throughout.
- **Future hardening options:** a shared-secret/bearer-token layer on the server, and Tailscale ACLs restricting which tailnet devices may reach port 8420.

## Architecture Summary

```
┌─────────────────────┐         Tailscale mesh          ┌──────────────────────┐
│  Laptop (roaming)   │  ── outbound WireGuard/DERP ──▶ │  Home Lab VM (hub)   │
│  Claude Code agent  │                                 │  behind pfSense      │
│  MCP client         │   http://<tailnet-ip>:8420/sse  │  FastMCP server :8420│
│                     │  ──── push_info / get_recent ──▶│  inbox.jsonl store   │
└─────────────────────┘                                 └──────────────────────┘
```

The design is symmetric in principle — the laptop could host its own MCP server and the VM could be its client — but hub-and-spoke was chosen deliberately: the VM is always on, while the laptop sleeps and roams, making it a poor server.

## How This Assists Going Forward

- **Location-independent workflow:** notes, findings, and context captured on the laptop anywhere land in one central store, ready for the home lab agent to act on
- **Foundation for richer tooling:** the hub is extensible — new narrowly-scoped tools (constrained file drops, status queries, task queues) can be added as needs emerge, each just a decorated Python function plus a service restart
- **Portfolio value:** demonstrates practical skills across MCP server development, mesh VPN deployment, Linux service management, firewall-aware architecture, and methodical network troubleshooting
- **Reusable pattern:** the same recipe (FastMCP + SSE + Tailscale + systemd) applies to any future service that needs secure remote reachability without punching holes in the home network

## Possible Next Steps

- Add token-based authentication in front of the server
- Apply Tailscale ACLs to restrict port 8420 to specific devices
- Swap the JSONL inbox for SQLite if volume or querying needs grow
- Add carefully-scoped action tools (e.g. sanitised folder/file creation) where a concrete use case exists
- Write up as a blog post alongside the existing home lab observability and network hardening entries
