---
title: "Debugging a Dead VMware NAT and Hardening My pfSense Containment Lab"
date: 2026-07-02T21:46:00+10:00
draft: false
description: "A Windows update silently re-enabled the hypervisor and killed my VMware lab's networking. The diagnosis, the fix, and the pfSense rebuild — bridged WAN plus egress rules — that came out of it."
tags: ["pfsense", "networking", "security", "vmware", "firewall", "home-lab"]
series: ["Home Lab"]
seriesTitle: "pfSense containment lab"
cover:
  image: "/images/posts/pfsense-dashboard.png"
  alt: "pfSense dashboard after the rebuild"
  hiddenInSingle: true
---

![pfSense dashboard after the rebuild — WAN bridged on 192.168.1.189, LAN on 10.10.0.1, pfSense 2.8.1](/images/posts/pfsense-dashboard.png)

I run my Claude Code work inside a Debian 13 VM (CLAUDDEB) on VMware Workstation Pro 17.6.4, with a pfSense 2.8.1 VM in front of it as a virtual router and firewall. pfSense exists in this setup for containment: if something on the Debian VM misbehaves — a prompt injection, a compromised dependency — it must not be able to reach my PC, my router's admin page, or anything else on the home network.

One day the lab had no internet at all. This post covers both halves of that session: diagnosing an outage that turned out to be the Windows hypervisor's fault, and rebuilding pfSense's WAN and firewall rules so the design no longer depends on the layer that failed.

## The layout

Before — Debian on a host-only network (pfSense's LAN), pfSense's WAN on VMware NAT:

```text
Debian VM (CLAUDDEB)                 pfSense (PfSense secondary)                 Host / Home
  ens33 ── host-only ──►  LAN (em1) ─────────────────── WAN (em0) ── VMware NAT ──► Host ──► Arcadyan ──► Internet
  10.10.0.102/24          10.10.0.1/24                  192.168.62.130/24 (vmnet8)
```

After — Debian unchanged, pfSense's WAN bridged straight to the home router:

```text
Debian VM (CLAUDDEB)                 pfSense (PfSense secondary)                 Home
  ens33 ── host-only ──►  LAN (em1) ─────────────────── WAN (em0) ── bridged ──► Arcadyan ──► Internet
  10.10.0.102/24          10.10.0.1/24                  192.168.1.189/24
```

No VMware NAT service in the path, and egress rules on the LAN interface block the Debian VM from every private range.

## Part 1 — the outage

After resuming the VMs from suspend, the Debian VM had no internet. Both VMs pinged each other fine and reported "connected", but nothing external worked. I followed the packet path outward, splitting the problem at each layer:

- **Gateway status** (System > Routing > Gateways): WAN_DHCP showed its gateway (`192.168.62.2`) online — but "online" only means gateway monitoring can ping the next hop, not that traffic flows.
- **A firewall notice** showed the ruleset had failed to load:

  ```text
  There were error(s) loading the rules: cannot define table bogonsv6:
  Cannot allocate memory - table <bogonsv6> persist file "/etc/bogonsv6"
  ```

  On resume, pf couldn't allocate a block large enough for the bogonsv6 table, aborting the whole ruleset. Fixed by disabling **Block bogon networks** on WAN (pointless on a private NAT address anyway) and adding RAM headroom. A real fix — but not the root cause.
- **Routing table**: default route `0.0.0.0 → 192.168.62.2` via em0 present and correct.
- **DNS from pfSense** — the key clue: a lookup against the VMware NAT DNS proxy (`192.168.62.2`) answered in 3 ms, while pfSense's own Unbound resolver timed out.
- **From the Debian VM**: `curl` failed with `Could not resolve host`; `ping 8.8.8.8` lost 100%. Debian's own config was clean. Narrowing DNS:

  ```bash
  dig pfSense.peas.arpa @10.10.0.1   # answers instantly (local record)
  dig +tcp google.com @10.10.0.1     # answers over TCP
  dig google.com @10.10.0.1          # SERVFAIL over UDP
  nc -zvu 10.10.0.1 53               # port 53 open
  ```

  Unbound was alive, TCP worked, but external recursion failed — even in forwarding mode with DNSSEC off.

### The decisive test

A direct `host google.com 192.168.62.2` from pfSense now timed out — the same NAT DNS proxy that had answered in 3 ms earlier. A raw TCP test from Debian (`curl -v https://1.1.1.1`) timed out too. **All traffic crossing the VMware NAT device was failing — TCP, UDP and ICMP — while everything local kept working.**

### Root cause: the Windows hypervisor

That pattern, surviving multiple full host reboots, pointed at the host:

```powershell
Get-CimInstance Win32_ComputerSystem | Select-Object HypervisorPresent
# True

Get-WindowsOptionalFeature -Online | Where-Object {$_.State -eq "Enabled" -and $_.FeatureName -match "Hyper|Hypervisor|VirtualMachinePlatform|WindowsHypervisorPlatform|WSL"}
# VirtualMachinePlatform   Enabled
# HypervisorPlatform       Enabled
```

The Windows hypervisor (VBS / Virtualization-Based Security) was active. When it runs, it takes ownership of the network stack in a way that breaks VMware Workstation's NAT forwarding — while VMware's NAT and DHCP services still show "Running" and vmnet8 shows "Up", which is why every check looked healthy. It survived reboots because the feature was *enabled*, almost certainly flipped on silently by a Windows update. Host proxy settings, hosts file, WFP filters, services and Run keys were all checked clean, ruling out malware.

### The fix

`bcdedit /set hypervisorlaunchtype off` alone wasn't enough — VBS re-launched the hypervisor. Disabling the underlying features worked:

```powershell
reg add "HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard" /v EnableVirtualizationBasedSecurity /t REG_DWORD /d 0 /f
reg add "HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity" /v Enabled /t REG_DWORD /d 0 /f
Disable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -NoRestart
Disable-WindowsOptionalFeature -Online -FeatureName HypervisorPlatform -NoRestart
bcdedit /set hypervisorlaunchtype off
```

Plus **Memory Integrity** off in Windows Security → Core isolation. After a reboot, `HypervisorPresent` returned `False` and connectivity came straight back: 0% loss to `8.8.8.8`, and `curl -I https://google.com` returned `HTTP/2 301`.

One self-inflicted detour worth recording: mid-diagnosis, the Debian VM's adapter got switched from host-only to NAT while running (the VMware log confirmed it: `ConfigDB: Setting ethernet0.connectionType = "nat"`), putting it on the wrong subnet entirely. Don't change a running VM's adapter mid-diagnosis.

## Part 2 — hardening: bridged WAN + egress rules

Even fixed, the NAT-based WAN had two problems for a containment lab: it depended on the fragile VMware NAT layer, and re-enabling Windows Memory Integrity would break it again. A bridged WAN removes both.

Bridging doesn't weaken isolation. The security property is **egress control** — the Debian VM reaches the internet but cannot initiate connections into the home network — and that's enforced by firewall rules on pfSense's LAN interface, not by the WAN type. The responsibility moves onto the egress rules, where it belongs.

### The changes

1. **Switched pfSense WAN to bridged.** Set VMware's bridged network to the physical adapter explicitly, changed `ethernet0.connectionType` from `"nat"` to `"bridged"` in the `.vmx` with the VM off, and let WAN pull a DHCP lease from the home router (`192.168.1.189/24`). LAN unchanged at `10.10.0.1/24`. Home subnet is therefore `192.168.1.0/24`, with the router as the gateway.
2. **Created an RFC1918 alias** covering all private address space (Firewall > Aliases > IP):

   | Name | Type | Networks |
   |------|------|----------|
   | `RFC1918` | Network(s) | `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` |

3. **LAN firewall rules** (first match wins, top to bottom):

   | # | Action | Source | Destination | Purpose |
   |---|--------|--------|-------------|---------|
   | 1 | (Anti-Lockout — pfSense managed) | * | LAN Address :443,80,22 | Guarantees web UI access |
   | 2 | Pass | LAN subnets | LAN address | DNS / gateway access to pfSense |
   | 3 | Block | LAN subnets | `RFC1918` (alias) | Blocks all private/home ranges |
   | 4 | Pass | LAN subnets | any | Internet access |

   The ordering is the point: DNS-to-pfSense allowed first, all private-range traffic dropped, then the public internet allowed. An agent on the Debian VM can reach out but cannot reach back in.

### Verification from the Debian VM

```bash
curl -I https://google.com      # internet     -> HTTP/2 301  (works)
dig google.com @10.10.0.1       # DNS          -> resolves    (works)
ping -c2 <router>               # Arcadyan     -> times out   (blocked)
ping -c2 192.168.1.189          # pfSense WAN  -> times out   (blocked)
```

Internet and DNS work; everything on the home subnet is unreachable. Containment proven. The dashboard screenshot at the top shows the final state — WAN bridged, LAN on `10.10.0.1`, both interfaces up at 1000baseT full-duplex.

## Outcome and habits

- Root cause was the Windows hypervisor breaking VMware NAT — not the lab configuration.
- The bridged WAN removes the VMware NAT dependency entirely, so Memory Integrity / VBS can be re-enabled on the host without breaking the lab.
- After Windows updates, re-check `HypervisorPresent` — with the bridged WAN it no longer matters, but it's worth knowing.
- Shut VMs down rather than suspending them; suspend/resume of a router VM kept triggering clock skew and NAT problems. Start pfSense first so the DHCP lease is always ready.
- Both `.vmx` files had `tools.syncTime = "FALSE"`, which lets guest clocks drift after suspend and can break DNSSEC/NTP.

## Threat model caveat

This setup contains an agent's *network* access — a prompt-injected or misbehaving process on the Debian VM can't reach the home network. It is not a guarantee against a determined VM-escape exploit; VMware has had such vulnerabilities historically. For network-level containment the design is solid; defending against escape as well would mean a separate physical machine or a disposable cloud instance.
