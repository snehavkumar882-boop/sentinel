
from pathlib import Path

import pytest

from src.knowledge.knowledge_base import KnowledgeBase


@pytest.fixture
def knowledge_base(tmp_path: Path):
    data_dir = tmp_path / "data"

    incidents_dir = data_dir / "historical_incidents"
    runbooks_dir = data_dir / "runbooks"

    incidents_dir.mkdir(parents=True)
    runbooks_dir.mkdir(parents=True)

    (incidents_dir / "INC-2024-03-12-pool.md").write_text(
        """# Database Connection Pool Exhaustion

## Symptoms

Database connections are exhausted and API requests time out.

## Root Cause

Connection leaks caused the database pool to reach its limit.

## Resolution

Restart affected services and inspect connection management.
""",
        encoding="utf-8",
    )

    (runbooks_dir / "RUNBOOK-API-001-errors.md").write_text(
        """# High API 5xx Rate

## Investigation

Inspect API logs and upstream response codes.

## Resolution

Check upstream service availability and restart unhealthy instances.
""",
        encoding="utf-8",
    )

    return KnowledgeBase(
        data_dir=data_dir,
        vector_store_dir=tmp_path / "vector_store",
        min_similarity=0.0,
    )


def test_knowledge_base_initial_status(knowledge_base):
    status = knowledge_base.get_status()

    assert status["source_documents"] == 2
    assert status["indexed_chunks"] == 0


def test_ingest_documents(knowledge_base):
    result = knowledge_base.ingest()

    assert result["documents_discovered"] == 2
    assert result["chunks_created"] > 0
    assert result["chunks_indexed"] == result["chunks_created"]
    assert result["total_chunks_in_store"] == result["chunks_created"]


def test_search_after_ingestion(knowledge_base):
    knowledge_base.ingest()

    results = knowledge_base.search(
        "database connection pool exhaustion"
    )

    assert results
    assert results[0]["document_type"] == "historical_incident"


def test_search_with_metadata_filter(knowledge_base):
    knowledge_base.ingest()

    results = knowledge_base.search(
        "API errors and upstream failures",
        where={"document_type": "runbook"},
    )

    assert results
    assert all(
        result["document_type"] == "runbook"
        for result in results
    )


def test_search_returns_source_traceability(knowledge_base):
    knowledge_base.ingest()

    results = knowledge_base.search(
        "database connection pool exhaustion"
    )

    assert results

    matching_source = [
        result
        for result in results
        if result["source_path"] == (
            "historical_incidents/INC-2024-03-12-pool.md"
        )
    ]

    assert matching_source

    result = matching_source[0]

    assert result["document_id"]
    assert result["chunk_id"]
    assert result["section"]
    assert result["metadata"]["source_path"]


def test_repeated_ingestion_does_not_duplicate_chunks(
    knowledge_base,
):
    first = knowledge_base.ingest()
    second = knowledge_base.ingest()

    assert first["chunks_created"] == second["chunks_created"]
    assert (
        first["total_chunks_in_store"]
        == second["total_chunks_in_store"]
    )


def test_rebuild_index(knowledge_base):
    knowledge_base.ingest()

    result = knowledge_base.rebuild()

    assert result["documents_discovered"] == 2
    assert result["chunks_created"] > 0
    assert (
        result["total_chunks_in_store"]
        == result["chunks_created"]
    )


def test_empty_query(knowledge_base):
    knowledge_base.ingest()

    assert knowledge_base.search("") == []


def test_empty_knowledge_directory(tmp_path):
    data_dir = tmp_path / "empty_data"
    data_dir.mkdir()

    kb = KnowledgeBase(
        data_dir=data_dir,
        vector_store_dir=tmp_path / "empty_store",
    )

    result = kb.ingest()

    assert result["documents_discovered"] == 0
    assert result["chunks_created"] == 0
    assert result["total_chunks_in_store"] == 0


def test_invalid_top_k(tmp_path):
    with pytest.raises(ValueError):
        KnowledgeBase(
            data_dir=tmp_path,
            vector_store_dir=tmp_path / "store",
            top_k=0,
        )


def test_invalid_similarity_threshold(tmp_path):
    with pytest.raises(ValueError):
        KnowledgeBase(
            data_dir=tmp_path,
            vector_store_dir=tmp_path / "store",
            min_similarity=1.5,
        )
