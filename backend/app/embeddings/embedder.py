"""
embedder.py
===========
Handles the generation of text embeddings using SentenceTransformers.
"""

from typing import List
from sentence_transformers import SentenceTransformer
import sys
from pathlib import Path

# Add project root to sys.path to import config
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from config import cfg

class Embedder:
    def __init__(self, model_name: str = None):
        self.model_name = model_name or cfg.EMBEDDING_MODEL
        print(f"Loading embedding model: {self.model_name}...")
        self.model = SentenceTransformer(self.model_name)
        print("Model loaded successfully.")

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generates embeddings for a list of text strings."""
        # Convert to list of floats for ChromaDB compatibility
        embeddings = self.model.encode(texts, show_progress_bar=False)
        return [embedding.tolist() for embedding in embeddings]

    def embed_query(self, query: str) -> List[float]:
        """Generates an embedding for a single query string."""
        return self.embed_texts([query])[0]
