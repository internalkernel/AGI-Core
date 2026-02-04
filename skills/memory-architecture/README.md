# Memory System for OpenClaw

A comprehensive tiered memory architecture providing persistent memory across sessions with semantic search, decay-based retrieval, and automated maintenance.

## 🎯 What This Solves

Agents wake up fresh each session with no memory of previous work. This skill provides:

- **Persistent memory** across sessions
- **Tiered storage** (hot→warm→cold) for efficient retrieval
- **Semantic search** for finding relevant context
- **Failure learning** via the Reflexion layer
- **Automated maintenance** workflows

## 📁 Architecture

```
memory/
├── 🔴 core.json              # Critical facts (always loaded)
├── 🟡 reflections.json       # MISS/FIX failure log
├── 🔵 MEMORY.md             # Curated long-term wisdom
├── 🟢 YYYY-MM-DD.md         # Daily raw logs
├── access-log.json          # Access timestamps
├── memory_cli.py           # Main CLI utility
├── memory_embed.py         # Semantic search (Ollama)
├── memory-search.js        # Decay-weighted search
└── search/embeddings/      # Vector embeddings
```

## 🚀 Quick Start

```bash
# Install
cd /root/clawd/skills/memory-system
./install.sh

# Or manually
python utils/memory_cli.py init

# Daily workflow
memory daily                    # Create today's file
memory search "project notes"   # Find relevant context
memory reflect --miss "..." --fix "..."  # Log lessons
memory maintain                 # Promote warm→cold
```

## 📖 Documentation

- **[SKILL.md](SKILL.md)** - Complete skill documentation
- **[INTEGRATION.md](docs/INTEGRATION.md)** - How to integrate with your agent
- **[API.md](docs/API.md)** - Programmatic API reference

## 🧠 Memory Tiers

| Tier | File | When Loaded | Purpose |
|------|------|-------------|---------|
| 🔴 Core | `core.json` | Every session | Identity, infrastructure, critical rules |
| 🟡 Reflexion | `reflections.json` | Session start + before retries | Learned failures |
| 🟢 Warm | `YYYY-MM-DD.md` | Today + yesterday | Recent raw context |
| 🔵 Cold | `MEMORY.md` | Main sessions only | Curated long-term wisdom |

## 🔍 Search Methods

**Semantic Search** (Python + Ollama):
```bash
python memory_embed.py search "Docker verification"
```

**Decay-Weighted Search** (Node.js + ACT-R model):
```bash
node memory-search.js "project decisions"
```

**Combined CLI**:
```bash
memory search "meeting notes" --semantic
```

## 🔄 Warm→Cold Promotion

Every few days, run maintenance to distill daily logs into long-term memory:

```bash
memory maintain
```

This analyzes recent daily files and suggests content to promote to MEMORY.md.

## 📝 Adding to Your Agent

Add this to your `AGENTS.md`:

```markdown
## Memory Protocol (Every Session)

**Tier 1 — Always load:**
1. Read `SOUL.md` — who you are
2. Read `USER.md` — who you're helping
3. Read `memory/core.json` — critical facts
4. Scan `memory/reflections.json` — recent failures

**Tier 2 — Context:**
5. Read `memory/YYYY-MM-DD.md` (today + yesterday)
6. **Main session only:** Read `MEMORY.md`

**Tier 3 — On-demand:**
7. Use `memory_search` for anything else
```

## 🛠️ Requirements

- Python 3.8+
- Node.js 16+ (for decay search)
- Ollama (optional, for semantic search)
  - Embedding model: `nomic-embed-text` or `embeddinggemma:300m`

## 📦 Files Included

```
skills/memory-system/
├── SKILL.md              # Main documentation
├── README.md             # This file
├── install.sh            # Installation script
├── templates/            # File templates
│   ├── core.json.template
│   ├── reflections.json.template
│   ├── MEMORY.md.template
│   └── daily.md.template
├── utils/                # Utilities
│   ├── memory_cli.py     # Main CLI
│   ├── memory_embed.py   # Semantic search
│   └── memory-search.js  # Decay search
└── docs/                 # Additional docs
    ├── INTEGRATION.md
    └── API.md
```

## 🤝 Contributing

This is part of the OpenClaw ecosystem. Contributions welcome!

## 📜 License

MIT
