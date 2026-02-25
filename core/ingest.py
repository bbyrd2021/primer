# core/ingest.py
import fitz  # PyMuPDF
from pathlib import Path

# Constants
MIN_CHUNK_WORDS: int = 50
CHUNK_SIZE: int = 800
CHUNK_OVERLAP: int = 100


def extract_text(pdf_path: str) -> tuple[str, list[dict]]:
    """Extract full text and page metadata from a PDF.

    Args:
        pdf_path: Absolute or relative path to the PDF file.

    Returns:
        A tuple of (full_text, pages) where:
        - full_text is the concatenated text of all pages (for card extraction).
        - pages is a list of dicts with keys: text, page, source (for chunking).
    """
    doc = fitz.open(pdf_path)
    pages = []
    full_text_parts = []

    for page_num, page in enumerate(doc):
        text = page.get_text("text").strip()
        if text:
            pages.append({
                "text": text,
                "page": page_num + 1,
                "source": Path(pdf_path).name,
            })
            full_text_parts.append(text)

    doc.close()
    return "\n\n".join(full_text_parts), pages


def chunk_pages(pages: list[dict]) -> list[dict]:
    """Split page text into overlapping chunks with source metadata.

    Uses word-level splitting with CHUNK_OVERLAP words of overlap between
    adjacent chunks to preserve context across chunk boundaries.

    Args:
        pages: List of page dicts with keys: text, page, source.

    Returns:
        List of chunk dicts with keys: text, page, source, chunk_id.
    """
    chunks = []

    for page in pages:
        words = page["text"].split()
        for i in range(0, len(words), CHUNK_SIZE - CHUNK_OVERLAP):
            chunk_words = words[i : i + CHUNK_SIZE]
            if len(chunk_words) < MIN_CHUNK_WORDS:
                continue
            chunks.append({
                "text": " ".join(chunk_words),
                "page": page["page"],
                "source": page["source"],
                "chunk_id": f"{page['source']}_p{page['page']}_c{i}",
            })

    return chunks


def estimate_text_density(full_text: str, page_count: int) -> float:
    """Return average characters per page. Low values indicate a scanned PDF.

    Args:
        full_text: The full concatenated text of the PDF.
        page_count: Total number of pages in the PDF.

    Returns:
        Average characters per page. Values below ~100 typically indicate
        a scanned or image-only PDF with little extractable text.
    """
    if page_count == 0:
        return 0.0
    return len(full_text) / page_count
