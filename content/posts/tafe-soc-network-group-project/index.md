---
title: "TAFE SOC Network Group Project"
date: 2026-11-04T12:31:00+11:00
draft: false
description: "A TAFE group project: designing, building, and then live attacking/defending a nine-zone SOC network in Proxmox."
tags: ["security", "networking", "pfsense", "firewall", "vpn", "siem", "detection-engineering"]
series: ["Build and Battle"]
seriesTitle: "The nine-zone SOC, built and attacked"
ShowToc: false
cover:
  image: "/posts/tafe-soc-network-group-project/images/02-network-zones-console.png"
  alt: "pfSense console with all nine zones assigned and addressed"
  hiddenInSingle: true

# The seven pages, in order. Read by the step shortcode for the tab row, the
# page headings and the previous/next links, so a title is written once.
steps:
  - title: "Project overview"
  - title: "Pre-planning and design decisions"
  - title: "Network architecture"
  - title: "What was built"
  - title: "Attack and defence rounds"
    highlight: true
  - title: "Troubleshooting and validation"
  - title: "Outcomes and lessons"

---

{{< soc-zones >}}

{{< steps >}}

{{< step 1 >}}
PEAS SOC is a nine-zone enterprise network I designed and built from scratch
in a Proxmox lab environment for a TAFE group project (CL5, "Build and
Battle"), then led the live attack-and-defence exercise against. As team
lead, I coordinated the planning, built the core infrastructure, and ran
blue-team detection across the exercise.

![Proxmox environment — the full VM set behind the project](images/01-proxmox-topology.png)
{{< /step >}}

{{< step 2 >}}
Before any build work, the group worked through the network's zone design
and threat model together: which segments a real business would realistically
need — a corporate LAN, a dedicated SOC analyst segment, a public-facing DMZ,
guest wifi, and a locked-down management plane — and, just as importantly,
which of those should never be allowed to talk to each other directly.

Role and round planning were revisited mid-project too. The group initially
scoped a five-round attack/defence exercise with rotating attacker/defender
roles each round. Once the blue/red split was finalised, we deliberately cut
this back to four rounds with **fixed roles**, each targeting a different
stage of the kill chain — a scoping decision made to keep the exercise
focused rather than repetitive, and to give red team more depth per round
instead of breadth.
{{< /step >}}

{{< step 3 >}}
pfSense sits at the centre as firewall and router, segmenting nine zones:
WAN, LAN, CORP, SOC, DMZ, GUEST, WIFICORP, WIFIGUEST, and a locked-down MGMT
plane reserved purely for firewall administration. Explicit deny rules
enforce isolation between zones that should never touch (GUEST can never
reach SOC or MGMT), and every block is logged.

![pfSense console — all nine zones assigned and addressed](images/02-network-zones-console.png)

Remote access runs through OpenVPN with FreeRADIUS authentication, where
RADIUS **group membership** — not just a valid login — determines which
internal segments a VPN client can actually reach. This was proven live:
one RADIUS group correctly reached CORP while being refused DMZ and SOC;
a second group was correctly refused entirely.

![FreeRADIUS running and processing authentication requests](images/03-freeradius-status.png)
{{< /step >}}

{{< step 4 >}}
- A Metasploitable-based target VM (VM 100) with a clean-baseline snapshot
  workflow, rolled back between rounds so every exercise starts from a
  known, identical state.
- A custom DMZ web application (PHP + MariaDB) deliberately built with a SQL
  injection flaw, later expanded with additional database tables to support
  a full UNION-based extraction chain rather than a single canned exploit —
  giving red team column-count discovery, padding technique, and multiple
  targets of different shapes to work through.
- Suricata IDS deployed across GUEST, DMZ and CORP, run in detection-only
  mode for the first three rounds, with round four dedicated purely to
  validating blocking behaviour.
- A full backup and disaster-recovery workflow for the firewall, including a
  genuinely off-host backup and a timed restore-and-boot test to produce
  real, measured recovery figures rather than estimates (~2 min 10 sec
  measured RTO, well inside the 1-hour target).
{{< /step >}}

{{< step 5 >}}
The live exercise ran as four fixed-role rounds, each with its own focus:

| Round | Focus | Defenders | Attackers |
|---|---|---|---|
| 1 | Reconnaissance & enumeration — Nmap scan, service/version scan | Fixed blue team | Fixed red team |
| 2 | Credential & service exploitation — brute force, FTP backdoor trigger | Fixed blue team | Fixed red team |
| 3 | Web application SQL injection — boolean bypass + UNION-based extraction chain | Fixed blue team | Fixed red team |
| 4 | Blocking-mode validation — Suricata blocking enabled, SYN flood test case | Fixed blue team | Fixed red team |

Round 1 reconnaissance, picked up and correctly attributed:

![Nmap scripting-engine scan detected and logged](images/04-round1-nmap-recon.png)

Zone isolation enforced and evidenced — a disallowed cross-zone request,
blocked and logged rather than silently dropped:

![Blocked cross-zone traffic, logged with rule name and timestamp](images/05-zone-isolation-block.png)

Suricata alerting on the DMZ segment during the exercise:

![Suricata DMZ alert log during an active round](images/06-suricata-alerts.png)

...correlated against Wazuh for a second, independent view of the same
activity:

![Wazuh event correlation for the same round](images/07-wazuh-events.png)

Between every round, VM 100 is rolled back to its clean baseline so each
round starts identical:

![Snapshot rollback and restart of the target VM between rounds](images/08-vm100-rollback.png)

For round 3, a genuine detection gap was found and documented rather than
hidden: the generic Suricata ruleset did not alert on a boolean-based SQL
injection payload at all — it was caught only via the database's own query
log. The baseline, confirmed working before any injection attempt:

![DMZ login app verified working before the SQLi round](images/09-sqli-baseline-login.png)

That gap, and the incident-response steps the blue team documented for it
(detect, contain, eradicate, recover, lessons learned), fed directly into
the project's blue-team playbook as a reference for future rounds.
{{< /step >}}

{{< step 6 >}}
Real infrastructure means real problems, found and fixed rather than
designed away:

- A campus WAN outage knocked out DHCP mid-project and had to be isolated
  and escalated before VPN testing could continue.
- VPN authentication failures needed careful isolation between genuine
  backend/config issues and simple operator error — both occurred, and both
  had to be distinguished before either could be called "fixed."
- A detection-pipeline gap between SOC's log forwarding and Wazuh was found,
  corrected, and then validated by forcing a fresh alert through end-to-end:

![Confirmed: a fresh alert now reaches Wazuh after the pipeline fix](images/10-detection-pipeline-fix.png)

- A shared lab host with SSH root login centrally locked down by policy
  needed a clean, self-removing workaround to get a backup archive
  genuinely off the host — rather than weakening the host's own security
  controls to make the job easier.
{{< /step >}}

{{< step 7 >}}
The project produced more than a working network: a measured, evidenced
disaster-recovery figure instead of a guess; a documented detection gap with
a real incident-response write-up attached to it, not just a "todo"; and a
round structure that was deliberately simplified once the team had enough
information to know five rounds added repetition, not depth. The blue-team
playbook and group report both carry this evidence forward as the project's
record of what was actually tested and proven, not just planned.
{{< /step >}}

{{< /steps >}}
