# RAW NOTES — post: hardening and segmenting my home network on an Arcadyan HWG2025

(Raw notes. /newpost turns these into a finished post in my voice.
This is the strongest piece for the networking/security angle — lead with it.)

## Context
- Router: Arcadyan HWG2025, NBN ~500Mb, Wi-Fi 7 (MLO capable).
- Goal: do it properly even though I don't have many devices — treat the home
  network like a small lab. Separate guest from main, fix DNS, follow best practices.
- Worked through this with Claude (chat app) — used it to research what this
  specific router can/can't do, draw the segmentation diagram, and generate
  passwords to a strict spec.

## Security hardening (the baseline)
- Changed default admin credentials first. (default admin/admin is the obvious hole)
- WPA3 with AES (WPA2 fallback only if a device can't do WPA3). Not TKIP.
- Disabled WPS — it's a known weak point.
- Disabled remote management.
- Firmware updated, then rebooted.
- DHCP reservations for the devices I care about.

## Segmentation
- Two zones:
  - Main / trusted: 192.168.1.0/24
  - Guest: 192.168.2.0/24, client isolation ON (guests can't see main network)
- Point of separation: anything I don't fully trust (visitors, later IoT) never
  touches the network my real machines are on.
- TODO: drop in the segmentation diagram here (have the SVG version).

## The DNS gotcha (good story beat)
- HWG2025 has ISP-LOCKED DNS fields — can't just set Cloudflare/Quad9 at the router.
- Workarounds I weighed:
  1. Use the provider picker list if it offers alternates.
  2. Set DNS per-device at the OS level (1.1.1.1 / 9.9.9.9).
  3. Run a Pi-hole as local DNS — also gets network-wide ad/tracker blocking.
- Leaning Pi-hole long term — it's the most "lab" answer and a future post on its own.

## Two config calls worth explaining
- 2.4 vs 5GHz: merged into ONE SSID via band steering / Smart Connect. With Wi-Fi 7
  MLO there's no reason to hand-split them. Exception: temporarily split to set up
  stubborn IoT gear, then merge back.
- SSID hiding: didn't do it. It's security theatre — hidden nets are still findable
  with a scanner, add friction, and make your devices broadcast the name when
  they're away from home looking for it. Real security is WPA3 + guest isolation +
  strong admin creds + WPS off, not hiding the name.

## Closing
- Small network, but the discipline is the point — this is the same thinking that
  scales to a real environment, and it's the Network+/Security+ direction I'm building toward.
- The "I used AI to research my exact router model and design this" angle is honest
  and is part of how I work now.
