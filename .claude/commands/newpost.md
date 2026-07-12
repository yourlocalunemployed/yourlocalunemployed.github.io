---
description: Turn a raw notes/report file into a finished, published blog post
argument-hint: <path-to-notes-or-report>  (e.g. notes/vlan-segmentation.md or ~/report/foo.md)
allowed-tools: Read, Write, Edit, Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(hugo:*), Bash(cp:*), Bash(mv:*), Bash(chmod:*), Bash(ls:*)
---

First read `./blog-author-context.md` for my background and voice. Then:

1. **Read the raw notes/report** at: $ARGUMENTS
   If no path was given, list the files in `notes/` and ask me which one.
   The source may live outside the repo (e.g. `~/report/`) and may reference
   images in that same folder — note where they are for step 4.

2. **Rewrite the notes into a finished post** in my voice (per the author context):
   - First person, plain and concrete; assume a technical reader.
   - Keep the failures and the fixes — not just the clean result.
   - Preserve real commands, configs, and error output. Language-tag every code block.
   - Convert any passive "report" phrasing ("a rule was added") to first person ("I added a rule").
   - No marketing fluff. Short paragraphs. Cut anything that doesn't earn its place.
   - Don't invent project details that aren't in the notes or the author context — ask me.

3. **Create the file** `content/posts/<slug>.md`, slug = kebab-case of the title,
   with the full front matter every post on this blog uses:
   ```yaml
   ---
   title: "<title>"
   date: <current RFC3339 timestamp, e.g. 2026-07-12T21:30:00+10:00>
   draft: false
   description: "<one-line summary for SEO and social cards>"
   tags: [<3-8 relevant tags>]
   series: ["<Home Lab | Hardening Network | SPT Mods | ...>"]
   seriesTitle: "<short label for this entry within the series>"
   cover:
     image: "/images/posts/<cover>.png"
     alt: "<describe the cover image>"
     hiddenInSingle: true
   ---
   ```
   Reuse an existing `series` name if one fits; only coin a new one when nothing does.

4. **Relocate the images.** For each image the report references:
   - Copy it into `static/images/posts/` with a consistent kebab-case name
     prefixed by the post topic (e.g. `vlan-fw-rules-iot.png`); `chmod 644`.
   - Update the post's `![]()` paths to `/images/posts/<name>.png`.
   - Pick the clearest "it works / result" shot as the `cover`. It may also
     appear once in-body — `hiddenInSingle: true` stops it duplicating at the top.

5. **Archive the source.** Copy the raw notes/report into `notes/<slug>.md`
   (`chmod 644`) so the repo keeps the original alongside the published post.

6. **Add it to the projects page** if it documents a project: a `##` heading, a
   1–2 sentence description in the page's terse style, and a
   `[Read: <title> →](/posts/<slug>/)` link in `content/projects.md`.

7. **Build-check:** run `hugo --gc --minify` and confirm it builds cleanly —
   no errors, and every image resolves in `public/`.

8. **Show me the finished post and wait for my OK** before publishing.
   (This gate is here on purpose — see note below.)

9. **On my OK, publish:**
   - `git add -A`   (post, images, notes archive, projects page, rebuilt `public/`)
   - `git commit -m "post: <title>"`
   - `git push`
   → **Cloudflare Pages** rebuilds from source on push and deploys to
     `https://billalrehmani.pages.dev` automatically. No manual `hugo`/`rsync` step.

<!--
NOTE on going hands-off:
Step 8 stops for review because this blog is public and tied to your LinkedIn —
auto-publishing unreviewed text to a portfolio recruiters read is a real risk.
Once you trust the output after a handful of runs, delete step 8 to make it
fully one-shot, or run headless: `claude -p "/newpost notes/<file>.md"`.
-->
