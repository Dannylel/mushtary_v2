"""
Build / rebuild the Tender Drafting knowledge base from source documents.

Usage (from project root, with the local Ollama embed model pulled):
    ollama pull nomic-embed-text
    python -m agents.rag.index_documents path/to/docs --authority law --category IT
    python -m agents.rag.index_documents past_tenders/ --approved   # only approved precedent

Accepts .pdf (via PyMuPDF), .md, and .txt files, or a directory (scanned recursively).
Each file is chunked, embedded, and added with provenance metadata, then the whole store
is saved to agents/rag/corpora/tender_kb/.

PROVENANCE RULE: only index human-approved material (use --approved for past tenders).
Never index un-approved AI drafts.
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from tqdm import tqdm

from .chunking import chunk_text
from .knowledge_base import TENDER_KB_DIR
from .schemas import Chunk
from .store import VectorStore

logger = logging.getLogger(__name__)

_SUPPORTED = {".pdf", ".docx", ".md", ".txt"}


def _read_docx(path: Path) -> str:
    """Extract paragraph text from a .docx (a zip of XML) with no extra dependency."""
    import re
    import zipfile

    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    # Preserve paragraph breaks, then strip all tags.
    xml = xml.replace("</w:p>", "\n").replace("<w:tab/>", "\t")
    text = re.sub(r"<[^>]+>", "", xml)
    for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&#160;", " ")):
        text = text.replace(a, b)
    return "\n".join(line.strip() for line in text.split("\n") if line.strip())


def _read_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        import fitz  # PyMuPDF — already a project dependency

        doc = fitz.open(str(path))
        text = "\n\n".join(page.get_text() for page in doc)
        doc.close()
        return text
    if suffix == ".docx":
        return _read_docx(path)
    return path.read_text(encoding="utf-8", errors="ignore")


def _gather(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() in _SUPPORTED else []
    return [p for p in sorted(input_path.rglob("*")) if p.suffix.lower() in _SUPPORTED]


def build_index(
    input_path: str | Path,
    *,
    authority: str = "reference",
    category: str | None = None,
    approved: bool = False,
    rebuild: bool = False,
) -> VectorStore:
    """Index every supported file under input_path into the tender KB. Returns the store."""
    input_path = Path(input_path)
    files = _gather(input_path)
    if not files:
        raise SystemExit(f"No .pdf/.md/.txt files found at {input_path}")

    # Append to the existing corpus by default; --rebuild starts fresh.
    store = VectorStore() if rebuild else VectorStore.load(TENDER_KB_DIR)

    for path in tqdm(files, desc="Indexing", unit="file"):
        text = _read_file(path)
        pieces = chunk_text(text)
        if not pieces:
            logger.warning("No text extracted from %s — skipping.", path.name)
            continue
        meta = {
            "source": path.name,
            "authority": authority,   # law | regulation | policy | past_tender | reference
            "approved": approved,
        }
        if category:
            meta["category"] = category
        store.add([Chunk(text=p, metadata=dict(meta)) for p in pieces], show_progress=False)

    store.save(TENDER_KB_DIR)
    print(f"Tender KB now holds {len(store)} chunks at {TENDER_KB_DIR}")
    return store


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Tender Drafting knowledge base.")
    parser.add_argument("input", help="A file or directory of .pdf/.md/.txt sources.")
    parser.add_argument("--authority", default="reference",
                        help="Provenance/authority tag: law | regulation | policy | past_tender | reference")
    parser.add_argument("--category", default=None, help="Optional category tag for these docs.")
    parser.add_argument("--approved", action="store_true",
                        help="Mark these sources as human-approved (required for past tenders).")
    parser.add_argument("--rebuild", action="store_true",
                        help="Start a fresh index instead of appending to the existing one.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    build_index(
        args.input,
        authority=args.authority,
        category=args.category,
        approved=args.approved,
        rebuild=args.rebuild,
    )


if __name__ == "__main__":
    main()
