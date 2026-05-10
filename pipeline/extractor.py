"""
extractor.py
============
Step 1 of the pipeline: Extract raw text, tables, and metadata
from HVAC PDF manuals.

Uses:
  - PyMuPDF (fitz)  → fast text extraction + page metadata
  - pdfplumber      → accurate table detection
  - pytesseract     → OCR fallback for scanned/image-only pages

Output format per block:
  {
    "content_type": "text" | "table" | "image_text",
    "text": "...",
    "page_number": 5,
    "source_file": "Carrier_50XC.pdf",
    "metadata": { "brand": ..., "model": ..., "doc_type": ... }
  }
"""

import fitz          # PyMuPDF
import pdfplumber
import re
import sys
import os
from pathlib import Path

# Allow running from any directory
sys.path.append(str(Path(__file__).parent.parent))
from config import cfg

try:
    import pytesseract
    from PIL import Image
    import io
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# Minimum characters a page must have before triggering OCR fallback
OCR_FALLBACK_THRESHOLD = 50


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def extract_pdf(pdf_path: str, metadata: dict = None) -> list[dict]:
    """
    Extract all content blocks from a PDF file.

    Args:
        pdf_path:  Absolute or relative path to the PDF.
        metadata:  Optional dict with keys: brand, model, doc_type, version.
                   Injected into every block for downstream filtering.

    Returns:
        List of content blocks (dicts) ready for cleaning + chunking.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    meta = _build_metadata(pdf_path, metadata or {})
    blocks = []

    print(f"  [extractor] Opening: {pdf_path.name} ...", flush=True)

    # Open with pdfplumber for table detection (keep open for full doc)
    with pdfplumber.open(str(pdf_path)) as plumber_doc:
        # Open with fitz for fast text extraction
        fitz_doc = fitz.open(str(pdf_path))

        for page_num in range(len(fitz_doc)):
            print(
                f"  [extractor]   Page {page_num + 1}/{len(fitz_doc)}",
                end="\r", flush=True
            )

            fitz_page  = fitz_doc[page_num]
            plumb_page = plumber_doc.pages[page_num]
            page_meta  = {**meta, "page_number": page_num + 1}

            # 1. Extract tables first (before text, so we can skip table regions)
            table_blocks = _extract_tables(plumb_page, page_meta)
            table_bboxes = _get_table_bboxes(plumb_page)

            # 2. Extract main text (excluding table areas)
            text_blocks = _extract_text(fitz_page, plumb_page, table_bboxes, page_meta)

            # 3. OCR fallback: if page has almost no text, try image OCR
            total_text = " ".join(b["text"] for b in text_blocks).strip()
            if len(total_text) < OCR_FALLBACK_THRESHOLD and OCR_AVAILABLE:
                ocr_block = _extract_ocr(fitz_page, page_meta)
                if ocr_block:
                    blocks.append(ocr_block)
            else:
                blocks.extend(text_blocks)

            blocks.extend(table_blocks)

        fitz_doc.close()

    # Final newline after carriage-return progress
    print(f"\n  [extractor] Done. Extracted {len(blocks)} raw blocks.", flush=True)
    return blocks


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _build_metadata(pdf_path: Path, user_meta: dict) -> dict:
    """Build the base metadata dict for a PDF."""
    name = pdf_path.stem  # filename without extension
    return {
        "source_file": pdf_path.name,
        "brand":    user_meta.get("brand",    _infer_brand(name)),
        "model":    user_meta.get("model",    _infer_model(name)),
        "doc_type": user_meta.get("doc_type", _infer_doc_type(name)),
        "version":  user_meta.get("version",  ""),
    }


def _infer_brand(filename: str) -> str:
    """Try to detect HVAC brand from filename heuristics."""
    brands = {
        "carrier": "Carrier", "trane": "Trane", "lennox": "Lennox",
        "york": "York", "daikin": "Daikin", "mitsubishi": "Mitsubishi",
        "goodman": "Goodman", "rheem": "Rheem", "ruud": "Ruud",
        "american_standard": "American Standard", "bryant": "Bryant",
        "heil": "Heil", "icp": "ICP", "comfortmaker": "Comfortmaker",
        "nordyne": "Nordyne", "bosch": "Bosch", "fujitsu": "Fujitsu",
        "lg": "LG", "samsung": "Samsung", "panasonic": "Panasonic",
    }
    fname_lower = filename.lower().replace("-", "_").replace(" ", "_")
    for key, brand in brands.items():
        if key in fname_lower:
            return brand
    return "Unknown"


def _infer_model(filename: str) -> str:
    """
    Extract model number / series name from filename using HVAC naming patterns.
    E.g. 'Carrier_Hi-Wall_QHF_series' -> 'QHF'
         'Carrier_50XC_ServiceManual'  -> '50XC'
         'Trane_4TTB3048_Install'      -> '4TTB3048'
    """
    fname_upper = filename.upper()

    # Pattern 1: Full model codes like 4TTB3048, 38QHF080, XR15, 50XC-060
    match = re.search(
        r'\b([0-9]{0,2}[A-Z]{1,4}[A-Z0-9]{2,12})(?:[_\-][A-Z0-9]+)?\b',
        fname_upper
    )
    if match:
        candidate = match.group(1)
        # Skip single-word brand names that slipped through
        skip = {"CARRIER", "TRANE", "LENNOX", "YORK", "DAIKIN",
                "GOODMAN", "RHEEM", "SERIES", "MANUAL", "GUIDE",
                "SERVICE", "INSTALL", "OPERATION", "PARTS"}
        if candidate not in skip and len(candidate) >= 3:
            return candidate

    # Pattern 2: Series keyword like "Hi-Wall QHF series" -> "QHF"
    series_match = re.search(r'\b([A-Z]{2,6})\s+[Ss]eries\b', filename)
    if series_match:
        return series_match.group(1).upper()

    return "Unknown"


def _infer_doc_type(filename: str) -> str:
    """Classify document type from filename keywords."""
    fname_lower = filename.lower()
    if any(k in fname_lower for k in ["service", "technician", "tech", "repair", "maintenance"]):
        return "service_manual"
    if any(k in fname_lower for k in ["install", "installation", "setup", "series", "hi-wall", "hi_wall"]):
        return "service_manual"   # HVAC series manuals include install + service
    if any(k in fname_lower for k in ["operation", "user", "owner", "guide"]):
        return "operation_manual"
    if any(k in fname_lower for k in ["parts", "catalog", "iom"]):
        return "parts_catalog"
    if any(k in fname_lower for k in ["trouble", "fault", "error", "diagnostic"]):
        return "troubleshooting_guide"
    if any(k in fname_lower for k in ["sop", "procedure", "checklist"]):
        return "sop"
    if any(k in fname_lower for k in ["safety", "hazard", "warning"]):
        return "safety_guide"
    return "manual"


def _get_table_bboxes(plumb_page) -> list[tuple]:
    """Return bounding boxes of all detected tables on a page."""
    bboxes = []
    for table in plumb_page.find_tables():
        if table.bbox:
            bboxes.append(table.bbox)   # (x0, top, x1, bottom)
    return bboxes


def _bbox_overlaps(text_bbox: tuple, table_bboxes: list[tuple]) -> bool:
    """Check if a text block's bounding box overlaps with any table area."""
    x0, y0, x1, y1 = text_bbox
    for (tx0, ty0, tx1, ty1) in table_bboxes:
        if x0 < tx1 and x1 > tx0 and y0 < ty1 and y1 > ty0:
            return True
    return False


def _extract_text(fitz_page, plumb_page, table_bboxes: list, page_meta: dict) -> list[dict]:
    """
    Extract plain text from a page, skipping regions covered by tables.
    Returns a list of text blocks (one per logical paragraph/block in the PDF).
    """
    blocks = []
    raw_blocks = fitz_page.get_text("blocks")   # list of (x0, y0, x1, y1, text, ...)

    for block in raw_blocks:
        if len(block) < 5:
            continue
        x0, y0, x1, y1, text = block[:5]
        text = text.strip()

        if not text:
            continue
        # Skip blocks that sit inside a detected table region
        if _bbox_overlaps((x0, y0, x1, y1), table_bboxes):
            continue

        blocks.append({
            "content_type": "text",
            "text": text,
            "metadata": {**page_meta},
        })

    return blocks


def _extract_tables(plumb_page, page_meta: dict) -> list[dict]:
    """
    Extract tables using pdfplumber and convert to markdown-style text.
    Each table becomes a single block with content_type='table'.
    """
    blocks = []
    for table in plumb_page.extract_tables():
        if not table:
            continue
        rows = []
        for row in table:
            # Replace None cells with empty string
            cleaned_row = [str(cell).strip() if cell else "" for cell in row]
            rows.append(" | ".join(cleaned_row))

        table_text = "\n".join(rows)
        if len(table_text.strip()) < 10:
            continue

        blocks.append({
            "content_type": "table",
            "text": table_text,
            "metadata": {**page_meta},
        })

    return blocks


def _extract_ocr(fitz_page, page_meta: dict) -> dict | None:
    """
    OCR fallback for image-only / scanned pages using pytesseract.
    Renders the page at 200 DPI and extracts text.
    """
    if not OCR_AVAILABLE:
        return None
    try:
        mat = fitz.Matrix(200 / 72, 200 / 72)   # 200 DPI
        pix = fitz_page.get_pixmap(matrix=mat, alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        text = pytesseract.image_to_string(img, config="--psm 6")
        text = text.strip()
        if len(text) < OCR_FALLBACK_THRESHOLD:
            return None
        return {
            "content_type": "image_text",
            "text": text,
            "metadata": {**page_meta, "ocr": True},
        }
    except Exception as e:
        print(f"\n  [extractor] OCR failed on page {page_meta.get('page_number')}: {e}")
        return None
