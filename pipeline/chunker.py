"""
chunker.py
==========
Step 3 of the pipeline: Split cleaned text blocks into chunks
suitable for embedding and retrieval (300-800 tokens each).

Strategy:
  1. Section-aware splitting — detect headings and start new chunks
  2. Sentence-boundary splitting — never cut mid-sentence
  3. Overlap — last N tokens of previous chunk prepended to next
  4. Tables — kept as a single chunk (never split across chunks)

Token counting uses tiktoken (cl100k_base — compatible with most LLMs).

Output per chunk:
  {
    "chunk_id": "carrier_50xc_service_manual_p12_c3",
    "text": "...",
    "token_count": 412,
    "metadata": {
      "source_file": "...", "brand": "...", "model": "...",
      "doc_type": "...", "page_number": 12,
      "section": "Error Codes", "content_type": "text",
      "chunk_index": 3, "total_chunks_in_doc": 47
    }
  }
"""

import re
import sys
import hashlib
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from config import cfg

try:
    import tiktoken
    _TOKENIZER = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_TOKENIZER.encode(text))

    def encode(text: str) -> list[int]:
        return _TOKENIZER.encode(text)

    def decode(tokens: list[int]) -> str:
        return _TOKENIZER.decode(tokens)

except ImportError:
    # Fallback: approximate 1 token ~ 4 characters
    def count_tokens(text: str) -> int:
        return max(1, len(text) // 4)

    def encode(text: str) -> list[int]:
        return list(range(count_tokens(text)))   # dummy

    def decode(tokens: list[int]) -> str:
        return ""   # not usable without tiktoken

# ------------------------------------------------------------------
# Section heading detection (compiled from config)
# ------------------------------------------------------------------

_HEADING_PATTERNS = [
    re.compile(p, re.MULTILINE) for p in cfg.SECTION_HEADING_PATTERNS
]

TARGET_TOKENS  = cfg.CHUNK_TARGET_TOKENS
MAX_TOKENS     = cfg.CHUNK_MAX_TOKENS
MIN_TOKENS     = cfg.CHUNK_MIN_TOKENS
OVERLAP_TOKENS = cfg.CHUNK_OVERLAP_TOKENS


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def chunk_blocks(clean_blocks: list[dict]) -> list[dict]:
    """
    Convert a list of cleaned blocks (from cleaner.py) into chunks.

    Args:
        clean_blocks: Output from cleaner.clean_blocks().

    Returns:
        List of chunk dicts, each with chunk_id, text, token_count, metadata.
    """
    all_chunks = []
    doc_chunk_idx = 0
    current_section = "Introduction"
    overlap_buffer = ""   # carries tail text from previous chunk

    for block in clean_blocks:
        content_type = block.get("content_type", "text")
        text = block.get("text", "").strip()
        meta = block.get("metadata", {})

        if not text:
            continue

        # Update section tracker from heading detection
        detected_section = _detect_section(text)
        if detected_section:
            current_section = detected_section
            overlap_buffer = ""   # reset overlap at section boundary

        meta_with_section = {**meta, "section": current_section, "content_type": content_type}

        if content_type == "table":
            # Tables are never split — emit as a single chunk
            chunk = _make_chunk(text, meta_with_section, doc_chunk_idx)
            if chunk:
                all_chunks.append(chunk)
                doc_chunk_idx += 1
            overlap_buffer = ""
        else:
            # Plain text: split with overlap
            new_chunks, overlap_buffer = _split_text(
                text, meta_with_section, doc_chunk_idx, overlap_buffer
            )
            all_chunks.extend(new_chunks)
            doc_chunk_idx += len(new_chunks)

    # Annotate total_chunks_in_doc (for context in retrieval)
    total = len(all_chunks)
    for chunk in all_chunks:
        chunk["metadata"]["total_chunks_in_doc"] = total

    print(
        f"  [chunker] Generated {total} chunks "
        f"(target: {TARGET_TOKENS} tokens, max: {MAX_TOKENS} tokens).",
        flush=True
    )
    return all_chunks


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _detect_section(text: str) -> str | None:
    """
    Check whether the first non-empty line of this text block looks
    like a section heading. Returns the heading text, or None.
    """
    first_line = text.strip().split("\n")[0].strip()
    if not first_line or len(first_line) > 120:
        return None
    for pattern in _HEADING_PATTERNS:
        if pattern.search(first_line):
            return first_line
    return None


def _split_sentences(text: str) -> list[str]:
    """
    Split text into sentences at '.', '!', '?' boundaries,
    but never split inside abbreviations like 'e.g.' or 'no.'.
    """
    # Protect common abbreviations
    text = re.sub(r'\b(e\.g\.|i\.e\.|etc\.|approx\.|Fig\.|fig\.|No\.|no\.|vs\.)', 
                  lambda m: m.group(0).replace('.', '__DOT__'), text)

    # Split on sentence-ending punctuation followed by whitespace + capital
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z\d"])', text)

    # Restore abbreviations
    sentences = [s.replace('__DOT__', '.') for s in sentences]
    return [s.strip() for s in sentences if s.strip()]


def _split_text(
    text: str,
    meta: dict,
    start_idx: int,
    overlap_buffer: str,
) -> tuple[list[dict], str]:
    """
    Split a text block into chunks of TARGET_TOKENS, with sentence
    boundaries respected and OVERLAP_TOKENS of overlap between chunks.

    Returns:
        (list_of_chunks, new_overlap_buffer)
    """
    sentences = _split_sentences(text)
    chunks = []
    current_sentences = []
    current_tokens = 0

    # Prepend overlap from previous chunk
    if overlap_buffer:
        overlap_tokens = count_tokens(overlap_buffer)
        if overlap_tokens <= OVERLAP_TOKENS:
            current_sentences = [overlap_buffer]
            current_tokens = overlap_tokens

    for sentence in sentences:
        s_tokens = count_tokens(sentence)

        # Single sentence too large → force-split by tokens
        if s_tokens > MAX_TOKENS:
            # Flush current buffer first
            if current_sentences:
                chunk_text = " ".join(current_sentences)
                c = _make_chunk(chunk_text, meta, start_idx + len(chunks))
                if c:
                    chunks.append(c)
                current_sentences = []
                current_tokens = 0

            # Split giant sentence by token windows
            sub_chunks = _split_by_tokens(sentence, meta, start_idx + len(chunks))
            chunks.extend(sub_chunks)
            continue

        # Adding this sentence would exceed max → flush first
        if current_tokens + s_tokens > TARGET_TOKENS and current_sentences:
            chunk_text = " ".join(current_sentences)
            c = _make_chunk(chunk_text, meta, start_idx + len(chunks))
            if c:
                chunks.append(c)

            # Start new chunk with overlap from tail of current
            overlap_text = _get_tail_tokens(current_sentences, OVERLAP_TOKENS)
            current_sentences = [overlap_text, sentence] if overlap_text else [sentence]
            current_tokens = count_tokens(" ".join(current_sentences))
        else:
            current_sentences.append(sentence)
            current_tokens += s_tokens

    # Flush remaining sentences
    if current_sentences:
        chunk_text = " ".join(current_sentences)
        if count_tokens(chunk_text) >= MIN_TOKENS:
            c = _make_chunk(chunk_text, meta, start_idx + len(chunks))
            if c:
                chunks.append(c)

    # Build next overlap buffer from the last chunk
    new_overlap = ""
    if chunks:
        last_text = chunks[-1]["text"]
        new_overlap = _get_tail_tokens([last_text], OVERLAP_TOKENS)

    return chunks, new_overlap


def _split_by_tokens(text: str, meta: dict, start_idx: int) -> list[dict]:
    """Force-split a very long string into MAX_TOKENS-sized pieces."""
    try:
        tokens = encode(text)
    except Exception:
        # Fallback: character split
        size = MAX_TOKENS * 4
        parts = [text[i:i+size] for i in range(0, len(text), size)]
        return [_make_chunk(p, meta, start_idx + i) for i, p in enumerate(parts) if p]

    chunks = []
    for i in range(0, len(tokens), MAX_TOKENS - OVERLAP_TOKENS):
        window = tokens[i: i + MAX_TOKENS]
        try:
            part_text = decode(window)
        except Exception:
            continue
        c = _make_chunk(part_text, meta, start_idx + len(chunks))
        if c:
            chunks.append(c)
    return chunks


def _get_tail_tokens(sentences: list[str], n_tokens: int) -> str:
    """Return the last N tokens worth of text from a list of sentences."""
    text = " ".join(sentences)
    try:
        tokens = encode(text)
        tail = tokens[-n_tokens:]
        return decode(tail).strip()
    except Exception:
        # Character fallback
        return text[-(n_tokens * 4):].strip()


def _make_chunk(text: str, meta: dict, chunk_index: int) -> dict | None:
    """
    Create a final chunk dict with a deterministic chunk_id.
    Returns None if the chunk is below MIN_TOKENS.
    """
    text = text.strip()
    if not text:
        return None

    token_count = count_tokens(text)
    if token_count < MIN_TOKENS:
        return None

    # Build a stable chunk_id from content hash + position
    source = meta.get("source_file", "doc")
    page   = meta.get("page_number", 0)
    hash6  = hashlib.md5(text[:200].encode()).hexdigest()[:6]

    # Sanitize source filename for use in ID
    source_slug = re.sub(r'[^a-z0-9]+', '_', source.lower().replace('.pdf', ''))
    chunk_id = f"{source_slug}_p{page}_c{chunk_index}_{hash6}"

    return {
        "chunk_id": chunk_id,
        "text": text,
        "token_count": token_count,
        "metadata": {
            **meta,
            "chunk_index": chunk_index,
        }
    }
