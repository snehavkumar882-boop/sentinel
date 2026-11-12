
"""Markdown document discovery and parsing for Sentinel's knowledge base."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DocumentSection:
    """A Markdown section with its heading hierarchy and original content."""

    heading: str
    heading_path: tuple[str, ...]
    level: int
    content: str


@dataclass(frozen=True)
class ParsedDocument:
    """Structured representation of a historical incident or runbook."""

    document_id: str
    document_type: str
    title: str
    source_path: str
    sections: tuple[DocumentSection, ...]
    incident_id: str | None = None
    runbook_id: str | None = None

    @property
    def metadata(self) -> dict:
        """Return document-level metadata for indexing."""
        return {
            "document_id": self.document_id,
            "document_type": self.document_type,
            "title": self.title,
            "source_path": self.source_path,
            "incident_id": self.incident_id or "",
            "runbook_id": self.runbook_id or "",
        }


class MarkdownParser:
    """Discover and parse Markdown incidents and operational runbooks."""

    SUPPORTED_DIRECTORIES = {
        "historical_incidents": "historical_incident",
        "runbooks": "runbook",
    }

    HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
    INCIDENT_PATTERN = re.compile(r"\bINC-\d{4}-\d{2}-\d{2}\b")
    RUNBOOK_PATTERN = re.compile(r"\bRUNBOOK-[A-Z]+-\d{3}\b")

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir).resolve()

    def discover_documents(self) -> list[Path]:
        """Find supported Markdown documents in the knowledge directories."""
        discovered = []

        for directory in self.SUPPORTED_DIRECTORIES:
            source_dir = self.data_dir / directory

            if not source_dir.exists():
                continue

            discovered.extend(
                path
                for path in source_dir.rglob("*.md")
                if path.is_file()
            )

        return sorted(discovered)

    def parse_file(self, file_path: str | Path) -> ParsedDocument:
        """Parse one Markdown file while preserving its section content."""
        path = Path(file_path).resolve()

        try:
            relative_path = path.relative_to(self.data_dir)
        except ValueError as exc:
            raise ValueError(
                f"Document must be inside the configured data directory: {path}"
            ) from exc

        if path.suffix.lower() != ".md":
            raise ValueError(f"Unsupported document format: {path.suffix}")

        if not path.is_file():
            raise FileNotFoundError(path)

        directory = relative_path.parts[0]

        if directory not in self.SUPPORTED_DIRECTORIES:
            raise ValueError(
                f"Unsupported knowledge directory: {directory}"
            )

        raw_text = path.read_text(encoding="utf-8")
        document_type = self.SUPPORTED_DIRECTORIES[directory]

        title, sections = self._parse_markdown(raw_text, path.stem)

        incident_match = self.INCIDENT_PATTERN.search(
            f"{path.name}\n{raw_text}"
        )
        runbook_match = self.RUNBOOK_PATTERN.search(
            f"{path.name}\n{raw_text}"
        )

        # Stable across runs and independent of document content changes.
        identity = f"{document_type}:{relative_path.as_posix()}"
        document_hash = hashlib.sha256(
            identity.encode("utf-8")
        ).hexdigest()[:16]

        return ParsedDocument(
            document_id=f"doc_{document_hash}",
            document_type=document_type,
            title=title,
            source_path=relative_path.as_posix(),
            sections=tuple(sections),
            incident_id=incident_match.group(0) if incident_match else None,
            runbook_id=runbook_match.group(0) if runbook_match else None,
        )

    def parse_all(self) -> list[ParsedDocument]:
        """Discover and parse all supported Markdown documents."""
        return [
            self.parse_file(path)
            for path in self.discover_documents()
        ]

    @classmethod
    def _parse_markdown(
        cls,
        text: str,
        fallback_title: str,
    ) -> tuple[str, list[DocumentSection]]:
        """Extract the title and heading-aware sections."""
        lines = text.splitlines()

        title = fallback_title
        heading_stack: list[str] = []
        sections: list[DocumentSection] = []

        current_heading = "Introduction"
        current_level = 1
        current_path: tuple[str, ...] = ()
        current_lines: list[str] = []

        inside_fence = False
        fence_marker = None
        title_found = False

        def save_section() -> None:
            content = "\n".join(current_lines).strip()

            if content:
                sections.append(
                    DocumentSection(
                        heading=current_heading,
                        heading_path=current_path,
                        level=current_level,
                        content=content,
                    )
                )

        for line in lines:
            stripped = line.strip()

            # Do not interpret headings inside fenced code blocks.
            fence_match = re.match(r"^(```+|~~~+)", stripped)

            if fence_match:
                marker = fence_match.group(1)

                if not inside_fence:
                    inside_fence = True
                    fence_marker = marker[0]
                elif marker[0] == fence_marker:
                    inside_fence = False
                    fence_marker = None

                current_lines.append(line)
                continue

            if not inside_fence:
                match = cls.HEADING_PATTERN.match(line)

                if match:
                    save_section()
                    current_lines = []

                    level = len(match.group(1))
                    heading = match.group(2).strip()

                    if level == 1 and not title_found:
                        title = heading
                        title_found = True
                        current_heading = "Introduction"
                        current_level = 1
                        current_path = ()
                        continue

                    heading_stack = heading_stack[: level - 1]
                    heading_stack.append(heading)

                    current_heading = heading
                    current_level = level
                    current_path = tuple(heading_stack)
                    continue

            current_lines.append(line)

        save_section()

        return title, sections
