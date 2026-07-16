#!/usr/bin/env python3
"""SessionStart — inject live repo state + the reliability/front-matter reminders as
context for Claude. Always non-blocking; fails silently."""
import sys, json, os, subprocess

try:
    data = json.load(sys.stdin)
    proj = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()

    def git(*a):
        try:
            return subprocess.run(["git", "-C", proj, *a],
                                  capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:
            return ""

    branch = git("rev-parse", "--abbrev-ref", "HEAD") or "?"
    dirty = len([l for l in git("status", "--porcelain").splitlines() if l.strip()])
    ctx = (
        f"Repo state: branch `{branch}`, {dirty} uncommitted change(s).\n"
        "Reliability bar (docs/reliability-and-guardrails.md): validate in code, ground claims, "
        "don't invent facts not in the notes or blog-author-context.md.\n"
        "Every post needs front matter: title, date, draft, description, tags. Read "
        "blog-author-context.md before drafting or editing a post.\n"
        "Publish = git push origin main (Cloudflare Pages auto-deploys). Project hooks gate post "
        "front matter (PostToolUse), the Hugo build (Stop), and catastrophic Bash (PreToolUse)."
    )
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                             "additionalContext": ctx}}))
except Exception:
    pass
sys.exit(0)
