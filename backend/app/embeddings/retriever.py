'''retriever.py
================
Utility for performing semantic retrieval over the HVAC chunks.
It uses the Embedder to turn a user query into an embedding and then
searches the ChromaDB collection via VectorDB.
'''

import sys
from pathlib import Path

# Ensure project root is on PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from config import cfg
from backend.app.embeddings.embedder import Embedder
from backend.app.embeddings.vectordb import VectorDB
from typing import List, Dict, Any


def retrieve(query: str, k: int = None, filter: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """Return the top‑k most similar chunks for *query*.

    Parameters
    ----------
    query: str
        Natural‑language query from the user.
    k: int, optional
        Number of results to return; defaults to cfg.TOP_K_RESULTS.
    filter: dict, optional
        Metadata filter passed to ChromaDB's ``where`` argument.

    Returns
    -------
    List[dict]
        Each dict contains ``chunk_id``, ``text``, ``metadata`` and ``score``
        (lower distance = higher similarity).
    """
    k = k or cfg.TOP_K_RESULTS

    embedder = Embedder()
    query_emb = embedder.embed_query(query)

    db = VectorDB()
    raw_results = db.search(query_embedding=query_emb, n_results=k, where_filter=filter)

    # Chroma returns a dict with parallel lists; collapse to a list of dicts.
    results = []
    for idx, doc in enumerate(raw_results["documents"][0]):
        meta = raw_results["metadatas"][0][idx]
        score = raw_results["distances"][0][idx]
        # The original chunk_id is stored in metadata (if present).
        chunk_id = meta.get("chunk_id", f"unknown_{idx}")
        results.append({
            "chunk_id": chunk_id,
            "text": doc,
            "metadata": meta,
            "score": score,
        })
    return results
