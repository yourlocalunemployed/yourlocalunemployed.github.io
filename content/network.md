---
title: "Network Design"
layout: network
description: "The lab's network from the design side — the addressing plan, the three trust zones, the firewall policy matrix, and the rules that don't change. Each row links to the post where it was built."
ShowToc: false
hideMeta: true
comments: false
---

The whole security model starts at the network. One firewall everything routes through, three trust zones that can't reach each other, and exactly one authenticated way in from outside. This page is the *design* — the addressing plan, the trust boundaries, and the actual firewall policy — not the parts list (that's [the lab overview](/lab/)). Home-LAN and public-IP specifics are deliberately left off; what's here is the lab-internal design the posts already walk through, box by box.
