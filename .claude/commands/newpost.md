---
description: Turn a raw notes file into a finished, published blog post
argument-hint: <path-to-notes-file>  (e.g. notes/debian-claude-code.md)
allowed-tools: Read, Write, Edit, Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(hugo:*), Bash(rsync:*)
---

First read `./blog-author-context.md` for my background and voice. Then:

1. **Read the raw notes** at: $ARGUMENTS
   If no path was given, list the files in `notes/` and ask me which one.

2. **Rewrite the notes into a finished post** in my voice (per the author context):
   - First person, plain and concrete; assume a technical reader.
   - Keep the failures and the fixes — not just the clean result.
   - Preserve real commands, configs, and error output. Language tag every code block.
   - No marketing fluff. Short paragraphs. Cut anything that doesn't earn its place.
   - Don't invent project details that aren't in the notes or the author context — ask me.

3. **Create the file** `content/posts/<slug>.md`, slug = kebab-case of the title, with:
   ```yaml
   ---
   title: "<title>"
   date: <current RFC3339 timestamp>
   draft: false
   description: "<one-line summary>"
   tags: [<3-6 relevant tags>]
   ---
   ```

4. **Show me the finished post and wait for my OK** before publishing.
   (This gate is here on purpose — see note below.)

5. **On my OK, publish:**
   - `git add content/posts/<slug>.md`
   - `git commit -m "post: <title>"`
   - `git push`
   - Deploy: `hugo --minify && rsync -az --delete public/ <user>@<server>:/var/www/blog/`
     (skip the rsync if this repo deploys automatically on push)

<!--
NOTE on going hands-off:
Step 4 stops for review because this blog is public and tied to your LinkedIn —
auto-publishing unreviewed text to a portfolio recruiters read is a real risk.
Once you trust the output after a handful of runs, delete step 4 to make it
fully one-shot, or run headless: `claude -p "/newpost notes/<file>.md"`.
-->
