---
title: "Metrics You Have to Remember to Look At Aren't Monitoring"
date: 2026-07-18T18:55:00+10:00
draft: false
description: "I had dashboards for months. What I didn't have was anything that told me when something broke. Building the alerting layer on top of the existing Prometheus stack — the packaging quirk, the isolated-network dead end, and the silent-config trap along the way."
tags: ["homelab", "prometheus", "alertmanager", "ntfy", "monitoring", "alerting", "docker"]
series: ["Home Lab"]
seriesTitle: "The lab pages my phone"
---

I'd had Grafana dashboards for months. What I didn't have was anything that told me when something broke — I had to *remember to look*. This is the alerting layer that fixes that, built on top of the existing Prometheus stack, plus the three things that got in the way.

**Stack:** Prometheus · Alertmanager · ntfy · Docker

---

## 1. The gap I'd been ignoring

My lab had a healthy [observability stack](/posts/prometheus-grafana-observability-stack/): Prometheus scraping metrics, node_exporter for the host, snmp_exporter pulling throughput off pfSense, all drawn in Grafana. It looked complete.

It wasn't. **Collecting metrics and reacting to them are different jobs, and I'd only done the first one.** If a service fell over at 3am, Prometheus dutifully recorded it going down — and I'd find out whenever I next happened to open a dashboard. My [backup cron](/posts/backup-you-havent-restored/) wrote to a logfile nobody read. That's not monitoring; it's a very thorough diary.

The distinction is worth stating plainly: **a metric you have to remember to check is not a monitor.** Monitoring is the thing that reaches out to *you*. Everything I'd built waited politely to be looked at.

So the goal for this session was small and specific: **make the lab tell me when something's wrong, on my phone, without me asking.**

---

## 2. The architecture

Prometheus already knew how to *evaluate* conditions — that's what alerting rules are. What it doesn't do is *notify*. That's a separate component: **Alertmanager**, which takes fired alerts and decides where they go, how they're grouped, and when to shut up.

```text
node_exporter ─┐
               ├─► Prometheus ──► Alertmanager ──► ntfy ──► phone
snmp_exporter ─┘    (rules)        (routing)
```

Why Alertmanager rather than Grafana's built-in alerting, which I already had? Honest answer: Grafana's would have worked and needed no new parts. I chose Alertmanager because it's the *standard* component of the Prometheus stack — it's what turns up in job ads, and it exposes concepts Grafana hides: routing trees, grouping, silences, inhibition. I'm building a portfolio as much as a lab, so I took the one worth knowing.

---

## 3. First wall: a package that refused to install

Prometheus on this box came from Debian's repos, so I reached for the matching Alertmanager package. It aborted mid-install:

```text
fatal: The user 'prometheus' already exists, but is not a system user. Exiting.
dpkg: error processing package prometheus-alertmanager
```

A genuinely informative error, once you slow down and read it. The package's post-install script tries to create a **system user** named `prometheus` — UID below 1000, no login shell. One already existed, but as a **regular** user. `adduser --system` refuses to touch a normal account rather than silently change it, so the whole install rolled back.

What it actually told me: **my Prometheus was never installed from apt.** Someone — a past me, or an install script — had set it up by hand and made an ordinary user for it. The packaging convention and my existing setup disagreed, and the packaging lost.

Three ways forward:

1. **Convert the user to a system user** — means changing its UID and `chown`-ing everything it owns. Surgery on a working service to satisfy a convention.
2. **Install Alertmanager by hand too** — consistent with Prometheus, but more to maintain.
3. **Run Alertmanager in Docker** — no system user, no conflict, sidesteps the whole thing.

I already run Docker for the rest of the lab, so option 3 was obvious. The lesson isn't "Docker good" — it's that **when a packaging assumption collides with your reality, the cleanest fix is often to stop fighting the assumption.** I wasn't going to win an argument with `adduser` about a user that already worked.

```yaml
services:
  alertmanager:
    image: prom/alertmanager:latest
    container_name: alertmanager
    restart: unless-stopped
    ports:
      - "127.0.0.1:9093:9093"
    volumes:
      - ./alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
      - alertmanager_data:/alertmanager

volumes:
  alertmanager_data:
```

Two deliberate choices:

- **`127.0.0.1:9093:9093`** — published to loopback only. My native Prometheus reaches it at `localhost:9093` exactly as if it were a local process; nothing on the LAN can. Same posture as everything else internal in the lab.
- **`alertmanager_data`** persists silences and notification state across restarts. Without it, a restart re-sends everything you'd already acknowledged.

---

## 4. Rules, and the one setting that makes them usable

Two rules to start — the things I'd actually want woken up for:

```yaml
groups:
  - name: lab
    rules:
      - alert: InstanceDown
        expr: up == 0
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "{{ $labels.job }} is down"

      - alert: DiskAlmostFull
        expr: node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"} * 100 < 15
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Disk below 15% free"
```

`up == 0` is a metric Prometheus generates for itself on every scrape — 1 if the target answered, 0 if it didn't. No exporter required; it's free.

But the line that matters most for *my* lab is **`for: 10m`**, and here's why it's not optional.

**I shut my VMs down every night.** So from Prometheus's point of view, every target vanishes at bedtime and reappears at boot — and Prometheus itself comes up before the things it's meant to scrape. Without `for:`, I'd get a faceful of "everything is down" alerts every single morning, for sixty seconds, until the stack finished starting.

`for: 10m` says *don't fire until the condition has held continuously for ten minutes.* It rides straight over the boot window. A target that's genuinely dead stays dead past ten minutes and pages me; a target that's just slow to wake never does.

That's the difference between an alerting system I trust and one I mute within a week. **An alert that cries wolf every morning trains you to ignore it — at which point it's worse than no alert at all**, because now you think you're covered.

---

## 5. Wiring Prometheus to Alertmanager — and a silent trap

Prometheus needs two things added at the **top level** of `prometheus.yml`:

```yaml
rule_files:
  - /etc/prometheus/alert_rules.yml

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['localhost:9093']
```

I added them, validated, restarted — and nothing reached Alertmanager. The rules were clearly firing (I could see them in the Prometheus UI), but Alertmanager's alert list stayed stubbornly empty.

The diagnosis is a small masterclass in *querying state instead of trusting config*:

```bash
curl localhost:9090/api/v1/alertmanagers
# {"activeAlertmanagers":[], "droppedAlertmanagers":[]}
```

**Both lists empty.** Prometheus didn't know Alertmanager existed. Which meant the `alerting:` block hadn't loaded — and the culprit was indentation. It's fatally easy to nest that block *inside* `scrape_configs:`, where YAML accepts it happily and Prometheus silently ignores it. It's valid YAML; it's just meaningless there. My validator passed it without complaint.

The tell:

```bash
grep -n -A4 '^alerting:' /etc/prometheus/prometheus.yml
```

`^alerting:` only matches if the block starts at column 0. Empty output = it's nested somewhere it shouldn't be. Once it was flush-left and Prometheus restarted (its systemd unit has no `ExecReload`, so a reload silently does nothing — it needs a full restart), the wiring came alive:

```json
"activeAlertmanagers":[{"url":"http://localhost:9093/api/v2/alerts"}]
```

**The recurring homelab lesson, again:** a config file passing a syntax check tells you it's *valid*, not that it's *loaded*, and certainly not that it's *doing what you meant*. The API that reports running state is the honest witness. Every hard bug in this lab has come down to the gap between what the config says and what the process is actually running.

---

## 6. The dead end: my display can't do this

I wanted alerts on the [LaMetric](/posts/implementing-lametric-time-to-network/) on my desk — the little pixel display already showing live CPU, RAM, and [pfSense throughput](/posts/implementing-lametric-time-to-network-part-2/). It would make a great at-a-glance "is everything OK" light.

It can't, and *why* it can't is the most interesting thing in this whole build.

The LaMetric's local notification API — the one with sound, priority, and "stay on screen until dismissed" — lives on the device at `192.168.1.139:8080`. To reach it, my lab host would have to send traffic to `192.168.1.x`.

**It can't. By design.**

```text
$ ping -c3 192.168.1.1
3 packets transmitted, 0 received, 100% packet loss
```

My lab is [deliberately segmented off](/posts/pfsense-lab-recovery-and-hardening/) from my home network. The lab host sits behind pfSense on `10.10.0.0/24`; the LaMetric sits on the home LAN on the *other side* of that firewall. pfSense's whole job is to keep those apart, and it's doing it perfectly. The gateway is unreachable; a TCP traceroute dies at the first hop.

So why do the *stats* work? Because they take the opposite path. The stats pusher sends data **outbound** to LaMetric's cloud, and the device pulls it down from there. That flow never touches the home LAN sideways — it goes out to the internet and comes back. The isolation was never in the way.

Alerts would need the local API, and the local API is on the wrong side of a wall I built on purpose. **The right call is to accept the constraint, not punch a hole through it.** I could special-case a firewall rule letting the lab reach one home IP on one port — but that's carving an exception into a security boundary for the sake of a beep. The boundary is worth more than the beep.

**A good design constraint should occasionally tell you *no*. If your segmentation never blocks anything you want to do, it probably isn't segmenting much.** This was mine earning its keep.

---

## 7. Where alerts actually land

The phone, via **ntfy** — a dead-simple pub/sub push service. Subscribe the phone app to a topic; anything POSTed to that topic pushes to the phone. On the public server, **the topic name *is* the password** — so it's a long random string, not `lab-alerts`.

```bash
echo "lab-$(openssl rand -hex 8)"
```

Alertmanager's route and receiver, first iteration:

```yaml
route:
  receiver: 'ntfy'
  group_by: ['alertname']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h

receivers:
  - name: 'ntfy'
    webhook_configs:
      - url: 'https://ntfy.sh/<topic>'
        send_resolved: true
```

The timings are the substance:

- **`group_wait: 30s`** — when a new alert group forms, hold briefly so related alerts arrive as one notification, not three for one outage.
- **`repeat_interval: 4h`** — re-nag about an *unresolved* alert every four hours. Short enough not to forget, long enough not to become wallpaper.
- **`send_resolved: true`** — also notify when it *clears*. Resolution is half of what alerting is for; an alert with no all-clear leaves you wondering.

The first delivery proved the path and exposed a formatting problem in the same buzz: pointing the webhook straight at ntfy means the notification arrives as Alertmanager's **entire raw JSON payload** — readable the way a packet capture is readable. Fine for proving delivery; useless at a glance.

I'd planned to write a small translator service to reshape it. Turns out I didn't have to — [ntfy-alertmanager](https://codeberg.org/xenrox/ntfy-alertmanager) already exists: a single container that sits between the two, maps `severity` to ntfy priority and emoji tags, formats the labels into a titled message, and adds a button linking back to the Prometheus graph that fired. The webhook now points at it instead of ntfy directly:

```yaml
webhook_configs:
  - url: 'http://ntfy-alertmanager:8080'
    send_resolved: true
```

Twenty lines of its config replaced a bespoke service I'd have had to maintain, back up, and debug at 3am. **The best version of a component is sometimes the one somebody else already wrote.**

---

## 8. Proving it end to end

The only test that counts is breaking something real:

```bash
sudo systemctl stop node_exporter
sleep 200
sudo systemctl start node_exporter
```

`InstanceDown` fires, the phone buzzes, and — because of `send_resolved` — buzzes again with the all-clear once the exporter's back.

One subtlety worth knowing, because it made an earlier test look broken: **Alertmanager only ever receives *firing* alerts, never *pending* ones.** While the `for:` timer is counting down, the alert is pending, and querying Alertmanager returns an empty list. That empty list is *correct* — Prometheus is deliberately holding the alert back. I'd been reading "empty" as "broken" when it meant "working exactly as designed, wait longer."

There's also a timing floor that isn't obvious: `evaluation_interval` defaults to **one minute**, so with `for: 1m` an alert can take up to ~3 minutes from cause to phone. Dropping `evaluation_interval` to `15s` (to match the scrape interval) makes it properly responsive, with no real cost at this scale.

**A footnote on how this got finished:** the last delivery bug got fixed while I was out of the house — SSH over Tailscale into the lab, driving Claude Code on the box itself. The lab's remote-access design meant "I'm not home" wasn't a reason to stop. Which is its own small validation of everything built before this.

---

## 9. What it survives, and what it doesn't

| Situation | Behaviour |
|---|---|
| A service dies | Phone buzzes after `for:` — no false alarm on a blip |
| It recovers | Phone buzzes with the all-clear |
| Nightly shutdown / morning boot | Silent — `for: 10m` rides over the boot window |
| Nothing wrong | Silent for days. The correct state. |
| Ongoing outage | Re-nagged every 4h until resolved |

A healthy lab is a quiet lab. That's the entire point — the value of an alert is inversely proportional to how often it's wrong.

---

## 10. Lessons

- **A metric you have to look at isn't a monitor.** Monitoring reaches out to you. Dashboards wait to be opened.
- **When a package's assumptions collide with your setup, stop fighting the assumption.** Docker dodged the system-user conflict cleanly; arguing with `adduser` would not have.
- **`for:` durations are load-bearing**, not decoration — especially when your infrastructure isn't 24/7. An alerting system that cries wolf gets muted, and a muted alert is worse than none.
- **A valid config isn't a loaded config.** Syntax checks prove neither that it's running nor that it means what you intended. The state-reporting API is the honest witness — the same lesson every hard bug in this lab keeps teaching.
- **Alertmanager receives firing, not pending.** An empty list can mean "working, wait."
- **A good boundary should sometimes tell you no.** The LaMetric dead end wasn't a failure — it was my segmentation doing its job. I chose the boundary over the convenience.
- **The best component is sometimes one you don't write.** The formatting bridge I'd planned already existed as a maintained project; deploying it was config, not code.

The build itself was maybe twenty lines of YAML. Everything worth writing down was in the parts that resisted: the packaging conflict that revealed how the stack was really installed, the silent indentation bug, and the firewall that correctly refused to let me do the convenient thing.

---

*Next: closing the loop on the alerts I create myself — teaching the nightly backup to report success or failure as a metric, so "the backup silently stopped running three weeks ago" stops being a way this can end.*
