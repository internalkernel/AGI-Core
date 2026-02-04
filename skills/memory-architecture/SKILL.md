# Memory System - OpenClaw Skill

A comprehensive tiered memory architecture for OpenClaw agents, inspired by cognitive science and ACT-R memory models. This skill provides persistent memory across sessions with semantic search, decay-based retrieval, and automated maintenance.

## Overview

The Memory System implements a **warm→cold memory hierarchy** that mirrors human memory:

| Tier | File | Purpose | Load Frequency |
|------|------|---------|----------------|
| 🔴 **Core** | `memory/core.json` | Critical facts that must NEVER be lost | Every session |
| 🟡 **Reflexion** | `memory/reflections.json` | MISS/FIX learning from failures | Session start + before retries |
| 🟢 **Warm** | `memory/YYYY-MM-DD.md` | Raw daily logs, recent context | Today + yesterday |
| 🔵 **Cold** | `MEMORY.md` | Curated long-term wisdom | Main sessions only |
| 🟣 **Indexed** | `memory/search/` | Semantic embeddings for retrieval | On-demand |

## Installation

### Quick Install

```bash
# From OpenClaw skills directory
openclaw skill install memory-system

# Or clone manually
git clone <repo> /root/clawd/skills/memory-system
cd /root/clawd/skills/memory-system
./install.sh
```

### Manual Setup

1. **Copy templates** to your workspace:
```bash
cp -r templates/memory ~/clawd/memory
```

2. **Install utilities**:
```bash
# Python dependencies
pip install numpy requests

# Node.js (for decay-weighted search)
# No additional deps needed
```

3. **Initialize the memory structure**:
```bash
python utils/memory_cli.py init
```

## Quick Start

### For Agent Developers

Add this to your `AGENTS.md` or session start routine:

```markdown
## Memory Protocol (Every Session)

**Tier 1 — Always load:**
1. Read `SOUL.md` — who you are
2. Read `USER.md` — who you're helping
3. Read `memory/core.json` — critical facts
4. Scan `memory/reflections.json` — recent failures to avoid

**Tier 2 — Context:**
5. Read `memory/YYYY-MM-DD.md` (today + yesterday)
6. **Main session only:** Read `MEMORY.md`

**Tier 3 — On-demand:**
7. Use `memory_search` for anything else
```

### Using Memory Search

```bash
# Semantic search (Python + Ollama)
python utils/memory_embed.py search "Docker verification"

# Decay-weighted search (Node.js)
node utils/memory-search.js "project decisions"

# Combined search with CLI
python utils/memory_cli.py search "meeting notes" --semantic
```

## File Structure

```
memory/
├── core.json              # 🔴 Critical infrastructure, identity, rules
├── reflections.json       # 🟡 MISS/FIX learning log
├── MEMORY.md             # 🔵 Curated long-term memory (main sessions)
├── YYYY-MM-DD.md         # 🟢 Daily raw logs
├── access-log.json       # Access timestamps for decay calculation
├── memory-search.js      # Decay-weighted search utility
├── memory_embed.py       # Semantic embedding search
└── search/
    └── embeddings/       # Generated vector embeddings
```

## Memory Files Reference

### core.json

Critical facts that must never be lost. Always loaded.

```json
{
  "_meta": {
    "description": "Core memory - critical facts",
    "lastUpdated": "2026-02-01",
    "version": 1
  },
  "identity": {
    "name": "AgentName",
    "shortName": "Short",
    "emoji": "🤖",
    "human": "HumanName"
  },
  "human": {
    "name": "HumanName",
    "timezone": "America/New_York",
    "email": "human@example.com"
  },
  "priorityContacts": {
    "ceo": { "name": "CEO", "priority": "HIGH" }
  },
  "infrastructure": {
    "keyService": { "id": "xxx", "note": "Important" }
  },
  "rules": {
    "customRule": "value"
  }
}
```

### reflections.json

Learning from failures. Concrete MISS/FIX entries only.

```json
{
  "_meta": {
    "description": "Reflexion layer - MISS/FIX log",
    "lastUpdated": "2026-02-01"
  },
  "reflections": [
    {
      "date": "2026-02-01",
      "MISS": "What specifically went wrong",
      "FIX": "What to do differently next time",
      "TAG": "confidence|speed|depth|uncertainty"
    }
  ],
  "_tags": {
    "confidence": "Was uncertain about approach",
    "speed": "Took longer than necessary",
    "depth": "Missed important context",
    "uncertainty": "Proceeded when should have asked"
  }
}
```

### Daily Files (YYYY-MM-DD.md)

Raw logs of what happened. Append-only.

```markdown
# 2026-02-04 - Tuesday

## Summary
Brief overview of the day's activities.

## Decisions Made
- Decision X because Y

## Context & Notes
- Important context to remember
- Conversations had

## Work Completed
- Task A
- Task B

## Next Steps
- Pending items
```

### MEMORY.md

Curated long-term memory. Structured sections, under 2-3KB.

```markdown
# MEMORY.md - Long-Term Memory

## 🎯 Preferences Learned
Working style, communication preferences, etc.

## 🔑 Key Decisions
Important decisions and their rationale.

## 👥 People & Relationships
Key contacts and relationship context.

## 📋 Projects & Context
Ongoing projects and their status.

## 🔒 Critical Rules
Must-follow rules and constraints.

## 💡 Ideas & Observations
Insights, potential improvements, observations.
```

## Warm→Cold Promotion

The key insight: **"Wrote it down" and "can find it when needed" are different problems.**

### During Heartbeats (Every Few Days)

```bash
# Run maintenance workflow
python utils/memory_cli.py maintain
```

This will:
1. Read recent daily files
2. Identify what's worth keeping long-term
3. Update MEMORY.md with distilled insights
4. Prune MEMORY.md if over 2-3KB

### What to Promote

**Promote to MEMORY.md:**
- Decisions made and why
- Preferences learned (gold for re-anchoring personality)
- Lessons from failures (consider adding to reflections.json)
- Project milestones
- Important context about people/relationships

**Keep in daily files:**
- Raw task lists
- Transient context
- Temporary notes

## Utilities

### memory_cli.py

Main CLI for memory operations.

```bash
# Initialize memory structure
python utils/memory_cli.py init

# Create today's daily file
python utils/memory_cli.py daily

# Search memories
python utils/memory_cli.py search "query" [--semantic] [--decay]

# Run maintenance (warm→cold promotion)
python utils/memory_cli.py maintain

# Add reflection entry
python utils/memory_cli.py reflect --miss "..." --fix "..." --tag speed

# Update core.json
python utils/memory_cli.py core --key "infrastructure.newService" --value '{"id": "xxx"}'

# Show stats
python utils/memory_cli.py stats
```

### memory_embed.py

Semantic search using Ollama embeddings.

```bash
# Index all memory files
python utils/memory_embed.py index

# Search
python utils/memory_embed.py search "Docker skill verification"

# Show stats
python utils/memory_embed.py stats

# Clear index
python utils/memory_embed.py clear
```

**Requirements:** Ollama running locally with embedding model.

### memory-search.js

Decay-weighted search using ACT-R inspired memory model.

```bash
# Search with decay weighting
node utils/memory-search.js "project decisions"

# In code:
const { searchMemory } = require('./utils/memory-search.js');
const results = searchMemory("query", { topK: 5 });
```

Features:
- Recency weighting (older memories fade)
- Access frequency boosting (used memories strengthen)
- Exponential decay: `score = base * 0.5^(age/30days)`

## Integration with OpenClaw

### As a Tool

Add to your agent's tool configuration:

```json
{
  "name": "memory_search",
  "description": "Search agent memory for relevant context",
  "parameters": {
    "query": "string",
    "method": "semantic|decay|both",
    "limit": "number"
  }
}
```

### In AGENTS.md

```markdown
## Memory Architecture

I wake up fresh each session. These files are my continuity:

### 🔴 Core Memory (`memory/core.json`)
Critical facts loaded every session. Identity, infrastructure, rules.

### 🟡 Reflexion Layer (`memory/reflections.json`)
MISS/FIX entries. Check before retrying failed tasks.

### 🟢 Archival Memory
- Daily: `memory/YYYY-MM-DD.md`
- Long-term: `MEMORY.md`
- Searchable via `memory_search` tool

### Memory Protocol
See [Memory System Skill](../skills/memory-system/SKILL.md)
```

## Best Practices

### Do

- ✓ Write significant events immediately
- ✓ Use concrete MISS/FIX entries in reflections
- ✓ Keep MEMORY.md curated (not a dump)
- ✓ Run maintenance every few days
- ✓ Search before answering questions about past work

### Don't

- ✗ Keep "mental notes" — they don't survive restarts
- ✗ Log vague self-improvement goals as reflections
- ✗ Let MEMORY.md grow beyond 2-3KB
- ✗ Load MEMORY.md in shared contexts (security)

## Troubleshooting

### Search returns no results

```bash
# Rebuild index
python utils/memory_embed.py clear
python utils/memory_embed.py index
```

### Ollama connection failed

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Pull embedding model
ollama pull nomic-embed-text
```

### Memory files getting large

```bash
# Run maintenance to archive old content
python utils/memory_cli.py maintain --archive-old
```

## License

MIT - Part of the OpenClaw ecosystem.

## Credits

- Shadowfax0's warm→cold methodology
- ACT-R cognitive architecture for decay models
- OpenClaw community contributions
