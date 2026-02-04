#!/usr/bin/env python3
"""
Semantic Memory Search with Ollama Embeddings

This module provides semantic search capabilities for memory files using
Ollama's embedding models. It indexes memory files and allows searching
based on semantic meaning rather than just keyword matching.

Usage:
    python memory_embed.py index          # Index all memory files
    python memory_embed.py search "query" # Search for semantically similar content
    python memory_embed.py stats          # Show index statistics
"""

import os
import sys
import json
import hashlib
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import requests

# Configuration
MEMORY_DIR = Path("/root/clawd/memory")
EMBEDDINGS_DIR = MEMORY_DIR / "search" / "embeddings"
INDEX_FILE = EMBEDDINGS_DIR / "index.json"
CHUNKS_DIR = EMBEDDINGS_DIR / "chunks"
OLLAMA_HOST = "http://localhost:11434"
EMBEDDING_MODEL = "embeddinggemma:300m"  # Gemma 300M for embeddings (307.58M params)
LLM_MODEL = "gemma:2b"
CHUNK_SIZE = 512
CHUNK_OVERLAP = 128
TOP_K = 5

class MemoryEmbedder:
    """Handles embedding generation and semantic search for memory files."""
    
    def __init__(self):
        self.embeddings_dir = EMBEDDINGS_DIR
        self.chunks_dir = CHUNKS_DIR
        self.index_file = INDEX_FILE
        self.index = self._load_index()
        
        # Ensure directories exist
        self.embeddings_dir.mkdir(parents=True, exist_ok=True)
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_index(self) -> Dict:
        """Load the embeddings index from disk."""
        if self.index_file.exists():
            with open(self.index_file, 'r') as f:
                return json.load(f)
        return {"files": {}, "version": "1.0", "last_updated": None}
    
    def _save_index(self):
        """Save the embeddings index to disk."""
        self.index["last_updated"] = datetime.now().isoformat()
        with open(self.index_file, 'w') as f:
            json.dump(self.index, f, indent=2)
    
    def _get_file_hash(self, filepath: Path) -> str:
        """Calculate MD5 hash of file content for change detection."""
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def _chunk_text(self, text: str, source_file: str) -> List[Dict]:
        """Split text into overlapping chunks with metadata."""
        chunks = []
        lines = text.split('\n')
        current_chunk = []
        current_size = 0
        chunk_index = 0
        
        for line_num, line in enumerate(lines):
            line_size = len(line)
            
            if current_size + line_size > CHUNK_SIZE and current_chunk:
                # Save current chunk
                chunk_text = '\n'.join(current_chunk)
                chunks.append({
                    "text": chunk_text,
                    "source_file": source_file,
                    "chunk_index": chunk_index,
                    "line_start": max(0, line_num - len(current_chunk)),
                    "line_end": line_num - 1,
                    "char_count": len(chunk_text)
                })
                chunk_index += 1
                
                # Start new chunk with overlap
                overlap_lines = current_chunk[-(CHUNK_OVERLAP // 50):]  # Approximate lines
                current_chunk = overlap_lines + [line]
                current_size = sum(len(l) for l in current_chunk)
            else:
                current_chunk.append(line)
                current_size += line_size
        
        # Don't forget the last chunk
        if current_chunk:
            chunk_text = '\n'.join(current_chunk)
            chunks.append({
                "text": chunk_text,
                "source_file": source_file,
                "chunk_index": chunk_index,
                "line_start": len(lines) - len(current_chunk),
                "line_end": len(lines) - 1,
                "char_count": len(chunk_text)
            })
        
        return chunks
    
    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding vector from Ollama API."""
        try:
            response = requests.post(
                f"{OLLAMA_HOST}/api/embeddings",
                json={
                    "model": EMBEDDING_MODEL,
                    "prompt": text[:4096]  # Limit text length for speed
                },
                timeout=120
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception as e:
            print(f"Error getting embedding: {e}")
            return None
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
    
    def _index_single_file(self, filepath: Path) -> bool:
        """Index a single memory file."""
        try:
            # Check if file needs re-indexing
            file_hash = self._get_file_hash(filepath)
            rel_path = str(filepath.relative_to(MEMORY_DIR))
            
            if rel_path in self.index["files"]:
                if self.index["files"][rel_path]["hash"] == file_hash:
                    print(f"  ✓ {rel_path} (unchanged)")
                    return True
            
            # Read and chunk the file
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            chunks = self._chunk_text(content, rel_path)
            chunk_embeddings = []
            
            print(f"  Indexing {rel_path} ({len(chunks)} chunks)...")
            
            for i, chunk in enumerate(chunks):
                embedding = self._get_embedding(chunk["text"])
                if embedding:
                    chunk_id = f"{rel_path}_{i}"
                    chunk["embedding_id"] = chunk_id
                    chunk["embedding"] = embedding
                    chunk_embeddings.append(chunk)
                    
                    # Save individual chunk file
                    chunk_file = self.chunks_dir / f"{hashlib.md5(chunk_id.encode()).hexdigest()}.json"
                    with open(chunk_file, 'w') as f:
                        json.dump(chunk, f)
            
            # Update index
            self.index["files"][rel_path] = {
                "hash": file_hash,
                "indexed_at": datetime.now().isoformat(),
                "chunk_count": len(chunk_embeddings),
                "file_size": filepath.stat().st_size
            }
            
            return True
            
        except Exception as e:
            print(f"  ✗ Error indexing {filepath}: {e}")
            return False
    
    def index_all(self):
        """Index all memory files in the memory directory."""
        print("🔍 Scanning memory files...")
        
        memory_files = []
        for ext in ['*.md', '*.json']:
            memory_files.extend(MEMORY_DIR.glob(ext))
        
        # Exclude system files
        memory_files = [f for f in memory_files 
                       if not f.name.startswith('.') 
                       and f.name not in ['memory-search.js', 'memory-search.py']]
        
        print(f"Found {len(memory_files)} files to index\n")
        
        success_count = 0
        for filepath in memory_files:
            if self._index_single_file(filepath):
                success_count += 1
        
        self._save_index()
        print(f"\n✅ Indexed {success_count}/{len(memory_files)} files")
        print(f"📁 Index saved to: {self.index_file}")
    
    def search(self, query: str, top_k: int = TOP_K) -> List[Dict]:
        """Perform semantic search across indexed memory files."""
        print(f"\n🔍 Searching for: \"{query}\"\n")
        
        # Get query embedding
        query_embedding = self._get_embedding(query)
        if not query_embedding:
            print("❌ Failed to get embedding for query")
            return []
        
        # Load all chunk embeddings and calculate similarity
        results = []
        chunk_files = list(self.chunks_dir.glob("*.json"))
        
        print(f"Scanning {len(chunk_files)} chunks...")
        
        for chunk_file in chunk_files:
            try:
                with open(chunk_file, 'r') as f:
                    chunk = json.load(f)
                
                similarity = self._cosine_similarity(query_embedding, chunk["embedding"])
                
                results.append({
                    "text": chunk["text"],
                    "source_file": chunk["source_file"],
                    "chunk_index": chunk["chunk_index"],
                    "line_start": chunk["line_start"],
                    "line_end": chunk["line_end"],
                    "similarity": similarity
                })
            except Exception as e:
                continue
        
        # Sort by similarity (highest first)
        results.sort(key=lambda x: x["similarity"], reverse=True)
        
        return results[:top_k]
    
    def format_results(self, results: List[Dict], query: str) -> str:
        """Format search results for display."""
        if not results:
            return f'No results found for "{query}"'
        
        output = f"🔍 Semantic search results for \"{query}\"\n"
        output += "=" * 60 + "\n\n"
        
        for i, result in enumerate(results, 1):
            similarity_pct = result["similarity"] * 100
            output += f"{i}. **{result['source_file']}** (Similarity: {similarity_pct:.1f}%)\n"
            output += f"   Lines {result['line_start']}-{result['line_end']}\n"
            
            # Format excerpt
            text = result["text"][:300] + "..." if len(result["text"]) > 300 else result["text"]
            output += f"   {text.replace(chr(10), chr(10) + '   ')}\n\n"
        
        return output
    
    def stats(self):
        """Display index statistics."""
        print("📊 Memory Index Statistics\n")
        print("=" * 40)
        
        total_files = len(self.index.get("files", {}))
        total_chunks = len(list(self.chunks_dir.glob("*.json")))
        
        print(f"Total indexed files: {total_files}")
        print(f"Total chunks: {total_chunks}")
        print(f"Embedding model: {EMBEDDING_MODEL}")
        print(f"Last updated: {self.index.get('last_updated', 'Never')}")
        
        if total_files > 0:
            print("\n📁 Indexed files:")
            for filepath, info in self.index["files"].items():
                print(f"  • {filepath} ({info['chunk_count']} chunks)")
    
    def clear_index(self):
        """Clear all indexed data."""
        import shutil
        
        if self.embeddings_dir.exists():
            shutil.rmtree(self.embeddings_dir)
            self.embeddings_dir.mkdir(parents=True, exist_ok=True)
            self.chunks_dir.mkdir(parents=True, exist_ok=True)
        
        self.index = {"files": {}, "version": "1.0", "last_updated": None}
        self._save_index()
        print("🗑️  Index cleared successfully")


def main():
    embedder = MemoryEmbedder()
    
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "index":
        embedder.index_all()
    
    elif command == "search":
        if len(sys.argv) < 3:
            print("Usage: python memory_embed.py search \"your query here\"")
            sys.exit(1)
        
        query = " ".join(sys.argv[2:])
        results = embedder.search(query)
        print(embedder.format_results(results, query))
    
    elif command == "stats":
        embedder.stats()
    
    elif command == "clear":
        embedder.clear_index()
    
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
