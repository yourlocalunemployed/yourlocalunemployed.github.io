---
title: "Resolve and maintenance of the homelab server"
date: 2026-09-28T19:40:26+10:00
draft: true
description: "Things that were already working, quietly stopping working. A vulnerability scanner reporting a clean result while scanning nothing, and an NTP server that spent months telling every client not to trust it."
tags: ["home-lab", "ntp", "troubleshooting", "monitoring", "detection-engineering", "claude-code"]
series: ["Home Lab"]
seriesTitle: "Maintenance"
---

Since I built the homelab server and kept adding more things to it, some of the
older services that had been running for a while started to become funky and
stopped operating properly. Some just quietly stopped working altogether.

## The scanner that reported a clean result while scanning nothing

The whole thing started about a week ago. First it was the vulnerability
scanner claiming a clean result — which turned out to be it scanning nothing at
all.

- The scan claimed **0 open ports**, which contradicted previous runs that had
  found 6–7.
- The cause was a hardcoded Docker bridge gateway. Docker had moved the network
  to a new range, so the address it had been scanning the entire time no longer
  existed.
- `nmap -Pn` **does not error on a dead target**. It reports the host as up with
  all ports filtered. So the run was technically clean — there was genuinely
  nothing to show — and the result read as a *hardened host* rather than a
  *failed scan*. A failed scan would have looked completely different.
- The fix was to resolve the gateway at runtime, and to warn loudly if a scan
  ever returns 0 open ports again.

**Lesson:** a wrong answer that looks like good news is worse than no answer at
all.

## The rest of them

There were plenty of other issues that came up and got resolved along the way:

- a detection rule that matched its own error message
- an alert that was correct and wrong at the same time
- a log source that looked dead but was just quiet
- verifying patched images properly instead of trusting "just pull the images"
- a certificate swap on the firewall that went backwards before it went forwards
- a whole month of notes that were meant to be synced, sitting locally on the
  server the entire time
- the AI analyst losing access to its own designated directory
- a queue in the observability stack throwing an error every 31 seconds, for a
  feature that was never configured
- runbooks six weeks behind, with documents completely out of date

None of those compare to the one I spent the most time on, though.

## The NTP server that said "do not trust me" for months

This is the one that ate me alive. No matter how many diagnostics I went
through, it kept coming back. I even had to correct Claude's judgement several
times — more than once it went off diagnosing a completely different scope of
the project that had nothing to do with the actual issue.

Here is the full breakdown.

### The symptom

The lab's clock kept drifting after suspends. I fixed it three times. It kept
coming back.

### The cause, found by replacing the tool rather than debugging harder

`systemd-timesyncd` contacts servers *"in turn, until one responds"*. It uses
the first responder and **never compares sources**. A config comment in my own
setup claimed that listing extra pool servers meant "one bad upstream cannot
define the lab's idea of now" — that is simply not how timesyncd works. The
mitigation had never worked at any point.

### Diagnosis

- I swapped to **chrony**, which polls every source, compares them, and rejects
  the outlier. Within seconds it refused the firewall entirely: `Reach 0`, never
  used.
- Probing the firewall directly showed **`leap=3`** — the NTP leap indicator,
  meaning *"I am not synchronised, do not use me"*. It had been answering every
  single query with that flag set, while reporting a healthy-looking
  **stratum 2**.
- **My own exporter was reporting it as healthy.** It set
  `lab_ntp_server_up = 1` whenever a packet came back and never read the leap
  indicator. A green light that meant "something replied", not "the answer is
  usable".
- timesyncd had also silently **wedged**. Its last successful sync was the exact
  moment the host suspended two days earlier, while it reported
  `NTP service: active` the whole time.

## Part two — day four, two more fixes

### Fix 1: the timer underneath the clock was wrong

- The firewall's status page showed **1273–1802 ms of jitter**. Its own
  documentation says that above roughly 100 ms the NTP daemon is "almost
  useless". I was at 10–18 times that.
- The cause is that the OS picks its clock source by a quality score. The one it
  picked scores highest on paper and is the *wrong* choice inside a VM — the
  hypervisor deschedules the CPU and the counter stops tracking real time.
- Switching to a dedicated hardware timer took root dispersion from
  **2.958s to 0.208s**. The readings became stable for the first time.
- **Nothing was misconfigured.** A fresh install of the same firewall makes the
  same choice. Automatic selection optimises for bare metal.
- Worth a line: this firewall **ignores** the two config files you would
  normally use to persist a kernel tunable. Only the GUI's tunables page works.
  Someone on the vendor forum lost a lot of time to that.

### Fix 2: a setting that meant the opposite of what it looked like

- One upstream was ticked **Prefer** — "trust this one when sources disagree".
- It was a **pool** hostname. A pool resolves to a different volunteer server on
  every lookup. So it granted veto power to a random machine and destroyed the
  outlier rejection that running four sources exists to provide.
- Same shape as the timesyncd bug above: a setting that *reads* like a safeguard
  and *behaves* like its removal.

### And then the interesting part

After both fixes, the leap indicator went from **3 to 0** for the first time all
week. The firewall stopped declaring itself unusable.

It was still exactly **two seconds fast**.

The fixes had converted *"unsynchronised and obviously broken"* into
*"synchronised, confident, and two seconds wrong"* — which is worse, because now
everything downstream believes it.

![pfSense NTP offset across four days. The red band is every period the firewall
was reporting leap=3. The gap is the host being suspended — nothing was measured
there, so nothing is drawn.](/images/posts/ntp-offset.svg)

<!-- ###########################################################################
     DRAFT STOPS HERE — the ending is missing.

     Everything above builds to "synchronised, confident, and two seconds
     wrong" and then the post just ends. The reveal is the payoff and it is not
     written yet. You have the material; it is in
     ~/Desktop/Blog Drafts/fixing-and-resolving-homelab-server.md section 8
     part three. The beats, briefly:

       - the hypervisor exposes the HOST clock to a guest, so it could be
         measured from inside the VM without logging into Windows
       - the Windows host was +1.367s; the Linux VM on the same host was
         accurate to 0.0003s
       - the difference between them was one setting: periodic host-to-guest
         time sync, disabled on one and enabled on the other. That was the
         control experiment, already running.
       - the reason the host was wrong: the Windows Time service was STOPPED.
         w32tm returned "The service has not been started. (0x80070426)".
         On a non-domain machine Windows leaves it on Manual (Trigger Start).
       - after starting it and pointing it at a real pool: host went
         +1.367s -> -0.050s, and the firewall went to leap=0, offset -0.004s
       - the angle: three days blaming the firewall, and the firewall was the
         only component reporting the problem honestly. leap=3 meant "do not
         trust me", which was true the entire time.
       - two fixes were needed, not one: correcting the clock removes the wrong
         VALUE, disabling periodic guest sync removes the MECHANISM.

     Also still to do before publishing:
       - set draft: false
       - run the redaction checklist (no internal addressing, no hostnames,
         crop browser chrome from any screenshots you add)
       - add the attribution block you use on the other posts
########################################################################### -->
