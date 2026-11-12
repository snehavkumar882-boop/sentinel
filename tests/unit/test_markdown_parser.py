
from pathlib import Path

import pytest

from src.knowledge.markdown_parser import MarkdownParser


@pytest.fixture
def parser():
    return MarkdownParser(Path("data"))


def test_discovers_all_knowledge_documents(parser):
    documents = parser.discover_documents()

    assert len(documents) == 6
    assert all(path.suffix == ".md" for path in documents)


def test_parses_historical_incident(parser):
    path = (
        Path("data/historical_incidents")
        / "INC-2024-03-12-connection-pool-exhaustion.md"
    )

    document = parser.parse_file(path)

    assert document.document_type == "historical_incident"
    assert document.incident_id == "INC-2024-03-12"
    assert document.title
    assert document.sections
    assert document.document_id.startswith("doc_")


def test_parses_runbook(parser):
    path = (
        Path("data/runbooks")
        / "RUNBOOK-DB-002-connection-pool-saturation.md"
    )

    document = parser.parse_file(path)

    assert document.document_type == "runbook"
    assert document.runbook_id == "RUNBOOK-DB-002"
    assert document.sections


def test_document_id_is_deterministic(parser):
    path = (
        Path("data/historical_incidents")
        / "INC-2024-03-12-connection-pool-exhaustion.md"
    )

    first = parser.parse_file(path)
    second = parser.parse_file(path)

    assert first.document_id == second.document_id


def test_metadata_contains_source_information(parser):
    path = (
        Path("data/runbooks")
        / "RUNBOOK-DB-002-connection-pool-saturation.md"
    )

    document = parser.parse_file(path)
    metadata = document.metadata

    assert metadata["document_id"] == document.document_id
    assert metadata["document_type"] == "runbook"
    assert metadata["runbook_id"] == "RUNBOOK-DB-002"
    assert metadata["source_path"].endswith(".md")


def test_preserves_code_blocks_and_nested_headings():
    markdown = """# Example Document

## Diagnostics

Check the metrics.

### Query

```sql
SELECT * FROM incidents;
# this is not a heading
```
"""

    title, sections = MarkdownParser._parse_markdown(
        markdown, "fallback"
    )

    assert title == "Example Document"
    assert len(sections) == 2
    assert sections[0].heading == "Diagnostics"
    assert sections[1].heading_path == ("Diagnostics", "Query")
    assert "SELECT * FROM incidents;" in sections[1].content
    assert "# this is not a heading" in sections[1].content


def test_rejects_document_outside_data_directory(parser, tmp_path):
    outside_file = tmp_path / "outside.md"
    outside_file.write_text("# Outside", encoding="utf-8")

    with pytest.raises(ValueError):
        parser.parse_file(outside_file)


def test_rejects_missing_file(parser):
    with pytest.raises(FileNotFoundError):
        parser.parse_file("data/runbooks/missing.md")
