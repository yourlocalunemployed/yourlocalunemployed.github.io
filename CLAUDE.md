# Blog — project instructions for Claude Code

Personal technical blog, built with **Hugo** (static site generator).
Content is markdown; the site builds to static files and deploys to
**GitHub Pages** via a push-triggered Actions workflow.

## Author background and voice
Author background, real project material, and writing voice live in
`./blog-author-context.md`. **Read it before drafting or editing any post.**
Every post must match that voice — no exceptions.

## Stack (and why)
- Hugo: single Go binary, no Node/npm dependency tree. Chosen for a small
  dependency/attack surface and clean self-hosting on Debian.
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
Push-triggered **GitHub Pages**. Remote `origin` is
`github.com/yourlocalunemployed/yourlocalunemployed.github.io`; the workflow
`.github/workflows/hugo.yml` runs on every push to `main`, builds Hugo
(extended, pinned via `HUGO_VERSION`) on the runner, and publishes to Pages.

After a post is approved, publishing is just a push:
```bash
git add -A && git commit -m "post: <title>"
git push origin main    # the Action builds + deploys — no other step
```
There is no manual `hugo`/`rsync` step. `public/` is committed but the Action
rebuilds it from source, so committing it is redundant (harmless). The old
rsync-to-Debian deploy is retired — ignore any reference to it.

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
