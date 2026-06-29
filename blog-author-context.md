# Author context — blog

Background and voice for Claude Code when drafting/editing posts for this blog.
Referenced from CLAUDE.md so it loads every session.

## Who's writing
- IT student (TAFE NSW), focused on networking and cybersecurity over heavy programming.
- Building toward roles/certs in that space (Network+, Security+ on the radar).
- Comfortable on Linux — daily Debian use, custom dev, self-hosting, system tinkering.
- High-end gaming PC (RTX 4090). Hands-on, project-driven learner.

## What the blog is for
- A public portfolio for LinkedIn — demonstrating real technical work to recruiters
  and peers in networking/security.
- Recurring theme: using the Claude app and Claude Code on Debian as part of an
  actual workflow, with honest write-ups of what worked and what didn't.

## Project material to draw on (real, mine — reference accurately)
- Self-hosting and home-network hardening on Debian: guest network segmentation,
  DNS config, router security (Arcadyan HWG2025, NBN ~500Mb).
- Game modding: SPT-AKI (Single Player Tarkov) — troubleshooting multi-mod server
  errors; hardened a TypeScript→C# port ("BiggerBang") for community release.
- Graphics: built a GLSL shader pack ("UltraRealism") for Minecraft Java / Forge —
  deferred rendering, PBR, screen-space path tracing, TAA; debugged Iris + NVIDIA
  driver issues (shader version downgrades, inlining includes, float-only hashing).
- Using Claude Code agentically: CLAUDE.md, slash commands, headless runs.

## Voice and style (write like this)
- First person, plain and concrete. Technical reader assumed — don't over-explain basics.
- Direct and honest. Include the failures and the fix, not just the polished result.
- No marketing fluff, no hype, no "in today's fast-paced world" openers.
- Short paragraphs. Real commands, configs, and error messages where they help.
- Code blocks always get a language tag.

## Don't
- Don't invent project details. If something isn't here and I haven't told you, ask.
- Don't claim certs or job titles I don't have.
- Don't pad word count. Cut anything that doesn't earn its place.

## Wire-up
Add to CLAUDE.md:
> Author background and voice for all posts live in `./blog-author-context.md`.
> Read it before drafting or editing any post.
