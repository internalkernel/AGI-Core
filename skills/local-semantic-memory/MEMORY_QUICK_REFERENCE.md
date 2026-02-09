# Semantic Memory Quick Reference

## Setup (One-Time)

```bash
# 1. Run setup script
~/.openclaw/scripts/setup-multi-agent-workspaces.sh

# 2. Start Ollama & pull model
ollama serve
ollama pull nomic-embed-text

# 3. Restart agents
pm2 restart ecosystem.config.js
```

## Common Commands

```bash
# Add memory (auto-detects agent workspace)
uv run ~/.openclaw/skills/local-semantic-memory/local-semantic-memory.py add "text"

# Search memories
uv run ~/.openclaw/skills/local-semantic-memory/local-semantic-memory.py search "query"

# View stats
uv run ~/.openclaw/skills/local-semantic-memory/local-semantic-memory.py stats

# Consolidate logs
uv run ~/.openclaw/skills/local-semantic-memory/local-semantic-memory.py consolidate
```

## Agent-Specific Commands

```bash
# Specific workspace
uv run local-semantic-memory.py --workspace ~/.openclaw/workspaces/agent-devops add "text"

# Shared memory
uv run local-semantic-memory.py --shared add "shared knowledge"

# With category
uv run local-semantic-memory.py add "text" --category user_prefs
```

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `OPENCLAW_WORKSPACE` | Agent's workspace path |
| `OPENCLAW_AGENT_ID` | Agent identifier |
| `OPENCLAW_AGENT_NAME` | Agent display name |

## Agents & Ports

| Agent | ID | Port | Workspace |
|-------|-----|------|-----------|
| Content Specialist | `content-specialist` | 8410 | `agent-content-specialist` |
| DevOps | `devops` | 8420 | `agent-devops` |
| Support Coordinator | `support-coordinator` | 8430 | `agent-support-coordinator` |
| Wealth Strategist | `wealth-strategist` | 8440 | `agent-wealth-strategist` |

## Troubleshooting

```bash
# Check Ollama
ollama list
ps aux | grep ollama

# Verify workspace structure
ls -la ~/.openclaw/workspaces/

# Check agent environment
pm2 env openclaw-devops

# Remove stale locks (agents stopped)
rm ~/.openclaw/workspaces/*/.memory.lock

# View agent logs
pm2 logs openclaw-devops
```

## File Locations

- **Skill**: `~/.openclaw/skills/local-semantic-memory/local-semantic-memory.py`
- **Workspaces**: `~/.openclaw/workspaces/`
- **PM2 Config**: `~/.openclaw/ecosystem.config.js`
- **Setup Script**: `~/.openclaw/scripts/setup-multi-agent-workspaces.sh`
- **Full Guide**: `~/.openclaw/MULTI_AGENT_MEMORY_SETUP.md`
