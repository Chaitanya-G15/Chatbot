# Step 4 — Embedding & Vector Database Pipeline

This directory contains the embedding generation and vector database pipeline for the HVAC Technician Copilot. 

## Project Structure

```bash
backend/
│
├── app/
│   ├── embeddings/
│   │   ├── embedder.py     # SentenceTransformers wrapper
│   │   ├── ingest.py       # Batch ingestion of chunks to ChromaDB
│   │   ├── retriever.py    # Semantic search with metadata filtering
│   │   └── vectordb.py     # ChromaDB client and connection handler
│   │
│   └── main.py             # Minimal FastAPI structure ready for Step 5
│
└── README.md
```

## Setup Instructions

1. Ensure you have completed **Step 3 (Chunking)** so that `data/chunks/chunks.json` exists.
2. Install the requirements (from the project root):
   ```bash
   pip install -r requirements.txt
   ```
   *(Ensure `chromadb` and `sentence-transformers` are uncommented).*

## 1. Ingest Data (Embed + Save to ChromaDB)

To read all chunks, generate embeddings, and save them to the persistent ChromaDB collection, run the ingestion script from the project root:

```bash
python -m backend.app.embeddings.ingest
```

This will:
- Load the chosen embedding model (`sentence-transformers/all-MiniLM-L6-v2` by default).
- Read batches from `data/chunks/chunks.json`.
- Compute vector embeddings.
- Upsert into `data/chroma_db`.

## 2. Retrieve Data (Semantic Search)

To test the retrieval pipeline, you can run the example retrieval script:

```bash
python -m backend.app.embeddings.retriever
```

This simulates a user query and returns the `top_k` most relevant text chunks using semantic similarity, returning metadata such as the `brand`, `model`, `doc_type`, and `page_number`.

### Using Metadata Filters Programmatically

You can easily apply filters based on metadata fields. Example usage in Python:

```python
from backend.app.embeddings.retriever import Retriever

retriever = Retriever()
results = retriever.retrieve(
    query="How to fix low refrigerant pressure?",
    top_k=3,
    filters={"brand": "Daikin", "doc_type": "service_manual"}
)

for res in results:
    print(res["text"])
```

## FastAPI Server (Ready Structure)

A basic structure is provided in `backend/app/main.py`. You can start it via:

```bash
uvicorn backend.app.main:app --reload
```
