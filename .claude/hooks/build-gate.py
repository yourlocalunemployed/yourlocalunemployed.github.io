#!/usr/bin/env python3
"""Stop — block finishing on a broken Hugo build, but only when build-affecting files
have uncommitted changes (so plain Q&A turns aren't gated). Builds to a throwaway dir
so it never touches public/. Fails OPEN (never traps the agent) except on a real build
failure; respects stop_hook_active to avoid loops."""
import sys, json, os, subprocess, shutil

try:
    data = json.load(sys.stdin)
    if data.get("stop_hook_active"):
        sys.exit(0)  # already continuing from a Stop hook — don't loop
    proj = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    hugo = shutil.which("hugo")
    if not hugo:
        sys.exit(0)  # can't build → don't trap the agent

    try:
        status = subprocess.run(["git", "-C", proj, "status", "--porcelain"],
                                capture_output=True, text=True, timeout=15).stdout
    except Exception:
        status = ""
    WATCH = ("content/", "layouts/", "assets/", "static/", "data/",
             "hugo.toml", "hugo.yaml", "config.toml", "i18n/", "archetypes/")
    changed = any(any(seg in line for seg in WATCH) for line in status.splitlines())
    if not changed:
        sys.exit(0)  # nothing that affects the build changed

    r = subprocess.run([hugo, "--gc", "--minify", "-d", "/tmp/claude-hugo-buildcheck"],
                       cwd=proj, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        tail = "\n".join((r.stderr or r.stdout or "").strip().splitlines()[-25:])
        print(json.dumps({
            "decision": "block",
            "reason": "Hugo build is broken — fix it before finishing (a broken build won't deploy "
                      "to Cloudflare Pages):\n" + tail,
        }))
        sys.exit(0)
except Exception:
    pass
sys.exit(0)
