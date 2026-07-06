---
title: "Adding Real WAN Throughput to My LaMetric Display: pfSense Over SNMP"
date: 2026-07-06
draft: false
tags: ["homelab", "pfsense", "snmp", "networking", "mqtt", "lametric", "python", "monitoring", "security"]
categories: ["Home Lab"]
summary: "My LaMetric display already showed my Debian box's stats. This is how I pulled real WAN throughput straight off my pfSense firewall over SNMP — turning 'a VM's stats' into 'my network's stats' — including the counter that proves it works and every gotcha in between."
---

In my [last post](/lametric-mqtt-homelab/) I got a LaMetric Time display showing live health from my home lab, delivered over MQTT so it worked across my network isolation. It showed CPU, memory, disk, the automation VM's own network traffic, uptime — all collected from a single Debian box.

Useful, but it was really *that box's* stats. The frame I actually wanted was the one the display was named for: my **network's** throughput. The traffic crossing my firewall. That data doesn't live on the Debian box — it lives on pfSense. So this is the follow-up: reaching into pfSense over SNMP to pull real WAN in/out rates and put them on the display.

This one is shorter than the MQTT build because the pipeline already existed. All I'm adding is a new data source. But the "how do I get numbers *out of pfSense*" part has enough sharp edges to be worth writing down.

## The setup, and why this one is reachable

Quick recap of the relevant topology. My automation VM (I call it CLAUDDEB) sits *behind* a virtual pfSense firewall in my lab. That firewall is CLAUDDEB's gateway, and it enforces RFC1918 containment rules that stop the VM from reaching the rest of my home network.

Here's the important distinction that makes this project possible: **CLAUDDEB can't reach *across* pfSense to other segments, but it can absolutely reach pfSense *itself*.** Querying your own default gateway isn't the same as routing through it to somewhere you're not allowed. So SNMP from CLAUDDEB to the firewall's LAN interface is fair game, even though CLAUDDEB can't (for example) reach the LaMetric on the guest network. The isolation blocks lateral movement; it doesn't blind a host to its own gateway.

That's the whole reason the WAN-throughput frame is achievable without weakening anything.

## The tools, and what each one is for

**SNMP (Simple Network Management Protocol)** — the standard way network gear exposes operational data (interface counters, uptime, system info) for polling. It's how you ask a router "how many bytes has this interface moved?" without logging into it. Purpose here: the read path into pfSense.

**pfSense's SNMP service (bsnmpd)** — the SNMP daemon built into pfSense, toggled under *Services → SNMP*. Purpose: it publishes the firewall's stats over SNMP so something on the network can poll them.

**IF-MIB interface counters** — the specific data I'm after. Two OIDs matter: `ifName` (to map a human interface name to its numeric SNMP index) and `ifHCInOctets` / `ifHCOutOctets` — the 64-bit byte counters for traffic in and out of an interface. Purpose: the raw numbers that become WAN throughput.

**64-bit ("HC", high-capacity) counters** — worth calling out on their own. The original 32-bit octet counters wrap around every few seconds on a fast link, which wrecks any rate calculation. The HC variants are 64-bit and don't realistically wrap, so throughput math stays sane. Purpose: correctness at speed.

**net-snmp client tools (`snmpwalk`, `snmpget`)** — the command-line SNMP clients on the Debian side (`sudo apt install snmp`). Purpose: my collector shells out to these to query pfSense, rather than pulling in a heavyweight Python SNMP library. Rock-solid and easy to test by hand.

The MQTT pipeline, the Python publisher, and the systemd service from the first build are all reused unchanged — the new WAN data just rides the same rails to the display.

## Configuring pfSense

This is the part that's entirely in the pfSense web UI, and it's quick.

**Enable SNMP** — *Services → SNMP*:

- Tick **Enable**.
- Set a **Community String**. Do not leave it as `public` — that's the SNMP equivalent of leaving the default password. I used a non-default, read-only-flavored name.
- Under **Interface Binding**, bind the daemon to the **LAN** interface — the side my VM reaches. **Never bind SNMP to WAN**; you don't want the firewall answering SNMP queries from the internet.
- Make sure the **MibII** module is enabled. That's the one carrying the interface counters I need; without it the `ifHC*` OIDs return nothing.

**Firewall rule** — because my LAN rules are restrictive (RFC1918 containment), I had to make sure traffic from CLAUDDEB to the pfSense LAN IP on **UDP 161** was permitted. Querying the firewall's own interface is often allowed by default, but if your SNMP test times out, this is the first thing to add.

**Identify the WAN interface** — *Interfaces → WAN* shows the underlying device name in parentheses next to the assignment. Mine turned out to be `em0`. This matters because SNMP identifies interfaces by an index number, and I need to point the collector at the *right* one — getting it backwards would label LAN traffic as WAN.

## The collector

The Python side does three things: resolve the WAN interface's SNMP index by name, read its two HC octet counters a second apart, and turn the delta into Mbps. Resolving by *name* (rather than hard-coding an index) means it survives the index shuffling around if interfaces change.

```python
def collect_pfsense(host, community, wan_iface, interval=1.0):
    result = {"reachable": False, "wan_rx_mbps": None, "wan_tx_mbps": None}

    # sysUpTime doubles as a reachability probe
    uptime = _snmp(["snmpget", "-v2c", "-c", community, "-Oqv",
                    "-t", "2", "-r", "1", host, _OID_SYSUPTIME])
    result["reachable"] = uptime is not None
    if not (wan_iface and result["reachable"]):
        return result

    idx = _resolve_ifindex(host, community, wan_iface)   # walk ifName, match, cache
    if not idx:
        return result

    in0  = _snmp_counter(host, community, f"{_OID_IFHCIN}.{idx}")
    out0 = _snmp_counter(host, community, f"{_OID_IFHCOUT}.{idx}")
    time.sleep(interval)
    in1  = _snmp_counter(host, community, f"{_OID_IFHCIN}.{idx}")
    out1 = _snmp_counter(host, community, f"{_OID_IFHCOUT}.{idx}")

    to_mbps = lambda d: max(d, 0) * 8 / 1e6 / interval
    result["wan_rx_mbps"] = to_mbps(in1 - in0)
    result["wan_tx_mbps"] = to_mbps(out1 - out0)
    return result
```

The index lookup walks `ifName` (falling back to `ifDescr`), finds the entry whose value matches the configured interface, and pulls the index off the end of the OID — then caches it so it only does that once. If SNMP is unreachable, every path returns `None` and the display frame shows `WAN DL ?` instead of the service crashing. Config is three lines in the existing `.env`:

```bash
PFSENSE_SNMP_HOST=<pfsense-lan-ip>
PFSENSE_SNMP_COMMUNITY=<your-community>
PFSENSE_WAN_IFACE=em0
```

## The process, and the one test that proves it all

After enabling SNMP on pfSense and `apt install snmp` on the VM, the single most useful command was walking the interface-name table — because it does double duty. If it returns anything, SNMP + firewall + community are all working; and its output *is* the list of interface names I need to identify WAN from:

```bash
snmpwalk -v2c -c <community> <pfsense-ip> 1.3.6.1.2.1.31.1.1.1.1
```

```
...1.1 = STRING: "em0"      <- physical
...1.2 = STRING: "em1"      <- physical
...1.3 = STRING: "enc0"     <- IPsec (virtual)
...1.4 = STRING: "lo0"      <- loopback
...1.5 = STRING: "pflog0"   <- pf logging
...1.6 = STRING: "pfsync0"  <- state sync
...1.7 = STRING: "ovpns1"   <- OpenVPN server
```

Only `em0` and `em1` are real NICs; the rest are internal. The pfSense UI confirmed `em0` is WAN, so that went into `PFSENSE_WAN_IFACE`.

Then, to *prove* the counter actually reflects WAN traffic before trusting the display, I ran two terminals on the VM: one generating a sustained download, the other polling the raw in-octets counter for `em0` (ifIndex 1, so the OID ends in `.6.1`):

```bash
# terminal 2 — watch em0's byte counter every 2s
for i in $(seq 5); do
  snmpget -v2c -c <community> <pfsense-ip> 1.3.6.1.2.1.31.1.1.1.6.1
  sleep 2
done
```

```
Counter64: 2940747473
Counter64: 3004631778
Counter64: 3078975251
Counter64: 3156804718
Counter64: 3215876127
```

Each 2-second step jumps ~64 million bytes. Do the arithmetic — 64 MB ÷ 2 s × 8 bits ≈ **256 Mbps** of real WAN traffic, live, straight off the firewall's counter. That's the moment it went from "I think this works" to "this works."

Last step was on the LaMetric app itself: it was built for 9 frames, so it capped there and hid the two new WAN frames. Same fix as always — edit the app in DevZone, bump it to 11 frames, republish, and force the device to re-pull (the app's info action, or remove/re-add it). Then WAN DL / WAN UL joined the rotation.

## The gotchas

The parts that cost me time:

- **Running the wrong copy of the script.** My first test showed the old reachability frame and no WAN numbers — because I'd dropped the updated script into a *second* folder while the service still ran the original. One project, one directory; verify what's actually running (`grep` for a string only the new version has) before you trust a test. This is a boring lesson that keeps being true.
- **Zero movement during a download — twice fooled.** The WAN frame sat at `0.0 Mb` while I "downloaded something." Two separate reasons: first, the download was on a *different* machine, so it never crossed *this* firewall at all; second, even a real download on the VM finished between sample windows. The collector reads one second out of every sixty, so only **sustained** traffic registers. A small file is invisible to it.
- **DNS in the contained environment.** My first test download host wouldn't resolve — the VM's outbound name resolution is limited by design. I just used a Debian mirror I knew it could already reach (it's where the packages come from).
- **Which WAN is this, really?** The big conceptual one. The pfSense my VM sits behind is my *lab* firewall — its "WAN" is the boundary of my isolated lab segment, not my household internet uplink. So this frame reports traffic crossing *that* boundary, not my whole house's usage. For a lab display that's arguably the more interesting number, but it's important to know exactly what you're looking at.

## A caveat worth stating

Because it samples one second per minute, the WAN frame is a **spot reading, not a continuous meter** — bursts between samples don't show up, and it should never be mistaken for traffic accounting. It answers "is the link busy right now?" at a glance, and that's all it's meant to do. If I ever want a true interval average, the cleaner approach is to diff the counters across the full 60-second publish cycle instead of a 1-second sub-sample. Easy change; I just haven't needed it.

## Security notes

Nothing here opened an attack surface, which was the point:

- SNMP is **read-only** and uses a **non-default community string**, so at worst it leaks stats to something already on my LAN.
- The daemon is bound to **LAN only** — SNMP is never exposed to the WAN/internet, which would be the classic mistake.
- The VM querying its own gateway stays entirely inside the isolation model — no lateral reach into other segments, no firewall holes, no port-forwards.

## The result

The display now cycles a `WAN DL` and `WAN UL` frame showing real megabits per second in and out of my lab firewall, pulled over SNMP from a device my automation VM isn't even allowed to route *through* — only to. Combined with the existing frames it's a genuine at-a-glance board for the whole segment: the VM's own health on one side, the network boundary's throughput on the other.

The broader lesson from this one is small but useful: **the data you want often isn't on the box you're standing on.** SNMP is the boring, universal, decades-old answer to "let me read stats off that other device," and it's worth being comfortable with — every switch, router, firewall, and NAS you'll ever touch speaks it. Once the WAN counters were flowing, the display finally lived up to its name.
