#!/usr/bin/env python3
"""
Quick Start Example for Memory System

This script demonstrates the basic usage of the memory system.
Run this after installation to verify everything is working.
"""

import subprocess
import sys
from pathlib import Path

def run_cmd(cmd, description):
    """Run a command and print the result."""
    print(f"\n{'='*60}")
    print(f"📝 {description}")
    print(f"Command: {cmd}")
    print('='*60)
    
    # Use python3 explicitly since some systems don't have 'python' alias
    cmd = cmd.replace("python ", "python3 ")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr, file=sys.stderr)
    return result.returncode == 0

def main():
    print("🧠 Memory System Quick Start Demo")
    print("="*60)
    
    # Check if memory_cli.py exists
    cli_path = Path("utils/memory_cli.py")
    if not cli_path.exists():
        print(f"❌ Error: {cli_path} not found. Run this from the skill directory.")
        sys.exit(1)
    
    # 1. Initialize memory structure
    print("\n1️⃣  Initialize the memory structure")
    run_cmd("python utils/memory_cli.py init", "Initialize memory structure")
    
    # 2. Create today's daily file
    print("\n2️⃣  Create today's daily file")
    run_cmd("python utils/memory_cli.py daily", "Create today's daily file")
    
    # 3. Update core.json
    print("\n3️⃣  Update core.json with sample data")
    run_cmd(
        'python utils/memory_cli.py core --key "infrastructure.example" --value \'{"id": "demo123"}\'',
        "Add sample infrastructure data"
    )
    
    # 4. Add a reflection
    print("\n4️⃣  Add a sample reflection")
    run_cmd(
        'python utils/memory_cli.py reflect --miss "Forgot to check memory system was installed" --fix "Run quickstart.py to verify" --tag speed',
        "Log a sample reflection"
    )
    
    # 5. Search
    print("\n5️⃣  Search memories")
    run_cmd('python utils/memory_cli.py search "demo"', "Search for 'demo'")
    
    # 6. Stats
    print("\n6️⃣  Show statistics")
    run_cmd("python utils/memory_cli.py stats", "Show memory statistics")
    
    # 7. Maintenance preview
    print("\n7️⃣  Preview maintenance")
    run_cmd("python utils/memory_cli.py maintain", "Run maintenance analysis")
    
    print("\n" + "="*60)
    print("✅ Quick start complete!")
    print("="*60)
    print("\nNext steps:")
    print("  1. Edit memory/core.json with your actual data")
    print("  2. Copy docs/AGENTS_MEMORY_SECTION.md into your AGENTS.md")
    print("  3. Run 'memory daily' each day to create daily files")
    print("  4. Run 'memory maintain' every few days for warm→cold promotion")
    print("\nFor semantic search, ensure Ollama is running:")
    print("  curl http://localhost:11434/api/tags")
    print("  python utils/memory_embed.py index")

if __name__ == "__main__":
    main()
