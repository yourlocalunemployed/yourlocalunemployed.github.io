---
title: "The Lab"
layout: lab
description: "The home lab as one system — the topology, every component, and how it's secured. Each box links to the post where I built it."
ShowToc: false
hideMeta: true
comments: false
---

This is the whole thing in one place: a segmented VMware lab behind a pfSense firewall, one identity provider enforcing MFA everywhere, a full metrics-and-logs monitoring stack, and encrypted off-site backups that have actually been restored. It runs on a single gaming PC and it's built to be operated, not just stood up — so the point of this page isn't the parts list, it's how they fit and what happens when one breaks. Since then it has grown a second layer: it watches itself, with a [SOC](/soc/) over its own logs and a digital twin that checks the network against what should be there, and it runs [AI agents](/ai/) under controls that are enforced in code rather than asked for.
