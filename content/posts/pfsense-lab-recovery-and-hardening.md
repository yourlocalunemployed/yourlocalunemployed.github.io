---
title: "Debugging a Dead VMware NAT and Hardening My pfSense Containment Lab"
date: 2026-07-02T21:46:00+10:00
draft: false
description: "A Windows update silently re-enabled the hypervisor and killed my VMware lab's networking. The diagnosis, the fix, and the pfSense rebuild — bridged WAN plus egress rules — that came out of it."
tags: ["pfsense", "networking", "security", "vmware", "firewall", "home-lab"]
---

![pfSense dashboard after the rebuild — WAN bridged on 192.168.1.189, LAN on 10.10.0.1, pfSense 2.8.1](/images/posts/pfsense-dashboard.png)

I run my Claude Code work inside a Debian 13 VM (CLAUDDEB) on VMware Workstation Pro 17.6.4, with a pfSense 2.8.1 VM in front of it as a virtual router and firewall. The whole reason pfSense exists in this setup is containment: if something on the Debian VM misbehaves — a prompt injection, a compromised dependency, an agent doing something it shouldn't — it must not be able to reach my PC, my router's admin page, or anything else on the home network.

One day the lab had no internet at all. This post covers both halves of that session: diagnosing an outage that turned out to be the Windows hypervisor's fault, not my configuration, and then rebuilding pfSense's WAN and firewall rules so the design no longer depends on the exact layer that failed.

## The layout

Before, the Debian VM sat on a host-only network that is pfSense's LAN, and pfSense's WAN was a VMware NAT (vmnet8) adapter:

```text
Debian VM (CLAUDDEB)                 pfSense (PfSense secondary)                 Host / Home
  ens33 ── host-only ──►  LAN (em1) ─────────────────── WAN (em0) ── VMware NAT ──► Host ──► Arcadyan ──► Internet
  10.10.0.102/24          10.10.0.1/24                  192.168.62.130/24 (vmnet8)
```

Debian was effectively double-NATed and sat entirely behind pfSense, which got its internet through VMware's NAT service on the host (gateway `192.168.62.2`).

After the rebuild, Debian is unchanged, but pfSense's WAN is bridged straight to the home router:

```text
Debian VM (CLAUDDEB)                 pfSense (PfSense secondary)                 Home
  ens33 ── host-only ──►  LAN (em1) ─────────────────── WAN (em0) ── bridged ──► Arcadyan ──► Internet
  10.10.0.102/24          10.10.0.1/24                  192.168.1.189/24
```

No VMware NAT service in the path at all, and egress firewall rules on the LAN interface stop the Debian VM from reaching any private network range. How I got there is the rest of the post.

## Part 1 — the outage

Resuming the VMs from suspend as usual, the Debian VM had no internet. Both VMs still pinged each other fine, and each VM said it was "connected", but nothing external worked.

### Working outward from the VM

I followed the packet path outward, splitting the problem at each layer.

**pfSense gateway status (System > Routing > Gateways).** WAN_DHCP showed a valid gateway (`192.168.62.2`) and a green "online" marker. That ruled out a dead route at the routing-table level — but "online" only means gateway monitoring can ping the next hop, not that traffic actually flows through it.

**A firewall notice about the bogon table.** pfSense reported the ruleset had failed to load:

```text
There were error(s) loading the rules: cannot define table bogonsv6:
Cannot allocate memory - table <bogonsv6> persist file "/etc/bogonsv6"
```

This was a real problem: on resume, pf couldn't allocate a contiguous block big enough for the huge bogonsv6 table, so the whole ruleset aborted. Fixed by disabling **Block bogon networks** on WAN (the WAN was a private NAT address, so bogon filtering there blocks nothing useful anyway) and giving the VM more RAM headroom. A genuine fix — but, it turned out, not the root cause of the outage.

**Routing table (Diagnostics > Routes).** Default route `0.0.0.0 → 192.168.62.2` via em0 was present and correct. pfSense's own routing was fine.

**DNS lookup from pfSense (Diagnostics > DNS Lookup).** The key clue. A lookup of `google.com` against the VMware NAT DNS proxy (`192.168.62.2`) answered in 3 ms, while pfSense's own Unbound resolver (`127.0.0.1`) timed out at ~10 seconds. So DNS *could* work through one specific path but not through the resolver.

**From the Debian VM.** `curl` failed with `Could not resolve host` — a DNS failure, not a connectivity failure. `ping 8.8.8.8` failed with 100% loss. Debian's own config was clean: single NIC `10.10.0.102/24`, correct default route via `10.10.0.1`, nameserver `10.10.0.1`.

**Narrowing DNS from Debian:**

```bash
dig pfSense.peas.arpa @10.10.0.1   # answers instantly (Unbound serving a local record)
dig +tcp google.com @10.10.0.1     # answers over TCP
dig google.com @10.10.0.1          # SERVFAIL over UDP
nc -zvu 10.10.0.1 53               # port 53 open
```

Unbound was alive and reachable, TCP worked, but recursive resolution of external names failed. Switching Unbound to forwarding mode (DNSSEC off) and pointing it at upstream servers still returned instant SERVFAIL.

### The decisive test

A direct `host google.com 192.168.62.2` from pfSense itself now timed out — the same NAT DNS proxy that had answered in 3 ms earlier was now dead. And a raw TCP test from Debian, `curl -v https://1.1.1.1`, timed out too. So it wasn't just DNS or just ICMP — **all traffic (TCP, UDP, ICMP) crossing the VMware NAT device was failing**, while everything local to each VM kept working.

### Root cause: the Windows hypervisor

The pattern — everything through the VMware NAT path dead, everything local fine, and the failure surviving multiple full host reboots — pointed at the host, not the lab config. On the Windows host:

```powershell
Get-CimInstance Win32_ComputerSystem | Select-Object HypervisorPresent
# True

Get-WindowsOptionalFeature -Online | Where-Object {$_.State -eq "Enabled" -and $_.FeatureName -match "Hyper|Hypervisor|VirtualMachinePlatform|WindowsHypervisorPlatform|WSL"}
# VirtualMachinePlatform   Enabled
# HypervisorPlatform       Enabled
```

The Windows hypervisor (VBS / Virtualization-Based Security) was active. When it runs, it takes ownership of the network stack in a way that breaks VMware Workstation's NAT forwarding. VMware's NAT and DHCP services still showed as "Running" and the vmnet8 adapter showed "Up" — which is exactly why every check looked healthy while nothing actually forwarded. It survived reboots because the feature was *enabled*, not merely wedged — almost certainly flipped on silently by a Windows update, which explains why the lab worked fine until that day.

Proxy settings, hosts file, WFP filters, services and Run keys on the host were all checked and clean, which is what confirmed the hypervisor as the cause rather than malware or a rogue filter.

### The fix

`bcdedit /set hypervisorlaunchtype off` alone was not enough — VBS re-launched the hypervisor regardless. The working fix was to disable the underlying features:

```powershell
reg add "HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard" /v EnableVirtualizationBasedSecurity /t REG_DWORD /d 0 /f
reg add "HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity" /v Enabled /t REG_DWORD /d 0 /f
Disable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -NoRestart
Disable-WindowsOptionalFeature -Online -FeatureName HypervisorPlatform -NoRestart
bcdedit /set hypervisorlaunchtype off
```

Plus turning **Memory Integrity** off in Windows Security → Device security → Core isolation. After a reboot:

```powershell
Get-CimInstance Win32_ComputerSystem | Select-Object HypervisorPresent
# False
```

With the hypervisor out of the way, connectivity came straight back: `ping 8.8.8.8` from Debian returned 0% loss, and `curl -I https://google.com` returned `HTTP/2 301`.

### A self-inflicted detour worth recording

Midway through, while trying things, the Debian VM's network adapter got switched from host-only to NAT while the VM was running. The VMware log confirmed it with a timestamp (`ConfigDB: Setting ethernet0.connectionType = "nat"`). That put Debian on the wrong subnet entirely and had to be reverted back to host-only in the `.vmx` file before anything else could work. Lesson: don't change a running VM's adapter mid-diagnosis.

## Part 2 — hardening: bridged WAN + egress rules

Even fixed, the NAT-based WAN had two downsides for a containment lab: it depended on the fragile VMware NAT layer (the exact thing that had just failed), and re-enabling Windows Memory Integrity would break it again. Switching to a bridged WAN removes both problems.

### Why bridged doesn't weaken isolation

The security property I care about is **egress control**: the Debian VM should reach the internet but must not be able to initiate connections into my home network. That property is enforced by firewall rules on pfSense's LAN interface — not by whether pfSense's WAN is NAT or bridged. Bridged just means pfSense's WAN gets a real home-LAN address instead of a VMware-NAT address; Debian still sits behind pfSense on the host-only side, still firewalled. The responsibility moves cleanly onto the egress rules, which is where it should be.

### Switching the WAN to bridged

- In VMware's Virtual Network Editor, set the bridged network (VMnet0) to bridge to the actual physical adapter explicitly rather than "Automatic".
- With the pfSense VM powered off, changed `ethernet0.connectionType` from `"nat"` to `"bridged"` in `PfSense secondary.vmx`.
- Booted pfSense. WAN (em0) pulled a DHCP lease directly from the Arcadyan router: `192.168.1.189/24`. LAN (em1) unchanged at `10.10.0.1/24`.
- Verified pfSense itself had internet (Diagnostics > Ping → 8.8.8.8, source WAN: 0% loss).

Home subnet is therefore `192.168.1.0/24`, with the router as the gateway.

### RFC1918 alias

One alias to represent all private address space, under **Firewall > Aliases > IP**:

| Name | Type | Networks |
|------|------|----------|
| `RFC1918` | Network(s) | `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` |

The `192.168.0.0/16` entry covers the home subnet (`192.168.1.0/24`), so this single alias blocks the Arcadyan router, the host PC, and every other home device at once.

### LAN firewall rules

**Firewall > Rules > LAN**, in evaluation order (first match wins, top to bottom):

| # | Action | Source | Destination | Purpose |
|---|--------|--------|-------------|---------|
| 1 | (Anti-Lockout — pfSense managed) | * | LAN Address :443,80,22 | Guarantees web UI access to pfSense |
| 2 | Pass | LAN subnets | LAN address | Lets the VM reach pfSense for DNS / gateway |
| 3 | Block | LAN subnets | `RFC1918` (alias) | Blocks the VM from all private/home ranges |
| 4 | Pass | LAN subnets | any | Internet access (all private space already denied above) |

The ordering is the whole point: DNS-to-pfSense is allowed first, then all private-range traffic is dropped, then everything else (the public internet) is allowed. An agent on the Debian VM can reach out to the internet but cannot reach back into the home network.

The IPv6 default-allow rule was left in place for now since the VM operates over IPv4; it can be disabled later for completeness.

### Verification from the Debian VM

```bash
curl -I https://google.com      # internet     -> HTTP/2 301  (works)
dig google.com @10.10.0.1       # DNS          -> resolves    (works)
ping -c2 <router>               # Arcadyan     -> times out   (blocked)
ping -c2 192.168.1.189          # pfSense WAN  -> times out   (blocked)
```

Win condition met: internet and DNS work; anything on the home subnet is unreachable. Containment proven. The dashboard screenshot at the top of this post is the final state — WAN bridged on `192.168.1.189` (pulled from the Arcadyan), LAN on `10.10.0.1`, both interfaces up at 1000baseT full-duplex, system on 2.8.1-RELEASE and healthy.

## Outcome

- Internet on the Debian VM restored — root cause was the Windows hypervisor / VBS breaking VMware NAT, not the lab configuration.
- pfSense WAN moved from NAT to bridged, removing the dependency on VMware's NAT service and making the lab immune to that whole class of host-hypervisor problem.
- Egress rules added so the Debian VM is contained: internet-out allowed, connections into the home network blocked.
- Because the WAN no longer relies on VMware NAT, Windows Memory Integrity / VBS can be re-enabled on the host without breaking the lab.

## Habits going forward

- After Windows updates, re-check `Get-CimInstance Win32_ComputerSystem | Select HypervisorPresent`. If it flips back to `True`, VBS was re-enabled — with the bridged WAN this no longer breaks the lab, but it's worth knowing.
- Shut the VMs down rather than suspending them. Suspend/resume of a router VM is what kept triggering clock skew and NAT problems.
- Start pfSense first and let it fully boot before starting the Debian VM, so the DHCP lease is always available.
- Both `.vmx` files had `tools.syncTime = "FALSE"`, which lets the guest clock drift after suspend and can cause DNSSEC/NTP problems. Enabling time sync (or just not suspending) avoids this.

## Caveat on the threat model

This setup contains an agent's *network* access — it stops a prompt-injected or misbehaving process on the Debian VM from reaching the home network. It is not a guarantee against a determined VM-escape (hypervisor breakout) exploit; VMware has had such vulnerabilities historically. For network-level prompt-injection containment the design is solid. Defending against escape as well would mean a separate physical machine or a disposable cloud instance, which is a larger scope.
