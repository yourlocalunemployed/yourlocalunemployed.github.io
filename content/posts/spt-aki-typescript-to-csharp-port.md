---
title: "Porting a TypeScript Game Mod to C# and Hardening It for Community Release"
date: 2026-06-29T12:20:00+10:00
draft: false
description: "How I ported the BiggerBang SPT mod from TypeScript to C#/.NET for the SPT 4.0 server rewrite, fixed five real bugs in the process, and packaged it for release."
tags: ["game-modding", "csharp", "typescript", "spt-aki", "claude-code"]
pinned: true
---

![Escape from Tarkov](/images/posts/escape-from-tarkov.jpg)

SPT-AKI (Single Player Tarkov) 4.0 rewrote the entire server from JavaScript/TypeScript to C#/.NET. Every mod built for SPT 3.x — loaded as `.ts`/`.js` files with a `package.json` — had to be rebuilt from scratch as a compiled `.dll` against the new C# API.

The mod I ported is BiggerBang, originally written for SPT 3.9 by Thunderbags. It adds a full custom trader (Boris Bangski) with an extensive inventory: custom ammo, weapons, magazines, grenades, injectors, containers, armour, equipment sets, and 13 quests. The original author had gone inactive. I ported it to C# for SPT 4.0.x, verified it against 4.0.13, did a hardening pass on five bugs, and released it to the community.

![SPT-AKI gameplay — the mod running in a live raid](/images/posts/spt-aki-gameplay.jpg)

## What the port actually involved

The SPT 3.x→4.x migration is a complete API break. The mapping:

| SPT 3.x (TypeScript) | SPT 4.x (C#) |
|---|---|
| `mod.ts` + `package.json` | `BiggerBangMod.cs` + `ModMetadata : AbstractModMetadata` |
| `IPreSptLoadMod` / `IPostDBLoadMod` | `IOnLoad` with `[Injectable(PostDBModLoader + 1)]` |
| `container.resolve("ServiceName")` | Constructor dependency injection |
| Readable item IDs (strings) | `ToId` hash mechanism — IDs derived by hashing |

The content carried over 1:1: the trader, the full inventory, all 13 quests, prices, loyalty levels. The work was the structural translation, not redesigning the mod.

I worked on this with Claude Code, with filesystem access to the live server at `C:\SPT-4.0` and my dev workspace. It read the full source, diagnosed log errors, and applied edits. I understood the system well enough to direct the port and verify that the output was correct — that's the important part of how this worked.

## Five hardening fixes

The port itself wasn't the hard part. The interesting work was what I found and fixed once the basic port was running.

**1. Decoupled weapons from the ammo toggle.** The original had a single `AmmoEnabled` flag that controlled both. If you wanted the custom weapons without the custom ammo, there was no way to do it. Added a separate `WeaponsEnabled` config flag.

**2. Fixed registration order for weapons and magazines.** Grenade-launcher magazines need the launcher to already exist when they're registered — they reference it. The original order was wrong. Reordered so weapons load before magazines and linked `msglAuto` to the launcher correctly.

**3. Added a database-existence guard in `CreateItemOffer`.** If an item fails to create, the original code would still try to add it to the trader's stock and flea market, creating dangling offers. Added a guard that skips the offer if the item doesn't exist in the database. This was also the root cause of a stray insurance error that had been in the original.

**4. Extended `ConvertIds` to rewrite `_tpl` fields.** The quest system has a `ConvertIds` routine that rewrites custom item references in quest rewards to their hashed IDs. It was missing `_tpl` fields, so some quest rewards didn't resolve. Fixed that and the Quest05a skip that resulted.

**5. Flipped `UnlockAllItemsLL1` to `false`.** The original had this set to `true`, which bypassed normal loyalty progression and gave players access to everything from the start. Not the right default for a community release.

## The deploy bug that ate an hour

My deploy script backed up the old build into `user/mods` before replacing it. SPT scans `user/mods` for DLLs on startup. So it loaded both the backup and the new build and threw a duplicate-assembly error.

Fix: back up outside the scanned directory.

```bash
# Wrong — SPT scans this folder for DLLs
C:\SPT-4.0\user\mods\_backup\

# Right
C:\SPT-4.0\_mod_backups\
```

Obvious in hindsight. Took a while to figure out why it was loading two copies of everything.

## Bonus: fixed a second mod while I was at it

The SOCOM trader mod had 6 item template IDs in its configuration that don't exist in SPT 4.0.13's database — they reference items added in a newer EFT patch that SPT 4.0.13 doesn't include yet. This caused a flea market cache error on every server startup.

I wrote a cleanup script that removed those 6 entries and their associated barter/loyalty references. Surgical removal, nothing else touched.

## Release

MIT licensed, matching the original. Full attribution to Thunderbags and the contributors (Tuhjay, GhostFenixx, Spartacus) in the README and header. Released via Google Drive as a community port while the original author is inactive — with a note that I'll take it down if they come back and want to manage it themselves.

I generated a `PORT_SUMMARY.md` documenting the rationale, the full API mapping, and each of the five fixes. If someone else needs to maintain it or update it for a future SPT version, the reasoning is all there.

## The actual takeaway

I'm not claiming to be a C# developer. The takeaway is that I understood the SPT mod system end to end well enough to direct an AI through a full language port, verify the output against a live server, and catch and fix five real bugs in the process. The mod runs clean on 4.0.13.
