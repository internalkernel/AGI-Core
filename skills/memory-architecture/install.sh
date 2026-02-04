#!/bin/bash
#
# Memory System Skill - Installation Script
# Sets up the tiered memory architecture for OpenClaw agents
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MEMORY_DIR="${MEMORY_DIR:-/root/clawd/memory}"
SKILL_DIR="${SCRIPT_DIR}"

echo "🧠 Memory System Skill Installer"
echo "================================"
echo ""

# Check if we're in the right place
if [ ! -f "$SKILL_DIR/SKILL.md" ]; then
    echo "❌ Error: SKILL.md not found. Are you in the skill directory?"
    exit 1
fi

# Create memory directory
echo "📁 Creating memory directory: $MEMORY_DIR"
mkdir -p "$MEMORY_DIR"

# Copy utilities
echo "📋 Installing utilities..."
cp "$SKILL_DIR/utils/memory_cli.py" "$MEMORY_DIR/"
chmod +x "$MEMORY_DIR/memory_cli.py"

# Check for existing memory_embed.py and memory-search.js
if [ -f "$MEMORY_DIR/memory_embed.py" ]; then
    echo "  • memory_embed.py already exists (keeping existing)"
else
    echo "  ⚠️  memory_embed.py not found - copy from source if needed"
fi

if [ -f "$MEMORY_DIR/memory-search.js" ]; then
    echo "  • memory-search.js already exists (keeping existing)"
else
    echo "  ⚠️  memory-search.js not found - copy from source if needed"
fi

# Initialize memory structure
echo ""
echo "🔧 Initializing memory structure..."
python3 "$MEMORY_DIR/memory_cli.py" init

# Create symlink for easy access
echo ""
echo "🔗 Creating convenience symlinks..."
if [ ! -L "/usr/local/bin/memory" ]; then
    ln -sf "$MEMORY_DIR/memory_cli.py" /usr/local/bin/memory 2>/dev/null || true
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "Quick start:"
echo "  memory daily          # Create today's daily file"
echo "  memory search <query> # Search memories"
echo "  memory maintain       # Run warm→cold promotion"
echo "  memory stats          # Show statistics"
echo ""
echo "Memory directory: $MEMORY_DIR"
