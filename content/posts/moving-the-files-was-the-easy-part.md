---
title: "simple file structure organised change a cause for a long troubleshooting week"
date: 2026-09-04T22:10:00+10:00
draft: false
description: "I reorganised the homelab's directory layout. Every container came back healthy, and four things broke anyway — none of them visible from docker ps."
tags: ["home-lab", "docker", "systemd", "prometheus", "backups", "troubleshooting", "bash"]
series: ["Home Lab"]
seriesTitle: "When the paths moved"
---

Since my homelab was expanding in services and containers, my home directory and folder structures started to become more clustered and unorganised, a lot of my containers were on my home directory without a proper nested structure, this made navigating through my configuration files harder, to ensure a smooth transition, I got my Codex agent to do a read audit check before migrating. Twelve service directories that had
been sitting at the top level went into `~/homelab/`, split by what they are:

```text
~/homelab/containers/   the compose stacks
~/homelab/apps/         things I wrote
~/homelab/security/     scan output
~/homelab/state/        bind-mounted data
~/homelab/backups/      the nightly sets
```

The containers were re-pointed at the new paths and recreated. All 28 came back
healthy, no missing mounts, no restart loops. `docker ps` was clean.

A note on how this was built, because the working model matters to the story. I
run this lab as an AI-assisted workflow: I direct the agents, decide what
changes, run anything that needs root, and investigate the results. **Codex** did
the read-only audit and carried out the migration itself — it ran out of budget
partway through and left its handoff blank, which is part of why the gaps below
went unrecorded. **Claude Code** wrote the checkers and the fix scripts and did
most of the diagnosis. I didn't write the scripts in this post, and I'm not going
to pretend otherwise. What I did was decide what to look at, insist on evidence,
and refuse a few answers that turned out to be wrong.

That distinction is the point rather than a disclaimer. Every failure below got
past at least one agent, and two of them were caused by a tool an agent wrote and
I accepted too readily.

Despite the clean dir structure change, four things were broken anyway, and not one of them showed up there.

## The backup script had five stale paths

`backup-lab.sh` builds its destination from a variable, so most of its paths look
harmless until you expand them:

```bash
HOME_DIR=/home/student
DEST=$HOME_DIR/backups/$STAMP
sqlite3 "$HOME_DIR/vaultwarden/data/db.sqlite3" ".backup '$DEST/vault-db.sqlite3'"
```

Both of those moved. The script's mtime was the same as the migration's, which
made it *look* updated. It wasn't.

It also tars a set of config files by **relative** name:

```bash
tar czf "$DEST/config.tar.gz" \
  -C $HOME_DIR authentik/.env authentik/docker-compose.yml \
                caddy/.env caddy/Caddyfile
```

I got claude to write a checker that rewrote `$HOME_DIR/...` patterns and reported the script
clean. It was blind to those seven relative names by construction — a tool finding
nothing has two explanations, and I only considered one.

## The failure was in a script I never opened

The nightly run failed at 20:30 and I had the wrong theory about why. The unit
does this:

```ini
ExecStartPre=/usr/local/sbin/lab-backup-wait-docker.sh
ExecStart=/usr/local/sbin/backup-lab.sh
```

That first script waits up to ten minutes for the database container before the
backup starts, so a catch-up run after a reboot doesn't die on a container that
isn't up yet. Line 14:

```bash
COMPOSE=/home/student/authentik/docker-compose.yml
```

A literal path, not a variable — invisible to the checker. It waited its full ten
minutes for a container it was looking up through a file that no longer existed:

```text
20:30:02 -> 20:40:26  FAILED   (10m24s)
22:14:22 -> 22:14:25  OK       (3s)
```

Claude had read that `ExecStartPre` line the day before and still traced the
chain one level short. I hadn't thought to ask it to.

## A permission bit deleted five alerts

Half my custom metrics vanished. The exporter was running fine — exit 0, file
written, correct contents. node_exporter just couldn't read it:

```text
textfile_collector/   drwxr-x---  root:node_exporter
clock.prom            -rw-r-----  root:root      <- group is root. invisible.
docker.prom           -rw-r--r--  root:root      <- readable. survived.
```

Same directory, same writer, different mode. The clock metrics feed five
Prometheus alert rules, including the one that catches the fault that has twice
broken my TOTP logins. Those rules didn't fire an error — they had nothing to
evaluate, which looks identical to nothing being wrong.

The fix belongs in the exporter, not in a one-off `chmod`. It rewrites that file
every five minutes; a manual fix reverts before you've finished reading the
output.

## The network moved house without telling anyone

This was the expensive one. The reverse proxy's docker network was created by
hand, years ago, with no subnet pinned. Recreating it let Docker pick a new one:

```text
was:  172.18.0.0/16, gateway 172.18.0.1
now:  172.28.0.0/16, gateway 172.28.0.1
```

Everything that reached the host through that gateway broke at once — three
reverse-proxy routes, fourteen dashboard widgets, a Prometheus systemd drop-in
from July, and a socket unit for the audit plane.

The part I didn't expect: two of those **kept working anyway**. A socket bound at
boot survives the interface disappearing underneath it. Prometheus was serving
happily on an address that no longer existed on any interface. It only died when
something restarted it — which, in this case, was a fix script of ours going
after a different problem:

```text
prometheus.service: Scheduled restart job, restart counter is at 2172.
level=ERROR msg="Unable to start web listener"
  err="listen tcp 172.18.0.1:9090: bind: cannot assign requested address"
```

We didn't cause that. We detonated it early. It would have gone off at the next
reboot instead, at whatever hour that happened to be, and the thing that tells me
when services break would have been the thing that was down.

## What I'd tell myself before the next move

A directory move isn't the change. The change is every reference to those paths
that lives somewhere a container health check can't see:

- **Root-owned scripts, including the ones units call via `ExecStartPre`.** Grep
  for literal paths, not just `$VAR/...`.
- **File modes**, compared against a file whose output still works.
- **Docker network subnets**, against anything that hardcodes a gateway.
- **Sockets that are still listening.** Restart the service deliberately and see
  if it comes back, rather than finding out at 3am.

And don't trust mtimes. Mine said one script had been migrated and another was
stale. Both were wrong, in opposite directions. Test the paths, not the
timestamps.

The network is still unpinned, incidentally. Pinning it means recreating it,
which means every container on it restarts — so it's waiting for a reboot, when
that costs nothing. Until then it's one `docker network rm` away from doing the
whole thing again.
