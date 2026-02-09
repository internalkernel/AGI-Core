# Smart Router - Multi-Agent Configuration

Updated configuration for 5-tier intelligent routing with Kimi AI and Claude models.

## Tier Configuration

### Tier 1: SIMPLE
- **Model**: Local Mistral 7b (Ollama)
- **Cost**: Free (local)
- **Use cases**: Heartbeat, basic queries, simple responses
- **Example**: "What is 2+2?", "Hello", "Thanks"

### Tier 2: MEDIUM
- **Model**: Kimi 2.5 (Synthetic/Moonshot AI)
- **Cost**: $0.50 input / $2.00 output per 1M tokens
- **Use cases**: Standard queries, moderate complexity
- **Example**: "Explain Docker containers", "Write a Python function to parse JSON"

### Tier 3: COMPLEX
- **Model**: Claude Sonnet 4.5 (Anthropic)
- **Cost**: $3.00 input / $15.00 output per 1M tokens
- **Use cases**: Advanced reasoning, nuanced problems, quality writing
- **Example**: "Design a microservices architecture", "Analyze this code for security issues"

### Tier 4: REASONING
- **Model**: Kimi-K2-Thinking (Synthetic/Moonshot AI)
- **Cost**: $2.00 input / $8.00 output per 1M tokens
- **Fallback**: Claude Opus 4.6 (automatic on failure)
- **Use cases**: Multi-step reasoning, mathematical proofs, complex algorithms
- **Example**: "Prove the Pythagorean theorem", "Design a distributed consensus algorithm"

### Tier 5: ONDEMAND
- **Model**: Claude Opus 4.6 (Anthropic)
- **Cost**: $15.00 input / $75.00 output per 1M tokens
- **Access**: Manual selection only OR automatic fallback from REASONING
- **Use cases**: Highest quality, most difficult problems, creative excellence
- **Example**: Manual override for critical tasks

---

## Usage

### Automatic Routing (Default)

```bash
# Uses smart-router/auto - automatically classifies and routes
openclaw agent --message "Your query here"

# The router will analyze and select the best tier
```

### Manual ONDEMAND Override

```bash
# Force Opus 4.6 for critical tasks
openclaw agent --model smart-router/ondemand --message "Critical analysis needed"
```

Or in PM2 config for specific requests:
```javascript
{
  model: {
    primary: "smart-router/ondemand"  // Use Opus 4.6 directly
  }
}
```

### Fallback Behavior

When **Kimi-K2-Thinking** fails (REASONING tier):
1. Error is caught automatically
2. Request retries with **Claude Opus 4.6**
3. Stats track fallback count
4. Response includes fallback metadata

---

## Environment Variables

### Required

```bash
# Anthropic (for COMPLEX and ONDEMAND tiers)
export ANTHROPIC_API_KEY="sk-ant-..."

# Google (optional, for alternative routing)
export GOOGLE_API_KEY="..."

# Synthetic/Kimi (for MEDIUM and REASONING tiers)
export SYNTHETIC_API_KEY="sk-..."
```

### Optional

```bash
# Custom Synthetic API URL (default: https://api.moonshot.cn/v1)
export SYNTHETIC_API_URL="https://api.moonshot.cn/v1"

# Ollama URL for local models (default: http://localhost:11434)
export OLLAMA_URL="http://localhost:11434"
```

---

## PM2 Multi-Agent Setup

Update `~/.openclaw/ecosystem.config.js`:

```javascript
module.exports = {
  apps: [
    {
      name: 'openclaw-content-specialist',
      script: 'openclaw',
      args: 'gateway',
      env: {
        OPENCLAW_WORKSPACE: `${process.env.HOME}/.openclaw/workspaces/agent-content-specialist`,
        OPENCLAW_AGENT_ID: 'content-specialist',
        ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY,
        GOOGLE_API_KEY: process.env.GOOGLE_API_KEY,
        SYNTHETIC_API_KEY: process.env.SYNTHETIC_API_KEY,
        OLLAMA_URL: 'http://localhost:11434',
      }
    },
    // ... other agents
  ]
}
```

---

## Statistics

View routing statistics:

```bash
openclaw router-stats
```

Output:
```
📊 Smart Router Statistics
   Total routes: 247
   Fallback triggers: 3
   Total estimated cost: $0.4521

   By Tier:
     SIMPLE: 98 (39.7%)
     MEDIUM: 87 (35.2%)
     COMPLEX: 42 (17.0%)
     REASONING: 15 (6.1%)
     ONDEMAND: 5 (2.0%)

   By Model:
     local/mistral-7b: 98 (39.7%)
     synthetic/kimi-2.5: 87 (35.2%)
     anthropic/claude-sonnet-4.5: 42 (17.0%)
     synthetic/kimi-k2-thinking: 12 (4.9%)
     anthropic/claude-opus-4.6: 8 (3.2%)
```

---

## Cost Analysis

**Typical Distribution** (per 1M tokens):
- 40% SIMPLE → $0.00 (local)
- 35% MEDIUM → $2.50 (Kimi 2.5)
- 17% COMPLEX → $18.00 (Sonnet 4.5)
- 6% REASONING → $10.00 (K2-Thinking)
- 2% ONDEMAND → $90.00 (Opus 4.6)

**Average cost: ~$7.50/1M tokens** vs **$90/1M (Opus only)** = **92% savings**

---

## Model Registry

All available models:

| Provider | Model | Input $/1M | Output $/1M |
|----------|-------|------------|-------------|
| Anthropic | claude-opus-4.6 | $15.00 | $75.00 |
| Anthropic | claude-opus-4.5 | $15.00 | $75.00 |
| Anthropic | claude-sonnet-4.5 | $3.00 | $15.00 |
| Anthropic | claude-haiku-4.5 | $0.80 | $4.00 |
| Google | gemini-2.0-pro | $1.25 | $5.00 |
| Google | gemini-2.0-flash-exp | $0.075 | $0.30 |
| Google | gemini-2.0-flash-thinking-exp | $0.00 | $0.00 |
| Synthetic | kimi-k2-thinking | $2.00 | $8.00 |
| Synthetic | kimi-2.5 | $0.50 | $2.00 |
| Local | mistral:7b | $0.00 | $0.00 |

---

## Rebuilding After Changes

If you modify the TypeScript source:

```bash
cd ~/.openclaw/extensions/smart-router
npm install  # First time only
npm run build
pm2 restart all
```

---

## Testing

### Test Each Tier

```bash
# SIMPLE tier
openclaw agent --message "Hello, how are you?"

# MEDIUM tier
openclaw agent --message "Explain how Docker networking works"

# COMPLEX tier
openclaw agent --message "Design a fault-tolerant distributed cache system with eventual consistency"

# REASONING tier
openclaw agent --message "Prove step-by-step that the square root of 2 is irrational"

# ONDEMAND tier (manual)
openclaw agent --model smart-router/ondemand --message "Provide a comprehensive analysis of this architecture"
```

### Test Fallback

Simulate K2-Thinking failure (requires testing with actual API):
```bash
# If K2-Thinking fails, should automatically use Opus 4.6
# Check stats to see fallback count
openclaw router-stats
```

---

## Customization

### Change Tier Models

Edit `~/.openclaw/extensions/smart-router/src/classifier.ts`:

```typescript
function getModelForTier(tier: RoutingDecision["tier"]): string {
  const tierModels = {
    SIMPLE: "local/mistral-7b",
    MEDIUM: "synthetic/kimi-2.5",
    COMPLEX: "anthropic/claude-sonnet-4.5",  // Change this
    REASONING: "synthetic/kimi-k2-thinking",
    ONDEMAND: "anthropic/claude-opus-4.6",
  };
  return tierModels[tier];
}
```

Then rebuild:
```bash
npm run build
```

---

## Troubleshooting

### Synthetic API Not Working

```bash
# Check API key
echo $SYNTHETIC_API_KEY

# Test manually
curl -X POST https://api.moonshot.cn/v1/chat/completions \
  -H "Authorization: Bearer $SYNTHETIC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "kimi-2.5",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### Ollama Not Responding

```bash
# Check Ollama is running
ps aux | grep ollama

# Start Ollama
ollama serve

# Pull Mistral model
ollama pull mistral:7b
```

### Fallbacks Not Triggering

- Fallback only works for REASONING tier
- Only triggers on actual errors (not low quality responses)
- Check logs for error messages

---

## Next Steps

1. Set environment variables (SYNTHETIC_API_KEY, etc.)
2. Rebuild the plugin: `npm run build`
3. Update PM2 config with API keys
4. Restart agents: `pm2 restart all`
5. Test routing: `openclaw router-stats`
