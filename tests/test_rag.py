"""Offline tests for PDF extraction and local embedding retrieval."""

import sys
import types
import unittest
from unittest.mock import patch

from agents import rag


class FakePage:
    def __init__(self, text):
        self.text = text

    def extract_text(self):
        return self.text


class FakePdfReader:
    pages = [FakePage("Plants use sunlight to make food."), FakePage("Water moves through the water cycle.")]
    is_encrypted = False

    def __init__(self, stream, strict=False):
        self.stream = stream
        self.strict = strict


class FakeEmbedder:
    def embed(self, texts):
        for text in texts:
            if "plant" in text.casefold() or "sunlight" in text.casefold():
                yield [1.0, 0.0]
            else:
                yield [0.0, 1.0]


class RagTests(unittest.TestCase):
    def test_pdf_extraction_keeps_filename_and_page_numbers(self):
        fake_pypdf = types.ModuleType("pypdf")
        fake_pypdf.PdfReader = FakePdfReader
        with patch.dict(sys.modules, {"pypdf": fake_pypdf}):
            chunks = rag.extract_pdf_chunks(b"%PDF-fake", "C:\\notes\\biology.pdf")
        self.assertEqual(chunks[0]["file_name"], "biology.pdf")
        self.assertEqual(chunks[0]["page"], 1)
        self.assertEqual(chunks[1]["page"], 2)

    def test_build_and_retrieve_uses_embeddings_and_returns_source(self):
        fake_pypdf = types.ModuleType("pypdf")
        fake_pypdf.PdfReader = FakePdfReader
        with patch.dict(sys.modules, {"pypdf": fake_pypdf}):
            index = rag.build_index(b"%PDF-fake", "biology.pdf", embedder=FakeEmbedder())
        results = rag.retrieve_passages(index, "How do plants use sunlight?", embedder=FakeEmbedder())
        self.assertEqual(results[0]["page"], 1)
        self.assertIn("sunlight", results[0]["text"])
        self.assertEqual(rag.source_labels(results), ["biology.pdf, p. 1"])
        self.assertIn("[biology.pdf, page 1]", rag.format_passages(results))

    def test_rejects_invalid_pdf_bytes(self):
        with self.assertRaisesRegex(ValueError, "valid PDF"):
            rag.extract_pdf_chunks(b"not a pdf", "notes.pdf")

    def test_reports_scanned_pdf_without_selectable_text(self):
        fake_pypdf = types.ModuleType("pypdf")
        fake_pypdf.PdfReader = lambda stream, strict=False: type(
            "Reader", (), {"is_encrypted": False, "pages": [FakePage("")]}
        )()
        with patch.dict(sys.modules, {"pypdf": fake_pypdf}):
            with self.assertRaisesRegex(ValueError, "Scanned-image PDFs need OCR"):
                rag.extract_pdf_chunks(b"%PDF-fake", "scan.pdf")


if __name__ == "__main__":
    unittest.main()
