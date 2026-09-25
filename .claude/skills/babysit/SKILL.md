---
name: babysit
description: Pointer to the steward skill, which holds this repo's PR conventions. Exists so a harness that looks for babysit/ rather than steward/ still finds the right guidance.
---

# babysit — see `steward`

This repo's PR conventions live in **`.claude/skills/steward/SKILL.md`**. Read
that file instead; everything that applies to babysitting a PR here is in it.

Why this file is a pointer and not a second copy: a harness that reads both
prefers `steward/`, so a full rule set here would almost never be read — and
two copies of the same conventions drift apart silently, which is exactly the
failure mode `CLAUDE.md` exists to prevent. One source of truth, reachable
under either name.

The posture rules still hold whichever file you arrive through: never punt on a
red or conflicted PR, address every unresolved thread, and a failing build is
never dismissed as a flake — this repo's only check is the Hugo build, and it
fails deterministically.
