"""
vectordb.py
===========
Handles ChromaDB connections, collection creation, and upserts.
"""

import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any
import sys
from pathlib import Path

# Add project root to sys.path to import config
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from config import cfg

class VectorDB:
    def __init__(self, db_dir: str = None, collection_name: str = None):
        self.db_dir = db_dir or str(cfg.CHROMA_DB_DIR)
        self.collection_name = collection_name or cfg.CHROMA_COLLECTION
        
        print(f"Initializing ChromaDB client at {self.db_dir}...")
        self.client = chromadb.PersistentClient(path=self.db_dir)
        
        print(f"Getting or creating collection '{self.collection_name}'...")
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"} # Use cosine similarity
        )
        print(f"Collection initialized. Current item count: {self.collection.count()}")

    def upsert_chunks(self, ids: List[str], texts: List[str], embeddings: List[List[float]], metadatas: List[Dict[str, Any]]):
        """Upserts batches of chunks into the ChromaDB collection."""
        # Clean metadata: ChromaDB only accepts str, int, float, bool.
        # We need to ensure no dicts/lists or None values are passed in metadata.
        cleaned_metadatas = []
        for meta in metadatas:
            clean_meta = {}
            for k, v in meta.items():
                if v is None:
                    continue
                if isinstance(v, (str, int, float, bool)):
                    clean_meta[k] = v
                else:
                    clean_meta[k] = str(v)
            cleaned_metadatas.append(clean_meta)

        self.collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=cleaned_metadatas
        )

    def search(self, query_embedding: List[float], n_results: int = 5, where_filter: Dict[str, Any] = None):
        """Semantically searches the vector database."""
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )
        return results
