# 2026-10-04 — The two-agent pipeline, the leak gate, and the first handoff

**The repo agent role was designed, the homelab agent built a leak gate that the
repo agent then stress-tested, and the first real handoff went through Phases 2
and 3 to a merged post.** Covers 2026-10-03 to 2026-10-04.

This log is in the repo because the session ran in a cloud container, where
`~/Desktop` does not survive. Same reasoning as the 2026-09-25 log.

Two agents did this work, and the commit list shows which did what. "Repo agent"
means Claude Code in this repository, in the cloud. "Homelab agent" means the
Claude on the lab. Commits authored as Billal Rehmani on 2026-10-04 came from the
homelab agent's side.

---

## What was done

### 1. Chat register recorded (`bff4315`)

CLAUDE.md now says how Bill likes to be talked to, scoped to chat only. It
explicitly does not change commit messages, PR bodies, posts or docs, and it
does not lower the reliability bar.

### 2. The handoff contract (`c5e7d42`, `a1b113e`)

`docs/blog-agent-handoff.md` defines the interface between two agents that never
share a conversation. Bill's three decisions shaped it:

| Question | Decision |
| :-- | :-- |
| How does a draft cross? | the homelab agent pushes a `draft/<slug>` branch |
| Who redacts? | the homelab agent redacts; CI verifies |
| Where does the repo agent stop? | it opens a PR; Bill merges |

The fact that decides the design is that **anything pushed is permanent**. Two
screenshots redacted in a later commit are still one `git show` away. So
redaction happens before the push, and the gate is the second line. A follow-up
fixed the image path. An earlier draft used a lab-host path that a cloud
container could never open, so images now ride the draft branch with
repo-relative paths.

### 3. The leak gate, and the stress test

The homelab agent built Phase 1: `scripts/leak-gate.py`, its planted-leak tests,
and `.github/workflows/leak-gate.yml`. The repo agent then attacked it. Three
findings were real (`dd31246`):

- **IPv6 was never checked.** `ipaddress` was imported but only ever reached
  dotted quads.
- **Path arguments were silently ignored.** `leak-gate.py /nonexistent/fake.md`
  exited 0 and reported clean, after scanning a file it never opened. It now
  exits 2.
- **The baseline header undercounted itself.** It said seven images while
  carrying nine.

Four other candidate findings were withdrawn after checking them, and are
recorded in `docs/leak-gate.md`.

Configuring the gate for real then found three more fail-open seams (`73a387b`).
The worst was an unedited template placeholder that loaded, counted as a
pattern, and matched nothing. A stale `LEAK_PATTERNS` secret ran for three CI
runs (`355e040`). It was only caught because the stale value was invalid; an
empty one would have reported clean. The fix is `scripts/leak-gate-expect.txt`:
the declared pattern count must match, or the gate refuses to run.

### 4. The first handoff: Phases 2 and 3 (PR #16)

`handoff/a-clean-result-that-means-nothing.yaml` became
`content/posts/a-clean-result-that-means-nothing.md`, and the handoff was
deleted in the same PR.

Corrections to the handoff body, each checked against the repo:

- **88 → 87 tests.** This is the suite's own count.
- **"Roughly half must pass" → about a third.** 30 of 87 tests assert a clean
  result or exit 0.
- **SVG caption.** It said "three of the four broken states"; the table shows
  three broken states and one correct one.
- **"The only way this gate could fail open".** The same post shows a second
  fail-open case, so the line was narrowed.
- **Incident title.** The handoff said "reporting clean", but CI *failed* those
  runs. The title now says so.

Standing pages reconciled:

| Change | Derived from |
| :-- | :-- |
| diagram: new "blog drafts" row; publish row starts at the merge | flows 10 → 11, `grep -c 'lab-publish'` |
| leak gate as a `/lab/` component | components 22 → 23, `grep -c '^        post:'` |
| `/ai/`: repo-agent card, "One post, start to finish" pipeline, leak gate control + limits | — |
| incident, `/now/`, projects, `/uses/`, `/about/`, contract status | — |
| stale SOC figures (17 → 24 Loki rules, 7 → 8 sources, 36 → 53 on `/now/`) | `data/detections.yaml`, `data/soc.yaml` |

---

## Key decisions and gotchas

**Check a claim against the repo, not against the handoff.** Every correction in
section 4 came from the repo itself. The draft was well written and still
carried five wrong statements. Of those, the incident title said the opposite of
what happened.

**Don't write a lock where there is only a rule.** `main` has no branch
protection and no ruleset (checked with the API). So "no agent merges to main"
is an instruction, and the pages say "only I merge", never "only I can". Whether
`main` is protected is not written on any public page.

**Screenshots find what greps miss.** Rendering the diagram exposed "17
detection rules" in the SOC row. That figure lives in a template, not in data,
and no count rule covered it.

**The handoff lifecycle works as specified.** After the merge, `handoff/` is
gone from `main`. An empty queue means there is nothing to triage on waking.

**A screenshot carries more than its subject.** The cover shows a "Security and
quality 1" badge, an open code-scanning alert. It's harmless, but the gate
cannot see it, and nobody chose to publish it.

---

## Artifacts

| Path | What |
| :-- | :-- |
| `docs/blog-agent-handoff.md` | the contract, lifecycle and triage table |
| `scripts/leak-gate.py`, `tests/leak-gate/`, `.github/workflows/leak-gate.yml` | Phase 1 (homelab agent) |
| `content/posts/a-clean-result-that-means-nothing.md` | the first handoff-built post |

---

## Commits

`git log --oneline 1301ae4..bc93f3f`:

```text
bc93f3f Merge pull request #16 from yourlocalunemployed/claude/gallant-knuth-l8cxxj
b7cc0ba lab, now: correct SOC figures the prose still carried
0155084 lab: reflect the two-agent blog pipeline and the leak gate
37d404d post: A clean result that means nothing
a6edea6 Merge pull request #15 from yourlocalunemployed/docs/handoff-lifecycle
42041e2 docs: define the handoff lifecycle and how to triage on waking
25c6aad Merge pull request #14 from yourlocalunemployed/fix/scan-size-invariant
ccb9896 Merge pull request #12 from yourlocalunemployed/draft/a-clean-result-that-means-nothing
5137c97 test: drop the scanned-file assertion, it fires on correct work
b5d85de handoff: add the pull-request checks screenshot as a second figure
420af2b Merge pull request #13 from yourlocalunemployed/feat/leak-gate
6ce71e4 handoff: add Billal's repository screenshot as the cover
8fb737a handoff: a clean result that means nothing
fded518 test: give the scan-size check the patterns the gate now requires
7dff417 test: assert the counts quoted in the docs are still true
f1a3fde docs: note that editing CI needs the Workflows token permission
fd1c787 Merge pull request #11 from yourlocalunemployed/alert-autofix-1
4af1b20 Potential fix for code scanning alert no. 1: Incomplete multi-character sanitization
09d9ea1 Merge pull request #10 from yourlocalunemployed/feat/leak-gate
355e040 feat: enforce the site-pattern count so a stale secret cannot pass
b658d5f ci: make the gate explain itself in GitHub annotations
36e263b ci: pin the runner image and move checkout off Node 20
73a387b fix: make the gate survive being configured by a person
a9dbd3b fix: refuse a site pattern that bans a mandated placeholder
dd31246 fix: close the two gaps found by the repo agent's adversarial pass
f937bea ci: run the leak gate on GitHub Actions
85ed941 feat: add the leak gate scanner and its planted-leak tests
3298ec7 Merge pull request #9 from yourlocalunemployed/claude/gallant-knuth-l8cxxj
a1b113e docs: close the handoff contract's open questions, and fix the image path
e378935 Merge pull request #8 from yourlocalunemployed/claude/gallant-knuth-l8cxxj
c5e7d42 docs: propose the handoff contract between the homelab and repo agents
bffff2b Merge pull request #7 from yourlocalunemployed/claude/gallant-knuth-l8cxxj
bff4315 docs: record the chat register, and scope it to chat
```

The 2026-09-28 commits in that range (the maintenance post, the NTP incidents,
`/now/`) were Bill's own work between sessions and are omitted above.

---

## Outstanding

1. **Protect `main` and require the leak gate check.** This turns "no agent
   merges" from an instruction into a lock.
2. **`scripts/check-counts.sh` is not built.** Phase 3 counts are still derived
   by hand. Today's diagram drift (the "17" in a template) argues for including
   template literals, not only data files.
3. **The homelab agent's `redaction_notes` template** produced a garbled
   sentence ("The PNG screenshot was / screenshots were inspected"). It isn't
   published, but fix it at the source.
4. **One open code-scanning alert**, visible in the post's cover screenshot.
5. **`data/projects.yaml` still says "seven log sources, 35 detection rules"**
   for the SOC build. It was left alone as a historical narrative. Revisit if it
   reads as present tense.
6. **The 2026-09-25 outstanding items** are unchanged, except that the
   `/now/` freshness item is resolved (updated 2026-10-04).
