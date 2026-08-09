---
title: "A Self-Hosted Multi-LLM Gateway for My Homelab"
date: 2026-07-29T13:45:00+10:00
draft: false
description: "One endpoint, many models: LiteLLM + Open WebUI + OpenRouter behind SSO and Langfuse, with Claude Code still the main driver."
tags: ["home-lab", "llm", "self-hosting", "litellm", "open-webui", "openrouter", "claude-code", "docker", "caddy", "authentik"]
cover:
  image: "/images/posts/self-hosted-multi-llm-gateway-homelab/cover.png"
  alt: "RAINBOW MATRIX cover — the post title in rainbow monospace over falling matrix rain on black"
  hiddenInSingle: true
---

Claude Code is the main LLM running my homelab. It builds, debugs, and documents most of what
happens on the Debian VM. But I wanted to try other models — and give the CLI tools a shared
backend — without wiring up a different SDK and API key for every provider.

So I put a gateway in front: **one endpoint, many models**. Claude stays the main driver; everything
else is now one config line away.

## The shape

Three containers, dropped into the Caddy + Authentik + Langfuse stack I already run:

- **LiteLLM** — the router. Speaks both the OpenAI (`/v1/chat/completions`) and Anthropic
  (`/v1/messages`) APIs, and forwards to whatever model a request names.
- **Open WebUI** — the chat frontend. Model picker, side-by-side compare.
- **OpenRouter** — one upstream key that fans out to hundreds of models, so LiteLLM only needs a
  single credential.

![Architecture: a browser and CLI agents both enter through Caddy — the browser via Authentik SSO to Open WebUI, the CLI via an API key to LiteLLM. LiteLLM routes out to OpenRouter, traces to Langfuse, and stores keys/spend in Postgres.](/images/posts/ai-gateway-architecture.svg)

No published host ports — everything is reached through Caddy, same as the rest of the lab.

![Open WebUI mid-chat, with the gateway's models in the picker.](/images/posts/ai-gateway-open-webui.png)

## The one real design decision: humans get SSO, machines get keys

The chat UI is for me, in a browser. The gateway endpoint is for CLI agents, which **can't** do an
interactive login. So the two subdomains are authenticated differently:

- `ai.` (Open WebUI) sits behind **Authentik `forward_auth`** — I log in once via SSO. I disabled
  Open WebUI's own login (`WEBUI_AUTH=false`) so there's no second prompt behind the SSO one.
- `llm.` (LiteLLM) is **not** behind SSO. It's protected by an API key instead, because that's what
  a script can actually present.

The Caddy blocks mirror the pattern my other gated services use:

```caddyfile
# chat UI — Authentik SSO
@ai host ai.mylab.duckdns.org
handle @ai {
    route {
        reverse_proxy /outpost.goauthentik.io/* authentik:9000
        forward_auth authentik:9000 {
            uri /outpost.goauthentik.io/auth/caddy
            trusted_proxies private_ranges
        }
        reverse_proxy open-webui:8080
    }
}

# gateway API — key auth only, for CLI agents
@llm host llm.mylab.duckdns.org
handle @llm {
    reverse_proxy litellm:4000
}
```

## The config

The model list maps a friendly name to an OpenRouter slug. A single key drives all of them:

```yaml
# litellm-config.yaml
model_list:
  - model_name: gpt-oss
    litellm_params:
      model: openrouter/openai/gpt-oss-20b:free
      api_key: os.environ/OPENROUTER_API_KEY
  - model_name: laguna-code
    litellm_params:
      model: openrouter/poolside/laguna-s-2.1:free
      api_key: os.environ/OPENROUTER_API_KEY
litellm_settings:
  success_callback: ["langfuse"]   # every call traced
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  database_url: os.environ/DATABASE_URL   # Postgres: virtual keys + spend
```

One thing worth knowing up front: on OpenRouter's **free tier there is no Claude, GPT-4o, or
Kimi-K2** — those cost credit. I built and tested the whole pipeline on free models
(`gpt-oss-20b`, a couple of coding models), which is enough to prove every path works. Adding credit
and uncommenting the paid models is a one-line change later; nothing else moves.

## Things that bit me

**Reasoning models return an empty reply if `max_tokens` is small.** My first test came back blank:

```json
{ "content": null, "finish_reason": "length" }
```

`gpt-oss` spends completion tokens on hidden reasoning *before* the visible answer. With
`max_tokens: 20`, all 20 went to reasoning and nothing was left for `content`. Bumping it to 200+
fixed it instantly. Cheap lesson, but a confusing one when the HTTP status is 200 and the body is
just… empty.

**Editing the Caddyfile did nothing until I restarted the container.** The Caddyfile is a
single-file bind mount. My editor replaced the file's *inode*, so the container kept serving the old
one — a `caddy reload` just re-read the stale inode. The new route simply wasn't there:

```bash
docker exec caddy grep -c "@llm host" /etc/caddy/Caddyfile   # -> 0, despite the host file having it
```

Fix is a full `docker restart caddy`, not a reload, whenever the file itself changes. Confirming the
count is `1` afterwards is now a habit.

**The chat UI 404'd instead of showing a login.** Wiring `forward_auth` in Caddy isn't enough on its
own — Authentik's embedded outpost has to know the hostname. Until I created the Application +
forward-auth provider and added it to the outpost, the outpost returned a 404 for `ai.`, and Caddy
faithfully passed that through. Once the app existed, the same URL flipped to a clean 302 → login.

**`docker: permission denied` right after adding myself to the group.** `usermod -aG docker` had
registered in the group database, but the running shell predated it. Rather than reboot mid-build, I
wrapped commands with `sg`:

```bash
sg docker -c 'docker compose up -d'
```

## Verifying it end to end

```bash
# models (OpenAI style)
curl -s https://llm.mylab.duckdns.org/v1/models -H "Authorization: Bearer $KEY"

# a completion
curl -s https://llm.mylab.duckdns.org/v1/chat/completions -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss","max_tokens":250,"messages":[{"role":"user","content":"Reply: gateway online"}]}'

# Anthropic style — the format Claude Code speaks
curl -s https://llm.mylab.duckdns.org/v1/messages -H "x-api-key: $KEY" \
  -H "anthropic-version: 2023-06-01" -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss","max_tokens":250,"messages":[{"role":"user","content":"Reply: gateway online"}]}'
```

All three returned `gateway online`, and — because `success_callback` is on — a matching trace showed
up in Langfuse seconds later, with token counts and cost. Cost is $0 for now; the free models report
zero, and the Postgres behind LiteLLM is already tracking spend for when it isn't.

![A gateway call captured as a trace in Langfuse — model, token counts, and cost.](/images/posts/ai-gateway-langfuse-trace.png)

## Where Claude Code fits

Nothing about my Claude Code workflow changed — it's still the main driver. What the gateway adds is
a **shared, traced, access-controlled backend** that other tools can point at. A small wrapper sends
Claude Code through the gateway when I want it to:

```bash
export ANTHROPIC_BASE_URL="https://llm.mylab.duckdns.org"
export ANTHROPIC_AUTH_TOKEN="$LITELLM_VIRTUAL_KEY"
claude "$@"
```

LiteLLM translates the Anthropic `/v1/messages` calls to whatever model I route to. Driving Claude
Code onto *non-Claude* models this way is experimental — it works, but it's clearly happiest on a
Claude model. Plain `claude` still talks to the real Anthropic API, untouched.

That's the whole point of the exercise: keep the tool I rely on exactly as it was, and give
everything else in the lab one clean door to walk through.
