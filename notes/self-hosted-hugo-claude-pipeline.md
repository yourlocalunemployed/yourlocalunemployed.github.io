# RAW NOTES — first post: self-hosted Hugo blog + Claude Code publishing pipeline

(These are raw notes. /newpost turns them into a finished post in my voice.
Expand into prose, keep the failures + decisions, add real commands.)

## Images for post
- Hugo logo: `/images/posts/hugo-logo.svg` — place near "Why Hugo" section
- Hugo on GitHub: `/images/posts/hugo-github-screenshot.png` — place near stack/deploy section

![Hugo static site generator](/images/posts/hugo-logo.svg)

## The goal
- Wanted a blog to show real technical work on LinkedIn — networking/security focus.
- Decided the blog itself should be a portfolio piece, not just hold posts.
- So: self-host it on my own Debian box, and automate publishing with Claude Code.

## Why Hugo (not Astro / not a hosted platform)
- Single Go binary. No Node, no node_modules, no npm dependency tree to patch/audit.
- Small dependency + attack surface — which is the point for a security portfolio.
- Builds to plain static files → trivial to serve and lock down.
- Hosted platforms (Medium etc.) = no ownership, paywalls, branding isn't mine.
- Tradeoff I accepted: I own uptime + patching. For a security blog that's a feature.

## The stack
- Hugo + PaperMod theme. Posts are markdown in content/posts/.
- `hugo --minify` builds to public/.
- Deploy: rsync public/ to the Debian box, served behind [nginx OR caddy] with TLS.
  TODO: paste the actual server-block / Caddyfile + the rsync line I use.

## The interesting bit — a Claude Code publishing pipeline
- Don't want to hand-format every post. Want: drop raw notes → get a published post.
- Set up three files in the repo:
  - CLAUDE.md — standing project rules, loaded every session.
  - blog-author-context.md — my background + writing voice, referenced from CLAUDE.md.
  - .claude/commands/newpost.md — a /newpost slash command.
- Workflow now: drop a file in notes/, run `/newpost notes/x.md`. It rewrites the
  notes in my voice, files the post with front matter, commits, deploys.
- Kept a review gate before publish on purpose — public blog tied to my name,
  not auto-shipping unreviewed text. Goes fully hands-off once I trust the voice.

## The nugget worth writing up — bridging two separate memories
- Claude has TWO memory systems that DON'T sync:
  - The chat app: auto-synthesizes memory from past conversations (~daily).
  - Claude Code: CLAUDE.md (manual) + auto memory (notes it writes per-repo).
- So Claude Code started nearly blank on context the chat app already had.
- Fix: exported the relevant background into a portable context file the repo
  loads every session. Manual bridge, but it works and stays version-controlled.
- Point of the post: this is a real gap people hit moving from chat to agentic CLI,
  and the portable-context-file pattern is the clean way around it.

## Honest caveats to include
- First few runs need voice tuning in the context file — not magic on run one.
- Placeholders to fill (server, web root) before deploy works.
- Auto memory builds up the mechanical stuff over time; context file holds the voice.

## Closing angle
- The blog you're reading was published by this exact pipeline. Meta but true.
- Next posts: the Debian network hardening write-up, the SPT-AKI mod port, the shader pack.
