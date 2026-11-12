
"""Persistent ChromaDB vector storage for Sentinel."""

from pathlib import Path
from typing import Any

import chromadb

from src.knowledge.chunker import DocumentChunk


class VectorStore:
    """
    Persistent ChromaDB vector store.

    Responsibilities:
    - Store document chunks and embeddings.
    - Persist indexed data locally.
    - Retrieve semantically relevant chunks.
    - Support metadata filtering.
    - Preserve source traceability.
    """

    def __init__(
        self,
        persist_directory: str | Path = "data/vector_store",
        collection_name: str = "sentinel_knowledge",
        distance_threshold: float = 0.65,
    ) -> None:
        if not 0.0 <= distance_threshold <= 1.0:
            raise ValueError(
                "distance_threshold must be between 0 and 1"
            )

        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        self.distance_threshold = distance_threshold

        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory)
        )

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def count(self) -> int:
        """Return the number of indexed chunks."""
        return self.collection.count()

    def add_chunks(self, chunks: list[DocumentChunk]) -> int:
        """Add or update chunks in the persistent vector store."""
        if not chunks:
            return 0

        ids = []
        documents = []
        metadatas = []

        for chunk in chunks:
            ids.append(chunk.chunk_id)
            documents.append(chunk.content)

            metadata = {
                key: value
                for key, value in chunk.metadata.items()
                if value is not None
            }

            safe_metadata = {}

            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    safe_metadata[key] = value
                else:
                    safe_metadata[key] = str(value)

            metadatas.append(safe_metadata)

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

        return len(ids)

    def search(
        self,
        query: str,
        top_k: int = 5,
        where: dict[str, Any] | None = None,
        min_similarity: float | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve semantically relevant chunks.

        ChromaDB cosine distance is converted to similarity:
            similarity = 1 - distance

        This score is a retrieval measure, not a probability.
        """
        if not query or not query.strip():
            return []

        if top_k < 1:
            raise ValueError("top_k must be at least 1")

        threshold = (
            self.distance_threshold
            if min_similarity is None
            else min_similarity
        )

        if not 0.0 <= threshold <= 1.0:
            raise ValueError(
                "min_similarity must be between 0 and 1"
            )

        total_chunks = self.count

        if total_chunks == 0:
            return []

        results = self.collection.query(
            query_texts=[query.strip()],
            n_results=min(top_k, total_chunks),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        matches = []

        result_ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for chunk_id, content, metadata, distance in zip(
            result_ids,
            documents,
            metadatas,
            distances,
        ):
            similarity = max(
                0.0,
                min(1.0, 1.0 - float(distance)),
            )

            if similarity < threshold:
                continue

            matches.append(
                {
                    "chunk_id": chunk_id,
                    "content": content,
                    "similarity": similarity,
                    "distance": float(distance),
                    "document_id": metadata.get("document_id"),
                    "document_type": metadata.get("document_type"),
                    "title": metadata.get("title"),
                    "section": metadata.get("section"),
                    "source_path": metadata.get("source_path"),
                    "metadata": metadata,
                }
            )

        return matches

    def delete_collection(self) -> None:
        """Delete the collection."""
        self.client.delete_collection(self.collection.name)

    def reset(self) -> None:
        """Remove all indexed chunks safely, including empty collections."""
        total_chunks = self.count

        if total_chunks == 0:
            return

        stored_ids = self.collection.get(
            limit=total_chunks
        )["ids"]

        if stored_ids:
            self.collection.delete(ids=stored_ids)

