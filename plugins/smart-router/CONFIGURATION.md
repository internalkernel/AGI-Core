# Smart Router - Configuration Reference

## Tier Configuration

### Tier 1: SIMPLE
- **Provider**: Synthetic (Kimi K2.5)
- **Cost**: Free via Synthetic API
- **Triggers**: Short messages (<30 chars), greetings, simple Q&A keywords
- **Example**: "Hello", "What is 2+2?", "Thanks"
- **Note**: Switch to `ollama` + `mistral:latest` when GPU is available for truly free local inference

### Tier 2: MEDIUM
- **Provider**: Google (Gemini 2.5 Pro)
- **Cost**: Standard Gemini pricing
- **Triggers**: Technical keywords, moderate length (>150 chars), single code references
- **Use cases**: Research, local search optimization, general technical queries
- **Example**: "Explain how nginx reverse proxy works", "What are best practices for PostgreSQL indexing?"

### Tier 3: COMPLEX
- **Provider**: Synthetic (Kimi K2.5)
- **Cost**: Free via Synthetic API
- **Triggers**: 3+ code keywords, code + technical terms, code + long messages (>200 chars)
- **Example**: "Implement an async function that uses Redis for caching with a class-based architecture"

### Tier 4: REASONING
- **Provider**: Synthetic (Kimi K2.5)
- **Cost**: Free via Synthetic API
- **Triggers**: 2+ reasoning keywords (prove, theorem, step-by-step, analyze, evaluate, etc.)
- **Example**: "Prove step-by-step that the square root of 2 is irrational using logic"

### Tier 5: ONDEMAND
- **Provider**: Anthropic (Claude Opus 4.6)
- **Cost**: $15.00 input / $75.00 output per 1M tokens
- **Access**: Request with `model: "ondemand"`, or include `/ondemand` in your message when using `auto`
- **Use cases**: Highest quality output, critical tasks, creative excellence
- **Example**: "/ondemand Write a production-ready OAuth2 implementation"

---

## OpenClaw Agent Configuration

Each agent needs configuration in **two locations**: the profile directory and the workspace directory.

### Directory Structure

```
~/.openclaw-<profile>/
├── openclaw.json                          # Profile config
└── agents/main/agent/
    ├── models.json                        # Provider + model definitions
    └── auth-profiles.json                 # API key auth

~/.openclaw/workspaces/<workspace>/
├── openclaw.json                          # Workspace config
└── agents/main/agent/
    ├── models.json                        # Provider + model definitions (copy)
    └── auth-profiles.json                 # API key auth (copy)
```

### models.json

The `smart-router` provider must be defined with:
- `baseUrl` pointing to the smart-router server
- `api` set to `openai-completions`
- Two models: `auto` (intelligent routing) and `ondemand` (direct Opus access)

```json
{
  "providers": {
    "smart-router": {
      "baseUrl": "http://127.0.0.1:9999/v1",
      "api": "openai-completions",
      "models": [
        {
          "id": "auto",
          "name": "Smart Router (Auto)",
          "reasoning": false,
          "input": ["text"],
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
          "contextWindow": 256000,
          "maxTokens": 8192
        },
        {
          "id": "ondemand",
          "name": "Smart Router (On-Demand)",
          "reasoning": false,
          "input": ["text"],
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
          "contextWindow": 256000,
          "maxTokens": 8192
        }
      ],
      "apiKey": "SMART_ROUTER_API_KEY"
    }
  }
}
```

You can include additional providers (e.g., `synthetic`) alongside `smart-router` in the same file.

### auth-profiles.json

**Critical**: Must use the versioned format. Simple key-value formats are silently ignored.

```json
{
  "version": 1,
  "profiles": {
    "synthetic:default": {
      "type": "api_key",
      "provider": "synthetic",
      "key": "YOUR_SYNTHETIC_API_KEY"
    },
    "smart-router:default": {
      "type": "api_key",
      "provider": "smart-router",
      "key": "local-plugin-no-key-needed"
    }
  }
}
```

### openclaw.json (profile level)

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "smart-router/auto"
      }
    }
  },
  "gateway": {
    "mode": "local"
  }
}
```

### openclaw.json (workspace level)

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "smart-router/auto"
      }
    }
  },
  "gateway": {
    "bind": "lan"
  }
}
```

---

## Environment Variables

### Required for smart-router server

| Variable | Tiers | Description |
|----------|-------|-------------|
| `ANTHROPIC_API_KEY` | ONDEMAND | Anthropic API key for Claude Opus 4.6 |
| `SYNTHETIC_API_KEY` | SIMPLE, COMPLEX, REASONING | Synthetic API key for Kimi K2.5 |
| `GOOGLE_API_KEY` | MEDIUM | Google AI API key for Gemini 2.5 Pro |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `ROUTER_PORT` | `9999` | Port for the smart-router HTTP server |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama endpoint for local models |

### For OpenClaw agents (PM2 env)

Each agent process also needs `SMART_ROUTER_API_KEY` set to any non-empty value (e.g., `local-plugin-no-key-needed`). This satisfies OpenClaw's auth resolution without needing a real key since the router runs locally.

---

## PM2 Multi-Agent Setup

See `examples/ecosystem.config.js` for a complete PM2 configuration. Key points:

1. **Start smart-router first** — it must be listening before agents try to connect
2. **Pass API keys via env** — PM2 reads from your shell environment at startup
3. **Use `--update-env`** — when restarting after env changes: `pm2 restart all --update-env`
4. **Each agent gets its own profile and workspace** — isolated state and configuration

```bash
# Start everything
pm2 start ~/.openclaw/ecosystem.config.js

# Check status
pm2 status

# View smart-router logs
pm2 logs smart-router

# Restart with updated env vars
pm2 restart all --update-env
```

---

## Testing

### Test via curl

```bash
# SIMPLE tier (short greeting)
curl -s http://127.0.0.1:9999/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"auto","stream":true,"messages":[{"role":"user","content":"hello"}]}'

# MEDIUM tier (technical keyword)
curl -s http://127.0.0.1:9999/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"auto","stream":true,"messages":[{"role":"user","content":"What are the best practices for configuring nginx as a reverse proxy?"}]}'

# ONDEMAND tier (manual override)
curl -s http://127.0.0.1:9999/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"ondemand","stream":true,"messages":[{"role":"user","content":"Provide a comprehensive analysis"}]}'

# Health check with stats
curl -s http://127.0.0.1:9999/health | jq
```

### Check routing decisions

Watch the smart-router logs to verify tier classification:

```bash
pm2 logs smart-router --lines 20
```

Example output:
```
[2026-02-12T22:28:44.649Z] REQ MEDIUM → gemini/gemini-2.5-pro | 1 msgs | stream=true | "What are the best practices for configuring nginx..."
[2026-02-12T22:29:22.388Z] OK  MEDIUM | 37741ms | 7605 chars
```

---

## Troubleshooting

### TUI shows empty/blank response
- The server must respond with SSE streaming format when `stream: true` is sent
- Check that the smart-router process is running: `pm2 status`
- Check for errors: `pm2 logs smart-router`

### "No API key found for provider smart-router"
- auth-profiles.json is in the wrong format (must be versioned, see above)
- The file must exist in both the profile and workspace agent directories

### Smart-router logs show request but TUI is blank
- This was the SSE streaming issue — ensure you're running the latest server.js
- Verify with: `curl -s http://127.0.0.1:9999/v1/chat/completions -d '{"model":"auto","stream":true,"messages":[{"role":"user","content":"hi"}]}' -H "Content-Type: application/json"`

### Raw tool-call tokens appearing in output
- Some models (Kimi) emit `<|tool_calls_section_begin|>` markup as text
- The `sanitize()` function in server.js strips these automatically
- If new patterns appear, add them to the sanitize regex

### Ollama too slow
- Ollama on CPU-only can take 30+ minutes for Mistral 7B
- Check GPU availability: `ollama ps` (look for `size_vram`)
- If no GPU, keep SIMPLE tier on synthetic/gemini instead of ollama
