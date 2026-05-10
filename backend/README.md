# Member 3 — Backend API & RAG Pipeline

**Your job:** Build the FastAPI backend that accepts user queries, retrieves
relevant chunks from ChromaDB (Member 2's output), and generates answers
via Gemini (or another LLM).

---

## Prerequisites

Member 2 must have populated `data/chroma_db/` before you can run queries.

---

## Setup

```powershell
venv\Scripts\activate
# Uncomment Member 3 deps in requirements.txt, then:
pip install fastapi "uvicorn[standard]" pydantic google-genai python-dotenv
```

Set in `.env`:
```
GOOGLE_API_KEY=your_key_here
LLM_MODEL=gemini-2.0-flash
TOP_K_RESULTS=5
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
```

---

## What to Build

Create `backend/app.py` — a FastAPI app with these endpoints:

### `POST /query`
```json
// Request
{
  "question": "What does error code E01 mean on a Carrier 50XC?",
  "brand": "Carrier",       // optional filter
  "model": "50XC",          // optional filter
  "top_k": 5                // optional, default from config
}

// Response
{
  "answer": "Error E01 on the Carrier 50XC indicates...",
  "sources": [
    {
      "chunk_id": "carrier_50xc_service_manual_p12_c3_ab1234",
      "source_file": "Carrier_50XC_ServiceManual.pdf",
      "page_number": 12,
      "section": "Error Codes",
      "score": 0.92
    }
  ],
  "conversation_id": "..."
}
```

### `GET /health`
```json
{ "status": "ok", "chunks_in_db": 1247 }
```

### `POST /ingest` (optional — trigger pipeline re-run)
Calls `pipeline/ingest.py` programmatically.

---

## RAG Prompt Template

```python
SYSTEM_PROMPT = """
You are an expert HVAC technician assistant. Answer questions based ONLY on
the provided manual excerpts. Always cite the source document and page number.
If the answer is not in the excerpts, say "I couldn't find this in the manuals."
"""

def build_prompt(question: str, chunks: list[dict]) -> str:
    context = "\n\n---\n\n".join(
        f"[Source: {c['metadata']['source_file']}, Page {c['metadata']['page_number']}]\n{c['text']}"
        for c in chunks
    )
    return f"{SYSTEM_PROMPT}\n\nContext:\n{context}\n\nQuestion: {question}\nAnswer:"
```

---

## CORS Configuration

Enable CORS for Member 4's frontend:
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
```

---

## Start the Server

```powershell
python backend/app.py
# or
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```

---

*Refer to `config.py` for `CHROMA_DB_DIR`, `CHROMA_COLLECTION`, `LLM_MODEL`, `TOP_K_RESULTS`.*
