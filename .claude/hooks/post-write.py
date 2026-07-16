#!/usr/bin/env python3
"""PostToolUse(Edit|Write):
  - content/posts/*.md  -> validate required front-matter keys (block on miss).
  - layouts/**/*.html   -> if the file has an inline <script>, remind about CSP hashes.
Fails OPEN on any error."""
import sys, json, os, re

REQUIRED = ["title", "date", "draft", "description", "tags"]


def out(obj):
    print(json.dumps(obj))
    sys.exit(0)


try:
    data = json.load(sys.stdin)
    ti = data.get("tool_input") or {}
    tr = data.get("tool_response") or {}
    path = ti.get("file_path") or tr.get("filePath") or ""
    if not path:
        sys.exit(0)
    cwd = data.get("cwd") or ""
    rel = path[len(cwd) + 1:] if cwd and path.startswith(cwd) else path
    base = os.path.basename(path)

    # --- front-matter validation for posts ---
    if re.search(r'(^|/)content/posts/[^/]+\.md$', path):
        try:
            text = open(path, encoding="utf-8").read()
        except Exception:
            sys.exit(0)
        m = re.match(r'^﻿?---\s*\n(.*?)\n---\s*\n', text, re.S)
        if not m:
            out({"decision": "block",
                 "reason": f"{base}: post is missing its YAML front-matter block. "
                           f"Add a `---` block with: {', '.join(REQUIRED)} (see CLAUDE.md)."})
        fm = m.group(1)
        missing = [k for k in REQUIRED if not re.search(r'(?m)^\s*' + re.escape(k) + r'\s*:', fm)]
        if missing:
            out({"decision": "block",
                 "reason": f"{base}: front matter is missing required key(s): {', '.join(missing)}. "
                           f"Every post needs {', '.join(REQUIRED)} (see CLAUDE.md)."})
        sys.exit(0)

    # --- CSP-hash reminder for inline-script layout edits (non-blocking) ---
    if re.search(r'(^|/)layouts/.*\.html$', path):
        try:
            has_inline = "<script" in open(path, encoding="utf-8").read()
        except Exception:
            has_inline = False
        if has_inline:
            out({
                "systemMessage": f"{base} has inline <script> — regenerate CSP hashes if you changed one.",
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": (
                        f"You edited {rel}, which contains an inline <script>. Per CLAUDE.md the production "
                        "script-src in static/_headers is hash-locked (no 'unsafe-inline'). If you changed any "
                        "inline script, regenerate the sha256 hashes with ~/Desktop/my_scripts/csp-hashes.sh and "
                        "paste them into static/_headers — otherwise the script is silently blocked in production."
                    ),
                },
            })
    sys.exit(0)
except Exception:
    pass
sys.exit(0)
