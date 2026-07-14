---
title: "Colophon — How This Blog Is Built"
date: 2026-07-14T12:00:00+10:00
description: "The stack, the pipeline, and the security decisions behind billsblog.dev — a static site that's meant to be as defensible as the work it documents."
hideMeta: true
ShowToc: true
ShowBreadCrumbs: true
comments: false
---

Most of what I write here is about *other* projects. This page is about the blog
itself — because how it's built is part of the point.

## The stack, and why it's static

This is a **static site**: a folder of plain HTML, CSS, and JS with no server-side
code and no database. I write posts in Markdown; **Hugo** (a single Go binary)
builds them into files; **Cloudflare Pages** serves them worldwide.

I chose static deliberately. A dynamic CMS runs code for every visitor — a live
attack surface of plugins, a database, and a server that can be compromised. A
static site is built *once*, ahead of time, so there's no per-request code to
exploit. For a blog that documents security work, the blog should be as
defensible as the work it shows. Hugo helps: one binary, no Node, no
`node_modules` tree to patch and audit.

- **Generator:** Hugo (extended) + the PaperMod theme, heavily customised
- **Content:** Markdown in `content/`, YAML front matter
- **Host:** Cloudflare Pages (global edge, automatic TLS, DDoS mitigation)
- **Domain:** `billsblog.dev` — a `.dev` TLD, which browsers force to HTTPS

## The publishing pipeline

There's no manual deploy step. The whole flow is one `git push`:

```text
edit Markdown ─► git commit + push ─► GitHub ─► Cloudflare builds (hugo --gc --minify) ─► served at the edge
```

Cloudflare watches the repo and rebuilds on every push to `main`. The generated
`public/` folder isn't even committed — Cloudflare regenerates it, so tracking it
would just be noise.

## Security — the part I actually enjoy

Because there's no backend, the security story is about protecting the *pipeline*
(accounts, tokens, DNS) and telling the browser how to behave (HTTP headers).

- **Content Security Policy:** a strict allowlist of what the page may load and
  run. `script-src` is **hash-locked** — it lists the SHA-256 hash of each inline
  script instead of `'unsafe-inline'`, so an injected `<script>` (different hash)
  is blocked. That's the real XSS defence.
- **HSTS** (`includeSubDomains; preload`), `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY` / `frame-ancestors 'none'`, `Referrer-Policy`,
  `Permissions-Policy`, and `Cross-Origin-Opener-Policy` — served from a
  `_headers` file at the edge.
- **The token** that pushes to GitHub is a fine-grained PAT scoped to just this
  one repo, with an expiry and a rotation habit.

I wrote up the two big moves in detail:
[moving off GitHub Pages for real security headers](/posts/cloudflare-pages-migration-security-headers/)
and [registering my own domain](/posts/registering-billsblog-dev/).

## The over-engineering (I know)

The blog is also a playground. Under the hood there's a WebGL shader background,
a preloader, smooth momentum scrolling, a command palette (**Ctrl/⌘ + K**), an
interactive [terminal](/terminal/), scroll-driven text reveals, and — yes — a
Konami code. All of it is CSS-first; any JavaScript is external and served from
the site's own origin so the hash-locked CSP stays clean, and everything respects
`prefers-reduced-motion`. It's deliberately excessive. It's also *fast on repeat
visits* — fingerprinted assets cached for a year, heavy media kept off mobile.

## Colophon details

- **Type:** Rajdhani (self-hosted `woff2`)
- **Theme accent:** `#E81A1A` on a near-black background
- **Analytics:** GoatCounter — no cookies, no cross-site tracking
- **Comments:** giscus, backed by GitHub Discussions (no database of my own)
- **Build:** `hugo --gc --minify`, `HUGO_VERSION` pinned

See the [changelog](/changelog/) for how it got here, and the [stats](/stats/)
for where it stands.
