---
title: "Porting a TypeScript Game Mod to C# and Hardening It for Community Release"
date: 2026-06-29T12:20:00+10:00
draft: false
description: "How I ported the BiggerBang SPT mod from TypeScript to C#/.NET for the SPT 4.0 server rewrite, fixed five real bugs in the process, and packaged it for release."
tags: ["game-modding", "csharp", "typescript", "spt-aki", "claude-code"]
pinned: true
cover:
  image: "/images/posts/escape-from-tarkov.jpg"
  alt: "Escape from Tarkov"
  hiddenInSingle: true
---

![Escape from Tarkov](/images/posts/escape-from-tarkov.jpg)

SPT-AKI (Single Player Tarkov) 4.0 rewrote the entire server from JavaScript/TypeScript to C#/.NET. Every SPT 3.x mod — loaded as `.ts`/`.js` files with a `package.json` — had to be rebuilt as a compiled `.dll` against the new C# API.

The mod I ported is BiggerBang, written for SPT 3.9 by Thunderbags, whose author had gone inactive. It adds a full custom trader (Boris Bangski) with an extensive inventory — ammo, weapons, magazines, grenades, injectors, containers, armour, equipment sets — and 13 quests. I ported it to C# for SPT 4.0.x, verified it against 4.0.13, fixed five bugs found along the way, and released it to the community.

![SPT-AKI gameplay — the mod running in a live raid](/images/posts/spt-aki-gameplay.jpg)

## What the port involved

The 3.x→4.x migration is a complete API break:

| SPT 3.x (TypeScript) | SPT 4.x (C#) |
|---|---|
| `mod.ts` + `package.json` | `BiggerBangMod.cs` + `ModMetadata : AbstractModMetadata` |
| `IPreSptLoadMod` / `IPostDBLoadMod` | `IOnLoad` with `[Injectable(PostDBModLoader + 1)]` |
| `container.resolve("ServiceName")` | Constructor dependency injection |
| Readable item IDs (strings) | `ToId` hash mechanism — IDs derived by hashing |

The content carried over 1:1 — trader, inventory, all 13 quests, prices, loyalty levels. The work was structural translation, not redesign.

I worked with Claude Code, giving it filesystem access to the live server and my dev workspace. It read the source, diagnosed log errors, and applied edits; I directed the port and verified the output. That division of labour is the important part of how this worked.

## Five hardening fixes

The port itself wasn't the hard part — the valuable work was what surfaced once it was running:

1. **Decoupled weapons from the ammo toggle.** A single `AmmoEnabled` flag controlled both; added a separate `WeaponsEnabled` config flag.
2. **Fixed registration order.** Grenade-launcher magazines reference the launcher, so it must exist first. Reordered weapon/magazine loading and linked `msglAuto` correctly.
3. **Added a database-existence guard in `CreateItemOffer`.** Failed items were still being added to trader stock and the flea market, creating dangling offers — also the root cause of a stray insurance error in the original.
4. **Extended `ConvertIds` to rewrite `_tpl` fields.** The quest-reward ID rewriter missed them, so some rewards never resolved — this also fixed the Quest05a skip.
5. **Flipped `UnlockAllItemsLL1` to `false`.** The original bypassed loyalty progression entirely — the wrong default for a community release.

## A deploy bug worth recording

My deploy script backed up the old build into `user/mods`, which SPT scans for DLLs on startup — so it loaded both copies and threw a duplicate-assembly error.

```bash
# Wrong — SPT scans this folder for DLLs
C:\SPT-4.0\user\mods\_backup\

# Right
C:\SPT-4.0\_mod_backups\
```

Back up outside the scanned directory.

## A second mod fixed along the way

The SOCOM trader mod shipped six item template IDs that don't exist in SPT 4.0.13's database (they belong to a newer EFT patch), causing a flea-market cache error on every startup. A cleanup script removed those six entries and their barter/loyalty references — nothing else touched.

## Release

MIT licensed, matching the original, with full attribution to Thunderbags and contributors (Tuhjay, GhostFenixx, Spartacus). Released as a community port while the original author is inactive, with a note that I'll hand it back if they return. A `PORT_SUMMARY.md` documents the rationale, the full API mapping, and each fix, so future maintainers have the reasoning.

## Takeaway

I'm not claiming to be a C# developer. The takeaway is that I understood the SPT mod system end to end well enough to direct an AI through a full language port, verify the result against a live server, and catch five real bugs in the process. The mod runs clean on 4.0.13.
