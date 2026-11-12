
from pathlib import Path

import pytest

from src.knowledge.chunker import SemanticChunker
from src.knowledge.markdown_parser import MarkdownParser


@pytest.fixture
def documents():
    parser = MarkdownParser(Path("data"))
    return parser.parse_all()


def test_chunks_all_documents(documents):
    chunker = SemanticChunker()

    chunks = chunker.chunk_documents(documents)

    assert chunks
    assert all(chunk.content.strip() for chunk in chunks)


def test_chunk_metadata_is_preserved(documents):
    chunker = SemanticChunker()
    chunks = chunker.chunk_documents(documents)

    chunk = chunks[0]

    assert chunk.document_id
    assert chunk.metadata["document_id"] == chunk.document_id
    assert chunk.metadata["document_type"] in {
        "historical_incident",
        "runbook",
    }
    assert chunk.metadata["source_path"].endswith(".md")
    assert chunk.metadata["section"]
    assert "section_path" in chunk.metadata


def test_chunk_ids_are_deterministic(documents):
    chunker = SemanticChunker()

    first = chunker.chunk_documents(documents)
    second = chunker.chunk_documents(documents)

    assert [c.chunk_id for c in first] == [
        c.chunk_id for c in second
    ]


def test_chunks_respect_configured_size():
    from src.knowledge.markdown_parser import (
        DocumentSection,
        ParsedDocument,
    )

    document = ParsedDocument(
        document_id="doc_test",
        document_type="runbook",
        title="Large Document",
        source_path="runbooks/test.md",
        sections=(
            DocumentSection(
                heading="Details",
                heading_path=("Details",),
                level=2,
                content="\n\n".join(
                    f"Paragraph {i}: " + ("evidence " * 15)
                    for i in range(20)
                ),
            ),
        ),
    )

    chunker = SemanticChunker(chunk_size=300, chunk_overlap=40)
    chunks = chunker.chunk_document(document)

    assert len(chunks) > 1
    assert all(len(chunk.content) <= 400 for chunk in chunks)


def test_section_context_is_included(documents):
    chunks = SemanticChunker().chunk_documents(documents)

    assert any("Section:" in chunk.content for chunk in chunks)


def test_empty_document_produces_no_chunks():
    from src.knowledge.markdown_parser import ParsedDocument

    document = ParsedDocument(
        document_id="doc_empty",
        document_type="runbook",
        title="Empty",
        source_path="runbooks/empty.md",
        sections=(),
    )

    assert SemanticChunker().chunk_document(document) == []


def test_invalid_chunk_size_is_rejected():
    with pytest.raises(ValueError):
        SemanticChunker(chunk_size=50)


def test_invalid_overlap_is_rejected():
    with pytest.raises(ValueError):
        SemanticChunker(chunk_size=200, chunk_overlap=200)
