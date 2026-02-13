# local-semantic-memory.py
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "ollama>=0.4.0",
#   "chromadb>=0.4.22",
#   "python-dateutil>=2.8.2",
#   "filelock>=3.12.0",
# ]
# ///

"""
OpenClaw Local Semantic Memory (Multi-Agent Edition)

Workspace-aware semantic memory using Ollama embeddings + ChromaDB.
Supports both isolated (per-agent) and shared (cross-agent) memory with:
- Agent identity tracking via OPENCLAW_AGENT_ID/OPENCLAW_AGENT_NAME
- Concurrent access protection with file-based locking
- Workspace validation for security
- Automatic retry with exponential backoff

Usage:
    # Auto-detect workspace from environment
    uv run local-semantic-memory.py add "User prefers Python"

    # Explicit workspace
    uv run local-semantic-memory.py --workspace ~/.openclaw/workspace-research add "Deep research findings"

    # Shared memory across all agents
    uv run local-semantic-memory.py --shared add "Company-wide knowledge"

    # Search in specific workspace
    uv run local-semantic-memory.py --workspace ~/.openclaw/workspace-coding search "Python best practices"

Environment Variables:
    OPENCLAW_WORKSPACE     - Explicit workspace path
    OPENCLAW_AGENT_ID      - Agent identifier (for tracking)
    OPENCLAW_AGENT_NAME    - Agent name (alternative to ID)
"""

import os
import sys
import json
import argparse
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import hashlib
import socket


class LocalSemanticMemory:
    """Workspace-aware semantic memory manager"""
    
    def __init__(self, workspace_path: Optional[str] = None, shared: bool = False):
        """
        Initialize memory with workspace awareness

        Args:
            workspace_path: Explicit workspace path, or None to auto-detect
            shared: If True, use shared memory location for all agents
        """
        if shared:
            # Shared memory location
            self.workspace_path = Path.home() / ".openclaw" / "workspaces" / "shared"
            self.workspace_path.mkdir(parents=True, exist_ok=True)
            print(f"📚 Using SHARED memory at: {self.workspace_path}")
        elif workspace_path:
            # Explicit workspace
            self.workspace_path = Path(workspace_path).expanduser()
            print(f"📂 Using workspace: {self.workspace_path}")
        else:
            # Auto-detect from environment
            self.workspace_path = self._detect_workspace()
            print(f"🔍 Auto-detected workspace: {self.workspace_path}")

        # Validate workspace path
        self._validate_workspace()

        # Detect agent identity
        self.agent_id = self._detect_agent_id()
        print(f"🤖 Agent ID: {self.agent_id}")

        # Ensure workspace exists
        if not self.workspace_path.exists():
            print(f"⚠️  Workspace not found: {self.workspace_path}")
            print(f"   Creating workspace directory...")
            self.workspace_path.mkdir(parents=True, exist_ok=True)
        
        # Vector DB location (within workspace)
        self.vector_db_path = self.workspace_path / "vector_db"
        self.vector_db_path.mkdir(parents=True, exist_ok=True)

        # Memory logs location
        self.memory_path = self.workspace_path / "memory"
        self.memory_path.mkdir(parents=True, exist_ok=True)

        # Initialize lock for concurrent access
        from filelock import FileLock
        self.lock_path = self.workspace_path / ".memory.lock"
        self.lock = FileLock(str(self.lock_path), timeout=10)
        
        # Initialize Ollama
        try:
            import ollama
            self.ollama_client = ollama.Client()
            # Test connection
            self.ollama_client.list()
        except Exception as e:
            print(f"❌ Ollama not available: {e}")
            print(f"   Make sure Ollama is running: ollama serve")
            sys.exit(1)
        
        # Initialize ChromaDB
        try:
            import chromadb
            self.chroma_client = chromadb.PersistentClient(path=str(self.vector_db_path))
            
            # Get or create collection
            self.collection = self.chroma_client.get_or_create_collection(
                name="semantic_memory",
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            print(f"❌ ChromaDB initialization failed: {e}")
            sys.exit(1)
        
        print(f"✓ Memory initialized with {self.collection.count()} existing memories")
    
    def _detect_workspace(self) -> Path:
        """
        Auto-detect current workspace from environment
        
        Priority:
        1. OPENCLAW_WORKSPACE env var
        2. Current working directory if under .openclaw/workspaces/
        3. Default workspace
        """
        # Check environment variable
        env_workspace = os.getenv("OPENCLAW_WORKSPACE")
        if env_workspace:
            return Path(env_workspace).expanduser()
        
        # Check if CWD is under a workspace
        cwd = Path.cwd()
        openclaw_base = Path.home() / ".openclaw"
        
        if str(cwd).startswith(str(openclaw_base / "workspaces")):
            # We're inside a workspace directory
            parts = cwd.relative_to(openclaw_base / "workspaces").parts
            if parts:
                workspace_name = parts[0]
                return openclaw_base / "workspaces" / workspace_name
        
        # Check for multi-workspace setup
        workspaces_dir = openclaw_base / "workspaces"
        if workspaces_dir.exists():
            # List available workspaces
            workspaces = [d for d in workspaces_dir.iterdir() if d.is_dir()]
            if workspaces:
                print(f"\n⚠️  Multiple workspaces detected:")
                for ws in workspaces:
                    print(f"   - {ws.name}")
                print(f"\n   Specify with --workspace flag or set OPENCLAW_WORKSPACE")
                print(f"   Falling back to default workspace...\n")
        
        # Fallback to default workspace
        default = openclaw_base / "workspace"
        if not default.exists():
            # Check if we have workspaces/agent-default
            alt_default = openclaw_base / "workspaces" / "agent-default"
            if alt_default.exists():
                return alt_default
        
        return default

    def _validate_workspace(self):
        """
        Validate workspace path for security and correctness

        Ensures workspace is in a safe location and properly structured.
        """
        openclaw_base = Path.home() / ".openclaw"
        workspace_path_resolved = self.workspace_path.resolve()

        # Check if workspace is under .openclaw directory
        try:
            # Allow workspaces under .openclaw/workspace or .openclaw/workspaces/
            valid_bases = [
                openclaw_base / "workspace",
                openclaw_base / "workspaces",
            ]
            # Also allow workspace-<name> directories (profile-based workspaces)
            if workspace_path_resolved.parent == openclaw_base.resolve():
                if workspace_path_resolved.name.startswith("workspace-"):
                    is_valid = True

            is_valid = any(
                str(workspace_path_resolved).startswith(str(base.resolve()))
                for base in valid_bases
            )

            if not is_valid:
                print(f"⚠️  Warning: Workspace is outside standard OpenClaw directories")
                print(f"   Path: {workspace_path_resolved}")
                print(f"   Expected under: {openclaw_base}")
                # Allow but warn - don't fail, as user may have custom setup
        except Exception as e:
            print(f"⚠️  Could not validate workspace path: {e}")

        # Check for suspicious paths (system directories)
        suspicious_paths = ['/bin', '/sbin', '/usr', '/lib', '/etc', '/sys', '/proc', '/dev']
        for suspicious in suspicious_paths:
            if str(workspace_path_resolved).startswith(suspicious):
                print(f"❌ Error: Workspace cannot be in system directory: {suspicious}")
                sys.exit(1)

    def _detect_agent_id(self) -> str:
        """
        Detect agent identity for tracking memory sources

        Priority:
        1. OPENCLAW_AGENT_ID env var
        2. OPENCLAW_AGENT_NAME env var
        3. Workspace name
        4. Hostname-based fallback
        """
        # Check environment variables
        agent_id = os.getenv("OPENCLAW_AGENT_ID")
        if agent_id:
            return agent_id

        agent_name = os.getenv("OPENCLAW_AGENT_NAME")
        if agent_name:
            return agent_name

        # Use workspace name
        workspace_name = self.workspace_path.name
        if workspace_name and workspace_name not in ['workspace', 'default']:
            return workspace_name

        # Fallback to hostname-based ID
        try:
            hostname = socket.gethostname()
            return f"{hostname}-{os.getpid()}"
        except:
            return f"agent-{os.getpid()}"

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using Ollama"""
        response = self.ollama_client.embeddings(
            model="nomic-embed-text",
            prompt=text
        )
        return response['embedding']
    
    def _generate_id(self, text: str, category: str) -> str:
        """Generate deterministic ID for memory"""
        content = f"{text}:{category}:{datetime.now().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def add(
        self,
        text: str,
        category: str = "general",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add a memory to the vector database with concurrent access protection"""

        # Generate embedding (outside lock - this is slow)
        embedding = self._generate_embedding(text)

        # Generate ID
        memory_id = self._generate_id(text, category)

        # Prepare metadata with agent tracking
        meta = {
            "category": category,
            "timestamp": datetime.now().isoformat(),
            "workspace": str(self.workspace_path.name),
            "agent_id": self.agent_id,
        }
        if metadata:
            meta.update(metadata)

        # Add to ChromaDB with lock protection and retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with self.lock:
                    self.collection.add(
                        ids=[memory_id],
                        embeddings=[embedding],
                        documents=[text],
                        metadatas=[meta]
                    )
                break  # Success
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 0.1 * (2 ** attempt)  # Exponential backoff
                    print(f"⚠️  Retry {attempt + 1}/{max_retries} after {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    print(f"❌ Failed to add memory after {max_retries} attempts: {e}")
                    raise

        print(f"✓ Added memory: {text[:60]}...")
        print(f"  Category: {category}")
        print(f"  Agent: {self.agent_id}")
        print(f"  ID: {memory_id}")

        return memory_id
    
    def search(
        self,
        query: str,
        n_results: int = 5,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search memories by semantic similarity"""
        
        # Generate query embedding
        query_embedding = self._generate_embedding(query)
        
        # Prepare filter
        where = {"category": category} if category else None
        
        # Search
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where
        )
        
        # Format results
        memories = []
        if results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                memory = {
                    "text": doc,
                    "distance": results['distances'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "id": results['ids'][0][i]
                }
                memories.append(memory)
        
        return memories
    
    def consolidate(self, days: int = 1):
        """Consolidate recent daily logs into semantic memory with concurrent access protection"""

        print(f"\n📋 Consolidating last {days} day(s) of logs...")

        # Find recent log files
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)

        log_files = []
        for log_file in self.memory_path.glob("*.md"):
            try:
                # Parse date from filename (YYYY-MM-DD.md)
                date_str = log_file.stem
                log_date = datetime.fromisoformat(date_str)
                if log_date >= cutoff:
                    log_files.append(log_file)
            except ValueError:
                continue

        if not log_files:
            print(f"  No logs found in last {days} day(s)")
            return

        print(f"  Found {len(log_files)} log file(s)")

        # Extract facts from logs (with lock protection for batch operation)
        with self.lock:
            consolidated = 0
            for log_file in sorted(log_files):
                print(f"  Processing: {log_file.name}")

                with open(log_file, 'r') as f:
                    content = f.read()

                # Simple extraction: look for bullet points
                lines = content.split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith('- ') or line.startswith('* '):
                        fact = line[2:].strip()
                        if len(fact) > 20:  # Meaningful content
                            try:
                                # Note: calling add() which has its own lock - we already hold the lock
                                # so we need to call the internal add logic directly
                                embedding = self._generate_embedding(fact)
                                memory_id = self._generate_id(fact, "episodic")
                                meta = {
                                    "category": "episodic",
                                    "timestamp": datetime.now().isoformat(),
                                    "workspace": str(self.workspace_path.name),
                                    "agent_id": self.agent_id,
                                    "source": log_file.name,
                                    "consolidated": True
                                }
                                self.collection.add(
                                    ids=[memory_id],
                                    embeddings=[embedding],
                                    documents=[fact],
                                    metadatas=[meta]
                                )
                                consolidated += 1
                            except Exception as e:
                                print(f"    ⚠️  Failed to add: {fact[:40]}... ({e})")

        print(f"✓ Consolidated {consolidated} memories from {len(log_files)} log(s)")
    
    def stats(self) -> Dict[str, Any]:
        """Get memory statistics including agent tracking"""

        total = self.collection.count()

        # Get all metadatas to analyze
        if total > 0:
            all_data = self.collection.get()
            categories = {}
            workspaces = {}
            agents = {}

            for meta in all_data['metadatas']:
                cat = meta.get('category', 'unknown')
                ws = meta.get('workspace', 'unknown')
                agent = meta.get('agent_id', 'unknown')
                categories[cat] = categories.get(cat, 0) + 1
                workspaces[ws] = workspaces.get(ws, 0) + 1
                agents[agent] = agents.get(agent, 0) + 1
        else:
            categories = {}
            workspaces = {}
            agents = {}

        return {
            "total_memories": total,
            "by_category": categories,
            "by_workspace": workspaces,
            "by_agent": agents,
            "current_workspace": str(self.workspace_path.name),
            "current_agent": self.agent_id,
            "vector_db_path": str(self.vector_db_path),
            "is_shared": self.workspace_path.name == "shared"
        }
    
    def delete(self, memory_id: str):
        """Delete a specific memory"""
        self.collection.delete(ids=[memory_id])
        print(f"✓ Deleted memory: {memory_id}")
    
    def clear_category(self, category: str):
        """Clear all memories in a category"""
        # Get all IDs for this category
        results = self.collection.get(where={"category": category})
        if results['ids']:
            self.collection.delete(ids=results['ids'])
            print(f"✓ Cleared {len(results['ids'])} memories from category: {category}")
        else:
            print(f"  No memories found in category: {category}")


def main():
    """CLI interface"""
    parser = argparse.ArgumentParser(
        description="Workspace-aware semantic memory for OpenClaw",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-detect workspace
  uv run local-semantic-memory.py add "User prefers Python"
  
  # Specific workspace
  uv run local-semantic-memory.py --workspace ~/.openclaw/workspace-research add "Research finding"
  
  # Shared memory
  uv run local-semantic-memory.py --shared add "Company knowledge"
  
  # Search
  uv run local-semantic-memory.py search "What does user prefer?"
  
  # Consolidate logs
  uv run local-semantic-memory.py consolidate
  
  # View stats
  uv run local-semantic-memory.py stats
        """
    )
    
    parser.add_argument(
        '--workspace',
        help='Explicit workspace path (default: auto-detect)'
    )
    parser.add_argument(
        '--shared',
        action='store_true',
        help='Use shared memory location for all agents'
    )
    parser.add_argument(
        'command',
        choices=['add', 'search', 'consolidate', 'stats', 'delete', 'clear'],
        help='Command to execute'
    )
    parser.add_argument(
        'text',
        nargs='?',
        help='Text for add/search commands'
    )
    parser.add_argument(
        '--category',
        default='general',
        help='Memory category (default: general)'
    )
    parser.add_argument(
        '--n-results',
        type=int,
        default=5,
        help='Number of search results (default: 5)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=1,
        help='Days to consolidate (default: 1)'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output in JSON format'
    )
    
    args = parser.parse_args()
    
    # Initialize memory
    memory = LocalSemanticMemory(
        workspace_path=args.workspace,
        shared=args.shared
    )
    
    if args.command == 'add':
        if not args.text:
            print("❌ Text required for add command")
            sys.exit(1)
        
        memory_id = memory.add(args.text, category=args.category)
        
        if args.json:
            print(json.dumps({"memory_id": memory_id, "text": args.text}))
    
    elif args.command == 'search':
        if not args.text:
            print("❌ Query text required for search command")
            sys.exit(1)
        
        results = memory.search(args.text, n_results=args.n_results, category=args.category if args.category != 'general' else None)
        
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(f"\n🔍 Search results for: '{args.text}'")
            print(f"   Found {len(results)} relevant memories\n")
            
            for i, result in enumerate(results, 1):
                print(f"--- Result {i} of {len(results)} ---")
                print(f"Text: {result['text']}")
                print(f"Category: {result['metadata']['category']}")
                print(f"Workspace: {result['metadata'].get('workspace', 'unknown')}")
                print(f"Agent: {result['metadata'].get('agent_id', 'unknown')}")
                print(f"Similarity: {1 - result['distance']:.3f}")
                print(f"Timestamp: {result['metadata']['timestamp']}")
                print()
    
    elif args.command == 'consolidate':
        memory.consolidate(days=args.days)
    
    elif args.command == 'stats':
        stats = memory.stats()
        
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print(f"\n📊 Memory Statistics")
            print(f"   Current workspace: {stats['current_workspace']}")
            print(f"   Current agent: {stats['current_agent']}")
            print(f"   Shared memory: {stats['is_shared']}")
            print(f"   Total memories: {stats['total_memories']}")
            print(f"   Vector DB: {stats['vector_db_path']}\n")

            if stats['by_category']:
                print(f"   By Category:")
                for cat, count in sorted(stats['by_category'].items()):
                    print(f"     {cat}: {count}")
                print()

            if stats['by_workspace']:
                print(f"   By Workspace:")
                for ws, count in sorted(stats['by_workspace'].items()):
                    print(f"     {ws}: {count}")
                print()

            if stats['by_agent']:
                print(f"   By Agent:")
                for agent, count in sorted(stats['by_agent'].items()):
                    print(f"     {agent}: {count}")
                print()
    
    elif args.command == 'delete':
        if not args.text:
            print("❌ Memory ID required for delete command")
            sys.exit(1)
        memory.delete(args.text)
    
    elif args.command == 'clear':
        if args.category == 'general':
            print("❌ Must specify --category to clear")
            sys.exit(1)
        memory.clear_category(args.category)


if __name__ == "__main__":
    main()
