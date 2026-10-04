#!/usr/bin/env python3
"""Planted-leak tests for scripts/leak-gate.py.

    python3 tests/leak-gate/test_leak_gate.py

The contract (docs/blog-agent-handoff.md, Phase 1) is explicit about why this
file exists rather than a happy-path check:

    Built the same way as ad-lab-runbook's validate.yml: tested against planted
    leaks, so it is proven to fail and not merely proven to pass. A gate that
    cannot fail is worse than no gate, because it buys false confidence.

So every test here is one of two kinds:

  MUST-FAIL  -- a planted leak. The test fails if the gate does NOT catch it.
  MUST-PASS  -- a legitimate construct that merely resembles a leak. The test
                fails if the gate DOES flag it.

The must-pass half is not padding. It is the half that decides whether the gate
survives: the first calibration run against the live corpus produced 31 findings
and every single one was a false positive, including SNMP OIDs chopped into
fake IP addresses, SVG path coordinates doing the same, LiteLLM's
`os.environ/NAME` reference syntax read as a 29-character secret, and correct
redactions like `auth.mylab.duckdns.org` rejected for being subdomains of the
placeholder. Each of those is now a test below. A gate that cries wolf gets
commented out within a week, which leaves you with no gate and a false memory
of having one.

Each case runs the real script against a real throwaway git repository, because
the gate reads `git ls-files` to decide what is in scope. Stubbing that out
would test a different program.
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GATE = os.path.join(REPO, "scripts", "leak-gate.py")


# ---------------------------------------------------------------------------
# Minimal image builders -- stdlib only, so CI installs nothing.
# ---------------------------------------------------------------------------
# These are built byte by byte rather than with Pillow for two reasons: the gate
# itself is stdlib-only and its tests should not need more than it does, and a
# hand-built file lets a test plant exactly one metadata segment and nothing
# else, which is what makes a failure diagnostic.
def png(chunks: list[tuple[bytes, bytes]]) -> bytes:
    """A PNG with the given chunks between a real IHDR and IEND."""
    out = [b"\x89PNG\r\n\x1a\n"]

    def chunk(ctype: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + ctype + data
                + struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF))

    # 1x1 greyscale, 8-bit
    out.append(chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)))
    for ctype, data in chunks:
        out.append(chunk(ctype, data))
    out.append(chunk(b"IDAT", zlib.compress(b"\x00\x00")))
    out.append(chunk(b"IEND", b""))
    return b"".join(out)


def jpeg(segments: list[tuple[int, bytes]]) -> bytes:
    """A JPEG with the given APPn/COM segments before the start of scan."""
    out = [b"\xff\xd8"]
    for marker, body in segments:
        out.append(bytes([0xFF, marker]) + struct.pack(">H", len(body) + 2) + body)
    # A start-of-scan the walker will stop at, then end of image.
    out.append(b"\xff\xda" + struct.pack(">H", 2))
    out.append(b"\xff\xd9")
    return b"".join(out)


def webp(chunks: list[tuple[bytes, bytes]]) -> bytes:
    body = [b"WEBP"]
    for ctype, data in chunks:
        pad = b"\x00" if len(data) % 2 else b""
        body.append(ctype + struct.pack("<I", len(data)) + data + pad)
    payload = b"".join(body)
    return b"RIFF" + struct.pack("<I", len(payload)) + payload


EXIF_WITH_GPS = b"Exif\x00\x00MM\x00*\x00\x00\x00\x08\x88\x25\x00\x04\x00\x00\x00\x01"
EXIF_PLAIN = b"Exif\x00\x00MM\x00*\x00\x00\x00\x08\x01\x12\x00\x03\x00\x00\x00\x01"


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------
class GateCase(unittest.TestCase):
    """Runs the real gate in a real throwaway repo."""

    def setUp(self) -> None:
        self.dir = tempfile.mkdtemp(prefix="leakgate-test-")
        run = lambda *a: subprocess.run(["git", "-C", self.dir, *a],
                                        capture_output=True, check=True)
        run("init", "-q")
        run("config", "user.email", "t@example.com")
        run("config", "user.name", "t")
        os.makedirs(os.path.join(self.dir, "scripts"), exist_ok=True)
        shutil.copy(GATE, os.path.join(self.dir, "scripts", "leak-gate.py"))
        # The allowlist travels with the gate: several must-pass cases depend on
        # it, and a test repo without it would fail them for the wrong reason.
        for name in ("leak-gate-allow.txt",):
            src = os.path.join(REPO, "scripts", name)
            if os.path.exists(src):
                shutil.copy(src, os.path.join(self.dir, "scripts", name))

    def tearDown(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, relpath: str, content, *, add: bool = True, force: bool = False):
        full = os.path.join(self.dir, relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        mode = "wb" if isinstance(content, bytes) else "w"
        with open(full, mode, **({} if isinstance(content, bytes) else {"encoding": "utf-8"})) as fh:
            fh.write(content)
        if add:
            args = ["git", "-C", self.dir, "add"] + (["-f"] if force else []) + [relpath]
            subprocess.run(args, capture_output=True, check=True)
        return full

    def run_gate(self, env_extra: dict | None = None):
        env = dict(os.environ)
        # Keep the developer's own local pattern file out of the test, or results
        # differ between machines and CI.
        env.pop("LEAK_PATTERNS", None)
        env.update(env_extra or {})
        return subprocess.run([sys.executable, "scripts/leak-gate.py"],
                              cwd=self.dir, capture_output=True, text=True, env=env)

    # -- assertions --------------------------------------------------------
    def assertCaught(self, rule: str, note: str = ""):
        r = self.run_gate()
        self.assertEqual(r.returncode, 1,
                         f"PLANTED LEAK NOT CAUGHT ({note}).\n"
                         f"exit={r.returncode}\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}")
        self.assertIn(rule, r.stdout,
                      f"caught, but not by {rule} ({note}).\nstdout:\n{r.stdout}")
        return r

    def assertClean(self, note: str = ""):
        r = self.run_gate()
        self.assertEqual(r.returncode, 0,
                         f"FALSE POSITIVE on legitimate content ({note}).\n"
                         f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}")
        return r


# ---------------------------------------------------------------------------
# MUST-FAIL: R1 credentials
# ---------------------------------------------------------------------------
class PlantedCredentials(GateCase):

    def test_anthropic_key(self):
        self.write("content/posts/x.md", "key: sk-ant-api03-" + "A" * 40 + "\n")
        self.assertCaught("R1-credential", "sk-ant- key")

    def test_github_token(self):
        self.write("content/posts/x.md", "token: ghp_" + "b" * 36 + "\n")
        self.assertCaught("R1-credential", "ghp_ token")

    def test_aws_access_key_id(self):
        self.write("content/posts/x.md", "id: AKIAIOSFODNN7EXAMPLE\n")
        self.assertCaught("R1-credential", "AKIA key id")

    def test_tailscale_auth_key(self):
        self.write("content/posts/x.md", "tskey-auth-k7Yd2mQ1x-abcdefghijkl\n")
        self.assertCaught("R1-credential", "tskey- auth key")

    def test_private_key_block(self):
        self.write("content/posts/x.md",
                   "-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----\n")
        self.assertCaught("R1-credential", "PEM private key block")

    def test_jwt(self):
        self.write("content/posts/x.md",
                   "auth: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27u\n")
        self.assertCaught("R1-credential", "JWT")

    def test_slack_token(self):
        self.write("content/posts/x.md", "hook: xoxb-123456789012-abcdefghijkl\n")
        self.assertCaught("R1-credential", "slack xoxb-")

    def test_generic_high_entropy_password(self):
        self.write("content/posts/x.md", "    password: Xk7!pQ2mFz9@Lw3Rt\n")
        self.assertCaught("R1-credential", "generic password with real entropy")

    def test_credential_value_is_never_printed(self):
        """The gate must not echo what it found: this repo's Actions logs are public."""
        secret = "sk-ant-api03-" + "Z" * 40
        self.write("content/posts/x.md", f"key: {secret}\n")
        r = self.assertCaught("R1-credential", "withholding check")
        self.assertNotIn(secret, r.stdout + r.stderr,
                         "the gate printed the credential it found -- on a public "
                         "repo that publishes it into a public Actions log")
        self.assertNotIn("Z" * 20, r.stdout + r.stderr, "partial secret leaked into output")

    def test_site_pattern_from_env_is_applied_and_withheld(self):
        self.write("content/posts/x.md", "the host is wopr-internal-07\n")
        r = self.run_gate({"LEAK_PATTERNS": "wopr-internal-\\d+"})
        self.assertEqual(r.returncode, 1, f"site pattern from env not applied:\n{r.stdout}")
        self.assertNotIn("wopr-internal-07", r.stdout, "site-pattern match was printed")
        self.assertNotIn("wopr-internal-\\d+", r.stdout, "site pattern itself was printed")


# ---------------------------------------------------------------------------
# MUST-FAIL: R2 public addresses
# ---------------------------------------------------------------------------
class PlantedAddresses(GateCase):

    def test_public_ip(self):
        self.write("content/posts/x.md", "WAN is 51.68.123.45 today\n")
        self.assertCaught("R2-public-ip", "ordinary public IPv4")

    def test_one_octet_outside_documentation_range(self):
        """203.0.113.0/24 is allowed; 203.0.114.0/24 is somebody's real network.

        The off-by-one is the case worth testing. A gate that allowlists by
        string prefix rather than by network passes this and should not.
        """
        self.write("content/posts/x.md", "gateway 203.0.114.5\n")
        self.assertCaught("R2-public-ip", "203.0.114.5, just outside TEST-NET-3")

    def test_public_ip_in_a_code_fence(self):
        self.write("content/posts/x.md", "```bash\ncurl http://51.68.123.45/api\n```\n")
        self.assertCaught("R2-public-ip", "a fence is not a hiding place")


# ---------------------------------------------------------------------------
# MUST-FAIL: R3 DDNS and tunnel hostnames
# ---------------------------------------------------------------------------
class PlantedHostnames(GateCase):

    def test_real_duckdns_host(self):
        self.write("content/posts/x.md", "https://myrealbox.duckdns.org/grafana\n")
        self.assertCaught("R3-ddns-host", "a duckdns host that is not the placeholder")

    def test_real_duckdns_subdomain(self):
        self.write("content/posts/x.md", "https://auth.myrealbox.duckdns.org/\n")
        self.assertCaught("R3-ddns-host", "subdomain of a REAL duckdns host")

    def test_ngrok_tunnel(self):
        self.write("content/posts/x.md", "forwarding to https://1a2b3c.ngrok-free.app\n")
        self.assertCaught("R3-ddns-host", "ngrok tunnel")

    def test_tailnet_name(self):
        self.write("content/posts/x.md", "ssh user@claudeb.tail9f2c1.ts.net\n")
        self.assertCaught("R3-ddns-host", "tailnet DNS name")

    def test_cloudflare_quick_tunnel(self):
        self.write("content/posts/x.md", "https://odd-words-here.trycloudflare.com\n")
        self.assertCaught("R3-ddns-host", "trycloudflare quick tunnel")


# ---------------------------------------------------------------------------
# MUST-FAIL: R4 image metadata
# ---------------------------------------------------------------------------
class PlantedImageMetadata(GateCase):

    def test_jpeg_exif(self):
        self.write("static/images/posts/x/a.jpg", jpeg([(0xE1, EXIF_PLAIN)]))
        self.assertCaught("R4-image-metadata", "JPEG with an EXIF APP1 segment")

    def test_jpeg_exif_with_gps_pointer(self):
        self.write("static/images/posts/x/a.jpg", jpeg([(0xE1, EXIF_WITH_GPS)]))
        r = self.assertCaught("R4-image-metadata", "JPEG carrying a GPS IFD pointer")
        self.assertIn("GPS", r.stdout,
                      "GPS must be named explicitly -- 'this has your coordinates' is "
                      "a different conversation from 'this has a camera model'")

    def test_jpeg_comment(self):
        self.write("static/images/posts/x/a.jpg", jpeg([(0xFE, b"shot at home")]))
        self.assertCaught("R4-image-metadata", "JPEG COM comment segment")

    def test_png_text_chunk(self):
        self.write("static/images/posts/x/a.png", png([(b"tEXt", b"Comment\x00internal host")]))
        self.assertCaught("R4-image-metadata", "PNG tEXt chunk")

    def test_png_exif_chunk(self):
        self.write("static/images/posts/x/a.png", png([(b"eXIf", EXIF_PLAIN[6:])]))
        self.assertCaught("R4-image-metadata", "PNG eXIf chunk")

    def test_webp_exif_chunk(self):
        self.write("static/images/posts/x/a.webp",
                   webp([(b"VP8 ", b"\x00" * 10), (b"EXIF", EXIF_PLAIN[6:])]))
        self.assertCaught("R4-image-metadata", "WebP EXIF chunk")

    def test_baseline_cannot_shelter_a_changed_file(self):
        """The evasion the baseline is designed to stop.

        A baseline keyed by PATH would let a fresh screenshot -- GPS and all --
        be dropped over an old filename and sail through. This one is keyed by
        sha256, so the entry stops applying the moment a byte changes.
        """
        img = "static/images/posts/x/pinned.jpg"
        self.write(img, jpeg([(0xE1, EXIF_PLAIN)]))
        import hashlib
        with open(os.path.join(self.dir, img), "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        self.write("scripts/leak-gate-baseline.txt", f"{digest}  {img}  # known\n")
        self.assertClean("a correctly hash-pinned baseline entry should pass")

        # Now swap in different content at the same path, keeping the old hash.
        self.write(img, jpeg([(0xE1, EXIF_WITH_GPS)]))
        self.assertCaught("R4-image-metadata",
                          "baseline keyed by hash must not shelter replaced content")


# ---------------------------------------------------------------------------
# MUST-FAIL: R5 notes/, R6 attestation
# ---------------------------------------------------------------------------
class PlantedNotesAndAttestation(GateCase):

    def test_notes_tracked(self):
        self.write("notes/raw.md", "the real password is hunter2\n", force=True)
        self.assertCaught("R5-notes", "a file under notes/ reached the index")

    def test_handoff_without_attestation(self):
        self.write("handoff/x.yaml", "slug: x\ntitle: X\nbody: |\n  hello\n")
        self.assertCaught("R6-attestation", "handoff with no redacted: key")

    def test_handoff_attestation_false(self):
        self.write("handoff/x.yaml", "slug: x\nbody: |\n  hi\nredacted: false\n")
        self.assertCaught("R6-attestation", "redacted: false")

    def test_handoff_missing_slug_and_body(self):
        self.write("handoff/x.yaml", "title: X\nredacted: true\n")
        r = self.assertCaught("R6-attestation", "handoff missing slug and body")
        self.assertIn("slug", r.stdout)
        self.assertIn("body", r.stdout)

    def test_valid_handoff_passes(self):
        self.write("handoff/x.yaml",
                   "slug: x\ntitle: X\nbody: |\n  hello 10.10.0.1\nredacted: true\n")
        self.assertClean("a complete, attested handoff")


# ---------------------------------------------------------------------------
# MUST-PASS: the false positives found against the live corpus
# ---------------------------------------------------------------------------
class LegitimateContent(GateCase):
    """Every case here was a real false positive on the first calibration run."""

    def test_rfc1918_is_allowed(self):
        self.write("content/posts/x.md",
                   "10.10.0.1 192.168.1.189 172.18.0.1 127.0.0.1 0.0.0.0 169.254.1.1\n")
        self.assertClean("RFC1918 + loopback: 12 existing posts use these deliberately")

    def test_documentation_ranges_are_allowed(self):
        self.write("content/posts/x.md", "203.0.113.5 198.51.100.7 192.0.2.1\n")
        self.assertClean("the three IANA documentation ranges")

    def test_tailscale_cgnat_is_allowed(self):
        self.write("content/posts/x.md", "resolver 100.100.100.100 peer 100.64.0.3\n")
        self.assertClean("100.64/10 is neither is_private nor is_global in Python")

    def test_snmp_oid_is_not_an_ip(self):
        self.write("content/posts/x.md",
                   "snmpwalk -v2c -c <community> <pfsense-ip> 1.3.6.1.2.1.31.1.1.1.1\n")
        self.assertClean("the OID in the LaMetric post yields 1.3.6.1 and 2.1.31.1")

    def test_svg_path_data_is_not_an_ip(self):
        self.write("layouts/_partials/f.html",
                   '<svg><path d="M12 .5C5.7.5.5 5.7.5 12c0 5.1 3.3 9.4 7.9 10.9"/></svg>\n')
        self.assertClean("footer.html path data yields 5.7.4.4, 3.2.7.8, 3.1.8.8")

    def test_allowlisted_public_resolvers(self):
        self.write("content/posts/x.md", "upstreams: 1.1.1.1 9.9.9.9 8.8.8.8 93.184.216.34\n")
        self.assertClean("public resolvers and example.com's documented address")

    def test_placeholder_hostname_and_its_subdomains(self):
        self.write("content/posts/x.md",
                   "https://mylab.duckdns.org and https://auth.mylab.duckdns.org\n")
        self.assertClean("a subdomain of the placeholder is a CORRECT redaction")

    def test_redacted_placeholders(self):
        self.write("content/posts/x.md",
                   "password: <password>\ntoken: <token>\n"
                   "community: <community>\nsecret: ***\napi_key: REDACTED\n")
        self.assertClean("this repo's own redaction vocabulary")

    def test_env_var_reference_forms(self):
        self.write("content/posts/x.md",
                   "api_key: os.environ/OPENROUTER_API_KEY\n"
                   "password: ${POSTGRES_PASSWORD}\n"
                   "token: $GITHUB_TOKEN\n"
                   "api_key: ${{ secrets.OPENAI_KEY }}\n"
                   "password: !secret db_password\n"
                   "secret: /run/secrets/pg_pass\n")
        self.assertClean("references to secrets, not secrets -- LiteLLM, compose, "
                         "Actions, Home Assistant, docker secrets")

    def test_redacted_uri_query_string(self):
        self.write("content/posts/x.md",
                   "uri: /?access_token=REDACTED&since=0&limit=50&dir=f\n")
        self.assertClean("the value must stop at & or the query string reads as entropy")

    def test_png_with_only_benign_chunks(self):
        self.write("static/images/posts/x/a.png",
                   png([(b"gAMA", struct.pack(">I", 45455)),
                        (b"pHYs", struct.pack(">IIB", 2835, 2835, 1))]))
        self.assertClean("colour/gamma/dimension chunks carry nothing about origin")

    def test_untracked_file_is_out_of_scope(self):
        """An untracked leak is not pushed, so it is not the gate's business."""
        self.write("content/posts/x.md", "clean\n")
        self.write("scratch.md", "sk-ant-api03-" + "Q" * 40 + "\n", add=False)
        self.assertClean("untracked files are never pushed")

    def test_hugo_output_is_out_of_scope(self):
        """public/ is build output; Cloudflare rebuilds it and it is gitignored."""
        self.write("content/posts/x.md", "clean\n")
        self.write("public/index.html", "leak 51.68.123.45\n", force=True)
        self.assertClean("public/ is generated and excluded by design")


# ---------------------------------------------------------------------------
# The gate's own failure modes
# ---------------------------------------------------------------------------
class GateFailsClosed(GateCase):

    def test_invalid_site_pattern_aborts_rather_than_skipping(self):
        """A broken pattern file must stop the run, not silently check less.

        'The extra patterns quietly stopped being checked' is the exact shape of
        failure this repo keeps producing -- a scanner reporting a clean result
        while scanning nothing.
        """
        self.write("content/posts/x.md", "clean\n")
        r = self.run_gate({"LEAK_PATTERNS": "this is ( not valid regex"})
        self.assertEqual(r.returncode, 2,
                         f"a malformed pattern file must exit 2, got {r.returncode}:\n"
                         f"{r.stdout}\n{r.stderr}")

    def test_clean_repo_exits_zero(self):
        self.write("content/posts/x.md", "a post about 10.10.0.1 and mylab.duckdns.org\n")
        r = self.assertClean("baseline sanity")
        self.assertIn("clean", r.stdout)

    def test_reports_when_no_site_patterns_are_loaded(self):
        """Absence of the optional pattern file is announced, never silent."""
        self.write("content/posts/x.md", "clean\n")
        r = self.assertClean("no pattern file present")
        self.assertIn("no site-specific patterns loaded", r.stdout)


# ---------------------------------------------------------------------------
# Regressions from the repo agent's adversarial pass, 2026-10-04
# ---------------------------------------------------------------------------
class IPv6(GateCase):
    """GAP 1. `ipaddress` was imported but only ever reached dotted quads.

    Nothing was leaking -- the corpus contains no IPv6 at all -- but a
    v6-capable lab quoting a real prefix in a draft would have walked straight
    through. The must-pass cases here are the ones that decide whether the rule
    is usable: a loose IPv6 regex is the easiest way to start reading clock
    times and C++ scope resolution as addresses.
    """

    def test_public_ipv6_is_caught(self):
        self.write("content/posts/x.md", "upstream 2a00:1450:4009:81a::200e\n")
        r = self.assertCaught("R2-public-ip", "Google's public IPv6")
        self.assertIn("IPv6", r.stdout, "the finding should name the family")

    def test_documentation_range_is_allowed(self):
        """2001:db8::/32 is to v6 what 203.0.113.0/24 is to v4."""
        self.write("content/posts/x.md", "example 2001:db8::1 and 2001:db8:85a3::8a2e:370:7334\n")
        self.assertClean("the documented v6 placeholder range")

    def test_link_local_and_unique_local_are_allowed(self):
        self.write("content/posts/x.md", "fe80::1 fd00::1 fc00::1 ::1 ::\n")
        self.assertClean("link-local, unique-local, loopback, unspecified")

    def test_allowlisted_v6_matches_either_spelling(self):
        """One v6 address has many legal spellings; a string match catches one."""
        self.write("content/posts/x.md",
                   "dns 2606:4700:4700::1111 and 2606:4700:4700:0:0:0:0:1111\n")
        self.assertClean("compressed and expanded forms of one allowlisted address")

    def test_clock_times_are_not_addresses(self):
        """Seven of the eleven v6 candidates in the real corpus are clock times."""
        self.write("content/posts/x.md",
                   "logged at 15:04:05 then 20:30:02 then 22:14:25\n")
        self.assertClean("timestamps must not parse as addresses")

    def test_mac_address_is_not_an_ipv6_address(self):
        self.write("content/posts/x.md", "vmware oui 00:0c:29:ab:cd:ef\n")
        self.assertClean("a MAC has six groups, not eight, and no ::")

    def test_scope_resolution_and_slices_are_not_addresses(self):
        """`::` alone IS a valid address, so the surrounding characters decide."""
        self.write("content/posts/x.md",
                   "```cpp\nstd::vector<int> v; auto s = a[::2];\n```\n"
                   "```css\np::before { content: ''; }\n```\n")
        self.assertClean("C++ scope resolution, Python slices, CSS pseudo-elements")


class CommandLineArguments(GateCase):
    """GAP 2, and the most dangerous bug the gate could have had.

    The script discarded argv, so `leak-gate.py /nonexistent/fake.md` printed
    `leak gate: clean` and exited 0 -- a clean result for a file it never
    opened. The contract has the homelab agent run this locally before pushing,
    which made the bug manufacture exactly the false confidence the gate exists
    to remove.
    """

    def test_nonexistent_path_is_an_error_not_a_pass(self):
        self.write("content/posts/x.md", "clean\n")
        r = subprocess.run([sys.executable, "scripts/leak-gate.py", "/nonexistent/fake.md"],
                           cwd=self.dir, capture_output=True, text=True)
        self.assertEqual(r.returncode, 2,
                         f"a path that does not exist must exit 2, not report clean:\n"
                         f"{r.stdout}\n{r.stderr}")
        self.assertNotIn("clean", r.stdout)

    def test_directory_argument_is_an_error(self):
        self.write("content/posts/x.md", "clean\n")
        r = subprocess.run([sys.executable, "scripts/leak-gate.py", "content"],
                           cwd=self.dir, capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, f"a directory must exit 2:\n{r.stderr}")

    def test_unrecognised_option_is_an_error(self):
        self.write("content/posts/x.md", "clean\n")
        r = subprocess.run([sys.executable, "scripts/leak-gate.py", "--scan-everything"],
                           cwd=self.dir, capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, "an unknown option must not be ignored")

    def test_help_exits_zero(self):
        self.write("content/posts/x.md", "clean\n")
        r = subprocess.run([sys.executable, "scripts/leak-gate.py", "--help"],
                           cwd=self.dir, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("usage:", r.stdout)

    def test_explicit_path_is_actually_scanned(self):
        """The inverse of the bug: a named file with a leak must still fail."""
        self.write("content/posts/bad.md", "wan 51.68.123.45\n")
        r = subprocess.run([sys.executable, "scripts/leak-gate.py", "content/posts/bad.md"],
                           cwd=self.dir, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, f"named file was not scanned:\n{r.stdout}")
        self.assertIn("R2-public-ip", r.stdout)

    def test_partial_scan_says_it_is_partial(self):
        """A narrower check must not look like the full one."""
        self.write("content/posts/x.md", "clean 10.10.0.1\n")
        r = subprocess.run([sys.executable, "scripts/leak-gate.py", "content/posts/x.md"],
                           cwd=self.dir, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("PARTIAL SCAN", r.stdout,
                      "a partial run must announce itself or it reads as the full check")
        self.assertIn("NOT the full check", r.stdout)

    def test_untracked_file_can_be_scanned_explicitly(self):
        """Full scans are git-scoped; an explicit path need not be tracked yet.

        This is the useful case: check a file before `git add`.
        """
        self.write("content/posts/x.md", "clean\n")
        self.write("draft.md", "wan 51.68.123.45\n", add=False)
        r = subprocess.run([sys.executable, "scripts/leak-gate.py", "draft.md"],
                           cwd=self.dir, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, f"explicit untracked path not scanned:\n{r.stdout}")


class BaselineDocumentation(unittest.TestCase):
    """The repo agent found the header said "seven" while carrying nine entries.

    The hashes and the safety claim were correct; only the narrative was wrong.
    It is tested because an inaccurate comment on a security control costs trust
    in the control, and a hand-maintained count is exactly the thing that drifts.
    """

    def test_every_entry_is_accounted_for_by_name(self):
        path = os.path.join(REPO, "scripts", "leak-gate-baseline.txt")
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        entries = [l.split()[1] for l in lines
                   if l.strip() and not l.strip().startswith("#") and len(l.split()) >= 2]
        header = "\n".join(l for l in lines if l.strip().startswith("#"))
        for e in entries:
            self.assertIn(os.path.basename(e), header,
                          f"{e} is pinned but not accounted for in the header. "
                          "Every baselined file must be named and explained.")

    def test_hashes_match_the_files(self):
        import hashlib
        path = os.path.join(REPO, "scripts", "leak-gate-baseline.txt")
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                digest, rel = s.split()[0], s.split()[1]
                full = os.path.join(REPO, rel)
                self.assertTrue(os.path.exists(full), f"{rel} is baselined but missing")
                with open(full, "rb") as img:
                    actual = hashlib.sha256(img.read()).hexdigest()
                self.assertEqual(actual, digest,
                                 f"{rel} has changed since it was baselined. Do NOT "
                                 "update the hash -- strip the metadata and delete "
                                 "the line.")


class SitePatternSanity(GateCase):
    """A site pattern that bans a mandated placeholder must be refused at load.

    This happened. The setup guide's worked example used 203.0.113.5 as the
    illustrative WAN address, so the first pattern file written from it banned
    TEST-NET-3 -- and the gate then failed on the contract's own redaction-rules
    table, which names 203.0.113.5 as the correct replacement. The findings gave
    no clue, because site patterns and their matches are withheld by design.
    Refusing at load time with a named reason turns that into an instruction.
    """

    def _with_pattern(self, pattern: str):
        self.write("content/posts/x.md", "nothing interesting here\n")
        self.write("scripts/leak-gate-patterns.local", pattern + "\n", add=False)
        return self.run_gate()

    def test_documentation_address_as_a_pattern_is_refused(self):
        r = self._with_pattern(r"\b203\.0\.113\.5\b")
        self.assertEqual(r.returncode, 2, f"TEST-NET-3 as a pattern must exit 2:\n{r.stdout}")
        self.assertIn("203.0.113.5", r.stderr)

    def test_the_check_is_structural_not_an_enumerated_list(self):
        """Any address in the ranges, not only the ones someone listed.

        The first version of this guard was a list of specific strings and it
        missed 198.51.100.77 because the list contained 198.51.100.5.
        """
        for addr in (r"\b198\.51\.100\.77\b", r"\b203\.0\.113\.99\b",
                     r"\b192\.0\.2\.254\b", r"\b10\.10\.0\.55\b",
                     r"\b2001:db8::dead\b"):
            r = self._with_pattern(addr)
            self.assertEqual(r.returncode, 2,
                             f"{addr} is private or documentation and must be "
                             f"refused as a pattern:\n{r.stdout}\n{r.stderr}")

    def test_a_real_public_address_is_accepted_as_a_pattern(self):
        """The case that must keep working: pinning your actual WAN address."""
        r = self._with_pattern(r"\b51\.68\.123\.45\b")
        self.assertEqual(r.returncode, 0,
                         f"a genuinely public address is a legitimate site "
                         f"pattern:\n{r.stdout}\n{r.stderr}")

    def test_mandated_hostname_as_a_pattern_is_refused(self):
        r = self._with_pattern(r"mylab\.duckdns\.org")
        self.assertEqual(r.returncode, 2, "banning the mandated replacement hostname")
        self.assertIn("mylab.duckdns.org", r.stderr)

    def test_redaction_vocabulary_as_a_pattern_is_refused(self):
        r = self._with_pattern(r"<password>")
        self.assertEqual(r.returncode, 2, "banning this repo's own redaction token")

    def test_source_label_names_the_file_actually_read(self):
        """The label said leak-patterns.local while reading leak-gate-patterns.local.

        A security control that misreports which file it loaded is the same
        class of defect as the baseline header that undercounted itself.
        """
        self.write("content/posts/x.md", "the host is wopr-internal-07\n")
        self.write("scripts/leak-gate-patterns.local", r"wopr-internal-\d+" + "\n", add=False)
        r = self.run_gate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("leak-gate-patterns.local", r.stdout,
                      "the finding must name the file that was actually read")


class UneditedTemplatePatterns(GateCase):
    """A pattern left as the template's stand-in must be refused.

    This happened on the first real attempt. The guide ships every example
    commented out with a capitalised stand-in; the intended edit is to
    uncomment AND substitute. Doing only the first half produced
    `\\bPUT-YOUR-REAL-LABEL-HERE\\b`, which loaded, counted toward
    "1 site pattern(s)", made the "no site patterns loaded" note disappear --
    every visible signal of a working configuration -- and matched nothing,
    because that string appears nowhere in the blog.

    It is the exact failure the gate exists to prevent, arriving through the
    gate's own configuration. The earlier canary guard did not catch it: that
    one refuses patterns banning MANDATED placeholders, which is a different
    mistake.
    """

    def _with_pattern(self, pattern: str):
        self.write("content/posts/x.md", "nothing interesting here\n")
        self.write("scripts/leak-gate-patterns.local", pattern + "\n", add=False)
        return self.run_gate()

    def test_guide_stand_in_is_refused(self):
        r = self._with_pattern(r"\bPUT-YOUR-REAL-LABEL-HERE\b")
        self.assertEqual(r.returncode, 2,
                         f"an unedited template placeholder must exit 2:\n{r.stdout}")
        self.assertIn("unedited template placeholder", r.stderr)

    def test_every_stand_in_this_guide_ships_is_refused(self):
        for ph in (r"\bPUT-YOUR-TAILNET-LABEL-HERE\b",
                   r"\bPUT-THE-ACTUAL-UUID-HERE\b",
                   r"\bNNN\.NNN\.NNN\.NNN\b"):
            r = self._with_pattern(ph)
            self.assertEqual(r.returncode, 2, f"{ph} should be refused")

    def test_generic_placeholder_shapes_are_refused(self):
        """The next template's stand-ins, and hand-written TODOs."""
        for ph in (r"\bCHANGEME\b", r"\bTODO\b", r"\bmy-real-value-here\b",
                   r"\bREPLACE-ME\b", r"\bxxxxxxxx\b"):
            r = self._with_pattern(ph)
            self.assertEqual(r.returncode, 2, f"{ph} should be refused as a placeholder")

    def test_a_real_looking_label_is_accepted(self):
        """The case that must keep working: an actual edited pattern."""
        r = self._with_pattern(r"\bwopr7lab\b")
        self.assertEqual(r.returncode, 0,
                         f"a genuine label must be accepted:\n{r.stdout}\n{r.stderr}")
        self.assertIn("1 site pattern(s)", r.stdout)
        self.assertNotIn("no site-specific patterns loaded", r.stdout)

    def test_an_edited_pattern_actually_fires(self):
        """Loading is not firing. Prove the accepted pattern blocks content.

        The label is used BARE here, not as wopr7lab.duckdns.org, so only R1
        fires. Attached to the domain it also trips R3, which prints the
        hostname by design -- and then an assertion that the value stayed
        withheld fails on R3's output while R1 behaved perfectly. That is the
        documented asymmetry doing its job, not a leak.
        """
        self.write("content/posts/x.md", "the host is called wopr7lab internally\n")
        self.write("scripts/leak-gate-patterns.local", r"\bwopr7lab\b" + "\n", add=False)
        r = self.run_gate()
        self.assertEqual(r.returncode, 1, f"an edited pattern must catch its value:\n{r.stdout}")
        self.assertIn("R1-credential", r.stdout)
        self.assertNotIn("wopr7lab", r.stdout, "the site-pattern match must stay withheld")


class MalformedPatternDiagnostics(GateCase):
    """A broken pattern must fail closed AND say how to fix it.

    Python's own message for the commonest slip here is `bad escape \\m at
    position 0`: accurate, and useless to someone who has just replaced a
    stand-in between two \\b anchors and taken the 'b' with it. A confusing
    error on a security control is not cosmetic -- it is how someone concludes
    the tool is broken and stops running it.
    """

    def _with_raw(self, raw: str):
        self.write("content/posts/x.md", "clean\n")
        self.write("scripts/leak-gate-patterns.local", raw + "\n", add=False)
        return self.run_gate()

    def test_lost_b_from_leading_word_boundary(self):
        r = self._with_raw(r"\mylabel\b")
        self.assertEqual(r.returncode, 2, "an invalid regex must fail closed")
        self.assertIn("missing its 'b'", r.stderr,
                      f"the diagnosis must name the actual cause:\n{r.stderr}")

    def test_unbalanced_bracket_is_diagnosed(self):
        r = self._with_raw(r"\b[0-9a-f\b")
        self.assertEqual(r.returncode, 2)
        self.assertIn("square brackets", r.stderr)

    def test_unbalanced_paren_is_diagnosed(self):
        r = self._with_raw(r"\b(abc\b")
        self.assertEqual(r.returncode, 2)
        self.assertIn("parentheses", r.stderr)

    def test_the_pattern_itself_is_not_echoed(self):
        """Even in an error path, a site pattern stays withheld."""
        r = self._with_raw(r"\msupersecretlabel\b")
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("supersecretlabel", r.stderr,
                         "the error path must not print the pattern")


class PatternCountIsEnforced(GateCase):
    """The one place the gate could fail OPEN, now closed.

    Site patterns live in two places nothing keeps in sync: a gitignored file
    on the lab host and the LEAK_PATTERNS secret in CI. Neither is reviewable.
    A secret holding a BROKEN pattern fails loudly, and did. A secret holding
    FEWER patterns, or none, reported `clean` and passed -- because a check
    that is not running finds nothing.

    That is not hypothetical: on 2026-10-04 CI ran against a stale secret for
    three runs, and it was caught only because the stale value happened to be
    invalid rather than empty. An empty one would have passed silently.

    scripts/leak-gate-expect.txt declares the required count. It is committed,
    so changing it shows up in a diff -- which is the point, since the patterns
    themselves never can.
    """

    def _setup(self, expected: str | None, patterns: str | None):
        self.write("content/posts/x.md", "a clean post about 10.10.0.1\n")
        if expected is not None:
            self.write("scripts/leak-gate-expect.txt", expected + "\n", add=False)
        env = {"LEAK_PATTERNS": patterns} if patterns is not None else None
        return self.run_gate(env)

    def test_missing_secret_no_longer_passes(self):
        """The exact fail-open case. Before this, exit 0."""
        r = self._setup("1", None)
        self.assertEqual(r.returncode, 2,
                         f"0 patterns against a declared 1 must fail:\n{r.stdout}")
        self.assertIn("INCOMPLETE", r.stderr)

    def test_all_commented_secret_no_longer_passes(self):
        r = self._setup("1", "# \\bsomelabel\\b")
        self.assertEqual(r.returncode, 2, "a secret with no live lines must fail")

    def test_correct_count_passes(self):
        r = self._setup("1", r"\bsomelabel\b")
        self.assertEqual(r.returncode, 0, f"the declared count must pass:\n{r.stderr}")

    def test_more_patterns_than_declared_also_fails(self):
        """Not dangerous, but it means an unreviewed pattern is in use."""
        r = self._setup("1", "\\bone\\b\n\\btwo\\b")
        self.assertEqual(r.returncode, 2, "an undeclared extra pattern must fail")
        self.assertIn("unreviewed", r.stderr)

    def test_absent_expect_file_leaves_the_gate_unconstrained(self):
        """A repo that has not opted in keeps the old behaviour."""
        r = self._setup(None, None)
        self.assertEqual(r.returncode, 0)
        self.assertIn("no site-specific patterns loaded", r.stdout)

    def test_zero_declared_means_zero_required(self):
        r = self._setup("0", None)
        self.assertEqual(r.returncode, 0, "declaring 0 must not then demand 1")

    def test_non_integer_expectation_is_refused(self):
        r = self._setup("one", None)
        self.assertEqual(r.returncode, 2, "a malformed expectation must not be ignored")

    def test_mismatch_is_annotated_in_ci(self):
        """The message has to reach someone who cannot read the Actions log."""
        self.write("content/posts/x.md", "clean\n")
        self.write("scripts/leak-gate-expect.txt", "1\n", add=False)
        r = self.run_gate({"GITHUB_ACTIONS": "true"})
        self.assertEqual(r.returncode, 2)
        self.assertIn("::error", r.stdout,
                      "a count mismatch must surface as an annotation, not only stderr")


class DocumentedCountsAreCurrent(unittest.TestCase):
    """Figures quoted in the docs must match what the code actually produces.

    `blog/CLAUDE.md`: "Counts must be derived or checked, never guessed."
    That rule exists because /detections/ once advertised "53 live alert rules
    -- 18 on logs, 18 on metrics", and 18 + 18 is 36. The same drift reached
    this project within a day: docs/leak-gate.md claimed 46 tests and 316
    scanned files after both had moved, and the contract's status table said
    46 while the suite ran 85.

    A number in prose that nothing checks is a number that is already wrong.
    """

    def _docs(self, name):
        return (pathlib.Path(REPO) / "docs" / name).read_text(encoding="utf-8")

    def test_documented_test_count_matches_this_suite(self):
        import unittest as ut
        loader = ut.TestLoader()
        actual = loader.discover(os.path.dirname(os.path.abspath(__file__)),
                                 pattern="test_leak_gate.py").countTestCases()
        for doc in ("leak-gate.md", "blog-agent-handoff.md"):
            text = self._docs(doc)
            for m in re.finditer(r"(\d+) (?:planted-leak )?tests? pass|"
                                 r"(\d+) planted-leak tests", text):
                claimed = int(m.group(1) or m.group(2))
                self.assertEqual(
                    claimed, actual,
                    f"docs/{doc} claims {claimed} tests; the suite has {actual}. "
                    "Update the prose, or stop quoting a number nothing checks.")

    def test_documented_scan_size_matches_a_real_run(self):
        """Shell out to the gate and compare the real scan size to the prose.

        The gate must be given enough site patterns to satisfy R7, which it
        enforces before scanning anything. Without them it exits 2 and prints
        no scan size at all -- which is exactly what happened the first time
        this test ran in CI, where the gitignored pattern file does not exist
        and LEAK_PATTERNS is scoped to the gate step rather than this one.

        That failure was the invariant working. A test that quietly ran the
        gate in an unconfigured state would have been measuring a weaker scan
        than the one the docs describe. So the patterns are supplied here, and
        the required number is read from the same file the gate reads rather
        than hardcoded, so this keeps working when that number changes.
        """
        expect_file = os.path.join(REPO, "scripts", "leak-gate-expect.txt")
        needed = 0
        if os.path.exists(expect_file):
            with open(expect_file, encoding="utf-8") as fh:
                for line in fh:
                    t = line.strip()
                    if t and not t.startswith("#"):
                        needed = int(t)
                        break
        # Inert stand-ins: they match nothing in the corpus, and they trip
        # neither the template-placeholder guard nor the mandated-value canary.
        env = dict(os.environ)
        if needed:
            env["LEAK_PATTERNS"] = "\n".join(
                rf"\bzqxj{i}notarealpatternzqxj\b" for i in range(needed))
        r = subprocess.run([sys.executable, "scripts/leak-gate.py"],
                           cwd=REPO, capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0,
                         f"the gate did not complete a scan:\n{r.stdout}\n{r.stderr}")
        m = re.search(r"(\d+) tracked files", r.stdout)
        self.assertIsNotNone(m, f"could not read the scan size:\n{r.stdout}")
        actual = int(m.group(1))
        text = self._docs("leak-gate.md")
        for dm in re.finditer(r"\*\*(\d+) tracked files", text):
            self.assertEqual(int(dm.group(1)), actual,
                             f"docs claim {dm.group(1)} tracked files; a real run "
                             f"scans {actual}.")

    def test_documented_baseline_size_matches_the_file(self):
        path = os.path.join(REPO, "scripts", "leak-gate-baseline.txt")
        with open(path, encoding="utf-8") as fh:
            entries = sum(1 for l in fh
                          if l.strip() and not l.strip().startswith("#"))
        text = self._docs("leak-gate.md")
        for dm in re.finditer(r"(\d+) baselined", text):
            self.assertEqual(int(dm.group(1)), entries,
                             f"docs claim {dm.group(1)} baselined images; "
                             f"the file pins {entries}.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
