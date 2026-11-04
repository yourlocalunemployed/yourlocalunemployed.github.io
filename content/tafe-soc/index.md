---
title: "TAFE SOC Network Group Project"
description: "A TAFE group project: designing, building, and then live attacking/defending a nine-zone SOC network in Proxmox."
layout: tafe-soc
ShowToc: false
hideMeta: true
comments: false
# The project's own standing page (layouts/_default/tafe-soc.html): figures
# derived from this file, the zone map from data/soc_project.yaml, then the
# seven pages below in the in-page stepper (layouts/_shortcodes/steps.html).
# Screenshots live beside this file in images/ and are referenced relatively.
# The text is the project handoff's, unchanged; the dated post at
# /posts/tafe-soc-network-group-project/ is the earlier write-up, kept as
# published.
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

{{< steps >}}

{{< step 1 >}}
PEAS SOC is a nine-zone enterprise network I designed and built from scratch
in a Proxmox lab environment for a TAFE group project (CL5, "Build and
Battle"), then led the live attack-and-defence exercise against. As team
lead, I coordinated the planning, built the core infrastructure, and ran
blue-team detection across the exercise.

![Proxmox environment — the full VM set behind the project](images/01-proxmox-topology.png)

This page covers the whole project end to end: the design decisions before
a single VM was built, the network itself, what got attacked and defended
across four live rounds, the troubleshooting that didn't make it into any
polished report, and what came out of it. It deliberately leaves out
configuration detail (firewall rule syntax, exact RADIUS config, etc.) —
that lives in the project's own playbook and report documents, not here.
{{< /step >}}

{{< step 2 >}}
Before any build work, the group worked through the network's zone design
and threat model together: which segments a real business would realistically
need — a corporate LAN, a dedicated SOC analyst segment, a public-facing DMZ,
guest wifi, and a locked-down management plane — and, just as importantly,
which of those should never be allowed to talk to each other directly. That
"never talk directly" list became the project's actual security requirement,
not an afterthought bolted on after the network was built.

The design went through a real draft stage before it was final. This is my
early prototype sketch — same router-on-a-stick concept through pfSense,
the same zone split, but still being worked out (VLAN IDs not yet settled
for every zone, addressing not yet consistent, the blue/red no-communication
rule still just a handwritten note rather than an enforced policy):

![Early prototype sketch of the topology — same zone concept, VLAN IDs and addressing still being worked out](images/00a-early-prototype-topology.png)

That got refined into the final logical network design below — router-on-a-stick
through pfSense, with Proxmox's VLAN-aware bridge handling trunking, every
zone on a settled subnet, and the intended team-interaction rules spelled out
explicitly instead of left as a note on the diagram:

![My final logical network design — router-on-a-stick through pfSense, seven VLANs, and the intended team-interaction rules](images/00-topology-design.png)

*Note: the SSH honeypot (Cowrie) drawn in the DMZ on this design was not used in the actual implementation of the project.*

Seven VLANs carry the design: CORP (10.10.10.0/24, AD/DNS/CA plus domain
workstations), Blue Team/SOC (10.20.20.0/24, Wazuh + EDR, syslog, FreeRADIUS),
DMZ (172.16.30.0/24, the Apache/Flask app and MariaDB),
Red Team/Guest (10.40.40.0/24, lab-safe only — segment-local scanning and
credential guessing against a test account with lockout), WiFi-CORP and
WiFi-Guest (design placeholders, no devices configured), and a locked-down
MGMT plane (10.99.99.0/24) reserved purely for firewall administration during
the build. The rule the whole design hangs off: Red Team to Blue Team direct
access is denied both ways and logged, full stop.

Segmentation was designed around aliases, not one-off rules, so the deny
policy could be reasoned about and audited as a whole rather than as a pile
of individual firewall entries:

![pfSense alias grouping the protected internal networks as a single reusable object](images/04-firewall-alias-design.png)

Role and round planning were revisited mid-project too. The group initially
scoped a five-round attack/defence exercise with rotating attacker/defender
roles each round. Once the blue/red split was finalised, we deliberately cut
this back to four rounds with **fixed roles**, each targeting a different
stage of the kill chain — a scoping decision made to keep the exercise
focused rather than repetitive, and to give red team more depth per round
instead of breadth. Fixed roles also meant blue team built up real
familiarity with "their" segment of the network across all four rounds,
instead of starting cold each time.
{{< /step >}}

{{< step 3 >}}
pfSense sits at the centre as firewall and router, segmenting nine zones:
WAN, LAN, CORP, SOC, DMZ, GUEST, WIFICORP, WIFIGUEST, and MGMT. Explicit deny
rules enforce isolation between zones that should never touch (GUEST can never
reach SOC or MGMT), and every block is logged.

![pfSense console — all nine zones assigned and addressed](images/02-network-zones-console.png)

DHCP on each zone uses a mix of dynamic leases and static mappings, so
known infrastructure (the SOC tooling, the DMZ target) always comes up on
a predictable address instead of drifting:

![DHCP static mapping pinning a known host to a fixed address](images/03-dhcp-static-mapping.png)

Remote access runs through OpenVPN on pfSense with FreeRADIUS authentication
against Active Directory, tunnelling clients onto a dedicated 10.200.0.0/24
network that reaches the SOC segment only — not CORP, not DMZ — with the
option to layer TOTP or privacyIDEA for MFA. RADIUS **group membership** —
not just a valid login — determines which internal segments a VPN client can
actually reach, proven live both ways: a member of the right group
authenticates and is accepted —

![RADIUS diagnostics: a group-member account authenticates successfully](images/23-radius-group-member-success.png)

— while an otherwise-valid account with no group membership is correctly
rejected at the same test:

![RADIUS diagnostics: an account with no group membership is rejected](images/24-radius-group-nonmember-fail.png)

The same accept/reject behaviour, confirmed again from the command line with
`radtest` against the live FreeRADIUS service — a correct password gets
`Access-Accept`, a deliberately wrong one gets `Access-Reject`:

![radtest confirming RADIUS Access-Accept for a correct password and Access-Reject for a wrong one](images/27-radius-radtest-accept-reject.png)

A Squid proxy also sits in the design.

Getting RADIUS working wasn't a one-shot config, either: an earlier pass
failed outright with no response from the server at all —

![Early RADIUS test: no reply from the server for the authentication request](images/07-radius-broken-no-reply.png)

— traced back through the LDAP bind chain and fixed, confirmed by the
service itself coming up clean:

![FreeRADIUS running and processing authentication requests](images/06-freeradius-status.png)
{{< /step >}}

{{< step 4 >}}
- A Metasploitable-based target VM (VM 100) with a clean-baseline snapshot
  workflow, rolled back between rounds so every exercise starts from a
  known, identical state — the disk-only baseline snapshot taken and
  verified by hand before the first round:

![Taking and verifying the clean-baseline disk snapshot for the target VM](images/22-proxmox-snapshot-workflow.png)

- A custom DMZ web application (PHP + MariaDB) deliberately built with a SQL
  injection flaw, later expanded with additional database tables to support
  a full UNION-based extraction chain rather than a single canned exploit —
  giving red team column-count discovery, padding technique, and multiple
  targets of different shapes to work through.
- Suricata IDS deployed across GUEST, DMZ and CORP, run in detection-only
  mode for the first three rounds, with round four dedicated purely to
  validating blocking behaviour.
- A full backup and disaster-recovery workflow for the firewall, using
  Proxmox's own `vzdump` with ZSTD compression and a keep-daily-3 retention
  policy across all seven project VMs — plus a genuinely off-host backup
  and a timed restore-and-boot test to produce real, measured recovery
  figures rather than estimates (~2 min 10 sec measured RTO, well inside
  the 1-hour target, verified by a before/after diff of the web page and
  database row count).

Isolation itself was built and proven incrementally, not assumed: the GUEST
zone's rule set was explicitly tightened to deny reach into the protected
internal networks, verified by comparing the rule set before and after the
change took effect —

![GUEST zone rules: explicit deny into the protected-networks alias, in place and logging](images/05-guest-rules-isolation.png)
{{< /step >}}

{{< step 5 >}}
The live exercise ran as four fixed-role rounds, each with its own focus:

| Round | Focus | Defenders | Attackers |
|---|---|---|---|
| 1 | Reconnaissance & enumeration — Nmap scan, service/version scan | Fixed blue team | Fixed red team |
| 2 | Credential & service exploitation — brute force, FTP backdoor trigger | Fixed blue team | Fixed red team |
| 3 | Web application SQL injection — boolean bypass + UNION-based extraction chain | Fixed blue team | Fixed red team |
| 4 | Blocking-mode validation — Suricata blocking enabled, SYN flood test case | Fixed blue team | Fixed red team |

**Round 1 — Reconnaissance.** Nmap scripting-engine scan detected and
correctly attributed:

![Nmap scripting-engine scan detected and logged](images/09-round1-nmap-recon.png)

**Round 2 — Cross-zone attack attempt and zone isolation.** Red team
(Kali, on GUEST) attempted to reach a protected internal host directly:

![Kali attacker pinging a target host from the GUEST zone](images/10-kali-ping-attempt.png)

...and was explicitly blocked and logged by the firewall rather than
silently dropped, with the rule name and timestamp captured as evidence:

![Blocked cross-zone traffic, logged with rule name and timestamp](images/11-kali-blocked-firewall-log.png)

The same isolation behaviour, shown from the other side of the log:

![Blocked cross-zone traffic, logged with rule name and timestamp](images/12-zone-isolation-block.png)

Suricata alerting on the DMZ segment during the exercise:

![Suricata DMZ alert log during an active round](images/13-suricata-dmz-alerts.png)

...correlated against Wazuh for a second, independent view of the same
activity:

![Wazuh event correlation for the same round](images/14-wazuh-events.png)

Between every round, VM 100 is rolled back to its clean baseline so each
round starts identical — by VM name, not just VM ID, so there's no ambiguity
about which host just got reset:

![Snapshot rollback and restart of the target VM, shown against the full named VM list](images/26-proxmox-vm-rollback-named.png)

The same rollback step shown from the command line:

![Snapshot rollback and restart of the target VM between rounds](images/15-vm100-rollback.png)

**Round 3 — SQL injection.** The baseline, confirmed working before any
injection attempt:

![DMZ login app verified working before the SQLi round](images/16-sqli-baseline-login.png)

A genuine detection gap was found here and documented rather than hidden:
the generic Suricata ruleset did not alert on a boolean-based SQL injection
payload at all — it was caught only via the database's own query log. The
SQL injection surface was later deliberately expanded beyond the single
boolean bypass into a full UNION-based extraction chain across three
differently-shaped database tables, giving red team column-count
discovery and NULL-padding technique to work through, not just one
canned payload.

While reviewing the app's own setup for that work, a separate, genuine
finding turned up: a stale reverse-proxy configuration routing requests to
a service that no longer matched the current deployment —

![A stale reverse-proxy configuration found while reviewing the DMZ app](images/17-stale-reverse-proxy-config.png)

That gap, and the incident-response steps the blue team documented for it
(detect, contain, eradicate, recover, lessons learned), fed directly into
the project's blue-team playbook as a reference for future rounds.

**Round 4 — Blocking-mode validation.** Suricata's detection tooling,
used throughout the exercise to pull logs per-instance for correlation:

![Suricata log browser, selecting the DMZ IDS instance's log](images/18-suricata-log-browser.png)
{{< /step >}}

{{< step 6 >}}
Real infrastructure means real problems, found and fixed rather than
designed away:

- A campus WAN outage knocked out DHCP mid-project — isolated by capturing
  traffic on the WAN interface itself and watching repeated, unanswered
  DHCP requests go nowhere, confirming the fault sat upstream of pfSense
  rather than in the lab's own config:

![Packet capture on the WAN interface showing repeated, unanswered DHCP requests during the outage](images/25-wan-dhcp-request-capture.png)

- VPN authentication failures needed careful isolation between genuine
  backend/config issues and simple operator error — both occurred, and both
  had to be distinguished before either could be called "fixed." The
  RADIUS no-reply/fixed pair on Page 3 was one strand of that work; the LDAP
  bind chain behind it took several more passes before it held up to a
  repeated test, not just a lucky first pass.
- A detection-pipeline gap between SOC's log forwarding and Wazuh was found,
  corrected, and then validated by forcing a fresh alert through end-to-end:

![Confirmed: a fresh alert now reaches Wazuh after the pipeline fix](images/19-detection-pipeline-fix.png)

- Elsewhere in the same log-pipeline work, a domain controller's clock had
  drifted out of sync with the rest of the environment, quietly breaking
  Kerberos and skewing event timestamps across the SOC's correlated view
  until it was corrected:

![Domain controller time source corrected after drift broke event correlation](images/20-ad-time-sync-fix.png)

- A SOC log listener that had silently stopped was found and brought back
  up under a fresh process, then confirmed receiving events again before
  being signed off as resolved:

![SOC log listener confirmed restored and receiving events again](images/21-wazuh-listener-restored.png)

- A shared lab host with SSH root login centrally locked down by policy
  needed a clean, self-removing workaround to get a backup archive
  genuinely off the host — rather than weakening the host's own security
  controls to make the job easier.

Each of these was a case of distinguishing "looks broken" from "is actually
broken, and why" before calling anything fixed — the no-reply RADIUS test,
the stale reverse-proxy config, and the quiet log listener all looked like
different symptoms of the same underlying discipline: verify with evidence,
not assumption.
{{< /step >}}

{{< step 7 >}}
The project produced more than a working network: a measured, evidenced
disaster-recovery figure instead of a guess; a documented detection gap with
a real incident-response write-up attached to it, not just a "todo"; a
genuinely expanded attack surface built collaboratively with red team rather
than left as a single toy exploit; and a round structure that was
deliberately simplified once the team had enough information to know five
rounds added repetition, not depth. The blue-team playbook and group report
both carry this evidence forward as the project's record of what was
actually tested and proven, not just planned — and the logical network
design on Page 2 was the plan every one of those decisions traces back to.
{{< /step >}}

{{< /steps >}}
