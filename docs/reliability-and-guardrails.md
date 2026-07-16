# Reliability & Guardrails — making the Claude Code workflow trustworthy

**Status:** plan (not yet implemented). Owner: Bill. Last updated: 2026-07-16.

**Goal.** Make the AI-assisted workflow on this project *reliable, accurate, and
aligned with official developer documentation* — so a confident-sounding wrong
answer, an invented command, or a silently-broken build can't reach `main`.

**Governing principle.** Don't trust a language model to police itself. Move as
much validation as possible **out of the model and into code** (hooks, schemas,
builds, tests). Use the model to *judge* only what code can't — and even then,
use more than one judge. This is defence-in-depth, the same way the lab is: the
model is a useful device on the network, not the firewall.

Everything below is grounded in official Anthropic / Claude Code docs, linked at
the bottom.

---

## 1. Why models are unreliable (name the failure modes)

- **Hallucination / confabulation** — fluent text that isn't true: an invented
  `nft` flag, a version that doesn't exist, a config key that was never in the
  notes. Worst on facts *not present in the provided context*.
- **Output-format drift** — the shape is wrong: missing front-matter keys, an
  untagged code block, malformed JSON from a tool call.
- **Behavioural unreliability** — the model does something adjacent-but-unasked
  (a "helpful" refactor, a `git push` you didn't request), or stops early
  claiming work is done that isn't.

These need *different* controls. One prompt won't fix all three.

---

## 2. The reliability stack (cheapest / most deterministic first)

Think of it as layers. Lower layers are deterministic and can't be argued out of
by a confident model; upper layers are probabilistic and catch what code can't.

```
Layer 4  JURIES  (LLM-as-judge, N judges, quorum)   ← catches voice / accuracy / hallucination
Layer 3  GROUNDING (quotes, "I don't know", notes-only) ← shrinks hallucination at generation
Layer 2  SCHEMAS  (structured outputs / strict tools)  ← output can't be malformed
Layer 1  HOOKS    (deterministic gates in the harness) ← the floor; enforced by code, not the model
```

### Layer 1 — Deterministic gates: **Claude Code hooks**

Hooks are shell/HTTP/MCP commands the *harness* runs at lifecycle points
(`PreToolUse`, `PostToolUse`, `Stop`, `SessionStart`, …), configured in
`.claude/settings.json`. **Exit code 2 blocks the action**; exit 0 with JSON on
stdout gives fine-grained control (`permissionDecision: "deny"`,
`decision: "block"`, `additionalContext`, `systemMessage`). This is the single
highest-ROI move for reliability, because a hook is code — it can't be
talked out of a decision.

Concrete hooks for *this* repo:

| Event / matcher | Hook does | Why |
|---|---|---|
| `PostToolUse` on `Edit\|Write` to `content/**/*.md` | Validate YAML front matter has `title/date/draft/description/tags`; fail → feedback to Claude | Catches format drift the moment a post is written |
| `Stop` | Run `hugo --gc --minify`; if it errors, **block the stop** (`decision: "block"`) with the build output | The agent literally cannot "finish" on a broken site |
| `PreToolUse` on `Bash` with `if: "Bash(rm *)"` / force-push / `curl … \| sh` | `permissionDecision: "deny"` | Behavioural guard — destructive/outward actions never fire silently |
| `PostToolUse` on `Edit` to `layouts/_partials/*.html` | If an inline `<script>` changed, emit `additionalContext` reminding to re-run `csp-hashes.sh` | Encodes the CLAUDE.md CSP rule so it can't be forgotten |
| `SessionStart` | Inject `blog-author-context.md` + the front-matter spec as `additionalContext` | Grounding is present *before* the first draft, every session |

Scripts live in `.claude/hooks/`; wire them via the `update-config` skill (it
edits `settings.json`). Keep hook scripts fast and dependency-light (`jq` + the
Hugo binary we already have).

### Layer 2 — Schema-constrained output

When a step must emit **structured data** (front matter, a changelog entry, a
"which posts changed" list), don't free-text it — constrain it. For anything
that calls the Claude API directly (the changelog generator, an Obsidian/vault
tool, the MCP hub), use:

- **Structured outputs** — `output_config: {format: {type: "json_schema", schema: …}}`
  guarantees the response validates against your schema (or you get
  `stop_reason: "refusal"`/`max_tokens`, which you handle explicitly).
- **Strict tool use** — `strict: true` on a tool definition (with
  `additionalProperties: false` + `required`) guarantees `tool_use.input`
  matches the schema exactly.

The blog's front-matter contract *is* a JSON schema — write it once, reuse it in
both the hook validator (Layer 1) and any generator (Layer 2).

### Layer 3 — Grounding (shrink hallucination at the source)

Anthropic's official "Reduce hallucinations" guidance, applied to posts:

1. **Allow "I don't know."** CLAUDE.md already forbids inventing project
   details — make the *permission to abstain* explicit in the prompt: *"If a
   command, version, or config isn't in the notes or author context, say so and
   ask — do not fill it in."*
2. **Quote-first grounding.** Before drafting, extract the exact commands,
   configs, and error messages from the raw notes **verbatim**; write the post
   *from those quotes*, not from memory.
3. **Verify-each-claim (citations).** After drafting, walk every technical claim
   and point it at a line in the notes. Anything with no source gets cut or
   flagged — don't ship an unverifiable claim.
4. **External-knowledge restriction.** For project facts, use *only* the notes +
   `blog-author-context.md`, not the model's general knowledge.

These are prompt-level and belong in the `/newpost` command and CLAUDE.md.

### Layer 4 — Juries (LLM-as-judge, done right)

Where code can't judge — *is the voice right? is this accurate? did it invent
anything?* — use an LLM judge. A **single** judge is noisy and biased, so use a
**jury**: several independent judges score the same output against a fixed
rubric, and you aggregate (majority vote, or mean with a pass threshold). This is
the same idea as `/code-review ultra` (a multi-agent cloud review = a jury) and
as *best-of-N / self-consistency* (run the check N times, disagreement =
red flag).

For this blog, a publish-gate jury scores each drafted post against a rubric
derived from `blog-author-context.md`:

- **Voice** — first person, plain, no marketing fluff, honest about what failed.
- **Substance** — real commands/configs/errors kept intact, code blocks tagged.
- **Accuracy** — every command/version/config traces to the source notes
  (the hallucination check).
- **Scope** — no invented project details.

Rules that make a jury trustworthy: judges run in **independent contexts**
(no shared thread), score against a **written rubric** (not vibes), return a
**structured verdict** (Layer 2), and you require a **quorum** to pass. On a
fail, feed the judges' reasons back and repair — don't publish.

---

## 3. The loop it all composes into

```
draft (grounded, notes-only)
  → Layer 1 hooks fire on every write/build   (deterministic, always)
  → Layer 2 schema validates structured bits  (deterministic, where applicable)
  → Layer 4 jury scores the finished post      (probabilistic, at the publish gate)
  → any failure feeds back as additionalContext/block → repair, don't ship
  → Stop hook builds the site; broken build = can't finish
```

Deterministic layers run cheaply on every action; the expensive jury runs once,
at the gate. Nothing reaches `main` that a hook, a schema, or a quorum rejected.

---

## 4. Implementation plan (phased)

**Phase 1 — deterministic floor (highest ROI).** Add `.claude/settings.json`
hooks + `.claude/hooks/` scripts: front-matter validator (`PostToolUse`),
build-gate (`Stop`), dangerous-Bash guard (`PreToolUse`), CSP-hash reminder,
`SessionStart` context loader. Do this first — it's pure code, no model trust.

**Phase 2 — grounding.** Fold the four reduce-hallucination patterns into the
`/newpost` command and CLAUDE.md (I-don't-know, quote-first, verify-each-claim,
notes-only).

**Phase 3 — jury gate.** Write the rubric (from `blog-author-context.md`); add a
verification pass to `/newpost` that runs a small jury (or reuses
`/code-review ultra`) before the commit, blocking on quorum-fail.

**Phase 4 — schemas.** Where any Claude-API tool emits structured data
(changelog gen, vault tooling), switch it to structured outputs / strict tool
use against the shared front-matter/entry schema.

Ship Phase 1 before the rest — it's where reliability actually comes from.

---

## 5. Official sources (align to these, not to memory)

- Claude Code hooks reference — https://code.claude.com/docs/en/hooks
- Claude Code hooks guide — https://code.claude.com/docs/en/hooks-guide
- Reduce hallucinations — https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations
- Increase output consistency — https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/increase-consistency
- Structured outputs — https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- Tool use (strict tool use) — https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview
- Citations — https://platform.claude.com/docs/en/build-with-claude/citations
- Create empirical evaluations (LLM-as-judge / grading) — https://platform.claude.com/docs/en/test-and-evaluate/develop-tests
