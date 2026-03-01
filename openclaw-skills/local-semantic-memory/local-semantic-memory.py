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
- Hybrid search (vector + FTS5 keyword) with RRF fusion
- Intent-aware search routing
- Deduplication (exact hash + near-duplicate detection)
- Memory decay with confidence tracking
- Optional LLM reranking via Ollama
- Error correction with retract-and-replace audit trail
- Structured lesson-learned recording

Usage:
    # Auto-detect workspace from environment
    uv run local-semantic-memory.py add "User prefers Python"

    # Explicit workspace
    uv run local-semantic-memory.py --workspace ~/.openclaw/workspace-research add "Deep research findings"

    # Shared memory across all agents
    uv run local-semantic-memory.py --shared add "Company-wide knowledge"

    # Search in specific workspace
    uv run local-semantic-memory.py --workspace ~/.openclaw/workspace-coding search "Python best practices"

    # Search with intent display
    uv run local-semantic-memory.py search "who is my doctor?" --show-intent

    # Search with LLM reranking
    uv run local-semantic-memory.py search "meeting schedule" --rerank

    # Decay stale memories
    uv run local-semantic-memory.py decay --dry-run --age-days 30

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
import re
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import hashlib
import socket


class LocalSemanticMemory:
    """Workspace-aware semantic memory manager"""

    # --- Phase 1: Intent classification patterns ---
    _INTENT_PATTERNS = {
        "WHO": (
            re.compile(r'\b(who|person|people|family|doctor|dentist|boss|manager|team|colleague)\b', re.I),
            0.5, 0.5
        ),
        "WHEN": (
            re.compile(r'\b(when|date|time|schedule|deadline|appointment|meeting\s+time|birthday|anniversary)\b', re.I),
            0.4, 0.6
        ),
        "WHERE": (
            re.compile(r'\b(where|location|address|place|office|room|building|city)\b', re.I),
            0.5, 0.5
        ),
        "PREFERENCE": (
            re.compile(r'\b(likes?|prefers?|preference|favorite|favourite|enjoys?|hates?|dislikes?|wants?)\b', re.I),
            0.8, 0.2
        ),
    }
    _DEFAULT_WEIGHTS = (0.7, 0.3)  # (vector_weight, fts_weight)

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

        # Ensure workspace exists with restricted permissions
        if not self.workspace_path.exists():
            print(f"⚠️  Workspace not found: {self.workspace_path}")
            print(f"   Creating workspace directory...")
            self.workspace_path.mkdir(parents=True, exist_ok=True, mode=0o700)
        else:
            self.workspace_path.chmod(0o700)

        # Vector DB location (within workspace)
        self.vector_db_path = self.workspace_path / "vector_db"
        self.vector_db_path.mkdir(parents=True, exist_ok=True, mode=0o700)

        # Memory logs location
        self.memory_path = self.workspace_path / "memory"
        self.memory_path.mkdir(parents=True, exist_ok=True, mode=0o700)

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

        # --- Phase 2: Initialize FTS5 ---
        self.fts_db_path = self.workspace_path / "memory.db"
        self._init_fts_schema()
        self._backfill_fts()

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
                print(f"❌ Error: Workspace is outside standard OpenClaw directories", file=sys.stderr)
                print(f"   Path: {workspace_path_resolved}", file=sys.stderr)
                print(f"   Expected under: {openclaw_base}", file=sys.stderr)
                print(f"   Use --workspace with a path under ~/.openclaw/ or set OPENCLAW_WORKSPACE", file=sys.stderr)
                sys.exit(1)
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

    # --- Phase 1: Intent-Aware Search Routing ---

    def _classify_intent(self, query: str) -> Tuple[str, float, float]:
        """
        Classify query intent to adjust vector/FTS weight balance.

        Returns:
            (intent_name, vector_weight, fts_weight)
        """
        for intent_name, (pattern, vw, fw) in self._INTENT_PATTERNS.items():
            if pattern.search(query):
                return (intent_name, vw, fw)
        return ("DEFAULT", *self._DEFAULT_WEIGHTS)

    # --- Phase 2: FTS5 Keyword Search + Hybrid RRF Fusion ---

    def _init_fts_schema(self):
        """Create FTS5 and hash tables if they don't exist."""
        conn = sqlite3.connect(str(self.fts_db_path))
        try:
            conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5("
                "doc_id, text, keywords, tokenize='porter unicode61')"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS memory_hashes ("
                "doc_id TEXT PRIMARY KEY, "
                "content_hash TEXT NOT NULL, "
                "created_at TEXT NOT NULL)"
            )
            # Index may already exist; ignore error
            try:
                conn.execute("CREATE INDEX idx_content_hash ON memory_hashes(content_hash)")
            except sqlite3.OperationalError:
                pass
            conn.commit()
        finally:
            conn.close()

    def _backfill_fts(self):
        """One-time backfill: sync existing ChromaDB docs into FTS5."""
        total = self.collection.count()
        if total == 0:
            return

        conn = sqlite3.connect(str(self.fts_db_path))
        try:
            existing = {row[0] for row in conn.execute("SELECT doc_id FROM memories_fts").fetchall()}
            all_data = self.collection.get()
            added = 0
            for doc_id, doc in zip(all_data['ids'], all_data['documents']):
                if doc_id in existing:
                    continue
                keywords = " ".join(set(re.findall(r'\b\w{3,}\b', doc.lower())))
                content_hash = hashlib.sha256(doc.strip().lower().encode()).hexdigest()
                conn.execute(
                    "INSERT INTO memories_fts(doc_id, text, keywords) VALUES (?, ?, ?)",
                    (doc_id, doc, keywords)
                )
                conn.execute(
                    "INSERT OR IGNORE INTO memory_hashes(doc_id, content_hash, created_at) VALUES (?, ?, ?)",
                    (doc_id, content_hash, datetime.now().isoformat())
                )
                added += 1
            if added:
                conn.commit()
                print(f"  FTS5 backfill: indexed {added} existing memories")
        finally:
            conn.close()

    def _fts_insert(self, doc_id: str, text: str):
        """Insert a document into FTS5 and hash tables."""
        keywords = " ".join(set(re.findall(r'\b\w{3,}\b', text.lower())))
        content_hash = hashlib.sha256(text.strip().lower().encode()).hexdigest()
        conn = sqlite3.connect(str(self.fts_db_path))
        try:
            conn.execute(
                "INSERT INTO memories_fts(doc_id, text, keywords) VALUES (?, ?, ?)",
                (doc_id, text, keywords)
            )
            conn.execute(
                "INSERT OR IGNORE INTO memory_hashes(doc_id, content_hash, created_at) VALUES (?, ?, ?)",
                (doc_id, content_hash, datetime.now().isoformat())
            )
            conn.commit()
        finally:
            conn.close()

    def _fts_delete(self, doc_ids: List[str]):
        """Delete documents from FTS5 and hash tables."""
        if not doc_ids:
            return
        conn = sqlite3.connect(str(self.fts_db_path))
        try:
            placeholders = ",".join("?" for _ in doc_ids)
            conn.execute(f"DELETE FROM memories_fts WHERE doc_id IN ({placeholders})", doc_ids)
            conn.execute(f"DELETE FROM memory_hashes WHERE doc_id IN ({placeholders})", doc_ids)
            conn.commit()
        finally:
            conn.close()

    def _fts_query(self, query: str, n_results: int = 10, category: Optional[str] = None) -> List[Tuple[str, float]]:
        """
        Query FTS5 index. Returns list of (doc_id, bm25_score).
        Lower bm25 = more relevant (negative values from bm25()).
        """
        # Tokenize query for FTS5 match
        tokens = re.findall(r'\b\w{2,}\b', query.lower())
        if not tokens:
            return []
        fts_expr = " OR ".join(tokens)

        conn = sqlite3.connect(str(self.fts_db_path))
        try:
            rows = conn.execute(
                "SELECT doc_id, bm25(memories_fts) AS score "
                "FROM memories_fts WHERE memories_fts MATCH ? "
                "ORDER BY score LIMIT ?",
                (fts_expr, n_results)
            ).fetchall()
            return [(row[0], row[1]) for row in rows]
        except sqlite3.OperationalError:
            # Malformed FTS query — fall back gracefully
            return []
        finally:
            conn.close()

    def _rrf_fuse(
        self,
        vector_results: List[Dict[str, Any]],
        fts_results: List[Tuple[str, float]],
        vector_weight: float,
        fts_weight: float,
        n_results: int
    ) -> List[Dict[str, Any]]:
        """
        Reciprocal Rank Fusion of vector and FTS results.

        score(d) = vector_weight / (60 + rank_vector) + fts_weight / (60 + rank_fts)
        """
        k = 60  # RRF constant

        # Build rank maps
        vector_rank = {}
        vector_lookup = {}
        for rank, mem in enumerate(vector_results):
            vector_rank[mem['id']] = rank
            vector_lookup[mem['id']] = mem

        fts_rank = {}
        for rank, (doc_id, _score) in enumerate(fts_results):
            fts_rank[doc_id] = rank

        # Collect all candidate IDs
        all_ids = set(vector_rank.keys()) | set(fts_rank.keys())

        # For FTS-only results we need to fetch full data from ChromaDB
        fts_only_ids = [did for did in fts_rank if did not in vector_lookup]
        if fts_only_ids:
            try:
                fetched = self.collection.get(ids=fts_only_ids)
                for i, doc_id in enumerate(fetched['ids']):
                    vector_lookup[doc_id] = {
                        "text": fetched['documents'][i],
                        "distance": 1.0,  # unknown vector distance
                        "metadata": fetched['metadatas'][i],
                        "id": doc_id
                    }
            except Exception:
                pass

        # Compute RRF scores
        scored = []
        for doc_id in all_ids:
            if doc_id not in vector_lookup:
                continue
            vr = vector_rank.get(doc_id, len(vector_results) + 100)
            fr = fts_rank.get(doc_id, len(fts_results) + 100)
            rrf_score = vector_weight / (k + vr) + fts_weight / (k + fr)
            entry = dict(vector_lookup[doc_id])
            entry['rrf_score'] = round(rrf_score, 6)
            scored.append(entry)

        scored.sort(key=lambda x: x['rrf_score'], reverse=True)
        return scored[:n_results]

    # --- Phase 3: Deduplication ---

    def _check_exact_duplicate(self, text: str) -> Optional[str]:
        """Check for exact content duplicate via SHA256 hash. Returns existing doc_id or None."""
        content_hash = hashlib.sha256(text.strip().lower().encode()).hexdigest()
        conn = sqlite3.connect(str(self.fts_db_path))
        try:
            row = conn.execute(
                "SELECT doc_id FROM memory_hashes WHERE content_hash = ? LIMIT 1",
                (content_hash,)
            ).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def _check_near_duplicate(self, embedding: List[float], threshold: float = 0.95) -> Optional[Tuple[str, float]]:
        """
        Check for near-duplicate via vector similarity.

        Returns (doc_id, similarity) if similarity >= threshold, else None.
        Warns (but allows) for similarity in [0.88, threshold).
        """
        if self.collection.count() == 0:
            return None

        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=3
        )
        if not results['distances'] or not results['distances'][0]:
            return None

        for i, dist in enumerate(results['distances'][0]):
            similarity = 1 - dist  # cosine distance → similarity
            doc_id = results['ids'][0][i]
            if similarity >= threshold:
                return (doc_id, similarity)
            if similarity >= 0.88:
                print(f"⚠️  Near-duplicate detected (similarity {similarity:.3f}): {results['documents'][0][i][:60]}...")
        return None

    # --- Phase 4: Memory Decay ---

    def _touch_results(self, results: List[Dict[str, Any]]):
        """Update last_accessed and access_count for returned search results."""
        if not results:
            return
        now = datetime.now().isoformat()
        ids_to_update = [r['id'] for r in results]
        try:
            existing = self.collection.get(ids=ids_to_update)
            for i, doc_id in enumerate(existing['ids']):
                meta = dict(existing['metadatas'][i])
                meta['last_accessed'] = now
                meta['access_count'] = meta.get('access_count', 0) + 1
                self.collection.update(ids=[doc_id], metadatas=[meta])
        except Exception:
            pass  # Non-critical — don't fail search if touch fails

    def decay(self, dry_run: bool = False, threshold: float = 0.15, age_days: int = 30) -> Dict[str, Any]:
        """
        Decay stale memories: reduce confidence for unaccessed memories, delete if below threshold.

        Args:
            dry_run: If True, report what would happen without changing anything.
            threshold: Delete memories with confidence below this value.
            age_days: Only consider memories not accessed in this many days.

        Returns:
            Summary dict with counts.
        """
        cutoff = (datetime.now() - timedelta(days=age_days)).isoformat()
        total = self.collection.count()
        if total == 0:
            print("  No memories to decay.")
            return {"decayed": 0, "deleted": 0, "protected": 0, "skipped": 0}

        all_data = self.collection.get()
        decayed = 0
        deleted = 0
        protected = 0
        skipped = 0
        delete_ids = []

        for i, doc_id in enumerate(all_data['ids']):
            meta = dict(all_data['metadatas'][i])
            confidence = meta.get('confidence', 1.0)
            if isinstance(confidence, str):
                try:
                    confidence = float(confidence)
                except ValueError:
                    confidence = 1.0
            pinned = meta.get('pinned', False)
            if isinstance(pinned, str):
                pinned = pinned.lower() == 'true'
            last_accessed = meta.get('last_accessed', meta.get('timestamp', ''))

            # Skip pinned
            if pinned:
                protected += 1
                continue

            # Skip recently accessed
            if last_accessed and last_accessed > cutoff:
                skipped += 1
                continue

            # Decay confidence
            new_confidence = round(confidence - 0.10, 2)
            if new_confidence < threshold:
                if dry_run:
                    print(f"  [DRY RUN] Would delete: {all_data['documents'][i][:60]}... (confidence {new_confidence:.2f})")
                else:
                    delete_ids.append(doc_id)
                deleted += 1
            else:
                if dry_run:
                    print(f"  [DRY RUN] Would decay: {all_data['documents'][i][:60]}... ({confidence:.2f} → {new_confidence:.2f})")
                else:
                    meta['confidence'] = new_confidence
                    self.collection.update(ids=[doc_id], metadatas=[meta])
                decayed += 1

        # Batch delete
        if delete_ids and not dry_run:
            with self.lock:
                self.collection.delete(ids=delete_ids)
                self._fts_delete(delete_ids)

        summary = {
            "decayed": decayed,
            "deleted": deleted,
            "protected": protected,
            "skipped": skipped,
            "total_evaluated": total
        }

        label = "[DRY RUN] " if dry_run else ""
        print(f"\n{label}Decay summary:")
        print(f"  Decayed (confidence reduced): {decayed}")
        print(f"  Deleted (below threshold {threshold}): {deleted}")
        print(f"  Protected (pinned): {protected}")
        print(f"  Skipped (recently accessed): {skipped}")
        return summary

    # --- Phase 5: LLM Reranking ---

    def _detect_rerank_model(self) -> Optional[str]:
        """Auto-detect a suitable Ollama model for reranking."""
        preferred = ['qwen2.5', 'llama3.2', 'mistral', 'phi3', 'gemma2']
        try:
            models = self.ollama_client.list()
            available = []
            if isinstance(models, dict):
                available = [m.get('name', m.get('model', '')) for m in models.get('models', [])]
            elif hasattr(models, 'models'):
                available = [m.model for m in models.models]
            for pref in preferred:
                for avail in available:
                    if pref in avail.lower():
                        return avail
            # Fall back to first available non-embed model
            for avail in available:
                if 'embed' not in avail.lower():
                    return avail
        except Exception:
            pass
        return None

    def _llm_rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        model: Optional[str] = None,
        top_n: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Rerank candidates using a local Ollama model.

        Sends top candidates to the model, asks for relevance ratings 0-5,
        blends 50/50 with original RRF score.
        """
        if not candidates:
            return candidates

        if model is None:
            model = self._detect_rerank_model()
        if model is None:
            print("⚠️  No reranking model available. Returning hybrid results.")
            return candidates

        # Take top candidates for reranking
        to_rerank = candidates[:top_n]

        # Build prompt
        docs_text = "\n".join(
            f"[{i}] {c['text'][:200]}" for i, c in enumerate(to_rerank)
        )
        prompt = (
            f"Rate the relevance of each document to the query on a scale of 0-5 "
            f"(0=irrelevant, 5=highly relevant). Return ONLY a JSON array of integers.\n\n"
            f"Query: {query}\n\nDocuments:\n{docs_text}\n\n"
            f"Return a JSON array of {len(to_rerank)} integers, e.g. [3, 5, 1, ...]"
        )

        try:
            response = self.ollama_client.generate(model=model, prompt=prompt, stream=False)
            text = response.get('response', '') if isinstance(response, dict) else str(response)

            # Extract JSON array from response
            match = re.search(r'\[[\d,\s]+\]', text)
            if not match:
                print("⚠️  Reranker returned unparseable response. Using hybrid scores.")
                return candidates

            ratings = json.loads(match.group())
            if len(ratings) != len(to_rerank):
                print(f"⚠️  Reranker returned {len(ratings)} ratings for {len(to_rerank)} docs. Using hybrid scores.")
                return candidates

            # Blend: 50% original RRF + 50% LLM rating (normalized to 0-1)
            for i, cand in enumerate(to_rerank):
                llm_score = ratings[i] / 5.0
                original_rrf = cand.get('rrf_score', 0)
                cand['llm_rating'] = ratings[i]
                cand['rerank_score'] = round(0.5 * original_rrf + 0.5 * llm_score, 6)

            to_rerank.sort(key=lambda x: x.get('rerank_score', 0), reverse=True)

            # Append any candidates beyond top_n that weren't reranked
            remaining = candidates[top_n:]
            return to_rerank + remaining

        except Exception as e:
            print(f"⚠️  Reranking failed ({e}). Using hybrid scores.")
            return candidates

    # --- Core methods ---

    def add(
        self,
        text: str,
        category: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
        force: bool = False
    ) -> str:
        """Add a memory to the vector database with concurrent access protection"""

        # --- Phase 3: Dedup checks (before expensive embedding if exact match) ---
        if not force:
            existing_id = self._check_exact_duplicate(text)
            if existing_id:
                print(f"⚠️  Exact duplicate detected (ID: {existing_id}). Use --force to add anyway.")
                return existing_id

        # Generate embedding (outside lock - this is slow)
        embedding = self._generate_embedding(text)

        # --- Phase 3: Near-duplicate check ---
        if not force:
            near_dup = self._check_near_duplicate(embedding)
            if near_dup:
                doc_id, similarity = near_dup
                print(f"⚠️  Near-duplicate detected (similarity {similarity:.3f}, ID: {doc_id}). Use --force to add anyway.")
                return doc_id

        # Generate ID
        memory_id = self._generate_id(text, category)

        # Prepare metadata with agent tracking + Phase 4 fields
        now = datetime.now().isoformat()
        meta = {
            "category": category,
            "timestamp": now,
            "workspace": str(self.workspace_path.name),
            "agent_id": self.agent_id,
            "confidence": 1.0,
            "access_count": 0,
            "last_accessed": now,
            "pinned": False,
            "content_hash": hashlib.sha256(text.strip().lower().encode()).hexdigest(),
        }
        if metadata:
            meta.update(metadata)

        # Add to ChromaDB + FTS5 with lock protection and retry logic
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
                    self._fts_insert(memory_id, text)
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
        category: Optional[str] = None,
        show_intent: bool = False,
        rerank: bool = False,
        rerank_model: Optional[str] = None,
        include_retracted: bool = False
    ) -> List[Dict[str, Any]]:
        """Search memories by hybrid vector + FTS5 similarity with RRF fusion."""

        # Phase 1: Intent classification
        intent_name, vector_weight, fts_weight = self._classify_intent(query)
        if show_intent:
            print(f"  Intent: {intent_name} (vector={vector_weight}, fts={fts_weight})")

        # Oversample 2x from each source for better fusion (extra buffer for retracted filtering)
        oversample = n_results * (2 if include_retracted else 3)

        # Generate query embedding
        query_embedding = self._generate_embedding(query)

        # Prepare filter
        where = {"category": category} if category else None

        # Vector search via ChromaDB
        vector_results_raw = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=oversample,
            where=where
        )

        vector_results = []
        if vector_results_raw['documents'] and vector_results_raw['documents'][0]:
            for i, doc in enumerate(vector_results_raw['documents'][0]):
                memory = {
                    "text": doc,
                    "distance": vector_results_raw['distances'][0][i],
                    "metadata": vector_results_raw['metadatas'][0][i],
                    "id": vector_results_raw['ids'][0][i]
                }
                vector_results.append(memory)

        # FTS5 keyword search
        fts_results = self._fts_query(query, n_results=oversample, category=category)

        # RRF fusion
        if fts_results:
            memories = self._rrf_fuse(vector_results, fts_results, vector_weight, fts_weight, n_results)
        else:
            # No FTS results — fall back to vector-only
            memories = vector_results[:n_results]
            for m in memories:
                m['rrf_score'] = round(1.0 / (60 + vector_results.index(m)), 6)

        # Filter out retracted memories unless explicitly requested
        if not include_retracted:
            before = len(memories)
            memories = [m for m in memories if not self._is_retracted(m)]
            filtered = before - len(memories)
            if filtered:
                print(f"  (Excluded {filtered} retracted memor{'y' if filtered == 1 else 'ies'}. Use --include-retracted to show.)")
        else:
            # Mark retracted entries visually
            for m in memories:
                if self._is_retracted(m):
                    m['retracted'] = True

        # Trim to requested count after filtering
        memories = memories[:n_results]

        # Phase 5: Optional LLM reranking
        if rerank and memories:
            memories = self._llm_rerank(query, memories, model=rerank_model)
            memories = memories[:n_results]

        # Phase 4: Touch results (update access tracking)
        self._touch_results(memories)

        # Add confidence to output
        for m in memories:
            m['confidence'] = m.get('metadata', {}).get('confidence', 1.0)

        return memories

    def _is_retracted(self, memory: Dict[str, Any]) -> bool:
        """Check if a memory has been retracted."""
        meta = memory.get('metadata', {})
        retracted = meta.get('retracted', False)
        if isinstance(retracted, str):
            return retracted.lower() == 'true'
        return bool(retracted)

    def consolidate(self, days: int = 1):
        """Consolidate recent daily logs into semantic memory with concurrent access protection"""

        print(f"\n📋 Consolidating last {days} day(s) of logs...")

        # Find recent log files
        cutoff = datetime.now() - timedelta(days=days)

        log_files = []
        memory_path_resolved = self.memory_path.resolve()
        for log_file in self.memory_path.glob("*.md"):
            # Skip symlinks and files that resolve outside the memory directory
            if log_file.is_symlink():
                continue
            if not str(log_file.resolve()).startswith(str(memory_path_resolved) + os.sep):
                continue
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
                                embedding = self._generate_embedding(fact)
                                memory_id = self._generate_id(fact, "episodic")
                                now = datetime.now().isoformat()
                                meta = {
                                    "category": "episodic",
                                    "timestamp": now,
                                    "workspace": str(self.workspace_path.name),
                                    "agent_id": self.agent_id,
                                    "source": log_file.name,
                                    "consolidated": True,
                                    "confidence": 1.0,
                                    "access_count": 0,
                                    "last_accessed": now,
                                    "pinned": False,
                                    "content_hash": hashlib.sha256(fact.strip().lower().encode()).hexdigest(),
                                }
                                self.collection.add(
                                    ids=[memory_id],
                                    embeddings=[embedding],
                                    documents=[fact],
                                    metadatas=[meta]
                                )
                                self._fts_insert(memory_id, fact)
                                consolidated += 1
                            except Exception as e:
                                print(f"    ⚠️  Failed to add: {fact[:40]}... ({e})")

        print(f"✓ Consolidated {consolidated} memories from {len(log_files)} log(s)")

    def stats(self) -> Dict[str, Any]:
        """Get memory statistics including agent tracking and decay info"""

        total = self.collection.count()

        # Get all metadatas to analyze
        if total > 0:
            all_data = self.collection.get()
            categories = {}
            workspaces = {}
            agents = {}
            total_confidence = 0.0
            decay_eligible = 0
            pinned_count = 0
            retracted_count = 0
            corrections_count = 0
            lessons_count = 0
            cutoff_30d = (datetime.now() - timedelta(days=30)).isoformat()

            for meta in all_data['metadatas']:
                cat = meta.get('category', 'unknown')
                ws = meta.get('workspace', 'unknown')
                agent = meta.get('agent_id', 'unknown')
                categories[cat] = categories.get(cat, 0) + 1
                workspaces[ws] = workspaces.get(ws, 0) + 1
                agents[agent] = agents.get(agent, 0) + 1

                conf = meta.get('confidence', 1.0)
                if isinstance(conf, str):
                    try:
                        conf = float(conf)
                    except ValueError:
                        conf = 1.0
                total_confidence += conf

                pinned = meta.get('pinned', False)
                if isinstance(pinned, str):
                    pinned = pinned.lower() == 'true'
                if pinned:
                    pinned_count += 1

                retracted = meta.get('retracted', False)
                if isinstance(retracted, str):
                    retracted = retracted.lower() == 'true'
                if retracted:
                    retracted_count += 1

                if meta.get('corrects_id'):
                    corrections_count += 1
                if meta.get('is_lesson'):
                    is_lesson = meta['is_lesson']
                    if isinstance(is_lesson, str):
                        is_lesson = is_lesson.lower() == 'true'
                    if is_lesson:
                        lessons_count += 1

                last_accessed = meta.get('last_accessed', meta.get('timestamp', ''))
                if not pinned and last_accessed and last_accessed < cutoff_30d:
                    decay_eligible += 1

            avg_confidence = round(total_confidence / total, 3) if total else 0
        else:
            categories = {}
            workspaces = {}
            agents = {}
            avg_confidence = 0
            decay_eligible = 0
            pinned_count = 0
            retracted_count = 0
            corrections_count = 0
            lessons_count = 0

        # FTS5 count
        fts_count = 0
        try:
            conn = sqlite3.connect(str(self.fts_db_path))
            row = conn.execute("SELECT COUNT(*) FROM memories_fts").fetchone()
            fts_count = row[0] if row else 0
            conn.close()
        except Exception:
            pass

        return {
            "total_memories": total,
            "fts_indexed": fts_count,
            "by_category": categories,
            "by_workspace": workspaces,
            "by_agent": agents,
            "avg_confidence": avg_confidence,
            "decay_eligible": decay_eligible,
            "pinned": pinned_count,
            "retracted": retracted_count,
            "corrections": corrections_count,
            "lessons": lessons_count,
            "current_workspace": str(self.workspace_path.name),
            "current_agent": self.agent_id,
            "vector_db_path": str(self.vector_db_path),
            "fts_db_path": str(self.fts_db_path),
            "is_shared": self.workspace_path.name == "shared"
        }

    def correct(self, memory_id: str, corrected_text: str, reason: str = "") -> str:
        """
        Retract an incorrect memory and replace it with a correction.

        The original memory is kept but marked as retracted (excluded from
        normal search). A new correction memory is created linking back to
        the original, preserving the audit trail.

        Args:
            memory_id: ID of the incorrect memory to retract.
            corrected_text: The corrected information.
            reason: Optional explanation of what was wrong.

        Returns:
            ID of the new correction memory.
        """
        # Fetch the original memory
        try:
            original = self.collection.get(ids=[memory_id])
        except Exception as e:
            print(f"❌ Could not fetch memory {memory_id}: {e}")
            sys.exit(1)

        if not original['ids']:
            print(f"❌ Memory not found: {memory_id}")
            sys.exit(1)

        original_text = original['documents'][0]
        original_meta = dict(original['metadatas'][0])
        original_category = original_meta.get('category', 'general')

        # Mark the original as retracted
        now = datetime.now().isoformat()
        original_meta['retracted'] = True
        original_meta['retracted_at'] = now
        original_meta['retracted_by_agent'] = self.agent_id
        if reason:
            original_meta['retraction_reason'] = reason

        # Add the correction memory first (so we have its ID for the link)
        correction_meta = {
            "corrects_id": memory_id,
            "original_text": original_text[:500],
        }
        if reason:
            correction_meta["correction_reason"] = reason

        correction_id = self.add(
            corrected_text,
            category=original_category,
            metadata=correction_meta,
            force=True  # bypass dedup — correction may be similar to original
        )

        # Now update the original with the retraction + link to correction
        original_meta['replaced_by'] = correction_id
        with self.lock:
            self.collection.update(ids=[memory_id], metadatas=[original_meta])

        print(f"\n✓ Correction applied:")
        print(f"  Retracted: {original_text[:60]}... ({memory_id})")
        print(f"  Replaced with: {corrected_text[:60]}... ({correction_id})")
        if reason:
            print(f"  Reason: {reason}")

        return correction_id

    def lesson(self, text: str, mistake: str = "", category: str = "lesson") -> str:
        """
        Record a structured lesson learned.

        Args:
            text: The lesson / correct approach.
            mistake: What went wrong (optional context).
            category: Category for the memory (default: "lesson").

        Returns:
            ID of the lesson memory.
        """
        # Build structured text that embeds both the lesson and mistake context
        if mistake:
            structured = f"LESSON: {text} | MISTAKE: {mistake}"
        else:
            structured = f"LESSON: {text}"

        meta = {"is_lesson": True}
        if mistake:
            meta["mistake"] = mistake

        lesson_id = self.add(structured, category=category, metadata=meta, force=True)
        if mistake:
            print(f"  Mistake: {mistake[:80]}")
        return lesson_id

    def delete(self, memory_id: str):
        """Delete a specific memory from ChromaDB and FTS5"""
        self.collection.delete(ids=[memory_id])
        self._fts_delete([memory_id])
        print(f"✓ Deleted memory: {memory_id}")

    def clear_category(self, category: str):
        """Clear all memories in a category from ChromaDB and FTS5"""
        # Get all IDs for this category
        results = self.collection.get(where={"category": category})
        if results['ids']:
            self.collection.delete(ids=results['ids'])
            self._fts_delete(results['ids'])
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

  # Search with intent display
  uv run local-semantic-memory.py search "who is my doctor?" --show-intent

  # Search with LLM reranking
  uv run local-semantic-memory.py search "meeting schedule" --rerank

  # Decay stale memories
  uv run local-semantic-memory.py decay --dry-run --age-days 30

  # Correct a wrong memory
  uv run local-semantic-memory.py correct "The correct info" --memory-id abc123 --reason "Was outdated"

  # Record a lesson learned
  uv run local-semantic-memory.py lesson "Always validate input before DB insert" --mistake "Stored raw user input"

  # Search including retracted memories
  uv run local-semantic-memory.py search "some query" --include-retracted

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
        choices=['add', 'search', 'consolidate', 'stats', 'delete', 'clear', 'decay', 'correct', 'lesson'],
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
    # Phase 1
    parser.add_argument(
        '--show-intent',
        action='store_true',
        help='Show detected query intent and weight balance'
    )
    # Phase 3
    parser.add_argument(
        '--force',
        action='store_true',
        help='Bypass deduplication checks on add'
    )
    # Phase 4
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview decay actions without applying them'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=0.15,
        help='Confidence threshold for decay deletion (default: 0.15)'
    )
    parser.add_argument(
        '--age-days',
        type=int,
        default=30,
        help='Days since last access before decay applies (default: 30)'
    )
    # Phase 5
    parser.add_argument(
        '--rerank',
        action='store_true',
        help='Enable LLM reranking of search results (requires Ollama model)'
    )
    parser.add_argument(
        '--rerank-model',
        default=None,
        help='Ollama model for reranking (auto-detected if not set)'
    )
    # Correction / lesson
    parser.add_argument(
        '--memory-id',
        default=None,
        help='Memory ID to correct (used with correct command)'
    )
    parser.add_argument(
        '--reason',
        default='',
        help='Explanation of what was wrong (used with correct/lesson commands)'
    )
    parser.add_argument(
        '--mistake',
        default='',
        help='What went wrong (used with lesson command)'
    )
    parser.add_argument(
        '--include-retracted',
        action='store_true',
        help='Include retracted memories in search results'
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

        memory_id = memory.add(args.text, category=args.category, force=args.force)

        if args.json:
            print(json.dumps({"memory_id": memory_id, "text": args.text}))

    elif args.command == 'search':
        if not args.text:
            print("❌ Query text required for search command")
            sys.exit(1)

        results = memory.search(
            args.text,
            n_results=args.n_results,
            category=args.category if args.category != 'general' else None,
            show_intent=args.show_intent,
            rerank=args.rerank,
            rerank_model=args.rerank_model,
            include_retracted=args.include_retracted
        )

        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(f"\n🔍 Search results for: '{args.text}'")
            print(f"   Found {len(results)} relevant memories\n")

            for i, result in enumerate(results, 1):
                meta = result['metadata']
                # Visual indicators for special memory types
                prefix = ""
                if result.get('retracted') or meta.get('retracted'):
                    prefix = "[RETRACTED] "
                elif meta.get('corrects_id'):
                    prefix = "[CORRECTION] "
                elif meta.get('is_lesson'):
                    prefix = "[LESSON] "

                print(f"--- Result {i} of {len(results)} ---")
                print(f"Text: {prefix}{result['text']}")
                print(f"Category: {meta['category']}")
                print(f"Workspace: {meta.get('workspace', 'unknown')}")
                print(f"Agent: {meta.get('agent_id', 'unknown')}")
                print(f"Similarity: {1 - result['distance']:.3f}")
                print(f"Confidence: {result.get('confidence', 'N/A')}")
                if 'rrf_score' in result:
                    print(f"RRF Score: {result['rrf_score']}")
                if 'rerank_score' in result:
                    print(f"Rerank Score: {result['rerank_score']} (LLM rating: {result.get('llm_rating', '?')})")
                print(f"Timestamp: {meta['timestamp']}")
                # Show correction chain info
                if meta.get('corrects_id'):
                    print(f"Corrects: {meta['corrects_id']}")
                if meta.get('replaced_by'):
                    print(f"Replaced by: {meta['replaced_by']}")
                if meta.get('correction_reason') or meta.get('retraction_reason'):
                    print(f"Reason: {meta.get('correction_reason') or meta.get('retraction_reason')}")
                if meta.get('mistake'):
                    print(f"Mistake: {meta['mistake']}")
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
            print(f"   FTS5 indexed: {stats['fts_indexed']}")
            print(f"   Avg confidence: {stats['avg_confidence']}")
            print(f"   Decay eligible: {stats['decay_eligible']}")
            print(f"   Pinned: {stats['pinned']}")
            print(f"   Retracted: {stats['retracted']}")
            print(f"   Corrections: {stats['corrections']}")
            print(f"   Lessons: {stats['lessons']}")
            print(f"   Vector DB: {stats['vector_db_path']}")
            print(f"   FTS DB: {stats['fts_db_path']}\n")

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

    elif args.command == 'decay':
        memory.decay(
            dry_run=args.dry_run,
            threshold=args.threshold,
            age_days=args.age_days
        )

    elif args.command == 'correct':
        if not args.memory_id:
            print("❌ --memory-id required for correct command")
            sys.exit(1)
        if not args.text:
            print("❌ Corrected text required for correct command")
            sys.exit(1)
        correction_id = memory.correct(args.memory_id, args.text, reason=args.reason)
        if args.json:
            print(json.dumps({"correction_id": correction_id, "retracted_id": args.memory_id}))

    elif args.command == 'lesson':
        if not args.text:
            print("❌ Lesson text required for lesson command")
            sys.exit(1)
        lesson_id = memory.lesson(args.text, mistake=args.mistake, category=args.category)
        if args.json:
            print(json.dumps({"lesson_id": lesson_id, "text": args.text, "mistake": args.mistake}))


if __name__ == "__main__":
    main()
