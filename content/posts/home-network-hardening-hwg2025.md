---
title: "Hardening and Segmenting My Home Network on an Arcadyan HWG2025"
date: 2026-06-29T12:10:00+10:00
draft: false
description: "How I hardened and segmented my home network on an ISP-provided Wi-Fi 7 router — and the DNS gotcha that makes doing it properly harder than it should be."
tags: ["networking", "security", "debian", "home-lab", "dns"]
---

![Arcadyan HWG2025 (iiNet Wi-Fi Max) — the router this whole post is about](/images/posts/hwg2025-router.jpg)

This is a small home network. One router, a handful of devices. The point wasn't complexity — it was doing it right, the same way you'd approach a small office or a real lab environment. Treating it as a learning environment for Network+ and Security+ is a lot more useful than treating it as a home Wi-Fi setup.

Router is an Arcadyan HWG2025 — the NBN-issued unit, Wi-Fi 7 with MLO. About 500Mb down. The ISP router doesn't give you a lot of room to move, but there's more than enough to do this properly.

## Baseline hardening

First things first, before touching segmentation:

- Changed the default admin credentials. The default on most ISP routers is `admin`/`admin` or printed on a sticker. That's the obvious first hole.
- WPA3 with AES everywhere. WPA2 fallback only for a device that genuinely can't do WPA3 — not as a default. TKIP is off.
- Disabled WPS. It's a known weak point and there's no upside to leaving it on.
- Disabled remote management. There's no reason for the router's admin interface to be reachable from outside.
- Updated firmware and rebooted before making any further changes.
- Set DHCP reservations for the devices I care about so their IPs are predictable.

None of this is advanced. It's just doing the basics before anything else.

## Network segmentation

Two zones:

| Zone | Subnet | Notes |
|---|---|---|
| Main / trusted | 192.168.1.0/24 | My machines |
| Guest | 192.168.2.0/24 | Visitors, untrusted devices |

Guest has client isolation on — devices on the guest network can't see or reach anything on the main network, and can't see each other. Anything I don't fully trust (visitors, eventually IoT devices) never touches the same broadcast domain as my actual machines.

The longer-term plan is an IoT segment as a third zone, but two is the right starting point.

## The DNS gotcha

This is the part that's more annoying than it should be.

The HWG2025 has ISP-locked DNS fields at the router level. You can't just set the upstream DNS servers to Cloudflare (1.1.1.1) or Quad9 (9.9.9.9) from the admin interface — the fields are greyed out or locked to the ISP's resolvers.

The workarounds I weighed:

1. **Per-device OS-level DNS** — set 1.1.1.1 and 9.9.9.9 on each machine manually. Works, but it's per-device and doesn't help for things you can't configure.
2. **Pi-hole as local DNS** — run a Pi-hole on a device on the network, point all DHCP clients at it, and have Pi-hole upstream to Cloudflare/Quad9. Gets you network-wide resolver control plus ad/tracker blocking as a bonus.

I'm leaning Pi-hole for the long term. It's the right lab answer and it'll get its own post when I set it up. For now, per-device DNS on the machines I control.

## Band steering and SSID choices

The HWG2025 supports Wi-Fi 7 with MLO (Multi-Link Operation), which means 2.4GHz and 5GHz can be handled automatically without manually splitting them into separate SSIDs.

I left them merged under one SSID with Smart Connect / band steering on. With a modern router doing MLO there's no reason to manage this by hand. The one exception: when setting up stubborn IoT gear that can only connect to 2.4GHz, I temporarily split them, got the device connected, then merged back.

On SSID hiding: I didn't do it. It's security theatre. Hidden networks are still trivially detectable with any wireless scanner — they just broadcast with an empty SSID. Worse, devices looking for a hidden network broadcast the network name when they're away from home, so you're advertising your SSID name on public Wi-Fi. Real security is WPA3, guest isolation, strong admin creds, and WPS off. Not hiding the name.

## Where this goes next

The discipline here is more important than the scale. Separating trusted from untrusted traffic, turning off things that shouldn't be on, using strong auth — these decisions don't change between a home network and a production environment. The reasoning is the same.

Next step is the Pi-hole setup for proper DNS control. After that, IoT segmentation as a third zone when I have devices that need it.
