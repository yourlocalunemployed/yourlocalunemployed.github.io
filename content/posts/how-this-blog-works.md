---
title: "How This Blog Works — the Static-Site Pipeline and the Security Behind It"
date: 2026-07-16T21:30:00+10:00
draft: false
description: "A plain-English tour of how this blog gets from Markdown to the internet — static site, Hugo, Cloudflare Pages, DNS/TLS — and the security decisions (a hash-locked CSP, HSTS, a scoped token) baked into the pipeline."
tags: ["meta", "hugo", "cloudflare", "static-site", "security", "csp", "tls", "dns", "blogging"]
cover:
  image: "/images/posts/cloudflare-migration-pipeline.svg"
  alt: "The publish pipeline — a git push to a builder that serves real HTTP security headers"
  hiddenInSingle: true
---

A plain-English tour of *this* blog: what it's made of, how it gets from my laptop to the internet, the security decisions baked into it, and what I stay cautious about — so the pipeline isn't a black box.

**Stack:** Hugo · PaperMod · Git / GitHub · Cloudflare Pages · billsblog.dev

---

## The 10-second mental model

This blog is a **static site**. That means it's just a folder of plain `.html`, `.css`, `.js`, image and video files. There is **no server running my code, no database, no backend**. I write in Markdown, a program called **Hugo** turns it into those files, **Git / GitHub** stores the source, and **Cloudflare Pages** builds and serves it worldwide at **https://billsblog.dev**.

Because nothing runs on the server per visit, there's very little to "hack" in the traditional sense. The security job is mostly about protecting the **pipeline** (my accounts, my token, my domain) and telling the visitor's **browser how to behave** (via HTTP headers). Keep those two ideas in mind and the rest follows.

---

## The pieces, and what each one does

| Piece | What it is | Why it's here |
|---|---|---|
| **Markdown** | A simple text format (`# heading`, `**bold**`) | How I write posts, in `content/posts/*.md` |
| **Hugo** | A *static site generator* — one Go binary | Turns Markdown + theme into the final HTML. No Node/npm, so a small attack surface |
| **PaperMod** | A Hugo *theme* (a git submodule) | The design/layout. I override bits of it in `layouts/` and `assets/` |
| **Git** | Version control | Tracks every change as a "commit" I can roll back to |
| **GitHub** | Hosts the git repo online | The single source of truth; also where Cloudflare pulls from |
| **Cloudflare Pages** | The build + hosting service | Runs Hugo on every push, serves the result globally |
| **Cloudflare Registrar / DNS** | Where I rent `billsblog.dev` + point it | Turns the name into the site |
| **GoatCounter** | Privacy-friendly analytics | Counts visitors without cookies |
| **giscus** | Comments, backed by GitHub Discussions | Lets readers comment without me running a database |

The key insight: **most of these are things other people run for me.** My "server" is Cloudflare's global network. My "database" for comments is GitHub. That's why the site is cheap, fast, and hard to break — but also why my *accounts* with those services are the thing worth protecting.

---

## Static vs dynamic — why this choice is a security win

- A **dynamic** site (e.g. WordPress) runs code *on the server for every visitor*: PHP talks to a database, assembles the page, sends it back. That means a live attack surface — SQL injection, vulnerable plugins, a server that can be compromised and made to run attacker code.
- A **static** site is built **once**, ahead of time. The server just hands out pre-made files. There's no database to inject, no per-request code to exploit.

So the attack surface shrinks to four things:

1. **The source repo** — could someone push malicious changes? → protect GitHub.
2. **The build** — could the build be tampered with? → protect Cloudflare.
3. **The delivery** — could someone intercept or impersonate the site? → HTTPS + DNS.
4. **The client side** — could injected JavaScript run in a visitor's browser? → Content Security Policy.

Almost everything security-related here maps to one of those four.

---

## The publish pipeline (from my keyboard to the world)

```text
  I edit             git                GitHub             Cloudflare Pages
 content/*.md  ─►  commit + push  ─►  stores source  ─►  runs `hugo --gc --minify`
                                                             │
                                                             ▼
                                                    outputs the public/ folder
                                                             │
                                                             ▼
                                            serves it from ~300 edge locations
                                                    at https://billsblog.dev
```

- **Commit** = a saved snapshot of my changes, with a message.
- **Push** = upload those commits to GitHub.
- **Build** = Cloudflare runs Hugo, which reads the source and *generates* the final `public/` folder of HTML/CSS/JS.
- **Deploy** = Cloudflare copies that output to its edge servers worldwide.

I never run `hugo` to publish — pushing to `main` triggers all of it. (`public/` is even gitignored, because Cloudflare regenerates it every time; committing it was redundant.)

---

## Git & GitHub — and why "the repo is public" matters

Git stores the project's full history. GitHub keeps a copy online. Two things I keep front of mind:

1. **The repo is public.** Anyone can read every file and every past commit. That's fine for a blog — but it means I must **never commit a secret** (a token, a password, an API key). Once it's in git history, it's effectively public forever, even if I delete it later. If it ever happens, the fix is to **rotate the secret immediately** — *revoke the leaked one*, not just delete the file.
2. **Pushing requires proof I'm allowed to.** That proof is a **Personal Access Token (PAT)** — see the secrets section below.

---

## What's an API? (and where they hide in this setup)

An **API** (Application Programming Interface) is a defined way for one program to talk to another over a contract: you send a request to an **endpoint** (a URL), with some data, and get a structured response back (usually JSON). It's how software talks to software without a human clicking buttons.

The blog itself has **no backend API** — it's just files. But APIs still appear around the edges:

- **GitHub's git service:** when I `git push`, my machine makes an authenticated HTTPS request to GitHub. The token is how it proves who it is.
- **GitHub's REST API:** I've used it (via `curl`) to check a token's scopes and look at the Pages settings. Same idea — a URL you send an authenticated request to.
- **GoatCounter:** when someone loads a page, a tiny script sends a request to `billal.goatcounter.com` to record the visit. That's the page *calling an API*.
- **giscus:** talks to GitHub's Discussions API to load and store comments.

This matters for security because **the Content Security Policy controls which APIs the pages are allowed to call** from a visitor's browser (the `connect-src` directive — below). If injected code tried to phone home to an attacker's server, the CSP would block the connection.

---

## DNS & the domain — how `billsblog.dev` finds the site

When someone types `billsblog.dev`, their computer asks the **DNS** (Domain Name System — the internet's phone book) "where does this name point?" The answer routes them to Cloudflare's edge, which serves the files.

The chain I own:

- **Registrar** — who I rent the name from (Cloudflare Registrar). Renew it or the name is lost.
- **Nameservers / DNS records** — Cloudflare holds a record pointing `billsblog.dev` at the Pages project.
- **DNSSEC** — cryptographically *signs* the DNS answers so an attacker can't forge "billsblog.dev lives over here" and hijack visitors.

**Things to be cautious of:** losing the registrar account (2FA + registrar lock), letting the domain expire (auto-renew), and DNS hijacking (DNSSEC). This is the *one* new attack surface a custom domain adds over the old `*.pages.dev` subdomain.

---

## HTTPS / TLS — the padlock

**TLS** is the encryption that makes it **HTTPS**. It does two jobs:

1. **Encrypts** traffic between the browser and the server, so nobody on the network can read or tamper with it.
2. **Proves identity** — the server presents a **certificate** vouching that it really is `billsblog.dev`, issued by a trusted authority.

Cloudflare provisions and renews the certificate automatically. And because I chose a **`.dev`** domain — a TLD that's on the browser **HSTS preload list** — browsers *refuse* to load it over plain HTTP at all. My own **HSTS** header (`Strict-Transport-Security: max-age=… ; includeSubDomains; preload`) reinforces this: "always use HTTPS for this site, never downgrade."

---

## Security headers & CSP — the part I spent the most effort on

**HTTP response headers** are instructions the server attaches to every file it sends, telling the browser how to treat it. Mine are set in `static/_headers` (Cloudflare reads that file). The set:

| Header | Plain meaning |
|---|---|
| `Strict-Transport-Security` | Always use HTTPS |
| `X-Content-Type-Options: nosniff` | Don't guess file types (prevents some tricks) |
| `X-Frame-Options: DENY` + `frame-ancestors 'none'` | Nobody can embed the site in an `<iframe>` (anti-clickjacking) |
| `Referrer-Policy` | Limit what URL info leaks to other sites |
| `Permissions-Policy` | Deny camera/mic/geolocation/etc. by default |
| `Cross-Origin-Opener-Policy` | Isolate the page from other windows |
| `Content-Security-Policy` | **The big one — see below** |

### Content Security Policy (CSP), explained

A CSP is a **strict allowlist of what the page may load and run**. The browser enforces it. If something isn't on the list, it's blocked — no matter how it got onto the page. It's the main defence against **XSS** (cross-site scripting: tricking a page into running attacker-supplied JavaScript).

It's made of **directives**, each controlling one type of resource:

- `default-src 'self'` — by default, only load things from my own origin.
- `script-src` — where JavaScript may come from.
- `style-src` — where CSS may come from.
- `img-src`, `font-src`, `connect-src` (APIs the page may call), `frame-src`, etc.

`'self'` means "same origin as the page." So when the site moved from `pages.dev` to `billsblog.dev`, the CSP needed *zero* changes — `'self'` just means the new domain.

### The clever bit: hash-locking the scripts

The lazy way to allow my own inline `<script>`s is `'unsafe-inline'` — but that allows **any** inline script, including one an attacker injects. That defeats the point. Instead, `script-src` lists the **SHA-256 hash** of each legitimate inline script:

```text
script-src 'self' https://giscus.app https://gc.zgo.at 'sha256-bOIl…' 'sha256-UBD9…' …
```

The browser hashes each inline script it finds; only scripts whose content matches a listed hash are allowed to run. An injected script has a different hash → **blocked**. This is why:

- Any real JavaScript I add lives in an **external file** (`assets/js/effects.js`, served from `'self'`) — external same-origin scripts are allowed by `'self'` and don't need a hash.
- If I (or a Hugo/PaperMod upgrade) change an inline script, its bytes change, its hash changes, and the old hash goes stale → that script silently breaks. The fix: re-run my `csp-hashes.sh` helper and paste the new hashes in.

`style-src` deliberately keeps `'unsafe-inline'` — the theme sets background images via inline `style="…"` **attributes**, which hashes can't cover. The trade-off is acceptable: inline CSS can't execute JavaScript, so the risk is low.

### Two layers

- `static/_headers` → the **strict** production policy Cloudflare enforces.
- The `<meta>` CSP in `layouts/_partials/extend_head.html` → a **loose** fallback so the local `hugo server` preview (which isn't minified, so the hashes wouldn't match) still works. In production both apply, and the strict header does the real blocking.

---

## Client-side JavaScript & why I'm fussy about it

All the effects (command palette, glitch title, cursor spotlight, and the rest) are **JavaScript that runs in the visitor's browser**, not on any server. This is where XSS lives, so the discipline is:

- Keep JS in an **external file from my own origin** → `script-src 'self'` allows it, no hash needed, and it's fingerprinted (`effects.min.<hash>.js`) with an integrity attribute (SRI) so a tampered file won't run.
- Avoid inline scripts; if one is unavoidable, it must be hash-listed.

Net effect: even if an attacker found a way to inject markup, they can't run script, because their script is neither `'self'` nor a listed hash.

---

## Secrets & tokens — the thing to guard most

To push to GitHub from my machine, git authenticates with a **fine-grained Personal Access Token (PAT)**, stored in `~/.git-credentials`. Mine is:

- **Scoped** to *only* the blog's repo, permission *Contents: Read/write* — the minimum needed to push. Not "all my repos."
- **Time-limited** — it expires, and after that `git push` fails auth until I rotate it (I keep a helper script for that, and a reminder scheduled).

The rules that matter, generally:

- **Never** paste a token into a chat, screenshot, commit, or public place. (I rotated mine after a copy once ended up somewhere it shouldn't — the fix is to *revoke* the leaked one, not just delete the file.)
- **Scope minimally** and **set an expiry** — so a leak is small and self-healing.
- **Rotate** on exposure or expiry, and **revoke** the old one (deleting the file isn't enough — the token is only dead once GitHub revokes it).
- Turn on **2FA** for GitHub *and* Cloudflare — the whole publish path runs through those two accounts.

---

## What to be cautious of — a practical checklist

- **Never commit secrets.** The repo is public and git history is forever.
- **2FA on GitHub + Cloudflare.**
- **Rotate the PAT** on its expiry (or sooner if exposed).
- **Domain hygiene:** auto-renew, registrar lock, DNSSEC on. Don't let it lapse.
- **After a Hugo/PaperMod upgrade,** the minified inline scripts can change → CSP hashes go stale → theme toggle / reading bar / code-copy silently break. Re-run `csp-hashes.sh`, update `_headers`, and test.
- **Adding any third-party thing** (a new analytics tool, an embed, an external font, a widget): it will be **blocked by the CSP** until I add its origin to the right directive. That block is the CSP doing its job — understand exactly what's being allowed in before adding it.
- **Asset sizes:** big images/videos bloat the repo and slow the site. Compress them (one DOOM clip went from 128 MB to 6.5 MB). A background video should be a few MB, not hundreds.
- **Read the diffs before committing.** Especially when a tool (Claude included) generates changes — `git diff` and skim what actually changed. That habit is how you *stop* relying blindly and start understanding.

---

## Verify it yourself (poke at the site)

You learn this stuff fastest by inspecting the real thing:

```bash
# See the security headers the site actually sends:
curl -sI https://billsblog.dev/ | grep -iE 'content-security|strict-transport|x-frame|referrer|permissions'

# See the generated HTML (View Source in the browser does the same):
curl -s https://billsblog.dev/ | less

# Check DNS resolution and DNSSEC:
dig billsblog.dev +short
dig billsblog.dev +dnssec | grep -i rrsig      # signed = DNSSEC working

# Inspect the TLS certificate:
echo | openssl s_client -connect billsblog.dev:443 -servername billsblog.dev 2>/dev/null | openssl x509 -noout -issuer -dates

# Run the whole site locally, exactly as Hugo builds it (drafts included):
hugo server -D          # then open http://localhost:1313
```

Also worth a visit: **securityheaders.com** and **hstspreload.org** (grade your headers), and browser **DevTools → Console** (CSP violations show up there).

---

## Glossary

- **Static site generator** — a tool that turns source (Markdown + templates) into plain HTML files, ahead of time. (Hugo.)
- **Front matter** — the `---`-fenced metadata at the top of a post (title, date, tags).
- **Repo / commit / push** — a project's history / a saved snapshot / uploading snapshots to GitHub.
- **PAT** — Personal Access Token; a scoped, expiring password for automated git.
- **CDN / edge** — a network of servers near users that cache and serve files fast. (Cloudflare.)
- **TLS / HTTPS** — encryption + identity for web traffic.
- **HSTS** — a header (and browser list) forcing HTTPS.
- **CSP** — Content Security Policy; an allowlist of what a page may load/run.
- **XSS** — cross-site scripting; injecting malicious JS into a page. CSP is the defence.
- **DNS / DNSSEC** — the internet's name→address lookup / cryptographic signing of those answers.
- **API / endpoint** — a program-to-program interface / the URL you send requests to.
- **Origin** — scheme + domain + port (e.g. `https://billsblog.dev`). `'self'` in CSP means "this origin."

---

The goal isn't to memorise all of this — it's to know *which drawer each concept lives in*, so that when something breaks or I want to add something, I know where to look and what question to ask. A static site is a small, honest machine: source in, files out, a handful of headers telling the browser how to behave. Understand those, and there's very little left that's mysterious.
