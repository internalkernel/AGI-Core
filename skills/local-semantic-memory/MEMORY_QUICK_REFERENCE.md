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

# Search memories (hybrid vector + FTS5)
uv run ~/.openclaw/skills/local-semantic-memory/local-semantic-memory.py search "query"

# Search with intent display
uv run local-semantic-memory.py search "who is my doctor?" --show-intent

# Search with LLM reranking
uv run local-semantic-memory.py search "query" --rerank

# View stats
uv run ~/.openclaw/skills/local-semantic-memory/local-semantic-memory.py stats

# Consolidate logs
uv run ~/.openclaw/skills/local-semantic-memory/local-semantic-memory.py consolidate

# Decay stale memories
uv run local-semantic-memory.py decay --dry-run
uv run local-semantic-memory.py decay --age-days 30 --threshold 0.15

# Correct a wrong memory
uv run local-semantic-memory.py correct "Corrected info" --memory-id <id> --reason "Was outdated"

# Record a lesson learned
uv run local-semantic-memory.py lesson "Always do X" --mistake "Did Y instead"

# Search excluding retracted (default) or including them
uv run local-semantic-memory.py search "query" --include-retracted
```

## Agent-Specific Commands

```bash
# Specific workspace
uv run local-semantic-memory.py --workspace ~/.openclaw/workspace-devops add "text"

# Shared memory
uv run local-semantic-memory.py --shared add "shared knowledge"

# With category
uv run local-semantic-memory.py add "text" --category user_prefs

# Force add (bypass dedup)
uv run local-semantic-memory.py add "text" --force
```

## New CLI Flags

| Flag | Command | Purpose |
|------|---------|---------|
| `--show-intent` | search | Show detected query intent and weights |
| `--rerank` | search | Enable LLM reranking via Ollama |
| `--rerank-model` | search | Specify Ollama model for reranking |
| `--force` | add | Bypass deduplication checks |
| `--dry-run` | decay | Preview decay without changes |
| `--threshold` | decay | Confidence threshold for deletion (default: 0.15) |
| `--age-days` | decay | Days since last access (default: 30) |
| `--memory-id` | correct | ID of the memory to retract and replace |
| `--reason` | correct | Explanation of what was wrong |
| `--mistake` | lesson | What went wrong (context for the lesson) |
| `--include-retracted` | search | Show retracted memories in results |

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `OPENCLAW_WORKSPACE` | Agent's workspace path |
| `OPENCLAW_AGENT_ID` | Agent identifier |
| `OPENCLAW_AGENT_NAME` | Agent display name |

## Agents & Ports

| Agent | ID | Port | Workspace |
|-------|-----|------|-----------|
| Content Specialist | `content-specialist` | 8410 | `workspace-content-specialist` |
| DevOps | `devops` | 8420 | `workspace-devops` |
| Support Coordinator | `support-coordinator` | 8430 | `workspace-support-coordinator` |
| Wealth Strategist | `wealth-strategist` | 8440 | `workspace-wealth-strategist` |

## Troubleshooting

```bash
# Check Ollama
ollama list
ps aux | grep ollama

# Verify workspace structure
ls -la ~/.openclaw/workspace-*/

# Check FTS5 index
sqlite3 ~/.openclaw/workspaces/shared/memory.db "SELECT COUNT(*) FROM memories_fts"

# Check agent environment
pm2 env openclaw-devops

# Remove stale locks (agents stopped)
rm ~/.openclaw/workspace-*/.memory.lock

# View agent logs
pm2 logs openclaw-devops
```

## File Locations

- **Skill**: `~/.openclaw/skills/local-semantic-memory/local-semantic-memory.py`
- **Workspaces**: `~/.openclaw/workspace-<agent>/`
- **Vector DB**: `~/.openclaw/workspace-<agent>/vector_db/`
- **FTS DB**: `~/.openclaw/workspace-<agent>/memory.db`
- **PM2 Config**: `~/.openclaw/ecosystem.config.js`
- **Setup Script**: `~/.openclaw/scripts/setup-multi-agent-workspaces.sh`
- **Full Guide**: `~/.openclaw/MULTI_AGENT_MEMORY_SETUP.md`
