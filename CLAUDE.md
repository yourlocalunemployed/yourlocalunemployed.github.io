# Blog — project instructions for Claude Code

Personal technical blog, built with **Hugo** (static site generator).
Content is markdown; the site builds to static files and is self-hosted on Debian.

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
Self-hosted on Debian. After a post is approved:
```bash
hugo --minify
rsync -az --delete public/ <user>@<server>:/var/www/blog/
```
Fill in `<user>` and `<server>`. If you later switch to push-triggered hosting
(Netlify / Vercel / Pages), drop the rsync and let `git push` trigger the build.
