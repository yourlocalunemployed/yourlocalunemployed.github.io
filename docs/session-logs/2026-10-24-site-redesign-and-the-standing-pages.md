# 2026-10-24 — Two pages retired, the home page reworked, two maps, a CV, and the standing pages brought current

**Fourteen pull requests between 2026-10-20 and 2026-10-24, all from the repo
agent, all merged by Bill: `/detections/` and `/incidents/` retired, the home
page's dead sidebar replaced and its layout fixed, light mode made to work, a
changelog and two generated topology maps added, a CV built from the resume,
the tag taxonomy folded, page transitions and scroll-driven motion, a post-page
pass, and eight stale claims corrected.** No leakage found in the audit that
opened the run.

In the repo because the session ran in a cloud container, same as the two logs
before it.

---

## What was done

### 1. Audit (2026-10-21): clean

Full tree, all 47 commits since the 2026-09-25 audit, every image added since:
no credentials, no real addresses, no real hostnames, no EXIF or GPS. Every
flag my sweeps raised resolved to the leak gate's own planted test fixtures, an
SNMP OID, or SVG path data. Structure: every layout resolved, every data file
read by a layout, 45 posts with full front matter, 0 broken links across 327
pages, all inline scripts covered by the CSP hashes.

Branch protection on `main` was proposed (PR #19) and **declined**. `main` has
no ruleset; "no agent merges" stays a rule the agents follow. The write-up
is on the branch history, not in the tree.

### 2. Pages retired (PR #18)

`/detections/` and `/incidents/` removed with their layouts and data files.
Redirects to `/soc/` and `/lab/`. The `/soc/` cards share the old catalogue's
`.detp-*` styles, so those eight rules were kept under a note that the prefix
is historical; everything else went. The rule counts (24 on logs, 29 on
metrics) can no longer be re-derived in the repo; they come only from the lab
host via the handoff's new `detection_rules` field, and CLAUDE.md, the steward
skill and the handoff contract say so.

### 3. Home page (PRs #20, #21, #22)

- The hand-typed **PC Setup** sidebar (a second copy of hardware `lab.yaml`
  already held) became a **Now** panel read from `/now/`'s front matter.
  `/now/` itself was brought current with the TAFE capstone.
- The sidebars had been `position: sticky` since they were built and had
  **never stuck**: `align-items: stretch` sized them to the whole row, and
  `body { overflow-x: hidden }` made `body` the scroll container. Now
  `align-items: start` and `overflow-x: clip`. On wide screens the grid grows
  to 1460px (it was a 1100px island on a 3440px display).
- The lab diagram's eleven flow rows are collapsed by default on the home
  page only (`lab_diagram.html` takes `collapsed`); `/lab/` is unchanged.
  Home page 5,428 → 4,755px at 1400 wide.

### 4. Light theme (PR #23)

Light mode had never worked on the lab pages: `html` is `#060608`, the
background overlay is a literal 0.88 black, and the matrix rain and wash are
literal dark values, so `/lab/`, `/soc/` and `/ai/` were black pages with
black text. One block at the end of `custom.css`, every rule scoped to
`[data-theme="light"]`; dark mode pixel-compared against the previous build.

### 5. New things (PRs #24, #25, #27, #28, #30)

| Added | Source of truth |
| :-- | :-- |
| `/lab/` **What changed**: 15 dated entries | `data/changelog.yaml`, dates pinned to commits or post dates |
| Footer **Search** link | the only non-JS route to `/search/` |
| `/lab/` **topology map**: inline SVG, every component a clickable box | `data/lab.yaml` (new `node` key per component) + `data/network.yaml` |
| `/cv/`: one-page profile, printable | Bill's 2026 resume, transcribed; phone, emails and references left off |
| `/ai/` **plane map** with a `:target` **detail panel behind every box** | `data/ai.yaml` (new `post`, `stages`, `publishing` per agent) + `lab.yaml` AI plane |

### 6. Tags (PR #26)

115 tags → 58, singletons 57 → 0, by folding each single-post tag into an
existing broader tag or dropping it. `homelab` and `home-lab` were both in
use. `data/topics.yaml` named 51 tags that no longer existed; cleaned, and
every post still lands in at least one topic.

### 7. Motion and the post page (PRs #29, #30)

- Cross-document **view transitions** with the header and background pinned.
- The **reading bar** is a `scroll(root)` timeline; the inline script that
  drove it is gone and its CSP hash removed. Cards and sections rise in on a
  `view()` timeline. All behind `@supports` and `prefers-reduced-motion`.
- Posts: the cover backs the header at 22%; a **series strip** under the
  breadcrumbs; the series box moved after the article; a **sticky TOC rail**
  from 1280px; the cursor spotlight on every card type.

### 8. Standing pages (PR #31)

`/privacy/` now discloses GoatCounter and giscus. "Three coding agents" in
three places became roles plus the one fact that does not drift. `/lab/`
intro, a ninth `/network/` principle for the digital twin, skills on
`/about/`, the Building the Blog blurb.

---

## Key decisions and gotchas

**`:target` and the theme's smooth-scroll script.** PaperMod's inline script
catches every `a[href^="#"]`, calls `preventDefault`, scrolls and
`pushState()`s the hash. A pushed hash never updates `:target`, so the AI
map's panels worked when the URL was loaded and did nothing when clicked. The
script is CSP-hashed, so it was not edited; the map links are `/ai/#am-…`
instead, which nothing intercepts. Applies to anything on the site that
relies on fragments.

**`data-theme` lives on `<html>`.** `[data-theme="light"] html` matches
nothing. It is `html[data-theme="light"]`. Cost one build.

**Sticky needs the right scroll container.** `overflow-x: hidden` on `body`
turns it into one. `overflow-x: clip` clips without doing that.

**Go template `define` is top-level only.** An inline partial defined inside
a `with` block fails to parse; hoisted to the top of the file, with its own
`end`.

**Measure text fit, do not eyeball it.** The lab map's overflows and label
collisions were found with `getBBox()` against each text's own rect; the AI
map passed the same check first time (76 nodes, 0 overflow).

**Fetching sites from this sandbox fails.** DNS is blocked for anything
outside GitHub and a few hosts, so the design research was from search
descriptions plus prior knowledge, and said so.

**A branch keeps commits from closed PRs.** The declined branch-protection
doc rode along until it was removed in its own commit; the net diff was
checked before opening the PR.

**Sweep after every rename.** Folding tags silently broke `topics.yaml`
(51 dead references) and would have dropped one post from a topic; the
`/detections/` retirement left docs telling agents to grep a file that no
longer existed. Both were caught by grepping for the old thing after the
change, which is now the habit.

---

## Artifacts

| Path | What |
| :-- | :-- |
| `data/changelog.yaml` | dated lab changes, rendered on `/lab/` |
| `layouts/_partials/lab_map.html`, `lm_wrap.html` | the lab map and its word-wrap helper |
| `layouts/_partials/ai_map.html` | the AI plane map and its panels |
| `layouts/_partials/now_panel.html`, `series_progress.html` | home Now rail; post series strip |
| `layouts/_default/cv.html`, `content/cv.md` | the CV |
| `static/_redirects` | four lines for the retired pages |

Removed: `content/detections.md`, `content/incidents.md`, their layouts and
data, `layouts/_partials/pc_specs.html`, the inline reading-bar script.

---

## Commits

`git log --first-parent --oneline 7c199a7..f9b1bc3` (PRs #18 and #20–#31):

```text
f9b1bc3 Merge pull request #31   pages: bring the standing pages back in line with the lab
eb1dd88 Merge pull request #30   posts: cover header, series strip, TOC rail, spotlight; ai: map + panels
30f721f Merge pull request #29   css: real page transitions, and scroll-driven motion without script
f2578d2 Merge pull request #28   cv: carry the resume onto /cv/; lab: fit every label on the map
398b8e5 Merge pull request #27   lab: an interactive topology map; cv: a printable one-page profile
c3b5140 Merge pull request #26   tags: fold the 57 single-post tags into the broader tags
c408a15 Merge pull request #25   footer: link to /search/
21d1f20 Merge pull request #24   lab: add a "What changed" record
a485e1a Merge pull request #23   css: make the light theme readable on the lab, series and study pages
4e74e3b Merge pull request #22   home: collapse the flow rows of the lab diagram by default
455d65c Merge pull request #21   home: make the sidebars actually stick; room on wide screens
a512055 Merge pull request #20   home: replace the PC Setup sidebar with a Now panel read from /now/
6f32b76 Merge pull request #18   site: retire the /detections/ and /incidents/ pages
```

PR #19 (branch protection) was closed unmerged.

---

## Outstanding

1. **Branch protection on `main`: declined, not forgotten.** The moment a
   second person or a separate machine account for the homelab agent enters
   the picture, the cost-benefit changes. The write-up is in the branch
   history at `ab92e35`.
2. **`scripts/check-counts.sh` is still not built.** Counts are derived by
   hand per the CLAUDE.md table. The template-literal drift this run found
   ("17 detection rules" in the diagram) argues for the script covering
   templates, not only data.
3. **The capstone series** waits on posts. Build & Battle is the strongest
   recruiter material of the year; subject-named, never "Proxmox".
4. **Design list items not taken:** the boot-log preloader from lab data, and
   the typography pass on the standing pages. Both still stand as options.
5. **`/cv/` experience** is the resume's two roles. Update there, not on
   `/about/`, when it changes; the page reads `/now/` for status.
6. **The AI map's `stages`/`publishing` lists** on each agent are my reading
   of the pipeline text. If the council changes, they change with it.
7. **The homelab agent's briefing** covered the `detection_rules` field. It
   has not been told about `data/changelog.yaml` or the `node` key on new
   components; both are the repo agent's job in Phase 3, so no action from it
   is required, but it should not be surprised by them in a diff.
