---
title: "I Hardened This VM by Hand. Lynis Scored It 68/100."
date: 2026-07-20T20:30:00+10:00
draft: false
description: "An independent auditor grades the Debian lab VM I already hardened. The baseline was 68/100 — here's what I fixed, the findings I deliberately ignored (and why), and the number after: 80."
tags: ["security", "hardening", "debian", "linux", "lynis", "auditing", "home-lab"]
series: ["Hardening Network"]
seriesTitle: "The Debian lab VM"
---

A while back I [hardened this Debian VM by hand](/posts/hardening-debian-homelab-vm/) — patched it, cut the attack surface, put a default-deny host firewall in front of it, sandboxed the custom services. I audited my own box and fixed the drift I found.

The problem with auditing your own box is that you grade your own homework. You check the things you already think to check. So this time I handed the job to something that has no idea what I *meant* to do and only reports what's actually there: **Lynis**, the system-auditing tool from CISOfy. It ran 274 tests and gave the VM a hardening index of **68 / 100**.

This is the write-up: the baseline, the quick wins, the findings I looked at and deliberately *didn't* fix, and the two things the audit taught me that I didn't expect.

## Why audit a box you already hardened

Two reasons. First, a checklist tool catches the boring, easy-to-forget stuff — a missing login banner, a sysctl left at its default — that never makes it onto a hand-written to-do list. Second, and more useful: it disagrees with you. An opinionated auditor flags things you did on purpose, which forces you to actually justify those decisions instead of assuming they're fine. Half the value here was in the findings I *rejected*.

## The baseline: 68, zero warnings, 47 suggestions

Lynis ships in Debian, so there's no install ritual:

```bash
sudo apt-get install lynis
sudo lynis audit system
```

It writes a full report to `/var/log/lynis-report.dat` and a human summary to the terminal. The headline:

```text
Hardening index : 68 [############        ]
Tests performed : 274
Warnings        : 0
Suggestions     : 47
```

Two things to read correctly here. **Zero warnings is good** — Lynis reserves warnings for genuine problems, and there were none; everything else is a *suggestion*, i.e. "you could go further." And the **hardening index isn't a test pass-rate** — it's a weighted score of hardening opportunities taken versus available. You don't chase it to 100; some of the remaining points cost more than they're worth, and a few are wrong for your setup entirely. It's a compass, not a target.

One honest note before the fixes: Lynis itself flagged that the Debian package (3.1.4) is a few months behind upstream. For a real assessment you'd run the latest from CISOfy so the test set is current; for a baseline on my own box, the packaged version is fine — I just noted it and moved on.

## The quick wins

These are the findings that were simply *correct* — safe, cheap, and no reason not to.

**Legal banners** (`BANN-7126`, `BANN-7130`). No warning banner on login. Trivial:

```bash
# /etc/issue and /etc/issue.net
Authorized access only. All activity on this system is logged and monitored.
Disconnect now if you are not an authorized user.
```

**Kernel and network sysctl** (`KRNL-6000`). Lynis compared 16 kernel knobs against its hardening profile. I applied the safe majority as a drop-in — restrict kernel pointer/symbol access, tighten ptrace, ignore ICMP redirects, log martians, harden the BPF JIT:

```conf
# /etc/sysctl.d/99-lynis-hardening.conf
kernel.kptr_restrict = 2
kernel.yama.ptrace_scope = 1
kernel.sysrq = 0
net.ipv4.conf.all.log_martians = 1
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
# ...and the rest of the safe set
```

```bash
sudo sysctl --system
```

(I left three of the sixteen alone on purpose — more on that below.)

**SSH, minus the theatre** (`SSH-7408`). Seven sub-findings against a stock `sshd_config`. Debian supports drop-ins, so nothing in the main file gets touched:

```conf
# /etc/ssh/sshd_config.d/60-hardening.conf
AllowTcpForwarding no
AllowAgentForwarding no
TCPKeepAlive no
ClientAliveCountMax 2
MaxSessions 2
LogLevel VERBOSE
```

```bash
sudo sshd -t && sudo systemctl reload ssh
```

Always `sshd -t` before reloading — a syntax error in SSH config is how you lock yourself out of a remote box. That cleared six of the seven. The seventh was "move off port 22," which I skipped deliberately.

**Password policy** (`AUTH-9230`, `AUTH-9286`, `AUTH-9328`) in `/etc/login.defs`: a stricter default `UMASK 027`, a sane password max-age, and SHA rounds. These set defaults for *new* accounts, so there's no risk of expiring the account you're logged in as.

**And a few tools.** `fail2ban` was already running, but its config lived in `jail.conf`, which package updates overwrite — Lynis wants a `jail.local` (`DEB-0880`). One `cp`. Then a batch of small utilities each of which closes a finding: `libpam-tmpdir`, `debsums`, `apt-show-versions`, `auditd`, and `rkhunter` to satisfy the "install a malware scanner" check (`HRDN-7230`).

## The judgment calls — what I didn't fix

This is the part a scanner can't do for you. Several findings were technically valid and I still said no.

**`net.ipv4.conf.all.forwarding = 0`.** Lynis wants IP forwarding off. But this VM runs Docker, and Docker *needs* `ip_forward = 1` to route container traffic. Turn it off to please the auditor and you break every container on the box. Left on, documented in the drop-in.

**`kernel.modules_disabled = 1`.** This locks kernel module loading until the next reboot — a one-way switch. On a VM where I still occasionally load modules, that's more foot-gun than hardening. Declined.

**`kernel.unprivileged_bpf_disabled` → 1.** Lynis wanted `1`; the box was already at `2`, which is *stricter*. "Fixing" this would have made it less secure. This is the clearest example of why you read findings instead of applying them blindly.

**SSH on port 22.** SSH here is only reachable over Tailscale — there's no public port 22 to scan. Moving it to a high port would add friction and log noise for zero real security. Obscurity isn't the control; the network boundary is.

**Apache mod_evasive / modsecurity** (`HTTP-6640/6643`). I don't expose an Apache app that needs a WAF in front of it. Not applicable.

**Separate `/home` and `/var` partitions** (`FILE-6310`) and a **GRUB password** (`BOOT-5122`). Both are real hardening on bare metal. On a single-disk VM whose console access already implies host access, they're not worth a repartition and a boot-password I'll forget. Noted and parked.

The point isn't that these are wrong. It's that a hardening index treats every finding as equal, and your context doesn't. Knowing which to skip *is* the skill.

## Two things the audit taught me the hard way

**Installing a tool isn't configuring it.** Adding `auditd` cleared the "install an audit daemon" finding (`ACCT-9628`) — and immediately raised a new one:

```text
ACCT-9630  Audit daemon is enabled with an empty ruleset. Disable the daemon or define rules
```

Exactly right. An audit daemon with no rules logs nothing useful; it's a checkbox, not a control. Writing a real `auditd` ruleset is a job of its own, so it's on the list for next time rather than faked now.

**`rkhunter` dragged in a mail server.** Installing the rootkit scanner pulled `exim4` as a dependency (it wants an MTA to email its reports). Suddenly there was a mail daemon on a box that had no business running one. Worth checking where it listens:

```bash
$ ss -tlnp | grep :25
LISTEN 0 20 127.0.0.1:25   0.0.0.0:*
LISTEN 0 20     [::1]:25      [::]:*
```

Loopback only — Debian's exim4 defaults to local delivery, so it's not exposed. But that's the kind of thing you only find because you went looking: a hardening step quietly *added* surface. If I don't want the MTA, the fix is to remove it and give rkhunter a null mailer.

There was also a finding I'd half-solved already. `LOGG-2154` suggested shipping logs to an external host. I do — pfSense, auth, and syslog all flow into [Loki](/posts/homelab-siem-loki/) — just not in the plain rsyslog-to-remote shape Lynis probes for. Central logging exists; the auditor just can't see it from where it's standing.

## Where it landed

After the safe fixes and the deliberate skips, a second run:

```text
Hardening index : 80 [################    ]
Warnings        : 0
Suggestions     : 31
```

**68 → 80**, sixteen suggestions closed, and — more importantly — a written reason for every one still open. The remaining 31 split cleanly into *deliberate* (Docker forwarding, the SSH port, partitions, GRUB), *not-applicable* (Apache WAF modules), and *genuinely next* (an `auditd` ruleset, an AIDE file-integrity baseline, scheduling `debsums`). None of them are surprises anymore, which is the actual goal — an unaudited box has unknown gaps; this one has a documented backlog.

## Lesson

A hardening score is a compass, not a scoreboard. The two most useful outputs of this audit weren't points — they were a finding I rejected because it would've broken Docker, and a finding my own tooling *created* by installing a daemon with no rules. Run the scanner, take the free wins, and then do the part it can't: decide what actually applies to the system in front of you. A control you don't understand is just a number, and a tool with no rules is theatre.
