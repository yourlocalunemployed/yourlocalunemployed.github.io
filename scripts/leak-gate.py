#!/usr/bin/env python3
"""Leak gate -- Phase 1 of docs/blog-agent-handoff.md.

Fails a branch that carries a credential, a real public address, a real DDNS
hostname, an image with metadata still attached, a file from notes/, or a
handoff that never attested to being redacted.

Run it by hand before any push:

    python3 scripts/leak-gate.py

In CI it runs on `draft/**` pushes and on pull requests into main. Exit 0 means
clean; exit 1 means findings; exit 2 means the gate itself could not run.

Why it fails closed
-------------------
Anything pushed to this repo is permanent. GitHub serves branch content, not
just main, so a leak on a `draft/` branch is public the moment it lands and
deleting the branch afterwards does not undo it. This already happened here:
two screenshots were redacted in a later commit and the unredacted originals
are still one `git show` away, because the redaction came after the push.

Note the deliberate contrast with .claude/hooks/. Those all fail OPEN, and that
is correct for them -- they are assistants, and an assistant that blocks the
work when its own code breaks is worse than no assistant. This file is the
opposite. It is a security control, and a control that fails open is not a
control, it is a label. Every unexpected condition here exits non-zero.

Why it does not print what it finds
-----------------------------------
This repo is public, so its GitHub Actions logs are public. A gate that echoes
the credential it found publishes that credential into a public log -- the gate
becomes the leak. So R1 reports the rule, the file, the line and the length, and
never an excerpt.

R2 and R3 DO print the value, on a different argument: by the time the gate
fires on a pushed branch that address is already public, and you cannot redact
an address you cannot see. The asymmetry is intentional, not an oversight.
"""
from __future__ import annotations

import hashlib
import ipaddress
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: True when running inside GitHub Actions.
IN_ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"


def annotate(level: str, title: str, message: str) -> None:
    """Emit a GitHub Actions annotation as well as writing to stderr.

    Without this the only thing a reader sees on a failed run is
    `Process completed with exit code 2`. The actual diagnosis goes to stderr,
    which lands in the job log -- and on this repository the Actions log needs
    authentication to read, so for anyone without it the gate fails for no
    stated reason. A security control that cannot say why it refused teaches
    people to re-run it until it passes.

    Workflow commands use %0A for newlines; a literal newline ends the command
    and the rest of the message is lost.
    """
    if IN_ACTIONS:
        esc = (message.replace("%", "%25").replace("\r", "")
                      .replace("\n", "%0A").replace(":", "%3A").replace(",", "%2C"))
        print(f"::{level} title={title}::{esc}", flush=True)

# ---------------------------------------------------------------------------
# R1 -- credentials
# ---------------------------------------------------------------------------
# Each entry is (rule-name, compiled regex). The name is what gets printed; the
# match never is. Lengths are deliberately generous at the low end -- a
# truncated token in a screenshot caption is still a token.
CRED_PATTERNS = [
    ("anthropic-api-key",   re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("openai-project-key",  re.compile(r"sk-proj-[A-Za-z0-9_\-]{20,}")),
    ("github-token",        re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("github-fine-grained", re.compile(r"github_pat_[A-Za-z0-9_]{22,}")),
    ("aws-access-key-id",   re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("tailscale-auth-key",  re.compile(r"tskey-[A-Za-z0-9\-]{10,}")),
    ("slack-token",         re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("gitlab-pat",          re.compile(r"glpat-[A-Za-z0-9_\-]{20,}")),
    ("private-key-block",   re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----")),
    # A JWT's three dot-separated base64url segments. Anchored on the `eyJ`
    # that every `{"` header encodes to, so it does not fire on arbitrary
    # dotted base64.
    ("jwt",                 re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")),
    ("aws-secret-key",      re.compile(r"(?i)aws_secret_access_key\s*[=:]\s*['\"]?[A-Za-z0-9/+=]{40}")),
]

# The generic `password: hunter2` rule is the one that decides whether this gate
# survives contact. Fire it too eagerly and every post quoting a config file
# fails, and a gate that cries wolf gets commented out within a week -- so it is
# narrowed three ways: the value must be long enough to be a real secret, must
# not be a placeholder, and must not be a shell/compose variable reference.
SECRET_ASSIGN = re.compile(
    r"(?i)\b(password|passwd|secret|api[_-]?key|apikey|auth[_-]?token|access[_-]?token)"
    r"\s*[=:]\s*"
    # `&?#` terminate the value as well as quotes and brackets. Without them a
    # URI like `/?access_token=REDACTED&limit=50` yields a 48-char "value" that
    # spans the remaining query parameters, and that mixture trips the
    # character-variety test even though the token itself says REDACTED. Caught
    # on the first calibration run against the live corpus, in
    # homelab-soc-logs-detections-dashboard.md:201.
    r"(?P<q>['\"]?)(?P<val>[^\s'\"<>`,;)}\]&?#]{8,})(?P=q)"
)

# Values that look like a secret's shape but are the absence of one. Every post
# in this repo redacts to `<password>` / `<token>`, so those must pass; the rest
# are the conventional stand-ins that show up in quoted upstream config.
PLACEHOLDER = re.compile(
    r"(?i)^(?:"
    r"<[^>]*>"                       # <password>, <token>, <community>
    # Every form of "this is a REFERENCE to a secret, not the secret". The list
    # grew on contact: `api_key: os.environ/OPENROUTER_API_KEY` is LiteLLM's own
    # syntax and appears twice in the gateway post, and the gate flagged it as a
    # 29-character mixed-class secret on the second calibration run. A homelab
    # blog quotes config from a dozen tools, so this needs to cover their
    # idioms, not just the shell's.
    r"|\$\{?[A-Za-z_][A-Za-z0-9_]*\}?"         # $VAR, ${VAR}            -- shell, compose
    r"|os\.environ[/\[.][^\s]*"                 # os.environ/NAME         -- LiteLLM
    r"|env:[^\s]+|ENV\[[^\]]*\]"               # env:NAME, ENV['NAME']   -- various
    r"|\$\{\{[^}]*\}\}|\{\{[^}]*\}\}"         # ${{ secrets.X }}, {{ x }} -- Actions, Jinja, Go
    r"|!secret\s+\S+"                          # !secret name            -- Home Assistant
    r"|%[A-Za-z_][A-Za-z0-9_]*%"                # %VAR%                   -- Windows
    r"|file://\S+|/run/secrets/\S+"            # a path to a secret, not one
    r"|\*{3,}|x{3,}|\.{3,}|-{3,}"    # ***, xxxx, ..., ----
    r"|redacted|removed|elided|snip|snipped"
    r"|changeme|change[_-]?me|placeholder|example|examplepass\w*"
    r"|your[_-]?\w+|some[_-]?\w+|my[_-]?\w+|the[_-]?\w+"
    r"|secret|password|passwd|token|apikey|api[_-]?key"   # the literal word as its own value
    r"|true|false|null|none|nil|empty|unset|yes|no"
    r"|enabled|disabled|required|optional|auto"
    r"|[0-9]{1,8}"                   # a bare small number is a setting, not a key
    r")$"
)


def looks_like_real_secret(val: str) -> bool:
    """True when a `key: value` value has the shape of an actual credential.

    Two signals, both required. Length, because real keys are long. And
    character variety, because `password: verylongwordhere` in prose is almost
    always documentation while `password: Xk7!pQ2mFz` is not. This will never be
    exact -- it is the second line behind the specific patterns above, and it is
    tuned to produce no findings on the current corpus so that any finding at
    all is worth reading.
    """
    if len(val) < 12:
        return False
    if PLACEHOLDER.match(val):
        return False
    classes = sum([
        bool(re.search(r"[a-z]", val)),
        bool(re.search(r"[A-Z]", val)),
        bool(re.search(r"[0-9]", val)),
        bool(re.search(r"[^A-Za-z0-9]", val)),
    ])
    return classes >= 3


# ---------------------------------------------------------------------------
# R2 -- public IPv4
# ---------------------------------------------------------------------------
# The lookarounds are the whole trick. Without them this regex carves fake
# addresses out of SNMP OIDs and SVG path data, both of which are in this repo
# right now: `1.3.6.1.2.1.31.1.1.1.1` in the LaMetric post yields `1.3.6.1` and
# `2.1.31.1`, and footer.html's `d="M12 .5C5.7.5.5 5.7..."` yields `5.7.4.4`.
# Requiring that no dot or digit sits on either side of the quad removes every
# one of them, because a real address is never embedded in a longer dotted run.
IPV4_RE = re.compile(r"(?<![\d.])((?:\d{1,3}\.){3}\d{1,3})(?![\d.])")

# SVG geometry is numbers separated by dots and commas and nothing else, so it
# is stripped before the IP pass rather than filtered after it.
SVG_NUMERIC_ATTR = re.compile(r'\b(?:d|viewBox|points|transform|stroke-dasharray)\s*=\s*"[^"]*"')

# 100.64.0.0/10 is carrier-grade NAT, which is where Tailscale lives. Python
# classifies it as neither private nor global -- verified on 3.13, it returns no
# flags at all -- so it would otherwise fall through both branches and get
# reported. 100.100.100.100 (MagicDNS) is inside it and the contract names it
# explicitly as allowed.
CGNAT = ipaddress.ip_network("100.64.0.0/10")

# IPv6, added 2026-10-04 after the repo agent's adversarial pass found that
# `ipaddress` was imported but only ever reached dotted quads, so
# 2a00:1450:4009:81a::200e walked straight through. Nothing was leaking --- the
# corpus contains no IPv6 at all --- but a v6-capable lab quoting a real prefix
# in a draft would not have been caught.
#
# The regex is deliberately LOOSE and the parser is the authority. An exact
# IPv6 grammar in a regex is long, hard to read and easy to get subtly wrong,
# and getting it wrong here means missing an address. So this finds runs of
# hex-and-colon with at least two colons and hands every candidate to
# ipaddress.ip_address(), which rejects the junk definitively.
#
# That split was checked against the tracked tree before being trusted: of 11
# candidates it produces, 7 are clock times (15:04:05, 20:30:02, ...) and one is
# a MAC prefix (00:0c:29:), and NONE of those eight parse as an address. The
# three that do parse are fe80::, ::1 and :: --- all allowed. Zero false
# positives on the real corpus.
#
# The surrounding character class also matters: excluding alphanumerics on both
# sides is what stops `std::vector`, `::before` and a Python `a[::2]` slice from
# being read as the unspecified address.
IPV6_RE = re.compile(
    r"(?<![0-9A-Za-z:._-])([0-9A-Fa-f]{0,4}(?::[0-9A-Fa-f]{0,4}){2,7})(?![0-9A-Za-z:._-])"
)


def ip_verdict(text: str) -> tuple[bool, str]:
    """(allowed, reason). Allowed means this address may appear in a public post."""
    try:
        addr = ipaddress.ip_address(text)
    except ValueError:
        # Not an address at all -- a version string like 17.6.4.1. Not our business.
        return True, "not an address"
    # CGNAT is an IPv4 network; comparing an IPv6Address against it raises
    # TypeError rather than returning False, so the version guard is load-bearing.
    if addr.version == 4 and addr in CGNAT:
        return True, "100.64/10 carrier-grade NAT (Tailscale)"
    # is_private is doing a lot of work here and it was checked rather than
    # assumed: it covers RFC1918, 127/8, 169.254/16, 0.0.0.0, 255.255.255.255
    # AND all three documentation ranges (192.0.2/24, 198.51.100/24,
    # 203.0.113/24), because they are all in the IANA special-purpose registry.
    # That is exactly the allowed set the contract lists, for free.
    # is_private is doing the heavy lifting for BOTH families and both were
    # measured rather than assumed. For v6 it covers 2001:db8::/32
    # (documentation), fe80::/10 (link-local), fc00::/7 (unique local), ::1 and
    # :: --- which is the same allowed set the contract lists for v4, again for
    # free.
    if addr.is_private:
        return True, "private or documentation range"
    if addr.is_multicast or addr.is_reserved:
        return True, "multicast or reserved"
    return False, f"globally routable IPv{addr.version}"


# ---------------------------------------------------------------------------
# R3 -- DDNS and tunnel hostnames
# ---------------------------------------------------------------------------
# The published placeholder. 26 occurrences across 4 posts today; anything else
# under these providers is a real endpoint and must not ship.
ALLOWED_DDNS_HOST = "mylab.duckdns.org"

DDNS_RE = re.compile(
    r"\b([A-Za-z0-9][A-Za-z0-9_\-]*(?:\.[A-Za-z0-9][A-Za-z0-9_\-]*)*"
    r"\.(?:duckdns\.org|no-ip\.(?:org|com|biz)|dynu\.(?:net|com)|ddns\.net"
    r"|ngrok\.(?:io|app)|ngrok-free\.app|trycloudflare\.com|loca\.lt"
    r"|ts\.net|tailscale\.net|zrok\.io|serveo\.net))\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# R4 -- image metadata
# ---------------------------------------------------------------------------
# Detection, not decoding. The rule is "any EXIF at all", so finding the segment
# is sufficient and keeps this stdlib-only -- no Pillow, no exiftool, nothing to
# install in CI that could silently go missing and turn the check into a no-op.
#
# Allowed chunks are the ones a legitimate export writes and that carry no
# information about where or on what the picture was taken: colour profile,
# gamma, physical dimensions.
PNG_METADATA_CHUNKS = {b"eXIf", b"tEXt", b"iTXt", b"zTXt"}


def jpeg_metadata(data: bytes) -> list[str]:
    """Names of metadata segments in a JPEG, walking the marker chain properly.

    A plain byte-search for b'Exif' would also hit the string inside image data
    by chance, and would miss a GPS IFD that sits in a segment the search did
    not anticipate. Walking the chain costs ten lines and is exact.
    """
    found: list[str] = []
    if not data.startswith(b"\xff\xd8"):
        return found
    i = 2
    n = len(data)
    while i + 3 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if marker == 0xDA:          # start of scan: pixel data from here on
            break
        seg_len = int.from_bytes(data[i + 2:i + 4], "big")
        if seg_len < 2:
            break
        body = data[i + 4:i + 2 + seg_len]
        if marker == 0xE1 and body.startswith(b"Exif\x00\x00"):
            found.append("EXIF")
            # The GPS IFD is pointer tag 0x8825. Naming it explicitly matters:
            # the contract singles out GPS, and "this one has your coordinates"
            # is a different conversation from "this one has a camera model".
            if b"\x88\x25" in body:
                found.append("EXIF/GPS-pointer")
        elif marker == 0xE1 and b"ns.adobe.com/xap" in body:
            found.append("XMP")
        elif marker == 0xED:
            found.append("IPTC/Photoshop")
        elif marker == 0xFE:
            found.append("JPEG-comment")
        i += 2 + seg_len
    return found


def png_metadata(data: bytes) -> list[str]:
    """Names of metadata chunks in a PNG, by walking the chunk list."""
    found: list[str] = []
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return found
    i = 8
    n = len(data)
    while i + 8 <= n:
        length = int.from_bytes(data[i:i + 4], "big")
        ctype = data[i + 4:i + 8]
        if ctype == b"IEND":
            break
        if ctype in PNG_METADATA_CHUNKS:
            found.append(ctype.decode("ascii", "replace"))
        i += 12 + length                 # length + type + data + crc
        if length < 0 or i <= 0:
            break
    return found


def webp_metadata(data: bytes) -> list[str]:
    """Names of metadata chunks in a WebP RIFF container."""
    found: list[str] = []
    if not (data.startswith(b"RIFF") and data[8:12] == b"WEBP"):
        return found
    i = 12
    n = len(data)
    while i + 8 <= n:
        ctype = data[i:i + 4]
        length = int.from_bytes(data[i + 4:i + 8], "little")
        if ctype in (b"EXIF", b"XMP "):
            found.append(ctype.decode("ascii", "replace").strip())
        i += 8 + length + (length & 1)   # chunks are even-padded
        if length < 0:
            break
    return found


def image_metadata(path: str) -> list[str]:
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        # Unreadable file in a security check is a failure, not a pass.
        return [f"unreadable: {exc}"]
    ext = os.path.splitext(path)[1].lower()
    if ext in (".jpg", ".jpeg"):
        return jpeg_metadata(data)
    if ext == ".png":
        return png_metadata(data)
    if ext == ".webp":
        return webp_metadata(data)
    return []


# ---------------------------------------------------------------------------
# R6 -- handoff attestation
# ---------------------------------------------------------------------------
# Top-level YAML keys by regex rather than a parser, so the gate keeps its
# zero-dependency property. The contract only asks three questions of this file
# and all three are answerable from column zero.
def handoff_findings(path: str, text: str) -> list[str]:
    problems = []
    for key in ("slug", "body"):
        if not re.search(r"(?m)^%s\s*:" % re.escape(key), text):
            problems.append(f"missing required key `{key}`")
    m = re.search(r"(?m)^redacted\s*:\s*(\S+)", text)
    if not m:
        problems.append("missing `redacted:` attestation")
    elif m.group(1).strip().lower() not in ("true", "yes"):
        problems.append(f"`redacted:` is {m.group(1)!r}, must be true")
    return problems


# ---------------------------------------------------------------------------
# Driving the scan
# ---------------------------------------------------------------------------
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".tif", ".tiff", ".heic"}
SKIP_DIRS = ("public/", "resources/", ".git/")

# This file necessarily contains every pattern it looks for, and the planted
# leaks exist precisely to be leaks. Both are excluded by path, and the test
# harness asserts the exclusion is narrow enough that a real leak elsewhere is
# still caught.
SELF_EXCLUDE = ("scripts/leak-gate.py", "tests/leak-gate/")


def tracked_files() -> list[str]:
    """Files git would actually push. Untracked files are not our problem."""
    out = subprocess.run(["git", "-C", ROOT, "ls-files", "-z"],
                         capture_output=True, check=True)
    return [p for p in out.stdout.decode("utf-8", "replace").split("\0") if p]


# Strings a site pattern must NEVER match. Every one of these is either a value
# the contract mandates as the safe replacement, or a value it explicitly allows.
# A pattern that matches one of them is definitionally wrong: it bans the thing
# you are supposed to redact TO, so correct content fails and the author's only
# way out is to stop running the gate.
#
# This guard exists because it happened. The worked example in the setup guide
# used 203.0.113.5 as the illustrative WAN address, so the first pattern file
# written from it banned TEST-NET-3 -- and the gate then failed on the contract's
# own redaction-rules table, which names 203.0.113.5 as the correct replacement.
# The findings gave no hint of the cause, because site patterns and their matches
# are withheld by design. Catching it at load time with a named reason costs
# twenty lines and turns a baffling failure into an instruction.
PLACEHOLDER_CANARIES = [
    ("203.0.113.5", "TEST-NET-3, the mandated WAN-address replacement"),
    ("203.0.113.1", "TEST-NET-3"),
    ("198.51.100.5", "TEST-NET-2, the alternate mandated replacement"),
    ("192.0.2.1", "TEST-NET-1"),
    ("2001:db8::1", "the documented IPv6 range"),
    ("mylab.duckdns.org", "the mandated DDNS hostname replacement"),
    ("auth.mylab.duckdns.org", "a subdomain of the mandated replacement"),
    ("10.10.0.1", "RFC1918, explicitly allowed by the contract"),
    ("192.168.1.1", "RFC1918, explicitly allowed"),
    ("172.18.0.1", "RFC1918, explicitly allowed"),
    ("127.0.0.1", "loopback, explicitly allowed"),
    ("100.100.100.100", "Tailscale MagicDNS, explicitly allowed"),
    ("<password>", "this repo's redaction vocabulary"),
    ("<token>", "this repo's redaction vocabulary"),
    ("<community>", "this repo's redaction vocabulary"),
    ("REDACTED", "this repo's redaction vocabulary"),
    ("CLAUDDEB", "an internal hostname the contract explicitly allows"),
    ("/home/student/blog", "a local path the contract explicitly allows"),
]


def pattern_as_address(rx_src: str) -> "ipaddress._BaseAddress | None":
    """If a pattern is essentially one literal IP, return that address.

    A string canary list can only name the addresses someone thought of, and
    the first version of it missed 198.51.100.77 because it listed
    198.51.100.5. This is the structural version: strip the regex furniture and
    ask ipaddress whether what remains is an address, so EVERY address in a
    documentation or private range is caught rather than the handful enumerated.
    """
    t = (rx_src.replace("\\b", "").replace("\\.", ".")
               .replace("^", "").replace("$", "").strip())
    if not t or not re.fullmatch(r"[0-9A-Fa-f:.]+", t):
        return None
    try:
        return ipaddress.ip_address(t)
    except ValueError:
        return None


# An unedited template line. The setup guide ships every example pattern
# commented out with a capitalised stand-in, and the intended edit is to
# uncomment AND substitute. Doing only the first half produces a pattern that
# loads, reports `1 site pattern(s)`, and matches nothing -- a check that does
# not run while reporting success, which is the precise failure this gate was
# built to prevent. It happened on the first real attempt.
#
# Both halves matter: the exact tokens catch this guide's stand-ins, and the
# shape heuristic catches the next template's, or a hand-written TODO.
TEMPLATE_TOKENS = (
    "PUT-YOUR-REAL-LABEL-HERE", "PUT-YOUR-TAILNET-LABEL-HERE",
    "PUT-THE-ACTUAL-UUID-HERE", "NNN.NNN.NNN.NNN",
)
TEMPLATE_SHAPE = re.compile(
    r"(?i)\b(?:put[-_]?your|your[-_]?real|replace[-_]?(?:me|with)|"
    r"change[-_]?me|fill[-_]?in|todo|fixme|xxxx+|example[-_]?value|"
    r"[a-z-]*-here)\b"
)


def check_patterns_are_edited(pats: list[tuple[str, re.Pattern]]) -> None:
    """Refuse a site pattern that is still the template's placeholder."""
    for name, rx in pats:
        src = rx.pattern
        literal = src
        for tok in (r"\b", "^", "$"):
            literal = literal.replace(tok, "")
        literal = literal.replace(r"\.", ".")
        hit = next((t for t in TEMPLATE_TOKENS
                    if t in src or rx.search(t)), None)
        if hit is None and TEMPLATE_SHAPE.search(literal):
            hit = literal
        if hit is not None:
            msg = (f"{name} is still an unedited template placeholder. "
                   "It loads, counts toward 'site pattern(s)', and matches "
                   "NOTHING -- a check that does not run while reporting "
                   "success. Replace the capitalised stand-in with your real "
                   "value, or comment the line out again.")
            annotate("error", "leak gate: unedited site pattern", msg)
            print(
                f"leak-gate: {name} is still an unedited template placeholder.\n"
                f"  It loads, it counts toward 'site pattern(s)', and it matches\n"
                f"  NOTHING -- a check that does not run while reporting success.\n"
                f"  Replace the capitalised stand-in with your real value, or\n"
                f"  comment the line out again.",
                file=sys.stderr)
            sys.exit(2)


def check_patterns_against_canaries(pats: list[tuple[str, re.Pattern]]) -> None:
    """Refuse a site pattern that would ban a mandated placeholder.

    Exits 2 rather than reporting findings, because this is the gate being
    misconfigured, not the content being wrong -- and a misconfigured security
    control should say so in those words instead of producing failures the
    author cannot interpret.
    """
    for name, rx in pats:
        # Structural check first: a pattern that IS an allowed address.
        addr = pattern_as_address(rx.pattern)
        if addr is not None:
            allowed, why = ip_verdict(str(addr))
            if allowed:
                annotate("error", "leak gate: self-defeating site pattern",
                         f"{name} is a literal {addr}, which is {why}. A site "
                         "pattern must never match an address the contract "
                         "mandates or allows.")
                print(
                    f"leak-gate: {name} is a literal {addr}, which is {why}.\n"
                    f"  A site pattern must never match an address the contract "
                    f"mandates or allows:\n"
                    f"  it would fail correct content and leave no way to pass.\n"
                    f"  Replace it with your REAL address, or delete the line.",
                    file=sys.stderr)
                sys.exit(2)
        # Then the string canaries, for the non-address placeholders.
        for value, why in PLACEHOLDER_CANARIES:
            if rx.search(value):
                # The pattern itself is still withheld; only its location and
                # what it wrongly matched are named.
                annotate("error", "leak gate: self-defeating site pattern",
                         f"{name} matches {value!r}, which is {why}. A site "
                         "pattern must never match a value the contract "
                         "mandates or allows.")
                print(
                    f"leak-gate: {name} matches {value!r}, which is {why}.\n"
                    f"  A site pattern must never match a value the contract "
                    f"mandates or allows:\n"
                    f"  it would fail correct content and leave no way to pass.\n"
                    f"  Edit that line to match your REAL value instead of the "
                    f"example, or delete it.",
                    file=sys.stderr)
                sys.exit(2)


def diagnose_regex_error(src: str, exc: re.error) -> str:
    """Turn Python's regex error into something actionable.

    Python says `bad escape \\m at position 0`, which is accurate and useless
    to someone who has just edited a word-boundary anchor. The commonest edit
    here is replacing a capitalised stand-in between two \\b anchors, and the
    commonest slip is selecting one character too many and taking the `b` with
    it -- leaving `\\mylabel\\b`, where `\\m` is not an escape.

    A confusing error on a security control is not cosmetic: it is how someone
    concludes the tool is broken and stops running it.
    """
    hints = []
    if src.startswith("\\") and len(src) > 1 and src[1].isalpha() and src[1] != "b":
        try:
            re.compile("\\b" + src[1:])
            hints.append(
                "The leading \\b is missing its 'b' -- the line starts "
                f"\\{src[1]} instead of \\b.\n"
                "  It looks like the 'b' was selected along with the "
                "placeholder when you replaced it.\n"
                "  Fix: add a 'b' straight after the first backslash, so the "
                "line reads \\b then your value then \\b.")
        except re.error:
            pass
    if not hints and src.endswith("\\") :
        hints.append("The line ends in a lone backslash, which escapes nothing.")
    if not hints and "(" in src and src.count("(") != src.count(")"):
        hints.append("Unbalanced parentheses. Escape a literal one as \\(.")
    if not hints and "[" in src and src.count("[") != src.count("]"):
        hints.append("Unbalanced square brackets. Escape a literal one as \\[.")
    if not hints:
        hints.append("A literal dot must be written \\. and a literal "
                     "backslash \\\\.")
    return "  " + "\n  ".join(hints)


def load_extra_patterns() -> list[tuple[str, re.Pattern]]:
    """Site-specific patterns that are themselves sensitive.

    One regex per line, `#` for comments -- the format scripts/leak-patterns.local
    established. Gitignored on purpose and so cannot be read in CI;
    there the same content arrives as the LEAK_PATTERNS environment variable from
    a repository secret. Either source is optional, and absence is NOT silently
    ignored -- it is reported, because "the extra patterns quietly stopped being
    checked" is the exact failure this repo keeps producing.
    """
    raw = os.environ.get("LEAK_PATTERNS", "")
    source = "LEAK_PATTERNS env"
    # Deliberately NOT scripts/leak-patterns.local. That file belongs to the
    # TALEB ILM exporter, and pointing this gate at it produced 27 findings
    # across six published posts on the first calibration run -- one 8-character
    # alphabetic word, matched over and over. Not a credential, just the wrong
    # corpus. The contract says this gate should have "this shape" of file, so
    # it gets its own with the same format and its own gitignore entry.
    local = os.path.join(ROOT, "scripts", "leak-gate-patterns.local")
    if not raw and os.path.exists(local):
        with open(local, encoding="utf-8") as fh:
            raw = fh.read()
        source = "scripts/leak-gate-patterns.local"
    pats = []
    for n, line in enumerate(raw.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        # An unescaped dot matches ANY character, so a pattern written as a
        # hostname silently matches far more than intended. Warned rather than
        # refused, because a deliberate `.` is legitimate -- but said out loud,
        # because the slip is invisible in the result: an over-broad pattern
        # still reports "clean" until the day it fires on something unrelated.
        bare_dot = re.sub(r"\\.", "", s).count(".")
        if bare_dot:
            print(f"  note: {source} line {n} contains {bare_dot} unescaped "
                  f"dot(s). A bare '.' matches any character; write a literal "
                  f"dot as \\. ", file=sys.stderr)
        try:
            pats.append((f"site-pattern:{source}:{n}", re.compile(s)))
        except re.error as exc:
            # The pattern itself is still withheld -- only the line number, the
            # parser's complaint and the diagnosis are shown.
            msg = (f"{source} line {n} is not a valid regex: {exc}\n"
                   f"{diagnose_regex_error(s, exc)}")
            print(f"leak-gate: {msg}", file=sys.stderr)
            annotate("error", "leak gate: invalid site pattern", msg)
            sys.exit(2)
    return pats


def load_baseline() -> dict[str, str]:
    """Pre-existing findings, keyed by sha256 so they cannot shelter a new one.

    Keyed by content hash and NOT by path, which is the whole point. A baseline
    keyed by path would let anyone drop a fresh screenshot -- GPS and all -- over
    an old filename and sail through. Change a byte and the hash stops matching,
    the entry stops applying, and the gate fails.
    """
    path = os.path.join(ROOT, "scripts", "leak-gate-baseline.txt")
    base: dict[str, str] = {}
    if not os.path.exists(path):
        return base
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            parts = s.split(None, 2)
            if len(parts) >= 2:
                base[parts[0].lower()] = parts[1]
    return base


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_ip(text: str) -> str:
    """Normalised form of an address, or the input unchanged if it is not one.

    Only matters for IPv6, where one address has many legal spellings. Without
    this, an allowlist entry written as 2606:4700:4700::1111 would not match the
    same address written out in full.
    """
    try:
        return str(ipaddress.ip_address(text))
    except ValueError:
        return text


def load_ip_allowlist() -> dict[str, str]:
    """Public addresses that are legitimately in posts, with a reason each.

    Committed and reviewable, unlike the secret pattern file -- the point of an
    allowlist is that adding to it shows up in a diff. Format: `IP  # reason`.
    """
    path = os.path.join(ROOT, "scripts", "leak-gate-allow.txt")
    allow: dict[str, str] = {}
    if not os.path.exists(path):
        return allow
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            ip, _, reason = s.partition("#")
            ip = ip.strip()
            why = reason.strip() or "allowlisted"
            allow[ip] = why
            # Store the canonical spelling too, so a v6 entry matches however it
            # was written in a post.
            allow[canonical_ip(ip)] = why
    return allow


USAGE = """usage: leak-gate.py [-h] [--try-pattern] [PATH ...]

With no PATH, scans every file `git ls-files` reports -- the full check, and the
one CI runs.

With one or more PATHs, scans exactly those files and labels the result a
PARTIAL SCAN. A path that does not exist, or is not a file, is an ERROR (exit 2),
never a silent skip.

That last part is the whole reason this argument parsing exists. Until
2026-10-04 the script discarded argv entirely, so

    python3 scripts/leak-gate.py /nonexistent/fake.md

printed `leak gate: clean` and exited 0 -- reporting a clean result for a file it
had never opened. The contract has the homelab agent run this locally before
pushing, which made that the single most dangerous bug the gate could have: it
manufactured exactly the false confidence the gate exists to remove. Found by
the repo agent's adversarial pass.

--try-pattern prompts for one string and reports which site patterns match it.
The string is read without echo, so it does not reach the terminal, the shell
history, or the process list, and it is never written anywhere. Use it to prove
a pattern actually fires: a pattern that loads but matches nothing is a check
that silently does not run, which is the failure this whole gate exists to stop.

exit 0 clean   1 findings   2 the gate could not run
"""


def try_pattern_mode() -> int:
    """Interactively confirm that a site pattern matches what it is meant to.

    Exists because writing a correct regex for a value you must not paste into
    a chat is genuinely hard, and the failure is silent: a typo, a missing \\b,
    or an unescaped dot produces a pattern that loads fine and never fires. The
    gate would then report `1 site pattern(s)` and `clean` forever while
    checking nothing -- indistinguishable from working.

    getpass is used rather than input() so the value never lands in the
    terminal scrollback, the shell history, or /proc/<pid>/cmdline.
    """
    import getpass
    pats = load_extra_patterns()
    check_patterns_are_edited(pats)
    check_patterns_against_canaries(pats)
    if not pats:
        print("No site patterns loaded. Nothing to test.\n"
              "  Expected: scripts/leak-gate-patterns.local with at least one "
              "uncommented line,\n  or the LEAK_PATTERNS environment variable.",
              file=sys.stderr)
        return 2
    print(f"{len(pats)} site pattern(s) loaded.")
    print("Type or paste a string to test. It is NOT echoed, NOT stored, and "
          "NOT printed back.")
    try:
        probe = getpass.getpass("  string: ")
    except (EOFError, KeyboardInterrupt):
        print("\naborted")
        return 2
    if not probe:
        print("  empty input, nothing tested")
        return 2
    hits = [name for name, rx in pats if rx.search(probe)]
    if hits:
        print(f"  MATCHED by {len(hits)} pattern(s):")
        for h in hits:
            print(f"    {h}")
        print("  Good -- that pattern would block this string in a draft.")
        return 0
    print("  NO PATTERN MATCHED.")
    print("  If this string is something you meant to catch, the pattern is "
          "wrong and is\n  currently a check that does nothing. Common causes: "
          "an unescaped dot, a\n  missing \\b, a typo, or the line still "
          "commented out.")
    return 1


def parse_args(argv: list[str]) -> list[str] | None:
    """Explicit paths to scan, or None meaning 'scan everything tracked'.

    Exits 2 on anything it does not understand. Silence is not an option here:
    an argument that is accepted but ignored is how a scanner comes to report on
    files it never read.
    """
    if not argv:
        return None
    for a in argv:
        if a in ("-h", "--help"):
            print(USAGE)
            sys.exit(0)
    if argv == ["--try-pattern"]:
        sys.exit(try_pattern_mode())
    bad_opts = [a for a in argv if a.startswith("-")]
    if bad_opts:
        print(f"leak-gate: unrecognised option(s): {' '.join(bad_opts)}\n",
              file=sys.stderr)
        print(USAGE, file=sys.stderr)
        sys.exit(2)
    missing = [a for a in argv if not os.path.isfile(a)]
    if missing:
        for a in missing:
            kind = "is a directory" if os.path.isdir(a) else "does not exist"
            print(f"leak-gate: {a}: {kind}", file=sys.stderr)
        print("\nRefusing to report a result for files that were not read. "
              "A clean result for a path that does not exist is worse than an "
              "error, because it looks like a pass.", file=sys.stderr)
        sys.exit(2)
    return argv


def main() -> int:
    findings: list[str] = []

    def report(rule: str, path: str, line: int | None, msg: str) -> None:
        where = f"{path}:{line}" if line else path
        findings.append(f"  [{rule}] {where}\n        {msg}")

    explicit = parse_args(sys.argv[1:])
    if explicit is None:
        try:
            files = tracked_files()
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            print(f"leak-gate: cannot list tracked files: {exc}", file=sys.stderr)
            return 2
    else:
        # Normalise to repo-relative, so findings read the same either way and
        # the baseline and exclusion paths still match.
        files = []
        for a in explicit:
            ap = os.path.abspath(a)
            files.append(os.path.relpath(ap, ROOT) if ap.startswith(ROOT + os.sep)
                         else ap)

    extra_patterns = load_extra_patterns()
    check_patterns_are_edited(extra_patterns)
    check_patterns_against_canaries(extra_patterns)
    ip_allow = load_ip_allowlist()
    baseline = load_baseline()
    baselined: list[str] = []

    # --- R5: notes/ must never be tracked --------------------------------
    # Gitignored on purpose; the only way one gets here is `git add -f`, which
    # is the single most expensive mistake available in this repo.
    for path in files:
        if path.startswith("notes/"):
            report("R5-notes", path, None,
                   "file under notes/ is tracked. notes/ holds UNREDACTED sources "
                   "(real credentials, full addressing) and is gitignored on purpose. "
                   "Remove it from the index: git rm --cached <path>")

    for path in files:
        if path.startswith(SKIP_DIRS) or path.startswith(SELF_EXCLUDE):
            continue
        abspath = os.path.join(ROOT, path)
        if not os.path.isfile(abspath):
            continue
        ext = os.path.splitext(path)[1].lower()

        # --- R4: image metadata -----------------------------------------
        if ext in IMAGE_EXT:
            meta = image_metadata(abspath)
            if meta:
                digest = sha256_of(abspath)
                if baseline.get(digest) == path:
                    # Unchanged pre-existing file. Noted, not failed -- and
                    # counted out loud below so it stays visible.
                    baselined.append(f"{path} ({', '.join(meta)})")
                    continue
            for kind in meta:
                report("R4-image-metadata", path, None,
                       f"carries {kind}. Strip it before pushing: "
                       f"exiftool -all= '{path}'  (or re-export without metadata). "
                       "GPS in a phone screenshot is the sharp case.")
            continue

        # Text pass. Anything that is not decodable UTF-8 is not prose and not
        # an image we know -- skipped rather than guessed at.
        try:
            with open(abspath, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        except (OSError, UnicodeDecodeError):
            continue

        is_handoff = re.match(r"^handoff/[^/]+\.ya?ml$", path) is not None
        if is_handoff:
            for problem in handoff_findings(path, "\n".join(lines)):
                report("R6-attestation", path, None,
                       problem + ". A handoff missing slug, body or redacted: true "
                                 "is rejected without further processing.")

        for n, line in enumerate(lines, 1):
            # --- R1: credentials ----------------------------------------
            for name, rx in CRED_PATTERNS:
                m = rx.search(line)
                if m:
                    # Length and rule only. Never the match -- see the module
                    # docstring: this log is public.
                    report("R1-credential", path, n,
                           f"matches {name} ({len(m.group(0))} chars). "
                           "Not printed: Actions logs on this repo are public. "
                           "Replace with <password>/<token>, or remove the key entirely.")
            for name, rx in extra_patterns:
                if rx.search(line):
                    report("R1-credential", path, n,
                           f"matches {name}. Pattern and match both withheld.")
            m = SECRET_ASSIGN.search(line)
            if m and looks_like_real_secret(m.group("val")):
                report("R1-credential", path, n,
                       f"`{m.group(1)}` is assigned a value with the shape of a real "
                       f"secret ({len(m.group('val'))} chars, mixed character classes). "
                       "Use <password> or <token>. If this is a genuine placeholder, "
                       "make it look like one.")

            # --- R2: public IPv4 ----------------------------------------
            scan_line = SVG_NUMERIC_ATTR.sub('d=""', line) if ext in (".html", ".svg", ".xml") else line
            for rx in (IPV4_RE, IPV6_RE):
                for m in rx.finditer(scan_line):
                    ip = m.group(1)
                    allowed, _reason = ip_verdict(ip)
                    if allowed:
                        continue
                    # Allowlist comparison is normalised for v6, where the same
                    # address has many spellings: 2606:4700:4700::1111 and
                    # 2606:4700:4700:0:0:0:0:1111 are one address, and a plain
                    # string match would catch only whichever one was typed
                    # into the allowlist file.
                    if ip in ip_allow or canonical_ip(ip) in ip_allow:
                        continue
                    hint = ("203.0.113.5 (TEST-NET-3) or 198.51.100.x"
                            if ":" not in ip else "2001:db8::/32 (the documented range)")
                    report("R2-public-ip", path, n,
                           f"{ip} is {_reason}. Replace with {hint}. If it is "
                           "genuinely public and safe (a public resolver, a "
                           "documented address), add it to "
                           "scripts/leak-gate-allow.txt with a reason.")

            # --- R3: DDNS / tunnel hostnames ----------------------------
            for m in DDNS_RE.finditer(line):
                host = m.group(1).lower()
                # A SUBDOMAIN of the placeholder is a correct redaction, not a
                # leak: the corpus already carries auth.mylab.duckdns.org and
                # grafana.mylab.duckdns.org, which are exactly what the rule
                # wants to see. An exact-match comparison flagged all six of
                # them on the first calibration run.
                if host == ALLOWED_DDNS_HOST or host.endswith("." + ALLOWED_DDNS_HOST):
                    continue
                report("R3-ddns-host", path, n,
                       f"{host} is a real dynamic-DNS or tunnel endpoint. "
                       f"Replace with {ALLOWED_DDNS_HOST}.")

    if baselined:
        print(f"leak gate: {len(baselined)} pre-existing image(s) carry metadata, "
              f"hash-pinned in scripts/leak-gate-baseline.txt:")
        for b in baselined:
            print(f"    {b}")
        print("    These were checked by hand: no GPS, no device model, no location.")
        print("    Strip them and delete the baseline lines -- do not update the hashes.\n")

    if explicit is not None:
        print(f"leak gate: PARTIAL SCAN -- {len(files)} path(s) given on the "
              f"command line.\n  This is NOT the full check. Rules R5 (tracked "
              f"files under notes/) and\n  anything in a file you did not name "
              f"are not covered. Run with no\n  arguments before pushing.\n")

    if findings:
        print("leak gate: FAILED\n")
        print("\n".join(findings))
        annotate("error", f"leak gate: {len(findings)} finding(s)",
                 "\n".join(f.strip() for f in findings))
        print(f"\n{len(findings)} finding(s). Nothing is pushed until these are clean.")
        print("A push cannot be undone: GitHub serves branch content, so deleting")
        print("the branch afterwards does not retract a leak.")
        return 1

    scanned = sum(1 for p in files
                  if not p.startswith(SKIP_DIRS) and not p.startswith(SELF_EXCLUDE))
    label = (("path scanned" if scanned == 1 else "paths scanned")
             if explicit is not None else "tracked files scanned")
    if IN_ACTIONS:
        print(f"::notice title=leak gate::clean - {scanned} {label}, "
              f"{len(extra_patterns)} site pattern(s)", flush=True)
    print(f"leak gate: clean ({scanned} {label}, "
          f"{len(extra_patterns)} site pattern(s), "
          f"{len(set(ip_allow)) } allowlisted address spelling(s))")
    if not extra_patterns:
        # Not a failure, but said out loud every run. A check that silently
        # stopped running is worse than one that was never added.
        print("  note: no site-specific patterns loaded "
              "(scripts/leak-gate-patterns.local absent and LEAK_PATTERNS unset)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:                      # noqa: BLE001 -- fail closed
        # Deliberately broad. An unexpected exception in a security control must
        # not read as a pass; see the module docstring.
        print(f"leak-gate: aborted: {type(exc).__name__}: {exc}", file=sys.stderr)
        annotate("error", "leak gate: aborted",
                 f"{type(exc).__name__}: {exc}")
        sys.exit(2)
