---
title: "Hardening My Debian Home-Lab VM — Even Behind pfSense"
date: 2026-07-07T21:50:00+10:00
draft: false
description: "The VM is already isolated behind a pfSense firewall — so why harden it? Because two paths reach in without ever crossing pfSense. An honest audit of my own box, the fixes, and the sandbox gotcha that broke a service."
tags: ["security", "hardening", "debian", "linux", "firewall", "home-lab"]
series: ["Hardening Network"]
seriesTitle: "The Debian lab VM"
cover:
  image: "/images/posts/vm-hardening-cover.png"
  alt: "Terminal summary of the VM hardening result"
  hiddenInSingle: true
---

My Debian automation VM already sits behind a pfSense firewall with egress containment — it can reach the internet but not my home network. So why harden the VM itself? Because "behind a firewall" is doing less work than it sounds. Two paths reach *into* the VM without ever crossing pfSense, and an honest audit of my own box turned up drift I didn't expect.

This is the write-up: what the audit found, what I changed, and the systemd sandbox mistake that quietly broke a service.

## pfSense doesn't see everything

The containment rules stop the VM reaching *out* to the home network. But two channels bypass pfSense entirely on the way *in*:

- **The Tailscale tunnel.** Any service bound to `0.0.0.0` is reachable from every device on my tailnet — the encrypted tunnel rides out through allowed egress and back in, invisible to pfSense rules. Today that's just my laptop; if the tailnet or that laptop were compromised, it's a direct line to every open port.
- **The VMware host-only segment.** The Windows host has an adapter on the same host-only network as the VM, so it talks straight to the VM's listeners with no pfSense in the path. Host malware would have the same reach. The shared folders are a second host↔VM channel with the same trust implication.

So the perimeter isn't the whole story. The VM needs its own posture — the same least-privilege logic the lab already runs on, applied one layer in.

## The audit — including my own drift

I started read-only: what's actually listening, what's patched, what's running. It was not all good news.

| Finding | Risk |
|---|---|
| **79 pending security updates**, no automatic updates | Known CVEs sitting unpatched — the biggest single issue |
| **Grafana listening on all interfaces** | My own [earlier post](/posts/prometheus-grafana-observability-stack/) says it's localhost-bound; Grafana's default is `0.0.0.0`, so it wasn't. Reachable from tailnet + host |
| **Apache serving on `*:80`** | A leftover install — the blog deploys to GitHub Pages, nothing local needs it |
| **Docker running, 0 containers, user in `docker` group** | The `docker` group is effectively passwordless root (mount the host FS, become root) — attack surface for nothing in use |
| **MCP hub on `0.0.0.0:8420`, no auth** | Any tailnet/host device could read and write its inbox |
| **No host firewall** (ufw and nftables both disabled) | Nothing filtering inbound at the host level at all |
| CUPS on localhost, SSH on all interfaces | Minor / expected, but worth tightening |

The Grafana one is the point of auditing: I'd *written* that it was localhost-only and believed it. The box disagreed.

## What I changed

### Patch, and keep patching

The updates first, then automate them so this never drifts again:

```bash
apt update && apt full-upgrade
apt install unattended-upgrades
```

```text
# /etc/apt/apt.conf.d/20auto-upgrades
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
```

### Cut the attack surface at the source

Rather than firewall around exposed services, I stopped exposing them:

- **Grafana → localhost.** A drop-in setting `GF_SERVER_HTTP_ADDR=127.0.0.1`, matching the design I'd claimed.
- **Apache, Docker, CUPS → disabled.** All unused. Disabling Docker also removed the root-equivalent `docker` group risk (and, with zero containers, cost nothing). Reversible — a `systemctl enable` away if a future project needs them.
- **MCP hub → bound to the Tailscale IP**, not `0.0.0.0`. It stays reachable from the laptop over the tailnet but disappears from the host-only segment.

### A host firewall, default-deny inbound

Defense-in-depth against both bypass paths, and insurance against the next "oops, bound to 0.0.0.0". SSH and the MCP hub are allowed **only** on the Tailscale interface:

```text
table inet filter {
    chain input {
        type filter hook input priority 0; policy drop;

        iif "lo" accept
        ct state established,related accept
        ct state invalid drop
        ip protocol icmp accept
        ip6 nexthdr ipv6-icmp accept
        udp sport 67 udp dport 68 accept          # DHCP client

        iifname "tailscale0" tcp dport { 22, 8420 } accept
    }
    chain forward { type filter hook forward priority 0; policy drop; }
    chain output  { type filter hook output  priority 0; policy accept; }
}
```

Because I ran this from the VM's own console (not an SSH session), there was no lock-out risk — and the desktop console is always a fallback even if a rule is wrong.

### SSH and brute-force protection

I have no SSH keys set up yet, so disabling password auth would have locked me out. Instead: root login off, tighter limits, and `fail2ban` to blunt brute force while password auth stays on. The firewall already restricts SSH to the tailnet, so the exposure is small.

```text
# /etc/ssh/sshd_config.d/99-hardening.conf
PermitRootLogin no
MaxAuthTries 3
LoginGraceTime 30
X11Forwarding no
```

(Setting up key auth, then flipping `PasswordAuthentication no`, is the next step.)

### Sandbox the custom services

My own long-running daemons (the LaMetric pusher, the MCP hub) got systemd sandboxing — cheap containment if any is ever exploited:

```ini
[Service]
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=read-only
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
```

The hub writes to its inbox, so it also gets `ReadWritePaths=<hub-dir>` to carve write access back for that one path under the otherwise read-only home.

## Troubleshooting: the sandbox that broke the bind

Applying all of the above, the MCP hub came back up — bound to `127.0.0.1`, not the Tailscale IP. So the laptop couldn't reach it.

The cause was a collision between two of my own changes. The hub detects its Tailscale IP at startup by shelling out to `ip addr show tailscale0`. But `ip` talks to the kernel over a **netlink** socket (`AF_NETLINK`) — and my sandbox's `RestrictAddressFamilies` line only allowed `AF_INET`, `AF_INET6`, and `AF_UNIX`. Netlink was blocked, `ip` failed, and the detection fell back to localhost.

The fix was to detect the IP a different way. `tailscale ip -4` asks the local `tailscaled` over a **Unix socket** (`AF_UNIX`) — which the sandbox *does* allow:

```python
for cmd in (["tailscale", "ip", "-4"],                       # AF_UNIX — allowed
            ["ip", "-4", "-o", "addr", "show", "tailscale0"]): # AF_NETLINK — blocked
    ...
```

Prefer the socket that survives the sandbox. A tidy reminder that hardening and functionality can trip over each other — tighten a restriction and something two steps away quietly changes behaviour instead of erroring loudly.

## Where it landed

- **0 pending security updates**, and automatic updates keep it there.
- Grafana on localhost; Apache, Docker and CUPS gone; the MCP hub on the tailnet only.
- A default-deny host firewall with SSH and the hub reachable only over Tailscale.
- Every remaining listener is either localhost or gated to the tailnet by the firewall — the `0.0.0.0:22` socket *looks* exposed, but the firewall only permits it on `tailscale0`.
- The two custom daemons run sandboxed.

None of this replaces the pfSense containment — it complements it. The firewall assumes the perimeter can be bypassed (because two paths do), and the sandboxing assumes a service can be popped. Layers, each doing its own job.

## What's next

- **SSH key auth**, then password auth off entirely.
- **A bearer token on the MCP hub** and a **Tailscale ACL** limiting port 8420 to the one device that needs it — auth on top of the network controls.
- A periodic re-audit, because the Grafana finding proved the gap between "what I documented" and "what the box is doing" is real. The honest check is the one worth repeating.
