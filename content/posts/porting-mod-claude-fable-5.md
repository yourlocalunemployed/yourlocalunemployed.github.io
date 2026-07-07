---
title: "Porting a Mod Through Claude Fable 5"
date: 2026-07-03T21:13:00+10:00
draft: false
description: "Running a full legacy mod port through Claude Fable 5: a 2022 JavaScript weapon-sound mod rebuilt as a C#/.NET 9 DLL for SPT 4.0.13 — five bugs found in the original, seven problems hit and fixed along the way."
tags: ["game-modding", "spt-aki", "csharp", "claude-code", "dotnet"]
series: ["SPT Mods"]
seriesTitle: "FoxWeaponSound (via Fable 5)"
cover:
  image: "/images/posts/spt-aki-gameplay.jpg"
  alt: "SPT-AKI gameplay"
  hiddenInSingle: true
---

![Escape from Tarkov — the single-player mod scene this port lives in](/images/posts/spt-aki-gameplay.jpg)

This is my second SPT mod port — the first was [BiggerBang](/posts/spt-aki-typescript-to-csharp-port/), a full trader mod. This one is smaller in scope, but I ran the entire process through Claude Fable 5 in Claude Code: extraction, code review, the rewrite, and the debugging. My role was direction and judgement calls; the model did the implementation. The most interesting part of this post is what it found.

The mod is FoxWeaponSoundMod v2.1.3 (by Fox), a weapon sound-replacement mod written for SPT-AKI 2.3.0 in 2022. It replaces the firing audio of ~80 weapons by re-pointing each weapon's prefab at a custom Unity container bundle referencing replacement audio banks. SPT 4.0 moved the server from Node.js to .NET 9, so JavaScript mods stopped loading entirely. The goal: port the loader logic to 4.0.13 while leaving the original audio bundles untouched.

## Legacy vs target

| | Legacy | Target |
|---|---|---|
| SPT version | 2.3.0 | 4.0.13 |
| Language | JavaScript (Node) | C# (.NET 9) |
| Metadata | `package.json` | `ModMetadata` record (`AbstractModMetadata`) |
| Entry point | `ModLoader.onLoad` hook | `[Injectable(TypePriority = OnLoadOrder.PostDBModLoader + 1)]` class implementing `IOnLoad` |
| DB access | global `DatabaseServer.tables` | injected `DatabaseService.GetItems()` |
| Bundles | `bundles.json` + `bundles/` | same format; served when metadata sets `IsBundleMod = true` |

The new API is barely documented, so it was derived from three sources: the XML docs shipped with the server, decompiling `SPTarkov.Server.Core.dll` with ILSpy, and two working reference mods already on 4.0 — one of which uses the same prefab-path replacement technique.

Before rewriting anything, a script cross-checked every weapon ID in the legacy mod against the SPT 4.0.13 item database, every referenced bundle file against the shipped archive, and the bundle manifest against the files on disk. All 82 original IDs still exist in 4.0.13. Validating the data before porting the code is cheap insurance.

The rewrite collapsed 450 lines of copy-pasted JavaScript into a single C# dictionary (weapon ID → bundle path, generated programmatically from the original source to avoid transcription errors), applied in one loop at post-database load. The `.csproj` targets `net9.0`, references the server DLLs via an overridable `SptPath` property, and copies bundle assets to the output folder — `bin/Release/` is the complete installable mod.

## Five bugs the original shipped with

Code review surfaced defects present since 2022:

1. **AKMN** — used the AKMSN's item ID, which the later AKMSN entry overwrote; the AKMN never received its sound.
2. **AKS-74** — pointed at the AK-101 (5.56) bundle instead of its own (copy-paste error).
3. **TT Gold** — assigned the plain TT bundle despite a dedicated gold container shipping in the mod.
4. **AK-104** — container bundle shipped but never wired up.
5. **Saiga-9** — shipped but never wired up.

Three weapons gained sounds they never had in v2.1.3, four years after release.

## What broke along the way

- **The archive wouldn't extract.** 7-Zip reported `Unsupported Method` on a RAR5 archive and silently left 0-byte files, so the extraction looked successful. Caught by checking file sizes; the official static `unrar` binary extracted it correctly (`All OK`).
- **SDK mismatch.** The server targets .NET 9; only the .NET 8 SDK was installed. A self-contained .NET 9 SDK in a user folder produced a build with 0 warnings, 0 errors.
- **PowerShell build failures on Windows.** Two argument mistakes before this worked:

  ```powershell
  dotnet build -c Release -p:SptPath=C:\<SPT folder>
  ```

  `MSB1009: Project file does not exist` came from malformed arguments (`Release:SPTPath=...` instead of `-c Release -p:SptPath=...`), and `MSB1003: Specify a project or solution file` from a space after the `=`, which splits the property into two arguments. The property and path must be one unbroken token.
- **Server crash on the first full test.** The stack trace pointed at an unrelated third-party mod reading a file with a hard-coded Windows backslash path, which fails on Linux. Isolation testing (moving other mods aside) confirmed the ported mod loaded cleanly on its own. Read the trace to the faulting module before suspecting new code.
- **`Unable to add bundle` × 8 after deployment.** On the full 42-mod install, eight container bundles failed to register. Decompilation showed the message fires on duplicate-key rejection — bundle keys are global across mods, and a content-backport mod shipping remastered versions of the same weapons owned eight overlapping keys, with load order silently deciding the winner. I chose to yield those weapons to the backport mod; since the removed entries wrote vanilla-identical paths, the deployed fix was a one-file `bundles.json` replacement with no rebuild.
- **Disk exhaustion.** Copying a multi-GB mod set aside for isolation testing filled the disk. Move-based isolation costs zero disk and achieves the same thing — the better pattern for large mod sets.

## Outcome

```text
[FoxWeaponSoundMod] v3.0.0 loaded – patched 76/76 weapon sound prefabs
```

FoxWeaponSoundMod 3.0.0 on SPT 4.0.13, no bundle errors alongside the full 42-mod installation. Five legacy bugs fixed, one `dotnet build` produces the complete installable mod, and the README documents the port, fixes, and compatibility decisions.

## What I'm keeping from this one

- Verify extractions — some tools fail partially and leave empty files that look fine.
- When documentation is thin, decompiled sources plus a working reference mod are the fastest reliable path into a new API.
- Validate data (IDs, paths, manifests) with scripts before rewriting code.
- Bundle keys are global across mods; decide asset ownership explicitly rather than trusting load order.

Compared to the BiggerBang port, the notable difference was how little I typed. The judgement calls — yielding contested weapons, accepting the isolation-test result, shipping without a rebuild — were mine. Everything between them was the model applying the same troubleshooting discipline I'd use by hand, faster.
