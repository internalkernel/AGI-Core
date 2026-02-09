# Multi-Agent Semantic Memory Configuration Guide

This guide explains how to configure and use the local semantic memory skill across multiple OpenClaw agents.

## Overview

The `local-semantic-memory` skill has been enhanced with:
- **Agent identity tracking** - Each memory is tagged with the agent that created it
- **Concurrent access protection** - File locks prevent conflicts between agents
- **Workspace validation** - Security checks ensure safe workspace locations
- **Isolated & shared memory** - Agents can have private memories or share knowledge

---

## Quick Setup

### 1. Run the Setup Script

```bash
~/.openclaw/scripts/setup-multi-agent-workspaces.sh
```

This creates:
- Individual workspace directories for each agent
- Shared memory workspace
- Required subdirectories (memory/, vector_db/, logs/, cache/)
- README files in each workspace

### 2. Install Prerequisites

```bash
# Ensure Ollama is running
ollama serve

# Pull the embedding model (in a new terminal)
ollama pull nomic-embed-text

# Install Python dependencies (handled automatically by uv)
```

### 3. Restart PM2 Agents

```bash
cd ~/.openclaw
pm2 restart ecosystem.config.js
```

---

## Workspace Structure

After setup, you'll have:

```
~/.openclaw/workspaces/
├── agent-content-specialist/
│   ├── memory/           # Daily logs
│   ├── vector_db/        # ChromaDB database
│   ├── logs/             # Agent logs
│   ├── cache/            # Temp files
│   ├── .memory.lock      # Concurrency lock (auto-created)
│   └── README.md
├── agent-devops/
│   ├── memory/
│   ├── vector_db/
│   └── ...
├── agent-support-coordinator/
│   └── ...
├── agent-wealth-strategist/
│   └── ...
└── shared/               # Cross-agent shared memory
    ├── memory/
    ├── vector_db/
    └── README.md
```

---

## PM2 Configuration

Your `ecosystem.config.js` has been updated with agent identity variables:

```javascript
{
  name: 'openclaw-content-specialist',
  env: {
    OPENCLAW_WORKSPACE: '/root/.openclaw/workspaces/agent-content-specialist',
    OPENCLAW_AGENT_ID: 'content-specialist',
    OPENCLAW_AGENT_NAME: 'Content Specialist Agent',
    OPENCLAW_PORT: '8410'
  }
}
```

### Environment Variables Explained

| Variable | Purpose | Example |
|----------|---------|---------|
| `OPENCLAW_WORKSPACE` | Agent's isolated workspace path | `~/.openclaw/workspaces/agent-devops` |
| `OPENCLAW_AGENT_ID` | Unique agent identifier for tracking | `devops` |
| `OPENCLAW_AGENT_NAME` | Human-readable agent name | `DevOps Agent` |
| `OPENCLAW_PORT` | Agent's API port | `8420` |

---

## Usage Examples

### From Within an Agent's Context

When Claude is running as a specific agent (via PM2), the workspace is auto-detected:

```bash
# Add a memory (uses agent's workspace automatically)
uv run ~/.openclaw/skills/local-semantic-memory/local-semantic-memory.py add "User prefers Python over JavaScript"

# Search agent's memories
uv run ~/.openclaw/skills/local-semantic-memory/local-semantic-memory.py search "programming preferences"

# View agent's memory stats
uv run ~/.openclaw/skills/local-semantic-memory/local-semantic-memory.py stats
```

### Manual Workspace Selection

```bash
# Specify a workspace explicitly
uv run ~/.openclaw/skills/local-semantic-memory/local-semantic-memory.py \
  --workspace ~/.openclaw/workspaces/agent-devops \
  add "Deployed v2.3.0 to production"

# Use shared memory
uv run ~/.openclaw/skills/local-semantic-memory/local-semantic-memory.py \
  --shared \
  add "Company-wide policy: All PRs require 2 reviews"
```

### Cross-Agent Memory Access

```bash
# Agent A adds a memory
OPENCLAW_AGENT_ID=content-specialist \
OPENCLAW_WORKSPACE=~/.openclaw/workspaces/agent-content-specialist \
uv run local-semantic-memory.py add "Blog post published on AI trends"

# Agent B searches across shared knowledge
uv run local-semantic-memory.py --shared search "blog posts"

# Agent C searches Agent A's workspace (if needed)
uv run local-semantic-memory.py \
  --workspace ~/.openclaw/workspaces/agent-content-specialist \
  search "AI trends"
```

---

## Memory Categories

Organize memories by category:

```bash
# User preferences
uv run local-semantic-memory.py add "Prefers dark mode" --category user_prefs

# Project facts
uv run local-semantic-memory.py add "API v2 launched 2024-01" --category project

# Episodic memories (from log consolidation)
uv run local-semantic-memory.py consolidate --days 7
```

---

## Monitoring & Maintenance

### View Statistics

```bash
# Current agent's stats
uv run local-semantic-memory.py stats

# Output:
# 📊 Memory Statistics
#    Current workspace: agent-devops
#    Current agent: devops
#    Total memories: 127
#
#    By Category:
#      general: 45
#      user_prefs: 12
#      episodic: 70
#
#    By Agent:
#      devops: 89
#      content-specialist: 38
```

### Consolidate Daily Logs

Convert markdown logs into searchable semantic memories:

```bash
# Consolidate last 1 day of logs
uv run local-semantic-memory.py consolidate

# Consolidate last week
uv run local-semantic-memory.py consolidate --days 7
```

### Clear Memories

```bash
# Delete specific memory by ID
uv run local-semantic-memory.py delete <memory-id>

# Clear entire category
uv run local-semantic-memory.py clear --category temporary
```

---

## Concurrent Access

The skill uses file-based locking to handle concurrent access safely:

- **Lock file**: `workspace/.memory.lock`
- **Timeout**: 10 seconds
- **Retry logic**: 3 attempts with exponential backoff
- **Safe for**: Multiple agents, parallel operations, high-frequency writes

### What Happens During Contention

1. Agent A starts writing a memory (acquires lock)
2. Agent B tries to write simultaneously (waits for lock)
3. Agent A finishes (releases lock)
4. Agent B acquires lock and writes
5. If timeout occurs, Agent B retries with backoff

---

## Troubleshooting

### Ollama Connection Errors

```
❌ Ollama not available: ConnectionRefusedError
```

**Solution**: Start Ollama
```bash
ollama serve
```

### Missing Embedding Model

```
❌ Model not found: nomic-embed-text
```

**Solution**: Pull the model
```bash
ollama pull nomic-embed-text
```

### Lock Timeout

```
⚠️ Retry 1/3 after 0.1s: Timeout acquiring lock
```

**Cause**: Multiple agents writing simultaneously
**Action**: Automatic retry - no action needed
**If persistent**: Check for stale lock files

```bash
# Remove stale lock (only if agents are stopped)
rm ~/.openclaw/workspaces/agent-*/. memory.lock
```

### Workspace Permission Errors

```
❌ Error: Workspace cannot be in system directory: /usr
```

**Cause**: Invalid workspace path
**Solution**: Use workspaces under `~/.openclaw/`

---

## Best Practices

### 1. **Isolated Workspaces by Default**
- Each agent should have its own workspace for private memories
- Use explicit workspace flags only when cross-agent access is needed

### 2. **Shared Memory for Common Knowledge**
- Company policies, shared resources, cross-agent coordination
- Use `--shared` flag for knowledge that benefits all agents

### 3. **Meaningful Categories**
- Organize memories with consistent category names
- Examples: `user_prefs`, `project_facts`, `episodic`, `knowledge_base`

### 4. **Regular Consolidation**
- Run `consolidate` daily or weekly to convert logs into searchable memories
- Automate with cron jobs if desired

### 5. **Monitor Memory Growth**
- Check `stats` periodically to track memory usage
- Clear old or irrelevant categories as needed

### 6. **Agent ID Consistency**
- Keep `OPENCLAW_AGENT_ID` stable across restarts
- Changing IDs creates new agent identities in memory tracking

---

## Integration with Skills

### Making Skills Workspace-Aware

When creating custom skills that need workspace access:

```python
import os
from pathlib import Path

# Get current workspace
workspace = os.getenv('OPENCLAW_WORKSPACE', str(Path.home() / '.openclaw/workspace'))
agent_id = os.getenv('OPENCLAW_AGENT_ID', 'default')

# Use workspace for skill data
skill_data = Path(workspace) / 'skill_data' / 'my-skill'
skill_data.mkdir(parents=True, exist_ok=True)
```

### Calling Semantic Memory from Skills

```python
import subprocess
import json

def add_memory(text, category='general'):
    cmd = [
        'uv', 'run',
        str(Path.home() / '.openclaw/skills/local-semantic-memory/local-semantic-memory.py'),
        'add', text,
        '--category', category,
        '--json'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)

def search_memory(query, n_results=5):
    cmd = [
        'uv', 'run',
        str(Path.home() / '.openclaw/skills/local-semantic-memory/local-semantic-memory.py'),
        'search', query,
        '--n-results', str(n_results),
        '--json'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)
```

---

## Testing the Setup

### 1. Basic Functionality Test

```bash
# Test each agent's workspace
for agent in content-specialist devops support-coordinator wealth-strategist; do
  echo "Testing agent: $agent"
  OPENCLAW_WORKSPACE=~/.openclaw/workspaces/agent-$agent \
  OPENCLAW_AGENT_ID=$agent \
  uv run ~/.openclaw/skills/local-semantic-memory/local-semantic-memory.py \
    add "Test memory for $agent"
done
```

### 2. Concurrent Access Test

```bash
# Start multiple writes simultaneously
for i in {1..5}; do
  uv run ~/.openclaw/skills/local-semantic-memory/local-semantic-memory.py \
    add "Concurrent test $i" &
done
wait
echo "All writes completed successfully!"
```

### 3. Cross-Agent Access Test

```bash
# Add to one agent
OPENCLAW_AGENT_ID=devops \
OPENCLAW_WORKSPACE=~/.openclaw/workspaces/agent-devops \
uv run local-semantic-memory.py add "DevOps deployed new feature"

# Search from shared memory
uv run local-semantic-memory.py --shared search "deployed"

# Verify stats show agent attribution
uv run local-semantic-memory.py \
  --workspace ~/.openclaw/workspaces/agent-devops \
  stats
```

---

## Summary

✅ **What's Configured**:
- Multi-agent workspace structure
- PM2 environment variables for agent identification
- Concurrent access protection
- Workspace validation

✅ **What's Automatic**:
- Workspace detection from environment
- Agent ID tracking in metadata
- Lock acquisition and retry logic
- Memory isolation per agent

✅ **What You Need**:
- Ollama running with `nomic-embed-text` model
- PM2 agents restarted with new config
- Workspaces initialized (via setup script)

---

## Support

For issues or questions:
1. Check `~/.openclaw/workspaces/<agent>/logs/` for agent-specific logs
2. Verify environment variables: `pm2 env <agent-name>`
3. Test Ollama: `ollama list` and `ollama serve`
4. Review lock files: `ls ~/.openclaw/workspaces/*/.memory.lock`

The skill is now production-ready for multi-agent deployments! 🚀
