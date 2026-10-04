# The leak gate — what it catches, and what it does not

Phase 1 of [`blog-agent-handoff.md`](blog-agent-handoff.md). Implemented in
`scripts/leak-gate.py` and proved by `tests/leak-gate/test_leak_gate.py`.

> **CI is not wired up yet.** `.github/workflows/leak-gate.yml` is written and
> validated but could not be pushed with it: creating a file under
> `.github/workflows/` needs a token carrying the `workflow` scope, and the one
> on this machine does not have it. Until that lands, the gate is a local
> pre-push check — run it by hand. The scanner and its tests are complete and
> stand on their own; the workflow is a thin wrapper around the same command.

```bash
python3 scripts/leak-gate.py              # full check -- every tracked file
python3 scripts/leak-gate.py path/to/a.md # partial, labelled as such
python3 tests/leak-gate/test_leak_gate.py # prove it can still fail
```

A path that does not exist, a directory, or an unrecognised option is an
**error (exit 2)**, never a silent skip — see known gaps and the changelog for
why that is stated so plainly. An explicit path need not be tracked yet, which
makes it the useful way to check a file before `git add`.

Exit 0 clean, 1 findings, 2 the gate could not run. It fails **closed**: a
crash, a malformed pattern file or an unreadable image is a non-zero exit, not a
pass. This is deliberately the opposite of the `.claude/hooks/` gates, which all
fail open — those are assistants, this is a control, and a control that fails
open is a label.

## Status

| Rule | What fails the branch |
| :-- | :-- |
| **R1** | Credentials: `sk-ant-`, `sk-proj-`, `gh[pousr]_`, `github_pat_`, `AKIA`/`ASIA`, `tskey-`, `xox[baprs]-`, `glpat-`, PEM private-key blocks, JWTs, `aws_secret_access_key`, plus a generic `key: value` rule and any site-specific patterns |
| **R2** | A globally routable IPv4 **or IPv6** that is not in `scripts/leak-gate-allow.txt` |
| **R3** | A DuckDNS / no-ip / dynu / ddns.net / ngrok / trycloudflare / loca.lt / ts.net / zrok / serveo hostname that is not `mylab.duckdns.org` or a subdomain of it |
| **R4** | EXIF, XMP, IPTC, a JPEG comment, or a PNG `tEXt`/`iTXt`/`zTXt`/`eXIf` chunk on any image, unless hash-pinned in `scripts/leak-gate-baseline.txt` |
| **R5** | Any tracked file under `notes/` |
| **R6** | A `handoff/*.yaml` missing `slug`, `body`, or `redacted: true` |
| **R7** | The number of site patterns loaded does not match `scripts/leak-gate-expect.txt` |

Scope is `git ls-files` — tracked files only, since untracked files are not
pushed. `public/`, `resources/` and `.git/` are excluded (build output).

## Two design decisions worth knowing

**It does not print what it finds — for R1.** This repo is public, so its Actions
logs are public. A gate that echoes the credential it found publishes that
credential into a public log; the gate becomes the leak. R1 reports the rule
name, the file, the line and the length, never an excerpt. R2 and R3 *do* print
the value, on the opposite argument: by the time the gate fires on a pushed
branch that address is already public, and you cannot redact an address you
cannot see. The asymmetry is intentional.

**The baseline is keyed by content hash, not by path.** Nine images published
before the gate existed carry benign metadata (`DateTime`, `Orientation`, XMP on
the two LABDECK phone screenshots; a GIMP comment; a `Software` chunk). All nine
were checked by hand on 2026-10-04: **no GPS, no device model, no location.**
They are pinned by sha256, so dropping a fresh screenshot — GPS and all — over
an old filename does not inherit the exemption. Change a byte and the entry
stops applying. The right way to clear one is to strip the metadata and delete
the line, never to update the hash.

## Calibration

The first run against the live corpus produced **31 findings, every one a false
positive.** That number is the reason the must-pass half of the test suite
exists. A gate that cries wolf gets commented out inside a week, and then you
have no gate plus a false memory of having one. The classes were:

- **SNMP OIDs read as IP addresses.** The OID `1.3.6.1.2.1.31.1.1.1.1` in the
  LaMetric post is carved into two plausible-looking public addresses by a naive
  dotted-quad regex.
- **SVG path data read as IP addresses.** The `d` attribute of the GitHub icon
  in `footer.html` is a run of bare coordinates separated by dots, and it yields
  three more.
  Both fixed by requiring no dot or digit on either side of the quad, plus
  stripping SVG geometry attributes before the IP pass.

  Neither the OID fragments nor the SVG coordinate run are quoted literally
  here, and the reason is worth recording: lifted out of context each one *is*
  a valid-looking routable address, so writing them out made this very document
  fail the gate. (In `footer.html` the coordinates sit inside a `d="…"`
  attribute, which the gate strips before the IP pass; quoted in prose they no
  longer do.) The fix
  was to reword rather than to add an inline `# leak-gate: allow` marker. Such a
  marker is the obvious convenience and it was refused on purpose — an
  unreviewable inline bypass in a security control is worth more to an attacker
  than it is to an author, and the only thing it bought here was two slightly
  more specific sentences. Reproduce them by running the regex if you need them.
- **Correct redactions rejected.** `auth.mylab.duckdns.org` is exactly what the
  rule wants to see; exact-match comparison flagged six of them.
- **A reference to a secret read as a secret.** `api_key: os.environ/OPENROUTER_API_KEY`
  is LiteLLM's own syntax. Now handled alongside `${VAR}`, `${{ secrets.X }}`,
  `!secret`, `%VAR%`, `env:`, `ENV[]` and `/run/secrets/`.
- **A redacted URI read as entropy.** `/?access_token=REDACTED&since=0&limit=50`
  gave a 48-character "value" spanning the query string, which passed the
  character-variety test. `&?#` now terminate a value.
- **The wrong pattern file.** `scripts/leak-patterns.local` belongs to the TALEB
  ILM exporter; pointed at this corpus it matched one ordinary 8-letter word 27
  times. This gate has its own `scripts/leak-gate-patterns.local` (gitignored,
  same format: one regex per line, `#` comments; `LEAK_PATTERNS` in CI).

Measured on 2026-10-04: 321 tracked files, no findings, 9 baselined. 87 tests pass. These figures are asserted by `DocumentedCountsAreCurrent` in the test suite rather than maintained by hand — the repo's own rule is that counts are derived or checked, never guessed, and this line had already drifted once.

## Known gaps — read this before trusting it

The gate is the **second** line. Redaction happens on the homelab side before
the push, and that ordering is not a formality: these are the things the gate
provably cannot catch.

1. **A leak drawn in pixels is invisible.** There is no OCR. A screenshot
   showing a token, a WAN address or a full service inventory passes every
   check, because R4 only inspects metadata. This is the largest gap and it is
   the one the contract already warns about — *"screenshots leak more than
   prose, because nobody re-reads a picture"*. Masking a port column while the
   service names stay visible beside it is the specific trap: SSH is 22 whether
   or not you blur it. **Mask the row or crop it.**
2. **It scans the tree, not the history.** A leak committed and then "fixed" in
   a later commit on the same branch is still served by GitHub at the earlier
   commit SHA. The gate passes; the leak is still public. Rewriting a pushed
   branch does not retract it either. This is why the rule is redact *before*
   the first push, not before the PR.
3. **R1's generic rule is shape-based, not entropy-based.** It wants ≥12
   characters and ≥3 of 4 character classes, tuned to produce zero findings on
   the current corpus. A long lowercase-only secret — base32, a passphrase, a
   hex digest — does not trip it. The specific vendor patterns are the real
   defence; the generic rule is a backstop.
4. **Encoded and split secrets pass.** Base64, hex, a key broken across lines,
   a token assembled by string concatenation. No decoding is attempted.
5. **Only images and UTF-8 text are inspected.** A PDF, an office document, an
   archive or a raster embedded as base64 inside an SVG is skipped, not scanned.
6. **R5 is path-based.** It catches `git add -f notes/x.md`. It does not catch
   the same unredacted content pasted into a file somewhere else — that falls to
   R1/R2/R3 on the content itself.
7. **R3 knows a provider list, not your domains.** A real hostname under a
   domain the lab owns, or a bare public FQDN, is not matched. Add such patterns
   to `leak-gate-patterns.local`.
8. **No homoglyph or Unicode-normalisation handling.** A Cyrillic `а` in a
   hostname defeats the regex. Note the repo agent tested a zero-width space in
   a hostname and the gate **did** block that one, but that is the pattern
   failing to match an altered string rather than the gate understanding
   homoglyphs — do not read it as coverage.
9. **There is no inline suppression, by choice.** Documentation that must
    quote a leak-shaped string has to reword instead, and the cost is now
    measured rather than guessed: **this file has tripped its own gate three
    times** — on SNMP OID fragments, on an SVG coordinate run, and on a Google
    public IPv6 address quoted as an example. Each time the fix was a reword.
    The trade stays open to challenge: a `# leak-gate: allow` marker is what
    most scanners do and would have saved three edits, but it is an
    unreviewable bypass that anyone can add to any line, and the thing being
    protected here is a public repo with permanent history. Three rewrites is
    the price; argue it if you think the balance is wrong.
10. **The pattern COUNT is enforced; the pattern CONTENT is not.** R7 catches a
    stale, empty or unset `LEAK_PATTERNS` secret, which was the one way this
    gate could fail open. It cannot catch a secret holding a *different*
    pattern that happens to count the same. A committed hash would, but a hash
    of a short pattern on a public repo is brute-forceable, so the count is the
    strongest invariant that can be published safely.
11. **R1's withholding is defeated when another rule matches the same value.**
    Site-pattern findings deliberately print neither the pattern nor the match.
    But if the value is also a DDNS hostname or a routable address, R3 or R2
    fires on the same line and prints it in full, because those rules print by
    design. Observed in testing: a draft containing the real hostname produced
    a withheld R1 finding and an R3 finding naming the host. This is not a
    contradiction — on a pushed branch the value is already public, which is
    the reasoning for R2/R3 printing — but do not assume a value is withheld
    just because a site pattern covers it.
12. **Editing the baseline file is not itself gated.** Adding a hash to
    `leak-gate-baseline.txt` grants an exemption. That is caught by reviewing
    the diff, which is why the file is committed and the hashes are visible.

## Adding to the allowlist

`scripts/leak-gate-allow.txt` is committed on purpose: the point of an allowlist
is that adding to it shows up in a diff and has to be justified. Format is
`IP  # reason`, and the bar is that the address must be public knowledge
independent of this lab. A public resolver qualifies. A VPS the lab talks to
does not, even as "just" a jump host — that is topology.

If a finding is a gate bug rather than an allowlist case, fix the gate and add
the case to `tests/leak-gate/test_leak_gate.py`, so it cannot come back.

## Changelog

### 2026-10-04 — independent adversarial pass (blog repo agent)

Three findings, all real, all fixed in the commit that follows this document.

**IPv6 was not checked at all.** `ipaddress` was imported but only ever reached
dotted quads, so a Google public IPv6 address passed. Nothing was leaking — the
corpus contains no IPv6 — but a v6-capable lab quoting a real prefix would have
walked through. Fixed by extracting v6 candidates with a deliberately loose
regex and handing every one to `ipaddress.ip_address()` as the authority, which
is what keeps clock times, MAC addresses, `std::vector`, `::before` and a
Python `a[::2]` slice from reading as addresses. Verified against the tracked
tree first: of the 11 candidates the regex produces, 8 do not parse and the 3
that do are `fe80::`, `::1` and `::`, all allowed. The v6 forms of the already
allowlisted public resolvers were added, and the allowlist now normalises
addresses so one entry matches every legal spelling of it.

**Path arguments were silently ignored** — the worst of the three findings.
`leak-gate.py /nonexistent/fake.md` printed `leak gate: clean` and exited 0,
reporting a clean result for a file it never opened. Since the contract has the
homelab agent run this locally before pushing, the bug manufactured exactly the
false confidence the gate exists to remove. It is the same failure as the
vulnerability scanner reporting zero open ports while scanning an address that
no longer existed. Fixed: explicit paths are scanned, a bad path or unknown
option exits 2, and a partial run prints `PARTIAL SCAN` and says what it did not
cover.

**The baseline header undercounted itself** — it said "seven images" while
carrying nine entries, and named only six. The hashes and the safety claim were
correct; only the prose was wrong. Replaced with a per-file list, because a
hand-maintained count is exactly what drifts, and there is now a test asserting
every pinned entry is named in the header and that every hash still matches its
file.

Test count went 46 → 62.

**Four findings were withdrawn by the reviewer, and are recorded here so nobody
"fixes" a non-problem later:**

- Uppercase `GHP_…` passing is correct. Real GitHub tokens are lowercase and
  `gh[pousr]_[A-Za-z0-9]{36,}` matches the genuine format.
- Decimal `3232235777` passing is correct. It decodes to `192.168.1.1`, which is
  RFC1918 and allowed by design.
- Base64-encoded secrets passing is accepted scope. Decoding every
  base64-shaped string would false-positive on hashes, minified assets and image
  data.
- Secrets split across source lines pass. Inherent to line-based scanning, and
  not worth the complexity for an agent-written draft.

The reviewer also independently re-verified all nine baseline hashes and
confirmed no GPS IFD, no `Make` and no `Model` in any of them, and confirmed the
workflow has no `continue-on-error` or `|| true` so failures propagate.

### 2026-10-04 (later) — first real pattern file, and what it exposed

Two defects, both found by the first site-pattern file written from the setup
guide rather than by a test.

**The source label named the wrong file.** The loader reads
`scripts/leak-gate-patterns.local` but reported findings as coming from
`scripts/leak-patterns.local` — the path variable was updated when the gate
moved to its own pattern file and the display string was not. Harmless to the
scan, corrosive to trust: a control that misreports which file it loaded is the
same class of defect as the baseline header that undercounted itself. Now
tested.

**A site pattern could ban a mandated placeholder, and nothing said so.** The
guide's worked example used `203.0.113.5` as the illustrative WAN address. That
is TEST-NET-3 — the value the contract mandates as the safe *replacement*. The
resulting pattern failed three places including the contract's own
redaction-rules table, and because site patterns and their matches are withheld
by design, the findings gave no hint of the cause. The same template also
offered a bare UUID shape, which matched the Greenbone scanner object ID in a
published post.

Both are guide bugs rather than user error, and the guide was rewritten: every
example line now ships commented out, so a half-finished pattern file is inert
rather than wrong, and no example contains a usable value.

The gate also refuses such a pattern at load time now, with the line number and
the reason. The check is **structural, not an enumerated list** — it strips the
regex furniture off each pattern and asks `ipaddress` whether what remains sits
in a private or documentation range, so every such address is caught rather
than the ones someone thought to list. That distinction was not theoretical:
the first version of the guard was a string list and missed `198.51.100.77`
because the list contained `198.51.100.5`. A genuinely public address is still
accepted as a pattern, which is the case that has to keep working.

Test count 62 → 68.

### 2026-10-04 (later still) — configuring it for real

Three defects, all found by a person configuring the gate rather than by a
test, and all in the seam between the tool and its instructions.

**An unedited template placeholder was accepted.** The guide ships every
example commented out with a capitalised stand-in, and the intended edit is to
uncomment *and* substitute. Doing only the first half produced
`\bPUT-YOUR-REAL-LABEL-HERE\b`, which loaded, counted toward
`1 site pattern(s)`, made the "no site patterns loaded" note disappear — every
visible sign of a working configuration — and matched nothing. The exact
failure this gate exists to prevent, arriving through its own configuration.
Now refused at load, by exact token and by shape (`PUT-YOUR`, `CHANGEME`,
`TODO`, `-HERE`, `xxxx`), so the next template's stand-ins are caught too.

**A malformed pattern gave a useless error.** Replacing the stand-in between
two `\b` anchors took the `b` with it, leaving a pattern starting `\m`.
Python said `bad escape \m at position 0`, which is accurate and no help at
all to the person who made the edit. The gate now diagnoses the common cases —
a lost `b` from a leading `\b`, unbalanced brackets or parens, a trailing lone
backslash — and a test asserts the pattern still is not echoed on the error
path, since an error message is exactly where a withheld value tends to escape.

**An unescaped dot is now warned about.** A pattern written as a hostname
rather than a label contains bare dots, each of which matches any character.
Warned rather than refused, because a deliberate `.` is legitimate, but said
out loud: an over-broad pattern reports clean until the day it fires on
something unrelated.

Also recorded as known gap 10: R1's withholding does not hold when R2 or R3
matches the same value, because those rules print by design.

Test count 68 → 77.

### 2026-10-04 (last) — closing the fail-open case

Everything above fails closed. One thing did not, and it was the gap worth
caring about most, because it was the only one where a broken configuration
produced a **passing** result.

Site patterns live in two places nothing keeps in sync: a gitignored file on
the lab host, and the `LEAK_PATTERNS` repository secret used by CI. Neither is
reviewable — the local file is not committed and a GitHub secret cannot be read
back out of the UI. A secret holding a *broken* pattern fails loudly, and did,
twice. A secret holding *fewer* patterns, or none at all, reported `clean` and
passed, because a check that is not running finds nothing.

That is not hypothetical. CI ran against a stale secret for three runs on this
very branch, and it was caught only because the stale value happened to be
invalid rather than empty. An empty one would have passed, and the gate would
have reported a clean scan while silently applying one fewer rule — the same
shape as the vulnerability scanner reporting zero open ports against an address
that no longer existed.

`scripts/leak-gate-expect.txt` now declares how many site patterns must load,
and the gate refuses to run when the number does not match. Fewer than declared
is reported as an incomplete configuration whose clean result cannot be
trusted; more than declared is reported as an unreviewed pattern in use. The
file is committed precisely so that changing the number appears in a diff,
which is the only review possible over configuration that is otherwise
invisible.

Before: an unset secret, an all-commented secret, and a correct secret all
exited 0. After: only the correct one does.

Test count 77 → 85.
