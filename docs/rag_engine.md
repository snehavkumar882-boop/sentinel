
# Sentinel — Knowledge Base & RAG Engine

## 1. Overview

Sentinel's Phase 4 implements a local Retrieval-Augmented Generation (RAG) knowledge retrieval layer.

The system ingests historical incident reports and operational runbooks, converts them into section-aware chunks, generates local embeddings, and stores them in a persistent ChromaDB vector database.

It supports semantic retrieval with metadata filtering, configurable top-k results, relevance thresholds, and source traceability.

This phase implements retrieval infrastructure only. It does not generate answers using an LLM or autonomously execute remediation actions.

## 2. Architecture

The ingestion and retrieval pipeline is:

Markdown Documents
        |
        v
Markdown Parser
        |
        v
Parsed Documents and Sections
        |
        v
Section-Aware Chunker
        |
        v
Document Chunks and Metadata
        |
        v
Local Embedding Function
        |
        v
Persistent ChromaDB Vector Store
        |
        v
Semantic Retrieval
        |
        v
Relevance Filtering and Metadata
        |
        v
Traceable Retrieval Results

### Main Components

| Component | Responsibility |
|---|---|
| MarkdownParser | Discovers and parses supported Markdown documents |
| SemanticChunker | Creates deterministic, section-aware chunks |
| VectorStore | Manages persistent vector storage and semantic search |
| KnowledgeBase | Coordinates ingestion, indexing, rebuilding and retrieval |
| Evaluation Script | Measures retrieval quality against manually labelled queries |

## 3. Document Ingestion

Supported source directories:

- `data/historical_incidents/`
- `data/runbooks/`

The parser discovers supported Markdown files and extracts:

- Document title
- Document type
- Document identifier
- Source path
- Heading hierarchy
- Section content
- Incident or runbook identifier where applicable

Document identifiers are deterministic, allowing the same source document to be identified consistently.

## 4. Chunking Strategy

Sentinel uses section-aware chunking.

Configuration:

- Chunk size: 1,200 characters
- Chunk overlap: 150 characters
- Chunk identifiers: Deterministic SHA-256-based identifiers

Each chunk retains its document and section context.

Chunk metadata includes:

- `chunk_id`
- `document_id`
- `document_type`
- `title`
- `source_path`
- `section`
- `section_path`
- `section_level`
- `chunk_index`
- `incident_id` or `runbook_id`, where applicable

The current chunk size is character-based, not token-based.

This approach preserves useful operational context but may split content at less-than-ideal semantic boundaries.

## 5. Embedding and Vector Storage

### Embedding

The implementation uses ChromaDB's default local embedding function.

The embedding model is based on:

`all-MiniLM-L6-v2`

Embeddings are generated locally through ChromaDB's default embedding implementation.

No external embedding API key is required.

### Vector Database

Storage technology: ChromaDB

Collection name: `sentinel_knowledge`

Persistence directory:

`data/vector_store/`

The collection uses cosine distance for similarity-based retrieval.

The vector database is stored separately from the original Markdown source documents.

## 6. Retrieval

The KnowledgeBase provides semantic search with:

- Configurable top-k results
- Optional metadata filters
- Configurable minimum similarity
- Source and section attribution

Default retrieval configuration:

- Top-k: 5
- Minimum similarity: 0.35

ChromaDB cosine distance is converted into a similarity score:

`similarity = 1 - cosine_distance`

The resulting score is a retrieval similarity measure, not a calibrated probability or confidence percentage.

Results below the configured minimum similarity are excluded.

### Retrieval Result Metadata

Each result contains:

- Chunk identifier
- Document identifier
- Document title
- Document type
- Section
- Source path
- Similarity score
- Original distance
- Complete metadata

This allows retrieved information to be traced to its original source document and section.

## 7. Persistence and Index Management

The vector store uses ChromaDB PersistentClient.

Indexed chunks remain available when a new KnowledgeBase instance is created.

The KnowledgeBase supports:

- `ingest()` — Parse and index discovered source documents.
- `search()` — Retrieve relevant chunks.
- `rebuild()` — Clear the existing index and rebuild it from source documents.
- `get_status()` — Report source document count, indexed chunk count, collection and storage location.

Repeated ingestion uses deterministic chunk identifiers and ChromaDB upsert operations to avoid duplicate chunk records.

A full rebuild should be used when source documents are removed or when a complete synchronization with the source directory is required.

## 8. Evaluation Methodology

A manually labelled internal evaluation set was created to test four operational scenarios and one unrelated distractor query.

Operational queries:

1. Database connection pool saturation
2. High API 5xx error rate
3. Memory exhaustion and out-of-memory events
4. Upstream payment gateway timeout

Distractor query:

5. Employee payroll tax filing

Each operational query was assigned expected relevant source documents.

The evaluation script measures:

- Top-1 hit rate
- Top-5 retrieval success rate
- Precision@5
- Distractor rejection rate
- Average query latency
- Top-k retrieval behaviour

### Evaluation Results

| Metric | Observed Result |
|---|---:|
| Operational queries | 4 |
| Top-1 hit rate | 100% |
| Top-5 retrieval success rate | 100% |
| Relevant-result precision@5 | 85% |
| Distractor rejection rate | 100% |
| Average query latency | 191.36 ms |

Precision@5 was calculated from 17 relevant results among 20 returned results across the four operational queries.

The distractor query returned no results above the configured relevance threshold.

The average latency includes the first query's 754.5 ms initial overhead. The remaining operational queries took approximately 48–54 ms each in this run.

Top-k behaviour was also verified for k values of 1, 3 and 5.

### Evaluation Limitations

The evaluation set is small and manually labelled.

The results demonstrate initial retrieval behaviour on the current internal corpus. They do not establish general-purpose retrieval accuracy or production readiness.

Latency measurements are environment-dependent and include cold-start overhead.

A larger benchmark with more operational queries, negative examples and independent relevance judgements is required for stronger conclusions.

## 9. Testing

The Phase 4 implementation includes dedicated tests for:

- Markdown parsing
- Document metadata extraction
- Deterministic chunking
- Chunk metadata preservation
- Vector store indexing
- Semantic retrieval
- Metadata filtering
- Persistent storage
- KnowledgeBase orchestration
- Empty knowledge directories
- Empty queries
- Source traceability
- Index rebuilding
- Invalid configuration values

The complete project test suite must be executed before Phase 4 is marked fully validated.

## 10. Known Limitations

1. Chunk sizing is character-based rather than token-based.
2. Similarity scores are not calibrated probabilities.
3. Retrieval quality is evaluated on a small internal dataset.
4. Semantic retrieval can return related but query-irrelevant chunks.
5. The current implementation does not generate natural-language answers.
6. The system does not perform autonomous remediation.
7. ChromaDB currently emits non-blocking telemetry and dependency deprecation warnings in this environment.
8. The local embedding configuration depends on ChromaDB's default embedding implementation.

## 11. Phase 4 Scope

Completed implementation scope:

- Markdown ingestion
- Structured document parsing
- Section-aware chunking
- Local embedding generation
- Persistent vector storage
- Semantic retrieval
- Metadata filtering
- Relevance threshold filtering
- Source traceability
- Retrieval evaluation

Out of scope:

- Autonomous reasoning agents
- LLM-generated answers
- Automated remediation
- Streamlit dashboard
- Production deployment

## 12. Conclusion

Sentinel's Phase 4 establishes a persistent, locally operated knowledge retrieval foundation.

The implementation successfully indexed six Markdown documents into 34 chunks and retrieved relevant incident and runbook information across the initial evaluation scenarios.

The architecture maintains separation between document parsing, chunking, vector storage and knowledge-base orchestration.

Further evaluation with a larger dataset is necessary before making production-readiness claims.
