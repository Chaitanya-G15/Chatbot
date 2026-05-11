"""
config.py
=========
Shared configuration for the HVAC Technician Copilot RAG system.
All team members import from this file to stay in sync.

Usage:
    from config import Config
    cfg = Config()
    print(cfg.PDF_INPUT_DIR)
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

# Project root (the Chatbot/ directory)
PROJECT_ROOT = Path(__file__).parent.resolve()


class Config:
    # -----------------------------------------------------------------
    # Member 1 — Pipeline paths
    # -----------------------------------------------------------------
    PDF_INPUT_DIR: Path = PROJECT_ROOT / os.getenv("PDF_INPUT_DIR", "data/raw_pdfs")
    CHUNKS_OUTPUT_DIR: Path = PROJECT_ROOT / os.getenv("CHUNKS_OUTPUT_DIR", "data/chunks")
    CHUNKS_FILE: Path = CHUNKS_OUTPUT_DIR / "chunks.json"
    MANIFEST_FILE: Path = CHUNKS_OUTPUT_DIR / "manifest.json"

    # -----------------------------------------------------------------
    # Member 1 — Chunking parameters
    # -----------------------------------------------------------------
    CHUNK_TARGET_TOKENS: int = 500       # Target size per chunk (tokens)
    CHUNK_MAX_TOKENS: int = 800          # Hard cap before forced split
    CHUNK_MIN_TOKENS: int = 50           # Discard chunks smaller than this
    CHUNK_OVERLAP_TOKENS: int = 80       # Overlap between consecutive chunks

    # -----------------------------------------------------------------
    # Member 2 — Embeddings & Vector DB
    # -----------------------------------------------------------------
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    CHROMA_DB_DIR: Path = PROJECT_ROOT / os.getenv("CHROMA_DB_DIR", "data/chroma_db")
    CHROMA_COLLECTION: str = os.getenv("CHROMA_COLLECTION", "hvac_manuals")

    # -----------------------------------------------------------------
    # Member 3 — Backend
    # -----------------------------------------------------------------
    BACKEND_HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-2.0-flash")
    TOP_K_RESULTS: int = int(os.getenv("TOP_K_RESULTS", "5"))

    # -----------------------------------------------------------------
    # Member 4 — Frontend
    # -----------------------------------------------------------------
    VITE_API_BASE_URL: str = os.getenv("VITE_API_BASE_URL", "http://localhost:8000")

    # -----------------------------------------------------------------
    # HVAC domain-specific settings (used by cleaner.py)
    # -----------------------------------------------------------------
    HVAC_REFRIGERANTS = [
        "R-22", "R-32", "R-410A", "R-407C", "R-134a",
        "R-404A", "R-448A", "R-454B", "R-744",
    ]

    HVAC_UNITS = [
        "BTU", "BTUH", "kW", "kWh", "CFM", "GPM",
        "PSI", "PSIG", "kPa", "MPa", "bar",
        "VAC", "VDC", "Hz", "Amps", "A", "V",
        "SEER", "EER", "COP", "HSPF",
        "RPM", "dB", "dBA",
        "°F", "°C", "°K",
        "in. WC", "in-wg",
    ]

    # Section heading patterns (used by chunker.py to split at headings)
    SECTION_HEADING_PATTERNS = [
        r"^(CHAPTER|SECTION|PART)\s+\d+",            # CHAPTER 1, SECTION A
        r"^\d+\.\d*\s+[A-Z][A-Za-z\s]{3,}$",        # 1.2 Installation Procedure
        r"^[A-Z][A-Z\s]{4,}$",                       # ALL CAPS HEADINGS
        r"^(WARNING|CAUTION|NOTE|DANGER)\s*:",       # Safety notices
        r"^(Error|Fault|Alarm)\s+Code",              # Error code sections
        r"^(Installation|Operation|Maintenance|Troubleshooting|Safety)",
    ]


# Singleton instance for easy imports
cfg = Config()
