
from pathlib import Path

import pytest

from src.knowledge.chunker import DocumentChunk
from src.knowledge.vector_store import VectorStore


@pytest.fixture
def vector_store(tmp_path: Path):
    return VectorStore(
        persist_directory=tmp_path / "vector_db",
        collection_name="test_knowledge",
        distance_threshold=0.0,
    )


@pytest.fixture
def sample_chunks():
    return [
        DocumentChunk(
            chunk_id="chunk_db_001",
            document_id="INC-DB-001",
            content=(
                "Database connection pool saturation causes "
                "request timeouts. Check active connections, "
                "pool limits and connection leaks."
            ),
            metadata={
                "document_id": "INC-DB-001",
                "document_type": "incident",
                "title": "Database Connection Pool Saturation",
                "section": "Root Cause",
                "section_path": "Investigation > Root Cause",
                "source_path": "data/historical_incidents/db.md",
                "incident_id": "INC-DB-001",
            },
        ),
        DocumentChunk(
            chunk_id="chunk_api_001",
            document_id="RUNBOOK-API-001",
            content=(
                "High API 5xx error rates can indicate "
                "upstream service failures. Inspect API logs "
                "and upstream response codes."
            ),
            metadata={
                "document_id": "RUNBOOK-API-001",
                "document_type": "runbook",
                "title": "High API 5xx Rate",
                "section": "Troubleshooting",
                "section_path": "Troubleshooting",
                "source_path": "data/runbooks/api.md",
                "runbook_id": "RUNBOOK-API-001",
            },
        ),
    ]


def test_add_chunks(vector_store, sample_chunks):
    added = vector_store.add_chunks(sample_chunks)

    assert added == 2
    assert vector_store.count == 2


def test_empty_chunk_list(vector_store):
    assert vector_store.add_chunks([]) == 0
    assert vector_store.count == 0


def test_semantic_search(vector_store, sample_chunks):
    vector_store.add_chunks(sample_chunks)

    results = vector_store.search(
        "database connection pool exhaustion",
        top_k=2,
    )

    assert results
    assert results[0]["chunk_id"] == "chunk_db_001"
    assert results[0]["document_id"] == "INC-DB-001"


def test_metadata_filter(vector_store, sample_chunks):
    vector_store.add_chunks(sample_chunks)

    results = vector_store.search(
        "service errors and failures",
        top_k=5,
        where={"document_type": "runbook"},
    )

    assert results
    assert all(
        result["document_type"] == "runbook"
        for result in results
    )


def test_source_traceability(vector_store, sample_chunks):
    vector_store.add_chunks(sample_chunks)

    results = vector_store.search(
        "database connection pool saturation",
        top_k=1,
    )

    result = results[0]

    assert result["source_path"] == (
        "data/historical_incidents/db.md"
    )
    assert result["section"] == "Root Cause"
    assert result["metadata"]["incident_id"] == "INC-DB-001"
    assert 0.0 <= result["similarity"] <= 1.0


def test_minimum_similarity_threshold(
    vector_store,
    sample_chunks,
):
    vector_store.add_chunks(sample_chunks)

    results = vector_store.search(
        "database connection pool saturation",
        top_k=2,
        min_similarity=1.0,
    )

    assert results == []


def test_empty_query(vector_store, sample_chunks):
    vector_store.add_chunks(sample_chunks)

    assert vector_store.search("") == []
    assert vector_store.search("   ") == []


def test_invalid_top_k(vector_store):
    with pytest.raises(ValueError):
        vector_store.search("database failure", top_k=0)


def test_invalid_similarity_threshold(vector_store):
    with pytest.raises(ValueError):
        vector_store.search(
            "database failure",
            min_similarity=1.5,
        )


def test_reset_collection(vector_store, sample_chunks):
    vector_store.add_chunks(sample_chunks)

    vector_store.reset()

    assert vector_store.count == 0


def test_persistence_after_reopening(tmp_path, sample_chunks):
    database_path = tmp_path / "persistent_db"

    first_store = VectorStore(
        persist_directory=database_path,
        collection_name="persistence_test",
        distance_threshold=0.0,
    )

    first_store.add_chunks(sample_chunks)

    second_store = VectorStore(
        persist_directory=database_path,
        collection_name="persistence_test",
        distance_threshold=0.0,
    )

    assert second_store.count == 2

    results = second_store.search(
        "database connection pool",
        top_k=1,
    )

    assert results
    assert results[0]["document_id"] == "INC-DB-001"
