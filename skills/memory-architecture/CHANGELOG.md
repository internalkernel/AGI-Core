# Changelog

All notable changes to the Memory System skill.

## [1.0.0] - 2026-02-04

### Added
- Initial release of the Memory System skill
- Tiered memory architecture (core, reflections, daily, long-term)
- Warm→cold promotion methodology
- Semantic search using Ollama embeddings
- Decay-weighted search using ACT-R inspired model
- Unified CLI (`memory` command)
- Comprehensive documentation
- Installation script
- Python package setup

### Features
- **core.json**: Critical facts that load every session
- **reflections.json**: MISS/FIX failure learning
- **Daily files**: Raw logs organized by date
- **MEMORY.md**: Curated long-term wisdom
- **Semantic search**: Vector-based similarity search
- **Decay search**: Recency and frequency weighted retrieval
- **Maintenance workflows**: Automated warm→cold promotion
- **Templates**: Ready-to-use file templates

### Documentation
- SKILL.md - Complete skill reference
- README.md - Quick start guide
- INTEGRATION.md - How to integrate with agents
- API.md - Complete API reference
- AGENTS_MEMORY_SECTION.md - Copy-paste for AGENTS.md

## Future Enhancements

- [ ] Multi-agent memory sharing
- [ ] Cloud sync options
- [ ] Additional embedding providers (OpenAI, etc.)
- [ ] Web UI for memory visualization
- [ ] Automatic summarization for warm→cold promotion
- [ ] Memory compression for large histories
