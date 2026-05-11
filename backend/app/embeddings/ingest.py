"""
ingest.py
=========
Reads chunked JSON data, generates embeddings, and saves into ChromaDB.
"""

import json
from pathlib import Path
import sys
from tqdm import tqdm

sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from config import cfg

from backend.app.embeddings.embedder import Embedder
from backend.app.embeddings.vectordb import VectorDB

def ingest_data(batch_size: int = 100):
    chunks_path = cfg.CHUNKS_FILE
    
    if not chunks_path.exists():
        print(f"Error: Chunks file not found at {chunks_path}")
        print("Please run Step 3 (chunker.py) first.")
        return

    print(f"Loading chunks from {chunks_path}...")
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    
    total_chunks = len(chunks)
    print(f"Found {total_chunks} chunks to ingest.")

    embedder = Embedder()
    vectordb = VectorDB()

    # Process in batches
    for i in tqdm(range(0, total_chunks, batch_size), desc="Ingesting Batches"):
        batch = chunks[i : i + batch_size]
        
        ids = [chunk["chunk_id"] for chunk in batch]
        texts = [chunk["text"] for chunk in batch]
        metadatas = [chunk.get("metadata", {}) for chunk in batch]
        
        # Generate embeddings
        embeddings = embedder.embed_texts(texts)
        
        # Upsert to ChromaDB
        vectordb.upsert_chunks(ids=ids, texts=texts, embeddings=embeddings, metadatas=metadatas)

    print(f"\nIngestion complete! Total chunks in DB: {vectordb.collection.count()}")

if __name__ == "__main__":
    ingest_data()
