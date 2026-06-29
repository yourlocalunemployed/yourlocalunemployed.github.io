# RAW NOTES — post: building a GLSL shader pack with a full deferred rendering pipeline

(Raw notes. /newpost turns these into a finished post in my voice.
NOTE TO SELF: this is the most code-heavy project and the detail here is from
memory — CONFIRM/expand the specifics before publishing. Marked [CHECK] below.)

## Context
- "UltraRealism" — a custom GLSL shader pack for Minecraft Java Edition.
- Forge 1.20.1, running through Iris Shaders. [CHECK exact versions]
- Goal: a from-scratch realistic rendering pipeline, not a tweak of an existing pack.
- Built iteratively with Claude — heavy back-and-forth debugging of shader compile
  errors and driver quirks.

## What the pipeline does
- Full DEFERRED rendering pipeline (G-buffer pass, then lighting pass).
- PBR lighting (physically based — albedo/normal/roughness/metalness handling).
- Screen-space path tracing for global illumination. [CHECK how far this went]
- TAA (temporal anti-aliasing).
- A post-processing stack on top. [CHECK which effects — tonemap, bloom, etc.]

## The debugging story (the real content)
- Two classes of problem fought the whole way:
  1. Iris Shaders compatibility issues — [CHECK specific symptoms].
  2. NVIDIA GLSL driver errors on the RTX 4090.
- Fixes that actually worked:
  - Downgraded the GLSL #version to get past compatibility breaks.
  - Inlined #include files instead of relying on the include mechanism.
  - Replaced uint-based hashing with FLOAT-ONLY hashing — the uint path tripped
    the NVIDIA driver. This was the key unlock. [CHECK exact context]

## Why it's a good portfolio piece
- Deferred rendering + PBR + screen-space GI is genuinely advanced graphics work.
- The interesting part for a write-up is the debugging: driver-level GLSL quirks
  are poorly documented, and the fixes (version downgrade, inlining, float hashing)
  are the kind of hard-won detail other people searching the same errors will want.

## Closing / honesty
- This stretched well past my comfort zone in shader code — the value was using
  Claude to move fast through compile/debug loops while I steered the architecture.
- TODO before publishing: fill the [CHECK] gaps with the real specifics so the
  post is accurate. Don't ship the guesses.
