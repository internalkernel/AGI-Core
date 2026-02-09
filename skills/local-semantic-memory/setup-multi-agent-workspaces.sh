#!/bin/bash
# Setup script for multi-agent workspace configuration
# This script initializes workspace directories for each agent

set -e

OPENCLAW_DIR="$HOME/.openclaw"
WORKSPACES_DIR="$OPENCLAW_DIR/workspaces"
SKILLS_DIR="$OPENCLAW_DIR/skills"

echo "🚀 Setting up multi-agent workspaces for OpenClaw"
echo ""

# Create workspaces directory
echo "📁 Creating workspaces directory structure..."
mkdir -p "$WORKSPACES_DIR"

# Define agents
agents=(
    "agent-content-specialist"
    "agent-devops"
    "agent-support-coordinator"
    "agent-wealth-strategist"
    "shared"  # Shared memory space
)

# Create workspace for each agent
for agent in "${agents[@]}"; do
    workspace="$WORKSPACES_DIR/$agent"

    if [ -d "$workspace" ]; then
        echo "  ✓ Workspace exists: $agent"
    else
        echo "  + Creating workspace: $agent"
        mkdir -p "$workspace"
    fi

    # Create subdirectories
    mkdir -p "$workspace/memory"
    mkdir -p "$workspace/vector_db"
    mkdir -p "$workspace/logs"
    mkdir -p "$workspace/cache"

    # Create a README for each workspace
    if [ "$agent" != "shared" ]; then
        cat > "$workspace/README.md" << EOF
# ${agent} Workspace

This workspace is dedicated to the \`${agent}\` agent.

## Directory Structure

- \`memory/\` - Daily log files and memory snapshots
- \`vector_db/\` - ChromaDB vector database for semantic memory
- \`logs/\` - Agent-specific logs
- \`cache/\` - Temporary cache files

## Environment Variables

This workspace should be accessed with:
\`\`\`bash
export OPENCLAW_WORKSPACE="${workspace}"
export OPENCLAW_AGENT_ID="${agent#agent-}"
\`\`\`

## Memory Usage

\`\`\`bash
# Add a memory
uv run ~/.openclaw/skills/local-semantic-memory/local-semantic-memory.py add "Important fact"

# Search memories
uv run ~/.openclaw/skills/local-semantic-memory/local-semantic-memory.py search "query"

# View stats
uv run ~/.openclaw/skills/local-semantic-memory/local-semantic-memory.py stats
\`\`\`
EOF
    else
        cat > "$workspace/README.md" << EOF
# Shared Memory Workspace

This workspace contains memories shared across all agents.

## Usage

Access shared memory with:
\`\`\`bash
uv run ~/.openclaw/skills/local-semantic-memory/local-semantic-memory.py --shared add "Shared knowledge"
uv run ~/.openclaw/skills/local-semantic-memory/local-semantic-memory.py --shared search "query"
\`\`\`

Shared memories are accessible to all agents regardless of their individual workspace.
EOF
    fi
done

echo ""
echo "✅ Workspace setup complete!"
echo ""
echo "📊 Workspace Summary:"
ls -la "$WORKSPACES_DIR" | tail -n +4 | awk '{print "  - " $9}'
echo ""

# Check if Ollama is running
echo "🔍 Checking prerequisites..."
if command -v ollama &> /dev/null; then
    if pgrep -x "ollama" > /dev/null; then
        echo "  ✓ Ollama is running"
    else
        echo "  ⚠️  Ollama is installed but not running"
        echo "     Start with: ollama serve"
    fi

    # Check if nomic-embed-text model is available
    if ollama list | grep -q "nomic-embed-text"; then
        echo "  ✓ nomic-embed-text model is available"
    else
        echo "  ⚠️  nomic-embed-text model not found"
        echo "     Install with: ollama pull nomic-embed-text"
    fi
else
    echo "  ❌ Ollama not found - required for semantic memory"
    echo "     Install from: https://ollama.ai"
fi

echo ""
echo "📝 Next steps:"
echo "  1. Ensure Ollama is running: ollama serve"
echo "  2. Pull the embedding model: ollama pull nomic-embed-text"
echo "  3. Restart PM2 agents: pm2 restart ecosystem.config.js"
echo "  4. Test memory skill from any agent workspace"
echo ""
