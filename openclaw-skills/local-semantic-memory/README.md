# Local Semantic Memory Skill

Multi-agent semantic memory system for OpenClaw using Ollama embeddings and ChromaDB.

## Features

- **Agent Identity Tracking** - Each memory is tagged with the agent that created it
- **Concurrent Access Protection** - File-based locking prevents conflicts between agents
- **Workspace Isolation** - Each agent maintains its own private memory space
- **Shared Memory** - Optional shared workspace for cross-agent knowledge
- **Semantic Search** - Vector-based similarity search using embeddings
- **Workspace Validation** - Security checks ensure safe workspace locations

## Quick Start

### 1. Setup Workspaces

```bash
./setup-multi-agent-workspaces.sh
```

### 2. Install Prerequisites

```bash
# Start Ollama
ollama serve

# Pull embedding model
ollama pull nomic-embed-text
```

### 3. Configure PM2 (if using)

Add these environment variables to your agent configuration:

```javascript
env: {
  OPENCLAW_WORKSPACE: '/path/to/workspace',
  OPENCLAW_AGENT_ID: 'agent-name',
  OPENCLAW_AGENT_NAME: 'Agent Display Name'
}
```

## Usage

```bash
# Add a memory (auto-detects workspace from env)
uv run local-semantic-memory.py add "Important fact"

# Search memories
uv run local-semantic-memory.py search "query text"

# View statistics
uv run local-semantic-memory.py stats

# Use shared memory
uv run local-semantic-memory.py --shared add "Shared knowledge"

# Consolidate daily logs
uv run local-semantic-memory.py consolidate --days 7
```

## Documentation

- **[MULTI_AGENT_MEMORY_SETUP.md](./MULTI_AGENT_MEMORY_SETUP.md)** - Complete setup and configuration guide
- **[MEMORY_QUICK_REFERENCE.md](./MEMORY_QUICK_REFERENCE.md)** - Command reference and troubleshooting

## Requirements

- Python 3.10+
- Ollama with `nomic-embed-text` model
- Dependencies (auto-installed by uv):
  - `ollama>=0.4.0`
  - `chromadb>=0.4.22`
  - `python-dateutil>=2.8.2`
  - `filelock>=3.12.0`

## Architecture

```
workspace/
├── memory/           # Daily log files
├── vector_db/        # ChromaDB vector database
├── logs/             # Agent logs
├── cache/            # Temporary files
└── .memory.lock      # Concurrency lock (auto-created)
```

## Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `OPENCLAW_WORKSPACE` | Agent's workspace path | `~/.openclaw/workspace-devops` |
| `OPENCLAW_AGENT_ID` | Agent identifier | `devops` |
| `OPENCLAW_AGENT_NAME` | Human-readable agent name | `DevOps Agent` |

## License

MIT
