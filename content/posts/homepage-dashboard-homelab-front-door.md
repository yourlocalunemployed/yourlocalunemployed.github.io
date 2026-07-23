---
title: "A Front Door for the Home Lab"
date: 2026-07-23T14:00:00+10:00
draft: false
description: "One page for the whole home lab with Homepage in Docker — no published ports, reverse-proxy plus wildcard TLS, and why the status dots (a green dot next to a dead link) taught me more than the links did."
tags: ["home-lab", "homepage", "docker", "caddy", "dashboard", "reverse-proxy", "self-hosting"]
series: ["Home Lab"]
seriesTitle: "Homelab dashboard"
cover:
  image: "/images/posts/homepage/dashboard.png"
  alt: "Homepage dashboard showing Infrastructure, Monitoring and Security service groups with live status dots"
  hiddenInSingle: true
---

At some point my lab crossed a line. I had a firewall, an identity provider, a password vault, dashboards, a log system, an alert router, and a vulnerability scanner — and I was typing subdomains from memory to reach any of them. Half the time I'd get one wrong.

So this project is small: **one page that links to everything**. It took under an hour, and it's the thing I now look at most.

![Homepage dashboard: Infrastructure, Monitoring and Security groups, each tile with a live status dot, host CPU/memory/disk across the top](/images/posts/homepage/dashboard.png)

## What Homepage is

Homepage is a self-hosted dashboard. You give it a YAML file listing your services, and it renders a clean page of tiles. That's the basic idea.

The part that makes it worth running, rather than just using browser bookmarks, is that it can show **live status** — whether each service is actually up — and pull real data from things you already run.

## The setup

It's one container. The interesting choices are in how it's wired:

```yaml
services:
  homepage:
    image: ghcr.io/gethomepage/homepage:latest
    container_name: homepage
    restart: unless-stopped
    volumes:
      - ./config:/app/config
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      HOMEPAGE_ALLOWED_HOSTS: home.<domain>
    networks:
      - caddy_web

networks:
  caddy_web:
    external: true
```

**No published ports.** The container doesn't expose anything to the network directly. Instead it joins the same Docker network as my reverse proxy, which reaches it internally by name. Nothing on my LAN can hit it except through the proxy — the same pattern I use for the password vault.

It also avoids a collision: my dashboards already use port 3000 on the host, and Homepage wants 3000 too. Since neither is published, they never meet.

**The reverse proxy entry** is three lines:

```caddy
	@home host home.<domain>
	handle @home {
		reverse_proxy homepage:3000
	}
```

Because my proxy holds a wildcard certificate for `*.<domain>`, the new subdomain gets HTTPS automatically. Nothing to register, nothing to renew.

## Two things that catch people

**`HOMEPAGE_ALLOWED_HOSTS` is mandatory.** Recent versions reject any request whose hostname isn't on this list. Miss it and you get a blank page with no useful error. It has to be the bare hostname — no `https://`, no trailing slash.

This isn't Homepage being awkward. The app makes requests *on your behalf* (to Docker, to service APIs), so it needs to know which hostnames it's legitimately being served under. Fair enough.

**The Docker socket is not really read-only.** Mounting `/var/run/docker.sock` is what lets Homepage see container status. It's tagged `:ro`, which sounds safe.

It isn't, particularly. Anything that can talk to the Docker socket can start containers, mount the host filesystem, and effectively become root on the host. The `:ro` stops writes to the socket file, not what you can *ask Docker to do* through it.

For a dashboard on a lab machine I've accepted that. But it's worth naming honestly rather than pasting the line and moving on — and if it bothers you, there's a thing called `docker-socket-proxy` that sits in front and only exposes the read-only endpoints.

## The config

Services are grouped in a YAML file. Each entry is a tile:

```yaml
- Security:
    - Vaultwarden:
        href: https://vault.<domain>
        description: Password vault
        icon: vaultwarden.png
        server: my-docker
        container: vaultwarden
```

Icons come from a built-in set — you just name the file, nothing to download.

The `server` and `container` lines are what add the live status dot. `server` points at a Docker connection defined in a second small file; `container` is the actual container name.

I split mine into three groups: **Infrastructure** (firewall, identity), **Monitoring** (dashboards, metrics, logs), and **Security** (vault, scanner). Not because it's necessary, but because the groups mirror how I think about the lab.

## The bit I didn't expect to care about

I set this up for the links. The **status indicators** turned out to be the valuable part — specifically for the services that have no web page at all.

My log shipper and log database don't have interfaces. You interact with them through a dashboard, never directly. So they're just... running, invisibly, and you'd never know if they stopped.

During my log-system build, the shipper silently stopped sending data for a stretch. There was no error I'd see — logs just quietly stopped arriving, and I only found out much later when a query came back empty. A red dot on a dashboard would have caught it in seconds.

So those two get tiles with **no link at all** — just a name and a status light:

```yaml
    - Log shipper:
        description: Ships logs to the database
        server: my-docker
        container: promtail
```

A tile you can't click, whose only job is to be green. That's arguably the most useful thing on the page.

I did the same for my identity provider's LDAP service — the piece my firewall login depends on. When that's down I have to fall back to a local break-glass account, and it's genuinely helpful to see *why* at a glance instead of debugging blind.

## A green dot next to a broken link

Here's a thing that confused me, and it turns out to be the most useful lesson in the whole project.

My vulnerability scanner's tile showed a **green "running" dot**. I clicked it. The page didn't load.

Both were correct. They just answer different questions.

**The status dot asks Docker: "is this container running?"** That's all. It never visits the link. It doesn't check whether the service responds, whether the port is reachable, or whether the URL is even right.

**The link is just a URL I typed into a config file.** Nothing validates it.

So a green dot beside a dead link isn't a bug — it's two independent facts, both true. The container was running fine. I simply couldn't reach it from where I was clicking.

Worth internalising if you build one of these: **a dashboard tells you what it's been told to check, not what you assume it's checking.**

### Why the link was dead

The scanner's web interface was published like this:

```text
127.0.0.1:9392 -> 443
```

That means: *on the host machine*, port 9392 forwards into the container's port 443. And `127.0.0.1` means **loopback only** — only the machine itself can connect, not anything else on the network.

So the link worked from the server's own desktop and nowhere else. My tile pointed at the server's LAN address, which that loopback binding refuses.

The fix was the same pattern as everything else in my lab: put it behind the reverse proxy and give it a proper subdomain.

### The part that took three attempts

This is where I learned something genuinely useful about Docker networking.

My proxy runs in a container. The scanner runs in a container. When one container talks to another, **the host's port mappings don't exist.** That `127.0.0.1:9392` is a rule for traffic arriving at the *host*. Container-to-container traffic never touches it.

So the proxy has to target the **container's own port**, not the host mapping. I kept pointing it at 9392 — the number I'd been typing in my browser — and getting this:

```text
tls: first record does not look like a TLS handshake -> 502
```

Translated: my proxy tried to start an encrypted conversation, and whatever answered replied in plain text. Inside the container, port 9392 is plain HTTP. Port **443** is the encrypted one — the actual web interface.

Pointing at 443 worked immediately:

```caddy
	@scan host scan.<domain>
	handle @scan {
		reverse_proxy https://greenbone-nginx:443 {
			transport http {
				tls_insecure_skip_verify
			}
		}
	}
```

That last option needs explaining, because it looks alarming. The scanner generates its own certificate, which nothing officially vouches for. Without `tls_insecure_skip_verify`, my proxy refuses to talk to it. The connection is **still encrypted** — the proxy just doesn't check who signed the certificate. For one container talking to another on a private network, that's a reasonable call.

![The OpenVAS/Greenbone login page now served over HTTPS through the reverse proxy at its own subdomain](/images/posts/homepage/openvas-via-proxy.png)

### And then the tile still didn't work

Because I'd fixed the *service* and forgotten the *dashboard*. The tile was still pointing at the old dead address. One line changed, refresh, done.

Which loops right back to the lesson: the dot and the link don't know about each other. Fixing one doesn't fix the other.

## Host stats

One more small file adds a live resource bar:

```yaml
- resources:
    cpu: true
    memory: true
    disk: /
```

CPU, memory and disk across the top of the page. Useful right now because I've just added a vulnerability scanner to a box that was already running a lot — I want to see memory pressure coming before it becomes a problem.

## Was it worth it?

It's the smallest project I've written up, and probably the highest ratio of daily use to effort spent.

But there's a slightly more serious point underneath. **A lab you can't see the state of is a lab you're guessing about.** I'd built monitoring, alerting, and log analysis — all of which are excellent at telling me about *problems*. None of them answered the simpler question: *is everything currently on?*

A dashboard of green dots answers that in one glance, and it costs almost nothing.

## Takeaways

- **Reverse proxy + wildcard certificate makes new services nearly free.** Three lines and a new subdomain works, with HTTPS, immediately.
- **Not publishing ports avoids collisions you'd otherwise have to work around.** Two services can both want port 3000 if neither is exposed to the host.
- **Read-only Docker socket access isn't as read-only as it sounds.** Know what you're accepting.
- **Status indicators are most valuable for services with no interface** — those are exactly the ones that fail silently.
- **A green dot and a working link are different claims.** The dot asks Docker if a container is running. The link is a string you typed. Neither checks the other.
- **Host port mappings don't apply between containers.** When one container talks to another, target the container's real port — the `host:container` mapping is only for traffic arriving at the host.
- **Small projects are allowed.** Not everything has to be a week of debugging.

*Next: putting authentication in front of my metrics database, which is currently sitting there with no login at all — something my own vulnerability scanner was quick to point out.*
