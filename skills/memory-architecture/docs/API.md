# API Reference

Complete API reference for the Memory System skill.

## memory_cli.py

Main CLI utility for memory operations.

### Commands

#### `init`

Initialize the memory structure with templates.

```bash
python memory_cli.py init
```

Creates:
- `memory/core.json`
- `memory/reflections.json`
- `MEMORY.md`
- `memory/access-log.json`
- Today's daily file

---

#### `daily`

Create or get today's daily file.

```bash
python memory_cli.py daily
```

Returns: Path to today's file (`memory/YYYY-MM-DD.md`)

---

#### `search`

Search memories using various methods.

```bash
python memory_cli.py search "query" [--semantic] [--decay] [--top-k N]
```

**Options:**
- `--semantic` - Use semantic search (requires Ollama)
- `--decay` - Use decay-weighted search (requires Node.js)
- `--top-k N` - Return top N results (default: 5)

**Example:**
```bash
python memory_cli.py search "Docker verification" --semantic
```

**Returns:** Formatted search results

---

#### `maintain`

Run warm→cold promotion maintenance.

```bash
python memory_cli.py maintain [--archive-old]
```

Analyzes recent daily files and suggests content to promote to MEMORY.md.

**Options:**
- `--archive-old` - Archive old MEMORY.md content to separate files

---

#### `reflect`

Add a MISS/FIX reflection entry.

```bash
python memory_cli.py reflect --miss "..." --fix "..." [--tag TAG]
```

**Options:**
- `--miss` (required) - What went wrong (concrete, specific)
- `--fix` (required) - How to fix it
- `--tag` - Category: `confidence`, `speed`, `depth`, `uncertainty`

**Example:**
```bash
python memory_cli.py reflect \
  --miss "Tried to commit Python venv directory" \
  --fix "Always add venv to .gitignore first" \
  --tag speed
```

---

#### `core`

Update core.json with a new value.

```bash
python memory_cli.py core --key <path> --value <json>
```

**Options:**
- `--key` - Dot-notation path (e.g., `infrastructure.service.id`)
- `--value` - JSON value to set

**Example:**
```bash
python memory_cli.py core \
  --key "infrastructure.sitesSheet" \
  --value '{"id": "xxx", "name": "Sites"}'
```

---

#### `stats`

Show memory system statistics.

```bash
python memory_cli.py stats
```

**Returns:**
- Total files in memory/
- Daily files count
- Recent files (last 7 days)
- JSON files count
- Reflections logged
- MEMORY.md size (with warning if > 3KB)

---

## memory_embed.py

Semantic search using Ollama embeddings.

### Commands

#### `index`

Index all memory files.

```bash
python memory_embed.py index
```

Creates embeddings for all `.md` and `.json` files in `memory/`.

**Requirements:**
- Ollama running at `http://localhost:11434`
- Embedding model installed (default: `embeddinggemma:300m`)

---

#### `search`

Perform semantic search.

```bash
python memory_embed.py search "your query here"
```

**Returns:** Top 5 semantically similar chunks with:
- Source file
- Similarity score
- Line numbers
- Text excerpt

---

#### `stats`

Show index statistics.

```bash
python memory_embed.py stats
```

---

#### `clear`

Clear all indexed data.

```bash
python memory_embed.py clear
```

---

### Python API

```python
from memory.memory_embed import MemoryEmbedder

embedder = MemoryEmbedder()

# Index all files
embedder.index_all()

# Search
results = embedder.search("query", top_k=5)
print(embedder.format_results(results, "query"))

# Stats
embedder.stats()

# Clear
embedder.clear_index()
```

---

## memory-search.js

Decay-weighted search using ACT-R inspired memory model.

### CLI Usage

```bash
node memory-search.js "your query"
```

### JavaScript API

```javascript
const { searchMemory, formatResults, calculateDecayFactor } = require('./memory-search.js');

// Search
const results = searchMemory("query", { topK: 5 });
console.log(formatResults(results, "query"));

// Calculate decay
const decay = calculateDecayFactor(Date.now() - 86400000); // 1 day ago
```

### Decay Model

Memory strength follows exponential decay:

```
score = base_score × 0.5^(age/half_life) × access_boost
```

Where:
- `half_life` = 30 days (default)
- `access_boost` = 1.2 for previously accessed memories

---

## File Formats

### core.json

```json
{
  "_meta": {
    "description": "...",
    "lastUpdated": "2026-02-01",
    "version": 1
  },
  "identity": { ... },
  "human": { ... },
  "priorityContacts": { ... },
  "infrastructure": { ... },
  "rules": { ... }
}
```

### reflections.json

```json
{
  "_meta": { ... },
  "reflections": [
    {
      "date": "2026-02-01",
      "MISS": "...",
      "FIX": "...",
      "TAG": "speed"
    }
  ],
  "_tags": { ... }
}
```

### Daily File (YYYY-MM-DD.md)

```markdown
# 2026-02-04 - Tuesday

## Summary
...

## Decisions Made
- ...

## Context & Notes
- ...

## Work Completed
- ...

## Next Steps
- ...
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MEMORY_DIR` | `/root/clawd/memory` | Path to memory directory |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API endpoint |

---

## Configuration

### Embedding Model

Edit `memory_embed.py`:

```python
EMBEDDING_MODEL = "nomic-embed-text"  # or your preferred model
CHUNK_SIZE = 512
CHUNK_OVERLAP = 128
TOP_K = 5
```

### Decay Parameters

Edit `memory-search.js`:

```javascript
const HALF_LIFE_DAYS = 30;
const ACCESS_BOOST = 0.2;
const MIN_SCORE = 0.1;
```
