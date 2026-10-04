# Blog agent handoff — contract between the homelab agent and the repo agent

**Status: proposed. Phase 0 is this document. Phases 1–3 are not built yet.**

This file is the interface between two agents that never share a conversation:

- the **homelab agent** — Bill's centralised Claude, which runs on the lab, sees
  the real infrastructure, and writes the draft after a project finishes;
- the **repo agent** — Claude Code working in this repository, which turns a
  draft into a published post and keeps the standing pages honest.

They can't talk. They share exactly one surface: this git repository. So the
handoff has to be a file both can read, and a contract neither is trusted to
follow on its own.

---

## Why this is shaped the way it is

**Anything pushed to this repo is permanent.** Not a caution — a finding. Two
screenshots in this repo were redacted in a later commit, and the unredacted
originals are still one `git show` away, because the redaction happened *after*
the push. See `docs/session-logs/2026-09-25-audit-guardrails-and-taxonomy.md`.

That single fact decides the whole design:

> Redaction happens on the homelab side, **before** the push. The repo agent
> and CI are the second line, not the first. By the time anything reaches this
> repo, a leak is already permanent.

The repo agent cannot undo a leak. It can only refuse to build on one, and say
so loudly.

---

## The flow

```
homelab project finishes
   │
   ▼
homelab agent  ──> redacts  ──> writes handoff/<slug>.yaml + images
   │                              pushes branch  draft/<slug>
   ▼
CI leak gate   ──> FAILS  ──> branch is quarantined, nothing proceeds
   │ passes
   ▼
repo agent     ──> voice pass, images, front matter, series
               ──> reconciles standing pages + derived counts
               ──> opens a PR with a Cloudflare preview URL
   │
   ▼
Bill reviews the diff  ──> merge = publish to billsblog.dev
```

The human gate at the end stays. `.claude/commands/newpost.md` already explains
why: this blog is tied to a LinkedIn profile recruiters read, and CI can prove
the site builds and nothing leaked — it cannot prove the writing is good or the
facts are true.

---

## Phase 0 — the handoff contract

The homelab agent writes **one file per project**, at `handoff/<slug>.yaml`, on
a branch named `draft/<slug>`.

```yaml
slug: network-digital-twin          # kebab-case, becomes content/posts/<slug>.md
title: "A network digital twin"     # working title; the repo agent may refine it
date: 2026-10-03T21:30:00+10:00     # RFC3339, when the work happened

series: "Detection Engineering"     # an existing series from data/series.yaml,
                                    # or "" to let the repo agent propose one
seriesTitle: "Network digital twin" # short label for this entry

summary: >
  One or two sentences on what this was. The repo agent writes the final
  description; this is raw material, not the finished line.

# The draft itself. Markdown. Written in first person per blog-author-context.md.
# Keep real commands, configs and error output — the specifics are the value.
body: |
  ## What I set out to do
  ...

# Images travel IN the branch, not as paths on the lab host. The homelab agent
# works from a local clone, so it copies each image into the repo at
# static/images/posts/<slug>/ (kebab-case name, chmod 644) and commits it on the
# draft branch alongside this file. `src` is therefore repo-relative and the
# repo agent can actually open it. Same convention as newpost.md step 4.
images:
  - src: static/images/posts/network-digital-twin/drift-table.png
    alt: "The recent network drift table, port numbers redacted"
    cover: true          # exactly one image may set this
    redactions: "port column masked"   # what was altered, or "none needed"

# Anything the homelab agent PROPOSED rather than took from Bill's own words,
# plus anything the repo agent should know and cannot work out from the file.
# Phase 4 requires the PR to list these; putting them here rather than in a
# commit message is what makes that possible, because the repo agent reads the
# file and not the history. Added 2026-10-04 after the first real handoff put
# its proposals in a commit message, where nothing downstream could see them.
notes_for_repo_agent: |
  - series and seriesTitle are proposals, not Bill's words.
  - The title is a working one; refine it if something fits better.
  - Image X is set as the cover for <reason>; swap it if you disagree.

# Attestation. The gate does not trust this — it verifies independently — but a
# missing or false attestation is itself a failure, because it means the
# homelab agent skipped the step.
redacted: true
redaction_notes: |
  - Real DDNS hostname -> mylab.duckdns.org
  - WAN address -> 203.0.113.5 (TEST-NET-3)
  - gvmd password -> <password>
  - Port column masked in drift-table.png

# What changed about the lab itself. Drives the standing-page reconciliation in
# Phase 3. Omit a key if nothing changed there.
lab_changes:
  services_added:   ["NetBox"]
  services_removed: []
  new_flows:        ["twin JSONL -> Promtail -> Loki"]
  detections_added: 3
  incidents:
    - title: "Scan blind spot on an uncommon port"
      status: "fixed"
```

A handoff missing `slug`, `body`, or `redacted: true` is rejected without
further processing.

---

## The redaction rules

These are the rules the homelab agent follows and the gate enforces. They are
derived from what this blog already does, not invented — the placeholder set
below is what existing posts use.

### Must be replaced before the push

| Real thing | Replace with | Already used in |
| :-- | :-- | :-- |
| The real DuckDNS / dynamic hostname | `mylab.duckdns.org` | 4 posts |
| A real public / WAN IP | `203.0.113.5` (TEST-NET-3) or `198.51.100.x` | 1 post |
| A real external domain under test | `example.com` | 1 post |
| Any password, token, API key, session cookie | `<password>`, `<token>` | the Greenbone post |
| Tailscale auth keys (`tskey-…`), node keys | removed entirely | — |
| Private keys, certificates with private material | removed entirely | — |

### Explicitly allowed — do not "fix" these

- **RFC1918 addresses** (`10.x`, `192.168.x`, `172.16–31.x`). Non-routable, and
  **12 existing posts use them deliberately**. A gate that bans these would
  fail a third of the blog. They stay.
- `100.100.100.100` — Tailscale MagicDNS, a documented constant.
- `127.0.0.1` and loopback ports.
- Internal hostnames that carry no routable meaning (`CLAUDDEB`, `pfSense.peas.arpa`).
- Local usernames in paths (`/home/student/...`). Real commands are the value.

### Images are the sharpest edge

Screenshots leak more than prose, because nobody re-reads a picture. Before a
push, the homelab agent must:

- strip EXIF entirely — **GPS especially**, on anything from a phone;
- mask port columns, credential fields, session tokens and full service
  inventories;
- check the *whole frame*, not the subject — browser tabs, notification popups,
  terminal scrollback behind the window.

Note from the audit: masking a port column is weaker than it looks when the
service names stay visible next to it. SSH is 22 whether or not you blur it.
Mask the row or crop it, not just the number.

---

## The handoff lifecycle, and what to do when you find one

Agreed with Bill on 2026-10-04, after the first real handoff went through and
exposed that the contract described how to *start* work but never how to tell
whether work was already done.

**A handoff is consumed by the publishing pull request.** That PR adds
`content/posts/<slug>.md` and **deletes** `handoff/<slug>.yaml` in the same
diff. The post supersedes the handoff, and git keeps the history, so nothing is
lost by removing it.

The reason is state, not tidiness. With one handoff in the directory, "a file
exists" obviously means "do this". With three published and one pending it
means nothing at all, and an agent that cannot distinguish pending work from
finished work will either redo a published post or skip a real one. Deleting on
publish makes the directory itself the queue: **if a handoff is there, it is
waiting.**

### Triage — what each state means

For the repo agent, which may wake to any of these with no conversation to go on:

| What you find | What it means | What to do |
| :-- | :-- | :-- |
| `handoff/<slug>.yaml` on `main`, no matching post | unprocessed work | Phase 2. Branch from `main`, write the post, delete the handoff in the same PR |
| A `draft/**` branch carrying a handoff | the homelab agent pushed and the gate passed | Phase 2 on that branch. Opening the PR is yours, not the homelab agent's |
| Both a handoff **and** its post exist | a publishing PR forgot to delete the handoff | Delete the handoff. The post is the record |
| The leak gate is red on a branch | something leaked, and the branch is already public | **Do not build on it.** Say so plainly. A credential needs rotating, not just editing out |
| A post merged to `main` | Phase 3 | Reconcile the standing pages from `lab_changes` and the table in `CLAUDE.md` |
| Nothing pending | nothing to do | Nothing. Do not invent work to look busy |

That last row is deliberate. An always-on agent with no queue should idle, not
go looking for things to change in a repository tied to a public site.

### What is still Bill's, always

Merging. CI proves the site builds and nothing leaked; it cannot prove the
writing is good or the facts are true. No agent merges to `main`.

---

## Phase 1 — the leak gate (CI, built 2026-10-04)

A workflow on `draft/**` branches and on PRs into `main`. It fails the branch —
it does not warn — on any of:

1. credential patterns (`sk-ant-`, `ghp_`, `AKIA`, `tskey-`, `-----BEGIN … PRIVATE KEY-----`, JWTs);
2. a **public** IPv4 outside the documentation ranges above;
3. a DDNS / tunnel hostname that is not `mylab.duckdns.org`;
4. EXIF or GPS in any image under `static/images/`;
5. anything staged under `notes/` (gitignored on purpose — never `git add -f`);
6. `redacted:` missing or not `true` in the handoff file.

Built the same way as `ad-lab-runbook`'s `validate.yml`: **tested against
planted leaks**, so it is proven to fail and not merely proven to pass. A gate
that cannot fail is worse than no gate, because it buys false confidence.

Site-specific patterns that are themselves sensitive go in a gitignored file —
the repo already has this shape at `scripts/leak-patterns.local` for the TALEB
ILM exporter.

---

## Phase 2 — draft to finished post (repo agent)

Mostly the existing `/newpost` logic, driven from the handoff file instead of a
chat argument. `.claude/commands/newpost.md` remains the detailed procedure;
this is the short form:

1. read `blog-author-context.md` first — every post matches that voice;
2. rewrite `body` into the finished post: first person, failures kept, every
   code block language-tagged, nothing invented that isn't in the handoff;
3. relocate images into `static/images/posts/<slug>/`, rewrite the paths, set
   the cover with `hiddenInSingle: true`;
4. write front matter including `series` and `seriesTitle` — already enforced by
   the `post-write.py` hook, which blocks the write if either is missing;
5. if `series` was left empty, propose one from `data/series.yaml`, naming it
   after the **subject** and never after a tool, and say in the PR that the name
   is a proposal rather than Bill's own word;
6. **delete `handoff/<slug>.yaml` in the same pull request.** See the lifecycle
   section above — the directory is the queue, so a consumed handoff must leave
   it;
7. carry everything from the handoff's `notes_for_repo_agent` into the PR body,
   along with anything you proposed yourself.

---

## Phase 3 — standing-page reconciliation (not built yet)

The part with the most value, because this is the failure that **already
happened twice**: `/uses/` listed a decommissioned scanner on a page opening
"every tool here is one I actually run", and `/detections/` advertised "53 live
alert rules — 18 on logs, 18 on metrics" when 18 + 18 is 36.

Driven by `lab_changes` in the handoff, per the table in `CLAUDE.md`:

| If the handoff says | Reconcile |
| :-- | :-- |
| `services_added` / `services_removed` | `content/uses.md`, `data/lab.yaml` layers + component count |
| agent / gateway / orchestration change | `data/ai.yaml`, the AI plane block in `data/lab.yaml` |
| `new_flows` | `layouts/_partials/lab_diagram.html` + the flow count |
| `incidents` | `data/incidents.yaml` — including still-open ones |
| anything at all | `content/now.md` (it reads as abandoned within a month) |
| a project worth showing | `data/projects.yaml` |

And a `scripts/check-counts.sh` that recomputes every derived figure and fails
when prose disagrees with data:

```bash
grep -c '^        post:' data/lab.yaml                      # components     -> 22
grep -c 'lab-publish' layouts/_partials/lab_diagram.html    # flows          -> 10
grep -c '^    engine: "Loki ruler"$' data/detections.yaml   # rules on logs  -> 24
grep -c '^    engine: "Prometheus"$' data/detections.yaml   # on metrics     -> 29
grep -oE '^    attack_id: "T[^"]+"' data/detections.yaml | sort -u | wc -l   # -> 18
grep -cE '^  - name: ' data/soc.yaml                        # log sources    -> 8
```

Values as of 2026-10-03. The point is not the numbers — it is that the script
derives them and compares, so nobody has to remember.

**The trap worth writing down:** fixing the data file alone is not enough. The
same figure is duplicated in *prose*, where nothing derives it —
`content/detections.md`, `content/soc.md`, `data/soc.yaml`, `content/uses.md`,
`data/projects.yaml`. In the audit, correcting `data/detections.yaml` left the
page contradicting itself one paragraph above its own stat tiles. Grep the repo
for the old number, and render the page, before calling it fixed.

---

## Phase 4 — the gate that stays

The repo agent opens a PR. It does not push to `main`.

The PR carries: the diff, the Cloudflare preview URL, CI status, every derived
count it changed and what it derived them from, and an explicit list of anything
it *proposed* rather than took from the handoff — a series name, a title, a
description. Bill merges, Cloudflare rebuilds, the post is live.

---

## What is built today, and what is not

| Piece | State |
| :-- | :-- |
| `post-write.py` — front matter + series gate | **built**, in `.claude/settings.json` |
| `build-gate.py` — blocks finishing on a broken build | **built** |
| `bash-guard.py` — catastrophic command guard | **built** |
| `/newpost` procedure | **built**, chat-driven |
| Handoff schema (Phase 0) | **this document only** |
| Leak gate CI (Phase 1) | **built** 2026-10-04 — `scripts/leak-gate.py`, 87 planted-leak tests, `.github/workflows/leak-gate.yml`. Rules, calibration and **known gaps** in [`leak-gate.md`](leak-gate.md) |
| Handoff-driven post build (Phase 2) | not built |
| Count reconciliation (Phase 3) | not built |

---

## Answered 2026-10-03

The three questions this document opened with are settled.

**The homelab agent can push to GitHub directly.** No token path needs
building; the `draft/<slug>` branch flow works as written.

**It works from a local clone of this repo.** Bill hands it the images, it
places them in the repo directory and commits. That is why `images[].src` above
is repo-relative rather than a lab-host path — an earlier draft of this file got
that wrong, and a repo-agent reading `/home/student/...` from a cloud container
would have found nothing there. Images ride the draft branch with the handoff.

One consequence worth stating: **a leaky image on a pushed draft branch is
already exposed**, because GitHub serves branch content, not just `main`. The
leak gate therefore runs on `draft/**` pushes, not only on PRs into `main`.
Deleting the branch afterwards does not undo a push that already happened.

**The homelab agent will be briefed to read this file.** A contract one side has
not read is not a contract, so that briefing is part of the setup rather than an
afterthought.

## Still open

- **Phase 1 is built as of 2026-10-04; Phases 2–3 are not.** The status table
  above is the authority on what exists. The leak gate came first, before any
  draft crossed the wire, for the reason this entry originally gave — a gate
  added after the first handoff is a gate that was not there when it mattered.
  Its limits are written down rather than implied: see the "Known gaps" section
  of [`leak-gate.md`](leak-gate.md). The largest is that **a leak drawn in
  pixels is invisible to it** — there is no OCR — which is exactly why redaction
  stays on the homelab side and the gate stays the second line.
