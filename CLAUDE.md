# Blog — project instructions for Claude Code

Personal technical blog, built with **Hugo** (static site generator).
Content is markdown; the site builds to static files and deploys to
**Cloudflare Pages** on every push to `main`.

## Author background and voice
Author background, real project material, and writing voice live in
`./blog-author-context.md`. **Read it before drafting or editing any post.**
Every post must match that voice — no exceptions.

## Stack (and why)
- Hugo: single Go binary, no Node/npm dependency tree. Chosen for a small
  dependency/attack surface and clean, low-maintenance deploys.
- Posts: `content/posts/<slug>.md`, markdown with YAML front matter.
- Build output: `public/`.
- Local preview: `hugo server -D` (includes drafts).
- Theme: PaperMod (minimal, dev-blog friendly). If the theme uses
  `content/blog/` instead of `content/posts/`, follow the theme's path.

## Post front matter — always include
```yaml
---
title: "..."
date: <current RFC3339 timestamp, e.g. 2026-06-29T14:30:00+10:00>
draft: false
description: "one-line summary for SEO and social cards"
tags: ["...", "..."]
---
```

## Conventions
- One post = one file in `content/posts/`; slug = kebab-case of the title.
- Every code block gets a language tag (```bash, ```ts, ```glsl, ```conf, ...).
- Keep real commands, configs, and error output intact — don't blur them into
  vague prose. The specifics are the value.
- Short paragraphs. No marketing fluff. Honest about what failed and how it was fixed.
- Don't invent project details. If something isn't in the author context and
  I haven't told you, ask before writing it as fact.

## Publishing
Use the `/newpost` command (`.claude/commands/newpost.md`). It turns a raw notes
file into a finished post, files it correctly, commits, and deploys.

## Deploy
Push-triggered **Cloudflare Pages**. The Pages project `billalrehmani` is
connected to `origin`
(`github.com/yourlocalunemployed/yourlocalunemployed.github.io`) and rebuilds on
every push to `main`, serving the site at **https://billalrehmani.pages.dev**.

Cloudflare build config (set in the Pages dashboard, not the repo):
- Build command: `hugo --gc --minify`
- Output directory: `public`
- Env: `HUGO_VERSION = 0.163.3` (extended; no Dart Sass — PaperMod ships plain CSS)

After a post is approved, publishing is just a push:
```bash
git add -A && git commit -m "post: <title>"
git push origin main    # Cloudflare Pages builds + deploys — no other step
```
No manual `hugo`/`rsync` step. `baseURL` in `hugo.toml` must match the Pages URL
(`https://billalrehmani.pages.dev/`). Security headers are served from
`static/_headers`. Its production **`script-src` is hash-locked** — it lists
`'sha256-...'` of the inline scripts instead of `'unsafe-inline'`, so injected
inline scripts are blocked. **`style-src` keeps `'unsafe-inline'`** on purpose: the
theme sets background images via inline `style="background-image:url(...)"`
attributes (hero/site bg in `list.html`/`extend_footer.html` + per-post
featured-card covers), and CSP hashes can't cover style *attributes* — removing it
blanks those backgrounds. The `<meta>` CSP in `layouts/_partials/extend_head.html`
is kept fully loose (`'unsafe-inline'` for scripts too) as the local `hugo server`
preview fallback (preview isn't minified, so the script hashes wouldn't match). If
you edit an inline script or bump Hugo/PaperMod, regenerate the script hashes with
`~/Desktop/my_scripts/csp-hashes.sh` and paste them into `static/_headers` (else the
affected script silently breaks). `public/` and `.hugo_build.lock` are
gitignored — Cloudflare rebuilds `public/` from source, so committing it was
redundant (untracked 2026-07-12). The old GitHub Pages Action and the even
older rsync-to-Debian deploy are both retired.

## Resuming after a shutdown
This VM gets shut down between sessions. Transcripts and the `~/.claude` memory
files survive a normal shutdown, but **don't rely on replaying a long
conversation** — it's slow and expensive. Instead:
- Durable facts live in **memory files** (auto-loaded each session) and this
  **CLAUDE.md**. Anything that must survive a VM *rebuild* goes in the **repo**
  (it's pushed to GitHub); `~/.claude` does not.
- At a good stopping point, checkpoint "where I left off" into a memory file or a
  repo note rather than trusting the live context to still be there.
- Start fresh next session and let the memory index + this file rehydrate the
  essentials cheaply; use `claude -c` / `claude -r` only to continue a specific
  in-flight thread.
