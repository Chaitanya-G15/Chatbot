# Member 2 — Embeddings & Vector DB

**Your job:** Take `data/chunks/chunks.json` (produced by Member 1) and load it
into a ChromaDB vector database with embeddings, so Member 3 can do similarity search.

---

## Prerequisites

Member 1 must have already run the ingestion pipeline so that
`data/chunks/chunks.json` exists and is populated.

---

## Setup

```powershell
# Activate the shared venv (or create your own)
venv\Scripts\activate

# Uncomment and install Member 2 deps in requirements.txt, then:
pip install chromadb sentence-transformers google-genai
```

Copy `.env.example` to `.env` and set:
```
GOOGLE_API_KEY=your_key_here
EMBEDDING_MODEL=models/text-embedding-004
CHROMA_DB_DIR=data/chroma_db
CHROMA_COLLECTION=hvac_manuals
```

---

## What to Build

Create `embeddings/embed_and_store.py` that:

1. **Loads chunks.json**
   ```python
   import json
   from config import cfg

   with open(cfg.CHUNKS_FILE) as f:
       chunks = json.load(f)
   ```

2. **Generates embeddings** using Google's text-embedding-004 (or sentence-transformers)

3. **Stores in ChromaDB** with the full metadata dict so Member 3 can filter by
   `brand`, `model`, `doc_type`, `page_number`, etc.
   ```python
   collection.add(
       ids=[c["chunk_id"] for c in batch],
       documents=[c["text"] for c in batch],
       embeddings=[...],
       metadatas=[c["metadata"] for c in batch],
   )
   ```

4. **Persists ChromaDB** to `data/chroma_db/` (set in config.py)

---

## Handoff to Member 3

After running your script, the ChromaDB database at `data/chroma_db/` is the
handoff artifact. Member 3 will load it with:
```python
import chromadb
from config import cfg
client = chromadb.PersistentClient(path=str(cfg.CHROMA_DB_DIR))
collection = client.get_collection(cfg.CHROMA_COLLECTION)
```

---

## Recommended Libraries

| Purpose | Library |
|---------|---------|
| Embeddings (cloud) | `google-genai` → `models/text-embedding-004` |
| Embeddings (local) | `sentence-transformers` → `all-MiniLM-L6-v2` |
| Vector DB | `chromadb` |

---

*Refer to `config.py` for all shared settings (embedding model, collection name, etc.)*
