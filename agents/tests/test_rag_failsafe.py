"""
RAG fail-safe tests: the RAG layer must NEVER break the pipeline — empty corpus and
unreachable embedding server both degrade to a harmless no-op. These tests run with no
Ollama server required.
"""
import unittest

from agents.rag import build_focused_sow_text, chunk_text
from agents.rag.knowledge_base import TenderKnowledgeBase


class TestChunking(unittest.TestCase):
    def test_empty_input_yields_no_chunks(self):
        self.assertEqual(chunk_text(""), [])
        self.assertEqual(chunk_text("   \n\n  "), [])

    def test_short_text_is_single_chunk(self):
        self.assertEqual(chunk_text("one short paragraph."), ["one short paragraph."])

    def test_long_text_is_split(self):
        doc = ("A paragraph of repeated words. " * 30 + "\n\n") * 10
        chunks = chunk_text(doc)
        self.assertGreater(len(chunks), 1)
        # No chunk should wildly exceed the packing budget (size + one overflow paragraph).
        self.assertTrue(all(len(c) <= 2400 for c in chunks))


class TestSowRetrievalFailsafe(unittest.TestCase):
    def test_short_document_passes_through_unchanged(self):
        text = "A short statement of work. Build a website."
        self.assertEqual(build_focused_sow_text(text), text)

    def test_long_document_never_raises_and_respects_budget(self):
        # With no embedding server this exercises the head+tail fallback; with one running
        # it exercises retrieval. Either way: no exception, output within ~budget.
        long_doc = "Section content sentence. " * 4000
        out = build_focused_sow_text(long_doc, max_chars=12000)
        self.assertLessEqual(len(out), 13000)
        self.assertGreater(len(out), 0)


class TestKnowledgeBaseFailsafe(unittest.TestCase):
    def test_missing_corpus_directory_loads_empty(self):
        kb = TenderKnowledgeBase(directory="nonexistent_dir_xyz")
        self.assertFalse(kb.available)
        self.assertEqual(kb.retrieve("anything"), [])

    def test_format_context_empty_is_empty_string(self):
        self.assertEqual(TenderKnowledgeBase.format_context([]), "")


if __name__ == "__main__":
    unittest.main()
