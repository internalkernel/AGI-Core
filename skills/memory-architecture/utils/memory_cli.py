#!/usr/bin/env python3
"""
Memory System CLI - Unified interface for the OpenClaw memory architecture.

Usage:
    memory_cli.py init                    # Initialize memory structure
    memory_cli.py daily                   # Create today's daily file
    memory_cli.py search <query>          # Search memories
    memory_cli.py maintain                # Run warm→cold promotion
    memory_cli.py reflect                 # Add reflection entry
    memory_cli.py core --key <k> --value <v>  # Update core.json
    memory_cli.py stats                   # Show memory statistics
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

# Configuration
MEMORY_DIR = Path(os.environ.get("MEMORY_DIR", "/root/clawd/memory"))
DATE_FORMAT = "%Y-%m-%d"

class MemorySystem:
    """Main interface for the memory architecture."""
    
    def __init__(self, memory_dir: Optional[Path] = None):
        self.memory_dir = memory_dir or MEMORY_DIR
        self.memory_dir.mkdir(parents=True, exist_ok=True)
    
    def init(self) -> bool:
        """Initialize the memory structure with templates."""
        print("🧠 Initializing memory system...")
        
        # Create core.json if doesn't exist
        core_path = self.memory_dir / "core.json"
        if not core_path.exists():
            template = self._load_template("core.json")
            template = template.replace("{{DATE}}", datetime.now().strftime(DATE_FORMAT))
            template = template.replace("{{AGENT_NAME}}", "Agent")
            template = template.replace("{{AGENT_SHORT}}", "Agent")
            template = template.replace("{{HUMAN_NAME}}", "Human")
            template = template.replace("{{TIMEZONE}}", "UTC")
            template = template.replace("{{HUMAN_EMAIL}}", "")
            
            with open(core_path, 'w') as f:
                f.write(template)
            print(f"  ✓ Created {core_path}")
        else:
            print(f"  • {core_path} already exists")
        
        # Create reflections.json if doesn't exist
        reflections_path = self.memory_dir / "reflections.json"
        if not reflections_path.exists():
            template = self._load_template("reflections.json")
            template = template.replace("{{DATE}}", datetime.now().strftime(DATE_FORMAT))
            
            with open(reflections_path, 'w') as f:
                f.write(template)
            print(f"  ✓ Created {reflections_path}")
        else:
            print(f"  • {reflections_path} already exists")
        
        # Create MEMORY.md if doesn't exist
        memory_md_path = self.memory_dir.parent / "MEMORY.md"
        if not memory_md_path.exists():
            template = self._load_template("MEMORY.md")
            
            with open(memory_md_path, 'w') as f:
                f.write(template)
            print(f"  ✓ Created {memory_md_path}")
        else:
            print(f"  • {memory_md_path} already exists")
        
        # Create access-log.json
        access_log_path = self.memory_dir / "access-log.json"
        if not access_log_path.exists():
            with open(access_log_path, 'w') as f:
                json.dump({}, f)
            print(f"  ✓ Created {access_log_path}")
        
        # Create today's daily file
        self.daily()
        
        print("\n✅ Memory system initialized!")
        print(f"📁 Memory directory: {self.memory_dir}")
        return True
    
    def _load_template(self, name: str) -> str:
        """Load a template file."""
        skill_dir = Path(__file__).parent.parent
        template_path = skill_dir / "templates" / f"{name}.template"
        
        if template_path.exists():
            with open(template_path, 'r') as f:
                return f.read()
        
        # Fallback templates
        templates = {
            "core.json": self._core_template(),
            "reflections.json": self._reflections_template(),
            "MEMORY.md": self._memory_md_template(),
        }
        return templates.get(name, "")
    
    def _core_template(self) -> str:
        return '''{
  "_meta": {
    "description": "Core memory - critical facts that must NEVER be lost",
    "lastUpdated": "%s",
    "version": 1
  },
  "identity": {
    "name": "Agent",
    "shortName": "Agent",
    "emoji": "🤖",
    "human": "Human"
  },
  "human": {
    "name": "Human",
    "timezone": "UTC"
  },
  "priorityContacts": {},
  "infrastructure": {},
  "rules": {}
}''' % datetime.now().strftime(DATE_FORMAT)
    
    def _reflections_template(self) -> str:
        return '''{
  "_meta": {
    "description": "Reflexion layer - MISS/FIX log",
    "lastUpdated": "%s",
    "version": 1
  },
  "reflections": [],
  "_tags": {
    "confidence": "Was uncertain about approach",
    "speed": "Took longer than necessary",
    "depth": "Missed important context",
    "uncertainty": "Proceeded when should have asked"
  }
}''' % datetime.now().strftime(DATE_FORMAT)
    
    def _memory_md_template(self) -> str:
        return '''# MEMORY.md - Long-Term Memory

*Curated wisdom, not raw logs. Keep under 2-3KB.*

## 🎯 Preferences Learned

## 🔑 Key Decisions

## 👥 People & Relationships

## 📋 Projects & Context

## 🔒 Critical Rules

## 💡 Ideas & Observations
'''
    
    def daily(self) -> Path:
        """Create or get today's daily file."""
        today = datetime.now().strftime(DATE_FORMAT)
        daily_path = self.memory_dir / f"{today}.md"
        
        if not daily_path.exists():
            day_of_week = datetime.now().strftime("%A")
            content = f"# {today} - {day_of_week}\n\n## Summary\n\n## Decisions Made\n- \n\n## Context & Notes\n- \n\n## Work Completed\n- \n\n## Next Steps\n- \n"
            
            with open(daily_path, 'w') as f:
                f.write(content)
            print(f"  ✓ Created {daily_path}")
        else:
            print(f"  • {daily_path} already exists")
        
        return daily_path
    
    def search(self, query: str, semantic: bool = False, decay: bool = False, top_k: int = 5) -> List[Dict]:
        """Search memories using various methods."""
        results = []
        
        if semantic:
            # Try semantic search via memory_embed.py
            try:
                embed_script = self.memory_dir / "memory_embed.py"
                if embed_script.exists():
                    result = subprocess.run(
                        [sys.executable, str(embed_script), "search", query],
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    print(result.stdout)
                    if result.stderr:
                        print(result.stderr, file=sys.stderr)
                else:
                    print("⚠️  Semantic search not available (memory_embed.py not found)")
            except Exception as e:
                print(f"⚠️  Semantic search failed: {e}")
        
        if decay or not semantic:
            # Use decay-weighted search
            try:
                search_script = self.memory_dir / "memory-search.js"
                if search_script.exists():
                    result = subprocess.run(
                        ["node", str(search_script), query],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    print(result.stdout)
                    if result.stderr:
                        print(result.stderr, file=sys.stderr)
                else:
                    # Fallback to simple file search
                    results = self._simple_search(query)
                    self._print_simple_results(results, query)
            except Exception as e:
                print(f"⚠️  Decay search failed: {e}")
                results = self._simple_search(query)
                self._print_simple_results(results, query)
        
        return results
    
    def _simple_search(self, query: str) -> List[Dict]:
        """Simple keyword search fallback."""
        results = []
        search_terms = query.lower().split()
        
        for file_path in self.memory_dir.glob("*"):
            if file_path.suffix not in ['.md', '.json']:
                continue
            if file_path.name.startswith('.'):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                content_lower = content.lower()
                score = sum(1 for term in search_terms if term in content_lower)
                
                if score > 0:
                    results.append({
                        'file': file_path.name,
                        'score': score,
                        'excerpt': content[:200] + '...' if len(content) > 200 else content
                    })
            except Exception:
                continue
        
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:10]
    
    def _print_simple_results(self, results: List[Dict], query: str):
        """Print simple search results."""
        if not results:
            print(f'No results found for "{query}"')
            return
        
        print(f"🔍 Search results for \"{query}\" ({len(results)} matches)")
        print("=" * 50)
        
        for i, result in enumerate(results, 1):
            print(f"\n{i}. **{result['file']}** (Score: {result['score']})")
            print(f"   {result['excerpt'][:150]}")
    
    def maintain(self, archive_old: bool = False) -> bool:
        """Run warm→cold promotion maintenance."""
        print("🔄 Running memory maintenance (warm→cold promotion)...")
        
        # Find recent daily files (last 7 days)
        recent_files = []
        cutoff = datetime.now() - timedelta(days=7)
        
        for file_path in self.memory_dir.glob("*.md"):
            if file_path.name == "MEMORY.md":
                continue
            try:
                date_str = file_path.stem
                file_date = datetime.strptime(date_str, DATE_FORMAT)
                if file_date >= cutoff:
                    recent_files.append(file_path)
            except ValueError:
                continue
        
        recent_files.sort()
        
        print(f"\n📅 Found {len(recent_files)} recent daily files")
        
        # Read MEMORY.md
        memory_md_path = self.memory_dir.parent / "MEMORY.md"
        current_memory = ""
        if memory_md_path.exists():
            with open(memory_md_path, 'r') as f:
                current_memory = f.read()
        
        # Analyze for promotion candidates
        print("\n📝 Analyzing content for warm→cold promotion...")
        
        candidates = {
            'decisions': [],
            'preferences': [],
            'milestones': [],
            'people': [],
            'rules': []
        }
        
        for file_path in recent_files:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Simple extraction (can be enhanced with LLM)
            lines = content.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                if line.startswith('## '):
                    current_section = line[3:].lower()
                elif line.startswith('- ') and current_section:
                    item = line[2:]
                    if 'decision' in current_section:
                        candidates['decisions'].append((file_path.name, item))
                    elif 'preference' in current_section:
                        candidates['preferences'].append((file_path.name, item))
                    elif 'milestone' in current_section:
                        candidates['milestones'].append((file_path.name, item))
                    elif 'people' in current_section:
                        candidates['people'].append((file_path.name, item))
                    elif 'rule' in current_section:
                        candidates['rules'].append((file_path.name, item))
        
        # Show candidates
        print("\n📊 Promotion candidates found:")
        for category, items in candidates.items():
            if items:
                print(f"  • {category.capitalize()}: {len(items)} items")
        
        # Check MEMORY.md size
        memory_size_kb = len(current_memory.encode('utf-8')) / 1024
        print(f"\n📏 Current MEMORY.md size: {memory_size_kb:.1f} KB")
        
        if memory_size_kb > 3:
            print("⚠️  WARNING: MEMORY.md exceeds 3KB. Consider archiving old content.")
        
        print("\n💡 Review these daily files and update MEMORY.md manually:")
        print("   - Add significant decisions to 'Key Decisions'")
        print("   - Add learned preferences to 'Preferences Learned'")
        print("   - Add relationship context to 'People & Relationships'")
        print("   - Archive older sections if MEMORY.md grows too large")
        
        return True
    
    def reflect(self, miss: str, fix: str, tag: str = "uncertainty") -> bool:
        """Add a reflection entry."""
        reflections_path = self.memory_dir / "reflections.json"
        
        with open(reflections_path, 'r') as f:
            data = json.load(f)
        
        entry = {
            "date": datetime.now().strftime(DATE_FORMAT),
            "MISS": miss,
            "FIX": fix,
            "TAG": tag
        }
        
        data['reflections'].insert(0, entry)
        data['_meta']['lastUpdated'] = datetime.now().strftime(DATE_FORMAT)
        
        with open(reflections_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✅ Reflection logged: {miss[:50]}...")
        return True
    
    def update_core(self, key: str, value: str) -> bool:
        """Update core.json with a new value."""
        core_path = self.memory_dir / "core.json"
        
        with open(core_path, 'r') as f:
            data = json.load(f)
        
        # Parse the key path (e.g., "infrastructure.service.id")
        keys = key.split('.')
        current = data
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        # Try to parse value as JSON
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            parsed_value = value
        
        current[keys[-1]] = parsed_value
        data['_meta']['lastUpdated'] = datetime.now().strftime(DATE_FORMAT)
        
        with open(core_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✅ Updated core.json: {key} = {value}")
        return True
    
    def stats(self) -> Dict:
        """Show memory system statistics."""
        stats = {
            'total_files': 0,
            'daily_files': 0,
            'json_files': 0,
            'memory_md_size': 0,
            'reflections_count': 0,
            'recent_days': 0
        }
        
        # Count files
        for file_path in self.memory_dir.glob("*"):
            if file_path.is_file():
                stats['total_files'] += 1
                
                if file_path.suffix == '.md' and len(file_path.stem) == 10:
                    stats['daily_files'] += 1
                    try:
                        file_date = datetime.strptime(file_path.stem, DATE_FORMAT)
                        if (datetime.now() - file_date).days <= 7:
                            stats['recent_days'] += 1
                    except ValueError:
                        pass
                elif file_path.suffix == '.json':
                    stats['json_files'] += 1
        
        # MEMORY.md size
        memory_md_path = self.memory_dir.parent / "MEMORY.md"
        if memory_md_path.exists():
            stats['memory_md_size'] = memory_md_path.stat().st_size / 1024
        
        # Reflections count
        reflections_path = self.memory_dir / "reflections.json"
        if reflections_path.exists():
            with open(reflections_path, 'r') as f:
                data = json.load(f)
                stats['reflections_count'] = len(data.get('reflections', []))
        
        # Print stats
        print("📊 Memory System Statistics")
        print("=" * 40)
        print(f"Total files in memory/: {stats['total_files']}")
        print(f"Daily files: {stats['daily_files']}")
        print(f"Recent (last 7 days): {stats['recent_days']}")
        print(f"JSON files: {stats['json_files']}")
        print(f"Reflections logged: {stats['reflections_count']}")
        print(f"MEMORY.md size: {stats['memory_md_size']:.1f} KB")
        
        if stats['memory_md_size'] > 3:
            print("⚠️  WARNING: MEMORY.md exceeds 3KB recommendation")
        
        return stats


def main():
    parser = argparse.ArgumentParser(
        description="Memory System CLI for OpenClaw",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s init
    %(prog)s daily
    %(prog)s search "Docker verification"
    %(prog)s search "meeting notes" --semantic
    %(prog)s maintain
    %(prog)s reflect --miss "Forgot to check X" --fix "Always check X first" --tag speed
    %(prog)s core --key infrastructure.sheets --value '{"id": "xxx"}'
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # init
    subparsers.add_parser('init', help='Initialize memory structure')
    
    # daily
    subparsers.add_parser('daily', help='Create today\'s daily file')
    
    # search
    search_parser = subparsers.add_parser('search', help='Search memories')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--semantic', action='store_true', help='Use semantic search')
    search_parser.add_argument('--decay', action='store_true', help='Use decay-weighted search')
    search_parser.add_argument('--top-k', type=int, default=5, help='Number of results')
    
    # maintain
    maintain_parser = subparsers.add_parser('maintain', help='Run warm→cold promotion')
    maintain_parser.add_argument('--archive-old', action='store_true', help='Archive old content')
    
    # reflect
    reflect_parser = subparsers.add_parser('reflect', help='Add reflection entry')
    reflect_parser.add_argument('--miss', required=True, help='What went wrong')
    reflect_parser.add_argument('--fix', required=True, help='How to fix it')
    reflect_parser.add_argument('--tag', default='uncertainty', 
                               choices=['confidence', 'speed', 'depth', 'uncertainty'],
                               help='Failure category')
    
    # core
    core_parser = subparsers.add_parser('core', help='Update core.json')
    core_parser.add_argument('--key', required=True, help='Dot-notation key path')
    core_parser.add_argument('--value', required=True, help='JSON value to set')
    
    # stats
    subparsers.add_parser('stats', help='Show statistics')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    memory = MemorySystem()
    
    if args.command == 'init':
        memory.init()
    elif args.command == 'daily':
        memory.daily()
    elif args.command == 'search':
        memory.search(args.query, args.semantic, args.decay, args.top_k)
    elif args.command == 'maintain':
        memory.maintain(args.archive_old)
    elif args.command == 'reflect':
        memory.reflect(args.miss, args.fix, args.tag)
    elif args.command == 'core':
        memory.update_core(args.key, args.value)
    elif args.command == 'stats':
        memory.stats()


if __name__ == '__main__':
    main()
