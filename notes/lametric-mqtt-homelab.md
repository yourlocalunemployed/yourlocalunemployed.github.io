---
title: "Piping Home-Lab Stats to a LaMetric Display Over MQTT (Without Breaking Network Isolation)"
date: 2026-07-05
draft: false
tags: ["homelab", "mqtt", "lametric", "pfsense", "networking", "python", "iot", "hivemq", "debian", "security"]
categories: ["Home Lab"]
summary: "I wanted my LaMetric Time to show live health from my isolated home lab. The catch: the display and the box publishing the data can't reach each other on the LAN — by design. Here's how I used an MQTT broker as a rendezvous point to bridge two deliberately-unreachable hosts without poking a single hole in the isolation."
---

I picked up a LaMetric Time — one of those little 8x37 pixel smart displays — and after locking it down on an isolated guest network, the obvious next move was to make it *useful*: put live health from my home lab on it. CPU, memory, network throughput, the stuff I actually want to glance at.

Simple idea. The interesting part is that making it work meant respecting a constraint I'd deliberately built into my network, and that constraint ended up dictating the whole architecture. This is the writeup of that build: the design decision, the tools, the pipeline, and every gotcha I hit — because the gotchas are the useful part.

## The setup, and the constraint that shaped everything

My lab runs on VMware Workstation on a Windows host. The relevant pieces:

- **CLAUDDEB** — a Debian 13 (Trixie) VM that does automation work. It sits *behind* a virtual pfSense firewall with RFC1918 rules that block it from reaching my home LAN. It gets outbound internet and nothing else. No inbound. It can't reach my home network devices, and it can't reach the guest network.
- **The LaMetric** — lives on an isolated guest SSID (WPA3, client isolation on). It can reach the internet outbound and that's it. It can't see my main LAN, and my LAN can't see it.

So here's the problem in one sentence: **the box that produces the data (CLAUDDEB) and the device that displays it (the LaMetric) are on two networks that cannot reach each other on the LAN — on purpose.** That isolation is a feature, not a bug, and I wasn't about to weaken it just to show a CPU percentage.

That single fact killed the obvious approach before I even started.

## Why the obvious approach doesn't work

LaMetric's indicator apps support a few delivery methods. When you create one in their developer portal (DevZone), you pick a communication type: **Local Push, Poll, MQTT, or Web Socket**.

The tutorials all reach for **Local Push** — you POST a little JSON blob straight to the device's IP on the local network. Fast, simple, and completely useless to me: it requires the pushing host to reach the device on the LAN, which is exactly what my isolation forbids. (The old cloud HTTP-push endpoint that some older guides mention has since been folded into LaMetric's "My Data DIY" app, which is also local-network only.)

So local/HTTP push was out. What's left are the methods where the **device reaches outward** rather than being reached:

| Method | How it works | Fits my isolation? |
|---|---|---|
| Local Push | You POST to the device IP on the LAN | ❌ needs LAN reachability |
| Poll | Device fetches a URL on a schedule | ⚠️ needs a public URL I'd have to host/expose |
| **MQTT** | Device *subscribes* to a broker; I *publish* to it | ✅ both sides connect **outbound** |
| Web Socket | Device connects to a WS server | ⚠️ needs a hosted WS endpoint |

**MQTT was the clean winner.** In a pub/sub model, both the LaMetric and CLAUDDEB open *outbound* connections to a broker sitting out on the internet and meet in the middle. Neither device ever accepts an inbound connection. Neither has to reach the other on the LAN. The isolation stays 100% intact, and I get near-real-time updates as a bonus.

It's the same principle my whole lab already runs on — everything connects *out* to a rendezvous point — so MQTT wasn't a workaround bolted on top of the design. It *was* the design, extended one hop further.

## The architecture

```
  CLAUDDEB (Debian, behind pfSense)          LaMetric (isolated guest Wi-Fi)
  ────────────────────────────────           ──────────────────────────────
   psutil collectors                                  subscribes to
   → build frames JSON                                labmetric/home/stats
   → paho-mqtt publish  ──┐                    ┌──►   renders frames
     (TLS 8883, QoS1,     │                    │
      retain=true)        │                    │
                          ▼                    │
                 ┌─────────────────────────────┴──┐
                 │      HiveMQ Cloud broker        │
                 │  (TLS, topic-based pub/sub)     │
                 └─────────────────────────────────┘
                   outbound-only from both sides
```

Data flows one way: CLAUDDEB gathers stats, formats them as LaMetric's native `{"frames":[...]}` payload, and publishes to a topic. The broker holds the message. The LaMetric, subscribed to that same topic, receives it and paints the frames. Nobody port-forwards anything.

## The tools, and what each one is actually for

**HiveMQ Cloud (Serverless free tier)** — the MQTT broker; the rendezvous point. I used the permanently-free serverless plan (no credit card). It exposes TLS-only MQTT on port 8883. Its **Access Management** is where I created credentials, and its **"Test your connection"** web client turned out to be the single most useful debugging tool of the whole project (more on that below).

**MQTT** — the messaging protocol itself. Lightweight publish/subscribe, purpose-built for exactly this: decoupled endpoints that don't know or care about each other's location, only sharing a topic name. The decoupling is what makes it fit isolated networks so naturally.

**LaMetric DevZone** — where I built the on-device "indicator app." This defines what the LaMetric subscribes to and how it renders incoming data. Communication type **MQTT**, TLS on, a topic, a subscribe-only credential, and data format set to **Predefined (LaMetric Format)** so it expects the native frames JSON.

**paho-mqtt** (Python) — the MQTT client library CLAUDDEB uses to publish. Handles the TLS handshake, auth, connection lifecycle, and QoS.

**psutil** (Python) — cross-platform system stats. Feeds the CPU / RAM / disk / uptime / network-IO frames with a couple of lines each.

**Python venv** — an isolated environment for the project's dependencies. Debian 13 enforces [PEP 668](https://peps.python.org/pep-0668/), so you can't `pip install` into the system Python anymore; a venv is the correct answer (and it's what the service points at).

**systemd** — runs the publisher as a persistent background service that survives reboots, instead of a cron job that reconnects every cycle. A long-lived MQTT connection is the idiomatic pattern.

**`/proc/net/tcp`** — I count established TCP connections by parsing this directly, which needs no root, rather than reaching for privileged socket enumeration.

**TLS (Let's Encrypt CA)** — everything to the broker is encrypted in transit. HiveMQ presents a publicly-trusted cert, so the client validates it against Debian's system CA store with zero extra config.

## Standing up the broker

Deploying the HiveMQ serverless cluster was a couple of clicks. The part worth calling out is credentials, where I went **least-privilege on purpose**:

- A **subscribe-only** user → lives on the LaMetric. The display only ever *receives*, so that's all the permission it gets.
- A **publish-only** user → lives in the script's config on CLAUDDEB. The publisher only ever *sends*.

Splitting them means a leak of either credential can't be used to do the other side's job. It's a small thing, but it's the kind of small thing that makes a project a portfolio piece instead of a hack.

> Security note: everywhere below I've redacted the real broker hostname to `<cluster>.s1.eu.hivemq.cloud`. Publishing your actual cluster URL isn't catastrophic, but there's no reason to hand it out either.

## The publisher

The heart of it is one Python script. Collectors gather stats and return plain dicts; a builder turns them into frames; a publisher ships them. Here's the frame builder, which also supports dropping any frame you don't want via a `SKIP_FRAMES` env var and re-indexes what's left:

```python
def build_frames(cfg):
    catalog = []
    sysd = collect_system(cfg["disk_path"])
    catalog.append(("cpu",  {"text": f"CPU {sysd['cpu']:.0f}%",  "icon": ICONS["cpu"]}))
    catalog.append(("ram",  {"text": f"RAM {sysd['ram']:.0f}%",  "icon": ICONS["ram"]}))
    catalog.append(("disk", {"text": f"DISK {sysd['disk']:.0f}%", "icon": ICONS["disk"]}))

    load1 = collect_load()
    if load1 is not None:
        catalog.append(("load", {"text": f"LOAD {load1:.2f}", "icon": ICONS["load"]}))

    tp = collect_throughput(cfg["net_skip"])
    catalog.append(("rx", {"text": f"RX {tp['rx_mbps']:.1f}Mb", "icon": ICONS["rx"]}))
    catalog.append(("tx", {"text": f"TX {tp['tx_mbps']:.1f}Mb", "icon": ICONS["tx"]}))
    catalog.append(("conn", {"text": f"CONN {collect_connections()}", "icon": ICONS["conn"]}))
    # ... net latency, uptime, optional pfSense ...

    frames = []
    for i, (_key, frame) in enumerate(c for c in catalog if c[0] not in cfg["skip"]):
        frames.append({"index": i, **frame})
    return frames
```

Network throughput is sampled as a delta over one second (loopback excluded), which is what turns a static "here's my box" display into something that actually reflects traffic:

```python
def collect_throughput(skip_prefixes, interval=1.0):
    def snap():
        nics = psutil.net_io_counters(pernic=True)
        rx = sum(s.bytes_recv for n, s in nics.items() if not n.startswith(skip_prefixes))
        tx = sum(s.bytes_sent for n, s in nics.items() if not n.startswith(skip_prefixes))
        return rx, tx
    rx0, tx0 = snap()
    time.sleep(interval)
    rx1, tx1 = snap()
    to_mbps = lambda d: max(d, 0) * 8 / 1e6 / interval
    return {"rx_mbps": to_mbps(rx1 - rx0), "tx_mbps": to_mbps(tx1 - tx0)}
```

And the publish itself — TLS, QoS 1 so the broker acknowledges receipt, and `retain=True` so the device shows current values the instant it (re)subscribes instead of waiting for the next cycle:

```python
def publish_frames(client, topic, frames, timeout=10.0):
    info = client.publish(topic, json.dumps({"frames": frames}), qos=1, retain=True)
    info.wait_for_publish(timeout=timeout)
    return info.is_published()
```

All the secrets and tunables live in a git-ignored `.env` (broker host, the publish credential, topic, which frames to skip). The script has three modes: `--dry-run` (build and print frames, no broker needed), `--once` (publish a single update), and `--loop --interval N` (persistent connection, publish on a timer — what the service runs).

## Running it, and the three-legged test that saved time

Debian 13's PEP 668 protection blocks system-wide pip, so everything runs in a venv:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt      # psutil, paho-mqtt
```

Then it goes permanent as a systemd service pointing straight at the venv's Python (no need to "activate" inside a unit):

```ini
[Service]
Type=simple
User=student
WorkingDirectory=/home/student/labmetric-pusher
ExecStart=/home/student/labmetric-pusher/.venv/bin/python \
          /home/student/labmetric-pusher/labmetric.py --loop --interval 60
Restart=always
RestartSec=10
```

The thing I'd most recommend to anyone building a multi-hop pipeline like this: **test each leg in isolation.** I verified in three independent steps, and it meant I never had to guess where a failure lived:

1. **Collection** — `--dry-run` prints the frames JSON with no network at all. If the numbers are right here, the collectors work.
2. **CLAUDDEB → broker** — subscribe to the topic in HiveMQ's web client, run `--once`, watch the JSON land. If it shows up here, publishing works and TLS/auth are good.
3. **Broker → device** — only now look at the physical display.

When something broke, I always knew which leg to blame. That's the whole point.

## The troubleshooting log

The parts that cost me time, so they don't cost you yours:

- **HiveMQ's new console hides the cluster.** The "Overview" tab (with your host/port) only appears *after* a cluster exists. You deploy via *Deploy a new broker → HiveMQ Cloud → Serverless*, then Manage Cluster.
- **Port 8883 is TLS-only.** The single most important checkbox in the whole LaMetric app config is **"Use TLS."** Leave it unticked with port 8883 and the connection silently fails the handshake. This is the first thing to check if nothing connects.
- **You can't recover a broker password.** HiveMQ stores a hash, so there's no "reveal" button. I forgot mine and just recreated the credential. Expected behaviour, not a bug.
- **The LaMetric app form blanks its credentials on save.** After a save/restart, the username, password, topic, and TLS checkbox came back empty while the host/port survived. Re-check those four every time you re-save.
- **A "private" LaMetric app still demands a privacy-policy URL.** Even for an app only you install. Any URL that resolves gets you past validation — I pointed it at my blog.
- **The `.env.example` dotfile didn't copy.** File managers hide dotfiles, so a drag-copy skipped it. I recreated `.env` by hand.
- **The frame-count trap.** This one got me at the end. The DevZone app builder wants the *same number of frames defined* as you push. I built 5 frames, later expanded the script to 9 — and the device kept showing only 5, silently ignoring the rest, even though the broker had the full 9-frame message. Fix: edit the app, add frames until the count matches, republish.
- **The device caches the app for ~10 hours.** After republishing with 9 frames, the display *still* showed 5, because LaMetric only checks for app updates roughly every 10 hours. Force it: open the app's options on the device and tap the "i" (info) action, or remove and re-add the app in the phone app. Then all nine appeared.

## A privacy catch worth mentioning

Once it was live, I noticed the LaMetric was displaying my **home address**. Mild heart-attack moment — but it wasn't my pipeline. I'd literally just watched the full MQTT payload in the broker's web client, and it contained nothing but my stat frames. The culprit was one of LaMetric's *native* built-in apps (the Weather app geolocates during setup) cycling in the rotation alongside mine. Worth knowing that these displays leak location by default, entirely separately from anything you build. The fix lives in the device's location/weather settings, not your code.

## The result

Nine frames now cycle on the display: **CPU, RAM, DISK, LOAD, RX, TX, CONN, NET latency, UPTIME** — refreshed every 60 seconds by a systemd service that survives reboots, delivered over TLS through a cloud broker, without a single inbound port open or a single crack in the network isolation between my automation VM and the rest of my network.

It also immediately earned its keep: the DISK frame flagged that CLAUDDEB's root filesystem was sitting at 99% — the sort of thing you notice on a glance-able display long before it takes a service down.

## What's next

The one collector still stubbed out is **pfSense over SNMP**, which would add real WAN throughput and firewall state — the genuinely lab-specific data. Enabling SNMP on pfSense and pointing the script at it is the natural next hop, and it turns "a Debian box's stats" into "my network's stats," which is what the display was always meant to be.

The broader takeaway, though, isn't about LaMetric at all. It's that a hard architectural constraint — *these two hosts must never talk on the LAN* — didn't block the feature. It just picked the design for me. When you can't connect two things directly, have them both connect out to a point in the middle. That pattern shows up everywhere once you start looking for it.
