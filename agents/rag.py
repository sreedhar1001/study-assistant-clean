"""PDF text extraction, chunking, local embeddings, and semantic retrieval."""

from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from io import BytesIO
import math
from pathlib import PurePath
import re
from collections.abc import Sequence

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MAX_PDF_BYTES = 200 * 1024 * 1024
MAX_PDF_PAGES = 120
MAX_INDEX_CHUNKS = 600
CHUNK_CHARS = 1200
CHUNK_OVERLAP = 180
MIN_RELEVANCE = 0.12


def safe_display_name(name: str) -> str:
    """Reduce an uploaded name to display-only characters; never use it as a path."""
    basename = PurePath(name.replace("\\", "/")).name
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", basename).strip(" ._")
    return (cleaned or "course-material.pdf")[:120]


def split_page_text(text: str, filename: str, page_number: int) -> list[dict]:
    """Split a page into overlapping chunks while keeping its source location."""
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    chunks = []
    start = 0
    while start < len(normalized):
        end = min(start + CHUNK_CHARS, len(normalized))
        if end < len(normalized):
            boundary = normalized.rfind(" ", start + CHUNK_CHARS // 2, end)
            if boundary > start:
                end = boundary
        chunk_text = normalized[start:end].strip()
        if chunk_text:
            chunks.append({"file_name": filename, "page": page_number, "text": chunk_text})
        if end >= len(normalized):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


def extract_pdf_chunks(pdf_bytes: bytes, filename: str) -> list[dict]:
    """Extract selectable text from a bounded PDF and retain page references."""
    if not isinstance(pdf_bytes, bytes) or not pdf_bytes:
        raise ValueError("Choose a PDF file first.")
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise ValueError("PDF files must be 200 MB or smaller.")
    if not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("The uploaded file does not look like a valid PDF.")
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise ValueError("Install the PDF dependency with `pip install -r requirements.txt`.") from error

    try:
        reader = PdfReader(BytesIO(pdf_bytes), strict=False)
        if reader.is_encrypted:
            raise ValueError("This PDF is password-protected. Upload an unlocked copy.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ValueError(f"PDF files are limited to {MAX_PDF_PAGES} pages.")
        display_name = safe_display_name(filename)
        chunks = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            chunks.extend(split_page_text(text, display_name, page_number))
            if len(chunks) > MAX_INDEX_CHUNKS:
                raise ValueError(f"This PDF creates more than {MAX_INDEX_CHUNKS} passages. Upload a smaller section.")
    except ValueError:
        raise
    except Exception as error:
        raise ValueError("I could not read this PDF. Check that it is valid and not damaged.") from error

    if not chunks:
        raise ValueError("No selectable text was found. Scanned-image PDFs need OCR before they can be searched.")
    return chunks


@lru_cache(maxsize=1)
def get_embedding_model():
    """Load one multilingual ONNX embedding model per app process."""
    try:
        from fastembed import TextEmbedding
    except ImportError as error:
        raise RuntimeError("Install the embedding dependency with `pip install -r requirements.txt`.") from error
    return TextEmbedding(model_name=MODEL_NAME)


def build_index(pdf_bytes: bytes, filename: str, embedder=None) -> dict:
    """Extract and embed PDF passages. The caller decides where to keep the index."""
    chunks = extract_pdf_chunks(pdf_bytes, filename)
    embedder = embedder or get_embedding_model()
    vectors = list(embedder.embed([chunk["text"] for chunk in chunks]))
    if len(vectors) != len(chunks):
        raise RuntimeError("The embedding model did not return one vector for each passage.")
    for chunk, vector in zip(chunks, vectors):
        chunk["embedding"] = [float(value) for value in vector]
    return {
        "file_name": chunks[0]["file_name"],
        "file_hash": sha256(pdf_bytes).hexdigest(),
        "chunks": chunks,
    }


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def retrieve_passages(
    index: dict,
    question: str,
    embedder=None,
    *,
    top_k: int = 4,
    min_relevance: float = MIN_RELEVANCE,
) -> list[dict]:
    """Return the most relevant embedded passages for a learner's question."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Type a question about the PDF first.")
    if type(top_k) is not int or not 1 <= top_k <= 10:
        raise ValueError("Choose between 1 and 10 passages to retrieve.")
    chunks = index.get("chunks") if isinstance(index, dict) else None
    if not isinstance(chunks, list) or not chunks:
        raise ValueError("Upload and index a PDF before retrieving passages.")
    embedder = embedder or get_embedding_model()
    query_vectors = list(embedder.embed([question.strip()[:1000]]))
    if not query_vectors:
        return []
    query_vector = [float(value) for value in query_vectors[0]]
    ranked = []
    for chunk in chunks:
        embedding = chunk.get("embedding")
        if not isinstance(embedding, list):
            continue
        score = cosine_similarity(query_vector, embedding)
        if score >= min_relevance:
            ranked.append({**chunk, "score": score})
    return sorted(ranked, key=lambda item: item["score"], reverse=True)[:top_k]


def source_labels(passages: Sequence[dict]) -> list[str]:
    """Return stable, deduplicated filename and page labels for citations."""
    seen = set()
    labels = []
    for passage in passages:
        label = f"{passage['file_name']}, p. {passage['page']}"
        if label not in seen:
            seen.add(label)
            labels.append(label)
    return labels


def format_passages(passages: Sequence[dict]) -> str:
    """Format passages with explicit page labels for the existing answer provider."""
    return "\n\n".join(
        f"[{passage['file_name']}, page {passage['page']}]\n{passage['text']}"
        for passage in passages
    )
