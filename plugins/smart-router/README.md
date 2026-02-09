# Smart Router Plugin - Installation Guide

## Quick Install
```bash
# 1. Clone or download the plugin
git clone <repo> smart-router-plugin
cd smart-router-plugin

# 2. Run install script
chmod +x install-plugin.sh
./install-plugin.sh

# 3. Configure OpenClaw
```

Edit `~/.openclaw/openclaw.json`:
```json
{
  "plugins": ["@local/smart-router"],
  "providers": {
    "anthropic": { "apiKey": "${ANTHROPIC_API_KEY}" },
    "openai": { "apiKey": "${OPENAI_API_KEY}" },
    "google": { "apiKey": "${GOOGLE_API_KEY}" }
  },
  "agents": {
    "defaults": {
      "model": "smart-router/auto"
    }
  }
}
```
```bash
# 4. Restart OpenClaw
openclaw gateway restart
```

## Usage

### Automatic Routing (Default)

Once installed, all requests automatically use smart routing:
```bash
# This gets routed automatically
openclaw agent --message "What is 2+2?"
# → Routes to SIMPLE tier (gemini-flash)

openclaw agent --message "Prove sqrt(2) is irrational"
# → Routes to REASONING tier (o1-mini)
```

### View Statistics
```bash
openclaw router-stats
```

Output:
```
📊 Smart Router Statistics
   Total routes: 157
   Total estimated cost: $0.3421

   By Tier:
     SIMPLE: 71 (45.2%)
     MEDIUM: 55 (35.0%)
     COMPLEX: 23 (14.6%)
     REASONING: 8 (5.1%)

   By Model:
     google/gemini-2.0-flash-exp: 71 (45.2%)
     openai/gpt-4o: 55 (35.0%)
     anthropic/claude-sonnet-4: 23 (14.6%)
     openai/o1-mini: 8 (5.1%)
```

### Manual Override

You can still manually select models when needed:
```bash
# Use specific model for critical task
openclaw agent --model anthropic/claude-opus-4 --message "Review architecture"

# Then back to auto
openclaw agent --model smart-router/auto --message "What's next?"
```

### Hybrid Config

Combine smart routing with manual overrides:
```json
{
  "agents": {
    "defaults": {
      "model": "smart-router/auto",
      "heartbeatModel": "google/gemini-2.0-flash-exp",
      "subAgentModel": "smart-router/auto"
    }
  },
  "aliases": {
    "auto": "smart-router/auto",
    "max": "anthropic/claude-opus-4"
  }
}
```

## How It Works
```
Request arrives
    ↓
Plugin intercepts (model: smart-router/auto)
    ↓
14-dimension classifier runs (<1ms)
    ↓
Tier determined (SIMPLE/MEDIUM/COMPLEX/REASONING)
    ↓
Model selected from tier
    ↓
Request routed to actual provider (Anthropic/OpenAI/Google)
    ↓
Response returned with routing metadata
```

## Cost Savings

**Typical distribution:**
- 45% SIMPLE → gemini-flash ($0.38/1M) → 99.5% savings vs Opus
- 35% MEDIUM → gpt-4o ($6.25/1M) → 92% savings vs Opus
- 15% COMPLEX → claude-sonnet ($9/1M) → 88% savings vs Opus
- 5% REASONING → o1-mini ($7.5/1M) → 90% savings vs Opus

**Average: $4.50/1M tokens** vs **$75/1M (Opus only)** = **94% savings**

## Configuration

The plugin uses sensible defaults but can be customized:

### Custom Tier Models

Create `~/.openclaw/workspace/router-config.json`:
```json
{
  "tierModels": {
    "SIMPLE": "google/gemini-2.0-flash-exp",
    "MEDIUM": "anthropic/claude-sonnet-4",
    "COMPLEX": "anthropic/claude-opus-4",
    "REASONING": "openai/o1"
  },
  "costWeight": 0.3
}
```

### Dimension Weights

Override scoring weights:
```json
{
  "customWeights": {
    "reasoningMarkers": 0.25,
    "codePresence": 0.20,
    "technicalTerms": 0.15
  }
}
```

## Troubleshooting

### Plugin not loading
```bash
# Check plugin is installed
ls -la ~/.openclaw/extensions/smart-router

# Check logs
openclaw logs --follow
```

### Wrong model selected
```bash
# Enable verbose logging
export DEBUG=smart-router:*
openclaw gateway restart
```

### API key issues
```bash
# Verify keys are set
echo $ANTHROPIC_API_KEY
echo $OPENAI_API_KEY
echo $GOOGLE_API_KEY

# Test providers directly
openclaw agent --model anthropic/claude-haiku-4 --message "test"
```

## Comparison: Plugin vs Skill

| Aspect | Plugin (This) | Skill |
|--------|---------------|-------|
| **Activation** | Automatic | Manual |
| **Integration** | Deep (provider-level) | Surface (tool call) |
| **Performance** | <1ms overhead | ~50ms+ (bash invocation) |
| **Transparency** | Seamless | Agent must remember to use |
| **Maintenance** | Set and forget | Requires prompting |

**The Plugin approach is superior for routing** because it's automatic, transparent, and performant.

## What You Get

✅ **Plug-and-play** - Install once, works forever  
✅ **Automatic routing** - Every request optimized  
✅ **94% cost savings** - vs always using premium models  
✅ **No manual intervention** - Agent doesn't need to think about it  
✅ **Statistics tracking** - See what's being routed where  
✅ **Manual override** - Can still force specific models  
✅ **TypeScript native** - Fast, type-safe, integrated  

## License

MIT
