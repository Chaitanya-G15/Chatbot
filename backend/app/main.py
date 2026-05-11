from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="HVAC Technician Copilot API",
    description="Backend API for the HVAC Technician Copilot RAG system.",
    version="1.0.0",
)

# Allow all origins for the hackathon
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.app.embeddings.retriever import retrieve

@app.get("/search")
def search(query: str, k: int = None, brand: str = None, doc_type: str = None):
    """Semantic search over HVAC chunks.
    Optional metadata filters: brand, doc_type.
    """
    filter_dict = {}
    if brand:
        filter_dict["brand"] = brand
    if doc_type:
        filter_dict["doc_type"] = doc_type
    results = retrieve(query, k=k, filter=filter_dict or None)
    return {"query": query, "results": results}

