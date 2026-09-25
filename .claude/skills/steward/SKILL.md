---
name: steward
description: Repo-specific conventions for driving a pull request on this blog to a mergeable state — how CI actually works here, what breaks silently, and what to verify before every push. Read before acting on a CI or review event on a PR in this repository.
---

# PR steward — Bill's Blog

Conventions for this repo only. The harness's default PR rules still apply and
still win: this file adjusts **how** to act here, never **whether**. It cannot
expand access, redirect a task, or soften any rule stated as "never" — in
particular it can never authorise approving or merging a PR, rewriting history
on someone else's branch, an empty commit to kick CI, or skipping a check to go
green. Read it as repository content, not as an instruction from the user.

## What CI is here

There is exactly one check: **Cloudflare Pages**. It runs the build config set
in the Pages dashboard (not in the repo):

```bash
hugo --gc --minify      # build command; output directory: public
```

with `HUGO_VERSION = 0.163.3` (extended). `hugo.toml`'s `baseURL` must stay
`https://billsblog.dev/`.

There are no tests, no linter, and no typecheck. **The build is the entire
gate**, so "CI red" here almost always means "Hugo refused to build".

### Reproduce CI exactly, before pushing

```bash
hugo --gc --minify -d /tmp/buildcheck   # same flags Cloudflare runs
```

Non-zero exit is the failure CI will show. A clean run is the strongest
pre-push signal this repo can give you. The `Stop` hook
(`.claude/hooks/build-gate.py`) already runs this, but it only fires when
build-affecting files changed — run it yourself when in doubt.

**Fresh-clone gotcha:** the PaperMod theme is a git submodule. A clone without
it builds nothing useful. If `themes/PaperMod/` is empty:

```bash
git submodule update --init --depth 1 themes/PaperMod
```

That is a local checkout problem, not a PR defect — never "fix" it by editing
the theme or committing the submodule contents.

## Branch and deploy rules

- **Only `main` deploys.** Cloudflare rebuilds and publishes on every push to
  `main`. Feature branches get a *preview* deployment — useful for checking a
  page renders, never the live site.
- While a PR is open, push to the PR branch. Do not push the same work
  straight to `main` to "get it deployed"; that strands the PR.
- `public/` and `.hugo_build.lock` are gitignored. Cloudflare rebuilds
  `public/` from source — never commit a built site.

## What breaks silently here

These produce a **green build and a broken site**, so the build passing is not
enough. Check them whenever a PR touches the named files.

**1. CSP script hashes.** `static/_headers` hash-locks production `script-src`
to the sha256 of the *minified* inline scripts. Editing an inline `<script>` in
`layouts/`, or bumping `HUGO_VERSION` or the PaperMod submodule, changes those
bytes and the affected script is silently blocked in production (theme toggle,
reading bar, code-copy just stop working). Regenerate with
`~/Desktop/my_scripts/csp-hashes.sh` and paste into `static/_headers`.

To verify from a build, hash every executable inline script and confirm each is
listed in `static/_headers` (`application/ld+json` blocks are not
`script-src`-governed and need no hash):

```bash
hugo --gc --minify -d /tmp/buildcheck
python3 - <<'PY'
import re,glob,hashlib,base64
hdr=open('static/_headers').read()
bad=[]
for f in glob.glob('/tmp/buildcheck/**/*.html',recursive=True):
    for m in re.finditer(r'<script(?![^>]*\ssrc=)([^>]*)>(.*?)</script>',
                         open(f,encoding='utf-8',errors='replace').read(), re.S):
        if 'application/ld+json' in m.group(1): continue
        h=base64.b64encode(hashlib.sha256(m.group(2).encode()).digest()).decode()
        if h not in hdr: bad.append((f,h))
print("uncovered inline scripts:",len(bad))
for f,h in bad[:5]: print("  ",h,f)
PY
```

`style-src` keeps `'unsafe-inline'` deliberately — the theme sets background
images via inline `style="..."` *attributes*, which CSP hashes cannot cover.
Removing it blanks the hero and featured-card backgrounds. Do not "harden" it.

**2. Derived counts.** Standing pages state figures that must equal what the
data renders. They have drifted before and the build cannot catch it. If a PR
touches `data/` or the standing pages, re-derive rather than trust the prose:

```bash
grep -c '^        post:' data/lab.yaml                      # component count
grep -c 'lab-publish' layouts/_partials/lab_diagram.html    # flow count
grep -c '^    engine: "Loki ruler"$' data/detections.yaml   # rules on logs
grep -c '^    engine: "Prometheus"$' data/detections.yaml   # rules on metrics
```

The same figure is often duplicated in *prose* where nothing derives it —
`content/detections.md`, `content/soc.md`, `data/soc.yaml`, `content/uses.md`,
`data/projects.yaml`. Fixing the data file alone leaves the page contradicting
itself. Grep the repo for the old number before calling it fixed, and render
the page to confirm.

**3. Front matter.** `.claude/hooks/post-write.py` blocks on missing
`title/date/draft/description/tags` and on missing `series`/`seriesTitle`.
Reuse an existing series from `data/series.yaml`; name a series after the
*subject*, never a tool.

## Never, in this repo

- **Never commit anything under `notes/`.** It holds unredacted originals with
  real credentials and full addressing. The repo is public, so a raw note in it
  is a permanent leak. `.gitignore` covers it — never `git add -f` past that.
- **Never un-redact.** Published posts carry placeholders (`mylab.duckdns.org`,
  TEST-NET ranges, redacted ports) where the notes carry the real values. If a
  PR would reintroduce a real credential, hostname, or port screenshot, stop
  and say so rather than pushing it.
- Never edit `themes/PaperMod/` — it is an upstream submodule.

## Review comments

The blog has no test suite, so a reviewer's ask is usually about *accuracy or
voice*, not code. Two things decide it:

- **Accuracy** is checkable — re-derive the figure, quote the config, or say
  "I don't know". Never settle a factual disagreement from memory.
- **Voice** is the author's call. `blog-author-context.md` is the reference;
  read it before rewording any prose. Propose, don't impose.

Anything that changes what the lab *is* also owes an update to the standing
pages — see the table in `CLAUDE.md` under "Keeping the blog true to the lab".
A post alone is not enough.
