"""
cleaner.py
==========
Step 2 of the pipeline: Clean and normalize raw extracted text blocks.

HVAC-aware cleaning preserves critical domain terms:
  - Refrigerants: R-410A, R-22, R-134a
  - Units: BTU, SEER, PSI, CFM, VAC, Hz, °F, °C
  - Error/Fault codes: E01, F23, 0xAB, etc.
  - Model numbers: 4TTB3048, 50XC-060, etc.

Does NOT:
  - Remove HVAC-specific measurements or codes
  - Alter table structure
"""

import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from config import cfg

# ------------------------------------------------------------------
# Patterns to PROTECT (never strip or split these)
# ------------------------------------------------------------------

# Refrigerant designations: R-22, R-410A, R-134a, R-407C
_RE_REFRIGERANT = re.compile(
    r'\bR-\d{2,3}[A-Za-z]?\b', re.IGNORECASE
)

# Physical units with optional numeric prefix: 14.7 PSI, 60 Hz, 208/230 VAC
_RE_UNITS = re.compile(
    r'\b\d+(?:[.,]\d+)?\s*'
    r'(?:BTU(?:H)?|kW(?:h)?|CFM|GPM|PSI(?:G)?|kPa|MPa|bar|'
    r'VAC|VDC|Hz|Amps?|A|V|SEER|EER|COP|HSPF|RPM|dB(?:A)?|'
    r'in\.?\s*WC|in-?wg|°[FCK]|lbs?)\b',
    re.IGNORECASE
)

# Error / fault codes: E01, F-23, 0xAB12, Code 55
_RE_ERROR_CODE = re.compile(
    r'\b(?:[EFe][_\-]?\d{1,4}|0x[0-9A-Fa-f]{1,6}|Code\s+\d+|Fault\s+\d+)\b'
)

# Model numbers: 4TTB3048E1, 50XC-060D, etc.
_RE_MODEL_NUM = re.compile(
    r'\b[0-9]{1,2}[A-Z]{2,4}[0-9A-Z\-]{3,12}\b'
)

# Wiring gauge & spec: 14 AWG, 3/4" NPT
_RE_SPEC = re.compile(
    r'\b\d+\s*(?:AWG|NPT|GA|gauge|"|\'\s*NPT)\b', re.IGNORECASE
)

# Temperature range: -20°F to 125°F, 0°C–45°C
_RE_TEMP_RANGE = re.compile(
    r'-?\d+\s*°[FCK]\s*(?:to|[-–])\s*-?\d+\s*°[FCK]', re.IGNORECASE
)

# Voltage spec: 208/230V, 460-3-60
_RE_VOLTAGE = re.compile(r'\b\d{2,3}(?:/\d{2,3})?(?:[-]\d)?(?:[-]\d{2})?\s*V(?:AC|DC)?\b')

# Combined "protect" pattern — anything matching these gets a placeholder
_PROTECT_PATTERNS = [
    _RE_REFRIGERANT, _RE_TEMP_RANGE, _RE_UNITS, _RE_ERROR_CODE,
    _RE_MODEL_NUM, _RE_SPEC, _RE_VOLTAGE,
]

# ------------------------------------------------------------------
# Header / footer noise patterns (to strip)
# ------------------------------------------------------------------

_HEADER_FOOTER_PATTERNS = [
    # Page numbers alone: "Page 12 of 45" or just "12"
    re.compile(r'^\s*Page\s+\d+\s+of\s+\d+\s*$', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^\s*\d+\s*$', re.MULTILINE),
    # Repeated company / manual title headers (3+ all-caps words at line start)
    re.compile(r'^[A-Z][A-Z\s\-]{15,}$', re.MULTILINE),
    # Copyright lines
    re.compile(r'^\s*©\s*\d{4}.*$', re.MULTILINE | re.IGNORECASE),
    re.compile(r'^\s*Copyright\s+\d{4}.*$', re.MULTILINE | re.IGNORECASE),
    # Revision lines: "Rev. A", "Revision 03-2022"
    re.compile(r'^\s*Rev(?:ision)?\.?\s+[A-Z0-9\-]+\s*$', re.MULTILINE | re.IGNORECASE),
    # Standalone URLs / part numbers repeated as watermarks
    re.compile(r'^\s*(https?://\S+|www\.\S+)\s*$', re.MULTILINE),
    # Catalog/form numbers: "Form 12345-67"
    re.compile(r'^\s*Form\s+\d+[\-\s]?\d*\s*$', re.MULTILINE | re.IGNORECASE),
    # TOC leader dots: sequences of 3+ dots (with optional spaces) used to
    # align page numbers in a table of contents, e.g. "Section 1 .............. 14"
    re.compile(r'\.{3,}', re.MULTILINE),
]

# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

# Pattern: a line that is ONLY a TOC entry —
# "<section name> <dots> <page number>" with nothing else meaningful.
# Matches lines like: "6.1 Installation ............. 14"
_RE_TOC_LINE = re.compile(
    r'^[\w\s\.\-,/()]{3,80}\.{3,}\s*\d+\s*$', re.MULTILINE
)


def _is_toc_block(text: str) -> bool:
    """
    Return True if this block is entirely a Table of Contents page —
    i.e., every non-empty line is a TOC entry (section name + dots + page num).
    Such blocks have no semantic value for RAG retrieval.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return False
    toc_line_count = sum(1 for l in lines if _RE_TOC_LINE.match(l))
    # If 60%+ of lines look like TOC entries, treat the whole block as TOC noise
    return toc_line_count / len(lines) >= 0.6


def clean_block(block: dict) -> dict | None:
    """
    Clean a single extracted block.

    Args:
        block: A dict with keys 'content_type', 'text', 'metadata'.

    Returns:
        Cleaned block, or None if the block should be discarded.
    """
    content_type = block.get("content_type", "text")
    text = block.get("text", "")

    # Discard entire TOC pages before any other cleaning
    if content_type != "table" and _is_toc_block(text):
        return None

    if content_type == "table":
        text = _clean_table(text)
    else:
        text = _clean_text(text)

    if not text or len(text.strip()) < 20:
        return None   # Discard near-empty blocks

    return {**block, "text": text}


def clean_blocks(blocks: list[dict]) -> list[dict]:
    """
    Clean a list of extracted blocks.

    Args:
        blocks: Output from extractor.extract_pdf().

    Returns:
        List of cleaned blocks (Nones filtered out).
    """
    cleaned = []
    discarded = 0
    for block in blocks:
        result = clean_block(block)
        if result:
            cleaned.append(result)
        else:
            discarded += 1

    print(
        f"  [cleaner] {len(cleaned)} blocks kept, {discarded} discarded.",
        flush=True
    )
    return cleaned


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _protect_terms(text: str) -> tuple[str, dict]:
    """
    Temporarily replace protected HVAC terms with placeholders
    so other cleaning steps don't accidentally mangle them.

    Returns:
        (text_with_placeholders, {placeholder: original_term})
    """
    placeholder_map = {}
    counter = [0]

    def replace(match):
        key = f"__HVAC_{counter[0]}__"
        placeholder_map[key] = match.group(0)
        counter[0] += 1
        return key

    for pattern in _PROTECT_PATTERNS:
        text = pattern.sub(replace, text)

    return text, placeholder_map


def _restore_terms(text: str, placeholder_map: dict) -> str:
    """Restore protected terms from placeholders."""
    for key, original in placeholder_map.items():
        text = text.replace(key, original)
    return text


def _strip_headers_footers(text: str) -> str:
    """Remove common header/footer noise patterns."""
    for pattern in _HEADER_FOOTER_PATTERNS:
        text = pattern.sub("", text)
    return text


def _normalize_whitespace(text: str) -> str:
    """Collapse excessive whitespace while preserving single blank lines."""
    # Fix hyphenated line breaks (e.g., "opera-\ntion" -> "operation")
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
    # Collapse multiple spaces/tabs to single space
    text = re.sub(r'[ \t]{2,}', ' ', text)
    # Collapse 3+ blank lines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _normalize_unicode(text: str) -> str:
    """Replace common non-ASCII characters with ASCII equivalents."""
    replacements = {
        '\u2019': "'",   # right single quote
        '\u2018': "'",   # left single quote
        '\u201c': '"',   # left double quote
        '\u201d': '"',   # right double quote
        '\u2013': '-',   # en dash
        '\u2014': '--',  # em dash
        '\u00b0': '°',   # degree symbol (keep as is — used in temps)
        '\u00b5': 'u',   # micro sign -> 'u' (e.g., microfarad)
        '\u00d7': 'x',   # multiplication sign
        '\u2022': '-',   # bullet -> dash
        '\u25cf': '-',   # filled circle -> dash
        '\ufb01': 'fi',  # fi ligature
        '\ufb02': 'fl',  # fl ligature
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text


def _clean_text(text: str) -> str:
    """Full cleaning pipeline for plain text blocks."""
    # 1. Normalize unicode
    text = _normalize_unicode(text)

    # 2. Protect HVAC terms before any stripping
    text, protected = _protect_terms(text)

    # 3. Remove header / footer noise
    text = _strip_headers_footers(text)

    # 4. Normalize whitespace
    text = _normalize_whitespace(text)

    # 5. Restore protected terms
    text = _restore_terms(text, protected)

    return text.strip()


def _clean_table(text: str) -> str:
    """
    Light cleaning for table blocks — preserve structure,
    just normalize unicode and whitespace.
    """
    text = _normalize_unicode(text)
    # Collapse extra spaces within cells but keep row separators
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        cells = [cell.strip() for cell in line.split("|")]
        cleaned_lines.append(" | ".join(cells))
    return "\n".join(cleaned_lines).strip()
