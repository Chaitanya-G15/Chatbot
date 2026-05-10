"""
ingest.py
=========
Master orchestrator for the HVAC PDF ingestion pipeline.

USAGE:
  # Process all PDFs in data/raw_pdfs/
  python pipeline/ingest.py

  # Process a single PDF with custom metadata
  python pipeline/ingest.py --file "data/raw_pdfs/Carrier_50XC.pdf" \
      --brand Carrier --model 50XC --doc_type service_manual

  # Reset (delete) existing chunks and re-process everything
  python pipeline/ingest.py --reset

OUTPUT:
  data/chunks/chunks.json    <- Main handoff artifact for Member 2
  data/chunks/manifest.json  <- Tracks which PDFs have been processed

TEAM HANDOFF:
  After running this script, commit data/chunks/chunks.json to Git.
  Member 2 will load this file to generate embeddings and populate
  the ChromaDB vector database.
"""

import json
import sys
import argparse
import time
from pathlib import Path
from datetime import datetime, timezone

# Allow running from project root or pipeline/ directory
sys.path.append(str(Path(__file__).parent.parent))

from config import cfg
from pipeline.extractor import extract_pdf
from pipeline.cleaner import clean_blocks
from pipeline.chunker import chunk_blocks


# ------------------------------------------------------------------
# Colour helpers (Windows-safe via colorama)
# ------------------------------------------------------------------
try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init(autoreset=True)
    def green(s):  return Fore.GREEN + s + Style.RESET_ALL
    def yellow(s): return Fore.YELLOW + s + Style.RESET_ALL
    def cyan(s):   return Fore.CYAN + s + Style.RESET_ALL
    def red(s):    return Fore.RED + s + Style.RESET_ALL
    def bold(s):   return Style.BRIGHT + s + Style.RESET_ALL
except ImportError:
    def green(s):  return s
    def yellow(s): return s
    def cyan(s):   return s
    def red(s):    return s
    def bold(s):   return s


# ------------------------------------------------------------------
# CLI argument parsing
# ------------------------------------------------------------------

def _parse_args():
    parser = argparse.ArgumentParser(
        description="HVAC Technician Copilot — PDF Ingestion Pipeline"
    )
    parser.add_argument(
        "--file", type=str, default=None,
        help="Process a single PDF file (path). Default: process all PDFs in data/raw_pdfs/"
    )
    parser.add_argument("--brand",    type=str, default=None, help="Override brand name")
    parser.add_argument("--model",    type=str, default=None, help="Override model number")
    parser.add_argument("--doc_type", type=str, default=None,
                        help="Override doc type (e.g. service_manual, installation_manual)")
    parser.add_argument("--version",  type=str, default=None, help="Document version/revision")
    parser.add_argument(
        "--reset", action="store_true",
        help="Delete existing chunks.json and manifest.json and re-process everything"
    )
    return parser.parse_args()


# ------------------------------------------------------------------
# Main pipeline
# ------------------------------------------------------------------

def run_pipeline(
    pdf_path: Path,
    metadata: dict,
    existing_chunks: list[dict],
) -> list[dict]:
    """
    Run the full extract → clean → chunk pipeline for one PDF.

    Args:
        pdf_path:        Path to the PDF file.
        metadata:        Override metadata (brand, model, doc_type, version).
        existing_chunks: Already-processed chunks (for append mode).

    Returns:
        New chunks generated from this PDF.
    """
    print(cyan(f"\n{'='*60}"))
    print(cyan(f"  Processing: {pdf_path.name}"))
    print(cyan(f"{'='*60}"))

    start = time.time()

    # Step 1: Extract
    print(yellow("  [1/3] Extracting text & tables..."))
    raw_blocks = extract_pdf(str(pdf_path), metadata)

    # Step 2: Clean
    print(yellow("  [2/3] Cleaning text blocks..."))
    clean = clean_blocks(raw_blocks)

    # Step 3: Chunk
    print(yellow("  [3/3] Chunking into retrieval units..."))
    new_chunks = chunk_blocks(clean)

    elapsed = time.time() - start
    print(green(f"  Done in {elapsed:.1f}s — {len(new_chunks)} chunks created."))

    return new_chunks


def load_manifest() -> dict:
    """Load the existing manifest, or return empty manifest."""
    if cfg.MANIFEST_FILE.exists():
        with open(cfg.MANIFEST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"processed_files": {}, "last_run": None}


def save_manifest(manifest: dict):
    """Persist the manifest to disk."""
    manifest["last_run"] = datetime.now(timezone.utc).isoformat()
    with open(cfg.MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def load_existing_chunks() -> list[dict]:
    """Load existing chunks.json if it exists."""
    if cfg.CHUNKS_FILE.exists():
        with open(cfg.CHUNKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_chunks(chunks: list[dict]):
    """Save the final chunks list to chunks.json."""
    cfg.CHUNKS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(cfg.CHUNKS_FILE, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)
    print(green(f"\n  Saved {len(chunks)} total chunks -> {cfg.CHUNKS_FILE}"))


def print_stats(chunks: list[dict]):
    """Print a summary of chunk statistics."""
    if not chunks:
        return

    token_counts = [c["token_count"] for c in chunks]
    avg_tokens   = sum(token_counts) / len(token_counts)
    min_tokens   = min(token_counts)
    max_tokens   = max(token_counts)

    # Distribution buckets
    under_300  = sum(1 for t in token_counts if t < 300)
    mid        = sum(1 for t in token_counts if 300 <= t <= 800)
    over_800   = sum(1 for t in token_counts if t > 800)

    # Unique PDFs
    sources = {c["metadata"].get("source_file", "?") for c in chunks}
    brands  = {c["metadata"].get("brand", "?") for c in chunks}
    doc_types = {c["metadata"].get("doc_type", "?") for c in chunks}

    print(bold("\n" + "="*60))
    print(bold("  PIPELINE SUMMARY"))
    print(bold("="*60))
    print(f"  Total chunks  : {len(chunks)}")
    print(f"  Source PDFs   : {len(sources)}")
    print(f"  Brands        : {', '.join(sorted(brands))}")
    print(f"  Doc types     : {', '.join(sorted(doc_types))}")
    print(f"\n  Token stats   :")
    print(f"    Average     : {avg_tokens:.0f} tokens")
    print(f"    Min / Max   : {min_tokens} / {max_tokens} tokens")
    print(f"\n  Distribution  :")
    print(f"    < 300 tokens: {under_300} chunks")
    print(f"    300-800     : {mid} chunks  (ideal range)")
    print(f"    > 800 tokens: {over_800} chunks")
    print(bold("="*60))

    # Show 3 sample chunks
    print(bold("\n  SAMPLE CHUNKS (first 3):"))
    for i, chunk in enumerate(chunks[:3]):
        meta = chunk["metadata"]
        preview = chunk["text"][:150].replace("\n", " ")
        print(f"\n  [{i+1}] {chunk['chunk_id']}")
        print(f"       Brand: {meta.get('brand')} | Model: {meta.get('model')} "
              f"| Page: {meta.get('page_number')} | Tokens: {chunk['token_count']}")
        print(f"       Section: {meta.get('section')}")
        print(f"       Preview: \"{preview}...\"")

    print(bold("\n" + "="*60))
    print(green("  chunks.json is ready for Member 2 (Embeddings & Vector DB)!"))
    print(bold("="*60))


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def main():
    args = _parse_args()

    # Ensure output dir exists
    cfg.CHUNKS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg.PDF_INPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Handle --reset
    if args.reset:
        for f in [cfg.CHUNKS_FILE, cfg.MANIFEST_FILE]:
            if f.exists():
                f.unlink()
                print(yellow(f"  Deleted {f}"))

    # Load existing state
    manifest       = load_manifest()
    existing_chunks = load_existing_chunks()
    all_chunks     = list(existing_chunks)   # start with previously processed chunks

    print(bold(f"\n  HVAC Technician Copilot — Ingestion Pipeline"))
    print(f"  Input dir : {cfg.PDF_INPUT_DIR}")
    print(f"  Output    : {cfg.CHUNKS_FILE}")
    print(f"  Already processed: {len(manifest['processed_files'])} file(s)")

    # Collect PDFs to process
    if args.file:
        pdf_files = [Path(args.file)]
        if not pdf_files[0].exists():
            print(red(f"  ERROR: File not found: {args.file}"))
            sys.exit(1)
    else:
        pdf_files = sorted(cfg.PDF_INPUT_DIR.glob("*.pdf"))
        if not pdf_files:
            print(yellow(
                f"\n  No PDF files found in {cfg.PDF_INPUT_DIR}\n"
                f"  Add your HVAC manuals there and re-run.\n"
                f"  Example:\n"
                f"    copy \"Carrier_50XC_ServiceManual.pdf\" \"{cfg.PDF_INPUT_DIR}\"\n"
                f"    python pipeline/ingest.py\n"
            ))
            return

    # Filter out already-processed files (unless --reset)
    if not args.reset:
        new_pdf_files = []
        for pdf in pdf_files:
            if pdf.name in manifest["processed_files"]:
                print(yellow(f"  Skipping (already processed): {pdf.name}"))
            else:
                new_pdf_files.append(pdf)
        pdf_files = new_pdf_files

    if not pdf_files:
        print(green("\n  All PDFs already processed. Use --reset to re-process."))
        print_stats(all_chunks)
        return

    print(f"\n  Processing {len(pdf_files)} PDF(s)...")

    # Process each PDF
    for pdf_path in pdf_files:
        user_meta = {
            "brand":    args.brand,
            "model":    args.model,
            "doc_type": args.doc_type,
            "version":  args.version,
        }
        # Remove None values so extractor can use its own inference
        user_meta = {k: v for k, v in user_meta.items() if v}

        try:
            new_chunks = run_pipeline(pdf_path, user_meta, all_chunks)

            # Remove old chunks from this file (in case of partial re-run)
            all_chunks = [
                c for c in all_chunks
                if c["metadata"].get("source_file") != pdf_path.name
            ]
            all_chunks.extend(new_chunks)

            manifest["processed_files"][pdf_path.name] = {
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "chunk_count": len(new_chunks),
                "brand":    new_chunks[0]["metadata"].get("brand") if new_chunks else "",
                "model":    new_chunks[0]["metadata"].get("model") if new_chunks else "",
                "doc_type": new_chunks[0]["metadata"].get("doc_type") if new_chunks else "",
            }

        except Exception as e:
            print(red(f"\n  ERROR processing {pdf_path.name}: {e}"))
            import traceback
            traceback.print_exc()
            continue

    # Save final outputs
    save_chunks(all_chunks)
    save_manifest(manifest)
    print_stats(all_chunks)


if __name__ == "__main__":
    main()
