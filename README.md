# HVAC Technician Copilot — RAG Chatbot

A production-ready RAG (Retrieval-Augmented Generation) chatbot that acts as a
**Technician Copilot** for HVAC service engineers. Ask it anything about error codes,
maintenance procedures, installation steps, or spare parts — it answers from your
own PDF manuals.

---

## Team Structure

| Member | Scope | Steps | Folder |
|--------|-------|-------|--------|
| **Member 1** | Data Ingestion & Parsing | 1–3 | `pipeline/` |
| **Member 2** | Embeddings & Vector DB | 4 | `embeddings/` |
| **Member 3** | Backend API & RAG Pipeline | 5–6 | `backend/` |
| **Member 4** | Frontend / UI & Deployment | 7–8, 11 | `frontend/` |

---

## Quick Start (Member 1 — Ingestion)

### 1. Clone / open the project
```powershell
cd c:\Users\Dell\.gemini\antigravity\scratch\Chatbot
```

### 2. Create a virtual environment
```powershell
python -m venv venv
venv\Scripts\activate
```

### 3. Install Member 1 dependencies
```powershell
pip install -r requirements.txt
```

### 4. Configure environment
```powershell
copy .env.example .env
# Open .env and fill in your values (see comments inside)
```

### 5. Add HVAC PDF manuals
```
data/raw_pdfs/
  Carrier_50XC_ServiceManual.pdf
  Trane_4TTB_InstallationGuide.pdf
  ...
```

### 6. Run the ingestion pipeline
```powershell
# Process all PDFs in data/raw_pdfs/
python pipeline/ingest.py

# Process a single PDF with metadata overrides
python pipeline/ingest.py --file "data/raw_pdfs/Carrier_50XC.pdf" \
    --brand Carrier --model 50XC --doc_type service_manual

# Re-process everything from scratch
python pipeline/ingest.py --reset
```

### 7. Verify output
The pipeline produces:
- `data/chunks/chunks.json` — **The main handoff artifact for Member 2**
- `data/chunks/manifest.json` — Tracks which PDFs were processed

---

## Handoff Instructions Per Member

### → Member 2 (Embeddings & Vector DB)
**Read:** `embeddings/README.md`

Your input is `data/chunks/chunks.json`. Each entry looks like:
```json
{
  "chunk_id": "carrier_50xc_service_manual_p12_c3_ab1234",
  "text": "Error Code E01 indicates a failed pressure sensor...",
  "token_count": 412,
  "metadata": {
    "source_file": "Carrier_50XC_ServiceManual.pdf",
    "brand": "Carrier",
    "model": "50XC",
    "doc_type": "service_manual",
    "page_number": 12,
    "section": "Error Codes",
    "content_type": "text",
    "chunk_index": 3,
    "total_chunks_in_doc": 47
  }
}
```
Generate embeddings for each `text` field and store in ChromaDB with the full
`metadata` dict (enables filtering by brand/model at query time).

### → Member 3 (Backend API & RAG)
**Read:** `backend/README.md`

Build a FastAPI app that:
1. Accepts a user query + optional `brand`/`model` filters
2. Embeds the query using the same model as Member 2
3. Searches ChromaDB for top-K matching chunks
4. Sends chunks + query to Gemini (or another LLM) to generate an answer
5. Returns the answer + source citations (chunk_ids, page numbers)

### → Member 4 (Frontend / UI)
**Read:** `frontend/README.md`

Build a React (or Next.js) chat interface:
- Mobile-first, HVAC-themed dark UI
- Text + optional image upload (for error display photos)
- Quick buttons: Troubleshoot / Maintenance / Parts / Safety
- Shows citations (manual name, page number) alongside each answer

---

## Project Structure

```
Chatbot/
├── README.md               ← You are here
├── .env.example            ← Copy to .env and fill in secrets
├── .env                    ← Local secrets (gitignored)
├── requirements.txt        ← Python deps (sectioned by member)
├── config.py               ← Shared config — ALL members import this
│
├── data/
│   ├── raw_pdfs/           ← Drop HVAC PDFs here (gitignored)
│   └── chunks/
│       ├── chunks.json     ← HANDOFF: Member 1 → Member 2
│       └── manifest.json   ← Tracks processed PDFs
│
├── pipeline/               ← Member 1's code
│   ├── extractor.py        ← PDF text + table extraction
│   ├── cleaner.py          ← HVAC-aware text cleaning
│   ├── chunker.py          ← Smart chunking (300-800 tokens)
│   └── ingest.py           ← Master CLI orchestrator
│
├── embeddings/             ← Member 2's code
│   └── README.md
│
├── backend/                ← Member 3's code
│   └── README.md
│
└── frontend/               ← Member 4's code
    └── README.md
```

---

## Environment Variables

See `.env.example` for the full list. Each section is labeled by member.

---

## Common Issues

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: pymupdf` | Run `pip install -r requirements.txt` in your venv |
| `pytesseract is not installed` | OCR is optional. Install Tesseract + `pip install pytesseract Pillow` |
| No PDFs found | Make sure files are in `data/raw_pdfs/` with `.pdf` extension |
| Chunks look garbled | Check if the PDF is scanned — enable OCR with `pip install pytesseract` |
| Token count wrong | `pip install tiktoken` for accurate counts |

---

*Built with PyMuPDF, pdfplumber, tiktoken · Designed for 4-member team parallel development*
