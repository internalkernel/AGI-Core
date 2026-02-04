# AGI Core 🧠

Core memory architecture and skills for AGI agents - featuring the proven tiered memory system with warm→cold promotion methodology.

## 🎯 Purpose

This repository contains essential tools and architectures for building persistent, learning AI agents. The flagship component is the **Memory Architecture Skill** - a complete implementation of the tiered memory system that enables agents to maintain continuity across sessions and learn from their experiences.

## 📦 Repository Structure

```
AGI-Core/
├── README.md                          # This file
├── LICENSE                           # MIT License
├── skills/                           # Agent skills
│   └── memory-architecture/          # Complete memory system
│       ├── SKILL.md                  # Detailed documentation
│       ├── README.md                 # Quick start guide
│       ├── install.sh                # Installation script
│       ├── utils/                    # Core utilities
│       ├── templates/                # Ready-to-use templates
│       └── docs/                     # Integration guides
└── examples/                         # Usage examples (coming soon)
```

## 🚀 Quick Start

### Install the Memory Architecture Skill

```bash
cd skills/memory-architecture
./install.sh
```

### Basic Usage

```bash
# Initialize your memory system
memory init

# Create today's daily log
memory daily

# Search your memories
memory search "Docker verification" --semantic

# Log a learning moment
memory reflect --miss "Forgot to check X" --fix "Always check X first"

# Run memory maintenance (warm→cold promotion)
memory maintain
```

## 🧠 Memory Architecture Overview

The memory system implements a **4-tier architecture** inspired by cognitive science:

1. **🔴 Core Memory** (`core.json`) - Critical facts that must NEVER be lost
2. **🟡 Reflections** (`reflections.json`) - MISS/FIX learning from failures
3. **🟢 Daily Logs** (`YYYY-MM-DD.md`) - Raw session transcripts
4. **🔵 Long-term Memory** (`MEMORY.md`) - Curated wisdom (warm→cold promoted)

### Key Features

- **Semantic Search** - Find memories by meaning, not just keywords
- **Decay-Weighted Search** - ACT-R inspired memory retrieval
- **Automated Maintenance** - Warm→cold promotion keeps MEMORY.md curated
- **Failure Learning** - Structured MISS/FIX reflection system
- **Multi-Format Support** - JSON for data, Markdown for narrative

## 📖 Documentation

- **[Memory Architecture Skill Guide](skills/memory-architecture/SKILL.md)** - Complete documentation
- **[Integration Guide](skills/memory-architecture/docs/INTEGRATION.md)** - Add to your agent
- **[API Reference](skills/memory-architecture/docs/API.md)** - All commands and options

## 🎯 Why This Matters

Most AI agents start each session with no memory of previous work. This architecture solves that by providing:

- **Continuity** - Remember important facts across sessions
- **Learning** - Improve from mistakes and successes
- **Efficiency** - Avoid repeating failed approaches
- **Growth** - Build institutional knowledge over time

## 🤝 Contributing

This is an evolving system. Contributions welcome!

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with the quickstart script
5. Submit a pull request

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

This memory architecture was developed through extensive real-world use and iteration. Thanks to all the agents and humans who contributed to refining these concepts.

---

**"Memory is the diary we all carry about with us"** - Oscar Wilde (but now agents can too!)