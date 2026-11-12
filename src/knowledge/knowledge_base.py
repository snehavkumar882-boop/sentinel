
"""KnowledgeBase orchestration for Sentinel's RAG layer."""

from pathlib import Path
from typing import Any

from src.knowledge.chunker import SemanticChunker
from src.knowledge.markdown_parser import MarkdownParser
from src.knowledge.vector_store import VectorStore


class KnowledgeBase:
    """Coordinate document ingestion and semantic knowledge retrieval."""

    def __init__(
        self,
        data_dir: str | Path = "data",
        vector_store_dir: str | Path = "data/vector_store",
        chunk_size: int = 1200,
        chunk_overlap: int = 150,
        top_k: int = 5,
        min_similarity: float = 0.35,
    ) -> None:
        if top_k < 1:
            raise ValueError("top_k must be at least 1")

        if not 0.0 <= min_similarity <= 1.0:
            raise ValueError("min_similarity must be between 0 and 1")

        self.data_dir = Path(data_dir)

        self.parser = MarkdownParser(self.data_dir)

        self.chunker = SemanticChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        self.vector_store = VectorStore(
            persist_directory=vector_store_dir,
            distance_threshold=min_similarity,
        )

        self.top_k = top_k
        self.min_similarity = min_similarity

    def ingest(self) -> dict[str, int]:
        """Parse, chunk and upsert all supported knowledge documents.

        Note:
            Upserting does not remove stale chunks belonging to source
            documents that have been deleted. Use rebuild() for a full
            index refresh.
        """
        documents = self.parser.parse_all()
        chunks = self.chunker.chunk_documents(documents)

        indexed_chunks = self.vector_store.add_chunks(chunks)

        return {
            "documents_discovered": len(documents),
            "chunks_created": len(chunks),
            "chunks_indexed": indexed_chunks,
            "total_chunks_in_store": self.vector_store.count,
        }

    def search(
        self,
        query: str,
        top_k: int | None = None,
        where: dict[str, Any] | None = None,
        min_similarity: float | None = None,
    ) -> list[dict[str, Any]]:
        """Search the knowledge base with optional metadata filters."""

        requested_top_k = self.top_k if top_k is None else top_k

        if requested_top_k < 1:
            raise ValueError("top_k must be at least 1")

        threshold = (
            self.min_similarity
            if min_similarity is None
            else min_similarity
        )

        if not 0.0 <= threshold <= 1.0:
            raise ValueError(
                "min_similarity must be between 0 and 1"
            )

        return self.vector_store.search(
            query=query,
            top_k=requested_top_k,
            where=where,
            min_similarity=threshold,
        )

    def rebuild(self) -> dict[str, int]:
        """Clear the existing index and rebuild it from source documents."""
        self.vector_store.reset()
        return self.ingest()

    def get_status(self) -> dict[str, Any]:
        """Return a summary of the knowledge base."""
        documents = self.parser.parse_all()

        return {
            "source_documents": len(documents),
            "indexed_chunks": self.vector_store.count,
            "vector_store_path": str(
                self.vector_store.persist_directory
            ),
            "collection": self.vector_store.collection.name,
            "embedding_model": "ChromaDB default embedding function",
        }

