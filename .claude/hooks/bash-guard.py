#!/usr/bin/env python3
"""PreToolUse(Bash) guard — deny catastrophic commands only. Fails OPEN on any error
so a bug here can never block legitimate work. Deliberately narrow: it targets a
handful of irreversible mistakes, not a general sandbox."""
import sys, json, re


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    sys.exit(0)


try:
    data = json.load(sys.stdin)
    cmd = (data.get("tool_input") or {}).get("command", "")
    if not isinstance(cmd, str) or not cmd.strip():
        sys.exit(0)

    # 1. rm -r/-R of a catastrophic target (root, home, cwd, parent, bare glob).
    #    Specific named paths like `rm -rf public` are intentionally allowed.
    BAD = {"/", "/*", "~", "~/", "$HOME", "${HOME}", ".", "./", "..", "../", "*"}
    for m in re.finditer(r'(?:^|[;&|]|\s)rm\s+([^;&|]*)', cmd):
        toks = m.group(1).split()
        if any(re.match(r'-[a-zA-Z]*[rR]', t) for t in toks) and any(t in BAD for t in toks):
            deny("Refused: `rm -r` targeting / ~ $HOME . .. or * is catastrophic. "
                 "Delete a specific named path (e.g. `public`) instead.")

    # 2. git force-push (can rewrite published history on main; --force-with-lease is fine)
    for m in re.finditer(r'git\s+push\b([^;&|]*)', cmd):
        seg = m.group(1)
        if (re.search(r'--force(?!-with-lease)', seg)
                or re.search(r'(?:^|\s)-f(?:\s|$)', seg)
                or re.search(r'\s\+\S', seg)):
            deny("Refused: git force-push can rewrite published history on main. "
                 "Use `--force-with-lease` and confirm with the user first.")

    # 3. pipe remote content straight into a shell
    if re.search(r'\b(?:curl|wget)\b[^|]*\|\s*(?:sudo\s+)?(?:sh|bash|zsh|dash)\b', cmd):
        deny("Refused: piping downloaded content into a shell. Download, inspect, then run.")

    # 4. raw-disk / filesystem-destroying commands + fork bomb
    if re.search(r'\bdd\b[^;&|]*\bof=/dev/', cmd) or re.search(r'\bmkfs\b', cmd) or re.search(r'>\s*/dev/sd', cmd):
        deny("Refused: writing to a raw disk device.")
    if re.search(r':\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;', cmd):
        deny("Refused: fork bomb.")

    # 5. recursive chmod/chown at the filesystem root
    if re.search(r'\bch(?:mod|own)\s+-[a-zA-Z]*R[a-zA-Z]*\s+[^;&|]*\s/(?:\s|$)', cmd):
        deny("Refused: recursive chmod/chown at /.")

except Exception:
    pass
sys.exit(0)
