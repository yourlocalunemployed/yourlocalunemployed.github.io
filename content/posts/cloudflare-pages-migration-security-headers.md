---
title: "Moving the Blog off GitHub Pages — for Real Security Headers"
date: 2026-07-12T23:29:00+10:00
draft: false
description: "Why I moved this Hugo blog from GitHub Pages to Cloudflare Pages: GitHub Pages can't set custom HTTP response headers, so a meta-tag CSP was as far as my security posture could go."
tags: ["cloudflare", "github-pages", "hugo", "security-headers", "csp"]
cover:
  image: "/images/posts/cloudflare-migration-pipeline.svg"
  alt: "Before/after diagram: GitHub repo → GitHub Actions → github.io, versus GitHub repo → Cloudflare Pages → pages.dev with security headers"
  hiddenInSingle: true
---

The blog you're reading changed builders. The `git push` that publishes it is
identical; what runs on the other end isn't. It used to be a GitHub Actions job
that built the site and served it from `yourlocalunemployed.github.io`. Now
Cloudflare Pages builds from the same repo and serves it at
`billalrehmani.pages.dev`.

![Same git push, different builder — now with real HTTP response headers](/images/posts/cloudflare-migration-pipeline.svg)

I didn't move for speed or for a nicer dashboard. I moved because GitHub Pages
won't let me set HTTP response headers, and for a blog that's meant to be a
security portfolio, that was the one limit I couldn't design around.

## The actual problem: a meta tag is not response headers

On GitHub Pages the only place I could express a Content-Security-Policy was a
`<meta http-equiv>` tag in the page `<head>`:

```html
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' https://giscus.app; ...; base-uri 'self'; form-action 'self';">
```

That works for the directives a meta tag is allowed to carry. The problem is the
ones it isn't. Browsers **ignore** `frame-ancestors`, `report-uri`, and
`sandbox` when the CSP arrives via `<meta>` — they're only honoured as a real
response header. So the directive that actually stops my pages being framed for
clickjacking was silently doing nothing.

And that's just CSP. A whole set of security headers can *only* exist as
response headers — there is no meta equivalent at all:

- `Strict-Transport-Security` (HSTS)
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options`
- `Permissions-Policy`
- `Cross-Origin-Opener-Policy`

On GitHub Pages, none of those were being sent. There's no setting for it —
Pages doesn't expose custom response headers, full stop. My security posture was
capped at whatever a meta tag could say, and a meta tag can't say most of it.

Cloudflare Pages reads a `_headers` file and turns it into real response
headers. That single capability is the whole reason for the move.

## The `_headers` file

Hugo copies anything in `static/` verbatim into `public/`, so
`static/_headers` lands at the site root where Cloudflare looks for it:

```conf
/*
  Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' https://giscus.app; style-src 'self' 'unsafe-inline' https://giscus.app; font-src 'self'; img-src 'self' data: https://avatars.githubusercontent.com; connect-src 'self' https://giscus.app; frame-src https://giscus.app; base-uri 'self'; form-action 'self'; object-src 'none'; frame-ancestors 'none'
  Strict-Transport-Security: max-age=31536000
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=()
  X-XSS-Protection: 0
  Cross-Origin-Opener-Policy: same-origin
```

The `/*` matches every route. Note the two directives the meta version couldn't
enforce are back and doing real work now: `object-src 'none'` and
`frame-ancestors 'none'`.

I kept the `<meta>` CSP in the template as a fallback — it still applies during
local `hugo server` preview, where nothing is serving a `_headers` file. The two
have to stay in sync by hand, so there's a comment at the top of `_headers`
saying exactly that, plus a reminder that if I ever wire up GoatCounter
analytics I have to add its origins to the CSP in *both* files. Duplicated
config is a liability; the least I can do is leave a note next to both copies.

## Pointing Hugo at the new URL

`baseURL` has to match wherever the site actually lives, or every absolute link
and the RSS feed point at the old host:

```toml
baseURL = "https://billalrehmani.pages.dev/"
```

## The build config that isn't in the repo

Cloudflare Pages' build settings live in its dashboard, not in a file in the
repo, which caught me out for a minute — there's nothing to `git blame` if it
breaks. For the record:

- **Build command:** `hugo --gc --minify`
- **Output directory:** `public`
- **Environment:** `HUGO_VERSION = 0.163.3` (the extended build)

Two things worth knowing. Pin `HUGO_VERSION` — Cloudflare's default Hugo is old,
and a version mismatch against what I run locally is exactly the kind of "works
on my machine" gap I don't want in a build I can't see. And the extended build
is fine here specifically because PaperMod ships plain CSS: no Dart Sass in the
toolchain to install or break. The theme is a git submodule, and Cloudflare
clones the repo recursively, so it comes down on its own — no extra step.

## Retiring the old pipeline

For a short window both pipelines were live, which meant every push
double-deployed: GitHub Actions rebuilt `github.io` *and* Cloudflare rebuilt
`pages.dev`. Two copies of the site from one push is confusing and pointless, so
I deleted the workflow:

```bash
git rm .github/workflows/hugo.yml
```

That's the whole retirement. With no workflow file, GitHub Actions has nothing to
run, and a push now only reaches Cloudflare.

One manual step is left that can't be done from the repo: GitHub → **Settings →
Pages → Source: None**, to take the stale `github.io` copy offline. Deleting the
Action stops *new* builds; it doesn't unpublish what Pages already served.

## Checking it actually worked

The point of the whole exercise was response headers, so that's what I verified —
straight from the command line, filtered down to the ones I care about:

```bash
curl -sI https://billalrehmani.pages.dev | grep -Ei 'content-security|strict-transport|x-frame|x-content|referrer|permissions'
```

Seeing `strict-transport-security`, `x-frame-options`, and the full CSP come back
as actual headers — not as a meta tag the browser half-honours — is the
difference the move was for. [securityheaders.com](https://securityheaders.com)
tells the same story more legibly if you'd rather see a grade than read raw
headers.

## What I traded

Nothing about the writing workflow changed — it's still notes in the repo,
`/newpost`, review, `git push`. What changed underneath:

- **Gained:** real security headers, plus Cloudflare's edge for free —
  automatic TLS, a global CDN, and DDoS mitigation I don't have to think about.
- **Cost:** the publish path now runs through both GitHub and Cloudflare, so
  both accounts hold 2FA and both matter. That's a slightly wider blast radius
  than "just GitHub" — a fair trade for headers I couldn't get any other way.

`public/` is still committed to the repo, which is now redundant since Cloudflare
rebuilds it from source on every push. It's harmless, so I've left it; pruning it
is a cleanup for another day, not a blocker.

Same `git push`. Different builder. This time the site tells the browser how to
protect it.
