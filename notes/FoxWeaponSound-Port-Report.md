# Project Report — Porting FoxWeaponSoundMod to SPT 4.0.13

**Date:** 3 July 2026
**Project type:** Legacy game-mod modernisation (SPT-AKI / Single Player Tarkov)
**Final status:** Complete — mod builds cleanly, loads on SPT 4.0.13 with no errors, 76 weapons patched

---

## 1. Purpose

FoxWeaponSoundMod v2.1.3 (by Fox) is a weapon sound-replacement mod written for
SPT-AKI 2.3.0 (2022). It replaces the firing audio of ~80 weapons by re-pointing
each weapon's prefab at a custom Unity container bundle that references the
author's replacement audio banks.

SPT 4.0 rewrote the mod platform entirely: the server moved from Node.js
(JavaScript mods) to .NET 9 (C# DLL mods). The legacy mod could no longer load.
The goal was to port it to SPT 4.0.13 while preserving its core purpose —
the original audio bundles untouched, only the loader logic modernised.

## 2. Source Material and Target

| | Legacy | Target |
|---|---|---|
| SPT version | 2.3.0 | 4.0.13 |
| Language | JavaScript (Node) | C# (.NET 9) |
| Metadata | `package.json` | `ModMetadata` record (`AbstractModMetadata`) |
| Entry point | `ModLoader.onLoad` hook | `[Injectable(TypePriority = OnLoadOrder.PostDBModLoader + 1)]` class implementing `IOnLoad` |
| DB access | global `DatabaseServer.tables` | injected `DatabaseService.GetItems()` |
| Bundles | `bundles.json` + `bundles/` | same format; served when metadata sets `IsBundleMod = true` |

## 3. Process

1. **Extraction** — unpacked the original `.rar` archive (see Troubleshooting #1).
2. **Code review of the legacy mod** — one JS file assigning 82 weapon-ID →
   bundle-path pairs. Review uncovered five defects (Troubleshooting #2).
3. **API study** — since the mod platform changed completely, the new API was
   derived from three sources: the XML documentation shipped with the server,
   decompilation of `SPTarkov.Server.Core.dll` (ILSpy), and two working
   reference mods already ported to 4.0 (one of which does exactly the same
   prefab-path replacement technique).
4. **Validation before porting** — a script cross-checked every weapon ID in
   the legacy mod against the SPT 4.0.13 item database, every referenced bundle
   file against the shipped archive, and the bundle manifest against the files
   on disk. All 82 original IDs still exist in 4.0.13.
5. **Rewrite** — the 450-line copy-pasted JS was collapsed into a single C#
   dictionary (weapon ID → bundle path, generated programmatically from the
   original source to avoid transcription errors) applied in one loop at
   post-database load time. Metadata record replaces `package.json`.
6. **Build system** — `.csproj` targeting `net9.0`, referencing the SPT server
   DLLs from the local install via an overridable `SptPath` property
   (offline-safe, version-exact). Bundle assets copy to the output folder, so
   `bin/Release/` is the complete installable mod.
7. **Verification** — the mod was installed and the actual SPT server booted
   with the mod isolated; the log confirmed all weapons patched.
8. **Windows deployment** — the project was rebuilt on the user's Windows
   machine with PowerShell (`dotnet build -c Release -p:SptPath=<SPT folder>`)
   and installed by copying `bin\Release\*` into `user\mods\FoxWeaponSound\`.
9. **Post-deployment conflict resolution** — a bundle-key collision with
   another installed mod surfaced on the full mod set and was diagnosed and
   resolved (Troubleshooting #6).

## 4. Bugs Found in the Original Mod (fixed during the port)

1. **AKMN** — the script used the AKMSN's item ID for the AKMN entry, which the
   later AKMSN entry then overwrote. The real AKMN never received its sound.
2. **AKS-74** — pointed at the AK-101 (5.56) bundle instead of its own
   AKS-74 bundle (copy-paste error).
3. **TT Gold** — given the plain TT bundle although a dedicated gold container
   shipped in the mod.
4. **AK-104** — container bundle shipped but never wired up.
5. **Saiga-9** — container bundle shipped but never wired up.
6. (Minor) one duplicated entry in the bundle manifest.

## 5. Errors Encountered and Troubleshooting

**#1 — Archive would not extract.** 7-Zip reported `Unsupported Method` on a
RAR5 archive created by a newer WinRAR, and silently left 0-byte files — a
partial extraction that initially looked successful. *Diagnosis:* file sizes
checked after extraction; text files were empty. *Fix:* official static
`unrar` binary; extraction verified with `All OK` and non-zero file sizes.

**#2 — No documentation for the new mod API.** Only some members appear in the
shipped XML docs. *Fix:* decompiled the server core with `ilspycmd` (an older
tool version pinned to run on the available SDK, with runtime roll-forward)
and studied two working 4.0 mods to confirm the metadata record, load-order
attribute, and `Prefab.Path` model shape.

**#3 — SDK mismatch.** The server targets .NET 9; only the .NET 8 SDK was
installed locally. *Fix:* self-contained .NET 9 SDK installed to a user
folder; build produced 0 warnings / 0 errors.

**#4 — PowerShell build failures on Windows.**
`MSB1009: Project file does not exist` — caused by malformed arguments
(`Release:SPTPath=...` instead of `-c Release -p:SptPath=...`).
`MSB1003: Specify a project or solution file` — caused by a space after the
`=`, which split the property into two arguments and made MSBuild treat the
path as the project to build. *Fix:* corrected syntax; the property and path
must be one unbroken token: `-p:SptPath=C:\<SPT folder>`.

**#5 — Server crashed on first full test run (Linux).** Stack trace showed the
crash came from an unrelated third-party mod that reads a file with a
hard-coded Windows backslash path, which fails on Linux. *Diagnosis:* read the
stack trace to the faulting mod rather than assuming the new mod was at fault.
*Fix/workaround:* isolation testing — temporarily moving all other mods aside;
the ported mod then loaded cleanly (`patched 84/84`).

**#6 — `Unable to add bundle` × 8 after deployment.** Eight weapon container
bundles failed to register on the full mod set. *Diagnosis path:*
decompilation showed the message fires when a bundle key is already registered
(duplicate-key rejection); a manifest comparison across all installed mods
found exactly 8 overlapping keys with a content-backport mod that ships
remastered versions of the same weapons; a live query of the server's bundle
endpoint proved which mod owned the contested keys (first to load wins).
*Resolution:* user chose to yield those 8 weapons to the content-backport mod.
The 8 entries were removed from this mod's manifest and mapping; a dependency
check confirmed nothing left referenced them. Result: no errors, remastered
weapons preserved, Fox sounds on the remaining 76 weapons. Because the
removed entries wrote vanilla-identical paths anyway, the deployed fix needed
only a one-file (`bundles.json`) replacement — no rebuild.

**#7 — Disk exhaustion during isolation testing.** Copying a multi-GB mod for
an isolation run filled the disk. *Fix:* recovered immediately and switched to
move-based isolation (zero disk cost), a safer pattern for large mod sets.

## 6. Final Outcome

- **FoxWeaponSoundMod 3.0.0** running on SPT 4.0.13:
  `[FoxWeaponSoundMod] v3.0.0 loaded – patched 76/76 weapon sound prefabs`,
  no bundle errors alongside the full 42-mod installation.
- Five legacy bugs fixed; three weapons gained sounds they never had in v2.1.3.
- Reproducible build: one `dotnet build` produces the complete installable mod.
- Documentation: project README covers the port, bug fixes, compatibility
  decision, and build instructions; a PowerShell command sheet covers Windows
  deployment and troubleshooting.

## 7. Lessons Learned

- Verify extractions: some tools fail partially and leave empty files.
- When docs are thin, decompiled sources plus a working reference mod are the
  fastest reliable path to a new API.
- Validate data (IDs, file paths, manifests) with scripts before rewriting code.
- Read crash stack traces to the faulting module before suspecting new code.
- Isolation testing quickly separates "my mod is broken" from "another mod is
  broken" — and use moves, not copies, for large assets.
- Bundle keys are global across mods: two mods replacing the same vanilla
  asset conflict silently except for one log line, with load order deciding
  the winner. Explicitly deciding ownership beats relying on load order.
