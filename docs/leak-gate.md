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

Current state: **316 tracked files, 0 findings, 9 baselined.** 46 tests pass.

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
10. **Editing the baseline file is not itself gated.** Adding a hash to
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
