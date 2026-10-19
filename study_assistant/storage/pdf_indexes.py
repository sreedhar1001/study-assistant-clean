"""Bounded in-memory PDF index storage for the local HTTP API."""

from __future__ import annotations

import time
import uuid
from threading import Lock

PDF_INDEX_TTL_SECONDS = 3600
MAX_ACTIVE_PDF_INDEXES = 8
PDF_INDEXES: dict[str, tuple[float, dict]] = {}
PDF_INDEXES_LOCK = Lock()


def store_pdf_index(index: dict) -> str:
    now = time.monotonic()
    index_id = uuid.uuid4().hex
    with PDF_INDEXES_LOCK:
        expired = [key for key, (created, _) in PDF_INDEXES.items() if now - created > PDF_INDEX_TTL_SECONDS]
        for key in expired:
            PDF_INDEXES.pop(key, None)
        while len(PDF_INDEXES) >= MAX_ACTIVE_PDF_INDEXES:
            oldest = min(PDF_INDEXES, key=lambda key: PDF_INDEXES[key][0])
            PDF_INDEXES.pop(oldest, None)
        PDF_INDEXES[index_id] = (now, index)
    return index_id


def get_pdf_index(index_id: str) -> dict | None:
    now = time.monotonic()
    with PDF_INDEXES_LOCK:
        stored = PDF_INDEXES.get(index_id)
        if stored is None:
            return None
        created, index = stored
        if now - created > PDF_INDEX_TTL_SECONDS:
            PDF_INDEXES.pop(index_id, None)
            return None
        return index


def delete_pdf_index(index_id: str) -> None:
    with PDF_INDEXES_LOCK:
        PDF_INDEXES.pop(index_id, None)
