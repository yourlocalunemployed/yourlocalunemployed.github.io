# 2026-09-25 — Leak audit, accuracy fixes, guardrails, taxonomy

**A privacy and accuracy audit across all three repos that turned into four
self-contradicting figures fixed, two new deterministic gates, a 24-post series
split, and the /now/ layout.** No credential leakage found anywhere.

This log lives in the repo rather than `~/Desktop/claudelogs/` because the
session ran in a cloud container, where `~/Desktop` does not survive. CLAUDE.md
allows for that: "If a log must persist, also copy it into the repo."

---

## What was done

### 1. Leak audit — clean, with one caveat

Scanned all three repos, working tree **and** full history.

| Surface | Result |
| :-- | :-- |
| Credential patterns (API keys, tokens, PEM, JWT) | none, in any repo, in any commit |
| History depth covered | 883 objects; 169 deleted/superseded blobs scanned individually |
| Deleted images | all 13 extracted and opened |
| GPS / EXIF across 133 images | none — personal photos carry no EXIF block at all |
| Emails in content | none |
| Public IPs / real DDNS hostnames | none — all TEST-NET, `example.com`, or `mylab.duckdns.org` placeholders |

**The one real exposure:** commits `651ae0a` and `b5b8845` replaced two
screenshots with port-redacted versions. Git keeps the originals, so on a public
repo `git show 651ae0a^:static/images/posts/network-digital-twin/netbox-expected-services.png`
still returns the full `CLAUDDEB` service inventory — every port with its
exposure level, including SSH 22 and XRDP 3389 both marked "Exposure: all".

Left as-is deliberately. Scrubbing it is a history rewrite and force-push;
going private closes it with neither. Most of those ports are inferable from
the service names the *current* redacted image still shows, so the exposure is
real but modest. Decision deferred to the author.

### 2. Accuracy — four figures that disproved themselves

`/detections/` claimed **"53 live alert rules — 18 on logs, 18 on metrics"**.
18 + 18 is 36. Both halves also disagreed with `data/lab.yaml` and with the
file's own header comment.

Derived from the authoritative `engine:` field: **24 Loki ruler + 29 Prometheus
= 53**. Not the `security:`/`health:` split, which groups by *purpose* (23/30)
and does not line up, because one Loki rule sits under `health:`.

The same block claimed 16 ATT&CK techniques; the catalogue maps **18** distinct
`attack_id` values (14 if sub-techniques collapse into parents). 16 is neither.

Fixing the data file only fixed the stat tiles. Rendering the page caught three
more copies in prose, where nothing derives them:

- `content/detections.md` — "18 over logs and 18 over metrics", directly above
  the corrected tiles
- `content/soc.md` — its **meta description** said "seven log sources, 35
  detection rules" while the same page's tiles rendered 8 and 53
- `data/soc.yaml` — "Four of the **35** rules watch the agent". The *four* is
  right; only the total was stale.

### 3. Guardrails — the gap that let it drift

`post-write.py` enforced `title/date/draft/description/tags` but never
`series`/`seriesTitle`, though CLAUDE.md makes that rule 1 of keeping the blog
true to the lab. Three posts had drifted past it. The hook now blocks on both.

`ad-lab-runbook` had **no CI at all** — which is why "no parser has ever seen
this script" sat in its docs across two commits and a publish. Added
`.github/workflows/validate.yml`: parse, variable-flow, smart-quotes.

Also added `.claude/skills/steward/SKILL.md` (with `babysit/` as a pointer, not
a second copy) so the next session inherits this repo's conventions — one CI
check, what breaks silently, what must never be committed — instead of
rediscovering them.

### 4. Publishing hygiene

- **35 of 43 meta descriptions** exceeded ~160 characters and were truncated
  mid-sentence in search results; the longest was 353. All rewritten, now
  115–160 with median 154. Verified as *rendered*, not just in front matter.
- **Sitemap 187 → 106 URLs.** 114 of the original were `/tags/` term pages
  against 43 actual posts, 85 of them listing one or two posts. A custom
  sitemap submits a tag page only at 3+ posts. Nothing deleted — all 114 still
  build and render.

### 5. Taxonomy — the 24-post series

`Home Lab` held 24 of 43 posts and rendered honestly as **"PART 24 OF 24"**,
which is an archive, not a series. Split by subject, never by tool:

| Series | Posts |
| :-- | --: |
| Home Lab | 24 → 8 |
| Agents in the Lab | 6 |
| Detection Engineering | 5 |
| Keeping It Running | 4 |
| Watching the Lab | 3 |

Each new series groups posts that already shared a subject — the observability
three already carried seriesTitles reading "The lab pages my phone" and "The
lab reads its own logs". They were a series before this, just unlabelled.

### 6. /now/ layout and the background flash

Sections are wildly uneven — Studies 3 items, Learning 4, Projects & Labs 19
averaging ~140 characters. Three equal columns in an 1100px page packed 19 long
bullets into a ~330px column. Page now widens to 1460px, and a section with 8+
items spans two columns with a 2-column internal list — driven by item count
via `:has()`, not by section name.

Separately, `#site-bg` carried `background-image` inline on every page, so on
video pages the still painted first and the video painted over it. Removed —
but scoped to `.has-video` above 768px under `no-preference` only, because that
same image is the fallback wherever the video is switched off.

### 7. terminal-quest — audited, unchanged

251 scenarios read; every command and explanation correct. Both built-in
self-tests pass (105/105 and 146/146, plus 146/146 anti-cheat). A false-accept
sweep over 23,332 wrong-answer pairs found 32, all supersets of the expected
answer (`ls -la` for `ls`) — lenient by design, not defects. Nothing to change.

---

## Key decisions and gotchas

**Verify before reporting.** Several findings evaporated on inspection, and each
would have been a false alarm shipped as fact:

- Minified HTML strips attribute quotes, so `loading="lazy"` and the GoatCounter
  script *looked* absent. Both were present and working.
- `wc -c` counts bytes; an em-dash is 3 bytes in UTF-8. A description measured
  "162" was 159 characters.
- The README's "11 challenge levels" vs the sub-README's "10" was not a
  contradiction — `ALL_LEVELS = LEVELS + [FINAL]`.
- "694 code lines" in VALIDATION-NOTES is exactly right when block-comment
  interiors are excluded. My first count said 768 and was the wrong measure.
- `New-ADServiceAccount` appeared missing from the runbook. It was there; my
  cmdlet inventory was truncated to the top 45 by frequency.

**A gate that cannot fail is worse than no gate.** The runbook CI was tested
against planted defects — an unterminated string, a variable assigned twice, a
curly quote in code — and each step exits non-zero and names the line. Testing
only the passing case would have shipped a green light that never turns red.

**Guard scope matters more than guard count.** 18 commands in the runbook lack
an idempotency guard, but only `Add-KdsRootKey` has real consequences: it is
forest-wide, and a second run adds a *second* root key. That one was fixed; the
other 17 were documented in a table rather than changed, because rewriting
guards with no domain to test against is exactly how the repo's own issue 5
happened — a guard whose brackets were misplaced, so the command silently never
ran. The new guard was AST-checked to confirm the call is genuinely inside the
`if` block.

**Scope the fix to the failure.** The background still image was three things
at once: loading placeholder, reduced-motion fallback, and mobile fallback.
Deleting it would have blanked the background for phones and reduced-motion
visitors, since `body` is transparent.

**Merge timing cost four PR cycles.** Four commits landed seconds after their PR
merged and each needed recovery: restart the branch from the new `main`, merge
rather than rebase (force-push is correctly blocked here), open a fresh PR.
Nothing was lost. Merging *after* a push lands keeps it to one PR.

**A Go template comment cannot contain `*/`.** The first `layouts/sitemap.xml`
failed to build because an example `grep` inside the comment contained
`[^<]*/tags/`, which closed the comment early.

---

## Artifacts created

| Path | What |
| :-- | :-- |
| `.claude/skills/steward/SKILL.md` | this repo's PR conventions |
| `.claude/skills/babysit/SKILL.md` | pointer to steward, so either name resolves |
| `layouts/sitemap.xml` | sitemap with a tunable thin-tag threshold |
| `ad-lab-runbook/.github/workflows/validate.yml` | PowerShell parse + variable-flow + smart-quote gate |

Throwaway analysis (not committed): PowerShell 7.4.6 AST scripts for parse and
variable-flow checking, a Playwright harness for measuring the /now/ grid and
the background-image matrix at three viewports, and blob-level history scanners.

---

## Commits

Blog (`4f61f23..083630e`):

```
083630e Merge pull request #5
027a537 Merge main into claude/gallant-knuth-l8cxxj
5e632b1 now: use the page width, and drop the still image under a video
9938a12 Merge pull request #4
902d67e series: split the Home Lab catch-all into four subjects
af369ac sitemap: stop submitting thin tag pages
dead953 Merge pull request #3
7bad866 posts: bring every meta description under the search-snippet limit
472c4ea Merge pull request #2
e43cd4f Merge branch 'main' into claude/gallant-knuth-l8cxxj
15b3adb skills: add a PR steward guide for this repo
c9ac6dc Merge pull request #1
8c4df4e detections/soc: correct the stale rule counts the prose still carried
1df09e4 detections: correct the rule split and ATT&CK count, and gate the series rule
```

ad-lab-runbook (`527f902..6479f48`):

```
6479f48 Merge pull request #2
5bd12bf Merge main into claude/gallant-knuth-l8cxxj
69619bd ci: run the parser check that the docs said had never run
6f43652 Merge pull request #1
c592d52 Record the live run, and guard the one command that must not run twice
```

terminal-quest: no commits — audited clean.

---

## Outstanding

1. **Repo visibility.** All three repos are public. That is the only thing
   making the pre-redaction screenshots reachable. Going private closes it with
   no history rewrite; staying public is defensible given the ports are largely
   inferable anyway and the blog is a job-seeking portfolio. Author's call.

2. **The new series names are Claude's words.** *Watching the Lab*, *Keeping It
   Running*, *Agents in the Lab*, *Detection Engineering* follow the CLAUDE.md
   rule and the posts' own subjects, but they were not authored. Now live and
   indexable, so renaming gets more expensive over time.

3. **55 singleton tags remain on posts.** Only the sitemap was changed. Pruning
   them alters what each post claims to be about — an authoring call — and would
   not affect related-posts either way, since a tag on one post cannot relate
   two posts.

4. **`content/now.md` was last updated 2026-09-10.** CLAUDE.md notes the page
   reads as abandoned within a month.

5. **ad-lab-runbook regions 9–21 have still never been executed.** The live run
   covered regions 1–8 plus 22 on Windows Server 2022. The docs now say so
   precisely; the other 13 regions remain parser-verified only.

6. **The runbook's variable-flow CI rule allows no reassignment at all.** Correct
   for this script today. A future block that legitimately reuses a name will
   need its own variable, or a change to the rule.
