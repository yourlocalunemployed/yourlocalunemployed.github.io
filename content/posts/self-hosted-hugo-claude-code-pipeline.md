---
title: "Self-Hosting a Hugo Blog with a Claude Code Publishing Pipeline"
date: 2026-06-29T12:00:00+10:00
draft: false
description: "How I set up a Hugo blog on Debian, automated publishing with Claude Code slash commands, and bridged the gap between two separate Claude memory systems."
tags: ["hugo", "claude-code", "self-hosting", "debian", "automation"]
cover:
  image: "/images/posts/hugo-github-screenshot.png"
  alt: "The Hugo blog running on GitHub Pages"
  hiddenInSingle: true
---

The blog you're reading was published by the pipeline this post describes.

![Hugo — the static site generator this blog runs on](/images/posts/hugo-logo.svg)

## Why Hugo, and why self-hosted

I needed somewhere to document real technical work — networking, security, mod projects — that I could point to from LinkedIn. Hosted platforms were out: no content ownership, paywall friction, someone else's branding.

Hugo won on attack surface. It's a single Go binary — no Node, no `node_modules`, no npm dependency tree to patch and audit. For a security portfolio, the blog itself should be as defensible as the work it documents. It builds to plain static files, so serving is trivial; the trade-off is owning uptime and patching, which for this use case is a feature.

The stack:

- Hugo + PaperMod theme
- Posts as Markdown in `content/posts/`
- `hugo --minify` builds to `public/`
- Deploy: rsync to a Debian box behind nginx with TLS

## The publishing pipeline

The target workflow: drop raw notes in the repo, run one command, get a finished post committed and deployed. Claude Code's slash commands (custom prompts in `.claude/commands/`) made that practical. Three files do the work:

- **`CLAUDE.md`** — project instructions loaded every session: stack, post conventions, front matter spec, and a pointer to the context file.
- **`blog-author-context.md`** — my background and writing voice, kept separate so it stays portable.
- **`.claude/commands/newpost.md`** — the `/newpost` command: reads a notes file, rewrites it in my voice, creates `content/posts/<slug>.md` with correct front matter, commits, and deploys.

```bash
# drop raw notes in the repo
notes/some-post.md

# run the command
/newpost notes/some-post.md
```

Claude drafts the post and waits for my approval before committing. I kept that review gate deliberately — this blog is public and tied to my name, and auto-publishing unreviewed text isn't a risk worth taking until the output has earned trust.

## The gap worth knowing: two separate Claude memory systems

This wasn't clearly documented anywhere I looked. The Claude chat app and Claude Code run completely separate memory systems that never sync:

- The **chat app** builds memory automatically from past conversations — after months of use, it knows your background and projects.
- **Claude Code** starts blank. It has `CLAUDE.md` (manual, version-controlled, per-repo) and its own auto memory in `~/.claude/projects/` — and it never pulls from the chat app.

So on first run, Claude Code had no idea who I was, despite months of chat history. The fix: export the relevant background into `blog-author-context.md` and have `CLAUDE.md` load it every session. A manual bridge, but version-controlled and reliable.

The pattern: anything every session should know must live in a file the repo loads explicitly. Don't assume chat-app context carries over.

## What the first runs looked like

The first draft had the right structure but the wrong voice — too clean, too passive, not enough about what broke. I made the author context explicit: include failures and fixes, keep real commands and error output, short paragraphs, cut anything that doesn't earn its place. By the third run, drafts needed only minor edits.

The rsync deploy also has `<user>` and `<server>` placeholders that must be set before deployment works; the pipeline stops if they aren't.

## What's next

With the pipeline working, the backlog of write-ups: home network hardening on the Arcadyan HWG2025, the SPT-AKI mod port, and further lab builds. This post was the foundation; the rest is filling it in.
