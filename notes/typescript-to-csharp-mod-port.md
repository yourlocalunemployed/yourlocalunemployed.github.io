# RAW NOTES — post: porting a TypeScript game mod to C#/.NET (and hardening it for release)

(Raw notes. /newpost turns these into a finished post in my voice.
Angle: I directed Claude through this with filesystem access — I understood the
system well enough to guide and verify the port, not that I hand-wrote every line.)

## Context
- SPT-AKI (Single Player Tarkov). SPT 4.0 rewrote the entire SERVER from
  JavaScript/TypeScript to C#/.NET. Every old 3.x mod (loaded as .ts/.js with a
  package.json) now has to be rebuilt as a compiled .dll against the new C# API.
- The mod: "BiggerBang", originally a TypeScript mod for SPT 3.9 by Thunderbags.
  I ported it to C# for SPT 4.0.x (verified against 4.0.13), then did a hardening pass.
- Worked with Claude with filesystem access to the live server (C:\SPT-4.0) and my
  dev workspace — it read the full source, diagnosed log errors, and applied surgical edits.

## The port (TS 3.9 → C# 4.x mapping)
- mod.ts + package.json        → BiggerBangMod.cs + ModMetadata : AbstractModMetadata
- IPreSptLoadMod/IPostDBLoadMod → IOnLoad with [Injectable(PostDBModLoader + 1)]
- container.resolve("X")        → constructor dependency injection
- readable item ids             → the ToId hash mechanism (ids derived by hashing)
- All content carried over 1:1: trader (Boris Bangski), full ammo/weapons/mags/
  grenades/injectors/containers/armour/equipment set, all 13 quests, prices + loyalty.

## The five hardening fixes (the real engineering)
1. Decoupled weapons registration from the ammo toggle — added a dedicated
   WeaponsEnabled config flag so you can run weapons without forcing ammo on.
2. Reordered registration so weapons load BEFORE magazines (grenade-launcher mags
   need the launcher to exist to attach), and linked msglAuto to the launcher.
3. Added a database-existence guard in CreateItemOffer — stops dangling trader/flea
   offers when an item fails to create. This was the root class of bug behind a
   stray insurance error too.
4. Extended the quest ConvertIds routine to rewrite _tpl fields, so custom item
   references in quest rewards convert correctly. Fixed a Quest05a skip.
5. Flipped UnlockAllItemsLL1 to false — normal loyalty progression as the release default.

## The deploy bug worth telling
- My deploy script backed up the old build INTO user/mods — but SPT scans that
  folder for DLLs, so it loaded two copies and threw a duplicate-assembly error.
- Fix: back up OUTSIDE the scanned dir (C:\SPT-4.0\_mod_backups). Obvious in
  hindsight, exactly the kind of thing that eats an hour.

## Bonus: fixed a second mod along the way
- SOCOM trader mod referenced 6 item template IDs that don't exist in 4.0.13's DB
  (newer EFT-patch items) — flea market cache error on every startup. Wrote a
  cleanup script to surgically remove those entries + their barter/loyalty refs.

## Release engineering
- MIT licensed (per original). Full attribution to Thunderbags + contributors
  (Tuhjay, GhostFenixx, Spartacus). Shared via Google Drive as a community port
  while the original author is inactive; take it down on request if they return.
- Generated a PORT_SUMMARY.md documenting the rationale, API mapping, and every fix.

## Closing
- The takeaway isn't "I'm a C# dev" — it's that I understood the system end to end
  well enough to drive an AI through a full language port and verify it actually ran clean.
