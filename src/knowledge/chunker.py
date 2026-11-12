
"""Section-aware Markdown chunking for Sentinel."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from src.knowledge.markdown_parser import ParsedDocument


@dataclass(frozen=True)
class DocumentChunk:
    """A retrievable piece of a parsed knowledge document."""

    chunk_id: str
    document_id: str
    content: str
    metadata: dict[str, Any]


class SemanticChunker:
    """Create deterministic, heading-aware chunks from parsed documents."""

    def __init__(
        self,
        chunk_size: int = 1200,
        chunk_overlap: int = 150,
    ):
        if chunk_size < 100:
            raise ValueError("chunk_size must be at least 100 characters")

        if chunk_overlap < 0:
            raise ValueError("chunk_overlap cannot be negative")

        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document(
        self,
        document: ParsedDocument,
    ) -> list[DocumentChunk]:
        """Convert a parsed document into section-aware chunks."""
        chunks: list[DocumentChunk] = []

        for section in document.sections:
            heading_context = " > ".join(section.heading_path)
            section_content = section.content.strip()

            if not section_content:
                continue

            pieces = self._split_section(section_content)

            for chunk_index, piece in enumerate(pieces):
                chunk_content = (
                    f"Document: {document.title}\n"
                    f"Section: {heading_context or section.heading}\n\n"
                    f"{piece}"
                )

                identity = (
                    f"{document.document_id}:"
                    f"{heading_context}:"
                    f"{chunk_index}:"
                    f"{chunk_content}"
                )

                chunk_hash = hashlib.sha256(
                    identity.encode("utf-8")
                ).hexdigest()[:20]

                metadata = {
                    **document.metadata,
                    "section": section.heading,
                    "section_path": heading_context or section.heading,
                    "section_level": section.level,
                    "chunk_index": chunk_index,
                }

                chunks.append(
                    DocumentChunk(
                        chunk_id=f"chunk_{chunk_hash}",
                        document_id=document.document_id,
                        content=chunk_content,
                        metadata=metadata,
                    )
                )

        return chunks

    def chunk_documents(
        self,
        documents: list[ParsedDocument],
    ) -> list[DocumentChunk]:
        """Chunk multiple documents in a deterministic order."""
        chunks = []

        for document in documents:
            chunks.extend(self.chunk_document(document))

        return chunks

    def _split_section(self, content: str) -> list[str]:
        """Pack paragraphs into chunks, splitting oversized paragraphs safely."""
        paragraphs = self._split_paragraphs(content)

        chunks: list[str] = []
        current_parts: list[str] = []
        current_length = 0

        for paragraph in paragraphs:
            fragments = self._split_oversized_paragraph(paragraph)

            for fragment in fragments:
                separator_length = 2 if current_parts else 0
                proposed_length = (
                    current_length + separator_length + len(fragment)
                )

                if current_parts and proposed_length > self.chunk_size:
                    chunks.append("\n\n".join(current_parts))

                    overlap_parts = self._get_overlap(current_parts)
                    current_parts = overlap_parts.copy()
                    current_length = sum(
                        len(part) for part in current_parts
                    ) + max(0, len(current_parts) - 1) * 2

                    # An overlap may leave insufficient space for the next
                    # fragment. Remove older overlap until it fits.
                    while (
                        current_parts
                        and current_length + 2 + len(fragment)
                        > self.chunk_size
                    ):
                        removed = current_parts.pop(0)
                        current_length -= len(removed)
                        if current_parts:
                            current_length -= 2

                if current_parts:
                    current_length += 2

                current_parts.append(fragment)
                current_length += len(fragment)

        if current_parts:
            chunks.append("\n\n".join(current_parts))

        return chunks

    def _split_paragraphs(self, content: str) -> list[str]:
        """Split on blank lines without changing paragraph contents."""
        paragraphs = re.split(r"\n\s*\n", content.strip())

        return [
            paragraph.strip()
            for paragraph in paragraphs
            if paragraph.strip()
        ]

    def _split_oversized_paragraph(
        self,
        paragraph: str,
    ) -> list[str]:
        """Split long paragraphs at line boundaries where possible."""
        if len(paragraph) <= self.chunk_size:
            return [paragraph]

        lines = paragraph.splitlines()
        fragments: list[str] = []
        current: list[str] = []
        current_length = 0

        for line in lines:
            separator = 1 if current else 0

            if current and current_length + separator + len(line) > self.chunk_size:
                fragments.append("\n".join(current))
                current = []
                current_length = 0

            if len(line) > self.chunk_size:
                if current:
                    fragments.append("\n".join(current))
                    current = []
                    current_length = 0

                for start in range(0, len(line), self.chunk_size):
                    fragments.append(
                        line[start:start + self.chunk_size]
                    )
                continue

            if current:
                current_length += 1

            current.append(line)
            current_length += len(line)

        if current:
            fragments.append("\n".join(current))

        return fragments

    def _get_overlap(self, parts: list[str]) -> list[str]:
        """Retain the most recent complete paragraphs within overlap size."""
        selected: list[str] = []
        total = 0

        for part in reversed(parts):
            additional = len(part) + (2 if selected else 0)

            if total + additional > self.chunk_overlap:
                break

            selected.insert(0, part)
            total += additional

        return selected
