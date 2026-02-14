# Smart Router for OpenClaw

A standalone HTTP server that provides intelligent multi-tier model routing for OpenClaw agents. It exposes an OpenAI-compatible chat completions API and automatically classifies queries to route them to the most cost-effective backend.

## Architecture

OpenClaw's plugin `registerProvider()` is decorative — the provider registry is never consumed for LLM dispatch. OpenClaw always resolves models via `baseUrl` from `models.json` and makes HTTP requests using `@mariozechner/pi-ai`. The only way to intercept and route requests is with a real HTTP server that OpenClaw calls as a custom provider.

The smart-router server sits between OpenClaw and the upstream LLM APIs:

```
OpenClaw Agent → HTTP POST /v1/chat/completions → Smart Router (:9999)
                                                       │
                         ┌─────────────┬────────────────┼────────────────┬──────────────┐
                         ▼             ▼                ▼                ▼              ▼
                      Ollama       Synthetic        Gemini API      Anthropic       (more...)
                   (local/free)   (Kimi K2.5)    (gemini-2.5-pro)  (Opus 4.6)
```

## Tier Routing

| Tier | Provider | Model | Triggers |
|------|----------|-------|----------|
| SIMPLE | Synthetic | Kimi K2.5 | Short messages, greetings, simple Q&A |
| MEDIUM | Gemini | gemini-2.5-pro | Technical keywords, moderate length, research |
| COMPLEX | Synthetic | Kimi K2.5 | Heavy code content, long technical queries |
| REASONING | Synthetic | Kimi K2.5 | Step-by-step, proofs, deep analysis |
| ONDEMAND | Anthropic | claude-opus-4-6 | Explicitly requested via `model: "ondemand"` |

## Quick Start

### 1. Install the server

```bash
mkdir -p ~/.openclaw/smart-router-server
cp server/server.js server/package.json ~/.openclaw/smart-router-server/
cd ~/.openclaw/smart-router-server && npm install
```

### 2. Set environment variables

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export SYNTHETIC_API_KEY="syn_..."
export GOOGLE_API_KEY="AIza..."
```

### 3. Start with PM2

```bash
# Copy and customize the ecosystem config
cp examples/ecosystem.config.js ~/.openclaw/ecosystem.config.js
pm2 start ~/.openclaw/ecosystem.config.js
```

### 4. Configure OpenClaw agents

Each agent needs three config files. Copy from `examples/` and customize:

**`models.json`** — Defines the smart-router as a provider with `baseUrl` pointing to the server.
- Profile path: `~/.openclaw-<profile>/agents/main/agent/models.json`
- Workspace path: `~/.openclaw/workspaces/<workspace>/agents/main/agent/models.json`

**`auth-profiles.json`** — Must use the versioned format (see below).
- Same paths as models.json

**`openclaw.json`** — Sets the default model to `smart-router/auto`.
- Profile path: `~/.openclaw-<profile>/openclaw.json`
- Workspace path: `~/.openclaw/workspaces/<workspace>/openclaw.json`

### 5. Test

```bash
# Health check
curl http://127.0.0.1:9999/health

# Non-streaming test
curl http://127.0.0.1:9999/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"auto","messages":[{"role":"user","content":"hello"}]}'

# Streaming test (what OpenClaw uses)
curl http://127.0.0.1:9999/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"auto","stream":true,"messages":[{"role":"user","content":"hello"}]}'
```

## Critical Configuration Notes

### auth-profiles.json format

OpenClaw requires a specific versioned format. A simple `{"provider": {"apiKey": "..."}}` format will **not work** — it fails silently and produces "No API key found" errors.

Correct format:
```json
{
  "version": 1,
  "profiles": {
    "smart-router:default": {
      "type": "api_key",
      "provider": "smart-router",
      "key": "local-plugin-no-key-needed"
    }
  }
}
```

### SSE streaming is required

OpenClaw always sends `stream: true` in requests. The server must respond with proper SSE (Server-Sent Events) format — plain JSON responses will result in empty/blank output in the TUI even if the backend returned content successfully.

### Content format

OpenClaw sends message content as arrays (`[{"type":"text","text":"..."}]`) not plain strings. The server's `extractText()` helper handles both formats.

### Response sanitization

Some models (notably Kimi) emit raw tool-call markup tokens (`<|tool_calls_section_begin|>`, etc.) as plain text. The server strips these automatically via the `sanitize()` function.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` or `/health` | Health check with request stats |
| GET | `/v1/models` | List available models (`auto`, `ondemand`) |
| POST | `/v1/chat/completions` | OpenAI-compatible chat completions (streaming + non-streaming) |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ROUTER_PORT` | No | Server port (default: 9999) |
| `ANTHROPIC_API_KEY` | For ONDEMAND tier | Anthropic API key |
| `SYNTHETIC_API_KEY` | For SIMPLE/COMPLEX/REASONING | Synthetic API key |
| `GOOGLE_API_KEY` | For MEDIUM tier | Google AI API key (Gemini) |
| `OLLAMA_URL` | For local models | Ollama endpoint (default: http://localhost:11434) |

## Customizing Tiers

Edit the `TIER_MODELS` object in `server/server.js`:

```javascript
const TIER_MODELS = {
  SIMPLE:    { provider: "ollama",    model: "mistral:latest" },  // Use local when GPU available
  MEDIUM:    { provider: "gemini",    model: "gemini-2.5-pro" },
  COMPLEX:   { provider: "anthropic", model: "claude-sonnet-4-5-20250929" },
  REASONING: { provider: "synthetic", model: "hf:moonshotai/Kimi-K2.5" },
  ONDEMAND:  { provider: "anthropic", model: "claude-opus-4-6" },
};
```

## Classifier Logic

The classifier examines the last user message and scores it against keyword patterns:

- **REASONING** — 2+ reasoning keywords (prove, theorem, step-by-step, analyze, etc.)
- **SIMPLE** — Short messages (<30 chars) or messages with greeting/simple keywords
- **COMPLEX** — 3+ code keywords, or 2+ code keywords with technical terms, or code + long message
- **MEDIUM** — Technical keywords, single code references, or messages over 150 chars
- **Default** — Falls back to SIMPLE

## File Structure

```
smart-router/
├── server/
│   ├── server.js           # The HTTP server (main entry point)
│   └── package.json        # Server dependencies
├── examples/
│   ├── ecosystem.config.js # PM2 multi-agent configuration
│   ├── models.json         # OpenClaw provider/model definitions
│   ├── auth-profiles.json  # OpenClaw auth (versioned format)
│   ├── openclaw-profile.json   # Profile-level config (local mode)
│   └── openclaw-workspace.json # Workspace-level config (LAN mode)
├── legacy-plugin/          # Original TypeScript plugin (decorative, see note)
├── README.md
└── CONFIGURATION.md
```

## Legacy Plugin

The `legacy-plugin/` directory contains the original OpenClaw plugin approach (TypeScript). This approach was abandoned after discovering that `api.registerProvider()` pushes to `registry.providers` but OpenClaw never consumes that array for LLM dispatch — it always uses HTTP via `baseUrl`.

## License

MIT
