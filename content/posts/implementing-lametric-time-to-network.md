---
title: "Implementing LaMetric TIME to Network"
date: 2026-07-05T21:30:00+10:00
draft: false
description: "Piping live home-lab stats to a LaMetric Time over MQTT — bridging two deliberately-isolated networks through a cloud broker without opening a single inbound port."
tags: ["lametric", "mqtt", "networking", "pfsense", "python", "home-lab"]
cover:
  image: "/images/posts/lametric-time.jpg"
  alt: "A LaMetric Time smart display"
  hiddenInSingle: true
---

I picked up a LaMetric Time — an 8x37 pixel smart display — and after locking it down on an isolated guest network, the next move was to make it useful: live health from my home lab. CPU, memory, network throughput — the numbers worth a glance.

The interesting part is that a constraint I'd deliberately built into my network dictated the whole architecture. This is the write-up: the design decision, the pipeline, and the gotchas — because the gotchas are the useful part.

## The constraint that shaped everything

The two relevant pieces of my lab:

- **CLAUDDEB** — a Debian 13 VM that does automation work, sitting behind a virtual pfSense firewall with RFC1918 rules that block it from the home LAN ([that build has its own post](/posts/pfsense-lab-recovery-and-hardening/)). Outbound internet only; no inbound.
- **The LaMetric** — on an isolated guest SSID (WPA3, client isolation, per [my home network setup](/posts/home-network-hardening-hwg2025/)). Outbound internet only.

In one sentence: **the box producing the data and the device displaying it sit on two networks that cannot reach each other on the LAN — by design.** That isolation is a feature, and I wasn't going to weaken it to show a CPU percentage.

## Picking the delivery method

LaMetric indicator apps support four communication types. The tutorials all use Local Push — POST a JSON blob to the device's IP — which requires exactly the LAN reachability my isolation forbids:

| Method | How it works | Fits the isolation? |
|---|---|---|
| Local Push | You POST to the device IP on the LAN | ❌ needs LAN reachability |
| Poll | Device fetches a URL on a schedule | ⚠️ needs a hosted public URL |
| **MQTT** | Device *subscribes* to a broker; I *publish* to it | ✅ both sides connect **outbound** |
| Web Socket | Device connects to a WS server | ⚠️ needs a hosted WS endpoint |

**MQTT was the clean winner.** Both the LaMetric and CLAUDDEB open outbound connections to a broker on the internet and meet in the middle. Neither accepts an inbound connection; neither reaches the other on the LAN. The isolation stays fully intact, with near-real-time updates as a bonus.

## The architecture

```text
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

The pieces, briefly:

- **HiveMQ Cloud (Serverless free tier)** — the broker. TLS-only MQTT on port 8883; its web test client became the most useful debugging tool of the project.
- **LaMetric DevZone** — defines the on-device indicator app: communication type MQTT, TLS on, a topic, a subscribe-only credential, data format **Predefined (LaMetric Format)**.
- **paho-mqtt + psutil** (Python, in a venv — Debian 13 enforces PEP 668) — collect the stats and publish the frames.
- **systemd** — runs the publisher as a persistent service; a long-lived MQTT connection is the idiomatic pattern.
- **TLS** — HiveMQ presents a publicly-trusted certificate, validated against Debian's CA store with zero extra config.

Credentials are least-privilege by design: a **subscribe-only** user on the LaMetric, a **publish-only** user in the script's config. A leak of either can't do the other side's job.

> Security note: the real broker hostname is redacted to `<cluster>.s1.eu.hivemq.cloud` throughout. Publishing your cluster URL isn't catastrophic, but there's no reason to hand it out.

## The publisher

One Python script: collectors gather stats into dicts, a builder turns them into LaMetric frames, a publisher ships them. The frame builder (with a `SKIP_FRAMES` env var to drop unwanted frames and re-index the rest):

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

Throughput is sampled as a one-second delta (loopback excluded), so the display reflects actual traffic. Established TCP connections are counted by parsing `/proc/net/tcp` directly — no root required. The publish uses QoS 1 and `retain=True`, so the device shows current values the moment it (re)subscribes:

```python
def publish_frames(client, topic, frames, timeout=10.0):
    info = client.publish(topic, json.dumps({"frames": frames}), qos=1, retain=True)
    info.wait_for_publish(timeout=timeout)
    return info.is_published()
```

Secrets and tunables live in a git-ignored `.env`. The script has three modes: `--dry-run` (print frames, no network), `--once` (single publish), and `--loop --interval N` (what the service runs). The systemd unit points straight at the venv's Python:

```ini
[Service]
Type=simple
User=<user>
WorkingDirectory=/home/<user>/labmetric-pusher
ExecStart=/home/<user>/labmetric-pusher/.venv/bin/python \
          /home/<user>/labmetric-pusher/labmetric.py --loop --interval 60
Restart=always
RestartSec=10
```

## Test each leg in isolation

The practice I'd most recommend for any multi-hop pipeline — three independent verification steps, so a failure always has an obvious home:

1. **Collection** — `--dry-run` prints the frames JSON with no network. If the numbers are right, the collectors work.
2. **Publisher → broker** — subscribe to the topic in HiveMQ's web client, run `--once`, watch the JSON land. If it arrives, publishing, TLS and auth are all good.
3. **Broker → device** — only now look at the physical display.

## The troubleshooting log

The parts that cost time:

- **HiveMQ's console hides the cluster until one exists.** Deploy via *Deploy a new broker → Serverless*, then Manage Cluster shows host and port.
- **Port 8883 is TLS-only.** The single most important checkbox in the LaMetric app config is **"Use TLS"** — without it the connection silently fails the handshake.
- **Broker passwords can't be recovered** (hashed server-side). Recreate the credential.
- **The LaMetric app form blanks its credentials on save** — username, password, topic and the TLS checkbox come back empty while host/port survive. Re-check all four on every re-save.
- **A "private" LaMetric app still requires a privacy-policy URL.** Any URL that resolves passes validation — I pointed it at [this blog's privacy page](/privacy/).
- **The `.env.example` dotfile didn't copy** — file managers hide dotfiles, so a drag-copy skipped it.
- **The frame-count trap.** The DevZone app must define the *same number of frames* as you publish. I expanded the script from 5 frames to 9 and the device silently kept showing 5, even though the broker held the full message. Fix: add frames in the app until the count matches, republish.
- **The device caches the app for ~10 hours.** After republishing, force an update via the app's "i" action on the device, or remove and re-add the app.

## A privacy catch worth knowing

Once live, the display started showing my **home address**. It wasn't my pipeline — I'd just watched the full MQTT payload in the broker's client, and it contained only stat frames. The culprit was LaMetric's built-in Weather app, which geolocates during setup and was cycling alongside my app. These displays leak location by default, independently of anything you build; the fix is in the device's location settings, not your code.

## The result

Nine frames cycle on the display — **CPU, RAM, DISK, LOAD, RX, TX, CONN, NET latency, UPTIME** — refreshed every 60 seconds by a systemd service, delivered over TLS through a cloud broker, with zero inbound ports and zero compromise to the network isolation.

{{< video src="videos/posts/lametric-demo.mp4" poster="images/posts/lametric-display.jpg" caption="The display cycling through the lab frames — NET latency, uptime, CPU, RAM, DISK." >}}

It earned its keep immediately: the DISK frame flagged CLAUDDEB's root filesystem at 99% — exactly the kind of thing a glanceable display catches before it takes a service down.

## What's next

The one collector still stubbed out is **pfSense over SNMP** — real WAN throughput and firewall state, the genuinely lab-specific data. That turns "a Debian box's stats" into "my network's stats."

The broader takeaway isn't about LaMetric. A hard architectural constraint — these two hosts must never talk on the LAN — didn't block the feature; it picked the design. When two things can't connect directly, have both connect out to a point in the middle. That pattern is everywhere once you look for it.
