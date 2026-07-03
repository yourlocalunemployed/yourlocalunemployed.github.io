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

The blog you're reading right now was published by the exact pipeline this post describes. I'll explain why that's worth writing up.

![Hugo — the static site generator this blog runs on](/images/posts/hugo-logo.svg)

## Why Hugo, and why self-hosted

I needed a place to document real technical work — networking, security, mod projects — somewhere I could point to from LinkedIn. Hosted platforms like Medium were out immediately: no ownership of the content, paywall friction for readers, branding that isn't mine.

I landed on Hugo. It's a single Go binary. No Node, no `node_modules`, no npm dependency tree to patch and audit. For a security portfolio that matters — the attack surface of the blog itself should be as small as what I'm writing about securing.

It builds to plain static files, so serving it is trivial. The tradeoff is I own uptime and patching. For this use case, that's a feature.

Stack:
- Hugo + PaperMod theme
- Posts are Markdown in `content/posts/`
- `hugo --minify` builds to `public/`
- Deploy: rsync to my Debian box, served behind nginx with TLS

## Setting up the Claude Code publishing pipeline

I didn't want to hand-format every post. The target workflow was: drop raw notes into the repo, run one command, get a finished post committed and deployed.

Claude Code supports slash commands — custom prompts stored in `.claude/commands/` that you invoke with `/commandname`. I built `/newpost` around that.

Three files make it work:

**`CLAUDE.md`** — the project instruction file Hugo picks up every session. Holds the stack, post conventions, front matter spec, and a pointer to the context file.

**`blog-author-context.md`** — my background and writing voice, kept separate so it stays portable. What I do, what the blog is for, how to write in my voice, what not to invent.

**`.claude/commands/newpost.md`** — the slash command itself. It reads the notes file, rewrites it in my voice per the author context, creates `content/posts/<slug>.md` with correct front matter, commits, and deploys.

The workflow now:

```bash
# drop raw notes in the repo
notes/some-post.md

# run the command
/newpost notes/some-post.md
```

Claude reads my author context, rewrites the notes as a finished post, shows me the draft, and waits for my OK before committing and pushing.

I kept the review gate intentionally. This blog is public and tied to my name. Auto-shipping unreviewed text to a portfolio isn't a risk I want to take until I've run it enough to trust the output. The command has a note explaining how to remove the gate once you do.

## The gap worth knowing about: two separate Claude memory systems

This is the part I didn't find documented clearly anywhere.

The Claude chat app and Claude Code are both Claude, but they run completely separate memory systems that don't sync.

The **chat app** builds memory automatically. It synthesises notes from past conversations on roughly a daily cycle. If you've been chatting with Claude for months, it knows your background, your projects, your preferences.

**Claude Code** knows none of that. It has two mechanisms: `CLAUDE.md` (manual, version-controlled, per-repo) and auto memory (notes it writes itself over time in `~/.claude/projects/`). The auto memory builds up the mechanical project context. But it starts blank. And it never pulls from the chat app.

So when I first ran Claude Code on this repo, it had no idea who I was — even though the chat app had months of context. I had to tell it everything from scratch.

The fix was to export the relevant background into a portable context file — `blog-author-context.md` — that `CLAUDE.md` references at the top. Every session, every command, it loads that context first. It's a manual bridge, but it works and it's version-controlled.

The pattern: anything you want every Claude Code session to know should live in a file the repo loads explicitly. Don't assume context from the chat app will carry over.

## What the first few runs actually looked like

Not magic on run one. The first draft had the right structure but the voice was off — too clean, too much passive construction, not enough "here's what broke and why."

I updated `blog-author-context.md` to be more explicit: include failures and the fix, not just the polished result. Keep real commands and error output. Short paragraphs. Cut anything that doesn't earn its place.

By the second or third run it was producing drafts I was happy to approve with minor edits.

There are also placeholders to fill before deploy actually works — `<user>` and `<server>` in the rsync line. The pipeline stops if you haven't set those. I'll document the full server config (nginx block, TLS setup) in a follow-up post.

## What's next

Now that the pipeline's working, the backlog of real write-ups:

- Debian home network hardening — guest segmentation, DNS config, router hardening on the Arcadyan HWG2025
- SPT-AKI mod port — hardening a TypeScript-to-C# port for community release, debugging multi-mod server errors
- The GLSL shader pack — deferred rendering, PBR, screen-space path tracing, and the NVIDIA driver issues that nearly broke it

This post was the foundation. The rest is filling it in.
